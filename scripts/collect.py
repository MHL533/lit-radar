"""Collect new papers from Crossref into the sharded library.

  python scripts/collect.py --year 2021          backfill one publication year (every core journal + keyword queries)
  python scripts/collect.py --daily [--days 6]   pick up papers registered in the last few days (run by the daily workflow)

Only CAS 2025 zone 1-2 journals are kept (scripts/journals_cas2025.csv); fields come from title rules in rules.py.
New papers get author institutions from OpenAlex before they are written.
"""
import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402
import rules  # noqa: E402


def quarters(year, until):
    for m in (1, 4, 7, 10):
        a = dt.date(year, m, 1)
        b = (dt.date(year + (m == 10), (m + 3) % 12 or 12, 1) - dt.timedelta(days=1))
        if a.isoformat() > until:
            return
        yield a.isoformat(), min(b.isoformat(), until)


def run(col, scan_filter, query_windows, rows):
    for n, issn in enumerate(rules.CORE_ISSNS, 1):
        before = len(col.new)
        col.scan_journal(issn, scan_filter)
        print(f"[scan {n}/{len(rules.CORE_ISSNS)}] {issn}: +{len(col.new) - before} (total {len(col.new)})", flush=True)
    for field in rules.FIELDS:
        before = len(col.new)
        for q in rules.QUERIES.get(field, []):
            for flt in query_windows:
                col.query(q, flt, rows=rows)
        print(f"[query] {field}: +{len(col.new) - before} (total {len(col.new)})", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int)
    ap.add_argument("--daily", action="store_true")
    ap.add_argument("--days", type=int, default=6)
    ap.add_argument("--enrich-missing", action="store_true", help="fill OpenAlex institutions / keywords / topics for papers that lack them")
    ap.add_argument("--minutes", type=float, default=20, help="time budget for --enrich-missing")
    ap.add_argument("--reclassify", action="store_true", help="re-run the title rules over the whole library")
    args = ap.parse_args()
    if args.enrich_missing:
        lib.enrich_shards(minutes=args.minutes)
        lib.build_meta()
        return
    if args.reclassify:
        lib.reclassify()
        lib.build_meta()
        return
    today = lib.bj_now().date()
    seen = set(lib.load_all())
    print("library:", len(seen), "papers", flush=True)

    if args.year:
        since = max(f"{args.year}-01-01", lib.SINCE)
        until = min(f"{args.year}-12-31", today.isoformat())
        col = lib.Collector(seen, since, until)
        run(col, f"from-pub-date:{since},until-pub-date:{until}",
            [f"from-pub-date:{a},until-pub-date:{b}" for a, b in quarters(args.year, until)], rows=1000)
    else:
        start = (today - dt.timedelta(days=args.days)).isoformat()
        col = lib.Collector(seen, (today - dt.timedelta(days=400)).isoformat(), (today + dt.timedelta(days=60)).isoformat(),
                            added=lib.bj_now().strftime("%Y-%m-%d %H:%M"))
        flt = f"from-created-date:{start}"
        run(col, flt, [flt], rows=200)

    new = col.new
    from collections import Counter
    print("new papers:", len(new), Counter(g for p in new.values() for g in lib.groups_of(p["f"])), flush=True)
    if not new:
        return
    lib.enrich(list(new.values()))
    lib.save_names(col.names, col.abbr)
    lib.save_records(new)
    if args.daily:
        path = os.path.join(lib.DATA, "latest.json")
        latest = json.load(open(path, encoding="utf-8")).get("papers", []) if os.path.exists(path) else []
        cutoff = (lib.bj_now() - dt.timedelta(days=7)).strftime("%Y-%m-%d %H:%M")
        latest = [p for p in latest if p.get("x", "") >= cutoff and p["id"] not in new] + list(new.values())
        latest.sort(key=lambda p: (p.get("x", ""), p.get("d", "")), reverse=True)
        json.dump({"updated": lib.bj_now().strftime("%Y-%m-%d %H:%M"), "papers": latest}, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    lib.build_meta()


if __name__ == "__main__":
    main()
