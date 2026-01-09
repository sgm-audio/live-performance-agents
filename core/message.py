"""
Message and Priority classes for inter-agent communication
"""

from dataclasses import dataclass, field
from enum import Enum
import time
import uuid
from typing import Dict, Any, Optional


class Priority(Enum):
    """Message priority levels for priority queue processing"""
    LOW = 0          # Background monitoring, periodic updates
    MEDIUM = 1       # Normal status updates, notifications
    HIGH = 2         # Real-time audio, MIDI, tempo changes
    CRITICAL = 3     # System failures, alerts


@dataclass
class Message:
    """
    Message for inter-agent communication

    Attributes:
        topic: Hierarchical topic name (e.g., "audio.live.process")
        sender: Agent ID of the sender
        payload: Message data as dictionary
        priority: Message priority level
        timestamp: Unix timestamp of message creation
        message_id: Unique message identifier
        correlation_id: For request/response tracking (links responses to original requests)
    """
    topic: str
    sender: str
    payload: Dict[str, Any]
    priority: Priority = Priority.MEDIUM
    timestamp: float = field(default_factory=time.time)
    message_id: str = field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:8]}")
    correlation_id: Optional[str] = None

    def __lt__(self, other: 'Message') -> bool:
        """
        Support priority queue comparison
        Higher priority values = processed first (CRITICAL before LOW)
        Same priority = FIFO based on timestamp
        """
        if not isinstance(other, Message):
            return NotImplemented

        if self.priority != other.priority:
            # Higher priority value = lower queue position (processed first)
            return self.priority.value > other.priority.value

        # Same priority - FIFO ordering
        return self.timestamp < other.timestamp

    def __repr__(self) -> str:
        return (f"Message(topic='{self.topic}', sender='{self.sender}', "
                f"priority={self.priority.name}, id={self.message_id[:8]})")
