"""
config.py
---------
All environment variables are loaded here using Pydantic Settings.
Access anywhere in the app via:  from app.config import settings
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database — falls back to SQLite if not set
    DATABASE_URL: str = ""

    # JWT
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # AI APIs
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # Vector DB
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX: str = "recruiter-index"

    # Email
    SENDGRID_API_KEY: str = ""
    FROM_EMAIL: str = "recruiter@yourcompany.com"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """
        Returns PostgreSQL URL if provided,
        otherwise falls back to local SQLite.
        """
        if self.DATABASE_URL.strip():
            return self.DATABASE_URL
        return "sqlite:///./recruiter.db"


settings = Settings()