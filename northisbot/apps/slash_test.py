import discord
from discord.ext import commands
from discord_slash import SlashContext, cog_ext


class Slash(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @cog_ext.cog_slash(name='test')
    async def _test(self, ctx: SlashContext):
        embed = discord.Embed(title='embed test')
        await ctx.send(content='test', embeds=[embed])
