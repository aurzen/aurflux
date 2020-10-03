from __future__ import annotations

import typing as ty
import urllib.parse

if ty.TYPE_CHECKING:
   import aiohttp.client


async def haste(session: aiohttp.client.ClientSession, content: str):
   async with session.post("https://h.ze.ax/documents", data=content) as resp:
      return f"https://h.ze.ax/{(await resp.json(content_type=None))['key']}"


def copylink(to_copy: str, embed=True) -> str:
   link = f"https://x.ze.ax/copy?{urllib.parse.quote(to_copy)}"
   if embed:
      return f"[{to_copy}]({link})"
   else:
      return link
