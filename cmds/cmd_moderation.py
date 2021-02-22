# Moderation commands
# bredo, 2020

import importlib

import discord, datetime, time, asyncio

import lib_db_obfuscator
importlib.reload(lib_db_obfuscator)
import lib_loaders
importlib.reload(lib_loaders)
import lib_parsers
importlib.reload(lib_parsers)

from lib_loaders import generate_infractionid
from lib_db_obfuscator import db_hlapi
from lib_parsers import grab_files, generate_reply_field


# Catches error if the bot cannot message the user
async def catch_dm_error(user, contents, log_channel):
    try:
        await user.send(embed=contents)
    except (AttributeError, discord.errors.HTTPException):
        if log_channel:
            await log_channel.send("ERROR: Could not DM user")


# Sends an infraction to database and log channels if user exists
async def log_infraction(message, client, user, moderator_id, infraction_reason, infraction_type):

    if not user:
        return (None, None)

    send_message = True
    with db_hlapi(message.guild.id) as database:

        # Collision test
        generated_id = generate_infractionid()
        while database.grab_infraction(generated_id):
            generated_id = generate_infractionid()

        # Grab log channel id from db
        channel_id = database.grab_config("infraction-log")

        # Generate log channel object
        if channel_id:  # If ID exists then use it
            log_channel = client.get_channel(int(channel_id))
        else:
            log_channel = None
            send_message = False

        # If channel doesnt exist simply skip it
        if not log_channel:
            send_message = False

        # Send infraction to database
        database.add_infraction(generated_id, user.id, moderator_id, infraction_type, infraction_reason, round(time.time()))

    embed = discord.Embed(title="Sonnet", description=f"New infraction for {user.mention}:", color=0x758cff)
    embed.set_thumbnail(url=user.avatar_url)
    embed.add_field(name="Infraction ID", value=str(generated_id))
    embed.add_field(name="Moderator", value=f"{client.get_user(int(moderator_id))}")
    embed.add_field(name="User", value=f"{user}")
    embed.add_field(name="Type", value=infraction_type)
    embed.add_field(name="Reason", value=infraction_reason)

    dm_embed = discord.Embed(title="Sonnet", description=f"Your punishment in {message.guild.name} has been updated:", color=0x758cff)
    dm_embed.set_thumbnail(url=user.avatar_url)
    dm_embed.add_field(name="Infraction ID", value=str(generated_id))
    dm_embed.add_field(name="Type", value=infraction_type)
    dm_embed.add_field(name="Reason", value=infraction_reason)
    if send_message:
        asyncio.create_task(log_channel.send(embed=embed))
    dm_sent = asyncio.create_task(catch_dm_error(user, dm_embed, log_channel))
    return (generated_id, dm_sent)


class InfractionGenerationError(Exception):
    pass


# General processor for infractions
async def process_infraction(message, args, client, infraction_type, pretty_infraction_type):

    # Check if automod
    automod = False
    try:
        if (type(args[0]) == int):
            args[0] = str(args[0])
            automod = True
    except IndexError:
        pass

    if len(args) > 1:
        reason = " ".join(args[1:])[:1024]
    else:
        reason = "No Reason Specified"

    # Parse moderatorID
    if automod:
        moderator_id = client.user.id
    else:
        moderator_id = message.author.id

    # Test if user is valid
    try:
        user = message.channel.guild.get_member(int(args[0].strip("<@!>")))
        is_member = True
    except ValueError:
        await message.channel.send("Invalid User")
        raise InfractionGenerationError("Invalid User")
    except IndexError:
        await message.channel.send("No user specified")
        raise InfractionGenerationError("No user specified")

    if not user:
        is_member = False
        user = client.get_user(int(args[0].strip("<@!>")))
        if not user:
            user = None

    # Test if user is self
    if user and moderator_id == user.id:
        await message.channel.send(f"{pretty_infraction_type} yourself is not allowed")
        raise InfractionGenerationError(f"Attempted self {infraction_type}")

    # Do a permission sweep
    if is_member and message.guild.roles.index(message.author.roles[-1]) <= message.guild.roles.index(user.roles[-1]):
        await message.channel.send(f"Cannot {infraction_type} a user with the same or higher role as yourself")
        raise InfractionGenerationError(f"Attempted nonperm {infraction_type}")

    # Log infraction
    infraction_id, dm_sent = await log_infraction(message, client, user, moderator_id, reason, infraction_type)

    return (automod, user, reason, infraction_id, is_member, dm_sent)


