from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://hyro:hyro@localhost:5432/hyro"
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "hyro-research"
    seed_user_email: str = "recruiter@example.test"
    mock_page_delay_seconds: float = 0.1
    mock_fail_once_source: str | None = None
    mock_fail_once_cursor: int = 1


settings = Settings()
