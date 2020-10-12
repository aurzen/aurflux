from __future__ import annotations
import typing as ty

if ty.TYPE_CHECKING:
   import discord

async def get_or_fetch_member(g: discord.Guild, m_id: int):
   return g.get_member(m_id) or await g.fetch_member(m_id)