async def warn_user(message, args, client, **kwargs):

    try:
        automod, user, reason, infractionID, is_member, dm_sent = await process_infraction(message, args, client, "warn", "Warning")
    except InfractionGenerationError:
        return

    if not (automod) and user:
        await message.channel.send(f"Warned {user.mention} with ID {user.id} for {reason}"[:2000])
    elif not user:
        await message.channel.send("User does not exist")


async def kick_user(message, args, client, **kwargs):

    try:
        automod, user, reason, infractionID, is_member, dm_sent = await process_infraction(message, args, client, "kick", "Kicking")
    except InfractionGenerationError:
        return

    # Attempt to kick user
    if is_member and user:
        try:
            await dm_sent  # Wait for dm to be sent before kicking
            await message.guild.kick((user), reason=reason)
        except discord.errors.Forbidden:
            await message.channel.send("The bot does not have permission to kick this user.")
            return
    else:
        await message.channel.send("User is not in this guild")
        return

    if not automod:
        await message.channel.send(f"Kicked {user.mention} with ID {user.id} for {reason}"[:2000])


async def ban_user(message, args, client, **kwargs):

    try:
        automod, user, reason, infractionID, is_member, dm_sent = await process_infraction(message, args, client, "ban", "Banning")
    except InfractionGenerationError:
        return

    # Attempt to ban user
    try:
        if is_member:
            await dm_sent  # Wait for dm to be sent before banning
        userOBJ = discord.Object(int(args[0].strip("<@!>")))
        await message.guild.ban(userOBJ, delete_message_days=0, reason=reason)

    except discord.errors.Forbidden:
        await message.channel.send("The bot does not have permission to ban this user.")
        return
    except (discord.errors.NotFound, discord.errors.HTTPException):
        await message.channel.send("This user does not exist")
        return

    if not automod:
        await message.channel.send(f"Banned <@!{args[0].strip('<@!>')}> with ID {args[0].strip('<@!>')} for {reason}"[:2000])


async def unban_user(message, args, client, **kwargs):

    # Test if user is valid
    try:
        user = await client.fetch_user(int(args[0].strip("<@!>")))
    except ValueError:
        await message.channel.send("Invalid User")
        return
    except IndexError:
        await message.channel.send("No user specified")
        return
    except discord.errors.NotFound:
        await message.channel.send("Invalid User")
        return

    if not user:
        await message.channel.send("Invalid User")
        return

    # Attempt to unban user
    try:
        await message.guild.unban(user)
    except discord.errors.Forbidden:
        await message.channel.send("The bot does not have permission to unban this user.")
        return
    except discord.errors.NotFound:
        await message.channel.send("This user is not banned")
        return

    await message.channel.send(f"Unbanned {user.mention} with ID {user.id}")


