from typing import Union

import discord.abc as d_abc
from discord_slash import SlashContext
from nextcord import Guild, Member, User
from nextcord.ext.commands import Context

from .lib.cog import Cog

ChannelT = Union[d_abc.GuildChannel, d_abc.PrivateChannel]

__all__ = ['Cog', 'Member', 'Guild', 'User', 'SlashContext', 'Context']
