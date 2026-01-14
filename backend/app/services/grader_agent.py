import json
import os
import google.generativeai as genai
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from app.core.config import settings

# Configure the API Key
if settings.GOOGLE_API_KEY:
    genai.configure(api_key=settings.GOOGLE_API_KEY)


# 1. Define the Pydantic model for validation
class GraderResult(BaseModel):
    main_topic: str = Field(
        description="The main grammatical topic from the performance table"
    )
    correct_variant: str = Field(description="The corrected version of the translation")
    alternatives: list[str] = Field(
        description="List of alternative correct translations"
    )
    score: int = Field(description="Score from 0 to 10")
    errors: list[Dict[str, str]] = Field(
        description="List of errors. Each error has 'type' and 'explanation'"
    )
    recommendation: str = Field(description="Recommendation for what to study next")


# 2. Integrate your Master Prompt (Combined with JSON instructions)
MASTER_PROMPT_TEXT = """
You are an experienced English teacher specializing in helping Russian-speaking students. 
Your task is to check my translations, grade them, find errors, and help me learn by adapting to my performance history.

INPUT DATA:
I will provide you with:
1. The Task (Russian original).
2. My Translation (English).
3. Context: My Performance Table (topics I struggle with).
4. Context: My Learning Journal (previous errors).

ALGORITHM:
1. Analyze the input. Compare my translation with the original.
2. Provide feedback in a STRICT JSON format.

JSON RESPONSE FORMAT:
You must respond with a raw JSON object (no markdown formatting like ```json ... ```) matching this structure:
{
    "main_topic": "Specific topic from the provided Performance Table (e.g., 'Articles (a/an, the)')",
    "correct_variant": "The best correct translation",
    "alternatives": ["Other valid option 1", "Other valid option 2"],
    "score": 0, // Integer 0-10
    "errors": [
        {
            "type": "Grammar/Lexis/Style",
            "explanation": "Concise explanation of the error."
        }
    ],
    "recommendation": "Specific advice based on the errors made."
}

TONE:
Friendly and supportive, but strict regarding rules. Help me think like a native speaker.
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

        # Construct the user message injecting the specific context files
        user_message = f"""
        --- CURRENT TASK ---
        **Task (Russian):** "{original_task}"
        **Student Answer (English):** "{student_translation}"
        
        --- CONTEXT: PERFORMANCE TABLE ---
        {context_table if context_table else "No data provided."}
        
        --- CONTEXT: LEARNING JOURNAL ---
        {context_journal if context_journal else "No data provided."}
        
        Analyze the answer and return the JSON result.
        """

        try:
            # Call Gemini
            response = await self.model.generate_content_async(user_message)

            # Parse JSON
            result_json = json.loads(response.text)

            # Validate with Pydantic
            validated_result = GraderResult(**result_json)

            return validated_result.model_dump()

        except Exception as e:
            # Fallback for errors
            print(f"AI Error: {e}")
            return {
                "main_topic": "System Error",
                "correct_variant": "Error processing request",
                "alternatives": [],
                "score": 0,
                "errors": [{"type": "System", "explanation": str(e)}],
                "recommendation": "Please check backend logs.",
            }
