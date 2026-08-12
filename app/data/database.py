import json
import os
import shutil
from datetime import datetime

from app.paths import AUDIO_DIR, DB_PATH
from typing import List, Dict, Optional
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

Base = declarative_base()


class UserPerformance(Base):
    __tablename__ = "user_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic_name = Column(String, unique=True, nullable=False)
    scores_list = Column(Text, default="[ ]")
    average_score = Column(Float, default=0.0)
    active_vocabulary = Column(Text, default="[ ]")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    russian_text = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    journals = relationship("Journal", back_populates="task")


class Journal(Base):
    __tablename__ = "journals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    student_audio_paths = Column(Text, default="[ ]")
    ai_feedback = Column(Text, default="{}")
    score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="journals")


class DatabaseManager:
    def __init__(self, db_url: Optional[str] = None):
        DATA_DIR = DB_PATH.parent
        os.makedirs(DATA_DIR, exist_ok=True)
        self.audio_dir = str(AUDIO_DIR)
        os.makedirs(self.audio_dir, exist_ok=True)
        if db_url is None:
            db_url = f"sqlite:///{DB_PATH.as_posix()}"
        self.engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        self._init_default_topics()

    def _init_default_topics(self):
        default_topics = [
            "Артикли (a/an, the)",
            "Предлоги (in, on, at, for)",
            "Времена Present (Simple vs. Cont.)",
            "Времена Past (Simple vs. Cont. vs. Perf.)",
            "Неправильные глаголы",
            "Порядок слов в предложении",
            "Модальные глаголы",
            "Условные предложения (Conditionals)",
            "Фразовые глаголы",
            "Косвенная речь (Reported Speech)",
        ]
        with self.SessionLocal() as session:
            for topic in default_topics:
                exists = (
                    session.query(UserPerformance).filter_by(topic_name=topic).first()
                )
                if not exists:
                    new_topic = UserPerformance(topic_name=topic)
                    session.add(new_topic)
            session.commit()

    def get_context(self):
        with self.SessionLocal() as session:
            topics = session.query(UserPerformance).all()
            table_content = "Context Table:\n"
            for t in topics:
                table_content += (
                    f"- Topic: {t.topic_name} | Avg Score: {t.average_score}\n"
                )

            journals = (
                session.query(Journal)
                .order_by(Journal.created_at.desc())
                .limit(5)
                .all()
            )
            journal_content = "Journal History:\n"
            for j in reversed(journals):
                task_text = j.task.russian_text if j.task else "Unknown"
                journal_content += f"**Задание (Русский):**\n{task_text}\n"

            return table_content, journal_content

    def add_task(self, russian_text: str) -> int:
        with self.SessionLocal() as session:
            task = Task(russian_text=russian_text)
            session.add(task)
            session.commit()
            session.refresh(task)
            return task.id

    def add_journal_entry(
        self, task_id: int, audio_paths: List[str], ai_feedback: Dict, score: float
    ):
        saved_audio_paths = []
        for path in audio_paths:
            if os.path.exists(path):
                filename = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{os.path.basename(path)}"
                dest_path = os.path.join(self.audio_dir, filename)
                shutil.copy2(path, dest_path)
                saved_audio_paths.append(dest_path)

        with self.SessionLocal() as session:
            journal = Journal(
                task_id=task_id,
                student_audio_paths=json.dumps(saved_audio_paths, ensure_ascii=False),
                ai_feedback=json.dumps(ai_feedback, ensure_ascii=False),
                score=score,
            )
            session.add(journal)
            session.commit()

    def update_performance(self, topic_name: str, score: float):
        if not topic_name:
            return
        with self.SessionLocal() as session:
            topic = (
                session.query(UserPerformance).filter_by(topic_name=topic_name).first()
            )
            if not topic:
                topic = UserPerformance(topic_name=topic_name)
                session.add(topic)

            scores = json.loads(topic.scores_list) if topic.scores_list else []
            scores.append(score)
            topic.scores_list = json.dumps(scores)
            topic.average_score = round(sum(scores) / len(scores), 1)

            # Логика обновления словаря удалена по запросу
            session.commit()

    def get_all_performance(self):
        with self.SessionLocal() as session:
            topics = session.query(UserPerformance).all()
            result = []
            for t in topics:
                # Возвращаем только 2 колонки
                result.append([t.topic_name, t.average_score])
            return result

    def get_journal_history_full(self):
        with self.SessionLocal() as session:
            journals = session.query(Journal).order_by(Journal.created_at.desc()).all()
            result = []
            for j in journals:
                task_text = j.task.russian_text if j.task else "Unknown"
                audio_paths = (
                    json.loads(j.student_audio_paths) if j.student_audio_paths else []
                )
                ai_feedback = json.loads(j.ai_feedback) if j.ai_feedback else {}
                result.append(
                    {
                        "id": j.id,
                        "task_text": task_text,
                        "created_at": j.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "audio_paths": audio_paths,
                        "ai_feedback": ai_feedback,
                        "score": j.score,
                    }
                )
            return result
