from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str | None = None
    openai_api_key: str | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    chunk_size_chars: int = 900
    chunk_overlap_chars: int = 150
    demo_feature_slug: str = "default-demo-feature"
    demo_feature_name: str = "Default Demo Feature"
    demo_review_title: str = "Default Shared Demo Review"
    app_env: str = "development"
    api_port: int = 4000
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file="backend/.env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
