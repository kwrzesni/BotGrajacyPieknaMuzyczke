from pathlib import Path
from memory_utils import from_human_size_to_bytes
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    token: str
    tracks_dir: Path
    tracks_dir_max_size: int
    guild_configs_dir: Path
    downloaded_track_info_db: Path
    lavalink_dir: Path
    cookies_file: Path
    temp_downloads_dir: Path
    logs_path: Path
    debug: bool

    # noinspection PyNestedDecorators
    @field_validator("tracks_dir_max_size", mode="before")
    @classmethod
    def validate_tracks_dir_max_size(cls, value: str) -> int:
        return from_human_size_to_bytes(value)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
