"""Terminal chat with the Krishna AI assistant (Task 12).

Run:  python -m krsna_ai.cli
      python -m krsna_ai.cli "I am anxious about my future"
      python -m krsna_ai.cli --voice ashtavakra "What is the mind, and how is it free?"
      KRSNA_VOICE=ashtavakra python -m krsna_ai.cli
"""
from __future__ import annotations

import asyncio
import sys

from krsna_ai import config
from krsna_ai.core import persona
from krsna_ai.core.engine import answer_question
from krsna_ai.core.store import Store

# Windows consoles default to cp1252, which cannot encode IAST diacritics (ṅ, ṛ, ñ) that appear in
# translations. A successful turn then died at print with UnicodeEncodeError. Replace rather than
# crash: the answer text itself is unaffected, only its console rendering.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def _voice_and_question(argv: list[str]) -> tuple[str, str]:
    """Split an optional ``--voice <name>`` from the question text."""
    voice = config.VOICE
    if "--voice" in argv:
        i = argv.index("--voice")
        if i + 1 < len(argv):
            voice = argv[i + 1]
            argv = argv[:i] + argv[i + 2:]
    return voice, " ".join(argv)


async def _ask(store: Store, question: str, voice: str) -> None:
    print("\nYou:", question)
    res = await answer_question(store, question, voice=voice)
    print(f"\n{persona.VOICE_LABELS[res['voice']]}:\n" + res["answer"])
    print(f"\n[citations ok: {res['citations_ok']} | retried: {res['retried']} | "
          f"references: {len(res['references'])}]")


async def _main() -> None:
    store = Store.load()
    print(f"Loaded {len(store.records)} verses from the Bhagavad Gita, Uddhava-gita and Ashtavakra Gita.")
    voice, question = _voice_and_question(sys.argv[1:])
    if voice not in persona.VOICES:
        print(f"Unknown voice {voice!r}; expected one of {sorted(persona.VOICES)}.")
        return
    print(f"Voice: {persona.VOICE_LABELS[voice]}")
    if question:
        await _ask(store, question, voice)
        return
    print(f"Ask {persona.VOICE_LABELS[voice]} about any life problem (empty line or 'quit' to exit).")
    history: list[dict] = []
    while True:
        q = input("\nYou: ").strip()
        if not q or q.lower() in {"quit", "exit"}:
            break
        res = await answer_question(store, q, history=history, voice=voice)
        print(f"\n{persona.VOICE_LABELS[res['voice']]}:\n" + res["answer"])
        print(f"\n[citations ok: {res['citations_ok']} | references: {len(res['references'])}]")
        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": res["answer"]})


if __name__ == "__main__":
    asyncio.run(_main())
