"""
Voice input system for speech-to-text.
"""
import speech_recognition as sr
import threading
from typing import Optional, Callable, List
import logging

logger = logging.getLogger(__name__)


class VoiceInput:
    """
    Voice input handler using speech_recognition library.
    
    Supports continuous listening and hotkey-triggered activation.
    """
    
    def __init__(self, 
                 device_index: Optional[int] = None,
                 wake_word: Optional[str] = None,
                 ambient_noise_duration: float = 1.0):
        """
        Initialize voice input.
        
        Args:
            device_index: Audio device index (None for default)
            wake_word: Optional wake word to trigger listening
            ambient_noise_duration: Seconds to sample for ambient noise adjustment
        """
        self.device_index = device_index
        self.wake_word = wake_word
        self.ambient_noise_duration = ambient_noise_duration
        
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone(device_index=device_index)
        
        self._is_listening = False
        self._listen_thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[str], None]] = None
        
        # Adjust for ambient noise
        self._calibrate()
    
    def _calibrate(self):
        """Calibrate recognizer for ambient noise."""
        try:
            with self.microphone as source:
                logger.info(f"Calibrating for ambient noise ({self.ambient_noise_duration}s)...")
                self.recognizer.adjust_for_ambient_noise(
                    source, 
                    duration=self.ambient_noise_duration
                )
                logger.info("Calibration complete.")
        except Exception as e:
            logger.warning(f"Could not calibrate microphone: {e}")
    
    def listen_once(self, timeout: Optional[float] = None,
                    phrase_time_limit: Optional[float] = None) -> Optional[str]:
        """
        Listen for a single utterance.
        
        Args:
            timeout: Maximum seconds to wait for audio (None for no timeout)
            phrase_time_limit: Maximum seconds for a phrase
            
        Returns:
            Transcribed text or None if failed
        """
        try:
            with self.microphone as source:
                logger.debug("Listening...")
                audio = self.recognizer.listen(source, timeout=timeout, 
                                               phrase_time_limit=phrase_time_limit)
            
            logger.debug("Recognizing...")
            text = self.recognizer.recognize_google(audio)
            logger.info(f"Heard: {text}")
            return text
            
        except sr.WaitTimeoutError:
            logger.debug("Listen timeout - no speech detected")
            return None
        except sr.UnknownValueError:
            logger.debug("Could not understand audio")
            return None
        except sr.RequestError as e:
            logger.error(f"Speech recognition service error: {e}")
            return None
    
    def start_continuous_listening(self, callback: Callable[[str], None],
                                   wake_word_required: bool = True):
        """
        Start continuous background listening.
        
        Args:
            callback: Function to call with recognized text
            wake_word_required: If True, only trigger on wake word detection
        """
        if self._is_listening:
            logger.warning("Already listening")
            return
        
        self._callback = callback
        self._is_listening = True
        
        def listen_loop():
            while self._is_listening:
                try:
                    text = self.listen_once(timeout=None, phrase_time_limit=5.0)
                    
                    if text:
                        if wake_word_required and self.wake_word:
                            if self.wake_word.lower() in text.lower():
                                # Wake word detected, strip it and use rest as command
                                logger.info("Wake word detected, processing command...")
                                self._play_beep()
                                # Remove wake word and clean up
                                command = text.lower().replace(self.wake_word.lower(), "").strip()
                                # Remove leading punctuation
                                command = command.lstrip(",.:;-'\" ")
                                if command:
                                    self._callback(command)
                                else:
                                    # Wake word only, listen for more
                                    command = self.listen_once(timeout=5.0, phrase_time_limit=10.0)
                                    if command:
                                        self._callback(command)
                        else:
                            self._callback(text)
                            
                except Exception as e:
                    logger.error(f"Error in listen loop: {e}")
        
        self._listen_thread = threading.Thread(target=listen_loop, daemon=True)
        self._listen_thread.start()
        logger.info("Continuous listening started")
    
    def _play_beep(self):
        """Play a short beep to indicate listening started."""
        try:
            import os
            os.system('afplay /System/Library/Sounds/Glass.aiff')
        except Exception:
            pass  # Ignore beep errors

    def stop_listening(self):
        """Stop continuous listening."""
        self._is_listening = False
        if self._listen_thread:
            self._listen_thread.join(timeout=2.0)
        logger.info("Listening stopped")
    
    def listen_for_hotkey(self, hotkey_callback: Callable[[], None]):
        """
        Set up hotkey-triggered listening (platform-specific).
        
        On macOS, this uses pynput for global hotkey detection.
        """
        try:
            from pynput import keyboard
            
            # Default hotkey: Cmd+Shift+J
            hotkey = keyboard.HotKey(
                keyboard.HotKey.parse('<cmd>+<shift>+j'),
                on_activate=hotkey_callback
            )
            
            def on_press(key):
                hotkey.press(key)
            
            def on_release(key):
                hotkey.release(key)
            
            listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            listener.daemon = True
            listener.start()
            
            logger.info("Hotkey listener started (Cmd+Shift+J)")
            return listener
            
        except ImportError:
            logger.error("pynput not installed. Hotkey listening not available.")
            return None
    
    @staticmethod
    def list_microphones() -> List[tuple[int, str]]:
        """List available microphones."""
        microphones = []
        for index, name in enumerate(sr.Microphone.list_microphone_names()):
            microphones.append((index, name))
        return microphones
