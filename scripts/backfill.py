"""Backfill papers.json from Crossref for every configured field.

Run by .github/workflows/backfill.yml. Settings live in scripts/backfill.json:
  {"since": "2025-11-08", "until": "2026-11-08", "own_until": "2025-12-31"}
"own_until" caps the date range for the hand-curated fields in CURATED, whose 2026 papers
were reviewed by hand and must not be re-added automatically.

Papers are kept only if the journal is listed in papers.json["journals"] (CAS zone 1-2 verified)
and the title passes the field's include/exclude rules. Backfilled entries have no Chinese summary.
"""
import datetime as dt
import json
import re
import time
import urllib.parse
import urllib.request

DATA = "papers.json"
CONF = "scripts/backfill.json"
MAILTO = "lit-radar@users.noreply.github.com"

I = re.I
NOISE = re.compile(r"corrigendum|erratum|retraction|retracted|expression of concern|issue information|cover image|front cover|back cover|inside cover|editorial board|graphical abstract|^correction|correction to|^addendum|quantum material|moir[eé]|vertical distribution|atmospheric (oxidation|chemistry)|ozone pollution|tropospher|stratospher|smog|emission inventor", I)
ENERGY = re.compile(r"batter(y|ies)|electrolys|water splitting|hydrogen evolution|oxygen evolution|oxygen reduction|\bHER\b|\bOER\b|\bORR\b|CO2 (electro)?reduction|CO2RR|nitrate reduction|ammonia (synthesis|production)|nitrogen reduction|N2 fixation|supercapacitor|fuel cell|hydrogen storage|lithium|sodium-ion|zinc-air|H2O2 (production|synthesis)|hydrogen peroxide (production|synthesis)|solar cell|tumou?r|cancer|wound|bacteria-infected|anticancer|drug delivery|sensor for|biosens", I)
AOP = re.compile(r"peroxymonosulfate|persulfate|peroxydisulfate|\bPMS\b|\bPDS\b|ozon|fenton|advanced oxidation|\bAOPs?\b|hydroxyl radical|singlet oxygen|sulfate radical|high-valent|degrad|mineraliz|VOCs?\b|volatile organic|toluene|formaldehyde|benzene|mercaptan|odou?r|decontamination|oxidation of (organic|pollutant|antibiotic)|catalytic oxidation", I)
WATERCTX = re.compile(r"water|wastewater|pollutant|contaminant|antibiotic|micropollutant|\bdyes?\b|pharmaceutical|phenol|bisphenol|sulfamethoxazole|tetracycline|ciprofloxacin|PFAS|organic", I)
GASCTX = re.compile(r"VOCs?\b|volatile organic|toluene|formaldehyde|benzene|xylene|odou?r|mercaptan|methyl sulfide|H2S|gaseous|indoor air|air purification|exhaust|chlorinated (VOC|hydrocarbon)|CVOC|ethyl acetate|propane|methane combustion|soot", I)
MP = re.compile(r"micro-?plastic|nano-?plastic", I)
MEM = re.compile(r"membrane|nanofiltration|reverse osmosis|forward osmosis|ultrafiltration|microfiltration|pervaporation|electrodialysis", I)
# biological / energy-device membranes are not separation membranes
NOTSEP = re.compile(r"cell membrane|plasma membrane|mitochondri|membrane protein|lipid (bi)?layer|liposom|membrane potential|erythrocyte|bacterial (outer )?membrane|membrane-bound|vesicle|thylakoid|proton exchange membrane|PEM fuel|membrane electrode assembly|fuel cell|electrolyzer|electrolyser|water electrolysis|redox flow batter|lithium.ion batter|separator for", I)
ML = re.compile(r"machine learning|deep learning|neural network|artificial intelligence|random forest|convolutional|\bCNN\b|transformer model|automated identification|spectral classification|SHAP|interpretable model|data-driven", I)


def rule(include, *, need=None, exclude=None, energy=False):
    def f(t):
        if not include.search(t):
            return False
        if need is not None and not all(n.search(t) for n in (need if isinstance(need, (list, tuple)) else [need])):
            return False
        if exclude is not None and exclude.search(t):
            return False
        if energy and ENERGY.search(t):
            return False
        return True
    return f


