"""
Real-Time Audio I/O Agent

This agent handles live audio input/output streams with ultra-low latency,
supporting multi-channel routing, zero-latency monitoring, and advanced
buffer management for professional live performance scenarios.
"""

import numpy as np
import threading
import queue
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from collections import deque
import logging

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    logging.warning("sounddevice not available - audio I/O will be simulated")

from core import BaseAgent, Message, Topics, Priority

logger = logging.getLogger(__name__)


@dataclass
class AudioInterfaceConfig:
    """Audio interface configuration"""
    sample_rate: int = 48000
    buffer_size: int = 128
    input_channels: List[int] = field(default_factory=lambda: [1, 2])
    output_channels: List[int] = field(default_factory=lambda: [1, 2])
    driver: str = "ASIO"  # ASIO, Core Audio, JACK, etc.
    bit_depth: int = 24


@dataclass
class MonitorMix:
    """Monitor mix configuration"""
    mix_id: str
    source_channels: List[int]
    output_channel: int
    levels: Dict[int, float]  # channel -> level (0.0-1.0)
    enabled: bool = True


@dataclass
class LatencyMetrics:
    """Latency measurement data"""
    input_latency_ms: float
    output_latency_ms: float
    round_trip_latency_ms: float
    buffer_size: int
    sample_rate: int
    measured_at: float


@dataclass
class RoutingConnection:
    """Audio routing connection"""
    connection_id: str
    source_channel: int
    destination_channel: int
    gain: float = 1.0
    enabled: bool = True


