"""Find the AG insertion rank that maximizes AG-in-top-6 while keeping recall >= 0.85."""
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
    return [vid for s, vid in scored if s > 0]


def build(committed: list[dict], store: Store, insert_at: int) -> list[dict]:
    out = []
    for t in committed:
        ags = ag_ranked(t, store)[:1]
        verses = list(t["verses"])
        if ags:
            pos = min(insert_at, len(verses))
            verses = verses[:pos] + ags + verses[pos:]
        out.append({"theme": t["theme"], "synonyms": t["synonyms"], "verses": verses})
    return out


def evaluate(topics: list[dict]) -> tuple[float, int, int, list[str]]:
    retriever.TOPICS = topics
    store = Store.load()
    rows = [json.loads(l) for l in GOLDEN.read_text(encoding="utf-8").splitlines() if l.strip()]
    total = hits = ag_present = 0
    no_ag = []
    for r in rows:
        got = [h["id"] for h in retriever.retrieve(store, r["question"])]
        exp = r["expected"]
        total += len(exp)
        hits += sum(1 for e in exp if e in got)
        if any(g.startswith("AG-") for g in got):
            ag_present += 1
        else:
            no_ag.append(r["question"][:44])
    return hits / total, ag_present, total, no_ag


def main() -> None:
    store = Store.load()
    committed = json.loads((ROOT / "data" / "topics.json").read_text(encoding="utf-8"))
    best = None
    for insert_at in range(0, 6):
        topics = build(committed, store, insert_at)
        recall, ag, total, no_ag = evaluate(topics)
        ok = recall >= 0.85
        print("insert_at=%d  recall %.3f %s | AG %d/%d" % (insert_at, recall, "OK " if ok else "LOW", ag, total))
        if best is None or (ag, recall) > (best[1], best[0]):
            best = (recall, ag, insert_at)
    print("best insert_at:", best[2])
    topics = build(committed, store, best[2])
    recall, ag, total, no_ag = evaluate(topics)
    for q in no_ag:
        print("  no-AG:", q)


if __name__ == "__main__":
    main()
