"""LLM client: async OpenAI-compatible calls via the LiteLLM gateway.

Primary model ``muse-wonder-1.0``; on transport/5xx failure, one retry on
``muse-spark-1.3`` (plan risk table). No streaming in v1 (chat endpoint
returns the verified answer whole, after citation checking).

Reasoning models bill ``reasoning_tokens`` against ``max_tokens``, so a run that
thinks past the budget returns ``finish_reason="length"`` with EMPTY content. That
is intermittent — the same prompt succeeds or fails run to run — so a truncated
run gets one escalated-budget retry on the same model before falling back. An empty
answer is never treated as an answer.
"""
from __future__ import annotations

import httpx

from krsna_ai import config

# Second budget for a run that thought its way past the first one.
ESCALATED_MAX_TOKENS = 12000


class GatewayError(RuntimeError):
    """Gateway was reachable but produced no usable answer."""


async def _complete(client: httpx.AsyncClient, model: str, messages: list[dict],
                    temperature: float, max_tokens: int) -> tuple[str, str | None]:
    """One call. Returns (content, finish_reason); content is '' when the run was truncated."""
    resp = await client.post("/chat/completions", json={
        "model": model, "messages": messages,
        "temperature": temperature, "max_tokens": max_tokens,
    })
    resp.raise_for_status()
    data = resp.json()
    choice = (data.get("choices") or [{}])[0]
    content = str((choice.get("message") or {}).get("content") or "").strip()
    return content, choice.get("finish_reason")


async def chat(messages: list[dict], temperature: float = 0.6,
               max_tokens: int = config.MAX_TOKENS, fast: bool = False) -> str:
    """One grounded generation. With ``fast=True`` (first-turn short answers)
    the call goes to the fast model with a small budget, falling back to the
    flagship; otherwise the flagship runs first with the full budget."""
    headers = {"Content-Type": "application/json"}
    if config.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
    last_err: Exception | None = None
    if fast:
        models = (config.FAST_MODEL, config.CHAT_MODEL)
        # A short MODE-1 answer needs no 12k escalation — doubling the small budget
        # is enough to cover a run that thought past it, and keeps the first response fast.
        budgets = (config.FAST_MAX_TOKENS, config.FAST_MAX_TOKENS * 2)
    else:
        models = (config.CHAT_MODEL, config.CHAT_MODEL_FALLBACK)
        budgets = (max_tokens, ESCALATED_MAX_TOKENS)
    async with httpx.AsyncClient(base_url=config.LLM_BASE_URL, headers=headers, timeout=300) as client:
        for model in models:
            for budget in budgets:
                try:
                    content, finish = await _complete(client, model, messages, temperature, budget)
                    if content:
                        return content
                    last_err = GatewayError(f"empty content from {model} (finish={finish}, "
                                            f"max_tokens={budget})")
                    if finish != "length":
                        break  # not a budget problem; a bigger budget will not help
                except Exception as exc:  # noqa: BLE001 - fall back once, then raise
                    last_err = exc
                    break  # transport failure: go to the next model, not a bigger budget
    raise GatewayError(f"LLM gateway failed on both models: {last_err}")
