from __future__ import annotations

import ast
async def sexec(script: str, globals_=None, locals_=None):
   exec_context = {**globals_, **locals_}

   stmts = list(ast.iter_child_nodes(ast.parse(script)))
   if not stmts:
      return None
   if isinstance(stmts[-1], ast.Expr):
      if len(stmts) > 1:
         exec(compile(ast.Module(body=stmts[:-1], type_ignores=[]), filename="<ast>", mode="exec"), exec_context)
      return eval(compile(ast.Expression(expr_body=stmts[-1].value), filename="<ast>", mode="eval"), exec_context)
   else:
      exec(script, globals_, locals_)


async def aexec(script: str, globals_=None, locals_=None):
   exec_context = {**globals_, **locals_}
   exec(
      f'async def __ex(): ' +
      ''.join(f'\n {l}' for l in script.split('\n')), exec_context
   )
   return await exec_context['__ex']()
