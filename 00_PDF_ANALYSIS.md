# 00 — PDF Analysis
### Workspace: `U:\MetaHackathon` · Goal: Krishna AI Assistant grounded in these texts
### Date of analysis: 2026-10-27 · Updated same day: third book added (see ADDENDUM below)

> **Citation convention used in this file:** "PDF page" = page number inside the PDF file (what a program reads).
> "Printed page" = the page number printed on the book page itself (what a reader sees). Both are given where known,
> because references given to users of the assistant should use the *scriptural* reference (chapter/verse), not PDF pages.

---

## 0. What was found in the workspace

| # | File | Size | Pages | Type |
|---|------|------|------:|------|
| 1 | `The Uddhava-gītā (2).pdf` | 10.5 MB | **929 PDF pages** | Born-digital text (fully extractable) |
| 2 | `Srimad Bhagavad Gita (Sanskrit, Hindi & English).pdf` | 13.3 MB | **428 PDF pages** | Scanned images only — **no text layer at all** |
| 3 | `Bhagavad_gita-As_It_Is-Original_authorized_Macmillan_edition.pdf` — *added later* | **177 MB** | **1,034 PDF pages** | ClearScan text layer present (2.01 M chars) — **directly readable** |

Other files in the workspace: [README.md](README.md) (Meta model/gateway info), [test_meta_models.py](test_meta_models.py)
(model connectivity test), [AGENTS.md](AGENTS.md) (workspace agent rules). No code project existed before this task.

**Bottom line (updated):** Two books can be read by a computer today — the Uddhava-gītā and, since the addendum,
*Bhagavad-gītā As It Is* (1972). The Star Publications scan would still need OCR and is now optional. This removes
the project's biggest technical risk; see the ADDENDUM next.

---

## ADDENDUM — Third book added by the user (2026-10-27, later)

**File:** `Bhagavad_gita-As_It_Is-Original_authorized_Macmillan_edition.pdf` (177 MB, **1,034 PDF pages**).

- **Identity (from PDF metadata):** Title *Bhagavad-gita As It Is*; Author **His Divine Grace A. C. Bhaktivedanta Swami
  Prabhupāda**; keywords "Macmillan 1972; pre-78; ISKCON books; BBT"; source Krishnapath.org. Scanned with a CanoScan
  LiDE 210 and OCR'd by the *Adobe Acrobat Paper Capture Plug-in with ClearScan* (2013-02-06).
- **Text layer: YES** — 2,014,622 chars (~1,948/page); only 20 near-empty pages (picture plates, e.g. PDF pp. 31–39,
  392–404, 758–763). No Tesseract OCR needed.
- **Structure (PDF bookmarks + Contents PDF pp. 7–8):** Foreword (PDF p. 9), Preface (p. 11 — author confirms this is
  the *complete* edition replacing the abridged first publication), Introduction (p. 15), Disciplic Succession (p. 59),
  then BG chapters 1–18 starting at PDF pp. 60, 100, 189, 241, 298, 333, 387, 450, 481, 531, 579, 635, 658, 702, 732,
  776, 805, 834; Appendixes p. 905; References p. 915; Glossary p. 917; Sanskrit Pronunciation Guide p. 933;
  **Index of Sanskrit Verses p. 935** (complete verse checklist — ideal for extraction validation); General Index p. 951.
- **Verse format (verified PDF pp. 62–63, 111–112):** identical 5-part layout to the Uddhava-gītā —
  `TEXT n` → Devanāgarī (garbled in text layer) → transliteration → synonyms (run-on) → `TRANSLATION` → `PURPORT`.
  Machine counts: **636 TRANSLATION blocks, 622 PURPORT blocks**; combined texts (e.g. "Texts 3–4") explain why this
  is below the traditional ~700 verses — the parser must split combined texts and reconcile against the Index of
  Sanskrit Verses.
- **Known defect:** ClearScan mojibake in diacritics — "Kṛṣṇa" appears as `Kr§pa`, `Krqva`, `Kf§!J.a`; "Kurukṣetra" as
  `KurukWetra`. English translations remain readable; ingestion must normalize these variants and never quote
  transliteration verbatim from the raw layer.
- **Revised source ranking:** this book becomes the **primary Bhagavad Gita** (readable today, same tradition and
  terminology as the Uddhava-gītā). The Star Publications 1993 scan becomes an **optional supplement** (Hindi blocks)
  only if Hindi answers are wanted later. Analysis of the Star edition (Part B below) is retained as-is.

---

## PART A — `The Uddhava-gītā (2).pdf`

### A.1 Title, author, provenance

