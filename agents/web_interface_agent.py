"""
Web Interface Agent - Bridges MessageBus and WebSocket for frontend

Provides real-time bidirectional communication between the agent system
and web-based frontend interfaces.
"""

import time
import threading
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set, Callable
from collections import deque, defaultdict
from enum import Enum

from core import BaseAgent, Message, Topics, Priority

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """WebSocket message types"""
    AGENT_STATUS = "agent_status"
    AUDIO_LEVELS = "audio_levels"
    MIDI_MESSAGE = "midi_message"
    EFFECT_CHANGE = "effect_change"
    LOOP_STATUS = "loop_status"
    SYNC_UPDATE = "sync_update"
    COMMAND = "command"
    RESPONSE = "response"
    ERROR = "error"


@dataclass
class WebSocketClient:
    """Connected WebSocket client"""
    client_id: str
    websocket: Any  # WebSocket connection object
    connected_at: float = field(default_factory=time.time)
    subscriptions: Set[str] = field(default_factory=set)  # Topic filters
    last_message_time: float = field(default_factory=time.time)
    message_count: int = 0


@dataclass
class ThrottleConfig:
    """Throttling configuration for message types"""
    min_interval_ms: float  # Minimum time between messages
    last_sent_time: float = 0.0


@dataclass
class WebInterfaceConfig:
    """Configuration for web interface"""
    host: str = "0.0.0.0"
    port: int = 8080
    max_clients: int = 10
    message_queue_size: int = 1000
    enable_throttling: bool = True

    # Throttle settings (in milliseconds)
    audio_levels_throttle_ms: float = 33.0  # 30 Hz
    agent_status_throttle_ms: float = 100.0  # 10 Hz
    effect_change_throttle_ms: float = 50.0  # 20 Hz
    midi_throttle_ms: float = 0.0  # No throttling (real-time)


