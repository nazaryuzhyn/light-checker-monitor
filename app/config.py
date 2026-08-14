from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str
    ESP_API_KEY: str

    # Seconds of ESP silence that count as a possible outage.
    PING_TIMEOUT: int = 60

    # Outage groups from the feed. The first one is the household the bot
    # reports on; the rest are kept for reference.
    OUTAGE_GROUPS: list[str] = ["GPV5.2"]

    SCHEDULE_URL: str = (
        "https://raw.githubusercontent.com/yaroslav2901/OE_OUTAGE_DATA"
        "/main/data/Ternopiloblenerho.json"
    )

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def outage_group(self) -> str | None:
        return self.OUTAGE_GROUPS[0] if self.OUTAGE_GROUPS else None


settings = Settings()
