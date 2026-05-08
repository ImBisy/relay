#!/usr/bin/env python3
"""Relay — entrypoint.

Modes:
  --cli          run an interactive command-line REPL
  --voice        run with speech input/output (macOS only)
  --serve        run the FastAPI dashboard on the given host/port
  --setup        run the interactive setup wizard

The orchestrator does all the real work. This file only wires CLI args
to the right launcher.
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("relay")


def _setup_signals() -> None:
    def handler(_sig, _frame):
        print("\nShutting down Relay...")
        sys.exit(0)
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)


def _build_orchestrator():
    from .core.orchestrator import RelayOrchestrator
    return RelayOrchestrator()


def run_cli(orchestrator) -> None:
    print("\nRelay - CLI mode")
    print("Type a command or 'quit' to exit.\n")
    print(orchestrator.greeting())
    while True:
        try:
            text = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return
        if not text:
            continue
        if text.lower() in {"quit", "exit", "bye"}:
            return
        response = orchestrator.process_input(text, source="cli")
        print(response)


def run_voice(orchestrator, use_hotkey: bool = True) -> None:
    from .input.voice import VoiceInput
    from .output.tts import TextToSpeech

    voice = VoiceInput()
    tts = TextToSpeech()
    orchestrator.set_response_callback(lambda text: tts.speak(text))
    orchestrator.set_notification_callback(lambda text: tts.speak(text))
    tts.speak(orchestrator.greeting(), blocking=False)

    if use_hotkey:
        print("Listening for hotkey: Cmd+Shift+J")

        def on_hotkey() -> None:
            print("\nListening...")
            voice._play_beep()
            text = voice.listen_once(timeout=5.0, phrase_time_limit=10.0)
            if text:
                print(f"You: {text}")
                response = orchestrator.process_input(text, source="voice")
                print(f"Relay: {response}")

        listener = voice.listen_for_hotkey(on_hotkey)
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            if listener:
                listener.stop()
    else:
        def on_voice_input(text: str) -> None:
            print(f"You: {text}")
            response = orchestrator.process_input(text, source="voice")
            print(f"Relay: {response}")
        voice.start_continuous_listening(on_voice_input, wake_word_required=True)
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            voice.stop_listening()


def run_serve(orchestrator, host: str, port: int) -> None:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is not installed. Run: pip install fastapi uvicorn")
        sys.exit(1)
    from .frontend.dashboard import create_app
    app = create_app(orchestrator)
    print(f"Relay dashboard listening on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


def run_setup() -> None:
    from .config.settings import config

    print("\nRelay setup\n" + "=" * 30)
    name = input("Your name (optional): ").strip()
    if name:
        config.user.name = name

    api_key = input("OpenRouter API key (blank to skip): ").strip()
    if api_key:
        config.api.openrouter_api_key = api_key

    if input("Configure email? (y/n): ").lower().strip() == "y":
        email_name = input("Account label (e.g. 'Work'): ").strip()
        smtp_server = input("SMTP server: ").strip()
        smtp_port = input("SMTP port [587]: ").strip() or "587"
        username = input("Username/email: ").strip()
        password = input("Password: ").strip()
        from_addr = input("From address: ").strip()
        config.email.add_account(
            email_name, smtp_server, int(smtp_port), username, password, from_addr,
        )

    config.save()
    print(f"\nSaved to {config.config_path}")


def main() -> None:
    _setup_signals()
    parser = argparse.ArgumentParser(description="Relay — local AI assistant")
    parser.add_argument("--cli", action="store_true", help="run interactive CLI")
    parser.add_argument("--voice", action="store_true", help="run voice mode")
    parser.add_argument("--serve", action="store_true", help="run dashboard")
    parser.add_argument("--setup", action="store_true", help="setup wizard")
    parser.add_argument("--host", default="127.0.0.1", help="dashboard host")
    parser.add_argument("--port", type=int, default=8765, help="dashboard port")
    parser.add_argument("--continuous", action="store_true",
                         help="continuous listening (no hotkey)")
    args = parser.parse_args()

    if args.setup:
        run_setup()
        return

    orchestrator = _build_orchestrator()
    if args.serve:
        run_serve(orchestrator, args.host, args.port)
    elif args.voice or args.continuous:
        run_voice(orchestrator, use_hotkey=not args.continuous)
    else:
        run_cli(orchestrator)


if __name__ == "__main__":
    main()
