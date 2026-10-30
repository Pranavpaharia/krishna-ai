"""Citation checker: real refs + verbatim quotes pass; inventions fail.

The checker is scoped to the passages actually retrieved — a quote that matches some other
record in the corpus is still a grounding violation, so it is reported as ``off_scope``.
"""
from krsna_ai.core import citations
from krsna_ai.core.store import Store

_store: Store | None = None


def store() -> Store:
    global _store
    if _store is None:
        _store = Store.load()
    return _store


def test_verbatim_quote_passes() -> None:
    rec = store().get("BG-6.5")
    ans = f'Krishna says: "{rec["translation"]}" (Bhagavad-gita 6.5)\n\nReferences: [BG-6.5]'
    rep = citations.check(ans, store(), retrieved=["BG-6.5"])
    assert rep["ok"] and rep["unknown_ids"] == [] and rep["bad_quotes"] == []
    assert rep["quotes"][0]["verse_id"] == "BG-6.5"


def test_invented_reference_fails() -> None:
    ans = 'As I said: "Do your duty and be at peace always." (Bhagavad-gita 99.99)\n\nReferences: [BG-99.99]'
    rep = citations.check(ans, store(), retrieved=["BG-6.5"])
    assert not rep["ok"] and "BG-99.99" in rep["unknown_ids"]


def test_fabricated_quote_fails() -> None:
    ans = ('"The moon is made of green cheese and so is thy sorrow, Arjuna, '
           'therefore eat cake and be merry." (Bhagavad-gita 6.5)\n\nReferences: [BG-6.5]')
    rep = citations.check(ans, store(), retrieved=["BG-6.5"])
    assert not rep["ok"] and rep["bad_quotes"]


def test_quote_from_another_verse_is_off_scope() -> None:
    """A real verse that was never retrieved cannot be presented as the answer's source."""
    other = store().get("BG-2.20")
    ans = (f'Krishna says: "{other["translation"]}" (Bhagavad-gita 2.20)\n\n'
           "References: [BG-2.20]")
    rep = citations.check(ans, store(), retrieved=["BG-6.5"])
    assert not rep["ok"]
    assert rep["off_scope"] and rep["off_scope"][0]["verse_id"] == "BG-2.20"
    assert rep["bad_quotes"] == []          # the quote is real, just not from the given passage
    assert rep["quotes"][0]["verse_id"] == "BG-2.20"


def test_missing_references_line_fails() -> None:
    rec = store().get("BG-6.5")
    ans = f'Krishna says: "{rec["translation"]}" (Bhagavad-gita 6.5)'
    rep = citations.check(ans, store(), retrieved=["BG-6.5"])
    assert not rep["ok"] and rep["missing_refs"]


def test_enforce_strips_unknown_ids_and_reports_removal() -> None:
    ans = "Text about the field of activity. (Bhagavad-gita 99.99)\n\nReferences: [BG-99.99, BG-6.5]"
    rep = citations.check(ans, store(), retrieved=["BG-6.5"])
    result = citations.enforce(ans, rep, store())
    assert "BG-99.99" not in result["answer"]
    assert "BG-6.5" in result["answer"]
    assert result["removed"]["unknown_ids"] == ["BG-99.99"]
    assert result["removed"]["bad_quotes"] == []


def test_enforce_strips_unverifiable_quote() -> None:
    ans = ('Krishna says: "Be merry and eat cake, Arjuna, for the moon is green." '
           "(Bhagavad-gita 6.5)\n\nReferences: [BG-6.5]")
    rep = citations.check(ans, store(), retrieved=["BG-6.5"])
    result = citations.enforce(ans, rep, store())
    assert "green cheese" not in result["answer"] and "eat cake" not in result["answer"]
    assert result["removed"]["bad_quotes"]
    assert "BG-6.5" in result["answer"]


def test_short_spans_are_paraphrase_not_quotes() -> None:
    """Below the 12-char threshold a span is conversational, not scripture: it is not checked."""
    short = 'He says "the mind" (Bhagavad-gita 6.5)\n\nReferences: [BG-6.5]'
    rep = citations.check(short, store(), retrieved=["BG-6.5"])
    assert rep["quotes"] == [] and rep["bad_quotes"] == [] and rep["ok"]

    rec = store().get("BG-6.5")
    span = rec["translation"].strip()[:40]
    assert len(span) >= 12
    long = f'"{span}" (Bhagavad-gita 6.5)\n\nReferences: [BG-6.5]'
    rep2 = citations.check(long, store(), retrieved=["BG-6.5"])
    assert rep2["ok"] and rep2["quotes"][0]["verse_id"] == "BG-6.5"
