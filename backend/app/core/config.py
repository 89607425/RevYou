from pydantic_settings import BaseSettings
import os

_ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), ".env")


class Settings(BaseSettings):
    model_config = {"env_file": _ENV_FILE, "case_sensitive": True, "extra": "ignore"}

    PROJECT_NAME: str = "RevYou"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "mysql+aiomysql://revyou:hjy89607425@localhost:3306/revyou"
    DATABASE_URL_SYNC: str = "mysql+pymysql://revyou:hjy89607425@localhost:3306/revyou"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: str = "revyou-jwt-secret-key-2026-must-be-32-chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    ENCRYPTION_KEY: str = "revyou-aes256-encryption-key-32b"

    UPLOAD_DIR: str = "/tmp/revyou-uploads"
    MAX_UPLOAD_SIZE: int = 20 * 1024 * 1024
    MAX_SESSION_SIZE: int = 50 * 1024 * 1024

    LLM_BASE_URL: str = "https://api.siliconflow.cn/v1"

    LLM_DEEPSEEK_API_KEY: str = ""
    LLM_DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"

    LLM_SILICONFLOW_API_KEY: str = ""
    LLM_SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"

    LLM_GEMINI_API_KEY: str = ""
    LLM_GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    LLM_ZHIPU_API_KEY: str = ""
    LLM_ZHIPU_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4/"

    TAPD_API_BASE: str = "https://api.tapd.cn"
    TAPD_DEFAULT_TOKEN: str = "83e76cf85e8d89074ec256485d67b04b41349256"
    TAPD_DEFAULT_STORY_WORKSPACE: str = "37119417"
    TAPD_DEFAULT_BUG_WORKSPACE: str = "38585571"


settings = Settings()
