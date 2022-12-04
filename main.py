import re  # regex
import time
from datetime import datetime
from sqlite3 import connect
from typing import Optional

import nextcord
import nextcord.ext.commands

strlen = lambda string: len(string.encode("utf-8"))
import schedule

from env import *  # api keys
from settings import *

log = print
if not DEBUG:
    log = lambda *_: None  # disable log on release


intents = nextcord.Intents.default()
intents.message_content = True
intents.members = True

client = nextcord.ext.commands.Bot(command_prefix="!", intents=intents)


database = connect("sqlite.db")

usr_cooldowns = {}


# get xp, level, ... of user_id, and create user entry if it doesn't exist
def get_userlevel(user_id):

    # check if user is in the db
    if (
        database.execute(
            "SELECT id FROM users WHERE id = ?", (str(user_id),)
        ).fetchone()
        is None
    ):
        database.execute("INSERT INTO users VALUES (?, ?, ?)", (str(user_id), 0, 0))

    xp, level = database.execute(
        "SELECT xp, level FROM users WHERE id = ?", (str(user_id),)
    ).fetchone()

    return xp, level


# returns rank as int or None if unranked (level 0)
def get_user_rank(user_id):
    xp, level = get_userlevel(user_id)

    if level < 1:
        return None

    rank = database.execute(
        "SELECT count(*)+1 FROM users WHERE level > ? OR ( level = ? AND xp > ? )",
        (level, level, xp),
    ).fetchone()[0]

    return rank


async def get_user(user_id):
    user_id = int(
        user_id
    )  # you would not believe how many issues this caused, I wasted 3 hours on this shit. Fuck soft typing, fuck nextcord, fuck sqlite

    # get from cache
    user = client.get_user(user_id)

    # get fresh
    if not user and not DEBUG:
        try:
            log(f"trying to fetch unknown user <@{user_id}>", user)
            user = await client.fetch_user(user_id)
        except:
            pass

    return user


############# LEADERBOARD COMMAND #############


async def get_leaderboard_msg(page: int, pagesize: int) -> str:

    no_users = database.execute(
        "SELECT COUNT(*) FROM users WHERE level > 0 "
    ).fetchone()[0]
    no_pages = (no_users + pagesize - 1) // pagesize

    if page > no_pages:
        page = no_pages

    chunks = []
    chunk = f"LEADERBOARD page {page}/{no_pages}\n```"

    rank = (page - 1) * pagesize
    for id, xp, level in database.execute(
        "SELECT id, xp, level FROM users WHERE level > 0 ORDER BY level DESC, xp DESC, id ASC LIMIT ? OFFSET ?",
        (pagesize, (page - 1) * pagesize),
    ).fetchall():
        rank += 1

        try:
            if xp != oldxp or level != oldlvl:
                showrank = rank
        except:  # first run
            showrank = get_user_rank(id)

        user = await get_user(id)
        username = str(user) if user else f"<@{id}>"

        row = f"Rank {showrank}: {username} level {level} ({xp}/{LEVELUP_XP(level)})\n"

        if (
            strlen(chunk + row + "```") > DISCORD_CHAR_LIMIT
        ):  # this row would make message too long, start new block
            chunk += "```"
            chunks.append(chunk)
            chunk = "```"

        chunk += row

        oldxp, oldlvl = xp, level

    chunk += "```"
    chunks.append(chunk)

    return chunks


@client.slash_command(
    guild_ids=BOT_SERVER_IDS, description="List the top ranked (most 'active') users"
)
async def leaderboard(
    message: nextcord.Interaction,
    page: int = nextcord.SlashOption(
        name="page", required=False, default=1, min_value=1
    ),
    pagesize: int = nextcord.SlashOption(
        name="pagesize",
        required=False,
        default=10,
        min_value=1,
        max_value=MAX_LEADERBOARD_SIZE,
    ),
) -> None:
    log(f"/leaderboard {page} {pagesize}")

    chunks = await get_leaderboard_msg(page, pagesize)

    await message.send(chunks.pop(0))
    for chunk in chunks:
        await message.channel.send(
            chunk
        )  # for some reason this sometimes crashes when called right after start. The !leaderboard doesn't. Fuck discord


@client.command()
async def leaderboard(message: nextcord.Interaction, page=None, pagesize=None):
    log(f"!leaderboard {page} {pagesize}")

    try:
        page = int(page)
    except:
        page = 1
    try:
        pagesize = int(pagesize)
    except:
        pagesize = 10

    if page < 1:
        page = 1
    if pagesize < 1:
        pagesize = 1
    if pagesize > MAX_LEADERBOARD_SIZE:
        pagesize = MAX_LEADERBOARD_SIZE

    chunks = await get_leaderboard_msg(page, pagesize)

    await message.reply(chunks.pop(0))
    for chunk in chunks:
        await message.channel.send(chunk)


############# RANK COMMAND #############


