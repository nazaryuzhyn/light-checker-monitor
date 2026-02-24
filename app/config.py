from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str
    ESP_API_KEY: str
    PING_TIMEOUT: int = 60

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
