"""Rebuild data/topics.json so every theme surfaces at least one Ashtavakra Gita verse.

For each theme in the committed map, pick the AG verses whose stored text matches the
theme's synonyms and insert them at the front of the verse list (highest boost
ranks). Evaluate against tests/eval_golden.jsonl: target AG in 32/32 golden top-6
results, per-verse recall >= 0.85. Writes only when both targets pass.
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
AG_PER_THEME = 2  # AG verses to insert per theme


def affinity(theme: dict, store: Store) -> list[str]:
    """AG verse ids ranked by substring overlap with the theme's synonyms."""
    scored = []
    for rec in store.records:
        if not rec["id"].startswith("AG-"):
            continue
        text = (rec.get("translation", "") + " " + rec.get("purport", "")).lower()
        s = sum(1 for syn in theme["synonyms"] if syn.lower() in text)
        scored.append((s, rec["id"]))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [vid for s, vid in scored[:AG_PER_THEME] if s > 0]


def build(store: Store) -> list[dict]:
    committed = json.loads((ROOT / "data" / "topics.json").read_text(encoding="utf-8"))
    out = []
    for t in committed:
        ag = affinity(t, store)
        out.append({"theme": t["theme"], "synonyms": t["synonyms"],
                   "verses": ag + t["verses"]})
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
            no_ag.append((r["question"][:48], got))
    return hits / total, ag_present, total, no_ag


def main() -> None:
    store = Store.load()
    committed = json.loads((ROOT / "data" / "topics.json").read_text(encoding="utf-8"))
    base = evaluate(committed)
    print("committed: per-verse recall %.3f, AG in %d/%d" % (base[0], base[1], base[2]))

    candidate = build(store)
    cand = evaluate(candidate)
    print("candidate: per-verse recall %.3f, AG in %d/%d" % (cand[0], cand[1], cand[2]))
    for q, got in cand[3]:
        print("  no-AG:", q, "top6:", got[:4])

    if cand[1] == cand[2] and cand[0] >= 0.85:
        out = ROOT / "data" / "topics.json"
        out.write_text(json.dumps(candidate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("PASS -> wrote", out)
    else:
        out = ROOT / "data" / "topics.json.candidate"
        out.write_text(json.dumps(candidate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("not written to live path; candidate saved to", out)


if __name__ == "__main__":
    main()
