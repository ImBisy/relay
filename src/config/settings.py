"""Configuration management for Relay.

Configuration sources, in order of precedence (highest first):

1. environment variables
2. ``.env`` at the repo root (loaded via python-dotenv)
3. ``~/.relay/config.json`` (legacy / per-machine overrides)
4. defaults

A single ``OPENROUTER_API_KEY`` is reused by every LLM-backed
subsystem in Relay (intent extractor, chat service, content engine).
``OPENROUTER_FAST_MODEL`` is used for routing/extraction — it must
feel instant. ``OPENROUTER_SLOW_MODEL`` is reserved for content polish
only.
"""
import os
from dataclasses import dataclass, field
from typing import Dict, Optional
from pathlib import Path
import json

try:
    from dotenv import load_dotenv

    # Load `.env` from the repo root if it exists. ``override=False``
    # so real environment variables always win.
    _REPO_ROOT = Path(__file__).resolve().parents[2]
    load_dotenv(_REPO_ROOT / ".env", override=False)
except ImportError:  # pragma: no cover - dotenv is optional at runtime
    pass


DEFAULT_FAST_MODEL = "qwen/qwen-2.5-7b-instruct:free"
DEFAULT_SLOW_MODEL = "anthropic/claude-3.5-sonnet"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass
class EmailConfig:
    """Email account configurations."""
    accounts: Dict[str, Dict[str, str]] = field(default_factory=dict)
    
    def add_account(self, name: str, smtp_server: str, smtp_port: int, 
                    username: str, password: str, from_address: str):
        self.accounts[name] = {
            "smtp_server": smtp_server,
            "smtp_port": smtp_port,
            "username": username,
            "password": password,
            "from_address": from_address
        }


@dataclass
class APIConfig:
    """OpenRouter / LLM endpoint configuration.

    The same key works for the fast model (routing/extraction) and the
    slow model (content polish). They differ only in which model id is
    requested.
    """
    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = DEFAULT_BASE_URL
    # ``openrouter_model`` mirrors ``slow_model`` for backward
    # compatibility — the legacy code path used the slow model for
    # everything.
    openrouter_model: str = DEFAULT_SLOW_MODEL
    fast_model: str = DEFAULT_FAST_MODEL
    slow_model: str = DEFAULT_SLOW_MODEL

    def __post_init__(self):
        if not self.openrouter_api_key:
            self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        env_base = os.getenv("OPENROUTER_BASE_URL")
        if env_base:
            self.openrouter_base_url = env_base
        env_fast = os.getenv("OPENROUTER_FAST_MODEL")
        if env_fast:
            self.fast_model = env_fast
        env_slow = os.getenv("OPENROUTER_SLOW_MODEL")
        if env_slow:
            self.slow_model = env_slow
            self.openrouter_model = env_slow


@dataclass
class VoiceConfig:
    """Voice and audio settings."""
    wake_word: str = "relay"
    hotkey: str = "cmd+shift+j"
    speech_rate: int = 180
    voice_id: Optional[str] = None
    input_device: Optional[int] = None


@dataclass
class UserPreferences:
    """User-specific preferences."""
    name: Optional[str] = None
    timezone: str = "America/New_York"
    date_format: str = "%Y-%m-%d"
    time_format: str = "%I:%M %p"


class Config:
    """Main configuration manager."""
    
    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            config_dir = os.path.expanduser("~/.relay")
        
        self.config_path = Path(config_dir)
        self.config_path.mkdir(exist_ok=True)
        
        self.config_file = self.config_path / "config.json"
        
        self.email = EmailConfig()
        self.api = APIConfig()
        self.voice = VoiceConfig()
        self.user = UserPreferences()
        
        self._load()
    
    def _load(self):
        """Load configuration from file."""
        if not self.config_file.exists():
            return
        
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
            
            if 'email' in data:
                self.email.accounts = data['email'].get('accounts', {})
            if 'api' in data:
                # Don't clobber an env-provided key with a stale file value.
                if not self.api.openrouter_api_key:
                    self.api.openrouter_api_key = data['api'].get('openrouter_api_key')
                self.api.openrouter_model = data['api'].get('openrouter_model', self.api.openrouter_model)
                self.api.fast_model = data['api'].get('fast_model', self.api.fast_model)
                self.api.slow_model = data['api'].get('slow_model', self.api.slow_model)
            if 'voice' in data:
                self.voice.wake_word = data['voice'].get('wake_word', self.voice.wake_word)
                self.voice.hotkey = data['voice'].get('hotkey', self.voice.hotkey)
            if 'user' in data:
                self.user.name = data['user'].get('name')
                self.user.timezone = data['user'].get('timezone', self.user.timezone)
        except Exception as e:
            print(f"Error loading config: {e}")
    
    def save(self):
        """Save configuration to file."""
        data = {
            'email': {'accounts': self.email.accounts},
            'api': {
                'openrouter_api_key': self.api.openrouter_api_key,
                'openrouter_model': self.api.openrouter_model,
                'fast_model': self.api.fast_model,
                'slow_model': self.api.slow_model,
            },
            'voice': {
                'wake_word': self.voice.wake_word,
                'hotkey': self.voice.hotkey
            },
            'user': {
                'name': self.user.name,
                'timezone': self.user.timezone
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_data_dir(self) -> Path:
        """Get data directory for storing notes, reminders, etc."""
        data_dir = self.config_path / "data"
        data_dir.mkdir(exist_ok=True)
        return data_dir


# Global config instance
config = Config()
