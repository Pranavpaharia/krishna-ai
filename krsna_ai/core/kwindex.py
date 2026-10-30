"""Shared keyword index (idf over the stored English text).

Kept in its own module so the store can own the index instance. Previously the retriever
cached it in a module-level dict keyed by ``id(store)``, which goes stale once a store is
garbage-collected and a new store reuses the same address.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

_STOP = set(
    "i me my am is are was the a an to of and or in on for with how do does can what why "
    "when who this that it its be been being have has had will would should could from by at "
    "as so if but not no yes you your yours he she they them then than too very just about "
    "into over after before".split()
)
_WORD = re.compile(r"[a-z']{2,}")

# Hinglish words users actually type, mapped to the English word the corpus uses.
# Kept deliberately small: one word in, one word out. Expanding a query into a whole
# theme's synonym set was tried and cut recall five-fold (see scratch/_tmp_eval_probe2.py).
_IAST: dict[str, str] = {
    "ā": "a", "ī": "i", "ū": "u", "ē": "e", "ō": "o", "ṛ": "ri", "ṣ": "sh", "ś": "sh",
    "ṇ": "n", "ñ": "ny", "ṭ": "t", "ḍ": "d", "ṅ": "ng",
}

_HINGLISH: dict[str, str] = {
    "gussa": "anger", "krodh": "anger",
    "dukh": "grief", "shok": "grief", "vedna": "grief",
    "bechaini": "anxiety", "chinta": "anxiety", "tension": "anxiety",
    "moh": "attachment", "asakti": "attachment",
    "ahankar": "pride", "irshya": "envy",
    "aalas": "laziness", "sust": "laziness",
    "apman": "insult", "apmaan": "insult",
    "sharm": "guilt", "pachtava": "guilt",
    "akelapan": "loneliness",
    "sankalp": "decision", "nirnay": "decision",
    "shraddha": "faith", "bhakti": "devotion",
    "bhay": "fear", "mrityu": "death",
    "neend": "sleep", "thak": "exhausted",
}


def _fold(text: str) -> str:
    """Normalise IAST to the ASCII a user actually types: kṛṣṇa -> krishna, gītā -> gita."""
    return "".join(_IAST.get(c, c) for c in unicodedata.normalize("NFC", text))


def tokenize(text: str) -> list[str]:
    return [w for w in _WORD.findall(_fold(text.lower())) if w not in _STOP]


def query_tokens(text: str) -> list[str]:
    """Tokens for a user query: folded, with Hinglish mapped to corpus English words."""
    return [_HINGLISH.get(w, w) for w in tokenize(text) if w not in _STOP]


class KwIndex:
    """Tiny idf keyword index over ref + chapter title + translation + purport words."""

    def __init__(self, records: list[dict]) -> None:
        self.docs: list[Counter] = []
        df: Counter = Counter()
        for r in records:
            toks = tokenize(
                f"{r['ref']} {r.get('chapter_title', '')} {r['translation']} {r.get('purport', '')[:400]}"
            )
            c = Counter(toks)
            self.docs.append(c)
            for w in c:
                df[w] += 1
        n = max(len(records), 1)
        self.idf = {w: math.log(1 + n / (1 + d)) for w, d in df.items()}

    def score(self, qtokens: list[str], idx: int) -> float:
        doc = self.docs[idx]
        return sum(
            self.idf.get(w, 0.0) * (1.0 + math.log1p(doc.get(w, 0)))
            for w in set(qtokens)
            if doc.get(w)
        )
