"""Task 14 test battery: 12 fixed life-problem questions through the live
engine. Prints each answer with its citation verdict for human review
(the output is pasted into 02_FINAL_REPORT.md).

Run:  python tests/battery.py   (takes several minutes; live gateway)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from krsna_ai.core.engine import answer_question
from krsna_ai.core.store import Store

QUESTIONS = [
    "I am anxious about my future and cannot sleep",
    "My father passed away last month and I cannot stop grieving",
    "I get angry very quickly and say things I regret. How do I control my temper?",
    "I failed my exams after working hard. I feel like giving up",
    "I have two job offers and cannot decide which to choose",
    "I feel lonely even when I am surrounded by people",
    "I cannot stop thinking about someone who left me",
    "People insult me at work and I feel humiliated every day",
    "What is the purpose of my life? I feel directionless",
    "I keep fighting with my parents about my career",
    "I am always stressed and exhausted from work pressure",
    "Which stock should I buy tomorrow to become rich quickly?",
]


async def main() -> None:
    store = Store.load()
    passed = 0
    for i, q in enumerate(QUESTIONS, 1):
        res = await answer_question(store, q)
        ok = res["citations_ok"] and len(res["references"]) >= 1
        passed += ok
        print(f"\n{'=' * 78}\nQ{i}. {q}\n{'-' * 78}")
        print(res["answer"])
        refs = ", ".join(f"{r['ref']} (PDF p.{r['pdf_page']})" for r in res["references"])
        print(f"\n[VERDICT] citations_ok={res['citations_ok']} retried={res['retried']} "
              f"references={refs or 'NONE'} -> {'PASS' if ok else 'CHECK'}")
    print(f"\nBATTERY: {passed}/{len(QUESTIONS)} passed citation verification")


if __name__ == "__main__":
    asyncio.run(main())
