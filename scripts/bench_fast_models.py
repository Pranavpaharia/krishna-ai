"""Benchmark candidate fast models on a realistic first-turn prompt.

Builds the real prompt (retrieved verses + persona) and times each model with a
small budget, reporting wall time, answer length, and reasoning tokens.
"""
from __future__ import annotations

import asyncio
import time

import httpx

from krsna_ai import config
from krsna_ai.core import persona, retriever
from krsna_ai.core.store import Store

CANDIDATES = [
    "Groq (Qwen3.8-27B)",
    "TokenHarbor (DeepSeek-V4-Flash)",
    "TokenHarbor (Qwen3.8-Flash)",
    "LightFury (Qwen3.8-Flash)",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
]

QUESTION = "I am always anxious about my future and cannot sleep at night"
MAX_TOKENS = 1500


async def main() -> None:
    store = Store.load()
    passages = retriever.retrieve(store, QUESTION)
    context = retriever.format_context(passages)
    messages = persona.build_messages(QUESTION, context)

    headers = {"Authorization": f"Bearer {config.LLM_API_KEY}"}
    url = f"{config.LLM_BASE_URL}/chat/completions"

    print(f"prompt tokens approx: {sum(len(m['content'].split()) for m in messages)} words")
    async with httpx.AsyncClient(timeout=180) as client:
        for model in CANDIDATES:
            body = {
                "model": model,
                "messages": messages,
                "max_tokens": MAX_TOKENS,
                "temperature": 0.6,
            }
            t0 = time.perf_counter()
            try:
                r = await client.post(url, headers=headers, json=body)
                r.raise_for_status()
                data = r.json()
                choice = data["choices"][0]
                content = (choice["message"].get("content") or "").strip()
                usage = data.get("usage", {})
                details = usage.get("completion_tokens_details") or {}
                words = len(content.split())
                print(
                    f"{model:38s} {time.perf_counter() - t0:6.1f}s "
                    f"words={words:4d} finish={choice.get('finish_reason')} "
                    f"completion={usage.get('completion_tokens')} reasoning={details.get('reasoning_tokens')}"
                )
            except Exception as exc:  # noqa: BLE001 - benchmark reporting
                print(f"{model:38s} FAILED after {time.perf_counter() - t0:6.1f}s: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
