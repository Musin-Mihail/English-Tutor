import json
import re
import os
import google.generativeai as genai
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from app.core.config import settings

if settings.GOOGLE_API_KEY:
    genai.configure(api_key=settings.GOOGLE_API_KEY)


class GraderResult(BaseModel):
    main_topic: str = Field(description="Тема из таблицы")
    correct_variant: str = Field(description="Правильный перевод")
    alternatives: list[str] = Field(description="Альтернативы")
    score: int = Field(description="Оценка")
    errors: list[Dict[str, str]] = Field(description="Список ошибок")
    recommendation: str = Field(description="Рекомендация")
    new_vocabulary: list[str] = Field(description="Новые слова")


MASTER_PROMPT_TEXT = """
Ты — AI-репетитор. Твоя роль — строго помогать с ПЕРЕВОДОМ.
ТВОЙ ЯЗЫК ОТВЕТОВ — СТРОГО РУССКИЙ.

ФОРМАТ ОТВЕТА (JSON):
Ты ОБЯЗАН вернуть ТОЛЬКО чистый JSON объект. 
Не используй markdown форматирование.

РЕЖИМ 1: ПРОВЕРКА (Когда есть Student Answer)
{
    "main_topic": "Тема из таблицы (ОБЯЗАТЕЛЬНО выбирай тему, к которой относится грамматика предложения)",
    "correct_variant": "Английский перевод",
    "alternatives": ["Вариант 2"],
    "score": 8,
    "errors": [{"type": "Грамматика", "explanation": "..."}],
    "recommendation": "...",
    "new_vocabulary": ["word1", "word2 - перевод"]
}

РЕЖИМ 2: ГЕНЕРАЦИЯ ЗАДАНИЯ (Action: GENERATE_TASK)
Твоя задача — придумать ОДНО НОВОЕ предложение НА РУССКОМ ЯЗЫКЕ.

АЛГОРИТМ ВЫБОРА ТЕМЫ (СТРОГО):
1. Посмотри в Context Table.
2. Найди темы, где "Все оценки" пусты или "Средний балл" равен 0.0 (например: Past Simple, Future, Conditionals).
3. ПРИОРИТЕТ: Если есть темы с 0 оценок — СГЕНЕРИРУЙ ЗАДАНИЕ ПО НИМ. Не зацикливайся на Present Simple.
4. Если все темы начаты, выбирай ту, где самый низкий балл.

ЗАПРЕЩЕНО: Давать задания в духе "Составь предложение...".
ЗАПРЕЩЕНО: Повторять то же самое предложение, что и в прошлый раз.
НУЖНО: Просто дать русское предложение.

Пример для темы Past Simple: "Вчера я ходил в парк."
Пример для темы Future Simple: "Завтра мы пойдем в кино."

Верни JSON:
{
    "next_task": "Текст предложения на русском..."
}
"""


class GraderAgent:
    def __init__(self, model_name: str = "gemma-3-27b-it"):
        print(f"--- INIT MODEL: {model_name} ---")
        self.model = genai.GenerativeModel(model_name=model_name)

    def _clean_json_response(self, text: str) -> str:
        """Мощная очистка JSON от Markdown и лишнего текста"""
        text = text.strip()

        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return match.group(1)

        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            return match.group(1)

        return text

    def _ensure_schema(self, data: Dict) -> Dict:
        """Гарантирует, что все поля есть"""
        return {
            "main_topic": data.get("main_topic", "General"),
            "correct_variant": data.get("correct_variant", ""),
            "alternatives": data.get("alternatives", []),
            "score": data.get("score", 0),
            "errors": data.get("errors", []),
            "recommendation": data.get("recommendation", ""),
            "new_vocabulary": data.get("new_vocabulary", []),
        }

    async def grade_translation(
        self,
        student_translation: str,
        original_task: str,
        context_table: Optional[str] = "",
        context_journal: Optional[str] = "",
    ) -> Dict[str, Any]:

        user_message = f"""
        {MASTER_PROMPT_TEXT}

        --- РЕЖИМ: ПРОВЕРКА ---
        Original Task (Russian): "{original_task}"
        Student Answer (English): "{student_translation}"
        
        CONTEXT TABLE:
        {context_table}
        """
        try:
            print(f"\n[CHECK] Sending request to AI...")
            response = await self.model.generate_content_async(user_message)
            raw_text = response.text
            print(f"[CHECK] Raw AI Response: {raw_text}")

            clean_text = self._clean_json_response(raw_text)
            parsed_response = json.loads(clean_text)

            if isinstance(parsed_response, list):
                parsed_response = parsed_response[0] if parsed_response else {}

            final_data = self._ensure_schema(parsed_response)
            return final_data

        except Exception as e:
            print(f"!!! [CHECK] ERROR: {e}")
            return {
                "score": 0,
                "errors": [{"type": "System Error", "explanation": str(e)}],
                "main_topic": "General",
                "correct_variant": "Error processing answer",
                "alternatives": [],
                "recommendation": "Try again later",
                "new_vocabulary": [],
            }

    async def generate_new_task(
        self,
        context_table: Optional[str] = "",
        context_journal: Optional[str] = "",
    ) -> str:

        forbidden_task = ""
        try:
            matches = re.findall(
                r"\*\*Задание \(Русский\):\*\*\s*\n(.*?)\n", context_journal, re.DOTALL
            )
            if matches:
                forbidden_task = matches[-1].strip()
                print(f"[ANTILOOP] Forbidden task identified: '{forbidden_task}'")
        except Exception as e:
            print(f"[ANTILOOP] Error extracting last task: {e}")

        anti_repeat_instruction = ""
        if forbidden_task:
            anti_repeat_instruction = f"""
            CRITICAL RULE: DO NOT GENERATE THE PHRASE: "{forbidden_task}". 
            You MUST generate a DIFFERENT sentence.
            """

        user_message = f"""
        {MASTER_PROMPT_TEXT}

        --- РЕЖИМ: ГЕНЕРАЦИЯ ЗАДАНИЯ ---
        ACTION: GENERATE_TASK
        
        {anti_repeat_instruction}

        CONTEXT TABLE:
        {context_table}
        
        CONTEXT JOURNAL (History):
        {context_journal}
        """
        try:
            print(f"\n[NEXT] Sending request to AI for new task...")
            response = await self.model.generate_content_async(user_message)
            raw_text = response.text
            print(f"[NEXT] Raw AI Response: {raw_text}")

            clean_text = self._clean_json_response(raw_text)
            data = json.loads(clean_text)

            task = data.get("next_task", "Переведи: У меня есть кот.")

            if forbidden_task and task.strip() == forbidden_task:
                print(
                    "!!! AI repeated the task despite instructions. Retrying logic..."
                )
                return "Вчера я видел большую собаку."

            return task

        except Exception as e:
            print(f"!!! [NEXT] ERROR generating task: {e}")
            return "Вчера я ходил в парк."
