"""
Performance Automation Agent

This agent handles parameter automation recording and playback, scene management,
macro controls, and timeline-based cues for live performances.
"""

import threading
import time
import numpy as np
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

from core import BaseAgent, Message, Topics, Priority

logger = logging.getLogger(__name__)


class AutomationCurve(Enum):
    """Automation curve types"""
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    LOGARITHMIC = "logarithmic"
    BEZIER = "bezier"
    STEP = "step"


@dataclass
class AutomationPoint:
    """Single automation point"""
    time: float  # seconds or beats
    value: float
    curve: AutomationCurve = AutomationCurve.LINEAR


@dataclass
class AutomationLane:
    """Automation lane for a parameter"""
    lane_id: str
    parameter_path: str  # "agent.parameter"
    points: List[AutomationPoint] = field(default_factory=list)
    enabled: bool = True


@dataclass
class Scene:
    """Performance scene"""
    scene_id: str
    scene_name: str
    parameter_snapshots: Dict[str, float]  # parameter -> value
    transition_curves: Dict[str, AutomationCurve]  # parameter -> curve
    transition_time: float = 0.0


@dataclass
class Macro:
    """Multi-parameter macro control"""
    macro_id: str
    macro_name: str
    target_parameters: List[Dict[str, Any]]  # [{param, min, max, curve}]
    current_value: float = 0.5
    enabled: bool = True


@dataclass
class PerformanceCue:
    """Timeline-based performance cue"""
    cue_id: str
    cue_name: str
    timecode: str  # "00:02:30.500" or "beat:16.0"
    actions: List[Dict[str, Any]]  # [{action_type, parameters}]
    condition: Optional[Dict[str, Any]] = None
    enabled: bool = True
    fired: bool = False


