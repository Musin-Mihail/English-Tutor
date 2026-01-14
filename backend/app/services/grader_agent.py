import json
import os
import google.generativeai as genai
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from app.core.config import settings

if settings.GOOGLE_API_KEY:
    genai.configure(api_key=settings.GOOGLE_API_KEY)


class GraderResult(BaseModel):
    main_topic: str = Field(description="Тема из таблицы успеваемости")
    correct_variant: str = Field(description="Правильный перевод")
    alternatives: list[str] = Field(description="Альтернативные варианты")
    score: int = Field(description="Оценка от 0 до 10")
    errors: list[Dict[str, str]] = Field(
        description="Список ошибок с типом и объяснением на русском"
    )
    recommendation: str = Field(description="Рекомендация что повторить")


MASTER_PROMPT_TEXT = """
Ты — опытный преподаватель английского языка для русскоязычных студентов.
Твоя задача — проверять переводы и создавать новые задания.
ТВОЙ ЯЗЫК ОТВЕТОВ — СТРОГО РУССКИЙ (Russian).

ФОРМАТ ОТВЕТА (JSON):
Ты всегда должен отвечать только валидным JSON объектом.

РЕЖИМ 1: ПРОВЕРКА (Когда дано "Student Answer")
{
    "main_topic": "Название темы из таблицы (например: 'Артикли')",
    "correct_variant": "Исправленный английский текст",
    "alternatives": ["Вариант 1", "Вариант 2"],
    "score": 0, // Целое число 0-10
    "errors": [
        {
            "type": "Грамматика/Лексика",
            "explanation": "Объяснение ошибки на русском языке."
        }
    ],
    "recommendation": "Совет на русском языке."
}

РЕЖИМ 2: ГЕНЕРАЦИЯ (Когда просят "GENERATE_TASK")
В ответ верни JSON:
{
    "next_task": "Предложение на русском языке для перевода, основанное на слабых местах студента."
}
"""


class GraderAgent:
    def __init__(self, model_name: str = "gemini-3-flash-preview"):
        self.model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=MASTER_PROMPT_TEXT,
            generation_config={"response_mime_type": "application/json"},
        )

    async def grade_translation(
        self,
        student_translation: str,
        original_task: str,
        context_table: Optional[str] = "",
        context_journal: Optional[str] = "",
    ) -> Dict[str, Any]:

        user_message = f"""
        --- РЕЖИМ ПРОВЕРКИ ---
        **Задание (Русский):** "{original_task}"
        **Ответ студента (English):** "{student_translation}"
        
        --- КОНТЕКСТ: УСПЕВАЕМОСТЬ ---
        {context_table}
        
        --- КОНТЕКСТ: ЖУРНАЛ ---
        {context_journal}
        
        Проверь перевод и верни JSON.
        """
        try:
            response = await self.model.generate_content_async(user_message)
            return json.loads(response.text)
        except Exception as e:
            return {"score": 0, "errors": [{"type": "Error", "explanation": str(e)}]}

    async def generate_new_task(
        self,
        context_table: Optional[str] = "",
        context_journal: Optional[str] = "",
    ) -> str:

        user_message = f"""
        --- РЕЖИМ ГЕНЕРАЦИИ ---
        Действие: GENERATE_TASK
        
        Проанализируй успеваемость студента:
        {context_table}
        
        И его прошлые ошибки:
        {context_journal}
        
        Придумай ОДНО предложение на русском языке для перевода на английский.
        Оно должно тренировать самую слабую тему студента.
        Верни JSON: {{"next_task": "..."}}
        """

        try:
            response = await self.model.generate_content_async(user_message)
            data = json.loads(response.text)
            return data.get("next_task", "Ошибка генерации задания.")
        except Exception as e:
            print(f"Error generating task: {e}")
            return "Переведи: У меня есть кот."
