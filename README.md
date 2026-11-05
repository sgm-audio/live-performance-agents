# Live Performance Agents

**Real-time agent-based system for live audio performance**

A collection of specialized Python agents designed for real-time live audio performance scenarios. The system is built on an agent-based architecture where each agent handles a specific aspect of live audio production (I/O, effects, MIDI control, looping, automation, etc.) and communicates through a high-performance message-passing system.

## Features

- **Ultra-low latency audio I/O** - ASIO/Core Audio support, <5ms round-trip latency
- **Real-time DSP effects chain** - Compression, EQ, reverb, delay with live parameter control
- **MIDI integration** - CC mapping, MIDI learn, note triggers, MIDI clock sync
- **Live looping** - Multi-track loop recording with overdub, undo/redo
- **Performance automation** - Scene management, macro controls, cue system
- **Tempo synchronization** - MIDI clock, Ableton Link, tap tempo
- **Visual/lighting control** - DMX output with audio-reactive mapping
- **Real-time mixing** - Auto-mixing, ducking, feedback suppression
- **System monitoring** - CPU/latency tracking, performance alerts
- **Backup/redundancy** - Automatic failover, state snapshots
- **Web-based control panel** - Real-time dashboard for monitoring and control
- **WebSocket API** - Bidirectional real-time communication with frontend

## Architecture

The system uses a **message-passing agent architecture**:
- Each agent is independent and communicates via publish/subscribe topics
- Priority-based message routing ensures real-time performance
- Thread-safe design for concurrent audio processing
- All agents inherit from `BaseAgent` with standardized lifecycle management

## Installation

```bash
# Clone the repository
git clone https://github.com/sgm-audio/live-performance-agents.git
cd live-performance-agents

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install package
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

## Quick Start

### Option 1: Complete System with Web Interface (Recommended)

```bash
# Start the complete system (agents + API server)
python main.py
```

The system will start:
- All 12 agents (audio, MIDI, effects, etc.)
- FastAPI server on `http://localhost:8080`
- WebSocket endpoint at `ws://localhost:8080/ws`

Then in a separate terminal, start the frontend:

```bash
cd frontend
npm install  # First time only
npm run dev
```

Access the web control panel at `http://localhost:5173`

### Option 2: Python API Only

```python
from core import MessageBus, AgentRegistry
from agents import RealtimeAudioIOAgent, LiveEffectsChainAgent, MIDIControlAgent

# Initialize message bus
bus = MessageBus()

# Create agent registry
registry = AgentRegistry()

# Register agents
audio_agent = RealtimeAudioIOAgent()
effects_agent = LiveEffectsChainAgent()
midi_agent = MIDIControlAgent()

registry.register(audio_agent)
registry.register(effects_agent)
registry.register(midi_agent)

# Start all agents
registry.start_all()

# Your performance code here...

# Cleanup
registry.stop_all()
```

## Available Agents

| Agent | Purpose |
|-------|---------|
| `RealtimeAudioIOAgent` | Ultra-low latency audio I/O with routing matrix |
| `LiveEffectsChainAgent` | Real-time DSP effects with preset management |
| `MIDIControlAgent` | MIDI device integration and CC mapping |
| `LiveLoopingAgent` | Multi-track loop recording and playback |
| `PerformanceAutomationAgent` | Parameter automation and scene control |
| `SynchronizationClockAgent` | Tempo/timing sync and MIDI clock |
| `VisualLightingControlAgent` | DMX/visual synchronization |
| `LiveMixingDynamicsAgent` | Channel mixing and dynamics processing |
| `PerformanceMonitoringAgent` | CPU/latency monitoring and alerts |
| `BackupRedundancyAgent` | System redundancy and failover |
| `IndustryStandardsAgent` | Audio standard compliance (LUFS, true peak) |
| `WebInterfaceAgent` | WebSocket bridge for web frontend communication |

## Requirements

### Backend (Python)

- Python 3.9+
- NumPy, SciPy for DSP
- sounddevice for audio I/O
- librosa for advanced audio processing
- pretty-midi, mido for MIDI
- PyTorch for ML/AI features
- psutil for system monitoring
- FastAPI, uvicorn for web API
- websockets for real-time communication

### Frontend (Web Interface)

- Node.js 18+
- React 18
- Vite
- Tailwind CSS
- See `frontend/package.json` for complete list

## Web Interface

The system includes a professional web-based control panel for monitoring and controlling all agents in real-time.

### Features

- **Real-time Dashboard** - Monitor all 12 agents, audio levels, and system performance
- **Agent Status Grid** - Visual status indicators for each agent
- **Audio Level Metering** - Real-time input/output meters with peak detection
- **Sync Status** - Current tempo, beat position, and playback state
- **Performance Monitoring** - CPU usage, latency, warnings, and errors
- **WebSocket Communication** - 30Hz audio updates, 10Hz status updates

### API Endpoints

**WebSocket:** `ws://localhost:8080/ws`
- Bidirectional real-time communication
- Agent status updates
- Audio level metering (30Hz)
- MIDI message feedback
- Effect parameter changes

**REST API:** `http://localhost:8080/api/`
- `/api/agents` - Get all agent status
- `/api/effects/{effect_id}/parameters` - Set effect parameters
- `/api/midi/devices` - Get MIDI device list
- `/api/loops/{loop_id}/record/start` - Start loop recording
- `/api/presets` - Manage presets
- Full API docs: `http://localhost:8080/docs`

See [frontend/README.md](frontend/README.md) for detailed frontend documentation.

## Documentation

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for architecture and development notes.

## Examples

`examples/basic_setup.py` starts the system with the default agents.

## License

MIT. See [LICENSE](LICENSE).

## Credits

Developed by **Sonic Mind Forge** as part of the EthoBeat ecosystem.
