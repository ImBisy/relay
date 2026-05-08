"""
Text-to-speech output system.
"""
import subprocess
import threading
from typing import Optional
import logging
import shutil

logger = logging.getLogger(__name__)


class TextToSpeech:
    """
    Text-to-speech handler using macOS native 'say' command.
    
    Supports macOS native voices with appropriate rate and tone.
    """
    
    def __init__(self, rate: int = 180, voice_id: Optional[str] = None):
        """
        Initialize TTS engine.
        
        Args:
            rate: Speech rate (words per minute)
            voice_id: Specific voice ID (None for system default)
        """
        self.rate = rate
        self.voice_id = voice_id
        self._voice = self._select_best_voice()
        self._has_say = shutil.which('say') is not None
        
        if not self._has_say:
            logger.error("macOS 'say' command not found. TTS will not work.")
        else:
            logger.info(f"TTS initialized with voice: {self._voice}")
    
    def _select_best_voice(self) -> str:
        """Select the best available voice for Relay character."""
        # Preferred voices in order (British, clear, professional)
        preferred = ['Daniel', 'Oliver', 'Samantha', 'Alex', 'Victoria', 'Fred']
        
        try:
            # Get available voices
            result = subprocess.run(['say', '-v', '?'], capture_output=True, text=True)
            available = result.stdout.lower()
            
            for pref in preferred:
                if pref.lower() in available:
                    logger.info(f"Selected voice: {pref}")
                    return pref
        except Exception as e:
            logger.warning(f"Could not list voices: {e}")
        
        return ''  # Empty string uses system default
    
    def speak(self, text: str, blocking: bool = False):
        """
        Speak the given text using macOS say command.
        
        Args:
            text: Text to speak
            blocking: If True, wait until speech is complete
        """
        if not self._has_say:
            print(f"🗣️  {text}")
            return
        
        if not text:
            return
        
        def run_say():
            try:
                cmd = ['say']
                
                # Add voice if selected
                if self._voice:
                    cmd.extend(['-v', self._voice])
                
                # Add rate (say uses words per minute)
                cmd.extend(['-r', str(self.rate)])
                
                cmd.append(text)
                
                subprocess.run(cmd, check=False, capture_output=True)
            except Exception as e:
                logger.error(f"TTS error: {e}")
                print(f"🗣️  {text}")
        
        if blocking:
            run_say()
        else:
            thread = threading.Thread(target=run_say, daemon=True)
            thread.start()
    
    def stop(self):
        """Stop current speech."""
        try:
            subprocess.run(['killall', 'say'], check=False, capture_output=True)
        except Exception:
            pass
    
    def set_rate(self, rate: int):
        """Set speech rate."""
        self.rate = rate
    
    def set_volume(self, volume: float):
        """Set speech volume (0.0 to 1.0)."""
        # macOS say doesn't support volume directly
        pass
    
    def list_voices(self) -> list:
        """List available voices."""
        try:
            result = subprocess.run(['say', '-v', '?'], capture_output=True, text=True)
            voices = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split()
                    if parts:
                        voices.append({'name': parts[0], 'language': parts[1] if len(parts) > 1 else ''})
            return voices
        except Exception:
            return []
