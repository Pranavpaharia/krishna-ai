"""Extract structured verses from 'The Uddhava-gita (2).pdf'.

Anchors (verified by probing the born-digital text layer):
* 1,043 Devanagari verse-end markers ``॥ ११.७.१ ॥`` — the canonical
  Śrīmad-Bhāgavatam canto.chapter.verse reference. This is the ONLY reliable
  verse boundary; the printed ``Text n`` head appears just 882 times because
  some verses share a block.
* Per-verse layout: [optional ``Text n``] → Devanagari → transliteration →
  ``Synonyms`` → ``Translation`` → ``Purport``.
* Body = ŚB Canto 11 ch. 6-29 presented as Uddhava-gita chapters 1-24
  (book chapter = SB chapter - 5). Front matter (PDF pp. 1-11) is skipped.

Run:  python -m krsna_ai.ingest.extract_uddhava
Out:  data/verses_uddhava.jsonl
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf

from krsna_ai.ingest.clean import clean_block, clean_field, is_mostly_garbage
from krsna_ai.ingest.schema import Verse

ROOT = Path(__file__).resolve().parents[2]
PDF_PATH = ROOT / "The Uddhava-gītā (2).pdf"
OUT_PATH = ROOT / "data" / "verses_uddhava.jsonl"
FIRST_BODY_PAGE = 12  # PDF page 12 (idx 11) = start of Uddhava-gita Chapter 1

DEV_NUM = {"०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
           "५": "5", "६": "6", "७": "7", "८": "8", "९": "9"}
VERSE_END = re.compile(r"॥\s*([०-९]+)\.([०-९]+)\.([०-९]+)\s*॥")
CHAP_HEADER = re.compile(r"CHAPTER\s+([A-Z ]+?)\s*\n")
WORD_NUM = {
    "ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5, "SIX": 6,
    "SEVEN": 7, "EIGHT": 8, "NINE": 9, "TEN": 10, "ELEVEN": 11,
    "TWELVE": 12, "THIRTEEN": 13, "FOURTEEN": 14, "FIFTEEN": 15,
    "SIXTEEN": 16, "SEVENTEEN": 17, "EIGHTEEN": 18, "NINETEEN": 19,
    "TWENTY": 20, "TWENTY-ONE": 21, "TWENTY-TWO": 22, "TWENTY-THREE": 23,
    "TWENTY-FOUR": 24, "TWENTY-FIVE": 25, "TWENTY-SIX": 26,
    "TWENTY-SEVEN": 27, "TWENTY-EIGHT": 28, "TWENTY-NINE": 29, "THIRTY": 30,
}
BLOCK_MARKERS = ("Synonyms", "Translation", "Purport")


def _chapter_summaries(doc: pymupdf.Document) -> list[Verse]:
    """Per-chapter records built from the 'chapter summary' prose that opens
    each body chapter (between the chapter header and its first verse).
    These answer overview questions like 'what is the Story of Pingala?'."""
    out: list[Verse] = []
    for idx in range(FIRST_BODY_PAGE - 1, doc.page_count):
        lines = doc[idx].get_text().splitlines()
        for li, ln in enumerate(lines):
            ms = re.fullmatch(r"CHAPTER\s+([A-Z\- ]+)", ln.strip())
            if not (ms and ms.group(1).strip() in WORD_NUM and li + 1 < len(lines)):
                continue
            sb_chap = WORD_NUM[ms.group(1).strip()]
            title = lines[li + 1].strip()
            rest = "\n".join(lines[li + 2:])
            cut = len(rest)
            for pat in (r"(?m)^Text \d+\s*$", r"(?m)^ŚB\s+11\.", r"॥"):
                mm = re.search(pat, rest)
                if mm:
                    cut = min(cut, mm.start())
            summary = clean_block(rest[:cut])
            if len(summary) < 80:
                continue
            out.append(Verse(
                id=f"SB-11.{sb_chap}.summary",
                book="Uddhava-gita",
                chapter=sb_chap - 5,
                verse=None,
                ref=f"Uddhava-gita chapter {sb_chap - 5}: {title} — chapter summary "
                    f"(Srimad-Bhagavatam 11.{sb_chap})",
                chapter_title=title,
                translation=summary,
                pdf_page=idx + 1,
                quality="summary",
            ))
    return out


def _dev_to_int(s: str) -> int:
    return int("".join(DEV_NUM[c] for c in s))


def _context_before(blob: str, pos: int, window: int = 4000) -> str:
    """Text immediately before a verse's Sanskrit run: chapter summary prose,
    narrative bridges, speaker introductions ('Lord Krishna said: ...').
    This is genuine teaching content, so we keep it attached to the verse."""
    pre = blob[max(0, pos - window):pos]
    # cut anything up to the previous verse-end marker
    prev = list(VERSE_END.finditer(pre))
    if prev:
        pre = pre[prev[-1].end():]
    # cut up to the end of a previous verse's Purport? keep it simple: drop
    # everything up to the last Synonyms/Translation/Purport marker block end
    lines = [ln for ln in pre.splitlines() if ln.strip()]
    keep: list[str] = []
    for ln in lines:
        s = ln.strip()
        if re.fullmatch(r"\d+", s) or "Uddhava-g" in s:
            continue
        if re.match(r"^Text \d+\s*$", s) or re.match(r"^ŚB\s+11\.", s):
            keep = []
            continue
        if s in ("Synonyms", "Translation", "Purport"):
            keep = []
            continue
        dev = sum(1 for c in s if "\u0900" <= c <= "\u097f")
        if len(s) > 4 and dev / len(s) > 0.3:
            keep = []
            continue
        keep.append(s)
    prose = clean_block(" ".join(keep))
    # heuristic: only real prose (>= 8 words, contains sentence punctuation)
    if len(prose.split()) >= 8 and ("." in prose or ":" in prose):
        return prose
    return ""


def _split_blocks(body: str) -> dict[str, str]:
    """Split the text between a verse-end marker and the next verse start
    into Synonyms / Translation / Purport (+ trailing narrative)."""
    parts: dict[str, str] = {}
    # find marker positions
    marks: list[tuple[int, str]] = []
    for m in re.finditer(r"(?m)^(Synonyms|Translation|Purport)\s*$", body):
        marks.append((m.start(), m.group(1)))
    for idx, (pos, name) in enumerate(marks):
        end = marks[idx + 1][0] if idx + 1 < len(marks) else len(body)
        chunk = body[pos + len(name):end]
        # drop everything from the NEXT verse's Sanskrit run onwards: the
        # block ends where a line that is mostly Devanagari begins, or at a
        # 'Text n' / 'ŚB 11.x.y-z' combined-verse heading.
        lines = chunk.splitlines()
        keep: list[str] = []
        for ln in lines:
            s = ln.strip()
            if re.match(r"^Text \d+\s*$", s) or re.match(r"^ŚB\s+11\.", s):
                break
            if len(keep) >= 1 and len(s) > 4:
                dev = sum(1 for c in s if "\u0900" <= c <= "\u097f")
                if dev / len(s) > 0.3:
                    break
            keep.append(ln)
        chunk = "\n".join(keep)
        parts[name.lower()] = clean_block(chunk)
    return parts


def _sanskrit_before(text: str, end_marker_start: int) -> str:
    """Devanagari run immediately before the verse-end marker."""
    pre = text[:end_marker_start]
    lines = [ln.strip() for ln in pre.splitlines() if ln.strip()]
    dev_lines: list[str] = []
    for ln in reversed(lines):
        if re.search(r"[\u0900-\u097F]", ln):
            dev_lines.append(ln)
        elif dev_lines:
            break
    return " ".join(reversed(dev_lines))


def extract() -> list[Verse]:
    doc = pymupdf.open(PDF_PATH)
    verses: list[Verse] = []
    seen: set[str] = set()

    # Chapter titles: 'CHAPTER SIX' (SB chapter number) followed by the title
    # line; only present on each chapter's opening page.
    chap_title: dict[int, str] = {}
    for idx in range(FIRST_BODY_PAGE - 1, doc.page_count):
        lines = doc[idx].get_text().splitlines()
        for li, ln in enumerate(lines):
            ms = re.fullmatch(r"CHAPTER\s+([A-Z\- ]+)", ln.strip())
            if ms and ms.group(1).strip() in WORD_NUM and li + 1 < len(lines):
                chap_title[WORD_NUM[ms.group(1).strip()]] = lines[li + 1].strip()

    # Pass 2: walk verse-end markers in reading order; the text between two
    # consecutive markers belongs (Synonyms/Translation/Purport) to the first.
    stream: list[tuple[int, str]] = []  # (marker_end_pos_in_doc_stream?)
    full: list[str] = []
    page_start: list[int] = []
    for idx in range(FIRST_BODY_PAGE - 1, doc.page_count):
        t = doc[idx].get_text()
        page_start.append(sum(len(x) for x in full))
        full.append(t)
    blob = "".join(full)

    def page_of(pos: int) -> int:
        # binary search over page starts
        lo, hi = 0, len(page_start) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if page_start[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return FIRST_BODY_PAGE + lo

    pending_group: dict[tuple[int, int, int], list[tuple[int, int]]] = {}
    matches = list(VERSE_END.finditer(blob))
    for i, m in enumerate(matches):
        canto, chap, num = (_dev_to_int(m.group(k)) for k in (1, 2, 3))
        vid = f"SB-{canto}.{chap}.{num}"
        if vid in seen:
            continue
        seen.add(vid)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(blob)
        body = blob[start:end]
        blocks = _split_blocks(body)
        context = _context_before(blob, m.start())
        sanskrit = _sanskrit_before(blob, m.start())
        # transliteration: lines between the marker and 'Synonyms' that are
        # Roman prose; skip the NEXT verse's Roman lines (they come after its
        # Devanagari run, which the dev-ratio check cuts off).
        pre_syn = body.split("Synonyms")[0] if "Synonyms" in body else ""
        trans_lines = []
        for ln in pre_syn.splitlines():
            s = ln.strip()
            if not s or re.fullmatch(r"\d+", s) or "Uddhava-g" in s:
                continue
            dev = sum(1 for c in s if "\u0900" <= c <= "\u097f")
            if len(s) > 4 and dev / len(s) > 0.3:
                break
            if not is_mostly_garbage(s):
                trans_lines.append(s)
        transliteration = clean_field(" ".join(trans_lines))
        # Group detection: a shared-verse heading ('ŚB 11.6.40-41' or
        # 'Texts 33-35') appears BEFORE an entire Sanskrit run. Register
        # this verse's index under the heading it follows; the group and
        # its shared Translation are resolved after the scan.
        pre = blob[max(0, m.start() - 2500):m.start()]
        heading_key: tuple[int, int] | None = None
        for hm in re.finditer(r"(?:ŚB\s+11\.\d+\.|Texts\s+)(\d+)\s*[-–]\s*(\d+)", pre):
            if int(hm.group(1)) <= num <= int(hm.group(2)):
                heading_key = (int(hm.group(1)), int(hm.group(2)))
        if heading_key:
            pending_group.setdefault((chap, heading_key[0], heading_key[1]), []).append((num, len(verses)))
        translation = blocks.get("translation", "")
        quality = "good" if translation else "partial"
        book_chap = chap - 5 if canto == 11 and 6 <= chap <= 29 else chap
        title = chap_title.get(chap, "")
        ref = f"Srimad-Bhagavatam {canto}.{chap}.{num}"
        if title:
            ref += f" (Uddhava-gita chapter {book_chap}: {title})"
        verses.append(Verse(
            id=vid,
            book="Uddhava-gita",
            chapter=book_chap,
            verse=num,
            ref=ref,
            chapter_title=title,
            sanskrit=clean_field(sanskrit),
            transliteration=transliteration,
            synonyms=blocks.get("synonyms", ""),
            translation=translation,
            purport=clean_block((context + " " + blocks.get("purport", "")).strip()),
            pdf_page=page_of(m.start()),
            quality=quality,
        ))
    # Propagate each group's shared Translation (sitting after the group's
    # transliteration run) to every member; annotate the citation honestly.
    verse_by_num = {v.verse: v for v in verses if v.chapter is not None}
    for (chap_n, lo_n, hi_n), members in pending_group.items():
        carrier = next((verses[j] for _, j in members if verses[j].translation), None)
        if carrier is None:
            continue
        lo_ref = f"Srimad-Bhagavatam 11.{chap_n}.{lo_n}"
        hi_ref = f"{hi_n}"
        for num, j in members:
            if verses[j].translation:
                continue
            verses[j].translation = carrier.translation
            verses[j].quality = "partial"
            verses[j].ref = (
                f"{lo_ref}-{hi_ref} (shared translation for verses {lo_n}-{hi_n}; "
                f"this is verse {num})"
            )

    doc.close()
    return verses


def main() -> None:
    doc = pymupdf.open(PDF_PATH)
    summaries = _chapter_summaries(doc)
    doc.close()
    verses = extract() + summaries
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as fh:
        for v in verses:
            fh.write(json.dumps(v.model_dump(), ensure_ascii=False) + "\n")
    good = sum(1 for v in verses if v.quality == "good")
    summ = sum(1 for v in verses if v.quality == "summary")
    print(f"Uddhava-gita: {len(verses)} records ({good} good, {summ} chapter summaries) -> {OUT_PATH}")
    by_chap: dict[int, int] = {}
    for v in verses:
        if v.verse is not None:
            by_chap[v.chapter] = by_chap.get(v.chapter, 0) + 1
    print("per-book-chapter verse counts:", dict(sorted(by_chap.items())))
    missing = [v.ref for v in verses if not v.translation]
    print("still missing translation:", len(missing), missing[:8])


if __name__ == "__main__":
    main()
