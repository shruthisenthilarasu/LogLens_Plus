"""
Data models for LogLens++.

This module defines the core data structures used throughout the system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class LogEvent:
    """
    Represents a single parsed log entry.
    
    Attributes:
        timestamp: The timestamp when the log event occurred
        level: The log level (e.g., 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        source: The source of the log (e.g., service name, application name)
        message: The log message content
        metadata: Optional dictionary containing additional structured data
    
    Raises:
        ValueError: If required fields are invalid or missing
    """
    
    timestamp: datetime
    level: str
    source: str
    message: str
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)
    
    # Valid log levels
    VALID_LEVELS = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'TRACE', 'FATAL'}
    
    def __post_init__(self):
        """
        Validate the LogEvent after initialization.
        
        Raises:
            ValueError: If any required field is invalid
        """
        # Validate timestamp
        if not isinstance(self.timestamp, datetime):
            raise ValueError(f"timestamp must be a datetime object, got {type(self.timestamp)}")
        
        # Validate level
        if not isinstance(self.level, str):
            raise ValueError(f"level must be a string, got {type(self.level)}")
        
        level_upper = self.level.upper()
        if level_upper not in self.VALID_LEVELS:
            raise ValueError(
                f"level must be one of {self.VALID_LEVELS}, got '{self.level}'"
            )
        # Normalize level to uppercase
        self.level = level_upper
        
        # Validate source
        if not isinstance(self.source, str):
            raise ValueError(f"source must be a string, got {type(self.source)}")
        if not self.source.strip():
            raise ValueError("source cannot be empty")
        
        # Validate message
        if not isinstance(self.message, str):
            raise ValueError(f"message must be a string, got {type(self.message)}")
        if not self.message.strip():
            raise ValueError("message cannot be empty")
        
        # Validate metadata
        if self.metadata is not None and not isinstance(self.metadata, dict):
            raise ValueError(f"metadata must be a dictionary or None, got {type(self.metadata)}")
        
        # Ensure metadata is a dict (not None) for easier access
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the LogEvent to a dictionary.
        
        Returns:
            Dictionary representation of the LogEvent
        """
        return {
            'timestamp': self.timestamp.isoformat(),
            'level': self.level,
            'source': self.source,
            'message': self.message,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LogEvent':
        """
        Create a LogEvent from a dictionary.
        
        Args:
            data: Dictionary containing log event data
            
        Returns:
            LogEvent instance
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Convert ISO format timestamp string to datetime if needed
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif not isinstance(timestamp, datetime):
            raise ValueError("timestamp must be a datetime object or ISO format string")
        
        return cls(
            timestamp=timestamp,
            level=data.get('level', 'INFO'),
            source=data['source'],
            message=data['message'],
            metadata=data.get('metadata', {})
        )
    
    def __str__(self) -> str:
        """String representation of the LogEvent."""
        return f"[{self.timestamp.isoformat()}] {self.level} {self.source}: {self.message}"
    
    def __repr__(self) -> str:
        """Detailed representation of the LogEvent."""
        return (
            f"LogEvent(timestamp={self.timestamp!r}, level={self.level!r}, "
            f"source={self.source!r}, message={self.message!r}, "
            f"metadata={self.metadata!r})"
        )

