import discord
import wavelink
import typing
import dotenv
import os
from discord.ext import commands

bot = commands.Bot()
channel_to_respond = {}
wisnia_id = 447457072725098506
banned_users = []
MAX_PLAYLIST_EMBED_SIZE = 5
MAX_QUEUE_EMBED_SIZE = 7
GLOBAL_DIR = ''
LOCAL_DIR = ''

def create_embed_from_song(song, title, author):
  seconds = song.length // 1000
  embed = discord.Embed(
    title=title,
    description=f"[{song.title}]({song.uri})",
    color=discord.Colour.blurple(),
  )
  embed.set_image(url=song.artwork)
  embed.add_field(name="Requested by", value=f"{author.mention}", inline=True)
  embed.add_field(name="Duration", value=f"{seconds//60}:{seconds%60:02d}", inline=True)
  return embed


def create_embed_from_playlist(playlist, title, author, search):
  selected_song = playlist.tracks[playlist.selected]
  embed = discord.Embed(
    title=title,
    description=f"[{playlist.name}]({search})",
    color=discord.Colour.blurple(),
  )
  embed.set_image(url=selected_song.artwork)
  embed.add_field(name="Requested by", value=f"{author.mention}", inline=True)
  embed.add_field(name="Selected", value=f"{playlist.selected + 1}", inline=True)
  embed.add_field(name="Size", value=f"{len(playlist.tracks)}", inline=True)

  embed.add_field(name="Id", value="", inline=True)
  embed.add_field(name="Title", value="", inline=True)
  embed.add_field(name="Duration", value="", inline=True)
  for i in range(playlist.selected, min(playlist.selected + MAX_PLAYLIST_EMBED_SIZE, len(playlist.tracks))):
    embed.add_field(name="", value=f"{i + 1}", inline=True)
    embed.add_field(name="", value=f"[{playlist.tracks[i].title}]({playlist.tracks[i].uri})", inline=True)
    seconds = playlist.tracks[i].length // 1000
    embed.add_field(name="", value=f"{seconds // 60}:{seconds % 60:02d}", inline=True)
  return embed


async def handle_song(vc, ctx, song, isPlaying):
  if isPlaying:
    vc.queue.put(song)
  else:
    await vc.play(song)



async def connect_nodes():
  """Connect to our Lavalink nodes."""
  await bot.wait_until_ready()

  nodes = [
    wavelink.Node(
      identifier="Node1",
      uri="http://127.0.0.1:2333",
      password="youshallnotpass"
    )
  ]

  await wavelink.Pool.connect(nodes=nodes, client=bot) # Connect our nodes



@bot.slash_command(name="play")
async def play(ctx: discord.ApplicationContext, search: str):
  if ctx.author.id in banned_users:
    await ctx.send_response("Niech ci DjUwU zagra jak jesteś taki cwany")
    return

  if ctx.author.voice is None:
    return await ctx.send_response("You must be in the voice channel.")

  vc = typing.cast(wavelink.Player, ctx.voice_client)
  if vc is not None and vc.channel.id != ctx.author.voice.channel.id:
    return await ctx.send_response("You must be in the same voice channel as the bot.")

  songs = await wavelink.Playable.search(search)
  if not songs:
    return await ctx.send_response("No song found.")

  channel_to_respond[ctx.guild] = ctx.channel
  if not vc:
    vc = await ctx.author.voice.channel.connect(cls=wavelink.Player)
    vc.autoplay = wavelink.AutoPlayMode.partial
  isPlaying = vc.playing
  if songs[0].playlist is None:
    song = songs[0]
    await handle_song(vc, ctx, song, isPlaying)
    return await ctx.send_response("", embed=create_embed_from_song(song, "Playing" if isPlaying else 'Queued', ctx.author))
  for i in range(songs.selected, len(songs)):
    await handle_song(vc, ctx, songs[i], isPlaying)
    isPlaying = True
  return await ctx.send_response("", embed=create_embed_from_playlist(songs, "Playing" if isPlaying else 'Queued', ctx.author, search))


@bot.slash_command(name="fplay")
async def fplay(ctx: discord.ApplicationContext, search: str):
  if ctx.author.id in banned_users:
    await ctx.send_response("Niech ci DjUwU zagra jak jesteś taki cwany")
    return

  if ctx.author.voice is None:
    return await ctx.send_response("You must be in the voice channel.")

  vc = typing.cast(wavelink.Player, ctx.voice_client)
  if vc is not None and vc.channel.id != ctx.author.voice.channel.id:
    return await ctx.send_response("You must be in the same voice channel as the bot.")

  candidates = []
  for file in os.listdir(GLOBAL_DIR):
    if file.find(search) == 0:
      candidates.append(file)
  songs = None
  if candidates:
    candidates.sort()
    songs = await wavelink.Playable.search(os.path.join(GLOBAL_DIR, candidates[0]), source='\\')
  if not songs:
    return await ctx.send_response("No song found.")
  if songs:
    song = songs[0]
    print(song.album)
    print(song.artist)
    print(song.artwork)
    print(song.author)
    print(song.encoded)
    print(song.extras)
    print(song.identifier)
    print(song.is_preview)
    print(song.is_seekable)
    print(song.is_stream)
    print(song.isrc)
    print(song.length)
    print(song.playlist)
    print(song.position)
    print(song.preview_url)
    print(song.raw_data)
    print(song.recommended)
    print(song.source)
    print(song.title)
    print(song.uri)
  channel_to_respond[ctx.guild] = ctx.channel
  if not vc:
    vc = await ctx.author.voice.channel.connect(cls=wavelink.Player)
    vc.autoplay = wavelink.AutoPlayMode.partial
  isPlaying = vc.playing
  if songs[0].playlist is None:
    song = songs[0]
    await handle_song(vc, ctx, song, isPlaying)
    return await ctx.send_response("", embed=create_embed_from_song(song, "Playing" if isPlaying else 'Queued', ctx.author))
  for i in range(songs.selected, len(songs)):
    await handle_song(vc, ctx, songs[i], isPlaying)
    isPlaying = True
  return await ctx.send_response("", embed=create_embed_from_playlist(songs, "Playing" if isPlaying else 'Queued', ctx.author, search))


