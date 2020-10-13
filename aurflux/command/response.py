from __future__ import annotations

__package__ = "aurflux.command"

import typing as ty

if ty.TYPE_CHECKING:
   from ..context import MessageCtx, CommandCtx
import aurcore as aur
import typing as ty
import asyncio as aio
import discord
from .. import utils
import datetime
from loguru import logger
import enum


class Status(enum.Enum):
   OK = utils.EMOJI.check
   ERROR = utils.EMOJI.x


class Response(aur.util.AutoRepr):
   __iter_done = False
   message: ty.Optional[discord.Message]
   delete_after: ty.Optional[float]

   def __init__(
         self,
         # ctx: Context,
         content: str = None,
         embed: discord.Embed = None,
         delete_after: ty.Union[float, datetime.timedelta] = None,
         status: ty.Literal["ok", "error"] = "ok",
         ping: bool = False,
         post_process: ty.Callable[[MessageCtx, discord.Message], ty.Coroutine] = None,
         trashable: bool = True,
   ):
      self.content = content
      self.embed = embed

      if isinstance(delete_after, datetime.timedelta):
         self.delete_after = delete_after.total_seconds()
      else:
         self.delete_after = delete_after

      self.status = status
      self.ping = ping
      self.post_process = post_process or (lambda *_: aio.sleep(0))
      self.trashable = trashable

   async def execute(self, ctx: CommandCtx):

      if self.status == "ok":
         await ctx.msg_ctx.message.add_reaction(utils.EMOJI.check)
      if self.status == "error":
         await ctx.msg_ctx.message.add_reaction(utils.EMOJI.x)

      if not self.content and not self.embed:
         return

      content = self.content if self.content else "" + (f"\n{ctx.author.mention}" if self.ping else "")
      if len(content) > 1900:
         content = f"Output too long, see:\n{await utils.haste(ctx.flux.aiohttp_session, content)}"

      message = await ctx.msg_ctx.dest.send(
         content=content,
         embed=self.embed,
         delete_after=self.delete_after
      )

      try:
         if self.trashable:
            await message.add_reaction(utils.EMOJI.trashcan)
            try:
               await ctx.msg_ctx.flux.router.wait_for(
                  ":reaction_add",
                  check=lambda ev: ev.args[0].message.id == message.id and ev.args[1] == ctx.msg_ctx.message.author,
                  timeout=20
               )
               await message.delete()
            except aio.exceptions.TimeoutError:
               await message.remove_reaction(emoji=utils.EMOJI.trashcan, member=ctx.msg_ctx.guild.me)

      except (discord.errors.NotFound, discord.errors.Forbidden) as e:
         logger.error(e)

      await self.post_process(ctx.msg_ctx, message)
