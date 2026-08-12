from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class BaseGraderAgent(Protocol):
    async def grade_translation(
        self,
        audio_paths: list[str],
        original_task: str,
        context_table: Optional[str] = "",
        context_journal: Optional[str] = "",
    ) -> Dict[str, Any]: ...

    async def generate_new_task(
        self,
        context_table: Optional[str] = "",
        context_journal: Optional[str] = "",
    ) -> Dict[str, Any]: ...
