import discord
import wavelink
import typing
import dotenv
import os
import pathlib
import yt_dlp
import subprocess
import requests
from moviepy import VideoFileClip
from discord.ext import commands
import re


def human_size(size):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024


def from_human_size_to_bytes(size: str):
    ind = 0
    while ind < len(size) and size[ind].isdigit():
        ind += 1
    value = int(size[:ind]) if ind != 0 else 0
    unit = size[ind:].upper().strip()
    if unit == "TB":
        return value * (1024 ** 4)
    if unit == "GB":
        return value * (1024 ** 3)
    if unit == "MB":
        return value * (1024 ** 2)
    if unit == "KB":
        return value * (1024 ** 1)
    return value


dotenv.load_dotenv()
TOKEN = str(os.getenv("TOKEN"))
TRACKS_DIR = str(os.getenv("TRACKS_DIR"))
TRACKS_DIR_MAX_SIZE = from_human_size_to_bytes(os.getenv("TRACKS_DIR_MAX_SIZE"))
CONFIGURATIONS_DIR = str(os.getenv("CONFIGURATION_DIR"))
DOWNLOADS_FILE = str(os.getenv("DOWNLOADS_FILE"))
LAVALINK_DIR = str(os.getenv("LAVALINK_DIR"))
COOKIES_PATH = str(os.getenv("COOKIES_PATH"))
LAVALINK_REPO = "https://api.github.com/repos/lavalink-devs/youtube-source"
MAX_PLAYLIST_EMBED_SIZE = 5
MAX_QUEUE_EMBED_SIZE = 7
MAX_LIST_SIZE = 20

bot = commands.Bot()
recomended_songs = {}
channel_to_respond = {}
configurations = {}
lavalink_process = None
lavalink_subprocess_pid = None
wavelink_node = None
lavalink_ready = False


