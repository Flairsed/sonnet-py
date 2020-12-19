# Administration commands.
# bredo, 2020

import discord, os
from datetime import datetime
import json, gzip, io, time

from sonnet_cfg import GLOBAL_PREFIX
from lib_mdb_handler import db_handler, db_error


async def recreate_db(message, args, client, stats, cmds):
    with db_handler() as db:
        db.make_new_table(f"{message.guild.id}_config",[["property", tuple, 1], ["value", str]])
        db.make_new_table(f"{message.guild.id}_infractions", [
        ["infractionID", tuple, 1],
        ["userID", str],
        ["moderatorID", str],
        ["type", str],
        ["reason", str],
        ["timestamp", int(64)]
        ])
    await message.channel.send("done (unless something broke)")


# Put channel item in DB, and check for collisions
async def update_log_channel(message, args, client, log_name):

    if not message.author.permissions_in(message.channel).administrator:
        await message.channel.send("Insufficient permissions.")
        raise RuntimeError("Insufficient permissions.")

    if len(args) >= 1:
        log_channel = args[0].strip("<#!>")
    else:
        await message.channel.send("No Channel supplied")
        raise RuntimeError("No Channel supplied")

    try:
        log_channel = int(log_channel)
    except ValueError:
        await message.channel.send("Channel is not a valid channel")
        raise RuntimeError("Channel is not a valid channel")

    discord_channel = client.get_channel(log_channel)
    if not discord_channel:
        await message.channel.send("Channel is not a valid channel")
        raise RuntimeError("Channel is not a valid channel")

    if discord_channel.guild.id != message.channel.guild.id:
        await message.channel.send("Channel is not in guild")
        raise RuntimeError("Channel is not in guild")

    # Nothing failed so send to db
    try:
        with db_handler() as db:
            db.add_to_table(f"{message.guild.id}_config", [
                ["property", log_name],
                ["value", log_channel]
                ])
    except db_error.OperationalError:
        await message.channel.send("Database error, run recreate-db")
        raise RuntimeError("Database error, run recreate-db")

    await message.channel.send(f"Successfully updated {log_name}")


async def inflog_change(message, args, client, stats, cmds):
    try:
        await update_log_channel(message, args, client, "infraction-log")
    except RuntimeError:
        return


async def joinlog_change(message, args, client, stats, cmds):
    try:
        await update_log_channel(message, args, client, "join-log")
    except RuntimeError:
        return


async def msglog_change(message, args, client, stats, cmds):
    try:
        await update_log_channel(message, args, client, "message-log")
    except RuntimeError:
        return

async def archivelog_change(message, args, client, stats, cmds):
    try:
        await update_log_channel(message, args, client, "archive-channel")
    except RuntimeError:
        return


class gdpr_functions:

    async def delete(message, guild_id):

        with db_handler() as database:
            for i in ["_config","_infractions"]:
                database.delete_table(f"{guild_id}{i}")

        os.remove(f"datastore/{guild_id}.cache.db")
        await message.channel.send(f"Deleted database for guild {message.guild.id}")

    async def download(message, guild_id):

        timestart = time.time()
        dbdict = {
            "config":[["property","value"]],
            "infractions":[["infractionID","userID","moderatorID","type","reason","timestamp"]]
            }

        with db_handler() as database:
            for i in ["config","infractions"]:
                try:
                    dbdict[i].extend(database.fetch_table(f"{guild_id}_{i}"))
                except db_error.OperationalError:
                    await message.channel.send(f"Could not grab {i}, it may not exist")
    
        # Convert to compressed json
        file_to_upload = io.BytesIO()
        with gzip.GzipFile(filename=f"{guild_id}.db.json.gz", mode="wb", fileobj=file_to_upload) as txt:
            txt.write(json.dumps(dbdict, indent=4).encode("utf8"))
        file_to_upload.seek(0)
        # Finalize discord file obj
        fileobj = discord.File(file_to_upload, filename="database.gz")
        
        await message.channel.send(f"Grabbing DB took: {round((time.time()-timestart)*100000)/100}ms", file=fileobj)


async def gdpr_database(message, args, client, stats, cmds):

    has_perms = (message.author.id == message.channel.guild.owner.id)
    if not has_perms:
        await message.channel.send("Only the Server Owner may run this command")
        return

    if len(args) >= 2:
        command = args[0]
        confirmation = args[1]
    elif len(args) >= 1:
        command = args[0]
        confirmation = None
    else:
        command = None


    commands_dict = {"delete": gdpr_functions.delete, "download": gdpr_functions.download}
    if command and command in commands_dict.keys():
        if confirmation and confirmation == str(message.guild.id):
            await commands_dict[command](message, message.guild.id)
        else:
            await message.channel.send(f"Please provide the guildid to confirm\nEx: `{GLOBAL_PREFIX}gdpr {command} {message.guild.id}`")
    else:
        message_embed = discord.Embed(title="GDPR COMMANDS", color=0xADD8E6)
        message_embed.add_field(name=f"{GLOBAL_PREFIX}gdpr download <guildid>", value="Download the infraction and config databases of this guild", inline=False)
        message_embed.add_field(name=f"{GLOBAL_PREFIX}gdpr delete <guildid>", value="Delete the infraction and config databases of this guild and clear cache", inline=False)
        await message.channel.send(embed=message_embed)


category_info = {
    'name': 'administration',
    'pretty_name': 'Administration',
    'description': 'Administration commands.'
}


commands = {
    'recreate-db': {
        'pretty_name': 'recreate-db',
        'description': 'Recreate the database if it doesn\'t exist',
        'execute': recreate_db
    },
    'message-log': {
        'pretty_name': 'message-log',
        'description': 'Change message log for this guild.',
        'execute': msglog_change
    },
    'infraction-log': {
        'pretty_name': 'infraction-log',
        'description': 'Change infraction log for this guild.',
        'execute': inflog_change
    },
    'join-log': {
        'pretty_name': 'join-log',
        'description': 'Change join log for this guild.',
        'execute': joinlog_change
    },
    'archive-channel': {
        'pretty_name': 'archive-channel',
        'description': 'Change archive log for this guild. (starboard)',
        'execute': archivelog_change
    },
    'gdpr': {
        'pretty_name': 'gdpr',
        'description': 'Enforce your GDPR rights, Server Owner only',
        'execute': gdpr_database
    }
}
