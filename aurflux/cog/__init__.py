from __future__ import annotations

import abc
import typing as ty

import aurcore as aur
from loguru import logger

from .. import Command

if ty.TYPE_CHECKING:
   from .. import FluxClient
   from ..command import Response

class FluxCog:
   def __init__(self, flux: FluxClient, name: ty.Optional[str] = None):
      self.name = name or self.__class__.__name__
      self.flux = flux
      self.router = aur.EventRouter(name, host=self.flux.router)
      self.command_names = set()
      logger.info(f"[FluxCog] {self.__class__.__name__} loaded!")
      self.load()

   def _commandeer(self, name: ty.Optional[str] = None, parsed: bool = True, private: bool = False) -> ty.Callable[[ty.Callable[[...], ty.Awaitable[Response]]], Command]:
      def command_deco(func: ty.Callable[[...], ty.Awaitable[Response]]) -> Command:
         cmd = Command(flux=self, func=func, name=(name or func.__name__), parsed=parsed, private=private)
         if cmd.name in self.command_names:
            raise TypeError(f"Attempting to register command {cmd} when one with the same name already exists")
         self.command_names.add(cmd.name)
         self.router.listen_for(f"flux:command:{cmd.name}")(cmd.execute)
         return cmd

      return command_deco

   async def startup(self):
      # self.router.listen_for("flux")
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
