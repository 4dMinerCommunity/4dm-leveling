import nextcord, nextcord.ext.commands
from sqlite3 import connect 

import time
from asyncio import create_task as unawait
import re  # regex
from typing import Optional

from env import *  # api keys
from settings import *

log = print
if not DEBUG: log = lambda *_: None  # disable log on release

############# CLIENT INITIALIZATION #############

intents = nextcord.Intents.default()
intents.message_content = True
intents.members = True
intents.typing = False

log(list(intents))
client = nextcord.ext.commands.Bot( command_prefix='!', intents=intents, default_guild_ids=BOT_SERVER_IDS )

############# LIBRARY #############

# in case dc ever changes how they measure stringlength AGAIN
def dcStrlen(string): return len(string)

# get xp, level, ... of user_id, and create user entry if it doesn't exist
def get_userlevel(user_id):
  
  #check if user is in the db
  if database.execute("SELECT id FROM users WHERE id = ?", (str(user_id),)).fetchone() is None:
    database.execute("INSERT INTO users VALUES (?, ?, ?)", (str(user_id), 0, 0))
  
  xp, level = database.execute("SELECT xp, level FROM users WHERE id = ?", (str(user_id),) ).fetchone()
  
  return xp, level

def get_totalxp(xp,level):
  # yes I know you could get a direct math equation for that sum but then you need to manage 2 equations,
  # here you can just change LEVELUP_XP to whatever. The runtime difference is negligible
  return xp + sum( LEVELUP_XP(lvl) for lvl in range(level) )

# returns rank as int or None if unranked (level 0)
def get_user_rank(xp,level):
  # xp, level = get_userlevel(user_id)
  
  if level < 1:
    return None
  
  rank = database.execute( "SELECT count(*)+1 FROM users WHERE level > ? OR ( level = ? AND xp > ? )", (level,level,xp) ).fetchone()[0]
  
  return rank

async def getUserName(user_id):
  user_id = int(user_id)  # you would not believe how many issues this caused, I wasted 3 hours on this shit. Fuck soft typing, fuck nextcord, fuck sqlite
  
  if check_snitchtome(user_id):
    return f'<@{user_id}>'
  
  # get from cache
  if client.get_user(user_id):
    return f'`{client.get_user(user_id)}`'
  
  # get fresh
  try:
    log(f'trying to fetch unknown user <@{user_id}>')
    return f'`{await client.fetch_user(user_id)}`'
  except:
    log(f'failed to fetch unknown user <@{user_id}>')
    return f'`<@{user_id}>`'
  

def parseIntInput(num,default,min=None,max=None):
  try: num = int(num)
  except: num = default
  
  if min is not None:
    if num < min: num = min
  if max is not None:
    if num > max: num = max
  
  return num

def intToWidth(int,width):
  int = str(int)
  int = (width-len(int))*' ' + int
  return int

############# LEADERBOARD COMMAND #############

async def get_leaderboard_msg( page: int, pagesize: int, is_xp_leaderboard: bool = False ) -> str:
  
  no_users = database.execute( "SELECT COUNT(*) FROM users WHERE level > 0 " ).fetchone()[0]
  no_pages = ( no_users + pagesize - 1 )//pagesize
  
  if page > no_pages:
    page = no_pages
  
  no_skippedUsers = (page-1)*pagesize
  
  data = database.execute( "SELECT id, xp, level FROM users WHERE level > 0 ORDER BY level DESC, xp DESC, id ASC LIMIT ? OFFSET ?", (pagesize,no_skippedUsers) ).fetchall()
  data = tuple(map(list,data))
  
  # generate the rank (difficult because of ties, especially ties starting before current page)
  for i, [user_id, xp, level] in enumerate(data):
    
    try:
      if xp != oldxp or level != oldlvl:
        rank = no_skippedUsers+1 + i
    except:  # first run
      rank = get_user_rank(xp,level)
    oldxp,oldlvl = xp,level
    
    data[i].append(rank)
  
  width_rank    = len(str( data[-1][3] ))
  if is_xp_leaderboard:
    width_totalxp = len(str( get_totalxp(data[0][1],data[0][2]) ))
  else:
    width_level   = len(str( data[0][2] ))
    width_xp      = len(str( max( row[1] for row in data ) )) # man this would be so much easier with numpy
    width_lvlupxp = len(str( LEVELUP_XP(data[0][2]) ))
    
  
  chunks = [ f"**LEADERBOARD page {page}/{no_pages}**\n" ]
  for user_id, xp, level, rank in data:
    rank = intToWidth(rank,width_rank)
    
    if is_xp_leaderboard:
      totalxp = get_totalxp(xp,level)
      row = f"`Rank {rank} - {intToWidth(totalxp,width_totalxp)} XP:` {await getUserName(user_id)}\n"
    else:
      row = f"`Rank {rank} - Level {intToWidth(level,width_level)} ({intToWidth(xp,width_xp)}/{intToWidth(LEVELUP_XP(level),width_lvlupxp)}):` {await getUserName(user_id)}\n"
    
    if dcStrlen(chunks[-1]+row) > DISCORD_CHAR_LIMIT:  # this row would make message too long, start new block
      chunks.append("")
    
    chunks[-1] += row
  
  return chunks

