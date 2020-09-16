from . import AurfluxCog, CommandCheck
from .command import MessageContext, Response
from . import utils
import discord
import re
import traceback


class Builtins(AurfluxCog):
   def load(self):
      # @CommandCheck.check(lambda ctx: ctx.author.id == self.aurflux.admin_id)
      # @self._commandeer(name="reload", parsed=False, private=True)
      # async def reload(ctx: MessageContext, cog_name: str):
      #    reloaded_cogs = []
      #    for cog in s.cogs:
      #       new_cog = cog
      #       if cog.__class__.__name__.lower() == cog_name:
      #          cog.teardown()
      #          module = importlib.reload(inspect.getmodule(cog))
      #          new_cog = getattr(module, cog.__class__.__name__)(ctx.aurflux)
      #          await new_cog.startup()
      #       reloaded_cogs.append(new_cog)
      #    ctx.aurflux.cogs = reloaded_cogs
      #    return Response()

      @CommandCheck.check(CommandCheck.has_permissions(discord.Permissions(manage_guild=True)))
      @self._commandeer(name="setprefix", parsed=False)
      async def set_prefix(ctx: MessageContext, prefix: str, *_):
         """
         Sets the prefix to [prefix]
         ..setprefix !!
         :param ctx:
         :param prefix:
         :param _:
         :return:
         """
         async with self.aurflux.CONFIG.writeable_conf(ctx) as cfg:
            cfg["prefix"] = prefix
         return Response()

      @CommandCheck.check(lambda ctx: ctx.author.id == self.aurflux.admin_id)
      @self._commandeer(name="exec", parsed=False, private=True)
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

      @self._commandeer(name="help", parsed=False)
      async def get_help(ctx: MessageContext, help_target: ty.Optional[str]):
         """
         help [command_name]
         :param ctx:
         :param args:
         :return:
         """
         configs = self.aurflux.CONFIG.of(ctx)
         public_cmds = {name: command for name, command in self.aurflux.commands.items() if not command.private and name != "help"}
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
               embed.add_field(name="Usage", value=f"{configs['prefix']}{public_cmds[help_target].short_usage}\n{public_cmds[help_target].long_usage}")
            return Response(embed=embed)