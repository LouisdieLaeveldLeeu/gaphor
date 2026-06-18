"""Adapter-level tests for the M2 SysML layer: closure, supermodel, freshness.

The SysML user concepts (PartDefinition/PartUsage and their closure) are
generated from SysML.xmi and generalize KerML kernel classes via the KerML
supermodel (the two-level SysML2 -> KerML -> Core chain).
"""

from __future__ import annotations

from pathlib import Path

from gaphor.codegen.coder import main as coder_main
from gaphor.SysML2 import sysml2
from gaphor.SysML2.codegen import xmi_adapter

SYSML_XMI = Path("docs/sysml-v2/omg/20250201/SysML.xmi")
KERML_XMI = Path("docs/sysml-v2/omg/20250201/KerML.xmi")
SYSML_MODEL = Path("models/SysML2.gaphor")
SYSML_MODULE = Path(sysml2.__file__)


def test_sysml_closure_contains_the_tracer_pair():
    kernel = xmi_adapter.extract_sysml(SYSML_XMI)
    names = {c.name for c in kernel.classes}
    assert {"PartDefinition", "PartUsage"} <= names


def test_sysml_closure_contains_the_action_pair():
    kernel = xmi_adapter.extract_sysml(SYSML_XMI)
    names = {c.name for c in kernel.classes}
    assert {"ActionDefinition", "ActionUsage"} <= names


def test_action_classes_generalize_the_kerml_supermodel():
    # The faithful SysML -> KerML chain: ActionUsage is a KerML Feature; the
    # action definition reaches the kernel Element/Classifier roots.
    from gaphor.SysML2 import kerml

    assert issubclass(sysml2.ActionUsage, kerml.Feature)
    mro = [c.__name__ for c in sysml2.ActionUsage.__mro__]
    assert "OccurrenceUsage" in mro and "Usage" in mro and "Feature" in mro
    def_mro = [c.__name__ for c in sysml2.ActionDefinition.__mro__]
    assert "OccurrenceDefinition" in def_mro and "Element" in def_mro


def test_sysml_closure_contains_the_requirement_and_constraint_classes():
    kernel = xmi_adapter.extract_sysml(SYSML_XMI)
    names = {c.name for c in kernel.classes}
    assert {
        "ConstraintDefinition",
        "ConstraintUsage",
        "RequirementDefinition",
        "RequirementUsage",
    } <= names


def test_requirement_constraint_classes_generalize_the_kerml_supermodel():
    # RequirementUsage -> ConstraintUsage -> {OccurrenceUsage, BooleanExpression}
    # and RequirementDefinition -> ConstraintDefinition -> {OccurrenceDefinition,
    # Predicate}: the constraint expression supers (now in the kernel) are kept,
    # and the chain reaches the KerML Feature/Element spine.
    from gaphor.SysML2 import kerml

    assert issubclass(sysml2.RequirementUsage, sysml2.ConstraintUsage)
    assert issubclass(sysml2.RequirementDefinition, sysml2.ConstraintDefinition)
    assert issubclass(sysml2.ConstraintUsage, kerml.BooleanExpression)
    assert issubclass(sysml2.ConstraintUsage, kerml.Feature)
    assert issubclass(sysml2.ConstraintDefinition, kerml.Predicate)
    assert issubclass(sysml2.RequirementUsage, kerml.Feature)


def test_sysml_closure_contains_the_port_classes():
    kernel = xmi_adapter.extract_sysml(SYSML_XMI)
    names = {c.name for c in kernel.classes}
    assert {"PortDefinition", "PortUsage"} <= names


def test_port_classes_generalize_the_kerml_supermodel():
    # PortDefinition -> {Structure, OccurrenceDefinition}; PortUsage ->
    # OccurrenceUsage -> ... -> Feature. No kernel growth was needed (all supers
    # already present), and nothing is dropped.
    from gaphor.SysML2 import kerml

    assert issubclass(sysml2.PortDefinition, kerml.Structure)
    assert issubclass(sysml2.PortUsage, kerml.Feature)
    mro = [c.__name__ for c in sysml2.PortUsage.__mro__]
    assert "OccurrenceUsage" in mro and "Feature" in mro


def test_action_classes_keep_their_behavior_step_supers():
    # Regression: ActionDefinition -> Behavior and ActionUsage -> Step are real
    # KerML generalizations that were silently dropped before the kernel carried
    # Behavior/Step. With the kernel expanded (and the emitter fail-fast guard),
    # the faithful chain is preserved.
    from gaphor.SysML2 import kerml

    assert issubclass(sysml2.ActionDefinition, kerml.Behavior)
    assert issubclass(sysml2.ActionUsage, kerml.Step)


def test_part_classes_generalize_the_kerml_supermodel():
    # The faithful SysML -> KerML chain is preserved in the generated module.
    from gaphor.SysML2 import kerml
    from gaphor.core.modeling.base import Base

    assert issubclass(sysml2.PartDefinition, Base)
    assert issubclass(sysml2.PartUsage, kerml.Feature)
    mro = [c.__name__ for c in sysml2.PartUsage.__mro__]
    assert "Feature" in mro and "Element" in mro


def test_sysml_model_is_deterministic():
    supers = xmi_adapter.kerml_class_names(KERML_XMI)
    first = xmi_adapter.build_sysml_model(SYSML_XMI, supers)
    second = xmi_adapter.build_sysml_model(SYSML_XMI, supers)
    assert first == second


def test_committed_sysml_model_is_up_to_date():
    supers = xmi_adapter.kerml_class_names(KERML_XMI)
    regenerated = xmi_adapter.build_sysml_model(SYSML_XMI, supers)
    assert regenerated == SYSML_MODEL.read_text(encoding="utf-8"), (
        "models/SysML2.gaphor is stale; run `poe sysml2-model`."
    )


def test_committed_sysml_module_is_up_to_date(tmp_path):
    outfile = tmp_path / "sysml2.py"
    coder_main(
        modelfile=str(SYSML_MODEL),
        outfile=str(outfile),
        supermodelfiles=[
            ("KerML", "models/KerML.gaphor"),
            ("Core", "models/Core.gaphor"),
        ],
    )
    assert outfile.read_text(encoding="utf-8") == SYSML_MODULE.read_text(
        encoding="utf-8"
    ), "gaphor/SysML2/sysml2.py is stale; run `poe sysml2-classes`."
