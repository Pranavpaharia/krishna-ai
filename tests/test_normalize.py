"""B3: query normalisation — diacritic-insensitive folding and Hinglish mapping.

The eval sets contain plain English, so they cannot show the value of folding; these tests
cover the case the eval sets miss: a user typing diacritics loosely, or in Hinglish.
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("KRSNA_OFFLINE", "1")

from krsna_ai.core import retriever
from krsna_ai.core.kwindex import query_tokens, tokenize
from krsna_ai.core.store import Store

ROOT = Path(r"U:\MetaHackathon")


def test_diacritic_typing_matches_the_corpus() -> None:
    assert tokenize("kṛṣṇa") == tokenize("krishna")
    assert tokenize("bhagavad-gītā") == tokenize("bhagavad gita")
    assert tokenize("prema") == tokenize("prēma")


def test_hinglish_query_maps_to_corpus_words() -> None:
    assert "anger" in query_tokens("mujhe gussa aata hai")
    assert "grief" in query_tokens("mera dukh bahut hai")
    assert "guilt" in query_tokens("mujhe sharm hoti hai")


def test_hinglish_question_retrieves_the_right_theme() -> None:
    store = Store.load()
    hits = retriever.retrieve(store, "mujhe bahut gussa aata hai aur phir sharm hoti hai")
    ids = {h["id"] for h in hits}
    assert {"BG-2.62", "BG-2.63"} & ids
    assert all(h["mode"] == "lexical" for h in hits)


def test_folding_does_not_change_the_measured_recall() -> None:
    """Folding is a robustness win, not a recall win: the golden floors must still hold."""
    store = Store.load()
    rows = [
        line for line in (ROOT / "tests" / "eval_golden.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    import json

    hits = total = 0
    for line in rows:
        q = json.loads(line)
        got = {h["id"] for h in retriever.retrieve(store, q["question"])}
        total += len(q["expected"])
        hits += sum(1 for e in q["expected"] if e in got)
    assert hits / total >= 0.85
