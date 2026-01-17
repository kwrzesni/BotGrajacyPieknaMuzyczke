import asyncio
import discord
import logging
import os
import typing
import config
import embed_creator
import wavelink
from discord.ext import commands
from guild_configs_manager import GuildConfig, GuildConfigsManager
from lavalink_manager import LavalinkManager
from lavalink_manager import State as LavalinkState
from tracks_manager import TracksManager, TrackInfo

config = config.Config()
logging.basicConfig(level=logging.DEBUG if config.debug else logging.INFO,
                    filename=config.logs_path,
                    format="%(asctime)s - %(levelname)s - %(message)s",
                    filemode="w",
                    encoding="utf-8")
guild_configs_manager = GuildConfigsManager(config.guild_configs_dir)
lavalink_manager = LavalinkManager(config.lavalink_dir)
tracks_manager = TracksManager(config.downloaded_track_info_db,
                               config.tracks_dir,
                               config.tracks_dir_max_size,
                               config.cookies_file,
                               config.temp_downloads_dir)
bot = commands.Bot()


async def handle_song(vc, guild, song):
    if vc.playing:
        vc.queue.put(song)
    else:
        if guild_configs_manager[guild].autoplay:
            await vc.play(song, populate=True, max_populate=1)
            if vc.auto_queue:
                guild_configs_manager[guild].recommended_song = vc.auto_queue[0]
                vc.auto_queue.clear()
        else:
            await vc.play(song)


def fill_song_info(song, track_info: TrackInfo):
    song._uri = TracksManager.video_id_to_youtube_url(track_info.video_id)
    song._title = track_info.title
    song._artwork = track_info.thumbnail_url
    if track_info.duration > 0:
        song._length = track_info.duration


def adjust_time_delta(delta, speed, rate):
    return int(delta * 1000 / (speed * rate)) if speed * rate != 0 else delta * 1000


@bot.slash_command(name="play", description="Gra muzyczke z linku lub szuka na jutjubie")
async def play(ctx: discord.ApplicationContext, search: str):
    logging.debug(f"Command play({search})")
    if lavalink_manager.state != LavalinkState.READY:
        embed = embed_creator.from_lavalink_state_error("Nie mogę grać w stanie: ", lavalink_manager.state)
        return await ctx.send_response("", embed=embed)

    if ctx.author.voice is None:
        return await ctx.send_response("", embed=embed_creator.one_line_error("Nie ma cię na kanale debilu"))

    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is not None and vc.channel.id != ctx.author.voice.channel.id:
        return await ctx.send_response("", embed=embed_creator.one_line_error("Jesteś na innym kanale niż ja bandyto"))

    msg = await ctx.send_response("", embed=embed_creator.one_line_info("..."))

    guild_config = guild_configs_manager[ctx.guild]
    track_info = tracks_manager.track_info_from_url(search)
    if track_info is not None:
        file_name = track_info.file_name
        songs = await wavelink.Playable.search(str(tracks_manager.tracks_dir_path / file_name), source=None)
    else:
        songs = await wavelink.Playable.search(search)
    if not songs:
        return await msg.edit(embed=embed_creator.one_line_error("Nie znalazłem twego utworu"))
    song = songs[0]
    if track_info is not None:
        fill_song_info(song, track_info)

    guild_config.channel_to_respond = ctx.channel
    if not vc:
        vc = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        vc.autoplay = wavelink.AutoPlayMode.disabled
        vc.filters.timescale.set(speed=guild_config.speed, pitch=guild_config.pitch, rate=guild_config.rate)
    if songs[0].playlist is None:
        song = songs[0]
        await msg.edit(embed=embed_creator.from_song(song, vc.playing, ctx.author))
        await handle_song(vc, ctx.guild, song)
    else:
        await msg.edit(embed=embed_creator.from_playlist(songs, vc.playing, ctx.author, search))
        for i in range(songs.selected, len(songs)):
            await handle_song(vc, ctx.guild, songs[i])


