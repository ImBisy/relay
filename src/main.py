#!/usr/bin/env python3
"""
Relay - macOS AI Assistant

A calm, voice-driven AI assistant that acts as a personal operator.
Uses OpenClaw-inspired architecture with OpenRouter as reasoning fallback.
"""

import sys
import signal
import logging
import argparse
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('relay')


def setup_signal_handlers():
    """Setup graceful shutdown handlers."""
    def signal_handler(sig, frame):
        print("\nShutting down Relay...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def run_cli_mode(orchestrator):
    """Run in CLI mode for testing."""
    print("\n🤖 Relay - CLI Mode")
    print("Type your command or 'quit' to exit\n")
    
    # Print greeting
    print(f"🎙️  {orchestrator.greeting()}")
    
    while True:
        try:
            user_input = input("\n> ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("Goodbye.")
                break
            
            # Process input
            response = orchestrator.process_input(user_input)
            print(f"🎙️  {response}")
            
        except KeyboardInterrupt:
            print("\nGoodbye.")
            break
        except EOFError:
            break


def run_voice_mode(orchestrator, use_hotkey: bool = True):
    """Run in voice mode with speech input and output."""
    from .input.voice import VoiceInput
    from .output.tts import TextToSpeech
    
    print("\n🤖 Relay - Voice Mode")
    print("Press Ctrl+C to exit\n")
    
    # Initialize components
    voice = VoiceInput()
    tts = TextToSpeech()
    
    # Setup callbacks
    orchestrator.set_response_callback(lambda text: tts.speak(text))
    orchestrator.set_notification_callback(lambda text: tts.speak(text))
    
    # Greeting
    tts.speak(orchestrator.greeting(), blocking=False)
    
    if use_hotkey:
        # Setup hotkey-triggered listening
        print(f"Listening for hotkey: Cmd+Shift+J")
        
        def on_hotkey():
            print("\n🎤 Listening...")
            voice._play_beep()
            text = voice.listen_once(timeout=5.0, phrase_time_limit=10.0)
            if text:
                print(f"🗣️  {text}")
                response = orchestrator.process_input(text)
                print(f"🎙️  {response}")
        
        listener = voice.listen_for_hotkey(on_hotkey)
        
        # Keep running
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            if listener:
                listener.stop()
    else:
        # Continuous listening mode
        print("Starting continuous listening...")
        
        def on_voice_input(text):
            print(f"🗣️  {text}")
            response = orchestrator.process_input(text)
            print(f"🎙️  {response}")
        
        voice.start_continuous_listening(on_voice_input, wake_word_required=True)
        
        # Keep running
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            voice.stop_listening()


def run_setup_wizard():
    """Run interactive setup wizard."""
    from .config.settings import config
    
    print("\n🤖 Relay Setup Wizard")
    print("=" * 40)
    
    # User info
    print("\n1. User Information")
    name = input("Your name (optional): ").strip()
    if name:
        config.user.name = name
    
    # OpenRouter API key
    print("\n2. OpenRouter Configuration (for AI reasoning)")
    api_key = input("OpenRouter API key (leave blank to skip): ").strip()
    if api_key:
        config.api.openrouter_api_key = api_key
        print("✓ OpenRouter configured")
    else:
        print("⚠️  OpenRouter not configured - some features will be limited")
    
    # Email configuration
    print("\n3. Email Configuration (optional)")
    setup_email = input("Configure email? (y/n): ").lower().strip() == 'y'
    
    if setup_email:
        email_name = input("Email account name (e.g., 'Work', 'Personal'): ").strip()
        smtp_server = input("SMTP server: ").strip()
        smtp_port = input("SMTP port [587]: ").strip() or "587"
        username = input("Username/email: ").strip()
        password = input("Password: ").strip()
        from_addr = input("From address: ").strip()
        
        config.email.add_account(
            email_name, smtp_server, int(smtp_port),
            username, password, from_addr
        )
        print(f"✓ Email account '{email_name}' configured")
    
    # Save configuration
    config.save()
    print("\n✓ Configuration saved!")
    print(f"Config location: {config.config_path}")


def main():
    """Main entry point."""
    setup_signal_handlers()
    
    parser = argparse.ArgumentParser(description='Relay - macOS AI Assistant')
    parser.add_argument('--cli', action='store_true', 
                       help='Run in CLI mode (text input)')
    parser.add_argument('--voice', action='store_true',
                       help='Run in voice mode (speech input/output)')
    parser.add_argument('--setup', action='store_true',
                       help='Run setup wizard')
    parser.add_argument('--hotkey', action='store_true', default=True,
                       help='Use hotkey trigger (default: True)')
    parser.add_argument('--continuous', action='store_true',
                       help='Use continuous listening (no hotkey)')
    
    args = parser.parse_args()
    
    if args.setup:
        run_setup_wizard()
        return
    
    # Import orchestrator after potential setup
    from .core.orchestrator import RelayOrchestrator
    orchestrator = RelayOrchestrator()
    
    # Register web and query tools
    from .tools.web import WebTool
    from .tools.query import QueryTool
    from .agents.openrouter import OpenRouterClient
    from .config.settings import config
    
    orchestrator.tools['web'] = WebTool()
    
    if config.api.openrouter_api_key:
        openrouter = OpenRouterClient(api_key=config.api.openrouter_api_key)
        orchestrator.tools['query'] = QueryTool(openrouter)
    
    if args.cli:
        run_cli_mode(orchestrator)
    elif args.voice or args.continuous:
        use_hotkey = not args.continuous
        run_voice_mode(orchestrator, use_hotkey=use_hotkey)
    else:
        # Default to CLI if no mode specified
        run_cli_mode(orchestrator)


if __name__ == '__main__':
    main()
