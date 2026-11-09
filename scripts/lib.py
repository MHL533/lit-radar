"""Shared helpers for the literature library: journal table, sharded storage, Crossref search, OpenAlex enrichment.

Storage layout (served as static files by GitHub Pages):
  data/meta.json                     fields, groups, journals, per-group monthly counts, update time
  data/<group>/<YYYY-MM>.json        {"papers": [record, ...]} newest first; a paper is stored in every group it belongs to
  data/latest.json                   papers added by the daily update during the last 7 days (for the push task)

Compact record keys:
  id  stable id from the DOI        t  title           j  journal display name     f  [field, ...] (first = primary)
  d   publication date YYYY-MM-DD   doi                a  [institutions]           c  [corresponding institutions]
  s   Chinese summary (optional)    k  1 = key paper   src [type, name, url] when not the publisher page
  x   time added by the daily update (Beijing time, optional)
"""
import csv
import datetime as dt
import glob
import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request

import rules

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
MAILTO = "lit-radar@users.noreply.github.com"
UA = f"lit-radar/2.0 (https://mhl533.github.io/lit-radar/; mailto:{MAILTO})"
SINCE = "2020-01-01"


def bj_now():
    return dt.datetime.utcnow() + dt.timedelta(hours=8)


# ---------------------------------------------------------------- journals
def load_journals():
    """ISSN -> info for every CAS 2025 zone 1-2 journal in the relevant categories."""
    by_issn = {}
    with open(os.path.join(ROOT, "scripts", "journals_cas2025.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            issns = r["issn"].split("|")
            info = {"cas_name": r["journal"], "cat": r["category"], "zone": r["cas_zone"], "top": r["top"] == "1",
                    "if": float(r["if_jcr2025"]) if re.fullmatch(r"[\d.]+", r["if_jcr2025"]) else None, "issn": issns[0], "issns": issns}
            for i in issns:
                by_issn[i] = info
    return by_issn


def load_names():
    p = os.path.join(ROOT, "scripts", "journal_names.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def save_names(names, abbr=None):
    json.dump(dict(sorted(names.items())), open(os.path.join(ROOT, "scripts", "journal_names.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if abbr:
        p = os.path.join(ROOT, "scripts", "journal_abbr.json")
        cur = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
        for k, v in abbr.items():
            cur.setdefault(k, v)
        json.dump(dict(sorted(cur.items())), open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def title_case(name):
    if name.upper() != name:
        return name
    small = {"of", "and", "the", "in", "for", "on", "a", "an", "to", "at"}
    words = name.lower().split()
    return " ".join(w if (i and w in small) else w[:1].upper() + w[1:] for i, w in enumerate(words))


# ---------------------------------------------------------------- storage
def shard_path(group, month):
    return os.path.join(DATA, group, month + ".json")


# Shard format v3: repeated strings are stored once per file.
#   {"v":3, "J":[journals], "I":[institutions], "K":[keywords], "T":[topics], "papers":[...]}
#   in each paper j is an index into J; a / c into I; kw into K; tp (OpenAlex topic, subfield) into T; id is derived from the DOI.
INTERN = (("j", "J", False), ("a", "I", True), ("c", "I", True), ("kw", "K", True), ("tp", "T", True))


_KWZH = None


def kw_zh():
    """English keyword -> Chinese, shared vocabulary in data/kw_zh.json (filled by translate.py)."""
    global _KWZH
    if _KWZH is None:
        p = os.path.join(DATA, "kw_zh.json")
        _KWZH = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    return _KWZH


def read_shard(path):
    try:
        data = json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        return []
    papers = data.get("papers", [])
    if data.get("v") != 3:
        return papers
    out = []
    for p in papers:
        p = dict(p)
        for key, table, many in INTERN:
            if key in p:
                p[key] = [data[table][i] for i in p[key]] if many else data[table][p[key]]
        p["id"] = pid(p["doi"])
        out.append(p)
    return out


def write_shard(path, papers):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    papers = sorted(papers, key=lambda p: (p.get("d", ""), p["id"]), reverse=True)
    freq = {}
    for p in papers:
        for key, table, many in INTERN:
            if key in p:
                for v in (p[key] if many else [p[key]]):
                    freq.setdefault(table, {}).setdefault(v, 0)
                    freq[table][v] += 1
    tables = {t: sorted(c, key=lambda v: (-c[v], v)) for t, c in freq.items()}
    index = {t: {v: i for i, v in enumerate(vs)} for t, vs in tables.items()}
    rows = []
    for p in papers:
        q = {k: v for k, v in p.items() if k != "id"}
        for key, table, many in INTERN:
            if key in q:
                q[key] = [index[table][v] for v in q[key]] if many else index[table][q[key]]
        rows.append(json.dumps(q, ensure_ascii=False, separators=(",", ":")))
    head = {"v": 3, **{t: tables.get(t, []) for t in ("J", "I", "K", "T")}}
    kz = kw_zh()
    if kz and head["K"]:
        head["KZ"] = [kz.get(k, "") for k in head["K"]]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(head, ensure_ascii=False, separators=(",", ":"))[:-1] + ',"papers":[\n' + ",\n".join(rows) + "\n]}\n")


def all_shards():
    return sorted(glob.glob(os.path.join(DATA, "*", "????-??.json")))


def load_all():
    """id -> record across every shard (one copy per paper)."""
    out = {}
    for path in all_shards():
        for p in read_shard(path):
            out.setdefault(p["id"], p)
    return out


def groups_of(fields):
    seen = []
    for f in fields:
        g = rules.GROUP_OF.get(f)
        if g and g not in seen:
            seen.append(g)
    return seen


def save_records(records, months=None):
    """Write records (id -> record) into their group/month shards, replacing earlier copies of the same ids.

    Only shards whose month is in `months` (or touched by a record) are rewritten.
    """
    by_shard = {}
    for p in records.values():
        for g in groups_of(p["f"]):
            by_shard.setdefault((g, p["d"][:7]), []).append(p)
    touched = set(by_shard)
    if months is not None:
        for path in all_shards():
            g, m = path.split(os.sep)[-2], os.path.basename(path)[:7]
            if m in months:
                touched.add((g, m))
    ids = set(records)
    for g, m in sorted(touched):
        path = shard_path(g, m)
        keep = [p for p in read_shard(path) if p["id"] not in ids]
        new = keep + by_shard.get((g, m), [])
        if new:
            write_shard(path, new)
        elif os.path.exists(path):
            os.remove(path)


def pid(doi):
    return re.sub(r"[^a-z0-9_.~:@+-]", "_", doi.lower())


def build_meta():
    p = os.path.join(ROOT, "scripts", "journal_abbr.json")
    abbr = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    by_issn = load_journals()
    names = load_names()
    name_issn = {v: k for k, v in names.items()}
    counts, used, hashes = {}, {}, {}
    for path in all_shards():
        g, m = path.split(os.sep)[-2], os.path.basename(path)[:7]
        ps = read_shard(path)
        counts.setdefault(g, {})[m] = len(ps)
        hashes.setdefault(g, {})[m] = hashlib.md5(open(path, "rb").read()).hexdigest()[:8]
        for p in ps:
            used[p["j"]] = used.get(p["j"], 0) + 1
    journals = {}
    for name in sorted(used):
        issn = name_issn.get(name)
        info = by_issn.get(issn) if issn else None
        if info:
            journals[name] = {"abbr": rules.ABBR.get(info["issn"]) or abbr.get(info["issn"]) or name,
                              "cas_zone": info["zone"] + "区", "if": info["if"], "top": info["top"], "cat": info["cat"]}
        else:
            journals[name] = {"abbr": name}
    meta = {
        "updated": bj_now().strftime("%Y-%m-%d %H:%M"),
        "since": SINCE[:7],
        "fields": rules.FIELDS,
        "groups": [{"id": g, "name": n, "fields": [f for f, *_ in fs], **({"default": True} if g == rules.DEFAULT_GROUP else {})}
                   for g, n, _, fs in rules.GROUPS],
        "journals": journals,
        "shards": {g: dict(sorted(v.items(), reverse=True)) for g, v in sorted(counts.items())},
        "hash": hashes,
        "total": len(load_all()),
    }
    json.dump(meta, open(os.path.join(DATA, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    return meta


def reclassify():
    """Re-run the title rules over the whole library (hand-curated papers, which carry a Chinese summary, keep their first field).

    Papers that no longer match any field are dropped. All shards are rewritten.
    """
    by_issn = load_journals()
    cat = {name: by_issn[i]["cat"] for i, name in load_names().items() if i in by_issn}
    recs = load_all()
    out, dropped = {}, 0
    for k, p in recs.items():
        p["j"] = re.sub(r"\s+", " ", p["j"]).strip()
        f = rules.classify(p["t"], cat.get(p["j"]), p.get("kw"))
        if p.get("s") or p.get("k"):
            f = [p["f"][0]] + [x for x in f if x != p["f"][0]]
        if not f:
            dropped += 1
            continue
        p["f"] = f
        out[k] = p
    for path in all_shards():
        os.remove(path)
    save_records(out)
    print(f"reclassified {len(out)} papers, dropped {dropped}")


# ---------------------------------------------------------------- Crossref
SELECT = "DOI,title,container-title,short-container-title,ISSN,published-online,published-print,issued,created,type"


def get_json(url, tries=5):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except Exception as e:  # network hiccup or rate limit: back off and retry
            print("  retry", attempt, str(e)[:120], flush=True)
            if getattr(e, "code", None) in (400, 404):
                return None
            time.sleep(8 * (attempt + 1))
    return None


def crossref_pages(base, params, max_items=None):
    """Yield Crossref items, following the cursor."""
    params = dict(params, cursor="*", mailto=MAILTO, select=SELECT)
    n = 0
    while True:
        res = get_json(base + "?" + urllib.parse.urlencode(params))
        time.sleep(0.25)
        if not res:
            return
        items = res["message"].get("items", [])
        for it in items:
            yield it
        n += len(items)
        cur = res["message"].get("next-cursor")
        if not items or not cur or (max_items and n >= max_items) or len(items) < params.get("rows", 20):
            return
        params["cursor"] = cur


def date_of(it):
    best = None
    for k in ("published-online", "published-print", "issued", "created"):
        parts = (it.get(k) or {}).get("date-parts", [[None]])[0]
        if not parts or parts[0] is None:
            continue
        s = "-".join([str(parts[0])] + [f"{x:02d}" for x in parts[1:3]])
        if len(s) == 10:
            return s
        best = best or s
    if best:
        return (best + "-01-01")[:10] if len(best) == 4 else best + "-01"
    return None


def source_name(doi):
    return ("ScienceDirect" if doi.startswith("10.1016") else "Nature" if doi.startswith("10.1038") else
            "ACS Publications" if doi.startswith("10.1021") else "Wiley Online Library" if doi.startswith("10.1002") else
            "RSC Publishing" if doi.startswith("10.1039") else "Science" if doi.startswith("10.1126") else
            "Cell Press" if doi.startswith("10.1016/j.joule") else "Copernicus" if doi.startswith("10.5194") else
            "AGU" if doi.startswith("10.1029") else "Springer" if doi.startswith("10.1007") else "Crossref")


class Collector:
    """Turns Crossref items into classified records, skipping DOIs already in the library."""

    def __init__(self, seen, since, until, added=None):
        self.by_issn = load_journals()
        self.names = load_names()
        self.seen = seen
        self.since, self.until = since, until
        self.added = added
        self.new = {}
        self.abbr = {}

    def take(self, it):
        if it.get("type") not in (None, "journal-article"):
            return
        doi = (it.get("DOI") or "").strip()
        key = pid(doi)
        if not doi or key in self.seen or key in self.new:
            return
        info = next((self.by_issn[i] for i in it.get("ISSN") or [] if i in self.by_issn), None)
        if not info:
            return
        title = re.sub(r"<[^>]+>", "", (it.get("title") or [""])[0])
        title = re.sub(r"\s+", " ", title).strip()
        fields = rules.classify(title, info["cat"])
        if not fields:
            return
        d = date_of(it)
        if not d or d < self.since or d > self.until:
            return
        issn = info["issn"]
        if issn not in self.names:
            ct = (it.get("container-title") or [""])[0].strip()
            self.names[issn] = title_case(re.sub(r"\s+", " ", ct or info["cas_name"]).strip())
        sct = (it.get("short-container-title") or [""])
        if sct and sct[0] and issn not in self.abbr:
            self.abbr[issn] = sct[0]
        rec = {"id": key, "t": title, "j": self.names[issn], "f": fields, "d": d, "doi": doi}
        if self.added:
            rec["x"] = self.added
        self.new[key] = rec

    def scan_journal(self, issn, date_filter):
        issns = self.by_issn[issn]["issns"] if issn in self.by_issn else [issn]
        flt = ",".join("issn:" + i for i in issns) + "," + date_filter + ",type:journal-article"
        for it in crossref_pages("https://api.crossref.org/works", {"filter": flt, "rows": 1000}):
            self.take(it)

    def query(self, q, date_filter, rows=1000):
        for it in crossref_pages("https://api.crossref.org/works", {"query.bibliographic": q, "filter": date_filter + ",type:journal-article", "rows": rows}, max_items=rows):
            self.take(it)


# ---------------------------------------------------------------- OpenAlex institutions
def enrich_shards(minutes=20):
    """Enrich papers lacking OpenAlex data shard by shard (newest first) within a time budget; progress is written as it goes."""
    deadline = time.time() + minutes * 60
    cache = {}
    keys = ("a", "c", "kw", "tp", "au", "an", "hb")
    done = 0
    for path in sorted(all_shards(), key=lambda x: os.path.basename(x), reverse=True):
        if time.time() > deadline:
            break
        recs = read_shard(path)
        for p in recs:
            hit = cache.get(p.get("doi", "").lower())
            if hit and needs_enrich(p):
                p.update(hit)
        todo = [p for p in recs if needs_enrich(p)]
        if not todo:
            continue
        enrich(todo, deadline=deadline)
        for p in todo:
            if not needs_enrich(p):
                cache[p["doi"].lower()] = {k: p[k] for k in keys if k in p}
                done += 1
        write_shard(path, recs)
        ABSTRACTS.flush()
        print(f"  {path[len(DATA) + 1:]}: {len(todo)} to enrich, total enriched {done}", flush=True)
    left = sum(1 for path in all_shards() for p in read_shard(path) if needs_enrich(p))
    print(f"enriched {done}; still missing {left}", flush=True)


def needs_enrich(p):
    return p.get("doi") and ("a" not in p or "kw" not in p or "au" not in p)


def crossref_abstracts(recs):
    """Second source for abstracts (publishers that deposit them with Crossref; Elsevier does not)."""
    recs = [p for p in recs if p.get("doi") and not p["doi"].startswith("10.1016/")]
    for i in range(0, len(recs), 40):
        part = {p["doi"].lower(): p for p in recs[i:i + 40]}
        url = "https://api.crossref.org/works?" + urllib.parse.urlencode({"filter": ",".join("doi:" + d for d in part), "select": "DOI,abstract", "rows": 40, "mailto": MAILTO})
        res = get_json(url, tries=2) or {}
        for it in (res.get("message") or {}).get("items", []):
            p = part.get((it.get("DOI") or "").lower())
            ab = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", it.get("abstract") or "")).strip()
            ab = re.sub(r"^(abstract|summary)[:.\s]+", "", ab, flags=re.I)
            if p is not None and len(ab) > 80:
                ABSTRACTS.put(p["id"], ab)
                p["hb"] = 1
        time.sleep(0.2)


def abstract_text(inv):
    """Rebuild an abstract from OpenAlex's inverted index."""
    if not inv:
        return ""
    pos = sorted((i, w) for w, idx in inv.items() for i in idx)
    text = " ".join(w for _, w in pos)
    text = re.sub(r"^(abstract|summary)[:.\s]+", "", text, flags=re.I).strip()
    return text if len(text) > 80 else ""


class AbstractStore:
    """Abstracts live outside the list shards: data/abs/<3 hex of md5(id)>.json = {id: [english, chinese]}."""

    def __init__(self):
        self.cache, self.dirty = {}, set()

    @staticmethod
    def bucket(pid_):
        h = 0x811C9DC5  # FNV-1a, same as absBucket() in index.html
        for b in pid_.encode():
            h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
        return format(h & 0xFFF, "03x")

    def path(self, b):
        return os.path.join(DATA, "abs", b + ".json")

    def load(self, b):
        if b not in self.cache:
            p = self.path(b)
            self.cache[b] = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
        return self.cache[b]

    def get(self, pid_):
        return self.load(self.bucket(pid_)).get(pid_)

    def put(self, pid_, en=None, zh=None):
        b = self.bucket(pid_)
        cur = self.load(b).get(pid_) or ["", ""]
        if en:
            cur[0] = en
        if zh:
            cur[1] = zh
        self.cache[b][pid_] = cur
        self.dirty.add(b)

    def flush(self):
        os.makedirs(os.path.join(DATA, "abs"), exist_ok=True)
        for b in sorted(self.dirty):
            with open(self.path(b), "w", encoding="utf-8") as fh:
                json.dump(dict(sorted(self.cache[b].items())), fh, ensure_ascii=False, separators=(",", ":"))
        n = len(self.dirty)
        self.dirty.clear()
        return n


ABSTRACTS = AbstractStore()


def enrich(records, batch=50, deadline=None):
    """Fill institutions (a / c), keywords (kw) and topic (tp = [topic, subfield]) from OpenAlex where missing."""
    todo = {p["doi"].lower(): p for p in records if needs_enrich(p)}
    keys = list(todo)
    filled = 0
    for i in range(0, len(keys), batch):
        flt = "doi:" + "|".join("https://doi.org/" + d for d in keys[i:i + batch])
        if deadline and time.time() > deadline:
            print("  time budget reached; stopping enrichment", flush=True)
            break
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode({"filter": flt, "per-page": batch, "select": "doi,authorships,keywords,primary_topic,abstract_inverted_index", "mailto": MAILTO})
        res = get_json(url, tries=3) or {}
        for w in res.get("results", []):
            p = todo.get((w.get("doi") or "").replace("https://doi.org/", "").lower())
            if not p:
                continue
            allinst, corr = [], []
            auth = [(a.get("author") or {}).get("display_name") for a in w.get("authorships") or []]
            auth = [x for x in auth if x]
            p["au"] = auth[:12]
            if len(auth) > 12:
                p["an"] = len(auth)
            ab = abstract_text(w.get("abstract_inverted_index"))
            if ab:
                ABSTRACTS.put(p["id"], ab)
                p["hb"] = 1
            for a in w.get("authorships") or []:
                names = [x.get("display_name") for x in a.get("institutions") or [] if x.get("display_name")]
                for n in names:
                    if n not in allinst:
                        allinst.append(n)
                if a.get("is_corresponding"):
                    for n in names:
                        if n not in corr:
                            corr.append(n)
            p["a"] = allinst[:8]
            if corr:
                p["c"] = corr[:4]
            p["kw"] = [k["display_name"] for k in sorted(w.get("keywords") or [], key=lambda k: -(k.get("score") or 0))
                       if k.get("display_name") and (k.get("score") or 0) >= 0.3][:6]
            t = w.get("primary_topic") or {}
            if t.get("display_name"):
                p["tp"] = [t["display_name"], (t.get("subfield") or {}).get("display_name", "")]
            filled += 1
        crossref_abstracts([todo[d] for d in keys[i:i + batch] if not todo[d].get("hb")])
        old = (dt.date.today() - dt.timedelta(days=45)).isoformat()
        for d in keys[i:i + batch]:  # not in OpenAlex: stop asking for older papers
            if res and needs_enrich(todo[d]) and todo[d].get("d", "") < old:
                todo[d].setdefault("a", [])
                todo[d].setdefault("kw", [])
                todo[d].setdefault("au", [])
        time.sleep(0.15)
        if (i // batch) % 50 == 0:
            print(f"  institutions {i + batch}/{len(keys)} (filled {filled})", flush=True)
    return filled