class WebInterfaceAgent(BaseAgent):
    """
    Bridges MessageBus and WebSocket for web frontend communication

    Features:
    - Subscribes to all relevant agent topics
    - Maintains connected WebSocket clients
    - Throttles high-frequency messages
    - Routes commands from frontend to MessageBus
    - Provides request/response pattern
    """

    def __init__(
        self,
        agent_id: str = "web_interface",
        config: Optional[WebInterfaceConfig] = None
    ):
        super().__init__(agent_id, "Web Interface Agent")

        self.config = config or WebInterfaceConfig()

        # WebSocket clients
        self.clients: Dict[str, WebSocketClient] = {}
        self.clients_lock = threading.Lock()

        # Message queue for outgoing messages
        self.outgoing_queue: deque = deque(maxlen=self.config.message_queue_size)
        self.queue_lock = threading.Lock()

        # Throttle configurations per message type
        self.throttle_configs: Dict[str, ThrottleConfig] = {
            MessageType.AUDIO_LEVELS.value: ThrottleConfig(
                min_interval_ms=self.config.audio_levels_throttle_ms
            ),
            MessageType.AGENT_STATUS.value: ThrottleConfig(
                min_interval_ms=self.config.agent_status_throttle_ms
            ),
            MessageType.EFFECT_CHANGE.value: ThrottleConfig(
                min_interval_ms=self.config.effect_change_throttle_ms
            ),
            MessageType.MIDI_MESSAGE.value: ThrottleConfig(
                min_interval_ms=self.config.midi_throttle_ms
            ),
        }

        # Topic-to-MessageType mapping
        self.topic_to_message_type: Dict[str, str] = {}

        # Command handlers
        self.command_handlers: Dict[str, Callable] = {}
        self._register_command_handlers()

        # Statistics
        self.stats = {
            "clients_connected": 0,
            "total_clients": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "messages_throttled": 0,
            "commands_processed": 0,
        }
        self.stats_lock = threading.Lock()

        # Worker thread for message broadcasting
        self.broadcast_active = False
        self.broadcast_thread: Optional[threading.Thread] = None

    def setup(self):
        """Initialize and subscribe to topics"""
        self.log("INFO", "Setting up Web Interface Agent")

        # Subscribe to all relevant topics
        self._subscribe_to_topics()

        # Start broadcast worker
        self._start_broadcast_worker()

        self.log("INFO", f"Web interface configured on {self.config.host}:{self.config.port}")

    def teardown(self):
        """Cleanup resources"""
        self.log("INFO", "Shutting down Web Interface Agent")

        # Stop broadcast worker
        self._stop_broadcast_worker()

        # Disconnect all clients
        with self.clients_lock:
            for client in list(self.clients.values()):
                self._disconnect_client(client.client_id)

        self.log("INFO", "Web Interface Agent shut down")

    def _subscribe_to_topics(self):
        """Subscribe to all relevant MessageBus topics"""
        # Agent status
        self.subscribe("agent.*.status", self._handle_agent_status)
        self.topic_to_message_type["agent.*.status"] = MessageType.AGENT_STATUS.value

        # Audio levels
        self.subscribe("audio.live.levels", self._handle_audio_levels)
        self.topic_to_message_type["audio.live.levels"] = MessageType.AUDIO_LEVELS.value

        # MIDI messages
        self.subscribe("midi.message.received", self._handle_midi_message)
        self.topic_to_message_type["midi.message.received"] = MessageType.MIDI_MESSAGE.value

        # Effect changes
        self.subscribe("effects.*.changed", self._handle_effect_change)
        self.topic_to_message_type["effects.*.changed"] = MessageType.EFFECT_CHANGE.value

        # Loop status
        self.subscribe("loop.*.status", self._handle_loop_status)
        self.topic_to_message_type["loop.*.status"] = MessageType.LOOP_STATUS.value

        # Sync updates
        self.subscribe("sync.tempo.changed", self._handle_sync_update)
        self.subscribe("sync.time.update", self._handle_sync_update)
        self.topic_to_message_type["sync.tempo.changed"] = MessageType.SYNC_UPDATE.value
        self.topic_to_message_type["sync.time.update"] = MessageType.SYNC_UPDATE.value

        # Monitor stats
        self.subscribe("monitor.stats", self._handle_monitor_stats)
        self.topic_to_message_type["monitor.stats"] = MessageType.AGENT_STATUS.value

    def _register_command_handlers(self):
        """Register handlers for frontend commands"""
        self.command_handlers = {
            "effect.parameter.set": self._handle_set_effect_parameter,
            "midi.mapping.create": self._handle_create_midi_mapping,
            "midi.mapping.delete": self._handle_delete_midi_mapping,
            "loop.record.start": self._handle_loop_record_start,
            "loop.record.stop": self._handle_loop_record_stop,
            "loop.play": self._handle_loop_play,
            "loop.stop": self._handle_loop_stop,
            "preset.load": self._handle_load_preset,
            "preset.save": self._handle_save_preset,
            "automation.start": self._handle_automation_start,
            "automation.stop": self._handle_automation_stop,
            "agent.start": self._handle_agent_start,
            "agent.stop": self._handle_agent_stop,
        }

    def handle_message(self, message: Message):
        """Handle incoming MessageBus messages"""
        # Messages are handled by specific topic handlers
        pass

    # =========================================================================
    # Client Management
    # =========================================================================

    def register_client(self, client_id: str, websocket: Any) -> bool:
        """
        Register a new WebSocket client

        Returns:
            True if registered successfully, False if max clients reached
        """
        with self.clients_lock:
            if len(self.clients) >= self.config.max_clients:
                self.log("WARNING", f"Max clients ({self.config.max_clients}) reached")
                return False

            client = WebSocketClient(
                client_id=client_id,
                websocket=websocket,
                subscriptions={"*"}  # Subscribe to all by default
            )

            self.clients[client_id] = client

            with self.stats_lock:
                self.stats["clients_connected"] = len(self.clients)
                self.stats["total_clients"] += 1

        self.log("INFO", f"Client registered: {client_id}")

        # Send initial state to client
        self._send_initial_state(client_id)

        return True

    def unregister_client(self, client_id: str):
        """Unregister a WebSocket client"""
        self._disconnect_client(client_id)

    def _disconnect_client(self, client_id: str):
        """Disconnect and remove a client"""
        with self.clients_lock:
            if client_id in self.clients:
                del self.clients[client_id]

                with self.stats_lock:
                    self.stats["clients_connected"] = len(self.clients)

        self.log("INFO", f"Client disconnected: {client_id}")

    def _send_initial_state(self, client_id: str):
        """Send initial system state to newly connected client"""
        # Send current agent statuses
        self._send_to_client(client_id, {
            "type": MessageType.AGENT_STATUS.value,
            "timestamp": time.time(),
            "data": {
                "message": "Connected to Live Performance Agents system",
                "version": "0.1.0"
            }
        })

    # =========================================================================
    # Message Handlers (MessageBus → Frontend)
    # =========================================================================

    def _handle_agent_status(self, message: Message):
        """Handle agent status updates"""
        self._queue_message(MessageType.AGENT_STATUS.value, message.payload)

    def _handle_audio_levels(self, message: Message):
        """Handle audio level updates"""
        self._queue_message(MessageType.AUDIO_LEVELS.value, message.payload)

    def _handle_midi_message(self, message: Message):
        """Handle MIDI messages"""
        self._queue_message(MessageType.MIDI_MESSAGE.value, message.payload)

    def _handle_effect_change(self, message: Message):
        """Handle effect parameter changes"""
        self._queue_message(MessageType.EFFECT_CHANGE.value, message.payload)

    def _handle_loop_status(self, message: Message):
        """Handle loop status updates"""
        self._queue_message(MessageType.LOOP_STATUS.value, message.payload)

    def _handle_sync_update(self, message: Message):
        """Handle synchronization updates"""
        self._queue_message(MessageType.SYNC_UPDATE.value, message.payload)

    def _handle_monitor_stats(self, message: Message):
        """Handle performance monitoring stats"""
        self._queue_message(MessageType.AGENT_STATUS.value, {
            "monitor_stats": message.payload
        })

    def _queue_message(self, message_type: str, data: Dict[str, Any]):
        """Queue a message for broadcast to clients"""
        # Check throttling
        if self.config.enable_throttling and message_type in self.throttle_configs:
            throttle = self.throttle_configs[message_type]
            current_time = time.time() * 1000  # Convert to ms

            if (current_time - throttle.last_sent_time) < throttle.min_interval_ms:
                with self.stats_lock:
                    self.stats["messages_throttled"] += 1
                return

            throttle.last_sent_time = current_time

        # Create WebSocket message
        ws_message = {
            "type": message_type,
            "timestamp": time.time(),
            "data": data
        }

        with self.queue_lock:
            self.outgoing_queue.append(ws_message)

    # =========================================================================
    # Message Broadcasting (to WebSocket clients)
    # =========================================================================

    def _start_broadcast_worker(self):
        """Start the broadcast worker thread"""
        self.broadcast_active = True
        self.broadcast_thread = threading.Thread(
            target=self._broadcast_worker,
            name=f"{self.agent_id}_broadcast",
            daemon=True
        )
        self.broadcast_thread.start()

    def _stop_broadcast_worker(self):
        """Stop the broadcast worker thread"""
        self.broadcast_active = False
        if self.broadcast_thread and self.broadcast_thread.is_alive():
            self.broadcast_thread.join(timeout=2.0)

    def _broadcast_worker(self):
        """Worker thread for broadcasting messages to all clients"""
        while self.broadcast_active:
            try:
                # Get message from queue
                message = None
                with self.queue_lock:
                    if len(self.outgoing_queue) > 0:
                        message = self.outgoing_queue.popleft()

                if message:
                    # Broadcast to all clients
                    with self.clients_lock:
                        for client_id in list(self.clients.keys()):
                            self._send_to_client(client_id, message)
                else:
                    # No messages, sleep briefly
                    time.sleep(0.01)  # 10ms

            except Exception as e:
                logger.error(f"Error in broadcast worker: {e}")

    def _send_to_client(self, client_id: str, message: Dict[str, Any]):
        """Send message to specific client"""
        with self.clients_lock:
            if client_id not in self.clients:
                return

            client = self.clients[client_id]

            try:
                # Convert to JSON
                json_message = json.dumps(message)

                # Send via WebSocket (this will be handled by FastAPI)
                # For now, we just store it - the API server will handle actual sending
                client.last_message_time = time.time()
                client.message_count += 1

                with self.stats_lock:
                    self.stats["messages_sent"] += 1

            except Exception as e:
                self.log("ERROR", f"Failed to send to client {client_id}: {e}")
                self._disconnect_client(client_id)

    # =========================================================================
    # Command Handlers (Frontend → MessageBus)
    # =========================================================================

    def receive_command(self, client_id: str, command_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receive and process command from frontend

        Returns:
            Response dict with status and optional data
        """
        with self.stats_lock:
            self.stats["messages_received"] += 1

        try:
            command_type = command_data.get("command")
            data = command_data.get("data", {})

            if command_type not in self.command_handlers:
                return {
                    "type": MessageType.ERROR.value,
                    "error": f"Unknown command: {command_type}"
                }

            # Call command handler
            handler = self.command_handlers[command_type]
            result = handler(data)

            with self.stats_lock:
                self.stats["commands_processed"] += 1

            return {
                "type": MessageType.RESPONSE.value,
                "command": command_type,
                "success": True,
                "data": result
            }

        except Exception as e:
            self.log("ERROR", f"Error processing command: {e}")
            return {
                "type": MessageType.ERROR.value,
                "error": str(e)
            }

    # Command handler implementations

    def _handle_set_effect_parameter(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Set effect parameter"""
        effect_id = data["effect_id"]
        parameter = data["parameter"]
        value = data["value"]

        self.publish(
            "effects.parameter.set",
            {
                "effect_id": effect_id,
                "parameter": parameter,
                "value": value
            },
            priority=Priority.HIGH
        )

        return {"effect_id": effect_id, "parameter": parameter, "value": value}

    def _handle_create_midi_mapping(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create MIDI CC mapping"""
        self.publish(
            "midi.mapping.create",
            data,
            priority=Priority.MEDIUM
        )
        return data

    def _handle_delete_midi_mapping(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Delete MIDI mapping"""
        self.publish(
            "midi.mapping.delete",
            data,
            priority=Priority.MEDIUM
        )
        return data

    def _handle_loop_record_start(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Start loop recording"""
        self.publish(
            "loop.record.start",
            data,
            priority=Priority.HIGH
        )
        return data

    def _handle_loop_record_stop(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Stop loop recording"""
        self.publish(
            "loop.record.stop",
            data,
            priority=Priority.HIGH
        )
        return data

    def _handle_loop_play(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Play loop"""
        self.publish(
            "loop.play",
            data,
            priority=Priority.HIGH
        )
        return data

    def _handle_loop_stop(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Stop loop"""
        self.publish(
            "loop.stop",
            data,
            priority=Priority.HIGH
        )
        return data

    def _handle_load_preset(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Load preset/scene"""
        self.publish(
            "effects.preset.load",
            data,
            priority=Priority.MEDIUM
        )
        return data

    def _handle_save_preset(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Save preset/scene"""
        self.publish(
            "effects.preset.save",
            data,
            priority=Priority.MEDIUM
        )
        return data

    def _handle_automation_start(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Start automation playback"""
        self.publish(
            "automation.playback.start",
            data,
            priority=Priority.MEDIUM
        )
        return data

    def _handle_automation_stop(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Stop automation playback"""
        self.publish(
            "automation.playback.stop",
            data,
            priority=Priority.MEDIUM
        )
        return data

    def _handle_agent_start(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Start an agent"""
        # This would require agent registry integration
        return {"message": "Agent start not yet implemented"}

    def _handle_agent_stop(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Stop an agent"""
        # This would require agent registry integration
        return {"message": "Agent stop not yet implemented"}

    # =========================================================================
    # Statistics & Status
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics"""
        with self.stats_lock:
            return self.stats.copy()

    def get_connected_clients(self) -> List[Dict[str, Any]]:
        """Get list of connected clients"""
        with self.clients_lock:
            return [
                {
                    "client_id": client.client_id,
                    "connected_at": client.connected_at,
                    "message_count": client.message_count,
                    "last_message_time": client.last_message_time
                }
                for client in self.clients.values()
            ]
