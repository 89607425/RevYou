"""Application configuration loaded from .env"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    # LLM
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096

    # Agent loop controls
    max_llm_calls_per_agent: int = 12
    max_reflect_loops: int = 2

    # TAPD
    tapd_api_url: str = "https://api.tapd.cn"
    tapd_token: str = ""
    tapd_workspace_ids: str = ""

    # App
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    db_path: str = str(Path(__file__).resolve().parent.parent.parent / "data" / "review.db")

    # Concurrency limit for LLM calls
    llm_concurrency: int = 6


settings = Settings()

# Resolve paths
BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR.parent
PROJECT_DIR = BACKEND_DIR.parent
PROMPTS_DIR = BACKEND_DIR / "prompts"
DATA_DIR = PROJECT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
