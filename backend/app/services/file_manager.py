import os
import re
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
        if not ai_result:
            return

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
        if new_voc_list is None:
            new_voc_list = []
        new_voc_str = ", ".join(new_voc_list)

        new_entry = f"""
### Задание

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
        if not ai_result:
            return

        topic = ai_result.get("main_topic")
        if not topic or not isinstance(topic, str):
            print("Ошибка: Нет темы в ответе AI")
            return

        content = self.read_file(self.table_path)

        new_voc = ai_result.get("new_vocabulary", [])
        if new_voc and isinstance(new_voc, list):
            voc_match = re.search(r"(\*\*Активный словарный запас:\*\* )(.*)", content)
            if voc_match:
                current_voc_str = voc_match.group(2)
                words_to_add = []
                for w in new_voc:
                    w_clean = str(w).strip()
                    if w_clean and w_clean not in current_voc_str and len(w_clean) > 2:
                        words_to_add.append(w_clean)

                if words_to_add:
                    updated_line = f"{voc_match.group(1)}{current_voc_str}, {', '.join(words_to_add)}"
                    content = content.replace(voc_match.group(0), updated_line)

        score = ai_result.get("score", 0)

        try:
            safe_topic = re.escape(topic.strip())
            pattern = rf"(### Тема:\s+{safe_topic}.*?)(?=\n\s*###|\Z)"
            section_match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)

            if section_match:
                start_idx = section_match.start(1)
                end_idx = section_match.end(1)
                section_text = section_match.group(1)

                scores_match = re.search(
                    r"(\*\*Все оценки:\*\*)[ \t]*(.*)", section_text
                )

                if scores_match:
                    old_scores_str = scores_match.group(2).strip()

                    if old_scores_str:
                        new_scores_str = f"{old_scores_str}, {score}"
                    else:
                        new_scores_str = f"{score}"

                    try:
                        score_list = [
                            float(x) for x in new_scores_str.split(",") if x.strip()
                        ]
                        avg_score = (
                            round(sum(score_list) / len(score_list), 1)
                            if score_list
                            else 0.0
                        )
                    except:
                        avg_score = 0.0

                    new_section = section_text.replace(
                        scores_match.group(0), f"**Все оценки:** {new_scores_str}", 1
                    )

                    new_section = re.sub(
                        r"(\*\*Средний балл.*?:\*\*).*",
                        rf"\1 {avg_score}",
                        new_section,
                        count=1,
                    )

                    content = content[:start_idx] + new_section + content[end_idx:]

                    with open(self.table_path, "w", encoding="utf-8") as f:
                        f.write(content)

                    print(f"Успешно обновлена тема: {topic}")
                else:
                    print(f"Не найдено поле '**Все оценки:**' в блоке {topic}")
            else:
                print(f"Тема '{topic}' не найдена в таблице.")

        except Exception as e:
            print(f"Ошибка обновления таблицы: {e}")
