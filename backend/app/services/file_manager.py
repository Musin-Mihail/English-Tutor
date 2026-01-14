import os
import re
import datetime
from typing import List, Dict


class FileManager:
    def __init__(self, data_dir: str = "app/data"):
        self.table_path = os.path.join(data_dir, "ENGLISH_performance_table.md")
        self.journal_path = os.path.join(data_dir, "ENGLISH_training_journal.md")

    def read_file(self, path: str) -> str:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def get_context(self):
        """
        Возвращает контекст для AI.
        ВАЖНО: Журнал обрезается до последних 5 заданий, чтобы не превысить лимит токенов (TPM).
        """
        table_content = self.read_file(self.table_path)
        journal_full = self.read_file(self.journal_path)

        parts = re.split(r"(?=### Задание)", journal_full)

        if len(parts) > 1:
            header = parts[0]
            tasks = parts[1:]

            recent_tasks = tasks[-5:] if len(tasks) > 5 else tasks

            journal_context = header + "".join(recent_tasks)
        else:
            journal_context = journal_full

        return table_content, journal_context

    def update_journal(self, task: str, student_ans: str, ai_result: Dict):
        """Дописывает новый блок в журнал (на диск пишем ВСЁ, историю не удаляем)"""
        if not ai_result:
            return

        today = datetime.date.today().strftime("%d.%m.%Y")

        errors_list = ai_result.get("errors", [])
        errors_text = ""
        if isinstance(errors_list, list):
            for err in errors_list:
                if isinstance(err, dict):
                    t = err.get("type", "Error")
                    e = err.get("explanation", "No explanation")
                    errors_text += f"  - **{t}:** {e}\n"

        topic = ai_result.get("main_topic") or "General"
        correct = ai_result.get("correct_variant") or "---"
        score = ai_result.get("score", 0)
        recommendation = ai_result.get("recommendation") or "No recommendation"

        new_voc_list = ai_result.get("new_vocabulary", [])
        new_voc_str = ", ".join(new_voc_list) if isinstance(new_voc_list, list) else ""

        new_entry = f"""
### Задание - {today}

**Задание (Русский):**
{task}

**Мой ответ (Английский):**
{student_ans}

**Проверка:**
- **Тема:** {topic}
- **Правильно:** {correct}
- **Оценка:** {score}/10
- **Разбор ошибок:**
{errors_text}
- **Рекомендация:** {recommendation}
- **Новые слова:** {new_voc_str}

---
"""
        try:
            with open(self.journal_path, "a", encoding="utf-8") as f:
                f.write(new_entry)
        except Exception as e:
            print(f"Ошибка записи в журнал: {e}")

    def update_performance_table(self, ai_result: Dict):
        """Обновляет оценки и слова в таблице"""
        if not ai_result:
            return

        topic = ai_result.get("main_topic")
        if not topic or not isinstance(topic, str):
            return

        content = self.read_file(self.table_path)

        new_voc = ai_result.get("new_vocabulary", [])
        if new_voc and isinstance(new_voc, list):
            voc_match = re.search(r"(\*\*Активный словарный запас:\*\* )(.*)", content)
            if voc_match:
                current_voc = voc_match.group(2)
                words_to_add = [str(w) for w in new_voc if str(w) not in current_voc]
                if words_to_add:
                    updated_line = (
                        f"{voc_match.group(1)}{current_voc}, {', '.join(words_to_add)}"
                    )
                    content = content.replace(voc_match.group(0), updated_line)

        score = ai_result.get("score")
        if score is None:
            score = 0

        today = datetime.date.today().strftime("%d.%m.%Y")

        try:
            safe_topic = re.escape(topic)
        except:
            return

        pattern = f"(### Тема:.*?{safe_topic}.*?)(?=\n###|\Z)"
        section_match = re.search(pattern, content, re.DOTALL)

        if section_match:
            section_text = section_match.group(1)

            scores_match = re.search(r"(\*\*Все оценки:\*\* )(.*)", section_text)
            if scores_match:
                old_scores_str = scores_match.group(2).strip()
                new_scores_str = (
                    f"{old_scores_str}, {score}" if old_scores_str else f"{score}"
                )

                try:
                    score_list = [
                        float(x) for x in new_scores_str.split(",") if x.strip()
                    ]
                    if score_list:
                        avg_score = round(sum(score_list) / len(score_list), 1)
                    else:
                        avg_score = 0.0
                except:
                    avg_score = 0.0

                new_section = section_text.replace(
                    scores_match.group(0), f"**Все оценки:** {new_scores_str}"
                )

                new_section = re.sub(
                    r"\*\*Средний балл.*?\n",
                    f"**Средний балл (из 10):** {avg_score}\n",
                    new_section,
                )

                new_section = re.sub(
                    r"\*\*Даты проверок:\*\* (.*)",
                    lambda m: (
                        f"**Даты проверок:** {m.group(1)}, {today}"
                        if m.group(1).strip()
                        else f"**Даты проверок:** {today}"
                    ),
                    new_section,
                )

                content = content.replace(section_text, new_section)

        try:
            with open(self.table_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            print(f"Ошибка перезаписи таблицы: {e}")
