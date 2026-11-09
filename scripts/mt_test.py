import json, time, os
os.environ.setdefault("OMP_NUM_THREADS", "4")
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
torch.set_num_threads(4)
S = json.load(open("scripts/mt_sample.json"))
def run(name, texts, **gen):
    tok = AutoTokenizer.from_pretrained(name, **({"src_lang": "eng_Latn"} if "nllb" in name else {}))
    m = AutoModelForSeq2SeqLM.from_pretrained(name).eval()
    t = time.time(); out = []
    for i in range(0, len(texts), 32):
        b = tok(texts[i:i + 32], return_tensors="pt", padding=True, truncation=True, max_length=256)
        with torch.no_grad():
            g = m.generate(**b, max_new_tokens=256, **gen)
        out += tok.batch_decode(g, skip_special_tokens=True)
    return out, time.time() - t
for name, gen in [("Helsinki-NLP/opus-mt-en-zh", {"num_beams": 1}), ("Helsinki-NLP/opus-mt-en-zh", {"num_beams": 3}), ("facebook/nllb-200-distilled-600M", {"num_beams": 1, "forced_bos_token_id": None})]:
    if "nllb" in name:
        tok = AutoTokenizer.from_pretrained(name, src_lang="eng_Latn"); gen["forced_bos_token_id"] = tok.convert_tokens_to_ids("zho_Hans")
    texts = S["titles"] + S["keywords"] + [S["abstract"]]
    out, sec = run(name, texts, **gen)
    print(f"===== {name} {gen.get('num_beams')} beams: {sec:.1f}s for {len(texts)} texts")
    for a, b in zip(texts, out):
        print(a[:110], "\n   ->", b)
