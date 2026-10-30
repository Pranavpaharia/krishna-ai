"""Engine tests with a fake LLM — no network, no gateway.

The engine's contract is what matters here: a clean answer passes untouched, a bad answer is
retried once, and if it is still bad the fabricated parts are stripped and the removal is
reported. Retrieval is forced offline (lexical-only) so the retrieved ids are deterministic.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from krsna_ai import config
from krsna_ai.core import audit, citations, engine, llm, retriever
from krsna_ai.core.store import Store

ROOT = Path(r"U:\MetaHackathon")


@pytest.fixture(scope="module")
def store() -> Store:
    return Store.load()


@pytest.fixture
def offline(monkeypatch) -> None:
    monkeypatch.setattr(config, "OFFLINE", True)


@pytest.fixture(autouse=True)
def _audit_to_tmp(tmp_path, monkeypatch) -> None:
    """Keep scripted test turns out of the production audit log."""
    monkeypatch.setattr(audit, "AUDIT_PATH", tmp_path / "audit.jsonl")


def fake_llm(answers: list[str], monkeypatch) -> list[int]:
    """Return an async stand-in for llm.chat that replays scripted answers in order."""
    calls = [0]

    async def chat(messages, temperature: float = 0.6, max_tokens: int = 4000,
                   fast: bool = False) -> str:
        i = calls[0]
        calls[0] += 1
        return answers[i] if i < len(answers) else answers[-1]

    monkeypatch.setattr(llm, "chat", chat)
    return calls


def clean_answer(store: Store, question: str) -> tuple[str, str]:
    """Build an answer that quotes the top retrieved verse verbatim."""
    hit = retriever.retrieve(store, question)[0]
    quote = hit["translation"].strip()
    answer = f"He says: \"{quote}\"\n\nReferences: ({hit['id']})"
    return answer, hit["id"]


def test_clean_answer_passes_without_retry(store, offline, monkeypatch):
    question = "I get angry at coworkers and then feel ashamed"
    answer, vid = clean_answer(store, question)
    calls = fake_llm([answer], monkeypatch)

    res = asyncio.run(engine.answer_question(store, question))

    assert calls[0] == 1, "a verified answer must not trigger a regeneration"
    assert res["citations_ok"] is True
    assert res["retried"] is False
    assert res["adjusted"] is None
    assert res["mode"] == "lexical"
    assert vid in res["cited"] if "cited" in res else vid in [r["id"] for r in res["references"]]


def test_bad_answer_retries_then_enforce_reports_removal(store, offline, monkeypatch):
    question = "I get angry at coworkers and then feel ashamed"
    first = 'Krishna says: "A quoted line that is not in the store at all."\n\nReferences: (Bhagavad-gita 99.99)'
    second = 'Still wrong: "another line that is not in the store" (BG-99.99).\n\nReferences: (BG-99.99)'
    calls = fake_llm([first, second], monkeypatch)

    res = asyncio.run(engine.answer_question(store, question))

    assert calls[0] == 2, "the first answer must trigger exactly one regeneration"
    assert res["retried"] is True
    assert res["adjusted"] is not None, "enforce() must report what it removed"
    assert "BG-99.99" in res["adjusted"]["unknown_ids"]
    assert res["adjusted"]["bad_quotes"], "the unverifiable quote must be reported"
    assert "BG-99.99" not in res["answer"], "no invented id may survive to the user"
    assert "not in the store" not in res["answer"], "no fabricated quote may survive to the user"
    # Nothing verifiable is left, so the answer must not be presented as citation-verified.
    assert res["citations_ok"] is False


def test_off_scope_quote_is_corrected(store, offline, monkeypatch):
    """A real quote from a verse that was not retrieved is off-scope, not a bad quote."""
    question = "I get angry at coworkers and then feel ashamed"
    hits = [h["id"] for h in retriever.retrieve(store, question)]
    other = next((vid for vid in ("BG-2.20", "BG-6.5", "BG-18.66") if vid not in hits), None)
    if other is None:
        pytest.skip("no out-of-scope verse available for this question")
    rec = store.get(other)
    answer = f'"{rec["translation"].strip()}"\n\nReferences: ({other})'
    calls = fake_llm([answer, answer], monkeypatch)

    res = asyncio.run(engine.answer_question(store, question))
    assert res["retried"] is True
    assert res["adjusted"] is not None
    assert res["adjusted"]["off_scope"] == [other]


def test_audit_record_never_raises_on_oserror(monkeypatch):
    """Telemetry must not break an answer when the audit file cannot be written."""
    monkeypatch.setattr(audit, "AUDIT_PATH", Path("Z:/definitely/not/writable/audit.jsonl"))
    audit.record({"question": "x", "ok": True})  # must return silently


def test_audit_writes_one_json_line_per_turn(store, offline, monkeypatch, tmp_path):
    monkeypatch.setattr(audit, "AUDIT_PATH", tmp_path / "audit.jsonl")
    answer, _ = clean_answer(store, "I feel anxious about the future")
    fake_llm([answer], monkeypatch)

    asyncio.run(engine.answer_question(store, "I feel anxious about the future"))

    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["mode"] == "lexical"
    assert entry["ok"] is True
    assert entry["retried"] is False
    assert entry["retrieved"]


def test_first_turn_routes_fast_follow_up_routes_full(store, offline, monkeypatch):
    """First question -> fast model path; once history exists -> full-depth path."""
    answer, vid = clean_answer(store, "I feel anxious about the future")
    seen = []

    async def chat(messages, temperature: float = 0.6, max_tokens: int = 4000,
                   fast: bool = False) -> str:
        seen.append(fast)
        return answer

    monkeypatch.setattr(llm, "chat", chat)
    asyncio.run(engine.answer_question(store, "I feel anxious about the future"))
    asyncio.run(engine.answer_question(
        store, "and what about my sleepless nights?",
        history=[{"role": "user", "content": "I feel anxious about the future"},
                 {"role": "assistant", "content": answer}]))

    assert seen[0] is True, "a first turn must use the fast path"
    assert seen[1] is False, "a follow-up with history must use the full-depth path"
