from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import zipfile
from pathlib import Path

import pytest

from podstudy import cards as cards_mod
from podstudy.cards import (
    build_cards,
    clip_bounds,
    cloze,
    highlight,
    push_anki_connect,
    resolve_sentence,
)
from podstudy.cli import main
from podstudy.export import read_master
from podstudy.ingest import ingest
from podstudy.marks import load_marks
from podstudy.providers import StubProvider


@pytest.fixture
def prepared(root, sample_dir):
    res = ingest(str(sample_dir / "sample.mp3"), root)
    return res.master, root / "videos/sample/audio.mp3"


def duration(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                          "default=nw=1:nk=1", str(p)], capture_output=True, text=True, check=True)
    return float(out.stdout)


def inspect_apkg(apkg: Path, tmp: Path) -> tuple[int, dict[str, str], list[str]]:
    dest = tmp / "unz"
    with zipfile.ZipFile(apkg) as z:
        z.extractall(dest)
    media = json.loads((dest / "media").read_text())
    for num in media:
        assert (dest / num).stat().st_size > 500, "media file empty"
    db = sqlite3.connect(dest / "collection.anki2")
    n = db.execute("select count(*) from notes").fetchone()[0]
    flds = [r[0] for r in db.execute("select flds from notes")]
    return n, media, flds


def test_clip_bounds_pad_and_clamp(prepared):
    master, _ = prepared
    s = master.sentences[0]  # starts at 0.5s
    start, end = clip_bounds(s)
    assert start == pytest.approx(0.2) and end == pytest.approx(s.end + 0.3)
    s2 = master.sentences[1]
    assert clip_bounds(s2)[0] == pytest.approx(s2.start - 0.3)


def test_resolve_sentence_by_text_and_timestamp(prepared):
    master, _ = prepared
    marks = load_marks(Path(__file__).parent / "fixtures/marks.json")
    assert [resolve_sentence(master, m).id for m in marks] == [0, 1, 3]
    from podstudy.models import Mark
    assert resolve_sentence(master, Mark("sample", 16.8, "unknown text", "")).id == 4


def test_highlight_and_cloze():
    assert highlight("我爱播客", "播客") == '我爱<span class="ph">播客</span>'
    assert highlight("a<b", "") == "a&lt;b"
    assert cloze("我爱播客", "播客") == "我爱{{c1::播客}}"
    assert cloze("我爱播客", "") == "{{c1::我爱播客}}"


def test_apkg_notes_equal_marks_and_media_present(prepared, fix, tmp_path):
    master, audio = prepared
    marks = load_marks(fix / "marks.json")
    res = build_cards(master, marks, audio, tmp_path / "out", StubProvider())
    assert res.notes == len(marks) == 3
    n, media, flds = inspect_apkg(res.apkg, tmp_path)
    assert n == len(marks)
    assert len(media) == len(marks) and all(v.endswith(".mp3") for v in media.values())
    assert {m for f in flds for m in media.values() if f"[sound:{m}]" in f} == set(media.values())
    first = flds[0].split("\x1f")
    assert first[0].startswith("[sound:") and 'class="ph">播客' in first[1]
    assert "youtube" not in first[7] and "local audio" in first[7]
    # clip length = sentence + 2*0.3 (start>=0.2 so no clamp on sentence 0 is 0.3 -> 0.2 here)
    s0 = master.sentences[0]
    clip = res.media[0]
    assert duration(clip) == pytest.approx(s0.end + 0.3 - max(0, s0.start - 0.3), abs=0.15)


def test_cloze_and_both_variants(prepared, fix, tmp_path):
    master, audio = prepared
    marks = load_marks(fix / "marks.json")
    cl = build_cards(master, marks, audio, tmp_path / "c", StubProvider(), "cloze")
    n, _, flds = inspect_apkg(cl.apkg, tmp_path / "c")
    assert n == 3 and all("{{c1::" in f for f in flds)
    both = build_cards(master, marks, audio, tmp_path / "b", StubProvider(), "both")
    assert inspect_apkg(both.apkg, tmp_path / "b")[0] == 6


def test_youtube_link_is_timestamped(prepared):
    master, _ = prepared
    master.source = {"type": "youtube", "url": "", "audio": "audio.mp3"}
    master.video_id = "abcdefghijk"
    link = cards_mod.video_link(master, master.sentences[1])
    assert "watch?v=abcdefghijk&t=4s" in link


def test_anki_connect_push(monkeypatch, tmp_path):
    sent = {}

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"result": 1, "error": null}'

    def fake_urlopen(req, timeout):
        sent["body"] = json.loads(req.data)
        sent["url"] = req.full_url
        return Resp()

    monkeypatch.setattr(cards_mod.urllib.request, "urlopen", fake_urlopen)
    apkg = tmp_path / "x.apkg"
    apkg.write_bytes(b"x")
    push_anki_connect(apkg)
    assert sent["body"]["action"] == "importPackage" and sent["url"].endswith(":8765")


def test_cli_end_to_end(sample_dir, fix, tmp_path, capsys):
    d = str(tmp_path / "d")
    assert main(["--data-dir", d, "ingest", str(sample_dir / "sample.mp3")]) == 0
    marks = tmp_path / "marks.json"
    shutil.copy(fix / "marks.json", marks)
    out = tmp_path / "out"
    assert main(["--data-dir", d, "cards", "sample", "--marks", str(marks), "--out", str(out),
                 "--llm", "stub"]) == 0
    assert "notes: 3" in capsys.readouterr().out
    assert (out / "sample.apkg").exists()
    assert read_master(Path(d) / "videos/sample/master.json").video_id == "sample"


def test_cli_no_english_warns(sample_dir, tmp_path, capsys):
    (sample_dir / "sample.en.srt").unlink()
    assert main(["--data-dir", str(tmp_path / "d"), "ingest", str(sample_dir / "sample.mp3"),
                 "--translator", "none"]) == 0
    assert "No English available" in capsys.readouterr().err


def test_cli_cards_without_marks_fails(sample_dir, tmp_path):
    d = str(tmp_path / "d")
    main(["--data-dir", d, "ingest", str(sample_dir / "sample.mp3")])
    assert main(["--data-dir", d, "cards", "sample", "--out", str(tmp_path / "o")]) == 1
