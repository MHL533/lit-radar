"""Research fields, groups, title-classification rules and Crossref search queries.

A paper is classified from its title. It gets every field whose rule matches (multi-label);
a field marked as a fallback ("其他…") is used only when no other field of the same group matched.
Groups also restrict which CAS 大类 (journal category) may feed them, which keeps e.g.
medical "electrode" papers out of the electrochemistry group.
"""
import re

I = re.I


def R(p):
    return re.compile(p, I)


# ---------------------------------------------------------------- shared patterns
NOISE = R(r"corrigendum|erratum|retraction|retracted|expression of concern|issue information|cover image|front cover|back cover|inside cover|"
          r"editorial board|graphical abstract|^correction|correction to|^addendum|^editorial\b|^preface\b|^in this issue|table of contents|"
          r"^reply to|^response to|^comment on|^author index|^masthead|^contents\b|^frontispiece|^announcement")
ENERGY = R(r"batter(y|ies)|electrolys|water splitting|hydrogen evolution|oxygen evolution|oxygen reduction|\bHER\b|\bOER\b|\bORR\b|"
           r"CO2 (electro)?reduction|CO2RR|nitrate reduction|ammonia (synthesis|production)|nitrogen reduction|N2 fixation|supercapacitor|"
           r"fuel cell|hydrogen storage|lithium|sodium-ion|zinc-air|H2O2 (production|synthesis)|hydrogen peroxide (production|synthesis)|"
           r"solar cell|tumou?r|cancer|wound|bacteria-infected|anticancer|drug delivery|sensor for|biosens")
AOP = R(r"peroxymonosulfate|persulfate|peroxydisulfate|\bPMS\b|\bPDS\b|ozon|fenton|advanced oxidation|\bAOPs?\b|hydroxyl radical|singlet oxygen|"
        r"sulfate radical|high-valent|degrad|mineraliz|VOCs?\b|volatile organic|toluene|formaldehyde|benzene|mercaptan|odou?r|decontamination|"
        r"oxidation of (organic|pollutant|antibiotic)|catalytic oxidation")
WATERCTX = R(r"water|wastewater|pollutant|contaminant|antibiotic|micropollutant|\bdyes?\b|pharmaceutical|phenol|bisphenol|sulfamethoxazole|"
             r"tetracycline|ciprofloxacin|PFAS|organic")
GASCTX = R(r"VOCs?\b|volatile organic|toluene|formaldehyde|benzene|xylene|odou?r|mercaptan|methyl sulfide|H2S|gaseous|indoor air|air purification|"
           r"exhaust|chlorinated (VOC|hydrocarbon)|CVOC|ethyl acetate|propane|methane combustion|soot")
MP = R(r"micro-?plastic|nano-?plastic")
MEM = R(r"membrane|nanofiltration|reverse osmosis|forward osmosis|ultrafiltration|microfiltration|pervaporation|electrodialysis")
# biological / energy-device membranes are not separation membranes
NOTSEP = R(r"\btherapy\b|antitumou?r|anticancer|nanocarrier|tumou?r|cancer|osteo|arthritis|wound (healing|dressing)|drug delivery|membrane.coated|"
           r"immunoassay|immunity|inflammat|antifungal|cell membrane|plasma membrane|mitochondri|membrane protein|lipid (bi)?layer|liposom|"
           r"membrane potential|erythrocyte|bacterial (outer )?membrane|membrane-bound|extracellular vesicle|thylakoid|proton exchange membrane|"
           r"PEM fuel|membrane electrode assembly|fuel cell|electrolyzer|electrolyser|water electrolysis|electrolysis cell|polymer electrolyte membrane|redox flow batter|lithium.ion batter|"
           r"separator for|tympanic|basement membrane|amniotic|mucous membrane|periodontal|guided bone|dental|nuclear membrane|cellular membrane|"
           r"protocell|giant vesicle|membrane remodel|membrane curvature|outer membrane|inner membrane|membrane fusion|membrane permeabili[sz]|"
           r"membrane damage|membrane integrity|lipid|phospholipid|biomembrane|peripheral protein|membrane.active|antimicrobial peptide|microRNA|\bDNA\b|\bRNA\b|amplification|Shewanella|dendrite|batter(y|ies)")
ATMOS = R(r"source apportionment|ozone formation|atmospheric (oxidation|chemistry|mercury|aerosol)|ozone pollution|tropospher|stratospher|smog|"
          r"emission inventor|sea.ice|phytoplankton|haze|PM2\.5|secondary organic aerosol|air quality model|elemental mercury")
ML = R(r"machine learning|deep learning|neural network|artificial intelligence|random forest|convolutional|\bCNN\b|transformer model|"
       r"automated identification|spectral classification|(?-i:\bSHAP\b)|interpretable model|data-driven")
CERAMIC = R(r"ceramic (membrane|ultrafiltration|nanofiltration|microfiltration|hollow.fib|filter|separation|support|tub)|inorganic membrane|"
            r"alumina (membrane|hollow.fib)|Al2O3 (membrane|hollow.fib)|SiC membrane|silicon carbide membrane|zirconia membrane|"
            r"ZrO2 membrane|titania membrane|TiO2 (ceramic )?membrane|mullite membrane|ceramic.based membrane|ceramic hollow|"
            r"mixed ionic.electronic conducting|\bMIEC\b|oxygen.permeable membrane|oxygen transport membrane|oxygen.permeation membrane|"
            r"perovskite (hollow.fib\w* )?membrane|dual.phase membrane|ceramic nanofiltration")
CATAL = R(r"catal|peroxymonosulfate|persulfate|peroxydisulfate|\bPMS\b|\bPDS\b|ozon|fenton|singlet oxygen|radical|degrad|membrane reactor")
NOTEC = R(r"\bEEG\b|electrocardiogra|electroencephalogra|electromyogra|deep brain|neural (recording|interface|probe|electrode)|cochlear|"
          r"electrophysiolog|cardiac|retina|neurostimulat|electrolyte (disorder|imbalance|abnormalit)|serum electrolyte|hyponatr|hyperkal|"
          r"electroconvulsive|electroacupuncture|patient|clinical|surgery|tumou?r|cancer")
