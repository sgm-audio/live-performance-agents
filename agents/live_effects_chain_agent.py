"""
Live Effects Chain Agent

This agent handles real-time audio effects processing with preset management,
scene-based recall, parameter automation, and dynamic effect chains for
live performance scenarios.
"""

import numpy as np
import threading
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
import copy

from core import BaseAgent, Message, Topics, Priority
from .effects_processors import (
    EffectProcessorFactory,
    EffectProcessor,
    EffectType as ProcessorEffectType
)

logger = logging.getLogger(__name__)


class EffectType(Enum):
    """Available effect types"""
    COMPRESSOR = "compressor"
    LIMITER = "limiter"
    GATE = "gate"
    EXPANDER = "expander"
    EQ_PARAMETRIC = "eq_parametric"
    EQ_GRAPHIC = "eq_graphic"
    REVERB = "reverb"
    DELAY = "delay"
    CHORUS = "chorus"
    FLANGER = "flanger"
    PHASER = "phaser"
    TREMOLO = "tremolo"
    VIBRATO = "vibrato"
    DISTORTION = "distortion"
    SATURATION = "saturation"
    PITCH_CORRECTION = "pitch_correction"


@dataclass
class Effect:
    """Single effect in a chain"""
    effect_id: str
    effect_type: EffectType
    parameters: Dict[str, float]
    bypassed: bool = False
    wet_dry_mix: float = 1.0  # 0.0 = dry, 1.0 = wet
    position: int = 0


@dataclass
class EffectChain:
    """Chain of effects"""
    chain_id: str
    chain_name: str
    effects: List[Effect] = field(default_factory=list)
    routing: str = "series"  # series or parallel
    enabled: bool = True
    input_gain: float = 1.0
    output_gain: float = 1.0


@dataclass
class Preset:
    """Effect chain preset"""
    preset_id: str
    preset_name: str
    chain_states: Dict[str, EffectChain]
    description: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class Scene:
    """Performance scene with effect states"""
    scene_id: str
    scene_name: str
    effect_states: Dict[str, Dict[str, Any]]  # effect_id -> parameters
    transitions: Dict[str, float]  # parameter -> ramp_time
    description: str = ""


@dataclass
class ParameterAutomation:
    """Parameter automation data"""
    automation_id: str
    effect_id: str
    parameter: str
    target_value: float
    ramp_time: float  # seconds
    curve: str = "linear"  # linear, exponential, logarithmic
    start_time: float = 0.0


