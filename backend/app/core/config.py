from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str | None = None
    openai_api_key: str | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    openai_query_model: str = "gpt-4.1-mini"
    embedding_dimensions: int = 1536
    query_match_count: int = 4
    query_scan_limit: int = 200
    query_min_similarity: float = 0.25
    query_max_context_chars: int = 3000
    query_max_history_chars: int = 2000
    query_max_question_chars: int = 1000
    query_max_output_tokens: int = 180
    chunk_size_chars: int = 900
    chunk_overlap_chars: int = 150
    demo_feature_slug: str = "default-demo-feature"
    demo_feature_name: str = "Default Demo Feature"
    demo_review_title: str = "Default Shared Demo Review"
    public_review_org_slug: str = "public-review-demo"
    public_review_org_name: str = "Public Review Demo"
    public_review_feature_slug: str = "public-checkout-experience"
    public_review_feature_name: str = "Public Checkout Experience"
    app_env: str = "development"
    api_port: int = 4000
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file="backend/.env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
