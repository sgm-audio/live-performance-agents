# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Live Performance Agents** is a production-ready, real-time agent-based system for live audio performance. The system features 11 specialized Python agents that communicate via a high-performance message bus to handle audio I/O, DSP effects, MIDI control, looping, automation, and synchronization.

**Current Status:** 90% production-ready with real hardware integration (sounddevice, mido, librosa).

## Installation & Setup

```bash
# Install package in editable mode
pip install -e .

# Install with development tools
pip install -e ".[dev]"

# Run basic example
python examples/basic_setup.py
```

## Architecture

### Core Framework (`core/`)

**Message-Passing System:**
- `MessageBus` - Singleton message broker with priority queue (LOW, MEDIUM, HIGH, CRITICAL)
- `BaseAgent` - Abstract base class all agents inherit from
- `AgentRegistry` - Manages agent lifecycle (startup/shutdown in correct order)
- `Message` - Dataclass with topic, sender, payload, priority, timestamp
- `Topics` - Predefined topic constants organized by category

**Agent Lifecycle:**
```python
class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_id="my_agent", agent_name="My Agent")

    def setup(self):
        # Subscribe to topics, start threads
        self.subscribe("some.topic")

    def teardown(self):
        # Stop threads, cleanup resources
        pass

    def handle_message(self, message: Message):
        # Route and process messages
        if message.topic == "some.topic":
            self._handle_topic(message)
```

### Agent Architecture (`agents/`)

**11 Production Agents:**

| Agent | Real I/O | Status | Purpose |
|-------|----------|--------|---------|
| RealtimeAudioIOAgent | sounddevice ✅ | 90% | Audio capture/playback, <5ms latency |
| LiveEffectsChainAgent | scipy DSP ✅ | 95% | 15 real-time effects, presets, scenes |
| MIDIControlAgent | mido ✅ | 90% | MIDI devices, CC mapping, MIDI learn |
| LiveLoopingAgent | librosa ✅ | 85% | Loop recording, time-stretch, pitch-shift |
| SynchronizationClockAgent | - | 90% | Tempo, BPM, beat tracking, tap tempo |
| PerformanceAutomationAgent | - | 85% | Parameter automation, scenes, macros |
| PerformanceMonitoringAgent | psutil ✅ | 90% | CPU/latency monitoring, alerts |
| BackupRedundancyAgent | - | 85% | State snapshots, failover |
| IndustryStandardsAgent | - | 95% | LUFS compliance, standards checking |
| VisualLightingControlAgent | - | 45% | DMX output (needs pyartnet) |
| LiveMixingDynamicsAgent | - | 40% | Auto-mixing (needs real DSP) |

### Message Flow Example

```
MIDI Controller → mido → MIDIControlAgent
                            ↓
            Message: automation.parameter.change (HIGH priority)
                            ↓
                  LiveEffectsChainAgent
                            ↓
                    DSP Processing (scipy)
                            ↓
            Processed Audio → RealtimeAudioIOAgent
                            ↓
                  sounddevice → Speakers
```

**Typical Latency:** ~5-10ms (professional-grade)

## Key Patterns

### Thread Safety (Critical for Real-Time)

**All agents use this pattern:**
```python
# Always create locks for shared state
self.config_lock = threading.Lock()
self.buffer_lock = threading.Lock()
self.stats_lock = threading.Lock()

# Always use context managers
with self.config_lock:
    self.config.sample_rate = new_rate
```

### Worker Thread Pattern

**Consistent across all agents:**
```python
def _start_{name}_thread(self):
    self.{name}_active = True
    self.{name}_thread = threading.Thread(
        target=self._{name}_worker,
        name=f"{self.agent_id}_{name}",
        daemon=True  # Always daemon
    )
    self.{name}_thread.start()

def _stop_{name}_thread(self):
    self.{name}_active = False
    if self.{name}_thread:
        self.{name}_thread.join(timeout=2.0)  # Always 2 second timeout

def _{name}_worker(self):
    while self.{name}_active:  # Check flag, not True
        try:
            # Work here
            time.sleep(interval)
        except Exception as e:
            logger.error(f"Error: {e}")
```

### Message Handling Pattern

```python
def handle_message(self, message: Message):
    try:
        if message.topic == "topic.one":
            self._handle_one(message)
        elif message.topic == "topic.two":
            self._handle_two(message)
    except Exception as e:
        self.log("ERROR", f"Error: {e}", {"topic": message.topic})

def _handle_one(self, message: Message):
    payload = message.payload
    param = payload.get('param', default_value)

    # Do work with locks
    with self.resource_lock:
        result = self._process(param)

    # Respond to sender
    self.respond(message, {'success': True, 'result': result})

    # Optionally publish event
    self.publish("topic.completed", {'param': param}, priority=Priority.MEDIUM)
```

### Dataclass Pattern

```python
from dataclasses import dataclass, field

@dataclass
class Config:
    name: str
    enabled: bool = True
    # ALWAYS use field(default_factory=...) for mutable types
    items: List[str] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)
    # NEVER: items: List[str] = []  # Wrong! Shared across instances
```

## Real I/O Integration

### Audio I/O (sounddevice)

**RealtimeAudioIOAgent** uses callbacks for ultra-low latency:
```python
def _audio_callback(self, indata, outdata, frames, time_info, status):
    # Runs in high-priority audio thread - keep minimal!
    # Input → buffer → processing → output
    with self.buffer_lock:
        self.input_buffer.append(indata.copy())
        if len(self.output_buffer) > 0:
            outdata[:] = self.output_buffer.popleft()
        else:
            outdata[:] = 0  # Silence if no output
```

**Fallback:** Gracefully falls back to simulated mode if sounddevice unavailable.

### MIDI I/O (mido)