@bot.slash_command(name="fplay", description="Gra muzyczke z pliku")
async def fplay(ctx: discord.ApplicationContext, search: str):
    logging.debug(f"Command fplay({search})")
    if lavalink_manager.state != LavalinkState.READY:
        embed = embed_creator.from_lavalink_state_error("Nie mogę grać w stanie: ", lavalink_manager.state)
        return await ctx.send_response("", embed=embed)

    if ctx.author.voice is None:
        return await ctx.send_response("", embed=embed_creator.one_line_error("Nie ma cię na kanale debilu"))

    guild_config = guild_configs_manager[ctx.guild]
    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is not None and vc.channel.id != ctx.author.voice.channel.id:
        return await ctx.send_response("", embed=embed_creator.one_line_error("Jesteś na innym kanale niż ja bandyto"))

    msg = await ctx.send_response("", embed=embed_creator.one_line_info("..."))

    track_info = tracks_manager.search_track(search)
    if track_info is None and TracksManager.is_youtube_url(search):
        track_info = tracks_manager.track_info_from_url(search)
    if track_info is None:
        logging.debug("Track_info not found")
        return await msg.edit(embed=embed_creator.one_line_error(f'Nie znalazłem twego utworu "{search}"'))

    logging.debug(f'Searching song: "{str(tracks_manager.tracks_dir_path / track_info.file_name)}"')
    songs = await wavelink.Playable.search(str(tracks_manager.tracks_dir_path / track_info.file_name), source=None)
    if not songs:
        logging.debug(f'Song not found. Search: "{str(tracks_manager.tracks_dir_path / track_info.file_name)}"')
        return await msg.edit(embed=embed_creator.one_line_error(f'Nie znalazłem twego utworu "{search}"'))
    logging.debug(f'Found songs: {songs}')

    guild_config.channel_to_respond = ctx.channel
    if not vc:
        vc = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        vc.autoplay = wavelink.AutoPlayMode.disabled
        vc.filters.timescale.set(speed=guild_config.speed, pitch=guild_config.pitch, rate=guild_config.rate)
    song = songs[0]
    fill_song_info(song, track_info)
    await msg.edit(embed=embed_creator.from_song(song, vc.playing, ctx.author))
    await handle_song(vc, ctx.guild, song)


@bot.slash_command(name="say", description="Mówi text")
async def say(ctx: discord.ApplicationContext, text: str):
    logging.debug(f"Command say({text})")
    if lavalink_manager.state != LavalinkState.READY:
        embed = embed_creator.from_lavalink_state_error("Nie mogę mówić w stanie: ", lavalink_manager.state)
        return await ctx.send_response("", embed=embed)

    if ctx.author.voice is None:
        return await ctx.send_response("", embed=embed_creator.one_line_error("Nie ma cię na kanale debilu"))

    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is not None and vc.channel.id != ctx.author.voice.channel.id:
        return await ctx.send_response("", embed=embed_creator.one_line_error("Jesteś na innym kanale niż ja bandyto"))

    song = await wavelink.Playable.search(text, source="speak")
    guild_config = guild_configs_manager[ctx.guild]
    guild_config.channel_to_respond = ctx.channel
    if not vc:
        vc = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        vc.autoplay = wavelink.AutoPlayMode.enabled if guild_config.autoplay else wavelink.AutoPlayMode.partial
        vc.filters.timescale.set(speed=guild_config.speed, pitch=guild_config.pitch, rate=guild_config.rate)
    song = song[0]
    song._title = text
    song._uri = None
    await ctx.send_response("", embed=embed_creator.from_speach(song, vc.playing, ctx.author))
    await handle_song(vc, ctx.guild, song)


@bot.slash_command(name="advance", description="Przesuwa pozycje w odtwarzanym utworze o delta sekund")
async def advance(ctx: discord.ApplicationContext, delta: int):
    logging.debug(f"Command advance({delta})")
    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is None or not vc.playing:
        return await ctx.send_response("", embed=embed_creator.one_line_error("Nic nie gram parówo"))

    if delta == 0:
        return await ctx.send_response("", embed=embed_creator.one_line_error("Madke se zadwancuj o 0"))

    guild_config = guild_configs_manager[ctx.guild]
    song = vc.current
    delta = adjust_time_delta(delta, guild_config.speed, guild_config.rate)
    new_position = max(0, min(vc.position + delta, song.length))
    await vc.seek(new_position)
    seconds = song.length // 1000
    played_seconds = int(new_position * guild_config.speed * guild_config.rate) // 1000
    await ctx.send_response("", embed=embed_creator.from_song_position("Nowa pozycja: ", played_seconds, seconds))


@bot.slash_command(name="pause", description="Pałzuje obecnie odtwarzany utwór")
async def pause(ctx: discord.ApplicationContext):
    logging.debug("Command pause")
    vc = typing.cast(wavelink.Player, ctx.voice_client)

    if vc is None or not vc.playing:
        return await ctx.send_response("", embed=embed_creator.one_line_error("Nawet nic nie gram gamoniu"))

    if ctx.author.voice is None or vc.channel.id != ctx.author.voice.channel.id:
        embed = embed_creator.one_line_error("Nie ma cię na tym samym kanale nicponiu")
        return await ctx.send_response("", embed=embed)

    await vc.pause(True)
    await ctx.send_response("", embed=embed_creator.one_line_info(f"Zapałzowałem {vc.current.title}"))


