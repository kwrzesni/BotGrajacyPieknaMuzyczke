import discord
import wavelink
import typing
import dotenv
import os
from discord.ext import commands

bot = discord.Bot()
channel_to_respond = {}
wisnia_id = 447457072725098506

def create_embed_from_song(song, title, author):
  seconds = song.length // 1000
  embed = discord.Embed(
    title=title,
    description=f"[{song.title}]({song.uri})",
    color=discord.Colour.blurple(),  # Pycord provides a class with default colors you can choose from
  )
  embed.set_image(url=song.artwork)
  embed.add_field(name="Requested by", value=f"{author.mention}", inline=True)
  embed.add_field(name="Duration", value=f"{seconds//60}:{seconds%60:02d}", inline=True)
  return embed


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
  if ctx.author.id == wisnia_id:
    await ctx.send_response("Niech ci DjUwU zagra jak jesteś taki cwany")
    return

  if ctx.author.voice is None:
    return await ctx.send_response("You must be in the voice channel.")

  vc = typing.cast(wavelink.Player, ctx.voice_client)
  if vc is not None and vc.channel.id != ctx.author.voice.channel.id:
    return await ctx.send_response("You must be in the same voice channel as the bot.")

  song = await wavelink.Playable.search(search)
  if not song:
    return await ctx.send_response("No song found.")
  else:
    song = song[0]

  channel_to_respond[ctx.guild] = ctx.channel
  if not vc:
    vc = await ctx.author.voice.channel.connect(cls=wavelink.Player)
    vc.autoplay = wavelink.AutoPlayMode.partial
    await vc.play(song)
    await ctx.send_response("", embed=create_embed_from_song(song, "Playing", ctx.author))
  elif not vc.playing:
    await vc.play(song)
    await ctx.send_response("", embed=create_embed_from_song(song, "Playing", ctx.author))
  else:
    vc.queue.put(song)
    await ctx.send_response("", embed=create_embed_from_song(song, "Queued", ctx.author))


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
    await ctx.send_response(f"bot is not playing anything")

  if ctx.author.voice is None or vc.channel.id != ctx.author.voice.channel.id:
    return await ctx.send_response("You must be in the same voice channel as the bot.")

  song = vc.current
  await vc.skip()
  await ctx.send_response(f"{song.title} skipped")



@bot.slash_command(name="queue")
async def queue(ctx: discord.ApplicationContext):
  vc = typing.cast(wavelink.Player, ctx.voice_client)
  if vc is None or not vc.playing:
    await ctx.send_response(f"bot is not playing anything")

  if ctx.author.voice is None or vc.channel.id != ctx.author.voice.channel.id:
    return await ctx.send_response("You must be in the same voice channel as the bot.")

  out = '**queue:**\n'
  for song in vc.queue:
    out += song.title + '\n'
  await ctx.send_response(out)


@bot.slash_command(name="current")
async def current(ctx: discord.ApplicationContext):
  vc = typing.cast(wavelink.Player, ctx.voice_client)
  if vc is None or not vc.playing:
    await ctx.send_response(f"bot is not playing anything")

  if ctx.author.voice is None or vc.channel.id != ctx.author.voice.channel.id:
    return await ctx.send_response("You must be in the same voice channel as the bot.")

  song = vc.current
  await ctx.send_response(f"{song.title}")


@bot.event
async def on_ready():
  await connect_nodes()
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