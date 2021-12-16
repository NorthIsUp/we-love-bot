from typing import Union

import nextcord.abc as n_abc

# from discord_slash import SlashContext
from nextcord import Guild, Member, User
from nextcord.ext.commands import Context

from .lib.cog import Cog

ChannelT = Union[n_abc.GuildChannel, n_abc.PrivateChannel]

__all__ = [
    'Cog', 'Member', 'Guild', 'User', 'Context', ]  # 'SlashContext',]
