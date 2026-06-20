"""Parse SysML v2 text into the AST.

Uses Lark with the layered grammar in `sysml2.lark`. A `Transformer` lowers the
parse tree into the small AST in `ast.py`. Parse failures raise `SyntaxError`
with the offending location, so callers never get a partially-built AST.
"""

from __future__ import annotations

from collections import namedtuple
from functools import lru_cache
from pathlib import Path

from lark import Lark, Transformer
from lark.exceptions import LarkError

from gaphor.SysML2.grammar import ast

# Internal carrier so connection_usage can tell an optional connect-clause apart
# from an optional type_ref (both reduce to tuples otherwise).
_Connect = namedtuple("_Connect", "source target")

_GRAMMAR_PATH = Path(__file__).with_name("sysml2.lark")


class _ASTBuilder(Transformer):
    # NAME tokens are kept as Lark Tokens (a str subclass) so each construct can
    # read the declaration's source `.line` for provenance; they are converted to
    # plain `str` here where they become AST values.
    def qualified_name(self, names):
        return tuple(str(name) for name in names)

    def type_ref(self, items):
        return items[0]

    def part_definition(self, items):
        (name,) = items
        return ast.PartDefinition(name=str(name), line=name.line)

    def part_usage(self, items):
        name = items[0]
        type_name = items[1] if len(items) > 1 else None
        return ast.PartUsage(name=str(name), type_name=type_name, line=name.line)

    def attribute_definition(self, items):
        (name,) = items
        return ast.AttributeDefinition(name=str(name), line=name.line)

    def attribute_usage(self, items):
        name = items[0]
        type_name = items[1] if len(items) > 1 else None
        return ast.AttributeUsage(name=str(name), type_name=type_name, line=name.line)

    def action_definition(self, items):
        (name,) = items
        return ast.ActionDefinition(name=str(name), line=name.line)

    def action_usage(self, items):
        name = items[0]
        type_name = items[1] if len(items) > 1 else None
        return ast.ActionUsage(name=str(name), type_name=type_name, line=name.line)

    def constraint_definition(self, items):
        (name,) = items
        return ast.ConstraintDefinition(name=str(name), line=name.line)

    def constraint_usage(self, items):
        name = items[0]
        type_name = items[1] if len(items) > 1 else None
        return ast.ConstraintUsage(name=str(name), type_name=type_name, line=name.line)

    def requirement_definition(self, items):
        (name,) = items
        return ast.RequirementDefinition(name=str(name), line=name.line)

    def requirement_usage(self, items):
        name = items[0]
        type_name = items[1] if len(items) > 1 else None
        return ast.RequirementUsage(name=str(name), type_name=type_name, line=name.line)

    def port_definition(self, items):
        (name,) = items
        return ast.PortDefinition(name=str(name), line=name.line)

    def port_usage(self, items):
        name = items[0]
        type_name = items[1] if len(items) > 1 else None
        return ast.PortUsage(name=str(name), type_name=type_name, line=name.line)

    def connection_definition(self, items):
        (name,) = items
        return ast.ConnectionDefinition(name=str(name), line=name.line)

    def connection_end(self, items):
        return items[0]  # qualified_name tuple

    def connect_clause(self, items):
        return _Connect(items[0], items[1])

    def connection_usage(self, items):
        name = items[0]
        type_name = None
        source = target = None
        for extra in items[1:]:
            if isinstance(extra, _Connect):
                source, target = extra.source, extra.target
            else:
                type_name = extra
        return ast.ConnectionUsage(
            name=str(name),
            type_name=type_name,
            source=source,
            target=target,
            line=name.line,
        )

    def package_definition(self, items):
        name = items[0]
        members = items[1]  # package_body -> tuple
        return ast.PackageDefinition(name=str(name), members=members, line=name.line)

    def empty_package_definition(self, items):
        (name,) = items
        return ast.PackageDefinition(name=str(name), members=(), line=name.line)

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
