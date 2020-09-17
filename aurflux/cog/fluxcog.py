from __future__ import annotations

import abc
import typing as ty

import aurcore as aur
from loguru import logger

from ..command import Command

if ty.TYPE_CHECKING:
   from .. import FluxClient
   from ..context import MessageContext
   from ..command import Response
   from ..types_ import *


class FluxCog:
   def __init__(self, flux: FluxClient, name: ty.Optional[str] = None):
      self.name = name or self.__class__.__name__
      self.flux = flux
      self.router = aur.EventRouter(self.name, host=self.flux.router.host)
      self.command_names: ty.Set[str] = set()
      logger.info(f"{self.name} loaded! Under {self.router}")
      self.load()

   def _commandeer(self, name: ty.Optional[str] = None, parsed: bool = True, private: bool = False) -> ty.Callable[[CommandFunc], Command]:
      def command_deco(func: CommandFunc) -> Command:
         cmd = Command(flux=self.flux, func=func, name=(name or func.__name__), parsed=parsed, private=private)
         if cmd.name in self.command_names:
            raise TypeError(f"Attempting to register command {cmd} when one with the same name already exists")
         self.command_names.add(cmd.name)
         self.router.listen_for(f"flux:command:{cmd.name}")(cmd.execute)
         logger.trace(f"Command {cmd} registered under flux:command:{cmd.name}")
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
