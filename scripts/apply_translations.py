"""Merge translation results (from scripts/translate.py, possibly run as parallel jobs) into the library.

  python scripts/apply_translations.py staging/     # folder holding titles-*.json, keywords-*.json and */data/abs/*.json
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402


def apply(results, abs_files=()):
    titles = {k: v for d in results.get("titles", []) for k, v in d.items()}
    kws = {k: v for d in results.get("keywords", []) for k, v in d.items()}
    if kws:
        kz = lib.kw_zh()
        kz.update(kws)
        json.dump(dict(sorted(kz.items())), open(os.path.join(lib.DATA, "kw_zh.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print("keywords added:", len(kws))
    if titles or kws:
        allp = lib.load_all()
        changed = {}
        for k, z in titles.items():
            if k in allp:
                allp[k]["tz"] = z
                changed[k] = allp[k]
        # new keyword translations are embedded per shard (KZ table), so every shard is rewritten then
        lib.save_records(allp if kws else changed)
        latest_p = os.path.join(lib.DATA, "latest.json")
        if titles and os.path.exists(latest_p):
            latest = json.load(open(latest_p, encoding="utf-8"))
            for p in latest.get("papers", []):
                if p["id"] in titles:
                    p["tz"] = titles[p["id"]]
            json.dump(latest, open(latest_p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print("titles applied:", len(changed))
    n = 0
    for f in abs_files:
        b = os.path.basename(f)[:3]
        cur = lib.ABSTRACTS.load(b)
        for k, (en, zh) in json.load(open(f, encoding="utf-8")).items():
            have = cur.get(k) or ["", ""]
            if zh and not have[1]:
                lib.ABSTRACTS.put(k, en=have[0] or en, zh=zh)
                n += 1
    lib.ABSTRACTS.flush()
    if abs_files:
        print("abstract translations applied:", n)
    lib.build_meta()


def main(stage):
    res = {"titles": [], "keywords": []}
    for f in glob.glob(os.path.join(stage, "**", "titles-*.json"), recursive=True):
        res["titles"].append(json.load(open(f, encoding="utf-8")))
    for f in glob.glob(os.path.join(stage, "**", "keywords-*.json"), recursive=True):
        res["keywords"].append(json.load(open(f, encoding="utf-8")))
    apply(res, glob.glob(os.path.join(stage, "**", "abs", "*.json"), recursive=True))


if __name__ == "__main__":
    main(sys.argv[1])
