# Contributing to Live Performance Agents

Thank you for your interest in contributing to the Live Performance Agents project! This document provides guidelines and instructions for developers joining the team.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing Guidelines](#testing-guidelines)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [Areas for Contribution](#areas-for-contribution)

## Getting Started

### Prerequisites

**Backend (Python):**
- Python 3.9 or higher
- Virtual environment tool (venv or conda)
- Audio hardware (soundcard, MIDI controller - optional)

**Frontend (React):**
- Node.js 18+ and npm
- Modern browser (Chrome 90+, Firefox 88+, Safari 14+, Edge 90+)

### Development Setup

#### 1. Clone the Repository

```bash
git clone https://github.com/SGM-Studios/live-performance-agents.git
cd live-performance-agents
```

#### 2. Backend Setup

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Verify installation
python examples/basic_setup.py
```

#### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
# Frontend runs at http://localhost:5173
```

#### 4. Run the Full System

```bash
# Terminal 1 - Backend (from project root)
python main.py
# Backend runs at http://localhost:8080

# Terminal 2 - Frontend
cd frontend
npm run dev
# Frontend runs at http://localhost:5173
```

## Project Structure

```
live-performance-agents/
├── core/                      # Core framework (message bus, base classes)
│   ├── message_bus.py         # Priority-based pub/sub system
│   ├── base_agent.py          # Abstract base class for agents
│   ├── agent_registry.py      # Agent lifecycle management
│   ├── message.py             # Message dataclass
│   └── topics.py              # Topic constants
├── agents/                    # 12 specialized agents
│   ├── realtime_audio_io_agent.py
│   ├── live_effects_chain_agent.py
│   ├── midi_control_agent.py
│   ├── live_looping_agent.py
│   ├── synchronization_clock_agent.py
│   ├── performance_automation_agent.py
│   ├── performance_monitoring_agent.py
│   ├── backup_redundancy_agent.py
│   ├── industry_standards_agent.py
│   ├── visual_lighting_control_agent.py
│   ├── live_mixing_dynamics_agent.py
│   ├── web_interface_agent.py
│   ├── effects_processors.py  # 15 DSP effects
│   └── loop_processors.py     # Time-stretch/pitch-shift
├── backend/                   # FastAPI server
│   └── api_server.py          # REST/WebSocket endpoints
├── frontend/                  # React web interface
│   ├── src/
│   │   ├── components/        # React components
│   │   ├── context/           # Context providers
│   │   └── hooks/             # Custom hooks
│   └── package.json           # Node dependencies
├── examples/                  # Usage examples
├── docs/                      # Documentation
├── main.py                    # Main entry point
└── CLAUDE.md                  # Architecture guidelines
```

## Development Workflow

### 1. Pick a Task

Check the project board or issues for available tasks:
- Frontend features (Effects UI, MIDI mapping, Loop controls)
- Backend improvements (agent enhancements, new effects)
- Documentation updates
- Bug fixes

### 2. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b bugfix/issue-description
```

Branch naming conventions:
- `feature/` - New features
- `bugfix/` - Bug fixes
- `refactor/` - Code refactoring
- `docs/` - Documentation updates
- `test/` - Test additions/improvements

### 3. Make Changes

Follow the code standards below and test your changes thoroughly.

### 4. Commit Your Changes

```bash
git add .
git commit -m "Your descriptive commit message"
```

See [Commit Messages](#commit-messages) for formatting guidelines.

### 5. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## Code Standards

### Python Backend

**Formatting:**
```bash
# Format code with Black (line length 100)
black . --line-length 100

# Lint with flake8
flake8 core/ agents/ backend/

# Type checking with mypy
mypy core/ agents/
```

**Agent Patterns:**

All agents MUST follow these patterns:

1. **Thread Safety:**
```python
# Always create locks for shared state
self.config_lock = threading.Lock()
self.buffer_lock = threading.Lock()

# Always use context managers
with self.config_lock:
    self.config.sample_rate = new_rate
```

2. **Worker Thread Pattern:**
```python
def _start_worker_thread(self):
    self.worker_active = True
    self.worker_thread = threading.Thread(
        target=self._worker,
        name=f"{self.agent_id}_worker",
        daemon=True
    )
    self.worker_thread.start()

def _stop_worker_thread(self):
    self.worker_active = False
    if self.worker_thread:
        self.worker_thread.join(timeout=2.0)

def _worker(self):
    while self.worker_active:  # NOT while True:
        try:
            # Work here
            time.sleep(interval)
        except Exception as e:
            logger.error(f"Error: {e}")
```

3. **Message Handling:**
```python
def handle_message(self, message: Message):
    try:
        if message.topic == "topic.one":
            self._handle_one(message)
    except Exception as e:
        self.log("ERROR", f"Error: {e}", {"topic": message.topic})
```

4. **Dataclass Pattern:**
```python
from dataclasses import dataclass, field

@dataclass
class Config:
    name: str
    enabled: bool = True
    # ALWAYS use field(default_factory=...) for mutable types
    items: List[str] = field(default_factory=list)
    # NEVER: items: List[str] = []  # Wrong!
```

**Real-Time Constraints:**
- Audio processing MUST complete within buffer time
- No logging in audio callbacks
- No blocking operations in callbacks
- Minimal lock contention
- Pre-allocate buffers

### JavaScript/React Frontend

**Formatting:**
```bash
cd frontend
npm run lint
```

**Component Standards:**
- Use functional components with hooks
- Prop validation with PropTypes or TypeScript
- Memoize expensive calculations with `useMemo`
- Memoize callbacks with `useCallback`
- Use `React.memo` for pure components

**File Structure:**
```jsx
// ComponentName.jsx
import React, { useState, useEffect } from 'react';

const ComponentName = ({ prop1, prop2 }) => {
  const [state, setState] = useState(initialValue);

  useEffect(() => {
    // Side effects
  }, [dependencies]);

  return (
    <div className="component-name">
      {/* JSX */}
    </div>
  );
};

export default ComponentName;
```

## Testing Guidelines

### Python Tests (Coming Soon)

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=core --cov=agents

# Run specific test
pytest tests/test_core/test_message_bus.py::test_priority_queue
```

**Test Structure:**
```python
import pytest
from core.message_bus import MessageBus

def test_message_publishing():
    bus = MessageBus()
    received = []

    def handler(msg):
        received.append(msg)

    bus.subscribe("test.topic", handler)
    bus.publish("test.topic", {"data": "value"})

    assert len(received) == 1
    assert received[0].payload["data"] == "value"
```

### Frontend Tests (Coming Soon)

```bash
cd frontend
npm test
```

## Commit Messages

Follow the conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding/updating tests
- `chore`: Build process, dependencies, etc.

**Examples:**

```
feat(frontend): add effects chain visual editor

- Implemented ReactFlow-based effects chain editor
- Added drag-and-drop effect ordering
- Integrated with WebSocket for real-time updates

Closes #42
```

```
fix(agents): resolve audio buffer underrun in RealtimeAudioIOAgent

- Increased buffer size to 256 samples
- Added buffer monitoring and alerts
- Improved thread priority for audio callback

Fixes #38
```

## Pull Request Process

1. **Update Documentation**: Ensure README, CLAUDE.md, or other docs are updated if needed
2. **Test Your Changes**: Run tests and verify functionality
3. **Format Code**: Run formatters (Black for Python, ESLint for JS)
4. **Write Clear PR Description**:
   - What does this PR do?
   - Why is it needed?
   - How was it tested?
   - Screenshots (for UI changes)
5. **Link Related Issues**: Use "Closes #issue-number" in PR description
6. **Request Review**: Tag team members for review
7. **Address Feedback**: Respond to review comments and make requested changes
8. **Squash Commits**: If requested, squash commits before merge

**PR Template:**

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How were these changes tested?

## Screenshots (if applicable)
Add screenshots for UI changes

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests added/updated
- [ ] All tests passing
```

## Areas for Contribution

### High Priority

**Frontend (4-6 weeks of work):**
- [ ] Effects Chain Visual Editor (ReactFlow integration)
- [ ] MIDI Mapping UI with MIDI Learn mode
- [ ] Loop Waveform Visualization (Web Audio API + Canvas)
- [ ] Automation Timeline Editor
- [ ] Preset Browser with search/tags
- [ ] Mobile-responsive design improvements

**Backend (2-3 weeks):**
- [ ] Complete Visual/Lighting Agent (pyartnet integration)
- [ ] Finish Live Mixing Dynamics Agent (auto-ducking, sidechain)
- [ ] Add comprehensive unit tests (pytest)
- [ ] Performance profiling and optimization
- [ ] Error handling improvements

**Documentation:**
- [ ] API reference documentation
- [ ] Video tutorials
- [ ] Architecture diagrams
- [ ] Performance benchmarking guide

### Medium Priority

**AI/ML Integration:**
- [ ] Integrate smolagents framework
- [ ] Add Hugging Face model inference
- [ ] Voice control via Pipecat
- [ ] ML-based audio analysis

**DevOps:**
- [ ] Docker containerization
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Automated testing
- [ ] Deployment scripts

### Low Priority

**Enhancements:**
- [ ] Additional DSP effects
- [ ] Plugin system for custom agents
- [ ] Cloud synchronization
- [ ] Multi-user collaboration features

## Getting Help

- **Documentation**: Check CLAUDE.md for architecture details
- **Issues**: Search existing issues or create a new one
- **Discussions**: Use GitHub Discussions for questions
- **Email**: Contact scottmills306@gmail.com

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what's best for the project
- Show empathy towards other contributors

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to Live Performance Agents! 🎵🤖
