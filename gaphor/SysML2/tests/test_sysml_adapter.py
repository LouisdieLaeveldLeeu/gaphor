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
