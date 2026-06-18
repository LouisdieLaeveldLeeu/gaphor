"""Parse SysML v2 text into the AST.

Uses Lark with the layered grammar in `sysml2.lark`. A `Transformer` lowers the
parse tree into the small AST in `ast.py`. Parse failures raise `SyntaxError`
with the offending location, so callers never get a partially-built AST.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from lark import Lark, Transformer
from lark.exceptions import LarkError

from gaphor.SysML2.grammar import ast

_GRAMMAR_PATH = Path(__file__).with_name("sysml2.lark")


class _ASTBuilder(Transformer):
    def NAME(self, token):
        return str(token)

    def qualified_name(self, names):
        return tuple(names)

    def type_ref(self, items):
        return items[0]

    def part_definition(self, items):
        (name,) = items
        return ast.PartDefinition(name=name)

    def part_usage(self, items):
        name = items[0]
        type_name = items[1] if len(items) > 1 else None
        return ast.PartUsage(name=name, type_name=type_name)

    def attribute_definition(self, items):
        (name,) = items
        return ast.AttributeDefinition(name=name)

    def attribute_usage(self, items):
        name = items[0]
        type_name = items[1] if len(items) > 1 else None
        return ast.AttributeUsage(name=name, type_name=type_name)

    def action_definition(self, items):
        (name,) = items
        return ast.ActionDefinition(name=name)

    def action_usage(self, items):
        name = items[0]
        type_name = items[1] if len(items) > 1 else None
        return ast.ActionUsage(name=name, type_name=type_name)

    def constraint_definition(self, items):
        (name,) = items
        return ast.ConstraintDefinition(name=name)

    def constraint_usage(self, items):
        name = items[0]
        type_name = items[1] if len(items) > 1 else None
        return ast.ConstraintUsage(name=name, type_name=type_name)

    def requirement_definition(self, items):
        (name,) = items
        return ast.RequirementDefinition(name=name)

    def requirement_usage(self, items):
        name = items[0]
        type_name = items[1] if len(items) > 1 else None
        return ast.RequirementUsage(name=name, type_name=type_name)

    def package_definition(self, items):
        name = items[0]
        members = items[1]  # package_body -> tuple
        return ast.PackageDefinition(name=name, members=members)

    def empty_package_definition(self, items):
        (name,) = items
        return ast.PackageDefinition(name=name, members=())

    def member(self, items):
        return items[0]

    def package_body(self, members):
        return tuple(members)

    def start(self, items):
        return ast.Package(members=items[0])


@lru_cache(maxsize=1)
def _parser() -> Lark:
    return Lark(
        _GRAMMAR_PATH.read_text(encoding="utf-8"),
        parser="lalr",
        transformer=_ASTBuilder(),
    )


def parse(text: str) -> ast.Package:
    """Parse SysML v2 source text into a `Package` AST.

    Raises `SyntaxError` on invalid input.
    """
    try:
        return _parser().parse(text)
    except LarkError as exc:
        raise SyntaxError(f"invalid SysML v2 text: {exc}") from exc
