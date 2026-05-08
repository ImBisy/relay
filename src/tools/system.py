"""
System control tool for macOS commands.
"""
import subprocess
import platform
from typing import Dict, Any, Optional, List
from .base import BaseTool, ToolResult


class SystemTool(BaseTool):
    """
    System control tool for macOS.
    
    Supports:
    - Opening/closing applications
    - Volume control
    - Screen brightness
    - System sleep/lock
    """
    
    name = "system"
    description = "Control macOS system functions"
    requires_confirmation = False
    
    # macOS app name mappings
    APP_ALIASES = {
        'safari': 'Safari',
        'chrome': 'Google Chrome',
        'firefox': 'Firefox',
        'mail': 'Mail',
        'messages': 'Messages',
        'slack': 'Slack',
        'spotify': 'Spotify',
        'music': 'Music',
        'itunes': 'Music',
        'notes': 'Notes',
        'reminders': 'Reminders',
        'calendar': 'Calendar',
        'finder': 'Finder',
        'terminal': 'Terminal',
        'code': 'Visual Studio Code',
        'vscode': 'Visual Studio Code',
    }
    
    def execute(self, entities: Dict[str, Any]) -> ToolResult:
        """Execute system command."""
        command = entities.get('command')
        
        if not command:
            return ToolResult.failure("No system command specified")
        
        handlers = {
            'volume_up': self._volume_up,
            'volume_down': self._volume_down,
            'volume_set': self._volume_set,
            'mute': self._mute,
            'unmute': self._unmute,
            'open_app': self._open_app,
            'close_app': self._close_app,
            'sleep': self._sleep,
            'lock': self._lock_screen,
            'restart': self._restart,
            'shutdown': self._shutdown,
        }
        
        handler = handlers.get(command)
        if not handler:
            return ToolResult.failure(f"Unknown command: {command}")
        
        return handler(entities)
    
    def _volume_up(self, entities: Dict[str, Any]) -> ToolResult:
        """Increase system volume."""
        try:
            subprocess.run(
                ['osascript', '-e', 'set volume output volume (output volume of (get volume settings) + 10)'],
                capture_output=True,
                check=True
            )
            return ToolResult.success("Volume increased.")
        except subprocess.CalledProcessError as e:
            return ToolResult.failure("Could not adjust volume", error=str(e))
    
    def _volume_down(self, entities: Dict[str, Any]) -> ToolResult:
        """Decrease system volume."""
        try:
            subprocess.run(
                ['osascript', '-e', 'set volume output volume (output volume of (get volume settings) - 10)'],
                capture_output=True,
                check=True
            )
            return ToolResult.success("Volume decreased.")
        except subprocess.CalledProcessError as e:
            return ToolResult.failure("Could not adjust volume", error=str(e))
    
    def _volume_set(self, entities: Dict[str, Any]) -> ToolResult:
        """Set system volume to specific level."""
        level = entities.get('level', 50)
        level = max(0, min(100, level))  # Clamp to 0-100
        
        try:
            subprocess.run(
                ['osascript', '-e', f'set volume output volume {level}'],
                capture_output=True,
                check=True
            )
            return ToolResult.success(f"Volume set to {level}%.")
        except subprocess.CalledProcessError as e:
            return ToolResult.failure("Could not set volume", error=str(e))
    
    def _mute(self, entities: Dict[str, Any]) -> ToolResult:
        """Mute system audio."""
        try:
            subprocess.run(
                ['osascript', '-e', 'set volume with output muted'],
                capture_output=True,
                check=True
            )
            return ToolResult.success("Muted.")
        except subprocess.CalledProcessError as e:
            return ToolResult.failure("Could not mute", error=str(e))
    
    def _unmute(self, entities: Dict[str, Any]) -> ToolResult:
        """Unmute system audio."""
        try:
            subprocess.run(
                ['osascript', '-e', 'set volume without output muted'],
                capture_output=True,
                check=True
            )
            return ToolResult.success("Unmuted.")
        except subprocess.CalledProcessError as e:
            return ToolResult.failure("Could not unmute", error=str(e))
    
    def _open_app(self, entities: Dict[str, Any]) -> ToolResult:
        """Open an application."""
        app_name = entities.get('app_name')
        
        if not app_name:
            return ToolResult.failure("No application specified")
        
        # Resolve alias
        app_name_lower = app_name.lower()
        resolved_name = self.APP_ALIASES.get(app_name_lower, app_name)
        
        try:
            subprocess.run(
                ['open', '-a', resolved_name],
                capture_output=True,
                check=True
            )
            return ToolResult.success(f"Opened {resolved_name}.")
        except subprocess.CalledProcessError as e:
            # Try with .app suffix
            try:
                subprocess.run(
                    ['open', '-a', f"{resolved_name}.app"],
                    capture_output=True,
                    check=True
                )
                return ToolResult.success(f"Opened {resolved_name}.")
            except subprocess.CalledProcessError:
                return ToolResult.failure(f"Could not open {resolved_name}. Is it installed?", error=str(e))
    
    def _close_app(self, entities: Dict[str, Any]) -> ToolResult:
        """Close an application."""
        app_name = entities.get('app_name')
        
        if not app_name:
            return ToolResult.failure("No application specified")
        
        # Resolve alias
        app_name_lower = app_name.lower()
        resolved_name = self.APP_ALIASES.get(app_name_lower, app_name)
        
        try:
            # AppleScript to quit app
            script = f'tell application "{resolved_name}" to quit'
            subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                check=True
            )
            return ToolResult.success(f"Closed {resolved_name}.")
        except subprocess.CalledProcessError as e:
            return ToolResult.failure(f"Could not close {resolved_name}", error=str(e))
    
    def _sleep(self, entities: Dict[str, Any]) -> ToolResult:
        """Put system to sleep."""
        try:
            subprocess.run(
                ['osascript', '-e', 'tell application "System Events" to sleep'],
                capture_output=True,
                check=True
            )
            return ToolResult.success("Going to sleep.")
        except subprocess.CalledProcessError as e:
            return ToolResult.failure("Could not sleep system", error=str(e))
    
    def _lock_screen(self, entities: Dict[str, Any]) -> ToolResult:
        """Lock the screen."""
        try:
            # Using the lock screen command
            subprocess.run(
                ['/usr/bin/pmset', 'displaysleepnow'],
                capture_output=True,
                check=False  # May not exist on all systems
            )
            
            # Alternative: activate screensaver
            subprocess.run(
                ['open', '-a', 'ScreenSaverEngine'],
                capture_output=True,
                check=False
            )
            
            return ToolResult.success("Screen locked.")
        except Exception as e:
            return ToolResult.failure("Could not lock screen", error=str(e))
    
    def _restart(self, entities: Dict[str, Any]) -> ToolResult:
        """Restart the system."""
        try:
            subprocess.run(
                ['osascript', '-e', 'tell application "System Events" to restart'],
                capture_output=True,
                check=True
            )
            return ToolResult.success("Restarting system.")
        except subprocess.CalledProcessError as e:
            return ToolResult.failure("Could not restart system", error=str(e))
    
    def _shutdown(self, entities: Dict[str, Any]) -> ToolResult:
        """Shut down the system."""
        try:
            subprocess.run(
                ['osascript', '-e', 'tell application "System Events" to shut down'],
                capture_output=True,
                check=True
            )
            return ToolResult.success("Shutting down.")
        except subprocess.CalledProcessError as e:
            return ToolResult.failure("Could not shut down system", error=str(e))
    
    def validate(self, entities: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate system command entities."""
        command = entities.get('command')
        
        if not command:
            return False, "System command required"
        
        valid_commands = [
            'volume_up', 'volume_down', 'volume_set', 'mute', 'unmute',
            'open_app', 'close_app', 'sleep', 'lock', 'restart', 'shutdown'
        ]
        
        if command not in valid_commands:
            return False, f"Unknown command: {command}"
        
        # Check for required app_name
        if command in ['open_app', 'close_app'] and not entities.get('app_name'):
            return False, "Application name required"
        
        return True, None
