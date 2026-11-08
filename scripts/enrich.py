"""Fill in author institutions for papers in papers.json using the OpenAlex API.

Only papers without an "affils" field are queried, so the script is cheap to
run after every data update. Writes papers.json back only when something changed.
"""
import json
import time
import urllib.parse
import urllib.request

PATH = "papers.json"
API = "https://api.openalex.org/works"
BATCH = 50


def fetch(dois):
    flt = "doi:" + "|".join("https://doi.org/" + d for d in dois)
    url = API + "?" + urllib.parse.urlencode(
        {"filter": flt, "per-page": BATCH, "select": "doi,authorships", "mailto": "lit-radar@users.noreply.github.com"}
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r).get("results", [])
        except Exception as e:  # network hiccup: retry a couple of times
            print("retry", attempt, e)
            time.sleep(5)
    return []


def main():
    data = json.load(open(PATH, encoding="utf-8"))
    papers = data.get("papers", [])
    todo = [p for p in papers if "affils" not in p and p.get("doi")]
    print(f"{len(todo)} papers need institutions")
    by_doi = {p["doi"].lower(): p for p in todo}
    keys = list(by_doi)
    changed = 0
    for i in range(0, len(keys), BATCH):
        for w in fetch(keys[i:i + BATCH]):
            doi = (w.get("doi") or "").replace("https://doi.org/", "").lower()
            p = by_doi.get(doi)
            if not p:
                continue
            allinst, corr = [], []
            for a in w.get("authorships") or []:
                names = [x.get("display_name") for x in a.get("institutions") or [] if x.get("display_name")]
                for n in names:
                    if n not in allinst:
                        allinst.append(n)
                if a.get("is_corresponding"):
                    for n in names:
                        if n not in corr:
                            corr.append(n)
            p["affils"] = allinst[:8]
            p["corr_affils"] = corr[:4]
            changed += 1
        time.sleep(1)
    print(f"filled {changed}")
    if changed:
        json.dump(data, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
