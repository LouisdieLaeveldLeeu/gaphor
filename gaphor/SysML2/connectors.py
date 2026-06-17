"""SysML v2 diagram connectors.

The generic `MetadataRelationConnect` connector (registered for any
ElementPresentation/LinePresentation pair) establishes a relationship line's
subject via `relationship_or_new` -- find-or-CREATE. For a projected
FeatureTyping that already has a subject (the existing typing the line views),
that path can create a DUPLICATE typing on connect.

This connector is registered more specifically for `FeatureTypingItem`, so it
wins by MRO. It connects the line's handles to the endpoint items exactly like
the generic one, but `connect_subject` REUSES the line's existing subject
instead of creating a new relationship -- so anchoring the line to its endpoint
boxes never duplicates the model element (invariant 4: the line is a view).
"""

from __future__ import annotations

from gaphor.diagram.connectors import Connector, MetadataRelationConnect
from gaphor.diagram.presentation import ElementPresentation
from gaphor.SysML2.diagramitems import FeatureTypingItem


@Connector.register(ElementPresentation, FeatureTypingItem)
class FeatureTypingConnect(MetadataRelationConnect):
    """Anchor a FeatureTyping line to its endpoint items, reusing the existing
    typing subject (never creating a duplicate)."""

    def connect_subject(self, handle):
        # The line already views an existing FeatureTyping (set when it was
        # projected). Keep it; do not find-or-create a new relationship.
        if self.line.subject is not None:
            return True
        # Fallback: if somehow unset (e.g. drawn fresh rather than projected),
        # defer to the generic find-or-create behaviour.
        return super().connect_subject(handle)
