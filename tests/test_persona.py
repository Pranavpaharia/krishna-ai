"""The single-persona contract: one voice (Krishna), three books, one grounding rule.

These tests pin the *shape* of the prompt, not its poetry. Exactly one voice exists, it
names all three books, and any other voice is rejected outright — so a config change
can never reintroduce a second speaker silently.
"""
from __future__ import annotations

import pytest

from krsna_ai import config
from krsna_ai.core import persona


def test_exactly_one_voice_exists() -> None:
    assert list(persona.VOICES) == ["krishna"]
    assert persona.VOICE == "krishna"


def test_voice_label_is_krishna() -> None:
    assert persona.VOICE_LABEL == "Krishna"
    assert persona.VOICE_LABELS == {"krishna": "Krishna"}


def test_the_single_system_prompt_is_the_only_prompt() -> None:
    assert persona.VOICES["krishna"] == persona.SYSTEM_PROMPT
    assert persona.KRISHNA_SYSTEM_PROMPT is persona.SYSTEM_PROMPT


def test_all_three_books_are_named_in_the_system_prompt() -> None:
    lowered = persona.SYSTEM_PROMPT.lower()
    for book in ("bhagavad-gita", "uddhava-gita", "ashtavakra"):
        assert book in lowered, f"{book!r} is not named in the system prompt"


def test_ashtavakra_is_attributed_to_ashtavakra_not_to_krishna() -> None:
    """The collapsed voice must still attribute Ashtavakra Gita quotes correctly."""
    assert "ashtavakra says" in persona.SYSTEM_PROMPT.lower()


def test_unknown_voice_is_rejected() -> None:
    with pytest.raises(ValueError):
        persona.build_messages("some question", "some context", voice="ashtavakra")


def test_context_and_question_reach_the_final_user_turn() -> None:
    msgs = persona.build_messages("What is steadiness?", "TEACHINGS…", history=[])
    assert msgs[0]["role"] == "system"
    assert msgs[-1]["role"] == "user"
    assert "What is steadiness?" in msgs[-1]["content"]
    assert "References:" in msgs[-1]["content"]


def test_history_is_included_and_capped_at_eight_turns() -> None:
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i}"}
               for i in range(12)]
    msgs = persona.build_messages("follow-up", "ctx", history=history)
    assert len(msgs) == 1 + 8 + 1
    assert msgs[1]["content"] == "turn 4"


def test_config_voice_matches_the_persona() -> None:
    assert config.VOICE == persona.VOICE
