"""
Synchronization & Clock Agent

Manages tempo, timing synchronization, MIDI clock, Ableton Link, and transport control.
"""

import threading
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from collections import deque
import logging

from core import BaseAgent, Message, Topics, Priority

logger = logging.getLogger(__name__)


@dataclass
class ClockState:
    """Clock state information"""
    bpm: float = 120.0
    time_signature_numerator: int = 4
    time_signature_denominator: int = 4
    current_beat: float = 0.0
    current_bar: int = 0
    is_playing: bool = False
    song_position: float = 0.0  # seconds


class SynchronizationClockAgent(BaseAgent):
    """Agent for tempo and timing synchronization"""

    def __init__(self):
        super().__init__(
            agent_id="synchronization_clock_agent",
            agent_name="Synchronization & Clock Agent"
        )

        self.clock_state = ClockState()
        self.clock_lock = threading.Lock()

        # Tap tempo
        self.tap_times = deque(maxlen=8)

        # MIDI clock
        self.midi_clock_enabled = False
        self.midi_clock_outputs: list = []

        # Ableton Link
        self.link_enabled = False
        self.link_session_peers: int = 0

        # Clock thread
        self.clock_thread: Optional[threading.Thread] = None
        self.clock_active = False

        self.stats = {
            'tempo_changes': 0,
            'midi_clock_pulses': 0,
            'tap_tempo_uses': 0
        }
        self.stats_lock = threading.Lock()

    def setup(self):
        """Initialize the synchronization agent"""
        self.subscribe("sync.tempo.set")
        self.subscribe("sync.tap.tempo")
        self.subscribe("sync.transport.play")
        self.subscribe("sync.transport.stop")
        self.subscribe("sync.transport.pause")
        self.subscribe("sync.midi.clock.enable")
        self.subscribe("sync.link.enable")
        self.subscribe("sync.tempo.detect")

        self._start_clock_thread()
        self.log("INFO", "Synchronization & Clock Agent initialized")

    def teardown(self):
        """Cleanup resources"""
        self._stop_clock_thread()
        self.log("INFO", "Synchronization & Clock Agent shutdown complete")

    def handle_message(self, message: Message):
        """Process incoming messages"""
        try:
            if message.topic == "sync.tempo.set":
                self._handle_tempo_set(message)
            elif message.topic == "sync.tap.tempo":
                self._handle_tap_tempo(message)
            elif message.topic == "sync.transport.play":
                self._handle_transport_play(message)
            elif message.topic == "sync.transport.stop":
                self._handle_transport_stop(message)
            elif message.topic == "sync.transport.pause":
                self._handle_transport_pause(message)
            elif message.topic == "sync.midi.clock.enable":
                self._handle_midi_clock_enable(message)
            elif message.topic == "sync.link.enable":
                self._handle_link_enable(message)
            elif message.topic == "sync.tempo.detect":
                self._handle_tempo_detect(message)
        except Exception as e:
            self.log("ERROR", f"Error handling message: {e}", {"topic": message.topic})

    def _handle_tempo_set(self, message: Message):
        """Handle tempo change"""
        payload = message.payload
        bpm = payload['bpm']
        time_signature = payload.get('time_signature', '4/4')
        transition_time = payload.get('transition_time', 0.0)

        with self.clock_lock:
            self.clock_state.bpm = bpm
            parts = time_signature.split('/')
            self.clock_state.time_signature_numerator = int(parts[0])
            self.clock_state.time_signature_denominator = int(parts[1])

        with self.stats_lock:
            self.stats['tempo_changes'] += 1

        # Publish tempo change
        self.publish("sync.clock.tempo", {
            'bpm': bpm,
            'time_signature': time_signature
        }, priority=Priority.HIGH)

        self.respond(message, {'success': True, 'bpm': bpm})

    def _handle_tap_tempo(self, message: Message):
        """Handle tap tempo input"""
        current_time = time.time()
        self.tap_times.append(current_time)

        if len(self.tap_times) >= 2:
            # Calculate average interval
            intervals = []
            for i in range(1, len(self.tap_times)):
                intervals.append(self.tap_times[i] - self.tap_times[i-1])

            avg_interval = sum(intervals) / len(intervals)
            bpm = 60.0 / avg_interval

            # Update tempo
            with self.clock_lock:
                self.clock_state.bpm = bpm

            with self.stats_lock:
                self.stats['tap_tempo_uses'] += 1

            # Publish
            self.publish("sync.clock.tempo", {'bpm': bpm}, priority=Priority.HIGH)

            self.respond(message, {'success': True, 'bpm': bpm, 'taps': len(self.tap_times)})
        else:
            self.respond(message, {'success': True, 'taps': len(self.tap_times)})

    def _handle_transport_play(self, message: Message):
        """Handle transport play"""
        with self.clock_lock:
            self.clock_state.is_playing = True

        self.publish("sync.transport.control", {'state': 'playing'}, priority=Priority.HIGH)
        self.respond(message, {'success': True, 'state': 'playing'})

    def _handle_transport_stop(self, message: Message):
        """Handle transport stop"""
        with self.clock_lock:
            self.clock_state.is_playing = False
            self.clock_state.current_beat = 0.0
            self.clock_state.current_bar = 0
            self.clock_state.song_position = 0.0

        self.publish("sync.transport.control", {'state': 'stopped'}, priority=Priority.HIGH)
        self.respond(message, {'success': True, 'state': 'stopped'})

    def _handle_transport_pause(self, message: Message):
        """Handle transport pause"""
        with self.clock_lock:
            self.clock_state.is_playing = False

        self.publish("sync.transport.control", {'state': 'paused'}, priority=Priority.HIGH)
        self.respond(message, {'success': True, 'state': 'paused'})

    def _handle_midi_clock_enable(self, message: Message):
        """Handle MIDI clock enable"""
        payload = message.payload
        enable = payload.get('enable', True)
        midi_port = payload.get('midi_port', 'default')

        self.midi_clock_enabled = enable
        if enable and midi_port not in self.midi_clock_outputs:
            self.midi_clock_outputs.append(midi_port)

        self.respond(message, {'success': True, 'midi_clock_enabled': self.midi_clock_enabled})

    def _handle_link_enable(self, message: Message):
        """Handle Ableton Link enable"""
        payload = message.payload
        enable = payload.get('enable', True)
        set_tempo = payload.get('set_tempo', False)

        self.link_enabled = enable

        self.respond(message, {
            'success': True,
            'link_enabled': self.link_enabled,
            'session_peers': self.link_session_peers
        })

    def _handle_tempo_detect(self, message: Message):
        """Handle tempo detection from audio"""
        payload = message.payload
        # Simulated tempo detection
        detected_bpm = 120.0  # Would use actual audio analysis

        self.respond(message, {'success': True, 'detected_bpm': detected_bpm})

    def _start_clock_thread(self):
        """Start clock thread"""
        self.clock_active = True
        self.clock_thread = threading.Thread(
            target=self._clock_worker,
            name=f"{self.agent_id}_clock",
            daemon=True
        )
        self.clock_thread.start()

    def _stop_clock_thread(self):
        """Stop clock thread"""
        self.clock_active = False
        if self.clock_thread:
            self.clock_thread.join(timeout=2.0)

    def _clock_worker(self):
        """Clock worker thread"""
        last_time = time.time()

        while self.clock_active:
            try:
                current_time = time.time()
                delta_time = current_time - last_time
                last_time = current_time

                with self.clock_lock:
                    if self.clock_state.is_playing:
                        # Update position
                        beats_per_second = self.clock_state.bpm / 60.0
                        delta_beats = beats_per_second * delta_time

                        self.clock_state.current_beat += delta_beats
                        self.clock_state.song_position += delta_time

                        # Update bar
                        beats_per_bar = self.clock_state.time_signature_numerator
                        if self.clock_state.current_beat >= beats_per_bar:
                            self.clock_state.current_bar += 1
                            self.clock_state.current_beat -= beats_per_bar

                        # Publish position
                        if int(self.clock_state.current_beat * 10) % 10 == 0:  # Every beat
                            self.publish("sync.clock.position", {
                                'beat': self.clock_state.current_beat,
                                'bar': self.clock_state.current_bar,
                                'time_seconds': self.clock_state.song_position
                            }, priority=Priority.MEDIUM)

                        # MIDI clock (24 pulses per quarter note)
                        if self.midi_clock_enabled:
                            self._send_midi_clock_pulse()

                time.sleep(0.001)  # 1ms precision

            except Exception as e:
                logger.error(f"Error in clock worker: {e}")

    def _send_midi_clock_pulse(self):
        """Send MIDI clock pulse"""
        with self.stats_lock:
            self.stats['midi_clock_pulses'] += 1

        self.publish("sync.midi.clock.out", {
            'pulse': True,
            'bpm': self.clock_state.bpm
        }, priority=Priority.LOW)
