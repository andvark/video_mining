# PROGRESS

## Milestones
- [x] M1 scaffold, fixtures (espeak-ng 20 s sample + aligned zh/en SRT), pipeline, viewer, cards, CLI
- [x] M2 tests for every step (`pytest -q` -> 33 passed, no network)
- [x] M3 README (install, ffmpeg, 5-command quickstart) + full acceptance run
- [x] Extras verified by hand: viewer driven in headless Chromium (pinyin/underline/EN-reveal/M hotkey/
      word-selection marks all work, no JS errors); real faster-whisper `tiny` run end-to-end.

## Acceptance (all run, outputs in the session transcript)
- `pytest -q` exit 0 · `podstudy ingest tests/fixtures/sample.mp3` -> master.json + zh/en/bilingual
  .srt/.vtt, all parsed by our strict parser *and* ffmpeg · `podstudy cards` on tests/fixtures/marks.json
  -> sample.apkg with 3 notes == 3 marks, 3 mp3 files in the media map · `ruff check .` clean.

## Known gaps / fallbacks
- **YouTube download not exercised live**: yt-dlp got `HTTP 403` from this sandbox, so the downloader
  (`podstudy/download.py`) is only covered via a fake `Downloader` in tests. On a normal machine
  yt-dlp may also need a JS runtime (deno/node) for YouTube extraction.
- **No real Mandarin TTS**: edge-tts was blocked by the sandbox TLS proxy, so the sample audio is
  robotic espeak-ng Mandarin. Whisper `tiny` hallucinates on it (the pipeline itself works); the
  whisper path in tests uses a fake transcriber.
- **LLM not exercised live**: no ANTHROPIC_API_KEY here. `AnthropicProvider` is tested against a fake SDK client (prompt context, JSON gloss parsing, auto-selection); the real API was never called.
- Dependency pin: `av<17` (PyAV 19 removed `open(metadata_errors=)` which faster-whisper 1.2.1 calls).
- The YouTube embed path of the viewer (IFrame API) was not run (no network to YouTube from the browser);
  the local-audio path was.
