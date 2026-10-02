"""Text matching for Tier 1: a tokenizer and a BM25 index, standard library only."""

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence

TOKEN_RE = re.compile(r"[a-z0-9]+")

# Generic English function words. Negations (no, not, without) are kept.
STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "then",
        "else",
        "of",
        "to",
        "in",
        "on",
        "at",
        "by",
        "for",
        "from",
        "as",
        "into",
        "onto",
        "over",
        "under",
        "up",
        "down",
        "out",
        "about",
        "than",
        "so",
        "such",
        "each",
        "any",
        "all",
        "also",
        "just",
        "only",
        "very",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "there",
        "their",
        "they",
        "them",
        "he",
        "she",
        "his",
        "her",
        "we",
        "you",
        "your",
        "i",
        "me",
        "my",
        "our",
        "us",
        "do",
        "does",
        "did",
        "done",
        "has",
        "have",
        "had",
        "will",
        "would",
        "can",
        "could",
        "should",
        "may",
        "might",
        "must",
    ]
)

MIN_STEM = 3


def stem(word: str) -> str:
    """Crude suffix stripping so inflections of a word share one key.

    The result need not be a real word, only consistent: save/saved -> sav.
    """
    if len(word) <= MIN_STEM or word.isdigit():
        return word
    if word.endswith("ies") and len(word) - 3 >= MIN_STEM - 1:
        return word[:-3] + "y"
    if word.endswith(("sses", "shes", "ches", "xes", "zes")):
        word = word[:-2]
    elif word.endswith("s") and not word.endswith(("ss", "us", "is")):
        word = word[:-1]
    for suffix in ("ing", "ed"):
        if word.endswith(suffix) and len(word) - len(suffix) >= MIN_STEM:
            word = word[: -len(suffix)]
            break
    if word.endswith("e") and len(word) > MIN_STEM:
        word = word[:-1]
    return word


class Tokenizer:
    """Lowercase, apply glossary phrases, split, drop stopwords, stem."""

    def __init__(self, glossary: Mapping[str, str] | None = None) -> None:
        self._glossary = {
            phrase.lower(): canonical.lower()
            for phrase, canonical in (glossary or {}).items()
        }
        phrases = sorted(self._glossary, key=len, reverse=True)
        pattern = "|".join(
            r"[\s-]+".join(map(re.escape, phrase.split())) for phrase in phrases
        )
        self._phrase_re = re.compile(rf"\b(?:{pattern})\b") if phrases else None

    def _canonical(self, match: re.Match[str]) -> str:
        return self._glossary[" ".join(re.split(r"[\s-]+", match[0]))]

    def __call__(self, text: str) -> list[str]:
        text = text.lower()
        if self._phrase_re is not None:
            text = self._phrase_re.sub(self._canonical, text)
        return [
            stem(token) for token in TOKEN_RE.findall(text) if token not in STOPWORDS
        ]


class Bm25Index:
    """Okapi BM25 over pre-tokenized documents, keyed by document ID."""

    def __init__(
        self, docs: Mapping[str, Sequence[str]], k1: float = 1.5, b: float = 0.75
    ) -> None:
        self._k1 = k1
        self._b = b
        self._keys = list(docs)
        self._tf = [Counter(tokens) for tokens in docs.values()]
        self._len = [len(tokens) for tokens in docs.values()]
        n = len(self._keys)
        self._avg_len = sum(self._len) / n if n else 0.0
        df = Counter(term for tf in self._tf for term in tf)
        # The +1 keeps IDF positive even for terms found in most documents.
        self._idf = {t: math.log((n - d + 0.5) / (d + 0.5) + 1) for t, d in df.items()}

    def _score(self, query: Sequence[str], doc: int) -> float:
        tf = self._tf[doc]
        norm = 1 - self._b + self._b * (self._len[doc] / self._avg_len)
        score = 0.0
        for term in query:
            freq = tf.get(term, 0)
            if freq:
                score += (
                    self._idf[term] * freq * (self._k1 + 1) / (freq + self._k1 * norm)
                )
        return score

    def top_k(self, query: Sequence[str], k: int) -> list[tuple[str, float]]:
        """Best k documents with a positive score, best first; ties keep doc order."""
        if k < 1:
            raise ValueError(f"k must be at least 1, got {k}")
        scored = [
            (key, score)
            for doc, key in enumerate(self._keys)
            if (score := self._score(query, doc)) > 0
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:k]
