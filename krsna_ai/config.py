"""Central configuration for the Krishna AI assistant.

Every environment-specific value (gateway URL, model names, data paths)
lives here. The API key is read from the environment variable
``KRSNA_LLM_API_KEY`` — never hardcode secrets in source.
"""
from __future__ import annotations

import os
import socket
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

# --- .env loading (python-dotenv if installed; tiny manual fallback) ---------
def _load_dotenv() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(env_file)
        return
    except ImportError:
        pass
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

# --- LLM / embedding gateway (LiteLLM, Dell Edge box) ------------------------
# Dell Edge, MAC 00-22-19-ee-01-24 (Dell OUI), LiteLLM on :4000. Its DHCP lease
# moved off 192.168.1.219 (dead subnet; the LAN is 192.168.0.0/24) to 192.168.0.60
# on 2026-10-29. Pin the lease on the router, or prefer the Tailscale address.
GATEWAY_CANDIDATES = (
    "http://192.168.0.60:4000/v1",     # LAN lease (Dell Edge)
    "http://100.125.143.43:4000/v1",   # Tailscale alias, same instance
)


def resolve_base_url() -> str:
    """Configured gateway, else the first candidate that answers on :4000."""
    env = os.environ.get("KRSNA_LLM_BASE_URL")
    if env:
        return env
    if os.environ.get("KRSNA_OFFLINE", "").lower() in ("1", "true", "yes"):
        return GATEWAY_CANDIDATES[0]
    for base in GATEWAY_CANDIDATES:
        netloc = urlparse(base).netloc
        host, _, port = netloc.partition(":")
        try:
            with socket.create_connection((host, int(port or 4000)), timeout=2):
                return base
        except OSError:
            continue
    return GATEWAY_CANDIDATES[0]


LLM_BASE_URL = resolve_base_url()
LLM_API_KEY = os.environ.get("KRSNA_LLM_API_KEY", "")
CHAT_MODEL = os.environ.get("KRSNA_CHAT_MODEL", "muse-wonder-1.0")
CHAT_MODEL_FALLBACK = os.environ.get("KRSNA_CHAT_FALLBACK_MODEL", "muse-spark-1.3")
EMBED_MODEL = os.environ.get("KRSNA_EMBED_MODEL", "nvidia/nemotron-3-embed-1b")
EMBED_DIM = 2048  # verified against the gateway (probe, 2026-10-27)

# Completion budget. These are reasoning models and reasoning_tokens count against max_tokens:
# observed runs spent 2.3k-3.5k tokens thinking on a ~2.1k-token prompt, so a 4000 cap sat right
# on the edge and intermittently returned finish_reason="length" with empty content. Sized for
# thinking + the 250-400 word answer, not the answer alone.
MAX_TOKENS = int(os.environ.get("KRSNA_MAX_TOKENS", "8000"))

# --- First-turn fast path ----------------------------------------------------
# The FIRST question of a conversation gets a short MODE-1 answer (see persona.py)
# routed to the fast model, so the first response is quick and light; follow-up
# depth answers use the flagship model with the full budget.
# muse-spark-1.3 is the preferred fast model, but the gateway returns 402 for the Meta
# muse models until quota is funded, so the working default is the fastest model that
# answers without a reasoning tax. Benchmarked 2026-10-30 on a real first-turn prompt
# (max_tokens 1500): TokenHarbor (DeepSeek-V4-Flash) 5.9s / 190 words / finish=stop;
# Groq (Qwen3.8-27B) 13.9s and returned EMPTY content (all 1500 tokens spent thinking).
# Set KRSNA_FAST_FIRST_TURN=0 to disable and always use the flagship model.
FAST_FIRST_TURN = os.environ.get("KRSNA_FAST_FIRST_TURN", "1").lower() in ("1", "true", "yes")
FAST_MODEL = os.environ.get("KRSNA_FAST_MODEL", "TokenHarbor (DeepSeek-V4-Flash)")
FAST_MAX_TOKENS = int(os.environ.get("KRSNA_FAST_MAX_TOKENS", "1500"))

# --- Data artifacts ----------------------------------------------------------
VERSES_PATH = DATA_DIR / "verses.jsonl"          # merged verse store
GITA_JSONL = DATA_DIR / "verses_gita.jsonl"      # extract_gita.py output
UDDHAVA_JSONL = DATA_DIR / "verses_uddhava.jsonl"  # extract_uddhava.py output
ASHTAVAKRA_JSONL = DATA_DIR / "verses_ashtavakra.jsonl"  # extract_ashtavakra.py output
INDEX_PATH = DATA_DIR / "index.npz"              # embedding matrix (aligned rows)

# --- Retrieval ----------------------------------------------------------------
TOP_K = 6
# Offline mode: skip the embedding service and score lexically only. Used by the eval suite
# (deterministic, no network) and by the app when the gateway is unreachable.
OFFLINE = os.environ.get("KRSNA_OFFLINE", "").lower() in ("1", "true", "yes")
