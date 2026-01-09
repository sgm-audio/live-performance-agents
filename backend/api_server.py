"""
FastAPI Backend Server for Live Performance Agents

Provides REST API and WebSocket endpoints for web frontend communication.
"""

import asyncio
import json
import uuid
import logging
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agents import WebInterfaceAgent

logger = logging.getLogger(__name__)

# Global WebInterfaceAgent instance
web_agent: Optional[WebInterfaceAgent] = None


# ============================================================================
# Application Lifecycle
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global web_agent

    # Startup
    logger.info("Starting FastAPI backend server")
    # Note: WebInterfaceAgent should be started by the main agent system
    # This API server just provides the HTTP/WebSocket interface

    yield

    # Shutdown
    logger.info("Shutting down FastAPI backend server")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Live Performance Agents API",
    description="Real-time control API for Live Performance Agents system",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite and CRA defaults
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Pydantic Models
# ============================================================================

class CommandRequest(BaseModel):
    """Command request from frontend"""
    command: str
    data: Dict[str, Any] = {}


class CommandResponse(BaseModel):
    """Command response to frontend"""
    type: str
    command: Optional[str] = None
    success: bool = True
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class AgentStatus(BaseModel):
    """Agent status information"""
    agent_id: str
    agent_name: str
    status: str
    cpu_usage: Optional[float] = None
    warnings: List[str] = []


class PresetInfo(BaseModel):
    """Preset information"""
    preset_id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None


# ============================================================================
# Helper Functions
# ============================================================================

def get_web_agent() -> WebInterfaceAgent:
    """Get the global WebInterfaceAgent instance"""
    global web_agent
    if web_agent is None:
        raise HTTPException(status_code=503, detail="Web agent not initialized")
    return web_agent


def set_web_agent(agent: WebInterfaceAgent):
    """Set the global WebInterfaceAgent instance"""
    global web_agent
    web_agent = agent


# ============================================================================
# WebSocket Endpoint
# ============================================================================

