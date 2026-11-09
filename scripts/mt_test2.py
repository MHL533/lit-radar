import json, time, subprocess, sys, urllib.request, concurrent.futures as cf
S = json.load(open("scripts/mt_sample.json"))
model = sys.argv[1]
SYSTEM = ("你是资深科技文献译者。把英文论文标题逐条译成规范、简洁的中文学术标题。化学式、材料与器件缩写（如 MOF、PEMFC、ZIF-8）、"
          "物种与地名保持原样或用通用译名。术语参考：nanofiltration 纳滤；reverse osmosis 反渗透；perovskite 钙钛矿；peroxymonosulfate 过一硫酸盐；"
          "interfacial polymerization 界面聚合；anode 负极（电池）/阳极（电解、腐蚀）；cathode 正极（电池）/阴极（电解）；electrolyte 电解质（电池）/电解液；"
          "oxygen evolution reaction 析氧反应；hydrogen evolution 析氢；solid electrolyte interphase 固体电解质界面膜（SEI）；molecularly imprinted 分子印迹；"
          "chemical looping 化学链；oxygen carrier 载氧体；agent-based model 基于智能体的模型；flood 洪水；microplastics 微塑料。"
          "按输入编号逐行输出“编号. 译文”，不要解释。")
def ask(items):
    body = {"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "\n".join(f"{i+1}. {t}" for i, t in enumerate(items))}],
            "temperature": 0.1, "max_tokens": 120 * len(items)}
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=600))
    return r["choices"][0]["message"]["content"], r.get("usage", {})
texts = S["titles"] + S["keywords"]
chunks = [texts[i:i + 8] for i in range(0, len(texts), 8)]
t = time.time(); toks = 0; outs = []
with cf.ThreadPoolExecutor(4) as ex:
    for out, u in ex.map(ask, chunks):
        outs.append(out); toks += u.get("completion_tokens", 0)
el = time.time() - t
print(f"===== {model}: {el:.1f}s for {len(texts)} items, {toks} completion tokens, {toks/el:.1f} tok/s")
for c, o in zip(chunks, outs):
    print("\n".join(c)); print("--->"); print(o); print()
t = time.time(); body = {"messages": [{"role": "system", "content": "你是资深科技文献译者。把英文摘要译成准确、通顺的中文，术语规范，化学式和缩写保持原样，只输出译文。"}, {"role": "user", "content": S["abstract"]}], "temperature": 0.1, "max_tokens": 600}
req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
r = json.load(urllib.request.urlopen(req, timeout=600)); print("ABSTRACT", round(time.time()-t,1), "s:", r["choices"][0]["message"]["content"])
