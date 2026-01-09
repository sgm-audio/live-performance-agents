"""
Backwards-compatible setup.py for Live Performance Agents

Modern installation uses pyproject.toml, but this file provides
compatibility with older tools and editable installs.
"""

from setuptools import setup, find_packages

# Read dependencies from requirements.txt
with open('requirements.txt') as f:
    requirements = [line.strip() for line in f
                   if line.strip() and not line.startswith('#')]

setup(
    name="live-performance-agents",
    version="0.1.0",
    packages=find_packages(include=['core', 'core.*', 'agents', 'agents.*']),
    install_requires=requirements,
    python_requires='>=3.9',
)
