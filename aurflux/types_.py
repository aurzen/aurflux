import typing as ty

if ty.TYPE_CHECKING:
   if ty.TYPE_CHECKING:
      from .context import GuildMessageCtx, CommandCtx, AuthorAwareCtx
      from .command import Response
      from auth import AuthAwareCtx
      import aurcore as aur
      from .flux import FluxEvent


   class CommandFunc(ty.Protocol):
      def __call__(self, msg_ctx: GuildMessageCtx, auth_ctx: ty.Optional[AuthAwareCtx] = None, cmd_args: str = None, **kwargs): ...


   ExtraCtxs: ty.TypeAlias = ty.Literal["auth"]


   class GuildCommandCtx:
      msg_ctx: GuildMessageCtx
      author_ctx: AuthorAwareCtx
      auth_ctxs: ty.List[AuthAwareCtx]


   class CommandEvent(FluxEvent):
      cmd_name: str
      cmd_ctx: GuildCommandCtx
      cmd_args: ty.Optional[str]
