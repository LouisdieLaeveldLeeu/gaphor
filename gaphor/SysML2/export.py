"""Export semantic elements back to SysML v2 text.

Walks a namespace's members and re-emits valid SysML text: each definition
(part/attribute/action) stays a definition, each usage (part/attribute/action)
stays a usage (with its typing read back from its FeatureTyping), and a Package
re-emits as `package Name { ... }` with its members exported recursively and
indented. The output is re-parseable by `grammar.parser`, which the round-trip
harness relies on.
"""

from __future__ import annotations

from gaphor.SysML2 import conjugation
from gaphor.SysML2 import constraints
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2 import requirements

_INDENT = "    "


def export_namespace(root: kerml.Namespace) -> str:
    """Render the members of `root` as SysML v2 text."""
    return "".join(_export_member(member, 0, root) for member in kk.members(root))


def _export_member(element: kerml.Element, depth: int, root: kerml.Namespace) -> str:
    pad = _INDENT * depth
    # A ConjugatedPortDefinition is the implicit conjugate of a PortDefinition; it
    # has no concrete syntax of its own (it surfaces only as `~Original` on a port
    # usage), so it is never emitted as a definition. It is also a PortDefinition,
    # so it must be skipped BEFORE the PortDefinition branch below.
    if isinstance(element, sysml2.ConjugatedPortDefinition):
        return ""
    # Package check first: PartDefinition/PartUsage are also Namespaces, but a
    # Package is the only member rendered as a nesting container.
    if isinstance(element, kerml.Package):
        inner = "".join(
            _export_member(m, depth + 1, root) for m in kk.members(element)
        )
        if inner:
            return f"{pad}package {element.declaredName} {{\n{inner}{pad}}}\n"
        return f"{pad}package {element.declaredName} {{ }}\n"
    # Definitions before usages, and the most-derived class before its bases:
    # RequirementDefinition is a ConstraintDefinition (-> `requirement def`),
    # ConnectionDefinition is a PartDefinition (-> `connection def`), and
    # InterfaceDefinition is a ConnectionDefinition (-> `interface def`), so the
    # more specific classes are checked first; likewise for the usages.
    if isinstance(element, sysml2.InterfaceDefinition):
        return f"{pad}interface def {element.declaredName};\n"
    if isinstance(element, sysml2.ConnectionDefinition):
        return f"{pad}connection def {element.declaredName};\n"
    if isinstance(element, sysml2.PartDefinition):
        return f"{pad}part def {element.declaredName};\n"
    if isinstance(element, sysml2.AttributeDefinition):
        return f"{pad}attribute def {element.declaredName};\n"
    if isinstance(element, sysml2.ActionDefinition):
        return f"{pad}action def {element.declaredName};\n"
    if isinstance(element, sysml2.RequirementDefinition):
        return (
            f"{pad}requirement def {element.declaredName}"
            f"{_requirement_tail(element, root)}\n"
        )
    if isinstance(element, sysml2.ConstraintDefinition):
        return f"{pad}constraint def {element.declaredName}{_constraint_tail(element)}\n"
    if isinstance(element, sysml2.PortDefinition):
        return f"{pad}port def {element.declaredName};\n"
    # Usages may carry a feature direction prefix (`in`/`out`/`inout`).
    if isinstance(element, sysml2.InterfaceUsage):
        dir_ = _direction_prefix(element)
        return f"{pad}{dir_}interface {_connection_decl(element, root)};\n"
    if isinstance(element, sysml2.ConnectionUsage):
        dir_ = _direction_prefix(element)
        return f"{pad}{dir_}connection {_connection_decl(element, root)};\n"
    if isinstance(element, sysml2.PartUsage):
        dir_ = _direction_prefix(element)
        return f"{pad}{dir_}part {_usage_decl(element, root)};\n"
    if isinstance(element, sysml2.AttributeUsage):
        dir_ = _direction_prefix(element)
        return f"{pad}{dir_}attribute {_usage_decl(element, root)};\n"
    if isinstance(element, sysml2.ActionUsage):
        dir_ = _direction_prefix(element)
        return f"{pad}{dir_}action {_usage_decl(element, root)};\n"
    if isinstance(element, sysml2.RequirementUsage):
        dir_ = _direction_prefix(element)
        return (
            f"{pad}{dir_}requirement {_usage_decl(element, root)}"
            f"{_requirement_tail(element, root)}\n"
        )
    if isinstance(element, sysml2.ConstraintUsage):
        dir_ = _direction_prefix(element)
        return (
            f"{pad}{dir_}constraint {_usage_decl(element, root)}"
            f"{_constraint_tail(element)}\n"
        )
    if isinstance(element, sysml2.PortUsage):
        dir_ = _direction_prefix(element)
        return f"{pad}{dir_}port {_usage_decl(element, root)};\n"
    return ""