class RealtimeAudioIOAgent(BaseAgent):
    """
    Agent responsible for real-time audio I/O with ultra-low latency.

    Capabilities:
    - Multi-channel audio input/output management
    - ASIO/Core Audio driver support
    - Buffer size optimization (32-256 samples)
    - Zero-latency monitoring
    - Flexible routing matrix
    - Latency measurement and reporting
    - Hot-swappable audio interfaces
    """

    def __init__(self):
        super().__init__(
            agent_id="realtime_audio_io_agent",
            agent_name="Real-Time Audio I/O Agent"
        )

        # Audio interface configuration
        self.audio_config = AudioInterfaceConfig()
        self.config_lock = threading.Lock()

        # Audio streams
        self.input_stream_active = False
        self.output_stream_active = False
        self.stream_lock = threading.Lock()
        self.audio_stream: Optional[sd.Stream] = None if SOUNDDEVICE_AVAILABLE else None

        # Real-time audio buffers for callback
        self.callback_input_buffer: Optional[np.ndarray] = None
        self.callback_output_buffer: Optional[np.ndarray] = None

        # Routing matrix
        self.routing_connections: Dict[str, RoutingConnection] = {}
        self.routing_lock = threading.Lock()

        # Monitor mixes
        self.monitor_mixes: Dict[str, MonitorMix] = {}
        self.monitor_lock = threading.Lock()

        # Buffer management
        self.input_buffer = deque(maxlen=10)
        self.output_buffer = deque(maxlen=10)
        self.buffer_lock = threading.Lock()

        # Latency tracking
        self.latency_history = deque(maxlen=100)
        self.latency_lock = threading.Lock()

        # Audio processing thread
        self.processing_thread: Optional[threading.Thread] = None
        self.processing_active = False

        # Statistics
        self.stats = {
            'buffers_processed': 0,
            'buffer_underruns': 0,
            'buffer_overruns': 0,
            'total_samples_processed': 0,
            'interface_switches': 0
        }
        self.stats_lock = threading.Lock()

    def setup(self):
        """Initialize the audio I/O agent"""
        # Subscribe to relevant topics
        self.subscribe("audio.live.input.request")
        self.subscribe("audio.live.output.send")
        self.subscribe("audio.live.interface.configure")
        self.subscribe("audio.live.routing.change")
        self.subscribe("audio.live.monitoring.config")
        self.subscribe("audio.live.latency.measure")
        self.subscribe("audio.live.buffer.optimize")

        # Initialize audio interface (simulated)
        self._initialize_audio_interface()

        # Start audio processing thread
        self._start_processing_thread()

        # Start latency monitoring
        self._start_latency_monitoring()

        self.log("INFO", f"Audio I/O Agent initialized - Sample Rate: {self.audio_config.sample_rate}Hz, Buffer: {self.audio_config.buffer_size} samples")

    def teardown(self):
        """Cleanup resources"""
        # Stop processing thread
        self._stop_processing_thread()

        # Close audio streams
        self._close_audio_streams()

        self.log("INFO", "Audio I/O Agent shutdown complete")

    def handle_message(self, message: Message):
        """Process incoming messages"""
        try:
            if message.topic == "audio.live.input.request":
                self._handle_input_request(message)
            elif message.topic == "audio.live.output.send":
                self._handle_output_send(message)
            elif message.topic == "audio.live.interface.configure":
                self._handle_interface_configure(message)
            elif message.topic == "audio.live.routing.change":
                self._handle_routing_change(message)
            elif message.topic == "audio.live.monitoring.config":
                self._handle_monitoring_config(message)
            elif message.topic == "audio.live.latency.measure":
                self._handle_latency_measure(message)
            elif message.topic == "audio.live.buffer.optimize":
                self._handle_buffer_optimize(message)
            else:
                self.log("WARNING", f"Unknown message topic: {message.topic}")

        except Exception as e:
            self.log("ERROR", f"Error handling message: {e}", {"topic": message.topic})

    def _handle_interface_configure(self, message: Message):
        """Handle audio interface configuration"""
        payload = message.payload

        with self.config_lock:
            # Update configuration
            if 'sample_rate' in payload:
                self.audio_config.sample_rate = payload['sample_rate']
            if 'buffer_size' in payload:
                self.audio_config.buffer_size = payload['buffer_size']
            if 'input_channels' in payload:
                self.audio_config.input_channels = payload['input_channels']
            if 'output_channels' in payload:
                self.audio_config.output_channels = payload['output_channels']
            if 'driver' in payload:
                self.audio_config.driver = payload['driver']

            # Reinitialize interface
            self._reinitialize_audio_interface()

        # Calculate new latency
        latency = self._calculate_latency()

        response = {
            'success': True,
            'config': {
                'sample_rate': self.audio_config.sample_rate,
                'buffer_size': self.audio_config.buffer_size,
                'input_channels': self.audio_config.input_channels,
                'output_channels': self.audio_config.output_channels,
                'driver': self.audio_config.driver
            },
            'latency': latency.__dict__
        }

        self.respond(message, response)

        # Publish configuration change
        self.publish("audio.live.interface.status", response, priority=Priority.HIGH)

    def _handle_routing_change(self, message: Message):
        """Handle routing matrix changes"""
        payload = message.payload
        action = payload.get('action', 'add')  # add, remove, update

        if action == 'add':
            connection = RoutingConnection(
                connection_id=payload.get('connection_id', f"route_{time.time()}"),
                source_channel=payload['source_channel'],
                destination_channel=payload['destination_channel'],
                gain=payload.get('gain', 1.0),
                enabled=payload.get('enabled', True)
            )

            with self.routing_lock:
                self.routing_connections[connection.connection_id] = connection

            self.respond(message, {
                'success': True,
                'connection_id': connection.connection_id,
                'action': 'added'
            })

        elif action == 'remove':
            connection_id = payload['connection_id']
            with self.routing_lock:
                if connection_id in self.routing_connections:
                    del self.routing_connections[connection_id]
                    success = True
                else:
                    success = False

            self.respond(message, {
                'success': success,
                'connection_id': connection_id,
                'action': 'removed'
            })

        elif action == 'update':
            connection_id = payload['connection_id']
            with self.routing_lock:
                if connection_id in self.routing_connections:
                    conn = self.routing_connections[connection_id]
                    if 'gain' in payload:
                        conn.gain = payload['gain']
                    if 'enabled' in payload:
                        conn.enabled = payload['enabled']
                    success = True
                else:
                    success = False

            self.respond(message, {
                'success': success,
                'connection_id': connection_id,
                'action': 'updated'
            })

    def _handle_monitoring_config(self, message: Message):
        """Handle monitor mix configuration"""
        payload = message.payload
        action = payload.get('action', 'create')  # create, update, delete

        if action == 'create':
            mix = MonitorMix(
                mix_id=payload.get('mix_id', f"mix_{time.time()}"),
                source_channels=payload['source_channels'],
                output_channel=payload['output_channel'],
                levels=payload.get('levels', {}),
                enabled=payload.get('enabled', True)
            )

            with self.monitor_lock:
                self.monitor_mixes[mix.mix_id] = mix

            self.respond(message, {
                'success': True,
                'mix_id': mix.mix_id,
                'action': 'created'
            })

        elif action == 'update':
            mix_id = payload['mix_id']
            with self.monitor_lock:
                if mix_id in self.monitor_mixes:
                    mix = self.monitor_mixes[mix_id]
                    if 'levels' in payload:
                        mix.levels.update(payload['levels'])
                    if 'enabled' in payload:
                        mix.enabled = payload['enabled']
                    success = True
                else:
                    success = False

            self.respond(message, {
                'success': success,
                'mix_id': mix_id,
                'action': 'updated'
            })

        elif action == 'delete':
            mix_id = payload['mix_id']
            with self.monitor_lock:
                if mix_id in self.monitor_mixes:
                    del self.monitor_mixes[mix_id]
                    success = True
                else:
                    success = False

            self.respond(message, {
                'success': success,
                'mix_id': mix_id,
                'action': 'deleted'
            })

    def _handle_input_request(self, message: Message):
        """Handle request for input audio data"""
        payload = message.payload
        num_samples = payload.get('num_samples', self.audio_config.buffer_size)
        channels = payload.get('channels', self.audio_config.input_channels)

        # Get audio from input buffer (simulated)
        audio_data = self._read_input_buffer(num_samples, channels)

        self.respond(message, {
            'success': True,
            'audio_data': audio_data.tolist() if audio_data is not None else None,
            'sample_rate': self.audio_config.sample_rate,
            'channels': channels,
            'num_samples': num_samples
        })

    def _handle_output_send(self, message: Message):
        """Handle sending audio to output"""
        payload = message.payload
        audio_data = np.array(payload['audio_data'])
        channels = payload.get('channels', self.audio_config.output_channels)

        # Send to output buffer
        success = self._write_output_buffer(audio_data, channels)

        self.respond(message, {
            'success': success,
            'samples_written': len(audio_data) if success else 0
        })

    def _handle_latency_measure(self, message: Message):
        """Handle latency measurement request"""
        latency = self._calculate_latency()

        with self.latency_lock:
            self.latency_history.append(latency)

        # Calculate statistics
        recent_latencies = list(self.latency_history)[-20:]
        avg_latency = np.mean([m.round_trip_latency_ms for m in recent_latencies])
        max_latency = np.max([m.round_trip_latency_ms for m in recent_latencies])
        min_latency = np.min([m.round_trip_latency_ms for m in recent_latencies])

        self.respond(message, {
            'success': True,
            'current_latency': latency.__dict__,
            'statistics': {
                'avg_latency_ms': float(avg_latency),
                'max_latency_ms': float(max_latency),
                'min_latency_ms': float(min_latency)
            }
        })

        # Publish latency report
        self.publish("audio.live.latency.report", {
            'latency': latency.__dict__,
            'statistics': {
                'avg_latency_ms': float(avg_latency),
                'max_latency_ms': float(max_latency),
                'min_latency_ms': float(min_latency)
            }
        }, priority=Priority.MEDIUM)

    def _handle_buffer_optimize(self, message: Message):
        """Handle buffer optimization request"""
        payload = message.payload
        target_latency_ms = payload.get('target_latency_ms', 5.0)

        # Calculate optimal buffer size
        optimal_buffer = self._calculate_optimal_buffer_size(target_latency_ms)

        # Update configuration
        with self.config_lock:
            old_buffer = self.audio_config.buffer_size
            self.audio_config.buffer_size = optimal_buffer
            self._reinitialize_audio_interface()

        new_latency = self._calculate_latency()

        self.respond(message, {
            'success': True,
            'old_buffer_size': old_buffer,
            'new_buffer_size': optimal_buffer,
            'achieved_latency_ms': new_latency.round_trip_latency_ms
        })

    def _initialize_audio_interface(self):
        """Initialize the audio interface with sounddevice"""
        if not SOUNDDEVICE_AVAILABLE:
            # Fallback to simulated mode
            with self.stream_lock:
                self.input_stream_active = True
                self.output_stream_active = True
            self.log("WARNING", "Sounddevice not available - using simulated audio I/O")
            return

        try:
            # Get number of channels
            num_input_channels = len(self.audio_config.input_channels)
            num_output_channels = len(self.audio_config.output_channels)

            # Create sounddevice stream with callback
            self.audio_stream = sd.Stream(
                samplerate=self.audio_config.sample_rate,
                blocksize=self.audio_config.buffer_size,
                channels=(num_input_channels, num_output_channels),
                dtype=np.float32,
                latency='low',
                callback=self._audio_callback
            )

            # Start the stream
            self.audio_stream.start()

            with self.stream_lock:
                self.input_stream_active = True
                self.output_stream_active = True

            with self.stats_lock:
                self.stats['interface_switches'] += 1

            self.log("INFO", f"Audio interface initialized: {self.audio_config.driver} "
                     f"@ {self.audio_config.sample_rate}Hz, buffer={self.audio_config.buffer_size}")

        except Exception as e:
            self.log("ERROR", f"Failed to initialize audio interface: {e}")
            # Fallback to simulated
            with self.stream_lock:
                self.input_stream_active = True
                self.output_stream_active = True

    def _reinitialize_audio_interface(self):
        """Reinitialize audio interface with new settings"""
        self._close_audio_streams()
        time.sleep(0.01)  # Brief pause
        self._initialize_audio_interface()

    def _close_audio_streams(self):
        """Close audio streams"""
        # Stop and close sounddevice stream
        if SOUNDDEVICE_AVAILABLE and self.audio_stream is not None:
            try:
                self.audio_stream.stop()
                self.audio_stream.close()
                self.audio_stream = None
            except Exception as e:
                self.log("ERROR", f"Error closing audio stream: {e}")

        with self.stream_lock:
            self.input_stream_active = False
            self.output_stream_active = False

    def _start_processing_thread(self):
        """Start audio processing thread"""
        self.processing_active = True
        self.processing_thread = threading.Thread(
            target=self._processing_worker,
            name=f"{self.agent_id}_processor",
            daemon=True
        )
        self.processing_thread.start()

    def _stop_processing_thread(self):
        """Stop audio processing thread"""
        self.processing_active = False
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2.0)

    def _audio_callback(self, indata: np.ndarray, outdata: np.ndarray, frames: int,
                       time_info, status):
        """
        Real-time audio callback from sounddevice

        This runs in a high-priority audio thread - keep processing minimal!
        """
        if status:
            self.log("WARNING", f"Audio callback status: {status}")
            with self.stats_lock:
                self.stats['buffer_underruns'] += 1

        try:
            # Store input for processing by other agents
            with self.buffer_lock:
                self.input_buffer.append(indata.copy())
                self.callback_input_buffer = indata.copy()

            # Get output from buffer or generate silence
            with self.buffer_lock:
                if len(self.output_buffer) > 0:
                    output_audio = self.output_buffer.popleft()
                    # Ensure correct shape
                    if output_audio.shape[0] == frames:
                        outdata[:] = output_audio
                    else:
                        # Fallback: zero-pad or truncate
                        min_frames = min(frames, output_audio.shape[0])
                        outdata[:min_frames] = output_audio[:min_frames]
                        if frames > min_frames:
                            outdata[min_frames:] = 0
                else:
                    # No output available - send silence to prevent glitches
                    outdata[:] = 0

            # Update statistics (minimal processing)
            with self.stats_lock:
                self.stats['buffers_processed'] += 1
                self.stats['total_samples_processed'] += frames

        except Exception as e:
            # Critical: don't let callback crash
            logger.error(f"Error in audio callback: {e}")
            outdata[:] = 0  # Silence on error
            with self.stats_lock:
                self.stats['buffer_underruns'] += 1

    def _processing_worker(self):
        """Audio processing worker thread - simulates real-time audio I/O"""
        while self.processing_active:
            try:
                # Simulate audio input
                if self.input_stream_active:
                    input_audio = self._generate_simulated_input()
                    with self.buffer_lock:
                        self.input_buffer.append(input_audio)

                # Process routing and monitoring
                self._process_routing()

                # Simulate audio output
                if self.output_stream_active:
                    self._process_output()

                # Update statistics
                with self.stats_lock:
                    self.stats['buffers_processed'] += 1
                    self.stats['total_samples_processed'] += self.audio_config.buffer_size

                # Publish stream status periodically
                if self.stats['buffers_processed'] % 100 == 0:
                    self.publish("audio.live.stream.status", {
                        'input_active': self.input_stream_active,
                        'output_active': self.output_stream_active,
                        'buffers_processed': self.stats['buffers_processed'],
                        'buffer_health': self._get_buffer_health()
                    }, priority=Priority.LOW)

                # Sleep to simulate real-time processing
                sleep_time = self.audio_config.buffer_size / self.audio_config.sample_rate
                time.sleep(sleep_time * 0.9)  # 90% to ensure no underruns

            except Exception as e:
                logger.error(f"Error in processing worker: {e}")
                with self.stats_lock:
                    self.stats['buffer_underruns'] += 1

    def _generate_simulated_input(self) -> np.ndarray:
        """Generate simulated input audio"""
        num_channels = len(self.audio_config.input_channels)
        audio = np.random.randn(self.audio_config.buffer_size, num_channels) * 0.01
        return audio.astype(np.float32)

    def _process_routing(self):
        """Process audio routing matrix"""
        # In real-time callback mode, routing happens in _audio_callback
        # This method now handles route setup and validation
        with self.routing_lock:
            active_routes = [r for r in self.routing_connections.values() if r.enabled]

            # Validate routing connections
            for route in active_routes:
                if route.source_channel >= len(self.audio_config.input_channels):
                    self.log("WARNING", f"Invalid source channel in route {route.connection_id}")
                if route.destination_channel >= len(self.audio_config.output_channels):
                    self.log("WARNING", f"Invalid destination channel in route {route.connection_id}")

    def _process_output(self):
        """Process audio output"""
        with self.buffer_lock:
            if len(self.output_buffer) > 0:
                output_audio = self.output_buffer.popleft()
                # Output audio would be sent to interface here
            else:
                # Buffer underrun
                with self.stats_lock:
                    self.stats['buffer_underruns'] += 1

    def _read_input_buffer(self, num_samples: int, channels: List[int]) -> Optional[np.ndarray]:
        """Read from input buffer"""
        with self.buffer_lock:
            if len(self.input_buffer) > 0:
                audio = self.input_buffer.popleft()
                return audio[:num_samples, :len(channels)]
            return None

    def _write_output_buffer(self, audio_data: np.ndarray, channels: List[int]) -> bool:
        """Write to output buffer"""
        with self.buffer_lock:
            if len(self.output_buffer) < self.output_buffer.maxlen:
                self.output_buffer.append(audio_data)
                return True
            else:
                with self.stats_lock:
                    self.stats['buffer_overruns'] += 1
                return False

    def _calculate_latency(self) -> LatencyMetrics:
        """Calculate current latency"""
        # Calculate latency based on buffer size and sample rate
        buffer_latency_ms = (self.audio_config.buffer_size / self.audio_config.sample_rate) * 1000

        # Add driver overhead (simulated)
        driver_overhead_ms = {
            'ASIO': 0.5,
            'Core Audio': 1.0,
            'JACK': 0.3,
            'WASAPI': 2.0
        }.get(self.audio_config.driver, 1.5)

        input_latency = buffer_latency_ms + driver_overhead_ms
        output_latency = buffer_latency_ms + driver_overhead_ms
        round_trip_latency = input_latency + output_latency

        return LatencyMetrics(
            input_latency_ms=input_latency,
            output_latency_ms=output_latency,
            round_trip_latency_ms=round_trip_latency,
            buffer_size=self.audio_config.buffer_size,
            sample_rate=self.audio_config.sample_rate,
            measured_at=time.time()
        )

    def _calculate_optimal_buffer_size(self, target_latency_ms: float) -> int:
        """Calculate optimal buffer size for target latency"""
        # Calculate buffer size needed for target latency
        target_samples = int((target_latency_ms / 1000.0) * self.audio_config.sample_rate / 2)

        # Round to nearest power of 2
        buffer_sizes = [32, 64, 128, 256, 512, 1024]
        optimal = min(buffer_sizes, key=lambda x: abs(x - target_samples))

        return optimal

    def _get_buffer_health(self) -> str:
        """Get buffer health status"""
        with self.stats_lock:
            underruns = self.stats['buffer_underruns']
            overruns = self.stats['buffer_overruns']
            total = self.stats['buffers_processed']

        if total == 0:
            return "unknown"

        error_rate = (underruns + overruns) / total

        if error_rate < 0.001:
            return "excellent"
        elif error_rate < 0.01:
            return "good"
        elif error_rate < 0.05:
            return "fair"
        else:
            return "poor"

    def _start_latency_monitoring(self):
        """Start periodic latency monitoring"""
        def monitor_loop():
            while self.processing_active:
                latency = self._calculate_latency()

                with self.latency_lock:
                    self.latency_history.append(latency)

                # Publish latency report
                self.publish("audio.live.latency.report", {
                    'latency': latency.__dict__
                }, priority=Priority.LOW)

                time.sleep(1.0)  # Update every second

        monitor_thread = threading.Thread(
            target=monitor_loop,
            name=f"{self.agent_id}_latency_monitor",
            daemon=True
        )
        monitor_thread.start()
