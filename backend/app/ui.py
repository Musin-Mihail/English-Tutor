import gradio as gr
from app.services.grader_agent import GraderAgent
from app.data.database import DatabaseManager

agent = GraderAgent()
db = DatabaseManager()


async def init_task():
    table_context, journal_context = db.get_context()
    task_text = await agent.generate_new_task(table_context, journal_context)
    task_id = db.add_task(task_text)
    return task_text, task_id


async def process_submission(
    task_id, task_text, audio1, audio2, audio3, audio4, audio5
):
    audios = [a for a in [audio1, audio2, audio3, audio4, audio5] if a is not None]
    if not audios:
        return (
            "⚠️ Пожалуйста, запишите хотя бы один аудиофайл.",
            gr.update(),
            gr.update(),
            audio1,
            audio2,
            audio3,
            audio4,
            audio5,
        )

    table_context, journal_context = db.get_context()
    result = await agent.grade_translation(
        audios, task_text, table_context, journal_context
    )

    score = result.get("score", 0)
    topic = result.get("main_topic", "General")
    vocab = result.get("new_vocabulary", [])

    db.add_journal_entry(task_id, audios, result, score)
    db.update_performance(topic, score, vocab)

    # Форматируем обратную связь
    feedback = f"### Оценка: {score}/10\n"
    feedback += f"**Тема:** {topic}\n\n"
    feedback += f"**Правильный вариант:**\n{result.get('correct_variant', '')}\n\n"
    if result.get("errors"):
        feedback += "**Ошибки:**\n"
        for err in result.get("errors", []):
            feedback += (
                f"- *{err.get('type', 'Error')}*: {err.get('explanation', '')}\n"
            )
    feedback += f"\n**Рекомендация:** {result.get('recommendation', '')}\n"

    # Получаем следующее задание
    next_task_text, next_task_id = await init_task()

    return feedback, next_task_text, next_task_id, None, None, None, None, None


def build_ui():
    with gr.Blocks(title="English Tutor AI") as demo:
        gr.Markdown("# 🎓 English Tutor AI (Voice Edition)")

        task_id_state = gr.State(value=0)

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 📝 Текущее задание:")
                task_display = gr.Textbox(
                    label="Переведите эти 5 предложений", interactive=False, lines=7
                )

                gr.Markdown("### 🎙️ Запись ответов (по одному на предложение):")
                audio1 = gr.Audio(
                    sources=["microphone"], type="filepath", label="Предложение 1"
                )
                audio2 = gr.Audio(
                    sources=["microphone"], type="filepath", label="Предложение 2"
                )
                audio3 = gr.Audio(
                    sources=["microphone"], type="filepath", label="Предложение 3"
                )
                audio4 = gr.Audio(
                    sources=["microphone"], type="filepath", label="Предложение 4"
                )
                audio5 = gr.Audio(
                    sources=["microphone"], type="filepath", label="Предложение 5"
                )

                submit_btn = gr.Button("Отправить на проверку", variant="primary")

            with gr.Column(scale=1):
                gr.Markdown("### 📊 Результат проверки:")
                feedback_display = gr.Markdown(
                    "Здесь появится разбор ваших ошибок и оценка."
                )

        # При загрузке страницы генерируем или загружаем задание
        demo.load(fn=init_task, outputs=[task_display, task_id_state])

        # Обработка отправки
        submit_btn.click(
            fn=process_submission,
            inputs=[
                task_id_state,
                task_display,
                audio1,
                audio2,
                audio3,
                audio4,
                audio5,
            ],
            outputs=[
                feedback_display,
                task_display,
                task_id_state,
                audio1,
                audio2,
                audio3,
                audio4,
                audio5,
            ],
        )

    return demo
