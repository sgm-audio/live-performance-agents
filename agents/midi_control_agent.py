"""
MIDI Control & Integration Agent

This agent handles MIDI controller integration, parameter mapping, MIDI learn
functionality, and MIDI message processing for live performance control.
"""

import threading
import time
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

try:
    import mido
    MIDO_AVAILABLE = True
except ImportError:
    MIDO_AVAILABLE = False
    logging.warning("mido not available - MIDI I/O will be simulated")

from core import BaseAgent, Message, Topics, Priority

logger = logging.getLogger(__name__)


class MIDIMessageType(Enum):
    """MIDI message types"""
    NOTE_ON = "note_on"
    NOTE_OFF = "note_off"
    CONTROL_CHANGE = "control_change"
    PROGRAM_CHANGE = "program_change"
    PITCH_BEND = "pitch_bend"
    AFTERTOUCH = "aftertouch"
    CLOCK = "clock"
    START = "start"
    STOP = "stop"
    CONTINUE = "continue"


@dataclass
class MIDIDevice:
    """MIDI device information"""
    device_id: str
    device_name: str
    port_number: int
    is_input: bool
    is_output: bool
    connected: bool = True


@dataclass
class MIDIMapping:
    """MIDI controller to parameter mapping"""
    mapping_id: str
    midi_cc: int
    midi_channel: int = 1
    target_agent: str = ""
    target_parameter: str = ""
    min_value: float = 0.0
    max_value: float = 1.0
    curve: str = "linear"  # linear, exponential, logarithmic
    enabled: bool = True


@dataclass
class MIDITrigger:
    """MIDI note-based trigger"""
    trigger_id: str
    note_number: int
    midi_channel: int = 1
    action: str = ""  # scene_change, effect_toggle, loop_record
    parameters: Dict[str, Any] = field(default_factory=dict)
    trigger_on_velocity: bool = True
    enabled: bool = True


@dataclass
class MIDIMessage:
    """MIDI message data"""
    message_type: MIDIMessageType
    channel: int
    data1: int  # Note number or CC number
    data2: int  # Velocity or CC value
    timestamp: float


