from __future__ import annotations

import abc
import typing as ty

import aurcore as aur

if ty.TYPE_CHECKING:
   import discord
   from .. import FluxClient
   from ..command import Command


class Context(abc.ABC, aur.util.AutoRepr):
   def __init__(self, flux: FluxClient):
      self.flux = flux

   @property
   @abc.abstractmethod
   def me(self) -> discord.abc.User: ...

   @property
   @abc.abstractmethod
   def config_identifier(self) -> int: ...

   @property
   def config(self) -> ty.Dict[ty.Any, str]:
      return self.flux.CONFIG.of(self.config_identifier)


class GuildTextChannelContext(Context):

   def __init__(self, flux: FluxClient, channel: discord.TextChannel):
      super(GuildTextChannelContext, self).__init__(flux=flux)
      self.channel = channel

   @property
   def guild(self) -> discord.Guild:
      return self.channel.guild

   @property
   def config_identifier(self) -> int:
      return self.channel.id

   @property
   def me(self) -> discord.abc.User:
      return self.guild.me


class GuildMessageContext(GuildTextChannelContext):
   def __init__(self, flux: FluxClient, message: discord.Message):
      super(GuildMessageContext, self).__init__(flux=flux, channel=message.channel)
      self.message = message

   @property
   def author(self) -> ty.Union[discord.User, discord.Member]:
      return self.message.author


class DMChannelContext(Context):
   def __init__(self, flux: FluxClient, channel: discord.DMChannel):
      super(DMChannelContext, self).__init__(flux=flux)
      self.channel = channel

   @property
   def me(self) -> discord.abc.User:
      return self.channel.me

   @property
   def config_identifier(self) -> int:
      return self.channel.recipient.id
