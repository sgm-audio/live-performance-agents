"""
Backend API Server for Live Performance Agents

FastAPI-based REST and WebSocket API for web frontend communication.
"""

from .api_server import app, get_web_agent

__all__ = ['app', 'get_web_agent']
