"""Short-name (`reqId`) quoting for the SysML v2 textual surface.

A KerML short name `<...>` is written either as a bare identifier (`<R1>`) or as a
single-quoted unrestricted name (`<'1.1.3'>`, `<'A\\'B'>`). This module is the
SINGLE place that knows the quoting/escaping rules, shared by the parser (decode
on read) and the exporter (encode on write) so the two can never drift.

Escaping is intentionally minimal and lossless: inside the quotes, a backslash is
written `\\\\` and a single quote `\\'`; the grammar's `QUOTED_NAME` accepts ONLY
those two escape sequences, so every value (including quotes, backslashes, spaces,
and dots) round-trips, and a stray/unterminated escape is a parse error rather
than silently corrupted text. No other backslash sequence is interpreted.
"""

from __future__ import annotations

import re

_IDENTIFIER = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")


def encode(value: str) -> str:
    """Render `value` as the inner text of a `<...>` short name.

    A value that is a bare identifier is returned as-is; anything else is
    single-quoted with `\\` and `'` escaped.
    """
    if _IDENTIFIER.fullmatch(value):
        return value
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def decode(token_text: str) -> str:
    """Decode a `short_name` token's text (a bare NAME or a quoted name) to its
    value. A quoted token has its surrounding quotes stripped and its `\\'`/`\\\\`
    escapes resolved; the grammar guarantees a backslash is always followed by `'`
    or `\\`."""
    if not (token_text.startswith("'") and token_text.endswith("'")):
        return token_text
    inner = token_text[1:-1]
    out: list[str] = []
    i = 0
    while i < len(inner):
        if inner[i] == "\\":
            out.append(inner[i + 1])
            i += 2
        else:
            out.append(inner[i])
            i += 1
    return "".join(out)
