#!/usr/bin/python3

import nextcord, nextcord.ext.commands
from nextcord import SlashOption as Option
from sqlite3 import connect 

from time import time
from asyncio import create_task as unawait
import re  # regex
import unicodedata

from env import *  # api keys
from settings import *

log = print
if not DEBUG: log = lambda *_: None  # disable log on release

############# CLIENT INITIALIZATION #############

intents = nextcord.Intents.none()
intents.guilds = True
intents.members = True
# intents.emojis = True
intents.guild_messages = True
intents.message_content = True

log([ intent[0] for intent in intents if intent[1] ])
client = nextcord.ext.commands.Bot( command_prefix='!', intents=intents, default_guild_ids=BOT_SERVER_IDS )

############# LIBRARY #############

# in case dc ever changes how they measure stringlength AGAIN
def dcStrlen(string): return len(string)

# get ( xp, level )
def get_userlevel(user_id):
  return database.execute("SELECT xp, level FROM levels WHERE id = ?", (user_id,) ).fetchone() or (0,0)

# save xp, level, ... of user_id
def set_userlevel(user_id,xp,level):
  database.execute("INSERT OR REPLACE INTO levels( id, xp, level ) VALUES (?, ?, ?)", (user_id, xp, level))

def get_totalxp(xp,level):
  # yes I know you could get a direct math equation for that sum but then you need to manage 2 equations,
  # here you can just change LEVELUP_XP to whatever. The runtime difference is negligible
  return xp + sum( LEVELUP_XP(lvl) for lvl in range(level) )

# returns rank as int or None if unranked (level 0)
def get_user_rank(xp,level):
  
  if level < 1:
    return None
  
  return database.execute( "SELECT count(*)+1 FROM levels WHERE level > ? OR ( level = ? AND xp > ? )", (level,level,xp) ).fetchone()[0]

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

async def commandRespond(call_env,response,mentions):
  if isinstance(call_env, nextcord.ext.commands.Context):
    await call_env.reply(response,allowed_mentions=mentions)
  else:
    await call_env.send(response,allowed_mentions=mentions)

async def printChunked(call_env,chunks,mentions):
  
  await commandRespond(call_env,chunks.pop(0),mentions)
  
  for chunk in chunks:
    await call_env.channel.send(chunk,allowed_mentions=mentions)

############# LEADERBOARD COMMAND #############

def get_leaderboard_msg( page: int, pagesize: int, is_xp_leaderboard: bool = False ) -> str:
  
  no_users = database.execute( "SELECT COUNT(*) FROM levels WHERE level > 0 " ).fetchone()[0]
  no_pages = ( no_users + pagesize - 1 )//pagesize
  
  if page > no_pages:
    page = no_pages
  
  no_skippedUsers = (page-1)*pagesize
  
  data = database.execute( "SELECT id, xp, level FROM levels WHERE level > 0 ORDER BY level DESC, xp DESC, id ASC LIMIT ? OFFSET ?", (pagesize,no_skippedUsers) ).fetchall()
  data = tuple(map(list,data))
  
  # generate the rank (difficult because of ties, especially ties starting before current page)
  for internalrank, row in enumerate(data,start=no_skippedUsers+1):
    
    _, xp, level = row
    try:
      if xp != oldxp or level != oldlvl:
        rank = internalrank
    except:  # first run
      rank = get_user_rank(xp,level)
    oldxp,oldlvl = xp,level
    
    row.append(rank)
  
  width_rank    = len(str( data[-1][3] ))
  if is_xp_leaderboard:
    width_totalxp = len(str( get_totalxp(data[0][1],data[0][2]) ))
  else:
    width_level   = len(str( data[0][2] ))
    width_xp      = len(str( max( row[1] for row in data ) )) # man this would be so much easier with numpy
    width_lvlupxp = len(str( LEVELUP_XP(data[0][2]) ))
    
  
  pings = []
  chunks = [ f"**LEADERBOARD page {page}/{no_pages}**\n" ]
  for user_id, xp, level, rank in data:
    rank = intToWidth(rank,width_rank)
    
    if is_xp_leaderboard:
      totalxp = get_totalxp(xp,level)
      row = f"`Rank {rank} - {intToWidth(totalxp,width_totalxp)} XP:` <@{user_id}>\n"
    else:
      row = f"`Rank {rank} - Level {intToWidth(level,width_level)} ({intToWidth(xp,width_xp)}/{intToWidth(LEVELUP_XP(level),width_lvlupxp)}):` <@{user_id}>\n"
    
    if check_setting('snitchtome',user_id):
      pings.append(user_id)
    
    if dcStrlen(chunks[-1]+row) > DISCORD_CHAR_LIMIT:  # this row would make message too long, start new block
      chunks.append("")
    
    chunks[-1] += row
  
  return chunks, nextcord.AllowedMentions(replied_user=False,users=[nextcord.Object(user_id) for user_id in pings])

