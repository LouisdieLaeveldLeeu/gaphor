"""Stable SysML v2 API-facing element identity (completion-roadmap Phase 12).

The OMG Systems Modeling API & Services identifies each element by `elementId`, a
UUID that is the canonical identity in API payloads. KerML `Element` already declares
`elementId` (generated from the normative XMI); this module POPULATES it:

- minted once at element CREATION (the mapper, via `assign_element_ids`) and persisted
  into `.gaphor`, so it is STABLE across save/reload;
- a fresh UUID, kept DISTINCT from Gaphor's internal `Base.id` (the standing identity
  rule: the repository id and the API id are separate concepts);
- IGNORED by round-trip / canonical equivalence, which stays purely structural -- so
  two models with the same structure but different elementIds still round-trip;
- never part of the textual syntax (text import mints fresh ids; there is no `<id>`
  surface), which is the correct API semantic: ids are assigned on creation, not
  carried by the human-readable text.

`assign_element_ids` is idempotent, so a reloaded model keeps its persisted ids.
"""

from __future__ import annotations

import uuid

from gaphor.core.modeling import ElementFactory
from gaphor.SysML2 import kerml


def element_id(element: kerml.Element) -> str:
    """The element's API-facing `elementId`, minting + persisting one if unset."""
    if not element.elementId:
        element.elementId = str(uuid.uuid4())
    return element.elementId


def assign_element_ids(factory: ElementFactory) -> int:
    """Ensure every KerML element in `factory` has an `elementId` (mint-if-missing).

    Idempotent -- an element that already has one keeps it, so ids are stable across
    save/reload and re-resolution. Returns the count newly minted."""
    minted = 0
    for element in factory.select(kerml.Element):
        if not element.elementId:
            element.elementId = str(uuid.uuid4())
            minted += 1
    return minted