def _requirement_tail(req: kerml.Element, root: kerml.Namespace) -> str:
    """` { subject ...; assume constraint {...} require constraint {...} }` for a
    requirement with parts, else `;` (Phase 6b).

    The subject's type and the assumed/required constraint bodies are re-emitted so
    the body re-parses to the same structure on round-trip.
    """
    parts: list[str] = []
    subj = requirements.subject(req)
    if subj is not None:
        type_name = _usage_type_name(subj, root)
        decl = (
            f"{subj.declaredName} : {type_name}"
            if type_name is not None
            else f"{subj.declaredName}"
        )
        parts.append(f"subject {decl};")
    for keyword, kind in (
        ("assume", requirements.Assumption),
        ("require", requirements.Requirement),
    ):
        for constraint in requirements.requirement_constraints(req, kind):
            parts.append(
                f"{keyword} constraint {{{constraints.body_text(constraint) or ''}}}"
            )
    if not parts:
        return ";"
    return " { " + " ".join(parts) + " }"


def _constraint_tail(constraint: kerml.Element) -> str:
    """` {<body>}` for a constraint with a preserved body, else `;` (Phase 6a).

    The inner body is re-injected VERBATIM between the braces, with NO added
    padding, so the exact preserved text (whitespace included) re-parses to the
    same body on round-trip.
    """
    body = constraints.body_text(constraint)
    return f" {{{body}}}" if body is not None else ";"


def _direction_prefix(usage: kerml.Feature) -> str:
    """`in `/`out `/`inout ` for a directed usage, else `""` (undirected).

    A usage's `direction` is the nullable KerML `Feature::direction`; `None`
    means undirected and emits no prefix (Phase 8b).
    """
    direction = usage.direction
    return f"{direction} " if direction is not None else ""


def _connection_decl(connection: kerml.Feature, root: kerml.Namespace) -> str:
    """`<name> [: <type>] [connect <end> to <end>]` for a ConnectionUsage.

    The connect clause is emitted only when both binary ends are present AND both
    are features -- the only ends with a valid textual form. A connection with a
    missing or non-feature end is an invalid model (reported by validation's
    `incomplete-connection` / `non-feature-connection-end` rules); rather than
    emit a clause the mapper would reject on re-import, the bare declaration is
    exported. Each end is rendered as a name that re-resolves under the import
    rules (bare when the end feature is a member of the connection's own
    namespace, else the path from the export root).
    """
    decl = _usage_decl(connection, root)
    source = kk._single(connection.source)
    target = kk._single(connection.target)
    if isinstance(source, kerml.Feature) and isinstance(target, kerml.Feature):
        return (
            f"{decl} connect {_end_name(connection, source, root)} "
            f"to {_end_name(connection, target, root)}"
        )
    return decl


def _end_name(
    connection: kerml.Feature, end: kerml.Element, root: kerml.Namespace
) -> str:
    owning = kk.owning_namespace(connection)
    if owning is not None and end in set(kk.members(owning)):
        return kk.effective_name(end)
    return _path_from_root(end, root)


def _usage_decl(usage: kerml.Feature, root: kerml.Namespace) -> str:
    """`<name>` or `<name> : <type>` for a usage (Part or Attribute)."""
    type_name = _usage_type_name(usage, root)
    if type_name is not None:
        return f"{usage.declaredName} : {type_name}"
    return f"{usage.declaredName}"


def _usage_type_name(usage: kerml.Feature, root: kerml.Namespace) -> str | None:
    """The type reference to emit for a usage, via its owned FeatureTyping.

    The emitted name must re-resolve under the import rules (simple name in the
    usage's own namespace, else a name qualified from the export root): a bare
    name when the type is a member of the usage's OWN namespace, otherwise the
    path from the export root down to the type. The path is computed relative to
    `root` by walking the ownership chain -- so it is correct whether or not the
    root is named (a named root must NOT prefix its own name; an unnamed root
    must NOT emit a leading `::`).
    """
    # A conjugated port typing (`: ~Fuel`) is rendered as `~<original>`, never as
    # the (unnamed, invisible) conjugate it actually points at.
    original = conjugation.conjugated_type_name(usage)
    if original is not None:
        owning = kk.owning_namespace(usage)
        if owning is not None and original in set(kk.members(owning)):
            return "~" + kk.effective_name(original)
        return "~" + _path_from_root(original, root)
    for relationship in usage.ownedRelationship:
        if isinstance(relationship, kerml.FeatureTyping):
            definition = kk._single(relationship.type)
            if definition is None:
                continue
            owning = kk.owning_namespace(usage)
            # Same-namespace: a bare name is sufficient and resolves locally.
            if owning is not None and definition in set(kk.members(owning)):
                return kk.effective_name(definition)
            return _path_from_root(definition, root)
    return None


def _path_from_root(element: kerml.Element, root: kerml.Namespace) -> str:
    """The `A::B::C` path from `root` (exclusive) down to `element`.

    Walks the owning-namespace chain from `element` up, stopping at `root`, so
    the result is independent of whether `root` is named.
    """
    segments: list[str] = []
    current: kerml.Element | None = element
    seen: set[str] = set()
    while current is not None and current.id != root.id:
        if current.id in seen:  # defensive against cycles
            break
        seen.add(current.id)
        name = kk.effective_name(current)
        segments.append(name if name is not None else "")
        current = kk.owning_namespace(current)
    return kk.QUALIFIED_NAME_SEPARATOR.join(reversed(segments))
