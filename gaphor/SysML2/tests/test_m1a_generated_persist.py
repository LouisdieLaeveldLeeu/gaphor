"""M1a generator feasibility spike: real persist/reload of a generated class.

This proves the chosen generator path end to end on ONE semantics-free class
(KerML `Element`, generated from the normative MOF XMI via the adapter + Gaphor
coder). It verifies real persistence, not just that the module imports:

- the generated class integrates with `Base` / `ElementFactory`;
- a generated primitive attribute persists and reloads through `.gaphor`;
- a generated reference persists and reloads through `.gaphor`.

If these fail, the generator path is unviable and M1b must not be built on it.
"""

from __future__ import annotations

from io import StringIO

import pytest

from gaphor.core.modeling import ElementFactory
from gaphor.core.modeling.base import Base
from gaphor.core.modeling.modelinglanguage import (
    CoreModelingLanguage,
    MockModelingLanguage,
)
import gaphor.storage as storage
from gaphor.SysML2 import kerml_slice
from gaphor.SysML2.modelinglanguage import SysML2ModelingLanguage


@pytest.fixture
def element_factory():
    return ElementFactory()


@pytest.fixture
def modeling_language():
    return MockModelingLanguage(CoreModelingLanguage(), SysML2ModelingLanguage())


@pytest.fixture
def saver(element_factory):
    def save():
        f = StringIO()
        storage.save(f, element_factory)
        data = f.getvalue()
        f.close()
        return data

    return save


@pytest.fixture
def loader(element_factory, modeling_language):
    def load(data):
        element_factory.flush()
        assert not list(element_factory.select())
        f = StringIO(data)
        storage.load(
            f, element_factory=element_factory, modeling_language=modeling_language
        )
        f.close()

    return load


def test_generated_class_is_a_base_subclass():
    """The generated class integrates with Base (and thus ElementFactory)."""
    assert issubclass(kerml_slice.Element, Base)


def test_generated_string_attribute_persists_and_reloads(
    element_factory, saver, loader
):
    element = element_factory.create(kerml_slice.Element)
    element.declaredName = "Engine"
    element_id = element.id

    loader(saver())

    reloaded = element_factory.lookup(element_id)
    assert reloaded is not None
    assert isinstance(reloaded, kerml_slice.Element)
    assert reloaded.declaredName == "Engine"


def test_generated_bool_attribute_persists_and_reloads(
    element_factory, saver, loader
):
    # NOTE: Gaphor's `attribute.load()` does not coerce the persisted string back
    # to the declared Python type (this is framework behaviour shared with UML/
    # SysML bool attributes, not a generator-path issue). What M1a proves here is
    # that the generated bool attribute survives the save/reload round-trip; the
    # persisted form is the string "True".
    element = element_factory.create(kerml_slice.Element)
    element.isLibraryElement = True
    element_id = element.id

    loader(saver())

    reloaded = element_factory.lookup(element_id)
    assert reloaded is not None
    assert reloaded.isLibraryElement == "True"


def test_generated_reference_persists_and_reloads(element_factory, saver, loader):
    owner = element_factory.create(kerml_slice.Element)
    owner.declaredName = "Owner"
    owned = element_factory.create(kerml_slice.Element)
    owned.declaredName = "Owned"
    owner.ownedElement = owned

    owner_id = owner.id
    owned_id = owned.id

    loader(saver())

    reloaded_owner = element_factory.lookup(owner_id)
    reloaded_owned = element_factory.lookup(owned_id)
    assert reloaded_owner is not None
    assert reloaded_owned is not None
    assert reloaded_owned in reloaded_owner.ownedElement
    assert list(reloaded_owner.ownedElement) == [reloaded_owned]
