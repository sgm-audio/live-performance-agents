"""
Live Mixing & Dynamics Agent

Intelligent mixing and dynamics processing including auto-mixing, ducking,
feedback suppression, and spatial processing.
"""

import threading
import time
import numpy as np
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import logging

from core import BaseAgent, Message, Topics, Priority

logger = logging.getLogger(__name__)


@dataclass
class ChannelConfig:
    """Audio channel configuration"""
    channel_id: int
    channel_name: str
    priority: int = 5  # 1-10, higher = more important
    enabled: bool = True
    volume: float = 1.0
    pan: float = 0.0  # -1.0 (left) to 1.0 (right)
    muted: bool = False
    solo: bool = False


@dataclass
class DuckingConfig:
    """Ducking (sidechain compression) configuration"""
    ducking_id: str
    sidechain_channel: int
    target_channels: List[int]
    threshold_db: float = -20.0
    ratio: float = 4.0
    attack_ms: float = 10.0
    release_ms: float = 300.0
    enabled: bool = True


@dataclass
class FeedbackFilter:
    """Feedback suppression filter"""
    filter_id: str
    channel_id: int
    frequency_hz: float
    bandwidth_hz: float
    attenuation_db: float
    auto_adapt: bool = True
    enabled: bool = True


class LiveMixingDynamicsAgent(BaseAgent):
    """Agent for intelligent live mixing and dynamics"""

    def __init__(self):
        super().__init__(
            agent_id="live_mixing_dynamics_agent",
            agent_name="Live Mixing & Dynamics Agent"
        )

        self.channels: Dict[int, ChannelConfig] = {}
        self.channels_lock = threading.Lock()

        self.ducking_configs: Dict[str, DuckingConfig] = {}
        self.ducking_lock = threading.Lock()

        self.feedback_filters: List[FeedbackFilter] = []
        self.feedback_lock = threading.Lock()

        # Auto-mixing state
        self.auto_mix_enabled = False
        self.auto_mix_sensitivity = 0.7
        self.auto_mix_channels: List[int] = []

        # Processing thread
        self.processing_thread: Optional[threading.Thread] = None
        self.processing_active = False

        self.stats = {
            'mix_adjustments': 0,
            'ducking_events': 0,
            'feedback_suppressions': 0
        }
        self.stats_lock = threading.Lock()

    def setup(self):
        """Initialize the mixing agent"""
        self.subscribe("mix.channel.add")
        self.subscribe("mix.channel.priority")
        self.subscribe("mix.automix.enable")
        self.subscribe("mix.ducking.configure")
        self.subscribe("mix.feedback.suppress")
        self.subscribe("mix.spatial.position")
        self.subscribe("audio.live.input.stream")

        self._start_processing_thread()
        self.log("INFO", "Live Mixing & Dynamics Agent initialized")

    def teardown(self):
        """Cleanup resources"""
        self._stop_processing_thread()
        self.log("INFO", "Live Mixing & Dynamics Agent shutdown complete")

    def handle_message(self, message: Message):
        """Process incoming messages"""
        try:
            if message.topic == "mix.channel.add":
                self._handle_channel_add(message)
            elif message.topic == "mix.channel.priority":
                self._handle_channel_priority(message)
            elif message.topic == "mix.automix.enable":
                self._handle_automix_enable(message)
            elif message.topic == "mix.ducking.configure":
                self._handle_ducking_configure(message)
            elif message.topic == "mix.feedback.suppress":
                self._handle_feedback_suppress(message)
            elif message.topic == "mix.spatial.position":
                self._handle_spatial_position(message)
            elif message.topic == "audio.live.input.stream":
                self._handle_audio_input(message)
        except Exception as e:
            self.log("ERROR", f"Error handling message: {e}", {"topic": message.topic})

    def _handle_channel_add(self, message: Message):
        """Handle channel addition"""
        payload = message.payload

        channel = ChannelConfig(
            channel_id=payload['channel_id'],
            channel_name=payload.get('channel_name', f"Channel {payload['channel_id']}"),
            priority=payload.get('priority', 5),
            volume=payload.get('volume', 1.0),
            pan=payload.get('pan', 0.0)
        )

        with self.channels_lock:
            self.channels[channel.channel_id] = channel

        self.respond(message, {'success': True, 'channel_id': channel.channel_id})

    def _handle_channel_priority(self, message: Message):
        """Handle channel priority change"""
        payload = message.payload
        channel_id = payload['channel_id']
        priority = payload['priority']

        with self.channels_lock:
            if channel_id in self.channels:
                self.channels[channel_id].priority = priority
                success = True
            else:
                success = False

        self.respond(message, {'success': success, 'channel_id': channel_id, 'priority': priority})

    def _handle_automix_enable(self, message: Message):
        """Handle auto-mix enable"""
        payload = message.payload
        enable = payload.get('enable', True)
        input_channels = payload.get('input_channels', [])
        sensitivity = payload.get('sensitivity', 0.7)

        self.auto_mix_enabled = enable
        self.auto_mix_channels = input_channels
        self.auto_mix_sensitivity = sensitivity

        self.respond(message, {
            'success': True,
            'auto_mix_enabled': self.auto_mix_enabled,
            'channels': len(self.auto_mix_channels)
        })

        self.publish("mix.automix.status", {
            'enabled': self.auto_mix_enabled,
            'channels': self.auto_mix_channels
        }, priority=Priority.MEDIUM)

    def _handle_ducking_configure(self, message: Message):
        """Handle ducking configuration"""
        payload = message.payload

        ducking = DuckingConfig(
            ducking_id=payload.get('ducking_id', f"duck_{time.time()}"),
            sidechain_channel=payload['sidechain_channel'],
            target_channels=payload['target_channels'],
            threshold_db=payload.get('threshold_db', -20.0),
            ratio=payload.get('ratio', 4.0),
            attack_ms=payload.get('attack_ms', 10.0),
            release_ms=payload.get('release_ms', 300.0)
        )

        with self.ducking_lock:
            self.ducking_configs[ducking.ducking_id] = ducking

        self.respond(message, {'success': True, 'ducking_id': ducking.ducking_id})

    def _handle_feedback_suppress(self, message: Message):
        """Handle feedback suppression"""
        payload = message.payload
        channel_id = payload['channel_id']
        num_filters = payload.get('num_filters', 12)
        auto_adapt = payload.get('auto_adapt', True)

        # Create feedback suppression filters
        filters_created = []

        for i in range(num_filters):
            feedback_filter = FeedbackFilter(
                filter_id=f"fb_{channel_id}_{i}_{time.time()}",
                channel_id=channel_id,
                frequency_hz=0.0,  # Will be set dynamically
                bandwidth_hz=10.0,
                attenuation_db=-12.0,
                auto_adapt=auto_adapt
            )

            with self.feedback_lock:
                self.feedback_filters.append(feedback_filter)

            filters_created.append(feedback_filter.filter_id)

        self.respond(message, {
            'success': True,
            'channel_id': channel_id,
            'filters_created': len(filters_created)
        })

    def _handle_spatial_position(self, message: Message):
        """Handle spatial positioning"""
        payload = message.payload
        channel_id = payload['channel_id']
        pan = payload.get('pan', 0.0)
        width = payload.get('width', 1.0)

        with self.channels_lock:
            if channel_id in self.channels:
                self.channels[channel_id].pan = pan
                success = True
            else:
                success = False

        self.respond(message, {'success': success, 'channel_id': channel_id, 'pan': pan})

    def _handle_audio_input(self, message: Message):
        """Handle audio input for processing"""
        payload = message.payload
        audio_data = payload.get('audio_data', [])

        if not audio_data or not self.auto_mix_enabled:
            return

        # Process auto-mixing
        self._process_auto_mix(audio_data)

        # Process ducking
        self._process_ducking(audio_data)

        # Detect and suppress feedback
        self._detect_and_suppress_feedback(audio_data)

    def _start_processing_thread(self):
        """Start processing thread"""
        self.processing_active = True
        self.processing_thread = threading.Thread(
            target=self._processing_worker,
            name=f"{self.agent_id}_processor",
            daemon=True
        )
        self.processing_thread.start()

    def _stop_processing_thread(self):
        """Stop processing thread"""
        self.processing_active = False
        if self.processing_thread:
            self.processing_thread.join(timeout=2.0)

    def _processing_worker(self):
        """Processing worker thread"""
        while self.processing_active:
            try:
                # Continuous monitoring and adjustment
                if self.auto_mix_enabled:
                    self._adjust_auto_mix_levels()

                time.sleep(0.01)  # 10ms processing interval

            except Exception as e:
                logger.error(f"Error in processing worker: {e}")

    def _process_auto_mix(self, audio_data: List[float]):
        """Process automatic gain riding"""
        if not self.auto_mix_channels:
            return

        # Calculate levels for each channel
        channel_levels = {}

        for channel_id in self.auto_mix_channels:
            # Simulated level detection
            level = np.random.random() * 0.5  # Placeholder
            channel_levels[channel_id] = level

        # Adjust levels based on priority and activity
        self._adjust_channel_levels(channel_levels)

    def _adjust_channel_levels(self, channel_levels: Dict[int, float]):
        """Adjust channel levels based on activity and priority"""
        with self.channels_lock:
            total_priority_weight = 0.0
            active_channels = []

            # Find active channels
            for channel_id, level in channel_levels.items():
                if channel_id in self.channels and level > 0.01:  # Activity threshold
                    channel = self.channels[channel_id]
                    active_channels.append((channel_id, level, channel.priority))
                    total_priority_weight += channel.priority

            if not active_channels:
                return

            # Adjust volumes based on priority
            for channel_id, level, priority in active_channels:
                if channel_id in self.channels:
                    # Higher priority = higher volume when multiple channels active
                    priority_factor = priority / total_priority_weight if total_priority_weight > 0 else 1.0
                    new_volume = min(1.0, priority_factor * (1.0 / len(active_channels)) * 2.0)

                    self.channels[channel_id].volume = new_volume

        with self.stats_lock:
            self.stats['mix_adjustments'] += 1

    def _adjust_auto_mix_levels(self):
        """Periodic auto-mix level adjustment"""
        # Simulated continuous adjustment
        pass

    def _process_ducking(self, audio_data: List[float]):
        """Process sidechain ducking"""
        with self.ducking_lock:
            for ducking in self.ducking_configs.values():
                if not ducking.enabled:
                    continue

                # Simulate sidechain level detection
                sidechain_level_db = -30.0  # Placeholder

                if sidechain_level_db > ducking.threshold_db:
                    # Apply ducking to target channels
                    reduction_db = (sidechain_level_db - ducking.threshold_db) / ducking.ratio

                    with self.channels_lock:
                        for target_channel in ducking.target_channels:
                            if target_channel in self.channels:
                                # Apply gain reduction
                                reduction_linear = 10 ** (-reduction_db / 20.0)
                                self.channels[target_channel].volume *= reduction_linear

                    with self.stats_lock:
                        self.stats['ducking_events'] += 1

    def _detect_and_suppress_feedback(self, audio_data: List[float]):
        """Detect and suppress feedback frequencies"""
        # Simplified feedback detection (would use FFT in production)
        with self.feedback_lock:
            for feedback_filter in self.feedback_filters:
                if not feedback_filter.enabled or not feedback_filter.auto_adapt:
                    continue

                # Simulate feedback detection
                if np.random.random() < 0.01:  # 1% chance of detecting feedback
                    feedback_freq = np.random.uniform(100, 8000)
                    feedback_filter.frequency_hz = feedback_freq

                    with self.stats_lock:
                        self.stats['feedback_suppressions'] += 1

                    self.publish("mix.feedback.detected", {
                        'channel_id': feedback_filter.channel_id,
                        'frequency': feedback_freq,
                        'filter_id': feedback_filter.filter_id
                    }, priority=Priority.HIGH)
