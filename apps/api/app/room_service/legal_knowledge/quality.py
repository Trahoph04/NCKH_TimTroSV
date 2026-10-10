"""Conservative text-layer checks; scores are heuristics, not OCR confidence."""
from __future__ import annotations

import re
import unicodedata

EXTRACTION_VERSION = "legal-v6"


def text_quality(text: str) -> float:
    words = re.findall(r"[^\W_]+", unicodedata.normalize("NFC", text), re.UNICODE)
    letters = [word for word in words if any(ch.isalpha() for ch in word)]
    if not letters:
        return 0.0
    damaged = sum(
        any(left.islower() and right.isupper() for left, right in zip(word, word[1:]))
        or (any(ch.isdigit() for ch in word) and any(ch.isalpha() for ch in word))
        for word in letters
    )
    # Broken embedded fonts often produce diQn, chri, nhd, th6ng, b6n...
    accented = sum(any(ord(ch) > 127 and ch.isalpha() for ch in word) for word in letters)
    replacement = text.count("�") + text.count("€")
    score = 1.0 - 3.5 * damaged / len(letters) - 4 * replacement / len(letters)
    if len(letters) > 40 and accented / len(letters) < 0.08:
        score -= 0.25
    return round(max(0.0, min(1.0, score)), 4)


def suspicious_numeric_range(text: str) -> bool:
    """Reject reversed monetary ranges, e.g. OCR '40 million to 20 million'."""
    for match in re.finditer(r"từ\s+([\d.]+)\s*đồng\s+đến\s+([\d.]+)\s*đồng", text, re.I):
        try:
            if int(match[1].replace(".", "")) > int(match[2].replace(".", "")):
                return True
        except ValueError:
            continue
    return False


def usable_legal_text(text: str) -> bool:
    return text_quality(text) >= 0.6 and not suspicious_numeric_range(text)
