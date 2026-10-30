"""Quality check: run a real two-turn conversation through the engine on each
working free endpoint, so speed is measured against grounding, not just latency.

Turn 1 = MODE 1 (fast path), turn 2 = MODE 2 (depth path). Both use the same
candidate model so the endpoint is judged on the whole conversation.
"""
from __future__ import annotations

import asyncio

from krsna_ai import config
from krsna_ai.core import engine
from krsna_ai.core.store import Store

CANDIDATES = [
    "TokenHarbor (DeepSeek-V4-Flash)",
    "openrouter/laguna-s-2.1:free",
    "openrouter/north-mini-code:free",
    "Groq (GPT-OSS-120B)",
    "TokenHarbor (MiMo-v2.5)",
]

Q1 = "I am always anxious about my future and cannot sleep at night"
Q2 = "I am a student and I overthink what others think of me; the anxiety is worst at night"


def words(s: str) -> int:
    return len(s.split())


async def main() -> None:
    store = Store.load()
    print(f"{'model':36s} {'turn1 s':>8s} {'w1':>4s} {'ok1':>5s} {'turn2 s':>8s} {'w2':>4s} {'ok2':>5s}")
    rows = []
    for model in CANDIDATES:
        config.FAST_MODEL = model
        config.CHAT_MODEL = model
        r1 = await engine.answer_question(store, Q1)
        r2 = await engine.answer_question(store, Q2, history=[
            {"role": "user", "content": Q1}, {"role": "assistant", "content": r1["answer"]}])
        rows.append((model, r1, r2))
        print(f"{model:36s} {r1['latency_ms']/1000:8.1f} {words(r1['answer']):4d} "
              f"{str(r1['citations_ok']):>5s} {r2['latency_ms']/1000:8.1f} {words(r2['answer']):4d} "
              f"{str(r2['citations_ok']):>5s}")

    print("\n=== sample MODE 1 answer (best endpoint) ===")
    best = max(rows, key=lambda r: (r[1]["citations_ok"], r[2]["citations_ok"], -r[1]["latency_ms"]))
    print(f"{best[0]} — turn 1 ({best[1]['latency_ms']/1000:.1f}s):")
    print(best[1]["answer"])
    print(f"\n{best[0]} — turn 2 ({best[2]['latency_ms']/1000:.1f}s):")
    print(best[2]["answer"])


if __name__ == "__main__":
    asyncio.run(main())
