# Live Performance Agents - Complete Setup Guide

This guide walks you through setting up the complete Live Performance Agents system, including the backend agents and the web-based control panel.

---

## Prerequisites

### Required Software

1. **Python 3.9 or higher**
   - Download: https://www.python.org/downloads/
   - Verify: `python --version`

2. **Node.js 18 or higher** (for web interface)
   - Download: https://nodejs.org/
   - Verify: `node --version` and `npm --version`

3. **Git** (optional, for cloning repository)
   - Download: https://git-scm.com/
   - Verify: `git --version`

### Optional (Recommended)

- **ASIO audio driver** (Windows) or **Core Audio** (macOS) for low-latency audio
- **MIDI controller** for hands-on control
- **Virtual environment** tool (`venv` or `conda`)

---

## Installation

### Step 1: Get the Code

**Option A: Clone from Git**
```bash
git clone https://github.com/sonic-mind-forge/live-performance-agents.git
cd live-performance-agents
```

**Option B: Download ZIP**
- Download and extract the repository
- Navigate to the extracted folder

### Step 2: Set Up Python Backend

#### Create Virtual Environment (Recommended)

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**On macOS/Linux:**
```bash
python -m venv venv
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt.

#### Install Python Dependencies

```bash
# Install the package in editable mode
pip install -e .

# Or install with all dependencies from requirements.txt
pip install -r requirements.txt
```

**Expected installation time:** 2-5 minutes depending on internet speed.

#### Verify Installation

```bash
python -c "from core import MessageBus; from agents import RealtimeAudioIOAgent; print('✓ Backend installed successfully')"
```

### Step 3: Set Up Frontend

```bash
cd frontend
npm install
```

**Expected installation time:** 1-3 minutes.

#### Verify Installation

```bash
npm run build
```

If it builds without errors, you're good to go!

---

## Running the System

### Method 1: Complete System (Recommended)

This starts both the backend agents and the API server.

#### Terminal 1: Start Backend + API Server

```bash
# Make sure you're in the project root directory
python main.py
```

**Expected output:**
```
============================================================
Live Performance Agents System
Version 0.1.0
============================================================
Creating agents...
Registering agents...
Starting all agents...
INFO - RealtimeAudioIOAgent setup complete
INFO - LiveEffectsChainAgent setup complete
INFO - MIDIControlAgent setup complete
... (all 12 agents)
Starting FastAPI server on http://0.0.0.0:8080
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
============================================================
System is running!
Web interface: http://localhost:8080
API docs: http://localhost:8080/docs
Press Ctrl+C to stop
============================================================
```

#### Terminal 2: Start Frontend

In a **new terminal window:**

```bash
cd frontend
npm run dev
```

**Expected output:**
```
  VITE v5.0.8  ready in 423 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
  ➜  press h + enter to show help
```

#### Access the Web Interface

Open your browser and navigate to:
**http://localhost:5173**

You should see the Live Performance Agents control panel with:
- Agent status grid showing all 12 agents
- Real-time audio level meters
- Sync status (tempo, beat)
- Performance monitoring (CPU, latency)

---

## Method 2: Backend Only (Python API)

If you only need the Python API without the web interface:

```python
# Create a file: my_performance.py

from core import MessageBus, AgentRegistry
from agents import (
    RealtimeAudioIOAgent,
    LiveEffectsChainAgent,
    MIDIControlAgent,
)

# Initialize system
registry = AgentRegistry()

# Create and register agents
audio_io = RealtimeAudioIOAgent()
effects = LiveEffectsChainAgent()
midi = MIDIControlAgent()

registry.register(audio_io)
registry.register(effects)
registry.register(midi)

# Start all agents
registry.start_all()

# Your performance code here
try:
    input("Press Enter to stop...\n")
finally:
    # Cleanup
    registry.stop_all()
