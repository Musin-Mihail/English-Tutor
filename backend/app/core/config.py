import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Базовые настройки
    PROJECT_NAME: str = "English Tutor AI"
    API_V1_STR: str = "/api/v1"

    # Настройки CORS (кто может стучаться на сервер)
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:4200"]

    # Ключи API (Обязательное поле, без него приложение упадет при старте)
    GOOGLE_API_KEY: str

    # Конфигурация для чтения .env файла
    model_config = SettingsConfigDict(
        env_file=".env", env_ignore_empty=True, extra="ignore"
    )


# Создаем единственный экземпляр настроек для импорта в других файлах
settings = Settings()
