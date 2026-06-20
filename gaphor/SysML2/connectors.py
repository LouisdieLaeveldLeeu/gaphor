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

from gaphas.connector import ConnectionSink
from gaphas.connector import Connector as ConnectorAspect

from gaphor.diagram.connectors import Connector, MetadataRelationConnect
from gaphor.diagram.presentation import ElementPresentation
from gaphor.SysML2 import kerml
from gaphor.SysML2.diagramitems import ConnectionUsageItem, FeatureTypingItem


@Connector.register(ElementPresentation, FeatureTypingItem)
class FeatureTypingConnect(MetadataRelationConnect):
    """Anchor a FeatureTyping line to its endpoint items as a view onto the
    existing typing -- reuse the subject, reject mismatched ends, never create."""

    def _actual_end_subjects(self, handle):
        subject = self.line.subject
        if not isinstance(subject, kerml.FeatureTyping):
            return None
        if handle is self.line.head:
            return list(subject.typedFeature)
        return list(subject.type)

    def _is_actual_endpoint(self, handle):
        target = self.element.subject
        if target is None:
            return True
        expected = self._actual_end_subjects(handle)
        return expected is None or target in expected

    def _actual_endpoint_item(self, handle):
        expected = self._actual_end_subjects(handle)
        if not expected:
            return None
        for subject in expected:
            for item in subject.presentation:
                if item.diagram is self.diagram:
                    return item
        return None

    def _restore_actual_endpoint(self, handle):
        item = self._actual_endpoint_item(handle)
        if item is None:
            return

        connector = ConnectorAspect(self.line, handle, self.diagram.connections)
        sink = ConnectionSink(item, distance=float("inf"))
        if self.diagram.connections.get_connection(handle):
            connector.disconnect_handle()
        connector.glue(sink)
        if sink.port:
            connector.connect_handle(sink)

    def allow(self, handle, port):
        if not super().allow(handle, port):
            return False
        # The head must connect to the typing's typed feature; the tail to its
        # type. Anything else would make the view misrepresent the model.
        return self._is_actual_endpoint(handle)

    def connect(self, handle, port):
        if not self._is_actual_endpoint(handle):
            self._restore_actual_endpoint(handle)
            return False
        return super().connect(handle, port)

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


@Connector.register(ElementPresentation, ConnectionUsageItem)
class ConnectionUsageConnect(MetadataRelationConnect):
    """Bind a ConnectionUsage line's handles to its connector ends.

    Unlike the view-only FeatureTyping connector, a connection's ends are
    authorable: connecting the head/tail to a feature item sets the connection's
    source/target (via the head/tail metadata the base applies). But the
    connection's OWN subject is preserved -- it is created by the toolbox or the
    projection drop, never find-or-created here -- so neither drawing nor
    reconnecting duplicates the connection.
    """

    def connect_subject(self, handle):
        if self.line.subject is not None:
            return True
        return super().connect_subject(handle)

    def disconnect_subject(self, handle):
        # Keep the connection while a handle is temporarily detached; the base
        # would delete the subject and a reconnect would create a new one.
        pass
