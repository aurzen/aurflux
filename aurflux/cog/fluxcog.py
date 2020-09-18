from __future__ import annotations

import typing as ty
import abc
import aurcore as aur
from loguru import logger
from ..auth import AuthAware, Record
from ..command import Command

if ty.TYPE_CHECKING:
   from .. import FluxClient
   from ..context import GuildMessageContext
   from ..command import Response
   from ..types_ import *
   from ..auth import Record


class FluxCog(AuthAware):
   def __init__(self, flux: FluxClient, name: ty.Optional[str] = None):
      self.name = name or self.__class__.__name__
      self.flux = flux
      self.router = aur.EventRouter(self.name, host=self.flux.router.host)
      self.commands: ty.List[Command] = []
      logger.info(f"{self.name} loaded! Under {self.router}")
      self.load()

   def _commandeer(self, name: ty.Optional[str] = None, parsed: bool = True, decompose: bool = False, default_auths: ty.List[Record] = None, provide_auth=False) -> ty.Callable[
      [CommandFunc], Command]:
      # default_auths = default_auths or [Record.deny_all()]

      def command_deco(func: CommandFunc) -> Command:
         cmd = Command(flux=self.flux, cog=self, func=func, name=(name or func.__name__), parsed=parsed, decompose=decompose, default_auths=default_auths,
                       provide_auth=provide_auth)
         if cmd.name in [c.name for c in self.commands]:
            raise TypeError(f"Attempting to register command {cmd} when one with the same name already exists")
         self.commands.append(cmd)
         self.router.listen_for(f"flux:command:{cmd.name}")(cmd.execute)
         logger.trace(f"Command {cmd} registered under flux:command:{cmd.name}")
         return cmd

      return command_deco

   async def startup(self):
      # self.router.listen_for("flux")
      pass

   @property
   def auth_id(self):
      return f"{self.name}"

   # def register(self, cog_member: ty.Union[Command, EventMuxer]):
   #    print(f"Cog registering!")
   #    print(cog_member)
   # if isinstance(cog_member, Command):
   #     self.commands.add(cog_member)
   # else:
   #     self.listeners[cog_member.name] = cog_member

   def teardown(self):
      self.router.detach()

   @property
   def default_auths(self) -> ty.List[Record]:
      return [Record.deny_all()]

   @abc.abstractmethod
   def load(self): ...