async def mute_user(message, args, client, **kwargs):

    if len(args) >= 2:
        try:
            multiplicative_factor = {"s": 1, "m": 60, "h": 3600}
            tmptime = args[1]
            if not tmptime[-1] in ["s", "m", "h"]:
                mutetime = int(tmptime)
                del args[1]
            else:
                mutetime = int(tmptime[:-1]) * multiplicative_factor[tmptime[-1]]
                del args[1]
        except (ValueError, TypeError):
            mutetime = 0
    else:
        mutetime = 0

    # This ones for you, curl
    if mutetime >= 60 * 60 * 256:
        mutetime = 0

    try:
        automod, user, reason, infractionID, is_member, dm_sent = await process_infraction(message, args, client, "mute", "Muting")
    except InfractionGenerationError:
        return

    if not user:
        await message.channel.send("User does not exist")
        return

    # Check they are in the guild
    if not is_member:
        await message.channel.send("User is not in this guild")
        return

    # Get muterole from DB
    with db_hlapi(message.guild.id) as db:
        mute_role = db.grab_config("mute-role")

    if mute_role:
        mute_role = message.guild.get_role(int(mute_role))
        if not mute_role:
            await message.channel.send("ERROR: no muterole set")
            return
    else:
        await message.channel.send("ERROR: no muterole set")
        return

    # Attempt to mute user
    try:
        await user.add_roles(mute_role)
    except discord.errors.Forbidden:
        await message.channel.send("The bot does not have permission to mute this user.")
        return

    if not automod and not mutetime:
        await message.channel.send(f"Muted {user.mention} with ID {user.id} for {reason}"[:2000])

    if mutetime:
        if not automod:
            asyncio.create_task(message.channel.send(f"Muted {user.mention} with ID {user.id} for {mutetime}s for {reason}"[:2000]))
        # add to mutedb
        with db_hlapi(message.guild.id) as db:
            db.mute_user(user.id, time.time() + mutetime, infractionID)

        await asyncio.sleep(mutetime)

        # unmute in db
        with db_hlapi(message.guild.id) as db:
            if db.is_muted(infractionid=infractionID):
                db.unmute_user(infractionid=infractionID)

                try:
                    await user.remove_roles(mute_role)
                except discord.errors.HTTPException:
                    pass


async def unmute_user(message, args, client, **kwargs):

    # Test if user is valid
    try:
        user = message.channel.guild.get_member(int(args[0].strip("<@!>")))
    except ValueError:
        await message.channel.send("Invalid User")
        return
    except IndexError:
        await message.channel.send("No user specified")
        return

    if not user:
        await message.channel.send("Invalid User")
        return

    # Get muterole from DB
    with db_hlapi(message.guild.id) as db:
        mute_role = db.grab_config("mute-role")
        db.unmute_user(userid=user.id)

    if mute_role:
        mute_role = message.guild.get_role(int(mute_role))
        if not mute_role:
            await message.channel.send("ERROR: no muterole set")
            return
    else:
        await message.channel.send("ERROR: no muterole set")
        return

    # Attempt to unmute user
    try:
        await user.remove_roles(mute_role)
    except discord.errors.Forbidden:
        await message.channel.send("The bot does not have permission to unmute this user.")
        return

    await message.channel.send(f"Unmuted {user.mention} with ID {user.id}")


async def general_infraction_grabber(message, args, client):

    # Reparse args
    args = message.content.replace("=", " ").split(" ")[1:]

    # Parse flags
    selected_chunk = 0
    responsible_mod = None
    infraction_type = None
    user_affected = None
    automod = True
    for index, item in enumerate(args):
        try:
            if item in ["-p", "--page"]:
                selected_chunk = int(float(args[index + 1])) - 1
            elif item in ["-m", "--mod"]:
                responsible_mod = (args[index + 1].strip("<@!>"))
            elif item in ["-u", "--user"]:
                user_affected = (args[index + 1].strip("<@!>"))
            elif item in ["-t", "--type"]:
                infraction_type = (args[index + 1])
            elif item == "--no-automod":
                automod = False
        except (ValueError, IndexError):
            await message.channel.send("Invalid flags supplied")
            return

    with db_hlapi(message.guild.id) as db:
        if user_affected:
            infractions = db.grab_user_infractions(user_affected)
        elif responsible_mod:
            infractions = db.grab_moderator_infractions(responsible_mod)
        else:
            await message.channel.send("Please specify a user or moderator")
            return

    # Generate sorts
    if not automod:
        automod_id = str(client.user.id)
        infractions = [i for i in infractions if not (i[2] == automod_id or "[AUTOMOD]" in i[4])]
    if responsible_mod:
        infractions = [i for i in infractions if i[2] == responsible_mod]
    if user_affected:
        infractions = [i for i in infractions if i[1] == user_affected]
    if infraction_type:
        infractions = [i for i in infractions if i[3] == infraction_type]

    # Sort newest first
    infractions.sort(reverse=True, key=lambda a: a[5])

    # Generate chunks from infractions
    do_not_exceed = 1900  # Discord message length limits
    chunks = [""]
    curchunk = 0
    for i in infractions:
        infraction_data = ", ".join([i[0], i[3], i[4]]) + "\n"
        if (len(chunks[curchunk]) + len(infraction_data)) > do_not_exceed:
            curchunk += 1
            chunks.append("")
        else:
            chunks[curchunk] = chunks[curchunk] + infraction_data

    # Test if valid page
    try:
        outdata = chunks[selected_chunk]
    except IndexError:
        outdata = chunks[0]
        selected_chunk = 0

    if infractions:
        await message.channel.send(f"Page {selected_chunk+1} of {len(chunks)} ({len(infractions)} infractions)\n```css\nID, Type, Reason\n{outdata}```")
    else:
        await message.channel.send("No infractions found")


