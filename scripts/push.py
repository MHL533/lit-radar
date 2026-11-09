"""Helper for the push task (the Claude scheduled task that sends the membrane digest).

  python scripts/push.py pending              JSON of papers added since the last push: membrane papers in full, other groups as counts
  python scripts/push.py annotate notes.json  write Chinese summaries / key flags back: notes.json = [{"id": ..., "s": "...", "k": 1}, ...]
  python scripts/push.py done                 record the current Beijing time as the last push
"""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402
import rules  # noqa: E402

STATE = os.path.join(lib.DATA, "push-state.json")
LATEST = os.path.join(lib.DATA, "latest.json")
CORE = {"pa-nf", "cat-mem", "cat-ceramic", "heo", "ml-mem"}


def load(path, default):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else default


def pending():
    now = lib.bj_now()
    last = load(STATE, {}).get("last_push") or (now - dt.timedelta(hours=12)).strftime("%Y-%m-%d %H:%M")
    latest = load(LATEST, {"papers": []})
    meta = load(os.path.join(lib.DATA, "meta.json"), {})
    journals = meta.get("journals", {})
    upd = latest.get("updated") or meta.get("updated") or ""
    stale = (now - dt.datetime.strptime(upd, "%Y-%m-%d %H:%M")).total_seconds() / 3600 if upd else None
    new = [p for p in latest["papers"] if p.get("x", "") > last]
    mem, others = [], {}
    names = {g: n for g, n, _, _ in rules.GROUPS}
    for p in new:
        gs = lib.groups_of(p["f"])
        if rules.PUSH_GROUP in gs:
            j = journals.get(p["j"], {})
            mem.append({"id": p["id"], "title": p["t"], "journal": p["j"], "abbr": j.get("abbr", p["j"]), "zone": j.get("cas_zone", ""),
                        "if": j.get("if"), "date": p["d"], "doi": p["doi"], "fields": [rules.FIELDS.get(f, f) for f in p["f"] if lib.groups_of([f]) == [rules.PUSH_GROUP]],
                        "core": bool(CORE & set(p["f"])), "summary": p.get("s", ""), "key": bool(p.get("k")), "keywords": p.get("kw", []), "affils": p.get("c") or p.get("a", [])[:3]})
        for g in gs:
            if g != rules.PUSH_GROUP:
                others[names[g]] = others.get(names[g], 0) + 1
    print(json.dumps({"now": now.strftime("%Y-%m-%d %H:%M"), "last_push": last, "data_updated": upd,
                      "hours_since_update": round(stale, 1) if stale is not None else None,
                      "membrane": sorted(mem, key=lambda x: (not x["key"], not x["core"], x["date"]), reverse=False),
                      "membrane_count": len(mem), "other_groups": others}, ensure_ascii=False, indent=1))


def annotate(path):
    notes = {n["id"]: n for n in json.load(open(path, encoding="utf-8"))}
    latest = load(LATEST, {"papers": []})
    recs = {}
    for p in latest["papers"]:
        if p["id"] in notes:
            n = notes[p["id"]]
            if n.get("s"):
                p["s"] = n["s"]
            if n.get("k"):
                p["k"] = 1
            recs[p["id"]] = p
    allp = lib.load_all()
    for k, p in recs.items():  # update the library copies (keeping their institutions / keywords)
        if k in allp:
            allp[k].update({x: p[x] for x in ("s", "k") if x in p})
            recs[k] = allp[k]
    lib.save_records(recs)
    json.dump(latest, open(LATEST, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("annotated", len(recs))


def done():
    json.dump({"last_push": lib.bj_now().strftime("%Y-%m-%d %H:%M")}, open(STATE, "w", encoding="utf-8"))
    print("ok")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pending"
    {"pending": pending, "done": done}.get(cmd, lambda: annotate(sys.argv[2]))()
