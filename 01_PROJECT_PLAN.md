# 01 — Project Plan: Krishna AI Assistant
### Source of truth: [00_PDF_ANALYSIS.md](00_PDF_ANALYSIS.md) (`U:\MetaHackathon`)
### Status: **APPROVED by user on 2026-10-27 ("start") — Phase 3 execution in progress**
### Updated 2026-10-27: primary Bhagavad Gita is now *Bhagavad-gītā As It Is* (Macmillan 1972) — see [00_PDF_ANALYSIS.md](00_PDF_ANALYSIS.md) ADDENDUM. The 428-page OCR job is eliminated.

---

## 1. Final goal (restated in my own words)

Build a **Krishna AI assistant** that a person can talk to about daily-life and life problems
(anxiety, grief, anger, fear, indecision, family conflict, work stress, loss, purpose, death, detachment, etc.).

The assistant must:

1. **Respond in the voice/persona of Lord Krishna** — kind, steady, wise, non-judgmental; like Krishna counselling
   Arjuna and Uddhava, not like a generic chatbot.
2. Be **grounded only in the supplied books** as its core knowledge:
   - ***Bhagavad-gītā As It Is*, original authorized Macmillan edition (1972)** by A. C. Bhaktivedanta Swami
     Prabhupāda — 1,034 pp., built-in text layer, verse + transliteration + synonyms + translation + purport.
     **This replaces the scanned Star Publications 1993 Gita as the assistant's Bhagavad Gita.**
   - *The Uddhava-gītā* (Śrīmad-Bhāgavatam Canto 11, ch. 6–29, with purports) — digital text, directly extractable.
   - The Star Publications 1993 scan is demoted to an **optional supplement** (only if Hindi blocks are ever wanted).
3. Give **correct, verifiable references** for every claim — e.g. *Bhagavad-gītā 2.47*, *Uddhava-gītā / SB 11.8*
   (Story of Piṅgalā) — quoting the verse's English translation from these very books, never invented text.
4. Give a **practical solution/path forward** for the user's problem, the way Krishna would — teaching first,
   then a concrete step the person can take.
5. **Never hallucinate scripture.** If the books do not cover something, the assistant must say so honestly
   ("NOT FOUND IN PDF" rule) instead of inventing a verse.

---

## 2. System architecture (how it will work)

