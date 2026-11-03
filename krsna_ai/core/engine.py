"""Answer engine: question -> retrieve -> prompt -> LLM -> citation check.

Enforcement flow (plan §5): generate; verify citations and quotes against the *retrieved*
passages; if anything fails, regenerate ONCE with the failures named; if it still fails, strip
the fabricated parts and mark the answer as adjusted. An answer is never allowed to carry an
invented reference out the door, and a degraded answer is never presented as verified.

Every turn is written to data/audit.jsonl so the grounding rate is measurable.
"""
from __future__ import annotations

import time

from krsna_ai import config
from krsna_ai.core import audit, citations, llm, persona, retriever
from krsna_ai.core.store import Store


def _failure_note(report: dict) -> str:
    parts = []
    if report["unknown_ids"]:
        parts.append(f"unknown references {report['unknown_ids']}")
    if report["bad_quotes"]:
        parts.append(f"unverifiable quotes {report['bad_quotes']}")
    if report["off_scope"]:
        parts.append(
            "quotes taken from verses you were not given: "
            + ", ".join(i["verse_id"] for i in report["off_scope"])
        )
    if report["missing_refs"]:
        parts.append("no References: line")
    return "; ".join(parts) or "grounding errors"


async def answer_question(
    store: Store,
    question: str,
    history: list[dict] | None = None,
    top_k: int = config.TOP_K,
    voice: str = config.VOICE,
) -> dict:
    """Answer one user turn with verified, grounded references.

    ``history`` may contain prior ``{role, content}`` turns from the UI. It helps the model
    understand short follow-ups, but retrieval and citation checking always run against the
    current question and the passages actually retrieved.

    ``voice`` names the single persona. It is validated here so no caller can silently
    reintroduce a second voice; the grounding contract is unchanged, so every quote is
    still verified verbatim against the store.
    """
    started = time.perf_counter()
    voice = str(voice).strip().lower()
    if voice not in persona.VOICES:
        raise ValueError(f"unknown voice {voice!r}; expected one of {sorted(persona.VOICES)}")
    # First question of a conversation -> fast model + short MODE-1 answer;
    # any prior turns -> flagship model + full MODE-2 depth.
    is_first = bool(config.FAST_FIRST_TURN) and not history
    passages = await retriever.retrieve_async(store, question, top_k)
    retrieved_ids = [p["id"] for p in passages]
    context = retriever.format_context(passages)
    messages = persona.build_messages(question, context, history=history, voice=voice)

    answer = await llm.chat(messages, fast=is_first)
    report = citations.check(answer, store, retrieved=retrieved_ids)

    retried = False
    retry_error: str | None = None
    if not report["ok"]:
        retry_msgs = messages + [
            {"role": "assistant", "content": answer},
            {"role": "user", "content": (
                f"Your answer has grounding errors: {_failure_note(report)}. Rewrite it using "
                "ONLY the passages given, quoting Translations exactly and listing their [IDs] "
                "in the References: line.")},
        ]
        # A failed rewrite must not throw away an answer that already exists. The rewrite is an
        # improvement, not the only source of truth: if the gateway truncates it, enforcement
        # below still strips whatever cannot be verified from the first answer.
        try:
            answer = await llm.chat(retry_msgs, fast=is_first)
            report = citations.check(answer, store, retrieved=retrieved_ids)
            retried = True
        except Exception as exc:  # noqa: BLE001 - keep the first answer, degrade instead of failing
            retry_error = str(exc)

    adjusted: dict | None = None
    if not report["ok"]:
        result = citations.enforce(answer, report, store)
        answer = result["answer"]
        adjusted = result["removed"]
        report = citations.check(answer, store, retrieved=retrieved_ids)

    refs = []
    for vid in report["cited"]:
        rec = store.get(vid)
        if rec:
            refs.append({"id": vid, "ref": rec["ref"],
                         "pdf_page": rec["pdf_page"], "book": rec["book"]})

    latency_ms = round((time.perf_counter() - started) * 1000)
    audit.record({
        "question": question,
        "voice": voice,
        "mode": passages[0].get("mode") if passages else None,
        "fast": is_first,
        "retrieved": retrieved_ids,
        "cited": report["cited"],
        "ok": bool(report["ok"]),
        "retried": retried,
        "retry_error": retry_error,
        "adjusted": adjusted,
        "ocr_noise": report["ocr_noise"],
        "latency_ms": latency_ms,
    })

    return {
        "answer": answer,
        "voice": voice,
        "references": refs,
        "citations_ok": bool(report["ok"]),
        "retried": retried,
        "retry_error": retry_error,
        "adjusted": adjusted,
        "mode": passages[0].get("mode") if passages else None,
        "latency_ms": latency_ms,
        "retrieved": [{"id": p["id"], "ref": p["ref"], "score": p["score"]} for p in passages],
    }