@bot.slash_command(name="resume", description="Wznawia obecnie odtwarzany utwór")
async def resume(ctx: discord.ApplicationContext):
    logging.debug("Command resume")
    vc = typing.cast(wavelink.Player, ctx.voice_client)

    if vc is None or not vc.playing:
        return await ctx.send_response("", embed=embed_creator.one_line_error("Nawet nic nie gram gamoniu"))

    if ctx.author.voice is None or vc.channel.id != ctx.author.voice.channel.id:
        embed = embed_creator.one_line_error("Nie ma cię na tym samym kanale nicponiu")
        return await ctx.send_response("", embed=embed)

    await vc.pause(False)
    await ctx.send_response("", embed=embed_creator.one_line_info(f"Znowu gram {vc.current.title}"))


@bot.slash_command(name="skip", description="Pomija obecnie odtwarzany utwór")
async def skip(ctx: discord.ApplicationContext):
    logging.debug("Command skip")
    vc = typing.cast(wavelink.Player, ctx.voice_client)

    if vc is None or not vc.playing:
        return await ctx.send_response("", embed=embed_creator.one_line_error("Nawet nic nie gram gamoniu"))

    if ctx.author.voice is None or vc.channel.id != ctx.author.voice.channel.id:
        embed = embed_creator.one_line_error("Nie ma cię na tym samym kanale nicponiu")
        return await ctx.send_response("", embed=embed)

    title = vc.current.title
    await vc.skip()
    await ctx.send_response("", embed=embed_creator.one_line_info(f"Wypierdalam {title}"))


@bot.slash_command(name="skipall", description="Pomija wszystkie dodane utwory")
async def skipall(ctx: discord.ApplicationContext):
    logging.debug("Command skipall")
    vc = typing.cast(wavelink.Player, ctx.voice_client)

    if vc is None or not vc.playing:
        return await ctx.send_response("", embed=embed_creator.one_line_error("Nawet nic nie gram gamoniu"))

    if ctx.author.voice is None or vc.channel.id != ctx.author.voice.channel.id:
        embed = embed_creator.one_line_error("Nie ma cię na tym samym kanale nicponiu")
        return await ctx.send_response("", embed=embed)

    vc.queue.clear()
    await vc.skip()
    await ctx.send_response("", embed=embed_creator.one_line_info("Wypierdalam wszystko"))


@bot.slash_command(name="nskip", description="Pomija n pierwszych utworów")
async def nskip(ctx: discord.ApplicationContext, n: int):
    logging.debug(f"Command nskip({n})")
    vc = typing.cast(wavelink.Player, ctx.voice_client)

    if vc is None or not vc.playing:
        return await ctx.send_response("", embed=embed_creator.one_line_error("Nawet nic nie gram gamoniu"))

    if ctx.author.voice is None or vc.channel.id != ctx.author.voice.channel.id:
        embed = embed_creator.one_line_error("Nie ma cię na tym samym kanale nicponiu")
        return await ctx.send_response("", embed=embed)

    n = max(1, n)
    n = min(n, len(vc.queue) + 1)
    for i in range(n - 1):
        vc.queue.delete(0)
    title = vc.current.title
    await vc.skip()
    if n == 1:
        await ctx.send_response("", embed=embed_creator.one_line_info(f"Wypierdalam {title}"))
    else:
        await ctx.send_response("", embed=embed_creator.one_line_info(f"Wypierdalam {n} piosenek"))


@bot.slash_command(name="leave", description="Wyrzuca bota z kanału")
async def leave(ctx: discord.ApplicationContext):
    logging.debug("Command leave")
    if ctx.voice_client is None:
        return await ctx.send_response("", embed=embed_creator.one_line_error("Nawet mnie nie ma głupolu"))
    await ctx.send_response("", embed=embed_creator.one_line_info("Mio byo ci sużyć"))
    guild_configs_manager[ctx.guild].channel_to_respond = None
    await ctx.voice_client.disconnect()


@bot.slash_command(name="queue", description="Wypisuje wybraną część kolejki utworów")
async def get_queue(ctx: discord.ApplicationContext, n: int = 1):
    logging.debug(f"Command queue({n})")
    n = max(1, n) - 1
    vc = typing.cast(wavelink.Player, ctx.voice_client)
    await ctx.send_response("", embed=embed_creator.from_queue(vc.queue if vc is not None else [], n))


