import os
import re
import sqlite3
import unicodedata
import discord
import yt_dlp
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from pydub import AudioSegment


python_type_to_sql_type = {float: "FLOAT",
                           int: "INTEGER",
                           str: "TEXT",
                           bool: "INTEGER (0/1)"}


@dataclass
class TrackInfo:
    file_name: str
    video_id: str
    title: str
    thumbnail_url: str
    duration: int


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[|\"'\U00010000-\U0010FFFF]", "", normalized).strip()
    return re.sub(r"\s+", " ", normalized)


class TracksManager:
    TABLE_NAME = "tracks"
    QUIET = False
    NO_PLAYLIST = True

    def __init__(self,
                 db_path: Path,
                 tracks_dir_path: Path,
                 tracks_dir_max_size: int,
                 cookies_file: Path,
                 temp_downloads_dir: Path):
        self.conn = sqlite3.connect(db_path)
        track_info_fields = fields(TrackInfo)
        create_quarry = f"""CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} \
                        ({track_info_fields[0].name} {python_type_to_sql_type[track_info_fields[0].type]} PRIMARY KEY"""
        for field in track_info_fields[1:]:
            create_quarry += f",{field.name} {python_type_to_sql_type[field.type]}"
        create_quarry += ")"
        self.conn.execute(create_quarry)
        self.conn.commit()
        self.tracks_dir_path = tracks_dir_path
        if not tracks_dir_path.exists():
            tracks_dir_path.mkdir(parents=True, exist_ok=True)
        self.tracks_dir_max_size = tracks_dir_max_size
        self.cookies_file = cookies_file
        self.temp_downloads_dir = temp_downloads_dir
        if not temp_downloads_dir.exists():
            temp_downloads_dir.mkdir(parents=True, exist_ok=True)

    def insert(self, track_info: TrackInfo):
        track_info_dict = asdict(track_info)
        self.conn.execute(
            f"INSERT INTO {self.TABLE_NAME} {tuple(track_info_dict.keys())} "
            f"VALUES ({', '.join('?' * len(track_info_dict))})",
            tuple(track_info_dict.values())
        )
        self.conn.commit()

    def read_by_file_name(self, file_name: str):
        cur = self.conn.execute(
            f"SELECT * FROM {self.TABLE_NAME} WHERE file_name=?", (file_name,)
        )
        row = cur.fetchone()
        return TrackInfo(*row) if row else None

    def read_by_video_id(self, video_id: str):
        cur = self.conn.execute(
            f"SELECT * FROM {self.TABLE_NAME} WHERE video_id=?", (video_id,)
        )
        row = cur.fetchone()
        return TrackInfo(*row) if row else None

    def read_by_youtube_url(self, url: str):
        return self.read_by_video_id(self.youtube_url_to_video_id(url))

    def delete(self, file_name):
        self.conn.execute(
            f"DELETE FROM {self.TABLE_NAME} WHERE file_name=?", (file_name,)
        )
        self.conn.commit()

    def file_name_exists(self, file_name: str):
        cur = self.conn.execute(
            f"SELECT EXISTS(SELECT 1 FROM {self.TABLE_NAME} WHERE file_name = ?)",
            (file_name,)
        )
        return bool(cur.fetchone()[0])

    def video_id_exists(self, video_id: str):
        cur = self.conn.execute(
            f"SELECT EXISTS(SELECT 1 FROM {self.TABLE_NAME} WHERE video_id = ?)",
            (video_id,)
        )
        return bool(cur.fetchone()[0])

    def change_file_name(self, old_file_name: str, new_file_name: str):
        self.conn.execute(
            f"UPDATE {self.TABLE_NAME} SET file_name=? WHERE file_name=?",
            (new_file_name, old_file_name)
        )
        self.conn.commit()

    def close(self):
        self.conn.close()

    def track_exists(self, file_name):
        return file_name in os.listdir(self.tracks_dir_path)

    def rename_track(self, old_file_name, new_file_name):
        os.rename(self.tracks_dir_path / old_file_name, self.tracks_dir_path / new_file_name)
        self.change_file_name(old_file_name, new_file_name)

    def remove_track(self, file_name):
        os.remove(self.tracks_dir_path / file_name)
        self.delete(file_name)

    def get_memory_usage(self):
        total_size = 0
        for root, dirs, files in os.walk(self.tracks_dir_path):
            for filename in files:
                filepath = os.path.join(root, filename)
                total_size += os.path.getsize(filepath)
        return total_size

    def is_full(self):
        return self.get_memory_usage() >= self.tracks_dir_max_size

    def get_track_names(self):
        return sorted(os.listdir(self.tracks_dir_path))

    def download_from_youtube(self, url: str, file_name: str = ""):
        if not self.is_youtube_url(url):
            raise ValueError("Uznaję tylko linki do jutjuba")

        if self.is_playlist_url(url):
            raise ValueError("Nie będę pobierał playlisty bo to dużo roboty i mi się nie chcę")

        video_id = self.youtube_url_to_video_id(url)
        if video_id is None:
            raise ValueError("Link nie zawiera video id")

        track_info = self.read_by_video_id(video_id)
        if self.video_id_exists(video_id):
            raise ValueError(f'Już kiedyś pobrałem ten utwór i nazwałem go "{track_info.file_name}"')

        info_dict = yt_dlp.YoutubeDL().extract_info(url, download=False)
        if not file_name:
            file_name = normalize_text(info_dict.get("title", ""))

        if not file_name:
            raise ValueError(f"Jak mam zapisać plik o pustej nazwie")

        if self.track_exists(file_name):
            raise ValueError(f"Już posiadam utwór o nazwie {file_name}")

        if self.is_full():
            raise ValueError("Mam już pełny brzuszek i nie będe nic więcej pobierał")

        ydl_opts = {"paths": {"home": str(self.temp_downloads_dir)},
                    "post_hooks": [lambda downloaded_file_path: self.hook(file_name, Path(downloaded_file_path))],
                    "quiet": str(self.QUIET),
                    "noplaylist": str(self.NO_PLAYLIST)}
        ydl = yt_dlp.YoutubeDL(ydl_opts)
        ydl.download([url])
        self.insert(TrackInfo(file_name,
                              video_id,
                              info_dict.get("title", "unknown title"),
                              info_dict.get("thumbnail", ""),
                              1000 * info_dict.get("duration", 0)))

    async def download_from_discord(self, file: discord.Attachment):
        if self.track_exists(file.filename):
            raise ValueError(f"Już posiadam utwór o nazwie {file.filename}")
        download_path = self.temp_downloads_dir / file.filename
        await file.save(download_path)
        self.process_downloaded_track(download_path, file.filename)

    def track_info_from_url(self, url):
        video_id = self.youtube_url_to_video_id(url)
        return self.read_by_video_id(video_id) if video_id is not None else None

    def search_track(self, search):
        file_names = [file_name for file_name in os.listdir(self.tracks_dir_path) if file_name.startswith(search)]
        if not file_names:
            return None
        file_name = str(sorted(file_names)[0])
        track_info = self.read_by_file_name(file_name)
        if track_info is not None:
            return track_info
        return TrackInfo(file_name, "", file_name, "", 0)

    @staticmethod
    def youtube_url_to_video_id(url):
        match = re.search("((youtu.be/)|([?&]v=))([a-zA-Z0-9_-]+)", url)
        return match.group(4) if match is not None else None

    @staticmethod
    def video_id_to_youtube_url(video_id):
        return f"https://www.youtube.com/watch?v={video_id}" if video_id else None

    @staticmethod
    def is_youtube_url(url):
        return "youtube" in url or "youtu.be" in url

    @staticmethod
    def is_playlist_url(url):
        return "&list" in url

    def hook(self, file_name: str, downloaded_file_path: Path):
        self.process_downloaded_track(downloaded_file_path, file_name)

    def process_downloaded_track(self, downloaded_file_path, file_name):
        try:
            audio = AudioSegment.from_file(downloaded_file_path)
            temp_file_name = f"_{file_name}.mp3"
            audio.export(self.temp_downloads_dir / temp_file_name, format="mp3")
            os.rename(self.temp_downloads_dir / temp_file_name, self.tracks_dir_path / file_name)
        finally:
            os.remove(downloaded_file_path)
