from __future__ import annotations

import functools as fnt
import traceback
import typing as ty

import aurcore as aur

from .response import Response
from .. import errors
from ..auth import Auth, AuthAware
from loguru import logger
from ..context import GuildMessageCtx

if ty.TYPE_CHECKING:
   from ..types_ import *
   from . import argh
   from .. import FluxClient
   from ..cog import FluxCog
   from ..auth import Record
   from ..flux import CommandEvent
import typing as ty
import asyncio as aio
import inspect


def _coroify(func):  # todo: move to aurcore
   if aio.iscoroutinefunction(func):
      return func
   fnt.wraps(func)

   async def __async_wrapper(*args, **kwargs):
      func(*args, **kwargs)

   return __async_wrapper


class Command(aur.util.AutoRepr, AuthAware):

   def __init__(
         self,
         flux: FluxClient,
         cog: FluxCog,
         func: CommandFunc,
         name: str,
         parsed: bool,
         decompose: bool,
         allow_dm: bool,
         default_auths: ty.List[Record],
         override_auths: ty.List[Record],
   ):
      self.func = func
      self.flux = flux
      self.cog = cog
      self.name = name
      self.doc = inspect.getdoc(func)
      self.parsed = False  # todo: argparser
      self.decompose = decompose
      self.allow_dm = allow_dm
      # self.checks: ty.List[ty.Callable[[GuildMessageContext], ty.Union[bool, ty.Awaitable[bool]]]] = []
      self.builtin = False
      # self.argparser: ty.Optional[argh.ArgumentParser] = None
      self.default_auths_: ty.List[Record] = default_auths
      self.override_auths_: ty.List[Record] = override_auths

      func_doc = inspect.getdoc(self.func)
      if not func_doc:
         raise RuntimeError(f"{self.func} lacks a docstring!")
      try:
         short_usage, long_usage, params, *_ = func_doc.split("==")
      except ValueError as e:
         raise ValueError(f"{e} : {self.name}")

      self.short_usage = short_usage.strip()
      self.description = long_usage.strip()

      def combine_params(acc: ty.List[ty.Tuple[str, str]], x: str):
         if acc and acc[-1][1].endswith("\\"):
            name, detail = acc.pop()
            acc.append((name, detail.removesuffix("\\").strip() + "\n" + x))
         else:
            name, detail = x.split(":", 1)
            acc.append((name, detail))
         return acc

      try:
         self.param_usage: ty.List[ty.Tuple[str, str]] = fnt.reduce(combine_params, [x for x in params.strip().split("\n") if x], [])
      except ValueError as e:
         raise ValueError(f"Param Parse error {e} in {self.name}")

   async def execute(self, ev: CommandEvent) -> None:
      cmd_ctx = ev.cmd_ctx

      if not isinstance(cmd_ctx.msg_ctx, GuildMessageCtx) and not self.allow_dm:
         return await Response(content="Cannot be used in DMs", errored=True).execute(cmd_ctx)

      logger.trace(f"Command {self} executing in {cmd_ctx.msg_ctx}")

      if not Auth.accepts_all(cmd_ctx.auth_ctxs, self):
         return await Response(content="Forbidden", errored=True).execute(cmd_ctx)

      try:
         with cmd_ctx.msg_ctx.channel.typing():
            if self.decompose:
               res = self.func(cmd_ctx, *ev.args, **ev.kwargs)
            else:
               res = self.func(cmd_ctx, ev.cmd_args)

         async for resp in aur.util.AwaitableAiter(res):
            await resp.execute(cmd_ctx)
      except errors.CommandError as e:
         info_message = f"{e}"
         await Response(content=info_message, errored=True).execute(cmd_ctx)
      except errors.CommandInfo as e:
         info_message = f"{e}"
         await Response(content=info_message).execute(cmd_ctx)
      except Exception as e:
         print(traceback.format_exc())
         await Response(content=f"```Unexpected Exception:\n{str(e)}\n```", errored=True).execute(cmd_ctx)
         logger.error(traceback.format_exc())

   @property
   def auth_id(self):
      return f"{self.cog.name}:{self.name}"

   @property
   def default_auths(self):
      return self.default_auths_

   @property
   def override_auths(self):
      return self.default_auths_

   def __str__(self):
      return f"Command {self.name} in {self.cog}: {self.func}"
# class CommandCheck:
#    CheckPredicate: ty.TypeAlias = ty.Callable[[GuildMessageContext], ty.Awaitable[bool]]
#    CommandTransformDeco: ty.TypeAlias = ty.Callable[[Command], Command]
#
#    @staticmethod
#    def check(*predicates: CheckPredicate) -> CommandTransformDeco:
#       def add_checks_deco(command: Command) -> Command:
#          command.checks.extend(predicates)
#          return command
#
#       return add_checks_deco
#
#    @staticmethod
#    def or_(*predicates: CheckPredicate) -> CheckPredicate:
#       async def orred_predicate(ctx: GuildMessageContext) -> bool:
#          return any(await predicate(ctx) for predicate in predicates)
#
#       return orred_predicate
#
#    @staticmethod
#    def and_(*predicates: CheckPredicate) -> CheckPredicate:
#       async def anded_predicate(ctx: GuildMessageContext) -> bool:
#          return all(await predicate(ctx) for predicate in predicates)
#
#       return anded_predicate
#
#    @staticmethod
#    def whitelist() -> CheckPredicate:
#       async def whitelist_predicate(ctx: GuildMessageContext) -> bool:
#          if ctx.config is None:
#             raise RuntimeError(f"Config has not been initialized for ctx {ctx} in cmd {Command}")
#          if not any(identifier in ctx.config["whitelist"] for identifier in ctx.auth_identifiers):
#             raise errors.NotWhitelisted()
#          return True
#
#       return whitelist_predicate
#
#    @staticmethod
#    def has_permissions(
#          required_perms: discord.Permissions
#    ) -> CheckPredicate:
#       async def perm_predicate(ctx):
#          ctx_perms: discord.Permissions = ctx.channel.permissions_for(ctx.author)
#
#          missing = [perm for perm, value in required_perms if getattr(ctx_perms, perm) != value]
#
#          if not missing:
#             return True
#
#          raise errors.UserMissingPermissions(missing)
#
#       return perm_predicate
#
#    @staticmethod
#    def bot_has_permissions(
#          required_perms: discord.Permissions
#    ) -> CheckPredicate:
#
#       async def perm_predicate(ctx: GuildMessageContext):
#          ctx_perms: discord.Permissions = ctx.channel.permissions_for(ctx.guild.me)
#
#          missing = [perm for perm, value in required_perms if getattr(ctx_perms, perm) != value]
#
#          if not missing:
#             return True
#
#          raise errors.BotMissingPermissions(missing)
#
#       return perm_predicate
