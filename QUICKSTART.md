# Quick Start Guide

## 1. Installation

```bash
# Navigate to project
cd /Users/charlieichikowitz/CascadeProjects/relay

# Install dependencies
pip install -r requirements.txt
```

## 2. Initial Setup

```bash
# Run the setup wizard
python -m src.main --setup
```

This will prompt you for:

- Your name (optional)
- OpenRouter API key (optional but recommended)
- Email configuration (optional)

## 3. Running Relay

### CLI Mode (Text Input)

Best for testing and development:

```bash
python -m src.main --cli
```

### Voice Mode with Hotkey

Press `Cmd+Shift+J` to activate:

```bash
python -m src.main --voice
```

### Voice Mode (Continuous)

Say "Relay" to wake:

```bash
python -m src.main --voice --continuous
```

## 4. First Commands

Try these in CLI mode first:

```
> remind me to take a break in 30 minutes
> take a note: meeting with team at 3pm
> set a 5 minute timer
> open Safari
> what's on my calendar today
```

## 5. Common Issues

### Microphone Access

If voice mode doesn't work:

1. Go to System Preferences → Security & Privacy → Privacy → Microphone
2. Check that Terminal (or your IDE) has microphone access

### Hotkey Not Working

If `Cmd+Shift+J` doesn't trigger:

1. Go to System Preferences → Security & Privacy → Privacy → Accessibility
2. Add Terminal (or your IDE) to the list

### Missing Dependencies

If you get import errors:

```bash
pip install --upgrade -r requirements.txt
```

### PyAudio Issues on macOS

If `pip install pyaudio` fails:

```bash
brew install portaudio
pip install pyaudio
```

## 6. Configuration

Edit `~/.relay/config.json` directly for advanced settings:

```bash
# Open config in default editor
open ~/.relay/config.json
```

## 7. Test Your Setup

```bash
# Run component tests
python test_relay.py
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Customize your email aliases in the config
- Set up OpenRouter for AI-powered queries
- Explore all available commands
