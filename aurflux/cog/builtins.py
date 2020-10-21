from __future__ import annotations

import datetime
import itertools as itt
import json
import re
import traceback
import typing as ty

import discord
import tabulate
from loguru import logger

from . import FluxCog
from .. import CommandEvent, utils
from ..auth import Auth, AuthList, Record
from ..command import Response
from ..context import CommandCtx, GuildMessageCtx, ManualAuthCtx, ManualAuthorCtx
from ..errors import CommandError
# noinspection PyUnresolvedReferences,Mypy
import context

if ty.TYPE_CHECKING:
   from ..context import GuildAwareCtx
   from ..command import Command
   from ..types_ import GuildCommandCtx


class Builtins(FluxCog):
   RULETYPES = {
      "p"          : "permissions",
      "r"          : "role",
      "m"          : "member",
      "permissions": "permissions",
      "role"       : "role",
      "member"     : "member",
   }

   def load(self) -> None:
      async def parse_auth_id(ctx: GuildAwareCtx, type_: str, target_: str) -> int:
         if type_ == "member":
            ids_ = utils.find_mentions(target_)

            if not ids_:
               raise CommandError(f"No member ID found in {target_}")
            if not await self.flux.get_member_s(ctx.guild, ids_[0]):
               raise CommandError(f"No member found with ID {ids_[0]}")
            return ids_[0]
         if type_ == "role":
            ids_ = utils.find_mentions(target_)
            role = ctx.guild.get_role(ids_[0])
            if role is None:
               raise CommandError(f"No role found with ID {target_}")
            return role.id
         if type_ == "permissions":
            p_dict: ty.List[str] = json.loads(target_)
            return discord.Permissions(**{p: True for p in p_dict}).value
         else:
            raise ValueError

      async def parse_auth_context(ctx: GuildAwareCtx, type_: str, target_: str) -> ManualAuthCtx:
         if type_ == "user":
            ids_ = utils.find_mentions(target_)
            if not ids_:
               raise CommandError(f"No user ID found in {target_}")
            user = await self.flux.get_user_s(ids_[0])
            if not user:
               raise CommandError(f"No user found with ID: {ids_[0]}")
            return ManualAuthCtx(flux=self.flux, auth_list=AuthList(user=user.id), config_identifier=ids_[0])
         auth_id = await parse_auth_id(ctx, type_=type_, target_=target_)
         if type_ == "member":
            member = await self.flux.get_member_s(ctx.guild, auth_id)
            if not member:
               raise CommandError(f"No member found with id `{auth_id}`")
            return ManualAuthCtx(flux=self.flux,
                                 auth_list=AuthList(
                                    user=member.id, roles=[r.id for r in member.roles],
                                    permissions=member.guild_permissions),
                                 config_identifier=str(ctx.guild.id))
         if type_ == "role":
            role = ctx.guild.get_role(auth_id)
            if not role:
               raise CommandError(f"No role found with id `{auth_id}`")
            return ManualAuthCtx(
               flux=self.flux,
               auth_list=AuthList(roles=[auth_id], permissions=role.permissions),
               config_identifier=str(ctx.guild.id))

         if type_ == "permissions":
            try:
               return ManualAuthCtx(
                  flux=self.flux,
                  auth_list=AuthList(permissions=discord.Permissions(permissions=auth_id)),
                  config_identifier=str(ctx.guild.id))
            except TypeError as e:
               raise CommandError(f"Permissions `{auth_id}` could not be parsed. See:\n{e}")
         raise ValueError

      @self._commandeer(name="asif", default_auths=[Record.allow_all()])
      async def __asif(ctx: GuildCommandCtx, args: str, ):
         """
         asif [type] <target>/{target} command args*
         ==
         Runs `command` as if it was being run by a `target` user, member, role, or permission-haver
         ==
         [type]: [user/role/member/permissions/u/r/m/p] the type of `target`
         <target>: <user/member/role>. Simulates usage by a given caller, \\
         with a role, or a set of permissions. See [here](s.ze.ax/perm) for {perms} names
         {target}: JSON Array of permissions to simulate having
         command: Name of the Command to run as `target`
         args: command arguments to pass to the Command
         ==
         :param ctx:
         :param args:
         :return:
         """

         try:
            mock_type, mock_target, command, command_args = utils.regex_parse(
               re.compile(r"(\S+)\s+((\[[^\]]*\])|([^\s\[]+))\s+(\S+)\s*(.*)"),
               args,
               [x - 1 for x in [1, 2, 5, 6]]
            )
         except (ValueError, AttributeError) as e:
            logger.info(e)
            raise CommandError(f"See `help asif` for usage")

         # noinspection PyPep8Naming
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
         mock_auth_ctx = await parse_auth_context(ctx=ctx.msg_ctx, type_=mock_type, target_=mock_target)
         if mock_type == "user":
            mock_author_ctx = ManualAuthorCtx(author=await self.flux.fetch_user(int(mock_target)))
         elif mock_type == "member" and ctx.msg_ctx.message.guild:
            mock_author_ctx = ManualAuthorCtx(author=await self.flux.get_member_s(ctx.msg_ctx.guild, int(mock_target)))
         else:
            mock_author_ctx = ctx.author_ctx

         cmd = utils.find_cmd_or_cog(self.flux, cmd_name, only="command")

         if not cmd:
            raise CommandError(f"Command {cmd_name} not found")
         if Auth.accepts_all(ctx.auth_ctxs + [mock_auth_ctx], cmd):
            await self.flux.router.submit(
               event=CommandEvent(flux=self.flux,
                                  cmd_ctx=CommandCtx(
                                     self.flux,
                                     ctx.msg_ctx,
                                     mock_author_ctx,
                                     ctx.auth_ctxs + [mock_auth_ctx]
                                  ),
                                  cmd_name=cmd_name,
                                  cmd_args=cmd_args))
         else:
            raise CommandError(f"Can only mock commands that you have access to")

         return Response()

      @self._commandeer(name="setprefix", default_auths=[Record.allow_server_manager()])
      async def __set_prefix(ctx: GuildCommandCtx, prefix: str):
         """
         setprefix prefix
         ==
         Sets the bot prefix to `prefix`
         Ignores surrounding whitespace.
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

      @self._commandeer(name="exec", override_auths=[Record.deny_all()])
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

      @self._commandeer(name="auth", default_auths=[Record.allow_server_manager()])
      async def __auth(ctx: GuildCommandCtx, auth_str):
         """
         auth name [rule] [id_type] <id>/{perm}
         ==
         Authorizes some group (a member, members that have a role, or have some permissions) to use a command or a cog
         ==
         name: Command name or Cog name;
         [rule]: [ALLOW/DENY];
         id_type: [member/role/permission/m/r/p] The type that `id` is
         <id>: <member/role> The target member or role to allow
         {perm}: A permission JSON array representing a set of permissions that a user must have ALL of. \\
         ex. ["manage_server","kick_members"]
         EXAMPLE: Want to allow the role @moderator to use `auth` (Note: This effectively gives full bot access): \\
         `auth auth ALLOW role @moderators`
         ==
         :param ctx:
         :param auth_str:
         :return:
         """
         try:
            rule_subject, rule, id_type, rule_target_id_raw, = utils.regex_parse(
               re.compile(r"(\S+)\s+(\S+)\s+(\S+)\s+((\[[^\]]*\])|([^\s\[]+))"),
               auth_str,
               [x - 1 for x in [1, 2, 3, 4]]
            )
         except (ValueError, AttributeError, TypeError):
            raise CommandError(f"See `help auth` for usage")

         rule_subject = rule_subject.lower()
         rule = rule.upper()
         id_type = id_type.lower()

         cmd_or_cog = utils.find_cmd_or_cog(self.flux, rule_subject)
         if not cmd_or_cog:
            raise CommandError(f"No cog or command found with name {rule_subject}")
         if rule not in ["ALLOW", "DENY"]:
            raise CommandError(f'rule {rule} not in ["ALLOW","DENY"]')
         try:
            target_id = await parse_auth_id(ctx.msg_ctx, type_=self.RULETYPES[id_type], target_=rule_target_id_raw)
         except KeyError:
            raise CommandError(f"Rule type {id_type} not in {self.RULETYPES.keys()}")

         record = Record(rule=rule, target_id=target_id, target_type=id_type.upper())
         await Auth.add_record(ctx.msg_ctx, auth_id=cmd_or_cog.auth_id, record=record)
         return Response(f"Added record {record}")

      # noinspection PyPep8Naming
      @self._commandeer(name="userinfo", default_auths=[Record.allow_server_manager()])
      async def __userinfo(ctx: GuildCommandCtx, target_raw):
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
         utils.perm_check(ctx.msg_ctx.channel, discord.Permissions(embed_links=True))

         if not target_raw:
            target = ctx.author_ctx.author
         else:
            if not (target := utils.find_mentions(target_raw)[0]):
               raise CommandError(f"Cannot find a user/member in `{target_raw}`. It should either be an ID or a mention")

            if isinstance(ctx.msg_ctx, GuildMessageCtx):
               target = await self.flux.get_member_s(ctx.msg_ctx.guild, target)
            else:
               target = await ctx.msg_ctx.flux.get_user(target)

         embed = discord.Embed(title=f"{utils.EMOJI.question}{target}'s Userinfo", color=target.color)
         embed.set_thumbnail(url=str(target.avatar_url))
         embed.add_field(name="Display Name", value=utils.copylink(target.display_name), inline=True)
         embed.add_field(name="ID", value=utils.copylink(str(target.id)), inline=False)
         embed.add_field(name="Latest Join", value=utils.copylink(target.joined_at.strftime(utils.DATETIME_FMT_L)), inline=False)
         embed.add_field(name="Creation Date", value=utils.copylink(target.created_at.strftime(utils.DATETIME_FMT_L)), inline=False)

         if isinstance(ctx.msg_ctx, GuildMessageCtx):
            if target.color != discord.Color.default():
               embed.add_field(name="Color", value=utils.copylink(hex(target.color.value).upper()), inline=False)
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
               roles = f"(roles)[{url}]"
            embed.add_field(name="Roles", value=roles)

            embed.add_field(
               name="Permissions in this channel",
               value=f"[Permissions](https://discordapi.com/permissions.html#{target.permissions_in(ctx.msg_ctx.channel).value})",
               inline=False
            )
            embed.add_field(
               name="Server Permissions",
               value=f"[Permissions](https://discordapi.com/permissions.html#{target.guild_permissions.value})",
               inline=False
            )
         return Response(embed=embed)

      @self._commandeer(name="serverinfo", default_auths=[Record.allow_server_manager()])
      async def __serverinfo(ctx: GuildCommandCtx, _):
         """
         serverinfo
         ==
         Gets information about the server
         ==
         ==
         :param ctx:
         :param _:
         :return:
         """
         utils.perm_check(ctx.msg_ctx.channel, discord.Permissions(embed_links=True))

         g = ctx.msg_ctx.guild
         embed = discord.Embed(title=f"{utils.EMOJI.question}{g} Server Info")
         embed.set_thumbnail(url=str(ctx.msg_ctx.guild.icon_url))
         # Info
         embed.add_field(name="Owner", value=f"<@!{g.owner_id}>", inline=True)
         embed.add_field(name="Region", value=f"{g.region}", inline=True)
         embed.add_field(name="Members", value=f"{g.member_count}")

         # Creation
         embed.add_field(name="Creation", value=g.created_at.strftime(utils.DATETIME_FMT_L), inline=False)

         # Extra Info
         embed.add_field(name="MFA Required", value=f"{bool(g.mfa_level)}", inline=True)
         embed.add_field(name="Verify Level", value=f"{g.verification_level}", inline=True)
         embed.add_field(name="Filter", value=f"{g.explicit_content_filter}", inline=True)

         # Boosters
         boosters_haste = await utils.haste(
            self.flux.aiohttp_session,
            tabulate.tabulate(
               headers=["Member", "Mention"],
               tabular_data=[[str(member), member.mention] for member in g.premium_subscribers])
         ) if g.premium_subscribers else ""
         embed.add_field(name="Nitro Boosters", value=f"[{g.premium_subscription_count} boosters]({boosters_haste})", inline=True)
         embed.add_field(name="Boost Level", value=f"{g.premium_tier}", inline=True)

         # Emoji
         emoji_haste = await utils.haste(
            self.flux.aiohttp_session,
            content=tabulate.tabulate(
               headers=["Emoji", "Animated", "URL"],
               tabular_data=[[str(emoji), emoji.animated, emoji.url] for emoji in g.emojis]
            )
         )
         embed.add_field(name="Emoji", value=f"[{len(g.emojis)}/{g.emoji_limit * 2} emojis]({emoji_haste})", inline=False)

         # Features
         features_haste = await utils.haste(
            self.flux.aiohttp_session,
            content="\n".join(feature for feature in g.features)
         ) if g.features else ""
         embed.add_field(name="Features", value=f"[{len(g.features)} features enabled]({features_haste})", inline=False)

         # Channels
         text_channels = [channel for channel in g.text_channels if channel.overwrites_for(g.default_role).read_messages is not False and g.default_role.permissions.read_messages]
         public_channels_haste = await utils.haste(
            self.flux.aiohttp_session,
            content=tabulate.tabulate(
               [[f"{channel}",
                 f"{channel.id}",
                 f"{channel.category}",
                 f"{channel.created_at.strftime(utils.DATETIME_FMT_S)}",
                 f"{channel.permissions_synced}",
                 f"{channel.slowmode_delay}s",
                 f"{channel.position}",
                 ]
                for channel in text_channels],
               headers=("Name", "ID", "Category", "Creation", "Perm Sync", "Slow", "Position")
            )
         ) if text_channels else ""
         embed.add_field(name="Public Text Channels", value=f"[{len(text_channels)} Channels]({public_channels_haste})", inline=True)

         voice_channels = [channel for channel in g.voice_channels if channel.overwrites_for(g.default_role).connect is not False and g.default_role.permissions.connect]
         public_vc_haste = await utils.haste(
            self.flux.aiohttp_session,
            content=tabulate.tabulate(
               [[f"{channel}",
                 f"{channel.id}",
                 f"{channel.category}",
                 f"{channel.created_at.strftime(utils.DATETIME_FMT_S)}",
                 f"{channel.permissions_synced}",
                 f"{channel.bitrate // 1000} kbps",
                 f"{channel.user_limit}"
                 ]
                for channel in voice_channels],
               headers=("Name", "ID", "Category", "Creation", "Perm Sync", "Bitrate", "User Limit")

            )
         ) if voice_channels else ""

         embed.add_field(name="Public Voice Channels", value=f"[{len(voice_channels)} Channels]({public_vc_haste})", inline=True)
         return Response(embed=embed)
         pass

      @self._commandeer(name="help", default_auths=[Record.allow_all()])
      async def __get_help(ctx: GuildCommandCtx, help_target: ty.Optional[str]):
         """
         help (command_name/section)
         ==
         My brother is dying! Get Help!
         ==
         command_name: The command to get help for. Command list if not provided. Gets help about reading help if you `help help`
         ==
         :param ctx:
         :param help_target: what to get help about
         :return:
         """
         utils.perm_check(ctx.msg_ctx.channel, discord.Permissions(embed_links=True))
         configs = self.flux.CONFIG.of(ctx.msg_ctx)
         authorized_cmds: ty.Dict[str, ty.Tuple[FluxCog, Command]] = {command.name: (cog, command) for cog in self.flux.cogs for command in cog.commands if
                                                                      Auth.accepts_all(ctx.auth_ctxs, command) and command.name != "help"}
         # Help
         if not help_target:
            help_embed = discord.Embed(title=f"{utils.EMOJI.question} Help", description=f"{configs['prefix']}help <command/section> for more info")
            cog_groups = itt.groupby(authorized_cmds.items(), lambda x: x[1][0])
            for cog, group in cog_groups:
               # noinspection Mypy
               cog: FluxCog  # https://youtrack.jetbrains.com/issue/PY-43664
               group: ty.Iterable[ty.Tuple[str, ty.Tuple[FluxCog, Command]]]
               usages = "\n".join(
                  ["\n".join([f"{configs['prefix']}{usage}" for usage in cmd_item[1][1].usage.split("\n")])
                   for cmd_item in group]
               )
               help_embed.add_field(name=cog.name, value=usages, inline=False)
            return Response(embed=help_embed)

         # Help for Cog

         if cog := next((c for c in self.flux.cogs if c.name.lower() == help_target.lower()), None):
            embed = discord.Embed(title=f"{utils.EMOJI.question} Section Help: {cog.name}")
            for cmd in cog.commands:
               if cmd.name in authorized_cmds:
                  embed.add_field(name=cmd.name, value=cmd.description, inline=False)
            return Response(embed=embed)

         # Help for Help
         if help_target == "help":
            embed = discord.Embed(title="\U00002754 Command Help", description="How to read help")
            embed.add_field(name="Usage", value='..commandname [lit] <user> {json} (optional) extra*', inline=False)
            embed.add_field(name="a/b", value="Either a or b. E.g. <user>/{userinfo} ", inline=False)
            embed.add_field(name="[lit]", value="Something with a limited set of choices. See `help commandname`", inline=False)
            embed.add_field(name="<user>", value="Either an ID or a Mention of something. E.g. a @user", inline=False)
            embed.add_field(name="(optional)", value="Can leave this out", inline=False)
            embed.add_field(name="{json}", value="Json. No spaces please ;w;", inline=False)
            embed.add_field(name="*extra", value="Can put multiple of these. Spaces okay.", inline=False)

            return Response(embed=embed)

         if help_target not in authorized_cmds:
            return Response(f"No command or section `{help_target}` to show help for", status="error")

         # Help for Command
         cog, cmd = authorized_cmds[help_target]
         embed = discord.Embed(
            title=f"\U00002754 Command Help: {help_target}",
            description=cmd.description)

         embed.add_field(name="Usage", value=cmd.usage, inline=False)
         for arg, detail in cmd.param_usage:
            embed.add_field(name=arg.strip(), value=detail.strip(), inline=False)

         return Response(embed=embed)

   @property
   def default_auths(self) -> ty.List[Record]:
      return []
