from typing import Union

import discord.abc as d_abc
from discord import Guild, Member, User
from discord.ext.commands import Context
from discord_slash import SlashContext

from .lib.cog import Cog

ChannelT = Union[d_abc.GuildChannel, d_abc.PrivateChannel]

__all__ = ['Cog', 'Member', 'Guild', 'User', 'SlashContext', 'Context']
