from app.core.config import settings
from app.services.base_grader import BaseGraderAgent
from app.services.cursor_grader import CursorGraderAgent
from app.services.gemini_grader import GeminiGraderAgent


def create_grader_agent() -> BaseGraderAgent:
    provider = settings.AI_PROVIDER.lower()
    if provider == "gemini":
        return GeminiGraderAgent(model_name=settings.GEMINI_MODEL)
    if provider == "cursor":
        return CursorGraderAgent(model_name=settings.CURSOR_MODEL)
    raise ValueError(
        f"Unknown AI_PROVIDER: {settings.AI_PROVIDER!r}. Use 'cursor' or 'gemini'."
    )
