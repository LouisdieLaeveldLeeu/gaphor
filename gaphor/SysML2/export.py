"""Export semantic elements back to SysML v2 text (M2 sub-step 5).

Walks a root namespace's members and re-emits valid SysML text for the tracer
slice: a PartDefinition stays a definition, a PartUsage stays a usage, and a
usage's typing (read back from its FeatureTyping) is preserved. The output is
re-parseable by `grammar.parser`, which the round-trip harness (sub-step 6)
relies on.
"""

from __future__ import annotations

from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk


def export_namespace(root: kerml.Namespace) -> str:
    """Render the members of `root` as SysML v2 text, one statement per line."""
    lines = [_export_member(member) for member in kk.members(root)]
    return "".join(f"{line}\n" for line in lines if line is not None)


def _export_member(element: kerml.Element) -> str | None:
    if isinstance(element, sysml2.PartDefinition):
        return f"part def {element.declaredName};"
    if isinstance(element, sysml2.PartUsage):
        type_name = _usage_type_name(element)
        if type_name is not None:
            return f"part {element.declaredName} : {type_name};"
        return f"part {element.declaredName};"
    return None


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
