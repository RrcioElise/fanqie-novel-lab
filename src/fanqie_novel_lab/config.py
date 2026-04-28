from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
DB_DIR = DATA_DIR / "db"
CONFIG_DIR = DATA_DIR / "config"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTLINE_DIR = OUTPUT_DIR / "outlines"
REVIEW_DIR = OUTPUT_DIR / "reviews"
CHAPTER_AUDIT_DIR = REVIEW_DIR / "chapters"
CHAPTER_DIR = OUTPUT_DIR / "chapters"
PUBLISH_DIR = OUTPUT_DIR / "publishing"
PUBLISH_WORK_DIR = PUBLISH_DIR / "works"
PUBLISH_PACKAGE_DIR = PUBLISH_DIR / "packages"
LOG_DIR = PROJECT_ROOT / "logs"

for path in [RAW_DIR, PROCESSED_DIR, DB_DIR, CONFIG_DIR, OUTLINE_DIR, REVIEW_DIR, CHAPTER_AUDIT_DIR, CHAPTER_DIR, PUBLISH_DIR, PUBLISH_WORK_DIR, PUBLISH_PACKAGE_DIR, LOG_DIR]:
    path.mkdir(parents=True, exist_ok=True)

load_dotenv(PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(PROJECT_ROOT / ".env"), extra="ignore")

    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    llm_api_key: str | None = None
    llm_temperature: float = 0.75
    llm_timeout_seconds: int = 120

    crawler_delay_seconds: float = 1.5
    crawler_user_agent: str = "fanqie-novel-lab/0.1 metadata-research"

    db_path: Path = DB_DIR / "fanqie_novel_lab.sqlite3"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
