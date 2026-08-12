from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.paths import PROJECT_ROOT


class Settings(BaseSettings):
    PROJECT_NAME: str = "English Tutor AI"
    API_V1_STR: str = "/api/v1"
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:4200"]
    GOOGLE_API_KEY: str
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_ignore_empty=True,
        extra="ignore",
    )


settings = Settings()
