from nextcord.ext import commands
from os import environ as env
import random
import nextcord


import time

from sqlite3 import connect 

client = commands.Bot(command_prefix='/')

BOT_CHANNEL_ID = 955220937995874334

usr_cooldowns = {}

# as per https://github.com/Mee6/Mee6-documentation/blob/master/docs/levels_xp.md
def levelup_xp(cur_level):
  return 5*cur_level**2 + 50*cur_level + 100


# def create_user(user_id): 
#   database.execute("INSERT INTO users VALUES (?, ?, ?)", (str(user_id), 0, 0))


# get xp, level, ... of user_id, and create user entry if it doesn't exist
def get_userlevel(user_id):
  
  #check if user is in the db
  if database.execute("SELECT id FROM users WHERE id = ?", (str(author.id),)).fetchone() is None:
    # create_user(user_id)
    database.execute("INSERT INTO users VALUES (?, ?, ?)", (str(user_id), 0, 0))

  usr = database.execute("SELECT xp, level level FROM users WHERE id = ?", (str(user_id), )).fetchone()
  
  return usr


@client.command()
async def rank(message, username):
  # TODO: make the username arguemnt work
  
  queried_user = message.author
  
  xp, level = get_userlevel(author.id)
  
  await message.send(f"User `{queried_user.name}` has level {level} ({xp}/{levelup_xp(level)} XP)")


@client.listen('on_message')
async def msg(message):
  author = message.author

  if author.bot: return  # ignore bots
  if usr_cooldowns.get(author.id, 0.0) < time.time(): return # check cooldown

  xp, level = get_userlevel(author.id)

  xp += random.randint(15, 25)  # are we trying to replicate mee6 or not?
  
  if levelup_xp(level) - xp <= 0:
    channel = nextcord.utils.get(client.get_all_channels(), id=BOT_CHANNEL_ID)
    
    level += 1
    xp -= levelup_xp(level)  # say levelup is 1000 xp and user has 1005 xp, they should still have 5 xp after levelup
    
    #TODO: ADD OPINAL PINGS
    await channel.send(f"{author.name} leveled up to {level}!!")
  
  
  usr_cooldowns[author.id] = time.time()+60
  database.execute("UPDATE users SET xp = ?, level = ? WHERE id = ?;", (xp, level, str(author.id)))
  conn.commit()


with connect("sqlite.db") as conn:
  global database, channel # yes IK, im to lasy to put it on the client Obj
  database = conn.cursor()
  
  try:
    client.run(env['token'])
  except:
    pass
  finally:
    conn.close()



# bot not working?
# try to do "pip install nextcord" in the shell
