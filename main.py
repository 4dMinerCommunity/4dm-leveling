# https://discord.com/api/oauth2/authorize?client_id=<should prob censor this too>&scope=bot%20messages.read%20applications.commands

import nextcord, nextcord.ext.commands
from typing import Optional

from os import environ as env
import random
import re  # regex

import time
from datetime import datetime

from sqlite3 import connect 


intents = nextcord.Intents.default()
intents.message_content = True
intents.members = True


client = nextcord.ext.commands.Bot(command_prefix='!', intents=intents)

# BOT_SERVER_IDS = [954156776671043625]
# BOT_CHANNEL_ID = 955220937995874334
BOT_SERVER_IDS = [<my own private server, I aint giving out that id>]
BOT_CHANNEL_ID = <my own private server, I aint giving out that id>

TIMEOUT = 60  # in seconds

usr_cooldowns = {}


database = connect("sqlite.db")


# as per https://github.com/Mee6/Mee6-documentation/blob/master/docs/levels_xp.md
def levelup_xp(cur_level):
  return 5*cur_level**2 + 50*cur_level + 100

# get xp, level, ... of user_id, and create user entry if it doesn't exist
def get_userlevel(user_id):
  
  #check if user is in the db
  if database.execute("SELECT id FROM users WHERE id = ?", (str(user_id),)).fetchone() is None:
    # create_user(user_id)
    database.execute("INSERT INTO users VALUES (?, ?, ?)", (str(user_id), 0, 0))
  
  usr = database.execute("SELECT xp, level FROM users WHERE id = ?", (str(user_id), )).fetchone()
  
  return usr

async def get_user(user_id):
  
  # get from cache
  user = client.get_user(user_id)
  
  # get fresh
  if not user:
    try:
      print(f'trying to fetch unknown user <@{user_id}>', user)
      user = await client.fetch_user(user_id)
    except: pass
  
  return user


async def get_leaderboard_msg( page: int, pagesize: int ) -> str:
  
  no_users = database.execute( "SELECT COUNT(*) FROM users WHERE level > 0 " ).fetchone()[0]
  no_pages = ( no_users + pagesize - 1 )//pagesize
  
  if page > no_pages:
    page = no_pages
  
  msg = ""
  
  msg += f"LEADERBOARD page {page}/{no_pages}\n```"
  
  rank = (page-1)*pagesize
  for id, xp, level in database.execute( "SELECT id, xp, level FROM users WHERE level > 0 ORDER BY level DESC, xp DESC, id ASC LIMIT ? OFFSET ?", (pagesize, (page-1)*pagesize) ).fetchall():
    rank += 1
    id = int(id)  # you would not believe how many issues this caused, I wasted 3 hours on this shit. Fuck soft typing, fuck nextcord, fuck sqlite
    
    user = await get_user(id)
    username = str(user) if user else f'<@{id}>'
    
    msg += f"Rank {rank}: {username} level {level} ({xp}/{levelup_xp(level)})\n"
    
    # if len(msg.encode('utf-8')) > 1900: break
  
  msg += "```"
  
  return msg


@client.slash_command(guild_ids=BOT_SERVER_IDS, description="List the top ranked (most 'active') users")
async def leaderboard(message:  nextcord.Interaction,
  page: int = nextcord.SlashOption(name="page", required=False, default=1, min_value=1),
  pagesize: int = nextcord.SlashOption(name="pagesize", required=False, default=10, choices=[5,10,20,30]),
) -> None:
  print(f'/leaderboard {page} {pagesize}')
  
  msg = await get_leaderboard_msg( page, pagesize )
  
  await message.response.send_message(msg)

@client.command()
async def leaderboard( message: nextcord.Interaction, page = None, pagesize = None ):
  print(f'!leaderboard {page} {pagesize}')
  
  try: page = int(page)
  except: page = 1
  try: pagesize = int(pagesize)
  except: pagesize = 10
  
  if page < 1: page = 1
  if pagesize < 1: pagesize = 1
  if pagesize > 30: pagesize = 30
  
  msg = await get_leaderboard_msg( page, pagesize )
  
  await message.reply(msg)


@client.slash_command(guild_ids=BOT_SERVER_IDS, description='Get xp and level of yourself or another user')
async def rank(message:  nextcord.Interaction, username: Optional[nextcord.Member] = nextcord.SlashOption(name="user", required=False, description='set to query for user, or leave empty')) -> None:
  print(f'/rank {username}')
  
  if username is None:
    queried_user = message.user
  else:
    queried_user = username
  
  xp, level = get_userlevel(queried_user.id)
  
  await message.response.send_message(f"User `{queried_user.name}` has level {level} ({xp}/{levelup_xp(level)} XP)")

@client.command()
async def rank(message, username = None ):
  print(f'!rank {username}')
  
  if username is not None:
    if match := re.match(r"<@(\d+)>", username):
      queried_user_id = match.group(1)
    else:
      await message.reply(f"Who's `{username}`?  (use @person or /rank)")
      return
  else:
    queried_user_id = message.author.id
  
  xp, level = get_userlevel(queried_user_id)
  
  user = await get_user(queried_user_id)
  username = str(user) if user else f'<\\@{queried_user_id}>'
  
  await message.reply(f"User {username} has level {level} ({xp}/{levelup_xp(level)} XP)")


@client.listen('on_message')
async def msg(message):
  author = message.author
  # print(f'got msg by {author.name}')

  if author.bot: return  # ignore bots
  if usr_cooldowns.get(author.id, 0.0) > time.time():
    print(f'skipped msg by {author.name} due to timeout ({usr_cooldowns.get(author.id, 0.0) - time.time()}s remaining)')
    return # check cooldown

  xp, level = get_userlevel(author.id)

  xp += random.randint(15, 25)  # are we trying to replicate mee6 or not?
  
  if levelup_xp(level) - xp <= 0:
    channel = nextcord.utils.get(client.get_all_channels(), id=BOT_CHANNEL_ID)
    
    xp -= levelup_xp(level)  # say levelup is 1000 xp and user has 1005 xp, they should still have 5 xp after levelup
    level += 1
    
    #TODO: ADD OPINAL PINGS
    await channel.send(f"{author.name} leveled up to {level}!!")
  
  
  usr_cooldowns[author.id] = time.time() + TIMEOUT
  database.execute("UPDATE users SET xp = ?, level = ? WHERE id = ?;", (xp, level, str(author.id)))
  database.commit()
  
  print(f'got msg by {author.name} (xp: {xp}, lvl: {level})')


# database.execute("DROP TABLE android_metadata;")  # clean up after my android sqlite editor
database.execute("""CREATE TABLE IF NOT EXISTS
  users (
    id varchar(400),
    level int,
    xp int
  );
""")

try:
  client.run('sike, you wish')
except KeyboardInterrupt:  # should not be called because client.run handles it by itself without throwing an error
  print('exiting due to keyboard interrupt')

database.commit()
database.close()
