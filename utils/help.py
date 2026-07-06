from __future__ import annotations

from typing import Optional

import discord
from discord.ext import commands

from utils import emojis
from utils.components_v2 import action_row, container, separator, text


MAX_PAGE_CHARS = 3600


class HelpDropdown(discord.ui.Select):
    def __init__(self, ctx: commands.Context, options: list[discord.SelectOption]):
        super().__init__(
            placeholder="Choose a Category for Help",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"help:v2:select:{ctx.author.id}",
        )
        self.invoker = ctx.author

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.invoker:
            await interaction.response.send_message("You must run this command to interact with it.", ephemeral=True)
            return

        index = self.view.find_index_from_select(self.values[0])  # type: ignore[union-attr]
        await self.view.set_page(index or 0, interaction)  # type: ignore[union-attr]


class HelpButton(discord.ui.Button):
    def __init__(
        self,
        *,
        invoker: discord.abc.User,
        action: str,
        emoji: str,
        disabled: bool = False,
        style: discord.ButtonStyle = discord.ButtonStyle.secondary,
    ):
        super().__init__(
            emoji=emoji,
            style=style,
            custom_id=f"help:v2:{action}:{invoker.id}",
            disabled=disabled,
        )
        self.invoker = invoker
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.invoker:
            await interaction.response.send_message("You must run this command to interact with it.", ephemeral=True)
            return

        view: HelpView = self.view  # type: ignore[assignment]
        if self.action == "home":
            await view.set_page(0, interaction)
        elif self.action == "prev":
            await view.set_page(view.index - 1, interaction)
        elif self.action == "delete":
            await interaction.response.defer()
            if interaction.message:
                await interaction.message.delete()
        elif self.action == "next":
            await view.set_page(view.index + 1, interaction)
        elif self.action == "last":
            await view.set_page(view.total_pages - 1, interaction)


class HelpView(discord.ui.LayoutView):
    def __init__(
        self,
        mapping: dict,
        ctx: commands.Context,
        homeembed: Optional[discord.Embed] = None,
        ui: int = 2,
        *,
        prefix: Optional[str] = None,
        total_commands: Optional[int] = None,
    ):
        super().__init__(timeout=None)
        self.mapping = mapping
        self.ctx = ctx
        self.prefix = prefix or getattr(ctx, "prefix", ">") or ">"
        self.total_commands = total_commands or len(set(ctx.bot.walk_commands()))
        self.index = 0
        self.pages, self.options = self._build_pages()
        self.total_pages = len(self.pages)
        self._render()

    def get_cogs(self):
        return list(self.mapping.keys())

    def find_index_from_select(self, value: str) -> int:
        for index, option in enumerate(self.options):
            if option.value == value:
                return index
        return 0

    def _build_home_page(self) -> str:
        module_lines = [
            f"{emojis.VOICE_003466} Voice",
            f"{emojis.GAMES} Games",
            f"{emojis.GREET} Welcomer",
            f"{emojis.AUTOREACT} Autoreact & responder",
            f"{emojis.AUTOROLE} Autorole & Invc",
            f"{emojis.EXTRA} Fun & AI Image Gen",
            f"{emojis.IGNORE} Ignore Channels",
            f"{emojis.LOGGING} Advance Logging",
            f"{emojis.INVITETRACKER} Invite Tracker",
        ]
        feature_lines = [
            f"{emojis.SECURITY} Security",
            f"{emojis.BOTS} Automoderation",
            f"{emojis.UTILITY} Utility",
            f"{emojis.MUSIC} Music",
            f"{emojis.MODERATION} Moderation",
            f"{emojis.CUSTOMROLE} Customrole",
            f"{emojis.GIVEAWAY_644980} Giveaway",
            f"{emojis.TICKET} Ticket",
            f"{emojis.VANITYROLES} Vanityroles",
        ]

        return "\n".join(
            [
                "## Help",
                f"{emojis.BLUEDOT} **Server Prefix:** `{self.prefix}`",
                f"{emojis.BLUEDOT} **Total Commands:** `{self.total_commands}`",
                f"{emojis.BLUEDOT} **Type `{self.prefix}antinuke enable` to get started**",
                "",
                f"### {emojis.MODULE} Module",
                "\n".join(module_lines),
                "",
                f"### {emojis.FILDER} My Features",
                "\n".join(feature_lines),
            ]
        )

    def _build_command_page(self, cog) -> str:
        _, label, description = cog.help_custom()
        lines = [f"## {label}", description or "Commands in this category.", ""]

        commands_for_cog = [command for command in cog.get_commands() if not command.hidden]
        if not commands_for_cog:
            lines.append("No commands available.")
        else:
            for command in commands_for_cog:
                params = "".join(f" <{param}>" for param in command.clean_params)
                help_text = command.help or "No description provided."
                lines.append(f"**`{self.prefix}{command.name}{params}`**")
                lines.append(help_text)
                lines.append("")

        page = "\n".join(lines).strip()
        if len(page) > MAX_PAGE_CHARS:
            page = page[: MAX_PAGE_CHARS - 40].rstrip() + "\n\n...more commands available."
        return page

    def _build_pages(self) -> tuple[list[str], list[discord.SelectOption]]:
        pages = [self._build_home_page()]
        options = [
            discord.SelectOption(label="Home", value="__home__", emoji=str(emojis.HOME), description="Main help panel")
        ]

        for cog in self.get_cogs():
            if "help_custom" not in dir(cog):
                continue

            emoji, label, description = cog.help_custom()
            pages.append(self._build_command_page(cog))
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    value=label[:100],
                    emoji=str(emoji),
                    description=(description or "")[:100],
                )
            )

        return pages, options[:25]

    def _footer(self) -> str:
        return f"Page {self.index + 1}/{self.total_pages} | Requested by: {self.ctx.author.display_name}"

    def _nav_buttons(self) -> list[HelpButton]:
        return [
            HelpButton(invoker=self.ctx.author, action="home", emoji=str(emojis.REWIND1), disabled=self.index == 0),
            HelpButton(invoker=self.ctx.author, action="prev", emoji=str(emojis.NEXT), disabled=self.index == 0),
            HelpButton(invoker=self.ctx.author, action="delete", emoji=str(emojis.DELETE), style=discord.ButtonStyle.danger),
            HelpButton(
                invoker=self.ctx.author,
                action="next",
                emoji=str(emojis.ICONS_NEXT),
                disabled=self.index >= self.total_pages - 1,
            ),
            HelpButton(
                invoker=self.ctx.author,
                action="last",
                emoji=str(emojis.FORWARD),
                disabled=self.index >= self.total_pages - 1,
            ),
        ]

    def _render(self) -> None:
        self.clear_items()
        self.add_item(
            container(
                text(self.pages[self.index]),
                separator(),
                text(self._footer()),
                separator(),
                action_row(*self._nav_buttons()),
                action_row(HelpDropdown(self.ctx, self.options)),
            )
        )

    async def set_page(self, page: int, interaction: discord.Interaction):
        self.index = max(0, min(page, self.total_pages - 1))
        self._render()
        await interaction.response.edit_message(view=self)


View = HelpView
