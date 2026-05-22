from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    FILESERVER_URL: str = "http://fileserver:9000"
    UDP_HOST: str = "0.0.0.0"
    UDP_PORT: int = 9001

    model_config = {"env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
