"""
Topic constants for message routing

This module provides predefined topic constants to avoid typos
and provide IDE autocomplete support.
"""


class Topics:
    """Predefined topic constants organized by category"""

    # Audio I/O topics
    class Audio:
        INPUT_REQUEST = "audio.live.input.request"
        OUTPUT_SEND = "audio.live.output.send"
        INTERFACE_CONFIGURE = "audio.live.interface.configure"
        INTERFACE_STATUS = "audio.live.interface.status"
        ROUTING_CHANGE = "audio.live.routing.change"
        MONITORING_CONFIG = "audio.live.monitoring.config"
        LATENCY_MEASURE = "audio.live.latency.measure"
        LATENCY_REPORT = "audio.live.latency.report"
        BUFFER_OPTIMIZE = "audio.live.buffer.optimize"
        PROCESS = "audio.live.process"
        STREAM_STATUS = "audio.live.stream.status"
        QUALITY_ANALYZE = "audio.quality.analyze"
        ANALYSIS_SPECTRUM = "audio.analysis.spectrum"

    # Effects topics
    class Effects:
        CHAIN_CREATE = "effects.chain.create"
        CHAIN_UPDATE = "effects.chain.update"
        CHAIN_DELETE = "effects.chain.delete"
        CHAIN_CREATED = "effects.chain.created"
        PRESET_RECALL = "effects.preset.recall"
        PRESET_SAVE = "effects.preset.save"
        PRESET_RECALLED = "effects.preset.recalled"
        PARAMETER_CHANGE = "effects.parameter.change"
        BYPASS_TOGGLE = "effects.bypass.toggle"
        SCENE_CHANGE = "effects.scene.change"
        SCENE_CREATE = "effects.scene.create"
        SCENE_CHANGED = "effects.scene.changed"
        MORPH_START = "effects.morph.start"
        AB_COMPARE = "effects.ab.compare"

    # MIDI topics
    class MIDI:
        DEVICE_SCAN = "midi.device.scan"
        DEVICE_CONNECT = "midi.device.connect"
        DEVICE_DISCONNECT = "midi.device.disconnect"
        DEVICE_CONNECTED = "midi.device.connected"
        MESSAGE_RECEIVED = "midi.message.received"
        MESSAGE_SEND = "midi.message.send"
        MAPPING_CREATE = "midi.mapping.create"
        MAPPING_DELETE = "midi.mapping.delete"
        MAPPING_CREATED = "midi.mapping.created"
        MAPPING_LEARNED = "midi.mapping.learned"
        LEARN_START = "midi.mapping.learn.start"
        LEARN_STOP = "midi.mapping.learn.stop"
        TRIGGER_CREATE = "midi.trigger.create"
        TRIGGER_DELETE = "midi.trigger.delete"
        TRIGGER_FIRED = "midi.trigger.fired"
        PROGRAM_CHANGE = "midi.program.change"
        FEEDBACK_ENABLE = "midi.feedback.enable"

    # Synchronization topics
    class Sync:
        TEMPO_SET = "sync.tempo.set"
        TEMPO_DETECT = "sync.tempo.detect"
        TAP_TEMPO = "sync.tap.tempo"
        CLOCK_TEMPO = "sync.clock.tempo"
        CLOCK_POSITION = "sync.clock.position"
        TRANSPORT_PLAY = "sync.transport.play"
        TRANSPORT_STOP = "sync.transport.stop"
        TRANSPORT_PAUSE = "sync.transport.pause"
        TRANSPORT_CONTROL = "sync.transport.control"
        MIDI_CLOCK_ENABLE = "sync.midi.clock.enable"
        MIDI_CLOCK_OUT = "sync.midi.clock.out"
        LINK_ENABLE = "sync.link.enable"

    # Automation topics
    class Automation:
        RECORD_START = "automation.record.start"
        RECORD_STOP = "automation.record.stop"
        PLAYBACK_ENABLE = "automation.playback.enable"
        PARAMETER_CHANGE = "automation.parameter.change"
        SCENE_TRIGGER = "automation.scene.trigger"
        SCENE_CREATE = "automation.scene.create"
        SCENE_TRIGGERED = "automation.scene.triggered"
        MACRO_CREATE = "automation.macro.create"
        MACRO_CHANGE = "automation.macro.change"
        CUE_CREATE = "automation.cue.create"
        CUE_FIRE = "automation.cue.fire"
        CUE_FIRED = "automation.cue.fired"

    # Loop topics
    class Loop:
        TRACK_CREATE = "loop.track.create"
        TRACK_DELETE = "loop.track.delete"
        TRACK_CREATED = "loop.track.created"
        RECORD_START = "loop.record.start"
        RECORD_STOP = "loop.record.stop"
        RECORD_STARTED = "loop.record.started"
        RECORD_STOPPED = "loop.record.stopped"
        PLAYBACK_TOGGLE = "loop.playback.toggle"
        OVERDUB_ENABLE = "loop.overdub.enable"
        CLEAR = "loop.clear"
        UNDO = "loop.undo"
        REDO = "loop.redo"
        MANIPULATE = "loop.manipulate"
        SYNC_QUANTIZE = "loop.sync.quantize"

    # Mixing topics
    class Mix:
        CHANNEL_ADD = "mix.channel.add"
        CHANNEL_PRIORITY = "mix.channel.priority"
        AUTOMIX_ENABLE = "mix.automix.enable"
        AUTOMIX_STATUS = "mix.automix.status"
        DUCKING_CONFIGURE = "mix.ducking.configure"
        FEEDBACK_SUPPRESS = "mix.feedback.suppress"
        FEEDBACK_DETECTED = "mix.feedback.detected"
        SPATIAL_POSITION = "mix.spatial.position"

    # Visual/Lighting topics
    class Visual:
        FIXTURE_ADD = "visual.fixture.add"
        FIXTURE_CONTROL = "visual.fixture.control"
        SCENE_CREATE = "visual.scene.create"
        SCENE_TRIGGER = "visual.scene.trigger"
        LIGHTING_SCENE = "visual.lighting.scene"
        AUDIO_MAPPING_CREATE = "visual.audio.mapping.create"
        BEAT_TRIGGER = "visual.beat.trigger"
        BEAT_DETECTED = "visual.beat.detected"
        DMX_UPDATE = "visual.dmx.update"

    # Monitoring topics
    class Monitor:
        METRICS_REQUEST = "monitor.metrics.request"
        PERFORMANCE_CPU = "monitor.performance.cpu"
        ALERT_CREATE = "monitor.alert.create"
        ALERT_DELETE = "monitor.alert.delete"
        ALERT_TRIGGERED = "monitor.alert.triggered"
        ALERT_CRITICAL = "monitor.alert.critical"
        REPORT_GENERATE = "monitor.report.generate"

    # Backup/Redundancy topics
    class Backup:
        ENABLE = "backup.enable"
        CONFIGURE = "backup.configure"
        SYSTEM_STATUS = "backup.system.status"
        STATE_SYNC = "backup.state.sync"
        STATE_SAVE = "backup.state.save"
        STATE_RESTORE = "backup.state.restore"
        RESTORE_STATE = "backup.restore.state"
        FAILOVER_TRIGGER = "backup.failover.trigger"
        RECORDING_START = "backup.recording.start"
        RECORDING_STOP = "backup.recording.stop"
        RECORDING_SAVE = "backup.recording.save"

    # Standards topics
    class Standards:
        ANALYZE = "standards.analyze"
        COMPARE = "standards.compare"
        RECOMMEND = "standards.recommend"
        REPORT_GENERATE = "standards.report.generate"

    # System topics
    class System:
        STATE_CHANGED = "system.state.changed"
        AGENT_HEARTBEAT = "system.agent.heartbeat"
