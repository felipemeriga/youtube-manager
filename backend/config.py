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
    openai_api_key: str = ""
    cors_origins: str = "http://localhost:5173"
    database_url: str = ""
    clips_cleanup_token: str = ""  # service token for /api/clips/cleanup
    clips_tmp_dir: str = "/tmp/clips"
    clips_bucket: str = "clips"
    # yt-dlp auth: YouTube now bot-blocks unauthenticated server IPs. Set
    # either a Netscape-format cookies file path OR a browser name
    # (chrome / firefox / safari / edge) to source cookies from. If both are
    # empty, yt-dlp runs without auth and may hit "Sign in to confirm you're
    # not a bot" errors.
    youtube_cookies_file: str = ""
    youtube_cookies_from_browser: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
