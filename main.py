"""
Live Performance Agents - Main Entry Point

Starts the complete agent system including the web interface.
"""

import time
import logging
import signal
import sys
import threading
from typing import Optional

from core import MessageBus, AgentRegistry
from agents import (
    RealtimeAudioIOAgent,
    LiveEffectsChainAgent,
    MIDIControlAgent,
    LiveLoopingAgent,
    PerformanceAutomationAgent,
    SynchronizationClockAgent,
    VisualLightingControlAgent,
    LiveMixingDynamicsAgent,
    PerformanceMonitoringAgent,
    BackupRedundancyAgent,
    IndustryStandardsAgent,
    WebInterfaceAgent,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global shutdown_requested
    logger.info("Shutdown signal received")
    shutdown_requested = True


def start_api_server_thread(web_agent: WebInterfaceAgent):
    """Start FastAPI server in background thread"""
    import uvicorn
    from backend.api_server import app, set_web_agent

    # Set the global web agent instance
    set_web_agent(web_agent)

    logger.info("Starting FastAPI server on http://0.0.0.0:8080")

    # Run uvicorn in this thread
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info",
        access_log=False  # Reduce noise
    )
    server = uvicorn.Server(config)
    server.run()


def main():
    """Main entry point"""
    global shutdown_requested

    logger.info("=" * 60)
    logger.info("Live Performance Agents System")
    logger.info("Version 0.1.0")
    logger.info("=" * 60)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize MessageBus and AgentRegistry
    message_bus = MessageBus()
    registry = AgentRegistry()

    # Create all agents
    logger.info("Creating agents...")

    # Core audio agents
    audio_io = RealtimeAudioIOAgent()
    effects_chain = LiveEffectsChainAgent()
    midi_control = MIDIControlAgent()

    # Performance agents
    looping = LiveLoopingAgent()
    automation = PerformanceAutomationAgent()
    sync_clock = SynchronizationClockAgent()

    # Visual and mixing
    visual_lighting = VisualLightingControlAgent()
    mixing_dynamics = LiveMixingDynamicsAgent()

    # System agents
    performance_monitor = PerformanceMonitoringAgent()
    backup_redundancy = BackupRedundancyAgent()
    industry_standards = IndustryStandardsAgent()

    # Web interface agent
    web_interface = WebInterfaceAgent()

    # Register all agents
    logger.info("Registering agents...")
    registry.register(audio_io)
    registry.register(effects_chain)
    registry.register(midi_control)
    registry.register(looping)
    registry.register(automation)
    registry.register(sync_clock)
    registry.register(visual_lighting)
    registry.register(mixing_dynamics)
    registry.register(performance_monitor)
    registry.register(backup_redundancy)
    registry.register(industry_standards)
    registry.register(web_interface)

    try:
        # Start all agents
        logger.info("Starting all agents...")
        registry.start_all()

        # Start API server in background thread
        api_thread = threading.Thread(
            target=start_api_server_thread,
            args=(web_interface,),
            name="FastAPI_Server",
            daemon=True
        )
        api_thread.start()

        logger.info("=" * 60)
        logger.info("System is running!")
        logger.info("Web interface: http://localhost:8080")
        logger.info("API docs: http://localhost:8080/docs")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 60)

        # Main loop - keep running until shutdown
        while not shutdown_requested:
            time.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        # Cleanup
        logger.info("Shutting down...")
        registry.stop_all()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
