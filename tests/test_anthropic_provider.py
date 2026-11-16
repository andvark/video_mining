"""AnthropicProvider logic exercised against a fake SDK client (no network)."""
from __future__ import annotations

import sys
import types

from podstudy.providers import AnthropicProvider, get_provider


class _Msg:
    def __init__(self, text: str) -> None:
        self.content = [types.SimpleNamespace(text=text)]


class FakeClient:
    prompts: list[str] = []

    class messages:  # noqa: N801
        @staticmethod
        def create(model: str, max_tokens: int, messages: list[dict[str, str]]) -> _Msg:
            prompt = messages[0]["content"]
            FakeClient.prompts.append(prompt)
            if "TARGET" in prompt:
                return _Msg("Welcome to the podcast.")
            return _Msg('Sure! {"pinyin": "bō kè", "meaning": "podcast", "usage": "noun"}')


def _install_fake(monkeypatch) -> None:
    mod = types.ModuleType("anthropic")
    mod.Anthropic = FakeClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "anthropic", mod)


def test_translate_prompt_has_context_and_gloss_parses_json(monkeypatch):
    _install_fake(monkeypatch)
    p = AnthropicProvider(model="test-model")
    assert p.translate(["前一句"], "欢迎收听", ["后一句"]) == "Welcome to the podcast."
    assert "前一句" in FakeClient.prompts[-1] and "后一句" in FakeClient.prompts[-1]
    g = p.gloss("播客", "欢迎收听播客")
    assert (g.pinyin, g.meaning, g.usage) == ("bō kè", "podcast", "noun")


def test_get_provider_auto_uses_anthropic_when_key_set(monkeypatch):
    _install_fake(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert get_provider("auto").name == "anthropic"  # type: ignore[union-attr]
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert get_provider("auto") is None
