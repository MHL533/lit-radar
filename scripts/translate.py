"""Chinese translation of titles, keywords and abstracts with a local LLM (llama.cpp server, OpenAI-compatible API).

  python scripts/translate.py titles    --minutes 300 [--part 0 --parts 1] [--out out/]
  python scripts/translate.py keywords  --minutes 60
  python scripts/translate.py abstracts --minutes 300 [--part 3 --parts 16]

With --out, results go to files in that folder (for parallel jobs; scripts/apply_translations.py merges them);
without it they are written straight into the library.
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402

SERVER = os.environ.get("LLM_SERVER", "http://127.0.0.1:8080")
GLOSSARY = ("术语参考：nanofiltration 纳滤；reverse osmosis 反渗透；forward osmosis 正渗透；ultrafiltration 超滤；membrane distillation 膜蒸馏；"
            "pervaporation 渗透汽化；thin-film composite 薄膜复合；interfacial polymerization 界面聚合；polyamide 聚酰胺；fouling 污染；"
            "perovskite 钙钛矿；peroxymonosulfate 过一硫酸盐；peroxydisulfate/persulfate 过硫酸盐；singlet oxygen 单线态氧；advanced oxidation 高级氧化；"
            "single-atom catalyst 单原子催化剂；dual-atom 双原子；metal-organic framework 金属有机框架（MOF）；covalent organic framework 共价有机框架（COF）；"
            "anode 负极（电池）/阳极（电解、腐蚀、燃料电池）；cathode 正极（电池）/阴极（电解、燃料电池）；electrolyte 电解质/电解液；"
            "solid electrolyte interphase 固体电解质界面膜（SEI）；oxygen evolution reaction 析氧反应；hydrogen evolution reaction 析氢反应；"
            "oxygen reduction reaction 氧还原反应；Faradaic efficiency 法拉第效率；capacitive deionization 电容去离子；layered double hydroxide 层状双氢氧化物；"
            "molecularly imprinted 分子印迹；chemical looping 化学链；oxygen carrier 载氧体；oxidative dehydrogenation 氧化脱氢；"
            "agent-based model 基于智能体的模型（ABM）；flood risk 洪水风险；inundation 淹没；microplastics 微塑料；nanoplastics 纳米塑料；"
            "Donnan 唐南；zeta potential Zeta 电位；high-entropy 高熵；spinel 尖晶石；heterojunction 异质结。")
SYS_TITLE = ("你是资深科技文献译者。把用户给出的英文论文标题译成规范、简洁、符合中文学术习惯的中文标题。化学式、元素符号、材料与器件缩写"
             "（如 MOF、PEMFC、ZIF-8、Li-S）、基因与物种名、人名保持原样。" + GLOSSARY + "只输出译文，不要解释。")
SYS_TERM = ("你是资深科技术语译者。把用户给出的英文学术关键词译成中文规范术语（如有通用缩写可保留，如 MOF、SEI）。" + GLOSSARY + "只输出译文，不要解释。")
SYS_ABS = ("你是资深科技文献译者。把英文论文摘要译成准确、通顺的中文学术摘要。化学式、缩写、数值与单位保持原样，不增删信息。"
           + GLOSSARY + "只输出译文。")


def chat(system, user, max_tokens):
    body = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.1, "max_tokens": max_tokens, "cache_prompt": True}
    for attempt in range(3):
        try:
            req = urllib.request.Request(SERVER + "/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=900) as r:
                return json.load(r)["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print("  llm retry", attempt, str(e)[:120], flush=True)
            time.sleep(5)
    return ""


CJK = re.compile(r"[一-鿿]")


def translate_one(text, system):
    zh = chat(system, text, 160)
    zh = re.sub(r"^(译文|翻译|中文)[:：]\s*", "", zh.splitlines()[0] if zh else "").strip().strip("“”\"")
    return zh if CJK.search(zh) else ""


def translate_abstract(en):
    parts, cur = [], ""
    for sent in re.split(r"(?<=[.!?])\s+", en):
        if len(cur) + len(sent) > 1400 and cur:
            parts.append(cur)
            cur = ""
        cur = (cur + " " + sent).strip()
    if cur:
        parts.append(cur)
    zh = "".join(chat(SYS_ABS, p, int(len(p) * 0.9) + 100) for p in parts)
    return zh if CJK.search(zh) else ""


def in_part(pid_, part, parts):
    return parts <= 1 or int(lib.AbstractStore.bucket(pid_), 16) % parts == part


def run_batches(batches, fn, deadline, workers=4):
    done = []
    with cf.ThreadPoolExecutor(workers) as ex:
        futs = {}
        it = iter(batches)
        for b in it:
            futs[ex.submit(fn, b)] = b
            if len(futs) >= workers * 2:
                break
        while futs:
            f = next(cf.as_completed(futs))
            b = futs.pop(f)
            done.append((b, f.result()))
            if time.time() < deadline:
                nxt = next(it, None)
                if nxt is not None:
                    futs[ex.submit(fn, nxt)] = nxt
    return done


def titles(args, deadline):
    recs = [p for p in lib.load_all().values() if not p.get("tz") and in_part(p["id"], args.part, args.parts)]
    recs.sort(key=lambda p: p.get("d", ""), reverse=True)
    print("titles to translate:", len(recs), flush=True)
    result, t0 = {}, time.time()
    for n, (p, z) in enumerate(run_batches(recs, lambda p: translate_one(p["t"], SYS_TITLE), deadline), 1):
        if z:
            result[p["id"]] = z
        if n % 1000 == 0:
            print(f"  {len(result)} titles, {len(result) / (time.time() - t0):.1f}/s", flush=True)
    print("translated titles:", len(result), flush=True)
    return result


def keywords(args, deadline):
    kz = lib.kw_zh()
    vocab = {}
    for p in lib.load_all().values():
        for k in p.get("kw", []):
            if k not in kz and in_part(k, args.part, args.parts):
                vocab[k] = vocab.get(k, 0) + 1
    todo = sorted(vocab, key=lambda k: -vocab[k])
    print("keywords to translate:", len(todo), flush=True)
    result = {}
    for k, z in run_batches(todo, lambda k: translate_one(k, SYS_TERM), deadline):
        if z:
            result[k] = z
    print("translated keywords:", len(result), flush=True)
    return result


def abstracts(args, deadline):
    store = lib.ABSTRACTS
    os.makedirs(os.path.join(lib.DATA, "abs"), exist_ok=True)
    buckets = sorted(f[:3] for f in os.listdir(os.path.join(lib.DATA, "abs")) if f.endswith(".json"))
    todo = [(b, k) for b in buckets if args.parts <= 1 or int(b, 16) % args.parts == args.part
            for k, v in store.load(b).items() if v[0] and not v[1]]
    print("abstracts to translate:", len(todo), flush=True)
    n, touched = 0, set()
    for (b, k), zh in run_batches(todo, lambda bk: translate_abstract(store.load(bk[0])[bk[1]][0]), deadline):
        if zh:
            store.put(k, zh=zh)
            touched.add(b)
            n += 1
        if n and n % 200 == 0:
            store.flush()
            print("  abstracts", n, flush=True)
    store.flush()
    if args.out:  # hand the changed bucket files to the merge job
        import shutil
        os.makedirs(os.path.join(args.out, "abs"), exist_ok=True)
        for b in touched:
            shutil.copy(store.path(b), os.path.join(args.out, "abs", b + ".json"))
    print("translated abstracts:", n, flush=True)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["titles", "keywords", "abstracts"])
    ap.add_argument("--minutes", type=float, default=60)
    ap.add_argument("--part", type=int, default=0)
    ap.add_argument("--parts", type=int, default=1)
    ap.add_argument("--out")
    args = ap.parse_args()
    deadline = time.time() + args.minutes * 60
    if args.what == "abstracts":
        abstracts(args, deadline)  # writes its own bucket files (disjoint per part)
        return
    res = titles(args, deadline) if args.what == "titles" else keywords(args, deadline)
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        json.dump(res, open(os.path.join(args.out, f"{args.what}-{args.part}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    else:
        import apply_translations
        apply_translations.apply({args.what: [res]})


if __name__ == "__main__":
    main()
