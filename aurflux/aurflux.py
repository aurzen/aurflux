from __future__ import annotations

import importlib

import discord.errors
import traceback
import abc
from .command import Command, CommandCheck
from .config import Config
from .builtins import Builtins
from .command.context import MessageContext
from .errors import *
from aurflux.command.response import Response
import aiohttp
from . import utils
import asyncio as aio
import re
import discord.ext
import aurcore as aur
from aurcore.event import EventRouter
import inspect
from loguru import logger
import logging as __logging
import typing as ty

__logging.getLogger("discord.client").addFilter(lambda r: r.getMessage() != "PyNaCl is not installed, voice will NOT be supported")

if ty.TYPE_CHECKING:
   import discord


class AurfluxEvent(aur.Event):
   def __init__(self, aurflux, __event_name, *args, **kwargs):
      super().__init__(__event_name, *args, **kwargs)
      self.bot: Aurflux = aurflux


class AurfluxCog:
   def __init__(self, aurflux: Aurflux, name: ty.Optional[str] = None):
      self.name = name or self.__class__.__name__
      self.aurflux = aurflux
      self.router = EventRouter(name, host=self.aurflux.router)
      self.command_names = set()
      logger.info(f"[AurfluxCog] {self.__class__.__name__} loaded!")
      self.load()

   def _commandeer(self, name: ty.Optional[str] = None, parsed: bool = True, private: bool = False) -> ty.Callable[[ty.Callable[[...], ty.Awaitable[Response]]], Command]:
      def command_deco(func: ty.Callable[[...], ty.Awaitable[Response]]) -> Command:
         cmd = Command(aurflux=self, func=func, name=(name or func.__name__), parsed=parsed, private=private)
         if cmd.name in self.command_names:
            raise TypeError(f"Attempting to register command {cmd} when one with the same name already exists")
         self.command_names.add(cmd.name)
         self.router.listen_for(f"aurflux:command:{cmd.name}")(cmd.execute)
         return cmd

      return command_deco

   async def startup(self):
      # self.router.listen_for("aurflux")
      pass

   # def register(self, cog_member: ty.Union[Command, EventMuxer]):
   #    print(f"Cog registering!")
   #    print(cog_member)
   # if isinstance(cog_member, Command):
   #     self.commands.add(cog_member)
   # else:
   #     self.listeners[cog_member.name] = cog_member

   def teardown(self):
      self.router.detach()

   @abc.abstractmethod
   def load(self):
      ...


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
         parent_router: EventRouter = None,
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
         self.register_cog(Builtins)
      self.router.endpoint(":ready")(lambda ev: print("Discord.py is ready!"))


   def dispatch(self, event, *args, **kwargs):
      super(Aurflux, self).dispatch(event, *args, **kwargs)
      aio.create_task(self.router.submit(AurfluxEvent(self, f":{event}", *args, **kwargs)))

   def register_cog(self, cog: ty.Type[AurfluxCog], name: str = None):
      self.cogs.append(cog(self, name=name))

   async def startup(self, token, *args, **kwargs):
      await aio.gather(*[cog.startup() for cog in self.cogs])
      await self.start(token, *args, **kwargs)

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
