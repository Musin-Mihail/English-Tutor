from typing import List, Literal, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.paths import PROJECT_ROOT


class Settings(BaseSettings):
    PROJECT_NAME: str = "English Tutor AI"
    API_V1_STR: str = "/api/v1"
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:4200"]

    AI_PROVIDER: Literal["cursor", "gemini"] = "cursor"

    CURSOR_API_KEY: Optional[str] = None
    CURSOR_MODEL: str = "composer-2.5"

    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3-flash-preview"

    WHISPER_MODEL: str = "large-v3"
    ASR_DEVICE: str = "auto"
    ASR_COMPUTE_TYPE: str = "auto"
    # Локальный каталог для весов Whisper (None → app/data/whisper_models)
    ASR_DOWNLOAD_ROOT: Optional[str] = None
    ASR_PRELOAD: bool = True

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_provider_keys(self) -> "Settings":
        if self.AI_PROVIDER == "cursor" and not self.CURSOR_API_KEY:
            raise ValueError(
                "CURSOR_API_KEY is required when AI_PROVIDER=cursor. "
                "Get a key at https://cursor.com/dashboard/integrations"
            )
        if self.AI_PROVIDER == "gemini" and not self.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is required when AI_PROVIDER=gemini")
        return self


settings = Settings()
