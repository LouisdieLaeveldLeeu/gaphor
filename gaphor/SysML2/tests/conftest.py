"""Shared fixtures for SysML2 tests: a headless ElementFactory + save/reload."""

from __future__ import annotations

from io import StringIO

import pytest

from gaphor.core.modeling import ElementFactory
from gaphor.core.modeling.modelinglanguage import (
    CoreModelingLanguage,
    MockModelingLanguage,
)
import gaphor.storage as storage
from gaphor.SysML2.modelinglanguage import (
    KerMLModelingLanguage,
    SysML2ModelingLanguage,
)


@pytest.fixture
def element_factory():
    return ElementFactory()


@pytest.fixture
def modeling_language():
    return MockModelingLanguage(
        CoreModelingLanguage(),
        KerMLModelingLanguage(),
        SysML2ModelingLanguage(),
    )


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
