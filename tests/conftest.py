"""Session-wide test setup: force offline mode so retrieval is reproducible without the gateway.

Sets KRSNA_OFFLINE before any test module imports krsna_ai.config, so config.OFFLINE is
deterministic regardless of test collection order.
"""
import os

os.environ.setdefault("KRSNA_OFFLINE", "1")
