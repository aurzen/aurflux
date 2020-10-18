from __future__ import annotations
import os

import asyncio as aio
import logging as __logging

import typing as ty

import aiohttp
import aurcore as aur

import discord.errors
import discord.ext

from aurcore import EventRouter

from .config import Config
from .context import GuildMessageCtx, AuthAwareCtx, CommandCtx, MessageCtx
from loguru import logger

if ty.TYPE_CHECKING:
   import discord
   from .cog import FluxCog
   from aurcore import EventRouterHost

aur.log.setup()


class FluxEvent(aur.Event):
   def __init__(self, flux, __event_name, *args, **kwargs):
      super().__init__(__event_name, *args, **kwargs)
      self.flux: FluxClient = flux


class CommandEvent(FluxEvent):
   def __init__(self, flux: FluxClient, cmd_ctx: CommandCtx, cmd_args: ty.Optional[str], cmd_name: str):
      super().__init__(flux, f"flux:command:{cmd_name}")
      self.cmd_name = cmd_name
      self.cmd_ctx = cmd_ctx
      self.cmd_args = cmd_args


class FluxClient(discord.Client):

   def __init__(
         self,
         name: str,
         admin_id: int,
         parent_router: EventRouterHost = None,
         builtins=True,
         status: str = None,
         *args, **kwargs
   ):
      if status:
         # noinspection PyArgumentList
         self._activity = discord.Game(name=status)
         kwargs |= {"activity": self._activity}

      super(FluxClient, self).__init__(*args, **kwargs)

      self.router = EventRouter(name="flux", host=parent_router)
      self.CONFIG: Config = Config(admin_id=admin_id, name=name)

      self.cogs: ty.List[FluxCog] = []

      self.aiohttp_session = aiohttp.ClientSession()

      self.register_listeners()

      if builtins:
         from .cog.builtins import Builtins
         self.register_cog(Builtins)

   def dispatch(self, event, *args, **kwargs):
      super(FluxClient, self).dispatch(event, *args, **kwargs)
      aio.create_task(self.router.submit(FluxEvent(self, f":{event}", *args, **kwargs)))

   def register_cog(self, cog: ty.Type[FluxCog], name: str = None):
      c = cog(flux=self, name=name)
      logger.success(f"Registered {c}")
      self.cogs.append(c)

   async def startup(self, token, *args, **kwargs):


      await aio.gather(*[cog.startup() for cog in self.cogs])
      await self.start(token, *args, **kwargs)

   async def shutdown(self, *args, **kwargs):
      await self.logout()

   def register_listeners(self):
      @self.router.listen_for(":message")
      @aur.Eventful.decompose
      async def _(message: discord.Message):
         if not message.content or message.author is self.user:
            return
         if message.guild:
            ctx = GuildMessageCtx(flux=self, message=message)
         else:
            ctx = MessageCtx(flux=self, message=message)

         prefix = self.CONFIG.of(ctx)["prefix"]

         if not message.content.startswith(prefix):
            return
         raw_cmd_name, args, *_ = [*message.content.split(" ", 1), None]
         cmd_name = raw_cmd_name[len(prefix):]

         await self.router.submit(event=CommandEvent(flux=self, cmd_ctx=CommandCtx(self, ctx, ctx, [ctx]), cmd_name=cmd_name, cmd_args=args.strip() if args else None))

      @self.router.listen_for(":resume")
      async def _(_):
         logger.info("Resuming...")
         await self.change_presence(activity=self._activity)

      @self.router.listen_for(":ready")
      async def _(_):
         logger.success("Discord.py is ready")

      @self.router.listen_for(":guild_join")
      async def _(g: discord.Guild):
         logger.info(f"Joined guild: {g}")

      @self.router.listen_for(":guild_remove")
      async def _(g: discord.Guild):
         logger.info(f"Removed from guild: {g}")

   async def get_user_s(self, user_id: int):
      return self.get_user(user_id) or await self.fetch_user(user_id)

   async def get_member_s(self, g: discord.Guild, member_id: int):
      return g.get_member(member_id) or await g.fetch_member(member_id)
