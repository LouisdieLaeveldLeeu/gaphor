"""Adapter-level tests for the M1a generator path.

Covers three concerns the persist/reload spike does not:

- fail-fast: a requested class/attribute/reference that is missing or has the
  wrong shape must raise, never silently produce an incomplete slice;
- determinism: the emitted `.gaphor` model is byte-identical across runs;
- freshness: the committed `models/KerMLSlice.gaphor` and the coder-generated
  `gaphor/SysML2/kerml_slice.py` are both up to date with the source XMI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gaphor.codegen.coder import main as coder_main
from gaphor.SysML2 import kerml_slice
from gaphor.SysML2.codegen import xmi_adapter

KERML_XMI = Path("docs/sysml-v2/omg/20250201/KerML.xmi")
SLICE_MODEL = Path("models/KerMLSlice.gaphor")
GENERATED_MODULE = Path(kerml_slice.__file__)


# --- fail-fast (finding 1) ---------------------------------------------------


def test_extract_slice_raises_on_missing_class():
    with pytest.raises(ValueError, match="not found"):
        xmi_adapter.extract_slice(
            KERML_XMI, "NoSuchClass", attributes=[], references=[]
        )


def test_extract_slice_raises_on_missing_attribute():
    with pytest.raises(ValueError, match="missing attributes"):
        xmi_adapter.extract_slice(
            KERML_XMI,
            "Element",
            attributes=["declaredName", "noSuchAttribute"],
            references=[],
        )


def test_extract_slice_raises_on_missing_reference():
    with pytest.raises(ValueError, match="missing references"):
        xmi_adapter.extract_slice(
            KERML_XMI,
            "Element",
            attributes=[],
            references=["noSuchReference"],
        )


def test_extract_slice_raises_when_attribute_is_actually_a_reference():
    # `ownedElement` is a class-typed reference, not a primitive attribute.
    with pytest.raises(ValueError, match="misclassified"):
        xmi_adapter.extract_slice(
            KERML_XMI,
            "Element",
            attributes=["ownedElement"],
            references=[],
        )


def test_extract_slice_succeeds_for_the_known_slice():
    slice_ = xmi_adapter.extract_slice(
        KERML_XMI,
        "Element",
        attributes=["declaredName", "isLibraryElement"],
        references=["ownedElement"],
    )
    assert {a.name for a in slice_.attributes} == {"declaredName", "isLibraryElement"}
    assert {r.name for r in slice_.references} == {"ownedElement"}


# --- determinism (finding 2) -------------------------------------------------


def test_emitted_model_is_deterministic():
    first = xmi_adapter.build_kerml_element_slice(KERML_XMI)
    second = xmi_adapter.build_kerml_element_slice(KERML_XMI)
    assert first == second


# --- freshness (finding 3) ---------------------------------------------------


def test_committed_slice_model_is_up_to_date():
    regenerated = xmi_adapter.build_kerml_element_slice(KERML_XMI)
    assert regenerated == SLICE_MODEL.read_text(encoding="utf-8"), (
        "models/KerMLSlice.gaphor is stale; run `poe sysml2-slice-model`."
    )


def test_committed_generated_module_is_up_to_date(tmp_path):
    outfile = tmp_path / "kerml_slice.py"
    coder_main(
        modelfile=str(SLICE_MODEL),
        outfile=str(outfile),
        supermodelfiles=[("Core", "models/Core.gaphor")],
    )
    assert outfile.read_text(encoding="utf-8") == GENERATED_MODULE.read_text(
        encoding="utf-8"
    ), "gaphor/SysML2/kerml_slice.py is stale; run `poe sysml2-slice`."
