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
    "main_topic": "ТОЧНОЕ название темы из таблицы",
    "correct_variant": "Правильный английский перевод",
    "alternatives": ["Вариант 2"],
    "score": 6,
    "errors": [{"type": "Грамматика", "explanation": "..."}],
    "recommendation": "...",
    "new_vocabulary": ["word - перевод"]
}

ПРАВИЛА ЗАПОЛНЕНИЯ ПРИ ПРОВЕРКЕ:
1. main_topic (Тема):
   - Ты ОБЯЗАН выбрать тему СТРОГО из заголовков "Context Table" (например: "Времена Past (Simple vs. Cont. vs. Perf.)").
   - ПРИОРИТЕТ: Если в предложении есть глагол в прошедшем времени, ГЛАВНАЯ тема — это "Времена Past...", а не "Предлоги" или "Артикли". Грамматика важнее лексики!
   - Копируй название темы буква в букву (включая скобки).

2. new_vocabulary (Словарь):
   - Включай сюда ТОЛЬКО слова из поля "correct_variant" (твоего правильного перевода).
   - ЗАПРЕЩЕНО добавлять слова с опечатками из ответа студента (например, если студент написал "yestudey", НЕ добавляй это).
   - Формат: "english_word - русский перевод".

3. CRITICAL RULE (ЯЗЫК):     
- Если ответ студента (Student Answer) написан на РУССКОМ языке (кириллицей), 
    ты ОБЯЗАН поставить "score": 0 и вернуть ошибку "Не переведено".
- Даже если смысл правильный, но язык русский — оценка 0.

РЕЖИМ 2: ГЕНЕРАЦИЯ ЗАДАНИЯ (Action: GENERATE_TASK)
Твоя задача — придумать ОДНО НОВОЕ предложение НА РУССКОМ ЯЗЫКЕ.

АЛГОРИТМ ВЫБОРА ТЕМЫ:
1. Найди в Context Table темы, где "Все оценки" пусты или "Средний балл" равен 0.0.
2. СГЕНЕРИРУЙ задание именно на эту тему, чтобы заполнить пробелы.
3. Пример: Если "Времена Past" пустые — дай предложение "Вчера я ходил в кино".

ЗАПРЕЩЕНО: Давать задания в духе "Составь предложение...".
ЗАПРЕЩЕНО: Повторять предыдущее задание.
НУЖНО: Просто дать русское предложение.

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
        text = text.strip()
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            return match.group(1)
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            return match.group(1)
        return text

    def _ensure_schema(self, data: Dict) -> Dict:
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
        
        CONTEXT TABLE HEADERS (Use one of these EXACTLY):
        - Артикли (a/an, the)
        - Предлоги (in, on, at, for)
        - Времена Present (Simple vs. Cont.)
        - Времена Past (Simple vs. Cont. vs. Perf.)
        - Неправильные глаголы
        - Порядок слов в предложении
        - Модальные глаголы
        - Условные предложения (Conditionals)
        - Фразовые глаголы
        - Косвенная речь (Reported Speech)
        
        FULL CONTEXT TABLE:
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
            return self._ensure_schema(parsed_response)
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
        except Exception:
            pass
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
                return "Вчера я ходил в магазин."
            return task
        except Exception as e:
            print(f"!!! [NEXT] ERROR generating task: {e}")
            return "Вчера я играл в футбол."
