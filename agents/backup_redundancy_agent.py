"""
Backup & Redundancy Agent

Ensures reliability with hot backup, automatic failover, state synchronization,
and crash recovery for live performance scenarios.
"""

import threading
import time
import json
import copy
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging

from core import BaseAgent, Message, Topics, Priority

logger = logging.getLogger(__name__)


class SystemMode(Enum):
    """System operating mode"""
    PRIMARY = "primary"
    BACKUP = "backup"
    FAILOVER = "failover"


@dataclass
class BackupConfig:
    """Backup system configuration"""
    primary_interface: str
    backup_interface: str
    sync_interval_ms: int = 100
    auto_failover: bool = True
    failover_threshold_ms: int = 50
    auto_recover: bool = True


@dataclass
class SystemState:
    """Complete system state snapshot"""
    timestamp: float
    mode: SystemMode
    active_agents: List[str] = field(default_factory=list)
    effect_chains: Dict[str, Any] = field(default_factory=dict)
    loop_tracks: Dict[str, Any] = field(default_factory=dict)
    scenes: Dict[str, Any] = field(default_factory=dict)
    midi_mappings: Dict[str, Any] = field(default_factory=dict)
    audio_routing: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceRecording:
    """Performance recording metadata"""
    recording_id: str
    output_path: str
    format: str
    bit_depth: int
    sample_rate: int
    start_time: float
    duration: float = 0.0
    file_size_mb: float = 0.0
    include_video: bool = False


