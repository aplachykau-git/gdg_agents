"""
GDG Agentic Workspace - Agents Package
Exposes all sub-agents and the main coordinating Root Agent.
"""

import warnings

# Suppress upstream Google ADK BaseAgentConfig deprecation warning
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message=r".*BaseAgentConfig is deprecated.*",
)

from .agenda_generator.agent import agenda_agent
from .event_planner.agent import planner_agent
from .linkedin_post_generator.agent import linkedin_agent
from .office_secretary.agent import office_agent
from .receipt_scanner.agent import receipt_agent
from .registration_manager.agent import registration_agent
from .root_agent.agent import root_agent
from .video_editor.agent import video_editor_agent as video_agent

__all__ = [
    "root_agent",
    "receipt_agent",
    "video_agent",
    "linkedin_agent",
    "registration_agent",
    "planner_agent",
    "agenda_agent",
    "office_agent",
]
