import discord
import lavalink_manager
from memory_utils import human_size

MAX_TITLE_LENGTH = 256
MAX_PLAYLIST_SIZE = 5
MAX_QUEUE_SIZE = 7
MAX_LIST_SIZE = 20
INFO_EMBED_COLOR = discord.Colour.blurple()
ERROR_EMBED_COLOR = discord.Colour.red()


def text_with_link(text, url):
    if url is None:
        return text
    return f"[{text}]({url})"


def from_song(song, is_playing, author):
    title = "Gram" if not is_playing else "Kolejkuję"
    seconds = song.length // 1000
    embed = discord.Embed(
        title=title,
        description=text_with_link(song.title, song.uri),
        color=INFO_EMBED_COLOR,
    )
    embed.set_image(url=song.artwork)
    embed.add_field(name="Na prośbę", value=f"{author.mention}", inline=True)
    embed.add_field(name="Czas", value=f"{seconds // 60}:{seconds % 60:02d}", inline=True)
    return embed


def from_speach(song, is_playing, author):
    title = "Mówię" if not is_playing else "Kiedyś powiem"
    embed = discord.Embed(
        title=title,
        description=text_with_link(song.title, song.uri),
        color=INFO_EMBED_COLOR,
    )
    embed.set_image(url=song.artwork)
    embed.add_field(name="Na prośbę", value=f"{author.mention}", inline=True)
    return embed


def from_playlist(playlist, is_playing, author, search):
    title = "Gram" if not is_playing else "Kolejkuję"
    selected_song = playlist.tracks[playlist.selected]
    embed = discord.Embed(
        title=title,
        description=f"[{playlist.name}]({search})",
        color=INFO_EMBED_COLOR,
    )
    embed.set_image(url=selected_song.artwork)
    embed.add_field(name="Na prośbę", value=f"{author.mention}", inline=True)
    embed.add_field(name="Ind", value=f"{playlist.selected + 1}", inline=True)
    embed.add_field(name="Rozmiar", value=f"{len(playlist.tracks)}", inline=True)

    embed.add_field(name="Id", value="", inline=True)
    embed.add_field(name="Tytuł", value="", inline=True)
    embed.add_field(name="Czas", value="", inline=True)
    for i in range(playlist.selected, min(playlist.selected + MAX_PLAYLIST_SIZE, len(playlist.tracks))):
        embed.add_field(name="", value=f"{i + 1}", inline=True)
        embed.add_field(name="", value=text_with_link(playlist.tracks[i].title, playlist.tracks[i].uri), inline=True)
        seconds = playlist.tracks[i].length // 1000
        embed.add_field(name="", value=f"{seconds // 60}:{seconds % 60:02d}", inline=True)
    return embed


def from_queue(queue, page_ind, *, add_header=True):
    size = len(queue)
    if size == 0:
        embed = discord.Embed(
            title=f"Kolejka[0] 0/0",
            color=INFO_EMBED_COLOR
        )
        embed.add_field(name="Id", value="", inline=True)
        embed.add_field(name="Tytuł", value="", inline=True)
        embed.add_field(name="Czas", value="", inline=True)
    else:
        start_ind = page_ind * MAX_QUEUE_SIZE
        if start_ind >= size:
            start_ind = max(0, size - 1 - (size - 1) % MAX_QUEUE_SIZE)
        end_ind = min(start_ind + MAX_QUEUE_SIZE, size)
        page_ind = start_ind // MAX_QUEUE_SIZE
        if add_header:
            embed = discord.Embed(
                title=f"Kolejka[{size}] {page_ind + 1}/{(size - 1) // MAX_QUEUE_SIZE + 1}",
                color=INFO_EMBED_COLOR,
            )
            embed.add_field(name="Id", value="", inline=True)
            embed.add_field(name="Tytuł", value="", inline=True)
            embed.add_field(name="Czas", value="", inline=True)
        else:
            embed = discord.Embed(
                title="",
                color=INFO_EMBED_COLOR,
            )

        for i in range(start_ind, end_ind):
            embed.add_field(name="", value=f"{i + 1}", inline=True)
            embed.add_field(name="", value=text_with_link(queue[i].title, queue[i].uri), inline=True)
            seconds = queue[i].length // 1000
            embed.add_field(name="", value=f"{seconds // 60}:{seconds % 60:02d}", inline=True)
    return embed


