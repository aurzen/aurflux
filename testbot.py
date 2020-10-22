from __future__ import annotations

import typing as ty

import sys
# sys.path.append("..")

# __package__ = "aurflux"
import aurflux

from loguru import logger
logger.add("stdout", backtrace=True, diagnose=True)

# from .. import aurflux
import aurcore as aur
import TOKENS


class TestBot:
   def __init__(self):
      self.event_router = aur.EventRouterHost(name="triviabot")
      self.aurflux = aurflux.FluxClient("testbot", admin_id=TOKENS.ADMIN_ID, parent_router=self.event_router, builtins=True)

      # self.aurflux.router.endpoint(":ready")(lambda ev: print("Ready!"))

   async def startup(self, token: str):
      await self.aurflux.startup(token)

   async def shutdown(self):
      await self.aurflux.shutdown()
      await self.aurflux.aiohttp_session.close()


triviabot = TestBot()

aur.aiorun(triviabot.startup(token=TOKENS.TESTBOT), triviabot.shutdown())
