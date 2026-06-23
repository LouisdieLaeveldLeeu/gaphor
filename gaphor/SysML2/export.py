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
from gaphor.SysML2 import kerml, shortnames, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2 import requirements

_INDENT = "    "


def export_namespace(root: kerml.Namespace) -> str:
    """Render the members of `root` as SysML v2 text."""
    return _export_members(root, 0, root)


def _export_members(
    namespace: kerml.Namespace, depth: int, root: kerml.Namespace
) -> str:
    """A namespace body: its imports, then its owned members and aliases (Phase 5b).

    Owned members are rendered by kind; an alias is rendered as `alias N for path;`
    (NOT by re-rendering its foreign target). Both are produced from the namespace's
    memberships in declaration order so the body keeps its source order.
    """
    out = [_export_imports(namespace, depth, root)]
    for membership in kk.owned_memberships(namespace):
        if isinstance(membership, kerml.OwningMembership):
            member = kk._single(membership.memberElement)
            if member is not None:
                out.append(_export_member(member, depth, root))
        elif kk.is_alias(membership):
            out.append(_export_alias(membership, depth, root))
    return "".join(out)


def _export_alias(
    membership: kerml.Membership, depth: int, root: kerml.Namespace
) -> str:
    """`[private ]alias <name> for <path>;` for an alias, or `""` when unresolved.

    The member default is public, so only a private alias emits a prefix; an
    unresolved alias (no target) has no textual form and is skipped (validation's
    unresolved-alias rule reports it), mirroring an unresolved import (Phase 5b)."""
    target = kk._single(membership.memberElement)
    if target is None:
        return ""
    pad = _INDENT * depth
    prefix = (
        "private "
        if membership.visibility == kerml.VisibilityKind.private
        else ""
    )
    return (
        f"{pad}{prefix}alias {membership.memberName} for "
        f"{_path_from_root(target, root)};\n"
    )


def _export_member(element: kerml.Element, depth: int, root: kerml.Namespace) -> str:
    """A member line, prefixed with `private ` when its membership is private (the
    member default is public, so only private is emitted) (Phase 5a)."""
    line = _export_member_line(element, depth, root)
    if line and _member_visibility(element) == kerml.VisibilityKind.private:
        pad = _INDENT * depth
        return f"{pad}private {line[len(pad):]}"
    return line


def _member_visibility(element: kerml.Element) -> kerml.VisibilityKind | None:
    membership = kk._single(element.owningRelationship)
    return membership.visibility if membership is not None else None


def _export_imports(
    namespace: kerml.Namespace, depth: int, root: kerml.Namespace
) -> str:
    pad = _INDENT * depth
    out = []
    for relationship in namespace.ownedRelationship:
        if isinstance(relationship, kerml.Import):
            decl = _import_decl(relationship, root)
            if decl:
                out.append(f"{pad}{decl}\n")
    return "".join(out)


def _import_decl(imp: kerml.Import, root: kerml.Namespace) -> str:
    """`[public ]import <path>[::*];` for an import, or `""` when unresolved.

    The import default is PRIVATE, so only a `public` import emits a prefix; an
    unresolved import (no target) has no textual form and is skipped (validation's
    unresolved-import rule reports it), mirroring a broken connector end."""
    target = kk._single(imp.target)
    if target is None:
        return ""
    prefix = "public " if imp.visibility == kerml.VisibilityKind.public else ""
    star = "::*" if kk.is_import_all(imp) else ""
    return f"{prefix}import {_path_from_root(target, root)}{star};"


