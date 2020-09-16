from __future__ import annotations

import asyncio as aio
import inspect
import logging as __logging
import typing as ty
import aiohttp
import aurcore as aur
import discord.errors
import discord.ext
from aurcore import EventRouter

from .context import MessageContext
from .config import Config

__logging.getLogger("discord.client").addFilter(lambda r: r.getMessage() != "PyNaCl is not installed, voice will NOT be supported")

if ty.TYPE_CHECKING:
   import discord
   from .cog import AurfluxCog
   from aurcore import EventRouterHost

class AurfluxEvent(aur.Event):
   def __init__(self, aurflux, __event_name, *args, **kwargs):
      super().__init__(__event_name, *args, **kwargs)
      self.bot: Aurflux = aurflux


def ms(key):
   try:
      return dict(inspect.getmembers(
         inspect.stack()[-1][0]))["f_globals"][key]
   except KeyError:
      for i in inspect.stack()[::-1]:
         try:
            return dict(inspect.getmembers(i[0]))["f_locals"][key]
         except KeyError:
            pass
         try:
            return dict(inspect.getmembers(i[0]))["f_globals"][key]
         except KeyError:
            pass
   raise KeyError("Could not find key " + key)


class Aurflux(discord.Client):

   def __init__(
         self,
         name: str,
         admin_id: int,
         parent_router: EventRouterHost = None,
         builtins=True,
         *args, **kwargs
   ):
      super(Aurflux, self).__init__(*args, **kwargs)
      self.router = EventRouter(name="aurflux", host=parent_router)
      self.CONFIG: Config = Config(name)

      self.commands: ty.Dict[str, Command] = {}
      self.admin_id = admin_id
      self.cogs: ty.List[AurfluxCog] = []

      self.aiohttp_session = aiohttp.ClientSession()

      self.register_command_listener()
      if builtins:
         from .cog.builtins import Builtins
         self.register_cog(Builtins)




   def dispatch(self, event, *args, **kwargs):
      super(Aurflux, self).dispatch(event, *args, **kwargs)
      aio.create_task(self.router.submit(AurfluxEvent(self, f":{event}", *args, **kwargs)))

   def register_cog(self, cog: ty.Type[AurfluxCog], name: str = None):
      self.cogs.append(cog(self, name=name))

   async def startup(self, token, *args, **kwargs):
      async def r():
         await self.router.wait_for(":ready", check=lambda x: True)
         print("Discord.py ready!")
      aio.create_task(r())

      await aio.gather(*[cog.startup() for cog in self.cogs])
      await self.start(token, *args, **kwargs)
      print("Started")

   async def shutdown(self, *args, **kwargs):
      await self.logout()


   def register_command_listener(self):
      @self.router.listen_for(":message", decompose=True)
      async def _(message: discord.Message):
         if not message.content or message.author is self.user:
            return
         ctx = MessageContext(bot=self, message=message)

         prefix = self.CONFIG.of(ctx)["prefix"]

         if not message.content.startswith(prefix):
            return

         cmd = message.content.split(" ", 1)[0][len(prefix):]
         await self.router.submit(event=aur.Event(f":command:{cmd}"))
