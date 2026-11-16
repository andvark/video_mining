"""Regenerate tests/fixtures/sample.mp3 (+ sample.zh.srt / sample.en.srt).

Uses espeak-ng (offline Mandarin TTS) and ffmpeg; sentence timings in the
subtitle files are measured from the generated audio, so they line up.
Run: python tests/fixtures/make_fixtures.py
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
LINES = [
    ("大家好，欢迎收听今天的播客。", "Hello everyone, welcome to today's podcast."),
    ("今天我们聊聊学习中文的方法。", "Today we talk about ways to learn Chinese."),
    ("我每天早上都会听一个小时的中文播客。",
     "Every morning I listen to a Chinese podcast for an hour."),
    ("这样可以提高我的听力水平。", "This improves my listening level."),
    ("你觉得这个方法怎么样？", "What do you think of this method?"),
]
GAP = 0.4


def run(*cmd: str) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def duration(path: Path) -> float:
    out = run("ffprobe", "-v", "error", "-show_entries", "format=duration",
              "-of", "default=nw=1:nk=1", str(path))
    return float(out.strip())


def stamp(t: float) -> str:
    ms = round(t * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_s:
        tmp = Path(tmp_s)
        parts: list[Path] = []
        times: list[tuple[float, float]] = []
        t = 0.5
        silence = tmp / "gap.wav"
        run("ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
            "-t", str(GAP), str(silence))
        lead = tmp / "lead.wav"
        run("ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
            "-t", "0.5", str(lead))
        parts.append(lead)
        for i, (zh, _) in enumerate(LINES):
            wav = tmp / f"s{i}.wav"
            run("espeak-ng", "-v", "cmn", "-s", "260", "-w", str(wav), zh)
            norm = tmp / f"n{i}.wav"
            run("ffmpeg", "-y", "-i", str(wav), "-ar", "22050", "-ac", "1", str(norm))
            d = duration(norm)
            times.append((t, t + d))
            t += d + GAP
            parts += [norm, silence]
        listing = tmp / "list.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in parts))
        full = tmp / "full.wav"
        run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), str(full))
        run("ffmpeg", "-y", "-i", str(full), "-t", "20", "-b:a", "48k", str(HERE / "sample.mp3"))
    for lang, idx in (("zh", 0), ("en", 1)):
        blocks = []
        for n, ((s, e), line) in enumerate(zip(times, LINES, strict=True), 1):
            blocks.append(f"{n}\n{stamp(s)} --> {stamp(min(e, 20.0))}\n{line[idx]}\n")
        (HERE / f"sample.{lang}.srt").write_text("\n".join(blocks), encoding="utf-8")
    print("ok", times)


if __name__ == "__main__":
    main()
