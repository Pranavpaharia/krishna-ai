"""Prompt-size breakdown: what we actually send per question, and what it costs
to drop the purport excerpts from the context."""
import statistics
import tiktoken

from krsna_ai.core import persona, retriever
from krsna_ai.core.store import Store

QS = [
    "I am always anxious about my future and cannot sleep at night",
    "I am a student and I overthink what others think of me; the anxiety is worst at night",
    "How do I stop procrastinating and stay disciplined?",
    "My mind will not stop racing at night and I feel like a failure as a student",
    "Tell me a short proverb about patience.",
    "What should I do when I am angry at my parents?",
    "I feel lonely even when I am with people. What does Krishna say about this?",
    "How can I focus during study without getting distracted by my phone?",
    "I am afraid of failing my exams. How do I handle the fear?",
    "Give me one verse about gratitude.",
]

enc = tiktoken.encoding_for_model("gpt-4")
store = Store.load()
cur, trim, qtok = [], [], []

for q in QS:
    passages = retriever.retrieve(store, q)
    msgs = persona.build_messages(q, retriever.format_context(passages))
    cur.append(len(enc.encode(msgs[0]["content"])) + len(enc.encode(msgs[-1]["content"])))

    short = "\n".join(
        f"[{p['id']}] {p['ref']} (PDF p. {p['pdf_page']})\nTranslation: {p['translation']}\n"
        for p in passages
    ).strip()
    m2 = persona.build_messages(q, short)
    trim.append(len(enc.encode(m2[0]["content"])) + len(enc.encode(m2[-1]["content"])))
    qtok.append(len(enc.encode(q)))

avg = lambda xs: round(statistics.mean(xs), 1)
print(f"current prompt (system + context)   avg tokens = {avg(cur)}")
print(f"translation-only context variant    avg tokens = {avg(trim)}")
print(f"question text alone                 avg tokens = {avg(qtok)}")
print(f"question share of prompt            {avg(qtok) / avg(cur) * 100:.1f}%")