async def search_infractions_by_user(message, args, client, **kwargs):

    await general_infraction_grabber(message, args, client)


async def get_detailed_infraction(message, args, client, **kwargs):

    if args:
        with db_hlapi(message.guild.id) as db:
            infraction = db.grab_infraction(args[0])
        if not infraction:
            await message.channel.send("Infraction ID does not exist")
            return
    else:
        await message.channel.send("No argument supplied")
        return

    infraction_id, user_id, moderator_id, infraction_type, reason, timestamp = infraction

    infraction_embed = discord.Embed(title="Infraction Search", description=f"Infraction for <@{user_id}>:", color=0x758cff)
    infraction_embed.add_field(name="Infraction ID", value=infraction_id)
    infraction_embed.add_field(name="Moderator", value=f"<@{moderator_id}>")
    infraction_embed.add_field(name="Type", value=infraction_type)
    infraction_embed.add_field(name="Reason", value=reason)
    infraction_embed.timestamp = datetime.datetime.utcfromtimestamp(int(timestamp))

    await message.channel.send(embed=infraction_embed)


async def delete_infraction(message, args, client, **kwargs):

    if args:
        with db_hlapi(message.guild.id) as db:
            infraction = db.grab_infraction(args[0])
            db.delete_infraction(infraction[0])
        if not infraction:
            await message.channel.send("Infraction ID does not exist")
            return
    else:
        await message.channel.send("No argument supplied")
        return

    infraction_id, user_id, moderator_id, infraction_type, reason, timestamp = infraction

    infraction_embed = discord.Embed(title="Infraction Deleted", description=f"Infraction for <@{user_id}>:", color=0xd62d20)
    infraction_embed.add_field(name="Infraction ID", value=infraction_id)
    infraction_embed.add_field(name="Moderator", value=f"<@{moderator_id}>")
    infraction_embed.add_field(name="Type", value=infraction_type)
    infraction_embed.add_field(name="Reason", value=reason)
    infraction_embed.timestamp = datetime.datetime.utcfromtimestamp(int(timestamp))

    await message.channel.send(embed=infraction_embed)


