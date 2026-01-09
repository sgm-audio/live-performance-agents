"""
Visual & Lighting Control Agent

Synchronizes visuals and lighting with audio performance using DMX/ArtNet protocols.
"""

import threading
import time
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

from core import BaseAgent, Message, Topics, Priority

logger = logging.getLogger(__name__)


@dataclass
class DMXFixture:
    """DMX lighting fixture"""
    fixture_id: str
    fixture_name: str
    fixture_type: str  # "par", "moving_head", "led_strip", etc.
    dmx_start_address: int
    num_channels: int
    current_values: Dict[int, int] = field(default_factory=dict)  # channel -> value (0-255)


@dataclass
class LightingScene:
    """Lighting scene"""
    scene_id: str
    scene_name: str
    fixture_states: Dict[str, Dict[int, int]]  # fixture_id -> channel_values
    sync_to_beat: bool = False
    fade_time: float = 0.0


@dataclass
class AudioReactiveMapping:
    """Audio to lighting mapping"""
    mapping_id: str
    frequency_band: Tuple[float, float]  # Hz range
    target_fixture: str
    target_channel: int
    response_curve: str = "linear"
    min_value: int = 0
    max_value: int = 255
    enabled: bool = True


class VisualLightingControlAgent(BaseAgent):
    """Agent for visual and lighting control"""

    def __init__(self):
        super().__init__(
            agent_id="visual_lighting_control_agent",
            agent_name="Visual & Lighting Control Agent"
        )

        self.fixtures: Dict[str, DMXFixture] = {}
        self.fixtures_lock = threading.Lock()

        self.scenes: Dict[str, LightingScene] = {}
        self.scenes_lock = threading.Lock()

        self.audio_mappings: List[AudioReactiveMapping] = []
        self.mappings_lock = threading.Lock()

        # DMX universe (512 channels)
        self.dmx_universe = [0] * 512
        self.dmx_lock = threading.Lock()

        # Beat detection
        self.last_beat_time = 0.0
        self.beat_period = 0.5  # 120 BPM

        # Output thread
        self.output_thread: Optional[threading.Thread] = None
        self.output_active = False

        self.stats = {'scenes_triggered': 0, 'beats_detected': 0, 'dmx_updates': 0}
        self.stats_lock = threading.Lock()

    def setup(self):
        """Initialize the lighting agent"""
        self.subscribe("visual.fixture.add")
        self.subscribe("visual.fixture.control")
        self.subscribe("visual.scene.create")
        self.subscribe("visual.scene.trigger")
        self.subscribe("visual.audio.mapping.create")
        self.subscribe("visual.beat.trigger")
        self.subscribe("audio.analysis.spectrum")
        self.subscribe("sync.clock.position")

        self._start_output_thread()
        self.log("INFO", "Visual & Lighting Control Agent initialized")

    def teardown(self):
        """Cleanup resources"""
        self._stop_output_thread()
        self.log("INFO", "Visual & Lighting Control Agent shutdown complete")

    def handle_message(self, message: Message):
        """Process incoming messages"""
        try:
            if message.topic == "visual.fixture.add":
                self._handle_fixture_add(message)
            elif message.topic == "visual.fixture.control":
                self._handle_fixture_control(message)
            elif message.topic == "visual.scene.create":
                self._handle_scene_create(message)
            elif message.topic == "visual.scene.trigger":
                self._handle_scene_trigger(message)
            elif message.topic == "visual.audio.mapping.create":
                self._handle_audio_mapping_create(message)
            elif message.topic == "visual.beat.trigger":
                self._handle_beat_trigger(message)
            elif message.topic == "audio.analysis.spectrum":
                self._handle_audio_analysis(message)
            elif message.topic == "sync.clock.position":
                self._handle_clock_position(message)
        except Exception as e:
            self.log("ERROR", f"Error handling message: {e}", {"topic": message.topic})

    def _handle_fixture_add(self, message: Message):
        """Handle fixture addition"""
        payload = message.payload

        fixture = DMXFixture(
            fixture_id=payload.get('fixture_id', f"fix_{time.time()}"),
            fixture_name=payload['fixture_name'],
            fixture_type=payload['fixture_type'],
            dmx_start_address=payload['dmx_start_address'],
            num_channels=payload['num_channels']
        )

        with self.fixtures_lock:
            self.fixtures[fixture.fixture_id] = fixture

        self.respond(message, {'success': True, 'fixture_id': fixture.fixture_id})

    def _handle_fixture_control(self, message: Message):
        """Handle fixture control"""
        payload = message.payload
        fixture_id = payload['fixture_id']
        channels = payload['channels']  # {channel: value}
        fade_time = payload.get('fade_time', 0.0)

        with self.fixtures_lock:
            if fixture_id not in self.fixtures:
                self.respond(message, {'success': False, 'error': 'Fixture not found'})
                return

            fixture = self.fixtures[fixture_id]

            # Update DMX universe
            with self.dmx_lock:
                for channel, value in channels.items():
                    dmx_address = fixture.dmx_start_address + channel - 1
                    if 0 <= dmx_address < 512:
                        if fade_time == 0:
                            self.dmx_universe[dmx_address] = value
                        else:
                            # Simplified fade (would use proper fading in production)
                            self.dmx_universe[dmx_address] = value

                    fixture.current_values[channel] = value

        with self.stats_lock:
            self.stats['dmx_updates'] += 1

        self.respond(message, {'success': True, 'fixture_id': fixture_id})

        self.publish("visual.dmx.update", {
            'fixture_id': fixture_id,
            'channels': channels
        }, priority=Priority.MEDIUM)

    def _handle_scene_create(self, message: Message):
        """Handle lighting scene creation"""
        payload = message.payload

        scene = LightingScene(
            scene_id=payload.get('scene_id', f"scene_{time.time()}"),
            scene_name=payload['scene_name'],
            fixture_states=payload.get('fixture_states', {}),
            sync_to_beat=payload.get('sync_to_beat', False),
            fade_time=payload.get('fade_time', 0.0)
        )

        with self.scenes_lock:
            self.scenes[scene.scene_id] = scene

        self.respond(message, {'success': True, 'scene_id': scene.scene_id})

    def _handle_scene_trigger(self, message: Message):
        """Handle scene trigger"""
        payload = message.payload
        scene_id = payload['scene_id']

        with self.scenes_lock:
            if scene_id not in self.scenes:
                self.respond(message, {'success': False, 'error': 'Scene not found'})
                return

            scene = self.scenes[scene_id]

            # Apply scene to fixtures
            for fixture_id, channel_values in scene.fixture_states.items():
                if fixture_id in self.fixtures:
                    self._apply_fixture_values(fixture_id, channel_values, scene.fade_time)

        with self.stats_lock:
            self.stats['scenes_triggered'] += 1

        self.respond(message, {'success': True, 'scene_id': scene_id})

        self.publish("visual.lighting.scene", {
            'scene_id': scene_id,
            'scene_name': scene.scene_name
        }, priority=Priority.HIGH)

    def _handle_audio_mapping_create(self, message: Message):
        """Handle audio-reactive mapping creation"""
        payload = message.payload

        mapping = AudioReactiveMapping(
            mapping_id=payload.get('mapping_id', f"map_{time.time()}"),
            frequency_band=tuple(payload['frequency_band']),
            target_fixture=payload['target_fixture'],
            target_channel=payload['target_channel'],
            response_curve=payload.get('response_curve', 'linear'),
            min_value=payload.get('min_value', 0),
            max_value=payload.get('max_value', 255)
        )

        with self.mappings_lock:
            self.audio_mappings.append(mapping)

        self.respond(message, {'success': True, 'mapping_id': mapping.mapping_id})

    def _handle_beat_trigger(self, message: Message):
        """Handle beat detection trigger"""
        payload = message.payload
        beat_number = payload.get('beat_number', 0)

        self.last_beat_time = time.time()

        with self.stats_lock:
            self.stats['beats_detected'] += 1

        # Trigger beat-synced scenes
        with self.scenes_lock:
            for scene in self.scenes.values():
                if scene.sync_to_beat:
                    for fixture_id, channel_values in scene.fixture_states.items():
                        self._apply_fixture_values(fixture_id, channel_values, 0.1)

        self.publish("visual.beat.detected", {'beat_number': beat_number}, priority=Priority.HIGH)

    def _handle_audio_analysis(self, message: Message):
        """Handle audio spectrum analysis"""
        payload = message.payload
        spectrum = payload.get('spectrum', [])

        if not spectrum:
            return

        # Apply audio-reactive mappings
        with self.mappings_lock:
            for mapping in self.audio_mappings:
                if not mapping.enabled:
                    continue

                # Calculate energy in frequency band
                energy = self._calculate_band_energy(spectrum, mapping.frequency_band)

                # Map to DMX value
                if mapping.response_curve == "linear":
                    value = int(mapping.min_value + (mapping.max_value - mapping.min_value) * energy)
                elif mapping.response_curve == "exponential":
                    value = int(mapping.min_value + (mapping.max_value - mapping.min_value) * (energy ** 2))
                else:
                    value = int(mapping.min_value + (mapping.max_value - mapping.min_value) * energy)

                # Apply to fixture
                self._apply_fixture_values(mapping.target_fixture, {mapping.target_channel: value}, 0.0)

    def _handle_clock_position(self, message: Message):
        """Handle clock position for beat detection"""
        payload = message.payload
        beat = payload.get('beat', 0.0)

        # Detect beat transitions
        current_beat = int(beat)
        if not hasattr(self, '_last_beat'):
            self._last_beat = current_beat

        if current_beat != self._last_beat:  # Beat just occurred
            self._handle_beat_trigger(Message(
                topic="visual.beat.trigger",
                sender="sync",
                payload={'beat_number': current_beat}
            ))
            self._last_beat = current_beat

    def _apply_fixture_values(self, fixture_id: str, channel_values: Dict[int, int], fade_time: float):
        """Apply values to a fixture"""
        with self.fixtures_lock:
            if fixture_id not in self.fixtures:
                return

            fixture = self.fixtures[fixture_id]

            with self.dmx_lock:
                for channel, value in channel_values.items():
                    dmx_address = fixture.dmx_start_address + channel - 1
                    if 0 <= dmx_address < 512:
                        self.dmx_universe[dmx_address] = value
                    fixture.current_values[channel] = value

    def _calculate_band_energy(self, spectrum: List[float], frequency_band: Tuple[float, float]) -> float:
        """Calculate energy in frequency band"""
        # Simplified energy calculation
        if not spectrum:
            return 0.0

        # Assume spectrum covers 0-20kHz evenly
        freq_per_bin = 20000.0 / len(spectrum)
        low_bin = int(frequency_band[0] / freq_per_bin)
        high_bin = int(frequency_band[1] / freq_per_bin)

        low_bin = max(0, min(low_bin, len(spectrum) - 1))
        high_bin = max(0, min(high_bin, len(spectrum) - 1))

        if low_bin >= high_bin:
            return 0.0

        energy = np.mean(spectrum[low_bin:high_bin])
        return min(1.0, energy)

    def _start_output_thread(self):
        """Start DMX output thread"""
        self.output_active = True
        self.output_thread = threading.Thread(
            target=self._output_worker,
            name=f"{self.agent_id}_output",
            daemon=True
        )
        self.output_thread.start()

    def _stop_output_thread(self):
        """Stop DMX output thread"""
        self.output_active = False
        if self.output_thread:
            self.output_thread.join(timeout=2.0)

    def _output_worker(self):
        """DMX output worker"""
        while self.output_active:
            try:
                # In production, this would send DMX/ArtNet packets
                with self.dmx_lock:
                    # Simulate DMX output
                    pass

                time.sleep(0.033)  # ~30 FPS update rate

            except Exception as e:
                logger.error(f"Error in output worker: {e}")
