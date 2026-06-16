"""Export semantic elements back to SysML v2 text.

Walks a namespace's members and re-emits valid SysML text: a PartDefinition
stays a definition, a PartUsage stays a usage (with its typing read back from
its FeatureTyping), and a Package re-emits as `package Name { ... }` with its
members exported recursively and indented. The output is re-parseable by
`grammar.parser`, which the round-trip harness relies on.
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
    if isinstance(element, sysml2.PartDefinition):
        return f"{pad}part def {element.declaredName};\n"
    if isinstance(element, sysml2.PartUsage):
        type_name = _usage_type_name(element, root)
        if type_name is not None:
            return f"{pad}part {element.declaredName} : {type_name};\n"
        return f"{pad}part {element.declaredName};\n"
    return ""


def _usage_type_name(usage: sysml2.PartUsage, root: kerml.Namespace) -> str | None:
    """The type reference to emit for a usage, via its owned FeatureTyping.

    The emitted name must re-resolve under the import rules (simple name in the
    usage's own namespace, else a root-relative qualified name): a bare name when
    the type is a member of the usage's OWN namespace, otherwise the type's
    qualified name with the implicit root prefix dropped (e.g. `A::Engine`), so a
    cross-package reference survives export -> re-import.
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
            # Otherwise emit the root-relative qualified name: the type's
            # qualified name with the implicit root segment dropped, since import
            # resolves a qualified name from the root's members.
            segments = kk.qualified_name(definition).split(
                kk.QUALIFIED_NAME_SEPARATOR
            )
            if (
                segments
                and kk.effective_name(root) is not None
                and segments[0] == kk.effective_name(root)
            ):
                segments = segments[1:]
            return kk.QUALIFIED_NAME_SEPARATOR.join(segments)
    return None
