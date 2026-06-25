"""SysML v2 Systems Modeling API element serialization (completion-roadmap Phase 12).

A model -> the OMG Systems Modeling API element representation (JSON): every KerML
element as a payload with `@id` (its API-facing `elementId`), `@type` (the metaclass
name), and each STORED attribute and reference -- references rendered as `{"@id": ...}`
(or a list), exactly the API's element-by-id shape. This is a faithful dump of the
abstract syntax the model already holds; it introduces no new semantics.

The whole repository (every `kerml.Element` in the factory, including library proxies
and relationship/membership elements) is exported, so no `@id` reference dangles --
unlike the TEXTUAL export, which omits elements that have no human-readable form. Two
Gaphor-internal properties are not abstract syntax and are excluded: `elementId` (it
becomes `@id`) and `presentation` (the diagram back-reference).
"""

from __future__ import annotations

import json

from gaphor.core.modeling import Base, ElementFactory
from gaphor.core.modeling.collection import collection
from gaphor.SysML2 import kerml
from gaphor.SysML2.element_id import element_id

#: Metamodel identifier echoed in the API document header.
METAMODEL = "SysML2"

#: Properties excluded from the payload: `elementId` is surfaced as `@id`;
#: `presentation` is the diagram back-reference, not SysML abstract syntax.
_EXCLUDED = frozenset({"elementId", "presentation"})


def api_elements(factory: ElementFactory) -> list[dict]:
    """Every KerML element as an API element payload, deterministically ordered.

    Each element's `@id` is its `element_id` (an explicit override or its `Base.id`),
    so it is always present -- no minting pass is needed."""
    payloads = [_element_payload(element) for element in factory.select(kerml.Element)]
    return sorted(payloads, key=lambda payload: (payload["@type"], payload["@id"]))


def api_document(factory: ElementFactory) -> dict:
    """The API export document: a metamodel header plus the element payloads."""
    elements = api_elements(factory)
    return {"metamodel": METAMODEL, "elementCount": len(elements), "elements": elements}


def export_api_json(factory: ElementFactory) -> str:
    """The API document as pretty-printed JSON text."""
    return json.dumps(api_document(factory), indent=2) + "\n"


def _element_payload(element: kerml.Element) -> dict:
    payload: dict = {"@id": element_id(element), "@type": type(element).__name__}

    def collect(name: str, value: object) -> None:
        if name not in _EXCLUDED:
            payload[name] = _value(value)

    element.save(collect)
    return payload


def _value(value: object) -> object:
    if isinstance(value, kerml.Element):
        return {"@id": element_id(value)}
    if isinstance(value, Base):  # a non-SysML element (e.g. a Presentation) by Base.id
        return {"@id": value.id}
    if isinstance(value, collection):
        return [_value(item) for item in value]
    return value  # a scalar: str / bool / int / enum value
