from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "RevYou"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "postgresql+asyncpg://revyou:hjy89607425@localhost:5432/revyou"
    DATABASE_URL_SYNC: str = "postgresql://revyou:hjy89607425@localhost:5432/revyou"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: str = "revyou-jwt-secret-key-2026-must-be-32-chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    ENCRYPTION_KEY: str = "revyou-aes256-encryption-key-32b"

    UPLOAD_DIR: str = "/data/uploads"
    MAX_UPLOAD_SIZE: int = 20 * 1024 * 1024  # 20MB
    MAX_SESSION_SIZE: int = 50 * 1024 * 1024  # 50MB total

    LLM_BASE_URL: str = "https://api.siliconflow.cn/v1"
    LLM_DEEPSEEK_API_KEY: str = ""
    LLM_DEEPSEEK_BASE_URL: str = "https://api.siliconflow.cn/v1"
    LLM_QWEN_API_KEY: str = ""
    LLM_QWEN_BASE_URL: str = "https://api.siliconflow.cn/v1"
    LLM_OPENAI_API_KEY: str = ""
    LLM_OPENAI_BASE_URL: str = "https://api.siliconflow.cn/v1"

    TAPD_API_BASE: str = "https://api.tapd.cn"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