```
┌─────────────────────────────── ONE-TIME INGESTION (offline) ───────────────────────────────┐
│ [Uddhava-gītā PDF] --PyMuPDF--> parse Text/Synonyms/Translation/Purport --> verses ─┐      │
│ [Bhagavad-gītā As It Is PDF] --PyMuPDF (built-in text layer)--> parse TEXT n /      │      │
│        Synonyms / TRANSLATION / PURPORT blocks --> verses (NO OCR needed)           ├─►    │
│                                                                                     │      │
│        verses.jsonl  --> embeddings (gateway nemotron-3-embed-1b) --> index.npz (numpy)   │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
                                              │
┌─────────────────────────────── RUNTIME (per question) ────────────────────────────────┐
│ User problem ─► embed query ─► semantic search top-K verses ─► (optional) keyword   │
│ boost ─► build grounded prompt (persona + verses + rules) ─► LLM (muse-wonder-1.0)  │
│ ─► answer in Krishna's voice with citations ─► citation checker (verify refs exist) │
│ ─► chat UI / CLI                                                                     │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

**Why this design (RAG — Retrieval-Augmented Generation):** the model never answers from its own memory of
scripture; it answers only from verses retrieved out of *your three books*, which are pasted into the prompt.
That is what makes the references correct and checkable, and it keeps answers faithful to these editions.

---

## 3. Tech stack (all verified working in this workspace on 2026-10-27)

| Layer | Choice | Why / evidence |
|---|---|---|
| Language | **Python 3.12** | Installed; workspace standard ([AGENTS.md](AGENTS.md): type annotations, `pydantic`, async where useful) |
| PDF text extraction | **PyMuPDF 1.28.2** (`pymupdf`) | Already extracted Uddhava-gītā: 1.88 M chars, 942 Synonyms + 942 Translation markers |
| OCR (now optional, Star scan only) | **Tesseract 5** (`eng` + `script/Devanagari`) + PyMuPDF rendering @300 dpi | English OCR verified clean on the Star scan p. 16; **no longer on the critical path** — *As It Is* has a built-in text layer (2.01 M chars) |
| Embeddings | **`nvidia/nemotron-3-embed-1b`** via LiteLLM Gateway (2048-dim) — **verified live** | No local VRAM cost; gateway is the mandated route ([AGENTS.md](AGENTS.md)); fallback: local `sentence-transformers 6.0.0` (installed) if gateway is down |
| Vector store | **NumPy cosine index** (`.npz`), no new dependencies | ~1,500–2,500 verses only — brute-force cosine is milliseconds; `faiss`/`chromadb` are **not installed** and unnecessary at this scale |
| Verse store | **JSONL + SQLite** (`verses.jsonl`, stdlib `sqlite3`) | Human-inspectable, diff-able, zero setup |
| LLM (generation) | **`muse-wonder-1.0`** via LiteLLM Gateway — **verified live** (`OK-WONDER`) | Flagship reasoning model, 128K context; `muse-spark-1.3` (also verified) as fast fallback |
| API server | **FastAPI 0.141 + uvicorn 0.46** (installed) | Async, typed (`pydantic`), standard |
| Chat UI | **Single static HTML/JS page** served by FastAPI (v1); Gradio optional later | No build tooling, works the moment the server runs; easy to upgrade |
| CLI | `python -m krishna_ai.cli` | For testing without a browser |

**No fine-tuning.** Persona + grounding comes from the system prompt and retrieved verses. Fine-tuning on
1.88 M chars would cost more, risk corrupting quotations, and still not guarantee correct references.

---

## 4. Folder / file structure

```
U:\MetaHackathon\
├── 00_PDF_ANALYSIS.md            ← Phase 1 (done)
├── 01_PROJECT_PLAN.md            ← this file (Phase 2)
├── 02_FINAL_REPORT.md            ← Phase 4 (at the end)
├── README.md / AGENTS.md / test_meta_models.py   (pre-existing, untouched)
├── The Uddhava-gītā (2).pdf                        (source, untouched)
├── Bhagavad_gita-As_It_Is-Original_authorized_Macmillan_edition.pdf  (PRIMARY Gita, untouched)
├── Srimad Bhagavad Gita (Sanskrit, Hindi & English).pdf  (optional supplement, untouched)
│
├── krsna_ai\
│   ├── __init__.py
│   ├── config.py            ← gateway URL, model names, paths (no secrets hardcoded —
│   │                          key read from env var KRSNA_LLM_API_KEY)
│   ├── ingest\
│   │   ├── extract_uddhava.py     ← PyMuPDF → structured verses (Text/Synonyms/Translation/Purport)
│   │   ├── extract_gita.py        ← PyMuPDF → As It Is TEXT n/Synonyms/TRANSLATION/PURPORT blocks
│   │   │                             (same 5-part layout; normalizes ClearScan mojibake like Kr§pa→Kṛṣṇa)
│   │   ├── ocr_gita.py            ← ONLY if the Star scan supplement is ever wanted (not in v1)
│   │   └── build_index.py         ← verses.jsonl → embeddings → index.npz + verse store
│   ├── core\
│   │   ├── store.py               ← load verses + index; cosine search; keyword boost
│   │   ├── retriever.py           ← query → top-K grounded passages (+ topic map)
│   │   ├── persona.py             ← KRISHNA_SYSTEM_PROMPT (voice, structure, rules, safety)
│   │   ├── llm.py                 ← OpenAI-compatible client → LiteLLM gateway (async httpx)
│   │   └── citations.py           ← verify every cited reference exists in the verse store
│   ├── app.py                     ← FastAPI: /chat, /health, serves web UI
│   ├── cli.py                     ← terminal chat for quick testing
│   └── web\index.html             ← chat UI (Krishna theme, shows references under each answer)
├── data\
│   ├── verses.jsonl               ← generated: every verse w/ book, chapter, ref, texts, PDF page
│   └── index.npz                  ← generated: embedding matrix aligned with verses.jsonl
├── tests\
│   ├── test_parse_uddhava.py      ← parser yields sane verse records (spot-check SB 11.7.1)
│   ├── test_retrieval.py          ← known queries retrieve known verses (2.47, Piṅgalā…)
│   └── test_citations.py          ← citation checker rejects invented references
└── requirements.txt               ← pinned deps (most already installed)
```

---

## 5. The Krishna persona & answer format (the heart of the product)

Every answer will follow the pattern Krishna Himself uses with Arjuna and Uddhava:

1. **Acknowledge** — speak to the person warmly, by their situation ("I hear your fear…"), teacher-friend tone
   (*sakhā*), never cold or clinical.
2. **Teach** — the underlying truth, drawn **only** from retrieved verses (soul's eternality, karma-yoga,
   equanimity, detachment, three modes, bhakti — whichever the verses support).
3. **Quote** — 1–3 verses in English **verbatim from these books**, each with its reference
   (e.g. *Bhagavad-gītā 6.5*, *Uddhava-gītā ch. 3 — Story of Piṅgalā, SB 11.8*).
4. **Apply** — one or two concrete, doable steps for *their* situation ("what Krishna would have said" to them).
5. **References block** — machine-checked list of every verse used.

Hard rules enforced in prompt + code:
- **No invented verses, no invented references.** Citation checker validates each ref against `verses.jsonl`;
  failures are regenerated once, then the reference is dropped and the answer marked accordingly.
- If the books don't address a topic → say so plainly, offer the nearest teaching, label it as such.
- **Safety:** for self-harm/medical/mental-health crises, Krishna's compassion + a gentle, clear direction to
  professional/human help; no medical/financial/legal advice beyond what the texts teach as general wisdom.
- Default reply language: English (user's language); Hindi support noted as future work (see §8).

---

## 6. Full task list (Phase 3 execution — in order)

**Ingestion — Uddhava-gītā (book 1)**
- [x] 1. `extract_uddhava.py`: full parse of all 929 pages → verse records (ref from `॥ ११.x.y ॥`, chapter,
        Sanskrit, transliteration, synonyms, translation, purport, PDF page)
        → DONE: 1,064 records (1,040 verses + 24 chapter summaries), 0 missing translations
- [x] 2. Validate counts (~940+ verses; reconcile 942 markers vs ~1,043 verse-end markers — multi-verse texts),
        print a parse report; manually spot-check 5 verses against the PDF
        → DONE: shared groups (ŚB 11.6.40-41, Texts 33-35, Texts 36-42…) get shared translations with
        honest "shared translation for verses n–m" refs; all 24 chapter titles captured
- [x] 3. Also extract chapter summaries (Contents, PDF pp. 2–6) as chapter-level records for broad questions
        → DONE (24 `SB-11.x.summary` records from chapter-opening prose)

**Ingestion — Bhagavad-gītā As It Is (book 2; replaces the old OCR tasks 4–6)**
- [x] 4. `extract_gita.py`: parse all 1,034 pages → verse records (chapter from the known chapter start-pages,
        `TEXT n` / combined `Texts n–m`, transliteration, synonyms, TRANSLATION, PURPORT, PDF page);
        normalize ClearScan mojibake (`Kr§pa`, `Krqva` → Kṛṣṇa…) in stored text
        → DONE: 700 records, 700 good; garbled heads ('1EXTS 6-7', 'TEXT lO'), garbled markers
        ('TRANSLATIO0') and page furniture all handled; leak scan CLEAN
- [x] 5. Split combined texts (`Texts 3–4`) into per-verse records so references stay verse-precise (BG c.v)
        → DONE: 78 combined/shared records carry honest "shared text for verses n–m" refs; embedded
        multi-translation bodies split by block ordinal; BG 10.35 (unheaded on PDF p.571), BG 12.5,
        BG 13.7 and BG 13.1/13.2 split recovered from page dumps
- [x] 6. Validate: reconcile parsed verses against the book's own **Index of Sanskrit Verses** (PDF p. 935);
        expect ~700 verses across 18 chapters; spot-check 10 verses (incl. BG 2.47, 2.20, 6.5, 18.66) against the PDF
        → DONE: per-chapter counts match this edition exactly {1:46, 2:72, 3:43, 4:42, 5:29, 6:47, 7:30,
        8:28, 9:34, 10:42, 11:55, 12:20, 13:35, 14:27, 15:20, 16:24, 17:28, 18:78} = 700; the edition's
        own Index proves Ch.1 ends at 1.46 here ('na yotsya iti govindam' → 2.9), so no BG 1.47 record
        is created; spot-checks BG 2.47/2.20/6.5/18.66 + 18.71-18.73 verified against PDF pages

**Index**
- [x] 7. `build_index.py`: embed Translation (+chapter summary) of every verse via gateway → `index.npz`;
        store aligned metadata in `verses.jsonl`
        → DONE: 1,764 records embedded (700 BG + 1,064 SB), `nvidia/nemotron-3-embed-1b` 2048-dim,
        matrix row-aligned with `data\verses.jsonl` (asserted at load)

**Core engine**
- [x] 8. `store.py` + `retriever.py`: cosine top-K (K=6) + keyword/topic boost
        (topic map: anxiety→BG 6, grief→BG 2, anger→BG 2/16, attachment→Piṅgalā SB 11.8, tolerance→Avantī SB 11.23…)
        → DONE: hybrid scorer (0.45 embedding + 0.35 idf-keyword + topic boost); embedding-only scores
        proved nearly flat on this corpus, keyword+boost carry the ranking; topic ids verified in-store
- [x] 9. `persona.py`: Krishna system prompt (voice, 5-part answer format, grounding + safety rules)
        → DONE: KRISHNA_SYSTEM_PROMPT + USER_TEMPLATE; includes "never claim the teachings are silent
        when a supplied passage speaks" refinement after live tests
- [x] 10. `llm.py`: async gateway client (wonder primary, spark fallback), streaming-ready
        → DONE: async httpx, wonder→spark fallback, empty-content guard, 4000-token budget
        (reasoning tokens truncate smaller budgets — found live)
- [x] 11. `citations.py`: extract refs from the answer, verify against store, enforce/fix
        → DONE: parses References line + inline refs, verifies ids exist and quotes match stored
        translations verbatim; engine regenerates once, then strips fabrications

**Interfaces**
- [x] 12. `cli.py`: terminal chat — ask 5 sample life problems, eyeball quality
        → DONE: `python -m krsna_ai.cli "question"` + REPL mode; live answers verified
        (anxiety, anger, stock-tips, loneliness — citations ok, first-try)
- [x] 13. `app.py` + `web\index.html`: FastAPI `/chat` + chat page showing references under each answer
        → DONE: server on http://127.0.0.1:8000 (`/health` = 1,764 verses, `/` = chat page,
        `/chat` verified end-to-end with the loneliness question)

**Verification (Phase 4)**
- [x] 14. Test battery: 12 fixed questions (anxiety, grief, anger, failure, death of loved one, indecision,
        loneliness, attachment, insult/tolerance, purpose, fear of future, family conflict) — check:
        answer grounded, quotes verbatim, refs real, voice right
        → DONE: 12/12 pass citation verification (11 first-try; the stock-tips question passed after the
        one allowed regeneration, honestly declining + nearest teaching SB 11.8.11/BG 9.31). Canonical
        verses landed as designed: BG 2.47/2.13/2.20/2.27 grief, BG 2.62/3.37/2.63 anger, Piṅgalā
        SB 11.8.44/11.8.37 attachment, Avantī brāhmaṇa SB 11.23.2/11.23.42 insult. Full output:
        `battery_output.txt` (Q12 re-verified live after persona fix)
- [x] 15. `pytest` suite green (parser, retrieval, citations)
        → DONE: 13 passed (tests/test_parse_data.py, test_retrieval.py, test_citations.py).
        The suite caught 3 real defects en route: BG-17.2 space-garbled marker leak,
        enforce() leaving prose citations, and the References-line multi-id parse
- [x] 16. Write `02_FINAL_REPORT.md` (done/pending/how to run) + usage section in this plan
        → DONE: `02_FINAL_REPORT.md` written (completed items, how it works, run instructions,
        pending/future work, acceptance table)

---

## 7. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| ~~Gītā OCR quality / runtime~~ — **eliminated** by switching to *As It Is* (built-in text layer) | — | Star 1993 scan is optional-only now; no OCR on the critical path |
| ClearScan mojibake in *As It Is* (diacritics garbled: Kṛṣṇa → `Kr§pa`/`Krqva`; Devanāgarī garbled) | Ugly Sanskrit/transliteration if quoted raw | Normalize known variants at ingestion; **quote only the English Translation verbatim**; transliteration stored cleaned-best-effort and flagged; validate 636 TRANSLATION blocks + Index of Sanskrit Verses (PDF p. 935) |
| Combined verses in *As It Is* ("Texts 3–4") | Reference could point at a verse pair, not one verse | Task #5 splits combined texts into per-verse records before indexing |
| Verse-reference mismatch (Uddhava book ch. ≠ SB ch.; 942 markers vs 1,043 verse-ends) | Wrong citations — fatal for this product | Parser keys on the printed `॥ ११.x.y ॥` canonical refs; dedicated validation task (#2) reconciles counts before indexing |
| LLM invents a plausible-sounding verse | Breaks "correct references" promise | Citation checker (#11) + prompt rule + regeneration/drop logic; test battery (#14) audits verbatim quotes |
| Persona drift (sounds like generic AI, or claims to *be* God in a confusing way) | Product feels wrong / could offend | Persona prompt: speak *as Krishna's voice from these texts*, devotional framing in UI ("guided by the Gita & Uddhava-gītā"); reviewed against sample answers in task #12 |
| Sensitive user inputs (self-harm, illness, money) | Harm if answered carelessly | Safety rules in persona (§5); crisis → compassionate redirect to human/professional help |
| Gateway/model outage | Assistant down | `muse-spark-1.3` fallback; local sentence-transformers fallback for embeddings; everything else runs offline once indexed |
| Copyright | Published editions (Macmillan/BBT 1972; Star Publications 1993; Uddhava edition) | Personal/hackathon use of the user's own PDFs; verse quotation with attribution; **flagged for user decision if this ever goes public** |

---

## 8. Missing information / ambiguities — decisions I need from you

Defaults I will follow **unless you say otherwise** when approving:

1. **Interface:** Web chat page + CLI (my default). Other options: Gradio, Telegram/WhatsApp bot, desktop app.
2. **Reply language:** English first. (Hindi replies are possible later — they would need the Star 1993 scan's
   Hindi blocks OCR'd, and the Uddhava-gītā is English-only.)
3. **Answer length:** Medium — teaching + 1–3 verses + practical step (not one-liners, not essays).
4. **Who "Krishna" is in the UI:** presented as *"Krishna's voice, guided by the Bhagavad Gita and Uddhava-gītā"*
   with a small note that it is an AI assistant — respectful and honest. Tell me if you want different framing.
5. **NOT FOUND IN PDF (unknowns from Phase 1):** Uddhava-gītā translator/publisher; exact per-chapter SB verse
   ranges. (The Star-scan question "what is on Gita pp. 419–428" is now moot for the build.) None block the
   build; all are logged in [00_PDF_ANALYSIS.md](00_PDF_ANALYSIS.md) §D.5.

---

## 9. How we will know it is correct (acceptance criteria)

- Ask *"I am anxious about my future"* → answer cites real verses (e.g. BG 6.x / 2.x), quotes match
  `verses.jsonl` character-for-character, and a citation check passes.
- Ask something the books never discuss (e.g. stock tips) → assistant says the texts do not cover it,
  offers the nearest teaching (e.g. karma-yoga / detachment from fruits), clearly labelled.
- Every reference shown can be opened in the source PDF at the stored PDF page.
- `pytest` green; 12-question battery reviewed with you in `02_FINAL_REPORT.md`.

---

## 10. Approval

**Please approve, approve with changes, or reject this plan.** On approval I execute §6 in order,
ticking the checkboxes as I go, and stop again if I hit a genuine ambiguity — per your rules,
no guessing, no invented scripture, and nothing beyond these three books presented as Krishna's word.
