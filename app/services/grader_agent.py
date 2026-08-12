import json
import re
import os
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from app.core.config import settings
from google import genai
from google.genai import types


class SentenceFeedback(BaseModel):
    sentence_number: int = Field(description="Номер предложения")
    student_transcription: str = Field(
        description="То, что сказал студент (распознанный текст)"
    )
    correct_variant: str = Field(description="Правильный перевод")
    alternatives: list[str] = Field(description="Альтернативы")
    errors: list[Dict[str, str]] = Field(description="Список ошибок")


class GraderResult(BaseModel):
    main_topic: str = Field(description="Тема из таблицы")
    score: int = Field(description="Оценка")
    sentences_feedback: list[SentenceFeedback] = Field(
        description="Фидбек по каждому предложению"
    )
    recommendation: str = Field(description="Рекомендация")


MASTER_PROMPT_TEXT = """
Ты — AI-репетитор.
Твоя роль — строго помогать с ПЕРЕВОДОМ.
ТВОЙ ЯЗЫК ОТВЕТОВ — СТРОГО РУССКИЙ.
ФОРМАТ ОТВЕТА (JSON):
Ты ОБЯЗАН вернуть ТОЛЬКО чистый JSON объект. 
Не используй markdown форматирование.

РЕЖИМ 1: ПРОВЕРКА (Когда переданы аудиофайлы Student Answer)
Студент произнес перевод предложений в прикрепленных аудиофайлах. 
Распознай текст каждого аудио, проверь правильность перевода и оцени произношение.
{
    "main_topic": "ТОЧНОЕ название темы из таблицы",
    "score": 6,
    "sentences_feedback": [
        {
            "sentence_number": 1,
            "student_transcription": "Распознанный текст из 1-го аудио, что сказал студент",
            "correct_variant": "Правильный английский перевод 1-го предложения",
            "alternatives": ["Альтернативный вариант перевода"],
            "errors": [{"type": "Грамматика", "explanation": "..."}]
        }
    ],
    "recommendation": "Общая рекомендация..."
}

ПРАВИЛА ЗАПОЛНЕНИЯ ПРИ ПРОВЕРКЕ:
1. main_topic (Тема):
   - Ты ОБЯЗАН выбрать тему СТРОГО из заголовков "Context Table".
   - ПРИОРИТЕТ: Грамматика важнее лексики!
2. sentences_feedback (Построчный анализ):
   - Сделай анализ ДЛЯ КАЖДОГО предложения отдельно (массив объектов от 1 до 5).
   - Обязательно напиши, что услышал от студента (`student_transcription`), чтобы он видел, правильно ли его поняли.
   - Укажи ошибки произношения в массиве errors, если они есть.
3. CRITICAL RULE (ЯЗЫК И АУДИО):     
   - Если ответ на русском языке или аудио пустые -> "score": 0.

РЕЖИМ 2: ГЕНЕРАЦИЯ ЗАДАНИЯ (Action: GENERATE_TASK)
Твоя задача — придумать 5 НОВЫХ предложений НА РУССКОМ ЯЗЫКЕ.
Найди в Context Table темы, где "Средний балл" самый низкий.
Каждое предложение выводи с новой строки (1., 2. и т.д.).
Верни JSON:
{
    "next_task": "Текст предложения на русском..."
}
"""


class GraderAgent:
    def __init__(self, model_name: str = "gemini-3-flash-preview"):
        print(f"--- INIT MODEL (New SDK): {model_name} ---")
        self.model_name = model_name
        self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)

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
            "score": data.get("score", 0),
            "sentences_feedback": data.get("sentences_feedback", []),
            "recommendation": data.get("recommendation", ""),
        }

    async def grade_translation(
        self,
        audio_paths: list[str],
        original_task: str,
        context_table: Optional[str] = "",
        context_journal: Optional[str] = "",
    ) -> Dict[str, Any]:
        user_message = f"""
        {MASTER_PROMPT_TEXT}
        --- РЕЖИМ: ПРОВЕРКА ---
        Original Task (Russian): "{original_task}"
        
        CONTEXT TABLE:
        {context_table}
        """
        contents_list = [user_message]
        try:
            for path in audio_paths:
                if os.path.exists(path):
                    uploaded_file = self.client.files.upload(file=path)
                    contents_list.append(uploaded_file)

            print(f"\n[CHECK] Sending request to AI ({self.model_name})...")
            response = await self.client.aio.models.generate_content(
                model=self.model_name, contents=contents_list
            )
            raw_text = response.text
            print(f"[CHECK] Raw AI Response: {raw_text}")
            clean_text = self._clean_json_response(raw_text)
            parsed_response = json.loads(clean_text)
            if isinstance(parsed_response, list):
                parsed_response = parsed_response[0] if parsed_response else {}

            input_tokens = (
                response.usage_metadata.prompt_token_count
                if response.usage_metadata
                else 0
            )
            output_tokens = (
                response.usage_metadata.candidates_token_count
                if response.usage_metadata
                else 0
            )

            return {
                "result": self._ensure_schema(parsed_response),
                "tokens": {"input": input_tokens, "output": output_tokens},
            }
        except Exception as e:
            print(f"!!! [CHECK] ERROR: {e}")
            return {
                "result": {
                    "score": 0,
                    "main_topic": "General",
                    "sentences_feedback": [
                        {
                            "sentence_number": 1,
                            "student_transcription": "",
                            "correct_variant": "Error processing answer",
                            "alternatives": [],
                            "errors": [{"type": "System Error", "explanation": str(e)}],
                        }
                    ],
                    "recommendation": "Try again later",
                },
                "tokens": {"input": 0, "output": 0},
            }

    async def generate_new_task(
        self,
        context_table: Optional[str] = "",
        context_journal: Optional[str] = "",
    ) -> Dict[str, Any]:
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
            print(f"\n[NEXT] Sending request to AI ({self.model_name}) for new task...")
            response = await self.client.aio.models.generate_content(
                model=self.model_name, contents=user_message
            )
            raw_text = response.text
            print(f"[NEXT] Raw AI Response: {raw_text}")
            clean_text = self._clean_json_response(raw_text)
            data = json.loads(clean_text)
            task = data.get("next_task", "Переведи: У меня есть кот.")
            if forbidden_task and task.strip() == forbidden_task:
                task = "Вчера я ходил в магазин."

            input_tokens = (
                response.usage_metadata.prompt_token_count
                if response.usage_metadata
                else 0
            )
            output_tokens = (
                response.usage_metadata.candidates_token_count
                if response.usage_metadata
                else 0
            )

            return {
                "result": task,
                "tokens": {"input": input_tokens, "output": output_tokens},
            }
        except Exception as e:
            print(f"!!! [NEXT] ERROR generating task: {e}")
            return {
                "result": "Вчера я играл в футбол.",
                "tokens": {"input": 0, "output": 0},
            }
