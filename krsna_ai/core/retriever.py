"""Retriever: user question -> the verses Krishna's answer must stand on.

Hybrid scoring (embedding-only scores proved nearly flat on this corpus, so lexical evidence
carries real weight and canonical verses are pinned by an explicit, inspectable topic map):

    score = 0.45 * embedding_cosine
          + 0.35 * keyword overlap over the stored English text (idf-weighted)
          + topic boost for classic life-problem themes
          - 0.08 for chapter summaries (they rank below verses for the same theme)

The topic map only re-orders store records; it can never introduce a verse that is not in the
books. Every id below was verified in data/verses.jsonl.

Resilience: if the embedding gateway is unreachable, scoring falls back to lexical-only and the
hit records the mode, so retrieval still works offline instead of raising. Query embeddings are
cached because the same question is often re-asked across a conversation.
"""
from __future__ import annotations

import json
import logging
from collections import OrderedDict
from pathlib import Path

import numpy as np

from krsna_ai import config
from krsna_ai.core.kwindex import KwIndex, query_tokens
from krsna_ai.core.store import Store

log = logging.getLogger("krsna_ai.retriever")

W_EMB = 0.45
W_KW = 0.35
SUMMARY_PENALTY = -0.08
EMB_CACHE_MAX = 256
BOOST_MAX = 0.60          # boost for the first verse of a matched theme; falls by 0.05 per rank
BOOST_STEP = 0.05

# Topic -> canonical verse ids (verified against data/verses.jsonl). Loaded from data/topics.json
# when present (synonym sets that survive paraphrase); this map is the fallback so the retriever
# still works if the data file is missing.
_FALLBACK_TOPICS: dict[str, list[str]] = {
    "anxiety|anxious|worried|worry|fear|afraid|future": ["BG-6.5", "BG-6.6", "BG-2.47", "BG-18.66", "BG-4.10"],
    "grief|grieving|sorrow|passed away|death of|lost my (mother|father|parent|wife|husband|child|friend)|bereav": ["BG-2.20", "BG-2.13", "BG-2.27", "BG-2.11", "BG-8.6"],
    "anger|angry|rage|furious|temper|shout": ["BG-2.62", "BG-2.63", "BG-3.37", "BG-16.21", "BG-5.26"],
    "attachment|attached|letting go|let go|obsess|someone who left|broke up|breakup": ["SB-11.8.37", "SB-11.8.44", "SB-11.8.30", "BG-2.62", "BG-2.64"],
    "failure|failed|defeat|unsuccessful|give up|giving up": ["BG-2.47", "BG-2.48", "BG-18.47", "BG-3.19"],
    "indecision|confused|dilemma|cannot decide|which path|don't know what to do": ["BG-2.7", "BG-18.63", "BG-18.58", "BG-4.34"],
    "lonely|loneliness|alone|isolated|no one understands": ["BG-6.30", "BG-9.29", "BG-10.20", "BG-7.18"],
    "insult|insulted|humiliat|criticis|tolerate|mocked": ["SB-11.23.2", "SB-11.23.42", "BG-12.13", "BG-12.18", "BG-5.18"],
    "purpose|meaning of life|direction in life|why am i here": ["BG-18.46", "BG-3.9", "BG-18.66"],
    "family conflict|parents don't|fight with my (parents|family|brother|sister)|relatives": ["SB-11.17.44", "BG-1.43"],
    "restless mind|can't concentrate|cannot concentrate|focus|distract|mind wanders": ["BG-6.26", "BG-6.35", "BG-6.34", "BG-6.5"],
    "lust|temptation|craving|addict": ["BG-3.37", "BG-3.39", "BG-2.70", "BG-3.41"],
    "ego|proud|pride|arrogant|boast": ["BG-3.27", "SB-11.23.30", "BG-18.17"],
    "jealous|envy|envious": ["BG-12.13", "BG-16.19"],
    "lazy|laziness|procrastinat|no motivation|demotivat": ["BG-18.39", "BG-3.8", "BG-6.16"],
    "guilt|ashamed|regret": ["BG-18.66", "BG-9.30", "BG-4.36"],
    "stress|pressure|burnout|exhausted": ["BG-6.5", "BG-2.48", "BG-6.17", "BG-3.19"],
}


def _load_topics() -> list[dict]:
    """Read data/topics.json; fall back to the built-in map if it is missing or unreadable."""
    path = config.DATA_DIR / "topics.json"
    try:
        topics = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [{"theme": pat, "synonyms": [pat], "verses": ids} for pat, ids in _FALLBACK_TOPICS.items()]
    clean = [t for t in topics if isinstance(t, dict) and t.get("synonyms") and t.get("verses")]
    return clean or [{"theme": pat, "synonyms": [pat], "verses": ids} for pat, ids in _FALLBACK_TOPICS.items()]


TOPICS: list[dict] = _load_topics()


