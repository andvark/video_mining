"""Plain data types shared across the pipeline."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Cue:
    """A timed piece of text (a subtitle cue or a transcribed word)."""

    start: float
    end: float
    text: str


@dataclass
class WordAnn:
    text: str
    pinyin: str


@dataclass
class Sentence:
    id: int
    video_id: str
    start: float
    end: float
    zh: str
    pinyin: str
    en: str | None = None
    words: list[WordAnn] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Master:
    video_id: str
    title: str
    source: dict[str, str]
    zh_source: str  # "manual" | "whisper" | "sidecar"
    en_source: str  # "manual" | "llm" | "stub" | "none"
    sentences: list[Sentence]

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_id": self.video_id,
            "title": self.title,
            "source": self.source,
            "zh_source": self.zh_source,
            "en_source": self.en_source,
            "en_available": self.en_source != "none",
            "sentences": [s.to_dict() for s in self.sentences],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Master:
        sents = [
            Sentence(
                id=s["id"], video_id=s["video_id"], start=s["start"], end=s["end"],
                zh=s["zh"], pinyin=s["pinyin"], en=s.get("en"),
                words=[WordAnn(**w) for w in s.get("words", [])],
            )
            for s in d["sentences"]
        ]
        return cls(
            video_id=d["video_id"], title=d.get("title", ""), source=d.get("source", {}),
            zh_source=d.get("zh_source", ""), en_source=d.get("en_source", "none"),
            sentences=sents,
        )


@dataclass
class Mark:
    video_id: str
    timestamp: float
    sentence: str
    phrase: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