@client.slash_command(description="List the top ranked (most 'active') users")
async def leaderboard(interaction, page: int = Option(default=1, min_value=1), pagesize: int = Option(default=10, min_value=1, max_value=MAX_LEADERBOARD_SIZE) ):
  log(f'/leaderboard {page} {pagesize}')
  
  await printChunked( interaction, *get_leaderboard_msg( page, pagesize ) )

@client.command(help="List the top ranked (most 'active') users")
async def leaderboard(message, page = None, pagesize = None ):
  log(f'!leaderboard {page} {pagesize}')
  
  page     = parseIntInput( page,     default= 1, min=1 )
  pagesize = parseIntInput( pagesize, default=10, min=1, max=MAX_LEADERBOARD_SIZE )
  
  await printChunked( message, *get_leaderboard_msg( page, pagesize ) )

############# XPLEADERBOARD COMMAND #############

@client.slash_command(description="List the top ranked (most 'active') users")
async def xpleaderboard(interaction, page: int = Option(default=1, min_value=1), pagesize: int = Option(default=10, min_value=1, max_value=MAX_LEADERBOARD_SIZE) ):
  log(f'/xpleaderboard {page} {pagesize}')
  
  await printChunked( interaction, *get_leaderboard_msg( page, pagesize, True ) )

@client.command(help="List the top ranked (most 'active') users with their total XP")
async def xpleaderboard(message, page = None, pagesize = None ):
  log(f'!xpleaderboard {page} {pagesize}')
  
  page     = parseIntInput( page,     default= 1, min=1 )
  pagesize = parseIntInput( pagesize, default=10, min=1, max=MAX_LEADERBOARD_SIZE )
  
  await printChunked( message, *get_leaderboard_msg( page, pagesize, True ) )

############# RANK COMMAND #############

def get_rank_msg( user_id: int ) -> str:
  
  xp, level = get_userlevel(user_id)
  rank = get_user_rank(xp,level)
  
  mention = nextcord.AllowedMentions(users=check_setting('snitchtome',user_id))
  
  if rank is None:
    return f"User <@{user_id}> is currently unranked ({xp}/{LEVELUP_XP(level)} XP)", mention
  
  return f"User <@{user_id}> is at rank {rank} with level {level} ({xp}/{LEVELUP_XP(level)} XP)", mention

@client.slash_command(description='Get xp and level of yourself or another user')
async def rank(interaction, user: nextcord.Member = Option(required=False,description='set to query for user, or leave empty')):
  log(f'/rank {user}')
  
  if user is None:
    queried_user_id = interaction.user.id
  else:
    queried_user_id = user.id
  
  await commandRespond( interaction, *get_rank_msg(queried_user_id) )

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
  
  await commandRespond( message, *get_rank_msg(queried_user_id) )

############# XPRANK COMMAND #############

