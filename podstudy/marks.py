"""marks.json persistence."""
from __future__ import annotations

import json
from pathlib import Path

from .models import Mark


def load_marks(path: Path) -> list[Mark]:
    if not path.exists():
        return []
    return [
        Mark(d["video_id"], float(d["timestamp"]), d["sentence"], d.get("phrase", ""))
        for d in json.loads(path.read_text(encoding="utf-8"))
    ]


def save_marks(path: Path, marks: list[Mark]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [m.to_dict() for m in marks]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def add_mark(path: Path, mark: Mark) -> list[Mark]:
    """Append a mark unless an identical (sentence, phrase) one exists."""
    marks = load_marks(path)
    if not any(m.sentence == mark.sentence and m.phrase == mark.phrase for m in marks):
        marks.append(mark)
        save_marks(path, marks)
    return marks
