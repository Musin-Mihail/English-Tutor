import os
import re
from typing import Any, Dict, Optional

from google import genai

from app.core.config import settings
from app.services.prompts import (
    MASTER_PROMPT_TEXT,
    ensure_grader_schema,
    error_grader_result,
    parse_json_response,
)


class GeminiGraderAgent:
    def __init__(self, model_name: str = "gemini-3-flash-preview"):
        print(f"--- INIT Gemini provider: {model_name} ---")
        self.model_name = model_name
        self.client = genai.Client(api_key=settings.GOOGLE_API_KEY)

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

            print(f"\n[CHECK/Gemini] Sending request ({self.model_name})...")
            response = await self.client.aio.models.generate_content(
                model=self.model_name, contents=contents_list
            )
            raw_text = response.text
            print(f"[CHECK/Gemini] Raw response: {raw_text}")
            parsed_response = parse_json_response(raw_text)

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
                "result": ensure_grader_schema(parsed_response),
                "tokens": {"input": input_tokens, "output": output_tokens},
            }
        except Exception as e:
            print(f"!!! [CHECK/Gemini] ERROR: {e}")
            return {
                "result": error_grader_result(e),
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
            print(f"\n[NEXT/Gemini] Sending request ({self.model_name})...")
            response = await self.client.aio.models.generate_content(
                model=self.model_name, contents=user_message
            )
            raw_text = response.text
            print(f"[NEXT/Gemini] Raw response: {raw_text}")
            data = parse_json_response(raw_text)
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
            print(f"!!! [NEXT/Gemini] ERROR: {e}")
            return {
                "result": "Вчера я играл в футбол.",
                "tokens": {"input": 0, "output": 0},
            }
