from functools import lru_cache
from typing import Generator, Annotated
from fastapi import Depends
from app.services.grader_agent import GraderAgent
from app.core.config import settings


@lru_cache
def get_settings():
    return settings


_grader_agent_instance = None


def get_grader_agent() -> GraderAgent:
    global _grader_agent_instance
    if _grader_agent_instance is None:
        _grader_agent_instance = GraderAgent(model_name="gemma-3-27b-it")
    return _grader_agent_instance


AgentDep = Annotated[GraderAgent, Depends(get_grader_agent)]
