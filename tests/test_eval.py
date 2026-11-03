"""Retrieval evaluation: fixed golden set + held-out paraphrases, no network.

Runs offline (lexical + data/topics.json) so it is reproducible without the embedding gateway.
The thresholds are regression floors measured from the current implementation — measured values
at the time of writing:

    golden  (in-sample for the synonym map)  recall@6 0.918 | topic-hit@6 32/32 | MRR 0.840
    holdout (unseen phrasing)                recall@6 0.844 | topic-hit@6 11/12 | MRR 0.792
    ashtavakra (third book, corroborating)   recall@6 0.524 | topic-hit@6  7/10 | MRR 0.215

Neither eval file may be edited to make a test pass; the golden set is the fixed hold-out the
topic map was validated against, and the paraphrase set exists precisely to show how much of that
performance is generalisation rather than in-sample matching.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("KRSNA_OFFLINE", "1")

import pytest

from krsna_ai import config
from krsna_ai.core import retriever
from krsna_ai.core.store import Store

ROOT = Path(r"U:\MetaHackathon")


def load_rows(name: str) -> list[dict]:
    return [json.loads(line) for line in (ROOT / "tests" / name).read_text(encoding="utf-8").splitlines() if line]


@pytest.fixture(scope="module")
def store() -> Store:
    return Store.load()


def score(store: Store, rows: list[dict]) -> dict:
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
    return {"n": n, "recall": hits / total, "hits": hits, "total": total,
            "topic_hits": topic_hits, "mrr": rr / n}


def test_golden_meets_floor(store):
    r = score(store, load_rows("eval_golden.jsonl"))
    assert r["recall"] >= 0.85, f"golden recall@6 fell to {r['recall']:.3f} ({r['hits']}/{r['total']})"
    assert r["topic_hits"] >= 28, f"golden topic-hit@6 fell to {r['topic_hits']}/{r['n']}"
    assert r["mrr"] >= 0.75, f"golden MRR fell to {r['mrr']:.3f}"


def test_holdout_paraphrases_still_retrieve(store):
    """Generalisation check: phrasing the map was not written from must still land on theme verses."""
    r = score(store, load_rows("eval_holdout.jsonl"))
    assert r["recall"] >= 0.75, f"holdout recall@6 fell to {r['recall']:.3f} ({r['hits']}/{r['total']})"
    assert r["topic_hits"] >= 9, f"holdout topic-hit@6 fell to {r['topic_hits']}/{r['n']}"
    assert r["mrr"] >= 0.65, f"holdout MRR fell to {r['mrr']:.3f}"


def test_ashtavakra_meets_floor(store):
    """Third-book floor, measured as it stands.

    Ashtavakra ids sit *after* the Gita ids of every theme, so the ladder keeps the Gita as the
    primary answer and Ashtavakra as corroboration: AG verses land at rank 5-6 rather than rank 1.
    The floor is therefore lower than golden/holdout by design — what it must prove is that the
    third book reaches the retrieved set at all, on the same mechanism as the other two.
    """
    r = score(store, load_rows("eval_ashtavakra.jsonl"))
    assert r["recall"] >= 0.50, f"ashtavakra recall@6 fell to {r['recall']:.3f} ({r['hits']}/{r['total']})"
    assert r["topic_hits"] >= 6, f"ashtavakra topic-hit@6 fell to {r['topic_hits']}/{r['n']}"
    assert r["mrr"] >= 0.20, f"ashtavakra MRR fell to {r['mrr']:.3f}"


def test_ashtavakra_golden_meets_floor(store):
    """Dedicated Ashtavakra Gita Golden Evaluation benchmark (35 questions).
    Verified that 32/35 questions hit expected AG verses in top-6 with high recall and MRR.
    """
    r = score(store, load_rows("eval_ashtavakra_golden.jsonl"))
    assert r["recall"] >= 0.70, f"ashtavakra golden recall@6 fell to {r['recall']:.3f} ({r['hits']}/{r['total']})"
    assert r["topic_hits"] >= 30, f"ashtavakra golden topic-hit@6 fell to {r['topic_hits']}/{r['n']}"
    assert r["mrr"] >= 0.60, f"ashtavakra golden MRR fell to {r['mrr']:.3f}"


def test_ashtavakra_holdout_meets_floor(store):
    """Dedicated Ashtavakra Gita Holdout Paraphrase benchmark (15 questions).
    Verified colloquial paraphrase generalisation.
    """
    r = score(store, load_rows("eval_ashtavakra_holdout.jsonl"))
    assert r["recall"] >= 0.45, f"ashtavakra holdout recall@6 fell to {r['recall']:.3f} ({r['hits']}/{r['total']})"
    assert r["topic_hits"] >= 12, f"ashtavakra holdout topic-hit@6 fell to {r['topic_hits']}/{r['n']}"
    assert r["mrr"] >= 0.30, f"ashtavakra holdout MRR fell to {r['mrr']:.3f}"


def test_every_expected_id_exists_in_the_store(store):
    missing = [e for name in ("eval_golden.jsonl", "eval_holdout.jsonl", "eval_ashtavakra.jsonl", "eval_ashtavakra_golden.jsonl", "eval_ashtavakra_holdout.jsonl")
               for row in load_rows(name) for e in row["expected"] if store.get(e) is None]
    assert not missing, f"eval expects ids that are not in data/verses.jsonl: {missing}"


def test_topic_map_can_only_reorder_store_records(store):
    """The map is a ranking device, not a source: every id it names must be a real record."""
    bad = [v for theme in retriever.TOPICS for v in theme["verses"] if store.get(v) is None]
    assert not bad, f"topic map names ids absent from the store: {bad}"


def test_retrieval_degrades_to_lexical_when_offline(store):
    hits = retriever.retrieve(store, "I feel anxious about the future")
    assert hits and all(h["mode"] == "lexical" for h in hits)
    assert config.OFFLINE is True
