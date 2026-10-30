# Meta Hackathon Workspace — Agent Rules & Directives

## 1. Primary Model Routing & Inference
When operating within this workspace:
- **Default Cloud Models**: Prioritize Meta's official hosted models via the LiteLLM Gateway on the Dell Edge box (`http://192.168.0.60:4000/v1`; Tailscale alias `http://100.125.143.43:4000/v1`):
  - `muse-wonder-1.0` (Flagship Reasoning & Multimodal, 128K context)
  - `muse-spark-1.3` (Fast Reasoning, 128K context)
- **Gateway Address Is Dynamic**: The Dell Edge box (MAC `00-22-19-ee-01-24`, Dell OUI) gets a DHCP lease; `192.168.1.219` is stale (the LAN is `192.168.0.0/24`). If the gateway times out, re-discover it — scan `:4000` on the ARP table, confirm with `/health/liveliness`, and compare `/models` — then update `.env`. Do not assume the old IP.
- **Local Fallback & Twin Workers**:
  - Heavy Architecture: Kittu (`10.10.10.50`)
  - Parallel C++ / Python coding: LightFury (`10.10.10.10`) & BlackBird (`10.10.10.30`)
  - Fast Triage Sentinel: Thunderbolt (`10.10.10.20`)

## 2. Coding & Prototyping Standards
- Fast, iterative Python prototypes.
- Type annotations and structured responses (`pydantic`).
- Maintain non-blocking async workflows where applicable.
- Route all external LLM calls through LiteLLM Gateway to preserve Langfuse telemetry and rate limiting.
