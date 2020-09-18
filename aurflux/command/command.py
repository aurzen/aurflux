from __future__ import annotations

import functools as fnt
import traceback
import typing as ty

import aurcore as aur

from .response import Response
from .. import errors
from ..auth import Auth, AuthAware

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
         default_auths: ty.List[Record],
         provide_auth,
   ):
      self.func = func
      self.flux = flux
      self.cog = cog
      self.name = name
      self.doc = inspect.getdoc(func)
      self.parsed = False  # todo: argparser
      self.decompose = decompose

      # self.checks: ty.List[ty.Callable[[GuildMessageContext], ty.Union[bool, ty.Awaitable[bool]]]] = []
      self.builtin = False
      # self.argparser: ty.Optional[argh.ArgumentParser] = None
      self.default_auths_: ty.List[Record] = default_auths
      self.provide_auth = provide_auth
      func_doc = inspect.getdoc(self.func)
      if not func_doc:
         raise RuntimeError(f"{self.func} lacks a docstring!")
      try:
         short_usage, long_usage, params, *_ = func_doc.split("==")
      except ValueError as e:
         raise ValueError(f"{e} : {self.name}")
      self.short_usage = short_usage.strip()
      self.description = long_usage.strip()
      self.param_usage: ty.List[ty.List[str]] = [param_line.strip().split(":") for param_line in params.split(";") if param_line.strip()]
      # else:
      #    self.short_usage: str = func_doc.split("\n")[0]
      #    raw_doc = func_doc[func_doc.index("\n"):func_doc.index(":param")].strip()
      #
      #    self.long_usage: ty.List[ty.List[str, str]] = [doc_line.split(":") for doc_line in raw_doc.split("\n")]

   async def execute(self, ev: CommandEvent) -> None:
      msg_ctx = ev.msg_ctx
      auth_ctx = ev.auth_ctx
      cmd_args = ev.cmd_args

      # if (self.argparser is not None) ^ self.parsed:
      #    raise RuntimeError(f"Parsed command {self} has not been decorated with Argh")

      if not Auth.accepts(auth_ctx, self):
         await Response(content="Forbidden", errored=True).execute(msg_ctx)
         return

      try:
         auths = {"auth_ctx": auth_ctx} if self.provide_auth else {}
         with msg_ctx.channel.typing():
            # if self.parsed:
            # assert self.argparser is not None  # typing
            # res = self.func(msg_ctx, **auths, **self.argparser.parse_args(cmd_args.split(" ") if cmd_args else []).__dict__)
            # else:
            if self.decompose:
               res = self.func(msg_ctx, *ev.args, **ev.kwargs, **auths)
            else:
               res = self.func(msg_ctx, cmd_args, **auths)

         async for resp in aur.util.AwaitableAiter(res):
            await resp.execute(msg_ctx)
      except errors.CommandError as e:
         info_message = f"{e}"
         # if self.argparser:
         #    info_message += f"\n```{self.argparser.format_help()}```"
         await Response(content=info_message, errored=True).execute(msg_ctx)
      except errors.CommandInfo as e:
         info_message = f"{e}"
         # if self.argparser:
         #    info_message += f"\n```{self.argparser.format_help()}```"
         await Response(content=info_message).execute(msg_ctx)
      except Exception as e:
         await Response(content=f"```Unexpected Exception:\n{str(e)}\n```", errored=True).execute(msg_ctx)
         print(traceback.format_exc())

   @property
   def auth_id(self):
      return f"{self.cog.name}:{self.name}"

   @property
   def default_auths(self):
      return self.default_auths_

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
