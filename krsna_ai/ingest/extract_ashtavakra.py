"""Extract verse records from 'The Heart of Awareness: Ashtavakra Gita'
(John Richards, 1996).

Layout (verified by probing the born-digital text layer):
* 48 pages; front matter = PDF pp. 1-5 (title, translator's intro, contents).
* Body = PDF pp. 6-48, chapters 1-20, each opening with ``Chapter N Title``.
* Verse numbers appear INLINE at the end of each verse's English text
  (e.g. ``...Tell me this, sir. 1.1``), spanning page breaks.
* No Sanskrit, transliteration, synonyms or purport blocks — this is a plain
  English translation. Speaker labels (``Janaka said:`` /
  ``Ashtavakra said:``) are kept as verse context.
* 298 verses total (Richards edition numbering).

Run:  python -m krsna_ai.ingest.extract_ashtavakra
Out:  data/verses_ashtavakra.jsonl
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):  # allow direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pymupdf  # type: ignore

from krsna_ai.ingest.clean import clean_field
from krsna_ai.ingest.schema import Verse

ROOT = Path(__file__).resolve().parents[2]
PDF_PATH = ROOT / "AshtavakraGita.pdf"
OUT_PATH = ROOT / "data" / "verses_ashtavakra.jsonl"

FIRST_BODY_PAGE = 6   # PDF page 6 = Chapter 1 opens
LAST_BODY_PAGE = 48   # last body page

CHAPTER_RE = re.compile(r"Chapter\s+(\d+)\s+(.+)")
VERSE_END_RE = re.compile(r"\b(\d+)\.(\d+)\b")


def _page_of(pos: int, boundaries: list[tuple[int, int, int]]) -> int:
    for start, end, pno in boundaries:
        if start <= pos < end:
            return pno
    return boundaries[-1][2]


def extract() -> list[Verse]:
    doc = pymupdf.open(PDF_PATH)

    # Gather body text page by page, recording page-position map
    page_texts: list[tuple[int, str]] = []
    for idx in range(FIRST_BODY_PAGE - 1, LAST_BODY_PAGE):
        text = doc[idx].get_text()
        page_texts.append((idx + 1, text))

    # Concatenate with page-position map
    full = ""
    boundaries: list[tuple[int, int, int]] = []
    pos = 0
    for pno, text in page_texts:
        full += text
        boundaries.append((pos, pos + len(text), pno))
        pos += len(text)
    doc.close()

    # Locate chapter headers in the concatenated body text
    chap_matches = list(CHAPTER_RE.finditer(full))
    chapters: list[tuple[int, str, int, int]] = []
    for i, m in enumerate(chap_matches):
        chap_num = int(m.group(1))
        title = m.group(2).strip()
        c_start = m.end()  # text *after* the chapter header
        c_end = chap_matches[i + 1].start() if i + 1 < len(chap_matches) else len(full)
        chapters.append((chap_num, title, c_start, c_end))

    verses: list[Verse] = []
    for chap_num, title, c_start, c_end in chapters:
        chap_text = full[c_start:c_end]
        verse_matches = list(VERSE_END_RE.finditer(chap_text))

        for i, m in enumerate(verse_matches):
            verse_num = int(m.group(2))

            # Verse text runs from chapter start (or previous verse number end)
            # up to (not including) this verse's trailing number
            v_start = 0 if i == 0 else verse_matches[i - 1].end()
            raw = chap_text[v_start:m.start()].strip()

            translation = clean_field(raw)

            verses.append(Verse(
                id=f"AG-{chap_num}.{verse_num}",
                book="Ashtavakra Gita",
                chapter=chap_num,
                verse=verse_num,
                ref=f"Ashtavakra Gita {chap_num}.{verse_num}",
                chapter_title=title,
                sanskrit="",
                transliteration="",
                synonyms="",
                translation=translation,
                purport="",
                pdf_page=_page_of(c_start + m.end(), boundaries),
                quality="good",
            ))

    return verses


def main() -> None:
    verses = extract()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as fh:
        for v in verses:
            fh.write(json.dumps(v.model_dump(), ensure_ascii=False) + "\n")
    good = sum(1 for v in verses if v.quality == "good")
    print(f"Ashtavakra Gita: {len(verses)} records ({good} good) -> {OUT_PATH}")
    by_chap: dict[int, int] = {}
    for v in verses:
        if v.verse is not None:
            by_chap[v.chapter] = by_chap.get(v.chapter, 0) + 1
    print("per-chapter verse counts:", dict(sorted(by_chap.items())))
    missing = [v.id for v in verses if not v.translation]
    print("missing translation:", len(missing), missing[:12])


if __name__ == "__main__":
    main()