async def grab_guild_message(message, args, client, **kwargs):

    try:
        message_link = args[0].replace("-", "/").split("/")
        log_channel = message_link[-2]
        message_id = message_link[-1]
    except IndexError:
        try:
            log_channel = args[0].strip("<#!>")
            message_id = args[1]
        except IndexError:
            await message.channel.send("Not enough args supplied")
            return

    try:
        log_channel = int(log_channel)
    except ValueError:
        await message.channel.send("Channel is not a valid channel")
        return

    discord_channel = client.get_channel(log_channel)
    if not discord_channel:
        await message.channel.send("Channel is not a valid channel")
        return

    if discord_channel.guild.id != message.channel.guild.id:
        await message.channel.send("Channel is not in guild")
        return

    try:
        discord_message = await discord_channel.fetch_message(int(message_id))
    except (ValueError, discord.errors.HTTPException):
        await message.channel.send("Invalid MessageID")
        return

    if not discord_message:
        await message.channel.send("Invalid MessageID")
        return

    # Generate replies
    message_content = generate_reply_field(discord_message)

    # Message has been grabbed, start generating embed
    message_embed = discord.Embed(title=f"Message in #{discord_message.channel}", description=message_content, color=0x758cff)

    message_embed.set_author(name=discord_message.author, icon_url=discord_message.author.avatar_url)
    message_embed.timestamp = discord_message.created_at

    # Grab files from cache
    fileobjs = grab_files(discord_message.guild.id, discord_message.id, kwargs["kernel_ramfs"])

    # Grab files async if not in cache
    if not fileobjs:
        awaitobjs = [asyncio.create_task(i.to_file()) for i in discord_message.attachments]
        fileobjs = [await i for i in awaitobjs]

    try:
        await message.channel.send(embed=message_embed, files=fileobjs)
    except discord.errors.HTTPException:
        await message.channel.send("There were files attached but they exceeded the guild filesize limit", embed=message_embed)


category_info = {'name': 'moderation', 'pretty_name': 'Moderation', 'description': 'Moderation commands.'}

commands = {
    'warn': {
        'pretty_name': 'warn <uid> [reason]',
        'description': 'Warn a user',
        'permission': 'moderator',
        'cache': 'keep',
        'execute': warn_user
        },
    'kick': {
        'pretty_name': 'kick <uid> [reason]',
        'description': 'Kick a user',
        'permission': 'moderator',
        'cache': 'keep',
        'execute': kick_user
        },
    'ban': {
        'pretty_name': 'ban <uid> [reason]',
        'description': 'Ban a user',
        'permission': 'moderator',
        'cache': 'keep',
        'execute': ban_user
        },
    'unban': {
        'pretty_name': 'unban <uid>',
        'description': 'Unban a user',
        'permission': 'moderator',
        'cache': 'keep',
        'execute': unban_user
        },
    'mute': {
        'pretty_name': 'mute <uid> [time[h|m|S]] [reason]',
        'description': 'Mute a user, defaults to no unmute (0s)',
        'permission': 'moderator',
        'cache': 'keep',
        'execute': mute_user
        },
    'unmute': {
        'pretty_name': 'unmute <uid>',
        'description': 'Unmute a user',
        'permission': 'moderator',
        'cache': 'keep',
        'execute': unmute_user
        },
    'warnings': {
        'alias': 'search-infractions'
        },
    'list-infractions': {
        'alias': 'search-infractions'
        },
    'search-infractions':
        {
            'pretty_name': 'search-infractions <-u USER | -m MOD> [-t TYPE] [-p PAGE] [--no-automod]',
            'description': 'Grab infractions of a user',
            'permission': 'moderator',
            'cache': 'keep',
            'execute': search_infractions_by_user
            },
    'get-infraction': {
        'alias': 'infraction-details'
        },
    'infraction-details':
        {
            'pretty_name': 'infraction-details <infractionID>',
            'description': 'Grab details of an infractionID',
            'permission': 'moderator',
            'cache': 'keep',
            'execute': get_detailed_infraction
            },
    'remove-infraction': {
        'alias': 'delete-infraction'
        },
    'rm-infraction': {
        'alias': 'delete-infraction'
        },
    'delete-infraction':
        {
            'pretty_name': 'delete-infraction <infractionID>',
            'description': 'Delete an infraction by infractionID',
            'permission': 'administrator',
            'cache': 'keep',
            'execute': delete_infraction
            },
    'get-message': {
        'alias': 'grab-message'
        },
    'grab-message':
        {
            'pretty_name': 'grab-message <channelID> <messageID>',
            'description': 'Grab a message and show its contents',
            'permission': 'moderator',
            'cache': 'keep',
            'execute': grab_guild_message
            }
    }

version_info = "1.1.4-DEV"
