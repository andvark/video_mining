"""Anki cards: audio clips (ffmpeg), LLM glosses, .apkg (genanki), AnkiConnect push."""
from __future__ import annotations

import hashlib
import html
import json
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import genanki

from .models import Mark, Master, Sentence
from .providers import Gloss, Provider

PAD = 0.3
CSS = (
    ".card{font-family:sans-serif;font-size:22px;text-align:center}"
    ".ph{color:#c00;font-weight:bold}"
)

BASIC_FIELDS = ["Audio", "Sentence", "Phrase", "Pinyin", "Meaning", "Translation", "Usage", "Link"]
BACK = (
    "{{FrontSide}}<hr id=answer><div class=ph>{{Phrase}}</div><div>{{Pinyin}}</div>"
    "<div>{{Meaning}}</div><div>{{Translation}}</div><div><i>{{Usage}}</i></div>"
    "<div>{{Link}}</div>"
)


def _model(model_id: int, name: str, cloze: bool) -> genanki.Model:
    fields = ["Text" if (cloze and f == "Sentence") else f for f in BASIC_FIELDS]
    front = "{{cloze:Text}}<br>{{Audio}}" if cloze else "{{Audio}}<div>{{Sentence}}</div>"
    return genanki.Model(
        model_id, name, fields=[{"name": f} for f in fields], css=CSS,
        templates=[{"name": "Card 1", "qfmt": front, "afmt": BACK.replace(
            "{{FrontSide}}", "{{cloze:Text}}<br>{{Audio}}" if cloze else "{{FrontSide}}")}],
        model_type=genanki.Model.CLOZE if cloze else genanki.Model.FRONT_BACK,
    )


BASIC_MODEL = _model(1607392311, "podstudy sentence", cloze=False)
CLOZE_MODEL = _model(1607392312, "podstudy cloze", cloze=True)


@dataclass
class CardsResult:
    apkg: Path
    notes: int
    media: list[Path]


def stable_id(text: str) -> int:
    return int(hashlib.sha1(text.encode()).hexdigest()[:8], 16)


def resolve_sentence(master: Master, mark: Mark) -> Sentence:
    """Find the transcript sentence for a mark (text match first, then timestamp)."""
    for s in master.sentences:
        if s.zh == mark.sentence:
            return s
    for s in master.sentences:
        if mark.sentence and (mark.sentence in s.zh or s.zh in mark.sentence):
            return s
    return min(master.sentences, key=lambda s: 0 if s.start <= mark.timestamp <= s.end
               else min(abs(mark.timestamp - s.start), abs(mark.timestamp - s.end)))


def clip_bounds(s: Sentence, duration: float | None = None) -> tuple[float, float]:
    start = max(0.0, s.start - PAD)
    end = s.end + PAD
    return start, min(end, duration) if duration else end


def cut_audio(audio: Path, start: float, end: float, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", str(audio),
         "-t", f"{end - start:.3f}", "-c:a", "libmp3lame", "-q:a", "4", str(out)],
        check=True,
    )


def highlight(sentence: str, phrase: str) -> str:
    esc = html.escape(sentence)
    ph = html.escape(phrase)
    if ph and ph in esc:
        return esc.replace(ph, f'<span class="ph">{ph}</span>', 1)
    return esc


def cloze(sentence: str, phrase: str) -> str:
    phrase = phrase or sentence
    return html.escape(sentence).replace(html.escape(phrase),
                                         "{{c1::" + html.escape(phrase) + "}}", 1)


def video_link(master: Master, s: Sentence) -> str:
    if master.source.get("type") != "youtube":
        return f"{master.title} @ {int(s.start)}s (local audio)"
    url = f"https://www.youtube.com/watch?v={master.video_id}&t={int(s.start)}s"
    return f'<a href="{url}">{url}</a>'


def build_cards(
    master: Master, marks: list[Mark], audio: Path, outdir: Path, provider: Provider,
    variant: str = "basic",
) -> CardsResult:
    """variant: basic | cloze | both (``both`` makes two notes per mark)."""
    media_dir = outdir / "media"
    deck = genanki.Deck(stable_id("deck:" + master.video_id), f"podstudy::{master.video_id}")
    media: list[Path] = []
    notes = 0
    for n, mark in enumerate(marks):
        sent = resolve_sentence(master, mark)
        phrase = mark.phrase or sent.zh
        clip = media_dir / f"{master.video_id}_{n:03d}_{int(sent.start * 1000)}.mp3"
        start, end = clip_bounds(sent)
        cut_audio(audio, start, end, clip)
        media.append(clip)
        gloss: Gloss = provider.gloss(phrase, sent.zh)
        translation = sent.en or provider.translate([], sent.zh, [])
        common = [f"[sound:{clip.name}]", "", phrase, gloss.pinyin, gloss.meaning, translation,
                  gloss.usage, video_link(master, sent)]
        guid_base = f"{master.video_id}|{n}|{mark.timestamp}|{phrase}"
        if variant in ("basic", "both"):
            fields = common.copy()
            fields[1] = highlight(sent.zh, mark.phrase)
            deck.add_note(genanki.Note(model=BASIC_MODEL, fields=fields,
                                       guid=genanki.guid_for("basic", guid_base)))
            notes += 1
        if variant in ("cloze", "both"):
            fields = common.copy()
            fields[1] = cloze(sent.zh, mark.phrase)
            deck.add_note(genanki.Note(model=CLOZE_MODEL, fields=fields,
                                       guid=genanki.guid_for("cloze", guid_base)))
            notes += 1
    pkg = genanki.Package(deck)
    pkg.media_files = [str(m) for m in media]
    apkg = outdir / f"{master.video_id}.apkg"
    pkg.write_to_file(str(apkg))
    return CardsResult(apkg, notes, media)


def push_anki_connect(apkg: Path, url: str = "http://127.0.0.1:8765") -> None:
    """Ask a running Anki (AnkiConnect add-on) to import the package."""
    body = json.dumps({"action": "importPackage", "version": 6,
                       "params": {"path": str(apkg.resolve())}}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
        reply = json.loads(resp.read())
    if reply.get("error"):
        raise RuntimeError(f"AnkiConnect error: {reply['error']}")
