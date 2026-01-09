"""
Basic Setup Example

Demonstrates how to initialize the Live Performance Agents system
with a minimal set of agents for audio processing.
"""

import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from core import MessageBus, AgentRegistry, Priority
from agents import (
    RealtimeAudioIOAgent,
    LiveEffectsChainAgent,
    SynchronizationClockAgent
)


def main():
    """Basic system setup with audio I/O, effects, and sync"""

    print("=" * 60)
    print("Live Performance Agents - Basic Setup Example")
    print("=" * 60)

    # Initialize message bus
    print("\n[1] Starting message bus...")
    bus = MessageBus()
    bus.start()

    # Create agent registry
    print("[2] Creating agent registry...")
    registry = AgentRegistry()

    # Register agents
    print("[3] Registering agents...")

    # Audio I/O agent
    audio_agent = RealtimeAudioIOAgent()
    registry.register(audio_agent)
    print(f"    - {audio_agent.agent_name}")

    # Effects chain agent
    effects_agent = LiveEffectsChainAgent()
    registry.register(effects_agent)
    print(f"    - {effects_agent.agent_name}")

    # Synchronization agent
    sync_agent = SynchronizationClockAgent()
    registry.register(sync_agent)
    print(f"    - {sync_agent.agent_name}")

    # Start all agents
    print("\n[4] Starting all agents...")
    registry.start_all()

    # Let the system run
    print("\n[5] System running. Agents are now active.")
    print("    Message bus stats:", bus.get_stats())
    print("    Registry stats:", registry.get_stats())

    print("\n[6] Running for 5 seconds...")
    time.sleep(5)

    # Cleanup
    print("\n[7] Shutting down...")
    registry.stop_all()
    bus.stop()

    print("\n[8] Shutdown complete!")
    print("    Final message bus stats:", bus.get_stats())

    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
