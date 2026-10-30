"""Benchmark the free online endpoints on the LiteLLM gateway and measure the
prompt we actually send for a Krishna question.

Phase A — every free/cloud endpoint, one realistic first-turn prompt each:
wall time, prompt tokens, completion tokens, finish reason.
Phase B — prompt-size statistics over a sample of realistic questions.
"""
from __future__ import annotations

import asyncio
import statistics
import time

import httpx
import tiktoken

from krsna_ai import config
from krsna_ai.core import persona, retriever
from krsna_ai.core.store import Store

FREE_ENDPOINTS = [
    "TokenHarbor (DeepSeek-V4-Flash)",
    "TokenHarbor (Qwen3.8-Flash)",
    "TokenHarbor (MiMo-v2.5)",
    "Groq (Qwen3.8-27B)",
    "Groq (GPT-OSS-120B)",
    "Groq (Allam-2-7B)",
    "openrouter/qwen3.8-27b:free",
    "openrouter/nemotron-3.5-lightning:free",
    "openrouter/laguna-s-2.1:free",
    "openrouter/inkling:free",
    "openrouter/north-mini-code:free",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "nvidia/llama-3.2-11b-vision-instruct",
    "stepfun-ai/step-5-preview",
]

SAMPLE_QUESTIONS = [
    "I am always anxious about my future and cannot sleep at night",
    "I am a student and I overthink what others think of me; the anxiety is worst at night",
    "How do I stop procrastinating and stay disciplined?",
    "My mind will not stop racing at night and I feel like a failure as a student",
    "Tell me a short proverb about patience.",
    "What should I do when I am angry at my parents?",
    "I feel lonely even when I am with people. What does Krishna say about this?",
    "How can I focus during study without getting distracted by my phone?",
    "I am afraid of failing my exams. How do I handle the fear?",
    "Give me one verse about gratitude.",
]

ENC = tiktoken.encoding_for_model("gpt-4")
MAX_TOKENS = 1500
HEADERS = {"Content-Type": "application/json", "Authorization": f"Bearer {config.LLM_API_KEY}"}


async def call(client: httpx.AsyncClient, model: str, messages: list[dict]) -> dict:
    t0 = time.perf_counter()
    try:
        r = await client.post("/chat/completions", json={
            "model": model, "messages": messages,
            "temperature": 0.6, "max_tokens": MAX_TOKENS,
        })
        r.raise_for_status()
        d = r.json()
        choice = (d.get("choices") or [{}])[0]
        usage = d.get("usage") or {}
        return {
            "model": model,
            "seconds": round(time.perf_counter() - t0, 1),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "finish": choice.get("finish_reason"),
            "content": str((choice.get("message") or {}).get("content") or "").strip(),
        }
    except Exception as exc:  # noqa: BLE001 - benchmark reporting
        return {"model": model, "seconds": round(time.perf_counter() - t0, 1), "error": str(exc)[:120]}


async def main() -> None:
    store = Store.load()
    q0 = SAMPLE_QUESTIONS[0]
    msgs0 = persona.build_messages(q0, retriever.format_context(retriever.retrieve(store, q0)))

    async with httpx.AsyncClient(base_url=config.LLM_BASE_URL, headers=HEADERS, timeout=120) as client:
        print("=== PHASE A: free endpoints, same first-turn prompt ===")
        print(f"{'model':40s} {'time':>6s} {'prompt_tok':>10s} {'compl_tok':>9s} finish")
        results = []
        for model in FREE_ENDPOINTS:
            r = await call(client, model, msgs0)
            results.append(r)
            if "error" in r:
                print(f"{model:40s} {r['seconds']:6.1f} {'FAILED':>10s} {'':>9s} {r['error']}")
            else:
                print(f"{model:40s} {r['seconds']:6.1f} {r['prompt_tokens']:>10d} {r['completion_tokens']:>9d} {r['finish']}")

        print("\n=== PHASE B: prompt size per question (what we actually send) ===")
        pt, cw, cc, sys_t, usr_t = [], [], [], [], []
        for q in SAMPLE_QUESTIONS:
            msgs = persona.build_messages(q, retriever.format_context(retriever.retrieve(store, q)))
            sys_txt = msgs[0]["content"]
            usr_txt = msgs[-1]["content"]
            sys_t.append(len(ENC.encode(sys_txt)))
            usr_t.append(len(ENC.encode(usr_txt)))
            cw.append(len(q.split()))
            cc.append(len(q))
            r = await call(client, config.FAST_MODEL, msgs)
            if "error" not in r and r.get("prompt_tokens"):
                pt.append(r["prompt_tokens"])

        def avg(xs): return round(statistics.mean(xs), 1) if xs else 0
        print(f"question text      avg words={avg(cw)} avg chars={avg(cc)}")
        print(f"system prompt      avg tokens={avg(sys_t)}")
        print(f"user turn          avg tokens={avg(usr_t)}")
        print(f"full prompt        avg tokens={avg(pt)} (measured by the gateway, n={len(pt)})")
        print(f"system share of prompt: {avg(sys_t) / avg(pt) * 100:.1f}%")

        best = next((r for r in results if r["model"] == config.FAST_MODEL and "error" not in r), None)
        if best:
            print(f"\n=== sample answer from {config.FAST_MODEL} ===")
            print(best["content"])


if __name__ == "__main__":
    asyncio.run(main())
