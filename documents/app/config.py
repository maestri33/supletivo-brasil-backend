from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "documents-service"
    env: str = "dev"
    log_level: str = "INFO"
    database_url: str = "sqlite:///root/documents.db"
    port: int = 80
    media_root: str = "/root/media"
    max_upload_mb: int = 10
    webhook_url: str = "http://10.10.10.129"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
