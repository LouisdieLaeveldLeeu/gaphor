"""Make the shared `element_factory`/dispatcher fixtures SysML2-aware.

The root conftest's `modeling_language` fixture omits SysML2, so creating a
SysML2Diagram + projection items through the event dispatcher would fail to resolve
the `SysML2` namespace. Override it to include KerML + SysML2 (plus the default
languages) so the synthesis service tests run against the real dispatch path.
"""

from __future__ import annotations

import pytest

from gaphor.core.modeling.modelinglanguage import (
    CoreModelingLanguage,
    MockModelingLanguage,
)
from gaphor.diagram.general.modelinglanguage import GeneralModelingLanguage
from gaphor.SysML2.modelinglanguage import (
    KerMLModelingLanguage,
    SysML2ModelingLanguage,
)


@pytest.fixture
def modeling_language():
    return MockModelingLanguage(
        CoreModelingLanguage(),
        GeneralModelingLanguage(),
        KerMLModelingLanguage(),
        SysML2ModelingLanguage(),
    )
