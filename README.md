# Krishna AI (Meta Global AI Developer Hackathon)

> **Zero-Hallucination Philosophical & Mental Wellness Counsel Agent powered by Meta's Open-Weights Models and Grounded RAG.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Meta Models](https://img.shields.io/badge/Meta%20AI-Muse%20%2F%20Llama-purple.svg)](https://ai.meta.com/)
[![Inference: Baseten](https://img.shields.io/badge/Inference-Baseten-orange.svg)](https://baseten.co)

---

## 📌 Overview
**Krishna AI** is an empathetic, persona-driven counseling companion designed to help individuals navigate real-world challenges—such as stress, anxiety, conflict, indecision, grief, and purpose.

Unlike generic conversational bots that hallucinate philosophical advice or invent scriptural references, Krishna AI strictly grounds every response in authentic classical wisdom texts:
1. ***Bhagavad-gītā As It Is*** (1972 Macmillan edition, A. C. Bhaktivedanta Swami Prabhupāda)
2. ***The Uddhava-gītā*** (Śrīmad-Bhāgavatam Canto 11)
3. ***Ashtavakra Gita*** (John Richards 1996)

Every counseling response is delivered in the warm, compassionate voice of Krishna, backed by verbatim verse quotations, verifiable references, and concrete daily actions.

---

## 🚀 Architecture & Tech Stack

```
┌───────────────────────────────── RAG PIPELINE ─────────────────────────────────┐
│ User Query ──► Query Normalization & IAST Diacritic Folding                    │
│                     │                                                          │
│                     ▼                                                          │
│          Hybrid Semantic & Lexical Retrieval (Top-K)                          │
│          • Embedding space + Topic taxonomy ladder                             │
│                     │                                                          │
│                     ▼                                                          │
│          Grounded Prompt Assembly (Persona + Verses + Strict Constraints)      │
│                     │                                                          │
│                     ▼                                                          │
│          Meta Open-Weights & Reasoning Models (via Baseten / LiteLLM)          │
│          • Primary: muse-wonder-1.0 (Flagship Multimodal / Reasoning)          │
│          • Fast Turn: muse-spark-1.3                                           │
│                     │                                                          │
│                     ▼                                                          │
│          Citation Verification & Hallucination Guardrail                       │
│          • Verbatim translation match check                                    │
│          • Rejection / Stripping of ungrounded book references                │
│                     │                                                          │
│                     ▼                                                          │
│          FastAPI Backend (JSON API) ──► Interactive Web Chat & CLI             │
└────────────────────────────────────────────────────────────────────────────────┘
```

- **Foundation Models**: Meta's Open-Weights Reasoning Models (`muse-wonder-1.0`, `muse-spark-1.3`, Llama series).
- **Inference & Serving**: [Baseten](https://baseten.co) dedicated high-throughput inference endpoints with 2M TPM rate limits.
- **Strict Guardrails**: Deterministic citation parser requiring exact verse matches against the ingested text corpora.
- **Telemetry**: Full observability via Langfuse.

---

## ⚡ Quickstart

### 1. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/Pranavpaharia/krishna-ai.git
cd krishna-ai
pip install -r requirements.txt
```

### 2. Environment Setup
Copy the example environment configuration:
```bash
cp .env.example .env
```
Configure your Meta / Baseten inference endpoints and API keys in `.env`.

### 3. Run the Conversational CLI
```bash
# Interactive mode
python -m krsna_ai.cli

# Direct question
python -m krsna_ai.cli "I feel overwhelmed and anxious about my duties"
```

### 4. Run the Web Interface & API
Start the FastAPI server:
```bash
python -m krsna_ai.app
```
Then open your browser at `http://localhost:8123` to experience the Krishna AI web companion.

### 5. Run the Evaluation Battery
Run the complete suite of 50 unit and evaluation benchmark tests:
```bash
python -m pytest tests/
```

---

## 📊 Benchmark & Evaluation Results
The system is continuously verified against golden and holdout benchmark suites:
- **Golden Evaluation Set**: 0.918 Recall@6 | 32/32 Topic Hit | 0.840 MRR
- **Holdout Paraphrase Set**: 0.844 Recall@6 | 11/12 Topic Hit | 0.792 MRR
- **Ashtavakra Golden Set**: 0.75+ Recall@6 | 32/35 Topic Hit | 0.60+ MRR

---

## 📜 License
Distributed under the MIT License. See `LICENSE` for details.

*Created for the Meta Global AI Developer Hackathon (Cerebral Valley).*
