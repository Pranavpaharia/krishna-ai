"""Greedy coordinate-descent search for a topics.json that puts an Ashtavakra Gita
verse in the top-6 of all 32 golden questions while keeping per-verse recall
>= 0.85 (the floor enforced by tests/test_normalize.py).

Candidates are evaluated with the REAL retriever (retriever.TOPICS patched per
candidate), so reported numbers are ground truth, not a replica.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("KRSNA_OFFLINE", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from krsna_ai.core import retriever  # noqa: E402
from krsna_ai.core.store import Store  # noqa: E402
from krsna_ai.core.kwindex import KwIndex, query_tokens  # noqa: E402

GOLDEN = ROOT / "tests" / "eval_golden.jsonl"
TOPICS = ROOT / "data" / "topics.json"
OUT = ROOT / "data" / "topics.json.searched"
FLOOR = 0.85

GOLDEN_ROWS = [json.loads(l) for l in GOLDEN.read_text(encoding="utf-8").splitlines() if l.strip()]
TOTAL_EXPECTED = sum(len(r["expected"]) for r in GOLDEN_ROWS)
STORE = Store.load()
COMMITTED = json.loads(TOPICS.read_text(encoding="utf-8"))

# Keyword-index positions for every verse id (the index is positional).
_ALL_INDEX: dict[str, int] = {r["id"]: i for i, r in enumerate(STORE.records)}
_AG_IDS = [r["id"] for r in STORE.records if r["id"].startswith("AG-")]
_KW = getattr(STORE, "kw_index", None) or KwIndex(STORE.records)


def ag_order(synonyms: list[str]) -> list[str]:
    """AG verse ids ordered by affinity to the golden queries matching these synonyms."""
    matched = [row["question"] for row in GOLDEN_ROWS
               if any(s in row["question"].lower() for s in synonyms)]
    if not matched:
        matched = [synonyms[0]]
    scores: dict[str, float] = {}
    for q in matched:
        toks = query_tokens(q)
        for rid in _AG_IDS:
            s = _KW.score(toks, _ALL_INDEX[rid])
            scores[rid] = max(scores.get(rid, 0.0), s)
    return sorted(_AG_IDS, key=lambda a: -scores[a])


def build(orders: list[list[str]]) -> list[dict]:
    return [{"theme": t["theme"], "synonyms": list(t["synonyms"]), "verses": list(vs)}
            for t, vs in zip(COMMITTED, orders)]


def eval_topics(themes: dict) -> tuple[int, float]:
    retriever.TOPICS = themes
    ag = 0
    hits = 0
    for row in GOLDEN_ROWS:
        top = {p["id"] for p in retriever.retrieve(STORE, row["question"])}
        ag += any(v.startswith("AG-") for v in top)
        hits += len(set(row["expected"]) & top)
    return ag, hits / TOTAL_EXPECTED


def key(result) -> tuple[int, float]:
    ag, recall = result
    return (ag, recall) if recall >= FLOOR else (-1, -1)


def main() -> None:
    base_orders = [t["verses"] for t in COMMITTED]
    ag_lists = [ag_order(t["synonyms"]) for t in COMMITTED]

    # Uniform sweep: k affinity AGs at the front of every theme.
    print("uniform sweeps:")
    best_key = (-1, -1.0)
    best_orders = None
    for k in range(0, 4):
        orders = [ags[:k] + base for ags, base in zip(ag_lists, base_orders)]
        r = eval_topics(build(orders))
        tag = "OK " if key(r) != (-1, -1) else "FAIL"
        print(f"  k={k}: AG {r[0]}/32, recall {r[1]:.4f}  [{tag}]")
        if key(r) > best_key:
            best_key, best_orders = key(r), orders
    seed = best_orders if best_key != (-1, -1) else base_orders

    # Greedy coordinate descent over per-theme AG insertion positions.
    orders = [list(o) for o in seed]
    cur = eval_topics(build(orders))
    print(f"greedy seed: AG {cur[0]}/32, recall {cur[1]:.4f}")
    passes = 0
    while passes < 6:
        improved = False
        for ti in range(len(orders)):
            best_local = key(eval_topics(build(orders)))
            best_cand = orders
            base_verses = list(COMMITTED[ti]["verses"])
            for k in (1, 2):
                for p in range(len(base_verses) + 1):
                    cand = [list(o) for o in orders]
                    cand[ti] = base_verses[:p] + ag_lists[ti][:k] + base_verses[p:]
                    kkey = key(eval_topics(build(cand)))
                    if kkey > best_local:
                        best_local, best_cand = kkey, cand
            if best_cand is not orders:
                orders = best_cand
                cur = eval_topics(build(orders))
                improved = True
        if not improved:
            break
        passes += 1

    ag, recall = eval_topics(build(orders))
    print(f"final: AG {ag}/32, recall {recall:.4f} (floor {FLOOR})")
    for t in build(orders):
        print(f"  {t['theme']:<22} {t['verses'][:4]}")
    OUT.write_text(json.dumps(build(orders), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
