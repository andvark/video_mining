"""SRT / VTT parsing and writing (strict: malformed input raises ValueError)."""
from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from .models import Cue

_TS = r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{3})"
_ARROW = re.compile(rf"^\s*{_TS}\s*-->\s*{_TS}")
_TAG = re.compile(r"<[^>]+>")


def _secs(h: str | None, m: str, s: str, ms: str) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_subs(text: str) -> list[Cue]:
    """Parse SRT or WebVTT text into cues."""
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    is_vtt = text.startswith("WEBVTT")
    if not is_vtt and not text.strip():
        return []
    cues: list[Cue] = []
    for block in re.split(r"\n{2,}", text.strip()):
        lines = block.split("\n")
        idx = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
        if idx is None:
            if is_vtt and (block.startswith(("WEBVTT", "NOTE", "STYLE"))):
                continue
            raise ValueError(f"cue block without timing line: {block[:40]!r}")
        m = _ARROW.match(lines[idx])
        if not m:
            raise ValueError(f"bad timing line: {lines[idx]!r}")
        g = m.groups()
        start, end = _secs(*g[:4]), _secs(*g[4:])
        if end < start:
            raise ValueError(f"cue ends before it starts: {lines[idx]!r}")
        body = _TAG.sub("", " ".join(ln.strip() for ln in lines[idx + 1:])).strip()
        if body:
            cues.append(Cue(start, end, body))
    return cues


def read_subs(path: Path) -> list[Cue]:
    return parse_subs(path.read_text(encoding="utf-8"))


def _stamp(t: float, sep: str) -> str:
    ms = round(t * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02}{sep}{ms:03}"


def format_srt(cues: Iterable[Cue]) -> str:
    out = []
    for i, c in enumerate(cues, 1):
        out.append(f"{i}\n{_stamp(c.start, ',')} --> {_stamp(c.end, ',')}\n{c.text}\n")
    return "\n".join(out)


def format_vtt(cues: Iterable[Cue]) -> str:
    out = ["WEBVTT\n"]
    for c in cues:
        out.append(f"{_stamp(c.start, '.')} --> {_stamp(c.end, '.')}\n{c.text}\n")
    return "\n".join(out)
