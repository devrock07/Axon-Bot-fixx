import asyncio
import os

import discord
import requests
from discord import ButtonStyle, SelectOption, ui
from discord.ext import commands

from utils.Tools import blacklist_check, ignore_check


class MapView(ui.View):
    def __init__(self, bot, location: str, ctx, latitude: float, longitude: float):
        super().__init__(timeout=300)
        self.bot = bot
        self.location = location
        self.ctx = ctx
        self.zoom_level = 14
        self.map_style = "map"
        self.map_size = "1200,900"
        self.latitude = latitude
        self.longitude = longitude
        self.coordinates = (latitude, longitude)
        self.update_map()

        self.add_item(MapStyleSelect(self))
        self.add_item(MapSizeSelect(self))

    @staticmethod
    async def fetch_coordinates(location: str):
        def _fetch():
            headers = {"User-Agent": "India Bot"}
            response = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": location, "format": "json"},
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
            if not data:
                return None
            return float(data[0]["lat"]), float(data[0]["lon"])

        try:
            return await asyncio.to_thread(_fetch)
        except (requests.RequestException, ValueError, KeyError, IndexError):
            return None

    def update_map(self):
        mapquest_key = os.getenv(
            "MAPQUEST_API_KEY",
            "E2SaL3qiTpXQ43nxZFBp0wzEnBI6pqbG",
        )
        self.map_url = (
            "https://www.mapquestapi.com/staticmap/v5/map"
            f"?key={mapquest_key}"
            f"&center={self.latitude},{self.longitude}"
            f"&zoom={self.zoom_level}&size={self.map_size}&type={self.map_style}"
        )

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title=f"Map of {self.location}", color=0x000000)
        embed.add_field(
            name="Open in Webpage",
            value=(
                "-> "
                f"**[Click Here](https://www.openstreetmap.org/?mlat={self.latitude}"
                f"&mlon={self.longitude}&zoom={self.zoom_level})**"
            ),
            inline=False,
        )
        embed.add_field(name="Current Zoom Level", value=f"-> {self.zoom_level}")
        embed.add_field(name="Map Style", value=f"-> {self.map_style}")
        embed.add_field(name="Map Size", value=f"-> {self.map_size}")
        embed.add_field(
            name="Current Coordinates",
            value=f"-> {self.latitude}, {self.longitude}",
            inline=False,
        )
        embed.set_image(url=self.map_url)
        embed.set_footer(
            text=f"Requested By {self.ctx.author}",
            icon_url=(
                self.ctx.author.avatar.url
                if self.ctx.author.avatar
                else self.ctx.author.default_avatar.url
            ),
        )
        return embed

    async def refresh_message(
        self, interaction: discord.Interaction, *, notice: str | None = None
    ) -> None:
        embed = self.build_embed()

        if interaction.response.is_done():
            await interaction.message.edit(embed=embed, view=self)
            if notice:
                await interaction.followup.send(notice, ephemeral=True)
            return

        await interaction.response.edit_message(embed=embed, view=self)
        if notice:
            await interaction.followup.send(notice, ephemeral=True)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="Sorry only the requested author can control this",
                    color=0x000000,
                ),
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="", emoji="⬅️", style=ButtonStyle.secondary)
    async def move_left(self, interaction: discord.Interaction, button: ui.Button):
        self.longitude -= 0.01
        self.update_map()
        await self.refresh_message(interaction)

    @discord.ui.button(label="", emoji="⬆️", style=ButtonStyle.secondary)
    async def move_up(self, interaction: discord.Interaction, button: ui.Button):
        self.latitude += 0.01
        self.update_map()
        await self.refresh_message(interaction)

    @discord.ui.button(
        label="", emoji="<:delete:1327842168693461022>", style=ButtonStyle.danger
    )
    async def delete_embed(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.response.is_done():
            await interaction.response.defer()
        await interaction.message.delete()

    @discord.ui.button(label="", emoji="⬇️", style=ButtonStyle.secondary)
    async def move_down(self, interaction: discord.Interaction, button: ui.Button):
        self.latitude -= 0.01
        self.update_map()
        await self.refresh_message(interaction)

    @discord.ui.button(label="", emoji="➡️", style=ButtonStyle.secondary)
    async def move_right(self, interaction: discord.Interaction, button: ui.Button):
        self.longitude += 0.01
        self.update_map()
        await self.refresh_message(interaction)

    @discord.ui.button(label="Zoom In", style=ButtonStyle.primary)
    async def zoom_in(self, interaction: discord.Interaction, button: ui.Button):
        self.zoom_level = min(self.zoom_level + 1, 18)
        self.update_map()
        await self.refresh_message(interaction)

    @discord.ui.button(label="Zoom Out", style=ButtonStyle.primary)
    async def zoom_out(self, interaction: discord.Interaction, button: ui.Button):
        self.zoom_level = max(self.zoom_level - 1, 0)
        self.update_map()
        await self.refresh_message(interaction)

    @discord.ui.button(label="Enter Coordinates", style=ButtonStyle.primary)
    async def enter_coordinates(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        await interaction.response.send_message(
            "Please enter the coordinates (latitude, longitude):", ephemeral=True
        )

        def check(message):
            return (
                message.author == interaction.user
                and message.channel == interaction.channel
            )

        try:
            coords_msg = await self.bot.wait_for("message", check=check, timeout=60)
            coords = coords_msg.content.split(",")
            if len(coords) != 2:
                await interaction.followup.send(
                    "Invalid coordinates format. Please enter `latitude, longitude`.",
                    ephemeral=True,
                )
                return

            self.latitude = float(coords[0].strip())
            self.longitude = float(coords[1].strip())
            self.coordinates = (self.latitude, self.longitude)
            self.update_map()
            await self.refresh_message(interaction, notice="Coordinates updated.")
        except (ValueError, TypeError):
            await interaction.followup.send(
                "Invalid coordinates. Please enter numeric `latitude, longitude` values.",
                ephemeral=True,
            )
        except asyncio.TimeoutError:
            await interaction.followup.send(
                "You took too long to respond. Please try again.", ephemeral=True
            )

    @discord.ui.button(label="Enter Address", style=ButtonStyle.success)
    async def enter_address(
        self, interaction: discord.Interaction, button: ui.Button
    ):
        await interaction.response.send_message(
            "Please enter the address:", ephemeral=True
        )

        def check(message):
            return (
                message.author == interaction.user
                and message.channel == interaction.channel
            )

        try:
            address_msg = await self.bot.wait_for("message", check=check, timeout=60)
            coordinates = await self.fetch_coordinates(address_msg.content)
            if coordinates is None:
                await interaction.followup.send(
                    "Failed to retrieve coordinates for that address. Please try again.",
                    ephemeral=True,
                )
                return

            self.latitude, self.longitude = coordinates
            self.coordinates = coordinates
            self.location = address_msg.content
            self.update_map()
            await self.refresh_message(interaction, notice="Address updated.")
        except asyncio.TimeoutError:
            await interaction.followup.send(
                "You took too long to respond. Please try again.", ephemeral=True
            )


class MapStyleSelect(ui.Select):
    def __init__(self, map_view):
        super().__init__(
            placeholder="Select Map Style",
            options=[
                SelectOption(label="Map", value="map"),
                SelectOption(label="Satellite", value="sat"),
                SelectOption(label="Hybrid", value="hyb"),
                SelectOption(label="Light", value="light"),
                SelectOption(label="Dark", value="dark"),
            ],
        )
        self.map_view = map_view

    async def callback(self, interaction: discord.Interaction):
        self.map_view.map_style = self.values[0]
        self.map_view.update_map()
        await self.map_view.refresh_message(interaction)


class MapSizeSelect(ui.Select):
    def __init__(self, map_view):
        super().__init__(
            placeholder="Select Map Size",
            options=[
                SelectOption(label="400x300", value="400,300"),
                SelectOption(label="800x600", value="800,600"),
                SelectOption(label="1200x900", value="1200,900"),
            ],
        )
        self.map_view = map_view

    async def callback(self, interaction: discord.Interaction):
        self.map_view.map_size = self.values[0]
        self.map_view.update_map()
        await self.map_view.refresh_message(interaction)


class Map(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="map",
        help="Shows a map of a location",
        usage="<location>",
        description="Shows a map of a location",
    )
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def map(self, ctx, *, location: str):
        coordinates = await MapView.fetch_coordinates(location)
        if coordinates is None:
            await ctx.send("Failed to retrieve coordinates for the location. Please try again.")
            return

        view = MapView(self.bot, location, ctx, coordinates[0], coordinates[1])
        await ctx.send(embed=view.build_embed(), view=view)
