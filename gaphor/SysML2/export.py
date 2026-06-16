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
    return "".join(_export_member(member, 0) for member in kk.members(root))


def _export_member(element: kerml.Element, depth: int) -> str:
    pad = _INDENT * depth
    # Package check first: PartDefinition/PartUsage are also Namespaces, but a
    # Package is the only member rendered as a nesting container.
    if isinstance(element, kerml.Package):
        inner = "".join(
            _export_member(m, depth + 1) for m in kk.members(element)
        )
        if inner:
            return f"{pad}package {element.declaredName} {{\n{inner}{pad}}}\n"
        return f"{pad}package {element.declaredName} {{ }}\n"
    if isinstance(element, sysml2.PartDefinition):
        return f"{pad}part def {element.declaredName};\n"
    if isinstance(element, sysml2.PartUsage):
        type_name = _usage_type_name(element)
        if type_name is not None:
            return f"{pad}part {element.declaredName} : {type_name};\n"
        return f"{pad}part {element.declaredName};\n"
    return ""


def _usage_type_name(usage: sysml2.PartUsage) -> str | None:
    """The declared type name of a usage, via its owned FeatureTyping.

    Reads the typing from the usage's owned relationships (the same containment
    spine the mapper wired), so export does not depend on a separate index.
    """
    for relationship in usage.ownedRelationship:
        if isinstance(relationship, kerml.FeatureTyping):
            definition = kk._single(relationship.type)
            if definition is not None:
                return kk.effective_name(definition)
    return None
