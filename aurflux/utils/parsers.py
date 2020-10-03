from __future__ import annotations

import re
import typing as ty


def find_mentions(message_content: str):
   matches = re.finditer(r"<?(@!|@|@&|#)?(\d{17,20})>?", message_content)
   return [int(x.group(2)) for x in matches]


def regex_parse(regex: re.Pattern, content: str, groups: ty.List[int]):
   group_tuple = regex.fullmatch(content).groups()
   return [group_tuple[i] for i in groups]
