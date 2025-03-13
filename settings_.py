# link to add bot to server: https://discord.com/api/oauth2/authorize?client_id=<your id here>&scope=bot%20messages.read%20applications.commands

BOT_SERVER_IDS = [<your discord server id>]
BOT_CHANNEL_ID = <channel id to print levelup messages to>


TIMEOUT = 60  # how long until a user can gain xp again in seconds

import random
XP_GAIN_AMOUNT = lambda: random.randint(15, 25)

# as per https://github.com/Mee6/Mee6-documentation/blob/master/docs/levels_xp.md
LEVELUP_XP = lambda cur_level: 5*cur_level**2 + 50*cur_level + 100

MAX_LEADERBOARD_SIZE = 100

DISCORD_CHAR_LIMIT = 2000

DEBUG = True
