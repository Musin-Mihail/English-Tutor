from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.core.config import settings
from app.services.base_grader import BaseGraderAgent
from app.services.grader_factory import create_grader_agent


@lru_cache
def get_settings():
    return settings


_grader_agent_instance: BaseGraderAgent | None = None


def get_grader_agent() -> BaseGraderAgent:
    global _grader_agent_instance
    if _grader_agent_instance is None:
        _grader_agent_instance = create_grader_agent()
    return _grader_agent_instance


AgentDep = Annotated[BaseGraderAgent, Depends(get_grader_agent)]