def from_current_song(song, guild_config, position):
    seconds = song.length // 1000
    played_seconds = int(position * guild_config.speed * guild_config.rate) // 1000
    embed = discord.Embed(
        title="Gram",
        description=text_with_link(song.title, song.uri),
        color=INFO_EMBED_COLOR,
    )
    embed.set_image(url=song.artwork)
    embed.add_field(name="Czas",
                    value=f"{played_seconds // 60}:{played_seconds % 60:02d}/{seconds // 60}:{seconds % 60:02d}",
                    inline=True)
    return embed


def from_version(current_release, current_commit, latest_release, latest_commit):
    embed = discord.Embed(
        title="Wersja",
        color=INFO_EMBED_COLOR,
    )
    embed.add_field(name="Obecny release", value=f"{current_release}", inline=False)
    embed.add_field(name="Obecny commit", value=f"{current_commit}", inline=False)
    embed.add_field(name="Najnowszy release", value=f"{latest_release}", inline=False)
    embed.add_field(name="Najnowszy commit", value=f"{latest_commit}", inline=False)
    return embed


def from_track_names(track_names, start_ind, end_ind, *, add_header=True):
    embed = discord.Embed(
        title=f"Utwory[{len(track_names)}]" if add_header else "",
        color=INFO_EMBED_COLOR,
    )

    for i in range(start_ind, end_ind):
        embed.add_field(name="", value=f"{track_names[i]}", inline=True)
    return embed


def from_track_exception(title, uri, message):
    if "youtube" in uri:
        embed = one_line_error(
            f"Dziobany jutjub nie pozwala mi zagrać \"{title}\", "
            f"bo: {message if message is not None else 'Chuj wie co'}")
    else:
        embed = one_line_error(
            f"Nie moge zagrać \"{title}\", bo: {message if message is not None else 'Chuj wie co'}")
    embed.add_field(name="Pobierz", value="🔽", inline=True)
    embed.add_field(name="Pobierz i zagraj", value="▶️", inline=True)
    return embed


def from_memory_usage(used_size, free_size, max_size):
    embed = discord.Embed(
        title="Pamięć",
        color=INFO_EMBED_COLOR,
    )
    embed.add_field(name="Wykorzystywana", value=f"{human_size(used_size)}", inline=True)
    embed.add_field(name="Wolna", value=f"{human_size(free_size)}", inline=True)
    embed.add_field(name="Całkowita", value=f"{human_size(max_size)}", inline=True)
    embed.add_field(name="", value=f"{round(100 * used_size / max_size)}%", inline=True)
    embed.add_field(name="", value=f"{100 - round(100 * used_size / max_size)}%", inline=True)
    embed.add_field(name="", value="100%", inline=True)
    return embed


def one_line_info(text):
    return discord.Embed(title=text[:MAX_TITLE_LENGTH], color=INFO_EMBED_COLOR)


def one_line_error(text):
    return discord.Embed(title=text[:MAX_TITLE_LENGTH], color=ERROR_EMBED_COLOR)


def from_song_position(prefix, played_seconds, seconds):
    return one_line_info(prefix +
                         f"{played_seconds // 60}:{played_seconds % 60:02d}/{seconds // 60}:{seconds % 60:02d}")


def from_exception(title, exception):
    embed = discord.Embed(title=title[:MAX_TITLE_LENGTH], color=ERROR_EMBED_COLOR)
    embed.add_field(name="", value=str(exception))
    return embed


def from_lavalink_state_error(title, state: lavalink_manager.State):
    return one_line_error(title + state.value)
