# Relay - macOS AI Assistant

A calm, intelligent, voice-driven AI assistant that acts as a personal operator for macOS. Built with an OpenClaw-inspired architecture and OpenRouter as the fallback reasoning layer.

## Overview

Relay provides a frictionless voice-controlled experience for managing communication, scheduling, and tasks. The system prioritizes speed, clarity, and low cognitive load for the user.

### Key Features

- **Voice-First Interface**: Speak naturally, get results immediately
- **Email Management**: Draft and send emails with confirmation safeguards
- **Calendar Integration**: Natural language scheduling ("tomorrow afternoon")
- **Reminders & Tasks**: Quick capture from speech
- **Notes**: Fast append-only idea capture
- **Timers**: Simple countdown management
- **System Control**: Volume, apps, sleep, lock
- **Web Search**: Quick browser integration
- **AI Queries**: General knowledge through OpenRouter

## Architecture

```
Voice Input → Speech-to-Text → Intent Parser → Action Router → Tool Execution → Response
```

### Components

| Component           | Purpose                                                      |
| ------------------- | ------------------------------------------------------------ |
| `VoiceInput`        | Speech recognition and hotkey handling                       |
| `IntentParser`      | Rule-based parsing with OpenRouter fallback                  |
| `RelayOrchestrator` | Main coordination and routing                                |
| `PersonalityEngine` | Relay response generation                                    |
| `Tools`             | Email, Calendar, Reminders, Notes, Timer, System, Web, Query |
| `OpenRouterClient`  | Complex reasoning and LLM tasks                              |
| `TextToSpeech`      | Voice output                                                 |

## Installation

### Prerequisites

- macOS 10.15+
- Python 3.9+
- Microphone access

### Setup

```bash
# Clone repository
cd /Users/charlieichikowitz/CascadeProjects/relay

# Install dependencies
pip install -r requirements.txt

# Run setup wizard
python -m src.main --setup
```

### macOS Permissions

Grant the following permissions in **System Preferences → Security & Privacy**:

- **Microphone** - For voice input
- **Accessibility** - For hotkey detection
- **Automation** - For system control features

## Usage

### CLI Mode (Development/Testing)

```bash
python -m src.main --cli
```

### Voice Mode with Hotkey

```bash
python -m src.main --voice
# Press Cmd+Shift+J to activate
```

### Voice Mode (Continuous)

```bash
python -m src.main --voice --continuous
# Say "Relay" to wake, then speak your command
```

## Commands

### Email

```
"Send an email to Work Email saying the meeting is moved to 3pm"
"Draft an email to John about the project update"
"Email my boss that I'll be late"
```

### Calendar

```
"Schedule a meeting with the team tomorrow at 2pm"
"Add dentist appointment for next Tuesday morning"
"What's on my calendar today?"
"Show my schedule for tomorrow"
```

### Reminders

```
"Remind me to call Mom at 5pm"
"Don't let me forget to buy milk"
"Remind me in 30 minutes to take a break"
```

### Notes

```
"Take a note: The API key is in the shared folder"
"Note that I need to review the design mockups"
"Jot down: Call Sarah about the contract"
```

### Timer

```
"Set a 12 minute timer"
"Timer for 2 hours"
"Stop timer"
"How much time is left?"
```

### System

```
"Open Safari"
"Close Chrome"
"Volume up"
"Mute"
"Lock screen"
"Put computer to sleep"
```

### Web

```
"Search for python datetime documentation"
"Open Gmail"
"Look up weather in San Francisco"
```

### Queries (requires OpenRouter)

```
"What's the capital of Norway?"
"How do I make sourdough bread?"
"Explain quantum computing simply"
```

## Configuration

Configuration is stored in `~/.relay/config.json`:

```json
{
	"email": {
		"accounts": {
			"Work": {
				"smtp_server": "smtp.gmail.com",
				"smtp_port": 587,
				"username": "user@gmail.com",
				"password": "...",
				"from_address": "user@gmail.com"
			}
		}
	},
	"api": {
		"openrouter_api_key": "...",
		"openrouter_model": "anthropic/claude-3.5-sonnet"
	},
	"voice": {
		"wake_word": "relay",
		"hotkey": "cmd+shift+j"
	},
	"user": {
		"name": "Your Name",
		"timezone": "America/New_York"
	}
}
```

## Safety & Confirmation

### Always Requires Confirmation

- **Email sending** - Recipient and content shown before sending

### No Confirmation Required

- Calendar events (unless ambiguous)
- Reminders
- Notes
- Timers

### Low Confidence Handling

If confidence < 0.7, Relay asks for clarification before acting.

## Personality

Relay speaks with:

- **Calm composure** - Never rushed or frantic
- **Efficiency** - Brief, informative responses
- **Subtle wit** - Occasional dry humor (rare, never disruptive)

Examples:

- "Done. I've scheduled that for you."
- "Email drafted. Waiting for your confirmation before sending."
- "That's... an interesting way to phrase it. I'll handle it anyway."

## Development

### Project Structure

```
relay/
├── src/
│   ├── agents/          # OpenRouter client
│   ├── config/          # Settings management
│   ├── core/            # Main orchestrator
│   ├── input/           # Voice input (STT)
│   ├── intent/          # Intent parsing
│   ├── output/          # TTS
│   ├── personality/     # Response generation
│   ├── tools/           # Tool implementations
│   └── main.py          # Entry point
├── requirements.txt
└── README.md
```

### Adding New Tools

1. Create tool class in `src/tools/`
2. Inherit from `BaseTool`
3. Implement `execute()` and `validate()`
4. Register in `RelayOrchestrator._init_tools()`

### Testing

```bash
# Test specific tool
python -c "from src.tools.email import EmailTool; ..."

# Test intent parsing
python -c "from src.intent.parser import IntentParser; ..."
```

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- Built with [SpeechRecognition](https://github.com/Uberi/speech_recognition)
- TTS via [pyttsx3](https://github.com/nateshmbhat/pyttsx3)
- LLM reasoning via [OpenRouter](https://openrouter.ai/)
- Inspired by OpenClaw architecture principles