EC_CTX = R(r"electro(?!n\b|ns\b|nic|static|magnet|spin|spun|phoresis|phoretic|wett|chromic|caloric|optic|mechanic|des\b)|\belectrode|\belectrolyte|"
           r"batter(y|ies)|anode|cathode|supercapacit|fuel cell|corrosion|voltammetr|redox flow|\bHER\b|\bOER\b|\bORR\b|faradaic")
PSC = R(r"perovskite")
PV = R(r"solar cell|photovoltaic|\bPSCs?\b|solar module|\bPV\b|power conversion efficienc|\bPCEs?\b|tandem|minimodule|solar energy conversion")
NOTPV = R(r"light.emitting|\bLEDs?\b|\bPeLEDs?\b|photodetector|scintillat|laser|X.ray detect|memristor|transistor")
CL = R(r"chemical.looping|oxygen carriers?\b|looping (combustion|gasification|reforming|process|cycle)|\bCLC\b|\bCLOU\b|\bCLR\b|\bCLHG\b|"
       r"\bCLG\b|\bCL-?ODH\b|\bCLSR\b|\bCLDR\b|\bCLPO\b|redox (catalysts?|looping|scheme)|calcium looping|\bCaL\b|oxygen uncoupling")
IMPRINT = R(r"imprint(ed|ing)")
NOTIMPRINT = R(r"nano.?imprint|imprint lithograph|genomic imprint|imprinting (control|disorder|centre|center)|parental|maternal|paternal|"
               r"filial imprint|imprinted gene|epigenetic|methylation|allele|syndrome|hot embossing|nanoimprint")
FLOOD = R(r"\bflood|inundation|storm surge|\bpluvial\b|\bfluvial (risk|hazard|flood)|levee|\bdikes?\b|\bdykes?\b|stormwater management|sponge cit|urban drainage|"
          r"coastal (flooding|risk|hazard|adaptation)|managed retreat|sea.level rise")
FLOOD_NEED = R(r"risk|hazard|manag|resilien|adapt|damage|loss|insur|vulnerab|exposure|mapping|forecast|warning|evacuat|mitigat|defen[cs]e|"
               r"protection|prepared|recover|model|simulat|inundation|susceptib|governance|polic|household|decision|plann|drainage|"
               r"infrastructure|nature.based|storage|retention|detention|control|urban|city|cities|surge|extreme|disaster|emergency")
NOTFLOOD = R(r"paddy|\brice\b|waterlogg|submergence|flood basalt|flooding (stress|tolerance)|seedling|germination|\bcrop\b|wetland plant|"
             r"fish|zooplankton|nematode|flood irrigation|flooded soil|soil redox|methane emission|N2O emission|waterflood|water.?flooding|polymer.flood|"
             r"oil recovery|reservoir rock|enhanced oil|CO2 flooding|gas flooding|chemical flooding|flood.?light|PPCPs?|pharmaceutical|microplastic|contaminant|pollution|pathogen|antibiotic")
ABM = R(r"agent.based|individual.based (model|simulation)|\bABMs?\b|multi.agent (model|simulation)|socio.hydrolog|"
        r"coupled human.(natural|water|flood)|human.flood")


def rule(include, *, need=None, exclude=None, energy=False):
    needs = [] if need is None else (list(need) if isinstance(need, (list, tuple)) else [need])
    excl = [] if exclude is None else (list(exclude) if isinstance(exclude, (list, tuple)) else [exclude])

    def f(t):
        if not include.search(t):
            return False
        if any(not n.search(t) for n in needs):
            return False
        if any(e.search(t) for e in excl):
            return False
        if energy and ENERGY.search(t):
            return False
        return True
    return f


C_CHEM, C_MAT, C_ENG, C_ENV, C_ALL, C_PHY, C_EARTH, C_AGR, C_BIO = "化学", "材料科学", "工程技术", "环境科学与生态学", "综合性期刊", "物理与天体物理", "地球科学", "农林科学", "生物学"
C_CS, C_MGT, C_ECO, C_SOC = "计算机科学", "管理学", "经济学", "社会学"

