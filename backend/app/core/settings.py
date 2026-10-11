from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Runtime configuration. Override with OS_* environment variables or backend/.env."""

    model_config = SettingsConfigDict(env_prefix="OS_", env_file=".env", extra="ignore")

    # SQLite by default (SRS 2.4: local database); set to a Postgres URL to use Supabase.
    database_url: str = f"sqlite:///{(REPO_ROOT / 'backend' / 'orbital.db').as_posix()}"
    secret_key: str = "dev-only-change-me"
    session_cookie: str = "os_session"
    session_max_age_seconds: int = 8 * 3600
    # Exposes /api/reset so test suites can restore the demo alerts. Turn off outside dev.
    enable_test_reset: bool = True
    data_dir: Path = REPO_ROOT / "data"
    models_dir: Path = REPO_ROOT / "models"
    results_dir: Path = REPO_ROOT / "docs" / "results"


settings = Settings()
