from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASHARE_F10_", env_file=".env", extra="ignore")

    data_dir: Path = Path("data")
    max_workers: int = 8
    page_workers: int = 4
    timeout: int = 45
    retries: int = 3
    cache_ttl_hours: int = 24
    host: str = "127.0.0.1"
    port: int = 8000
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150 Safari/537.36"
    )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
