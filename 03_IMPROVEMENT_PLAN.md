# 03 — Improvement Plan (Krishna AI Assistant)

Written 2026-10-29. Baseline: v1 complete (see [02_FINAL_REPORT.md](02_FINAL_REPORT.md)) —
1,764 records, 13 tests green, 12/12 battery pass, app on :8123.

The product's only differentiator is **provably grounded citation**. Every improvement below
serves that first: make the guarantee airtight, make quality measurable, then make it feel
like a product.

---

## 1. Findings that drive the plan

| # | Finding | Evidence | Impact |
|---|---|---|---|
| 1 | Gateway unreachable at audit time; app not running | `http://192.168.1.219:4000` timed out (20 s); `:8123` refused | Single network dependency halts the whole product |
| 2 | Quote check accepts a quote from **any** store record, not the retrieved ones | `citations.py` L60–62 (60-char window over `store.records`) | Model can quote a verse it was never given and still report `citations_ok=True` |
| 3 | Quotes under 25 chars are ignored | `_QUOTE_RE` `{25,}` | Short paraphrases presented as scripture pass unverified |
| 4 | `enforce()` never marks the answer as degraded | `citations.py` L73–90 | A silently weakened answer looks clean to the user |
| 5 | Sync `httpx` inside the async request path | `retriever.py` L77–87 | Blocks the event loop; no shared client, no cache, no fallback |
| 6 | `_kw_cache` keyed by `id(store)` | `retriever.py` L74, L93 | Stale/unbounded after GC; index rebuilt lazily |
| 7 | No tests for the enforcement loop or LLM fallback | `tests/` covers parsing, retrieval smoke, checker basics | The core guarantee is untested end-to-end |
| 8 | No measurable quality baseline | `tests/battery.py` is human-reviewed prose | Improvements cannot be proven; regressions go unnoticed |
| 9 | Topic map is a hardcoded 17-theme regex table | `retriever.py` L26–44 | Blind to depression, addiction, health, finances, doubt, forgiveness, gratitude |
| 10 | 101 `partial` records of 1,764; garbled Devanāgarī/transliteration; scan-era typos in some translations | `quality` distribution: good=1639, partial=101, summary=24 | Ugly UI cards, weak lexical signal |
| 11 | No persistence, no streaming, no tracing, no auth/rate limit, no packaging, no git, no CI | `app.py`, `web/index.html` (no localStorage), `requirements.txt` | Not deployable; AGENTS.md Langfuse requirement unmet |
| 12 | Crisis handling exists only as prompt text | `persona.py` L38 | No code-level detection, no audit trail |

---

## 2. Tier A — Tighten the integrity core *(do first)*

| Task | What changes | Acceptance |
|---|---|---|
| A1 | `check(answer, store, retrieved_ids)` — a quote must match a **retrieved** verse; fuzzy OCR match becomes a warning (`ocr_noise`), not a pass | Quote from an unretrieved verse fails |
| A2 | Attribute each quoted span to the verse it came from (`quotes: [{quote, verse_id}]`) | UI can render per-quote cards; wrong attribution fails |
| A3 | `enforce()` returns `{answer, removed}`; response gains `adjusted`; UI shows "citations adjusted — removed: …" | Degraded answers are visibly degraded |
| A4 | Short-quote threshold lowered (≥12 chars) and paraphrase detection added | A paraphrase presented as scripture is flagged |
| A5 | Audit log `data/audit.jsonl`: question, retrieved, cited, verdict, retry, latency | Hallucination rate becomes a number |
| A6 | Engine tests with a fake LLM (no network): retry path, enforce fallback, missing `References:` line, wrong attribution, empty content | Core guarantee tested end-to-end |
| A7 | Keyword index stored on the `Store` instance, built once at load | No `id(store)` cache bug |

## 3. Tier B — Make retrieval quality measurable, then improve it

| Task | What changes | Acceptance |
|---|---|---|
| B1 | `tests/eval_golden.jsonl` — 30–40 life-problem questions with expected verse ids; `test_eval.py` asserts recall@6 and MRR | A committed baseline that fails on regression |
| B2 | Two-stage retrieval: pool top-40 → rerank (cross-encoder or `muse-spark-1.3`) → top-6; topic map becomes a prior, not an oracle | Recall@6 improves on the golden set |
| B3 | Query normalisation: diacritic-insensitive tokens, synonym expansion, Hindi/Hinglish tokens | Non-English questions retrieve |
| B4 | `data/topics.json` built from purport text + manual overrides | Themes inspectable, extendable, testable |
| B5 | Embedding cache + offline lexical fallback (and optional local `sentence-transformers`) | Retrieval still works when the gateway is down |

## 4. Tier C — Runtime, observability, product

| Task | What changes |
|---|---|
| C1 | Async embeddings, shared `httpx.AsyncClient`, retry + backoff, per-request timeout, structured logging |
| C2 | Langfuse tracing per request (question, retrieval scores, prompt, model, verdict) — AGENTS.md requirement |
| C3 | `data/sessions.db` (SQLite): turns + citations + verdicts → follow-up context and longitudinal quality |
| C4 | Streaming with post-verification; badge lands after the prose |
| C5 | Code-level crisis detection → helpline block + logged event |
| C6 | Bearer token, CORS, rate limit, no secrets in logs |

## 5. Tier D — Data, packaging, licensing

