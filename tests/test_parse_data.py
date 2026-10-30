"""Dataset integrity: both books fully extracted, references sane (Tasks 1-6)."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

GITA_COUNTS = {1: 46, 2: 72, 3: 43, 4: 42, 5: 29, 6: 47, 7: 30, 8: 28, 9: 34,
               10: 42, 11: 55, 12: 20, 13: 35, 14: 27, 15: 20, 16: 24, 17: 28, 18: 78}


def _load(name: str) -> list[dict]:
    return [json.loads(l) for l in (DATA / name).open(encoding="utf-8")]


def test_gita_complete() -> None:
    rows = _load("verses_gita.jsonl")
    assert len(rows) == 700
    counts = Counter(r["chapter"] for r in rows if r["verse"] is not None)
    assert dict(counts) == GITA_COUNTS
    assert all(r["translation"].strip() for r in rows)
    assert len({r["id"] for r in rows}) == 700


def test_gita_no_furniture_leaks() -> None:
    rows = _load("verses_gita.jsonl")
    for r in rows:
        t = r["translation"]
        assert "TION" not in t[:16], r["id"]
        assert "As It Is" not in t, r["id"]
        assert "[Ch." not in t, r["id"]


def test_gita_spot_checks() -> None:
    by_id = {r["id"]: r for r in _load("verses_gita.jsonl")}
    assert "elevate himself by his own mind" in by_id["BG-6.5"]["translation"]
    assert "Abandon all varieties of religion" in by_id["BG-18.66"]["translation"]
    assert "Of hymns I am the Brhat" in by_id["BG-10.35"]["translation"]
    assert by_id["BG-10.35"]["pdf_page"] == 571


def test_gita_chapter_titles_populated() -> None:
    rows = _load("verses_gita.jsonl")
    titles = {r["chapter"]: r["chapter_title"] for r in rows}
    assert len(titles) == 18
    assert all(titles.values())
    assert titles[2] == "Contents of the Gita Summarized"
    assert titles[12] == "Devotional Service"


def test_uddhava_complete() -> None:
    rows = _load("verses_uddhava.jsonl")
    verses = [r for r in rows if r["verse"] is not None]
    assert len(verses) == 1040
    assert all(v["translation"].strip() for v in verses)
    assert len({r["id"] for r in rows}) == len(rows)


def test_merged_store_aligned() -> None:
    rows = _load("verses.jsonl")
    assert len(rows) == 2062
    import numpy as np

    z = np.load(DATA / "index.npz")
    assert [str(x) for x in z["ids"]] == [r["id"] for r in rows]
    assert z["embeddings"].shape == (2062, 2048)
