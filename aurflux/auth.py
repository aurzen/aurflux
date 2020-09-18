from __future__ import annotations

import typing as ty
import dataclasses as dtcs
import abc
import itertools as itt
import discord

if ty.TYPE_CHECKING:
   from cog import FluxCog
   # from command import
   from .context import ConfigAware, GuildMessageContext, AuthAwareContext
   from .command import Command


@dtcs.dataclass
class AuthList:
   user: int = None
   roles: ty.List[int] = dtcs.field(default_factory=list)
   permissions: ty.Optional[discord.Permissions] = None


@dtcs.dataclass(frozen=True)
class Record:
   # topic : str
   rule: ty.Literal["ALLOW", "DENY"]
   target_id: int
   target_type: ty.Literal["MEMBER", "ROLE", "PERMISSION", "ALL"]

   def __post_init__(self):
      if self.rule not in ["ALLOW", "DENY"]:
         raise TypeError(f"Attempted to create a record with a RULE not in ['ALLOW','DENY']: {self}")
      if self.target_type not in ["MEMBER", "ROLE", "PERMISSION", "ALL"]:
         raise TypeError(f"Attempted to create a record with a TARGET_TYPE not in ['MEMBER', 'ROLE', 'PERMISSION', 'ALL']")

   def to_dict(self):
      return dtcs.asdict(self)

   @classmethod
   def admin_record(cls, admin_id: id):
      return cls(rule="ALLOW", target_id=admin_id, target_type="MEMBER")

   @classmethod
   def allow_perm(cls, perm: discord.Permissions):
      return cls(rule="ALLOW", target_id=perm.value, target_type="PERMISSION")

   @classmethod
   def deny_all(cls):
      return cls(rule="DENY", target_id=0, target_type="ALL")

   @classmethod
   def allow_all(cls):
      return cls(rule="ALLOW", target_id=0, target_type="ALL")

   def evaluate(self, ctx: AuthAwareContext) -> ty.Optional[bool]:
      if (
            (self.target_type == "ALL") or
            (self.target_type == "PERMISSION" and ctx.auth_identifiers.permissions and discord.Permissions(permissions=self.target_id) <= ctx.auth_identifiers.permissions) or
            (self.target_type == "ROLE" and self.target_id in ctx.auth_identifiers.roles) or
            (self.target_type == "MEMBER" and self.target_id == ctx.auth_identifiers.user)
      ):
         return self.rule == "ALLOW"
      return None

   PRECEDENCE = {
      "MEMBER"    : 0,
      "ROLE"      : -1,
      "PERMISSION": -2,
      "ALL"       : -3
   }


class AuthAware:
   @property
   @abc.abstractmethod
   def default_auths(self) -> ty.List[Record]: ...

   @property
   @abc.abstractmethod
   def auth_id(self) -> str: ...


class Auth:

   @staticmethod
   def order_records(records: ty.List[Record]):
      return sorted(records, key=lambda record: Record.PRECEDENCE[record.target_type])

   @staticmethod
   def accepts(ctx: AuthAwareContext, cmd: Command):
      auths = ctx.config["auths"]
      print("\nAccepts?")
      print(ctx.config_identifier)
      print(auths.keys())
      print(cmd.auth_id)
      # print(auths[cmd.auth_id])
      cog_specifics = Auth.order_records([Record(**record) for record in (auths.get(cmd.cog.auth_id, []))])
      cmd_specifics = Auth.order_records([Record(**record) for record in (auths.get(cmd.auth_id, []))])
      cog_defaults = Auth.order_records(cmd.cog.default_auths)
      cmd_defaults = Auth.order_records(cmd.default_auths)

      accept = False
      print(f"Evaluating rules for {cmd.name}")
      print(f"Context: {ctx}")
      for record in itt.chain(cog_defaults, cmd_defaults, cog_specifics, cmd_specifics, [Record.admin_record(ctx.config["admin_id"])]):
         print(f"Evaluating {record}")
         res = record.evaluate(ctx)
         print(res)
         if res is not None:
            accept = res
      return accept

   @staticmethod
   async def add_record(ctx: AuthAwareContext, auth_id: str, record: Record):
      async with ctx.flux.CONFIG.writeable_conf(ctx) as cfg_w:
         if auth_id in cfg_w["auths"]:
            cfg_w["auths"][auth_id] = [auth_rec for auth_rec in cfg_w["auths"][auth_id] if auth_rec["target_id"] != record.target_id]
            cfg_w["auths"][auth_id].append(record.to_dict())
         else:
            cfg_w["auths"][auth_id] = [record.to_dict()]
