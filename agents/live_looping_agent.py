"""
Live Looping Agent

This agent handles real-time loop recording, playback, and manipulation with
multi-track support, overdubbing, time-stretching, and tempo synchronization.
"""

import numpy as np
import threading
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import deque
from enum import Enum
import logging

from core import BaseAgent, Message, Topics, Priority
from .loop_processors import (
    TimeStretcher,
    PitchShifter,
    LoopSlicer,
    CrossfadeProcessor,
    LoopQuantizer,
    LoopRecorder,
    OverdubProcessor
)

logger = logging.getLogger(__name__)


class LoopMode(Enum):
    """Loop recording modes"""
    REPLACE = "replace"
    OVERDUB = "overdub"
    MULTIPLY = "multiply"
    INSERT = "insert"


class LoopState(Enum):
    """Loop playback states"""
    STOPPED = "stopped"
    RECORDING = "recording"
    PLAYING = "playing"
    OVERDUBBING = "overdubbing"
    PAUSED = "paused"


@dataclass
class LoopTrack:
    """Multi-track loop"""
    track_id: str
    track_name: str
    audio_data: np.ndarray = field(default_factory=lambda: np.array([]))
    length_beats: int = 4
    sync_to_tempo: bool = True
    state: LoopState = LoopState.STOPPED
    volume: float = 1.0
    pan: float = 0.0  # -1.0 (left) to 1.0 (right)
    reverse: bool = False
    speed: float = 1.0  # 0.5 = half speed, 2.0 = double speed
    pitch_shift: float = 0.0  # semitones
    undo_history: List[np.ndarray] = field(default_factory=list)
    redo_stack: List[np.ndarray] = field(default_factory=list)


