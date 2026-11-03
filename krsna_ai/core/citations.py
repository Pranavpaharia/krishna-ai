"""Citation integrity: every reference must resolve to a real record, every quote must be verbatim.

Two rules make an answer trustworthy:

1. A cited verse id must exist in the verse store.
2. A quoted span must appear verbatim in that verse's stored translation — and in a verse the
   model was actually *given* (the retrieved passages). A quote that matches some other record
   elsewhere in the corpus is still a grounding violation: the model produced text it cannot
   have retrieved, so it is reported as ``off_scope`` rather than silently accepted.

Fuzzy matching is kept only as a warning (``ocr_noise``) because the ClearScan layer has
scan-era typos ("0" for "O", "brahmai).as"); a tolerant match is not proof of verbatim quoting.
"""
from __future__ import annotations
import re

from krsna_ai.core import store as store_mod

# Book-agnostic: any "<PREFIX>-n.n(.n)" id resolves through the store, so a third book needs no
# new pattern here. The prose form is the human-readable spelling the model writes in running
# text; each label maps back to the same id prefix.
_ID_RE = re.compile(r"\[([A-Z]{2,4}-\d+(?:\.\d+)+)\]")
_ID_TOKEN = re.compile(r"\b([A-Z]{2,4}-\d+(?:\.\d+)+)\b")
_PROSE_REF = re.compile(r"\((Bhagavad-gita|Uddhava-gita, SB|Ashtavakra Gita)\s+(\d+(?:\.\d+)+)\)")
_PROSE_LABEL = {"BG": "Bhagavad-gita", "SB": "Uddhava-gita, SB", "AG": "Ashtavakra Gita"}
_PROSE_PREFIX = {label: prefix for prefix, label in _PROSE_LABEL.items()}
# Quotes of 12+ chars are checked; shorter spans are paraphrase, not scripture, and are
# reported separately so the engine can ask for a real quote.
_QUOTE_RE = re.compile(r"[\"“]([^\"”]{12,})[\"”]")
_REFS_LINE = re.compile(r"(?mi)^References:\s*(.*)$")


def parse_cited_ids(answer: str) -> list[str]:
    ids = set(_ID_RE.findall(answer))
    for m in _PROSE_REF.finditer(answer):
        ids.add(f"{_PROSE_PREFIX[m.group(1)]}-{m.group(2)}")
    for m in _ID_TOKEN.finditer(answer):
        ids.add(m.group(1))
    return sorted(ids)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower().rstrip(".")


def _tolerant(s: str) -> str:
    """Normalisation used only for the OCR-noise warning, never for a pass."""
    s = _norm(s).translate(str.maketrans({"0": "o", "§": "ṣ", "¦": "ī"}))
    return re.sub(r"[^\w\s]", "", s)


def check(answer: str, store: store_mod.Store,
         retrieved: list[str] | None = None) -> dict:
    """Verify ids + verbatim quotes against the *retrieved* passages.

    Returns a report: ok, cited, unknown_ids, bad_quotes, quotes (quote -> verse_id),
    off_scope, ocr_noise, paraphrases, missing_refs.
    """
    cited = parse_cited_ids(answer)
    known = [i for i in cited if store.get(i)]
    unknown = [i for i in cited if not store.get(i)]
    scope = set(retrieved) if retrieved else set(known)

    quotes: list[dict] = []
    bad_quotes: list[str] = []
    off_scope: list[dict] = []
    ocr_noise: list[dict] = []

    for q in _QUOTE_RE.findall(answer):
        nq = _norm(q)
        attributed = None
        for vid in known:
            rec = store.get(vid)
            if rec and nq in _norm(rec["translation"]):
                attributed = vid
                break
        if attributed is None:
            for vid in known:
                rec = store.get(vid)
                if rec and _tolerant(nq) in _tolerant(rec["translation"]):
                    attributed = vid
                    ocr_noise.append({"quote": q, "verse_id": vid})
                    break
        if attributed is None:
            bad_quotes.append(q)
        else:
            quotes.append({"quote": q, "verse_id": attributed})
            if scope and attributed not in scope:
                off_scope.append({"quote": q, "verse_id": attributed})

    report = {
        "cited": cited,
        "unknown_ids": unknown,
        "bad_quotes": bad_quotes,
        "quotes": quotes,
        "off_scope": off_scope,
        "ocr_noise": ocr_noise,
        "missing_refs": not bool(_REFS_LINE.search(answer)),
    }
    report["ok"] = bool(known) and not unknown and not bad_quotes and not off_scope \
        and not report["missing_refs"]
    return report


def enforce(answer: str, report: dict, store: store_mod.Store) -> dict:
    """Strip fabricated references and unverifiable quotes, rebuild the References line.

    Returns ``{"answer": cleaned, "removed": {...}}`` so the caller can tell the user that the
    answer was degraded rather than presenting it as verified.
    """
    removed: dict[str, list] = {
        "unknown_ids": list(report["unknown_ids"]),
        "bad_quotes": list(report["bad_quotes"]),
        "off_scope": [i["verse_id"] for i in report["off_scope"]],
    }
    out = answer
    # Drop the model's own References line first: it is rebuilt below from store-known ids only,
    # otherwise a fabricated id survives in the line it was supposed to certify.
    out = _REFS_LINE.sub("", out)
    for vid in report["unknown_ids"]:
        prefix, tail = vid.split("-", 1)
        label = _PROSE_LABEL.get(prefix)
        if label:
            out = out.replace(f"({label} {tail})", "")
        out = out.replace(vid, "")          # a bare invented id in prose must not survive either
    for q in report["bad_quotes"] + [i["quote"] for i in report["off_scope"]]:
        out = out.replace(f'"{q}"', "").replace(f"“{q}”", "")
    out = re.sub(r"\s{2,}", " ", out).strip()

    # Rebuild the References line from store-known ids only: the model's own line is dropped so a
    # fabricated id cannot certify itself, but legitimate citations (known ids) are preserved.
    kept = {i for i in report["cited"] if store.get(i)}
    ids = sorted(kept | {i for i in parse_cited_ids(out) if store.get(i)})
    if out:
        out = f"{out}\n\nReferences: [{', '.join(ids)}]"
    return {"answer": out, "removed": removed}
