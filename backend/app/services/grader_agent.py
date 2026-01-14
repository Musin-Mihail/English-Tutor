import json
import os
import google.generativeai as genai
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from app.core.config import settings

if settings.GOOGLE_API_KEY:
    genai.configure(api_key=settings.GOOGLE_API_KEY)


class GraderResult(BaseModel):
    main_topic: str = Field(
        description="Тема из таблицы успеваемости (в точности как в заголовке)"
    )
    correct_variant: str = Field(description="Правильный перевод")
    alternatives: list[str] = Field(description="Альтернативные варианты")
    score: int = Field(description="Оценка от 0 до 10")
    errors: list[Dict[str, str]] = Field(description="Список ошибок")
    recommendation: str = Field(description="Рекомендация")
    new_vocabulary: list[str] = Field(
        description="Список 3-5 полезных английских слов из этого перевода для запоминания"
    )


MASTER_PROMPT_TEXT = """
Ты — AI-репетитор английского. Твоя задача — проверять переводы и генерировать задания.
ТВОЙ ЯЗЫК ОТВЕТОВ — СТРОГО РУССКИЙ.

ВАЖНО: При проверке учитывай "Текущий уровень" студента из контекста. Не требуй знаний уровня C1, если студент A1.

ФОРМАТ ОТВЕТА (JSON):
РЕЖИМ 1: ПРОВЕРКА
{
    "main_topic": "Тема (копируй точное название заголовка из таблицы, например 'Артикли (a/an, the)')",
    "correct_variant": "Текст",
    "alternatives": ["Вариант"],
    "score": 8,
    "errors": [{"type": "...", "explanation": "..."}],
    "recommendation": "...",
    "new_vocabulary": ["word1", "word2 - перевод"]
}

РЕЖИМ 2: ГЕНЕРАЦИЯ ЗАДАНИЯ
Проанализируй таблицу. Найди темы с низким баллом или малым количеством оценок.
Учитывай список "Активный словарный запас" — старайся использовать изученные слова + 1-2 новых.
Верни JSON:
{
    "next_task": "Предложение на русском языке..."
}
"""


class GraderAgent:
    def __init__(
        self, model_name: str = "gemini-3-flash-preview"
    ):  # ЗАПРЕЩЕНО менять модель
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
        --- ЗАДАНИЕ ---
        Original: "{original_task}"
        Student: "{student_translation}"
        
        --- КОНТЕКСТ УСПЕВАЕМОСТИ И УРОВНЯ ---
        {context_table}
        
        --- ИСТОРИЯ ОШИБОК ---
        {context_journal}
        """
        try:
            response = await self.model.generate_content_async(user_message)
            parsed_response = json.loads(response.text)

            if isinstance(parsed_response, list):
                if len(parsed_response) > 0:
                    return parsed_response[0]
                else:
                    return {}

            return parsed_response
        except Exception as e:
            return {
                "score": 0,
                "errors": [{"type": "Error", "explanation": str(e)}],
                "main_topic": "General",
                "correct_variant": "Error",
                "alternatives": [],
                "recommendation": "Try again",
                "new_vocabulary": [],
            }

    async def generate_new_task(
        self,
        context_table: Optional[str] = "",
        context_journal: Optional[str] = "",
    ) -> str:
        user_message = f"""
        Действие: GENERATE_TASK
        Контекст:
        {context_table}
        {context_journal}
        """
        try:
            response = await self.model.generate_content_async(user_message)
            data = json.loads(response.text)
            return data.get("next_task", "Переведи: У меня есть кот.")
        except:
            return "Переведи: У меня есть собака."
