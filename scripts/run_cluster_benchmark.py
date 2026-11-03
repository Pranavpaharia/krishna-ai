import json
import os
import sys
sys.path.insert(0, ".")

os.environ["KRSNA_OFFLINE"] = "1"
from krsna_ai.core.store import Store
from krsna_ai.core import retriever

store = Store.load()

def score(rows_file):
    with open(rows_file, "r", encoding="utf-8") as f:
        rows = [json.loads(l) for l in f if l.strip()]
    hits = total = 0
    rr = 0.0
    topic_hits = 0
    for q in rows:
        top = [h["id"] for h in retriever.retrieve(store, q["question"])]
        expected = q["expected"]
        found = [e for e in expected if e in top]
        hits += len(found)
        total += len(expected)
        ranks = [top.index(e) + 1 for e in expected if e in top]
        rr += (1 / ranks[0] if ranks else 0.0)
        if found:
            topic_hits += 1
    n = len(rows)
    return {
        "n": n,
        "recall": hits / total if total > 0 else 0,
        "hits": hits,
        "total": total,
        "topic_hits": topic_hits,
        "mrr": rr / n if n > 0 else 0
    }

print("=" * 65)
print("THUNDERBOLT FULL BENCHMARK SUITE REPORT")
print("=" * 65)
files = [
    ("Bhagavad Gita Golden", "tests/eval_golden.jsonl"),
    ("Bhagavad Gita Holdout", "tests/eval_holdout.jsonl"),
    ("Ashtavakra Gita Golden", "tests/eval_ashtavakra_golden.jsonl"),
    ("Ashtavakra Gita Holdout", "tests/eval_ashtavakra_holdout.jsonl"),
]

for label, path in files:
    r = score(path)
    pct = r["topic_hits"] / r["n"] * 100 if r["n"] > 0 else 0
    print(f"{label:24} (n={r['n']:02d}) | Hits: {r['topic_hits']:02d}/{r['n']:02d} ({pct:5.1f}%) | Recall@6: {r['recall']:.3f} | MRR: {r['mrr']:.3f}")
print("=" * 65)
