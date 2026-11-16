"""LLM provider interface with an offline stub and an Anthropic implementation."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Protocol

from .annotate import pinyin_of

CONTEXT = 3  # lines of context on each side when translating


@dataclass
class Gloss:
    pinyin: str
    meaning: str
    usage: str


class Provider(Protocol):
    name: str

    def translate(self, before: list[str], target: str, after: list[str]) -> str: ...

    def gloss(self, phrase: str, sentence: str) -> Gloss: ...


class StubProvider:
    """Deterministic, offline provider used in tests and when no LLM is configured."""

    name = "stub"

    def translate(self, before: list[str], target: str, after: list[str]) -> str:
        return f"[stub translation] {target}"

    def gloss(self, phrase: str, sentence: str) -> Gloss:
        return Gloss(pinyin_of(phrase), f"[stub meaning] {phrase}", f"[stub usage] {sentence}")


class AnthropicProvider:
    """Calls the Anthropic Messages API. Needs `pip install anthropic` + ANTHROPIC_API_KEY."""

    name = "anthropic"

    def __init__(self, model: str | None = None) -> None:
        import anthropic

        self._client = anthropic.Anthropic()
        self._model = model or os.environ.get("PODSTUDY_MODEL", "claude-haiku-5-5")

    def _ask(self, prompt: str) -> str:
        msg = self._client.messages.create(
            model=self._model, max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(getattr(b, "text", "") for b in msg.content).strip()

    def translate(self, before: list[str], target: str, after: list[str]) -> str:
        ctx_b = "\n".join(before) or "(none)"
        ctx_a = "\n".join(after) or "(none)"
        return self._ask(
            "Translate the TARGET Chinese podcast line into natural English. "
            "Use the context only for disambiguation. Reply with the translation only.\n\n"
            f"CONTEXT BEFORE:\n{ctx_b}\n\nTARGET:\n{target}\n\nCONTEXT AFTER:\n{ctx_a}"
        )

    def gloss(self, phrase: str, sentence: str) -> Gloss:
        raw = self._ask(
            "You help a learner of Chinese. Reply with JSON only, keys: pinyin, meaning, usage "
            "(usage = one short usage note). \n"
            f"Phrase: {phrase}\nSentence it appears in: {sentence}"
        )
        match = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(match.group(0)) if match else {}
        return Gloss(
            str(data.get("pinyin") or pinyin_of(phrase)),
            str(data.get("meaning", "")), str(data.get("usage", "")),
        )


def get_provider(name: str) -> Provider | None:
    """name: auto | stub | anthropic | none. ``none`` returns None."""
    if name == "none":
        return None
    if name == "stub":
        return StubProvider()
    if name == "anthropic":
        return AnthropicProvider()
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return AnthropicProvider()
        except ImportError:
            return None
    return None


def translate_all(provider: Provider, lines: list[str], window: int = CONTEXT) -> list[str]:
    """Translate every line using +-``window`` lines of context."""
    out = []
    for i, line in enumerate(lines):
        before = lines[max(0, i - window):i]
        after = lines[i + 1:i + 1 + window]
        out.append(provider.translate(before, line, after))
    return out
