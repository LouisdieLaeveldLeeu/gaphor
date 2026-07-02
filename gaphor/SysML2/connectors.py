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
from gaphor.diagram.support import get_diagram_item_metadata
from gaphor.SysML2 import kerml
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.diagramitems import (
    ConnectionUsageItem,
    FeatureTypingItem,
    PartDefinitionItem,
    PartUsageItem,
    PortUsageItem,
)


@Connector.register(PartDefinitionItem, PortUsageItem)
@Connector.register(PartUsageItem, PortUsageItem)
class PortUsageBoundaryConnector:
    """Attach a PortUsage boundary square to its owning part's item -- a VISUAL
    nesting only. The PortUsage already exists in the model (a member of the part), so
    this connector NEVER creates, deletes, or retypes a subject; it only sets the
    diagram parent, so the square rides the part's boundary and moves with it. It is
    used both by interactive drag and by the `connect()` helper that synthesis calls."""

    def __init__(self, owner, port: PortUsageItem):
        self.owner = owner
        self.port = port

    def _owns_port(self) -> bool:
        """Whether `owner` is the port's ACTUAL owning namespace -- so a boundary
        square can never be attached to a part that does not semantically own it (that
        would make the persisted diagram misrepresent the model)."""
        return (
            bool(self.owner.diagram)
            and self.owner.diagram is self.port.diagram
            and self.port.subject is not None
            and self.owner.subject is not None
            and kk.owning_namespace(self.port.subject) is self.owner.subject
        )

    def allow(self, handle, port) -> bool:
        return self._owns_port()

    def connect(self, handle, port) -> bool:
        # Re-verify at connect time. Returning False is NOT enough: the aspect layer
        # (`PresentationConnector.connect`) physically glues the handle BEFORE calling
        # this adapter and ignores its return value, and the programmatic `connect()`
        # helper never consults `allow()`. So on a wrong owner the just-made physical
        # connection must be actively severed, or the square would ride a part that
        # does not own it and the persisted diagram would misrepresent the model.
        if not self._owns_port():
            connections = self.port.diagram.connections
            if connections.get_connection(handle):
                connections.disconnect_item(self.port, handle)
            return False
        self.port.change_parent(self.owner)
        return True

    def disconnect(self, handle) -> None:
        if self.port.diagram:
            self.port.change_parent(None)


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
    source/target. But the connection's OWN subject is preserved -- it is created
    by the toolbox or the projection drop, never find-or-created here -- so
    neither drawing nor reconnecting duplicates the connection.

    Two narrowings over the generic relationship connector:

    - A connector end must be a `Feature` (a usage). The item metadata types
      source/target as the generic `Element`, so the base `allow` would let a
      handle land on a `ConnectionDefinitionItem` even though the text mapper
      rejects definitions as ends. `allow` refuses a non-feature endpoint at the
      UI layer; because Gaphor's low-level `connect()` does NOT consult `allow`,
      `connect_subject` independently refuses to author a non-feature end (and
      `validation` catches one that reached the model by any other route). So the
      "ends are features" invariant holds at hover, at connect, and at the model.
    - For an EXISTING connection (toolbox/projection) `connect_subject` authors
      the ends onto that subject itself rather than returning early (which would
      leave `source`/`target` None) or find-or-creating (which would duplicate
      the connection). source/target are multi-valued, so each end is cleared
      before being set, making a reconnect replace rather than accumulate ends.
    """

    def _feature_subject(self, item):
        # Only a Feature may be a connector end. A non-feature item (e.g. a
        # ConnectionDefinitionItem) yields no end, so the diagram path never
        # writes a non-feature source/target even when the low-level connect
        # bypassed allow().
        subject = item.subject if item is not None else None
        return subject if isinstance(subject, kerml.Feature) else None

    def _is_feature_end(self, item) -> bool:
        # An unconnected handle (item is None) or one whose item has no subject
        # yet is fine; a connected endpoint must be a feature.
        return (
            item is None
            or item.subject is None
            or isinstance(item.subject, kerml.Feature)
        )

    def allow(self, handle, port):
        if not super().allow(handle, port):
            return False
        opposite = self.get_connected(self.line.opposite(handle))
        return self._is_feature_end(self.element) and self._is_feature_end(opposite)

    def _set_end(self, relation, value) -> None:
        # source/target are relation_many: replace the end rather than append,
        # so authoring or re-authoring never accumulates duplicate ends.
        subject = self.line.subject
        for existing in list(relation.get(subject) or ()):
            relation.delete(subject, existing)
        if value is not None:
            relation.set(subject, value)

    def connect_subject(self, handle):
        metadata = get_diagram_item_metadata(type(self.line))
        if not metadata:
            return False
        line = self.line
        if line.subject is None:
            # Drawn fresh rather than projected: defer to find-or-create.
            return super().connect_subject(handle)
        head_item = self.get_connected(line.head)
        tail_item = self.get_connected(line.tail)
        # Only a Feature is authored as an end; a non-feature connected item
        # leaves that end unset (and so an incomplete connection that validation
        # reports), never a stored non-feature end.
        self._set_end(metadata["head"], self._feature_subject(head_item))
        self._set_end(metadata["tail"], self._feature_subject(tail_item))
        return True

    def disconnect_subject(self, handle):
        # Keep the connection while a handle is temporarily detached; the base
        # would delete the subject and a reconnect would create a new one.
        pass
