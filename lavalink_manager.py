import socket
import subprocess
import psutil
import requests
import wavelink
import yaml
from enum import Enum
from pathlib import Path


class State(Enum):
    STARTING = "starting"
    READY = "ready"
    RESTARTING = "restarting"
    UPDATING = "updating"


class LavalinkManager:
    NODE_IDENTIFIER = "Node1"
    CONFIG_FILE_NAME = "application.yml"
    REPO_LINK = "https://api.github.com/repos/lavalink-devs/youtube-source"

    def __init__(self, lavalink_dir_path: Path):
        self.dir_path = lavalink_dir_path
        self.config_path = self.dir_path / self.CONFIG_FILE_NAME
        self.process = None
        self.node = None
        self.config = self.read_config()
        self.state = State.STARTING
        self.procedure = "none"

    def read_config(self):
        with open(self.config_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)

    def write_config(self):
        with open(self.config_path, "w", encoding="utf-8") as file:
            return yaml.safe_dump(self.config, file)

    def start_process(self):
        if self.process is not None:
            return
        self.process = subprocess.Popen(["java", "-jar", "Lavalink.jar"],
                                        cwd=self.dir_path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def kill_process(self):
        if self.process is None:
            return
        try:
            self.process.kill()
        except Exception:
            pass
        self.process = None
        self.node = None

    def restart_process(self):
        try:
            self.kill_process()
            self.start_process()
        except Exception:
            pass

    def get_endpoint(self):
        return self.config["server"]["address"], self.config["server"]["port"]

    def get_password(self):
        return self.config["lavalink"]["server"]["password"]

    def get_youtube_plugin_info(self):
        return next(plugin for plugin in self.config["lavalink"]["plugins"] if "youtube-plugin" in plugin["dependency"])

    def get_youtube_plugin_version(self):
        info = self.get_youtube_plugin_info()
        return info["dependency"].split(":")[-1], info["snapshot"]

    def set_youtube_plugin_version(self, version: str, snapshot: bool):
        info = self.get_youtube_plugin_info()
        prefix, _, _ = info["dependency"].rpartition(":")
        info["dependency"] = f"{prefix}:{version}"
        info["snapshot"] = snapshot
        self.write_config()

    def get_youtube_plugin_commits(self):
        url = f"{self.REPO_LINK}/commits"
        response = requests.get(url, headers={"Accept": "application/vnd.github.v3+json"})
        if response.status_code != 200:
            return [], response.status_code
        return [commit["sha"] for commit in response.json()], response.status_code

    def set_youtube_plugin_commit(self, commit):
        self.set_youtube_plugin_version(commit, True)

    def get_youtube_plugin_releases(self):
        url = f"{self.REPO_LINK}/tags"
        response = requests.get(url, headers={"Accept": "application/vnd.github.v3+json"})
        if response.status_code != 200:
            return [], response.status_code
        return [(tag["name"], tag["commit"]["sha"]) for tag in response.json()], response.status_code

    def set_youtube_plugin_release(self, release):
        self.set_youtube_plugin_version(release, False)

    async def connect_node(self, client):
        ip, port = self.get_endpoint()
        password = self.get_password()
        if self.node is None:
            self.node = wavelink.Node(
                identifier=self.NODE_IDENTIFIER,
                uri=f"http://{ip if ip != '0.0.0.0' else socket.gethostbyname(socket.gethostname())}:{port}",
                password=password
            )
            await wavelink.Pool.connect(nodes=[self.node], client=client)
        else:
            await wavelink.Pool.reconnect()