def get_xp_msg( user_id: int ) -> str:
  
  xp, level = get_userlevel(user_id)
  rank = get_user_rank(xp,level)
  totalxp = get_totalxp(xp,level)
  
  mention = nextcord.AllowedMentions(users=check_setting('snitchtome',user_id))
  
  if rank is None:
    return f"User <@{user_id}> is currently unranked with {totalxp} XP", mention
  
  return f"User <@{user_id}> is at rank {rank} with {totalxp} XP", mention

@client.slash_command(description='Get total XP of yourself or another user')
async def xp(interaction, user: nextcord.Member = Option(required=False,description='set to query for user, or leave empty')):
  log(f'/xp {user}')
  
  if user is None:
    queried_user_id = interaction.user.id
  else:
    queried_user_id = user.id
  
  await commandRespond( interaction, *get_xp_msg(queried_user_id) )

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
  
  await commandRespond( message, *get_xp_msg(queried_user_id) )

############# EXPORT DATA COMMAND #############

files = ['sqlite.db']

@client.slash_command(description="Export the datafiles of 4D Leveling")
async def export(interaction):
  log(f'/export')
  
  for filename in files:
    with open(filename,'rb') as file:
      dcfile = nextcord.File(file,force_close=True)
    
    await interaction.send(file=dcfile)

@client.command(help="Export the datafiles of 4D Leveling")
async def export(context):
  log(f'!export')
  
  for filename in files:
    with open(filename,'rb') as file:
      dcfile = nextcord.File(file,force_close=True)
    
    await context.reply(file=dcfile)

############# SETTINGS MANAGEMENT #############

# creates accompanying tables with "_users" appended to the settings name
usersettings = {
  "pingme": { 'description':"Toggle getting pinged when you level up (default is off)",
    'onmessage':"you will now get pinged upon levelup", 'offmessage':"you will no longer get pinged on levelup" },
  "snitchtome": { 'description':"Toggle getting pinged when someone queries your rank (default is off)",
    'onmessage':"I will now snitch to you when someone queries your rank", 'offmessage':"you will no longer get notified when someone queries your rank" },
}

def check_setting( setting: str, user_id ) -> bool:
  return database.execute( f"SELECT id FROM {setting}_users WHERE id = ?", (user_id,) ).fetchone() is not None

def toggle_setting( setting: str, user_id ) -> str:
  if not check_setting(setting,user_id):
    database.execute( f"INSERT INTO {setting}_users VALUES (?)", (user_id,) )
    return usersettings[setting]['onmessage']
  else:
    database.execute( f"DELETE FROM {setting}_users WHERE id = ?", (user_id,) )
    return usersettings[setting]['offmessage']

# needs to be function so the toggle functions are local scope and don't get overwritten. It's a python limitation
def register_toggle_command(setting):
  
  @client.slash_command( setting, usersettings[setting]['description'] )
  async def toggle_slashcommand(interaction):
    log(f"/{setting} {interaction.user}")
    await interaction.send( toggle_setting( setting, interaction.user.id ) )
  
  @client.command( name=setting, help=usersettings[setting]['description'] )
  async def toggle_command(message):
    log(f"!{setting} {message.author}")
    await message.reply( toggle_setting( setting, message.author.id ) )

for setting in usersettings:
  register_toggle_command(setting)

############# XP LISTENER AND OTHER MESSAGE LISTENERS #############

