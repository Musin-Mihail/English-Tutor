import os
import gradio as gr
from app.services.grader_agent import GraderAgent
from app.data.database import DatabaseManager

agent = GraderAgent()
db = DatabaseManager()


def format_token_display(state):
    return f"**📊 Токены за сессию:** Вход: {state['input']} | Выход: {state['output']} | Потрачено: ${state['cost']:.4f}"


def generate_feedback_markdown(result, score, topic):
    feedback = f"### Оценка: {score}/10\n"
    feedback += f"**Тема:** {topic}\n\n"

    sentences = result.get("sentences_feedback", [])
    if sentences:
        for s in sentences:
            feedback += f"#### Предложение {s.get('sentence_number', '?')}\n"
            if s.get("student_transcription"):
                feedback += f"🗣 **Вы сказали:** {s.get('student_transcription')}\n"
            feedback += f"✅ **Правильный вариант:** {s.get('correct_variant', '')}\n"

            alts = s.get("alternatives", [])
            if alts:
                feedback += f"🔄 **Альтернативы:** {', '.join(alts)}\n"

            errors = s.get("errors", [])
            if errors:
                feedback += "**Ошибки:**\n"
                for err in errors:
                    feedback += f"- *{err.get('type', 'Error')}*: {err.get('explanation', '')}\n"
            else:
                feedback += "✨ **Ошибок нет!**\n"
            feedback += "\n---\n"
    else:
        # Fallback для старых записей из журнала
        feedback += f"**Правильный вариант:**\n{result.get('correct_variant', '')}\n\n"
        if result.get("errors"):
            feedback += "**Ошибки:**\n"
            for err in result.get("errors", []):
                feedback += (
                    f"- *{err.get('type', 'Error')}*: {err.get('explanation', '')}\n"
                )

    feedback += f"\n**Рекомендация:** {result.get('recommendation', '')}\n"
    return feedback


async def init_task(token_state):
    table_context, journal_context = db.get_context()
    task_response = await agent.generate_new_task(table_context, journal_context)
    task_text = task_response["result"]

    token_state["input"] += task_response["tokens"]["input"]
    token_state["output"] += task_response["tokens"]["output"]
    token_state["cost"] = (token_state["input"] / 1_000_000) * 0.50 + (
        token_state["output"] / 1_000_000
    ) * 3.00

    task_id = db.add_task(task_text)
    return task_text, task_id, token_state, format_token_display(token_state)


async def process_submission(
    task_id, task_text, token_state, audio1, audio2, audio3, audio4, audio5
):
    audios = [a for a in [audio1, audio2, audio3, audio4, audio5] if a is not None]
    if not audios:
        return (
            "⚠️ Пожалуйста, запишите хотя бы один аудиофайл.",
            gr.update(),
            gr.update(),
            token_state,
            format_token_display(token_state),
            audio1,
            audio2,
            audio3,
            audio4,
            audio5,
            gr.update(),
        )

    table_context, journal_context = db.get_context()
    eval_response = await agent.grade_translation(
        audios, task_text, table_context, journal_context
    )
    result = eval_response["result"]

    token_state["input"] += eval_response["tokens"]["input"]
    token_state["output"] += eval_response["tokens"]["output"]
    token_state["cost"] = (token_state["input"] / 1_000_000) * 0.50 + (
        token_state["output"] / 1_000_000
    ) * 3.00

    score = result.get("score", 0)
    topic = result.get("main_topic", "General")

    db.add_journal_entry(task_id, audios, result, score)
    db.update_performance(topic, score)

    feedback = generate_feedback_markdown(result, score, topic)

    next_task_text, next_task_id, token_state, token_disp = await init_task(token_state)
    new_perf_ui = update_performance_ui()

    return (
        feedback,
        next_task_text,
        next_task_id,
        token_state,
        token_disp,
        None,
        None,
        None,
        None,
        None,
        new_perf_ui,
    )


def get_performance_data():
    try:
        data = db.get_all_performance()
        if not data:
            return [["Нет данных", "0.0"]]
        return [[str(row[0]), str(row[1])] for row in data]
    except Exception as e:
        print(f"Ошибка загрузки успеваемости: {e}")
        return [["Ошибка БД", str(e)]]


def update_performance_ui():
    return gr.update(value=get_performance_data())


def load_journal_choices():
    history = db.get_journal_history_full()
    choices = [
        f"{item['id']}: {item['task_text']} ({item['created_at']})" for item in history
    ]
    return gr.update(choices=choices)