# id, name, allowed journal categories, [(field, label, rule, fallback?)] in priority order
GROUPS = [
    ("membrane", "膜分离", {C_CHEM, C_MAT, C_ENG, C_ENV, C_ALL, C_PHY}, [
        ("ml-mem", "机器学习+膜", rule(ML, need=R(r"nanofiltration|reverse osmosis|polyamide|ion.selective|thin.film composite|membrane"),
                                       exclude=R(r"proton exchange|fuel cell|electrolyzer|cell membrane|battery separator"))),
        ("pa-nf", "聚酰胺纳滤膜", rule(R(r"nanofiltration"), exclude=R(r"organic solvent|\bOSN\b|solvent.resistant|ceramic nanofiltration|juice|bio-oil|irrigation|spacer"))),
        ("osn", "有机溶剂纳滤", rule(R(r"organic solvent (nano|ultra)?filtration|organic solvent reverse osmosis|solvent.resistant (nano|ultra)filtration|\bOSN\b|\bOSRO\b|solvent.resistant membrane|solvent separation membrane"))),
        ("cat-ceramic", "催化陶瓷膜", rule(CERAMIC, need=CATAL, exclude=R(r"fuel cell|battery|electrolyzer|solid oxide|proton.?ceramic|protonic|electrolyte|cermet|electrolysis"))),
        ("cat-mem", "催化膜", rule(R(r"membrane"), need=R(r"catal|peroxymonosulfate|persulfate|\bPMS\b|ozon|fenton|singlet oxygen|radical"),
                                  exclude=R(r"hydrogen|methane|syngas|reform|dehydrogenation|\bNOx?\b|dust|exchange membrane|electrolyzer|fuel cell|battery|CO2|cell membrane|lipid"))),
        ("heo", "高熵氧化物催化", rule(R(r"high.entropy|mercaptan|CH3SH"), need=R(r"catal|ozon|degrad|peroxymonosulfate|persulfate|VOC|toluene|propane|pollut|mercaptan|CH3SH"), exclude=R(r"\balloys?\b|coating|oxidation (behaviou?r|resistance)|ablation|cementation|thermal barrier|electrocatal|sens(or|ing)|detection|sulfur (conversion|reduction)|methanol|urea|lithium|sodium"), energy=True)),
        ("ceramic", "陶瓷膜", rule(CERAMIC, need=R(r"membrane|filtrat|separat|permeat|filter"), exclude=[NOTSEP, R(r"solid oxide fuel|battery")])),
        ("ro-fo", "反渗透/正渗透", rule(R(r"reverse osmosis|forward osmosis|pressure.retarded osmosis|osmotic|desalination membrane|seawater desalination|\bSWRO\b|\bBWRO\b"), need=MEM, exclude=NOTSEP)),
        ("gas-sep", "气体分离膜", rule(MEM, need=R(r"gas separation|CO2 (capture|separation|/N2|/CH4)|H2/CO2|hydrogen (separation|purification)|O2/N2|olefin/paraffin|propylene/propane|ethylene/ethane|helium|natural gas|biogas upgrading|carbon molecular sieve|mixed.matrix membrane|polymers? of intrinsic microporosity|\bPIM-1\b|facilitated transport|gas permeat"), exclude=NOTSEP)),
        ("md", "膜蒸馏/渗透汽化", rule(R(r"membrane distillation|pervaporation|osmotic distillation|vapor permeation|membrane crystalli"), exclude=NOTSEP)),
        ("iem-ed", "离子交换膜/电渗析", rule(R(r"ion.exchange membrane|electrodialysis|bipolar membrane|monovalent.selective|ion.selective membrane|lithium extraction membrane|acid recovery membrane|diffusion dialysis|membrane capacitive deionization"), exclude=R(r"fuel cell|water electrolysis|electrolyzer|redox flow|tumou?r|cancer"))),
        ("mbr", "膜生物反应器", rule(R(r"membrane bioreactor|\bMBRs?\b|\bAnMBRs?\b|gravity.driven membrane|membrane.aerated biofilm|\bMABRs?\b"), exclude=NOTSEP)),
        ("2d-mem", "二维/框架材料膜", rule(MEM, need=R(r"graphene oxide|\bGO\b|MXene|lamellar|nanosheet|two.dimensional|\b2D\b|covalent organic framework|\bCOFs?\b|metal.organic framework|\bMOFs?\b|zeolite|carbon nanotube|nanochannel|angstrom|[aå]ngstr|sub.nanometer channel"), exclude=NOTSEP)),
        ("oil-water", "油水分离膜", rule(R(r"oil.water|oil/water|oil.in.water|water.in.oil|emulsion (separation|demulsif)|emulsified oil|oily wastewater|underwater superoleophob|superwettab|oil spill|crude oil.*separation"), need=R(r"membrane|mesh|filtration|separat|fabric|filter"), exclude=NOTSEP)),
        ("uf-mf", "超滤/微滤", rule(R(r"ultrafiltration|microfiltration|filtration membrane|membrane filtration|hollow fib\w* membrane|phase inversion|electrospun (nanofiber(s)? )?membrane|nanofibrous membrane|janus membrane|loose membrane|porous membrane|membrane filter"), exclude=NOTSEP)),
        ("osmotic-energy", "盐差能与纳流体离子传输", rule(R(r"osmotic (energy|power)|salinity gradient|blue energy|reverse electrodialysis|ionic diode|ion.selective (channel|nanochannel)|ionic (current )?rectification|nanofluidic|ion transport.*(membrane|channel)|iontronic|ion sieving"), need=R(r"membrane|channel|nanofluidic|nanopore|sieving"), exclude=NOTSEP)),
        ("mem-model", "膜模拟与传质机理", rule(MEM, need=R(r"molecular dynamics|molecular simulation|simulation|computational|density functional|\bDFT\b|modell?ing|\bCFD\b|computational fluid|transport model|Donnan|Nernst.Planck|\bDSPM\b|first.principles|theoretical|mechanistic model"), exclude=NOTSEP)),
        ("mem-process", "膜过程与应用", rule(MEM, need=R(r"process|system|pilot|full.scale|brine|zero liquid discharge|\bZLD\b|resource recovery|lithium (extraction|recovery)|recovery of|techno.economic|life cycle|integrated|hybrid|module|energy consumption|treatment of|reclamation|reuse"), exclude=NOTSEP)),
        ("fouling", "膜污染与清洗", rule(MEM, need=R(r"fouling|scaling|biofouling|membrane cleaning|cleaning strateg|wetting|chlorine (resistance|attack)|ageing|aging"), exclude=NOTSEP)),
        ("mem-other", "其他膜分离", rule(MEM, need=R(r"separat|filtrat|permea|rejection|selectiv|desalinat|purif|sieving|\bflux\b|water treatment|wastewater|antifouling|\bdyes?\b|\bions?\b|solvent|\bgas\b|\boil\b|porous|removal|recovery|transport|dialysis|osmosis|extraction|capture|adsorpt"),
                                        exclude=[NOTSEP, R(r"battery|supercapacitor|solar cell|electrolyzer|triboelectric|sensor|actuator|wearable|skin")]), True),
    ]),
    ("microplastics", "微塑料", {C_CHEM, C_MAT, C_ENG, C_ENV, C_ALL, C_EARTH, C_AGR, C_BIO}, [
        ("mp-ml", "微塑料机器学习识别", rule(MP, need=ML)),
        ("mp-stain", "微塑料染色与标记", rule(MP, need=R(r"nile red|stain|fluorescen|label(l)?ing|dye-?based"))),
        ("mp", "微塑料", rule(MP)),
    ]),
    ("aop", "高级氧化与催化材料", {C_CHEM, C_MAT, C_ENG, C_ENV, C_ALL}, [
        ("dac", "双原子催化", rule(R(r"dual.atom|diatomic|dual single.atom|atom.pair|binuclear|dual-site single"), need=AOP, energy=True)),
        ("sac", "单原子催化", rule(R(r"single.atom|atomically dispersed|isolated (metal|Fe|Co|Cu|Mn|Ni) (site|atom)"), need=AOP, energy=True)),
        ("cof", "COF 材料", rule(R(r"covalent organic framework|\bCOFs?\b"), need=AOP, energy=True)),
        ("mof", "MOF 材料", rule(R(r"metal.organic framework|\bMOFs?\b|\bZIF-?\d|\bUiO-?6|\bMIL-?\d|prussian blue"), need=AOP, energy=True)),
        ("aop-gas", "气相高级氧化", rule(GASCTX, need=R(r"oxidation|ozon|degrad|catalytic|abatement|removal|elimination|photocatal"), exclude=[ATMOS, R(r"cracking|pyrolysis|tar\b")], energy=True)),
        ("aop-water", "水相高级氧化", rule(R(r"peroxymonosulfate|persulfate|peroxydisulfate|\bPMS\b|\bPDS\b|ozon|fenton|advanced oxidation|\bAOPs?\b|hydroxyl radical|singlet oxygen|sulfate radical|high-valent|photocatalytic degradation|electrocatalytic degradation|catalytic degradation"), need=WATERCTX, exclude=ATMOS, energy=True)),
    ]),
    ("electrochem", "电化学", {C_CHEM, C_MAT, C_ENG, C_ENV, C_ALL, C_PHY}, [
        ("ec-li", "锂离子/锂金属电池", rule(R(r"lithium.ion (batter|full cell|cell|storage|anode|cathode)|\bli[\s‐-]ion\b|(?-i:\bLIBs?\b)|lithium metal (batter|anode)|li metal (batter|anode)|lithium (anode|batter|deposition|dendrite|plating|stripping)|(?-i:\bNCM\d*|\bLFP\b|\bLiNi|\bLiMn|\bLiCoO2|\bLiFePO4|\bSEI\b|\bCEI\b)|Ni.rich (layered |cathode)|high.nickel|\bLi.rich|silicon(.based)? anode|\bSi anode|graphite anode|solid electrolyte interphase|cathode electrolyte interphase|anode.free lithium"),
                                     exclude=[NOTEC, R(r"lithium extraction|lithium recovery|Li\+/Mg2\+|lithium.sulfur|li.s batter|lithium.oxygen|Li.O2|Li.air|Li.CO2")])),
        ("ec-ss", "固态电池与固态电解质", rule(R(r"solid.state (lithium |sodium |li |na )?(metal )?batter|all.solid.state|solid(.state)? (polymer )?electrolyte|sulfide electrolyte|garnet|\bLLZO|argyrodite|halide (solid )?electrolyte|polymer electrolyte|quasi.solid|gel (polymer )?electrolyte|\bPEO\b.*electrolyte|NASICON"),
                                         need=R(r"batter|lithium|sodium|\bLi\b|\bNa\b|ion.conduct|anode|cathode|Li\+"), exclude=[NOTEC, R(r"solid oxide|\bSOFC|\bSOEC|proton.conducting|electrolysis|fuel cell|electrolyzer")])),
        ("ec-beyond", "钠/钾/锌等新型电池", rule(R(r"sodium.ion (batter|full cell|storage|anode|cathode|capacitor)|(?-i:\bSIBs?\b|\bPIBs?\b|\bZIBs?\b|\bAZIBs?\b)|\bna[\s‐-]ion\b|sodium (metal (batter|anode)|batter|storage)|potassium.ion (batter|storage|anode|cathode)|potassium (metal (batter|anode)|batter|storage)|zinc.ion (batter|hybrid|capacitor|storage)|aqueous zinc|zinc (metal )?anode|\bZn anode|\bZn metal (anode|batter)|zinc batter|magnesium.ion batter|magnesium (metal )?batter|\bMg batter|calcium.ion batter|alumin(i)?um.ion batter|ammonium.ion batter|proton batter|dual.ion batter|redox flow|flow batter|aqueous batter|hard carbon anode|Prussian blue (analogue )?cathode|Zn.ion batter"),
                                           exclude=[NOTEC, R(r"zinc.air|Zn.air|zinc.oxygen")])),
        ("ec-lis", "锂硫与金属-空气电池", rule(R(r"lithium.sulfur|li.s batter|\bLSBs?\b|polysulfide|sulfur cathode|lithium.selenium|lithium.oxygen|Li.O2|Li.air|zinc.air|Zn.air|metal.air|Li.CO2|sodium.sulfur|Na.S batter|room.temperature sodium.sulfur"), exclude=NOTEC)),
        ("ec-sc", "超级电容器", rule(R(r"supercapacit|pseudocapacit|electrochemical capacitor|electric(al)? double.layer capacit|\bEDLCs?\b|hybrid capacitor|zinc.ion capacitor|lithium.ion capacitor|capacitive energy storage"), exclude=NOTEC)),
        ("ec-water", "电解水制氢", rule(R(r"water (electrolysis|splitting)|electrolysis cells?|PEM electrolysis|(electrocatalytic|photoelectrochemical|electrochemical) water oxidation|hydrogen evolution|oxygen evolution|\bHERs?\b|\bOERs?\b|electrolyzer|electrolyser|\bAEMWE|\bPEMWE|seawater (electrolysis|splitting|oxidation)|overall water|bifunctional electrocatalyst|electrocatalytic hydrogen|hydrogen production by electrolysis|alkaline electrolysis|acidic oxygen evolution|anodic oxygen"),
                                         exclude=[NOTEC, R(r"^(?!.*electro).*photocatal|dye.sensitized")])),
        ("ec-co2", "CO2 电还原", rule(R(r"CO2 (electro)?reduction|\bCO2RR\b|\bCO2ER\b|\beCO2RR\b|electrochemical CO2|electroreduction of (CO2|carbon dioxide)|CO2 electrolysis|CO2 electrolyzer|CO electroreduction|\bCORR\b|carbon dioxide (electro)?reduction|CO2.to.|electrocatalytic CO2"),
                                      need=R(r"electro|\bCO2RR\b|\bCO2ER\b|\bCORR\b|cathode|faradaic|current density|membrane electrode|flow cell|\bMEA\b"), exclude=[NOTEC, R(r"^(?!.*electro).*photo")])),
        ("ec-n", "含氮电催化（硝酸盐/氮还原）", rule(R(r"nitrate (electro)?reduction|reduction of (NO3|nitrate|nitrite|NO2|NO\b)|\bNO3-?RR\b|\bNO3RR\b|nitrogen reduction|\bNRR\b|electrochemical ammonia|ammonia electrosynthesis|electrosynthesis of ammonia|nitrite (electro)?reduction|\bNO2-?RR\b|\bNORR\b|nitric oxide (electro)?reduction|urea (electro)?synthesis|electrocatalytic (urea|ammonia|C.N coupling)|C.N coupling|nitrogen fixation|N2 fixation|ammonia oxidation reaction|\bAOR\b|hydrazine oxidation"),
                                                need=R(r"electro|\bNRR\b|\bNO3-?RR\b|\bNO2-?RR\b|\bNORR\b|\bAOR\b|faradaic|cathod|anod"), exclude=[NOTEC, R(r"^(?!.*electro).*photo")])),
        ("ec-fc", "燃料电池与氧还原", rule(R(r"fuel cell|oxygen (electro)?reduction (reaction|electrocatal|catalys)|electrocatalytic oxygen reduction|oxygen electroreduction|\bORR\b|\bPEMFCs?\b|\bAEMFCs?\b|\bSOFCs?\b|\bSOECs?\b|\bPCFCs?\b|\bPCECs?\b|solid oxide (fuel|electroly|cell)|protonic ceramic|proton exchange membrane fuel|anion exchange membrane fuel|membrane electrode assembl|methanol oxidation|ethanol oxidation|formic acid (electro)?oxidation|formate (electro)?oxidation|hydrogen oxidation reaction|\bHOR\b|\bMOR\b|catalyst layer|platinum group metal.free|PGM.free|air cathode"),
                                         exclude=[NOTEC, R(r"^(?!.*(electro|fuel cell|\bORR\b|\bHOR\b|cathode|anode)).*photo")])),
        ("ec-synth", "电合成与 H2O2", rule(R(r"electrosynthes|electrochemical synthes|electro.?organic|electrochemical (oxidation|reduction|hydrogenation|dehydrogenation|coupling|fluorination|amination|carboxylation|halogenation|functionali[sz]ation|cyclization|C.H)|paired electrolysis|electrocatalytic (oxidation|hydrogenation|upgrading|reduction|semi.?hydrogenation|valori[sz]ation)|H2O2 (electro)?(synthesis|production|generation)|electrochemical (production|synthesis|generation) of (hydrogen peroxide|H2O2)|two.electron oxygen reduction|2e.? ?ORR|glycerol (electro)?oxidation|\bHMF\b.*oxidation|biomass (electro|valori)|electroreductive|electrooxidative|electrochemically (enabled|driven|mediated)|electrophotocatal|photoelectrochemical (oxidation|synthesis|conversion)|electrifi(ed|cation of) (chemical|synthesis)"),
                                           need=EC_CTX, exclude=[NOTEC, R(r"wastewater|pollut|degrad|contamina|\bdrugs?\b|removal|treat|antibiotic|nitrate|nitrite|\bNO3|CO2")])),
        ("ec-env", "环境电化学", rule(R(r"electro.?fenton|electrochemical (oxidation|degradation|treatment|disinfection|advanced oxidation|removal|recovery|desalination|lithium extraction|phosphorus|nitrate removal|ammonia (removal|recovery)|water treatment|abatement|dechlorination|remediation)|electrocatalytic (degradation|dechlorination|removal|denitrification|oxidation of (pollutant|organic|antibiotic))|anodic oxidation|electro.?oxidation of (pollutant|organic|PFAS|antibiotic|micropollutant)|capacitive deionization|\bCDI\b|electrosorption|electrocoagulation|electroflotation|bioelectrochem|microbial (fuel|electrolysis) cell|\bMFCs?\b|\bMECs?\b|boron.doped diamond|\bBDD\b|electro.?peroxone|electrochemical membrane|electrified membrane|electroactive membrane|conductive membrane|electro.?chlorination|electrochemical (ozone|chlorine) (generation|production)|electrodeionization|faradaic deionization|battery deionization|electrochemical (CO2 )?capture|electrochemically mediated"), exclude=NOTEC)),
        ("ec-sensor", "电化学传感与分析", rule(R(r"electrochemical (bio)?sens|electrochemical (detection|determination|monitoring|analysis|aptasens|immunosens|assay|quantification|platform for)|voltammetric|amperometric|electrochemiluminescen|\bECL\b|potentiometric|ion.selective electrode|photoelectrochemical (bio)?sens|photoelectrochemical (detection|assay|aptasens|immunosens)|\bPEC (bio)?sens|impedimetric|non.enzymatic (glucose |H2O2 )?sens|electrochemical glucose|glucose (bio)?sensor|electrochemical aptamer|wearable (sweat )?sensor"), exclude=R(r"\bEEG\b|electrocardiogra|neural|cochlear"))),
        ("ec-corr", "腐蚀与电沉积", rule(R(r"corrosion|electrodeposit|electroplat|electropolish|anodi[sz]ation|anodi[sz]ed|anodic (oxide|alumina|film|TiO2)|passive film|passivation film|pitting|cathodic protection|electrochemical machining|galvanic|micro.arc oxidation|plasma electrolytic oxidation|electroless"),
                                       exclude=[NOTEC, R(r"concrete|reinforced|rebar|microbiologically|biocorrosion|dental|implant")])),
        ("ec-other", "其他电化学", rule(R(r"electrochem|electrocatal|photoelectrocatal|photoelectrochem|\belectrodes?\b|\belectrolytes?\b|batter(y|ies)|electrolys[ie]s|redox flow|cathode material|anode material|\banodes?\b|\bcathodes?\b|faradaic|voltammetr|impedance spectroscop|electrochromic|electroreduction|electrooxidation|electrocapillar|ionic liquid electrolyte|energy storage device"),
                                         exclude=[NOTEC, R(r"electrospun|electrospinning|electrostatic|electron microscop")]), True),
    ]),
    ("abm-flood", "智能体建模与洪水风险", {C_EARTH, C_ENV, C_ENG, C_CS, C_MGT, C_ECO, C_SOC, C_ALL}, [
        ("abm", "基于智能体建模（ABM）", rule(ABM, exclude=R(r"\bLLMs?\b|large language model|reinforcement learning|robot|cancer|tumou?r|\bcells?\b|immune|epidemi|COVID|infection|drug|smart grid|swarm|uncrewed|unmanned|\bUAVs?\b|power system|microgrid|cyber|attack|consensus control|formation control"))),
        ("flood", "洪水风险管理", rule(FLOOD, need=FLOOD_NEED, exclude=NOTFLOOD)),
    ]),
    ("mip", "分子印迹", {C_CHEM, C_MAT, C_ENG, C_ENV, C_ALL, C_AGR}, [
        ("mip-sensor", "分子印迹传感检测", rule(IMPRINT, need=R(r"sens|detect|determin|assay|electrochem|fluorescen|SERS|Raman|chemiluminescen|ratiometric|aptasens|probe|monitor|quantif|analysis of|recogni[sz]ing and|visual"), exclude=NOTIMPRINT)),
        ("mip-sep", "分子印迹分离与吸附", rule(IMPRINT, need=R(r"extract|adsorb|adsorpt|sorbent|removal|separat|enrich|purif|solid.phase|\bSPE\b|\bMSPE\b|chromatograph|recover|membrane|captur|elimination|uptake"), exclude=NOTIMPRINT)),
        ("mip-other", "分子印迹材料与机理", rule(IMPRINT, need=R(r"polymer|\bMIPs?\b|\bIIPs?\b|molecular|ion.imprinted|template|recognition|nanozyme|catal|antibod|epitope"), exclude=NOTIMPRINT), True),
    ]),
    ("chemloop", "化学链", {C_CHEM, C_MAT, C_ENG, C_ENV, C_ALL}, [
        ("cl-odh", "化学链氧化脱氢", rule(R(r"oxidative dehydrogenation|\bODH\b|\bCL-?ODH\b|selective hydrogen combustion|\bSHC\b|oxidative coupling of methane|\bOCM\b|chemical looping (dehydrogenation|oxidative)|redox oxidative"),
                                       need=R(r"chemical.looping|lattice oxygen|redox (catalyst|scheme|looping|mode)|oxygen carriers?|looping|oxygen.storage|\bCL\b|\bCL-?ODH\b|O2.free|oxygen.free|in the absence of (gaseous )?(O2|oxygen)"))),
        ("cl-comb", "化学链燃烧", rule(R(r"chemical.looping combustion|\bCLC\b|\bCLOU\b|oxygen uncoupling|looping combustion|chemical looping (with oxygen uncoupling|of (solid|coal|biomass) fuel)|in.situ gasification chemical looping|\biG-?CLC\b|\bCDCL\b|coal direct chemical looping"))),
        ("cl-h2", "化学链制氢/重整/气化", rule(R(r"chemical.looping[\w\s-]{0,30}(hydrogen|reform|gasif|steam|water splitting|partial oxidation|syngas|methane conversion|CO2 (splitting|conversion|reduction)|air separation|ammonia|nitrogen|olefin|methanol|ethylene|propylene|aromatics|sulfur|upgrading)|\bCLR\b|\bCLHG\b|\bCLG\b|\bCLSR\b|\bCLDR\b|\bCLPO\b|\bCLMR\b|\bCLWS\b|\bCLAS\b|chemical looping (H2|NH3)|redox looping|thermochemical (water|CO2) splitting|oxygen carrier.*(reform|gasif|hydrogen|syngas)|calcium looping|\bCaL\b|sorption.enhanced (steam )?reforming"), exclude=R(r"dehydrogenation"))),
        ("cl-other", "氧载体与其他化学链", rule(CL), True),
    ]),
    ("psc", "钙钛矿太阳能电池", {C_CHEM, C_MAT, C_ENG, C_PHY, C_ALL}, [
        ("psc-tandem", "叠层电池", rule(PSC, need=[PV, R(r"tandem|perovskite.silicon|perovskite/silicon|perovskite/CIGS|perovskite/organic|perovskite/perovskite|all.perovskite|four.terminal|two.terminal|\b[24]T\b|multijunction|triple.junction")], exclude=NOTPV)),
        ("psc-pbfree", "无铅/锡基钙钛矿", rule(PSC, need=[PV, R(r"lead.free|Pb.free|tin.based|Sn.based|tin perovskite|Sn perovskite|tin.lead|Sn.Pb|Sn-Pb|narrow.band.?gap|bismuth|double perovskite|germanium|\bFASnI3|\bCsSnI3|antimony")], exclude=NOTPV)),
        ("psc-stab", "稳定性与封装", rule(PSC, need=[PV, R(r"stab|degrad|encapsulat|lifetime|durab|operational|damp.heat|thermal cycl|moisture|humid|ion migration|phase segregation|halide segregation|outdoor|light soaking|reliab|recycl|lead leakage|lead sequestration|toxicity")], exclude=NOTPV)),
        ("psc-int", "界面与传输层", rule(PSC, need=[PV, R(r"interface|interfacial|passivat|hole.transport|electron.transport|hole.selective|electron.selective|\bHTLs?\b|\bETLs?\b|\bHTMs?\b|self.assembled monolayer|\bSAMs?\b|spiro|SnO2|NiOx|NiO\b|TiO2|buried|charge (extraction|transport)|contact|carrier.selective|electrode|2D/3D|surface (treatment|reconstruction|modification)")], exclude=NOTPV)),
        ("psc-module", "柔性与大面积组件", rule(PSC, need=[PV, R(r"flexible|large.area|module|scal(able|e.up|ing.up)|minimodule|blade.coat|slot.die|print|roll.to.roll|indoor|semi.?transparent|carbon.based|carbon electrode|fully printed|ambient (air )?fabrication|vacuum.free|upscal")], exclude=NOTPV)),
        ("psc-other", "钙钛矿薄膜与组分", rule(PSC, need=PV, exclude=NOTPV), True),
    ]),
]

