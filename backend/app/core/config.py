from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str | None = None
    app_env: str = "development"
    api_port: int = 4000
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file="backend/.env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
