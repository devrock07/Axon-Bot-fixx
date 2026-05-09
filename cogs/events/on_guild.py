from discord.ext import commands
from core import axon, Cog
import discord
import logging
from discord.ui import View, Button, Select

logging.basicConfig(
    level=logging.INFO,
    format="\x1b[38;5;197m[\x1b[0m%(asctime)s\x1b[38;5;197m]\x1b[0m -> \x1b[38;5;197m%(message)s\x1b[0m",
    datefmt="%H:%M:%S",
)

class Guild(Cog):
    def __init__(self, client: axon):
        self.client = client

    async def safe_send(self, channel, *args, **kwargs):
        if channel is None:
            return False

        guild = getattr(channel, "guild", None)
        if guild is not None and guild.me is not None:
            permissions = channel.permissions_for(guild.me)
            if not permissions.view_channel or not permissions.send_messages:
                return False

        try:
            await channel.send(*args, **kwargs)
            return True
        except (discord.Forbidden, discord.NotFound):
            return False
        except discord.HTTPException as e:
            logging.error(f"Failed to send guild event message: {e}")
            return False

    @commands.Cog.listener(name="on_guild_join")
    async def on_guild_add(self, guild):
        try:
            
            try:
                rope = [inv for inv in await guild.invites() if inv.max_age == 0 and inv.max_uses == 0]
            except discord.Forbidden:
                rope = []
            ch = 1327829068644876391  
            me = self.client.get_channel(ch)
            if me is None:
                logging.warning(f"Guild join log channel with ID {ch} not found or not cached.")

            channels = len(set(self.client.get_all_channels()))
            embed = discord.Embed(title=f"{guild.name}'s Information", color=0x000000)
            
            embed.set_author(name="Guild Joined")
            embed.set_footer(text=f"Added in {guild.name}")

            embed.add_field(
                name="**__About__**",
                value=f"**Name : ** {guild.name}\n**ID :** {guild.id}\n**Owner <:owner:1329041011984433185> :** {guild.owner} (<@{guild.owner_id}>)\n**Created At : **{guild.created_at.month}/{guild.created_at.day}/{guild.created_at.year}\n**Members :** {len(guild.members)}",
                inline=False
            )
            embed.add_field(
                name="**__Description__**",
                value=f"""{guild.description}""",
                inline=False
            )
            embed.add_field(
                name="**__Members__**",
                value=f"""<:riverse_fun:1327829569264160870> Members : {len(guild.members)}\n <:user:1329379728603353108> Humans : {len(list(filter(lambda m: not m.bot, guild.members)))}\n<:icons_bot:1327829370881966092> Bots : {len(list(filter(lambda m: m.bot, guild.members)))}
                """,
                inline=False
            )
            embed.add_field(
                name="**__Channels__**",
                value=f"""
Categories : {len(guild.categories)}
Text Channels : {len(guild.text_channels)}
Voice Channels : {len(guild.voice_channels)}
Threads : {len(guild.threads)}
                """,
                inline=False
            )  
            embed.add_field(name="__Bot Stats:__", 
            value=f"Servers: `{len(self.client.guilds)}`\nUsers: `{len(self.client.users)}`\nChannels: `{channels}`", inline=False)  

            if guild.icon is not None:
                embed.set_thumbnail(url=guild.icon.url)

            embed.timestamp = discord.utils.utcnow()
            await self.safe_send(me, f"{rope[0]}" if rope else "No Pre-Made Invite Found", embed=embed)

            if not guild.chunked:
                await guild.chunk()

            embed = discord.Embed(description="<:iconArrowRight:1327829310962401331> Prefix For This Server is `>`\n<:iconArrowRight:1327829310962401331> Get Started with `>help`\n<:iconArrowRight:1327829310962401331> For detailed guides, FAQ & information, visit our **[India Support Server](https://discord.gg/codexdev)**",
    color=0xff0000)
            embed.set_author(name="Thanks for adding me!", icon_url=guild.me.display_avatar.url)
            embed.set_footer(text="Powered by India Server™",)
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)

            support = Button(label='Support',
                             style=discord.ButtonStyle.link,
                    url=f'https://dsc.gg/codexdev')
            
            view = View()
            view.add_item(support)
            channel = discord.utils.get(guild.text_channels, name="general")
            if channel is None or not channel.permissions_for(guild.me).send_messages:
                channels = [
                    channel for channel in guild.text_channels
                    if channel.permissions_for(guild.me).view_channel
                    and channel.permissions_for(guild.me).send_messages
                ]
                channel = channels[0] if channels else None

            if not await self.safe_send(channel, embed=embed, view=view):
                logging.warning(f"No accessible channel found for guild join message in guild: {guild.name}")

        except Exception as e:
            logging.error(f"Error in on_guild_join: {e}")

    @commands.Cog.listener(name="on_guild_remove")
    async def on_guild_remove(self, guild):
        try:
            ch = 1271825683672203294  
            idk = self.client.get_channel(ch)
            if idk is None:
                logging.warning(f"Guild remove log channel with ID {ch} not found or not cached.")
                return

            channels = len(set(self.client.get_all_channels()))
            embed = discord.Embed(title=f"{guild.name}'s Information", color=0x000000)
        
            embed.set_author(name="Guild Removed")
            embed.set_footer(text=f"{guild.name}")

            embed.add_field(
                name="**__About__**",
                value=f"**Name : ** {guild.name}\n**ID :** {guild.id}\n**Owner <:axon_owner:1228227536207740989> :** {guild.owner} (<@{guild.owner_id}>)\n**Created At : **{guild.created_at.month}/{guild.created_at.day}/{guild.created_at.year}\n**Members :** {len(guild.members)}",
                inline=False
            )
            embed.add_field(
                name="**__Description__**",
                value=f"""{guild.description}""",
                inline=False
            )
            
                
            embed.add_field(
                name="**__Members__**",
                value=f"""
Members : {len(guild.members)}
Humans : {len(list(filter(lambda m: not m.bot, guild.members)))}
Bots : {len(list(filter(lambda m: m.bot, guild.members)))}
                """,
                inline=False
            )
            embed.add_field(
                name="**__Channels__**",
                value=f"""
Categories : {len(guild.categories)}
Text Channels : {len(guild.text_channels)}
Voice Channels : {len(guild.voice_channels)}
Threads : {len(guild.threads)}
                """,
                inline=False
            )   
            embed.add_field(name="__Bot Stats:__", 
            value=f"Servers: `{len(self.client.guilds)}`\nUsers: `{len(self.client.users)}`\nChannels: `{channels}`", inline=False)

            if guild.icon is not None:
                embed.set_thumbnail(url=guild.icon.url)

            embed.timestamp = discord.utils.utcnow()
            await self.safe_send(idk, embed=embed)
        except Exception as e:
            logging.error(f"Error in on_guild_remove: {e}")

#client.add_cog(Guild(client))
