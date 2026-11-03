"""Retrieval smoke tests: known questions surface their canonical verses."""
from krsna_ai.core import retriever
from krsna_ai.core.store import Store

_store: Store | None = None


def store() -> Store:
    global _store
    if _store is None:
        _store = Store.load()
    return _store


def test_anger_surfaces_bg_262() -> None:
    hits = retriever.retrieve(store(), "I get angry very quickly, how do I control my temper?")
    ids = [h["id"] for h in hits]
    assert "BG-2.62" in ids and "BG-2.63" in ids


def test_attachment_surfaces_pingala() -> None:
    hits = retriever.retrieve(store(), "How do I stop being attached to someone who left me?")
    ids = [h["id"] for h in hits]
    assert any(i.startswith("SB-11.8.") for i in ids)


def test_grief_surfaces_bg_220() -> None:
    hits = retriever.retrieve(store(), "My mother passed away and I cannot stop grieving")
    assert "BG-2.20" in [h["id"] for h in hits]


def test_every_hit_is_a_real_record() -> None:
    hits = retriever.retrieve(store(), "What is the purpose of my life?")
    assert hits and all(store().get(h["id"]) is not None for h in hits)


def test_ashtavakra_surfaces_on_its_own_theme() -> None:
    """The third book must reach the prompt, not just exist in the store."""
    hits = retriever.retrieve(store(), "How is one to attain liberation and dispassion?")
    ids = [h["id"] for h in hits]
    assert "AG-1.1" in ids and "AG-18.71" in ids
