from dotenv import load_dotenv
from datetime import datetime, timedelta
from discord.ext import commands, tasks
import sqlite3 as sql
import os
import subprocess
import discord
import asyncio
import random
[4, 8, 15, 16, 23, 42]
print("Starting up...")

# TODO 2 look through code and find ratelimit optimizations
# TODO 4 Add more prints now that they don't look like ass
# TODO 5 Make sure the new sync code works properly
# TODO 4 i can probably enable -m with no problems

# Create database link
db = sql.connect('database.db')
#db = sql.connect(':memory:')
cursor = db.cursor()

# Load .env
load_dotenv()
key = os.environ.get('key')

intents = discord.Intents.default()
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="f!", intent=intents, case_insensitive=True)
bot.remove_command("help")



# Returns a random hexadecimal value from a given seed
async def getRandomHex(seed):
	random.seed(seed)
	return random.randint(0, 16777215)

# Creates a standard Embed object
async def getEmbed(ctx, title='', content='', footer=''):
	embed = discord.Embed(
		title=title,
		description=content,
		color=await getRandomHex(ctx.author.id)
	)
	embed.set_author(name=ctx.author.display_name,
					 icon_url=ctx.author.avatar_url)
	# embed.set_footer(footer=footer)
	return embed

# Creates and sends an Embed message
async def send(ctx, title='', content='', footer=''):
	embed = await getEmbed(ctx, title, content, footer)
	return await ctx.send(embed=embed)

# Make sure tables exist for all servers bot is in
async def updateDB():
	guilds = bot.guilds
	cursor.execute("SELECT id FROM Servers")
	dbGuilds = cursor.fetchall()

	for guild in guilds:  # Loop through each server reported by discord
		for guildTpl in dbGuilds:  # Loop through each entry pulled from db
			if guild.id == guildTpl[0]:  # If guild id is in database
				dbGuilds.remove(guildTpl)  # Remove the match from the database pull
				guilds.remove(guild) # Remove the match from the api pull

	if len(guilds) != 0: # entries not in database
		for guild in guilds:
			pront("WARNING", f"Cleaning found new server {guild.name} ({guild.id}), adding to database")
			cursor.execute("INSERT INTO Servers (id, channel, options) VALUES (?, ?, ?)", (guild.id, None, None))

	if len(dbGuilds) != 0:  # entries not in discord
		for guild in dbGuilds:
			pront("WARNING", f"Cleaning found extra server {guild[0]}, removing from database")
			cursor.execute("DELETE FROM Servers WHERE id=?", (guild[0],))

	db.commit()

# Refresh the bot's status to match server counts
async def refreshStatus():
	await updateDB()
	cursor.execute('SELECT id FROM Servers')
	cachedServers = len(cursor.fetchall())
	servers = len(bot.guilds)
	if cachedServers != servers:
		pront("ERROR",
			"!!!!!!!!!!!COUNT OF CACHED SERVERS MISSING DISCORD LISTED SERVERS!!!!!!!!!!!!")
		pront("ERROR", f'cachedServers = {cachedServers}')
		pront("ERROR", f'serverCount = {servers}')
	await bot.change_presence(activity=discord.Activity(
		type=discord.ActivityType.watching, name=f"for f! in {servers:,} servers!"))

# Build database tables if they don't already exist
async def buildtables():
	cursor.execute(
		"SELECT name FROM sqlite_master WHERE type='table' AND name='Servers';")
	if cursor.fetchone() is None:
		pront("WARNING", 'Servers table not found, creating...')
		cursor.execute("""
			CREATE TABLE Servers (
			id INTEGER KEY,
			channel INTEGER,
			options STRING
			);
		""")
		db.commit()
	cursor.execute(
		"SELECT name FROM sqlite_master WHERE type='table' AND name='feedback';")
	if cursor.fetchone() is None:
		pront("WARNING", 'feedback table not found, creating...')
		cursor.execute("""
		CREATE TABLE feedback (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			server STRING,
			user STRING,
			message STRING
			);
		""")
		db.commit()
	cursor.execute(
		"SELECT name FROM sqlite_master WHERE type='table' AND name='bannedFeedback';")
	if cursor.fetchone() is None:
		pront("WARNING", 'table bannedFeedback not found, creating...')
		cursor.execute("""
			CREATE TABLE bannedFeedback (
			id INTEGER KEY,
			reason STRING
			);
		""")
		db.commit()

