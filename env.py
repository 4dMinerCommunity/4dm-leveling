# because systemd environment sucks and is systemd specific.
# also so I don't accidentally push my test settings like TIMEOUT=1 to prod

BOT_API_KEY = '<your api key here>'

BOT_SERVER_IDS = [954156776671043625]
BOT_CHANNEL_ID = 955220937995874334

TIMEOUT = 60  # how long until a user can gain xp again in seconds

import random
XP_GAIN_AMOUNT = lambda: random.randint(15, 25)

# as per https://github.com/Mee6/Mee6-documentation/blob/master/docs/levels_xp.md
LEVELUP_XP = lambda cur_level: 5*cur_level**2 + 50*cur_level + 100

# link to add bot to server: https://discord.com/api/oauth2/authorize?client_id=<your id here>&scope=bot%20messages.read%20applications.commands