RULES = {
    # owner's group (curated by hand for 2026; only backfilled up to own_until)
    "ml-mem": rule(ML, need=re.compile(r"nanofiltration|reverse osmosis|polyamide|ion.selective|thin.film composite|membrane (design|performance|material)", I),
                   exclude=re.compile(r"gas separation|proton exchange|fuel cell|distillation|bioreactor|fouling prediction of MBR", I)),
    "pa-nf": rule(re.compile(r"nanofiltration", I), exclude=re.compile(r"organic solvent|\bOSN\b|solvent.resistant|ceramic|juice|bio-oil|irrigation|spacer|concentrate treatment|crystalli[sz]ation", I)),
    "cat-mem": rule(re.compile(r"membrane", I), need=re.compile(r"catal|peroxymonosulfate|persulfate|\bPMS\b|ozon|fenton|singlet oxygen|radical", I),
                    exclude=re.compile(r"hydrogen|methane|syngas|reform|dehydrogenation|\bNOx?\b|dust|exchange membrane|electrolyzer|fuel cell|battery|CO2", I)),
    "heo": rule(re.compile(r"high.entropy|mercaptan|CH3SH", I), need=re.compile(r"catal|oxidation|ozon|degrad|peroxymonosulfate|persulfate|VOC|toluene|propane|sulfur|pollut|mercaptan", I), energy=True),
    # owner's broader membrane-separation fields (not hand-curated: backfilled over the whole range)
    "osn": rule(re.compile(r"organic solvent (nano|ultra)?filtration|organic solvent reverse osmosis|solvent.resistant (nano|ultra)filtration|\bOSN\b|\bOSRO\b", I)),
    "ro-fo": rule(re.compile(r"reverse osmosis|forward osmosis|pressure.retarded osmosis|osmotic|desalination membrane|seawater desalination|\bSWRO\b|\bBWRO\b", I), need=MEM, exclude=NOTSEP),
    "gas-sep": rule(MEM, need=re.compile(r"gas separation|CO2 (capture|separation|/N2|/CH4)|H2/CO2|hydrogen (separation|purification)|O2/N2|olefin/paraffin|propylene/propane|ethylene/ethane|helium|natural gas|biogas upgrading|carbon molecular sieve|mixed.matrix membrane|polymers? of intrinsic microporosity|\bPIM-1\b|facilitated transport", I), exclude=NOTSEP),
    "md": rule(re.compile(r"membrane distillation|pervaporation|osmotic distillation|vapor permeation|membrane crystalli", I), exclude=NOTSEP),
    "iem-ed": rule(re.compile(r"ion.exchange membrane|electrodialysis|bipolar membrane|monovalent.selective|ion.selective membrane|lithium extraction membrane|acid recovery membrane|diffusion dialysis", I), exclude=NOTSEP),
    "mbr": rule(re.compile(r"membrane bioreactor|\bMBRs?\b|\bAnMBR\b|gravity.driven membrane|membrane.aerated biofilm|\bMABR\b", I), exclude=NOTSEP),
    "2d-mem": rule(MEM, need=re.compile(r"graphene oxide|\bGO\b|MXene|lamellar|nanosheet|two.dimensional|\b2D\b|covalent organic framework|\bCOF\b|metal.organic framework|\bMOF\b|zeolite|carbon nanotube|nanochannel|angstrom|sub.nanometer channel", I), exclude=NOTSEP),
    "uf-mf": rule(re.compile(r"ultrafiltration|microfiltration|filtration membrane|membrane filtration|ceramic membrane|hollow fiber membrane|oil.water separation|oil/water separation|emulsion separation|phase inversion|electrospun (nanofiber )?membrane|janus membrane", I), exclude=NOTSEP),
    "mem-process": rule(MEM, need=re.compile(r"process|system|pilot|full.scale|brine|zero liquid discharge|\bZLD\b|resource recovery|lithium (extraction|recovery)|recovery of|techno.economic|life cycle|integrated|hybrid|module|energy consumption|treatment of|reclamation|reuse", I), exclude=NOTSEP),
    "fouling": rule(MEM, need=re.compile(r"fouling|scaling|biofouling|membrane cleaning|cleaning strateg|wetting|chlorine (resistance|attack)|ageing|aging", I), exclude=NOTSEP),
    # microplastics group
    "mp-ml": rule(MP, need=ML),
    "mp-stain": rule(MP, need=re.compile(r"nile red|stain|fluorescen|label(l)?ing|dye-?based", I)),
    "mp": rule(MP),
    # advanced oxidation & catalytic materials group (environmental use only)
    "dac": rule(re.compile(r"dual.atom|diatomic|dual single.atom|atom.pair|binuclear|dual-site single", I), need=AOP, energy=True),
    "sac": rule(re.compile(r"single.atom|atomically dispersed|isolated (metal|Fe|Co|Cu|Mn|Ni) (site|atom)", I), need=AOP, energy=True),
    "cof": rule(re.compile(r"covalent organic framework|\bCOFs?\b", I), need=AOP, energy=True),
    "mof": rule(re.compile(r"metal.organic framework|\bMOFs?\b|\bZIF-?\d|\bUiO-?6|\bMIL-?\d|prussian blue", I), need=AOP, energy=True),
    "aop-gas": rule(GASCTX, need=re.compile(r"oxidation|ozon|degrad|catalytic|abatement|removal|elimination|photocatal", I), energy=True),
    "aop-water": rule(re.compile(r"peroxymonosulfate|persulfate|peroxydisulfate|\bPMS\b|\bPDS\b|ozon|fenton|advanced oxidation|\bAOPs?\b|hydroxyl radical|singlet oxygen|sulfate radical|high-valent|photocatalytic degradation|electrocatalytic degradation|catalytic degradation", I), need=WATERCTX, energy=True),
}

