# Live Performance Agents - Frontend Architecture

## Overview

The frontend provides a real-time web-based control panel for monitoring and controlling all Live Performance Agents during live performances. It connects to the backend agent system via WebSocket for bidirectional real-time communication.

---

## Technology Stack

### Backend API Layer
- **FastAPI** - Modern async Python web framework
  - WebSocket support for real-time bidirectional communication
  - REST API for configuration and state management
  - Automatic OpenAPI/Swagger documentation
  - CORS support for local development

### Frontend Application
- **React 18** - Component-based UI framework
  - Functional components with hooks
  - Context API for global state management
  - React Query for server state synchronization

- **Tailwind CSS** - Utility-first CSS framework
  - Responsive design out of the box
  - Dark mode support for performance environments
  - Custom color palette matching brand identity

- **Visualization Libraries**
  - **Canvas API** - Real-time audio metering and waveforms
  - **D3.js** - Advanced visualizations for automation curves
  - **React Flow** - Visual effects chain editor
  - **Chart.js** - Performance statistics and monitoring

### Real-Time Communication
- **WebSocket Protocol** - Bidirectional communication
  - Agent status updates (10Hz)
  - Audio level metering (30Hz)
  - MIDI message feedback (real-time)
  - Effect parameter changes (real-time)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Browser (Frontend)                       │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │ Dashboard  │  │ Effects Chain│  │ MIDI Controller  │    │