class ConnectionManager:
    """Manages active WebSocket connections"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket) -> str:
        """Accept new connection and return client ID"""
        await websocket.accept()
        client_id = str(uuid.uuid4())
        self.active_connections[client_id] = websocket

        # Register with WebInterfaceAgent
        agent = get_web_agent()
        agent.register_client(client_id, websocket)

        logger.info(f"WebSocket client connected: {client_id}")
        return client_id

    async def disconnect(self, client_id: str):
        """Disconnect client"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]

            # Unregister from WebInterfaceAgent
            try:
                agent = get_web_agent()
                agent.unregister_client(client_id)
            except:
                pass

            logger.info(f"WebSocket client disconnected: {client_id}")

    async def send_message(self, client_id: str, message: dict):
        """Send message to specific client"""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            await websocket.send_json(message)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to {client_id}: {e}")


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time bidirectional communication

    Receives commands from frontend and sends updates from agents.
    """
    client_id = await manager.connect(websocket)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()

            try:
                message = json.loads(data)

                # Process command via WebInterfaceAgent
                agent = get_web_agent()
                response = agent.receive_command(client_id, message)

                # Send response
                await websocket.send_json(response)

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "error": "Invalid JSON"
                })
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                await websocket.send_json({
                    "type": "error",
                    "error": str(e)
                })

    except WebSocketDisconnect:
        await manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        await manager.disconnect(client_id)


# ============================================================================
# REST API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Live Performance Agents API",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    try:
        agent = get_web_agent()
        stats = agent.get_stats()
        return {
            "status": "healthy",
            "clients_connected": stats.get("clients_connected", 0),
            "uptime": "unknown"  # TODO: Track uptime
        }
    except:
        return {
            "status": "unhealthy",
            "error": "Web agent not initialized"
        }


@app.get("/api/stats")
async def get_stats():
    """Get web interface statistics"""
    agent = get_web_agent()
    return agent.get_stats()


@app.get("/api/clients")
async def get_clients():
    """Get list of connected clients"""
    agent = get_web_agent()
    return agent.get_connected_clients()


# ============================================================================
# Agent Management Endpoints
# ============================================================================

@app.get("/api/agents", response_model=List[AgentStatus])
async def get_agents():
    """
    Get status of all agents

    Returns:
        List of agent status information
    """
    # TODO: This would require integration with AgentRegistry
    # For now, return placeholder
    return [
        {
            "agent_id": "audio_io",
            "agent_name": "Realtime Audio I/O Agent",
            "status": "running",
            "cpu_usage": 8.5,
            "warnings": []
        },
        {
            "agent_id": "effects_chain",
            "agent_name": "Live Effects Chain Agent",
            "status": "running",
            "cpu_usage": 12.3,
            "warnings": []
        },
        {
            "agent_id": "midi_control",
            "agent_name": "MIDI Control Agent",
            "status": "running",
            "cpu_usage": 3.2,
            "warnings": []
        }
    ]


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str):
    """
    Get status of specific agent

    Args:
        agent_id: Agent identifier

    Returns:
        Agent status information
    """
    # TODO: Implement agent status retrieval
    raise HTTPException(status_code=501, detail="Not implemented")


# ============================================================================
# Effect Management Endpoints
# ============================================================================

@app.post("/api/effects/{effect_id}/parameters")
async def set_effect_parameter(effect_id: str, request: CommandRequest):
    """
    Set effect parameter

    Args:
        effect_id: Effect identifier
        request: Parameter update request

    Returns:
        Command response
    """
    agent = get_web_agent()

    command_data = {
        "command": "effect.parameter.set",
        "data": {
            "effect_id": effect_id,
            **request.data
        }
    }

    response = agent.receive_command("api_request", command_data)
    return CommandResponse(**response)


@app.get("/api/effects")
async def get_effects():
    """Get list of active effects"""
    # TODO: Implement effects list retrieval
    return []


# ============================================================================
# MIDI Management Endpoints
# ============================================================================

@app.get("/api/midi/devices")
async def get_midi_devices():
    """Get list of MIDI devices"""
    # TODO: Implement MIDI device list retrieval
    return []


@app.post("/api/midi/mappings")
async def create_midi_mapping(request: CommandRequest):
    """Create MIDI CC mapping"""
    agent = get_web_agent()

    command_data = {
        "command": "midi.mapping.create",
        "data": request.data
    }

    response = agent.receive_command("api_request", command_data)
    return CommandResponse(**response)


@app.delete("/api/midi/mappings/{mapping_id}")
async def delete_midi_mapping(mapping_id: str):
    """Delete MIDI mapping"""
    agent = get_web_agent()

    command_data = {
        "command": "midi.mapping.delete",
        "data": {"mapping_id": mapping_id}
    }

    response = agent.receive_command("api_request", command_data)
    return CommandResponse(**response)


# ============================================================================
# Loop Management Endpoints
# ============================================================================

@app.post("/api/loops/{loop_id}/record/start")
async def start_loop_recording(loop_id: str, request: CommandRequest):
    """Start loop recording"""
    agent = get_web_agent()

    command_data = {
        "command": "loop.record.start",
        "data": {
            "loop_id": loop_id,
            **request.data
        }
    }

    response = agent.receive_command("api_request", command_data)
    return CommandResponse(**response)


@app.post("/api/loops/{loop_id}/record/stop")
async def stop_loop_recording(loop_id: str):
    """Stop loop recording"""
    agent = get_web_agent()

    command_data = {
        "command": "loop.record.stop",
        "data": {"loop_id": loop_id}
    }

    response = agent.receive_command("api_request", command_data)
    return CommandResponse(**response)


@app.post("/api/loops/{loop_id}/play")
async def play_loop(loop_id: str):
    """Play loop"""
    agent = get_web_agent()

    command_data = {
        "command": "loop.play",
        "data": {"loop_id": loop_id}
    }

    response = agent.receive_command("api_request", command_data)
    return CommandResponse(**response)


@app.post("/api/loops/{loop_id}/stop")
async def stop_loop(loop_id: str):
    """Stop loop"""
    agent = get_web_agent()

    command_data = {
        "command": "loop.stop",
        "data": {"loop_id": loop_id}
    }

    response = agent.receive_command("api_request", command_data)
    return CommandResponse(**response)


# ============================================================================
# Preset Management Endpoints
# ============================================================================

@app.get("/api/presets", response_model=List[PresetInfo])
async def get_presets():
    """Get list of available presets"""
    # TODO: Implement preset list retrieval
    return []


@app.post("/api/presets/{preset_id}/load")
async def load_preset(preset_id: str):
    """Load preset"""
    agent = get_web_agent()

    command_data = {
        "command": "preset.load",
        "data": {"preset_id": preset_id}
    }

    response = agent.receive_command("api_request", command_data)
    return CommandResponse(**response)


@app.post("/api/presets")
async def save_preset(request: CommandRequest):
    """Save new preset"""
    agent = get_web_agent()

    command_data = {
        "command": "preset.save",
        "data": request.data
    }

    response = agent.receive_command("api_request", command_data)
    return CommandResponse(**response)


# ============================================================================
# Automation Endpoints
# ============================================================================

@app.post("/api/automation/start")
async def start_automation(request: CommandRequest):
    """Start automation playback"""
    agent = get_web_agent()

    command_data = {
        "command": "automation.start",
        "data": request.data
    }

    response = agent.receive_command("api_request", command_data)
    return CommandResponse(**response)


@app.post("/api/automation/stop")
async def stop_automation():
    """Stop automation playback"""
    agent = get_web_agent()

    command_data = {
        "command": "automation.stop",
        "data": {}
    }

    response = agent.receive_command("api_request", command_data)
    return CommandResponse(**response)


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )


# ============================================================================
# Main Entry Point (for development)
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run server
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )
