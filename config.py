from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import SecretStr, Field


class Settings(BaseSettings):

    BOT_TOKEN: SecretStr

    SUPER_ADMIN_ID: list[int]

    BASE_DIR: Path = Path(__file__).resolve().parent

    FILES_DIR: str = Field(
        default_factory=lambda: str(
            Path(__file__).resolve().parent / "files" / "checks"
        ),
        env="FILES_DIR",
    )

    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
