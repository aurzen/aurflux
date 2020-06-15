import ast
import time

import contextlib
import datetime
import re

EMOJIS = {"white_check_mark": "\U00002705",
          "x"               : "\U0000274c",
          "trashcan":"\U0001f5d1",
          "question":"\U00002754"}


async def sexec(script: str, globals_=None, locals_=None):
    exec_context = {**globals_, **locals_}

    stmts = list(ast.iter_child_nodes(ast.parse(script)))
    if not stmts:
        return None
    if isinstance(stmts[-1], ast.Expr):
        if len(stmts) > 1:
            exec(compile(ast.Module(body=stmts[:-1], type_ignores=[]), filename="<ast>", mode="exec"), exec_context)
        return eval(compile(ast.Expression(body=stmts[-1].value), filename="<ast>", mode="eval"), exec_context)
    else:
        exec(script, globals_, locals_)


async def aexec(script: str, globals_=None, locals_=None):
    exec_context = {**globals_, **locals_}
    exec(
        f'async def __ex(): ' +
        ''.join(f'\n {l}' for l in script.split('\n')), exec_context
    )
    return await exec_context['__ex']()


def find_mentions(message_content):
    matches = re.findall(r"<#(\d+)>", message_content)
    return [int(x) for x in matches]


class Timer:
    def __enter__(self):
        self.elapsed = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = time.perf_counter() - self.elapsed
