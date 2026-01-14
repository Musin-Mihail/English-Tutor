from pydantic import BaseModel


class TranslationRequest(BaseModel):
    student_translation: str
    original_task: str
    context_table: str = ""
    context_journal: str = ""


class TaskGenerationRequest(BaseModel):
    context_table: str = ""
    context_journal: str = ""


class CheckResponse(BaseModel):
    result: dict


class TaskResponse(BaseModel):
    task_text: str