class PerformanceAutomationAgent(BaseAgent):
    """
    Agent responsible for performance automation and scene management.

    Capabilities:
    - Real-time parameter automation recording
    - Automation playback with curves
    - Scene-based parameter snapshots
    - Macro controls (multi-parameter)
    - Timeline cues
    - Conditional triggers
    """

    def __init__(self):
        super().__init__(
            agent_id="performance_automation_agent",
            agent_name="Performance Automation Agent"
        )

        # Automation lanes
        self.automation_lanes: Dict[str, AutomationLane] = {}
        self.lanes_lock = threading.Lock()

        # Scenes
        self.scenes: Dict[str, Scene] = {}
        self.current_scene_id: Optional[str] = None
        self.scenes_lock = threading.Lock()

        # Macros
        self.macros: Dict[str, Macro] = {}
        self.macros_lock = threading.Lock()

        # Performance cues
        self.cues: List[PerformanceCue] = []
        self.cues_lock = threading.Lock()

        # Recording state
        self.recording_active = False
        self.recording_start_time: float = 0.0
        self.recording_parameters: List[str] = []

        # Playback state
        self.playback_active = False
        self.playback_time: float = 0.0
        self.playback_thread: Optional[threading.Thread] = None
        self.playback_thread_active = False

        # Statistics
        self.stats = {
            'automations_recorded': 0,
            'scenes_triggered': 0,
            'cues_fired': 0,
            'macros_changed': 0
        }
        self.stats_lock = threading.Lock()

    def setup(self):
        """Initialize the automation agent"""
        self.subscribe("automation.record.start")
        self.subscribe("automation.record.stop")
        self.subscribe("automation.playback.enable")
        self.subscribe("automation.scene.trigger")
        self.subscribe("automation.scene.create")
        self.subscribe("automation.macro.create")
        self.subscribe("automation.macro.change")
        self.subscribe("automation.cue.create")
        self.subscribe("automation.cue.fire")
        self.subscribe("automation.parameter.change")
        self.subscribe("sync.clock.position")  # Listen for timeline position

        self._start_playback_thread()
        self.log("INFO", "Performance Automation Agent initialized")

    def teardown(self):
        """Cleanup resources"""
        self._stop_playback_thread()
        self.log("INFO", "Performance Automation Agent shutdown complete")

    def handle_message(self, message: Message):
        """Process incoming messages"""
        try:
            if message.topic == "automation.record.start":
                self._handle_record_start(message)
            elif message.topic == "automation.record.stop":
                self._handle_record_stop(message)
            elif message.topic == "automation.playback.enable":
                self._handle_playback_enable(message)
            elif message.topic == "automation.scene.trigger":
                self._handle_scene_trigger(message)
            elif message.topic == "automation.scene.create":
                self._handle_scene_create(message)
            elif message.topic == "automation.macro.create":
                self._handle_macro_create(message)
            elif message.topic == "automation.macro.change":
                self._handle_macro_change(message)
            elif message.topic == "automation.cue.create":
                self._handle_cue_create(message)
            elif message.topic == "automation.cue.fire":
                self._handle_cue_fire(message)
            elif message.topic == "automation.parameter.change":
                self._handle_parameter_change(message)
            elif message.topic == "sync.clock.position":
                self._handle_clock_position(message)
        except Exception as e:
            self.log("ERROR", f"Error handling message: {e}", {"topic": message.topic})

    def _handle_record_start(self, message: Message):
        """Handle automation recording start"""
        payload = message.payload
        parameter_path = payload['parameter_path']

        self.recording_active = True
        self.recording_start_time = time.time()
        self.recording_parameters.append(parameter_path)

        # Create automation lane if doesn't exist
        with self.lanes_lock:
            if parameter_path not in self.automation_lanes:
                self.automation_lanes[parameter_path] = AutomationLane(
                    lane_id=f"lane_{time.time()}",
                    parameter_path=parameter_path
                )

        with self.stats_lock:
            self.stats['automations_recorded'] += 1

        self.respond(message, {'success': True, 'parameter': parameter_path})

    def _handle_record_stop(self, message: Message):
        """Handle automation recording stop"""
        payload = message.payload
        parameter_path = payload.get('parameter_path')

        if parameter_path and parameter_path in self.recording_parameters:
            self.recording_parameters.remove(parameter_path)

        if len(self.recording_parameters) == 0:
            self.recording_active = False

        self.respond(message, {'success': True})

    def _handle_playback_enable(self, message: Message):
        """Handle automation playback enable/disable"""
        payload = message.payload
        enable = payload.get('enable', True)

        self.playback_active = enable
        if enable:
            self.playback_time = 0.0

        self.respond(message, {'success': True, 'playback_active': self.playback_active})

    def _handle_scene_trigger(self, message: Message):
        """Handle scene trigger"""
        payload = message.payload
        scene_id = payload['scene_id']
        transition_time = payload.get('transition_time', 0.0)

        with self.scenes_lock:
            if scene_id not in self.scenes:
                self.respond(message, {'success': False, 'error': 'Scene not found'})
                return

            scene = self.scenes[scene_id]
            self.current_scene_id = scene_id

            # Apply scene parameters
            for param_path, value in scene.parameter_snapshots.items():
                curve = scene.transition_curves.get(param_path, AutomationCurve.LINEAR)

                # Publish parameter change
                self.publish("effects.parameter.change", {
                    'parameter_path': param_path,
                    'value': value,
                    'ramp_time': transition_time,
                    'curve': curve.value
                }, priority=Priority.HIGH)

        with self.stats_lock:
            self.stats['scenes_triggered'] += 1

        self.respond(message, {
            'success': True,
            'scene_id': scene_id,
            'scene_name': scene.scene_name
        })

        self.publish("automation.scene.triggered", {
            'scene_id': scene_id,
            'scene_name': scene.scene_name
        }, priority=Priority.HIGH)

    def _handle_scene_create(self, message: Message):
        """Handle scene creation"""
        payload = message.payload

        scene = Scene(
            scene_id=payload.get('scene_id', f"scene_{time.time()}"),
            scene_name=payload['scene_name'],
            parameter_snapshots=payload.get('parameter_snapshots', {}),
            transition_curves={k: AutomationCurve(v) for k, v in payload.get('transition_curves', {}).items()},
            transition_time=payload.get('transition_time', 0.0)
        )

        with self.scenes_lock:
            self.scenes[scene.scene_id] = scene

        self.respond(message, {
            'success': True,
            'scene_id': scene.scene_id,
            'scene_name': scene.scene_name
        })

    def _handle_macro_create(self, message: Message):
        """Handle macro creation"""
        payload = message.payload

        macro = Macro(
            macro_id=payload.get('macro_id', f"macro_{time.time()}"),
            macro_name=payload['macro_name'],
            target_parameters=payload['target_parameters'],
            current_value=payload.get('default_value', 0.5)
        )

        with self.macros_lock:
            self.macros[macro.macro_id] = macro

        self.respond(message, {
            'success': True,
            'macro_id': macro.macro_id,
            'macro_name': macro.macro_name
        })

    def _handle_macro_change(self, message: Message):
        """Handle macro value change"""
        payload = message.payload
        macro_id = payload['macro_id']
        value = payload['value']

        with self.macros_lock:
            if macro_id not in self.macros:
                self.respond(message, {'success': False, 'error': 'Macro not found'})
                return

            macro = self.macros[macro_id]
            macro.current_value = value

            # Update all target parameters
            for target in macro.target_parameters:
                param = target['param']
                min_val = target['min']
                max_val = target['max']
                curve = target.get('curve', 'linear')

                # Calculate scaled value
                if curve == 'linear':
                    scaled_value = min_val + (max_val - min_val) * value
                elif curve == 'exponential':
                    scaled_value = min_val + (max_val - min_val) * (value ** 2)
                elif curve == 'logarithmic':
                    scaled_value = min_val + (max_val - min_val) * (value ** 0.5)
                else:
                    scaled_value = min_val + (max_val - min_val) * value

                # Publish parameter change
                self.publish("effects.parameter.change", {
                    'parameter_path': param,
                    'value': scaled_value
                }, priority=Priority.HIGH)

        with self.stats_lock:
            self.stats['macros_changed'] += 1

        self.respond(message, {'success': True, 'macro_id': macro_id, 'value': value})

    def _handle_cue_create(self, message: Message):
        """Handle performance cue creation"""
        payload = message.payload

        cue = PerformanceCue(
            cue_id=payload.get('cue_id', f"cue_{time.time()}"),
            cue_name=payload['cue_name'],
            timecode=payload['timecode'],
            actions=payload['actions'],
            condition=payload.get('condition'),
            enabled=payload.get('enabled', True)
        )

        with self.cues_lock:
            self.cues.append(cue)

        self.respond(message, {
            'success': True,
            'cue_id': cue.cue_id,
            'cue_name': cue.cue_name
        })

    def _handle_cue_fire(self, message: Message):
        """Handle manual cue fire"""
        payload = message.payload
        cue_id = payload['cue_id']

        with self.cues_lock:
            cue = next((c for c in self.cues if c.cue_id == cue_id), None)

            if cue is None:
                self.respond(message, {'success': False, 'error': 'Cue not found'})
                return

            self._execute_cue(cue)

        self.respond(message, {'success': True, 'cue_id': cue_id})

    def _handle_parameter_change(self, message: Message):
        """Handle parameter change (for automation recording)"""
        if not self.recording_active:
            return

        payload = message.payload
        parameter_path = payload.get('parameter_path', '')
        value = payload.get('value', 0.0)

        if parameter_path in self.recording_parameters:
            elapsed_time = time.time() - self.recording_start_time

            with self.lanes_lock:
                if parameter_path in self.automation_lanes:
                    lane = self.automation_lanes[parameter_path]
                    point = AutomationPoint(
                        time=elapsed_time,
                        value=value
                    )
                    lane.points.append(point)

    def _handle_clock_position(self, message: Message):
        """Handle clock position update"""
        payload = message.payload
        self.playback_time = payload.get('time_seconds', 0.0)

        # Check for cue triggers
        self._check_cue_triggers()

    def _start_playback_thread(self):
        """Start automation playback thread"""
        self.playback_thread_active = True
        self.playback_thread = threading.Thread(
            target=self._playback_worker,
            name=f"{self.agent_id}_playback",
            daemon=True
        )
        self.playback_thread.start()

    def _stop_playback_thread(self):
        """Stop automation playback thread"""
        self.playback_thread_active = False
        if self.playback_thread and self.playback_thread.is_alive():
            self.playback_thread.join(timeout=2.0)

    def _playback_worker(self):
        """Automation playback worker"""
        while self.playback_thread_active:
            try:
                if self.playback_active:
                    self._process_automation_playback()
                time.sleep(0.01)  # 10ms intervals
            except Exception as e:
                logger.error(f"Error in playback worker: {e}")

    def _process_automation_playback(self):
        """Process automation playback"""
        with self.lanes_lock:
            for lane in self.automation_lanes.values():
                if not lane.enabled or len(lane.points) == 0:
                    continue

                # Find current automation value
                value = self._get_automation_value(lane, self.playback_time)

                if value is not None:
                    # Publish parameter change
                    self.publish("effects.parameter.change", {
                        'parameter_path': lane.parameter_path,
                        'value': value
                    }, priority=Priority.MEDIUM)

    def _get_automation_value(self, lane: AutomationLane, time: float) -> Optional[float]:
        """Get automation value at specific time"""
        if len(lane.points) == 0:
            return None

        # Find surrounding points
        before = None
        after = None

        for point in sorted(lane.points, key=lambda p: p.time):
            if point.time <= time:
                before = point
            elif point.time > time:
                after = point
                break

        if before is None:
            return lane.points[0].value if len(lane.points) > 0 else None

        if after is None:
            return before.value

        # Interpolate between points
        progress = (time - before.time) / (after.time - before.time)

        if before.curve == AutomationCurve.LINEAR:
            return before.value + (after.value - before.value) * progress
        elif before.curve == AutomationCurve.EXPONENTIAL:
            return before.value + (after.value - before.value) * (progress ** 2)
        elif before.curve == AutomationCurve.LOGARITHMIC:
            return before.value + (after.value - before.value) * (progress ** 0.5)
        elif before.curve == AutomationCurve.STEP:
            return before.value
        else:
            return before.value + (after.value - before.value) * progress

    def _check_cue_triggers(self):
        """Check if any cues should be triggered"""
        with self.cues_lock:
            for cue in self.cues:
                if not cue.enabled or cue.fired:
                    continue

                # Parse timecode
                if cue.timecode.startswith("beat:"):
                    # Beat-based trigger (would need beat position from sync agent)
                    continue
                else:
                    # Time-based trigger
                    cue_time = self._parse_timecode(cue.timecode)
                    if abs(self.playback_time - cue_time) < 0.05:  # 50ms tolerance
                        self._execute_cue(cue)
                        cue.fired = True

    def _parse_timecode(self, timecode: str) -> float:
        """Parse timecode to seconds"""
        # Simple parser for "HH:MM:SS.mmm" format
        try:
            parts = timecode.split(":")
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        except:
            return 0.0

    def _execute_cue(self, cue: PerformanceCue):
        """Execute a performance cue"""
        # Check condition if present
        if cue.condition:
            if not self._evaluate_condition(cue.condition):
                return

        # Execute all actions
        for action in cue.actions:
            action_type = action.get('action_type', '')
            parameters = action.get('parameters', {})

            # Route to appropriate topic
            topic_map = {
                'scene_change': 'automation.scene.trigger',
                'parameter_change': 'effects.parameter.change',
                'loop_trigger': 'loop.record.start',
                'lighting_cue': 'visual.lighting.scene'
            }

            topic = topic_map.get(action_type, 'automation.cue.action')
            self.publish(topic, parameters, priority=Priority.HIGH)

        with self.stats_lock:
            self.stats['cues_fired'] += 1

        self.publish("automation.cue.fired", {
            'cue_id': cue.cue_id,
            'cue_name': cue.cue_name
        }, priority=Priority.MEDIUM)

    def _evaluate_condition(self, condition: Dict[str, Any]) -> bool:
        """Evaluate a conditional trigger"""
        # Simple condition evaluation (would be more sophisticated in production)
        condition_type = condition.get('type', '')

        if condition_type == 'parameter_threshold':
            # Check if a parameter exceeds a threshold
            return True  # Simplified
        elif condition_type == 'time_range':
            # Check if current time is in range
            return True  # Simplified

        return True