```

Run it:
```bash
python my_performance.py
```

---

## Verifying System Operation

### 1. Check Agent Status

In the web interface (`http://localhost:5173`), you should see all 12 agents with green status indicators.

### 2. Check API Health

Open `http://localhost:8080/api/health` in your browser. You should see:

```json
{
  "status": "healthy",
  "clients_connected": 1,
  "uptime": "unknown"
}
```

### 3. Check WebSocket Connection

In the web interface, look for the green "Connected" indicator in the top header. If it shows "Disconnected" (red), check:
- Backend is running on port 8080
- No firewall blocking WebSocket connections
- Browser console for connection errors (F12 → Console tab)

### 4. Check Audio I/O

**Backend should log:**
```
INFO - Available audio interfaces: [list of your audio devices]
INFO - Using simulated audio interface (real I/O available if sounddevice installed)
```

**To enable real audio I/O:**
- Ensure `sounddevice` is installed: `pip install sounddevice`
- Restart the backend: `python main.py`

### 5. Check MIDI Devices

**Backend should log:**
```
INFO - Scanning MIDI devices...
INFO - Found X MIDI input devices
INFO - Found Y MIDI output devices
```

**To test MIDI:**
- Connect a MIDI controller
- Move a knob or fader
- Check the web interface for MIDI activity indicators

---

## Configuration

### Backend Configuration

#### Audio Settings

Edit your performance script or create a config file:

```python
from agents import RealtimeAudioIOAgent
from agents.realtime_audio_io_agent import AudioIOConfig

config = AudioIOConfig(
    sample_rate=48000,
    buffer_size=128,  # Lower = lower latency, higher CPU
    num_input_channels=2,
    num_output_channels=2,
)

audio_io = RealtimeAudioIOAgent(config=config)
```

#### MIDI Settings

```python
from agents import MIDIControlAgent
from agents.midi_control_agent import MIDIConfig

config = MIDIConfig(
    auto_connect=True,  # Auto-connect to all MIDI devices
    learn_timeout_ms=5000,  # MIDI learn timeout
)

midi = MIDIControlAgent(config=config)
```

### Frontend Configuration

#### API Endpoint

Edit `frontend/vite.config.js` if your backend is on a different port:

```javascript
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:YOUR_PORT',  // Change this
      changeOrigin: true,
    },
    '/ws': {
      target: 'ws://localhost:YOUR_PORT',  // Change this
      ws: true,
    },
  },
}
```

#### WebSocket URL

Edit `frontend/src/context/AgentContext.jsx`:

```javascript
const ws = useWebSocket('ws://YOUR_HOST:YOUR_PORT/ws', {
  // ...
});
```

---

## Troubleshooting

### Backend Issues

#### "ModuleNotFoundError: No module named 'core'"

**Solution:**
```bash
# Make sure you're in the project root directory
pip install -e .
```

#### "sounddevice not found"

**Solution:**
```bash
pip install sounddevice
```

The system will work in simulated mode without it, but you won't get real audio I/O.

#### "Port 8080 already in use"

**Solution:**
- Stop any other services using port 8080
- Or change the port in `backend/api_server.py` and `main.py`

#### High CPU Usage

**Solutions:**
- Increase audio buffer size (256 or 512 samples)
- Disable unused agents
- Check for audio feedback loops
- Monitor per-agent CPU in the web interface

### Frontend Issues

#### "npm install" fails

**Solution:**
```bash
# Clear npm cache
npm cache clean --force

# Delete node_modules and package-lock.json
rm -rf node_modules package-lock.json  # macOS/Linux
rmdir /s node_modules  # Windows
del package-lock.json  # Windows

# Reinstall
npm install
```

#### "WebSocket connection failed"

**Checklist:**
- ✓ Backend is running
- ✓ Backend shows "FastAPI server running on http://0.0.0.0:8080"
- ✓ Open `http://localhost:8080` in browser (should show JSON response)
- ✓ Check browser console (F12) for error messages
- ✓ Firewall allows connections to port 8080