@client.slash_command(description="List the top ranked (most 'active') users")
async def leaderboard(message:  nextcord.Interaction,
  page: int = nextcord.SlashOption(name="page", required=False, default=1, min_value=1),
  pagesize: int = nextcord.SlashOption(name="pagesize", required=False, default=10, min_value=1, max_value=MAX_LEADERBOARD_SIZE),
) -> None:
  log(f'/leaderboard {page} {pagesize}')
  
  chunks = await get_leaderboard_msg( page, pagesize )
  
  await message.send(chunks.pop(0))
  for chunk in chunks:
    await message.channel.send(chunk)  # for some reason this sometimes crashes when called right after start. The !leaderboard doesn't. Fuck discord

@client.command(help="List the top ranked (most 'active') users")
async def leaderboard( message: nextcord.Interaction, page = None, pagesize = None ):
  log(f'!leaderboard {page} {pagesize}')
  
  page     = parseIntInput( page,     default= 1, min=1 )
  pagesize = parseIntInput( pagesize, default=10, min=1, max=MAX_LEADERBOARD_SIZE )
  
  chunks = await get_leaderboard_msg( page, pagesize )
  
  await message.reply(chunks.pop(0))
  for chunk in chunks:
    await message.channel.send(chunk)

############# XPLEADERBOARD COMMAND #############

@client.slash_command(description="List the top ranked (most 'active') users")
async def xpleaderboard(message:  nextcord.Interaction,
  page: int = nextcord.SlashOption(name="page", required=False, default=1, min_value=1),
  pagesize: int = nextcord.SlashOption(name="pagesize", required=False, default=10, min_value=1, max_value=MAX_LEADERBOARD_SIZE),
) -> None:
  log(f'/xpleaderboard {page} {pagesize}')
  
  chunks = await get_leaderboard_msg( page, pagesize, True )
  
  await message.send(chunks.pop(0))
  for chunk in chunks:
    await message.channel.send(chunk)  # for some reason this sometimes crashes when called right after start. The !xpleaderboard doesn't. Fuck discord

@client.command(help="List the top ranked (most 'active') users with their total XP")
async def xpleaderboard( message: nextcord.Interaction, page = None, pagesize = None ):
  log(f'!xpleaderboard {page} {pagesize}')
  
  page     = parseIntInput( page,     default= 1, min=1 )
  pagesize = parseIntInput( pagesize, default=10, min=1, max=MAX_LEADERBOARD_SIZE )
  
  chunks = await get_leaderboard_msg( page, pagesize, True )
  
  await message.reply(chunks.pop(0))
  for chunk in chunks:
    await message.channel.send(chunk)

############# RANK COMMAND #############

async def get_rank_msg( user_id: int ) -> str:
  
  xp, level = get_userlevel(user_id)
  rank = get_user_rank(xp,level)
  
  if rank is None:
    return f"User {await getUserName(user_id)} is currently unranked ({xp}/{LEVELUP_XP(level)} XP)"
  
  return f"User {await getUserName(user_id)} is at rank {rank} with level {level} ({xp}/{LEVELUP_XP(level)} XP)"

@client.slash_command(description='Get xp and level of yourself or another user')
async def rank(message:  nextcord.Interaction, username: Optional[nextcord.Member] = nextcord.SlashOption(name="user", required=False, description='set to query for user, or leave empty')) -> None:
  log(f'/rank {username}')
  
  if username is None:
    queried_user_id = message.user.id
  else:
    queried_user_id = username.id
  
  msg = await get_rank_msg( int(queried_user_id) )
  
  await message.send(msg)

