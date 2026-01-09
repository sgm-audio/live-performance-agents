"""
Thread-safe priority-based publish/subscribe message bus
"""

import threading
import queue
from typing import Dict, Set, Callable, Optional
from collections import defaultdict
import logging

from .message import Message, Priority

logger = logging.getLogger(__name__)


class MessageBus:
    """
    Thread-safe priority-based publish/subscribe message bus

    Implements singleton pattern for global message routing.
    All agents communicate through this central bus.

    Features:
    - Priority-based message delivery (CRITICAL -> HIGH -> MEDIUM -> LOW)
    - Thread-safe subscription management
    - Request/response correlation
    - Asynchronous message processing
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern - only one message bus instance"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Prevent re-initialization
        if hasattr(self, '_initialized'):
            return

        self._initialized = True

        # Priority queue for message delivery
        self.message_queue = queue.PriorityQueue()

        # Subscriptions: topic -> set of callback functions
        self.subscriptions: Dict[str, Set[Callable]] = defaultdict(set)
        self.subscriptions_lock = threading.Lock()

        # Response handlers: correlation_id -> callback
        self.response_handlers: Dict[str, Callable] = {}
        self.response_lock = threading.Lock()

        # Message processing thread
        self.active = False
        self.worker_thread: Optional[threading.Thread] = None

        # Statistics
        self.stats = {
            'messages_sent': 0,
            'messages_delivered': 0,
            'subscriptions_count': 0,
            'errors': 0
        }
        self.stats_lock = threading.Lock()

        logger.info("Message bus initialized")

    def start(self):
        """Start message processing worker thread"""
        if self.active:
            logger.warning("Message bus already started")
            return

        self.active = True
        self.worker_thread = threading.Thread(
            target=self._message_worker,
            name="MessageBus_Worker",
            daemon=True
        )
        self.worker_thread.start()
        logger.info("Message bus started")

    def stop(self):
        """Stop message processing and cleanup"""
        if not self.active:
            return

        self.active = False
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=2.0)

        logger.info("Message bus stopped")

    def subscribe(self, topic: str, callback: Callable[[Message], None]):
        """
        Subscribe to a topic

        Args:
            topic: Topic name to subscribe to
            callback: Function to call when messages arrive (receives Message object)
        """
        with self.subscriptions_lock:
            self.subscriptions[topic].add(callback)
            with self.stats_lock:
                self.stats['subscriptions_count'] = sum(
                    len(cbs) for cbs in self.subscriptions.values()
                )

        logger.debug(f"Subscribed to topic: {topic}")

    def unsubscribe(self, topic: str, callback: Callable[[Message], None]):
        """
        Unsubscribe from a topic

        Args:
            topic: Topic name to unsubscribe from
            callback: Callback function to remove
        """
        with self.subscriptions_lock:
            if topic in self.subscriptions:
                self.subscriptions[topic].discard(callback)
                if not self.subscriptions[topic]:
                    del self.subscriptions[topic]
                with self.stats_lock:
                    self.stats['subscriptions_count'] = sum(
                        len(cbs) for cbs in self.subscriptions.values()
                    )

        logger.debug(f"Unsubscribed from topic: {topic}")

    def publish(self, message: Message):
        """
        Publish a message to the bus

        Args:
            message: Message to publish
        """
        self.message_queue.put(message)
        with self.stats_lock:
            self.stats['messages_sent'] += 1

        logger.debug(f"Published: {message}")

    def request(self, topic: str, sender: str, payload: Dict,
                callback: Callable[[Dict], None],
                priority: Priority = Priority.MEDIUM,
                timeout: float = 5.0):
        """
        Send a request and register a response callback

        Args:
            topic: Topic to send request to
            sender: Agent ID of sender
            payload: Request data
            callback: Function to call with response payload
            priority: Message priority
            timeout: Response timeout (not yet implemented)
        """
        message = Message(
            topic=topic,
            sender=sender,
            payload=payload,
            priority=priority
        )

        # Register response handler
        with self.response_lock:
            self.response_handlers[message.message_id] = callback

        # Publish request
        self.publish(message)

        # TODO: Implement timeout handling

    def respond(self, original_message: Message, sender: str, response_payload: Dict):
        """
        Respond to a message

        Args:
            original_message: The message being responded to
            sender: Agent ID of responder
            response_payload: Response data
        """
        response = Message(
            topic=f"{original_message.topic}.response",
            sender=sender,
            payload=response_payload,
            priority=original_message.priority,
            correlation_id=original_message.message_id
        )
        self.publish(response)

    def get_stats(self) -> Dict:
        """Get message bus statistics"""
        with self.stats_lock:
            return self.stats.copy()

    def _message_worker(self):
        """Worker thread for message delivery"""
        while self.active:
            try:
                # Get next message with timeout to allow shutdown
                message = self.message_queue.get(timeout=0.1)

                # Handle responses (messages with correlation_id)
                if message.correlation_id:
                    with self.response_lock:
                        handler = self.response_handlers.pop(message.correlation_id, None)

                    if handler:
                        try:
                            handler(message.payload)
                        except Exception as e:
                            logger.error(f"Error in response handler: {e}")
                            with self.stats_lock:
                                self.stats['errors'] += 1

                # Deliver to subscribers
                with self.subscriptions_lock:
                    # Copy callbacks to avoid holding lock during delivery
                    callbacks = self.subscriptions.get(message.topic, set()).copy()

                for callback in callbacks:
                    try:
                        callback(message)
                        with self.stats_lock:
                            self.stats['messages_delivered'] += 1
                    except Exception as e:
                        logger.error(
                            f"Error delivering message to subscriber: {e}",
                            extra={'topic': message.topic, 'sender': message.sender}
                        )
                        with self.stats_lock:
                            self.stats['errors'] += 1

            except queue.Empty:
                # No messages - continue loop
                continue
            except Exception as e:
                logger.error(f"Error in message worker: {e}")
                with self.stats_lock:
                    self.stats['errors'] += 1
