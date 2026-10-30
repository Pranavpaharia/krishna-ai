"""Append-only audit trail: one JSON line per answered question.

The acceptance criterion for this project is *provable* grounding. Without a log there is no
hallucination rate — only a battery a human read once. Every turn records the question, the
retrieved ids, the cited ids, the verdict and latency, so "how often does the model cite a
verse it was not given" is a number rather than an impression.
"""
from __future__ import annotations

import json
import logging

from krsna_ai import config

log = logging.getLogger("krsna_ai.audit")
AUDIT_PATH = config.DATA_DIR / "audit.jsonl"


def record(entry: dict) -> None:
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with AUDIT_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:  # telemetry must never break an answer
        log.warning("audit write failed: %s", exc)