def _export_member_line(
    element: kerml.Element, depth: int, root: kerml.Namespace
) -> str:
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
        inner = _export_members(element, depth + 1, root)
        if inner:
            return f"{pad}package {element.declaredName} {{\n{inner}{pad}}}\n"
        return f"{pad}package {element.declaredName} {{ }}\n"
    # Definitions before usages, and the most-derived class before its bases:
    # ConcernDefinition is a RequirementDefinition (-> `concern def`),
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
        return f"{pad}action def {element.declaredName}{_action_body(element, depth, root)}\n"
    if isinstance(element, sysml2.ConcernDefinition):
        return (
            f"{pad}concern def {_short_name_prefix(element)}{element.declaredName}"
            f"{_requirement_tail(element, root)}\n"
        )
    if isinstance(element, sysml2.RequirementDefinition):
        return (
            f"{pad}requirement def {_short_name_prefix(element)}{element.declaredName}"
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
    # FlowUsage IS an ActionUsage and SuccessionAsUsage IS a ConnectorAsUsage; both
    # are binary connectors, checked BEFORE ActionUsage so a flow is not emitted as
    # a plain action (Phase 7). A broken/incomplete connector has no valid textual
    # form, so it is skipped (validation reports it), mirroring connections.
    if isinstance(element, sysml2.FlowUsage):
        return _connector_line(element, "flow", "from", "to", pad, root)
    if isinstance(element, sysml2.SuccessionAsUsage):
        return _connector_line(element, "succession", "first", "then", pad, root)
    if isinstance(element, sysml2.ActionUsage):
        dir_ = _direction_prefix(element)
        return (
            f"{pad}{dir_}action {_usage_decl(element, root)}"
            f"{_action_body(element, depth, root)}\n"
        )
    if isinstance(element, sysml2.ConcernUsage):
        dir_ = _direction_prefix(element)
        return (
            f"{pad}{dir_}concern {_short_name_prefix(element)}"
            f"{_usage_decl(element, root)}"
            f"{_requirement_tail(element, root)}\n"
        )
    if isinstance(element, sysml2.RequirementUsage):
        dir_ = _direction_prefix(element)
        return (
            f"{pad}{dir_}requirement {_short_name_prefix(element)}"
            f"{_usage_decl(element, root)}"
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


def _action_body(action: kerml.Element, depth: int, root: kerml.Namespace) -> str:
    """` { <members> }` for an action with body members, else `;` (Phase 7).

    The body members are the action's FEATURES (steps, directed parameters,
    successions, flows); each is re-exported recursively at one deeper indent. An
    action with no members renders `;` (an empty `{ }` body carries no semantics and
    is not distinguished from none)."""
    pad = _INDENT * depth
    inner = _export_members(action, depth + 1, root)
    return f" {{\n{inner}{pad}}}" if inner else ";"


def _connector_line(
    connector: kerml.Feature,
    keyword: str,
    src_kw: str,
    tgt_kw: str,
    pad: str,
    root: kerml.Namespace,
) -> str:
    """`<keyword> [<name>] <src_kw> <end> <tgt_kw> <end>;` for a binary connector
    usage (succession / flow), or `""` when an end is missing or non-feature.

    A one-ended/broken connector has no valid textual form, so it is skipped
    (validation's incomplete/non-feature rules report it) rather than emitted as
    invalid text -- mirroring a broken connection's connect clause (Phase 7)."""
    source = kk._single(connector.source)
    target = kk._single(connector.target)
    if not (isinstance(source, kerml.Feature) and isinstance(target, kerml.Feature)):
        return ""
    name = f"{connector.declaredName} " if connector.declaredName else ""
    return (
        f"{pad}{keyword} {name}{src_kw} {_end_name(connector, source, root)} "
        f"{tgt_kw} {_end_name(connector, target, root)};\n"
    )


def _short_name_prefix(req: kerml.Element) -> str:
    """`<reqId> ` for a requirement with a reqId (declaredShortName), else `""`.

    The reqId is encoded as a bare `<id>` when it is a valid identifier, else as a
    quoted, escaped `<'id'>` (e.g. a dotted `1.1.3`, or one containing a quote or
    backslash), so it re-parses to the same value (Phase 6c). Encoding rules live
    in `shortnames`.
    """
    value = requirements.reqId(req)
    if not value:
        return ""
    return f"<{shortnames.encode(value)}> "


def _requirement_tail(req: kerml.Element, root: kerml.Namespace) -> str:
    """` { subject ...; actor ...; stakeholder ...; frame concern ...;
    assume constraint {...} require constraint {...} }` for a requirement (or
    concern) with parts, else `;` (Phase 6b/6c/6d).

    The subject/actor/stakeholder/frame types and the assumed/required constraint
    bodies are re-emitted so the body re-parses to the same structure on
    round-trip. Shared by requirements AND concerns (a ConcernDefinition/Usage IS a
    RequirementDefinition/Usage).
    """
    parts: list[str] = []
    subj = requirements.subject(req)
    if subj is not None:
        parts.append(f"subject {_parameter_decl(subj, root)};")
    for keyword, features in (
        ("actor", requirements.actors(req)),
        ("stakeholder", requirements.stakeholders(req)),
    ):
        for feature in features:
            parts.append(f"{keyword} {_parameter_decl(feature, root)};")
    for concern in requirements.framed_concerns(req):
        referenced = requirements.framed_concern_reference(concern)
        if referenced is not None:
            # REFERENCE form (`frame <existing>`): a well-formed anonymous usage
            # referencing an existing concern (the shared predicate also enforces
            # anonymity/untyped); emit a name that re-resolves.
            parts.append(f"frame {_end_name(req, referenced, root)};")
        elif concern.declaredName and not requirements.is_referencing_frame(concern):
            # DECLARE form (`frame concern <name> [: <C>]`).
            parts.append(f"frame concern {_parameter_decl(concern, root)};")
        # else: a broken framed concern -- an unresolved `frame <ref>` (anonymous,
        # no subsetting), a reference that does not target a ConcernUsage, or a mixed
        # declare+reference state (a named usage that also owns a subsetting) -- is
        # reported by validation and NOT re-emitted as invalid/lossy text (mirrors a
        # broken connect clause / unresolved usage type).
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


def _parameter_decl(feature: kerml.Feature, root: kerml.Namespace) -> str:
    """`<name>` or `<name> : <type>` for a requirement parameter (subject/actor/
    stakeholder) feature, re-emitting its declared type when present."""
    type_name = _usage_type_name(feature, root)
    if type_name is not None:
        return f"{feature.declaredName} : {type_name}"
    return f"{feature.declaredName}"


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