# Print function
def pront(lvl, content):
	colors = {
		"LOG" : "",
		"OKBLUE" : "\033[94m",
		"OKCYAN" : "\033[96m",
		"OKGREEN" : "\033[92m",
		"WARNING" : "\033[93m",
		"ERROR" : "\033[91m",
		"NONE" : "\033[0m"
	}
	print(colors[lvl] + "{" + datetime.now().strftime("%x %X") + "} " + lvl + ": " + str(content) + colors["NONE"])

# Function to check if args contain illegal options
def restricted(args):
	restricted = ["f", "m", "n", "w"]
	for restriction in restricted:
		for a in args:
			# Skip empty strings
			if len(a) == 0:
				continue
			# If the first character is a dash
			if a[0] == "-":
				# If the argument also has an illegal character
				if a.find(restriction) != -1:
					return True
	return False

##
## Bot Events
##

# When bot connects to Discord
@bot.event
async def on_ready():
	pront('LOG', 'Bot Online!')
	await buildtables()
	await refreshStatus()
	cursor.execute('SELECT id FROM Servers')
	pront('LOG', 'Registered server IDs: ' + str(cursor.fetchall()))
	pront('LOG', 'Discord listed server IDs:' + str(bot.guilds))
	fortune.start()

# Custom error handler
@bot.event
async def on_command_error(ctx, error):
	# If an unknown command is issued
	if isinstance(error, discord.ext.commands.errors.CommandNotFound):
		await send(ctx, 'Command not found:', f'{str(error)} is not a valid command, please refer to f!help for a list of commands.')
		return

	# If the bot doesn't have high enough permissions to do something
	if isinstance(getattr(error, 'original', error), discord.Forbidden):
		embed = await getEmbed(ctx, "The bot doesn't have enough permissions to do this!")
		embed.add_field(name='What went wrong:',
						value="This error appears when the bot doesn't have the permissions it needs.  This is likely caused by the order of roles in this server.", inline=True)
		embed.add_field(name='How to fix it:',
						value=f"Most likely you can fix this by moving the role created for the bot ({ctx.guild.self_role.mention}) to the top of your server's role list.  If the issue persists, feel free to submit a bug report with f!feedback!", inline=True)
		await ctx.send(embed=embed)
		return

	# If a command is on cooldown
	if isinstance(error, commands.CommandOnCooldown):
		await send(ctx, 'Command on cooldown:', f'This command is on cooldown, please try again in {round(error.retry_after)} seconds.')
		return

	# If the user isn't allowed to use a command
	if isinstance(error, commands.MissingPermissions):
		await send(ctx, 'Insufficient permissions:', 'You do not have the required permissions to run this command.')

	# If we're being ratelimited (uh oh)
	if isinstance(error, discord.HTTPException):
		await send(ctx, "The bot is currently being ratelimited!", "Please report this to the developer with f!feedback alongside what you were doing to cause this!")
		pront("ERROR", "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
		pront("ERROR", "being ratelimited fuck fuck fuck")
		pront("ERROR", str(error))
		pront("ERROR", "@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
		raise error

	pront("ERROR", str(error))
	# Send generic error message if none of the above apply
	embed = await getEmbed(ctx, 'Oops!  Something just went wrong...', error)
	embed.add_field(name='Bug Reports:', value="If this looks like it's a bug, please report it with f!feedback!  Make sure to include details on how to reproduce the bug and I'll patch it as soon as I can!", inline=False)
	await ctx.send(embed=embed)
	raise error

# When the bot joins a new guild
@bot.event
async def on_guild_join(guild):
	# Update the status (updateDB() will catch the new guild)
	await refreshStatus()
	# Loop through channels until we find one we can send the welcome message in	
	for channel in guild.text_channels:
		if channel.permissions_for(guild.me).send_messages:
			embed = discord.Embed(
				title='Thanks for adding Fortune Bot!',
				description='Thank you for adding Fortune Bot, my prefix is "f!" Try `f!help setup` to get started!',
				color=await getRandomHex(guild.id)
			)
			embed.set_author(
				name=guild.name,
				icon_url=guild.icon_url
			)
			await channel.send(embed=embed)
			break

# When the bot is removed from a guild :(
@bot.event
async def on_guild_remove(guild):
	pront("WARNING", f"{guild.name} has removed the bot, clearing from DB.")
	# Purge server from database
	cursor.execute('SELECT id FROM Servers')
	serverList = cursor.fetchall()
	if (guild.id, ) not in serverList:
		pront("ERROR", "!!!!!!!!!!!!!!LEFT UNDOCUMENTED SERVER HOW THE FUCK!!!!!!!!!!!!!!")
		return
	cursor.execute('DELETE FROM Servers WHERE id=?',(guild.id,))
	db.commit()
	# Update the status to match
	await refreshStatus()

# When a reaction is added to a message
@bot.event
async def on_raw_reaction_add(payload):
	# If the event was triggered by the bot
	if payload.user_id == bot.user.id:
		return

	# Do nothing if it is not a unicode emoji
	if not payload.emoji.is_unicode_emoji():
		return

	# If it's an emoji we don't care about
	emojis = ["🌟", "❌"]
	if payload.emoji.name not in emojis:
		return

	# If it's in DMs get the message from DMs
	if payload.member is None:
		user = await bot.fetch_user(payload.user_id)
		message = await user.fetch_message(payload.message_id)
	# Otherwise get it normally
	else:
		message = await bot.get_channel(payload.channel_id).fetch_message(payload.message_id)

	reaction = discord.utils.get(message.reactions)

	# If the reaction wasn't started by the bot
	if not reaction.me:
		return

	# If the reaction was a star (and it's in a server)
	if reaction.emoji == "🌟" and payload.member is not None:
		embed = discord.Embed(
			title=f"Favorited fortune from {message.guild.name}:",
			url=message.jump_url,
			description=message.embeds[0].description,
			color=await getRandomHex(message.guild.id)
		)
		embed.set_author(
			name=message.guild.name,
			icon_url=message.guild.icon_url
		)
		message = await payload.member.send(embed=embed)
		await message.add_reaction("❌")
		return

	# If the reaction was a x (and it's not in a server)
	if reaction.emoji == "❌" and payload.member is None:
		await message.delete()

##
## Tasks
##

# Task to print a fortune every 24 hours
@tasks.loop(seconds = 0)
async def fortune():
	# Synchronize fortune task
	time = datetime.now()
	
	# Calculate ~how long to wait
	if int(time.strftime("%H")) < 12: # If we don't have to wait another day
		target = datetime.today().replace(hour = 12, minute = 00, second = 00, microsecond = 0)
	else: # Otherwise
		target = (datetime.today() + timedelta(days=1)).replace(hour = 12, minute = 00, second = 00, microsecond = 0)

	delta = target-time
	if delta.total_seconds() < 0:
		pront("ERROR", "Time calculation delta returned negative value (%s" % delta + "), something has gone horribly wrong")
		return
	
	pront("OKBLUE", 'Entering cryogenic storage for: %s' % delta + " until %s " % target)
	await asyncio.sleep(delta.total_seconds())
	pront("OKGREEN", 'Cryogenic freeze completed, we are now in the future! ' + str(datetime.now()))

	if datetime.now().strftime("%H:%M") != "12:00":
		pront("ERROR", "Stupid time calculation was wrong, we're off!  It's actually %s" % datetime.now())

	
	# Declare time now so the exec duration of fortune doesn't matter
	time = datetime.now()
	pront("LOG", "Fortunes are going out")
	cursor.execute("SELECT * FROM Servers")
	servers = cursor.fetchall()
	# Loop through every server in the database
	for server in servers:
		if server[1] is None:
			pront("WARNING", server[0] + " has no set channel, skipping.")
			continue

		ctx = bot.get_channel(server[1])
		options = server[2]

		# If we couldn't find the channel for fortunes
		if ctx is None:
			pront("WARNING", "Could not find channel for " + server[0] + " even though it exists")
			continue

		# Split stored options into argument array
		args = ['fortune']

		# If there are options set
		if options is not None:
			args += options.split(" ")
		
		# Execute fortune with the guild's options
		result = subprocess.run(args, stdout=subprocess.PIPE, text=True).stdout

		# Replace poor formatting
		result = result.replace('```', "'''")
		result = result.replace('\t', '        ')
		# If there's just a % on a line (it's junk data)
		result = result.replace('\n%\n', '\n\n')

		embed = discord.Embed(
			title='Daily fortune:',
			description=f"```ansi\n{result}\n```",  # Ansi formatting to make Android clients full box
			color=await getRandomHex(server[0])
		)
		embed.set_author(
			name=ctx.guild.name,
			icon_url=ctx.guild.icon_url
		)
		message = await ctx.send(embed=embed)
		await message.add_reaction("🌟")

	pront("OKGREEN", "Fortunes completed, took " + str(datetime.now() - time) + " to complete.")

	# Flag for fortune taking longer than a minute to exec
	if time.strftime("%H:%M") != datetime.now().strftime("%H:%M"):
		pront("ERROR", "!!!!!!!!!!!!!!!!!!!!\nFortune task took > 1 minute to execute, DO SOMETHING\n!!!!!!!!!!!!!!!!!!!!")

	# Refresh the bot's status just for fun
	await refreshStatus()

	# Safeguard against fortune desync
	if time.strftime("%H:%M") != "12:00":
		pront("ERROR", "Fortune task has become desynced with system time!")

##
## Commands
##

# Help command
@bot.command()
async def help(ctx, helpType=None):
	# Function to add the options for help to an embed
	async def elaborate(embed):
		embed.add_field(name="Setup", value="Gives details on how to configure the bot in your server.")
		embed.add_field(name="Commands", value="A list of commands and a small example about how to use them.")
		await ctx.send(embed=embed)
	# If the user wants help setting up the bot
	if helpType == 'setup':
		await send(ctx, 'Helping with Setup', """Simply run `f!channel` followed by the channel you want fortunes to be posted into. The bot will post in that channel on the next daily cycle!\n\n
			If you want to set custom options, like the chance for a category of fortune to appear, use f!options with the options you want from https://linux.die.net/man/6/fortune.
		""")
		return
	# List the bot's commands
	elif helpType == 'commands':
		embed = await getEmbed(ctx, 'Helping describe commands')
		embed.add_field(name="list [options]:", value="Prints the categories of fortune to be drawn from and the % chance that it will be chosen with the server's options (or the ones specified to the command).  Usage example: `f!list -a`")
		embed.add_field(name="channel (channel):", value="Sets the channel the bot will post fortunes into. Usage example: `f!channel #fortunes`")
		embed.add_field(name="options (options):", value="Set options for fortunes in this server, use https://linux.die.net/man/6/fortune as a reference to what's supported. Usage example: `f!options -e startrek cookie`")
		embed.add_field(name="feedback (message):", value="Allows you to send feedback to the developer of this bot. An example of the feedback command in use would look like 'f!feedback this bot is great!'")
		embed.add_field(name="Key:", value="`()` = Mandatory argument\n`[]` = Optional argument")
		await ctx.send(embed=embed)
		return
	# If no helpType is asked for
	elif helpType == None:
		embed = await getEmbed(ctx, 'This command requires one of the following arguments:')
		await elaborate(embed)
	# If an invalid helpType is asked for
	else:
		embed = await getEmbed(ctx, "That isn't a valid help argument! Try one of the following instead:")
		await elaborate(embed)
		return

# Alias individual commands to help categories (i saw people trying to see help categories like this so i implemented it)

# Send commands alias
@bot.command(aliases=['commands'])
async def command(ctx):
	await help(ctx, 'commands')

# Send setup alias
@bot.command()
async def setup(ctx):
	await help(ctx, 'setup')

# End Help

# List all fortunes
@bot.command(aliases=['list', 'fortune'])
@commands.has_guild_permissions(manage_channels=True)
@commands.cooldown(1,5,commands.BucketType.user)
async def fortunes(ctx, *, arg=''):
	args = ['fortune']
	options = None
	if arg != '':  # If an arg is provided
		if arg.lower() != "none":
			options = arg
			args += arg.split(" ")
		# Make sure no restricted arguments try to pass
		if (restricted(args)):
			await send(ctx, "Illegal options detected!", "The options `-f`, `-m`, `-n`, and `-w` are disabled for security reasons and cannot be used!")
			return		
	else:  # Otherwise pull from DB
		cursor.execute("SELECT options FROM Servers WHERE id=?", (ctx.guild.id,))
		options = cursor.fetchone()[0]
		if options is not None:
			args += options.split(" ")

	args.insert(1, "-f",) # Add -f after all of that to avoid restricted yelling
	
	fortuneCall = subprocess.run(args, stderr=subprocess.PIPE, text=True)

	# Exit code is 0 through -f flag, read exit code to find errors
	if fortuneCall.returncode != 0:
		# Format stderr for printing, make newlines actually work, etc.
		stderr = fortuneCall.stderr.replace('\\n', '\n').replace('\\t', '\t')
		embed = await getEmbed(ctx, "Something went wrong getting categories!", 
			f"""The option{'s' if len(args) > 2 else ''} `{options}` w{'ere' if len(args) > 2 else 'as'} not accepted by fortune.\n 
			Please refer to https://linux.die.net/man/6/fortune for a list of all options.""")
		embed.add_field(name="Error:", value="```ansi\n" + stderr + "```", inline=True)
		await ctx.send(embed=embed)
		return

	fortunes = fortuneCall.stderr.replace("/usr/share/games/", "").replace('\\n', '\n').replace('\\t', '\t')

	suffix = f"the option{'s' if len(args) > 2 else ''} `" + options + "`" if options is not None else 'no options'
	message = await send(ctx, "Listing fortunes:", f"List fortune categories and % chances with " + suffix + f":\n```ansi\n{fortunes}```")
	embed = await getEmbed(ctx, "Listing fortunes:", "Fortunes have been hidden to keep chat clean.")
	await asyncio.sleep(300)
	await message.edit(embed=embed)

# Sets the channel the bot uses for fortunes
@bot.command()
@commands.has_guild_permissions(manage_channels=True)
@commands.cooldown(1,5,commands.BucketType.user)
async def channel(ctx, *, arg=''):
	# Pull guild's channel
	cursor.execute('SELECT channel FROM Servers WHERE id=?',(ctx.guild.id,))
	channelID = cursor.fetchone()[0]
	# Can't guild.get_channel of None so do a little trolling
	#if channelID == None:
	#	channelID = -1
	storedChannel = ctx.guild.get_channel(channelID)

	# If we can't find the channel but it has been set
	if storedChannel is None and channelID != None:
		pront("WARNING", ctx.guild.name + "'s previous channel was deleted")
		cursor.execute('UPDATE Servers SET channel=? WHERE id=?', (None, ctx.guild.id))
		db.commit()

	# If there isn't a channel mentioned
	if not ctx.message.channel_mentions:
		# If we don't already have a channel set
		if channelID == None:
			await send(ctx, 'There is no channel set.', 'Please mention a channel for the bot to post fortunes into.')
			return
		# If we do, say what it is
		await send(ctx, 'Current channel:', f'The current channel is `{storedChannel}`, please mention a different channel with f!channel to change it.')
		return
	
	channel = ctx.message.channel_mentions
	# Channel mention count check
	if len(channel) > 1:
		await send(ctx, 'Too many channels mentioned!', "You can't have multiple fortune channels!\n\nPlease ping *one* channel to use.")
		return

	channel = channel[0]
	# Already channel
	if channel.id == channelID:
		await send(ctx, 'Error changing channel!', f'`{channel.name}` is already being used for fortunes!')
		return

	# Checks if this is the first time entering a channel
	if storedChannel is None or channelID is None:
		suffix = f'to `{channel.name}`'
	else:
		suffix = f'from `{storedChannel.name}` to `{channel.name}`'

	await send(ctx, 'Changing channel:', f'Changing the channel where fortunes are sent {suffix}.')
	# Push the new channel to the database
	cursor.execute('UPDATE Servers SET channel=? WHERE id=?', (channel.id, ctx.guild.id))
	db.commit()

# Set options for the fortune task
@bot.command(aliases=['option', 'setoptions'])
@commands.has_guild_permissions(manage_channels=True)
@commands.cooldown(1,5,commands.BucketType.user)
async def options(ctx, *, arg=''):

	# If user does not provide any options
	if arg == '':
		cursor.execute("SELECT options FROM Servers WHERE id=?", (ctx.guild.id,))
		options = cursor.fetchone()[0]
		# If there are options set
		if options is not None:
			embed = await getEmbed(ctx, "Current options:", f"`{options}`")
			embed.add_field(name='Tip:', value="If you want to clear your options, run `f!options None`.", inline=False)
			await ctx.send(embed=embed)
			return
		await send(ctx, "You need to specify options!", "To see all options, refer to https://linux.die.net/man/6/fortune")
		return
	
	# If the user wants to clear the options
	if arg.lower() == "none":
		cursor.execute("UPDATE Servers SET options=? WHERE id=?", (None, ctx.guild.id))
		db.commit()
		await send(ctx, "Options reset!")
		return

	# The user definitely wants us to set options now

	# Split input into argument array
	args = ['fortune'] + arg.split(" ")

	# Make sure no restricted arguments try to pass
	if (restricted(args)):
		await send(ctx, "Illegal options detected!", "The options `-f`, `-m`, `-n`, and `-w` are disabled for security reasons and cannot be set as options!")
		return			

	# Redirect to /dev/null to supress cmd output
	fortuneCall = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

	# If the return code indicates an error
	if fortuneCall.returncode != 0:
		# Format stderr for printing, make newlines actually work, etc.
		stderr = fortuneCall.stderr.decode("utf-8").replace('\\n', '\n').replace('\\t', '\t')

		embed = await getEmbed(ctx, "Something went wrong setting the options!", 
		"""The options you specified were not accepted by fortune.\n 
		Please refer to https://linux.die.net/man/6/fortune for a list of all options.""")
		embed.add_field(name="Error:", value="```ansi\n" + stderr + "```", inline=True)
		await ctx.send(embed=embed)
		return
	cursor.execute("UPDATE Servers SET options=? WHERE id=?", (arg, ctx.guild.id))
	db.commit()
	await send(ctx, "Success!", f"The option{'s' if len(args) > 2 else ''} `{arg}` ha{'ve' if len(args) > 2 else 's'} been successfully set.")


# Feedback command (300 second cooldown)
@bot.command()
@commands.cooldown(1,300,commands.BucketType.user)
async def feedback(ctx, *, arg=''):
	# If user is banned don't let them send feedback
	cursor.execute('SELECT id FROM bannedFeedback WHERE id=?', (ctx.author.id,))
	if cursor.fetchone() is not None:
		cursor.execute('SELECT reason FROM bannedFeedback WHERE id=?', (ctx.author.id,))
		reason = cursor.fetchone()[0]
		await send(ctx, 'You are banned from using this command for:', reason)
		return
	# If the user doesn't provide any feedback in the command
	if arg is None:
		await send(ctx, 'This command requires an argument.')
		return
	cursor.execute('INSERT INTO feedback (server, user, message) VALUES (?, ?, ?)', (int(ctx.guild.id), int(ctx.message.author.id), str(arg)))
	db.commit()
	await send(ctx, 'Thanks!', 'Your feedback is appreciated, thank you!')

# End Feedback

# Read me the feedback
@bot.command()
@commands.is_owner()
async def readFeedback(ctx):
	result = cursor.execute(f'SELECT * FROM feedback')
	for row in result:
		guild = bot.get_guild(row[1])
		user = bot.get_user(row[2])
		try:
			row = (row[0], guild.name, user.name, row[3])
		except:
			pront("ERROR", f'Something went wrong translating row {row[0]}')
		finally:
			message = await ctx.author.send(row)
			await message.add_reaction("❌")

# Reply to the user who sent me feedback
@bot.command()
@commands.is_owner()
async def replyFeedback(ctx, feedbackIndex, *, message="The developer fucked up and didn't leave a reply! lmao!"):
	feedback = cursor.execute('SELECT * FROM feedback')
	for entry in feedback:
		if entry[0] == int(feedbackIndex):
			# Break down database tuple
			guild = bot.get_guild(entry[1])
			user = bot.get_user(entry[2])
			# Provide a sample of their message
			feedbackMsg = entry[3][11:21].rstrip()
			if len(entry[3]) > 21:
				feedbackMsg += '...'
			embed = await getEmbed(ctx, f"Reply from developer about your post `{feedbackMsg}` in `{guild.name}`:", message)
			embed.add_field(name='A quick note:', value='Please note that any responses you make in DMs do not go back to the developer, if you need to make a follow-up message please send f!feedback, preferably in the same server you sent the first message.', inline=False)
			await user.send(embed=embed)
			await send(ctx, 'Message sent!')
			break

# Ban a user from using the feedback command
@bot.command()
@commands.is_owner()
async def banFeedback(ctx, id='', *, reason=''):
	if ctx.message.mentions:
		id = ctx.message.mentions[0].id
	if id is None:
		await send(ctx, 'You need to send a uID to ban or ping a user!')
		return
	if reason == '':
		await send(ctx, 'You need to send a reason for the ban!')
		return
	cursor.execute('INSERT INTO bannedFeedback (id, reason) VALUES (?, ?)', (int(id), reason))
	db.commit()
	await send(ctx, 'Done!')

# Unban a user from using the feedback command
@bot.command()
@commands.is_owner()
async def unbanFeedback(ctx, id=''):
	if id is None:
		await send(ctx, 'You need to send a uID to unban!')
		return
	if ctx.message.mentions:
		id = ctx.message.mentions[0].id
	cursor.execute('SELECT id FROM bannedFeedback WHERE id=?', (id,))
	if cursor.fetchone() is None:
		await send(ctx, "This isn't the ID of a banned user!")
	cursor.execute('DELETE FROM bannedFeedback WHERE id=?', (id,))
	await send(ctx, 'Done!')

# Clear the feedback messages currently in db
@bot.command()
@commands.is_owner()
async def clearFeedback(ctx):
  await ctx.send('Clearing...')
  cursor.execute('DROP TABLE feedback ;')
  db.commit()
  cursor.execute("""
	CREATE TABLE feedback (
	  id INTEGER PRIMARY KEY AUTOINCREMENT,
	  server STRING,
	  user STRING,
	  message STRING
	);
	""")
  db.commit()
  await ctx.send('Cleared!')

# Clear dms with me
@bot.command()
@commands.is_owner()
async def clearDMs(ctx):
	await send(ctx, 'Beginning purge...')
	async for message in ctx.author.history(limit=100000):
		if message.author == bot.user:
			await message.delete()
	await send(ctx, 'Purge done.')

# Send raw commands to the SQL DB
@bot.command()
@commands.is_owner()
async def editDB(ctx, *, arg):
	cursor.execute(arg)
	db.commit()
	await send(ctx, 'Changes commited to DB.')

# Send raw read commands to the SQL DB
@bot.command()
@commands.is_owner()
async def readDB(ctx, *, arg):
	cursor.execute(arg)
	await send(ctx, f'Result of {arg}:', cursor.fetchall())

# Evaluate a command sent by me
@bot.command(aliases=['eval'])
@commands.is_owner()
async def execute(ctx, *, arg):
	result = eval(arg)
	if result is not None:
		await send(ctx, "Eval result:", result)
		return
	await send(ctx, "Eval returned a NoneType.")

# Modular command from Nick's demands
import discord.ext.commands.errors
@bot.command()
async def cum(ctx):
	if ctx.author.id != 334836951037509634:
		raise discord.ext.commands.errors.CommandNotFound(message='Command "cum"')
	if ctx.guild.voice_client is not None:
		pront("LOG", 'already in vc, leaving.')
		await ctx.voice_client.disconnect()
		return
	authorStatus = ctx.author.voice
	if authorStatus is None or ctx.author.voice.channel is None:
		await ctx.send('join vc and run again')
		return
	voice_channel = ctx.author.voice.channel
	vc = await voice_channel.connect()
	fileArray = os.listdir('/home/pi/bot/audio/')
	rng = random.randint(0, len(fileArray)-1)
	song = fileArray[rng]
	pront("LOG", song)
	vc.play(discord.FFmpegPCMAudio(f'/home/pi/bot/audio/{song}'))
	while vc.is_playing():
		await asyncio.sleep(1)
	if ctx.guild.voice_client is None:
		return
	await ctx.voice_client.disconnect()

bot.run(key)