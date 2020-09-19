from __future__ import annotations

import abc
import typing as ty
from abc import ABCMeta
from builtins import property

import aurcore as aur

from ..auth import AuthList

if ty.TYPE_CHECKING:
   import discord
   from .. import FluxClient


class ConfigContext(aur.util.AutoRepr):
   def __init__(self, flux: FluxClient, **kwargs):
      self.flux = flux

   @property
   @abc.abstractmethod
   def config_identifier(self) -> str: ...

   @property
   def config(self) -> ty.Dict[str, ty.Any]:
      return self.flux.CONFIG.of(self)

   @property
   def me(self) -> discord.abc.User:
      return self.flux.user


class _GuildAware(ConfigContext):
   def __init__(self, **kwargs):
      super().__init__(**kwargs)

   @property
   @abc.abstractmethod
   def guild(self) -> discord.Guild: ...

   @property
   def config_identifier(self) -> str:
      return str(self.guild.id)


class _Messageable(ConfigContext):
   def __init__(self, **kwargs):
      super().__init__(**kwargs)

   @property
   @abc.abstractmethod
   def dest(self) -> discord.abc.Messageable: ...


class AuthAwareContext(ConfigContext):
   def __init__(self, **kwargs):
      super().__init__(**kwargs)

   @property
   @abc.abstractmethod
   def auth_lists(self) -> [AuthList]: ...



class ManualAuthContext(AuthAwareContext):

   def __init__(self, auth_lists: ty.List[AuthList], config_identifier: str, **kwargs):
      super().__init__(**kwargs)
      self.auth_list = auth_lists
      self.config_identifier_ = config_identifier

   @property
   def auth_lists(self) -> [AuthList]:
      return [self.auth_list]

   @property
   def config_identifier(self) -> str:
      return self.config_identifier_


class GuildMemberContext(AuthAwareContext, _GuildAware):

   def __init__(self, member: discord.Member, **kwargs):
      super().__init__(**kwargs)
      self.member = member

   @property
   def auth_lists(self) -> [AuthList]:
      return [AuthList(
         user=self.member.id,
         roles=[role.id for role in self.member.roles],
         permissions=self.member.guild_permissions
      )]

   def guild(self) -> discord.Guild:
      return self.member.guild


class MessageContext(AuthAwareContext, metaclass=ABCMeta):
   def __init__(self, message: discord.Message, **kwargs):
      super().__init__(**kwargs)
      self.message = message

   @property
   def author(self) -> ty.Union[discord.Member, discord.User]:
      return self.message.author

   @property
   def dest(self) -> discord.abc.Messageable:
      return self.message.channel


class GuildTextChannelContext(_GuildAware, _Messageable):

   def __init__(self, channel: discord.TextChannel, **kwargs):
      super().__init__(**kwargs)
      self.channel = channel

   @property
   def guild(self) -> discord.Guild:
      return self.channel.guild


   @property
   def me(self) -> discord.abc.User:
      return self.guild.me

   @property
   def dest(self) -> discord.abc.Messageable:
      return self.channel


class DMChannelContext(_Messageable, AuthAwareContext):
   def __init__(self, channel: discord.DMChannel, **kwargs):
      super().__init__(**kwargs)
      self.channel = channel

   @property
   def recipient(self) -> discord.User:
      return self.channel.recipient

   @property
   def me(self) -> discord.User:
      return self.channel.me

   @property
   def config_identifier(self) -> str:
      return str(self.channel.recipient.id)

   @property
   def dest(self) -> discord.abc.Messageable:
      return self.recipient.dm_channel

   @property
   def auth_lists(self) -> [AuthList]:
      return [AuthList(
         user=self.recipient.id,
      )]


class GuildMessageContext(GuildTextChannelContext, MessageContext, GuildMemberContext):
   def __init__(self, message: discord.Message, **kwargs):
      super().__init__(message=message, channel=message.channel, member=message.author, **kwargs)

   @property
   def author(self) -> discord.Member:
      return self.member


class DMMessageContext(DMChannelContext, MessageContext):
   def __init__(self, **kwargs):
      super().__init__(**kwargs)
