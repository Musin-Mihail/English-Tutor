from fastapi import APIRouter, HTTPException
from app.models.domain import TranslationRequest, CheckResponse, TaskResponse
from app.services.grader_agent import GraderAgent
from app.services.file_manager import FileManager

router = APIRouter()
agent = GraderAgent()
file_manager = FileManager()


@router.post("/check", response_model=CheckResponse)
async def check_translation(request: TranslationRequest):
    table_content, journal_content = file_manager.get_context()

    result = await agent.grade_translation(
        student_translation=request.student_translation,
        original_task=request.original_task,
        context_table=table_content,
        context_journal=journal_content,
    )

    should_save = True

    if result.get("correct_variant") == "Error processing answer":
        should_save = False

    if result.get("errors"):
        for err in result.get("errors"):
            err_type = err.get("type", "").lower()
            if "error" in err_type or "system" in err_type:
                should_save = False
                break

    if result.get("score") == 0 and result.get("main_topic") == "General":
        if "Error" in result.get("correct_variant", ""):
            should_save = False

    if should_save:
        try:
            file_manager.update_journal(
                task=request.original_task,
                student_ans=request.student_translation,
                ai_result=result,
            )
            file_manager.update_performance_table(ai_result=result)
        except Exception as e:
            print(f"Ошибка записи файлов: {e}")
    else:
        print(
            "!!! ОБНАРУЖЕНА ОШИБКА AI. Запись в журнал отменена, чтобы не портить историю."
        )

    return CheckResponse(result=result)


@router.get("/next", response_model=TaskResponse)
async def get_next_task():
    try:
        table_content, journal_content = file_manager.get_context()

        task_text = await agent.generate_new_task(
            context_table=table_content, context_journal=journal_content
        )
        return TaskResponse(task_text=task_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
