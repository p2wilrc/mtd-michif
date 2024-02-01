"""
Text normalization functions.
"""

import logging
import re
from typing import Optional

LOGGER = logging.getLogger("textnorm")


def simplify(text: str) -> str:
    """Trivial normalization of input text."""
    if text is None:
        return None

    return re.sub(r"\s+", " ", text.lower())


def oversimplify(text: str) -> str:
    """Trivial overnormalization of input text."""
    if text is None:
        return None
    text = text.lower()
    # Remove whitespace
    text = re.sub(r"\W+", "", text)
    text = re.sub(r"_", "", text)  # It's a "word" character above...
    # OCR errors
    text = re.sub(r"[li1j]", "I", text)
    text = re.sub(r"[ft]", "F", text)
    text = re.sub(r"[oc0]", "O", text)
    text = re.sub(r"[wv]+", "W", text)
    # Neutralize spelling vairants
    text = re.sub(r"aW|ah|aWh", "A", text)
    text = re.sub(r"Ou|OO", "U", text)
    return text


def neutralize_ocr(text: str) -> str:
    """Neutralize some common OCR errors."""
    # remove final ! first as it's unlikely to be a confusion
    text = re.sub(r"!$", "", text)
    text = re.sub(r"[!li1j]", "I", text)
    text = re.sub(r"[ft]", "F", text)
    text = re.sub(r"[oc0]", "O", text)
    text = re.sub(r"[wv]+", "W", text)
    return text


def normalize_english(english: Optional[str]) -> str:
    """Trivial overnormalization of English text."""
    if english is None:
        return ""
    english = english.lower().strip()
    english = neutralize_ocr(english)
    # Remove whitespace
    english = re.sub(r"\W+", "", english)
    english = re.sub(r"_", "", english)  # It's a "word" character above...
    return english


def normalize_michif(michif: Optional[str]) -> str:
    """Normalize Michif text neutralizing various differences that are
    irrelevant for matching entries."""
    if michif is None:
        return ""
    michif = michif.lower().strip()
    michif = neutralize_ocr(michif)
    # Neutralize spelling vairants
    michif = re.sub(r"aW|ah|aWh", "A", michif)
    michif = re.sub(r"Ou|OO|u", "U", michif)
    # Remove whitespace
    michif = re.sub(r"\W+", "", michif)
    michif = re.sub(r"_", "", michif)  # It's a "word" character above...
    return michif


def deduplicate(text: Optional[str]) -> str:
    """Repair duplicated text."""
    if text is None:
        return ""
    text = re.sub(r"\s+", " ", text.strip())
    if text == "":
        return text
    half = len(text) // 2
    # Not actually a duplicate, e.g. "goody-goody"
    if len(text) > half * 2 and text[half] != " ":
        return text
    # Too short to consider, e.g. "booboo", "groo groo"
    if " " not in text[:half] and half < 8:
        return text
    if text[-half:].lower() == text[:half].lower():
        LOGGER.warning("DUPLICATE:%s -> %s", text, text[:half])
        return text[:half]
    return text
