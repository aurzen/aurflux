import typing as ty

if ty.TYPE_CHECKING:
   if ty.TYPE_CHECKING:
      from .context import GuildMessageCtx
      from .command import Response
      from auth import AuthAwareCtx
      import aurcore as aur


   class CommandFunc(ty.Protocol):
      def __call__(self, msg_ctx: GuildMessageCtx, auth_ctx: ty.Optional[AuthAwareCtx] = None, cmd_args: str = None, **kwargs): ...


   ExtraCtxs: ty.TypeAlias = ty.Literal["auth"]