@bot.slash_command(name="pause")
async def pause(ctx: discord.ApplicationContext):
  vc = typing.cast(wavelink.Player, ctx.voice_client)
  if vc is None or not vc.playing:
    await ctx.send_response(f"bot is not playing anything")

  if ctx.author.voice is None or vc.channel.id != ctx.author.voice.channel.id:
    return await ctx.send_response("You must be in the same voice channel as the bot.")

  await vc.pause(True)
  await ctx.send_response(f"{vc.current.title} paused")


@bot.slash_command(name="resume")
async def resume(ctx: discord.ApplicationContext):
  vc = typing.cast(wavelink.Player, ctx.voice_client)
  if vc is None or not vc.playing:
    await ctx.send_response(f"bot is not playing anything")

  if ctx.author.voice is None or vc.channel.id != ctx.author.voice.channel.id:
    return await ctx.send_response("You must be in the same voice channel as the bot.")

  await vc.pause(False)
  await ctx.send_response(f"{vc.current.title} resumed")



@bot.slash_command(name="skip")
async def skip(ctx: discord.ApplicationContext):
  vc = typing.cast(wavelink.Player, ctx.voice_client)
  if vc is None or not vc.playing:
    return await ctx.send_response("Nawet nic nie gram gamoniu")

  if ctx.author.voice is None or vc.channel.id != ctx.author.voice.channel.id:
    return await ctx.send_response("Nawet nie jesteś na kanale pajacu")

  song = vc.current
  await vc.skip()
  await ctx.send_response(f"{song.title} skipped")


@bot.slash_command(name="skipall")
async def skipall(ctx: discord.ApplicationContext):
  vc = typing.cast(wavelink.Player, ctx.voice_client)
  if vc is None or not vc.playing:
    return await ctx.send_response("Nawet nic nie gram gamoniu")

  if ctx.author.voice is None or vc.channel.id != ctx.author.voice.channel.id:
    return await ctx.send_response("Nawet nie jesteś na kanale pajacu")

  vc.queue.clear()
  await vc.skip()
  await ctx.send_response(f"All song skipped")


@bot.slash_command(name="nskip")
async def nskip(ctx: discord.ApplicationContext, n: int):
  vc = typing.cast(wavelink.Player, ctx.voice_client)
  if vc is None or not vc.playing:
    return await ctx.send_response("Nawet nic nie gram gamoniu")

  if ctx.author.voice is None or vc.channel.id != ctx.author.voice.channel.id:
    return await ctx.send_response("Nawet nie jesteś na kanale pajacu")

  n = min(n, len(vc.queue) + 1)
  for i in range(n - 1):
    vc.queue.delete(0)
  await vc.skip()
  await ctx.send_response(f"{n} songs skipped")


@bot.slash_command(name="queue")
async def queue(ctx: discord.ApplicationContext):
  vc = typing.cast(wavelink.Player, ctx.voice_client)
  if vc is None:
    n = 0
  else:
    n = len(vc.queue)
  embed = discord.Embed(
    title=f"Queue[{n}]",
    color=discord.Colour.blurple(),
  )
  embed.add_field(name="Id", value="", inline=True)
  embed.add_field(name="Title", value="", inline=True)
  embed.add_field(name="Duration", value="", inline=True)

  n = min(n, MAX_QUEUE_EMBED_SIZE)
  for i in range(n):
    embed.add_field(name="", value=f"{i + 1}", inline=True)
    embed.add_field(name="", value=f"[{vc.queue[i].title}]({vc.queue[i].uri})", inline=True)
    seconds = vc.queue[i].length // 1000
    embed.add_field(name="", value=f"{seconds // 60}:{seconds % 60:02d}", inline=True)
  await ctx.send_response("", embed=embed)


@bot.slash_command(name="current")
async def current(ctx: discord.ApplicationContext):
  vc = typing.cast(wavelink.Player, ctx.voice_client)
  if vc is None or not vc.playing:
    return await ctx.send_response(f"Nic nie gram parówo")

  song = vc.current
  seconds = song.length // 1000
  embed = discord.Embed(
    title='Playing',
    description=f"[{song.title}]({song.uri})",
    color=discord.Colour.blurple(),
  )
  embed.set_image(url=song.artwork)
  embed.add_field(name="Duration", value=f"{seconds // 60}:{seconds % 60:02d}", inline=True)
  await ctx.send_response("", embed=embed)


@bot.event
async def on_ready():
  await connect_nodes()
  await bot.sync_commands(commands=bot.application_commands, guild_ids=[guild.id for guild in bot.guilds], force=True)
  for guild in bot.guilds:
    channel_to_respond[guild] = None

@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
  print(f"Node with ID {payload.session_id} has connected")
  print(f"Resumed session: {payload.resumed}")


@commands.Cog.listener()
async def on_wavelink_track_end(event: wavelink.TrackEndEventPayload):
  if not event.player.queue:
    if channel_to_respond[event.player.guild] is not None:
      await channel_to_respond[event.player.guild].send('Mio byo ci sużyć')
      channel_to_respond[event.player.guild] = None
    await event.player.disconnect()


dotenv.load_dotenv()
bot.add_listener(on_wavelink_track_end)
bot.run(str(os.getenv("TOKEN")))