"""Pydantic schema for one ingested verse / chapter-summary record.

A single ``Verse`` is the atomic unit of the verse store. Every record keeps
enough provenance to re-open the exact source page, so citations shown to a
user can always be verified against the PDF they came from.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Verse(BaseModel):
    """One verse (or chapter-level summary) from one of the source books."""

    id: str = Field(description="Stable unique id, e.g. 'BG-2.47' or 'SB-11.8.15'")
    book: str = Field(description="'Bhagavad Gita' or 'Uddhava-gita'")
    chapter: int = Field(description="Chapter number within the book's own numbering")
    verse: int | None = Field(
        default=None, description="Verse number within the chapter; None for summaries"
    )
    ref: str = Field(
        description="Canonical citation, e.g. 'Bhagavad-gita 2.47' or "
        "'Srimad-Bhagavatam 11.8.15 (Uddhava-gita, Story of Pingala)'"
    )
    chapter_title: str = Field(default="", description="Chapter heading from the book")
    sanskrit: str = Field(default="", description="Devanagari verse text (best effort)")
    transliteration: str = Field(default="", description="Roman transliteration (best effort)")
    synonyms: str = Field(default="", description="Word-for-word meanings, if present")
    translation: str = Field(default="", description="English translation — the quotable text")
    purport: str = Field(default="", description="Commentary / purport text, may be empty")
    pdf_page: int = Field(description="1-based PDF page where the record's head appears")
    quality: str = Field(
        default="good",
        description="'good' | 'partial' (some blocks missing) | 'summary' (chapter-level record)",
    )
