from __future__ import annotations
import re
import unicodedata
from collections import Counter


STOPWORDS = {
    "de", "la", "el", "los", "las", "un", "una", "y", "o", "para", "por", "con",
    "del", "al", "se", "en", "que", "es", "a", "como", "su", "sus", "este",
    "esta", "estos", "estas", "the", "and", "or", "to", "of", "in"
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip()


def tokens(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9_./:-]{3,}", normalize(text))
        if token not in STOPWORDS
    }


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def extract_issue_keys(text: str) -> set[str]:
    return set(re.findall(r"\b[A-Z][A-Z0-9]+-\d+\b", text.upper()))


def extract_paths(text: str) -> set[str]:
    return set(re.findall(r"(?<!\w)/(?:[A-Za-z0-9_{}.-]+/?)+", text))


def top_terms(text: str, limit: int = 8) -> list[str]:
    counts = Counter(tokens(text))
    return [term for term, _ in counts.most_common(limit)]
