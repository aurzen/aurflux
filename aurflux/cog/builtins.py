from __future__ import annotations

import re
import traceback
import typing as ty

import discord
import ast
from ..auth import Record, Auth, AuthList
from . import FluxCog
from .. import utils
import json
from .. import FluxEvent, CommandEvent
from ..command import Response
from ..command.argh import Arg
from ..errors import CommandError
from ..context import GuildMemberCtx, ManualAuthCtx, ManualAuthorCtx
import datetime

if ty.TYPE_CHECKING:
   from ..context import CommandCtx, GuildMessageCtx, AuthAwareCtx, MessageCtx, GuildAwareCtx, AuthorAwareCtx
   from ..command import Command


class Builtins(FluxCog):
   RULETYPES = {
      "p"          : "permissions",
      "r"          : "role",
      "m"          : "member",
      "permissions": "permissions",
      "role"       : "role",
      "member"     : "member",
   }

   def load(self):
      def parse_auth_id(ctx: GuildAwareCtx, type_: str, target_: str) -> int:
         if type_ == "member":
            ids_ = utils.find_mentions(target_)

            if not ids_:
               raise CommandError(f"No member ID found in {target_}")
            if not ctx.guild.get_member(ids_[0]):
               raise CommandError(f"No member found with ID {ids_[0]}")
            return ids_[0]
         if type_ == "role":
            ids_ = utils.find_mentions(target_)
            try:
               role_id = ctx.guild.get_role(int(ids_[0])).id
            except AttributeError:
               raise CommandError(f"No role found with ID {target_}")
            return role_id
         if type_ == "permissions":
            p_dict: ty.List[str] = json.loads(target_)
            return discord.Permissions(**{p: True for p in p_dict}).value

      def parse_auth_context(ctx: GuildAwareCtx, type_: str, target_: str) -> ManualAuthCtx:
         if type_ == "user":
            ids_ = utils.find_mentions(target_)
            if not ids_:
               raise CommandError(f"No user ID found in {target_}")

            return ManualAuthCtx(flux=self.flux, auth_list=AuthList(user=self.flux.get_user(ids_[0]).id), config_identifier=ids_[0])
         auth_id = parse_auth_id(ctx, type_=type_, target_=target_)
         if type_ == "member":
            member = ctx.guild.get_member(auth_id)
            if not member:
               raise CommandError(f"No member found with id `{auth_id}`")
            return ManualAuthCtx(flux=self.flux, auth_list=AuthList(user=member.id, roles=[r.id for r in member.roles], permissions=member.guild_permissions),
                                 config_identifier=str(ctx.guild.id))
         if type_ == "role":
            role = ctx.guild.get_role(auth_id)
            if not role:
               raise CommandError(f"No role found with id `{auth_id}`")
            return ManualAuthCtx(flux=self.flux, auth_list=AuthList(roles=[auth_id], permissions=role.permissions), config_identifier=str(ctx.guild.id))

         if type_ == "permissions":
            try:
               return ManualAuthCtx(flux=self.flux, auth_list=AuthList(permissions=discord.Permissions(permissions=auth_id)), config_identifier=str(ctx.guild.id))
            except TypeError as e:
               raise CommandError(f"Permissions `{auth_id}` could not be parsed. See:\n{e}")

      # @CommandCheck.check(lambda ctx: ctx.author.id == self.flux.admin_id)
      # @self._commandeer(name="reload", parsed=False, private=True)
      # async def reload(ctx: MessageContext, cog_name: str):
      #    reloaded_cogs = []
      #    for cog in s.cogs:
      #       new_cog = cog
      #       if cog.__class__.__name__.lower() == cog_name:
      #          cog.teardown()
      #          module = importlib.reload(inspect.getmodule(cog))
      #          new_cog = getattr(module, cog.__class__.__name__)(ctx.flux)
      #          await new_cog.startup()
      #       reloaded_cogs.append(new_cog)
      #    ctx.flux.cogs = reloaded_cogs
      #    return Response()

      @self._commandeer(name="asif", parsed=False, default_auths=[Record.allow_all()])
      async def __asif(ctx: CommandCtx, args: str, ):
         """
         asif [type] <target>/{target} command args*
         ==
         Runs `command` as if it was being run by a `target` user, member, role, or permission-haver
         ==
         [type]: [user/role/member/permissions/u/r/m/p] the type of `target`;
         <target>: <user/member/role>. Simulates usage by a given user, member,
         member with a role, or member that has a set of permissions. See s.ze.ax/perm for {perms} structure;
         {target}: JSON Array of permissions to simulate having
         command: Name of the Command to run as `target`;
         args: command arguments to pass to the Command
         ==
         :param ctx:
         :param args:
         :return:
         """

         try:
            mock_type, mock_target, command, command_args = utils.regex_parse(re.compile(r"(\S+)\s+(\S+)\s+((\[[^\]]*\])|([^\s\[]+))\s+(\S+)\s*(.*)"),
                                                                              args,
                                                                              [x - 1 for x in [1, 2, 3, 6, 7]])
         except (ValueError, AttributeError):
            raise CommandError(f"See `help asif` for usage")

         MOCK_TYPES = {
            "u"   : "user",
            "user": "user",
            **self.RULETYPES
         }
         try:
            mock_type = MOCK_TYPES[mock_type]
         except KeyError:
            raise CommandError(f"`{mock_type}` must be in [{', '.join(MOCK_TYPES.keys())}]")

         cmd_name, cmd_args, *_ = [*command.split(" ", 1), None]
         mock_auth_ctx = parse_auth_context(ctx=ctx.msg_ctx, type_=mock_type, target_=mock_target)
         mock_author_ctx = ManualAuthorCtx(ctx.msg_ctx.message.guild.get_member(mock_target)) if ctx.msg_ctx.message.guild else ctx.author_ctx

         cmd = utils.find_cmd_or_cog(self.flux, cmd_name, only="command")

         if not cmd:
            raise CommandError(f"Command {cmd_name} not found")
         if Auth.accepts_all(ctx.auth_ctxs + [mock_auth_ctx], cmd):
            await self.flux.router.submit(
               event=CommandEvent(flux=self.flux, cmd_ctx=CommandCtx(ctx.msg_ctx, mock_author_ctx, ctx.auth_ctxs + [mock_auth_ctx]), cmd_name=cmd_name, cmd_args=cmd_args))
         else:
            raise CommandError(f"Can only mock commands that you have access to")

         return Response()

      @self._commandeer(name="setprefix", parsed=False, default_auths=[Record.allow_perm(discord.Permissions(manage_guild=True))])
      async def __set_prefix(ctx: CommandCtx, prefix: str):
         """
         setprefix prefix
         ==
         Sets the bot prefix to `prefix`
         Ignores surrounding whitespace. Please don't.
         ==
         prefix: The string to put before a command name. Strips leading and trailing spaces.
         ==
         :param ctx:
         :param prefix:
         :return:
         """
         async with self.flux.CONFIG.writeable_conf(ctx.msg_ctx) as cfg:
            cfg["prefix"] = prefix.strip()
         return Response()

      @self._commandeer(name="exec", parsed=False, override_auths=[Record.deny_all()])
      async def __exec(ctx: CommandCtx, script: str):
         """
         exec ute order 66
         ==
         Safe™
         ==
         :)
         ==
         :param ctx:
         :param script:
         :return:
         """
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

      @self._commandeer(name="auth", parsed=False, default_auths=[Record.allow_perm(discord.Permissions(manage_guild=True))])
      async def __auth(ctx: CommandCtx, auth_str):
         """
         auth name [rule] <id>/{perm} [id_type]
         ==
         Authorizes some group (member, has a role, or has a permission) to use a command or a cog
         ==
         name: Command name or Cog name;
         [rule]: [ALLOW/DENY];
         <id>: <member/role> The target member or role to allow;
         {perm:} A permission JSON array representing a set of permissions that a user must have ALL of.
         ex. ["manage_server","kick_members"]
         id_type: [MEMBER/ROLE/PERMISSION] Whatever `id` corresponds to
         ==
         :param ctx:
         :param auth_str:
         :return:
         """
         try:
            rule_subject, rule, rule_target_id_raw, rule_type = utils.regex_parse(re.compile(r"(\S+)\s+(\S+)\s+((\[[^\]]*\])|([^\s\[]+))\s+(\S+)"),
                                                                                  auth_str,
                                                                                  [x - 1 for x in [1, 2, 3, 6]])
         except (ValueError, AttributeError):
            raise CommandError(f"See `help auth` for usage")

         rule_subject = rule_subject.lower()
         rule = rule.upper()
         rule_type = rule_type.lower()

         cmd_or_cog = utils.find_cmd_or_cog(self.flux, rule_subject)
         if not cmd_or_cog:
            raise CommandError(f"No cog or command found with name {rule_subject}")
         if rule not in ["ALLOW", "DENY"]:
            raise CommandError(f'rule {rule} not in ["ALLOW","DENY"]')
         try:
            target_id = parse_auth_id(ctx.msg_ctx, type_=self.RULETYPES[rule_type], target_=rule_target_id_raw)
         except KeyError:
            raise CommandError(f"Rule type {rule_type} not in {self.RULETYPES.keys()}")

         record = Record(rule=rule, target_id=target_id, target_type=rule_type.upper())
         await Auth.add_record(ctx.msg_ctx, auth_id=cmd_or_cog.auth_id, record=record)
         return Response(f"Added record {record}")

      @self._commandeer(name="userinfo", parsed=False, default_auths=[Record.allow_perm(discord.Permissions(manage_guild=True))])
      async def __userinfo(ctx: CommandCtx, target_raw):
         """
         userinfo (<user/member>)
         ==
         Authorizes some group (member, has a role, or has a permission) to use a command or a cog
         ==
         <user/member>: The target member/user to userinfo. Defaults to caller if not provided.
         ==
         :param ctx:
         :param target_raw:
         :return:
         """
         if not (target := utils.find_mentions(target_raw)):
            raise CommandError(f"Cannot find a user/member in `{target_raw}`. It should either be an ID or a mention")
         if isinstance(ctx.msg_ctx, GuildMessageCtx):
            target = ctx.guild.get_member(target)
         else:
            target = await ctx.msg_ctx.flux.get_user(target)

         embed = discord.Embed(title=f"{target}'s Userinfo", url=str(target.avatar_url), color=target.color)
         embed.add_field(name="Display Name", value=target.display_name, inline=True)
         embed.add_field(name="ID", value=str(target.id), inline=False)
         embed.add_field(name="Latest Join", value=target.joined_at.strftime("%I:%M:%S %p on %a, %b %d, %Y"))

         if isinstance(ctx.msg_ctx, GuildMessageCtx):
            if target.premium_since:
               delta = (datetime.datetime.utcnow() - target.premium_since).days
               D_IN_M = 29.53
               D_IN_Y = 365.25
               if delta < 7:
                  output = f"{delta} days"
               elif delta < D_IN_M:  # average month length
                  output = f"{delta // 7} weeks"
               elif delta < D_IN_Y * 2 + 1:
                  output = f"{delta // D_IN_M} months"
               else:
                  output = f"{delta // D_IN_Y} years"
               embed.add_field(name="Boosting for ", value=output)
            roles = ",".join(role.mention for role in (target.roles or ())[::-1])
            if len(roles) >= 2048:
               url = utils.haste(self.flux.aiohttp_session, "\n".join(f"{role.id}:{role.name}" for role in target.roles))
               roles = f"[roles]({url})"
            embed.add_field(name="Roles", value=roles)

            embed.add_field(name="Permissions in this channel", value=f"[Permissions](https://discordapi.com/permissions.html#{target.permissions_in(ctx.msg_ctx.channel)})")
            embed.add_field(name="Server Permissions", value=f"[Permissions](https://discordapi.com/permissions.html#{target.permissions_in(ctx.msg_ctx.channel)})")

      @self._commandeer(name="help", parsed=False, default_auths=[Record.allow_all()])
      async def __get_help(ctx: CommandCtx, help_target: ty.Optional[str]):
         """
         help (command_name)
         ==
         My brother is dying! Get Help!
         ==
         command_name: The command to get help for. Command list if not provided. Gets help about reading help if you `help help`
         ==
         :param ctx:
         :param args:
         :param help_target: what to get help about
         :param auth_ctx: Auth Context
         :return:
         """
         print("HELP!")
         configs = self.flux.CONFIG.of(ctx.msg_ctx)
         authorized_cmds: ty.Dict[str, Command] = {command.name: command for cog in self.flux.cogs for command in cog.commands if
                                                   Auth.accepts_all(ctx.auth_ctxs, command) and command.name != "help"}

         if not help_target:
            help_embed = discord.Embed(title=f"{utils.EMOJIS['question']} Command Help", description=f"{configs['prefix']}help <command> for more info")
            for cmd_name, command in authorized_cmds.items():
               usage = "\n".join([f"{configs['prefix']}{usage}" for usage in command.short_usage.split("\n")])
               help_embed.add_field(name=cmd_name, value=usage, inline=False)

            return Response(embed=help_embed)

         if help_target == "help":
            embed = discord.Embed(title="\U00002754 Command Help", description="How to read help")
            embed.add_field(name="Usage", value='..commandname [lit] <user> {json} (optional) extra*', inline=False)
            embed.add_field(name="a/b", value="Either a or b. E.g. <user>/{userinfo} ", inline=False)
            embed.add_field(name="[lit]", value="Something with a limited set of choices. See `help commandname`", inline=False)
            embed.add_field(name="<user>", value="Either an ID or a Mention of something. E.g. a @user", inline=False)
            embed.add_field(name="(optional)", value="Can leave this out", inline=False)
            embed.add_field(name="{json}", value="Json. No spaces please ;w;", inline=False)
            embed.add_field(name="extra*", value="Spaces OK", inline=False)

            return Response(embed=embed)

         if help_target not in authorized_cmds:
            return Response(f"No command `{help_target}` to show help for", errored=True)

         cmd = authorized_cmds[help_target]
         embed = discord.Embed(
            title=f"\U00002754 Command Help for {help_target}",
            description=cmd.description)

         embed.add_field(name="Usage", value=cmd.short_usage, inline=False)

         for arg, detail in cmd.param_usage:
            embed.add_field(name=arg.strip(), value=detail.strip(), inline=False)
            # embed.add_field(name=detail,value="", inline=False)

         # args, details = list(zip(*cmd.long_usage))
         # embed.add_field(name="Param", value="\n".join(args), inline=True)
         # embed.add_field(name="Details", value="\n".join(details), inline=True)

         # embed.add_field(name="usage", value=f"{configs['prefix']}{cmd.long_usage}", inline=False)
         return Response(embed=embed)

   @property
   def default_auths(self) -> ty.List[Record]:
      return []
