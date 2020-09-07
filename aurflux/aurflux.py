from __future__ import annotations

import importlib

import discord.errors
import traceback
import abc
from .command import Command, CommandCheck
from .config import Config
from .context import MessageContext
from .errors import *
from .response import Response
import aiohttp
from . import utils
import asyncio as aio
from . import argh
import re
import discord.ext
from aurcore.event import EventRouter, EventWaiter, EventMuxer,  EventFunction
import inspect
import logging

logging.getLogger("discord.client").addFilter(lambda r: r.getMessage() != "PyNaCl is not installed, voice will NOT be supported")
logger = logging.getLogger(__name__)
if ty.TYPE_CHECKING:
    import discord
    from .types import *


class AurfluxEvent(Event):
    def __init__(self, aurflux, __event_name, *args, **kwargs):
        super().__init__(__event_name, *args, **kwargs)
        self.bot: Aurflux = aurflux


class AurfluxCog:
    def __init__(self, aurflux: Aurflux):
        self.aurflux = aurflux
        self.router = EventRouter(self.__class__.__name__, self.aurflux.router)
        self.listeners: ty.Dict[ty.Union[EventFunction, EventRouter, EventWaiter], EventMuxer] = {}
        self.commands = set()
        self.route()
        logging.info(f"[AurfluxCog] {self.__class__.__name__} loaded!")

    async def startup(self):
        pass

    def register(self, cog_member: ty.Union[Command,EventMuxer]):
        print(f"Cog registering!")
        print(cog_member)
        # if isinstance(cog_member, Command):
        #     self.commands.add(cog_member)
        # else:
        #     self.listeners[cog_member.name] = cog_member


    def teardown(self):
        pass
        # for listener, muxer in self.listeners.items():
        #     print(f"Deregistering {listener} on {muxer}")
        #     if isinstance(listener, EventRouter):
        #         muxer.router = None
        #     else:
        #         muxer.remove_listener(listener)
        # for command in self.commands:
        #     del self.aurflux.commands[command.name]
        # self.router.detatch()

    @abc.abstractmethod
    def route(self):
        ...


def ms(key):
    try:
        return dict(inspect.getmembers(
            inspect.stack()[-1][0]))["f_globals"][key]
    except KeyError:
        for i in inspect.stack()[::-1]:
            try:
                return dict(inspect.getmembers(i[0]))["f_locals"][key]
            except KeyError:
                pass
            try:
                return dict(inspect.getmembers(i[0]))["f_globals"][key]
            except KeyError:
                pass
    raise KeyError("Could not find key " + key)


def __aiterify(obj: ty.Union[ty.Coroutine, ty.AsyncIterable]):
    if aio.iscoroutine(obj) or aio.isfuture(obj):
        class AiterCoro:
            def __aiter__(self):
                async def gen():
                    yield await obj

                return gen()

        return AiterCoro()
    else:
        return obj


