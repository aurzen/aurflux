from __future__ import annotations

class CommandException(BaseException):
   def __init__(self, message=None, *args):
      if message is not None:
         # clean-up @everyone and @here mentions
         m = message.replace('@everyone', '@\u200beveryone').replace('@here', '@\u200bhere')
         super().__init__(m, *args)
      else:
         super().__init__(*args)


class CommandInfo(CommandException):
   pass


class CommandError(CommandException):
   pass


class CheckFailure(CommandError):
   pass


class UserMissingPermissions(CheckFailure):
   def __init__(self, missing_perms, *args):
      self.missing_perms = missing_perms

      missing = [perm.replace('_', ' ').replace('guild', 'server').title() for perm in missing_perms]

      if len(missing) > 2:
         fmt = '{}, and {}'.format(", ".join(missing[:-1]), missing[-1])
      else:
         fmt = ' and '.join(missing)
      message = 'You are missing {} permission{} to run this command.'.format(fmt, "s" if len(missing) > 2 else "")
      super().__init__(message, *args)


class BotMissingPermissions(CheckFailure):
   def __init__(self, missing_perms, *args):
      self.missing_perms = missing_perms

      missing = [perm.replace('_', ' ').replace('guild', 'server').title() for perm in missing_perms]

      if len(missing) > 2:
         fmt = '{}, and {}'.format(", ".join(missing[:-1]), missing[-1])
      else:
         fmt = ' and '.join(missing)
      message = 'I am missing {} permission{} to run this command.'.format(fmt, "s" if len(missing) > 2 else "")
      super().__init__(message, *args)


class NotWhitelisted(CheckFailure):
   def __init__(self, *args):
      message = 'You are not whitelisted for this command.'
      super().__init__(message, *args)
