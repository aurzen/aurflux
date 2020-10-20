from __future__ import annotations
import typing as ty
import abc
import aurcore as aur
from loguru import logger
from ..auth import AuthAware, Record
from ..command import Command

if ty.TYPE_CHECKING:
   from .. import FluxClient
   from ..context import GuildMessageCtx
   from ..types_ import *


class FluxCog(AuthAware, metaclass=abc.ABCMeta):
   def __init__(self, flux: FluxClient, name: ty.Optional[str] = None):
      self.name = name or self.__class__.__name__
      self.flux = flux
      self.router = aur.EventRouter(self.name, host=self.flux.router.host)
      self.commands: ty.List[Command] = []
      logger.success(f"{self} registered under {self.router}")
      self.load()

   def _commandeer(
         self,
         name: ty.Optional[str] = None,
         decompose: bool = False,
         allow_dm=False,
         default_auths: ty.List[Record] = (),
         override_auths: ty.List[Record] = (),
   ) -> ty.Callable[[CommandFunc], Command]:
      def command_deco(func: CommandFunc) -> Command:
         cmd = Command(
            flux=self.flux,
            cog=self,
            func=func,
            name=(name or func.__name__),
            decompose=decompose,
            allow_dm=allow_dm,
            default_auths=default_auths,
            override_auths=override_auths,
         )
         if cmd.name in [c.name for c in self.commands]:
            raise TypeError(f"Attempting to register command {cmd} when one with the same name already exists")
         self.commands.append(cmd)
         self.router.listen_for(f"flux:command:{cmd.name}")(cmd.execute)

         logger.success(f"{cmd} registered under flux:command:{cmd.name}")
         return cmd

      return command_deco

   async def startup(self):
      pass

   @property
   def auth_id(self):
      return f"{self.name}"

   def teardown(self):
      logger.info(f"Cog {self.name} detaching from {self.router}")

      self.router.detach()

   @property
   def default_auths(self) -> ty.List[Record]:
      return [Record.deny_all()]

   @property
   def override_auths(self) -> ty.List[Record]:
      return []

   @abc.abstractmethod
   def load(self) -> None: ...

   def __str__(self) -> str:
      return f"<Cog {self.name}>"
