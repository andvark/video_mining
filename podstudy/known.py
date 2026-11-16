"""Known-vocabulary list (data/known.txt, one word per line)."""
from __future__ import annotations

from pathlib import Path

from .annotate import has_han
from .models import Sentence


def load_known(path: Path) -> set[str]:
    if not path.exists():
        return set()
    lines = path.read_text(encoding="utf-8").splitlines()
    return {ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")}


def unknown_words(sentence: Sentence, known: set[str]) -> list[str]:
    return [w.text for w in sentence.words if has_han(w.text) and w.text not in known]