@client.command(help="Get xp and level of yourself or another user")
async def rank(message, username = None ):
  log(f'!rank {username}')
  
  if username is not None:
    if match := re.match(r"<@(\d+)>", username):  # how user mentions look internally <@234086647409410059>
      queried_user_id = match.group(1)
    elif match := re.match(r"\\?<\\?@(\d+)\\?>", username):  # user mention but escaped
      queried_user_id = match.group(1)
    elif match := re.match(r"(\d+)", username):  # user id directly
      queried_user_id = match.group(1)
    else:
      await message.reply(f"Who's `{username}`?  (use @person or /rank)")
      return
  else:
    queried_user_id = message.author.id
  
  msg = await get_rank_msg( int(queried_user_id) )
  
  await message.reply(msg)

############# XPRANK COMMAND #############

async def get_xp_msg( user_id: int ) -> str:
  
  xp, level = get_userlevel(user_id)
  rank = get_user_rank(xp,level)
  totalxp = get_totalxp(xp,level)
  
  if rank is None:
    return f"User {await getUserName(user_id)} is currently unranked with {totalxp} XP"
  
  return f"User {await getUserName(user_id)} is at rank {rank} with {totalxp} XP"

@client.slash_command(description='Get total XP of yourself or another user')
async def xp(message:  nextcord.Interaction, username: Optional[nextcord.Member] = nextcord.SlashOption(name="user", required=False, description='set to query for user, or leave empty')) -> None:
  log(f'/xp {username}')
  
  if username is None:
    queried_user_id = message.user.id
  else:
    queried_user_id = username.id
  
  msg = await get_xp_msg( int(queried_user_id) )
  
  await message.send(msg)

@client.command(help="Get total XP of yourself or another user")
async def xp(message, username = None ):
  log(f'!xp {username}')
  
  if username is not None:
    if match := re.match(r"<@(\d+)>", username):  # how user mentions look internally <@234086647409410059>
      queried_user_id = match.group(1)
    elif match := re.match(r"\\?<\\?@(\d+)\\?>", username):  # user mention but escaped
      queried_user_id = match.group(1)
    elif match := re.match(r"(\d+)", username):  # user id directly
      queried_user_id = match.group(1)
    else:
      await message.reply(f"Who's `{username}`?  (use @person or /xp)")
      return
  else:
    queried_user_id = message.author.id
  
  msg = await get_xp_msg( int(queried_user_id) )
  
  await message.reply(msg)

############# PINGME COMMAND #############

# returns True if user has choosen to get pinged, False if they haven't
def pinguser( user_id: int ) -> bool:
  return database.execute( "SELECT id FROM ping_users WHERE id = ?", (user_id,) ).fetchone() is not None

async def do_pingme( user_id: int ) -> str:
  user_id = int(user_id)
  
  if pinguser(user_id):
    database.execute( "DELETE FROM ping_users WHERE id = ?", (user_id,) )
    return "you will no longer get pinged on levelup"
  else:
    database.execute( "INSERT INTO ping_users VALUES (?)", (user_id,) )
    return "you will now get pinged upon levelup"

@client.slash_command(description='Toggle getting pinged when you level up (default is off)')
async def pingme( message: nextcord.Interaction ) -> None:
  log(f'/pingme {message.user}')
  
  msg = await do_pingme( message.user.id )
  
  await message.send(msg)

@client.command(help='Toggle getting pinged when you level up (default is off)')
async def pingme( message: nextcord.Interaction ) -> None:
  log(f'!pingme {message.author}')
  
  msg = await do_pingme( message.author.id )
  
  await message.reply(msg)

############# SNITCHTOME COMMAND #############

# returns True if user has choosen to get pinged, False if they haven't
def check_snitchtome( user_id: int ) -> bool:
  return database.execute( "SELECT id FROM snitchtome_users WHERE id = ?", (user_id,) ).fetchone() is not None

async def toggle_snitchtome( user_id: int ) -> str:
  user_id = int(user_id)
  
  if check_snitchtome(user_id):
    database.execute( "DELETE FROM snitchtome_users WHERE id = ?", (user_id,) )
    return "you will no longer get notified when someone queries your rank"
  else:
    database.execute( "INSERT INTO snitchtome_users VALUES (?)", (user_id,) )
    return "I will now snitch to you when someone queries your rank"

@client.slash_command(description='Toggle getting pinged when someone queries your rank (default is off)')
async def snitchtome( message: nextcord.Interaction ) -> None:
  log(f'/snitchtome {message.user}')
  
  msg = await toggle_snitchtome( message.user.id )
  
  await message.send(msg)

@client.command(help='Toggle getting pinged when someone queries your rank (default is off)')
async def snitchtome( message: nextcord.Interaction ) -> None:
  log(f'!snitchtome {message.author}')
  
  msg = await toggle_snitchtome( message.author.id )
  
  await message.reply(msg)

