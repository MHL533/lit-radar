"""Merge shard files produced by parallel backfill jobs (staging/<job>/data/...) into data/.

Records already in data/ win; missing institutions are filled from the staged copy.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402


def main(stage):
    names, abbr = lib.load_names(), {}
    for job in sorted(glob.glob(os.path.join(stage, "*"))):
        for f, target in (("journal_names.json", names), ("journal_abbr.json", abbr)):
            p = os.path.join(job, "scripts", f)
            if os.path.exists(p):
                for k, v in json.load(open(p, encoding="utf-8")).items():
                    target.setdefault(k, v)
        n = 0
        for path in glob.glob(os.path.join(job, "data", "*", "????-??.json")):
            g, m = path.split(os.sep)[-2], os.path.basename(path)
            dest = os.path.join(lib.DATA, g, m)
            cur = {p["id"]: p for p in lib.read_shard(dest)}
            for p in lib.read_shard(path):
                if p["id"] in cur:
                    for k in ("a", "c"):
                        if k in p and k not in cur[p["id"]]:
                            cur[p["id"]][k] = p[k]
                else:
                    cur[p["id"]] = p
                    n += 1
            lib.write_shard(dest, list(cur.values()))
        print(job, "added", n)
    lib.save_names(names, abbr)
    lib.reclassify()
    meta = lib.build_meta()
    print("total", meta["total"], {g: sum(v.values()) for g, v in meta["shards"].items()})


if __name__ == "__main__":
    main(sys.argv[1])
