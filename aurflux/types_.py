import typing as ty

if ty.TYPE_CHECKING:
   if ty.TYPE_CHECKING:
      from .context import GuildMessageContext
      from .command import Response
      import aurcore as aur

   CommandFunc: ty.TypeAlias = ty.Callable[[GuildMessageContext, str], aur.util.AwaitableAiter]
