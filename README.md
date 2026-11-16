# podstudy

Learn Chinese from YouTube podcasts. `podstudy` downloads (or transcribes) a podcast,
produces a sentence-aligned transcript with pinyin and English, serves a study viewer where
you flag sentences/phrases, and turns your marks into Anki cards with audio.

```
ingest ──► data/videos/<id>/master.json + subs/{zh,en,bilingual}.{srt,vtt}
serve  ──► web viewer, writes data/videos/<id>/marks.json
cards  ──► out/<id>.apkg  (audio clips cut with ffmpeg, glosses via the LLM provider)
```

## Install

Requirements: **Python 3.11+** and **ffmpeg** (with `ffprobe`) on your `PATH`
(`apt install ffmpeg` / `brew install ffmpeg`). ffmpeg is used to extract/cut audio and
by yt-dlp to convert downloads to mp3.

```bash
python -m venv .venv && source .venv/bin/activate   # or: uv venv && source .venv/bin/activate
pip install -e ".[dev,llm]"                          # `llm` adds the Anthropic SDK (optional)
```

The first transcription downloads the faster-whisper model (default `medium`, ~1.5 GB).

## Quickstart (5 commands)

```bash
pip install -e ".[dev,llm]"
export ANTHROPIC_API_KEY=...   # optional: real translations/glosses; without it English comes from subs only
podstudy ingest "https://www.youtube.com/watch?v=VIDEO_ID"   # or a local file: podstudy ingest talk.mp3
podstudy serve VIDEO_ID        # open http://127.0.0.1:8000 - press M / select words to flag
podstudy cards VIDEO_ID        # -> out/VIDEO_ID.apkg, import it into Anki
```

(For a local file the id is the slugified file name, e.g. `talk`. Sidecar subtitles named
`talk.zh.srt` / `talk.en.srt` next to the audio are used if present.)

> **YouTube note:** yt-dlp may need a JavaScript runtime (deno or node) installed for YouTube
> extraction, and YouTube sometimes blocks automated downloads; if so, download the audio
> yourself and use `podstudy ingest file.mp3` (with optional `file.zh.srt` / `file.en.srt`).

## How it works

**ingest** `podstudy ingest <youtube_url_or_audio> [--whisper-model medium] [--translator auto|anthropic|stub|none]`

1. yt-dlp fetches audio plus *manual* zh/en subtitles. If manual zh subs exist they are used;
   otherwise faster-whisper transcribes with word timestamps. Text is normalised to simplified
   with OpenCC and split into sentences (timings interpolated per character).
2. English: manual en subs are aligned to sentences by time; otherwise each sentence is
   translated by the provider with ±3 lines of context.
3. pypinyin + jieba add sentence pinyin and per-word pinyin.
4. Output: `master.json` (`video_id, start, end, zh, pinyin, en|null` per sentence, plus words)
   and `subs/{zh,en,bilingual}.{srt,vtt}`.

   **No English available:** if there are no English subs and no provider is configured, `en` is
   `null`, `master.json` has `"en_available": false`, a warning is printed, and the en-only and
   bilingual files are *not* written (only zh). Re-run with `--translator anthropic` to add them.

**serve** `podstudy serve <video_id> [--port 8000]`: YouTube embed (or an `<audio>` player for
local files) synced with the transcript. Buttons: 中文 / 中文+拼音 / 中文+EN / EN hidden until
click. Press **M** to flag the current sentence; select words to flag a phrase. Marks go to
`marks.json` as `{video_id, timestamp, sentence, phrase}`. Words missing from `data/known.txt`
(one word per line) are underlined.

**cards** `podstudy cards <video_id> [--marks marks.json] [--variant basic|cloze|both] [--anki-connect]`

Cuts audio for each mark (sentence start-0.3s … end+0.3s) with ffmpeg, asks the provider for
pinyin/meaning/usage, and writes an `.apkg` (genanki). Front: audio + sentence with the phrase
highlighted. Back: phrase, pinyin, meaning, sentence translation, timestamped video link.
`--variant cloze` makes cloze notes instead (`both` makes two notes per mark).
`--anki-connect [URL]` additionally imports the package into a running Anki with the AnkiConnect
add-on.

## LLM providers

`podstudy.providers.Provider` has two methods, `translate(before, target, after)` and
`gloss(phrase, sentence)`. Included: `AnthropicProvider` (model via `PODSTUDY_MODEL`) and an
offline `StubProvider` (used by the tests). Add your own by implementing the protocol.

## Development

```bash
pytest -q          # no network needed; uses tests/fixtures/sample.mp3 (20 s) + fixture subs
ruff check .
python tests/fixtures/make_fixtures.py   # regenerate fixtures (needs espeak-ng + ffmpeg)
```
