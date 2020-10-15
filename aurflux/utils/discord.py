from __future__ import annotations
import typing as ty
from ..errors import BotMissingPermissions

if ty.TYPE_CHECKING:
   import discord


async def get_or_fetch_member(g: discord.Guild, m_id: int):
   return g.get_member(m_id) or await g.fetch_member(m_id)


def perm_check(c: discord.TextChannel, need:discord.Permissions):
   if not need <= (p := c.permissions_for(c.guild.me)):
      raise BotMissingPermissions(need, p)