class LiveEffectsChainAgent(BaseAgent):
    """
    Agent responsible for real-time effects processing and management.

    Capabilities:
    - Zero-latency effect chains
    - Dynamic effect bypass/enable
    - Parallel and series effect routing
    - Preset management and morphing
    - Scene-based recall
    - Parameter automation
    - A/B comparison
    """

    def __init__(self, sample_rate: int = 44100):
        super().__init__(
            agent_id="live_effects_chain_agent",
            agent_name="Live Effects Chain Agent"
        )

        # Audio configuration
        self.sample_rate = sample_rate

        # Effect chains
        self.effect_chains: Dict[str, EffectChain] = {}
        self.chains_lock = threading.Lock()

        # Presets
        self.presets: Dict[str, Preset] = {}
        self.presets_lock = threading.Lock()

        # Scenes
        self.scenes: Dict[str, Scene] = {}
        self.scenes_lock = threading.Lock()

        # Current states
        self.current_scene_id: Optional[str] = None
        self.ab_state: Dict[str, Any] = {'a': None, 'b': None, 'current': 'a'}

        # Active automations
        self.active_automations: List[ParameterAutomation] = []
        self.automation_lock = threading.Lock()

        # Automation processing thread
        self.automation_thread: Optional[threading.Thread] = None
        self.automation_active = False

        # Effect processors (cached per effect)
        self.processors: Dict[str, EffectProcessor] = {}
        self.processors_lock = threading.Lock()

        # Statistics
        self.stats = {
            'effects_processed': 0,
            'preset_recalls': 0,
            'scene_changes': 0,
            'automations_completed': 0,
            'total_processing_time_ms': 0.0,
            'peak_latency_ms': 0.0
        }
        self.stats_lock = threading.Lock()

    def setup(self):
        """Initialize the effects chain agent"""
        # Subscribe to relevant topics
        self.subscribe("effects.chain.create")
        self.subscribe("effects.chain.update")
        self.subscribe("effects.chain.delete")
        self.subscribe("effects.preset.recall")
        self.subscribe("effects.preset.save")
        self.subscribe("effects.parameter.change")
        self.subscribe("effects.bypass.toggle")
        self.subscribe("effects.scene.change")
        self.subscribe("effects.scene.create")
        self.subscribe("effects.morph.start")
        self.subscribe("effects.ab.compare")
        self.subscribe("audio.live.process")

        # Start automation thread
        self._start_automation_thread()

        # Load default effects
        self._create_default_effects()

        self.log("INFO", "Live Effects Chain Agent initialized")

    def teardown(self):
        """Cleanup resources"""
        # Stop automation thread
        self._stop_automation_thread()

        # Cleanup all processors
        with self.processors_lock:
            self.processors.clear()

        self.log("INFO", "Live Effects Chain Agent shutdown complete")

    def handle_message(self, message: Message):
        """Process incoming messages"""
        try:
            if message.topic == "effects.chain.create":
                self._handle_chain_create(message)
            elif message.topic == "effects.chain.update":
                self._handle_chain_update(message)
            elif message.topic == "effects.chain.delete":
                self._handle_chain_delete(message)
            elif message.topic == "effects.preset.recall":
                self._handle_preset_recall(message)
            elif message.topic == "effects.preset.save":
                self._handle_preset_save(message)
            elif message.topic == "effects.parameter.change":
                self._handle_parameter_change(message)
            elif message.topic == "effects.bypass.toggle":
                self._handle_bypass_toggle(message)
            elif message.topic == "effects.scene.change":
                self._handle_scene_change(message)
            elif message.topic == "effects.scene.create":
                self._handle_scene_create(message)
            elif message.topic == "effects.morph.start":
                self._handle_morph_start(message)
            elif message.topic == "effects.ab.compare":
                self._handle_ab_compare(message)
            elif message.topic == "audio.live.process":
                self._handle_audio_process(message)
            else:
                self.log("WARNING", f"Unknown message topic: {message.topic}")

        except Exception as e:
            self.log("ERROR", f"Error handling message: {e}", {"topic": message.topic})

    def _handle_chain_create(self, message: Message):
        """Handle effect chain creation"""
        payload = message.payload

        chain = EffectChain(
            chain_id=payload.get('chain_id', f"chain_{time.time()}"),
            chain_name=payload['chain_name'],
            effects=[],
            routing=payload.get('routing', 'series'),
            enabled=payload.get('enabled', True),
            input_gain=payload.get('input_gain', 1.0),
            output_gain=payload.get('output_gain', 1.0)
        )

        # Add effects to chain
        for effect_data in payload.get('effects', []):
            effect = Effect(
                effect_id=effect_data.get('effect_id', f"effect_{time.time()}_{len(chain.effects)}"),
                effect_type=EffectType(effect_data['type']),
                parameters=effect_data.get('parameters', {}),
                bypassed=effect_data.get('bypassed', False),
                wet_dry_mix=effect_data.get('wet_dry_mix', 1.0),
                position=effect_data.get('position', len(chain.effects))
            )
            chain.effects.append(effect)

        # Sort effects by position
        chain.effects.sort(key=lambda e: e.position)

        with self.chains_lock:
            self.effect_chains[chain.chain_id] = chain

        self.respond(message, {
            'success': True,
            'chain_id': chain.chain_id,
            'num_effects': len(chain.effects)
        })

        self.publish("effects.chain.created", {
            'chain_id': chain.chain_id,
            'chain_name': chain.chain_name
        }, priority=Priority.MEDIUM)

    def _handle_chain_update(self, message: Message):
        """Handle effect chain update"""
        payload = message.payload
        chain_id = payload['chain_id']

        with self.chains_lock:
            if chain_id not in self.effect_chains:
                self.respond(message, {'success': False, 'error': 'Chain not found'})
                return

            chain = self.effect_chains[chain_id]

            # Update chain properties
            if 'enabled' in payload:
                chain.enabled = payload['enabled']
            if 'input_gain' in payload:
                chain.input_gain = payload['input_gain']
            if 'output_gain' in payload:
                chain.output_gain = payload['output_gain']

        self.respond(message, {'success': True, 'chain_id': chain_id})

    def _handle_chain_delete(self, message: Message):
        """Handle effect chain deletion"""
        payload = message.payload
        chain_id = payload['chain_id']

        with self.chains_lock:
            if chain_id in self.effect_chains:
                del self.effect_chains[chain_id]
                success = True
            else:
                success = False

        # Cleanup processors for deleted effects
        if success:
            self._cleanup_processors()

        self.respond(message, {'success': success, 'chain_id': chain_id})

    def _handle_preset_recall(self, message: Message):
        """Handle preset recall"""
        payload = message.payload
        preset_name = payload['preset_name']
        transition_time = payload.get('transition_time', 0.0)

        with self.presets_lock:
            preset = None
            for p in self.presets.values():
                if p.preset_name == preset_name:
                    preset = p
                    break

            if preset is None:
                self.respond(message, {'success': False, 'error': 'Preset not found'})
                return

            # Apply preset
            if transition_time == 0:
                # Instant recall
                with self.chains_lock:
                    for chain_id, chain_state in preset.chain_states.items():
                        if chain_id in self.effect_chains:
                            self.effect_chains[chain_id] = copy.deepcopy(chain_state)
            else:
                # Animated transition
                self._animate_preset_transition(preset, transition_time)

        with self.stats_lock:
            self.stats['preset_recalls'] += 1

        self.respond(message, {
            'success': True,
            'preset_name': preset_name,
            'transition_time': transition_time
        })

        self.publish("effects.preset.recalled", {
            'preset_name': preset_name
        }, priority=Priority.MEDIUM)

    def _handle_preset_save(self, message: Message):
        """Handle preset save"""
        payload = message.payload
        preset_name = payload['preset_name']

        # Capture current chain states
        with self.chains_lock:
            chain_states = copy.deepcopy(self.effect_chains)

        preset = Preset(
            preset_id=f"preset_{time.time()}",
            preset_name=preset_name,
            chain_states=chain_states,
            description=payload.get('description', ''),
            tags=payload.get('tags', [])
        )

        with self.presets_lock:
            self.presets[preset.preset_id] = preset

        self.respond(message, {
            'success': True,
            'preset_id': preset.preset_id,
            'preset_name': preset_name
        })

    def _handle_parameter_change(self, message: Message):
        """Handle effect parameter change"""
        payload = message.payload
        effect_id = payload['effect_id']
        parameter = payload['parameter']
        value = payload['value']
        ramp_time = payload.get('ramp_time', 0.0)

        # Find the effect
        effect = self._find_effect(effect_id)

        if effect is None:
            self.respond(message, {'success': False, 'error': 'Effect not found'})
            return

        if ramp_time == 0:
            # Instant change
            effect.parameters[parameter] = value
            success = True
        else:
            # Animated change
            automation = ParameterAutomation(
                automation_id=f"auto_{time.time()}",
                effect_id=effect_id,
                parameter=parameter,
                target_value=value,
                ramp_time=ramp_time,
                curve=payload.get('curve', 'linear'),
                start_time=time.time()
            )

            with self.automation_lock:
                self.active_automations.append(automation)

            success = True

        self.respond(message, {
            'success': success,
            'effect_id': effect_id,
            'parameter': parameter,
            'value': value
        })

    def _handle_bypass_toggle(self, message: Message):
        """Handle effect bypass toggle"""
        payload = message.payload
        effect_id = payload['effect_id']
        bypassed = payload.get('bypassed')  # None = toggle

        effect = self._find_effect(effect_id)

        if effect is None:
            self.respond(message, {'success': False, 'error': 'Effect not found'})
            return

        if bypassed is None:
            effect.bypassed = not effect.bypassed
        else:
            effect.bypassed = bypassed

        self.respond(message, {
            'success': True,
            'effect_id': effect_id,
            'bypassed': effect.bypassed
        })

    def _handle_scene_change(self, message: Message):
        """Handle scene change"""
        payload = message.payload
        scene_id = payload['scene_id']
        transition_time = payload.get('transition_time', 0.0)

        with self.scenes_lock:
            if scene_id not in self.scenes:
                self.respond(message, {'success': False, 'error': 'Scene not found'})
                return

            scene = self.scenes[scene_id]

            # Apply scene
            self._apply_scene(scene, transition_time)
            self.current_scene_id = scene_id

        with self.stats_lock:
            self.stats['scene_changes'] += 1

        self.respond(message, {
            'success': True,
            'scene_id': scene_id,
            'scene_name': scene.scene_name
        })

        self.publish("effects.scene.changed", {
            'scene_id': scene_id,
            'scene_name': scene.scene_name
        }, priority=Priority.HIGH)

    def _handle_scene_create(self, message: Message):
        """Handle scene creation"""
        payload = message.payload

        # Capture current effect states
        effect_states = {}
        with self.chains_lock:
            for chain in self.effect_chains.values():
                for effect in chain.effects:
                    effect_states[effect.effect_id] = {
                        'parameters': copy.deepcopy(effect.parameters),
                        'bypassed': effect.bypassed,
                        'wet_dry_mix': effect.wet_dry_mix
                    }

        scene = Scene(
            scene_id=payload.get('scene_id', f"scene_{time.time()}"),
            scene_name=payload['scene_name'],
            effect_states=payload.get('effect_states', effect_states),
            transitions=payload.get('transitions', {}),
            description=payload.get('description', '')
        )

        with self.scenes_lock:
            self.scenes[scene.scene_id] = scene

        self.respond(message, {
            'success': True,
            'scene_id': scene.scene_id,
            'scene_name': scene.scene_name
        })

    def _handle_morph_start(self, message: Message):
        """Handle preset morphing"""
        payload = message.payload
        preset_a = payload['preset_a']
        preset_b = payload['preset_b']
        morph_position = payload.get('morph_position', 0.5)  # 0.0 = A, 1.0 = B

        # Get presets
        with self.presets_lock:
            pa = next((p for p in self.presets.values() if p.preset_name == preset_a), None)
            pb = next((p for p in self.presets.values() if p.preset_name == preset_b), None)

            if pa is None or pb is None:
                self.respond(message, {'success': False, 'error': 'Preset not found'})
                return

            # Morph between presets
            self._morph_presets(pa, pb, morph_position)

        self.respond(message, {
            'success': True,
            'preset_a': preset_a,
            'preset_b': preset_b,
            'morph_position': morph_position
        })

    def _handle_ab_compare(self, message: Message):
        """Handle A/B comparison"""
        payload = message.payload
        action = payload.get('action', 'toggle')  # toggle, set_a, set_b, recall_a, recall_b

        if action == 'set_a':
            with self.chains_lock:
                self.ab_state['a'] = copy.deepcopy(self.effect_chains)
        elif action == 'set_b':
            with self.chains_lock:
                self.ab_state['b'] = copy.deepcopy(self.effect_chains)
        elif action == 'toggle':
            current = self.ab_state['current']
            new_state = 'b' if current == 'a' else 'a'
            if self.ab_state[new_state] is not None:
                with self.chains_lock:
                    self.effect_chains = copy.deepcopy(self.ab_state[new_state])
                self.ab_state['current'] = new_state
        elif action == 'recall_a':
            if self.ab_state['a'] is not None:
                with self.chains_lock:
                    self.effect_chains = copy.deepcopy(self.ab_state['a'])
                self.ab_state['current'] = 'a'
        elif action == 'recall_b':
            if self.ab_state['b'] is not None:
                with self.chains_lock:
                    self.effect_chains = copy.deepcopy(self.ab_state['b'])
                self.ab_state['current'] = 'b'

        self.respond(message, {
            'success': True,
            'current_state': self.ab_state['current'],
            'action': action
        })

    def _handle_audio_process(self, message: Message):
        """Handle audio processing request"""
        payload = message.payload
        audio_data = np.array(payload.get('audio_data', []))

        if len(audio_data) == 0:
            self.respond(message, {'success': False, 'error': 'No audio data'})
            return

        # Process through effect chains
        processed_audio = self._process_audio(audio_data)

        with self.stats_lock:
            self.stats['effects_processed'] += 1

        self.respond(message, {
            'success': True,
            'processed_audio': processed_audio.tolist(),
            'num_chains': len(self.effect_chains)
        })

    def _process_audio(self, audio: np.ndarray) -> np.ndarray:
        """Process audio through effect chains with real DSP"""
        start_time = time.perf_counter()
        processed = audio.copy()

        with self.chains_lock:
            for chain in self.effect_chains.values():
                if not chain.enabled:
                    continue

                # Apply input gain
                chain_audio = processed * chain.input_gain

                # Process through effects
                for effect in chain.effects:
                    if not effect.bypassed:
                        effect_start = time.perf_counter()
                        chain_audio = self._apply_effect(chain_audio, effect)
                        effect_time = (time.perf_counter() - effect_start) * 1000  # ms

                        # Track latency
                        with self.stats_lock:
                            if effect_time > self.stats['peak_latency_ms']:
                                self.stats['peak_latency_ms'] = effect_time

                # Apply output gain
                processed = chain_audio * chain.output_gain

        # Track total processing time
        total_time = (time.perf_counter() - start_time) * 1000  # ms
        with self.stats_lock:
            self.stats['total_processing_time_ms'] += total_time

        return processed

    def _apply_effect(self, audio: np.ndarray, effect: Effect) -> np.ndarray:
        """Apply a single effect using real DSP processors"""
        # Get or create processor for this effect
        processor = self._get_processor(effect.effect_id, effect.effect_type)

        if processor is None:
            # If processor creation failed, return unprocessed audio
            logger.warning(f"No processor available for effect {effect.effect_id}")
            return audio

        try:
            # Process audio
            wet = processor.process(audio, effect.parameters)

            # Apply wet/dry mix
            dry = audio
            mixed = wet * effect.wet_dry_mix + dry * (1.0 - effect.wet_dry_mix)

            return mixed

        except Exception as e:
            logger.error(f"Error processing effect {effect.effect_id}: {e}")
            return audio  # Return dry signal on error

    def _get_processor(self, effect_id: str, effect_type: EffectType) -> Optional[EffectProcessor]:
        """Get or create an effect processor instance"""
        with self.processors_lock:
            if effect_id in self.processors:
                return self.processors[effect_id]

            # Create new processor
            try:
                # Convert EffectType to ProcessorEffectType
                processor_type = ProcessorEffectType(effect_type.value)
                processor = EffectProcessorFactory.create(processor_type, self.sample_rate)
                self.processors[effect_id] = processor
                return processor

            except ValueError as e:
                logger.error(f"Failed to create processor for {effect_type}: {e}")
                return None

    def _reset_processor(self, effect_id: str):
        """Reset an effect processor's internal state"""
        with self.processors_lock:
            if effect_id in self.processors:
                self.processors[effect_id].reset()

    def _cleanup_processors(self):
        """Remove processors for deleted effects"""
        with self.processors_lock:
            # Get all active effect IDs
            active_effect_ids = set()
            with self.chains_lock:
                for chain in self.effect_chains.values():
                    for effect in chain.effects:
                        active_effect_ids.add(effect.effect_id)

            # Remove processors for deleted effects
            processor_ids = list(self.processors.keys())
            for proc_id in processor_ids:
                if proc_id not in active_effect_ids:
                    del self.processors[proc_id]

    def _find_effect(self, effect_id: str) -> Optional[Effect]:
        """Find an effect by ID"""
        with self.chains_lock:
            for chain in self.effect_chains.values():
                for effect in chain.effects:
                    if effect.effect_id == effect_id:
                        return effect
        return None

    def _apply_scene(self, scene: Scene, transition_time: float):
        """Apply a scene"""
        if transition_time == 0:
            # Instant change
            for effect_id, state in scene.effect_states.items():
                effect = self._find_effect(effect_id)
                if effect:
                    effect.parameters.update(state.get('parameters', {}))
                    effect.bypassed = state.get('bypassed', effect.bypassed)
                    effect.wet_dry_mix = state.get('wet_dry_mix', effect.wet_dry_mix)
        else:
            # Animated transition
            for effect_id, state in scene.effect_states.items():
                effect = self._find_effect(effect_id)
                if effect:
                    # Create automations for each parameter
                    for param, value in state.get('parameters', {}).items():
                        ramp_time = scene.transitions.get(param, transition_time)
                        automation = ParameterAutomation(
                            automation_id=f"scene_auto_{time.time()}_{param}",
                            effect_id=effect_id,
                            parameter=param,
                            target_value=value,
                            ramp_time=ramp_time,
                            start_time=time.time()
                        )
                        with self.automation_lock:
                            self.active_automations.append(automation)

    def _animate_preset_transition(self, preset: Preset, transition_time: float):
        """Animate transition to a preset"""
        # Similar to scene application but for full preset
        for chain_id, chain_state in preset.chain_states.items():
            if chain_id in self.effect_chains:
                for effect in chain_state.effects:
                    current_effect = self._find_effect(effect.effect_id)
                    if current_effect:
                        for param, value in effect.parameters.items():
                            automation = ParameterAutomation(
                                automation_id=f"preset_auto_{time.time()}_{param}",
                                effect_id=effect.effect_id,
                                parameter=param,
                                target_value=value,
                                ramp_time=transition_time,
                                start_time=time.time()
                            )
                            with self.automation_lock:
                                self.active_automations.append(automation)

    def _morph_presets(self, preset_a: Preset, preset_b: Preset, position: float):
        """Morph between two presets"""
        # Interpolate between preset A and B based on position
        for chain_id in preset_a.chain_states.keys():
            if chain_id in preset_b.chain_states and chain_id in self.effect_chains:
                chain_a = preset_a.chain_states[chain_id]
                chain_b = preset_b.chain_states[chain_id]

                for i, effect_a in enumerate(chain_a.effects):
                    if i < len(chain_b.effects):
                        effect_b = chain_b.effects[i]
                        current_effect = self._find_effect(effect_a.effect_id)

                        if current_effect:
                            # Morph parameters
                            for param in effect_a.parameters.keys():
                                if param in effect_b.parameters:
                                    val_a = effect_a.parameters[param]
                                    val_b = effect_b.parameters[param]
                                    morphed_val = val_a * (1.0 - position) + val_b * position
                                    current_effect.parameters[param] = morphed_val

    def _start_automation_thread(self):
        """Start automation processing thread"""
        self.automation_active = True
        self.automation_thread = threading.Thread(
            target=self._automation_worker,
            name=f"{self.agent_id}_automation",
            daemon=True
        )
        self.automation_thread.start()

    def _stop_automation_thread(self):
        """Stop automation processing thread"""
        self.automation_active = False
        if self.automation_thread and self.automation_thread.is_alive():
            self.automation_thread.join(timeout=2.0)

    def _automation_worker(self):
        """Process active automations"""
        while self.automation_active:
            try:
                current_time = time.time()
                completed = []

                with self.automation_lock:
                    for automation in self.active_automations:
                        elapsed = current_time - automation.start_time

                        if elapsed >= automation.ramp_time:
                            # Automation complete
                            effect = self._find_effect(automation.effect_id)
                            if effect:
                                effect.parameters[automation.parameter] = automation.target_value
                            completed.append(automation)
                        else:
                            # Update parameter
                            progress = elapsed / automation.ramp_time
                            effect = self._find_effect(automation.effect_id)
                            if effect:
                                current_val = effect.parameters.get(automation.parameter, 0.0)

                                # Apply curve
                                if automation.curve == "exponential":
                                    progress = progress ** 2
                                elif automation.curve == "logarithmic":
                                    progress = np.sqrt(progress)

                                new_val = current_val + (automation.target_value - current_val) * progress
                                effect.parameters[automation.parameter] = new_val

                    # Remove completed automations
                    for auto in completed:
                        self.active_automations.remove(auto)
                        with self.stats_lock:
                            self.stats['automations_completed'] += 1

                time.sleep(0.01)  # 10ms update rate

            except Exception as e:
                logger.error(f"Error in automation worker: {e}")

    def _create_default_effects(self):
        """Create some default effect chains"""
        # Create a basic vocal chain
        vocal_chain_msg = Message(
            topic="effects.chain.create",
            sender="system",
            payload={
                'chain_name': 'Vocal Chain',
                'effects': [
                    {
                        'type': 'gate',
                        'parameters': {'threshold': -40.0, 'ratio': 10.0}
                    },
                    {
                        'type': 'compressor',
                        'parameters': {'threshold': -20.0, 'ratio': 4.0, 'attack': 5.0, 'release': 50.0}
                    },
                    {
                        'type': 'eq_parametric',
                        'parameters': {'freq1': 100.0, 'gain1': -3.0, 'freq2': 3000.0, 'gain2': 2.0}
                    },
                    {
                        'type': 'reverb',
                        'parameters': {'room_size': 0.5, 'damping': 0.7, 'wet_dry': 0.3}
                    }
                ]
            }
        )
        self._handle_chain_create(vocal_chain_msg)
