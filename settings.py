# so I don't accidentally push my test settings like TIMEOUT=1 to prod

TIMEOUT = 60  # how long until a user can gain xp again in seconds

import random

XP_GAIN_AMOUNT = lambda: random.randint(15, 25)

# as per https://github.com/Mee6/Mee6-documentation/blob/master/docs/levels_xp.md
LEVELUP_XP = lambda cur_level: 5 * cur_level**2 + 50 * cur_level + 100

MAX_LEADERBOARD_SIZE = 100

DISCORD_CHAR_LIMIT = 2000

DEBUG = False
