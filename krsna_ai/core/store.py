"""Verse store: loads the merged dataset + embedding index into memory.

The store is the single source of truth for scriptural text at runtime.
Answers may only quote translations found here, and the citation checker
validates every reference against these records.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np

from krsna_ai import config
from krsna_ai.core.kwindex import KwIndex


@dataclass
class Store:
    records: list[dict] = field(default_factory=list)
    by_id: dict[str, dict] = field(default_factory=dict)
    matrix: np.ndarray | None = None  # (N, 2048) L2-normalised, row-aligned
    # Keyword index built once at load. Owned by the store instance rather than cached in a
    # module-level dict keyed by id(store), which goes stale after garbage collection.
    kw_index: KwIndex | None = None

    @classmethod
    def load(cls) -> "Store":
        rows = [json.loads(l) for l in config.VERSES_PATH.open(encoding="utf-8")]
        z = np.load(config.INDEX_PATH, allow_pickle=False)
        ids = [str(x) for x in z["ids"]]
        matrix = z["embeddings"].astype(np.float32)
        assert ids == [r["id"] for r in rows], "index/verses row misalignment"
        store = cls(records=rows, by_id={r["id"]: r for r in rows}, matrix=matrix)
        store.kw_index = KwIndex(rows)
        return store

    def get(self, vid: str) -> dict | None:
        return self.by_id.get(vid)

    def search(self, query_vec: np.ndarray, top_k: int = config.TOP_K) -> list[tuple[dict, float]]:
        """Cosine top-K (matrix rows are L2-normalised, so dot = cosine)."""
        if self.matrix is None:
            raise RuntimeError("index not loaded")
        scores = self.matrix @ query_vec.astype(np.float32)
        idx = np.argsort(-scores)[:top_k]
        return [(self.records[int(i)], float(scores[int(i)])) for i in idx]
