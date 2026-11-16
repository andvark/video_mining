"""yt-dlp wrapper: audio + manual zh/en subtitles."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

_YT_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})")


@dataclass
class Downloaded:
    video_id: str
    title: str
    audio: Path
    zh_subs: Path | None
    en_subs: Path | None
    url: str


class Downloader(Protocol):
    def fetch(self, url: str, outdir: Path) -> Downloaded: ...


def is_url(s: str) -> bool:
    return s.startswith(("http://", "https://")) or bool(_YT_ID.search(s))


def youtube_id(url: str) -> str | None:
    m = _YT_ID.search(url)
    return m.group(1) if m else None


def _pick(outdir: Path, vid: str, prefix: str) -> Path | None:
    cands = [p for ext in ("vtt", "srt") for p in sorted(outdir.glob(f"{vid}.{prefix}*.{ext}"))]
    # prefer simplified, then anything
    cands.sort(key=lambda p: (0 if "Hans" in p.name or ".zh." in p.name else 1, p.name))
    return cands[0] if cands else None


class YtDlpDownloader:
    def fetch(self, url: str, outdir: Path) -> Downloaded:
        import yt_dlp

        outdir.mkdir(parents=True, exist_ok=True)
        opts: dict[str, Any] = {
            "format": "bestaudio/best",
            "outtmpl": str(outdir / "%(id)s.%(ext)s"),
            "writesubtitles": True,          # manual subs only
            "writeautomaticsub": False,
            "subtitleslangs": ["zh.*", "en.*"],
            "subtitlesformat": "vtt/srt/best",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"}
            ],
            "quiet": True,
            "noprogress": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        vid = str(info["id"])
        return Downloaded(
            video_id=vid, title=str(info.get("title", vid)), audio=outdir / f"{vid}.mp3",
            zh_subs=_pick(outdir, vid, "zh"), en_subs=_pick(outdir, vid, "en"), url=url,
        )