def register_builtins(aurflux: Aurflux, builtins=True):
    @aurflux.router.endpoint(":ready", decompose=True)
    async def _():
        print("Ready!")

    @aurflux.router.endpoint(":message", decompose=True)
    async def command_listener(message: discord.Message):
        if not message.content or message.author is aurflux.user:
            return

        ctx = MessageContext(bot=aurflux, message=message)
        prefix = aurflux.CONFIG.of(ctx)["prefix"]
        cmd = message.content.split(" ", 1)[0][len(prefix):]

        if cmd not in aurflux.commands:
            return

        if not message.content.startswith(prefix):
            return
        try:
            if cmd not in aurflux.commands:
                return
            async for response in __aiterify(await aurflux.commands[cmd].execute(ctx)):
                await response.execute(ctx)
        except CommandError as e:
            info_message = f"{e}"
            if argparser := aurflux.commands[cmd].argparser:
                info_message += f"\n```{argparser.format_help()}```"
            await Response(content=info_message, errored=True).execute(ctx)
        except CommandInfo as e:
            info_message = f"{e}"
            if argparser := aurflux.commands[cmd].argparser:
                info_message += f"\n```{argparser.format_help()}```"
            await Response(content=info_message).execute(ctx)

    @CommandCheck.check(lambda ctx: ctx.author.id == aurflux.admin_id)
    @aurflux.commandeer(name="reload", parsed=False, private=True)
    async def reload(ctx: MessageContext, cog_name: str):
        reloaded_cogs = []
        for cog in aurflux.cogs:
            new_cog = cog
            if cog.__class__.__name__.lower() == cog_name:
                cog.teardown()
                module = importlib.reload(inspect.getmodule(cog))
                new_cog = getattr(module, cog.__class__.__name__)(ctx.aurflux)
                await new_cog.startup()
            reloaded_cogs.append(new_cog)
        ctx.aurflux.cogs = reloaded_cogs
        return Response()

    @CommandCheck.check(CommandCheck.has_permissions(discord.Permissions(manage_guild=True )))
    @aurflux.commandeer(name="setprefix", parsed=False)
    async def set_prefix(ctx: MessageContext, prefix: str, *_):
        """
        Sets the prefix to [prefix]
        ..setprefix !!
        :param ctx:
        :param prefix:
        :param _:
        :return:
        """
        async with aurflux.CONFIG.writeable_conf(ctx) as cfg:
            cfg["prefix"] = prefix
        return Response()

    if not builtins:

        @CommandCheck.check(lambda ctx: ctx.author.id == aurflux.admin_id)
        @aurflux.commandeer(name="exec", parsed=False, private=True)
        async def exec_(ctx: MessageContext, script: str):
            exec_func = utils.sexec
            if "await " in script:
                exec_func = utils.aexec

            with utils.Timer() as t:
                # noinspection PyBroadException
                try:
                    res = await exec_func(script, globals(), locals())
                except Exception as e:
                    res = re.sub(r'File ".*[\\/]([^\\/]+.py)"', r'File "\1"', traceback.format_exc(limit=1))

            return Response((f""
                             f"Ran in {t.elapsed * 1000:.2f} ms\n"
                             f"**IN**:\n"
                             f"```py\n{script}\n```\n"
                             f"**OUT**:\n"
                             f"```py\n{res}\n```"), trashable=True)

    @aurflux.commandeer(name="help", parsed=False)
    async def get_help(ctx: MessageContext, help_target: ty.Optional[str]):
        """
        help [command_name]
        :param ctx:
        :param args:
        :return:
        """
        configs = aurflux.CONFIG.of(ctx)
        public_cmds = {name: command for name, command in aurflux.commands.items() if not command.private and name != "help"}
        if not help_target:
            help_embed = discord.Embed(title=f"{utils.EMOJIS['question']} Command Help", description=f"{configs['prefix']}help <command> for more info")
            for cmd_name, command in public_cmds.items():
                help_embed.add_field(name=cmd_name, value=f"{configs['prefix']}{command.short_usage}", inline=False)

            return Response(
                embed=help_embed
            )
        else:
            if help_target not in public_cmds:
                return Response(f"No command `{help_target}` to show help for", errored=True)
            embed = discord.Embed(
                title="\U00002754 Command Help",
                description=f"Help for `{configs['prefix']}{help_target}`")
            if public_cmds[help_target].argparser:
                embed.add_field(name="Usage", value=f"{public_cmds[help_target].short_usage}\n{public_cmds[help_target].long_usage}")
            return Response(embed=embed)


class Aurflux(discord.Client):
    CONFIG: Config

    def __init__(self, name, admin_id: int, parent_router: EventRouter = None, builtins=True, *args, **kwargs):
        super(Aurflux, self).__init__(*args, **kwargs)
        self.CONFIG = Config(name)
        self.commands: ty.Dict[str, Command] = {}
        self.router = EventRouter(name="aurflux", parent=parent_router)
        self.admin_id = admin_id
        # if not secondary:
        register_builtins(self, builtins)
        self.cogs: ty.List[AurfluxCog] = []
        self.aiohttp_session = aiohttp.ClientSession()

    def commandeer(self, name: ty.Optional[str] = None, parsed: bool = True, private: bool = False) -> ty.Callable[[ty.Callable[[...], ty.Awaitable[Response]]], Command]:
        def command_deco(func: ty.Callable[[...], ty.Awaitable[Response]]) -> Command:
            cmd = Command(aurflux=self, func=func, name=(name or func.__name__), parsed=parsed, private=private)
            if cmd.name in self.commands:
                raise TypeError(f"Attempting to register command {cmd} when {self.commands[cmd.name]} already exists")
            self.commands[cmd.name] = cmd
            return cmd

        return command_deco

    def dispatch(self, event, *args, **kwargs):
        super(Aurflux, self).dispatch(event, *args, **kwargs)
        asyncio.create_task(self.router.submit(AurfluxEvent(self, f":{event}", *args, **kwargs)))

    def register_cog(self, cog: ty.Type[AurfluxCog]):
        self.cogs.append(cog(self))

    async def startup(self, token, *args, **kwargs):
        await aio.gather(*[cog.startup() for cog in self.cogs])
        await self.start(token, *args, **kwargs)
