"""Command line interface: podstudy ingest | serve | cards."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config
from .providers import StubProvider, get_provider


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="podstudy", description=__doc__)
    p.add_argument("--data-dir", default=None,
                   help="workspace dir (default ./data or $PODSTUDY_DATA)")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("ingest", help="download/transcribe/translate/annotate")
    i.add_argument("source", help="YouTube URL or local audio file")
    i.add_argument("--whisper-model", default="medium")
    i.add_argument("--translator", default="auto", choices=["auto", "anthropic", "stub", "none"])

    s = sub.add_parser("serve", help="start the local viewer")
    s.add_argument("video_id")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--host", default="127.0.0.1")

    c = sub.add_parser("cards", help="build an Anki .apkg from marks")
    c.add_argument("video_id")
    c.add_argument("--marks", default=None, help="marks.json path (default: the video's own)")
    c.add_argument("--out", default="out")
    c.add_argument("--variant", default="basic", choices=["basic", "cloze", "both"])
    c.add_argument("--llm", default="auto", choices=["auto", "anthropic", "stub"])
    c.add_argument("--anki-connect", nargs="?", const="http://127.0.0.1:8765", default=None,
                   help="also import into a running Anki via AnkiConnect")
    return p


def cmd_ingest(args: argparse.Namespace, root: Path) -> int:
    from .ingest import ingest

    provider = get_provider(args.translator)
    res = ingest(args.source, root, provider=provider, whisper_model=args.whisper_model)
    print(f"video_id: {res.master.video_id}")
    print(f"sentences: {len(res.master.sentences)} (zh: {res.master.zh_source}, "
          f"en: {res.master.en_source})")
    print(f"master: {res.master_path}")
    for f in res.sub_files:
        print(f"subs: {f}")
    for w in res.warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    return 0


def cmd_serve(args: argparse.Namespace, root: Path) -> int:
    import uvicorn

    from .server import create_app

    app = create_app(root, args.video_id)
    print(f"Viewer: http://{args.host}:{args.port}  (marks -> "
          f"{config.marks_path(root, args.video_id)})")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


def cmd_cards(args: argparse.Namespace, root: Path) -> int:
    from .cards import build_cards, push_anki_connect
    from .export import read_master
    from .marks import load_marks

    master = read_master(config.master_path(root, args.video_id))
    marks_file = Path(args.marks) if args.marks else config.marks_path(root, args.video_id)
    marks = load_marks(marks_file)
    if not marks:
        print(f"no marks found in {marks_file}", file=sys.stderr)
        return 1
    provider = get_provider(args.llm) or StubProvider()
    if provider.name == "stub":
        print("note: using offline stub glosses (set ANTHROPIC_API_KEY for real ones)",
              file=sys.stderr)
    audio = config.video_dir(root, args.video_id) / master.source["audio"]
    res = build_cards(master, marks, audio, Path(args.out), provider, args.variant)
    print(f"apkg: {res.apkg}  notes: {res.notes}  media: {len(res.media)}")
    if args.anki_connect:
        push_anki_connect(res.apkg, args.anki_connect)
        print("pushed to Anki via AnkiConnect")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = config.data_dir(args.data_dir)
    handlers = {"ingest": cmd_ingest, "serve": cmd_serve, "cards": cmd_cards}
    return handlers[args.cmd](args, root)


if __name__ == "__main__":
    sys.exit(main())