QUERIES = {
    "ml-mem": ["machine learning nanofiltration", "machine learning membrane", "interpretable machine learning membrane"],
    "pa-nf": ["polyamide nanofiltration membrane", "nanofiltration interlayer", "nanofiltration ion selectivity", "nanofiltration interfacial polymerization", "positively charged nanofiltration"],
    "cat-mem": ["catalytic membrane peroxymonosulfate", "catalytic ultrafiltration membrane", "catalytic ceramic membrane", "nanoconfined catalytic membrane", "catalytic membrane ozonation"],
    "heo": ["high-entropy oxide catalyst", "high-entropy spinel", "high-entropy perovskite catalyst", "methyl mercaptan"],
    "osn": ["organic solvent nanofiltration", "solvent resistant membrane", "organic solvent reverse osmosis"],
    "ro-fo": ["reverse osmosis membrane", "forward osmosis membrane", "thin film composite desalination membrane", "pressure retarded osmosis"],
    "gas-sep": ["gas separation membrane", "CO2 separation membrane", "mixed matrix membrane gas", "hydrogen separation membrane", "carbon molecular sieve membrane"],
    "md": ["membrane distillation", "pervaporation membrane", "membrane crystallization"],
    "iem-ed": ["ion exchange membrane", "electrodialysis", "bipolar membrane electrodialysis", "monovalent selective membrane"],
    "mbr": ["membrane bioreactor", "anaerobic membrane bioreactor", "gravity-driven membrane"],
    "2d-mem": ["graphene oxide membrane separation", "MXene membrane", "covalent organic framework membrane", "metal-organic framework membrane separation", "lamellar membrane ion sieving"],
    "uf-mf": ["ultrafiltration membrane", "microfiltration membrane", "ceramic membrane filtration", "oil water separation membrane", "hollow fiber membrane"],
    "mem-process": ["membrane process brine", "membrane lithium extraction", "membrane system wastewater reclamation", "membrane resource recovery"],
    "fouling": ["membrane fouling", "membrane scaling", "membrane biofouling", "membrane cleaning"],
    "mp-ml": ["microplastics machine learning", "microplastics deep learning identification", "microplastics Raman spectra classification"],
    "mp-stain": ["microplastics Nile Red staining", "microplastics fluorescent labeling"],
    "mp": ["microplastics", "nanoplastics", "microplastic toxicity", "microplastic removal", "microplastics soil", "microplastics aging"],
    "dac": ["dual-atom catalyst peroxymonosulfate", "diatomic catalyst degradation", "dual-atom catalyst Fenton-like"],
    "sac": ["single-atom catalyst peroxymonosulfate", "single-atom catalyst Fenton-like", "single-atom catalyst ozonation", "single-atom catalyst degradation pollutant"],
    "cof": ["covalent organic framework photocatalytic degradation", "covalent organic framework peroxymonosulfate", "COF advanced oxidation"],
    "mof": ["metal-organic framework peroxymonosulfate", "metal-organic framework Fenton-like", "MOF photocatalytic degradation", "MOF catalytic ozonation"],
    "aop-gas": ["catalytic oxidation VOCs", "catalytic ozonation toluene", "formaldehyde oxidation catalyst", "photocatalytic oxidation VOCs", "methyl mercaptan removal"],
    "aop-water": ["peroxymonosulfate activation degradation", "persulfate activation", "Fenton-like degradation", "catalytic ozonation water", "advanced oxidation process"],
}
# assignment priority: first matching field wins
PRIORITY = ["ml-mem", "pa-nf", "osn", "cat-mem", "heo", "ro-fo", "gas-sep", "md", "iem-ed", "mbr", "2d-mem", "uf-mf", "mem-process", "fouling",
            "mp-ml", "mp-stain", "mp", "dac", "sac", "cof", "mof", "aop-gas", "aop-water"]