async def get_rank_msg(user_id: int) -> str:

    xp, level = get_userlevel(user_id)
    rank = get_user_rank(user_id)

    user = await get_user(user_id)
    username = str(user) if user else f"<@{user_id}>"

    if rank is None:
        return f"User `{username}` is currently unranked ({xp}/{LEVELUP_XP(level)} XP)"

    return f"User `{username}` is at rank {rank} with level {level} ({xp}/{LEVELUP_XP(level)} XP)"


@client.slash_command(
    guild_ids=BOT_SERVER_IDS, description="Get xp and level of yourself or another user"
)
async def rank(
    message: nextcord.Interaction,
    username: Optional[nextcord.Member] = nextcord.SlashOption(
        name="user", required=False, description="set to query for user, or leave empty"
    ),
) -> None:
    log(f"/rank {username}")

    if username is None:
        queried_user_id = message.user.id
    else:
        queried_user_id = username.id

    msg = await get_rank_msg(int(queried_user_id))

    await message.send(msg)


@client.command()
async def rank(message, username=None):
    log(f"!rank {username}")

    if username is not None:
        if match := re.match(r"<@(\d+)>", username):
            queried_user_id = match.group(1)
        else:
            await message.reply(f"Who's `{username}`?  (use @person or /rank)")
            return
    else:
        queried_user_id = message.author.id

    msg = await get_rank_msg(int(queried_user_id))

    await message.reply(msg)


############# PINGME COMMAND #############

# returns True if user has choosen to get pinged, False if they haven't
def pinguser(user_id: int) -> bool:
    return (
        database.execute(
            "SELECT id FROM ping_users WHERE id = ?", (user_id,)
        ).fetchone()
        is not None
    )


async def do_pingme(user_id: int) -> str:
    user_id = int(user_id)

    if pinguser(user_id):
        database.execute("DELETE FROM ping_users WHERE id = ?", (user_id,))
        return "you will no longer get pinged on levelup"
    else:
        database.execute("INSERT INTO ping_users VALUES (?)", (user_id,))
        return "you will now get pinged uppon levelup"


@client.slash_command(
    guild_ids=BOT_SERVER_IDS,
    description="Toggle getting pinged when you level up (default is off)",
)
async def pingme(message: nextcord.Interaction) -> None:
    log(f"/pingme {message.user}")

    msg = await do_pingme(message.user.id)

    await message.send(msg)


@client.command()
async def pingme(message: nextcord.Interaction) -> None:
    log(f"!pingme {message.author}")

    msg = await do_pingme(message.author.id)

    await message.reply(msg)


############# XP LISTENER #############


@client.listen("on_message")
async def msg(message):
    author = message.author
    # log(f'got msg by {author.name}')

    if author.bot:
        return  # ignore bots
    if usr_cooldowns.get(author.id, 0.0) > time.time():
        log(
            f"skipped msg by {author.name} due to timeout ({usr_cooldowns.get(author.id, 0.0) - time.time()}s remaining)"
        )
        return  # check cooldown

    xp, level = get_userlevel(author.id)

    xp += XP_GAIN_AMOUNT()

    if LEVELUP_XP(level) - xp <= 0:
        channel = nextcord.utils.get(client.get_all_channels(), id=BOT_CHANNEL_ID)

        xp -= LEVELUP_XP(
            level
        )  # say levelup is 1000 xp and user has 1005 xp, they should still have 5 xp after levelup
        level += 1

        rank = get_user_rank(
            author.id
        )  # should never be None since user just got to at least level 1

        username = (
            f"<@{author.id}>" if pinguser(author.id) else f"`{author}`"
        )  # ping if set to do so

        await channel.send(
            f"{username} leveled up to {level}!!  They are currently ranked {rank}"
        )

        print(f"{author} leveled up! (xp: {xp}, lvl: {level})")

    usr_cooldowns[author.id] = time.time() + TIMEOUT
    database.execute(
        "UPDATE users SET xp = ?, level = ? WHERE id = ?;", (xp, level, str(author.id))
    )

    log(f"got msg by {author} (xp: {xp}, lvl: {level})")


# database.execute("DROP TABLE android_metadata;")  # clean up after my android sqlite editor
database.execute(
    """CREATE TABLE IF NOT EXISTS
  users (
    id varchar(400),
    level int,
    xp int
  );
"""
)
database.execute(
    """CREATE TABLE IF NOT EXISTS
  ping_users (
    id UNSIGNED BIG INT PRIMARY KEY
  );
"""
)

schedule.every(5).minutes.do(lambda: database.commit())

try:
    client.run(BOT_API_KEY)
except KeyboardInterrupt:  # should not be called because client.run handles it by itself without throwing an error
    print("exiting due to keyboard interrupt")

database.commit()
database.close()


"""
Changelog:
 - moved settings, env variables, etc. to env.py
 - larger leaderboards, and support for longer names, by splitting messages into chunks
 - give users the same rank if they have equal xp
 - show rank of users in various places
 - full discord name mentioned in levelup messages like elsewhere
 - pingme command to toggle getting pinged on levelup
 - corresponding sqlite table to hold that pingme info
 - getting pinged on levelup if set to do so
 - don't commit for every message, that'll just either kill your drive or get cached to ram anyways. Commiting when exiting and every 5 mins is plenty
"""