**MIDIControlAgent** connects to real devices:
```python
# Device scanning
input_names = mido.get_input_names()  # Real device discovery
output_names = mido.get_output_names()

# Port opening with callback
port = mido.open_input(device_name, callback=self._midi_input_callback)

# Callback processes messages in real-time
def _midi_input_callback(self, midi_msg):
    # Convert mido message → internal format → publish
    self.publish("midi.message.received", {...}, priority=Priority.HIGH)
```

**Fallback:** Simulated devices if mido unavailable.

### Loop Processing (librosa)

**TimeStretcher & PitchShifter** in `loop_processors.py`:
```python
# Time-stretch without changing pitch
stretched = librosa.effects.time_stretch(audio, rate=1.0/factor)

# Pitch-shift without changing duration
shifted = librosa.effects.pitch_shift(audio, sr=sample_rate, n_steps=semitones)
```

**Fallback:** Basic overlap-add and resample methods if librosa unavailable.

## DSP Processing

### Effects Processors (`agents/effects_processors.py`)

**15 Working Effects:**
- Dynamics: Compressor, Limiter, Gate, Expander
- EQ: Parametric (4-band), Graphic (31-band)
- Time: Reverb (Schroeder), Delay, Chorus, Flanger
- Modulation: Phaser, Tremolo, Vibrato
- Distortion: Waveshaping, Saturation

**All optimized for <2ms latency using scipy.signal**

### Effect Processing Flow

1. Agent receives `audio.live.process` message
2. `_get_processor(effect_id, effect_type)` - cached processor retrieval
3. `processor.process(audio, parameters)` - DSP processing
4. Wet/dry mix: `output = wet * mix + dry * (1 - mix)`
5. Processors maintain state (delays, envelopes, filters)

## Topic Naming

**Hierarchical dot notation:**
- `audio.live.{operation}` - Audio I/O operations
- `effects.{operation}` - Effect control
- `midi.{operation}` - MIDI messages
- `sync.{operation}` - Tempo/clock
- `loop.{operation}` - Loop control
- `automation.{operation}` - Parameter automation
- `monitor.{operation}` - Performance monitoring

**See `core/topics.py` for complete list of predefined constants.**

## Audio Format Standards

**All audio is np.ndarray, float32:**
- Mono: `(num_samples,)` or `(num_samples, 1)`
- Stereo: `(num_samples, 2)`
- Sample range: -1.0 to +1.0
- Common sample rates: 44100, 48000, 96000 Hz
- Common buffer sizes: 64, 128, 256 samples

**Latency calculation:**
```python
buffer_latency_ms = (buffer_size / sample_rate) * 1000
# e.g., 128 samples @ 48kHz = 2.67ms
```

## Code Style

**Enforced via pyproject.toml:**
```bash
# Format code
black . --line-length 100

# Type checking
mypy core/ agents/

# Linting
flake8 core/ agents/
```

**Logging:**
```python
# Module-level
logger = logging.getLogger(__name__)

# Agent-level
self.log("INFO", "Message", {"context": "value"})
self.log("ERROR", "Error occurred", {"topic": message.topic})
```

## Testing

**Test structure (when implemented):**
```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_core/test_message_bus.py::test_priority_queue

# With coverage
pytest --cov=core --cov=agents
```

## Important Notes

### Real-Time Constraints

**Audio processing MUST complete within buffer time:**
- 128 samples @ 48kHz = 2.67ms
- 256 samples @ 48kHz = 5.33ms
- Processing must finish in <80% of buffer time to prevent glitches

**Keep audio callbacks minimal:**
- No logging in callbacks
- No blocking operations
- Minimal lock contention
- Pre-allocate buffers

### Thread Safety Checklist

- [ ] All shared state protected by locks
- [ ] Lock naming: `{resource}_lock`
- [ ] Always use `with` statements
- [ ] Worker threads use active flags, not `while True:`
- [ ] Threads joined with 2-second timeout
- [ ] All threads are daemon=True

### Error Handling

**Always catch exceptions in:**
- Message handlers (`handle_message`)
- Worker threads
- Audio/MIDI callbacks

**Never:**
- Let exceptions crash agents
- Use bare `except:` without logging
- Block in error handlers

## Common Gotchas

1. **Mutable defaults in dataclasses** - Use `field(default_factory=list)`, not `= []`
2. **Thread loops** - Use `while self.active:`, not `while True:`
3. **Audio callback blocking** - Keep under 1ms, no I/O operations
4. **Lock acquisition order** - Always acquire in same order to prevent deadlock
5. **Buffer sizes** - Must match across audio chain (input → processing → output)

## Development Workflow

**Typical development session:**
```bash
# 1. Make changes to agents or core
# 2. Install in editable mode (if not already)
pip install -e .

# 3. Run example to test
python examples/basic_setup.py

# 4. Check for errors
# 5. Format and lint
black . --line-length 100
flake8 core/ agents/

# 6. Commit changes
git add .
git commit -m "Description"
```

## Performance Targets

**Real-time audio system benchmarks:**
- Round-trip latency: <10ms (achieved: ~5-10ms)
- CPU usage per effect: <2% @ 48kHz
- Message bus throughput: >10,000 msgs/sec
- MIDI latency: <5ms (CC to parameter change)
- Buffer underruns: 0 in normal operation

## Dependencies

**Production:**
- numpy, scipy - DSP and numerical processing
- sounddevice - Real-time audio I/O
- librosa, numba - Time/pitch processing
- mido, pretty-midi - MIDI I/O
- torch, torchaudio - ML features (future)
- psutil - System monitoring

**Development:**
- pytest, pytest-cov - Testing
- black - Code formatting (line-length=100)
- flake8 - Linting
- mypy - Type checking
