"""Connection end semantics: binary connector endpoints (Phase 9, non-chain).

`connection c connect a to b;` resolves each endpoint (nearest-first, non-chain)
to a feature and sets the connector's source/target; broken or non-feature
endpoints are recorded and validated; the connection exports its connect clause
and round-trips.
"""

from __future__ import annotations

from gaphor.core.modeling import ElementFactory
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2 import sysml2
from gaphor.SysML2.export import export_namespace
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.roundtrip import round_trip
from gaphor.SysML2.validation import has_errors, validate


def _map(text: str):
    factory = ElementFactory()
    return factory, map_package(parse(text), factory)


def _conn(factory) -> sysml2.ConnectionUsage:
    return next(iter(factory.select(sysml2.ConnectionUsage)))


def test_binary_connection_resolves_endpoints():
    factory, result = _map("part a;\npart b;\nconnection c connect a to b;")
    assert not result.unresolved_ends
    connection = _conn(factory)
    assert kk._single(connection.source).declaredName == "a"
    assert kk._single(connection.target).declaredName == "b"


def test_typed_connection_with_endpoints():
    factory, result = _map(
        "connection def Flow;\npart a;\npart b;\n"
        "connection c : Flow connect a to b;"
    )
    assert not result.unresolved_ends and not result.unresolved_types
    connection = _conn(factory)
    assert kk.feature_type(connection).declaredName == "Flow"
    assert kk._single(connection.source).declaredName == "a"


def test_declaration_only_connection_still_works():
    factory, result = _map("connection c;")
    assert not result.unresolved_ends
    assert kk._single(_conn(factory).source) is None


def test_broken_endpoint_is_recorded_and_validated():
    factory, result = _map("part a;\nconnection c connect a to missing;")
    connection = _conn(factory)
    assert connection.id in result.unresolved_ends
    diagnostics = validate(
        factory, result.unresolved_types, result.mistyped, result.unresolved_ends
    )
    assert has_errors(diagnostics)
    assert any(d.rule == "broken-connection-end" for d in diagnostics)


def test_endpoint_to_non_feature_is_mismatched():
    # An endpoint that resolves to a definition (a Classifier, not a Feature) is a
    # mismatched end; the ends are atomic, so the good end `a` is NOT kept either.
    factory, result = _map("part def D;\npart a;\nconnection c connect a to D;")
    connection = _conn(factory)
    assert "D" in result.unresolved_ends[connection.id]
    assert kk._single(connection.source) is None
    assert kk._single(connection.target) is None


def test_partial_endpoint_resolution_drops_both_ends():
    # Binary ends are atomic: if one end is broken the connect clause is reported
    # broken and NEITHER end is materialised (a one-ended connection has no valid
    # textual form and would otherwise be dropped silently on export).
    factory, result = _map("part a;\nconnection c connect a to missing;")
    connection = _conn(factory)
    assert result.unresolved_ends[connection.id] == ["missing"]
    assert kk._single(connection.source) is None
    assert kk._single(connection.target) is None


def test_one_ended_connection_is_reported_model_derived():
    # A one-ended connection that reaches the model outside the textual path (here
    # via the kernel API) is caught model-derived, with no mapping context.
    factory, _ = _map("part a;\nconnection c;")
    connection = _conn(factory)
    part_a = next(p for p in factory.select(sysml2.PartUsage) if p.declaredName == "a")
    connection.source = part_a

    diagnostics = validate(factory)

    assert any(d.rule == "incomplete-connection" for d in diagnostics)
    assert has_errors(diagnostics)


def test_complete_and_endless_connections_are_not_flagged():
    # Neither a fully-connected (two ends) nor a declaration-only (no ends)
    # connection trips the incomplete-connection rule.
    factory, _ = _map(
        "part a;\npart b;\nconnection c connect a to b;\nconnection d;"
    )
    assert not any(
        d.rule == "incomplete-connection" for d in validate(factory)
    )


def test_connection_exports_with_endpoints():
    factory, result = _map("part a;\npart b;\nconnection c connect a to b;")
    assert "connection c connect a to b;" in export_namespace(result.root)


def test_connection_with_endpoints_round_trips():
    result = round_trip("part a;\npart b;\nconnection c connect a to b;")
    assert result.preserved
    assert result.valid


def test_connection_endpoints_resolve_through_enclosing_namespace():
    result = round_trip(
        "package P { part a; part b; connection c connect a to b; }"
    )
    assert result.preserved
    assert result.valid
