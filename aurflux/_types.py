from __future__ import annotations

import typing as ty
import re

if ty.TYPE_CHECKING:
    from .context import Context

ParsingType = ty.Literal["argparse", "basic"]

ContextFunction: ty.TypeAlias = ty.Callable[[Context, ...], ty.Awaitable]

DiscordListener: ty.TypeAlias = ty.Callable[..., ty.Awaitable]