class BackupRedundancyAgent(BaseAgent):
    """Agent for backup, redundancy, and crash recovery"""

    def __init__(self):
        super().__init__(
            agent_id="backup_redundancy_agent",
            agent_name="Backup & Redundancy Agent"
        )

        # Backup configuration
        self.backup_config: Optional[BackupConfig] = None
        self.config_lock = threading.Lock()

        # System state
        self.current_state = SystemState(
            timestamp=time.time(),
            mode=SystemMode.PRIMARY
        )
        self.backup_state: Optional[SystemState] = None
        self.state_lock = threading.Lock()

        # State history for recovery
        self.state_history = []
        self.max_history_size = 1000
        self.history_lock = threading.Lock()

        # Failover tracking
        self.primary_healthy = True
        self.last_primary_heartbeat = time.time()
        self.failover_active = False

        # Performance recording
        self.active_recordings: Dict[str, PerformanceRecording] = {}
        self.recordings_lock = threading.Lock()

        # Sync thread
        self.sync_thread: Optional[threading.Thread] = None
        self.sync_active = False

        # Statistics
        self.stats = {
            'state_syncs': 0,
            'failover_events': 0,
            'recoveries': 0,
            'recordings_saved': 0
        }
        self.stats_lock = threading.Lock()

    def setup(self):
        """Initialize the backup agent"""
        self.subscribe("backup.enable")
        self.subscribe("backup.configure")
        self.subscribe("backup.failover.trigger")
        self.subscribe("backup.state.sync")
        self.subscribe("backup.state.save")
        self.subscribe("backup.state.restore")
        self.subscribe("backup.recording.start")
        self.subscribe("backup.recording.stop")
        self.subscribe("system.state.changed")  # Listen for state changes
        self.subscribe("system.agent.heartbeat")  # Monitor health

        self._start_sync_thread()
        self.log("INFO", "Backup & Redundancy Agent initialized")

    def teardown(self):
        """Cleanup resources"""
        self._stop_sync_thread()

        # Stop any active recordings
        with self.recordings_lock:
            for recording_id in list(self.active_recordings.keys()):
                self._stop_recording(recording_id)

        self.log("INFO", "Backup & Redundancy Agent shutdown complete")

    def handle_message(self, message: Message):
        """Process incoming messages"""
        try:
            if message.topic == "backup.enable":
                self._handle_backup_enable(message)
            elif message.topic == "backup.configure":
                self._handle_backup_configure(message)
            elif message.topic == "backup.failover.trigger":
                self._handle_failover_trigger(message)
            elif message.topic == "backup.state.sync":
                self._handle_state_sync(message)
            elif message.topic == "backup.state.save":
                self._handle_state_save(message)
            elif message.topic == "backup.state.restore":
                self._handle_state_restore(message)
            elif message.topic == "backup.recording.start":
                self._handle_recording_start(message)
            elif message.topic == "backup.recording.stop":
                self._handle_recording_stop(message)
            elif message.topic == "system.state.changed":
                self._handle_state_changed(message)
            elif message.topic == "system.agent.heartbeat":
                self._handle_agent_heartbeat(message)
        except Exception as e:
            self.log("ERROR", f"Error handling message: {e}", {"topic": message.topic})

    def _handle_backup_enable(self, message: Message):
        """Handle backup enable"""
        payload = message.payload
        enable = payload.get('enable', True)

        if enable:
            self._start_sync_thread()
        else:
            self._stop_sync_thread()

        self.respond(message, {'success': True, 'backup_enabled': enable})

    def _handle_backup_configure(self, message: Message):
        """Handle backup configuration"""
        payload = message.payload

        with self.config_lock:
            self.backup_config = BackupConfig(
                primary_interface=payload['primary_interface'],
                backup_interface=payload['backup_interface'],
                sync_interval_ms=payload.get('sync_interval_ms', 100),
                auto_failover=payload.get('auto_failover', True),
                failover_threshold_ms=payload.get('failover_threshold_ms', 50),
                auto_recover=payload.get('auto_recover', True)
            )

        self.respond(message, {
            'success': True,
            'config': asdict(self.backup_config)
        })

        self.publish("backup.system.status", {
            'status': 'configured',
            'mode': self.current_state.mode.value
        }, priority=Priority.MEDIUM)

    def _handle_failover_trigger(self, message: Message):
        """Handle manual failover trigger"""
        payload = message.payload
        trigger_conditions = payload.get('trigger_conditions', {})

        success = self._execute_failover()

        with self.stats_lock:
            if success:
                self.stats['failover_events'] += 1

        self.respond(message, {
            'success': success,
            'new_mode': self.current_state.mode.value
        })

    def _handle_state_sync(self, message: Message):
        """Handle state sync request"""
        payload = message.payload

        # Update system state from message
        with self.state_lock:
            if 'effect_chains' in payload:
                self.current_state.effect_chains = payload['effect_chains']
            if 'loop_tracks' in payload:
                self.current_state.loop_tracks = payload['loop_tracks']
            if 'scenes' in payload:
                self.current_state.scenes = payload['scenes']

            self.current_state.timestamp = time.time()

            # Create backup copy
            self.backup_state = copy.deepcopy(self.current_state)

        with self.stats_lock:
            self.stats['state_syncs'] += 1

        self.respond(message, {'success': True})

    def _handle_state_save(self, message: Message):
        """Handle state save request"""
        payload = message.payload
        state_name = payload['state_name']
        include_audio = payload.get('include_audio', False)

        state_id = f"state_{time.time()}"

        # Save current state
        with self.state_lock:
            state_snapshot = copy.deepcopy(self.current_state)

        # Store in history
        with self.history_lock:
            self.state_history.append({
                'state_id': state_id,
                'state_name': state_name,
                'timestamp': time.time(),
                'state': state_snapshot
            })

            # Limit history size
            if len(self.state_history) > self.max_history_size:
                self.state_history.pop(0)

        self.respond(message, {
            'success': True,
            'state_id': state_id,
            'state_name': state_name
        })

        self.log("INFO", f"State saved: {state_name}")

    def _handle_state_restore(self, message: Message):
        """Handle state restore request"""
        payload = message.payload
        state_id = payload.get('state_id')
        state_name = payload.get('state_name')

        # Find state in history
        with self.history_lock:
            state_record = None

            for record in reversed(self.state_history):
                if (state_id and record['state_id'] == state_id) or \
                   (state_name and record['state_name'] == state_name):
                    state_record = record
                    break

            if state_record is None:
                self.respond(message, {'success': False, 'error': 'State not found'})
                return

            # Restore state
            with self.state_lock:
                self.current_state = copy.deepcopy(state_record['state'])

        with self.stats_lock:
            self.stats['recoveries'] += 1

        self.respond(message, {
            'success': True,
            'state_id': state_record['state_id'],
            'state_name': state_record['state_name']
        })

        # Publish restore event
        self.publish("backup.restore.state", {
            'state_id': state_record['state_id'],
            'state_name': state_record['state_name']
        }, priority=Priority.HIGH)

        self.log("INFO", f"State restored: {state_record['state_name']}")

    def _handle_recording_start(self, message: Message):
        """Handle performance recording start"""
        payload = message.payload

        recording = PerformanceRecording(
            recording_id=payload.get('recording_id', f"rec_{time.time()}"),
            output_path=payload['output_path'],
            format=payload.get('format', 'wav'),
            bit_depth=payload.get('bit_depth', 24),
            sample_rate=payload.get('sample_rate', 48000),
            start_time=time.time(),
            include_video=payload.get('include_video', False)
        )

        with self.recordings_lock:
            self.active_recordings[recording.recording_id] = recording

        self.respond(message, {
            'success': True,
            'recording_id': recording.recording_id
        })

        self.log("INFO", f"Recording started: {recording.recording_id}")

    def _handle_recording_stop(self, message: Message):
        """Handle performance recording stop"""
        payload = message.payload
        recording_id = payload['recording_id']

        success = self._stop_recording(recording_id)

        self.respond(message, {'success': success, 'recording_id': recording_id})

    def _handle_state_changed(self, message: Message):
        """Handle system state change notification"""
        # Capture state change for backup
        payload = message.payload

        with self.state_lock:
            if 'agent_id' in payload:
                agent_id = payload['agent_id']
                if agent_id not in self.current_state.active_agents:
                    self.current_state.active_agents.append(agent_id)

            self.current_state.timestamp = time.time()

    def _handle_agent_heartbeat(self, message: Message):
        """Handle agent heartbeat for health monitoring"""
        payload = message.payload
        agent_id = payload.get('agent_id')

        if agent_id == "realtime_audio_io_agent":
            # Monitor primary audio interface health
            self.last_primary_heartbeat = time.time()
            self.primary_healthy = True

    def _start_sync_thread(self):
        """Start state sync thread"""
        if self.sync_active:
            return

        self.sync_active = True
        self.sync_thread = threading.Thread(
            target=self._sync_worker,
            name=f"{self.agent_id}_sync",
            daemon=True
        )
        self.sync_thread.start()

    def _stop_sync_thread(self):
        """Stop state sync thread"""
        self.sync_active = False
        if self.sync_thread:
            self.sync_thread.join(timeout=2.0)

    def _sync_worker(self):
        """State synchronization worker"""
        while self.sync_active:
            try:
                # Check for failover conditions
                if self.backup_config and self.backup_config.auto_failover:
                    time_since_heartbeat = time.time() - self.last_primary_heartbeat

                    if time_since_heartbeat > (self.backup_config.failover_threshold_ms / 1000.0):
                        if not self.failover_active:
                            self.log("WARNING", "Primary system unresponsive, initiating failover")
                            self._execute_failover()

                # Sync state to backup
                self._sync_state_to_backup()

                # Sleep for sync interval
                sleep_time = self.backup_config.sync_interval_ms / 1000.0 if self.backup_config else 0.1
                time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Error in sync worker: {e}")

    def _sync_state_to_backup(self):
        """Synchronize state to backup system"""
        with self.state_lock:
            self.backup_state = copy.deepcopy(self.current_state)

        # Publish sync event
        self.publish("backup.state.sync", {
            'timestamp': self.current_state.timestamp,
            'mode': self.current_state.mode.value
        }, priority=Priority.LOW)

    def _execute_failover(self) -> bool:
        """Execute failover to backup system"""
        try:
            with self.state_lock:
                if self.current_state.mode == SystemMode.PRIMARY:
                    self.current_state.mode = SystemMode.FAILOVER
                    self.failover_active = True

                    # Restore from backup state
                    if self.backup_state:
                        self.current_state = copy.deepcopy(self.backup_state)
                        self.current_state.mode = SystemMode.FAILOVER

            # Publish failover event
            self.publish("backup.failover.trigger", {
                'timestamp': time.time(),
                'reason': 'primary_failure',
                'new_mode': self.current_state.mode.value
            }, priority=Priority.CRITICAL)

            self.log("INFO", "Failover executed successfully")
            return True

        except Exception as e:
            self.log("ERROR", f"Failover failed: {e}")
            return False

    def _stop_recording(self, recording_id: str) -> bool:
        """Stop a performance recording"""
        with self.recordings_lock:
            if recording_id not in self.active_recordings:
                return False

            recording = self.active_recordings[recording_id]
            recording.duration = time.time() - recording.start_time

            # Simulated file save
            recording.file_size_mb = recording.duration * 10.0  # Approximation

            del self.active_recordings[recording_id]

        with self.stats_lock:
            self.stats['recordings_saved'] += 1

        self.publish("backup.recording.save", {
            'recording_id': recording_id,
            'duration': recording.duration,
            'output_path': recording.output_path
        }, priority=Priority.MEDIUM)

        self.log("INFO", f"Recording stopped: {recording_id}, Duration: {recording.duration:.1f}s")
        return True
