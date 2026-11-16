"""Local web viewer (FastAPI)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from . import config
from .export import read_master
from .known import load_known
from .marks import add_mark, load_marks
from .models import Mark

WEB = Path(__file__).parent / "web"


class MarkIn(BaseModel):
    timestamp: float
    sentence: str
    phrase: str = ""


def create_app(root: Path, video_id: str) -> FastAPI:
    mpath = config.master_path(root, video_id)
    if not mpath.exists():
        raise FileNotFoundError(f"{mpath} not found - run `podstudy ingest` first")
    app = FastAPI(title="podstudy")
    marks_file = config.marks_path(root, video_id)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (WEB / "index.html").read_text(encoding="utf-8")

    @app.get("/api/master")
    def master() -> dict[str, Any]:
        return read_master(mpath).to_dict()

    @app.get("/api/known")
    def known() -> list[str]:
        return sorted(load_known(config.known_path(root)))

    @app.get("/api/marks")
    def get_marks() -> list[dict[str, Any]]:
        return [m.to_dict() for m in load_marks(marks_file)]

    @app.post("/api/marks")
    def post_mark(m: MarkIn) -> list[dict[str, Any]]:
        mark = Mark(video_id, round(m.timestamp, 3), m.sentence, m.phrase)
        return [x.to_dict() for x in add_mark(marks_file, mark)]

    @app.get("/media/audio")
    def audio() -> FileResponse:
        name = read_master(mpath).source.get("audio", "")
        path = config.video_dir(root, video_id) / name
        if not name or not path.exists():
            raise HTTPException(404, "audio not found")
        return FileResponse(path)

    return app
