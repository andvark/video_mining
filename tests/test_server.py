from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from podstudy.ingest import ingest
from podstudy.server import create_app


@pytest.fixture
def client(root, sample_dir):
    ingest(str(sample_dir / "sample.mp3"), root)
    (root / "known.txt").write_text("我\n今天\n", encoding="utf-8")
    return TestClient(create_app(root, "sample")), root


def test_viewer_page_has_required_controls(client):
    c, _ = client
    html = c.get("/").text
    needles = ("中文+拼音", "click to reveal", "iframe_api", "<audio",
               'key.toLowerCase() !== "m"', "getSelection", "unk")
    for needle in needles:
        assert needle in html


def test_master_known_and_audio(client):
    c, _ = client
    assert len(c.get("/api/master").json()["sentences"]) == 5
    assert c.get("/api/known").json() == ["今天", "我"]
    r = c.get("/media/audio")
    assert r.status_code == 200 and len(r.content) > 1000


def test_marks_saved_to_marks_json(client):
    c, root = client
    c.post("/api/marks", json={"timestamp": 1.5, "sentence": "大家好，欢迎收听今天的播客。"})
    out = c.post("/api/marks", json={"timestamp": 1.0, "sentence": "大家好，欢迎收听今天的播客。",
                                     "phrase": "播客"}).json()
    c.post("/api/marks", json={"timestamp": 1.0, "sentence": "大家好，欢迎收听今天的播客。",
                               "phrase": "播客"})  # duplicate ignored
    assert len(out) == 2
    saved = json.loads((root / "videos/sample/marks.json").read_text(encoding="utf-8"))
    assert len(saved) == 2
    assert set(saved[1]) == {"video_id", "timestamp", "sentence", "phrase"}
    assert saved[1]["video_id"] == "sample" and saved[1]["phrase"] == "播客"
    assert c.get("/api/marks").json() == saved


def test_missing_video(root):
    with pytest.raises(FileNotFoundError):
        create_app(root, "nope")
