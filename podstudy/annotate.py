"""Pinyin + word segmentation."""
from __future__ import annotations

import re

import jieba
from pypinyin import Style, lazy_pinyin

from .models import WordAnn

_HAN = re.compile(r"[㐀-鿿]")
jieba.setLogLevel(60)


def has_han(text: str) -> bool:
    return bool(_HAN.search(text))


def pinyin_of(text: str) -> str:
    return " ".join(lazy_pinyin(text, style=Style.TONE))


def annotate(zh: str) -> tuple[str, list[WordAnn]]:
    """Return (pinyin string for the sentence, per-word annotations)."""
    words: list[WordAnn] = []
    for tok in jieba.lcut(zh):
        if not tok.strip():
            continue
        py = pinyin_of(tok) if has_han(tok) else ""
        words.append(WordAnn(tok, py))
    sentence_py = " ".join(w.pinyin if w.pinyin else w.text for w in words)
    return sentence_py, words
