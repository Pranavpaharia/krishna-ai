"""Terminal chat with the Krishna AI assistant (Task 12).

Run:  python -m krsna_ai.cli
      python -m krsna_ai.cli "I am anxious about my future"
"""
from __future__ import annotations

import asyncio
import sys

from krsna_ai.core.engine import answer_question
from krsna_ai.core.store import Store


async def _ask(store: Store, question: str) -> None:
    print("\nYou:", question)
    res = await answer_question(store, question)
    print("\nKrishna:\n" + res["answer"])
    print(f"\n[citations ok: {res['citations_ok']} | retried: {res['retried']} | "
          f"references: {len(res['references'])}]")


async def _main() -> None:
    store = Store.load()
    print(f"Loaded {len(store.records)} verses from the Bhagavad Gita and Uddhava-gita.")
    if len(sys.argv) > 1:
        await _ask(store, " ".join(sys.argv[1:]))
        return
    print("Ask Krishna about any life problem (empty line or 'quit' to exit).")
    history: list[dict] = []
    while True:
        q = input("\nYou: ").strip()
        if not q or q.lower() in {"quit", "exit"}:
            break
        res = await answer_question(store, q, history=history)
        print("\nKrishna:\n" + res["answer"])
        print(f"\n[citations ok: {res['citations_ok']} | references: {len(res['references'])}]")
        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": res["answer"]})


if __name__ == "__main__":
    asyncio.run(_main())
