"""ReqLev – Application Configuration"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Database ────────────────────────────────────────────────────────────
    DATABASE_URL: str = "mysql+pymysql://root:@localhost:3306/reqlev"

    # ── Security ────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-this-in-production-use-a-long-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43_200  # 30 days – persist until logout

    # ── App ─────────────────────────────────────────────────────────────────
    APP_NAME: str = "ReqLev"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