# hand-curated for 2026: only backfilled up to conf["own_until"]
CURATED = {"ml-mem", "pa-nf", "cat-mem", "heo"}


def norm(s):
    s = (s or "").lower().replace("&amp;", "and").replace("&", "and")
    s = re.sub(r"^the ", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


ALIASES = {"appliedcatalysisbenvironmental": "Applied Catalysis B: Environment and Energy",
           "tractrendsinanalyticalchemistry": "TrAC Trends in Analytical Chemistry"}


def get(url):
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"lit-radar/1.0 (mailto:{MAILTO})"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as e:
            print("  retry", attempt, e)
            time.sleep(5 * (attempt + 1))
    return None


def months(since, until):
    a = dt.date.fromisoformat(since)
    b = dt.date.fromisoformat(until)
    while a <= b:
        nxt = (a.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
        yield a.isoformat(), min(nxt - dt.timedelta(days=1), b).isoformat()
        a = nxt


def main():
    conf = json.load(open(CONF, encoding="utf-8"))
    data = json.load(open(DATA, encoding="utf-8"))
    journals = data["journals"]
    jmap = {norm(k): k for k in journals}
    jmap.update({k: v for k, v in ALIASES.items() if v in journals})
    own = CURATED
    seen = {p["doi"].lower() for p in data["papers"]}
    added = []
    for field in PRIORITY:
        until = conf["until"]
        if field in own:
            until = min(until, conf.get("own_until", until))
        if until < conf["since"]:
            continue
        for q in QUERIES[field]:
            for a, b in months(conf["since"], until):
                url = "https://api.crossref.org/works?" + urllib.parse.urlencode({
                    "query.bibliographic": q, "rows": 400, "mailto": MAILTO,
                    "filter": f"from-created-date:{a},until-created-date:{b},type:journal-article",
                    "select": "DOI,title,container-title,created,published-online"})
                res = get(url)
                time.sleep(0.4)
                if not res:
                    continue
                for it in res["message"]["items"]:
                    doi = (it.get("DOI") or "").lower()
                    title = re.sub(r"<[^>]+>", "", (it.get("title") or [""])[0])
                    title = re.sub(r"\s+", " ", title).strip()
                    jname = jmap.get(norm((it.get("container-title") or [""])[0]))
                    if not doi or doi in seen or not jname or not title or NOISE.search(title):
                        continue
                    fld = next((f for f in PRIORITY if RULES[f](title)), None)
                    if fld is None:
                        continue
                    if fld in own and (it.get("created", {}).get("date-time", "")[:10] > conf.get("own_until", "9999")):
                        continue
                    parts = (it.get("published-online") or it.get("created") or {}).get("date-parts", [[None]])[0]
                    if not parts or parts[0] is None:
                        continue
                    pub = "-".join([str(parts[0])] + [f"{x:02d}" for x in parts[1:3]])
                    if len(pub) < 10:
                        c = it.get("created", {}).get("date-parts", [[None]])[0]
                        pub = "-".join([str(c[0])] + [f"{x:02d}" for x in c[1:3]])
                    if pub < conf["since"]:
                        continue
                    seen.add(doi)
                    pid = re.sub(r"[^a-z0-9_.~:@+-]", "_", doi)
                    url_doi = "https://doi.org/" + it["DOI"]
                    src = ("ScienceDirect" if doi.startswith("10.1016") else "Nature" if doi.startswith("10.1038") else
                           "ACS Publications" if doi.startswith("10.1021") else "Wiley Online Library" if doi.startswith("10.1002") else
                           "RSC Publishing" if doi.startswith("10.1039") else "Crossref")
                    added.append({"_id": pid, "title": title, "journal": jname, "cas_zone": journals[jname]["cas_zone"],
                                  "field": fld, "published": pub, "pushed": pub, "doi": it["DOI"], "url": url_doi,
                                  "summary_zh": "", "source_type": "官方", "source_name": src, "source_url": url_doi,
                                  "key": False, "auto": True})
            print(f"{field:10s} after '{q}': total added {len(added)}")
    if added:
        from collections import Counter
        print("by field:", Counter(p["field"] for p in added))
        data["papers"] = sorted(data["papers"] + added, key=lambda p: (p.get("published", ""), p["_id"]), reverse=True)
        data["updated"] = (dt.datetime.utcnow() + dt.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
        json.dump(data, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("added", len(added))


if __name__ == "__main__":
    main()
