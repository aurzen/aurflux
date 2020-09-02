from __future__ import annotations
from . import ext

import typing as ty

if ty.TYPE_CHECKING:
    from .context import MessageContext
    from .types import *
    from .errors import *
    from .aurflux import Aurflux

import typing as ty
import itertools as itt
import asyncio as aio
import inspect
import discord
import aurflux
import argparse
import datetime


class Response:
    __iter_done = False
    message: ty.Optional[discord.Message]

    def __init__(
            self,
            # ctx: Context,
            content: ty.Optional[str] = None,
            embed: ty.Optional[discord.Embed] = None,
            delete_after: ty.Optional[ty.Union[float, datetime.timedelta]] = None,
            reaction: ty.Optional[ty.Iterable[ty.Union[discord.Emoji, str]]] = None,
            errored: bool = False,
            ping: bool = False,
            post_process: ty.Optional[ty.Callable[[MessageContext, discord.Message], ty.Coroutine]] = None,
            trashable: bool = False
            # reaction: str = ""  # todo: white check mark
    ):
        self.content = content
        self.embed = embed
        self.delete_after = delete_after if isinstance(delete_after, datetime.timedelta) or not delete_after else datetime.timedelta(seconds=delete_after)
        self.errored = errored
        self.reactions = reaction or (("❌",) if self.errored else ("✅",))
        self.ping = ping
        self.post_process = post_process or (lambda *_: aio.sleep(0))
        self.trashable = trashable

    async def execute(self, ctx: MessageContext):
        print(ctx)
        if self.content or self.embed:
            content = self.content if self.content else "" + (ctx.author.mention if self.ping else "")
            if len(content) > 1900:
                async with ctx.aurflux.aiohttp_session.post("https://h.ze.ax/documents", data=content) as resp:
                    content = (await resp.json(content_type=None))["key"]
            message = await ctx.channel.send(
                content=content,
                embed=self.embed,
                delete_after=self.delete_after.seconds if self.delete_after else None  # todo: check if seconds,

            )
            self.message = message

            await self.post_process(ctx, message)
        try:
            for reaction in self.reactions:
                await ctx.message.add_reaction(reaction)

            if self.trashable:
                await self.message.add_reaction(aurflux.utils.EMOJIS["trashcan"])
                try:
                    await ctx.aurflux.router.wait_for(":reaction_add", check=lambda ev: ev.args[0].message.id == self.message.id and ev.args[1] == ctx.message.author, timeout=15)
                    await self.message.delete()
                except aio.exceptions.TimeoutError:
                    await self.message.remove_reaction(emoji=aurflux.utils.EMOJIS["trashcan"], member=ctx.guild.me)
        except discord.errors.NotFound as e:
            print(e)
            pass
    # def __aiter__(self):
    #     async def gen():
    #         yield self
    #     return gen()
