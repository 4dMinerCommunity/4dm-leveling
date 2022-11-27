from nextcord.ext import commands
from os import environ as env
import random
import nextcord


import time

from sqlite3 import connect 

client = commands.Bot()

CHANNEL_ID = 955220937995874334

usr_cooldowns = {}


def create_user(user_id): 
	database.execute("INSERT INTO users VALUES (?, ?, ?)", (str(user_id), 0, 0))



@client.listen('on_message')
async def msg(message):
	author = message.author

	if usr_cooldowns.get(author.id, 0.0) < time.time(): return #cooldown

	if author.bot: return
	#check if user is in the db
	if database.execute("SELECT id FROM users WHERE id = ?", (str(author.id),)).fetchone() is None:
		create_user(author.id)

	usr = database.execute("SELECT xp, level level FROM users WHERE id = ?", (str(author.id), )).fetchone()

	xp = usr[0]
	level = usr[1]

	xp += random.randint(1, 5)
	if (5 * (level ^ 2) + (50 * level) + 100) - xp <= 0:
		channel = nextcord.utils.get(client.get_all_channels(), id=CHANNEL_ID)
		
		level += 1
		xp = 0

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
