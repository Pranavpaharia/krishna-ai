"""Compare topic-map placement strategies on tests/eval_golden.jsonl.

Strategies:
  committed   - data/topics.json as-is
  ag_front1   - 1 best-affinity AG verse at rank 0, originals after
  ag_front2   - 2 best-affinity AG verses at ranks 0-1, originals after
  ag_last     - originals first, 1 best-affinity AG verse appended at the end

Reports per-verse recall (must stay >= 0.85) and AG-in-top-6 count (target 32/32).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from krsna_ai.core.store import Store
from krsna_ai.core import retriever

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "eval_golden.jsonl"


def ag_ranked(theme: dict, store: Store) -> list[str]:
    scored = []
    for rec in store.records:
        if not rec["id"].startswith("AG-"):
            continue
        text = (rec.get("translation", "") + " " + rec.get("purport", "")).lower()
        s = sum(1 for syn in theme["synonyms"] if syn.lower() in text)
        scored.append((s, rec["id"]))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [vid for vid_s in scored for vid in [vid_s[1]] if vid_s[0] > 0]


def build(committed: list[dict], store: Store, strategy: str) -> list[dict]:
    out = []
    for t in committed:
        ags = ag_ranked(t, store)
        if strategy == "committed":
            verses = t["verses"]
        elif strategy == "ag_front1":
            verses = ags[:1] + t["verses"]
        elif strategy == "ag_front2":
            verses = ags[:2] + t["verses"]
        elif strategy == "ag_last":
            base = t["verses"]
            rest = [v for v in t["verses"] if not v.startswith("AG-")]
            verses = t["verses"] + ags[:1] if not t["verses"][0].startswith("AG-") else t["verses"]
            # committed already has no AG; append one AG at the end
            verses = t["verses"] + ags[:1]
        out.append({"theme": t["theme"], "synonyms": t["synonyms"], "verses": verses})
    return out


def evaluate(topics: list[dict]) -> tuple[float, int, int]:
    retriever.TOPICS = topics
    store = Store.load()
    rows = [json.loads(l) for l in GOLDEN.read_text(encoding="utf-8").splitlines() if l.strip()]
    total = hits = ag_present = 0
    for r in rows:
        got = [h["id"] for h in retriever.retrieve(store, r["question"])]
        exp = r["expected"]
        total += len(exp)
        hits += sum(1 for e in exp if e in got)
        ag_present += any(g.startswith("AG-") for g in got)
    return hits / total, ag_present, total


def main() -> None:
    store = Store.load()
    committed = json.loads((ROOT / "data" / "topics.json").read_text(encoding="utf-8"))
    for strategy in ("committed", "ag_last", "ag_front1", "ag_front2"):
        topics = build(committed, store, strategy)
        recall, ag, total = evaluate(topics)
        print("%-12s recall %.3f | AG in %d/%d" % (strategy, recall, ag, total))


if __name__ == "__main__":
    main()