FIELDS = {f: label for _, _, _, fs in GROUPS for f, label, *_ in fs}
GROUP_OF = {f: g for g, _, _, fs in GROUPS for f, *_ in fs}
DEFAULT_GROUP = "membrane"
# fields whose recent papers get Chinese summaries in the push
PUSH_GROUP = "membrane"


def classify(title, category=None):
    """Return the list of matching fields (priority order) for a title from a journal of the given CAS category."""
    if not title or NOISE.search(title):
        return []
    out = []
    for gid, _, cats, fs in GROUPS:
        if category and category not in cats:
            continue
        hit = [f for f, _, r, *fb in fs if not fb and r(title)]
        if not hit:
            hit = [f for f, _, r, *fb in fs if fb and r(title)][:1]
        out += hit
    return out


# ---------------------------------------------------------------- Crossref keyword queries
QUERIES = {
    "ml-mem": ["machine learning nanofiltration", "machine learning membrane", "interpretable machine learning membrane"],
    "pa-nf": ["polyamide nanofiltration membrane", "nanofiltration interlayer", "nanofiltration ion selectivity", "nanofiltration interfacial polymerization", "positively charged nanofiltration", "loose nanofiltration"],
    "osn": ["organic solvent nanofiltration", "solvent resistant membrane", "organic solvent reverse osmosis"],
    "cat-ceramic": ["catalytic ceramic membrane", "ceramic membrane peroxymonosulfate", "ceramic membrane ozonation", "catalytic ceramic membrane reactor"],
    "cat-mem": ["catalytic membrane peroxymonosulfate", "catalytic ultrafiltration membrane", "nanoconfined catalytic membrane", "catalytic membrane ozonation", "photocatalytic membrane"],
    "heo": ["high-entropy oxide catalyst", "high-entropy spinel", "high-entropy perovskite catalyst", "methyl mercaptan"],
    "ceramic": ["ceramic membrane", "ceramic ultrafiltration membrane", "ceramic hollow fiber membrane", "oxygen transport membrane perovskite", "silicon carbide membrane"],
    "ro-fo": ["reverse osmosis membrane", "forward osmosis membrane", "thin film composite desalination membrane", "pressure retarded osmosis"],
    "gas-sep": ["gas separation membrane", "CO2 separation membrane", "mixed matrix membrane gas", "hydrogen separation membrane", "carbon molecular sieve membrane"],
    "md": ["membrane distillation", "pervaporation membrane", "membrane crystallization"],
    "iem-ed": ["ion exchange membrane", "electrodialysis", "bipolar membrane electrodialysis", "monovalent selective membrane"],
    "mbr": ["membrane bioreactor", "anaerobic membrane bioreactor", "gravity-driven membrane"],
    "2d-mem": ["graphene oxide membrane separation", "MXene membrane", "covalent organic framework membrane", "metal-organic framework membrane separation", "lamellar membrane ion sieving"],
    "oil-water": ["oil water separation membrane", "emulsion separation membrane", "superwetting membrane oil"],
    "uf-mf": ["ultrafiltration membrane", "microfiltration membrane", "hollow fiber membrane", "electrospun nanofiber membrane filtration"],
    "osmotic-energy": ["osmotic energy conversion membrane", "reverse electrodialysis membrane", "nanofluidic ion transport membrane"],
    "mem-model": ["membrane molecular dynamics simulation separation", "membrane transport model nanofiltration", "membrane CFD simulation"],
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
    "ec-li": ["lithium-ion battery", "lithium metal anode", "nickel-rich cathode", "silicon anode lithium", "lithium battery electrolyte"],
    "ec-ss": ["solid-state battery", "solid electrolyte lithium", "sulfide solid electrolyte", "polymer electrolyte battery"],
    "ec-beyond": ["sodium-ion battery", "aqueous zinc-ion battery", "potassium-ion battery", "zinc anode", "redox flow battery", "magnesium battery"],
    "ec-lis": ["lithium-sulfur battery", "zinc-air battery", "lithium-oxygen battery", "metal-air battery"],
    "ec-sc": ["supercapacitor electrode", "supercapacitor", "pseudocapacitive", "zinc-ion hybrid capacitor"],
    "ec-water": ["hydrogen evolution electrocatalyst", "oxygen evolution electrocatalyst", "water electrolysis", "seawater electrolysis", "anion exchange membrane water electrolyzer", "overall water splitting"],
    "ec-co2": ["CO2 electroreduction", "electrochemical CO2 reduction", "CO2 electrolysis", "CO2RR copper"],
    "ec-n": ["electrochemical nitrate reduction ammonia", "electrocatalytic nitrogen reduction", "urea electrosynthesis", "nitrite electroreduction"],
    "ec-fc": ["oxygen reduction reaction electrocatalyst", "proton exchange membrane fuel cell", "solid oxide fuel cell", "anion exchange membrane fuel cell", "methanol oxidation electrocatalyst"],
    "ec-synth": ["electrosynthesis", "electrochemical H2O2 production", "electrocatalytic oxidation biomass", "organic electrosynthesis", "paired electrolysis"],
    "ec-env": ["electro-Fenton", "electrochemical oxidation wastewater", "capacitive deionization", "electrocatalytic degradation", "microbial fuel cell", "electrochemical advanced oxidation"],
    "ec-sensor": ["electrochemical sensor", "electrochemical biosensor", "electrochemiluminescence", "photoelectrochemical biosensor", "voltammetric determination"],
    "ec-corr": ["corrosion resistance electrochemical", "electrodeposition", "corrosion inhibitor", "micro-arc oxidation coating"],
    "ec-other": ["electrochemical", "electrocatalysis", "photoelectrochemical"],
    "abm": ["agent-based model", "agent-based modeling", "agent-based simulation", "socio-hydrology", "agent-based model flood"],
    "flood": ["flood risk management", "flood risk", "flood resilience", "flood inundation modeling", "urban flooding", "flood adaptation", "flood vulnerability", "flood insurance", "coastal flood"],
    "mip-sensor": ["molecularly imprinted sensor", "molecularly imprinted electrochemical sensor", "molecularly imprinted fluorescent", "molecularly imprinted polymer detection"],
    "mip-sep": ["molecularly imprinted solid-phase extraction", "molecularly imprinted adsorbent", "ion-imprinted polymer", "molecularly imprinted membrane"],
    "mip-other": ["molecularly imprinted polymer", "molecular imprinting", "surface imprinting"],
    "cl-odh": ["chemical looping oxidative dehydrogenation", "oxidative dehydrogenation lattice oxygen", "redox oxidative dehydrogenation", "chemical looping ethane", "selective hydrogen combustion"],
    "cl-comb": ["chemical looping combustion", "oxygen carrier chemical looping combustion", "chemical looping oxygen uncoupling"],
    "cl-h2": ["chemical looping hydrogen", "chemical looping reforming", "chemical looping gasification", "chemical looping methane partial oxidation", "chemical looping CO2 splitting", "calcium looping"],
    "cl-other": ["chemical looping", "oxygen carrier", "chemical looping ammonia", "chemical looping air separation"],
    "psc-tandem": ["perovskite silicon tandem solar cell", "all-perovskite tandem", "perovskite tandem solar cell"],
    "psc-pbfree": ["tin perovskite solar cell", "lead-free perovskite solar cell", "tin-lead perovskite solar cell"],
    "psc-stab": ["perovskite solar cell stability", "perovskite solar cell encapsulation", "perovskite solar cell degradation"],
    "psc-int": ["perovskite solar cell interface passivation", "perovskite solar cell hole transport layer", "self-assembled monolayer perovskite solar cell", "electron transport layer perovskite solar cell"],
    "psc-module": ["perovskite solar module", "flexible perovskite solar cell", "large-area perovskite solar cell", "printed perovskite solar cell"],
    "psc-other": ["perovskite solar cell", "perovskite photovoltaic", "inverted perovskite solar cell", "perovskite film crystallization solar cell"],
}