@bot.slash_command(name="allqueue", description="Wypisuje cała kolejke utworów")
async def allqueue(ctx: discord.ApplicationContext):
    logging.debug("Command allqueue")
    vc = typing.cast(wavelink.Player, ctx.voice_client)
    queue = vc.queue if vc is not None else []
    await ctx.send_response("", embed=embed_creator.from_queue(queue, 0))
    for page_ind in range(1, len(queue) // embed_creator.MAX_QUEUE_SIZE):
        await ctx.send_followup("", embed=embed_creator.from_queue(queue, page_ind, add_header=False))


@bot.slash_command(name="current", description="Wypisuje obecnie odtwarzany utworów")
async def current(ctx: discord.ApplicationContext):
    logging.debug("Command current")
    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is None or not vc.playing:
        return await ctx.send_response("", embed=embed_creator.one_line_error("Nic nie gram parówo"))
    song = vc.current
    guild_config = guild_configs_manager[ctx.guild]
    await ctx.send_response("", embed=embed_creator.from_current_song(song, guild_config, vc.position))


@bot.slash_command(name="position", description="Wypisuje pozycje w obecnie odtwarzanym utworze")
async def position(ctx: discord.ApplicationContext):
    logging.debug("Command position")
    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is None or not vc.playing:
        return await ctx.send_response("", embed=embed_creator.one_line_error("Nic nie gram parówo"))

    guild_config = guild_configs_manager[ctx.guild]
    song = vc.current
    seconds = song.length // 1000
    played_seconds = int(vc.position * guild_config.speed * guild_config.rate) // 1000
    await ctx.send_response("", embed=embed_creator.from_song_position("Pozycja: ", played_seconds, seconds))


@bot.slash_command(name="autoplay", description="Przełącza opcje autoodtwarzanie")
async def autoplay(ctx: discord.ApplicationContext):
    logging.debug("Command autoplay")
    guild_config = guild_configs_manager[ctx.guild]
    guild_config.toggle_autoplay()
    await ctx.send_response("", embed=embed_creator.one_line_info(f"autoplay = {guild_config.autoplay}"))


@bot.slash_command(name="set_speed", description="Ustawia prędkość odtwarzania na speed")
async def set_speed(ctx: discord.ApplicationContext, speed: float):
    logging.debug(f"Command set_speed({speed})")
    min_value, max_value = GuildConfig.MIN_SPEED, GuildConfig.MAX_SPEED
    if speed < min_value or speed > max_value:
        embed = embed_creator.one_line_error(f"Speed musi być z zakresu: [{min_value}, {max_value}]")
        return await ctx.send_response("", embed=embed)

    guild_config = guild_configs_manager[ctx.guild]
    if guild_config.speed == speed:
        embed = embed_creator.one_line_error(f"Już mam ustawiony speed na {speed} gałganie")
        return await ctx.send_response("", embed=embed)

    guild_config.set_speed(speed)
    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is not None and vc.playing:
        vc.filters.timescale.set(speed=guild_config.speed, pitch=guild_config.pitch, rate=guild_config.rate)
        await vc.set_filters(vc.filters)

    await ctx.send_response("", embed=embed_creator.one_line_info(f"Speed = {guild_config.speed}"))


@bot.slash_command(name="set_pitch", description="Ustawia wysokość dźwięku na pitch")
async def set_pitch(ctx: discord.ApplicationContext, pitch: float):
    logging.debug(f"Command set_pitch({pitch})")
    min_value, max_value = GuildConfig.MIN_PITCH, GuildConfig.MAX_PITCH
    if pitch < min_value or pitch > max_value:
        embed = embed_creator.one_line_error(f"Pitch musi być z zakresu: [{min_value}, {max_value}]")
        return await ctx.send_response("", embed=embed)

    guild_config = guild_configs_manager[ctx.guild]
    if guild_config.pitch == pitch:
        embed = embed_creator.one_line_error(f"Już mam ustawiony pitch na {pitch} gałganie")
        return await ctx.send_response("", embed=embed)

    guild_config.set_pitch(pitch)
    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is not None and vc.playing:
        vc.filters.timescale.set(speed=guild_config.speed, pitch=guild_config.pitch, rate=guild_config.rate)
        await vc.set_filters(vc.filters)

    await ctx.send_response("", embed=embed_creator.one_line_info(f"Pitch = {guild_config.pitch}"))


@bot.slash_command(name="set_rate", description="Ustawia częstotliwość dźwięku na rate")
async def set_rate(ctx: discord.ApplicationContext, rate: float):
    logging.debug(f"Command set_rate({rate})")
    min_value, max_value = GuildConfig.MIN_RATE, GuildConfig.MAX_RATE
    if rate < min_value or rate > max_value:
        embed = embed_creator.one_line_error(f"Rate musi być z zakresu: [{min_value}, {max_value}]")
        return await ctx.send_response("", embed=embed)

    guild_config = guild_configs_manager[ctx.guild]
    if guild_config.rate == rate:
        embed = embed_creator.one_line_error(f"Już mam ustawiony rate na {rate} gałganie")
        return await ctx.send_response("", embed=embed)

    guild_config.set_rate(rate)
    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is not None and vc.playing:
        vc.filters.timescale.set(speed=guild_config.speed, pitch=guild_config.pitch, rate=guild_config.rate)
        await vc.set_filters(vc.filters)

    await ctx.send_response("", embed=embed_creator.one_line_info(f"Rate = {guild_config.rate}"))


@bot.slash_command(name="reset_config", description="Resetuje konfiugracje odtwarzania")
async def reset_config(ctx: discord.ApplicationContext):
    logging.debug("Command reset_config")
    guild_config = guild_configs_manager[ctx.guild]
    guild_config.reset()

    vc = typing.cast(wavelink.Player, ctx.voice_client)
    if vc is not None and vc.playing:
        vc.autoplay = wavelink.AutoPlayMode.enabled if guild_config.autoplay else wavelink.AutoPlayMode.partial
        vc.filters.timescale.set(speed=guild_config.speed, pitch=guild_config.pitch, rate=guild_config.rate)
        await vc.set_filters(vc.filters)

    await ctx.send_response("", embed=embed_creator.one_line_info(f"Ustawienia zresetowane"))


@bot.slash_command(name="configuration", description="Wypisuje konfiugracje odtwarzania")
async def configuration(ctx: discord.ApplicationContext):
    logging.debug("Command configuration")
    guild_config = guild_configs_manager[ctx.guild]
    await ctx.send_response("", embed=embed_creator.one_line_info("Ustawienia:\n" + str(guild_config)))


@bot.slash_command(name="upload", description="Przesyła plik na serwer bota")
async def upload(ctx: discord.ApplicationContext, file: discord.Attachment):
    logging.debug(f"Command upload({file})")
    msg = await ctx.send_response("", embed=embed_creator.one_line_info(f"Kradne {file.filename}"))
    try:
        await tracks_manager.download_from_discord(file)
        await msg.edit(embed=embed_creator.one_line_info(f"Ukradłem {file.filename}"))
    except ValueError as e:
        await msg.edit(embed=embed_creator.one_line_error(f"{e}"))
    except Exception as e:
        await msg.edit(embed=embed_creator.from_exception(f"Nie udało mi się ukraść {file.filename}:", e))


@bot.slash_command(name="download", description="Pobiera utwór z jutjuba")
async def download(ctx: discord.ApplicationContext, url: str, name: str = None):
    logging.debug(f"Command download({url}, {name})")
    msg = await ctx.send_response("", embed=embed_creator.one_line_info(f"Pobieram {url}"))
    try:
        tracks_manager.download_from_youtube(url, name)
        track_info = tracks_manager.track_info_from_url(url)
        await msg.edit(embed=embed_creator.one_line_info(f'Pobrałem {url} i nazwałem go "{track_info.file_name}"'))
    except ValueError as e:
        await msg.edit(embed=embed_creator.one_line_error(f"{e}"))
    except Exception as e:
        await msg.edit(embed=embed_creator.from_exception(f"Nie udało mi się pobrać {url}:", e))


@bot.slash_command(name="rename", description="Zmienia nazwe posiadanego utworu")
async def rename(ctx: discord.ApplicationContext, old_name: str, new_name: str):
    logging.debug(f"Command rename({old_name}, {new_name})")
    if not tracks_manager.track_exists(old_name):
        embed = embed_creator.one_line_error(f"Nie posiadam utwór o nazwie {old_name}")
        return await ctx.send_response("", embed=embed)

    if tracks_manager.track_exists(new_name):
        embed = embed_creator.one_line_error(f"Już posiadam utwór o nazwie {new_name}")
        return await ctx.send_response("", embed=embed)

    is_used = False
    for vc in bot.voice_clients:
        vc = typing.cast(wavelink.Player, vc)
        if vc.current.title == old_name or old_name in [song.title for song in vc.queue]:
            is_used = True
            break
    if is_used:
        embed = embed_creator.one_line_error(f"Nie zmieniaj nazwy utworu który jest używany daunie")
        return await ctx.send_response("", embed=embed)

    tracks_manager.rename_track(old_name, new_name)
    await ctx.send_response("", embed=embed_creator.one_line_info(f"Przenazwowałem \"{old_name}\" na \"{new_name}\""))


@bot.slash_command(name="remove", description="Usuwa posiadany utwór")
async def remove(ctx: discord.ApplicationContext, name: str):
    logging.debug(f"Command remove({name})")
    if not tracks_manager.track_exists(name):
        return await ctx.send_response("", embed=embed_creator.one_line_error(f"Nie posiadam utwór o nazwie {name}"))

    is_used = False
    for vc in bot.voice_clients:
        vc = typing.cast(wavelink.Player, vc)
        if vc.current.title == name or name in [song.title for song in vc.queue]:
            is_used = True
            break
    if is_used:
        embed = embed_creator.one_line_error(f"Nie usuwaj utworu który jest używany daunie")
        return await ctx.send_response("", embed=embed)

    tracks_manager.remove_track(name)
    await ctx.send_response("", embed=embed_creator.one_line_info(f"Wyjebałem utwór o nazwie \"{name}\""))


@bot.slash_command(name="list", description="Wypisuje posiadane utwory")
async def list_tracks(ctx: discord.ApplicationContext):
    logging.debug("Command list")
    track_names = tracks_manager.get_track_names()
    size = len(track_names)
    n = min(embed_creator.MAX_LIST_SIZE, size)
    await ctx.send_response("", embed=embed_creator.from_track_names(track_names, 0, n))
    for start_ind in range(n, size, embed_creator.MAX_LIST_SIZE):
        end_ind = min(start_ind + embed_creator.MAX_LIST_SIZE, size)
        embed = embed_creator.from_track_names(track_names, start_ind, end_ind, add_header=False)
        await ctx.send_followup("", embed=embed)


@bot.slash_command(name="memory", description="Wypisuje ilość miejsca zajmowanego przez posiadane utwory")
async def memory(ctx: discord.ApplicationContext):
    logging.debug("Command memory")
    used_size = min(tracks_manager.get_memory_usage(), config.tracks_dir_max_size)
    free_size = config.tracks_dir_max_size - used_size
    embed = embed_creator.from_memory_usage(used_size, free_size, tracks_manager.tracks_dir_max_size)
    await ctx.send_response("", embed=embed)


@bot.slash_command(name="version", description="Wypisuje wersje używanego pluginu lavalinku")
async def get_version(ctx: discord.ApplicationContext):
    logging.debug("version")
    version, is_snapshot = lavalink_manager.get_youtube_plugin_version()
    commits, commits_status_code = lavalink_manager.get_youtube_plugin_commits()
    releases, releases_status_code = lavalink_manager.get_youtube_plugin_releases()

    if not commits:
        return await ctx.send_response("", embed=embed_creator.one_line_error(f"Błąd: {commits_status_code}"))

    if not releases:
        return await ctx.send_response("", embed=embed_creator.one_line_error(f"Błąd: {releases_status_code}"))

    current_release = next((release for release in releases if version in release), None)
    if current_release is not None:
        current_release, current_commit = current_release
    else:
        current_release = "-"
        current_commit = next((commit for commit in commits if version == commit), None)

    latest_release = releases[0][0]
    latest_commit = commits[0]
    embed = embed_creator.from_version(current_release, current_commit, latest_release, latest_commit)
    await ctx.send_response("", embed=embed)


@bot.slash_command(name="update", description="Aktualizuje wersje używanego pluginu lavalinku do version")
async def update(ctx: discord.ApplicationContext, version: str = ""):
    logging.debug(f"update({version})")
    msg = await ctx.send_response("", embed=embed_creator.one_line_info("..."))
    if lavalink_manager.state != LavalinkState.READY:
        embed = embed_creator.from_lavalink_state_error("Nie mogę się updateować w stanie: ", lavalink_manager.state)
        return await msg.edit(embed=embed)

    current_version, is_snapshot = lavalink_manager.get_youtube_plugin_version()
    commits, commits_status_code = lavalink_manager.get_youtube_plugin_commits()
    releases, releases_status_code = lavalink_manager.get_youtube_plugin_releases()

    if not commits:
        return await msg.edit(embed=embed_creator.one_line_error(f"Błąd: {commits_status_code}"))

    if not releases:
        return await msg.edit(embed=embed_creator.one_line_error(f"Błąd: {releases_status_code}"))

    if not version:
        version = commits[0]

    matching_release = next((release for release in releases if version in release), None)
    if matching_release is not None:
        if current_version != matching_release[0]:
            lavalink_manager.set_youtube_plugin_release(matching_release[0])
        else:
            return await msg.edit(embed=embed_creator.one_line_error(f"Już jestem na wersji: {version}, bambaryło"))
    else:
        matching_commit = next((commit for commit in commits if version == commit), None)
        if matching_commit is not None:
            if current_version != matching_commit:
                lavalink_manager.set_youtube_plugin_commit(matching_commit)
            else:
                embed = embed_creator.one_line_error(f"Już jestem na wersji: {version}, bambaryło")
                return await msg.edit(embed=embed)
        else:
            embed = embed_creator.one_line_error(f"Nawet nie ma takiej wersji gupcze")
            return await msg.edit(embed=embed)

    await msg.edit(embed=embed_creator.one_line_info(f"Zmieniam wersje na {version}"))
    for guild_config in guild_configs_manager:
        if guild_config.channel_to_respond is not None:
            embed = embed_creator.one_line_info("Poszłem sobie na aktualizację")
            await guild_config.channel_to_respond.send("", embed=embed)
    for vc in bot.voice_clients:
        await vc.disconnect(force=True)
    lavalink_manager.state = LavalinkState.UPDATING
    await lavalink_manager.restart_process()


@bot.slash_command(name="restart", description="Restartuje lavalinka")
async def restart(ctx: discord.ApplicationContext):
    logging.debug("restart")
    if lavalink_manager.state != LavalinkState.READY:
        embed = embed_creator.from_lavalink_state_error("Nie mogę się restartować w stanie: ", lavalink_manager.state)
        return await ctx.send_response("", embed=embed)
    await ctx.send_response("", embed=embed_creator.one_line_info(f"Zaczynam restart"))
    for guild_config in guild_configs_manager:
        if guild_config.channel_to_respond is not None:
            await guild_config.channel_to_respond.send("", embed=embed_creator.one_line_info("Restartuje sie"))
    for vc in bot.voice_clients:
        await vc.disconnect(force=True)
    lavalink_manager.state = LavalinkState.RESTARTING
    await lavalink_manager.restart_process()


@bot.slash_command(name="lavalink_state", description="Wypisuje stan lavalinku")
async def lavalink_state(ctx: discord.ApplicationContext):
    logging.debug("lavalink_state")
    embed = embed_creator.one_line_info(f"Stan: {lavalink_manager.state.value}")
    await ctx.send_response("", embed=embed)


@bot.event
async def on_ready():
    await bot.wait_until_ready()
    await lavalink_manager.connect_node(bot)

    if not os.path.exists(config.tracks_dir):
        os.mkdir(config.tracks_dir)
    guild_configs_manager.fill_guild_configs(bot.guilds)
    guild_configs_manager.clear_removed_guild(bot.guilds)

    await bot.sync_commands(commands=bot.pending_application_commands, method="bulk",
                            guild_ids=[guild.id for guild in bot.guilds], force=True)
    logging.info(f"Discord commands synced")


@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
    lavalink_manager.ready = True
    logging.info(f"Node with ID {payload.session_id} has connected")
    if lavalink_manager.state in (LavalinkState.RESTARTING, LavalinkState.UPDATING):
        message_end = "restartować" if lavalink_manager.state == LavalinkState.RESTARTING else "aktualizować"
        embed = embed_creator.one_line_info("Skończyłem się " + message_end)
        for guild_config in guild_configs_manager:
            if guild_config.channel_to_respond is not None:
                await guild_config.channel_to_respond.send("", embed=embed)
                guild_config.channel_to_respond = None
    lavalink_manager.state = LavalinkState.READY


@bot.event
async def on_wavelink_node_closed(node: wavelink.Node, disconnected: list[wavelink.Player]):
    logging.info(f"Node with ID {node.session_id} has disconnected")


@bot.event
async def on_wavelink_track_end(event: wavelink.TrackEndEventPayload):
    if event.player is None:
        return
    guild_config = guild_configs_manager[event.player.guild]
    if not event.player.queue:
        if guild_config.recommended_song is not None:
            song = guild_config.recommended_song
            await event.player.play(song, populate=True, max_populate=1)
            if event.player.auto_queue:
                guild_config.recommended_song = event.player.auto_queue[0]
                event.player.auto_queue.clear()
        else:
            if guild_config.channel_to_respond is not None:
                await guild_config.channel_to_respond.send("", embed=embed_creator.one_line_info("Mio byo ci sużyć"))
                guild_config.channel_to_respond = None
            await event.player.disconnect()
    else:
        song = event.player.queue[0]
        event.player.queue.delete(0)
        video_id = song.identifier
        if tracks_manager.video_id_exists(video_id) and song.source != "local":
            track_info = tracks_manager.read_by_video_id(video_id)
            if track_info is not None:
                search = str(tracks_manager.tracks_dir_path / track_info.file_name)
                songs = await wavelink.Playable.search(search, source=None)
                if songs:
                    song = songs[0]
                    fill_song_info(song, track_info)
        if guild_config.autoplay:
            await event.player.play(song, populate=True, max_populate=1)
            if event.player.auto_queue:
                guild_config.recommended_song = event.player.auto_queue[0]
                event.player.auto_queue.clear()
        else:
            await event.player.play(song)


@bot.event
async def on_wavelink_track_exception(event: wavelink.TrackExceptionEventPayload):
    guild_config = guild_configs_manager[event.player.guild]
    channel_to_respond = guild_config.channel_to_respond
    if channel_to_respond is not None:
        embed = embed_creator.from_track_exception(event.track.title, 
                                                   event.track.uri, 
                                                   event.exception.get("message", None))
        message = await channel_to_respond.send("", embed=embed)
        await message.add_reaction("🔽")
        await message.add_reaction("▶")
        try:
            reaction, user = await bot.wait_for(
                "reaction_add", 
                timeout=30.0, 
                check=lambda react, usr: not usr.bot and (react.emoji == "🔽" or react.emoji == "▶")
            )
        except asyncio.TimeoutError:
            await message.add_reaction("⛔")
        else:
            url = event.track.uri
            msg = await channel_to_respond.send("", embed=embed_creator.one_line_info(f"Pobieram {url}"))
            try:
                tracks_manager.download_from_youtube(url)
                track_info = tracks_manager.track_info_from_url(url)
                embed = embed_creator.one_line_info(f'Pobrałem {url} i nazwałem go "{track_info.file_name}"')
                await msg.edit(embed=embed)
            except ValueError as e:
                return await msg.edit(embed=embed_creator.one_line_error(f"{e}"))
            except Exception as e:
                return await msg.edit(embed=embed_creator.from_exception(f"Nie udało mi się pobrać {url}:", e))
            if reaction.emoji == "▶":
                if user.voice is None:
                    embed = embed_creator.one_line_error("Nie ma cię na kanale debilu")
                    return await channel_to_respond.send("", embed=embed)

                vc = event.player.guild.voice_client
                if vc is not None and vc.channel.id != user.voice.channel.id:
                    embed = embed_creator.one_line_error("Jesteś na innym kanale niż ja bandyto")
                    return await channel_to_respond.send("", embed=embed)

                track_info = tracks_manager.read_by_youtube_url(url)
                if track_info is None:
                    embed = embed_creator.one_line_error("Nie mam takiego utworu")
                    return await channel_to_respond.send("", embed=embed)

                search = str(tracks_manager.tracks_dir_path / track_info.file_name)
                songs = await wavelink.Playable.search(search, source=None)
                if not songs:
                    embed = embed_creator.one_line_error("Nie znalazłem twego utworu")
                    return await channel_to_respond.send("", embed=embed)

                if not vc:
                    vc = await user.voice.channel.connect(cls=wavelink.Player)
                    vc.autoplay = wavelink.AutoPlayMode.disabled
                    vc.filters.timescale.set(speed=guild_config.speed, pitch=guild_config.pitch, rate=guild_config.rate)
                song = songs[0]
                fill_song_info(song, track_info)
                await channel_to_respond.send("", embed=embed_creator.from_song(song, vc.playing, user))
                await handle_song(vc, user.guild, song)


@bot.event
async def on_guild_join(guild):
    logging.info(f"Added guild = id: {guild.id}, name: {guild.name}")
    guild_configs_manager.add_guild(guild)


@bot.event
async def on_guild_remove(guild):
    logging.info(f"Removed guild = id: {guild.id}, name: {guild.name}")
    guild_configs_manager.remove_guild(guild)


lavalink_manager.start_process()
logging.info("Lavalink process started")
bot.run(config.token)
