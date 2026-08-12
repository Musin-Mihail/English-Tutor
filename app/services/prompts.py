import json
import re
from typing import Any, Dict

MASTER_PROMPT_TEXT = """
Ты — AI-репетитор.
Твоя роль — строго помогать с ПЕРЕВОДОМ.
ТВОЙ ЯЗЫК ОТВЕТОВ — СТРОГО РУССКИЙ.
ФОРМАТ ОТВЕТА (JSON):
Ты ОБЯЗАН вернуть ТОЛЬКО чистый JSON объект. 
Не используй markdown форматирование.

РЕЖИМ 1: ПРОВЕРКА (Когда переданы аудиофайлы или распознанный текст Student Answer)
Студент произнес перевод предложений. 
Распознай/используй текст каждого ответа, проверь правильность перевода и оцени произношение (если возможно).
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


def clean_json_response(text: str) -> str:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        return match.group(1)
    return text


def ensure_grader_schema(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "main_topic": data.get("main_topic", "General"),
        "score": data.get("score", 0),
        "sentences_feedback": data.get("sentences_feedback", []),
        "recommendation": data.get("recommendation", ""),
    }


def parse_json_response(raw_text: str) -> Dict[str, Any]:
    clean_text = clean_json_response(raw_text)
    parsed = json.loads(clean_text)
    if isinstance(parsed, list):
        return parsed[0] if parsed else {}
    return parsed


def error_grader_result(exc: Exception) -> Dict[str, Any]:
    return {
        "score": 0,
        "main_topic": "General",
        "sentences_feedback": [
            {
                "sentence_number": 1,
                "student_transcription": "",
                "correct_variant": "Error processing answer",
                "alternatives": [],
                "errors": [{"type": "System Error", "explanation": str(exc)}],
            }
        ],
        "recommendation": "Try again later",
    }