def load_journal_entry(choice):
    if not choice:
        return "Выберите запись", None, None, None, None, None
    try:
        entry_id = int(choice.split(":")[0])
        history = db.get_journal_history_full()
        entry = next((item for item in history if item["id"] == entry_id), None)
        if not entry:
            return "Запись не найдена", None, None, None, None, None

        result = entry["ai_feedback"]
        score = entry.get("score", 0)
        topic = result.get("main_topic", "General")

        feedback = generate_feedback_markdown(result, score, topic)

        audios = entry.get("audio_paths", [])
        audios_out = []
        for i in range(5):
            if i < len(audios) and os.path.exists(audios[i]):
                audios_out.append(audios[i])
            else:
                audios_out.append(None)

        return feedback, *audios_out
    except Exception as e:
        return f"Ошибка загрузки: {e}", None, None, None, None, None


def build_ui():
    with gr.Blocks(title="English Tutor AI") as demo:
        gr.Markdown("# 🎓 English Tutor AI (Voice Edition)")

        token_state = gr.State(value={"input": 0, "output": 0, "cost": 0.0})
        token_display = gr.Markdown(
            "**📊 Токены за сессию:** Вход: 0 | Выход: 0 | Потрачено: $0.0000"
        )

        with gr.Tabs():
            # Первая вкладка: Практика
            with gr.Tab("📝 Практика"):
                task_id_state = gr.State(value=0)

                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 📝 Текущее задание:")
                        task_display = gr.Textbox(
                            label="Переведите эти 5 предложений",
                            interactive=False,
                            lines=7,
                        )

                        gr.Markdown("### 🎙️ Запись ответов (по одному на предложение):")
                        # ДОБАВЛЕН format="mp3" ко всем микрофонам
                        audio1 = gr.Audio(
                            sources=["microphone"],
                            type="filepath",
                            format="mp3",
                            label="Предложение 1",
                        )
                        audio2 = gr.Audio(
                            sources=["microphone"],
                            type="filepath",
                            format="mp3",
                            label="Предложение 2",
                        )
                        audio3 = gr.Audio(
                            sources=["microphone"],
                            type="filepath",
                            format="mp3",
                            label="Предложение 3",
                        )
                        audio4 = gr.Audio(
                            sources=["microphone"],
                            type="filepath",
                            format="mp3",
                            label="Предложение 4",
                        )
                        audio5 = gr.Audio(
                            sources=["microphone"],
                            type="filepath",
                            format="mp3",
                            label="Предложение 5",
                        )

                        submit_btn = gr.Button(
                            "Отправить на проверку", variant="primary"
                        )

                    with gr.Column(scale=1):
                        gr.Markdown("### 📊 Результат проверки:")
                        feedback_display = gr.Markdown(
                            "Здесь появится разбор ваших ошибок и оценка."
                        )

            # Вторая вкладка: Успеваемость
            with gr.Tab("📈 Успеваемость") as perf_tab:
                perf_table = gr.Dataframe(
                    value=get_performance_data(),
                    headers=["Тема", "Средний балл"],
                    datatype=["str", "str"],
                    type="array",
                    column_count=(2, "fixed"),
                    interactive=False,
                )
                refresh_perf_btn = gr.Button("Обновить данные")

            # Третья вкладка: Журнал
            with gr.Tab("📓 Журнал занятий") as journal_tab:
                with gr.Row():
                    with gr.Column():
                        journal_dropdown = gr.Dropdown(
                            label="Выберите занятие", choices=[]
                        )
                        journal_refresh_btn = gr.Button("Обновить список")
                        j_a1 = gr.Audio(label="Ответ 1", interactive=False)
                        j_a2 = gr.Audio(label="Ответ 2", interactive=False)
                        j_a3 = gr.Audio(label="Ответ 3", interactive=False)
                        j_a4 = gr.Audio(label="Ответ 4", interactive=False)
                        j_a5 = gr.Audio(label="Ответ 5", interactive=False)
                    with gr.Column():
                        journal_feedback = gr.Markdown("Здесь появится разбор.")

        demo.load(
            fn=init_task,
            inputs=[token_state],
            outputs=[task_display, task_id_state, token_state, token_display],
        )

        journal_tab.select(fn=load_journal_choices, outputs=[journal_dropdown])

        refresh_perf_btn.click(fn=update_performance_ui, outputs=[perf_table])
        journal_refresh_btn.click(fn=load_journal_choices, outputs=[journal_dropdown])

        journal_dropdown.change(
            fn=load_journal_entry,
            inputs=[journal_dropdown],
            outputs=[journal_feedback, j_a1, j_a2, j_a3, j_a4, j_a5],
        )

        submit_btn.click(
            fn=process_submission,
            inputs=[
                task_id_state,
                task_display,
                token_state,
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
                token_state,
                token_display,
                audio1,
                audio2,
                audio3,
                audio4,
                audio5,
                perf_table,
            ],
        )

    return demo