class MIDIControlAgent(BaseAgent):
    """
    Agent responsible for MIDI control and integration.

    Capabilities:
    - Multiple MIDI device support
    - MIDI learn functionality
    - CC to parameter mapping
    - Note-based triggering
    - Program change handling
    - MIDI feedback to controllers
    - MIDI processing (quantization, filtering)
    """

    def __init__(self):
        super().__init__(
            agent_id="midi_control_agent",
            agent_name="MIDI Control & Integration Agent"
        )

        # MIDI devices
        self.devices: Dict[str, MIDIDevice] = {}
        self.devices_lock = threading.Lock()

        # MIDI mappings
        self.mappings: Dict[str, MIDIMapping] = {}
        self.mappings_lock = threading.Lock()

        # MIDI triggers
        self.triggers: Dict[str, MIDITrigger] = {}
        self.triggers_lock = threading.Lock()

        # MIDI learn mode
        self.learn_mode = False
        self.learn_target: Optional[Dict[str, str]] = None
        self.learn_lock = threading.Lock()

        # MIDI message queue
        self.message_queue: List[MIDIMessage] = []
        self.queue_lock = threading.Lock()

        # Real MIDI ports
        self.midi_inputs: Dict[str, any] = {}  # device_id -> mido.ports.BaseInput
        self.midi_outputs: Dict[str, any] = {}  # device_id -> mido.ports.BaseOutput
        self.midi_ports_lock = threading.Lock()

        # MIDI processing thread
        self.processing_thread: Optional[threading.Thread] = None
        self.processing_active = False

        # Statistics
        self.stats = {
            'messages_received': 0,
            'messages_sent': 0,
            'mappings_triggered': 0,
            'triggers_fired': 0
        }
        self.stats_lock = threading.Lock()

    def setup(self):
        """Initialize the MIDI control agent"""
        # Subscribe to relevant topics
        self.subscribe("midi.device.scan")
        self.subscribe("midi.device.connect")
        self.subscribe("midi.device.disconnect")
        self.subscribe("midi.mapping.create")
        self.subscribe("midi.mapping.delete")
        self.subscribe("midi.mapping.learn.start")
        self.subscribe("midi.mapping.learn.stop")
        self.subscribe("midi.trigger.create")
        self.subscribe("midi.trigger.delete")
        self.subscribe("midi.message.send")
        self.subscribe("midi.feedback.enable")

        # Start MIDI processing thread
        self._start_processing_thread()

        # Scan for MIDI devices
        self._scan_midi_devices()

        self.log("INFO", "MIDI Control Agent initialized")

    def teardown(self):
        """Cleanup resources"""
        # Stop processing thread
        self._stop_processing_thread()

        # Disconnect all devices
        self._disconnect_all_devices()

        self.log("INFO", "MIDI Control Agent shutdown complete")

    def handle_message(self, message: Message):
        """Process incoming messages"""
        try:
            if message.topic == "midi.device.scan":
                self._handle_device_scan(message)
            elif message.topic == "midi.device.connect":
                self._handle_device_connect(message)
            elif message.topic == "midi.device.disconnect":
                self._handle_device_disconnect(message)
            elif message.topic == "midi.mapping.create":
                self._handle_mapping_create(message)
            elif message.topic == "midi.mapping.delete":
                self._handle_mapping_delete(message)
            elif message.topic == "midi.mapping.learn.start":
                self._handle_learn_start(message)
            elif message.topic == "midi.mapping.learn.stop":
                self._handle_learn_stop(message)
            elif message.topic == "midi.trigger.create":
                self._handle_trigger_create(message)
            elif message.topic == "midi.trigger.delete":
                self._handle_trigger_delete(message)
            elif message.topic == "midi.message.send":
                self._handle_message_send(message)
            elif message.topic == "midi.feedback.enable":
                self._handle_feedback_enable(message)
            else:
                self.log("WARNING", f"Unknown message topic: {message.topic}")

        except Exception as e:
            self.log("ERROR", f"Error handling message: {e}", {"topic": message.topic})

    def _handle_device_scan(self, message: Message):
        """Handle MIDI device scan"""
        devices = self._scan_midi_devices()

        self.respond(message, {
            'success': True,
            'devices': [
                {
                    'device_id': d.device_id,
                    'device_name': d.device_name,
                    'is_input': d.is_input,
                    'is_output': d.is_output,
                    'connected': d.connected
                }
                for d in devices
            ]
        })

    def _handle_device_connect(self, message: Message):
        """Handle MIDI device connection with real mido ports"""
        payload = message.payload
        device_id = payload['device_id']
        success = False

        with self.devices_lock:
            if device_id not in self.devices:
                self.respond(message, {'success': False, 'error': 'Device not found'})
                return

            device = self.devices[device_id]

            if not MIDO_AVAILABLE:
                # Simulated mode
                device.connected = True
                success = True
            else:
                try:
                    # Open real MIDI port
                    if device.is_input:
                        port = mido.open_input(device.device_name, callback=self._midi_input_callback)
                        with self.midi_ports_lock:
                            self.midi_inputs[device_id] = port
                        self.log("INFO", f"Opened MIDI input: {device.device_name}")

                    if device.is_output:
                        port = mido.open_output(device.device_name)
                        with self.midi_ports_lock:
                            self.midi_outputs[device_id] = port
                        self.log("INFO", f"Opened MIDI output: {device.device_name}")

                    device.connected = True
                    success = True

                except Exception as e:
                    self.log("ERROR", f"Failed to connect MIDI device {device.device_name}: {e}")
                    success = False

        self.respond(message, {'success': success, 'device_id': device_id})

        if success:
            self.publish("midi.device.connected", {
                'device_id': device_id
            }, priority=Priority.MEDIUM)

    def _handle_device_disconnect(self, message: Message):
        """Handle MIDI device disconnection"""
        payload = message.payload
        device_id = payload['device_id']
        success = False

        with self.devices_lock:
            if device_id not in self.devices:
                self.respond(message, {'success': False, 'error': 'Device not found'})
                return

            device = self.devices[device_id]

            if MIDO_AVAILABLE:
                try:
                    # Close real MIDI ports
                    with self.midi_ports_lock:
                        if device_id in self.midi_inputs:
                            self.midi_inputs[device_id].close()
                            del self.midi_inputs[device_id]
                            self.log("INFO", f"Closed MIDI input: {device.device_name}")

                        if device_id in self.midi_outputs:
                            self.midi_outputs[device_id].close()
                            del self.midi_outputs[device_id]
                            self.log("INFO", f"Closed MIDI output: {device.device_name}")

                except Exception as e:
                    self.log("ERROR", f"Error closing MIDI device: {e}")

            device.connected = False
            success = True

        self.respond(message, {'success': success, 'device_id': device_id})

    def _handle_mapping_create(self, message: Message):
        """Handle MIDI mapping creation"""
        payload = message.payload

        mapping = MIDIMapping(
            mapping_id=payload.get('mapping_id', f"map_{time.time()}"),
            midi_cc=payload['midi_cc'],
            midi_channel=payload.get('midi_channel', 1),
            target_agent=payload['target_agent'],
            target_parameter=payload['target_parameter'],
            min_value=payload.get('min_value', 0.0),
            max_value=payload.get('max_value', 1.0),
            curve=payload.get('curve', 'linear'),
            enabled=payload.get('enabled', True)
        )

        with self.mappings_lock:
            self.mappings[mapping.mapping_id] = mapping

        self.respond(message, {
            'success': True,
            'mapping_id': mapping.mapping_id
        })

        self.publish("midi.mapping.created", {
            'mapping_id': mapping.mapping_id,
            'midi_cc': mapping.midi_cc
        }, priority=Priority.MEDIUM)

    def _handle_mapping_delete(self, message: Message):
        """Handle MIDI mapping deletion"""
        payload = message.payload
        mapping_id = payload['mapping_id']

        with self.mappings_lock:
            if mapping_id in self.mappings:
                del self.mappings[mapping_id]
                success = True
            else:
                success = False

        self.respond(message, {'success': success, 'mapping_id': mapping_id})

    def _handle_learn_start(self, message: Message):
        """Handle MIDI learn start"""
        payload = message.payload

        with self.learn_lock:
            self.learn_mode = True
            self.learn_target = {
                'agent': payload['target_agent'],
                'parameter': payload['target_parameter']
            }

        self.respond(message, {
            'success': True,
            'learn_mode': True
        })

        self.log("INFO", f"MIDI learn started for {payload['target_agent']}.{payload['target_parameter']}")

    def _handle_learn_stop(self, message: Message):
        """Handle MIDI learn stop"""
        with self.learn_lock:
            self.learn_mode = False
            self.learn_target = None

        self.respond(message, {
            'success': True,
            'learn_mode': False
        })

    def _handle_trigger_create(self, message: Message):
        """Handle MIDI trigger creation"""
        payload = message.payload

        trigger = MIDITrigger(
            trigger_id=payload.get('trigger_id', f"trig_{time.time()}"),
            note_number=payload['note_number'],
            midi_channel=payload.get('midi_channel', 1),
            action=payload['action'],
            parameters=payload.get('parameters', {}),
            trigger_on_velocity=payload.get('trigger_on_velocity', True),
            enabled=payload.get('enabled', True)
        )

        with self.triggers_lock:
            self.triggers[trigger.trigger_id] = trigger

        self.respond(message, {
            'success': True,
            'trigger_id': trigger.trigger_id
        })

    def _handle_trigger_delete(self, message: Message):
        """Handle MIDI trigger deletion"""
        payload = message.payload
        trigger_id = payload['trigger_id']

        with self.triggers_lock:
            if trigger_id in self.triggers:
                del self.triggers[trigger_id]
                success = True
            else:
                success = False

        self.respond(message, {'success': success, 'trigger_id': trigger_id})

    def _handle_message_send(self, message: Message):
        """Handle MIDI message send"""
        payload = message.payload

        # Simulate sending MIDI message
        midi_msg = MIDIMessage(
            message_type=MIDIMessageType(payload['message_type']),
            channel=payload.get('channel', 1),
            data1=payload['data1'],
            data2=payload['data2'],
            timestamp=time.time()
        )

        # Send to device (simulated)
        success = True

        with self.stats_lock:
            self.stats['messages_sent'] += 1

        self.respond(message, {'success': success})

    def _handle_feedback_enable(self, message: Message):
        """Handle MIDI feedback enable"""
        payload = message.payload
        controller_id = payload['controller_id']
        parameter_values = payload.get('parameter_values', {})

        # Send MIDI feedback to controller
        for cc, value in parameter_values.items():
            self._send_midi_feedback(controller_id, int(cc), int(value))

        self.respond(message, {
            'success': True,
            'controller_id': controller_id,
            'values_sent': len(parameter_values)
        })

    def _start_processing_thread(self):
        """Start MIDI processing thread"""
        self.processing_active = True
        self.processing_thread = threading.Thread(
            target=self._processing_worker,
            name=f"{self.agent_id}_processor",
            daemon=True
        )
        self.processing_thread.start()

    def _stop_processing_thread(self):
        """Stop MIDI processing thread"""
        self.processing_active = False
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2.0)

    def _processing_worker(self):
        """MIDI processing worker thread"""
        while self.processing_active:
            try:
                # Simulate receiving MIDI messages
                if len(self.devices) > 0:
                    self._simulate_midi_input()

                # Process MIDI message queue
                with self.queue_lock:
                    messages_to_process = self.message_queue.copy()
                    self.message_queue.clear()

                for midi_msg in messages_to_process:
                    self._process_midi_message(midi_msg)

                time.sleep(0.001)  # 1ms processing loop

            except Exception as e:
                logger.error(f"Error in MIDI processing worker: {e}")

    def _simulate_midi_input(self):
        """Simulate MIDI input (for testing)"""
        # In production, this would read from actual MIDI devices
        pass

    def _process_midi_message(self, midi_msg: MIDIMessage):
        """Process a MIDI message"""
        with self.stats_lock:
            self.stats['messages_received'] += 1

        # Publish raw MIDI message
        self.publish("midi.message.received", {
            'message_type': midi_msg.message_type.value,
            'channel': midi_msg.channel,
            'data1': midi_msg.data1,
            'data2': midi_msg.data2,
            'timestamp': midi_msg.timestamp
        }, priority=Priority.HIGH)

        # Check for MIDI learn
        with self.learn_lock:
            if self.learn_mode and midi_msg.message_type == MIDIMessageType.CONTROL_CHANGE:
                if self.learn_target:
                    # Create mapping
                    mapping = MIDIMapping(
                        mapping_id=f"learned_{time.time()}",
                        midi_cc=midi_msg.data1,
                        midi_channel=midi_msg.channel,
                        target_agent=self.learn_target['agent'],
                        target_parameter=self.learn_target['parameter'],
                        min_value=0.0,
                        max_value=1.0,
                        curve='linear',
                        enabled=True
                    )

                    with self.mappings_lock:
                        self.mappings[mapping.mapping_id] = mapping

                    self.publish("midi.mapping.learned", {
                        'mapping_id': mapping.mapping_id,
                        'midi_cc': mapping.midi_cc,
                        'target': f"{mapping.target_agent}.{mapping.target_parameter}"
                    }, priority=Priority.MEDIUM)

                    self.learn_mode = False
                    self.learn_target = None

                return

        # Process CC mappings
        if midi_msg.message_type == MIDIMessageType.CONTROL_CHANGE:
            self._process_cc_mapping(midi_msg)

        # Process note triggers
        elif midi_msg.message_type == MIDIMessageType.NOTE_ON:
            self._process_note_trigger(midi_msg)

        # Process program changes
        elif midi_msg.message_type == MIDIMessageType.PROGRAM_CHANGE:
            self._process_program_change(midi_msg)

    def _process_cc_mapping(self, midi_msg: MIDIMessage):
        """Process CC mapping"""
        with self.mappings_lock:
            for mapping in self.mappings.values():
                if (mapping.enabled and
                    mapping.midi_cc == midi_msg.data1 and
                    mapping.midi_channel == midi_msg.channel):

                    # Scale MIDI value (0-127) to target range
                    normalized = midi_msg.data2 / 127.0

                    # Apply curve
                    if mapping.curve == "exponential":
                        normalized = normalized ** 2
                    elif mapping.curve == "logarithmic":
                        normalized = normalized ** 0.5

                    # Scale to target range
                    value = mapping.min_value + (mapping.max_value - mapping.min_value) * normalized

                    # Send parameter change
                    self.publish("automation.parameter.change", {
                        'agent': mapping.target_agent,
                        'parameter': mapping.target_parameter,
                        'value': value,
                        'source': 'midi'
                    }, priority=Priority.HIGH)

                    with self.stats_lock:
                        self.stats['mappings_triggered'] += 1

    def _process_note_trigger(self, midi_msg: MIDIMessage):
        """Process note trigger"""
        with self.triggers_lock:
            for trigger in self.triggers.values():
                if (trigger.enabled and
                    trigger.note_number == midi_msg.data1 and
                    trigger.midi_channel == midi_msg.channel):

                    # Fire trigger action
                    self._fire_trigger(trigger, midi_msg.data2)

                    with self.stats_lock:
                        self.stats['triggers_fired'] += 1

    def _fire_trigger(self, trigger: MIDITrigger, velocity: int):
        """Fire a trigger action"""
        action_data = {
            'action': trigger.action,
            'parameters': trigger.parameters.copy(),
            'velocity': velocity / 127.0 if trigger.trigger_on_velocity else 1.0
        }

        # Route to appropriate topic based on action
        topic_map = {
            'scene_change': 'effects.scene.change',
            'effect_toggle': 'effects.bypass.toggle',
            'loop_record': 'loop.record.start',
            'preset_recall': 'effects.preset.recall'
        }

        topic = topic_map.get(trigger.action, 'midi.trigger.fired')

        self.publish(topic, action_data, priority=Priority.HIGH)

    def _process_program_change(self, midi_msg: MIDIMessage):
        """Process program change"""
        self.publish("midi.program.change", {
            'channel': midi_msg.channel,
            'program': midi_msg.data1
        }, priority=Priority.MEDIUM)

    def _send_midi_feedback(self, controller_id: str, cc: int, value: int):
        """Send MIDI feedback to controller"""
        # In production, this would send actual MIDI CC messages
        pass

    def _scan_midi_devices(self) -> List[MIDIDevice]:
        """Scan for MIDI devices using mido"""
        devices = []

        if not MIDO_AVAILABLE:
            # Fallback to simulated devices
            self.log("WARNING", "mido not available - using simulated MIDI devices")
            devices = [
                MIDIDevice(
                    device_id="midi_sim_0",
                    device_name="Simulated MIDI Controller",
                    port_number=0,
                    is_input=True,
                    is_output=True,
                    connected=False
                )
            ]
        else:
            try:
                # Scan for real MIDI input ports
                input_names = mido.get_input_names()
                for idx, name in enumerate(input_names):
                    device_id = f"midi_in_{idx}"
                    devices.append(MIDIDevice(
                        device_id=device_id,
                        device_name=name,
                        port_number=idx,
                        is_input=True,
                        is_output=False,
                        connected=False
                    ))

                # Scan for real MIDI output ports
                output_names = mido.get_output_names()
                for idx, name in enumerate(output_names):
                    device_id = f"midi_out_{idx}"
                    devices.append(MIDIDevice(
                        device_id=device_id,
                        device_name=name,
                        port_number=idx,
                        is_input=False,
                        is_output=True,
                        connected=False
                    ))

                self.log("INFO", f"Found {len(input_names)} MIDI inputs and {len(output_names)} outputs")

            except Exception as e:
                self.log("ERROR", f"Error scanning MIDI devices: {e}")

        with self.devices_lock:
            for device in devices:
                self.devices[device.device_id] = device

        return devices

    def _midi_input_callback(self, midi_msg):
        """
        Callback for incoming MIDI messages from mido

        This is called from mido's input thread - keep processing minimal!
        """
        try:
            # Convert mido message to our format
            msg_type = self._convert_mido_message_type(midi_msg.type)
            if msg_type is None:
                return  # Unsupported message type

            # Create internal MIDI message
            message = MIDIMessage(
                message_type=msg_type,
                channel=getattr(midi_msg, 'channel', 0) + 1,  # mido uses 0-15, we use 1-16
                data1=getattr(midi_msg, 'note', getattr(midi_msg, 'control', 0)),
                data2=getattr(midi_msg, 'velocity', getattr(midi_msg, 'value', 0)),
                timestamp=time.time()
            )

            # Add to queue for processing
            with self.queue_lock:
                self.message_queue.append(message)

            # Update statistics
            with self.stats_lock:
                self.stats['messages_received'] += 1

            # Publish MIDI message received event
            self.publish("midi.message.received", {
                'message_type': msg_type.value,
                'channel': message.channel,
                'data1': message.data1,
                'data2': message.data2,
                'timestamp': message.timestamp
            }, priority=Priority.HIGH)

        except Exception as e:
            logger.error(f"Error in MIDI input callback: {e}")

    def _convert_mido_message_type(self, mido_type: str) -> Optional[MIDIMessageType]:
        """Convert mido message type to our enum"""
        type_map = {
            'note_on': MIDIMessageType.NOTE_ON,
            'note_off': MIDIMessageType.NOTE_OFF,
            'control_change': MIDIMessageType.CONTROL_CHANGE,
            'program_change': MIDIMessageType.PROGRAM_CHANGE,
            'pitchwheel': MIDIMessageType.PITCH_BEND,
            'aftertouch': MIDIMessageType.AFTERTOUCH,
            'clock': MIDIMessageType.CLOCK,
            'start': MIDIMessageType.START,
            'stop': MIDIMessageType.STOP,
        }
        return type_map.get(mido_type)

    def _disconnect_all_devices(self):
        """Disconnect all MIDI devices"""
        # Close all real MIDI ports
        if MIDO_AVAILABLE:
            with self.midi_ports_lock:
                for port in list(self.midi_inputs.values()):
                    try:
                        port.close()
                    except:
                        pass
                for port in list(self.midi_outputs.values()):
                    try:
                        port.close()
                    except:
                        pass
                self.midi_inputs.clear()
                self.midi_outputs.clear()

        with self.devices_lock:
            for device in self.devices.values():
                device.connected = False