usr_cooldowns = {}
@client.listen('on_message')
async def msg(message):
  author = message.author
  uid = author.id
  
  # ignore bots
  if author.bot:
    return
  
  # check cooldown
  if usr_cooldowns.get(uid, 0) > time():
    log(f'skipped msg by {author.name} due to timeout ({usr_cooldowns.get(uid, 0) - time()}s remaining)')
    return
  usr_cooldowns[uid] = time() + TIMEOUT
  
  
  xp, level = get_userlevel(uid)
  
  xp += XP_GAIN_AMOUNT()
  leveled_up = xp >= LEVELUP_XP(level)
  
  if leveled_up:
    xp -= LEVELUP_XP(level)  # say levelup is 1000 xp and user has 1005 xp, they should still have 5 xp after levelup
    level += 1
  
  set_userlevel(uid, xp, level )
  log(f'got msg by {author} (xp: {xp}, lvl: {level})')
  
  if leveled_up:
    
    rank = get_user_rank(xp,level)  # should never be None since user just got to at least level 1
    ping = nextcord.AllowedMentions(users=check_setting('pingme',uid))
    
    unawait( client.get_partial_messageable(BOT_CHANNEL_ID).send(f"<@{uid}> leveled up to {level}!!  They are currently ranked {rank}",allowed_mentions=ping) )
    
    print(f'{author} leveled up! (xp: {xp}, lvl: {level})')

############# STOP THE EEPS #############

@client.listen('on_message')
async def operationCounterEEP(message):
  eep = f'{chr(0x6d)}eep'  # the accursed word
  allowedEEPpercent = 0.15
  
  content = message.content
  content = re.sub("<:"+eep+":\\d{10,}>", eep, content)  # replace eep emojis with normal eeps for more realistic evaluation
  content = "".join(ch for ch in content if unicodedata.category(ch) not in {'Cf','Mn'})  # remove zero width characters
  content = content.lower().replace('е','e').replace('р','p')  # don't get fooled by cyrillics
  
  # only affect messages that are primarily (> allowedEEPpercent) eeps
  if not len(content)*allowedEEPpercent < len(eep) * content.count( eep ):
    return
  
  await message.add_reaction( nextcord.utils.get(message.guild.emojis,name='shut') )
  log('Shut')

############# CRON #############

cron_minfreq = 60  # cron checks for due tasks every this many seconds
cronjobs = [
  { 'name': "db autosave",        'frequencySeconds':  300, 'function': lambda:database.commit() },
  { 'name': "clear old timeouts", 'frequencySeconds': 3600, 'function': lambda:
    globals().__setitem__('usr_cooldowns',{ id: cooldowntime for id, cooldowntime in usr_cooldowns.items() if cooldowntime > time() })
  },
  { 'name': "update activity",    'frequencySeconds':   60, 'function': lambda: unawait(
    client.change_presence(activity=nextcord.Activity( type=nextcord.ActivityType.playing, name=f"{sum(guild.member_count for guild in client.guilds)} watchers" ))
  )},
]

@client.listen('on_ready')
async def cron():
  client.remove_listener( cron, 'on_ready' )  # stop more crons spawning on connection loss & restore
  
  print('Ready. Starting internal Cron')
  
  while not client.is_closed():  # check is_closed in case we missed the on_close event
    
    for cronjob in cronjobs:
      if cronjob.get('nextrun',0) <= time():
        cronjob['nextrun'] = time() + cronjob['frequencySeconds'] - cron_minfreq/10  # some leeway for rounding etc.
        cronjob['function']()
        log(f"ran {cronjob['name']}")
    
    try:
      if not client.is_closed(): await client.wait_for( 'close', timeout=cron_minfreq )
      break
    except: pass
  
  print('Stopping internal Cron')

############# DATABASE #############

database = connect("sqlite.db")

database.execute("""CREATE TABLE IF NOT EXISTS levels (
  id UNSIGNED BIG INT PRIMARY KEY,
  level UNSIGNED BIG INT,
  xp UNSIGNED BIG INT
  );
""")
for setting in usersettings:
  database.execute(f"""CREATE TABLE IF NOT EXISTS {setting}_users (
    id UNSIGNED BIG INT PRIMARY KEY
    );
  """)
log(database.execute(" SELECT type, name FROM sqlite_schema WHERE type IN ('table','view') ").fetchall())


############# STARTUP AND SHUTDOWN #############

client.run(BOT_API_KEY)

database.commit()
database.close()
