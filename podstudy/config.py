"""Workspace layout: everything lives under one data directory."""
from __future__ import annotations

import os
import re
from pathlib import Path


def data_dir(override: str | Path | None = None) -> Path:
    return Path(override or os.environ.get("PODSTUDY_DATA") or "data")


def video_dir(root: Path, video_id: str) -> Path:
    return root / "videos" / video_id


def master_path(root: Path, video_id: str) -> Path:
    return video_dir(root, video_id) / "master.json"


def marks_path(root: Path, video_id: str) -> Path:
    return video_dir(root, video_id) / "marks.json"


def known_path(root: Path) -> Path:
    return root / "known.txt"


def slugify(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", text).strip("-")
    return slug or "video"
