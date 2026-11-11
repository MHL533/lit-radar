"""Mirror the library into the Supabase `papers` table (see supabase/papers.sql) so the web page can search all of it.

  SUPABASE_SERVICE_ROLE_KEY=... python scripts/sync_db.py          upsert shards changed since the last sync
  SUPABASE_SERVICE_ROLE_KEY=... python scripts/sync_db.py --full   upsert everything and delete rows no longer in the library

The project URL is read from config.js. Without the key the script does nothing (so workflows still pass before it is set up).
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402
import rules  # noqa: E402

STATE = os.path.join(lib.DATA, "db-sync.json")


def config():
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    url = os.environ.get("SUPABASE_URL", "").strip()
    if not url:
        m = re.search(r'supabaseUrl:\s*"([^"]+)"', open(os.path.join(lib.ROOT, "config.js"), encoding="utf-8").read())
        url = m.group(1) if m else ""
    return url.rstrip("/"), key


def call(url, key, method="POST", body=None, headers=None, tries=5):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    h = {"apikey": key, "Content-Type": "application/json", **(headers or {})}
    if not key.startswith("sb_"):  # legacy JWT service_role key; new sb_secret_ keys go in the apikey header only
        h["Authorization"] = "Bearer " + key
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=data, method=method, headers=h)
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            print("  HTTP", e.code, msg, flush=True)
            if e.code in (400, 401, 403, 404, 409):
                raise
        except Exception as e:
            print("  retry", attempt, str(e)[:150], flush=True)
        time.sleep(5 * (attempt + 1))
    raise RuntimeError("Supabase request failed: " + url)


def short_authors(au):
    """First three authors plus the last one (often the corresponding author) keep the rows small."""
    return au if len(au) <= 4 else au[:3] + au[-1:]


def refresh_counts(url, key, shards):
    """Per-group monthly counts, computed here and written to paper_month_counts (cheap for the database)."""
    counts, seen = {}, set()
    for path in shards:
        g, m = path.split(os.sep)[-2], os.path.basename(path)[:7]
        ps = lib.read_shard(path)
        counts[(g, m)] = len(ps)
        for p in ps:
            if p["id"] not in seen:
                seen.add(p["id"])
                counts[("*", p["d"][:7])] = counts.get(("*", p["d"][:7]), 0) + 1
    rows = [{"grp": g, "month": m, "n": n} for (g, m), n in counts.items()]
    call(url + "/rest/v1/paper_month_counts?grp=neq.__none__", key, method="DELETE", headers={"Prefer": "return=minimal"})
    for i in range(0, len(rows), 500):
        call(url + "/rest/v1/paper_month_counts", key, body=rows[i:i + 500], headers={"Prefer": "return=minimal"})


def row(p, journals, kz):
    j = journals.get(p["j"], {})
    zone = (j.get("cas_zone") or "")[:1]
    kws = p.get("kw", [])
    return {
        "id": p["id"], "doi": p["doi"], "title": p["t"], "title_zh": p.get("tz"), "journal": p["j"], "journal_abbr": j.get("abbr"),
        "cas_zone": int(zone) if zone.isdigit() else None, "impact_factor": j.get("if"), "published": p["d"],
        "fields": p["f"], "groups": lib.groups_of(p["f"]), "keywords": kws, "keywords_zh": [kz.get(k, "") for k in kws],
        "authors": short_authors(p.get("au", [])), "author_count": p.get("an") or len(p.get("au", [])) or None,
        "affils": p.get("a", [])[:3], "corr_affils": p.get("c", [])[:1], "first_affil": (p.get("a") or [None])[0],
        "summary_zh": p.get("s"), "is_key": bool(p.get("k")), "has_abstract": bool(p.get("hb")),
        "added": (p["x"].replace(" ", "T") + ":00+08:00") if p.get("x") else None,
        "synced_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()
    url, key = config()
    if os.path.exists(os.path.join(lib.ROOT, "supabase", "SYNC_PAUSED")):
        print("Database sync paused (supabase/SYNC_PAUSED exists); skipping.")
        return
    if not url or not key:
        print("Supabase not configured (SUPABASE_SERVICE_ROLE_KEY secret missing); skipping database sync.")
        return
    meta = json.load(open(os.path.join(lib.DATA, "meta.json"), encoding="utf-8"))
    journals, kz = meta["journals"], lib.kw_zh()
    state = {} if args.full or not os.path.exists(STATE) else json.load(open(STATE, encoding="utf-8"))
    shards = lib.all_shards()
    hashes = {os.path.relpath(p, lib.DATA): hashlib.md5(open(p, "rb").read()).hexdigest() for p in shards}
    hashes["kw_zh"] = hashlib.md5(json.dumps(kz, sort_keys=True).encode()).hexdigest()
    hashes["journals"] = hashlib.md5(json.dumps(journals, sort_keys=True).encode()).hexdigest()
    # keyword translations are embedded in each shard, so a changed vocabulary already changes the affected shard hashes
    everything = args.full or state.get("journals") != hashes["journals"]
    todo = [p for p in shards if everything or state.get(os.path.relpath(p, lib.DATA)) != hashes[os.path.relpath(p, lib.DATA)]]
    print(f"shards to sync: {len(todo)} / {len(shards)}", flush=True)
    sent, seen, batch = set(), set(), []
    endpoint = url + "/rest/v1/papers?on_conflict=id"
    hdr = {"Prefer": "resolution=merge-duplicates,return=minimal"}

    def flush():
        if batch:
            call(endpoint, key, body=batch, headers=hdr)
            batch.clear()

    for n, path in enumerate(todo, 1):
        for p in lib.read_shard(path):
            if p["id"] in sent:
                continue
            sent.add(p["id"])
            batch.append(row(p, journals, kz))
            if len(batch) >= 500:
                flush()
        flush()
        state[os.path.relpath(path, lib.DATA)] = hashes[os.path.relpath(path, lib.DATA)]
        if n % 50 == 0:
            print(f"  {n}/{len(todo)} shards, {len(sent)} papers", flush=True)
    state["kw_zh"], state["journals"] = hashes["kw_zh"], hashes["journals"]
    if args.full:  # drop rows that left the library (re-classified away or removed)
        library = {p["id"] for path in shards for p in lib.read_shard(path)}
        last = ""
        while True:
            ids = call(url + "/rest/v1/papers?select=id&order=id&limit=1000&id=gt." + urllib.request.quote(last, safe=""), key, method="GET")
            if not ids:
                break
            seen.update(r["id"] for r in ids)
            last = ids[-1]["id"]
        gone = sorted(seen - library)
        for i in range(0, len(gone), 200):
            chunk = ",".join('"' + g.replace('"', '') + '"' for g in gone[i:i + 200])
            call(url + "/rest/v1/papers?id=in.(" + urllib.request.quote(chunk, safe=",()\"") + ")", key, method="DELETE")
        print("deleted stale rows:", len(gone))
    if sent or args.full:
        refresh_counts(url, key, shards)
    json.dump(state, open(STATE, "w", encoding="utf-8"), indent=0, sort_keys=True)
    print(f"synced {len(sent)} papers")


if __name__ == "__main__":
    main()