#### "Page is blank / white screen"

**Solution:**
```bash
# Check browser console for errors (F12)
# Common causes:

# 1. Build failed - rebuild:
npm run build

# 2. Dev server not running:
npm run dev

# 3. Port 5173 in use - kill process or change port in vite.config.js
```

#### Audio meters not updating

**Checklist:**
- ✓ WebSocket is connected (green indicator in header)
- ✓ Backend is processing audio (check backend logs)
- ✓ Canvas rendering is working (check browser console)
- ✓ Try refreshing the page (Ctrl+R)

### Common Errors

#### "ASIO error" or "Audio interface initialization failed"

This is usually fine - the system will fall back to simulated audio. To use real audio:

1. Install proper audio drivers (ASIO on Windows, Core Audio on macOS)
2. Configure audio device in system settings
3. Set correct device in audio configuration

#### "MIDI device not found"

1. Connect MIDI device before starting backend
2. Check device is recognized by OS (Device Manager on Windows, Audio MIDI Setup on macOS)
3. Restart backend after connecting MIDI device

---

## Performance Optimization

### For Low-Latency Audio

1. **Use ASIO drivers** (Windows) or **Core Audio** (macOS)
2. **Reduce buffer size**: Start with 128 samples, increase if crackling
3. **Increase sample rate**: 48kHz or 96kHz (higher = more CPU)
4. **Disable unused agents**: Comment out agents you don't need in `main.py`
5. **Close other applications**: Free up CPU and RAM

### For Web Interface

1. **Use Chrome or Edge**: Better WebSocket performance than Firefox
2. **Disable browser extensions**: Some block WebSocket connections
3. **Close unused tabs**: Reduces browser memory usage
4. **Use wired connection**: WiFi can introduce WebSocket lag

---

## Next Steps

### Learning the System

1. **Explore the web interface** - Click through all tabs (Dashboard, Effects, MIDI, Loops, Automation)
2. **Read the API docs** - http://localhost:8080/docs
3. **Check examples** - See `examples/` directory
4. **Read architecture docs** - See `CLAUDE.md` and `docs/FRONTEND_ARCHITECTURE.md`

### Building Your Performance

1. **Connect audio interface**
2. **Connect MIDI controller**
3. **Create MIDI mappings** (via web interface or Python API)
4. **Configure effects chain**
5. **Save presets/scenes**
6. **Test automation**
7. **Perform!**

### Advanced Topics

- **Custom effects** - Create your own DSP processors
- **ML/AI integration** - Use PyTorch for intelligent features
- **DMX lighting** - Sync visuals with audio
- **Ableton Link** - Sync with other software
- **Remote collaboration** - Multi-location performances

---

## Getting Help

### Documentation

- **Architecture:** `CLAUDE.md`
- **Frontend:** `frontend/README.md`
- **Fan Engagement:** `docs/FAN_ENGAGEMENT_FEATURES.md`
- **Branding:** `docs/BRANDING_STRATEGY.md`

### Support

- **GitHub Issues:** https://github.com/sonic-mind-forge/live-performance-agents/issues
- **Discussions:** https://github.com/sonic-mind-forge/live-performance-agents/discussions

---

## System Requirements

### Minimum

- **CPU:** Dual-core 2.0 GHz
- **RAM:** 4 GB
- **OS:** Windows 10, macOS 10.15, Ubuntu 20.04
- **Python:** 3.9+
- **Node.js:** 18+

### Recommended

- **CPU:** Quad-core 3.0 GHz or higher
- **RAM:** 8 GB or more
- **OS:** Windows 11, macOS 13+, Ubuntu 22.04
- **Audio Interface:** Professional audio interface with ASIO/Core Audio
- **MIDI Controller:** USB MIDI controller
- **Storage:** SSD for faster load times

---

**You're all set! Enjoy performing with Live Performance Agents! 🎵🎶**
