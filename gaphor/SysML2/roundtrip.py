"""Round-trip harness + canonical form (M2 sub-step 6).

The harness is the project's coverage dashboard: it drives a construct through
the full chain and asserts the model is preserved by comparing *canonical
forms*, never raw text or element ids (invariant 6 / the round-trip rule).

Canonical form here is a structural fingerprint of a namespace: for each member,
its kind, effective (qualified) name, and -- for a usage -- the qualified name of
its resolved type. It deliberately ignores element ids, declaration order, and
textual formatting, so equivalence means "same semantic structure", not "same
bytes".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import StringIO

from gaphor.core.modeling import ElementFactory
from gaphor.core.modeling.modelinglanguage import (
    CoreModelingLanguage,
    MockModelingLanguage,
)
import gaphor.storage as storage
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.export import export_namespace
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.modelinglanguage import (
    KerMLModelingLanguage,
    SysML2ModelingLanguage,
)
from gaphor.SysML2.validation import Diagnostic, has_errors, validate


def canonical_form(root: kerml.Namespace) -> frozenset[tuple[str, ...]]:
    """A structural fingerprint of `root`, independent of ids/order/formatting."""
    entries: set[tuple[str, ...]] = set()
    for member in kk.members(root):
        if isinstance(member, sysml2.PartDefinition):
            entries.add(("PartDefinition", kk.qualified_name(member)))
        elif isinstance(member, sysml2.PartUsage):
            entries.add(
                (
                    "PartUsage",
                    kk.qualified_name(member),
                    _usage_type_qualified_name(member) or "",
                )
            )
    return frozenset(entries)


def _usage_type_qualified_name(usage: sysml2.PartUsage) -> str | None:
    for relationship in usage.ownedRelationship:
        if isinstance(relationship, kerml.FeatureTyping):
            definition = kk._single(relationship.type)
            if definition is not None:
                return kk.qualified_name(definition)
    return None


def _modeling_language() -> MockModelingLanguage:
    return MockModelingLanguage(
        CoreModelingLanguage(),
        KerMLModelingLanguage(),
        SysML2ModelingLanguage(),
    )


@dataclass
class RoundTripResult:
    source_form: frozenset[tuple[str, ...]]
    reloaded_form: frozenset[tuple[str, ...]]
    exported_text: str
    reexported_form: frozenset[tuple[str, ...]]
    # Diagnostics from validating the source model (before save). The harness
    # validates the reloaded model too and asserts it matches.
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def preserved(self) -> bool:
        return self.source_form == self.reloaded_form == self.reexported_form

    @property
    def valid(self) -> bool:
        return not has_errors(self.diagnostics)


def round_trip(text: str, root_name: str = "Root") -> RoundTripResult:
    """import -> validate -> save -> reload -> validate -> export -> re-parse.

    Compares canonical forms (structure, never ids/text) across the source,
    reloaded, and re-exported models, and runs validation on the source and the
    reloaded model -- asserting validation survives persistence too, so the
    harness exercises the full M2 chain (including validate), not just storage.
    """
    # import (text -> AST -> semantic model)
    factory = ElementFactory()
    result = map_package(parse(text), factory)
    result.root.declaredName = root_name
    source_form = canonical_form(result.root)
    source_diagnostics = validate(factory, result.unresolved_types)
    root_id = result.root.id

    # save -> reload through .gaphor
    f = StringIO()
    storage.save(f, factory)
    data = f.getvalue()
    factory.flush()
    storage.load(
        StringIO(data), element_factory=factory, modeling_language=_modeling_language()
    )
    reloaded_root = factory.lookup(root_id)
    assert isinstance(reloaded_root, kerml.Namespace)
    reloaded_form = canonical_form(reloaded_root)
    # Validate the reloaded (no mapping context) model: the model-derived rules
    # must reach the same verdict as the source, proving validation is not
    # dependent on transient mapping state.
    reloaded_diagnostics = validate(factory)
    assert has_errors(reloaded_diagnostics) == has_errors(source_diagnostics)

    # export -> re-parse -> re-map -> canonical form
    exported_text = export_namespace(reloaded_root)
    reexport_factory = ElementFactory()
    reexport_result = map_package(parse(exported_text), reexport_factory)
    reexport_result.root.declaredName = root_name
    reexported_form = canonical_form(reexport_result.root)

    return RoundTripResult(
        source_form=source_form,
        reloaded_form=reloaded_form,
        exported_text=exported_text,
        reexported_form=reexported_form,
        diagnostics=source_diagnostics,
    )
