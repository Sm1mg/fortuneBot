[4,8,15,16,23,42]
print("Starting up...")

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv


# Load .env
load_dotenv()
key=os.environ.get('key')

intents = discord.Intents.default()
intents.members = True

bot = commands.bot(command_prefix = "f!", intents=intents, case_insensitive=True)
bot.remove_command("help")

opts = None

@bot.event()
async def on_ready():
	print('Bot online!')

@bot.command()
async def setopts(ctx, *, opts)
	global opts
	opts = opts

@bot.command()
async def setchannel(ctx, 

bot.run(key)
