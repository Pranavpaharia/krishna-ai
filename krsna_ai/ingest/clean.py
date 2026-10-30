"""Shared text-cleanup helpers for the Krishna AI ingestion pipeline.

Both source books carry scanning/OCR artefacts:
* The Uddhava-gītā (born-digital) has proper IAST diacritics but hyphenates
  words across line breaks ("mes­sage") and has noisy whitespace.
* Bhagavad-gītā As It Is (ClearScan OCR) garbles the diacritic letters —
  "Kṛṣṇa" appears as ``Kr§pa``, ``Krqva``, ``Kf§!J.a`` etc. — while the plain
  English translations stay readable.  We normalise the known garble
  patterns so stored text is presentable, and we NEVER quote the garbled
  Sanskrit/transliteration verbatim at answer time (only the English
  Translation, which is clean, plus this normalised transliteration).
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Generic cleanup
# ---------------------------------------------------------------------------

def join_hyphenation(text: str) -> str:
    """Re-join words hyphenated at line breaks: ``mes-\nsage`` -> ``message``."""
    return re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)


def collapse_ws(text: str) -> str:
    """Collapse all whitespace runs (incl. newlines) into single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def clean_block(text: str) -> str:
    """Full cleanup for a stored prose block."""
    text = text.replace("\u00ad", "")  # soft hyphen (InDesign line-break artefact)
    return collapse_ws(join_hyphenation(text))


def clean_field(text: str) -> str:
    """Cleanup for verse text fields (Sanskrit/transliteration/translations):
    no hyphen re-joining, because IAST uses hyphens inside words
    (``tanu-bhṛtām``). Soft hyphens are removed."""
    return collapse_ws(text.replace("\u00ad", ""))


# ---------------------------------------------------------------------------
# ClearScan mojibake normalisation (Bhagavad-gītā As It Is)
#
# The 2013 ClearScan OCR mapped the book's IAST diacritic glyphs onto random
# ASCII/control characters.  The mappings below are derived from actual
# samples observed in the extraction (e.g. PDF p. 62-63, 111-112) and are
# deliberately conservative: they only fire on sequences that cannot occur
# in ordinary English prose.
# ---------------------------------------------------------------------------

# Whole-word fixes for the most common garbled spiritual vocabulary.
_WORD_FIXES: dict[str, str] = {
    "saiijaya": "Sañjaya",
    "safijaya": "Sañjaya",
    "dhftarli§tra": "Dhṛtarāṣṭra",
    "dhṛtarli§tra": "Dhṛtarāṣṭra",
    "kuruk§etra": "Kurukṣetra",
    "kurukwetra": "Kurukṣetra",
    "kum*etra": "Kurukṣetra",
}

# Character-level replacements for leftover diacritic garbage.
_CHAR_FIXES: list[tuple[str, str]] = [
    ("§", "ṣ"),          # ş-like glyph in Kṛṣṇa / Kurukṣetra samples
    ("¦", "ī"),
]

# Family-level regex fixes: the OCR mangles the same sacred names in dozens
# of variants (Kṛṣṇa -> Kr\x81!J.a / Kf§!J.a / Krąl).a ...). These patterns
# only fire on shapes that cannot be ordinary English words.
_FAMILY_FIXES: list[tuple[str, str]] = [
    (r"\bK[rf][^\sa]{1,5}a\b", "Kṛṣṇa"),
    (r"\bDh[^\s]{4,10}?tra\b", "Dhṛtarāṣṭra"),
    (r"\bSa[fr]?i?jaya\b|\bSanjaya\b", "Sañjaya"),
    (r"\bKuru[^\s]{1,6}?etra\b|\bKum\*etra\b", "Kurukṣetra"),
    (r"\bP[al][^\s]{2,9}?avas\b", "Pāṇḍavas"),
    (r"\bP[al][^\s]{2,9}?ava\b", "Pāṇḍava"),
    (r"\bPa[^\s]{2,4}u\b", "Pāṇḍu"),
    (r"\bgitii\b", "gītā"),
    (r"\bGitii\b", "Gītā"),
    (r"\bBhagavad-glta\b", "Bhagavad-gītā"),
    (r"\bmiihiitmya\b", "māhātmya"),
    (r"\bGitii-miihiitmya\b", "Gītā-māhātmya"),
]
_CLUSTER_FIXES: list[tuple[str, str]] = [
    ("Kf§!J.a", "Kṛṣṇa"),
    ("Kr§pa", "Kṛṣṇa"),
    ("Kr§!J.a", "Kṛṣṇa"),
    ("Krqva", "Kṛṣṇa"),
    ("Kr>pa", "Kṛṣṇa"),
    ("Kfl).a", "Kṛṣṇa"),
    ("KrtJa", "Kṛṣṇa"),
    ("KrtJa", "Kṛṣṇa"),
    ("Kr§!J,a", "Kṛṣṇa"),  # noqa: typo-tolerant variant observed in Preface
]

