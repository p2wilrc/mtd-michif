"""
Language identification for English vs. Michif, with manual overrides.
"""

import json
from pathlib import Path

import fasttext  # type: ignore

from .textnorm import oversimplify

MODEL_PATH = Path(__file__).parent / "models" / "eng-crg-text.fasttext"
CLASSIFIER = fasttext.load_model(str(MODEL_PATH))
OVERRIDES_PATH = Path(__file__).parent / "models" / "eng-crg-text.overrides.json"
with open(OVERRIDES_PATH) as infh:
    OVERRIDES = json.load(infh)
    for lang in OVERRIDES:
        OVERRIDES[lang] = [oversimplify(text) for text in OVERRIDES[lang]]


def language_id(text: str) -> tuple[str, float]:
    """Identify text as 'eng' (English) or 'crg' (Michif)"""
    norm = oversimplify(text)
    if norm in OVERRIDES["eng"]:
        return "eng", 1.0
    if norm in OVERRIDES["crg"]:
        return "crg", 1.0
    (label,), score = CLASSIFIER.predict(text)
    return label.replace("__label__", ""), float(score[0])
