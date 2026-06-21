"""Parse SysML v2 text into the AST.

Uses Lark with the layered grammar in `sysml2.lark`. A `Transformer` lowers the
parse tree into the small AST in `ast.py`. Parse failures raise `SyntaxError`
with the offending location, so callers never get a partially-built AST.
"""

from __future__ import annotations

from collections import namedtuple
from functools import lru_cache
from pathlib import Path

from lark import Lark, Token, Transformer
from lark.exceptions import LarkError, VisitError

from gaphor.SysML2 import shortnames
from gaphor.SysML2.grammar import ast

# Internal carrier so connection_usage can tell an optional connect-clause apart
# from an optional type_ref (both reduce to tuples otherwise).
_Connect = namedtuple("_Connect", "source target")


def _split_direction(items):
    """Pop a leading DIRECTION token (a usage's `in`/`out`/`inout` prefix).

    Returns `(direction, rest)`: the direction string (or None when absent) and
    the remaining items. The DIRECTION terminal is optional and only appears
    first, so the rest keeps the usage's existing positional layout.
    """
    if items and isinstance(items[0], Token) and items[0].type == "DIRECTION":
        return str(items[0]), items[1:]
    return None, items


def _split_short_name(items):
    """Pop a leading requirement short name (`<reqId>`). Returns `(reqId, rest)`."""
    if items and isinstance(items[0], _ShortName):
        return items[0].value, items[1:]
    return None, items

# Internal carrier for a port's `[~]<type>` reference: keeps the conjugation flag
# alongside the (qualified) type name through the transform.
_PortType = namedtuple("_PortType", "conjugated type_name")

# Internal carrier for a constraint body so it is distinguishable from an optional
# type_ref (a tuple) in the transform.
_Body = namedtuple("_Body", "text")

# Internal carriers for requirement-body clauses (Phase 6b), distinguished by
# type while collecting a requirement_body's children.
_Assume = namedtuple("_Assume", "body")
_Require = namedtuple("_Require", "body")
# Carrier for a whole requirement body, so it is distinguishable from an optional
# type_ref (a tuple) on a requirement usage.
_ReqBody = namedtuple("_ReqBody", "clauses")
# Carrier for a requirement short name (`<reqId>`), distinguishable from the
# NAME token (a Token is a str subclass, so a plain str would be ambiguous).
_ShortName = namedtuple("_ShortName", "value")


