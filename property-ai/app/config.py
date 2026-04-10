from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    database_url_sync: str
    ollama_base_url: str = "http://localhost:11434"
    ollama_llm_model: str = "qwen2.5-coder:7b"
    ollama_embed_model: str = "nomic-embed-text"
    debug: bool = False

    # Appeal scoring thresholds
    strong_candidate_z_score: float = 2.0
    strong_candidate_zip_pct: float = 0.20
    moderate_candidate_z_score: float = 1.5
    moderate_candidate_zip_pct: float = 0.30


settings = Settings()
