"""One-off: convert the old single papers.json into data/<group>/<month>.json shards with multi-label fields.

Hand-curated papers (no "auto" flag) keep their original field first; backfilled ones are re-classified with
the current rules (falling back to their old field when nothing matches).
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402
import rules  # noqa: E402


def norm(s):
    s = (s or "").lower().replace("&amp;", "and").replace("&", "and")
    s = re.sub(r"^the ", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def main():
    old = json.load(open(os.path.join(lib.ROOT, "papers.json"), encoding="utf-8"))
    by_issn = lib.load_journals()
    by_name = {norm(v["cas_name"]): v for v in by_issn.values()}
    alias = {"appliedcatalysisbenvironmentandenergy": "appliedcatalysisbenvironmentandenergy", "angewandtechemieinternationaledition": "angewandtechemieinternationaledition"}
    names = lib.load_names()
    jinfo = {}
    for jname in old["journals"]:
        info = by_name.get(alias.get(norm(jname), norm(jname)))
        if not info:
            print("journal not in CAS table:", jname)
            continue
        names.setdefault(info["issn"], jname)
        jinfo[jname] = info
    lib.save_names(names)
    recs = {}
    changed = 0
    for p in old["papers"]:
        info = jinfo.get(p["journal"])
        f = rules.classify(p["title"], info["cat"] if info else None)
        if not p.get("auto"):
            f = [p["field"]] + [x for x in f if x != p["field"]]
        elif not f:
            f = [p["field"]]
        if f[0] != p["field"]:
            changed += 1
        r = {"id": p["_id"], "t": p["title"], "j": p["journal"], "f": f, "d": p["published"], "doi": p["doi"]}
        if "affils" in p:
            r["a"] = p["affils"]
        if p.get("corr_affils"):
            r["c"] = p["corr_affils"]
        if p.get("summary_zh"):
            r["s"] = p["summary_zh"]
        if p.get("key"):
            r["k"] = 1
        if p.get("source_type", "官方") != "官方" or (p.get("source_url") and p["source_url"] != p.get("url")):
            r["src"] = [p.get("source_type", ""), p.get("source_name", ""), p.get("source_url", "")]
        recs[r["id"]] = r
    print("papers", len(recs), "primary field changed", changed)
    lib.save_records(recs)
    meta = lib.build_meta()
    print({g: sum(v.values()) for g, v in meta["shards"].items()})


if __name__ == "__main__":
    main()
