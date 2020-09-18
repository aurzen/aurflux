import typing as ty

if ty.TYPE_CHECKING:
   if ty.TYPE_CHECKING:
      from .context import GuildMessageContext
      from .command import Response
      from auth import AuthAwareContext
      import aurcore as aur


   class CommandFunc(ty.Protocol):
      def __call__(self, msg_ctx: GuildMessageContext, auth_ctx: ty.Optional[AuthAwareContext] = None, cmd_args: str = None, **kwargs): ...


   ExtraCtxs: ty.TypeAlias = ty.Literal["auth"]
