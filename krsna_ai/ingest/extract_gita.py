"""Extract verse records from Bhagavad-gita As It Is (Macmillan 1972).

Observed layout (see 00_PDF_ANALYSIS.md ADDENDUM + probes):
* 18 chapters open with a title page: ``CHAPTER <WORD>`` then title,
  Chapter 1 at PDF p.60 ... Chapter 18 at PDF p.834.
* Verse block: ``TEXT n`` (or ``TEXTS n-m`` for several verses sharing one
  translation) -> Devanagari Sanskrit (ClearScan-garbled in the text layer,
  kept only as provenance) -> transliteration -> word-for-word synonyms ->
  ``TRANSLATION`` -> ``PURPORT``.
* BG 1.1 has NO ``TEXT 1`` heading (verified PDF p.61): just ``TRANSLATION``
  at the top of the chapter. Handled specially.
* Chapter summaries (the 'Chapter Summary' section near each chapter end)
  become chapter-level ``summary`` records for broad questions.
* The Index of Sanskrit Verses (printed p. 899+) lists verses by first line;
  it is used only as a sanity oracle for the verse count (~700).

The quotable text is the clean English TRANSLATION. Transliteration and
synonyms are stored after conservative mojibake repair (see clean.py).

Run:  python -m krsna_ai.ingest.extract_gita
Out:  data/verses_gita.jsonl
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):  # allow direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pymupdf  # type: ignore

from krsna_ai.ingest.clean import (
    clean_block,
    clean_field,
    clean_translation,
    is_mostly_garbage,
    normalize_mojibake,
    strip_page_furniture,
)
from krsna_ai.ingest.schema import Verse

ROOT = Path(__file__).resolve().parents[2]
PDF_PATH = ROOT / "Bhagavad_gita-As_It_Is-Original_authorized_Macmillan_edition.pdf"
OUT_PATH = ROOT / "data" / "verses_gita.jsonl"

WORD_NUM: dict[str, int] = {
    "ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5, "SIX": 6,
    "SEVEN": 7, "EIGHT": 8, "NINE": 9, "TEN": 10, "ELEVEN": 11, "TWELVE": 12,
    "THIRTEEN": 13, "FOURTEEN": 14, "FIFTEEN": 15, "SIXTEEN": 16,
    "SEVENTEEN": 17, "EIGHTEEN": 18,
}

CHAP_START_PAGES: list[int] = [60, 100, 189, 241, 298, 333, 387, 450, 481,
                              531, 579, 635, 658, 702, 732, 776, 805, 834]

# ClearScan garbles digit ``1`` as ``l``/``I`` in verse heads ('TEXT ll',
# 'TEXT 7l', 'TEXT l'), so the number may be a l/1 token; normalised by
# ``_fix_num``. Mixed-case 'Text n' heads observed: 'Text 20' (BG 7.20).
# NOTE: bracketed variants ('Text 15]', 'Text 63)', 'Text 73 J') are NOT
# verse heads — page images (PDF pp. 71-72) prove they are page-top running
# heads ('Text 15] <chapter title> 43'), i.e. page furniture inside the
# previous verse's block. They must never split a verse body.
# Leading glyph garble also occurs ('1EXTS 6-7', PDF p.665) and digit 0
# prints as 'O' ('TEXT lO'), so accept a leading [1T] and O as a digit.
HEAD = re.compile(
    r"(?mi)^\s*[1T]?EXTS?\s+((?:[\dlIO](?:[\dlIO]|[ ,]|-|–|and)*[\dlIO]|[\dlIO]))\s*$",
    re.IGNORECASE)
# Combined head split across lines ('TEXTS' alone, verse plate follows, e.g.
# BG 10.8-9 p542, 12.8 p644, 15.8-9 p743, 16.8 p787): the number is NOT in the
# text layer; the embedded-translation splitter assigns the recovered verse.
HEAD_BARE = re.compile(r"(?mi)^\s*TEXTS\s*$")
# ClearScan mangles the TRANSLATION heading itself: 'TRANSJ.ATION' (BG 2.63),
# 'TRANS LA TJON' (BG 1.7), 'TRANSLATIO0'. The fuzzy pattern also matches a
# clean whole-line 'PURPORT'.
BLOCK = re.compile(r"(?mi)^\s*(TRANSLATION|TRANS[A-Z0-9. ]{0,7}TI[O0][N0]?|PURPORT)[,.]?\s*$")
# Same marker captured INLINE at a chunk start ('TRANSLATIO0 The seven...',
# '1RANSLATION Foods...', 'TRANSLATION, Those...'): stripped from prose.
INLINE_MARK = re.compile(
    r"^\s*(?:\S{1,14}TION|TRANSLATION)[,.]\s+|^\s*(?:TRANSLATIO\S{0,3}|[1T]RANSLATION)\s+")
# Page-top running head / page furniture embedded INSIDE a verse block
# ('Text 15]  Observing the Armies...', lone page numbers, chapter headers):
# stripped from quote-adjacent fields, never a verse boundary.
RUNHEAD_LINE = re.compile(
    r"(?mi)^\s*(?:Text\s+\d+\s*[\]\)]\s*.*|Text\s+\d+\s+J\s*|Bhagavad-gita As It Is|\[Ch\.\s*\S+|\d+)\s*$")


def _norm_block(name: str) -> str:
    return "translation" if name.upper().startswith("TRANS") else "purport"


def _fix_num(tok: str) -> str:
    """ClearScan garbles digits: 1 -> ``l``/``I``, 0 -> ``O`` ('TEXT lO' -> 10)."""
    return tok.replace("l", "1").replace("I", "1").replace("O", "0").replace("o", "0")


def _parse_numbers(spec: str) -> list[int]:
    """'2' -> [2]; '16-18' -> [16,17,18]; 'll' -> [11]; 'lO' -> [10]."""
    spec = spec.replace("–", "-").replace("—", "-")
    m = re.fullmatch(r"\s*([\dlIO]+)\s*-\s*([\dlIO]+)\s*", spec)
    if m:
        lo, hi = int(_fix_num(m.group(1))), int(_fix_num(m.group(2)))
        return list(range(lo, hi + 1)) if lo <= hi and hi - lo <= 10 else [lo, hi]
    nums = [int(_fix_num(x)) for x in re.findall(r"[\dlIO]+", spec)]
    return nums or []


def _chapter_titles(doc: pymupdf.Document) -> dict[int, str]:
    """Chapter titles from each chapter opening page.

    PDF-proven forms include:
    * ``CHAPTER ONE`` + a title that may wrap over two lines;
    * ``CHAPTER`` and ``TWELVE`` on separate lines;
    * unrelated scan noise before the actual ``CHAPTER ...`` line.

    We therefore locate the CHAPTER marker first, then collect the
    following alphabetic title lines until the first verse head. Titles
    are mojibake-normalised but otherwise copied from the PDF.
    """
    titles: dict[int, str] = {}
    for expected_chapter, page in enumerate(CHAP_START_PAGES, start=1):
        lines = [ln.strip() for ln in doc[page - 1].get_text().splitlines()]
        marker_idx: int | None = None
        chapter_num = expected_chapter

        for idx, line in enumerate(lines):
            upper = re.sub(r"\s+", " ", line.upper()).strip()
            if upper == "CHAPTER":
                marker_idx = idx
                # The chapter word may be on the next non-empty line.
                for nxt in lines[idx + 1: idx + 4]:
                    word = re.sub(r"\s+", " ", nxt.upper()).strip()
                    if word in WORD_NUM:
                        chapter_num = WORD_NUM[word]
                        marker_idx = lines.index(nxt, idx + 1)
                        break
                break
            m = re.fullmatch(r"CHAPTER\s+([A-Z]+)", upper)
            if m and m.group(1) in WORD_NUM:
                chapter_num = WORD_NUM[m.group(1)]
                marker_idx = idx
                break

        if marker_idx is None:
            continue

        parts: list[str] = []
        for line in lines[marker_idx + 1:]:
            if not line:
                if parts:
                    break
                continue
            if HEAD.match(line) or HEAD_BARE.match(line):
                break
            # Title lines in this edition are alphabetic prose. Stop at
            # Sanskrit plates / symbol lines once a title is collected.
            if parts and (is_mostly_garbage(line) or not re.search(r"[A-Za-z]{2,}", line)):
                break
            parts.append(line)
            joined = " ".join(parts)
            # All printed titles in this edition are short; avoid eating
            # the first verse block if OCR has removed a blank line.
            if len(joined.split()) >= 9:
                break

        title = normalize_mojibake(clean_block(" ".join(parts)))
        title = title.replace("Kuruksetra", "Kurukṣetra").strip(" .")
        if title:
            titles[chapter_num] = title
    return titles


def _chapter_summaries(doc: pymupdf.Document) -> list[Verse]:
    """Chapter-summary prose (printed near each chapter's end) as summary
    records, so broad questions ('what is chapter 2 about?') can be answered."""
    out: list[Verse] = []
    titles = _chapter_titles(doc)
    for ch_i, start in enumerate(CHAP_START_PAGES, start=1):
        end = CHAP_START_PAGES[ch_i] if ch_i < 18 else 905
        buf: list[str] = []
        capturing = False
        first_page = 0
        for idx in range(start - 1, end - 1):
            t = doc[idx].get_text()
            t = t.replace("\u00ad", "")
            if not capturing:
                if re.search(r"(?mi)^\s*CHAPTER SUMMARY\s*$", t):
                    capturing = True
                    first_page = idx + 1
                    t = re.sub(r"(?mi)^\s*CHAPTER SUMMARY\s*$", "", t, count=1)
                else:
                    continue
            # stop at the next verse heading / chapter title page noise
            m = HEAD.search(t)
            if m and capturing and buf:
                t = t[: m.start()]
            buf.append(t)
        pros = normalize_mojibake(clean_block(" ".join(buf)))
        if len(pros) < 200 or first_page == 0:
            continue
        title = titles.get(ch_i, "")
        out.append(Verse(
            id=f"BG-{ch_i}.summary",
            book="Bhagavad Gita",
            chapter=ch_i,
            verse=None,
            ref=f"Bhagavad-gita chapter {ch_i}: {title} — chapter summary",
            chapter_title=title,
            translation=pros,
            pdf_page=first_page,
            quality="summary",
        ))
    return out


def extract() -> list[Verse]:
    doc = pymupdf.open(PDF_PATH)
    titles = _chapter_titles(doc)
    verses: list[Verse] = []
    seen: set[str] = set()

    # Concatenate body pages 60..904 with page tracking.
    page_start: list[int] = []
    parts: list[str] = []
    for idx in range(59, 904):
        page_start.append(sum(len(p) for p in parts))
        parts.append(doc[idx].get_text())
    blob = "".join(parts)
    FIRST = 60  # PDF page of page_start[0]

    def page_of(pos: int) -> int:
        lo, hi = 0, len(page_start) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if page_start[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return FIRST + lo

    def chapter_of(pos: int) -> int:
        ch = 1
        for i, sp in enumerate(CHAP_START_PAGES):
            if page_of(pos) >= sp:
                ch = i + 1
        return ch

    matches = list(HEAD.finditer(blob)) + list(HEAD_BARE.finditer(blob))
    matches.sort(key=lambda m: m.start())

    # BG 1.1 special: no 'TEXT 1' heading; the chapter's first block starts
    # at the first TRANSLATION marker.
    first_head = matches[0].start() if matches else len(blob)
    open_block = BLOCK.search(blob, 0, first_head)
    synthetic = ""
    if open_block:
        synthetic = blob[open_block.start():first_head]

    def make_record(chap: int, num: int, body: str, pos: int, shared: str = "") -> Verse:
        marks = [(m.start(), m.group(1), m.end()) for m in BLOCK.finditer(body)]
        blocks: dict[str, str] = {}
        for k, (mpos, name, mend) in enumerate(marks):
            e = marks[k + 1][0] if k + 1 < len(marks) else len(body)
            chunk = body[mend:e]
            # cut off any leaked verse-head text of the next block
            chunk = HEAD.split(chunk)[0]
            kind = _norm_block(name)
            if kind == "translation":
                # quotable text: full furniture/marker hygiene
                clean = clean_translation(chunk)
                clean = INLINE_MARK.sub("", clean)
                # a trailing chunk may swallow the NEXT page-top furniture
                clean = re.sub(r"\s*(Text\s+\d+\s*[\]\)].*)$", "", clean)
            else:
                clean = normalize_mojibake(clean_block(chunk))
            blocks[kind] = clean
        pre = body[: marks[0][0]] if marks else body
        if not blocks.get("translation"):
                # Some verses' TRANSLATION heading is garbled beyond the fuzzy
            # pattern or missing entirely, leaving the translation prose
            # unheaded just before PURPORT (or, like BG 10.35/10.34, with no
            # heading at all: the prose sits after the synonyms). Recover it:
            # the synonyms end with the last word-gloss (separator ';' or
            # '—'), so take the prose after that last gloss. Reject candidates
            # that are really the NEXT verse's synonyms.
            cut = max(pre.rfind(";"), pre.rfind("—"))
            if cut >= 0:
                tail = pre[cut + 1:]
                tail_lines = [RUNHEAD_LINE.sub("", ln) for ln in tail.splitlines()]
                tail = clean_translation("\n".join(tail_lines))
                # drop a dangling final gloss ('... prati§thitii-fixed up.'
                # is the synonyms' own last line: word-gloss, no sentence).
                tail = re.sub(r"^\S{1,30}-[^.;]{0,45}\.\s+", "", tail, count=1)
                tail = tail.strip()
                if len(tail) >= 40 and ":" not in tail:
                    # re-run the cleaner: the gloss strip above can move a
                    # fused marker ('1RANSLATION Foods...') to position 0
                    blocks["translation"] = clean_translation(tail)
        sanskrit_lines, trans_lines = [], []
        for ln in pre.splitlines():
            s = RUNHEAD_LINE.sub("", ln).strip()
            if not s or re.fullmatch(r"\d+", s) or "Bhagavad-gita As It Is" in s:
                continue
            if is_mostly_garbage(s):
                sanskrit_lines.append(s)
            elif re.search(r"[a-z]{2,}", s) and "—" not in s and "-" in s or ";" in s:
                continue  # synonyms line noise pre-split; handled below
            else:
                trans_lines.append(s)
        # synonyms: everything after the transliteration's blank-ish split is
        # unreliable in the ClearScan layer; keep the tail of the pre-block.
        syn = ""
        if ";" in pre or "—" in pre:
            syn = normalize_mojibake(clean_block(pre.split("\n\n")[-1]))[:2000]
        ref = f"Bhagavad-gita {chap}.{num}"
        title = titles.get(chap, "")
        if title:
            ref += f" ({title})"
        if shared:
            ref += f" — {shared}"
        return Verse(
            id=f"BG-{chap}.{num}",
            book="Bhagavad Gita",
            chapter=chap,
            verse=num,
            ref=ref,
            chapter_title=title,
            sanskrit=normalize_mojibake(clean_field(" ".join(sanskrit_lines))),
            transliteration=normalize_mojibake(clean_field(" ".join(trans_lines))),
            synonyms=syn,
            translation=blocks.get("translation", ""),
            purport=blocks.get("purport", ""),
            pdf_page=page_of(pos),
            quality="good" if blocks.get("translation") else "partial",
        )

    for i, m in enumerate(matches):
        chap = chapter_of(m.start())
        nums = _parse_numbers(m.group(1)) if m.re is HEAD and m.groups() else []
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(blob)
        body = blob[start:end]
        # A head whose body holds more TRANSLATION blocks than its numbers
        # declare means following verses were set without repeated heads
        # (scan proved 20 such bodies). Extend the run so each embedded
        # translation becomes its own record. For a bare 'TEXTS' head the
        # first verse number is lost in the layer: it directly follows the
        # highest verse already seen in this chapter, and the body holds
        # exactly one verse per TRANSLATION marker (BG 10.8-9, 12.8,
        # 15.8-9, 16.8 — plate evidence from PDF pp. 542/644/743/787).
        n_trans = sum(1 for mm in BLOCK.finditer(body) if _norm_block(mm.group(1)) == "translation")
        if not nums and n_trans == 0:
            continue  # unnumbered fragment with no translation (furniture)
        if not nums:
            prev = max((v.verse for v in verses if v.chapter == chap and v.verse), default=0)
            nums = list(range(prev + 1, prev + 1 + n_trans))
        elif n_trans > len(nums):
            # Extension is only safe when the declared head does NOT itself
            # already cover the unheaded verse sitting inside its purport
            # (BG ch.10: verses 34 AND 35 both lack headings; extending
            # 33->34 would steal 35). Ch.10 guard: the extra translation
            # belongs to the NEXT unparsed verse only when the head verse
            # is not itself known-unheaded. Verified unheaded set: BG 10.33
            # has a clean TRANSLATION heading (p569), so extension is safe
            # there; the generic rule stays, ch.10 is handled by donor
            # reassignment below.
            nxt = nums[-1] + 1
            nums = nums + list(range(nxt, nxt + (n_trans - len(nums))))
        # Split a multi-translation body into per-verse pieces: piece k ends
        # where verse k+1's verse-plate begins. The plate starts at the blank
        # line that follows the donor's purport and precedes the next
        # verse's transliteration/synonyms, located just before the next
        # TRANSLATION marker; approximate via the last double-newline before
        # that marker but after the donor's own purport marker.
        # Combined ranges share ONE translation in the book itself, so every
        # member gets the full shared body, honestly annotated by `shared`.
        shared = f"shared text for verses {nums[0]}–{nums[-1]}" if len(nums) > 1 and n_trans <= 1 else ""
        if n_trans > 1:
            shared = ""
        sh_start = 0
        for num in nums:
            if n_trans <= 1:
                piece, s_pos = body, m.start()
            else:
                # Pick THIS verse's own translation block plus its
                # immediately following purport, straight from the whole
                # body (no fragile physical re-splitting: translating k-th
                # verse = k-th TRANSLATION block in reading order).
                tmarks = [mm for mm in BLOCK.finditer(body)
                          if _norm_block(mm.group(1)) == "translation"]
                k = nums.index(num)
                tm = tmarks[k] if k < len(tmarks) else None
                if tm is None:
                    piece, s_pos = "", m.start()
                else:
                    end_k = tmarks[k + 1].start() if k + 1 < len(tmarks) else len(body)
                    s_pos = m.start() + tm.start()
                    piece = body[max(0, tm.start() - 4000):end_k]
            vid = f"BG-{chap}.{num}"
            if vid in seen:
                # Headerless re-mention (plate/runhead duplicate): fold its
                # body into the existing record when ours is still empty, so
                # adjacent split pieces of one verse recombine.
                idx = next((j for j, v in enumerate(verses) if v.id == vid), None)
                if idx is not None and not verses[idx].translation:
                    merged = make_record(chap, num, piece, s_pos, shared)
                    if merged.translation:
                        verses[idx] = verses[idx].model_copy(update={
                            "translation": merged.translation,
                            "transliteration": verses[idx].transliteration or merged.transliteration,
                            "synonyms": verses[idx].synonyms or merged.synonyms,
                            "purport": verses[idx].purport or merged.purport,
                            "quality": "good",
                        })
                continue
            seen.add(vid)
            verses.append(make_record(chap, num, piece, m.start(), shared))

    if synthetic:
        verses.insert(0, make_record(1, 1, "TRANSLATION\n" + synthetic, 0))
    verses.sort(key=lambda v: (v.chapter, v.verse or 0))
    verses = _postprocess(doc, verses)
    verses.sort(key=lambda v: (v.chapter, v.verse or 0))
    doc.close()
    return verses


_T35_PLATE = re.compile(r"brhat-sāma|brhat-siima", re.IGNORECASE)
_T35_TEXT = (
    "Of hymns I am the Brhat-sama sung to the Lord Indra, and of poetry I am "
    "the Gayatri verse, sung daily by brahmanas. Of months I am November and "
    "December, and of seasons I am flower-bearing spring."
)


def _page_text(doc: pymupdf.Document, page1: int) -> str:
    return doc[page1 - 1].get_text()


def _cut_prose(txt: str, start: int, stops: tuple[str, ...]) -> str:
    """Prose from ``start`` to the first stop marker (or page end)."""
    end = len(txt)
    for s in stops:
        i = txt.find(s, start)
        if 0 <= i < end:
            end = i
    return txt[start:end]


def _postprocess(doc: pymupdf.Document, verses: list[Verse]) -> list[Verse]:
    """PDF-proven repairs for verses the ClearScan layer sets without a
    usable heading. Every rule below is backed by a raw page dump; nothing
    is copied from another edition.

    * BG 10.35 — no TEXT head in the layer (PDF p.571): verse plate,
      synonyms, translation and purport sit unheaded between BG 10.34's
      purport and TEXT 36. Read straight from the page.
    * BG 12.5 — BG 12.3-4 share ONE translation (PDF p.638); the second
      translation block on p.639 is 12.5's own, but landed on the 12.4
      record. Reassign: 12.4 takes the shared text + annotation.
    * BG 13.7 — head prints '1EXTS 6-7' (PDF p.665); handled by HEAD, but
      if 13.7 is still absent, 13.6-13.7 share one translation: clone.
    * BG 13.1/13.2 — this edition prints both verses under one combined
      block (see probe18 dump): 13.1 asks the question, 13.2 answers it.
      Split the merged translation at the answer boundary.
    * BG 1.46 — translation glued with page furniture (PDF p.99); clean
      via rebuild from the page's TRANSLATION block.
    """
    by_id = {v.id: v for v in verses}

    # --- BG 10.35 ---
    if "BG-10.35" not in by_id:
        t571 = _page_text(doc, 571)
        m_trans = re.search(r"Of hymns I am the Brhat", t571)
        if m_trans:
            t35 = clean_translation(_cut_prose(t571, m_trans.start(), ("PURPORT",)))
            p_end = _cut_prose(t571, t571.find("PURPORT", m_trans.start()) + 7, ("TEXT 36",))
            t_end = _cut_prose(_page_text(doc, 572), 0, ("TEXT 36",))
            purport = clean_translation(strip_page_furniture(p_end)) + " " + clean_translation(strip_page_furniture(t_end))
            plate_start = t571.find("brhat-s")
            synonyms = clean_translation(t571[plate_start:m_trans.start()]) if plate_start >= 0 else ""
            v35 = Verse(
                id="BG-10.35", book="Bhagavad Gita", chapter=10, verse=35,
                ref="Bhagavad-gita 10.35 (The Opulence of the Absolute)",
                chapter_title=by_id.get("BG-10.34").chapter_title if by_id.get("BG-10.34") else "",
                transliteration="", synonyms=synonyms, translation=t35,
                purport=purport, pdf_page=571, quality="good",
            )
            verses.append(v35)
            by_id[v35.id] = v35

    # --- BG 12.5 / 12.4 shared-text repair ---
    v124, v125 = by_id.get("BG-12.4"), by_id.get("BG-12.5")
    if v124 is not None and v124.translation.startswith("For those whose minds are attached"):
        t639 = _page_text(doc, 639)
        m35 = re.search(r"For those whose minds are attached", t639)
        if m35:
            t125 = clean_translation(_cut_prose(t639, m35.start(), ("\n##########",)))
            t640 = _page_text(doc, 640)
            mp = t640.find("PURPORT")
            p125 = clean_translation(strip_page_furniture(t640[mp + 7:])) if mp >= 0 else ""
            i124 = verses.index(v124)
            shared35 = by_id["BG-12.3"].translation if "BG-12.3" in by_id else v124.translation
            verses[i124] = v124.model_copy(update={
                "translation": shared35,
                "ref": "Bhagavad-gita 12.4 (Devotional Service) — shared text for verses 3–4",
                "quality": "good",
            })
            if v125 is None:
                v125 = Verse(
                    id="BG-12.5", book="Bhagavad Gita", chapter=12, verse=5,
                    ref="Bhagavad-gita 12.5 (Devotional Service)",
                    chapter_title=v124.chapter_title, transliteration="",
                    synonyms="", translation=t125, purport=p125,
                    pdf_page=639, quality="good",
                )
                verses.append(v125)
                by_id[v125.id] = v125

    # --- BG 13.7 shared clone ---
    if "BG-13.7" not in by_id and "BG-13.6" in by_id:
        src = by_id["BG-13.6"]
        v137 = src.model_copy(update={
            "id": "BG-13.7", "verse": 7,
            "ref": "Bhagavad-gita 13.7 (Nature, the Enjoyer, and Consciousness) — shared text for verses 6–7",
        })
        verses.append(v137)
        by_id[v137.id] = v137

    # --- BG 13.1/13.2 split ---
    # The main loop already emits both records (the combined head extends
    # to two numbers), but each received the FULL merged body. Shorten:
    # 13.1 = question only, 13.2 = the Lord's answer only.
    v131, v132 = by_id.get("BG-13.1"), by_id.get("BG-13.2")
    if (v131 is not None and v132 is not None
            and "The Blessed Lord then said" in v131.translation
            and v132.translation.startswith("Arjuna said")):
        head, tail = v131.translation.split("The Blessed Lord then said:", 1)
        i131, i132 = verses.index(v131), verses.index(v132)
        verses[i131] = v131.model_copy(update={"translation": head.strip().rstrip(".") + "."})
        verses[i132] = v132.model_copy(update={
            "translation": "The Blessed Lord said: " + tail.strip(),
            "ref": "Bhagavad-gita 13.2 (Nature, the Enjoyer, and Consciousness)",
        })

    # --- BG 1.46 rebuild from PDF p.99 ---
    v146 = by_id.get("BG-1.46")
    if v146 is not None and not v146.translation.startswith("Sañjaya said"):
        t99 = _page_text(doc, 99)
        mt = re.search(r"Sañjaya said:|Safijaya said:", t99)
        if mt:
            t146 = clean_translation(_cut_prose(t99, mt.start(), ("PURPORT",)))
            mp = t99.find("PURPORT", mt.start())
            p146 = clean_translation(strip_page_furniture(t99[mp + 7:])) if mp >= 0 else v146.purport
            i146 = verses.index(v146)
            verses[i146] = v146.model_copy(update={
                "translation": t146, "purport": p146,
                "pdf_page": 99, "quality": "good",
            })
    return verses


def main() -> None:
    doc = pymupdf.open(PDF_PATH)
    summaries = _chapter_summaries(doc)
    doc.close()
    verses = extract()
    all_rows = sorted(verses + summaries, key=lambda v: (v.chapter, v.verse or 0))

    # sanity oracle: Index of Sanskrit Verses page count of entries
    doc = pymupdf.open(PDF_PATH)
    idx_text = "".join(doc[p].get_text() for p in range(934, 950))
    doc.close()
    index_like = len(re.findall(r"(?m)^\s*[a-zāī][^\n]{3,60}$", idx_text))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as fh:
        for v in all_rows:
            fh.write(json.dumps(v.model_dump(), ensure_ascii=False) + "\n")
    good = sum(1 for v in all_rows if v.quality == "good")
    print(f"Bhagavad-gita: {len(all_rows)} records ({good} good) -> {OUT_PATH}")
    by_chap: dict[int, int] = {}
    for v in all_rows:
        if v.verse is not None:
            by_chap[v.chapter] = by_chap.get(v.chapter, 0) + 1
    print("per-chapter verse counts:", dict(sorted(by_chap.items())))
    miss = [v.id for v in all_rows if v.verse is not None and not v.translation]
    print("missing translation:", len(miss), miss[:12])
    print(f"index-of-verses oracle rows (rough): {index_like}")


if __name__ == "__main__":
    main()
