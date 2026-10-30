"""Merge the book datasets and build the embedding index (Task 7).

Inputs : data/verses_gita.jsonl (700) + data/verses_uddhava.jsonl (1,064)
         + data/verses_ashtavakra.jsonl (298)
Outputs: data/verses.jsonl   (merged, one record per line, aligned with rows)
         data/index.npz      (L2-normalised embedding matrix + record ids)

Embeddings come from the LiteLLM gateway model ``nvidia/nemotron-3-embed-1b``
(2048-dim, verified live). Each record's embedded text is its reference +
chapter title + English translation (quotable text only — never the garbled
Sanskrit layer).

Run:  python -m krsna_ai.ingest.build_index
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

if __package__ in (None, ""):  # allow direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx
import numpy as np

from krsna_ai import config

BATCH = 32


def _embed_text(rec: dict) -> str:
    title = rec.get("chapter_title", "")
    return f"{rec['ref']} {title}. {rec['translation']}".strip()


def _embed_batch(texts: list[str]) -> np.ndarray:
    headers = {"Content-Type": "application/json"}
    if config.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
    with httpx.Client(base_url=config.LLM_BASE_URL, headers=headers, timeout=120) as client:
        resp = client.post("/embeddings", json={"model": config.EMBED_MODEL, "input": texts})
        resp.raise_for_status()
        data = resp.json()["data"]
    data.sort(key=lambda d: d["index"])
    vec = np.array([d["embedding"] for d in data], dtype=np.float32)
    norms = np.linalg.norm(vec, axis=1, keepdims=True)
    return vec / np.maximum(norms, 1e-9)


def main() -> None:
    rows: list[dict] = []
    for path in (config.GITA_JSONL, config.UDDHAVA_JSONL, config.ASHTAVAKRA_JSONL):
        recs = [json.loads(l) for l in path.open(encoding="utf-8")]
        print(f"{path.name}: {len(recs)} records")
        rows.extend(recs)
    rows.sort(key=lambda r: (r["book"], r["chapter"], r["verse"] or 0))
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate ids in merged store!"

    texts = [_embed_text(r) for r in rows]
    vecs: list[np.ndarray] = []
    t0 = time.time()
    for i in range(0, len(texts), BATCH):
        vecs.append(_embed_batch(texts[i:i + BATCH]))
        print(f"embedded {min(i + BATCH, len(texts))}/{len(texts)} "
              f"({time.time() - t0:.0f}s)", flush=True)
    matrix = np.vstack(vecs)
    assert matrix.shape == (len(rows), config.EMBED_DIM), matrix.shape

    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    with config.VERSES_PATH.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    np.savez_compressed(config.INDEX_PATH, ids=np.array(ids), embeddings=matrix)
    print(f"OK: {len(rows)} records -> {config.VERSES_PATH.name} + "
          f"{config.INDEX_PATH.name} {matrix.shape}")


if __name__ == "__main__":
    main()
