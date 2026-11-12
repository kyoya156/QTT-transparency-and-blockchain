"""Typed settings for the chatbot. Everything configurable lives in .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # database
    database_url: str = "postgresql+psycopg://qne:qne@localhost:5433/qne_chatbot"

    # crawler contract
    crawler_base_url: str = "http://localhost:8000"
    crawler_api_key: str = ""
    crawler_page_size: int = 500
    crawler_timeout_s: float = 30.0
    sync_source_types: str = "web,post"

    # sync source selection
    sync_source: str = "file"
    sync_file: str = "data/chunks.json"

    # embeddings
    embed_provider: str = "local"
    embed_model: str = "AITeamVN/Vietnamese_Embedding_v2"
    embed_dim: int = 1024
    embed_device: str = "cpu"
    # float32 is the safe default; float16 halves the memory the model needs,
    # which is what lets a 14 GB laptop with a small pagefile load BGE-M3 at all.
    embed_dtype: str = "float32"
    embed_batch_size: int = 16

    # retrieval
    retrieval_k: int = 5
    retrieval_pool: int = 20
    rrf_k: int = 60
    # measured, not guessed: on the fixture a real question's best chunk scored
    # 0.612 cosine while a nonsense one scored 0.461, so 0.45 answered the
    # nonsense. 0.55 rejects it and keeps the real match.
    retrieval_min_similarity: float = 0.55
    # only used when no vector signal exists at all (EMBED_PROVIDER=none)
    retrieval_min_ts_rank: float = 0.30

    # llm (M3+)
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = ""
    llm_api_key: str = ""

    # api
    api_port: int = 8080

    @property
    def configured_source_types(self) -> frozenset[str]:
        return frozenset(
            part.strip().lower()
            for part in self.sync_source_types.split(",")
            if part.strip()
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
