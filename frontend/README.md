# Live Performance Agents - Frontend

Real-time web-based control panel for the Live Performance Agents system.

## Features

- **Real-time Dashboard** - Monitor all agent status and system metrics
- **Audio Level Metering** - Visual audio input/output levels with peak detection
- **Agent Status Grid** - See health of all 12 agents at a glance
- **Sync Status** - Tempo, beat position, and playback state
- **Performance Monitoring** - CPU usage, latency, and system health
- **WebSocket Communication** - Bidirectional real-time updates

## Technology Stack

- **React 18** - UI framework
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Utility-first styling
- **WebSocket** - Real-time communication
- **Canvas API** - Audio visualization
- **React Query** - Server state management (future)

## Setup

### Prerequisites

- Node.js 18+ and npm
- Backend API server running on `http://localhost:8080`

### Installation

```bash
cd frontend
npm install
```

### Development

Start the dev server:

```bash
npm run dev
```

The app will be available at `http://localhost:5173`

### Build for Production

```bash
npm run build
```

Output will be in `dist/` directory.

## Project Structure

```
frontend/
├── public/              # Static assets
├── src/
│   ├── components/      # React components
│   │   ├── Dashboard/   # Dashboard components
│   │   ├── Header.jsx   # App header
│   │   └── Sidebar.jsx  # Navigation sidebar
│   ├── context/         # React context providers
│   │   └── AgentContext.jsx  # Agent state management
│   ├── hooks/           # Custom React hooks
│   │   └── useWebSocket.js   # WebSocket hook
│   ├── App.jsx          # Main app component
│   ├── main.jsx         # Entry point
│   └── index.css        # Global styles
├── index.html           # HTML template
├── package.json         # Dependencies
├── vite.config.js       # Vite configuration
├── tailwind.config.js   # Tailwind configuration
└── postcss.config.js    # PostCSS configuration
```

## Components

### Dashboard

- **AgentStatusGrid** - Grid showing status of all agents
- **AudioMeters** - Real-time audio level visualization
- **SyncStatus** - Tempo and sync information
- **PerformanceMonitor** - System performance metrics

### Context

- **AgentContext** - Provides agent state and commands to all components
  - `agents` - Status of all agents
  - `audioLevels` - Real-time audio levels
  - `midiMessages` - Recent MIDI messages
  - `syncStatus` - Tempo and playback state
  - Command functions for controlling the system

### Hooks

- **useWebSocket** - WebSocket connection with automatic reconnection
  - Handles connection lifecycle
  - Provides `sendCommand()` for sending commands
  - Delivers incoming messages to callback

## WebSocket Protocol

### Connection

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');
```

### Message Format

**Incoming (Backend → Frontend):**

```json
{
  "type": "agent_status" | "audio_levels" | "midi_message" | "sync_update",
  "timestamp": 1234567890.123,
  "data": { ... }
}
```

**Outgoing (Frontend → Backend):**

```json
{
  "command": "effect.parameter.set",
  "data": {
    "effect_id": "reverb_1",
    "parameter": "mix",
    "value": 0.5
  }
}
```

## Available Commands

### Effect Control

```javascript
setEffectParameter('reverb_1', 'mix', 0.5);
```

### MIDI Mapping

```javascript
createMidiMapping('midi_in_0', 7, 'effects_chain', 'reverb_1.mix', 0.0, 1.0);
deleteMidiMapping('mapping_123');
```

### Loop Control

```javascript
startLoopRecording('loop_1', true); // true = quantize
stopLoopRecording('loop_1');
playLoop('loop_1');
stopLoop('loop_1');
```

### Preset Management

```javascript
loadPreset('preset_123');
savePreset('My Preset', 'Custom effect chain');
```

### Automation

```javascript
startAutomation('automation_123');
stopAutomation();
```

## Styling

### Custom Tailwind Classes

- **Colors:**
  - `app-bg` - Background (#0a0a0a)
  - `app-surface` - Surface (#1a1a1a)
  - `app-primary` - Primary blue (#3b82f6)
  - `app-success` - Success green (#10b981)
  - `app-warning` - Warning amber (#f59e0b)
  - `app-error` - Error red (#ef4444)
  - `app-text` - Text (#f3f4f6)
  - `app-text-secondary` - Secondary text (#9ca3af)

- **Components:**
  - `btn`, `btn-primary`, `btn-success`, `btn-danger`, `btn-secondary`
  - `card`, `card-header`
  - `input`
  - `slider`

### Custom Fonts

- **Sans:** Inter (body text)
- **Mono:** JetBrains Mono (code/numbers)

## Performance

- **Real-time Updates:**
  - Audio levels: 30 Hz (33ms)
  - Agent status: 10 Hz (100ms)
  - MIDI messages: Real-time (no throttling)

- **Optimizations:**
  - React.memo() for expensive components
  - Canvas rendering with RequestAnimationFrame
  - Debounced parameter updates

## Browser Compatibility

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

**Required APIs:**
- WebSocket
- Canvas API
- LocalStorage

## Development

### Hot Module Replacement

Vite provides instant HMR - changes appear immediately without full page reload.

### Linting

```bash
npm run lint
```

### Preview Production Build

```bash
npm run build
npm run preview
```

## Future Features

- [ ] Effects chain visual editor (React Flow)
- [ ] MIDI controller mapping interface
- [ ] Loop waveform visualization
- [ ] Automation timeline editor
- [ ] Preset browser with search
- [ ] Multi-user collaboration
- [ ] Mobile responsive design

## Troubleshooting

### WebSocket Connection Issues

1. Ensure backend server is running on `http://localhost:8080`
2. Check browser console for connection errors
3. Verify CORS is enabled in backend
4. Check firewall settings

### Build Errors

1. Delete `node_modules/` and run `npm install` again
2. Clear Vite cache: `rm -rf node_modules/.vite`
3. Ensure Node.js version is 18+

### Performance Issues

1. Check browser DevTools Performance tab
2. Reduce update frequencies in AgentContext
3. Enable React DevTools Profiler
4. Check for memory leaks in WebSocket handlers

## Contributing

Follow the established code style:
- Use functional components with hooks
- Prefer composition over inheritance
- Keep components small and focused
- Use Tailwind utility classes
- Add comments for complex logic

## License

MIT