def start_lavalink_process():
    return subprocess.Popen(["java", "-jar", "Lavalink.jar"], cwd=LAVALINK_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Configuration:
    DEFAULT_AUTOPLAY = False
    MIN_SPEED = 0.0
    MAX_SPEED = 10.0
    DEFAULT_SPEED = 1.0
    MIN_PITCH = 0.0
    MAX_PITCH = 10.0
    DEFAULT_PITCH = 1.0
    MIN_RATE = 0.0
    MAX_RATE = 10.0
    DEFAULT_RATE = 1.0

    def __init__(self, path):
        self.autoplay = Configuration.DEFAULT_AUTOPLAY
        self.speed = Configuration.DEFAULT_SPEED
        self.pitch = Configuration.DEFAULT_PITCH
        self.rate = Configuration.DEFAULT_RATE
        self.path = path
        self.read()

    def read(self):
        if not os.path.exists(self.path):
            self.write()
            return
        with open(self.path, "r") as file:
            for line in file.readlines():
                items = line.split("=")
                key, value = items[0].strip().lower(), items[1].strip().lower()
                if key == "autoplay":
                    self.autoplay = True if value == "true" else False
                elif key == "speed":
                    self.speed = max(Configuration.MIN_SPEED, min(float(value), Configuration.MAX_SPEED))
                elif key == "pitch":
                    self.pitch = max(Configuration.MIN_PITCH, min(float(value), Configuration.MAX_PITCH))
                elif key == "rate":
                    self.rate = max(Configuration.MIN_RATE, min(float(value), Configuration.MAX_RATE))

    def write(self):
        with open(self.path, "w") as file:
            file.write(str(self))

    def __str__(self):
        return f"autoplay = {'true' if self.autoplay else 'false'}\n" \
               f"speed = {self.speed}\n" \
               f"pitch = {self.pitch}\n" \
               f"rate = {self.rate}\n"

    def toggle_autoplay(self):
        self.autoplay = not self.autoplay
        self.write()

    def set_speed(self, speed):
        self.speed = max(Configuration.MIN_SPEED, min(speed, Configuration.MAX_SPEED))
        self.write()

    def set_pitch(self, pitch):
        self.pitch = max(Configuration.MIN_PITCH, min(pitch, Configuration.MAX_PITCH))
        self.write()

    def set_rate(self, rate):
        self.rate = max(Configuration.MIN_RATE, min(rate, Configuration.MAX_RATE))
        self.write()

    def set_as_default(self):
        Configuration.DEFAULT_AUTOPLAY = self.autoplay
        Configuration.DEFAULT_SPEED = self.speed
        Configuration.DEFAULT_PITCH = self.pitch
        Configuration.DEFAULT_RATE = self.rate

    def reset(self):
        self.autoplay = Configuration.DEFAULT_AUTOPLAY
        self.speed = Configuration.DEFAULT_SPEED
        self.pitch = Configuration.DEFAULT_PITCH
        self.rate = Configuration.DEFAULT_RATE
        self.write()


def get_ip_address():
    key1 = "address:"
    key2 = "port:"
    with open(os.path.join(LAVALINK_DIR, "application.yml"), "r") as file:
        data = file.read()
    start1 = data.find(key1) + len(key1)
    end1 = data.find("\n", start1)
    start2 = data.find(key2) + len(key2)
    end2 = data.find("\n", start2)
    return data[start1:end1].strip(), data[start2:end2].strip()


async def connect_nodes():
    await bot.wait_until_ready()
    ip, port = get_ip_address()

    global wavelink_node
    if wavelink_node is None:
        wavelink_node = wavelink.Node(
            identifier="Node1",
            uri=f"http://127.0.0.1:{port}",
            password="youshallnotpass"
        )
        await wavelink.Pool.connect(nodes=[wavelink_node], client=bot)
    else:
        await wavelink.Pool.reconnect()


async def disconnect_nodes():
    global wavelink_node
    if wavelink_node is None:
        return

    await bot.wait_until_ready()
    await wavelink_node.close()


def is_link_to_playlist(link):
    return "&list" in link


def format_link(link):
    if is_link_to_playlist(link):
        return link
    key = "youtu.be/"
    if key in link:
        start = link.find(key) + len(key)
        end = link.find("?", start)
        return f"https://www.youtube.com/watch?v={link[start:end] if end != -1 else link[start:]}"
    key = "youtube"
    if key in link:
        key = "?v="
        start = link.find(key) + len(key)
        end = link.find("&", start)
        return f"https://www.youtube.com/watch?v={link[start:end] if end != -1 else link[start:]}"
    return link


def get_memory_usage():
    total_size = 0
    for root, dirs, files in os.walk(TRACKS_DIR):
        for filename in files:
            filepath = os.path.join(root, filename)
            total_size += os.path.getsize(filepath)
    return total_size


def created_downloads_file_if_not_exist():
    if not os.path.isfile(DOWNLOADS_FILE):
        open(DOWNLOADS_FILE, "a").close()


def add_downloaded(url, name, info_dict):
    created_downloads_file_if_not_exist()
    url = url
    name = name
    title = info_dict["title"] if "title" in info_dict else ""
    artwork = info_dict["thumbnail"] if "thumbnail" in info_dict else ""
    length = 1000 * info_dict["duration"] if "duration" in info_dict else 0
    with open(DOWNLOADS_FILE, "a", encoding="utf-8") as file:
        file.write(f"{url};{name};{title};{artwork};{length}\n")


def get_downloaded_by_name(name):
    created_downloads_file_if_not_exist()
    with open(DOWNLOADS_FILE, "r", encoding="utf-8") as file:
        for line in file.readlines():
            line = line.strip()
            if line.split(";")[1] == name:
                return line
    return None


def get_downloaded_by_url(url):
    created_downloads_file_if_not_exist()
    with open(DOWNLOADS_FILE, "r", encoding="utf-8") as file:
        for line in file.readlines():
            line = line.strip()
            if line.split(";")[0] == url:
                return line
    return None


def change_downloaded(old_name, new_name):
    created_downloads_file_if_not_exist()
    out = ""
    with open(DOWNLOADS_FILE, "r", encoding="utf-8") as file:
        for line in file.readlines():
            line = line.strip()
            tokens = line.split(";")
            if tokens[1] == old_name:
                tokens[1] = new_name
                out += ";".join(tokens) + "\n"
            else:
                out += line + "\n"
    with open(DOWNLOADS_FILE, "w", encoding="utf-8") as file:
        file.write(out)


def remove_downloaded(name):
    created_downloads_file_if_not_exist()
    out = ""
    with open(DOWNLOADS_FILE, "r", encoding="utf-8") as file:
        for line in file.readlines():
            line = line.strip()
            if line.split(";")[1] != name:
                out += line + "\n"
    with open(DOWNLOADS_FILE, "w", encoding="utf-8") as file:
        file.write(out)


def create_one_line_embed(text):
    return discord.Embed(title=text, color=discord.Colour.blurple())


def create_embed_from_song(song, title, author):
    seconds = song.length // 1000
    embed = discord.Embed(
        title=title,
        description=f"[{song.title}]({song.uri})" if song.uri is not None else f"{song.title}",
        color=discord.Colour.blurple(),
    )
    embed.set_image(url=song.artwork)
    embed.add_field(name="Na prośbę", value=f"{author.mention}", inline=True)
    embed.add_field(name="Czas", value=f"{seconds // 60}:{seconds % 60:02d}", inline=True)
    return embed


def create_embed_from_playlist(playlist, title, author, search):
    selected_song = playlist.tracks[playlist.selected]
    embed = discord.Embed(
        title=title,
        description=f"[{playlist.name}]({search})",
        color=discord.Colour.blurple(),
    )
    embed.set_image(url=selected_song.artwork)
    embed.add_field(name="Na prośbę", value=f"{author.mention}", inline=True)
    embed.add_field(name="Ind", value=f"{playlist.selected + 1}", inline=True)
    embed.add_field(name="Rozmiar", value=f"{len(playlist.tracks)}", inline=True)

    embed.add_field(name="Id", value="", inline=True)
    embed.add_field(name="Tytuł", value="", inline=True)
    embed.add_field(name="Czas", value="", inline=True)
    for i in range(playlist.selected, min(playlist.selected + MAX_PLAYLIST_EMBED_SIZE, len(playlist.tracks))):
        embed.add_field(name="", value=f"{i + 1}", inline=True)
        embed.add_field(name="", value=f"[{playlist.tracks[i].title}]({playlist.tracks[i].uri})", inline=True)
        seconds = playlist.tracks[i].length // 1000
        embed.add_field(name="", value=f"{seconds // 60}:{seconds % 60:02d}", inline=True)
    return embed


def get_lavalink_version():
    key1 = "dev.lavalink.youtube:youtube-plugin:"
    key2 = "snapshot:"
    with open(os.path.join(LAVALINK_DIR, "application.yml"), "r") as file:
        data = file.read()
    start1 = data.find(key1) + len(key1)
    end1 = data.find("\"", start1)
    start2 = data.find(key2, end1) + len(key2)
    end2 = data.find("\n", start2)
    return data[start1:end1].strip(), data[start2:end2].strip()


def set_lavalink_version(version, is_snapshot):
    key1 = "dev.lavalink.youtube:youtube-plugin:"
    key2 = "snapshot:"
    with open(os.path.join(LAVALINK_DIR, "application.yml"), "r") as file:
        data = file.read()
    start1 = data.find(key1)
    end1 = data.find("\n", start1)
    start2 = data.find(key2, end1)
    end2 = data.find("\n", start2)

    data = data[:start1] + f"{key1}{version}\"" + data[end1:start2] + f"{key2} {'true' if is_snapshot else 'false'}" + data[end2:]
    with open(os.path.join(LAVALINK_DIR, "application.yml"), "w") as file:
        file.write(data)


def get_lavalink_commits():
    url = f"{LAVALINK_REPO}/commits"
    response = requests.get(url, headers={"Accept": "application/vnd.github.v3+json"})
    if response.status_code != 200:
        return [], response.status_code
    return [commit["sha"] for commit in response.json()], response.status_code


def get_lavalink_releases():
    url = f"{LAVALINK_REPO}/tags"
    response = requests.get(url, headers={"Accept": "application/vnd.github.v3+json"})
    if response.status_code != 200:
        return [], response.status_code
    return [(tag["name"], tag["commit"]["sha"]) for tag in response.json()], response.status_code


async def handle_song(vc, guild, song, isPlaying):
    if isPlaying:
        vc.queue.put(song)
    else:
        if configurations[guild].autoplay:
            await vc.play(song, populate=True, max_populate=1)
            if vc.auto_queue:
                recomended_songs[guild] = vc.auto_queue[0]
                vc.auto_queue.clear()
        else:
            await vc.play(song)


@bot.slash_command(name="play")
async def play(ctx: discord.ApplicationContext, search: str):
    if not lavalink_ready:
        return await ctx.send_response("", embed=create_one_line_embed("Spokojnie jeszcze nie wszystko gotowe"))

    search = format_link(search)
    if ctx.author.voice is None:
        return await ctx.send_response("", embed=create_one_line_embed("Nie ma cię na kanale debilu"))

    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is not None and vc.channel.id != ctx.author.voice.channel.id:
        return await ctx.send_response("", embed=create_one_line_embed("Jesteś na innym kanale niż ja bandyto"))

    msg = await ctx.send_response("", embed=create_one_line_embed("..."))

    configuration = configurations[ctx.guild]
    record = get_downloaded_by_url(search)
    if record is not None:
        name = record.split(";")[1]
        songs = await wavelink.Playable.search(os.path.join(TRACKS_DIR, name), source=None)
        channel_to_respond[ctx.guild] = ctx.channel
        if not vc:
            vc = await ctx.author.voice.channel.connect(cls=wavelink.Player)
            vc.autoplay = wavelink.AutoPlayMode.disabled
            vc.filters.timescale.set(speed=configuration.speed, pitch=configuration.pitch, rate=configuration.rate)
        isPlaying = vc.playing
        tokens = record.split(";")
        song = songs[0]
        song._uri = tokens[0]
        song._title = tokens[2]
        song._artwork = tokens[3]
        song._length = int(tokens[4])
        await handle_song(vc, ctx.guild, song, isPlaying)
        return await msg.edit(embed=create_embed_from_song(song, "Gram" if not isPlaying else "Kolejkuję", ctx.author))

    songs = await wavelink.Playable.search(search)
    if not songs:
        return await msg.edit(embed=create_one_line_embed("Nie znalazłem twego utworu"))

    channel_to_respond[ctx.guild] = ctx.channel
    if not vc:
        vc = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        vc.autoplay = wavelink.AutoPlayMode.disabled
        vc.filters.timescale.set(speed=configuration.speed, pitch=configuration.pitch, rate=configuration.rate)
    isPlaying = vc.playing
    if songs[0].playlist is None:
        song = songs[0]
        try:
            await handle_song(vc, ctx.guild, song, isPlaying)
        except Exception as e:
            print(e)
        return await msg.edit(embed=create_embed_from_song(song, "Gram" if not isPlaying else "Kolejkuję", ctx.author))
    for i in range(songs.selected, len(songs)):
        await handle_song(vc, ctx.guild, songs[i], isPlaying)
        isPlaying = True
    return await msg.edit(embed=create_embed_from_playlist(songs, "Gram" if not isPlaying else "Kolejkuję", ctx.author, search))


@bot.slash_command(name="fplay")
async def fplay(ctx: discord.ApplicationContext, search: str):
    if not lavalink_ready:
        return await ctx.send_response("", embed=create_one_line_embed("Spokojnie jeszcze nie wszystko gotowe"))

    if ctx.author.voice is None:
        return await ctx.send_response("", embed=create_one_line_embed("Nie ma cię na kanale debilu"))

    configuration = configurations[ctx.guild]
    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is not None and vc.channel.id != ctx.author.voice.channel.id:
        return await ctx.send_response("", embed=create_one_line_embed("Jesteś na innym kanale niż ja bandyto"))

    candidates = []
    for file in os.listdir(TRACKS_DIR):
        if file.find(search) == 0:
            candidates.append(file)
    songs = None
    if candidates:
        candidates.sort()
        songs = await wavelink.Playable.search(os.path.join(TRACKS_DIR, candidates[0]), source=None)
    if not songs:
        return await ctx.send_response("", embed=create_one_line_embed("Nie znalazłem twego utworu"))

    channel_to_respond[ctx.guild] = ctx.channel
    if not vc:
        vc = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        vc.autoplay = wavelink.AutoPlayMode.disabled
        vc.filters.timescale.set(speed=configuration.speed, pitch=configuration.pitch, rate=configuration.rate)
    isPlaying = vc.playing
    song = songs[0]
    song._title = candidates[0]
    song._uri = None
    record = get_downloaded_by_name(candidates[0])
    if record is not None:
        tokens = record.split(";")
        song._uri = tokens[0]
        song._title = tokens[2]
        song._artwork = tokens[3]
        song._length = int(tokens[4])
    await handle_song(vc, ctx.guild, song, isPlaying)
    await ctx.send_response("",
                            embed=create_embed_from_song(song, "Gram" if not isPlaying else "Kolejkuję", ctx.author))


@bot.slash_command(name="pause")
async def pause(ctx: discord.ApplicationContext):
    vc = typing.cast(wavelink.Player, ctx.voice_client)

    if vc is None or not vc.playing:
        return await ctx.send_response("", embed=create_one_line_embed("Nawet nic nie gram gamoniu"))

    if ctx.author.voice is None or vc.channel.id != ctx.author.voice.channel.id:
        return await ctx.send_response("", embed=create_one_line_embed("Nie ma cię na tym samym kanale nicponiu"))

    await vc.pause(True)
    await ctx.send_response("", embed=create_one_line_embed(f"Zapałzowałem {vc.current.title}"))


@bot.slash_command(name="resume")
async def resume(ctx: discord.ApplicationContext):
    vc = typing.cast(wavelink.Player, ctx.voice_client)

    if vc is None or not vc.playing:
        return await ctx.send_response("", embed=create_one_line_embed("Nawet nic nie gram gamoniu"))

    if ctx.author.voice is None or vc.channel.id != ctx.author.voice.channel.id:
        return await ctx.send_response("", embed=create_one_line_embed("Nie ma cię na tym samym kanale nicponiu"))

    await vc.pause(False)
    await ctx.send_response("", embed=create_one_line_embed(f"Znowu gram {vc.current.title}"))


@bot.slash_command(name="skip")
async def skip(ctx: discord.ApplicationContext):
    vc = typing.cast(wavelink.Player, ctx.voice_client)

    if vc is None or not vc.playing:
        return await ctx.send_response("", embed=create_one_line_embed("Nawet nic nie gram gamoniu"))

    if ctx.author.voice is None or vc.channel.id != ctx.author.voice.channel.id:
        return await ctx.send_response("", embed=create_one_line_embed("Nie ma cię na tym samym kanale nicponiu"))

    title = vc.current.title
    await vc.skip()
    await ctx.send_response("", embed=create_one_line_embed(f"Wypierdalam {title}"))


@bot.slash_command(name="skipall")
async def skipall(ctx: discord.ApplicationContext):
    vc = typing.cast(wavelink.Player, ctx.voice_client)

    if vc is None or not vc.playing:
        return await ctx.send_response("", embed=create_one_line_embed("Nawet nic nie gram gamoniu"))

    if ctx.author.voice is None or vc.channel.id != ctx.author.voice.channel.id:
        return await ctx.send_response("", embed=create_one_line_embed("Nie ma cię na tym samym kanale nicponiu"))

    vc.queue.clear()
    await vc.skip()
    await ctx.send_response("", embed=create_one_line_embed("Wypierdalam wszystko"))


@bot.slash_command(name="nskip")
async def nskip(ctx: discord.ApplicationContext, n: int):
    vc = typing.cast(wavelink.Player, ctx.voice_client)

    if vc is None or not vc.playing:
        return await ctx.send_response("", embed=create_one_line_embed("Nawet nic nie gram gamoniu"))

    if ctx.author.voice is None or vc.channel.id != ctx.author.voice.channel.id:
        return await ctx.send_response("", embed=create_one_line_embed("Nie ma cię na tym samym kanale nicponiu"))

    n = max(1, n)
    n = min(n, len(vc.queue) + 1)
    for i in range(n - 1):
        vc.queue.delete(0)
    title = vc.current.title
    await vc.skip()
    if n == 1:
        await ctx.send_response("", embed=create_one_line_embed(f"Wypierdalam {title}"))
    else:
        await ctx.send_response("", embed=create_one_line_embed(f"Wypierdalam {n} piosenek"))


@bot.slash_command(name="queue")
async def queue(ctx: discord.ApplicationContext, n: int = 1):
    n = max(1, n)
    n = n - 1
    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is None:
        size = 0
    else:
        size = len(vc.queue)

    if size == 0:
        embed = discord.Embed(
            title=f"Kolejka[0] 0/0",
            color=discord.Colour.blurple(),
        )
        embed.add_field(name="Id", value="", inline=True)
        embed.add_field(name="Tytuł", value="", inline=True)
        embed.add_field(name="Czas", value="", inline=True)
        return await ctx.send_response("", embed=embed)

    startInd = n * MAX_QUEUE_EMBED_SIZE
    if startInd >= size:
        startInd = max(0, size - 1 - (size - 1) % MAX_QUEUE_EMBED_SIZE)
    endInd = min(startInd + MAX_QUEUE_EMBED_SIZE, size)
    n = startInd // MAX_QUEUE_EMBED_SIZE

    embed = discord.Embed(
        title=f"Kolejka[{size}] {n + 1}/{(size - 1) // MAX_QUEUE_EMBED_SIZE + 1}",
        color=discord.Colour.blurple(),
    )
    embed.add_field(name="Id", value="", inline=True)
    embed.add_field(name="Tytuł", value="", inline=True)
    embed.add_field(name="Czas", value="", inline=True)

    for i in range(startInd, endInd):
        embed.add_field(name="", value=f"{i + 1}", inline=True)
        embed.add_field(name="", value=f"[{vc.queue[i].title}]({vc.queue[i].uri})" if vc.queue[
                                                                                          i].uri is not None else f"{vc.queue[i].title}",
                        inline=True)
        seconds = vc.queue[i].length // 1000
        embed.add_field(name="", value=f"{seconds // 60}:{seconds % 60:02d}", inline=True)
    await ctx.send_response("", embed=embed)


@bot.slash_command(name="allqueue")
async def allqueue(ctx: discord.ApplicationContext):
    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is None:
        size = 0
    else:
        size = len(vc.queue)

    embed = discord.Embed(
        title=f"Kolejka[{size}]",
        color=discord.Colour.blurple(),
    )
    embed.add_field(name="Id", value="", inline=True)
    embed.add_field(name="Tytuł", value="", inline=True)
    embed.add_field(name="Czas", value="", inline=True)

    n = min(size, MAX_QUEUE_EMBED_SIZE)
    for i in range(n):
        embed.add_field(name="", value=f"{i + 1}", inline=True)
        embed.add_field(name="", value=f"[{vc.queue[i].title}]({vc.queue[i].uri})" if vc.queue[
                                                                                          i].uri is not None else f"{vc.queue[i].title}",
                        inline=True)
        seconds = vc.queue[i].length // 1000
        embed.add_field(name="", value=f"{seconds // 60}:{seconds % 60:02d}", inline=True)
    await ctx.send_response("", embed=embed)

    if size > MAX_QUEUE_EMBED_SIZE:
        for startInd in range(MAX_QUEUE_EMBED_SIZE, size, MAX_QUEUE_EMBED_SIZE):
            embed = discord.Embed(
                title="",
                color=discord.Colour.blurple(),
            )
            endInd = min(startInd + MAX_QUEUE_EMBED_SIZE, size)
            for i in range(startInd, endInd):
                embed.add_field(name="", value=f"{i + 1}", inline=True)
                embed.add_field(name="", value=f"[{vc.queue[i].title}]({vc.queue[i].uri})" if vc.queue[
                                                                                                  i].uri is not None else f"{vc.queue[i].title}",
                                inline=True)
                seconds = vc.queue[i].length // 1000
                embed.add_field(name="", value=f"{seconds // 60}:{seconds % 60:02d}", inline=True)
            await ctx.send_followup("", embed=embed)


@bot.slash_command(name="current")
async def current(ctx: discord.ApplicationContext):
    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is None or not vc.playing:
        return await ctx.send_response("", embed=create_one_line_embed("Nic nie gram parówo"))

    configuration = configurations[ctx.guild]
    song = vc.current
    seconds = song.length // 1000
    played_seconds = int(vc.position * configuration.speed * configuration.rate) // 1000
    embed = discord.Embed(
        title="Gram",
        description=f"[{song.title}]({song.uri})" if song.uri is not None else f"{song.title}",
        color=discord.Colour.blurple(),
    )
    embed.set_image(url=song.artwork)
    embed.add_field(name="Czas",
                    value=f"{played_seconds // 60}:{played_seconds % 60:02d}/{seconds // 60}:{seconds % 60:02d}",
                    inline=True)
    await ctx.send_response("", embed=embed)


@bot.slash_command(name="position")
async def position(ctx: discord.ApplicationContext):
    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is None or not vc.playing:
        return await ctx.send_response("", embed=create_one_line_embed("Nic nie gram parówo"))

    configuration = configurations[ctx.guild]
    song = vc.current
    seconds = song.length // 1000
    played_seconds = int(vc.position * configuration.speed * configuration.rate) // 1000
    await ctx.send_response("", embed=create_one_line_embed(
        f"Pozycja: {played_seconds // 60}:{played_seconds % 60:02d}/{seconds // 60}:{seconds % 60:02d}"))


@bot.slash_command(name="advance")
async def advance(ctx: discord.ApplicationContext, delta: int):
    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is None or not vc.playing:
        return await ctx.send_response("", embed=create_one_line_embed("Nic nie gram parówo"))

    if delta == 0:
        return await ctx.send_response("", embed=create_one_line_embed("Madke se zadvancuj o 0"))

    configuration = configurations[ctx.guild]
    song = vc.current
    delta = int(delta * 1000 / (
                configuration.speed * configuration.rate)) if configuration.speed * configuration.rate != 0 else delta * 1000
    new_position = max(0, min(vc.position + delta, song.length))
    await vc.seek(new_position)
    seconds = song.length // 1000
    played_seconds = int(new_position * configuration.speed * configuration.rate) // 1000
    await ctx.send_response("", embed=create_one_line_embed(
        f"Nowa pozycja: {played_seconds // 60}:{played_seconds % 60:02d}/{seconds // 60}:{seconds % 60:02d}"))


@bot.slash_command(name="autoplay")
async def autoplay(ctx: discord.ApplicationContext):
    configuration = configurations[ctx.guild]
    configuration.toggle_autoplay()
    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if not configuration.autoplay:
        recomended_songs[ctx.guild] = None

    await ctx.send_response("",
                            embed=create_one_line_embed(f"autoplay = {'true' if configuration.autoplay else 'false'}"))


@bot.slash_command(name="speed")
async def speed(ctx: discord.ApplicationContext, speed: float):
    configuration = configurations[ctx.guild]
    speed = max(Configuration.MIN_SPEED, min(speed, Configuration.MAX_SPEED))
    if configuration.speed == speed:
        return await ctx.send_response("", embed=create_one_line_embed(f"Już mam ustawiony speed na {speed} gałganie"))
    configuration.set_speed(speed)
    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is not None and vc.playing:
        vc.filters.timescale.set(speed=configuration.speed, pitch=configuration.pitch, rate=configuration.rate)
        await vc.set_filters(vc.filters)

    await ctx.send_response("", embed=create_one_line_embed(f"Speed = {configuration.speed}"))


@bot.slash_command(name="pitch")
async def pitch(ctx: discord.ApplicationContext, pitch: float):
    configuration = configurations[ctx.guild]
    pitch = max(Configuration.MIN_PITCH, min(pitch, Configuration.MAX_PITCH))
    if configuration.pitch == pitch:
        return await ctx.send_response("", embed=create_one_line_embed(f"Już mam ustawiony pitch na {pitch} gałganie"))
    configuration.set_pitch(pitch)
    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is not None and vc.playing:
        vc.filters.timescale.set(speed=configuration.speed, pitch=configuration.pitch, rate=configuration.rate)
        await vc.set_filters(vc.filters)

    await ctx.send_response("", embed=create_one_line_embed(f"Pitch = {configuration.pitch}"))


@bot.slash_command(name="rate")
async def rate(ctx: discord.ApplicationContext, rate: float):
    configuration = configurations[ctx.guild]
    rate = max(Configuration.MIN_RATE, min(rate, Configuration.MAX_RATE))
    if configuration.rate == rate:
        return await ctx.send_response("", embed=create_one_line_embed(f"Już mam ustawiony rate na {rate} gałganie"))
    configuration.set_rate(rate)
    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is not None and vc.playing:
        vc.filters.timescale.set(speed=configuration.speed, pitch=configuration.pitch, rate=configuration.rate)
        await vc.set_filters(vc.filters)

    await ctx.send_response("", embed=create_one_line_embed(f"Rate = {configuration.rate}"))


@bot.slash_command(name="reset_config")
async def reset_config(ctx: discord.ApplicationContext):
    configuration = configurations[ctx.guild]
    configuration.reset()
    if not configuration.autoplay:
        recomended_songs[ctx.guild] = None
    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is not None and vc.playing:
        vc.autoplay = wavelink.AutoPlayMode.enabled if configuration.autoplay else wavelink.AutoPlayMode.partial
        vc.filters.timescale.set(speed=configuration.speed, pitch=configuration.pitch, rate=configuration.rate)
        await vc.set_filters(vc.filters)

    await ctx.send_response("", embed=create_one_line_embed(f"Ustawienia zresetowane"))


@bot.slash_command(name="configuration")
async def configuration(ctx: discord.ApplicationContext):
    configuration = configurations[ctx.guild]
    await ctx.send_response("", embed=create_one_line_embed("Ustawienia:\n" + str(configuration)))


@bot.slash_command(name="upload")
async def upload(ctx: discord.ApplicationContext, file: discord.Attachment):
    if file.filename in os.listdir(TRACKS_DIR):
        return await ctx.send_response("", embed=create_one_line_embed(f"Już posiadam utwór o nazwie {file.filename}"))
    msg = await ctx.send_response("", embed=create_one_line_embed(f"Kradne {file.filename}"))
    await file.save(pathlib.Path(os.path.join(TRACKS_DIR, file.filename)))
    await msg.edit(embed=create_one_line_embed(f"Ukradłem {file.filename}"))


@bot.slash_command(name="download")
async def download(ctx: discord.ApplicationContext, url: str, name: str):
    if ";" in name:
        return await ctx.send_response("", embed=create_one_line_embed(f"Ale nie wpisuj mi takich głupich znaczków jak ';' homoseksualisto"))
    if is_link_to_playlist(url):
        return await ctx.send_response("", embed=create_one_line_embed(f"Nie będę pobierał playlisty bo to dużo roboty i mi się nie chcę"))
    url = format_link(url)
    record = get_downloaded_by_url(url)
    if record is not None:
        return await ctx.send_response("", embed=create_one_line_embed(f"Już kiedyś pobrałem ten utwór i nazwałem go {record.split(';')[1]}"))
    if name in os.listdir(TRACKS_DIR):
        return await ctx.send_response("", embed=create_one_line_embed(f"Już posiadam utwór o nazwie {name}"))
    if get_memory_usage() >= TRACKS_DIR_MAX_SIZE:
        return await ctx.send_response("", embed=create_one_line_embed(f"Mam już pełny brzuszek i nie będe nic więcej pobierał"))
    msg = await ctx.send_response("", embed=create_one_line_embed(f"Pobieram {url}"))
    try:
        def hook(filename):
            video = VideoFileClip(filename)
            video.audio.write_audiofile("output.mp3")
            video.close()
            os.rename("output.mp3", os.path.join(TRACKS_DIR, name))
            os.remove(filename)
            info_dict = ydl.extract_info(url, download=False)
            add_downloaded(url, name, info_dict)

        ydl_opts = {"cookiefile": COOKIES_PATH, "paths": {"home": "downloads"}, "post_hooks": [hook], "quiet": "True",
                    "noplaylist": "True",  "format": "mp4"}
        ydl = yt_dlp.YoutubeDL(ydl_opts)
        ydl.download([url])
        await msg.edit(embed=create_one_line_embed(f"Pobrałem {url}"))
    except Exception as e:
        await msg.edit(embed=create_one_line_embed(f"Nie udało mi się pobrać {url} - błąd: {e}"))


@bot.slash_command(name="rename")
async def rename(ctx: discord.ApplicationContext, old_name: str, new_name: str):
    if old_name not in os.listdir(TRACKS_DIR):
        return await ctx.send_response("", embed=create_one_line_embed(f"Nie posiadam utwór o nazwie {old_name}"))

    if new_name in os.listdir(TRACKS_DIR):
        return await ctx.send_response("", embed=create_one_line_embed(f"Już posiadam utwór o nazwie {new_name}"))

    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is not None:
        if vc.current.title == old_name:
            return await ctx.send_response("",
                                           embed=create_one_line_embed(f"Nie zmieniaj nazwy utworu który gram daunie"))
        elif old_name in [song.title for song in vc.queue]:
            return await ctx.send_response("", embed=create_one_line_embed(
                f"Nie zmieniaj nazwy utworu który mam w kolejce matole"))

    os.rename(os.path.join(TRACKS_DIR, old_name), os.path.join(TRACKS_DIR, new_name))
    await ctx.send_response("", embed=create_one_line_embed(f"Przenazwowałem \"{old_name}\" na \"{new_name}\""))
    if get_downloaded_by_name(old_name) is not None:
        change_downloaded(old_name, new_name)


@bot.slash_command(name="remove")
async def remove(ctx: discord.ApplicationContext, name: str):
    if name not in os.listdir(TRACKS_DIR):
        return await ctx.send_response("", embed=create_one_line_embed(f"Nie posiadam utwór o nazwie {name}"))

    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is not None:
        if vc.current.title == name:
            return await ctx.send_response("", embed=create_one_line_embed(f"Nie usuwaj utworu który gram daunie"))
        elif name in [song.title for song in vc.queue]:
            return await ctx.send_response("", embed=create_one_line_embed(
                f"Nie usuwaj utworu który mam w kolejce matole"))

    os.remove(os.path.join(TRACKS_DIR, name))
    if get_downloaded_by_name(name) is not None:
        remove_downloaded(name)
    await ctx.send_response("", embed=create_one_line_embed(f"Wyjebałem utwór o nazwie \"{name}\""))


@bot.slash_command(name="list")
async def list(ctx: discord.ApplicationContext):
    songs = os.listdir(TRACKS_DIR)
    songs = sorted(songs)
    size = len(songs)

    embed = discord.Embed(
        title=f"Utwory[{size}]",
        color=discord.Colour.blurple(),
    )

    n = min(size, MAX_LIST_SIZE)
    for i in range(n):
        embed.add_field(name="", value=f"{songs[i]}", inline=True)
    await ctx.send_response("", embed=embed)

    if size > MAX_LIST_SIZE:
        for startInd in range(MAX_LIST_SIZE, size, MAX_LIST_SIZE):
            embed = discord.Embed(
                title="",
                color=discord.Colour.blurple(),
            )
            endInd = min(startInd + MAX_LIST_SIZE, size)
            for i in range(startInd, endInd):
                embed.add_field(name="", value=f"{songs[i]}", inline=True)
            await ctx.send_followup("", embed=embed)


@bot.slash_command(name="say")
async def say(ctx: discord.ApplicationContext, text: str):
    if ctx.author.voice is None:
        return await ctx.send_response("", embed=create_one_line_embed("Nie ma cię na kanale debilu"))

    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is not None and vc.channel.id != ctx.author.voice.channel.id:
        return await ctx.send_response("", embed=create_one_line_embed("Jesteś na innym kanale niż ja bandyto"))

    song = await wavelink.Playable.search(text, source="speak")

    channel_to_respond[ctx.guild] = ctx.channel
    if not vc:
        configuration = configurations[ctx.guild]
        vc = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        vc.autoplay = wavelink.AutoPlayMode.enabled if configuration.autoplay else wavelink.AutoPlayMode.partial
        vc.filters.timescale.set(speed=configuration.speed, pitch=configuration.pitch, rate=configuration.rate)
    isPlaying = vc.playing
    song = song[0]
    song._title = text
    song._uri = None
    await handle_song(vc, ctx.guild, song, isPlaying)
    await ctx.send_response("", embed=create_embed_from_song(song, "Mówię" if not isPlaying else "Kiedyś powiem",
                                                             ctx.author))


@bot.slash_command(name="version")
async def version(ctx: discord.ApplicationContext):
    version = get_lavalink_version()[0]
    commits, commits_status_code = get_lavalink_commits()
    releases, releases_status_code = get_lavalink_releases()

    if not commits:
        return await ctx.send_response("", embed=create_one_line_embed(f"Błąd: {commits_status_code}"))

    if not releases:
        return await ctx.send_response("", embed=create_one_line_embed(f"Błąd: {releases_status_code}"))

    current_release = None
    current_commit = None
    for release in releases:
        if release[0] == version:
            current_release = release[0]
            current_commit = release[1]
            break
    if current_release is None:
        current_release = "-"
        current_commit = version
    latest_release = releases[0][0]
    latest_commit = commits[0]

    embed = discord.Embed(
        title="Wersja",
        color=discord.Colour.blurple(),
    )
    embed.add_field(name="Obecny release", value=f"{current_release}", inline=False)
    embed.add_field(name="Obecny commit", value=f"{current_commit}", inline=False)
    embed.add_field(name="Najnowszy release", value=f"{latest_release}", inline=False)
    embed.add_field(name="Najnowszy commit", value=f"{latest_commit}", inline=False)
    await ctx.send_response("", embed=embed)


@bot.slash_command(name="update")
async def update(ctx: discord.ApplicationContext, version: str = ""):
    current_version = get_lavalink_version()
    commits, commits_status_code = get_lavalink_commits()
    releases, releases_status_code = get_lavalink_releases()

    if not commits:
        return await ctx.send_response("", embed=create_one_line_embed(f"Błąd: {commits_status_code}"))

    if not releases:
        return await ctx.send_response("", embed=create_one_line_embed(f"Błąd: {releases_status_code}"))

    if version == "":
        version = commits[0]

    is_snapshot = True
    for release in releases:
        if release[1] == version:
            version = release[0]

        if release[0] == version:
            is_snapshot = False
            if current_version[0] == release[0] or current_version[0] == release[1]:
                return await ctx.send_response("", embed=create_one_line_embed(
                    f"Już jestem na wersji: {version}, bambaryło"))
            break

    if is_snapshot and version not in commits:
        return await ctx.send_response("", embed=create_one_line_embed(f"Nawet nie ma takiej wersji gupcze"))

    if is_snapshot and current_version[1] and version == current_version:
        return await ctx.send_response("", embed=create_one_line_embed(f"Już jestem na wersji: {version}, bambaryło"))

    await ctx.send_response("", embed=create_one_line_embed(f"Zmieniam wersje na {version}"))

    set_lavalink_version(version, is_snapshot)

    global lavalink_process, lavalink_ready

    for vc in bot.voice_clients:
        if channel_to_respond[vc.guild] is not None:
            await channel_to_respond[vc.guild].send("", embed=create_one_line_embed("Poszłem sobie na aktualizację"))
            channel_to_respond[vc.guild] = None
        await vc.disconnect()

    lavalink_ready = False
    lavalink_process.kill()
    lavalink_process = start_lavalink_process()

    await disconnect_nodes()
    await connect_nodes()


@bot.slash_command(name="leave")
async def leave(ctx: discord.ApplicationContext):
    if ctx.voice_client is None:
        return await ctx.send_response("", embed=create_one_line_embed("Nawet mnie nie ma głupolu"))

    await ctx.send_response("", embed=create_one_line_embed("Mio byo ci sużyć"))
    channel_to_respond[ctx.guild] = None
    await ctx.voice_client.disconnect()


@bot.slash_command(name="restart")
async def restart(ctx: discord.ApplicationContext):
    await ctx.send_response("", embed=create_one_line_embed(f"Zaczynam restart"))

    global lavalink_process, lavalink_ready

    for vc in bot.voice_clients:
        if channel_to_respond[vc.guild] is not None:
            await channel_to_respond[vc.guild].send("", embed=create_one_line_embed("Restartuje sie"))
            channel_to_respond[vc.guild] = None
        await vc.disconnect()

    lavalink_ready = False
    lavalink_process.kill()
    lavalink_process = start_lavalink_process()

    await disconnect_nodes()
    await connect_nodes()


@bot.slash_command(name="memory")
async def memory(ctx: discord.ApplicationContext):
    used_size = min(get_memory_usage(), TRACKS_DIR_MAX_SIZE)
    free_size = TRACKS_DIR_MAX_SIZE - used_size
    embed = discord.Embed(
        title="Pamięć",
        color=discord.Colour.blurple(),
    )
    embed.add_field(name="Wykorzystywana", value=f"{human_size(used_size)}", inline=True)
    embed.add_field(name="Wolna", value=f"{human_size(free_size)}", inline=True)
    embed.add_field(name="Całkowita", value=f"{human_size(TRACKS_DIR_MAX_SIZE)}", inline=True)
    embed.add_field(name="", value=f"{100*round(used_size/TRACKS_DIR_MAX_SIZE)}%", inline=True)
    embed.add_field(name="", value=f"{100-100*round(used_size/TRACKS_DIR_MAX_SIZE)}%", inline=True)
    embed.add_field(name="", value="100%", inline=True)
    await ctx.send_response("", embed=embed)


@bot.event
async def on_ready():
    await connect_nodes()

    global configurations, channel_to_respond
    if not os.path.exists(TRACKS_DIR):
        os.mkdir(TRACKS_DIR)
    if not os.path.exists(CONFIGURATIONS_DIR):
        os.mkdir(CONFIGURATIONS_DIR)
    default_configuration_path = os.path.join(CONFIGURATIONS_DIR, "default")
    default_configuration = Configuration(default_configuration_path)
    default_configuration.set_as_default()

    servers_configurations_path = os.path.join(CONFIGURATIONS_DIR, "servers")
    if not os.path.exists(servers_configurations_path):
        os.mkdir(servers_configurations_path)
    for guild in bot.guilds:
        recomended_songs[guild] = None
        channel_to_respond[guild] = None
        path = os.path.join(servers_configurations_path, str(guild.id))
        configurations[guild] = Configuration(path)

    await bot.sync_commands(commands=bot.pending_application_commands, method="bulk",
                            guild_ids=[guild.id for guild in bot.guilds], force=True)
    print("commands synced", flush=True)


@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
    global lavalink_ready
    lavalink_ready = True
    print(f"Node with ID {payload.session_id} has connected", flush=True)
    print(f"Resumed session: {payload.resumed}", flush=True)


@commands.Cog.listener()
async def on_wavelink_track_end(event: wavelink.TrackEndEventPayload):
    if event.player is None:
        return
    if not event.player.queue:
        if recomended_songs[event.player.guild] is not None:
            song = recomended_songs[event.player.guild]
            recomended_songs[event.player.guild] = None
            if configurations[event.player.guild].autoplay:
                await event.player.play(song, populate=True, max_populate=1)
                if event.player.auto_queue:
                    recomended_songs[event.player.guild] = event.player.auto_queue[0]
                    event.player.auto_queue.clear()
        else:
            if channel_to_respond[event.player.guild] is not None:
                await channel_to_respond[event.player.guild].send("", embed=create_one_line_embed("Mio byo ci sużyć"))
                channel_to_respond[event.player.guild] = None
            await event.player.disconnect()
    else:
        song = event.player.queue[0]
        event.player.queue.delete(0)
        if configurations[event.player.guild].autoplay:
            await event.player.play(song, populate=True, max_populate=1)
            if event.player.auto_queue:
                recomended_songs[event.player.guild] = event.player.auto_queue[0]
                event.player.auto_queue.clear()
        else:
            await event.player.play(song)


@commands.Cog.listener()
async def on_wavelink_track_exception(event: wavelink.TrackExceptionEventPayload):
    channel = channel_to_respond[event.player.guild]
    if channel is not None:
        if "youtube" in event.track.uri:
            embed = create_one_line_embed(f"Dziobany jutjub nie pozwala mi zagrać \"{event.track.title}\", bo: {event.exception['message'] if 'message' in event.exception else 'Chuj wie co'}")
        else:
            embed = create_one_line_embed(f"Nie moge zagrać \"{event.track.title}\", bo: {event.exception['message'] if 'message' in event.exception else 'Chuj wie co'}")
        embed.add_field(name="Pobierz", value="🔽", inline=True)
        embed.add_field(name="Pobierz i zagraj", value="▶️", inline=True)

        message = await channel.send("", embed=embed)
        await message.add_reaction("🔽")
        await message.add_reaction("▶")
        try:
            reaction, user = await bot.wait_for("reaction_add", timeout=30.0, check=lambda reaction, user: not user.bot and (reaction.emoji == "🔽" or reaction.emoji == "▶"))
        except Exception as exception:
            await message.add_reaction("⛔")
        else:
            url = event.track.uri
            name = re.sub(r"[\U00010000-\U0010FFFF]", "", event.track.title).strip()
            name = re.sub(r"\s+", " ", name)

            record = get_downloaded_by_url(url)
            if record is not None:
                return await channel.send("", embed=create_one_line_embed(
                    f"Już kiedyś pobrałem ten utwór i nazwałem go {record.split(';')[1]}"))
            if name in os.listdir(TRACKS_DIR):
                return await channel[event.player.guild].send("", embed=create_one_line_embed(f"Już posiadam utwór o nazwie {name}"))
            if get_/memory_usage() >= TRACKS_DIR_MAX_SIZE:
                return await channel[event.player.guild].send("", embed=create_one_line_embed("Mam już pełny brzuszek i nie będe nic więcej pobierał"))
            msg = await channel.send("", embed=create_one_line_embed(f"Pobieram {url}"))
            try:
                def hook(filename):
                    video = VideoFileClip(filename)
                    video.audio.write_audiofile("output.mp3")
                    video.close()
                    os.rename("output.mp3", os.path.join(TRACKS_DIR, name))
                    os.remove(filename)
                    info_dict = ydl.extract_info(url, download=False)
                    add_downloaded(url, name, info_dict)

                ydl_opts = {"cookiefile": COOKIES_PATH, "paths": {"home": "downloads"},
                            "post_hooks": [hook], "quiet": "True",
                            "noplaylist": "True", "format": "mp4"}
                ydl = yt_dlp.YoutubeDL(ydl_opts)
                ydl.download([url])
                await msg.edit(embed=create_one_line_embed(f"Pobrałem {url}"))
            except Exception as e:
                await msg.edit(embed=create_one_line_embed(f"Nie udało mi się pobrać {url} - błąd: {e}"))

            if reaction.emoji == "▶":
                if user.voice is None:
                    return await channel.send("", embed=create_one_line_embed("Nie ma cię na kanale debilu"))

                configuration = configurations[user.guild]
                vc = None
                for voice_client in bot.voice_clients:
                    if voice_client.guild == user.guild:
                        vc = voice_client
                        break
                if vc is not None and vc.channel.id != user.voice.channel.id:
                    return await channel.send("",
                                                   embed=create_one_line_embed("Jesteś na innym kanale niż ja bandyto"))

                candidates = [name]
                songs = None
                if candidates:
                    candidates.sort()
                    songs = await wavelink.Playable.search(os.path.join(TRACKS_DIR, candidates[0]), source=None)
                if not songs:
                    return await channel.send("", embed=create_one_line_embed("Nie znalazłem twego utworu"))

                channel_to_respond[user.guild] = channel
                if not vc:
                    vc = await user.voice.channel.connect(cls=wavelink.Player)
                    vc.autoplay = wavelink.AutoPlayMode.disabled
                    vc.filters.timescale.set(speed=configuration.speed, pitch=configuration.pitch,
                                             rate=configuration.rate)
                isPlaying = vc.playing
                song = songs[0]
                song._title = candidates[0]
                song._uri = None
                record = get_downloaded_by_name(name)
                if record is not None:
                    tokens = record.split(";")
                    song._uri = tokens[0]
                    song._title = tokens[2]
                    song._artwork = tokens[3]
                    song._length = int(tokens[4])
                await handle_song(vc, user.guild, song, isPlaying)
                await channel.send("", embed=create_embed_from_song(song, "Gram" if not isPlaying else "Kolejkuję", user))


@bot.event
async def on_guild_join(guild):
    servers_configurations_path = os.path.join(CONFIGURATIONS_DIR, "servers")
    if not os.path.exists(servers_configurations_path):
        os.mkdir(servers_configurations_path)
    channel_to_respond[guild] = None
    path = os.path.join(servers_configurations_path, str(guild.id))
    configurations[guild] = Configuration(path)


bot.add_listener(on_wavelink_track_end)
bot.add_listener(on_wavelink_track_exception)

print("lavalink started", flush=True)
lavalink_process = start_lavalink_process()
print("bot run", flush=True)
bot.run(TOKEN)