| Task | What changes |
|---|---|
| D1 | Re-normalize the 101 `partial` records; typo map for scan-era spellings; keep `raw_translation` so verbatim quoting stays honest |
| D2 | Verify Uddhava chapter → ŚB Canto 11 mapping against the book's contents page; store `canto_chapter` explicitly |
| D3 | Licensing decision recorded before any public deployment (both books are copyrighted) |
| D4 | `git init`, `pyproject.toml`, `ruff`, CI, move `_tmp_probe_*` scratch files to `scratch/` |
| D5 | Hindi only if it is a real goal — the 428-page scan needs an OCR pass |

## 6. Tier E — Demo polish

- `python tests/battery.py --json` → scorecard table pasted into the final report.
- UI: "open PDF page p.N" links, degraded-citation warning, latency line.
- A 90-second demo script with one golden answer that never fails verification.

---

## 7. Order of execution

**A1–A7 + B1** (≈1 day) → **C1–C4** → **D**. Rationale: the guarantee currently has a hole
(finding 2) and no measurement (finding 8); everything else is polish on an unproven core.

## 8. Status

Implemented in this pass (Tier A + B1, plus B3). Offline suite is green: `KRSNA_OFFLINE=1 python -m pytest -q` → **32 passed in 1.4 s**.

- [x] A1 scoped quote verification (`check(answer, store, retrieved=…)`, `off_scope`, `ocr_noise` as a warning only)
- [x] A2 quote attribution (`quotes: [{quote, verse_id}]`)
- [x] A3 degraded-answer marking (`enforce() → {answer, removed}`, `adjusted` in the API response and the UI badge)
- [x] A4 short-quote threshold ≥ 12 chars
- [x] A5 audit log `data/audit.jsonl` (never raises on an unwritable path)
- [x] A6 engine tests with a fake LLM — 5 tests, no network
- [x] A7 keyword index owned by the `Store`, built once at load
- [x] B1 golden eval set (32 questions) + `tests/test_eval.py` asserting recall@6 / topic-hit@6 / MRR
- [x] B4 `data/topics.json` (22 themes) — now the primary map, the literal trigger-word map is the fallback
- [x] B5-lite offline lexical fallback + bounded embedding LRU cache
- [x] B3 IAST folding (`kṛṣṇa` → `krishna`, `gītā` → `gita`) + a small Hinglish map (`gussa` → anger, `dukh` → grief, `sharm` → guilt), applied to the query only; `data/topics.json` gained 20 Hinglish synonyms so the theme boost fires on Hinglish questions

Two genuine defects the new tests caught (they were not test bugs):

1. `enforce()` rebuilt the `References:` line but left the model's original line in place, so a
   fabricated id survived inside the very line meant to certify it.
2. `enforce()` stripped only the `(Bhagavad-gita X.Y)` rendering, so a bare invented id in prose
   (`BG-99.99`) survived to the user.

Both are fixed, and the suite now asserts the honest contract: an answer left with nothing
verifiable reports `citations_ok = False` rather than being presented as verified.

### Measured retrieval — production path, offline (lexical + `data/topics.json`)

| Set | n | map fired | recall@6 | topic-hit@6 | MRR |
|---|---|---|---|---|---|
| golden (in-sample for the map) | 32 | 32/32 | **0.918** (89/97) | **32/32** | **0.840** |
| holdout (unseen phrasing) | 12 | 11/12 | **0.844** (27/32) | **11/12** | **0.792** |

Before the synonym map, on the same production path: golden 0.247 / 14/32 / 0.289, holdout
0.000 / 0/12 / 0.000. The map carries the recall; the embedder alone measures 0.155 (golden) /
0.156 (holdout) cosine-only, and the semantic layer adds ≈ +0.03 recall on the holdout with no
topic-hit gain. The holdout is the number that matters — 0.844 against 0.918 in-sample shows the
synonym lexicon generalises rather than memorising the golden phrasings.

**Reconciliation of the earlier 0.371 vs 0.918 conflict:** the boost formula was never the
difference (both used `0.60 − 0.05 × rank`). It was the lexical weight — `_rank` set `w_kw = 1.0`
whenever no embedding vector was available, which let raw word overlap outrank the capped boost.
`_rank` now uses `W_KW` in both modes, so the production path and the lab sweep agree.

`tests/test_eval.py` asserts floors *below* the measured values (golden 0.85 / 28 / 0.75, holdout
0.75 / 9 / 0.65) — regression guards, not thresholds tuned to pass, and neither eval file may be
edited to make a test green.

**B3 measured, and it is not a recall win.** Folding is neutral on both eval sets — golden
0.918 / 32/32, holdout 0.844 / 11/12, identical before and after (`scratch/_tmp_probe9.py`,
production weights and boost, only the tokenizer varied). The eval files are plain English, so
they cannot show folding's value; its value is robustness for user-typed diacritics and Hinglish,
which is why it is covered by `tests/test_normalize.py` instead of by a recall target. Concept
expansion as extra query tokens remains rejected (probe2: recall fell five-fold to 0.0515).

Also fixed: the engine tests were writing scripted turns into the production `data/audit.jsonl`
(30 lines of test noise), which would have made the hallucination-rate number meaningless. An
autouse fixture now redirects `AUDIT_PATH` to `tmp_path`.

Next: B2 two-stage rerank (blocked offline — the cross-encoder is not in the HF cache, only
MiniLM is), then Tier C. Gateway status as of the last check: both LiteLLM endpoints
(`192.168.1.219:4000`, `10.10.10.50:4000`) refuse TCP connections, so nothing live — battery,
live retrieval, or a live reranker — can run until one is back.
