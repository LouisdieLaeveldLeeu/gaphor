"""Export semantic elements back to SysML v2 text.

Walks a namespace's members and re-emits valid SysML text: each definition
(part/attribute/action) stays a definition, each usage (part/attribute/action)
stays a usage (with its typing read back from its FeatureTyping), and a Package
re-emits as `package Name { ... }` with its members exported recursively and
indented. The output is re-parseable by `grammar.parser`, which the round-trip
harness relies on.
"""

from __future__ import annotations

from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk

_INDENT = "    "


def export_namespace(root: kerml.Namespace) -> str:
    """Render the members of `root` as SysML v2 text."""
    return "".join(_export_member(member, 0, root) for member in kk.members(root))


def _export_member(element: kerml.Element, depth: int, root: kerml.Namespace) -> str:
    pad = _INDENT * depth
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
    # RequirementDefinition is a ConstraintDefinition (-> `requirement def`), and
    # ConnectionDefinition is a PartDefinition (-> `connection def`), so the more
    # specific classes are checked first; likewise for the usages.
    if isinstance(element, sysml2.ConnectionDefinition):
        return f"{pad}connection def {element.declaredName};\n"
    if isinstance(element, sysml2.PartDefinition):
        return f"{pad}part def {element.declaredName};\n"
    if isinstance(element, sysml2.AttributeDefinition):
        return f"{pad}attribute def {element.declaredName};\n"
    if isinstance(element, sysml2.ActionDefinition):
        return f"{pad}action def {element.declaredName};\n"
    if isinstance(element, sysml2.RequirementDefinition):
        return f"{pad}requirement def {element.declaredName};\n"
    if isinstance(element, sysml2.ConstraintDefinition):
        return f"{pad}constraint def {element.declaredName};\n"
    if isinstance(element, sysml2.PortDefinition):
        return f"{pad}port def {element.declaredName};\n"
    if isinstance(element, sysml2.ConnectionUsage):
        return f"{pad}connection {_connection_decl(element, root)};\n"
    if isinstance(element, sysml2.PartUsage):
        return f"{pad}part {_usage_decl(element, root)};\n"
    if isinstance(element, sysml2.AttributeUsage):
        return f"{pad}attribute {_usage_decl(element, root)};\n"
    if isinstance(element, sysml2.ActionUsage):
        return f"{pad}action {_usage_decl(element, root)};\n"
    if isinstance(element, sysml2.RequirementUsage):
        return f"{pad}requirement {_usage_decl(element, root)};\n"
    if isinstance(element, sysml2.ConstraintUsage):
        return f"{pad}constraint {_usage_decl(element, root)};\n"
    if isinstance(element, sysml2.PortUsage):
        return f"{pad}port {_usage_decl(element, root)};\n"
    return ""


def _connection_decl(connection: kerml.Feature, root: kerml.Namespace) -> str:
    """`<name> [: <type>] [connect <end> to <end>]` for a ConnectionUsage.

    The connect clause is emitted only when both binary ends are present; each end
    is rendered as a name that re-resolves under the import rules (bare when the
    end feature is a member of the connection's own namespace, else the path from
    the export root).
    """
    decl = _usage_decl(connection, root)
    source = kk._single(connection.source)
    target = kk._single(connection.target)
    if source is not None and target is not None:
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