- **Title:** *The Uddhava-gītā* (PDF page 1).
- **What it is:** The dialogue between Lord Kṛṣṇa and His devotee Uddhava, taken from **Śrīmad-Bhāgavatam
  (Bhāgavata Purāṇa), Canto 11**, combined in this PDF with background chapters from Canto 3
  (e.g. PDF pages 9–11 quote ŚB 3.4.24 and ŚB 3.1.25 on how Uddhava met Vidura).
- **Author / translator / commentator:** **NOT FOUND IN PDF** (front matter). The PDF metadata titles/authors are empty.
  The Introduction quotes lectures and room conversations of Śrīla Prabhupāda (e.g. "Room Conversation Oct. 6, 1972
  Berkeley", PDF page 11) and glosses by Śrīla Viśvanātha Cakravartī Ṭhākura and Śrīla Jīva Gosvāmī (PDF pages 9, 28),
  which indicates a Bhaktivedanta (ISKCON-tradition) edition — **but the edition, translator and publisher are not
  printed in the pages inspected, so this is an inference, not a verified fact.**
- **PDF provenance (file metadata):** created with *Adobe InDesign CC 2017 (Windows)*, 2019-03-16. This is file metadata,
  not book publication data.

### A.2 Table of Contents / Structure (PDF pages 2–6, confirmed against PDF bookmarks)

Printed page numbers below are the book's own page numbers as printed in the Contents.

| Book chapter | Title | Printed p. | Source in Śrīmad-Bhāgavatam* |
|---|---|---:|---|
| — | Preface | 1 | — |
| — | Introduction | 2 | — |
| 1 | The Yadu Dynasty Retires to Prabhāsa | 6 | SB 11.6 |
| 2 | Lord Kṛṣṇa Instructs Uddhava | 18 | SB 11.7 |
| 3 | The Story of Piṅgalā | 91 | SB 11.8 |
| 4 | Detachment from All that Is Material | 130 | SB 11.9 |
| 5 | The Nature of Fruitive Activity | 163 | SB 11.10 |
| 6 | The Symptoms of Conditioned and Liberated Living Entities | 201 | SB 11.11 |
| 7 | Beyond Renunciation and Knowledge | 260 | SB 11.12 |
| 8 | The Haṁsa-avatāra Answers the Questions of the Sons of Brahmā | 288 | SB 11.13 |
| 9 | Lord Kṛṣṇa Explains the Yoga System to Śrī Uddhava | 329 | SB 11.14 |
| 10 | Lord Kṛṣṇa's Description of Mystic Yoga Perfections | 367 | SB 11.15 |
| 11 | The Lord's Opulence | 396 | SB 11.16 |
| 12 | Lord Kṛṣṇa's Description of the Varṇāśrama System | 429 | SB 11.17 |
| 13 | Description of Varṇāśrama-dharma | 479 | SB 11.18 |
| 14 | The Perfection of Spiritual Knowledge | 523 | SB 11.19 |
| 15 | Pure Devotional Service Surpasses Knowledge and Detachment | 557 | SB 11.20 |
| 16 | Lord Kṛṣṇa's Explanation of the Vedic Path | 597 | SB 11.21 |
| 17 | Enumeration of the Elements of Material Creation | 642 | SB 11.22 |
| 18 | The Song of the Avantī Brāhmaṇa | 693 | SB 11.23 |
| 19 | The Philosophy of Sāṅkhya | 739 | SB 11.24 |
| 20 | The Three Modes of Nature and Beyond | 761 | SB 11.25 |
| 21 | The Aila-gītā | 787 | SB 11.26 |
| 22 | Lord Kṛṣṇa's Instructions on the Process of Deity Worship | 812 | SB 11.27 |
| 23 | Jñāna-yoga | 850 | SB 11.28 |
| 24 | Bhakti-yoga | 889 | SB 11.29 |

\* **Mapping note:** Book chapters 1–24 run parallel to SB Canto 11, chapters 6–29 (offset of +5), and the Introduction
also draws on Canto 3. This mapping is inferred from the visible citation "Canto 11 … CHAPTER SIX" on book chapter 1
(PDF page 12) and verse references such as ॥ ११.७.१ ॥ in book chapter 2 (PDF page 25). **Each chapter's exact SB range
must be verified programmatically during extraction — NOT FOUND IN PDF as an explicit table.**

### A.3 How each verse is laid out (the unit the assistant will quote)

Every verse ("Text") follows a fixed, machine-parseable 5-part pattern — verified on PDF pages 25–28:

1. `Text N` heading
2. **Sanskrit** in Devanāgarī, ending with the canonical reference, e.g. `॥ ११.७.१ ॥`
3. **Transliteration** (IAST roman, e.g. `śrī-bhagavān uvāca …`)
4. **Synonyms** — word-by-word glossary
5. **Translat
...[truncated 13588 chars]