_GARBLE_CHARS = re.compile(r"[\x00-\x1f\x7f\x81-\x86\xad]")


def normalize_mojibake(text: str) -> str:
    """Best-effort repair of ClearScan garbling. Never invents content:
    unknown garbage characters are dropped, known ones mapped."""
    out = text
    for pat, good in _FAMILY_FIXES:
        out = re.sub(pat, good, out)
    for bad, good in _CLUSTER_FIXES:
        out = out.replace(bad, good)
    for bad, good in _WORD_FIXES.items():
        out = re.sub(rf"(?i)\b{re.escape(bad)}\b", good, out)
    for bad, good in _CHAR_FIXES:
        out = out.replace(bad, good)
    out = _GARBLE_CHARS.sub("", out)
    return out


# Page furniture that ClearScan leaves stranded inside verse blocks:
# running heads ('Text 35] The Opulence of the Absolute 531'), lone printed
# page numbers, and scrambled symbol lines left by the scanned Devanagari
# plates. These are stripped from quotable prose so stored translations read
# exactly as the book's English text. Conservative: patterns never match
# ordinary English sentences.
_RUNNING_HEAD = re.compile(r"Text\s+\d+\s*[\]\)]\s+[A-Z][A-Za-z ,'-]{2,60}?\s+\d{2,3}(?=\s|$)")
_BARE_RUNNING_HEAD = re.compile(r"Text\s+\d+\s*[\]\)]")
_CH_TAG = re.compile(r"\[Ch\.\s*\S+")
_BOOK_TITLE_LINE = re.compile(r"/?Bha\w*avad\s*-?\s*g'?\w+\s*\.?\s*·?\s*As It [I1]s\s*\.?")
_TRAILING_PAGENUM = re.compile(r"\s\d{3}$")
_LEADING_JUNK = re.compile(r"^[.…;·•:' ,’+*]{2,}\s*")


def strip_page_furniture(text: str) -> str:
    """Remove running heads, page numbers and junk plate lines from prose.

    Operates line-wise BEFORE whitespace collapse, because running heads
    are whole-line furniture in the raw text layer; the glued forms left
    after collapsing are handled by ``clean_translation``.
    """
    kept = []
    for ln in text.splitlines():
        s = ln.strip()
        if _BARE_RUNNING_HEAD.fullmatch(s) or _BOOK_TITLE_LINE.fullmatch(s):
            continue
        if re.fullmatch(r"\d{2,3}", s) or _CH_TAG.fullmatch(s):
            continue
        kept.append(ln)
    return "\n".join(kept)


# Marker leaks fused to the following paragraph ('TRANSLATIO0The seven...',
# '1RANSLATIONFoods...', 'TRANSLATION, Those...'): the garbled heading has NO
# trailing space. Anchor on the 'TION' token + the first plausible English
# word start after it, requiring the text before TION to be heading-shaped.
_MARKER_LEAK = re.compile(r"^\s*\S{0,14}?TI[O0][N0]?[,.]?\s*(?=[A-Z](?:[a-z]{2,}|\s))")
# space-garbled heading variant: 'TRA NSLATION The...' (space injected)
_MARKER_LEAK_SP = re.compile(r"^\s*TR[A ]{0,2}NSL[A ]{0,1}TION[,.]?\s+")