def _req_body_kwargs(body):
    """Return the requirement-body AST kwargs, shared by requirement AND concern
    nodes (a ConcernDefinition/Usage reuses the requirement body, Phase 6d).

    A requirement has a SINGLE subject (KerML `subjectParameter` is [0..1]), so a
    second `subject` clause is rejected rather than silently overwriting the first
    (no silent loss). `actor`/`stakeholder`/`frame` are ordered, so all are kept. A
    missing body yields no subject and empty tuples.
    """
    subject = None
    assume: list[str] = []
    require: list[str] = []
    actors: list = []
    stakeholders: list = []
    framed: list = []
    if body is not None:
        for clause in body.clauses:
            if isinstance(clause, ast.SubjectClause):
                if subject is not None:
                    raise SyntaxError("a requirement may declare at most one subject")
                subject = clause
            elif isinstance(clause, ast.ActorClause):
                actors.append(clause)
            elif isinstance(clause, ast.StakeholderClause):
                stakeholders.append(clause)
            elif isinstance(clause, (ast.FrameClause, ast.FrameReference)):
                framed.append(clause)
            elif isinstance(clause, _Assume):
                assume.append(clause.body)
            elif isinstance(clause, _Require):
                require.append(clause.body)
    return {
        "subject": subject,
        "assume": tuple(assume),
        "require": tuple(require),
        "actors": tuple(actors),
        "stakeholders": tuple(stakeholders),
        "framedConcerns": tuple(framed),
    }

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
        direction, items = _split_direction(items)
        name = items[0]
        type_name = items[1] if len(items) > 1 else None
        return ast.PartUsage(
            name=str(name), type_name=type_name, direction=direction, line=name.line
        )

    def attribute_definition(self, items):
        (name,) = items
        return ast.AttributeDefinition(name=str(name), line=name.line)

    def attribute_usage(self, items):
        direction, items = _split_direction(items)
        name = items[0]
        type_name = items[1] if len(items) > 1 else None
        return ast.AttributeUsage(
            name=str(name), type_name=type_name, direction=direction, line=name.line
        )

    def action_definition(self, items):
        (name,) = items
        return ast.ActionDefinition(name=str(name), line=name.line)

    def action_usage(self, items):
        direction, items = _split_direction(items)
        name = items[0]
        type_name = items[1] if len(items) > 1 else None
        return ast.ActionUsage(
            name=str(name), type_name=type_name, direction=direction, line=name.line
        )

    def constraint_body(self, items):
        # `{` body_element* `}` -- reassemble the inner text VERBATIM (opaque,
        # lossless). Each body_element is an inner-text piece: a BODY_TEXT run
        # (whitespace kept) or a nested `{...}` group with its braces re-added.
        # The outer braces are dropped; only the empty-check (on set / in
        # validation) treats a whitespace-only body as empty.
        return _Body("".join(items))

    def body_element(self, items):
        # A BODY_TEXT run (a str-subclass Token) or a nested braced_text (a str).
        return str(items[0])

    def braced_text(self, items):
        # A nested `{...}` group inside a body -- re-add its braces verbatim.
        return "{" + "".join(items) + "}"

    def constraint_definition(self, items):
        name = items[0]
        body = items[1].text if len(items) > 1 else None
        return ast.ConstraintDefinition(name=str(name), body=body, line=name.line)

    def constraint_usage(self, items):
        direction, items = _split_direction(items)
        name = items[0]
        type_name = None
        body = None
        for extra in items[1:]:
            if isinstance(extra, _Body):
                body = extra.text
            else:
                type_name = extra
        return ast.ConstraintUsage(
            name=str(name),
            type_name=type_name,
            direction=direction,
            body=body,
            line=name.line,
        )

    def short_name(self, items):
        # `<NAME>` or `<'quoted'>` -> the reqId string (quotes stripped, escapes
        # resolved). The encode/decode rules live in `shortnames`.
        return _ShortName(shortnames.decode(str(items[0])))

    def subject_clause(self, items):
        name = items[0]
        type_name = items[1] if len(items) > 1 else None
        return ast.SubjectClause(name=str(name), type_name=type_name)

    def actor_clause(self, items):
        name = items[0]
        type_name = items[1] if len(items) > 1 else None
        return ast.ActorClause(name=str(name), type_name=type_name)

    def stakeholder_clause(self, items):
        name = items[0]
        type_name = items[1] if len(items) > 1 else None
        return ast.StakeholderClause(name=str(name), type_name=type_name)

    def frame_declare(self, items):
        name = items[0]
        type_name = items[1] if len(items) > 1 else None
        return ast.FrameClause(name=str(name), type_name=type_name)

    def frame_reference(self, items):
        # `frame <qualified_name>` -> a reference to an existing concern.
        return ast.FrameReference(target=items[0])

    def assume_clause(self, items):
        return _Assume(items[0].text)

    def require_clause(self, items):
        return _Require(items[0].text)

    def requirement_clause(self, items):
        return items[0]

    def requirement_body(self, items):
        return _ReqBody(tuple(items))

    def requirement_definition(self, items):
        req_id, items = _split_short_name(items)
        name = items[0]
        body = items[1] if len(items) > 1 else None
        return ast.RequirementDefinition(
            name=str(name), reqId=req_id, line=name.line, **_req_body_kwargs(body)
        )

    def requirement_usage(self, items):
        direction, items = _split_direction(items)
        req_id, items = _split_short_name(items)
        name = items[0]
        type_name = None
        body = None
        for extra in items[1:]:
            if isinstance(extra, _ReqBody):
                body = extra
            else:
                type_name = extra
        return ast.RequirementUsage(
            name=str(name),
            type_name=type_name,
            direction=direction,
            reqId=req_id,
            line=name.line,
            **_req_body_kwargs(body),
        )

    def concern_definition(self, items):
        req_id, items = _split_short_name(items)
        name = items[0]
        body = items[1] if len(items) > 1 else None
        return ast.ConcernDefinition(
            name=str(name), reqId=req_id, line=name.line, **_req_body_kwargs(body)
        )

    def concern_usage(self, items):
        direction, items = _split_direction(items)
        req_id, items = _split_short_name(items)
        name = items[0]
        type_name = None
        body = None
        for extra in items[1:]:
            if isinstance(extra, _ReqBody):
                body = extra
            else:
                type_name = extra
        return ast.ConcernUsage(
            name=str(name),
            type_name=type_name,
            direction=direction,
            reqId=req_id,
            line=name.line,
            **_req_body_kwargs(body),
        )

    def port_definition(self, items):
        (name,) = items
        return ast.PortDefinition(name=str(name), line=name.line)

    def port_type_ref(self, items):
        # `["~"] type_ref` -> the carrier _PortType(conjugated, type_name). The
        # CONJUGATE token is present only for `~<type>`.
        conjugated = bool(items) and getattr(items[0], "type", None) == "CONJUGATE"
        type_name = items[-1]
        return _PortType(conjugated=conjugated, type_name=type_name)

    def port_usage(self, items):
        direction, items = _split_direction(items)
        name = items[0]
        port_type = items[1] if len(items) > 1 else None
        type_name = port_type.type_name if port_type is not None else None
        conjugated = port_type.conjugated if port_type is not None else False
        return ast.PortUsage(
            name=str(name),
            type_name=type_name,
            conjugated=conjugated,
            direction=direction,
            line=name.line,
        )

    def connection_definition(self, items):
        (name,) = items
        return ast.ConnectionDefinition(name=str(name), line=name.line)

    def connection_end(self, items):
        return items[0]  # qualified_name tuple

    def connect_clause(self, items):
        return _Connect(items[0], items[1])

    def connection_usage(self, items):
        direction, items = _split_direction(items)
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
            direction=direction,
            line=name.line,
        )

    def interface_definition(self, items):
        (name,) = items
        return ast.InterfaceDefinition(name=str(name), line=name.line)

    def interface_usage(self, items):
        direction, items = _split_direction(items)
        name = items[0]
        type_name = None
        source = target = None
        for extra in items[1:]:
            if isinstance(extra, _Connect):
                source, target = extra.source, extra.target
            else:
                type_name = extra
        return ast.InterfaceUsage(
            name=str(name),
            type_name=type_name,
            source=source,
            target=target,
            direction=direction,
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
    except VisitError as exc:
        # A transformer raised (e.g. a semantic constraint like "at most one
        # subject"). Surface its own SyntaxError message rather than Lark's
        # wrapper.
        if isinstance(exc.orig_exc, SyntaxError):
            raise exc.orig_exc from None
        raise SyntaxError(f"invalid SysML v2 text: {exc}") from exc
    except LarkError as exc:
        raise SyntaxError(f"invalid SysML v2 text: {exc}") from exc
