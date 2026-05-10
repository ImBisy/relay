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

Relay is **code-first, tool-driven, and deterministic**. The only place
natural language is *interpreted* is the schema-based intent extractor
(Instructor + Pydantic, fast model). Tool dispatch, confirmations, and
persistence happen on the structured output — not on the model.

```
Input → IntentExtractor (LLM, fast) → typed Intent objects
      → Router (code) → ActionPlan → Tool(s) → Storage → Response
                                          ↳ (optional) Content polish via LLM
```

### Two-model strategy

| Model       | Used for                                              | Default                              |
| ----------- | ----------------------------------------------------- | ------------------------------------ |
| Fast model  | Intent extraction / routing                           | `qwen/qwen-2.5-7b-instruct:free`     |
| Slow model  | Content polish (email body / subject, notes), chat    | `anthropic/claude-3.5-sonnet`        |

The fast model never picks tools; the slow model never picks tools.
When no API key is configured the extractor falls back to a small
deterministic keyword classifier so the assistant remains usable
offline.

### Components

| Component             | Purpose                                                              |
| --------------------- | -------------------------------------------------------------------- |
| `IntentExtractor`     | Fast LLM → typed `Intent` objects (with offline fallback)            |
| `Router`              | Deterministic routing — confirmation / cancellation / chat / command |
| `ActionPlan`          | Multi-step plan (e.g. "send email and take a note")                  |
| `ToolRegistry`        | Lookup of tools by name / alias                                      |
| `Tools`               | Email, Calendar, Reminders, Notes, Timer, System, Web, Query         |
| `Storage` (SQLite)    | Reminders, notes, calendar, action logs, pending actions             |
| `PendingActionsStore` | Structured confirmation records (no in-process callbacks)            |
| `ContentEngine`       | Optional LLM polish for emails / reminders / notes                   |
| `ChatService`         | Isolated boundary for general LLM conversation                       |
| `RelayOrchestrator`   | Thin coordinator — dispatch, log, render                             |
| `PersonalityEngine`   | Renders structured results into calm, concise replies                |
| `Frontend dashboard`  | FastAPI dashboard at `/` for browsing reminders / notes / logs       |

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

### Dashboard

```bash
python -m src.main --serve
# Open http://127.0.0.1:7474 to browse reminders, notes, logs and pending actions
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

Configuration is stored in two places:

1. **`.env` at the repo root** (recommended for keys). Copy
   `.env.example` to `.env` and fill in `OPENROUTER_API_KEY`. The
   same key is reused by every LLM-backed subsystem (intent
   extractor, chat, content polish).
2. **`~/.relay/config.json`** for email accounts and per-machine
   overrides:

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
		"fast_model": "qwen/qwen-2.5-7b-instruct:free",
		"slow_model": "anthropic/claude-3.5-sonnet"
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
│   ├── chat/            # Free-form chat boundary
│   ├── config/          # Settings + .env loader
│   ├── content/         # Optional LLM polish (slow model)
│   ├── core/            # Router, orchestrator, action plans
│   ├── frontend/        # FastAPI dashboard
│   ├── input/           # Voice input (STT)
│   ├── llm/             # Schema-based intent extraction (fast model)
│   ├── output/          # TTS
│   ├── personality/     # Response renderer
│   ├── storage/         # SQLite stores + models
│   ├── tools/           # Tool implementations
│   └── main.py          # Entry point
├── tests/
├── .env.example
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
pytest tests/ -q
```

## License

MIT License - See LICENSE file for details.

## Acknowledgments

- Built with [SpeechRecognition](https://github.com/Uberi/speech_recognition)
- TTS via [pyttsx3](https://github.com/nateshmbhat/pyttsx3)
- LLM reasoning via [OpenRouter](https://openrouter.ai/)
- Inspired by OpenClaw architecture principles
