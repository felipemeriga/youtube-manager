from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_key: str
    gemini_api_key: str
    guardian_url: str = "http://localhost:3000"
    guardian_api_key: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"
    voyage_api_key: str = ""
    cors_origins: str = "http://localhost:5173"
    database_url: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
