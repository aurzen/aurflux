from __future__ import annotations

import asyncio as aio
import logging as __logging
from loguru import logger
import typing as ty

import aiohttp
import aurcore as aur
import discord.errors
import discord.ext

from aurcore import EventRouter

from .command import Command
from .config import Config
from .context import GuildMessageContext

__logging.getLogger("discord.client").addFilter(lambda r: r.getMessage() != "PyNaCl is not installed, voice will NOT be supported")

if ty.TYPE_CHECKING:
   import discord
   from .cog import FluxCog
   from aurcore import EventRouterHost


class FluxEvent(aur.Event):
   def __init__(self, flux, __event_name, *args, **kwargs):
      super().__init__(__event_name, *args, **kwargs)
      self.bot: FluxClient = flux


class FluxClient(discord.Client):

   def __init__(
         self,
         name: str,
         admin_id: int,
         parent_router: EventRouterHost = None,
         builtins=True,
         *args, **kwargs
   ):
      super(FluxClient, self).__init__(*args, **kwargs)
      self.router = EventRouter(name="flux", host=parent_router)
      self.CONFIG: Config = Config(name)

      self.commands: ty.Dict[str, Command] = {}
      self.admin_id = admin_id
      self.cogs: ty.List[FluxCog] = []

      self.aiohttp_session = aiohttp.ClientSession()

      self.register_command_listener()
      if builtins:
         from .cog.builtins import Builtins
         self.register_cog(Builtins)

   def dispatch(self, event, *args, **kwargs):
      super(FluxClient, self).dispatch(event, *args, **kwargs)
      aio.create_task(self.router.submit(FluxEvent(self, f":{event}", *args, **kwargs)))

   def register_cog(self, cog: ty.Type[FluxCog], name: str = None):
      self.cogs.append(cog(flux=self, name=name))

   async def startup(self, token, *args, **kwargs):
      async def r():
         await self.router.wait_for(":ready", check=lambda x: True)
         print("Discord.py ready!")

      aio.create_task(r())

      await aio.gather(*[cog.startup() for cog in self.cogs])
      await self.start(token, *args, **kwargs)

   async def shutdown(self, *args, **kwargs):
      await self.logout()

   def register_command_listener(self):
      @self.router.listen_for(":message")
      @aur.Eventful.decompose
      async def _(message: discord.Message):
         if not message.content or message.author is self.user:
            return
         ctx = GuildMessageContext(flux=self, message=message)

         prefix = self.CONFIG.of(ctx)["prefix"]

         if not message.content.startswith(prefix):
            return
         cmd = message.content.split(" ", 1)[0][len(prefix):]
         logger.info(f"Command recognized! flux:command:{cmd}")

         # print(aur.Event(f"flux:command:{cmd}", ctx=ctx))
         await self.router.submit(event=aur.Event(f"flux:command:{cmd}", ctx=ctx))
