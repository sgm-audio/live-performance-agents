"""
Base agent class for all Live Performance agents
"""

import threading
import logging
from typing import Dict, Any, Optional, Set
from abc import ABC, abstractmethod

from .message import Message, Priority
from .message_bus import MessageBus

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base class for all agents in the Live Performance system

    All agents must inherit from this class and implement:
    - setup(): Initialize agent, subscribe to topics, start threads
    - teardown(): Cleanup resources, stop threads
    - handle_message(): Process incoming messages

    Provides:
    - Message bus communication (subscribe, publish, respond)
    - Standardized logging
    - Thread-safe message handling
    """

    def __init__(self, agent_id: str, agent_name: str):
        """
        Initialize base agent

        Args:
            agent_id: Unique identifier for this agent (e.g., "audio_io_agent")
            agent_name: Human-readable name (e.g., "Realtime Audio I/O Agent")
        """
        self.agent_id = agent_id
        self.agent_name = agent_name

        # Message bus reference (singleton)
        self.message_bus = MessageBus()

        # Track subscriptions for cleanup
        self._subscribed_topics: Set[str] = set()

        # Agent-specific logger
        self.logger = logging.getLogger(f"{__name__}.{agent_id}")

    @abstractmethod
    def setup(self):
        """
        Initialize agent - subscribe to topics, start threads

        Called once when agent starts. Must be implemented by subclass.

        Example:
            def setup(self):
                self.subscribe("audio.live.process")
                self.subscribe("audio.live.configure")
                self._start_processing_thread()
                self.log("INFO", "Agent initialized")
        """
        pass

    @abstractmethod
    def teardown(self):
        """
        Cleanup resources - stop threads, release resources

        Called once when agent stops. Must be implemented by subclass.

        Example:
            def teardown(self):
                self._stop_processing_thread()
                self.log("INFO", "Agent shutdown complete")
        """
        pass

    @abstractmethod
    def handle_message(self, message: Message):
        """
        Process incoming messages - routing logic

        Called for each message on subscribed topics. Must be implemented by subclass.

        Example:
            def handle_message(self, message: Message):
                try:
                    if message.topic == "audio.live.process":
                        self._handle_audio_process(message)
                    elif message.topic == "audio.live.configure":
                        self._handle_configure(message)
                except Exception as e:
                    self.log("ERROR", f"Error handling message: {e}",
                            {"topic": message.topic})
        """
        pass

    def subscribe(self, topic: str):
        """
        Subscribe to a message topic

        Args:
            topic: Topic name to subscribe to (e.g., "audio.live.process")
        """
        self.message_bus.subscribe(topic, self._on_message)
        self._subscribed_topics.add(topic)
        self.log("DEBUG", f"Subscribed to topic: {topic}")

    def unsubscribe(self, topic: str):
        """
        Unsubscribe from a topic

        Args:
            topic: Topic name to unsubscribe from
        """
        self.message_bus.unsubscribe(topic, self._on_message)
        self._subscribed_topics.discard(topic)
        self.log("DEBUG", f"Unsubscribed from topic: {topic}")

    def publish(self, topic: str, payload: Dict[str, Any],
                priority: Priority = Priority.MEDIUM):
        """
        Publish a message to the bus

        Args:
            topic: Topic name (e.g., "audio.live.processed")
            payload: Message data as dictionary
            priority: Message priority (default: MEDIUM)
        """
        message = Message(
            topic=topic,
            sender=self.agent_id,
            payload=payload,
            priority=priority
        )
        self.message_bus.publish(message)

    def respond(self, original_message: Message, response_payload: Dict[str, Any]):
        """
        Respond to a message (request/response pattern)

        Args:
            original_message: The message being responded to
            response_payload: Response data as dictionary
        """
        self.message_bus.respond(original_message, self.agent_id, response_payload)

    def log(self, level: str, message: str, context: Optional[Dict[str, Any]] = None):
        """
        Standardized logging for agents

        Args:
            level: Log level ("DEBUG", "INFO", "WARNING", "ERROR")
            message: Log message
            context: Optional additional context as dictionary
        """
        # Build extra context
        extra = {
            'agent_id': self.agent_id,
            'agent_name': self.agent_name
        }
        if context:
            extra.update(context)

        # Get appropriate log method
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(message, extra=extra)

    def _on_message(self, message: Message):
        """
        Internal message handler - routes to handle_message()

        Wraps user's handle_message() with error handling to prevent
        agent crashes from propagating.
        """
        try:
            self.handle_message(message)
        except Exception as e:
            self.log("ERROR", f"Error handling message: {e}",
                    {'topic': message.topic, 'message_id': message.message_id})

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id='{self.agent_id}', name='{self.agent_name}')"
