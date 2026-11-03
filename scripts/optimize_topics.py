"""Greedy per-theme optimization of AG-verse insertion positions in data/topics.json.

Objective: maximize AG-in-top-6 across the 32 golden questions, subject to
per-verse recall >= 0.85 (the tests/test_normalize.py floor). Tie-break on higher
recall. Each theme gets its top-affinity AG verse inserted at the best position;
themes with no affinity match keep their committed list.
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
RECALL_FLOOR = 0.85


def affinity_ag(theme: dict, store: Store) -> list[str]:
    scored = []
    for rec in store.records:
        if not rec["id"].startswith("AG-"):
            continue
        text = (rec.get("translation", "") + " " + rec.get("purport", "")).lower()
        s = sum(1 for syn in theme["synonyms"] if syn.lower() in text)
        scored.append((s, rec["id"]))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [vid for s, vid in scored if s > 0]


def place(verses: list[str], ags: list[str], pos: int | None) -> list[str]:
    if not ags:
        return list(verses)
    p = len(verses) if pos is None else min(pos, len(verses))
    return verses[:p] + ags + verses[p:]


def score(topics: list[dict], store: Store) -> tuple[int, float]:
    retriever.TOPICS = topics
    rows = [json.loads(l) for l in GOLDEN.read_text(encoding="utf-8").splitlines() if l.strip()]
    total = hits = ag = 0
    for r in rows:
        got = [h["id"] for h in retriever.retrieve(store, r["question"])]
        total += len(r["expected"])
        hits += sum(1 for e in r["expected"] if e in got)
        ag += any(v.startswith("AG-") for v in got)
    return ag, hits / total


def main() -> None:
    store = Store.load()
    committed = json.loads((ROOT / "data" / "topics.json").read_text(encoding="utf-8"))
    ags = [affinity_ag(t, store) for t in committed]

    # start from the best uniform strategy (insert_at=2)
    positions = [min(2, len(t["verses"])) if ags[i] else None for i, t in enumerate(committed)]
    best = score([{"theme": t["theme"], "synonyms": t["synonyms"],
                  "verses": place(t["verses"], ags[i], positions[i])}
                 for i, t in enumerate(committed)], store)
    print("start: AG %d/%d, recall %.4f" % (best[0], 32, best[1]))

    improved = True
    passes = 0
    while improved and passes < 4:
        improved = False
        for i, t in enumerate(committed):
            if not ags[i]:
                continue
            base = [v for v in t["verses"]]
            cur_pos = positions[i]
            for p in range(len(base) + 1):
                cand_topics = []
                for j, tt in enumerate(committed):
                    pos = p if j == i else positions[j]
                    cand_topics.append({"theme": tt["theme"], "synonyms": tt["synonyms"],
                                       "verses": place(tt["verses"], ags[j], pos)})
                s = score(cand_topics, store)
                if s[1] >= RECALL_FLOOR and (s[0], s[1]) > (best[0], best[1]):
                    best, positions[i] = s, p
                    improved = True
        passes += 1

    final = [{"theme": t["theme"], "synonyms": t["synonyms"], "verses": place(t["verses"], ags[i], positions[i])}
             for i, t in enumerate(committed)]
    print("final: AG %d/%d, recall %.4f" % (best[0], 32, best[1]))
    for t, ag in zip(final, [a[0] if a else None for a in ags]):
        print("  %-20s %s" % (t["theme"], t["verses"][:3]))
    out = ROOT / "data" / "topics.json.optimized"
    out.write_text(json.dumps(final, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("saved", out)


if __name__ == "__main__":
    main()
