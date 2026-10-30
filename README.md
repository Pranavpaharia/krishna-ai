# Meta Hackathon Workspace

Workspace dedicated to Meta AI hackathon projects, prototyping, and autonomous agents using Meta's Model API and local cluster infrastructure.

## 1. Quick Facts & Environment
- **Gateway**: LiteLLM Gateway on Dell Edge (`http://192.168.0.60:4000/v1` / Tailscale `http://100.125.143.43:4000/v1`) — DHCP lease, MAC `00-22-19-ee-01-24`; the old `192.168.1.219` address is stale
- **Master API Key**: set `KRSNA_LLM_API_KEY` in your local `.env` (see `.env.example`; never commit `.env`)
- **Native Direct Meta Endpoint**: `https://api.meta.ai/v1`
- **Telemetry**: Langfuse Observability (`https://jp.cloud.langfuse.com`)
- **DSH Web Portal**: `http://127.0.0.1:3080` / `https://lightfury.tail4531a5.ts.net`

## 2. Meta Models Matrix

| Model ID | Aliases | Specialization & Capabilities | Context Window |
| :--- | :--- | :--- | :---: |
| **`muse-wonder-1.0`** | `Meta Muse Wonder`, `meta/muse-wonder-1.0` | **Flagship Reasoning & Multimodal**: Deep reasoning, image/vision understanding, function calling, agentic problem solving. | 128K |
| **`muse-spark-1.3`** | `Meta Muse Spark`, `meta/muse-spark-1.3` | **Fast Reasoning**: High-speed deliberation, rapid tool use, iterative logic verification. | 128K |
| **`sam-3.1`** | — | **Segment Anything 3.1**: Advanced visual segmentation and object isolation. | — |
| **`muse-voice-transcribe-1.0`** | — | **Audio Transcription**: High-accuracy speech-to-text. | — |
| **`muse-image-1.0`** | — | **Image Generation**: High-fidelity text-to-image synthesis. | — |

## 3. Quickstart: Querying via LiteLLM

```python
import openai

client = openai.OpenAI(
    base_url="http://192.168.0.60:4000/v1",
    api_key=os.environ["KRSNA_LLM_API_KEY"]  # from your local .env, never hardcoded
)

response = client.chat.completions.create(
    model="muse-wonder-1.0",
    messages=[
        {"role": "user", "content": "Explain our Meta hackathon concept."}
    ]
)
print(response.choices[0].message.content)
```

To run the verification test suite:
```powershell
python test_meta_models.py
```
