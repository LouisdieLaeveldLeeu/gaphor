"""SysML v2 diagram connectors.

A `FeatureTypingItem` is a VIEW onto an EXISTING `FeatureTyping` relation; it is
not a tool for editing which elements are typed (that is UI-edit, out of scope).
The generic relationship connector (`MetadataRelationConnect`, registered for any
ElementPresentation/LinePresentation) establishes a line's subject via
`relationship_or_new` -- find-or-CREATE -- which duplicates the typing on
connect, and base `disconnect_subject` deletes `line.subject`, so an ordinary
handle reconnect (disconnect then connect) would lose the subject and then
create a new one.

`FeatureTypingConnect` is registered more specifically for `FeatureTypingItem`
(wins by MRO) and makes the projected line's reconnect semantics explicit:

- it NEVER creates a relation for a projected line (`connect_subject` keeps the
  existing subject and does not fall back to find-or-create);
- a handle may only connect to the item whose subject is the typing's ACTUAL end
  (head -> typedFeature, tail -> type); dragging onto any other element is
  refused (`allow` returns False);
- a temporary disconnect preserves `line.subject` (the view survives detach).

So the line stays a faithful view of one existing relation: no duplicate, and no
silent model rewrite. Real relationship editing is left to a later UI-edit phase.
"""

from __future__ import annotations

from gaphor.diagram.connectors import Connector, MetadataRelationConnect
from gaphor.diagram.presentation import ElementPresentation
from gaphor.SysML2 import kerml
from gaphor.SysML2.diagramitems import FeatureTypingItem


@Connector.register(ElementPresentation, FeatureTypingItem)
class FeatureTypingConnect(MetadataRelationConnect):
    """Anchor a FeatureTyping line to its endpoint items as a view onto the
    existing typing -- reuse the subject, reject mismatched ends, never create."""

    def allow(self, handle, port):
        if not super().allow(handle, port):
            return False
        subject = self.line.subject
        if not isinstance(subject, kerml.FeatureTyping):
            # No existing typing to validate against -> defer to generic rules.
            return True
        target = self.element.subject
        if target is None:
            return True
        # The head must connect to the typing's typed feature; the tail to its
        # type. Anything else would make the view misrepresent the model.
        if handle is self.line.head:
            return target in list(subject.typedFeature)
        return target in list(subject.type)

    def connect_subject(self, handle):
        # A projected line already views an existing FeatureTyping. Keep it; do
        # NOT find-or-create (which would duplicate the relation on connect or
        # reconnect). For a line with no subject (e.g. drawn fresh rather than
        # projected) defer to the generic behaviour.
        if self.line.subject is not None:
            return True
        return super().connect_subject(handle)

    def disconnect_subject(self, handle):
        # Preserve the view's subject across a temporary disconnect (base would
        # `del self.line.subject`). The line keeps viewing the same typing while
        # a handle is detached, so a reconnect cannot fall into create-new.
        pass
