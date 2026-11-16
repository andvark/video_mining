"""Speech-to-text via faster-whisper (word timestamps)."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .models import Cue


class Transcriber(Protocol):
    def transcribe(self, audio: Path) -> list[Cue]: ...


class FasterWhisperTranscriber:
    def __init__(self, model: str = "medium", device: str = "auto",
                 compute_type: str = "int8", language: str = "zh") -> None:
        self.model_name = model
        self.device = device
        self.compute_type = compute_type
        self.language = language

    def transcribe(self, audio: Path) -> list[Cue]:
        from faster_whisper import WhisperModel

        model = WhisperModel(self.model_name, device=self.device, compute_type=self.compute_type)
        segments, _info = model.transcribe(
            str(audio), language=self.language, word_timestamps=True, vad_filter=True,
        )
        cues: list[Cue] = []
        for seg in segments:
            if seg.words:
                cues += [Cue(w.start, w.end, w.word) for w in seg.words if w.word.strip()]
            elif seg.text.strip():
                cues.append(Cue(seg.start, seg.end, seg.text))
        return cues
