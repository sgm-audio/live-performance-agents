"""
Agent registry for lifecycle management
"""

import threading
from typing import Dict, Optional, List
import logging

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Registry for managing agent lifecycle

    Implements singleton pattern for centralized agent management.
    Handles registration, startup, and shutdown of all agents.

    Usage:
        registry = AgentRegistry()
        registry.register(my_agent)
        registry.start_all()
        # ... application runs ...
        registry.stop_all()
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern - only one registry instance"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Prevent re-initialization
        if hasattr(self, '_initialized'):
            return

        self._initialized = True

        # Agents: agent_id -> BaseAgent
        self.agents: Dict[str, BaseAgent] = {}
        self.agents_lock = threading.Lock()

        # Track startup order for proper shutdown
        self.startup_order: List[str] = []

        logger.info("Agent registry initialized")

    def register(self, agent: BaseAgent):
        """
        Register an agent

        Args:
            agent: Agent instance to register

        Raises:
            ValueError: If agent with same ID already registered
        """
        with self.agents_lock:
            if agent.agent_id in self.agents:
                raise ValueError(
                    f"Agent with ID '{agent.agent_id}' already registered"
                )

            self.agents[agent.agent_id] = agent

        logger.info(f"Registered agent: {agent.agent_name} ({agent.agent_id})")

    def unregister(self, agent_id: str):
        """
        Unregister an agent

        Args:
            agent_id: ID of agent to unregister
        """
        with self.agents_lock:
            agent = self.agents.pop(agent_id, None)

            # Remove from startup order
            if agent_id in self.startup_order:
                self.startup_order.remove(agent_id)

        if agent:
            logger.info(f"Unregistered agent: {agent.agent_name} ({agent.agent_id})")
        else:
            logger.warning(f"Agent not found for unregister: {agent_id}")

    def get(self, agent_id: str) -> Optional[BaseAgent]:
        """
        Get an agent by ID

        Args:
            agent_id: Agent identifier

        Returns:
            Agent instance or None if not found
        """
        with self.agents_lock:
            return self.agents.get(agent_id)

    def get_all(self) -> List[BaseAgent]:
        """
        Get all registered agents

        Returns:
            List of all agent instances
        """
        with self.agents_lock:
            return list(self.agents.values())

    def start_all(self):
        """
        Setup all registered agents

        Calls setup() on each agent in registration order.
        Tracks startup order for proper shutdown sequence.
        """
        with self.agents_lock:
            agents = list(self.agents.values())

        for agent in agents:
            try:
                agent.setup()
                self.startup_order.append(agent.agent_id)
                logger.info(f"Started agent: {agent.agent_name}")
            except Exception as e:
                logger.error(f"Error starting agent {agent.agent_name}: {e}")
                # Continue starting other agents

    def stop_all(self):
        """
        Teardown all registered agents

        Calls teardown() on each agent in reverse startup order
        to ensure proper cleanup dependencies.
        """
        # Shutdown in reverse order
        for agent_id in reversed(self.startup_order):
            agent = self.agents.get(agent_id)
            if not agent:
                continue

            try:
                agent.teardown()
                logger.info(f"Stopped agent: {agent.agent_name}")
            except Exception as e:
                logger.error(f"Error stopping agent {agent.agent_name}: {e}")

        self.startup_order.clear()

    def get_stats(self) -> Dict:
        """
        Get registry statistics

        Returns:
            Dictionary with agent counts and status
        """
        with self.agents_lock:
            return {
                'total_agents': len(self.agents),
                'running_agents': len(self.startup_order),
                'agent_ids': list(self.agents.keys())
            }

    def __repr__(self) -> str:
        with self.agents_lock:
            return (f"AgentRegistry(total={len(self.agents)}, "
                   f"running={len(self.startup_order)})")
