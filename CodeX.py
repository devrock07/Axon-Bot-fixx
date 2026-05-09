import asyncio
import logging
import os
from threading import Thread

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask

from core.axon import IndiaBot

os.environ["JISHAKU_NO_DM_TRACEBACK"] = "False"
os.environ["JISHAKU_HIDE"] = "True"
os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
os.environ["JISHAKU_FORCE_PAGINATOR"] = "True"

load_dotenv()

TOKEN = os.getenv("TOKEN")
COMMAND_LOG_WEBHOOK = os.getenv("COMMAND_LOG_WEBHOOK")
ENABLE_KEEP_ALIVE = os.getenv("ENABLE_KEEP_ALIVE", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger("india.main")
client = IndiaBot()


@client.listen("on_ready")
async def log_ready_state() -> None:
    print("India loaded and online.")
    print(f"Logged in as: {client.user}")
    print(f"Connected guilds: {len(client.guilds)}")
    print(f"Cached users: {len(client.users)}")
    print(f"Loaded prefix commands: {len(client.commands)}")

    tree_stats = client.get_command_tree_stats()
    print(
        "Application commands prepared: "
        f"{tree_stats['top_level']} top-level / {tree_stats['total_walked']} total"
    )

    invite_url = discord.utils.oauth_url(
        client.user.id,
        permissions=discord.Permissions(administrator=True),
        scopes=("bot", "applications.commands"),
    )
    print(f"Invite with slash-command scope: {invite_url}")

    sync_overview = client.get_command_sync_overview()
    if sync_overview:
        print(f"Last slash sync report: {sync_overview}")
    else:
        print("Slash commands are syncing through the startup sync manager.")


@client.event
async def on_command_completion(context: commands.Context) -> None:
    if context.author.id == 767979794411028491:
        return

    if not COMMAND_LOG_WEBHOOK:
        return

    try:
        full_command_name = context.command.qualified_name
        executed_command = str(full_command_name.split("\n")[0])

        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(COMMAND_LOG_WEBHOOK, session=session)
            embed = discord.Embed(color=0x000000)
            avatar_url = (
                context.author.avatar.url
                if context.author.avatar
                else context.author.default_avatar.url
            )
            embed.set_author(
                name=f"Executed {executed_command} Command By : {context.author}",
                icon_url=avatar_url,
            )
            embed.set_thumbnail(url=avatar_url)
            embed.add_field(name=" Command Name :", value=executed_command, inline=False)
            embed.add_field(
                name=" Command Executed By :",
                value=(
                    f"{context.author} | ID: "
                    f"[{context.author.id}](https://discord.com/users/{context.author.id})"
                ),
                inline=False,
            )

            if context.guild is not None:
                embed.add_field(
                    name=" Command Executed In :",
                    value=(
                        f"{context.guild.name} | ID: "
                        f"[{context.guild.id}](https://discord.com/guilds/{context.guild.id})"
                    ),
                    inline=False,
                )
                embed.add_field(
                    name=" Command Executed In Channel :",
                    value=(
                        f"{context.channel.name} | ID: "
                        f"[{context.channel.id}]"
                        f"(https://discord.com/channels/{context.guild.id}/{context.channel.id})"
                    ),
                    inline=False,
                )

            embed.timestamp = discord.utils.utcnow()
            embed.set_footer(
                text="India Development",
                icon_url=client.user.display_avatar.url if client.user else None,
            )
            await webhook.send(embed=embed)
    except Exception:
        logger.exception("Failed to send command completion webhook.")


app = Flask(__name__)


@app.route("/")
def home():
    return "India Server 2026"


def run():
    app.run(host="0.0.0.0", port=8080, use_reloader=False)


def keep_alive():
    server = Thread(target=run, daemon=True)
    server.start()


async def main():
    if not TOKEN:
        raise RuntimeError("TOKEN is missing from the environment.")

    if ENABLE_KEEP_ALIVE:
        keep_alive()

    async with client:
        os.system("cls" if os.name == "nt" else "clear")
        await client.load_extension("jishaku")
        await client.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
