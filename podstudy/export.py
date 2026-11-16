"""Master JSON + SRT/VTT export (zh-only, en-only, bilingual)."""
from __future__ import annotations

import json
from pathlib import Path

from .models import Cue, Master
from .subs import format_srt, format_vtt


def variant_cues(master: Master) -> dict[str, list[Cue]]:
    """Cue lists per variant. ``en`` / ``bilingual`` are omitted when no English exists."""
    zh = [Cue(s.start, s.end, s.zh) for s in master.sentences]
    variants: dict[str, list[Cue]] = {"zh": zh}
    if master.en_source == "none":
        return variants
    variants["en"] = [Cue(s.start, s.end, s.en or "") for s in master.sentences if s.en]
    variants["bilingual"] = [
        Cue(s.start, s.end, f"{s.zh}\n{s.en}" if s.en else s.zh) for s in master.sentences
    ]
    return variants


def write_master(master: Master, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(master.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def read_master(path: Path) -> Master:
    return Master.from_dict(json.loads(path.read_text(encoding="utf-8")))


def write_subs(master: Master, outdir: Path) -> list[Path]:
    """Write <variant>.srt and <variant>.vtt; returns written paths."""
    outdir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, cues in variant_cues(master).items():
        for ext, fmt in (("srt", format_srt), ("vtt", format_vtt)):
            p = outdir / f"{name}.{ext}"
            p.write_text(fmt(cues), encoding="utf-8")
            written.append(p)
    return written
