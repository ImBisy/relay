"""
Configuration management for Relay Assistant.
"""
import os
from dataclasses import dataclass, field
from typing import Dict, Optional
from pathlib import Path
import json


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
    """API keys and endpoints."""
    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "anthropic/claude-3.5-sonnet"
    
    def __post_init__(self):
        if not self.openrouter_api_key:
            self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")


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
                self.api.openrouter_api_key = data['api'].get('openrouter_api_key')
                self.api.openrouter_model = data['api'].get('openrouter_model', self.api.openrouter_model)
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
                'openrouter_model': self.api.openrouter_model
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
