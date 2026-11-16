# PROGRESS

## Milestones
- [x] M1 scaffold, fixtures (espeak-ng 20s sample + aligned zh/en SRT), pipeline modules, CLI
- [ ] M2 tests for every step
- [ ] M3 README + acceptance run

## Known gaps / fallbacks
- Real Mandarin TTS (edge-tts) was blocked by the sandbox TLS proxy; the sample audio is
  espeak-ng Mandarin (robotic). Subtitle timings are measured from the generated audio.
- No ANTHROPIC_API_KEY in the sandbox: LLM translation/glosses are tested with the offline
  `StubProvider`; `AnthropicProvider` is implemented but not exercised against the live API.
