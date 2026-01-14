import os
from fastapi import APIRouter, HTTPException
from app.models.domain import TranslationRequest, CheckResponse
from app.services.grader_agent import GraderAgent

router = APIRouter()
agent = GraderAgent()


# Helper to read files safely
def load_context_file(filename: str) -> str:
    # Adjust path to where you put the .md files
    file_path = os.path.join("data", filename)
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


@router.post("/check", response_model=CheckResponse)
async def check_translation(request: TranslationRequest):
    try:
        # 1. Load context from local files
        table_content = load_context_file("ENGLISH_performance_table.md")
        journal_content = load_context_file("ENGLISH_training_journal.md")

        # 2. Call the agent with the loaded context
        result = await agent.grade_translation(
            student_translation=request.student_translation,
            original_task=request.original_task,
            context_table=table_content,
            context_journal=journal_content,
        )
        return CheckResponse(result=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