class LiveLoopingAgent(BaseAgent):
    """
    Agent responsible for live looping functionality.

    Capabilities:
    - Multi-track loop recording
    - Synchronized loop start/stop
    - Overdubbing and multiply modes
    - Undo/redo functionality
    - Time-stretching and pitch-shifting
    - Reverse playback
    - Loop quantization
    - Tempo-locked loops
    """

    def __init__(self, sample_rate: int = 44100):
        super().__init__(
            agent_id="live_looping_agent",
            agent_name="Live Looping Agent"
        )

        # Audio configuration
        self.sample_rate = sample_rate

        # Loop tracks
        self.loop_tracks: Dict[str, LoopTrack] = {}
        self.tracks_lock = threading.Lock()

        # Master tempo and sync
        self.master_tempo: float = 120.0
        self.time_signature: str = "4/4"
        self.current_beat: float = 0.0
        self.beat_lock = threading.Lock()

        # Recording settings
        self.quantize_recording: bool = True
        self.count_in_bars: int = 0
        self.auto_record: bool = False

        # Processors
        self.time_stretcher = TimeStretcher(sample_rate)
        self.pitch_shifter = PitchShifter(sample_rate)
        self.quantizer = LoopQuantizer(sample_rate)
        self.slicer = LoopSlicer()
        self.crossfader = CrossfadeProcessor()
        self.overdubber = OverdubProcessor()

        # Active recorders (one per track)
        self.recorders: Dict[str, LoopRecorder] = {}
        self.recorders_lock = threading.Lock()

        # Playback thread
        self.playback_thread: Optional[threading.Thread] = None
        self.playback_active = False

        # Statistics
        self.stats = {
            'loops_recorded': 0,
            'overdubs_performed': 0,
            'undos_performed': 0,
            'loops_played': 0,
            'slices_created': 0
        }
        self.stats_lock = threading.Lock()

    def setup(self):
        """Initialize the looping agent"""
        # Subscribe to relevant topics
        self.subscribe("loop.track.create")
        self.subscribe("loop.track.delete")
        self.subscribe("loop.record.start")
        self.subscribe("loop.record.stop")
        self.subscribe("loop.playback.toggle")
        self.subscribe("loop.overdub.enable")
        self.subscribe("loop.clear")
        self.subscribe("loop.undo")
        self.subscribe("loop.redo")
        self.subscribe("loop.manipulate")
        self.subscribe("loop.sync.quantize")
        self.subscribe("sync.clock.tempo")  # Listen for tempo changes

        # Start playback thread
        self._start_playback_thread()

        self.log("INFO", "Live Looping Agent initialized")

    def teardown(self):
        """Cleanup resources"""
        # Stop playback thread
        self._stop_playback_thread()

        self.log("INFO", "Live Looping Agent shutdown complete")

    def handle_message(self, message: Message):
        """Process incoming messages"""
        try:
            if message.topic == "loop.track.create":
                self._handle_track_create(message)
            elif message.topic == "loop.track.delete":
                self._handle_track_delete(message)
            elif message.topic == "loop.record.start":
                self._handle_record_start(message)
            elif message.topic == "loop.record.stop":
                self._handle_record_stop(message)
            elif message.topic == "loop.playback.toggle":
                self._handle_playback_toggle(message)
            elif message.topic == "loop.overdub.enable":
                self._handle_overdub_enable(message)
            elif message.topic == "loop.clear":
                self._handle_clear(message)
            elif message.topic == "loop.undo":
                self._handle_undo(message)
            elif message.topic == "loop.redo":
                self._handle_redo(message)
            elif message.topic == "loop.manipulate":
                self._handle_manipulate(message)
            elif message.topic == "loop.sync.quantize":
                self._handle_sync_quantize(message)
            elif message.topic == "sync.clock.tempo":
                self._handle_tempo_change(message)
            else:
                self.log("WARNING", f"Unknown message topic: {message.topic}")

        except Exception as e:
            self.log("ERROR", f"Error handling message: {e}", {"topic": message.topic})

    def _handle_track_create(self, message: Message):
        """Handle loop track creation"""
        payload = message.payload

        track = LoopTrack(
            track_id=payload.get('track_id', f"track_{time.time()}"),
            track_name=payload['track_name'],
            length_beats=payload.get('length_beats', 4),
            sync_to_tempo=payload.get('sync_to_tempo', True),
            volume=payload.get('volume', 1.0),
            pan=payload.get('pan', 0.0)
        )

        with self.tracks_lock:
            self.loop_tracks[track.track_id] = track

        self.respond(message, {
            'success': True,
            'track_id': track.track_id,
            'track_name': track.track_name
        })

        self.publish("loop.track.created", {
            'track_id': track.track_id,
            'track_name': track.track_name
        }, priority=Priority.MEDIUM)

    def _handle_track_delete(self, message: Message):
        """Handle loop track deletion"""
        payload = message.payload
        track_id = payload['track_id']

        with self.tracks_lock:
            if track_id in self.loop_tracks:
                del self.loop_tracks[track_id]
                success = True
            else:
                success = False

        self.respond(message, {'success': success, 'track_id': track_id})

    def _handle_record_start(self, message: Message):
        """Handle loop recording start"""
        payload = message.payload
        track_id = payload['track_id']
        mode = LoopMode(payload.get('mode', 'replace'))
        quantize = payload.get('quantize', self.quantize_recording)

        with self.tracks_lock:
            if track_id not in self.loop_tracks:
                self.respond(message, {'success': False, 'error': 'Track not found'})
                return

            track = self.loop_tracks[track_id]

            # Save to undo history
            if len(track.audio_data) > 0:
                track.undo_history.append(track.audio_data.copy())
                track.redo_stack.clear()

            # Set state
            if mode == LoopMode.REPLACE:
                track.state = LoopState.RECORDING
                track.audio_data = np.array([])
            elif mode == LoopMode.OVERDUB:
                track.state = LoopState.OVERDUBBING
            elif mode == LoopMode.MULTIPLY:
                track.state = LoopState.RECORDING
                # Keep existing audio, will multiply length

        with self.stats_lock:
            self.stats['loops_recorded'] += 1

        self.respond(message, {
            'success': True,
            'track_id': track_id,
            'mode': mode.value,
            'state': track.state.value
        })

        self.publish("loop.record.started", {
            'track_id': track_id,
            'mode': mode.value
        }, priority=Priority.HIGH)

    def _handle_record_stop(self, message: Message):
        """Handle loop recording stop"""
        payload = message.payload
        track_id = payload['track_id']

        with self.tracks_lock:
            if track_id not in self.loop_tracks:
                self.respond(message, {'success': False, 'error': 'Track not found'})
                return

            track = self.loop_tracks[track_id]

            # Stop recording and start playback
            if track.state in [LoopState.RECORDING, LoopState.OVERDUBBING]:
                track.state = LoopState.PLAYING

                # Quantize loop length if enabled
                if self.quantize_recording and track.sync_to_tempo:
                    track.audio_data = self._quantize_loop_length(track)

        self.respond(message, {
            'success': True,
            'track_id': track_id,
            'state': track.state.value,
            'length_samples': len(track.audio_data)
        })

        self.publish("loop.record.stopped", {
            'track_id': track_id
        }, priority=Priority.HIGH)

    def _handle_playback_toggle(self, message: Message):
        """Handle loop playback toggle"""
        payload = message.payload
        track_id = payload['track_id']

        with self.tracks_lock:
            if track_id not in self.loop_tracks:
                self.respond(message, {'success': False, 'error': 'Track not found'})
                return

            track = self.loop_tracks[track_id]

            # Toggle playback state
            if track.state == LoopState.PLAYING:
                track.state = LoopState.STOPPED
            elif track.state == LoopState.STOPPED:
                track.state = LoopState.PLAYING

        self.respond(message, {
            'success': True,
            'track_id': track_id,
            'state': track.state.value
        })

    def _handle_overdub_enable(self, message: Message):
        """Handle overdub mode enable"""
        payload = message.payload
        track_id = payload['track_id']

        with self.tracks_lock:
            if track_id not in self.loop_tracks:
                self.respond(message, {'success': False, 'error': 'Track not found'})
                return

            track = self.loop_tracks[track_id]

            # Save to undo history
            track.undo_history.append(track.audio_data.copy())
            track.redo_stack.clear()

            track.state = LoopState.OVERDUBBING

        with self.stats_lock:
            self.stats['overdubs_performed'] += 1

        self.respond(message, {
            'success': True,
            'track_id': track_id,
            'state': track.state.value
        })

    def _handle_clear(self, message: Message):
        """Handle loop clear"""
        payload = message.payload
        track_id = payload['track_id']

        with self.tracks_lock:
            if track_id not in self.loop_tracks:
                self.respond(message, {'success': False, 'error': 'Track not found'})
                return

            track = self.loop_tracks[track_id]

            # Save to undo history
            track.undo_history.append(track.audio_data.copy())
            track.redo_stack.clear()

            # Clear audio
            track.audio_data = np.array([])
            track.state = LoopState.STOPPED

        self.respond(message, {
            'success': True,
            'track_id': track_id
        })

    def _handle_undo(self, message: Message):
        """Handle loop undo"""
        payload = message.payload
        track_id = payload['track_id']

        with self.tracks_lock:
            if track_id not in self.loop_tracks:
                self.respond(message, {'success': False, 'error': 'Track not found'})
                return

            track = self.loop_tracks[track_id]

            if len(track.undo_history) > 0:
                # Save current state to redo stack
                track.redo_stack.append(track.audio_data.copy())

                # Restore previous state
                track.audio_data = track.undo_history.pop()
                success = True

                with self.stats_lock:
                    self.stats['undos_performed'] += 1
            else:
                success = False

        self.respond(message, {
            'success': success,
            'track_id': track_id,
            'undo_available': len(track.undo_history) > 0
        })

    def _handle_redo(self, message: Message):
        """Handle loop redo"""
        payload = message.payload
        track_id = payload['track_id']

        with self.tracks_lock:
            if track_id not in self.loop_tracks:
                self.respond(message, {'success': False, 'error': 'Track not found'})
                return

            track = self.loop_tracks[track_id]

            if len(track.redo_stack) > 0:
                # Save current state to undo history
                track.undo_history.append(track.audio_data.copy())

                # Restore next state
                track.audio_data = track.redo_stack.pop()
                success = True
            else:
                success = False

        self.respond(message, {
            'success': success,
            'track_id': track_id,
            'redo_available': len(track.redo_stack) > 0
        })

    def _handle_manipulate(self, message: Message):
        """Handle loop manipulation"""
        payload = message.payload
        track_id = payload['track_id']
        operation = payload['operation']
        parameters = payload.get('parameters', {})

        with self.tracks_lock:
            if track_id not in self.loop_tracks:
                self.respond(message, {'success': False, 'error': 'Track not found'})
                return

            track = self.loop_tracks[track_id]

            # Save to undo history
            track.undo_history.append(track.audio_data.copy())
            track.redo_stack.clear()

            # Apply operation
            if operation == "reverse":
                track.reverse = not track.reverse
                track.audio_data = np.flip(track.audio_data)
            elif operation == "half_speed":
                track.speed = 0.5
                track.audio_data = self.time_stretcher.stretch(track.audio_data, 2.0)
            elif operation == "double_speed":
                track.speed = 2.0
                track.audio_data = self.time_stretcher.stretch(track.audio_data, 0.5)
            elif operation == "pitch_shift":
                semitones = parameters.get('semitones', 0.0)
                track.pitch_shift = semitones
                track.audio_data = self.pitch_shifter.shift(track.audio_data, semitones)
            elif operation == "time_stretch":
                stretch_factor = parameters.get('factor', 1.0)
                track.audio_data = self.time_stretcher.stretch(track.audio_data, stretch_factor)
            elif operation == "normalize":
                track.audio_data = self._normalize_audio(track.audio_data)
            elif operation == "slice_by_beats":
                num_slices = parameters.get('num_beats', track.length_beats)
                slices = self.slicer.slice_by_beats(
                    track.audio_data,
                    num_slices,
                    self.master_tempo,
                    self.sample_rate
                )
                # Store slices as metadata (could be used for rearrangement)
                with self.stats_lock:
                    self.stats['slices_created'] += len(slices)
            elif operation == "crossfade_loop":
                crossfade_ms = parameters.get('crossfade_ms', 10.0)
                crossfade_samples = int((crossfade_ms / 1000.0) * self.sample_rate)
                track.audio_data = self.crossfader.loop_crossfade(track.audio_data, crossfade_samples)
            elif operation == "overdub":
                new_audio = np.array(parameters.get('audio_data', []))
                mix = parameters.get('mix', 0.5)
                track.audio_data = self.overdubber.overdub(track.audio_data, new_audio, mix)

        self.respond(message, {
            'success': True,
            'track_id': track_id,
            'operation': operation
        })

    def _handle_sync_quantize(self, message: Message):
        """Handle loop sync quantization"""
        payload = message.payload
        master_tempo = payload.get('master_tempo', self.master_tempo)
        time_signature = payload.get('time_signature', self.time_signature)

        with self.beat_lock:
            self.master_tempo = master_tempo
            self.time_signature = time_signature

        # Quantize all synced loops
        with self.tracks_lock:
            for track in self.loop_tracks.values():
                if track.sync_to_tempo and len(track.audio_data) > 0:
                    track.audio_data = self._quantize_loop_length(track)

        self.respond(message, {
            'success': True,
            'master_tempo': master_tempo,
            'time_signature': time_signature
        })

    def _handle_tempo_change(self, message: Message):
        """Handle tempo change from sync agent"""
        payload = message.payload
        new_tempo = payload.get('bpm', self.master_tempo)

        with self.beat_lock:
            self.master_tempo = new_tempo

        # Time-stretch loops to match new tempo if needed
        self._adjust_loops_to_tempo()

    def _start_playback_thread(self):
        """Start playback processing thread"""
        self.playback_active = True
        self.playback_thread = threading.Thread(
            target=self._playback_worker,
            name=f"{self.agent_id}_playback",
            daemon=True
        )
        self.playback_thread.start()

    def _stop_playback_thread(self):
        """Stop playback processing thread"""
        self.playback_active = False
        if self.playback_thread and self.playback_thread.is_alive():
            self.playback_thread.join(timeout=2.0)

    def _playback_worker(self):
        """Playback processing worker"""
        while self.playback_active:
            try:
                # Update beat position
                with self.beat_lock:
                    beat_increment = (self.master_tempo / 60.0) * 0.01  # 10ms intervals
                    self.current_beat += beat_increment

                # Process playing loops
                with self.tracks_lock:
                    for track in self.loop_tracks.values():
                        if track.state == LoopState.PLAYING:
                            # Publish loop audio output
                            self._process_loop_playback(track)

                            with self.stats_lock:
                                self.stats['loops_played'] += 1

                time.sleep(0.01)  # 10ms processing interval

            except Exception as e:
                logger.error(f"Error in playback worker: {e}")

    def _process_loop_playback(self, track: LoopTrack):
        """Process loop playback (simulated)"""
        if len(track.audio_data) == 0:
            return

        # In production, this would output audio through the audio I/O agent
        pass

    def _quantize_loop_length(self, track: LoopTrack) -> np.ndarray:
        """Quantize loop length to beat grid"""
        if len(track.audio_data) == 0:
            return track.audio_data

        return self.quantizer.quantize_to_beats(
            track.audio_data,
            track.length_beats,
            self.master_tempo
        )

    def _time_stretch(self, audio: np.ndarray, factor: float) -> np.ndarray:
        """Time-stretch audio using phase vocoder"""
        if len(audio) == 0:
            return audio

        return self.time_stretcher.stretch(audio, factor)

    def _normalize_audio(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio to peak level"""
        if len(audio) == 0:
            return audio

        peak = np.max(np.abs(audio))
        if peak > 0:
            return audio / peak * 0.95
        return audio

    def _adjust_loops_to_tempo(self):
        """Adjust all loops to match new tempo"""
        with self.tracks_lock:
            for track in self.loop_tracks.values():
                if track.sync_to_tempo and len(track.audio_data) > 0:
                    track.audio_data = self._quantize_loop_length(track)
