# import nextcord

# from welovebot.prelude import *


# class Slash(Cog):
#     def __init__(self, bot):
#         self.bot = bot

#     @Cog.slash(name='test')
#     async def _test(self, ctx: SlashContext):
#         embed = nextcord.Embed(title='embed test')
#         await ctx.send(content='test', embeds=[embed])

#     @Cog.slash(name='test2')
#     async def _test(self, ctx: SlashContext):
#         embed = nextcord.Embed(title='embed test')
#         await ctx.send(content='test2', embeds=[embed])

#     @Cog.slash_subcommand(base='test-group', name='echo')
#     async def ping(self, ctx: SlashContext, text: str) -> None:
#         await ctx.send(content=text)

#     @Cog.command()
#     async def test3(self, ctx, *, member: nextcord.Member = None):
#         await ctx.send('hello there')