def clean_translation(text: str) -> str:
    """Final hygiene for the storable English translation of one verse.

    Repairs hyphenation-collapsed artefacts left by the scan layer,
    strips running heads / printed page numbers glued into the prose,
    and drops non-text junk lines (scanned plate symbol soup)."""
    out = normalize_mojibake(strip_page_furniture(text))
    out = clean_block(out)
    out = _MARKER_LEAK_SP.sub("", out)  # 'TRA NSLATION The...' -> 'The...'
    out = _MARKER_LEAK.sub("", out)  # 'TRANSLATIO0The...' -> 'The...'
    out = _RUNNING_HEAD.sub(" ", out)
    out = _BARE_RUNNING_HEAD.sub(" ", out)
    out = _CH_TAG.sub(" ", out)
    out = _BOOK_TITLE_LINE.sub(" ", out)
    out = _TRAILING_PAGENUM.sub("", out)
    out = _LEADING_JUNK.sub("", out)
    # whole-line headings that share a line with the adjacent page's start
    out = re.sub(r"\s+(?:PURPORT|TRANS\S{0,9}TION)\s+", " ", out)
    out = re.sub(r"\s+TRANSLATION\s+", " ", out)
    # running heads glued MID-text at page turns ('... existences. 625
    # Bhagavad-gita As It Is [Ch. 13 ...'): page number + book title + tag
    out = re.sub(r"\s+\d{3}\s+Bha\w*avad-g\w+ As It Is\s*", " ", out)
    out = re.sub(r"\[Ch\.\s*\d+\]?\s*", "", out)
    # leading scanned-plate token soup (no-vowel tokens before real prose)
    toks = out.split(" ")
    drop = 0
    for tk in toks[:8]:
        core = tk.strip(".,;:()[]'’")
        if len(core) >= 2 and not re.search(r"[aeiouAEIOUāīūṛṣṭ]", core):
            drop += 1
        else:
            break
    if 0 < drop < len(toks):
        out = " ".join(toks[drop:])
    out = re.sub(r"^(Devotional Service|The Opulence of the Absolute|"
                 r"Nature, the Enjoyer, and Consciousness)\s+", "", out)
    # glued running-head title chains, e.g. '... patience. The Opulence of
    # the Absolute' trailing a completed translation sentence
    out = re.sub(r"\s+(The Opulence of the Absolute|Devotional Service|"
                 r"Nature, the Enjoyer, and Consciousness|"
                 r"The Three Modes of Material Nature|"
                 r"Observing the Armies on the Battlefield of Kurukṣetra)\s*$", "", out)
    out = re.sub(r"\s+\d{3}\s+Bha\w*avad-g\w+ As It Is\s*$", "", out)
    out = re.sub(r"\s+\S{1,4}\s+''\s*\(Ch\.\s*\d+\s*$", "", out)
    out = re.sub(r"\s+ie\s+''\s*$", "", out)
    out = re.sub(r"\s+\[Ch\.\s*\d+\s*$", "", out)
    # fused marker at a paragraph joint inside running prose: the synonyms
    # of the NEXT verse's plate can glue 'TRANSLATIO0' straight onto its
    # translation ('TRANSLATIO0The seven great sages...'). Only fires on
    # the exact TION-token + capitalised word shape, never on real words
    # (no English word contains 'TRANSLATIO').
    out = re.sub(r"\b\S{0,12}TI[O0][N0]?[,.]?(?=[A-Z][a-z]{2,}\s)", "", out)
    # symbol-soup plate lines that survive collapsing (no vowels, long)
    words = out.split(" ")
    cleaned = []
    for w in words:
        if len(w) > 14 and not re.search(r"[aeiouAEIOU]", w) and re.search(r"[.;:+•·']", w):
            continue  # scanned-plate symbol line, never English prose
        cleaned.append(w)
    out = " ".join(cleaned)
    return re.sub(r"\s+", " ", out).strip()



def is_mostly_garbage(text: str, threshold: float = 0.12) -> bool:
    """True when a line is Devanāgarī rendered as ClearScan junk (unusable)."""
    if not text:
        return True
    total = len(text)
    bad = sum(1 for c in text if ord(c) < 32 or 0x81 <= ord(c) <= 0x86 or c in "§¦\xad")
    letters = sum(1 for c in text if c.isalpha())
    return (bad / max(total, 1)) > threshold or letters < 3
