import asyncio
import re
from typing import Any, Dict, Optional

from cursor_sdk import (
    AgentOptions,
    AsyncAgent,
    AsyncClient,
    CursorAgentError,
    LocalAgentOptions,
)

from app.core.config import settings
from app.paths import PROJECT_ROOT
from app.services.asr import LocalTranscriber
from app.services.prompts import (
    MASTER_PROMPT_TEXT,
    ensure_grader_schema,
    error_grader_result,
    parse_json_response,
)


class CursorGraderAgent:
    """Провайдер на Cursor SDK (локальный агент) + Whisper ASR на GPU."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.CURSOR_MODEL
        self.transcriber = LocalTranscriber()
        self._client: Any = None
        self._client_cm: Any = None
        self._client_loop: asyncio.AbstractEventLoop | None = None
        self._lock: asyncio.Lock | None = None
        print(
            f"--- INIT Cursor provider (local): model={self.model_name}, "
            f"cwd={PROJECT_ROOT} ---"
        )

    def _agent_options(self) -> AgentOptions:
        return AgentOptions(
            api_key=settings.CURSOR_API_KEY,
            model=self.model_name,
            local=LocalAgentOptions(cwd=str(PROJECT_ROOT)),
        )

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def _close_client(self) -> None:
        if self._client_cm is not None:
            try:
                await self._client_cm.__aexit__(None, None, None)
            except Exception as e:
                print(f"[Cursor] Warning while closing bridge: {e}")
        self._client = None
        self._client_cm = None
        self._client_loop = None

    async def _get_client(self):
        loop = asyncio.get_running_loop()
        async with self._get_lock():
            if self._client is not None and self._client_loop is loop:
                return self._client

            await self._close_client()
            self._client_cm = await AsyncClient.launch_bridge(
                workspace=str(PROJECT_ROOT)
            )
            self._client = await self._client_cm.__aenter__()
            self._client_loop = loop
            print("--- Cursor AsyncClient bridge ready ---")
            return self._client

    async def _prompt(self, message: str) -> tuple[str, Dict[str, int]]:
        client = await self._get_client()
        try:
            result = await AsyncAgent.prompt(
                message,
                self._agent_options(),
                client=client,
            )
        except CursorAgentError as e:
            # Bridge мог отвалиться — сбросим и пробросим понятную ошибку
            await self._close_client()
            raise RuntimeError(f"Cursor startup failed: {e.message}") from e

        if result.status == "error":
            raise RuntimeError(f"Cursor agent run failed: {result.result}")

        raw_text = result.result or ""
        tokens = {"input": 0, "output": 0}
        if result.usage is not None:
            tokens = {
                "input": result.usage.input_tokens,
                "output": result.usage.output_tokens,
            }
        return raw_text, tokens

    async def grade_translation(
        self,
        audio_paths: list[str],
        original_task: str,
        context_table: Optional[str] = "",
        context_journal: Optional[str] = "",
    ) -> Dict[str, Any]:
        try:
            transcriptions = await asyncio.to_thread(
                self.transcriber.transcribe_files, audio_paths
            )
            transcription_block = "\n".join(
                f'Предложение {i + 1}: "{text}"'
                for i, text in enumerate(transcriptions)
            )

            user_message = f"""
            {MASTER_PROMPT_TEXT}
            --- РЕЖИМ: ПРОВЕРКА ---
            Original Task (Russian): "{original_task}"

            РАСПОЗНАННЫЕ ОТВЕТЫ СТУДЕНТА (локальный Whisper на GPU):
            {transcription_block}

            Используй эти распознанные тексты как student_transcription для каждого предложения.
            Если распознавание пустое — считай, что студент не ответил.

            CONTEXT TABLE:
            {context_table}
            """

            print(f"\n[CHECK/Cursor] Sending request ({self.model_name})...")
            raw_text, tokens = await self._prompt(user_message)
            print(f"[CHECK/Cursor] Raw response: {raw_text}")
            parsed_response = parse_json_response(raw_text)

            return {
                "result": ensure_grader_schema(parsed_response),
                "tokens": tokens,
            }
        except Exception as e:
            print(f"!!! [CHECK/Cursor] ERROR: {e}")
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
            print(f"\n[NEXT/Cursor] Sending request ({self.model_name})...")
            raw_text, tokens = await self._prompt(user_message)
            print(f"[NEXT/Cursor] Raw response: {raw_text}")
            data = parse_json_response(raw_text)
            task = data.get("next_task", "Переведи: У меня есть кот.")
            if forbidden_task and task.strip() == forbidden_task:
                task = "Вчера я ходил в магазин."

            return {
                "result": task,
                "tokens": tokens,
            }
        except Exception as e:
            print(f"!!! [NEXT/Cursor] ERROR: {e}")
            return {
                "result": "Вчера я играл в футбол.",
                "tokens": {"input": 0, "output": 0},
            }