# journals scanned in full (every article) besides the keyword queries; matched by ISSN against the CAS table
CORE_ISSNS = [
    # membrane / water / environment
    "0376-7388", "0011-9164", "1383-5866", "2772-4212", "0043-1354", "1385-8947", "0013-936X", "2328-8930", "0304-3894", "0926-3373",
    "2213-3437", "0048-9697", "0269-7491", "0160-4120", "0025-326X", "0147-6513", "0013-9351", "0021-9797", "0955-2219", "0272-8842",
    # electrochemistry / energy / perovskite photovoltaics
    "0013-4686", "2405-8297", "1614-6832", "2211-2855", "2380-8195", "1754-5692", "2542-4351", "2058-7546", "2095-4956", "2352-152X",
    "2637-9368", "2667-1417", "0360-3199", "1944-8244", "1613-6810", "1616-301X", "0935-9648", "1433-7851", "0002-7863", "2041-1723",
    "2155-5435", "2050-7488", "0925-4005", "0956-5663", "0003-2700", "0010-938X", "2575-0356", "2567-3165", "1936-0851", "2198-3844",
    # chemical looping / energy engineering / catalysis
    "0306-2619", "0016-2361", "0196-8904", "0378-3820", "0010-2180", "0009-2509", "0360-5442", "1872-2067",
    # molecular imprinting / analytical / food
    "0003-2670", "0039-9140", "0308-8146", "0021-9673", "0026-3672", "0165-9936",
    # flood risk / agent-based modelling
    "0022-1694", "0043-1397", "1027-5606", "1364-8152", "1561-8633", "2212-4209", "2210-6707", "0169-2046", "0959-3780", "2328-4277",
    "0301-4797", "0198-9715", "2095-0055", "1748-9326", "0921-8009",
]

