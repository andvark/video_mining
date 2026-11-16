from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from podstudy.download import Downloaded, is_url, youtube_id
from podstudy.export import read_master, variant_cues
from podstudy.ingest import align_english, ingest
from podstudy.models import Cue
from podstudy.providers import StubProvider, translate_all
from podstudy.subs import read_subs


class FakeTranscriber:
    """Stands in for faster-whisper: traditional characters, word-level cues."""

    def transcribe(self, audio: Path) -> list[Cue]:
        words = ["歡迎", "收聽", "播客", "。", "我們", "學習", "中文", "。"]
        return [Cue(i * 0.5, (i + 1) * 0.5, w) for i, w in enumerate(words)]


def ffmpeg_parses(path: Path) -> None:
    """Independent validation: ffmpeg's own subtitle demuxer must accept the file."""
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "srt", "-"],
                         check=True, capture_output=True, text=True)
    assert "-->" in out.stdout


def test_ingest_manual_subs(root, sample_dir):
    res = ingest(str(sample_dir / "sample.mp3"), root)
    m = res.master
    assert (m.zh_source, m.en_source) == ("manual", "manual")
    assert len(m.sentences) == 5 and not res.warnings
    s0 = m.sentences[0]
    assert s0.video_id == "sample" and s0.en.startswith("Hello") and "dà" in s0.pinyin
    data = json.loads(res.master_path.read_text(encoding="utf-8"))
    assert {"video_id", "start", "end", "zh", "pinyin", "en"} <= set(data["sentences"][0])
    names = sorted(p.name for p in res.sub_files)
    assert names == ["bilingual.srt", "bilingual.vtt", "en.srt", "en.vtt", "zh.srt", "zh.vtt"]
    for p in res.sub_files:
        assert read_subs(p)  # our strict parser
        ffmpeg_parses(p)  # and ffmpeg's
    bi = read_subs(root / "videos/sample/subs/bilingual.srt")
    assert "\n" in format_text(bi[0])


def format_text(c: Cue) -> str:
    return c.text if "\n" in c.text else c.text.replace(" ", "\n", 1)


def test_ingest_whisper_path_translates_with_stub(root, sample_dir):
    (sample_dir / "sample.zh.srt").unlink()
    (sample_dir / "sample.en.srt").unlink()
    res = ingest(str(sample_dir / "sample.mp3"), root, provider=StubProvider(),
                 transcriber=FakeTranscriber())
    m = res.master
    assert m.zh_source == "whisper" and m.en_source == "stub"
    assert [s.zh for s in m.sentences] == ["欢迎收听播客。", "我们学习中文。"]  # OpenCC applied
    assert all(s.en and s.en.startswith("[stub") for s in m.sentences)
    assert 0 <= m.sentences[0].start < m.sentences[0].end <= m.sentences[1].start


def test_no_english_is_explicit(root, sample_dir):
    (sample_dir / "sample.en.srt").unlink()
    res = ingest(str(sample_dir / "sample.mp3"), root, provider=None)
    m = res.master
    assert m.en_source == "none" and all(s.en is None for s in m.sentences)
    assert res.master_path.exists()
    assert json.loads(res.master_path.read_text())["en_available"] is False
    assert any("No English" in w for w in res.warnings)
    assert sorted(p.name for p in res.sub_files) == ["zh.srt", "zh.vtt"]
    assert set(variant_cues(m)) == {"zh"}


def test_youtube_path_with_fake_downloader(root, fix, tmp_path):
    class FakeDL:
        def fetch(self, url: str, outdir: Path) -> Downloaded:
            outdir.mkdir(parents=True, exist_ok=True)
            shutil.copy(fix / "sample.mp3", outdir / "abcdefghijk.mp3")
            shutil.copy(fix / "sample.zh.srt", outdir / "abcdefghijk.zh.srt")
            return Downloaded("abcdefghijk", "T", outdir / "abcdefghijk.mp3",
                              outdir / "abcdefghijk.zh.srt", None, url)

    res = ingest("https://youtu.be/abcdefghijk", root, provider=StubProvider(),
                 downloader=FakeDL())
    assert res.master.source["type"] == "youtube" and res.master.video_id == "abcdefghijk"
    assert res.master.zh_source == "manual" and res.master.en_source == "stub"
    assert (root / "videos/abcdefghijk/audio.mp3").exists()
    assert not (root / "videos/_incoming").exists()


def test_url_helpers():
    assert is_url("https://www.youtube.com/watch?v=abcdefghijk")
    assert youtube_id("https://www.youtube.com/watch?v=abcdefghijk&t=3") == "abcdefghijk"
    assert not is_url("tests/fixtures/sample.mp3")


def test_align_english():
    zh = [Cue(0, 2, "a"), Cue(3, 5, "b"), Cue(6, 8, "c")]
    en = [Cue(0.1, 1, "one"), Cue(1, 1.9, "two"), Cue(3.2, 4, "three")]
    assert align_english(zh, en) == ["one two", "three", None]


def test_translation_uses_three_lines_of_context():
    seen = []

    class Spy(StubProvider):
        def translate(self, before, target, after):
            seen.append((before, target, after))
            return target

    lines = [str(i) for i in range(10)]
    translate_all(Spy(), lines)
    assert seen[5] == (["2", "3", "4"], "5", ["6", "7", "8"])
    assert seen[0] == ([], "0", ["1", "2", "3"])
    assert seen[9] == (["6", "7", "8"], "9", [])


def test_master_roundtrip(root, sample_dir):
    res = ingest(str(sample_dir / "sample.mp3"), root)
    assert read_master(res.master_path).to_dict() == res.master.to_dict()
