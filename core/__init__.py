"""
Live Performance Agents - Core Framework

This package provides the foundational components for the agent-based
live audio performance system.
"""

from .message import Message, Priority
from .base_agent import BaseAgent
from .message_bus import MessageBus
from .agent_registry import AgentRegistry
from .topics import Topics

__all__ = [
    'Message',
    'Priority',
    'BaseAgent',
    'MessageBus',
    'AgentRegistry',
    'Topics',
]

__version__ = '0.1.0'