def _topic_boost(question: str) -> dict[str, float]:
    """Bounded, capped boost for themes matched by any synonym (never extra query tokens)."""
    q = question.lower()
    boost: dict[str, float] = {}
    for theme in TOPICS:
        if any(s in q for s in theme["synonyms"]):
            for rank, vid in enumerate(theme["verses"]):
                boost[vid] = max(boost.get(vid, 0.0), BOOST_MAX - BOOST_STEP * rank)
    return boost


_emb_cache: OrderedDict[str, np.ndarray] = OrderedDict()


def _cache_get(text: str) -> np.ndarray | None:
    vec = _emb_cache.get(text)
    if vec is not None:
        _emb_cache.move_to_end(text)
    return vec


def _cache_put(text: str, vec: np.ndarray) -> None:
    _emb_cache[text] = vec
    _emb_cache.move_to_end(text)
    while len(_emb_cache) > EMB_CACHE_MAX:
        _emb_cache.popitem(last=False)


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if config.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
    return headers


def _normalize(vec: np.ndarray) -> np.ndarray:
    return vec / max(float(np.linalg.norm(vec)), 1e-9)


def _embed_query(text: str) -> np.ndarray | None:
    """Sync embedding (CLI/tests). Returns None when the gateway is unreachable."""
    if config.OFFLINE:
        return None
    cached = _cache_get(text)
    if cached is not None:
        return cached
    import httpx

    try:
        with httpx.Client(base_url=config.LLM_BASE_URL, headers=_headers(), timeout=60) as client:
            resp = client.post("/embeddings", json={"model": config.EMBED_MODEL, "input": [text]})
            resp.raise_for_status()
            vec = np.array(resp.json()["data"][0]["embedding"], dtype=np.float32)
    except Exception as exc:  # noqa: BLE001 - offline retrieval must degrade, not crash
        log.warning("embedding failed (%s); falling back to lexical-only scoring", exc)
        return None
    vec = _normalize(vec)
    _cache_put(text, vec)
    return vec


async def _embed_query_async(text: str) -> np.ndarray | None:
    """Async embedding for the request path (never blocks the event loop)."""
    if config.OFFLINE:
        return None
    cached = _cache_get(text)
    if cached is not None:
        return cached
    import httpx

    try:
        async with httpx.AsyncClient(base_url=config.LLM_BASE_URL, headers=_headers(), timeout=60) as client:
            resp = await client.post("/embeddings", json={"model": config.EMBED_MODEL, "input": [text]})
            resp.raise_for_status()
            vec = np.array(resp.json()["data"][0]["embedding"], dtype=np.float32)
    except Exception as exc:  # noqa: BLE001
        log.warning("embedding failed (%s); falling back to lexical-only scoring", exc)
        return None
    vec = _normalize(vec)
    _cache_put(text, vec)
    return vec


def _rank(store: Store, question: str, vec: np.ndarray | None, top_k: int) -> list[dict]:
    kw = store.kw_index or KwIndex(store.records)
    qtokens = query_tokens(question)
    mode = "hybrid" if vec is not None else "lexical"

    kw_scores = np.array([kw.score(qtokens, i) for i in range(len(store.records))], dtype=np.float32)
    kw_max = float(kw_scores.max()) if kw_scores.size else 0.0
    if kw_max > 0:
        kw_scores = kw_scores / kw_max

    # Weights stay comparable in both modes: the lexical term is normalised per query to [0, 1]
    # and the theme boost is capped at BOOST_MAX, so a matched theme outranks raw word overlap by
    # design (the map encodes curated canonical verses) without ever inventing one.
    w_emb, w_kw = (W_EMB, W_KW) if vec is not None else (0.0, W_KW)
    emb_scores = store.matrix @ vec if vec is not None else None
    boost = _topic_boost(question)

    combined: list[tuple[float, int]] = []
    for i, rec in enumerate(store.records):
        s = w_kw * float(kw_scores[i])
        if emb_scores is not None:
            s += w_emb * float(emb_scores[i])
        s += boost.get(rec["id"], 0.0)
        if rec.get("verse") is None:
            s += SUMMARY_PENALTY
        combined.append((s, i))
    combined.sort(key=lambda x: -x[0])

    out = []
    for score, i in combined[:top_k]:
        item = dict(store.records[i])
        item["score"] = round(float(score), 4)
        item["mode"] = mode
        out.append(item)
    return out


def retrieve(store: Store, question: str, top_k: int = config.TOP_K) -> list[dict]:
    """Top-K grounded passages for ``question`` (store records + score)."""
    return _rank(store, question, _embed_query(question), top_k)


async def retrieve_async(store: Store, question: str, top_k: int = config.TOP_K) -> list[dict]:
    """Async variant used by the API request path."""
    return _rank(store, question, await _embed_query_async(question), top_k)


def format_context(passages: list[dict]) -> str:
    """Render retrieved passages for the LLM prompt (verbatim translations)."""
    lines = []
    for p in passages:
        lines.append(f"[{p['id']}] {p['ref']} (PDF p. {p['pdf_page']})")
        lines.append(f"Translation: {p['translation']}")
        if p.get("purport"):
            lines.append(f"Purport excerpt: {p['purport'][:600]}")
        lines.append("")
    return "\n".join(lines).strip()
