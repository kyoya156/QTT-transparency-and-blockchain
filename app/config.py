from pydantic_settings import BaseSettings, SettingsConfigDict
import pathlib

_ENV = pathlib.Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    # Khong dat gia tri mac dinh cho secret/DSN trong code: khai bao trong .env
    database_url: str = ""
    crawler_url: str = "http://host.docker.internal:8000"
    crawler_api_key: str = ""
    sync_page_size: int = 500
    sync_timeout: float = 30.0
    # Neu 1 lan sync se xoa nhieu hon ti le nay so chunk hien co -> huy (tranh mat du lieu khi crawler loi)
    sync_max_delete_ratio: float = 0.5
    embed_dim: int = 1536
    embed_model: str = "text-embedding-3-small"
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = ""

    model_config = SettingsConfigDict(env_file=str(_ENV), extra="ignore")


settings = Settings()