│  │ Component  │  │ Editor       │  │ Mapping          │    │
│  └────────────┘  └──────────────┘  └──────────────────┘    │
│         │                │                    │              │
│         └────────────────┴────────────────────┘              │
│                          │                                   │
│                 ┌────────▼────────┐                          │
│                 │ WebSocket Client│                          │
│                 └────────┬────────┘                          │
└──────────────────────────┼──────────────────────────────────┘
                           │ WebSocket
                           │ (ws://localhost:8080/ws)
┌──────────────────────────▼──────────────────────────────────┐
│                  FastAPI Backend Server                      │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              WebInterfaceAgent                          ││
│  │  - Subscribes to all MessageBus topics                 ││
│  │  - Forwards messages to WebSocket clients              ││
│  │  - Receives commands from frontend                     ││
│  │  - Publishes to MessageBus                             ││
│  └─────────────────────────────────────────────────────────┘│
│                          │                                   │
│                 ┌────────▼────────┐                          │
│                 │   MessageBus    │                          │
│                 └────────┬────────┘                          │
└──────────────────────────┼──────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐      ┌────▼────┐      ┌────▼────┐
    │ Audio   │      │ Effects │      │ MIDI    │
    │ I/O     │      │ Chain   │      │ Control │
    │ Agent   │      │ Agent   │      │ Agent   │
    └─────────┘      └─────────┘      └─────────┘
```

---

## Core Components

### 1. WebInterfaceAgent (New Backend Agent)

```python
class WebInterfaceAgent(BaseAgent):
    """
    Bridges MessageBus and WebSocket for frontend communication

    Features:
    - Subscribes to all agent status topics
    - Maintains list of connected WebSocket clients
    - Forwards relevant messages to clients (filtered/throttled)
    - Receives commands from frontend and publishes to MessageBus
    - Authentication and rate limiting
    """
```

**Message Subscriptions:**
- `agent.*.status` - All agent status updates
- `audio.live.levels` - Audio metering data
- `midi.message.received` - MIDI feedback
- `effects.*.changed` - Effect parameter changes
- `sync.tempo.changed` - Tempo changes
- `loop.*.status` - Loop status updates
- `monitor.stats` - Performance statistics

**Frontend Commands Handled:**
- `effect.parameter.set` - Change effect parameter
- `midi.mapping.create` - Create MIDI CC mapping
- `loop.record.start` - Start loop recording
- `preset.load` - Load preset/scene
- `automation.start` - Start automation playback

### 2. FastAPI Backend Server

**File:** `backend/api_server.py`

```python
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio

app = FastAPI(title="Live Performance Agents API")

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # Register client with WebInterfaceAgent
    # Forward messages bidirectionally

# REST endpoints
@app.get("/api/agents")
async def get_agents():
    """Get all agent status"""

@app.get("/api/presets")
async def get_presets():
    """Get available presets"""

@app.post("/api/effects/{effect_id}/parameters")
async def set_effect_parameter(effect_id: str, parameter: dict):
    """Set effect parameter"""
```

### 3. React Frontend Application

**File Structure:**
```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   ├── Dashboard/
│   │   │   ├── AgentStatusGrid.jsx
│   │   │   ├── AudioMeters.jsx
│   │   │   └── PerformanceMonitor.jsx
│   │   ├── EffectsChain/
│   │   │   ├── EffectNode.jsx
│   │   │   ├── EffectParameters.jsx
│   │   │   └── ChainEditor.jsx
│   │   ├── MIDIControl/
│   │   │   ├── MIDIDeviceList.jsx
│   │   │   ├── MappingEditor.jsx
│   │   │   └── MIDILearn.jsx
│   │   ├── LoopControl/
│   │   │   ├── LoopRecorder.jsx
│   │   │   ├── LoopGrid.jsx
│   │   │   └── LoopWaveform.jsx
│   │   └── Automation/
│   │       ├── AutomationTimeline.jsx
│   │       └── CurveEditor.jsx
│   ├── hooks/
│   │   ├── useWebSocket.js
│   │   ├── useAgentStatus.js
│   │   └── useAudioLevels.js
│   ├── context/
│   │   └── AgentContext.jsx
│   ├── App.jsx
│   └── index.jsx
├── package.json
└── tailwind.config.js
```

---

## Key Features

### 1. Real-Time Dashboard

**Components:**
- **Agent Status Grid** - Visual status of all 11 agents
  - Green: Running normally
  - Yellow: Warning (high CPU, buffer underrun)
  - Red: Error state
  - Gray: Stopped/Offline

- **Audio Meters** - Real-time input/output levels
  - Peak hold indicators
  - Clipping detection (red flash)
  - 30 FPS update rate using Canvas API

- **Performance Monitor** - System resources
  - CPU usage per agent
  - Audio buffer health
  - Latency measurements
  - Message queue depth

### 2. Effects Chain Editor

**Visual Node-Based Interface:**
- Drag-and-drop effect reordering
- Visual connections showing signal flow
- Add/remove effects from palette
- A/B comparison toggle
- Wet/dry mix controls
- Bypass individual effects

**Parameter Controls:**
- Real-time parameter sliders with value display
- MIDI learn for any parameter (right-click)
- Automation envelope display overlay
- Preset save/load per effect
- Undo/redo for parameter changes

### 3. MIDI Controller Mapping

**Features:**
- Auto-scan for connected MIDI devices
- Visual MIDI activity indicator
- MIDI learn workflow:
  1. Click "Learn" on parameter
  2. Move MIDI controller
  3. Mapping auto-created and saved
- Mapping list with edit/delete
- Support for CC, notes, pitch bend
- Min/max range mapping
- Curve adjustment (linear/exponential/logarithmic)

### 4. Loop Recording & Control

**Interface:**
- Record button with countdown (quantized to beat)
- Waveform visualization for each loop
- Play/stop/overdub controls
- Volume/pan per loop
- Time-stretch and pitch-shift controls
- Slice and rearrange interface
- Export loop as WAV

### 5. Automation Timeline

**Features:**
- Timeline view showing all active automations
- Multi-parameter automation on single timeline
- Curve editor with adjustable shapes
- Record automation from MIDI controller
- Playback controls (play/pause/stop)
- Loop automation sequences
- Snap to beat grid

### 6. Preset Management

**Scenes and Presets:**
- Scene = Full system state (all agents)
- Preset = Single effect/chain configuration
- Save/load/delete interface
- Quick-switch between scenes (0-9 keys)
- Import/export presets as JSON
- Preset browser with search/tags

---

## WebSocket Message Protocol

### Message Format

```json
{
  "type": "agent_status" | "audio_levels" | "midi_message" | "command" | "response",
  "timestamp": 1234567890.123,
  "data": {...}
}
```

### Frontend → Backend (Commands)

```json
// Set effect parameter
{
  "type": "command",
  "command": "effect.parameter.set",
  "data": {
    "effect_id": "reverb_1",
    "parameter": "mix",
    "value": 0.5
  }
}

// Start loop recording
{
  "type": "command",
  "command": "loop.record.start",
  "data": {
    "loop_id": "loop_1",
    "quantize": true
  }
}

// Create MIDI mapping
{
  "type": "command",
  "command": "midi.mapping.create",
  "data": {
    "device_id": "midi_in_0",
    "cc_number": 7,
    "target_agent": "effects_chain",
    "target_parameter": "reverb_1.mix",
    "min_value": 0.0,
    "max_value": 1.0
  }
}
```

### Backend → Frontend (Updates)

```json
// Agent status update
{
  "type": "agent_status",
  "timestamp": 1234567890.123,
  "data": {
    "agent_id": "audio_io",
    "status": "running",
    "cpu_usage": 12.5,
    "warnings": []
  }
}

// Audio levels (30Hz)
{
  "type": "audio_levels",
  "timestamp": 1234567890.123,
  "data": {
    "inputs": [0.45, 0.52],  // L/R RMS
    "outputs": [0.38, 0.41],
    "peaks": [0.89, 0.92],
    "clipping": false
  }
}

// MIDI message received
{
  "type": "midi_message",
  "timestamp": 1234567890.123,
  "data": {
    "device_id": "midi_in_0",
    "message_type": "CONTROL_CHANGE",
    "channel": 1,
    "cc_number": 7,
    "value": 127
  }
}
```

---

## Performance Optimizations

### 1. Message Throttling

**WebInterfaceAgent throttles high-frequency updates:**
- Audio levels: Max 30 Hz (33ms interval)
- Agent status: Max 10 Hz (100ms interval)
- MIDI messages: No throttling (real-time)
- Effect changes: Max 20 Hz (50ms interval)

### 2. Frontend Optimizations

**React Performance:**
- Use `React.memo()` for expensive components
- `useMemo()` and `useCallback()` for heavy computations
- Virtual scrolling for large lists (loop library, preset browser)
- Debounce parameter sliders (update on mouse up)

**Canvas Rendering:**
- RequestAnimationFrame for smooth 60 FPS
- Only redraw when data changes
- Offscreen canvas for complex visualizations
- WebGL for waveform rendering (if needed)

### 3. Data Compression

**For high-frequency data (audio levels, waveforms):**
- Binary WebSocket messages instead of JSON
- Float32Array for audio data
- Delta compression for repeated values

---

## Security & Authentication

### Development Mode
- No authentication required
- CORS allows localhost origins
- WebSocket accepts all connections

### Production Mode (Future)
- JWT token authentication
- HTTPS/WSS only
- Rate limiting per client
- Input validation on all commands

---

## Installation & Setup

### Backend Dependencies

```bash
# Add to requirements.txt
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
websockets>=12.0
python-multipart>=0.0.6
```

### Frontend Setup

```bash
cd frontend
npm install react react-dom
npm install @tanstack/react-query
npm install tailwindcss postcss autoprefixer
npm install react-flow-renderer
npm install chart.js react-chartjs-2
npm install d3
npm install --save-dev vite @vitejs/plugin-react
```

### Running the System

```bash
# Terminal 1: Start agents backend
python main.py

# Terminal 2: Start API server
uvicorn backend.api_server:app --reload --port 8080

# Terminal 3: Start frontend dev server
cd frontend && npm run dev
```

**Access:** http://localhost:5173

---

## Responsive Design

### Breakpoints (Tailwind)
- `sm`: 640px - Mobile landscape
- `md`: 768px - Tablet
- `lg`: 1024px - Desktop
- `xl`: 1280px - Large desktop

### Layout Modes

**Mobile (< 768px):**
- Single column layout
- Tabbed interface (Dashboard / Effects / MIDI / Loops)
- Simplified controls (touch-friendly)
- Bottom navigation bar

**Tablet (768px - 1024px):**
- Two column layout
- Side panel for parameters
- Collapsible sections

**Desktop (> 1024px):**
- Multi-panel layout
- Left: Agent status + navigation
- Center: Main workspace (effects/loops/automation)
- Right: Parameter controls + meters

---

## Dark Mode Design

**Color Palette:**
- Background: `#0a0a0a` (near black)
- Surface: `#1a1a1a` (dark gray)
- Primary: `#3b82f6` (blue for active elements)
- Success: `#10b981` (green for running agents)
- Warning: `#f59e0b` (amber for warnings)
- Error: `#ef4444` (red for errors)
- Text: `#f3f4f6` (light gray)
- Text secondary: `#9ca3af` (medium gray)

**Accessibility:**
- WCAG AA contrast ratios
- Focus indicators on all interactive elements
- Keyboard navigation support
- Screen reader labels

---

## Future Enhancements

### Phase 2 Features
- Multi-user collaboration (multiple performers)
- Session recording and playback
- Integrated sample browser
- Visual theme customization
- Plugin marketplace integration

### Phase 3 Features (Fan Engagement)
- Public performance view (read-only)
- Audience voting interface
- Tip trigger overlays
- Social media clip export
- Leaderboard display

---

## Development Workflow

1. **Component Development** - Build in isolation with Storybook (optional)
2. **State Management** - Use React Context for global state
3. **API Integration** - Mock API responses during development
4. **Testing** - Jest + React Testing Library
5. **Build** - `npm run build` creates production bundle
6. **Deployment** - Serve from FastAPI static files or CDN

---

## Browser Compatibility

**Minimum Requirements:**
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

**Required APIs:**
- WebSocket
- Canvas API
- Web Audio API (for waveform visualization)
- LocalStorage (for preset caching)

---

**This architecture provides a professional, real-time control interface for Live Performance Agents, suitable for both studio and live performance environments.**
