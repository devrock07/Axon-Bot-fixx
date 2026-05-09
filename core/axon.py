from __future__ import annotations

import asyncio
import logging
import os
import typing
from typing import List, Optional, Sequence

import aiosqlite
import discord
from colorama import Fore, Style, init
from discord import app_commands
from discord.ext import commands

from utils import getConfig
from utils.config import OWNER_IDS

from .Context import Context

init(autoreset=True)

extensions: List[str] = ["cogs"]

_SYNC_MODE_AUTO = "auto"
_SYNC_MODE_GUILD = "guild"
_SYNC_MODE_GLOBAL = "global"
_SYNC_MODE_OFF = "off"


class IndiaCommandTree(app_commands.CommandTree):
    async def on_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        logger = logging.getLogger("india.tree")
        command_name = getattr(interaction.command, "qualified_name", None) or getattr(
            interaction.command, "name", "unknown"
        )

        original = getattr(error, "original", error)
        message = "This slash command failed unexpectedly."

        if isinstance(error, app_commands.CommandOnCooldown):
            message = f"You're on cooldown. Try again in {error.retry_after:.1f}s."
        elif isinstance(error, app_commands.CheckFailure):
            message = "You do not have permission to use this command here."
        elif isinstance(error, app_commands.TransformerError):
            message = "One or more command arguments were invalid."
        elif isinstance(original, commands.CommandOnCooldown):
            message = f"You're on cooldown. Try again in {original.retry_after:.1f}s."
        elif isinstance(original, commands.CheckFailure):
            message = "You do not have permission to use this command here."
        elif isinstance(
            original, (commands.BadArgument, commands.MissingRequiredArgument)
        ):
            message = "One or more command arguments were invalid."
        else:
            logger.exception(
                "Application command '%s' failed in guild=%s channel=%s user=%s",
                command_name,
                getattr(interaction.guild, "id", None),
                getattr(interaction.channel, "id", None),
                getattr(interaction.user, "id", None),
                exc_info=original,
            )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            logger.exception(
                "Failed to send app command error response for '%s'.", command_name
            )


