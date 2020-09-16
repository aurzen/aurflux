from __future__ import annotations

import typing as ty
import aurflux
import aurcore as aur
import TOKENS


class TestBot:
   def __init__(self):
      self.event_router = aur.EventRouterHost(name="triviabot")
      self.aurflux = aurflux.FluxClient("triviabot", admin_id=TOKENS.ADMIN_ID, parent_router=self.event_router, builtins=False)

      # self.aurflux.router.endpoint(":ready")(lambda ev: print("Ready!"))

   async def startup(self, token: str):
      await self.aurflux.startup(token)

   async def shutdown(self):
      await self.aurflux.shutdown()


triviabot = TestBot()

aur.aiorun(triviabot.startup(token=TOKENS.TESTBOT), triviabot.shutdown())
