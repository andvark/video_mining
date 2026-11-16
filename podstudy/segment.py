"""Simplified-Chinese normalisation and sentence splitting with timing."""
from __future__ import annotations

import re
from functools import lru_cache

from .models import Cue

_END = set("。！？!?；;…\n")
_CLOSERS = set("”’）)」』\"'")


@lru_cache(maxsize=1)
def _converter():  # type: ignore[no-untyped-def]
    from opencc import OpenCC

    return OpenCC("t2s")


def to_simplified(text: str) -> str:
    return str(_converter().convert(text))


def _char_times(cues: list[Cue]) -> list[tuple[str, float, float]]:
    """Spread each cue's duration evenly over its characters."""
    out: list[tuple[str, float, float]] = []
    for cue in cues:
        text = re.sub(r"\s+", " ", cue.text.strip())
        if not text:
            continue
        step = (cue.end - cue.start) / len(text)
        for i, ch in enumerate(text):
            out.append((ch, cue.start + i * step, cue.start + (i + 1) * step))
    return out


def split_sentences(cues: list[Cue], max_chars: int = 60) -> list[Cue]:
    """Join cues, normalise to simplified, split on sentence punctuation.

    Sentences longer than ``max_chars`` are also split at commas.
    """
    chars = [(to_simplified(c), s, e) for c, s, e in _char_times(cues)]
    sentences: list[Cue] = []
    buf: list[tuple[str, float, float]] = []

    def flush() -> None:
        text = "".join(c for c, _, _ in buf).strip()
        if text and any(not c.isspace() and c not in "，,。！？!?；;…" for c in text):
            sentences.append(Cue(buf[0][1], buf[-1][2], text))
        buf.clear()

    for i, item in enumerate(chars):
        buf.append(item)
        ch = item[0]
        nxt = chars[i + 1][0] if i + 1 < len(chars) else ""
        if ch in _END and nxt not in _CLOSERS:
            flush()
        elif ch in "，,、" and len(buf) >= max_chars:
            flush()
    flush()
    return sentences
