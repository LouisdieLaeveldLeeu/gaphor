"""Stable SysML v2 API-facing element identity (completion-roadmap Phase 12).

The OMG Systems Modeling API & Services identifies each element by `elementId`, a UUID
that is the canonical identity in API payloads. KerML `Element` declares `elementId`
(generated from the normative XMI); rather than mint a PARALLEL repository id (which
the standing identity rule forbids, and which Gaphor offers no clean per-element
creation hook to assign), the API identity DEFAULTS to Gaphor's own creation-time
`Base.id`:

- present from CREATION and stable for the element's whole life (it IS `Base.id`,
  minted in `Base.__init__` and persisted) -- no late sweep, no path can persist an
  element without an API identity;
- IGNORED by round-trip / canonical equivalence, which stays purely structural;
- never part of the textual syntax (a fresh text import mints fresh `Base.id`s, the
  correct API semantic: ids are assigned on creation, not carried by the text).

The generated `elementId` attribute is the optional OVERRIDE slot: if a model carries
an explicitly-assigned API id (e.g. imported from an external OMG API repository), that
value wins; otherwise the identity is `Base.id`.
"""

from __future__ import annotations

from gaphor.SysML2 import kerml


def element_id(element: kerml.Element) -> str:
    """The element's API-facing `elementId`: an explicitly-assigned one if present,
    else Gaphor's creation-time `Base.id` (so every element has a stable API identity
    from creation, with no minting)."""
    return element.elementId or element.id
