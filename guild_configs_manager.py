import json
import os
from pathlib import Path
from discord import Guild


class GuildConfig:
    DEFAULT_AUTOPLAY: bool = False
    MIN_SPEED: float = 0.0
    MAX_SPEED = 10.0
    DEFAULT_SPEED = 1.0
    MIN_PITCH = 0.0
    MAX_PITCH = 10.0
    DEFAULT_PITCH = 1.0
    MIN_RATE = 0.0
    MAX_RATE = 10.0
    DEFAULT_RATE = 1.0

    def __init__(self, path: Path):
        self.recommended_song = None
        self.channel_to_respond = None
        self.autoplay = self.DEFAULT_AUTOPLAY
        self.speed = self.DEFAULT_SPEED
        self.pitch = self.DEFAULT_PITCH
        self.rate = self.DEFAULT_RATE
        self.path = path
        if self.path.exists() and self.path.is_file():
            self.read()
        else:
            self.write()

    def read(self):
        with open(self.path, encoding="utf-8") as file:
            data = json.load(file)
            self.autoplay = data.get("autoplay", self.DEFAULT_AUTOPLAY)
            self.set_speed(data.get("speed", self.DEFAULT_SPEED))
            self.set_pitch(data.get("pitch", self.DEFAULT_PITCH))
            self.set_rate(data.get("speed", self.DEFAULT_PITCH))

    def to_json(self):
        out = {
            "autoplay": self.autoplay,
            "speed": self.speed,
            "pitch": self.pitch,
            "rate": self.rate
        }
        return json.dumps(out)

    def write(self):
        with open(self.path, "w", encoding="utf-8") as file:
            file.write(self.to_json())

    def toggle_autoplay(self):
        self.autoplay = not self.autoplay
        if not self.autoplay:
            self.recommended_song = None
        self.write()

    def set_speed(self, speed):
        self.speed = max(self.MIN_SPEED, min(speed, self.MAX_SPEED))
        self.write()

    def set_pitch(self, pitch):
        self.pitch = max(self.MIN_PITCH, min(pitch, self.MAX_PITCH))
        self.write()

    def set_rate(self, rate):
        self.rate = max(self.MIN_RATE, min(rate, self.MAX_RATE))
        self.write()

    def reset(self):
        self.autoplay = self.DEFAULT_AUTOPLAY
        self.speed = self.DEFAULT_SPEED
        self.pitch = self.DEFAULT_PITCH
        self.rate = self.DEFAULT_RATE
        self.write()

    def set_as_default(self):
        self.DEFAULT_AUTOPLAY = self.autoplay
        self.DEFAULT_SPEED = self.speed
        self.DEFAULT_PITCH = self.pitch
        self.DEFAULT_RATE = self.rate

    def __str__(self):
        return str(self.to_json())

    __repr__ = __str__


class GuildConfigsManager:
    DEFAULT_CONF_FILE_NAME: str = 'default.json'

    def __init__(self, config_path: Path, ):
        self.config_path = config_path
        self.default_config_path = config_path / self.DEFAULT_CONF_FILE_NAME
        self.guilds_path = self.config_path / 'guilds'
        self.configs = {}

        config_path.mkdir(parents=True, exist_ok=True)
        config_path / self.DEFAULT_CONF_FILE_NAME
        GuildConfig(self.default_config_path).set_as_default()
        self.guilds_path.mkdir(exist_ok=True)

    def fill_guild_configs(self, guilds: list[Guild]):
        self.configs = {guild: GuildConfig(self.guilds_path / f"{guild.id}.json") for guild in guilds}

    def clear_removed_guild(self, guilds: list[Guild]):
        joined_guilds_file_names = [f"{guild.id}.json" for guild in guilds]
        for file_name in os.listdir(self.guilds_path):
            file_name = str(file_name)
            if file_name not in joined_guilds_file_names:
                os.remove(self.guilds_path / file_name)

    def add_guild(self, guild: Guild):
        self.configs[guild] = GuildConfig(self.guilds_path / f"{guild.id}.json")

    def remove_guild(self, guild: Guild):
        if guild in self.configs:
            del self.configs[guild]
        os.remove(self.guilds_path / f"{guild.id}.json")

    def __getitem__(self, guild: Guild) -> GuildConfig:
        return self.configs[guild]

    def __iter__(self):
        return iter(self.configs.values())
