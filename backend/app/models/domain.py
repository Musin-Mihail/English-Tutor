from pydantic import BaseModel


class TranslationRequest(BaseModel):
    student_translation: str
    original_task: str
    # Контекст пока можно сделать опциональным
    context_table: str = ""
    context_journal: str = ""


class CheckResponse(BaseModel):
    result: dict  # Сюда положим JSON, который вернет Gemini
