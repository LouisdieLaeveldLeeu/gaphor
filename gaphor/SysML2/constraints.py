"""Constraint body preservation (Phase 6a).

A constraint body -- `constraint c { <expr> }` -- is preserved as OPAQUE text, not
parsed into a KerML expression tree. It is stored as a `TextualRepresentation`
(language `sysml`) owned by the constraint: the normative KerML carrier for "this
element's content represented as text in a named language". So the body
round-trips losslessly WITHOUT claiming any expression semantics (the faithful
expression tree -- operators as invocations of library functions -- is a later,
multi-phase dependency; the rows stay `alpha`).

The TextualRepresentation is owned through the ordinary OwningMembership spine
(there is no `Annotation` relationship class in the kernel closure yet), which is
enough to persist, cascade on delete, and round-trip; the faithful annotation
attachment is deferred with the expression tree.
"""

from __future__ import annotations

from gaphor.SysML2 import kerml
from gaphor.SysML2 import kerml_kernel as kk

# The language tag distinguishing a preserved SysML body from any other textual
# representation an element might carry.
BODY_LANGUAGE = "sysml"


def body_representation(
    element: kerml.Element,
) -> kerml.TextualRepresentation | None:
    """The TextualRepresentation carrying `element`'s constraint body, if any."""
    for member in kk.members(element):
        if (
            isinstance(member, kerml.TextualRepresentation)
            and member.language == BODY_LANGUAGE
        ):
            return member
    return None


def body_text(element: kerml.Element) -> str | None:
    """The preserved constraint body text of `element`, or None."""
    rep = body_representation(element)
    return rep.body if rep is not None else None


def set_body_text(
    element: kerml.Element, text: str | None
) -> kerml.TextualRepresentation | None:
    """Set (or, with `text=None`, clear) `element`'s preserved constraint body.

    Stores the text in an owned `TextualRepresentation` (language `sysml`),
    reusing an existing one. Clearing unlinks its owning membership (cascading the
    representation away) so no empty carrier lingers.
    """
    rep = body_representation(element)
    if text is None:
        if rep is not None:
            membership = kk._single(rep.owningRelationship)
            (membership or rep).unlink()
        return None

    if rep is None:
        factory = element.model
        rep = factory.create(kerml.TextualRepresentation)
        rep.language = BODY_LANGUAGE
        kk.add_owned_member(element, rep, factory.create(kerml.OwningMembership))
    rep.body = text
    return rep
