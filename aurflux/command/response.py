from __future__ import annotations

__package__ = "aurflux.command"

import typing as ty

if ty.TYPE_CHECKING:
   from .. import context
   from ..context import MessageCtx, CommandCtx
import aurcore as aur
import typing as ty
import asyncio as aio
import discord
from .. import utils
import datetime


class Message(aur.util.AutoRepr):
   pass

   def __init__(self, message_ctx: context.MessageCtx, author_ctx: context.GuildMessageCtx):
      pass


class Response(aur.util.AutoRepr):
   __iter_done = False
   message: ty.Optional[discord.Message]

   def __init__(
         self,
         # ctx: Context,
         content: str = None,
         embed: discord.Embed = None,
         delete_after: ty.Union[float, datetime.timedelta] = None,
         errored: bool = False,
         ping: bool = False,
         post_process: ty.Callable[[MessageCtx, discord.Message], ty.Coroutine] = None,
         trashable: bool = True,
   ):
      self.content = content
      self.embed = embed
      self.delete_after: ty.Optional[datetime.timedelta] = delete_after if (isinstance(delete_after, datetime.timedelta) or not delete_after) else datetime.timedelta(
         seconds=delete_after)
      self.errored = errored
      self.ping = ping
      self.post_process = post_process or (lambda *_: aio.sleep(0))
      self.trashable = trashable

   async def execute(self, ctx: CommandCtx):
      if self.content or self.embed:
         content = self.content if self.content else "" + (ctx.author.mention if self.ping else "")
         if len(content) > 1900:
            content = utils.haste(ctx.flux.aiohttp_session, content)
         message = await ctx.msg_ctx.channel.send(
            content=content,
            embed=self.embed,
            delete_after=self.delete_after.seconds if self.delete_after else None
         )
         self.message = message

         await self.post_process(ctx.msg_ctx, message)
      try:
         await ctx.msg_ctx.message.add_reaction(utils.EMOJI.trashcan if self.errored else utils.EMOJI.check)

         if self.trashable:
            await self.message.add_reaction(utils.EMOJI.trashcan)
            try:
               await ctx.msg_ctx.flux.router.wait_for(":reaction_add",
                                                      check=lambda ev: ev.args[0].message.id == self.message.id and ev.args[1] == ctx.msg_ctx.message.author,
                                                      timeout=15)
               await self.message.delete()
            except aio.exceptions.TimeoutError:
               await self.message.remove_reaction(emoji=utils.EMOJI.trashcan, member=ctx.msg_ctx.guild.me)
      except (discord.errors.NotFound, discord.errors.Forbidden) as e:
         print(e)
         pass