class IndiaBot(commands.AutoShardedBot):
    @property
    def loop(self):
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            loop = getattr(self, "_india_loop", None)
            if loop is None:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self._india_loop = loop
            return loop

    @loop.setter
    def loop(self, value):
        self._india_loop = value

    def __init__(self, *arg, **kwargs):
        intents = discord.Intents.all()
        intents.presences = True
        intents.members = True

        self.logger = logging.getLogger("india.bot")
        self._startup_sync_done = False
        self._command_sync_lock = asyncio.Lock()
        self._background_tasks: set[asyncio.Task] = set()
        self._last_command_sync_report: dict[str, typing.Any] = {}

        super().__init__(
            command_prefix=self.get_prefix,
            case_insensitive=True,
            intents=intents,
            status=discord.Status.online,
            strip_after_prefix=True,
            owner_ids=set(OWNER_IDS),
            allowed_mentions=discord.AllowedMentions(
                everyone=False, replied_user=False, roles=False
            ),
            shard_count=2,
            tree_cls=IndiaCommandTree,
        )

    async def setup_hook(self):
        await self.load_extensions()
        self.before_invoke(self._auto_defer_interaction)
        self.add_listener(self._run_startup_sync_once, "on_ready")

    async def get_context(self, origin, /, *, cls=Context):
        return await super().get_context(origin, cls=cls)

    def create_background_task(
        self, coro: typing.Coroutine[typing.Any, typing.Any, typing.Any], *, name: str
    ) -> asyncio.Task:
        task = self.loop.create_task(coro, name=name)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        task.add_done_callback(self._handle_task_result)
        return task

    def _handle_task_result(self, task: asyncio.Task) -> None:
        if task.cancelled():
            return

        try:
            task.result()
        except Exception:
            self.logger.exception(
                "Background task '%s' crashed.",
                task.get_name() if hasattr(task, "get_name") else "unknown",
            )

    async def _auto_defer_interaction(self, ctx: Context) -> None:
        interaction: Optional[discord.Interaction] = getattr(ctx, "interaction", None)
        if interaction is None or interaction.response.is_done():
            return

        try:
            await interaction.response.defer(thinking=True)
        except (discord.InteractionResponded, discord.NotFound, discord.HTTPException):
            pass

    async def load_extensions(self):
        failures: list[tuple[str, Exception]] = []

        for extension in extensions:
            try:
                await self.load_extension(extension)
                self.logger.info("Loaded extension: %s", extension)
                print(Fore.BLUE + Style.BRIGHT + f"Loaded extension: {extension}")
            except Exception as exc:
                failures.append((extension, exc))
                self.logger.exception("Failed to load extension '%s'.", extension)
                print(
                    f"{Fore.RED}{Style.BRIGHT}Failed to load extension {extension}. {exc}"
                )

        print(Fore.GREEN + Style.BRIGHT + "*" * 20)

        if failures:
            failed_names = ", ".join(name for name, _ in failures)
            raise RuntimeError(f"Required extensions failed to load: {failed_names}")

    async def on_connect(self):
        await self.change_presence(
            status=discord.Status.dnd,
            activity=discord.Activity(
                type=discord.ActivityType.playing, name=">help | .gg/india"
            ),
        )

    async def _run_startup_sync_once(self):
        async with self._command_sync_lock:
            if self._startup_sync_done:
                return

            self._startup_sync_done = True

            try:
                self._last_command_sync_report = await self.sync_application_commands()
            except Exception:
                self.logger.exception("Startup application command sync failed.")

    def _configured_sync_guild_ids(self) -> list[int]:
        raw_ids = os.getenv("COMMAND_SYNC_GUILDS", "")
        guild_ids: list[int] = []

        for value in raw_ids.split(","):
            value = value.strip()
            if not value:
                continue
            try:
                guild_ids.append(int(value))
            except ValueError:
                self.logger.warning("Ignoring invalid COMMAND_SYNC_GUILDS entry: %s", value)

        return guild_ids

    def _resolve_sync_mode(self) -> str:
        mode = os.getenv("COMMAND_SYNC_MODE", _SYNC_MODE_AUTO).strip().lower()
        if mode not in {
            _SYNC_MODE_AUTO,
            _SYNC_MODE_GUILD,
            _SYNC_MODE_GLOBAL,
            _SYNC_MODE_OFF,
        }:
            self.logger.warning(
                "Unknown COMMAND_SYNC_MODE '%s'. Falling back to '%s'.",
                mode,
                _SYNC_MODE_AUTO,
            )
            return _SYNC_MODE_AUTO
        return mode

    def get_command_sync_overview(self) -> dict[str, typing.Any]:
        return dict(self._last_command_sync_report)

    def _store_command_sync_report(
        self, report: dict[str, typing.Any]
    ) -> dict[str, typing.Any]:
        self._last_command_sync_report = dict(report)
        return report

    def get_command_tree_stats(self) -> dict[str, int]:
        top_level = list(self.tree.get_commands())
        all_commands = list(self.tree.walk_commands())
        chat_input_top_level = [
            command
            for command in top_level
            if getattr(command, "type", discord.AppCommandType.chat_input)
            == discord.AppCommandType.chat_input
        ]
        return {
            "top_level": len(top_level),
            "top_level_chat_input": len(chat_input_top_level),
            "total_walked": len(all_commands),
        }

    def _validate_application_command_tree(self) -> dict[str, int]:
        stats = self.get_command_tree_stats()
        top_level = list(self.tree.get_commands())
        duplicate_names = {
            command.name
            for command in top_level
            if sum(1 for other in top_level if other.name == command.name) > 1
        }

        if duplicate_names:
            raise RuntimeError(
                f"Duplicate top-level app command names found: {sorted(duplicate_names)}"
            )

        if stats["top_level_chat_input"] > 100:
            raise RuntimeError(
                "Discord allows at most 100 top-level slash commands per scope. "
                f"Current count: {stats['top_level_chat_input']}"
            )

        for command in top_level:
            try:
                command.to_dict(self.tree)
            except TypeError:
                command.to_dict()

        return stats

    async def sync_application_commands(
        self,
        *,
        guild_ids: Optional[Sequence[int]] = None,
        global_sync: bool = False,
    ) -> dict[str, typing.Any]:
        stats = self._validate_application_command_tree()
        report: dict[str, typing.Any] = {
            "top_level": stats["top_level"],
            "top_level_chat_input": stats["top_level_chat_input"],
            "total_walked": stats["total_walked"],
            "guild_results": [],
            "global_count": 0,
            "mode": None,
        }

        if global_sync:
            synced = await self.tree.sync()
            report["mode"] = _SYNC_MODE_GLOBAL
            report["global_count"] = len(synced)
            self.logger.info("Synced %s global application commands.", len(synced))
            return self._store_command_sync_report(report)

        if guild_ids:
            report["mode"] = _SYNC_MODE_GUILD
            for guild_id in guild_ids:
                guild_object = discord.Object(id=guild_id)
                self.tree.copy_global_to(guild=guild_object)
                synced = await self.tree.sync(guild=guild_object)
                guild_name = getattr(self.get_guild(guild_id), "name", str(guild_id))
                report["guild_results"].append(
                    {
                        "guild_id": guild_id,
                        "guild_name": guild_name,
                        "command_count": len(synced),
                    }
                )
                self.logger.info(
                    "Synced %s application commands to guild %s (%s).",
                    len(synced),
                    guild_name,
                    guild_id,
                )
            return self._store_command_sync_report(report)

        mode = self._resolve_sync_mode()
        configured_guild_ids = self._configured_sync_guild_ids()

        if mode == _SYNC_MODE_OFF:
            report["mode"] = _SYNC_MODE_OFF
            self.logger.warning("Application command sync is disabled by configuration.")
            return self._store_command_sync_report(report)

        if configured_guild_ids:
            return await self.sync_application_commands(guild_ids=configured_guild_ids)

        if mode == _SYNC_MODE_GLOBAL:
            return await self.sync_application_commands(global_sync=True)

        if mode == _SYNC_MODE_GUILD:
            if not self.guilds:
                self.logger.warning(
                    "No guilds are cached yet. Falling back to a global sync."
                )
                return await self.sync_application_commands(global_sync=True)
            return await self.sync_application_commands(
                guild_ids=[guild.id for guild in self.guilds]
            )

        if len(self.guilds) <= 10 and self.guilds:
            return await self.sync_application_commands(
                guild_ids=[guild.id for guild in self.guilds]
            )

        return await self.sync_application_commands(global_sync=True)

    async def on_ready(self):
        stats = self.get_command_tree_stats()
        self.logger.info(
            "Bot is ready as %s. Prefix commands=%s, app top-level=%s, app total=%s.",
            self.user,
            len(self.commands),
            stats["top_level"],
            stats["total_walked"],
        )
        print(f"Bot is ready! Logged in as {self.user}")

    async def close(self) -> None:
        for task in list(self._background_tasks):
            task.cancel()
        try:
            await super().close()
        except AttributeError as exc:
            if "_AutoShardedClient__queue" not in str(exc):
                raise
            self.logger.debug(
                "Skipped shard queue cleanup because the bot never fully initialized."
            )

    async def send_raw(
        self, channel_id: int, content: str, **kwargs
    ) -> typing.Optional[discord.Message]:
        await self.http.send_message(channel_id, content, **kwargs)

    async def invoke_help_command(self, ctx: Context) -> None:
        return await ctx.send_help(ctx.command)

    async def fetch_message_by_channel(
        self, channel: discord.TextChannel, messageID: int
    ) -> typing.Optional[discord.Message]:
        async for msg in channel.history(
            limit=1,
            before=discord.Object(messageID + 1),
            after=discord.Object(messageID - 1),
        ):
            return msg

    async def get_prefix(self, message: discord.Message):
        async def is_no_prefix_user(user_id: int) -> bool:
            async with aiosqlite.connect("db/np.db") as db:
                async with db.execute(
                    "SELECT 1 FROM np WHERE id = ?", (user_id,)
                ) as cursor:
                    return await cursor.fetchone() is not None

        if message.guild:
            prefix = (await getConfig(message.guild.id))["prefix"]
            if await is_no_prefix_user(message.author.id):
                return commands.when_mentioned_or(prefix, ">", "")(self, message)
            return commands.when_mentioned_or(prefix, ">")(self, message)

        if await is_no_prefix_user(message.author.id):
            return commands.when_mentioned_or(">")(self, message)

        return commands.when_mentioned_or(">")(self, message)

    async def on_message_edit(self, before, after):
        if before.content == after.content:
            return

        if after.guild is None or after.author.bot:
            return

        if isinstance(after.channel, discord.Thread):
            return

        ctx: Context = await self.get_context(after, cls=Context)
        if ctx.command is None:
            return

        await self.invoke(ctx)


def setup_bot():
    intents = discord.Intents.all()
    bot = IndiaBot(intents=intents)
    return bot


AxonCommandTree = IndiaCommandTree
axon = IndiaBot
