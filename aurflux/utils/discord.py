from __future__ import annotations
import typing as ty
from ..errors import BotMissingPermissions

if ty.TYPE_CHECKING:
   import discord


def perm_check(c: discord.TextChannel, need:discord.Permissions):
   print(c)
   print(need)
   print(c.permissions_for(c.guild.me))

   if not need <= (p := c.permissions_for(c.guild.me)):
      raise BotMissingPermissions(need, p)