############# XP LISTENER AND OTHER MESSAGE LISTENERS #############

usr_cooldowns = {}
@client.listen('on_message')
async def msg(message):
  author = message.author

  # if author.bot: return  # ignore bots
  
  if usr_cooldowns.get(author.id, 0.0) > time.time():
    log(f'skipped msg by {author.name} due to timeout ({usr_cooldowns.get(author.id, 0.0) - time.time()}s remaining)')
    return # check cooldown
  usr_cooldowns[author.id] = time.time() + TIMEOUT
  
  
  xp, level = get_userlevel(author.id)
  
  xp += XP_GAIN_AMOUNT()
  leveledup = xp >= LEVELUP_XP(level)
  
  if leveledup:
    xp -= LEVELUP_XP(level)  # say levelup is 1000 xp and user has 1005 xp, they should still have 5 xp after levelup
    level += 1
  
  database.execute("UPDATE users SET xp = ?, level = ? WHERE id = ?;", (xp, level, str(author.id)))
  
  
  log(f'got msg by {author} (xp: {xp}, lvl: {level})')
  
  if leveledup:
    
    xp, level = get_userlevel(author.id)  # jsut to be sure, yaknow
    rank = get_user_rank(xp,level)  # should never be None since user just got to at least level 1
    
    username = f'<@{author.id}>' if pinguser(author.id) else f'`{author}`'  # ping if set to do so
    
    unawait( client.get_partial_messageable(BOT_CHANNEL_ID).send(f"{username} leveled up to {level}!!  They are currently ranked {rank}") )
    
    print(f'{author} leveled up! (xp: {xp}, lvl: {level})')

@client.listen('on_message')
async def operationCounterEEP(message):
  eep = f'{chr(0x6d)}eep'  # the accursed word
  allowedEEPpercent = 0.15
  
  # # only affect anith and test acount
  # if not ( message.author.id == 411317904081027072 or message.author.id == 933495055895912448 ):
  #   return
  
  content = message.content
  content = re.sub("<:"+eep+":\\d{10,}>", eep, content)  # replace eep emojis with normal eeps for more realistic evaluation
  
  # only affect messages that are primarily (>20%) eeps
  if not len(content) < 4/allowedEEPpercent * content.lower().count( eep ):
    return
  
  try:
    emoji = [ emoji for emoji in await message.guild.fetch_emojis() if emoji.name == 'shut' ][0]
  except: return
  
  await message.add_reaction(emoji)
  log('Shut')

############# CRON #############

def prune_timeouts():
  global usr_cooldowns  # do atomic swap of dict to prevent thread issues
  usr_cooldowns = { id: cooldowntime for id, cooldowntime in usr_cooldowns.items() if cooldowntime > time.time() }  # only keep timeouts in the future

# minimum frequency is 1 minute
cronjobs = [
  { 'name': "db autosave",        'frequencySeconds':  300, 'nextrun': 0, 'function': lambda:database.commit() },
  { 'name': "clear old timeouts", 'frequencySeconds': 3600, 'nextrun': 0, 'function': prune_timeouts },
]

@client.listen('on_ready')
async def cron():
  print('Ready. Starting internal Cron')
  
  while not client.is_closed():  # check is_closed in case we missed the on_close event
    
    for cronjob in cronjobs:
      if cronjob['nextrun'] <= time.time():
        cronjob['nextrun'] = time.time() + cronjob['frequencySeconds']
        cronjob['function']()
        log(f"ran {cronjob['name']}")
    
    try:
      if not client.is_closed(): await client.wait_for( 'close', timeout=60 )
      break
    except: pass
  
  print('Stopping internal Cron')

############# DATABASE #############

database = connect("sqlite.db")

database.execute("""CREATE TABLE IF NOT EXISTS
  users (
    id varchar(400),
    level int,
    xp int
  );
""")
database.execute("""CREATE TABLE IF NOT EXISTS
  ping_users (
    id UNSIGNED BIG INT PRIMARY KEY
  );
""")
database.execute("""CREATE TABLE IF NOT EXISTS
  snitchtome_users (
    id UNSIGNED BIG INT PRIMARY KEY
  );
""")
# database.execute("UPDATE users SET xp = 90, level = 0 WHERE id = 933496023916093502;")  # my testing account (Greenjard)

############# STARTUP AND SHUTDOWN #############

client.run(BOT_API_KEY)

database.commit()
database.close()
