"""Ingest pipeline: download/locate audio, get zh text, English, annotate, export."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from . import config
from .annotate import annotate
from .download import Downloaded, Downloader, YtDlpDownloader, is_url
from .export import write_master, write_subs
from .models import Cue, Master, Sentence
from .providers import Provider, translate_all
from .segment import split_sentences
from .subs import read_subs
from .transcribe import FasterWhisperTranscriber, Transcriber


@dataclass
class IngestResult:
    master: Master
    master_path: Path
    sub_files: list[Path]
    warnings: list[str]


def align_english(sentences: list[Cue], en_cues: list[Cue]) -> list[str | None]:
    """Assign each English cue to the zh sentence containing its midpoint."""
    buckets: list[list[str]] = [[] for _ in sentences]
    for cue in en_cues:
        mid = (cue.start + cue.end) / 2
        best = min(
            range(len(sentences)),
            key=lambda i: 0 if sentences[i].start <= mid <= sentences[i].end
            else min(abs(mid - sentences[i].start), abs(mid - sentences[i].end)),
        )
        buckets[best].append(cue.text)
    return [" ".join(b) if b else None for b in buckets]


def _local_source(src: Path, dest: Path) -> Downloaded:
    dest.mkdir(parents=True, exist_ok=True)
    audio = dest / f"audio{src.suffix}"
    shutil.copyfile(src, audio)

    def sidecar(lang: str) -> Path | None:
        for ext in ("srt", "vtt"):
            for name in (f"{src.stem}.{lang}.{ext}", f"{src.stem}.{lang}-Hans.{ext}"):
                if (src.parent / name).exists():
                    return src.parent / name
        return None

    return Downloaded(config.slugify(src.stem), src.stem, audio, sidecar("zh"), sidecar("en"),
                      str(src))


def ingest(
    source: str, root: Path, *, provider: Provider | None = None,
    transcriber: Transcriber | None = None, downloader: Downloader | None = None,
    whisper_model: str = "medium",
) -> IngestResult:
    warnings: list[str] = []
    staging = root / "videos" / "_incoming"
    if is_url(source) and not Path(source).exists():
        dl = (downloader or YtDlpDownloader()).fetch(source, staging)
        src_type = "youtube"
    else:
        dl = _local_source(Path(source), staging)
        src_type = "local"
    vdir = config.video_dir(root, dl.video_id)
    vdir.mkdir(parents=True, exist_ok=True)
    audio = vdir / f"audio{dl.audio.suffix}"
    if dl.audio.resolve() != audio.resolve():
        shutil.move(str(dl.audio), audio)

    # 1. Chinese text
    if dl.zh_subs:
        raw, zh_source = read_subs(dl.zh_subs), "manual"
    else:
        tr = transcriber or FasterWhisperTranscriber(model=whisper_model)
        raw, zh_source = tr.transcribe(audio), "whisper"
    zh_cues = split_sentences(raw)
    if not zh_cues:
        raise ValueError("no Chinese text could be obtained from the source")

    # 2. English
    en: list[str | None]
    if dl.en_subs:
        en, en_source = align_english(zh_cues, read_subs(dl.en_subs)), "manual"
    elif provider is not None:
        en, en_source = list(translate_all(provider, [c.text for c in zh_cues])), provider.name
    else:
        en, en_source = [None] * len(zh_cues), "none"
        warnings.append(
            "No English available: no manual English subtitles and no translation provider "
            "configured. English fields are null; en-only and bilingual subtitle variants "
            "were not written. Re-run with --translator anthropic (or stub) to add English."
        )

    # 3. annotate
    sentences = []
    for i, (cue, e) in enumerate(zip(zh_cues, en, strict=True)):
        py, words = annotate(cue.text)
        sentences.append(Sentence(i, dl.video_id, round(cue.start, 3), round(cue.end, 3),
                                  cue.text, py, e, words))
    source_info = {"type": src_type, "url": dl.url if src_type == "youtube" else "",
                   "audio": audio.name}
    master = Master(dl.video_id, dl.title, source_info, zh_source, en_source, sentences)

    # 4. write
    mpath = config.master_path(root, dl.video_id)
    write_master(master, mpath)
    subs = write_subs(master, vdir / "subs")
    shutil.rmtree(staging, ignore_errors=True)
    return IngestResult(master, mpath, subs, warnings)
