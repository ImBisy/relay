"""
Base tool interface for the assistant.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class ToolResultStatus(Enum):
    """Status of tool execution."""
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"
    CANCELLED = "cancelled"
    NEEDS_CONFIRMATION = "needs_confirmation"


@dataclass
class ToolResult:
    """Result of tool execution."""
    status: ToolResultStatus
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    requires_confirmation: bool = False
    confirmation_prompt: Optional[str] = None
    
    @classmethod
    def success(cls, message: str, data: Optional[Dict[str, Any]] = None) -> "ToolResult":
        return cls(status=ToolResultStatus.SUCCESS, message=message, data=data)
    
    @classmethod
    def failure(cls, message: str, error: Optional[str] = None) -> "ToolResult":
        return cls(status=ToolResultStatus.FAILURE, message=message, error=error)
    
    @classmethod
    def pending(cls, message: str, data: Optional[Dict[str, Any]] = None) -> "ToolResult":
        return cls(status=ToolResultStatus.PENDING, message=message, data=data)
    
    @classmethod
    def needs_confirmation(cls, message: str, prompt: str, 
                          data: Optional[Dict[str, Any]] = None) -> "ToolResult":
        return cls(
            status=ToolResultStatus.NEEDS_CONFIRMATION,
            message=message,
            data=data,
            requires_confirmation=True,
            confirmation_prompt=prompt
        )


class BaseTool(ABC):
    """Base class for all tools."""
    
    name: str = ""
    description: str = ""
    requires_confirmation: bool = False
    
    @abstractmethod
    def execute(self, entities: Dict[str, Any]) -> ToolResult:
        """
        Execute the tool with given entities.
        
        Args:
            entities: Dictionary of extracted entities
            
        Returns:
            ToolResult with status and data
        """
        pass
    
    @abstractmethod
    def validate(self, entities: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate if entities are sufficient for execution.
        
        Returns:
            (is_valid, error_message)
        """
        pass
    
    def get_confirmation_prompt(self, entities: Dict[str, Any]) -> Optional[str]:
        """
        Generate confirmation prompt if needed.
        
        Returns:
            Confirmation prompt string or None
        """
        if not self.requires_confirmation:
            return None
        return None
