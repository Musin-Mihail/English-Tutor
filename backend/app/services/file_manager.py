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
        return self.read_file(self.table_path), self.read_file(self.journal_path)

    def update_journal(self, task: str, student_ans: str, ai_result: Dict):
        """Дописывает новый блок в журнал"""
        today = datetime.date.today().strftime("%d.%m.%Y")

        errors_text = ""
        for err in ai_result.get("errors", []):
            errors_text += f"  - **{err['type']}:** {err['explanation']}\n"

        new_entry = f"""
### Задание - {today}

**Задание (Русский):**
{task}

**Мой ответ (Английский):**
{student_ans}

**Проверка:**
- **Тема:** {ai_result.get('main_topic')}
- **Правильно:** {ai_result.get('correct_variant')}
- **Оценка:** {ai_result.get('score')}/10
- **Разбор ошибок:**
{errors_text}
- **Рекомендация:** {ai_result.get('recommendation')}
- **Новые слова:** {', '.join(ai_result.get('new_vocabulary', []))}

---
"""
        with open(self.journal_path, "a", encoding="utf-8") as f:
            f.write(new_entry)

    def update_performance_table(self, ai_result: Dict):
        """Обновляет оценки и слова в таблице"""
        content = self.read_file(self.table_path)

        new_voc = ai_result.get("new_vocabulary", [])
        if new_voc:
            voc_match = re.search(r"(\*\*Активный словарный запас:\*\* )(.*)", content)
            if voc_match:
                current_voc = voc_match.group(2)
                words_to_add = [w for w in new_voc if w not in current_voc]
                if words_to_add:
                    updated_line = (
                        f"{voc_match.group(1)}{current_voc}, {', '.join(words_to_add)}"
                    )
                    content = content.replace(voc_match.group(0), updated_line)

        topic = ai_result.get("main_topic")
        score = ai_result.get("score")
        today = datetime.date.today().strftime("%d.%m.%Y")

        safe_topic = re.escape(topic)
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

                score_list = [float(x) for x in new_scores_str.split(",") if x.strip()]
                avg_score = round(sum(score_list) / len(score_list), 1)

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

        with open(self.table_path, "w", encoding="utf-8") as f:
            f.write(content)