# short names shown on cards for journals not covered by Crossref's short-container-title
ABBR = {
    "0376-7388": "J. Membr. Sci.", "0011-9164": "Desalination", "1383-5866": "Sep. Purif. Technol.", "2772-4212": "J. Membr. Sci. Lett.",
    "0043-1354": "Water Res.", "1385-8947": "Chem. Eng. J.", "0013-936X": "Environ. Sci. Technol.", "2328-8930": "Environ. Sci. Technol. Lett.",
    "0304-3894": "J. Hazard. Mater.", "0926-3373": "Appl. Catal. B", "2213-3437": "J. Environ. Chem. Eng.", "0048-9697": "Sci. Total Environ.",
    "0269-7491": "Environ. Pollut.", "0160-4120": "Environ. Int.", "0025-326X": "Mar. Pollut. Bull.", "0147-6513": "Ecotoxicol. Environ. Saf.",
    "0013-9351": "Environ. Res.", "0021-9797": "J. Colloid Interface Sci.", "0955-2219": "J. Eur. Ceram. Soc.", "0272-8842": "Ceram. Int.",
    "0013-4686": "Electrochim. Acta", "2405-8297": "Energy Storage Mater.", "1614-6832": "Adv. Energy Mater.", "2211-2855": "Nano Energy",
    "2380-8195": "ACS Energy Lett.", "1754-5692": "Energy Environ. Sci.", "2542-4351": "Joule", "2058-7546": "Nat. Energy",
    "2095-4956": "J. Energy Chem.", "2352-152X": "J. Energy Storage", "2637-9368": "Carbon Energy", "2667-1417": "eScience",
    "0360-3199": "Int. J. Hydrogen Energy", "1944-8244": "ACS Appl. Mater. Interfaces", "1613-6810": "Small", "1616-301X": "Adv. Funct. Mater.",
    "0935-9648": "Adv. Mater.", "1433-7851": "Angew. Chem.", "0002-7863": "J. Am. Chem. Soc.", "2041-1723": "Nat. Commun.",
    "2155-5435": "ACS Catal.", "2050-7488": "J. Mater. Chem. A", "0925-4005": "Sens. Actuators B", "0956-5663": "Biosens. Bioelectron.",
    "0003-2700": "Anal. Chem.", "0010-938X": "Corros. Sci.", "2575-0356": "Energy Environ. Mater.", "2567-3165": "EcoMat", "1936-0851": "ACS Nano",
    "2198-3844": "Adv. Sci.", "0306-2619": "Appl. Energy", "0016-2361": "Fuel", "0196-8904": "Energy Convers. Manage.",
    "0378-3820": "Fuel Process. Technol.", "0010-2180": "Combust. Flame", "0009-2509": "Chem. Eng. Sci.", "0360-5442": "Energy",
    "1872-2067": "Chin. J. Catal.", "0003-2670": "Anal. Chim. Acta", "0039-9140": "Talanta", "0308-8146": "Food Chem.",
    "0021-9673": "J. Chromatogr. A", "0026-3672": "Microchim. Acta", "0165-9936": "TrAC", "0022-1694": "J. Hydrol.",
    "0043-1397": "Water Resour. Res.", "1027-5606": "Hydrol. Earth Syst. Sci.", "1364-8152": "Environ. Model. Softw.",
    "1561-8633": "Nat. Hazards Earth Syst. Sci.", "2212-4209": "Int. J. Disaster Risk Reduct.", "2210-6707": "Sustain. Cities Soc.",
    "0169-2046": "Landsc. Urban Plan.", "0959-3780": "Glob. Environ. Change", "2328-4277": "Earth's Future", "0301-4797": "J. Environ. Manage.",
    "0198-9715": "Comput. Environ. Urban Syst.", "2095-0055": "Int. J. Disaster Risk Sci.", "1748-9326": "Environ. Res. Lett.",
    "0921-8009": "Ecol. Econ.", "0959-6526": "J. Clean. Prod.", "0169-4332": "Appl. Surf. Sci.", "1001-0742": "J. Environ. Sci.",
}
