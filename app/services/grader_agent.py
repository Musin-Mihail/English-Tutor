"""Backward-compatible entry point for grader agents."""

from app.services.base_grader import BaseGraderAgent
from app.services.cursor_grader import CursorGraderAgent
from app.services.gemini_grader import GeminiGraderAgent
from app.services.grader_factory import create_grader_agent

__all__ = [
    "BaseGraderAgent",
    "CursorGraderAgent",
    "GeminiGraderAgent",
    "create_grader_agent",
]

# Legacy alias: GraderAgent() still works via factory.
GraderAgent = create_grader_agent
