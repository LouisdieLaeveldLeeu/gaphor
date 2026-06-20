"""Port conjugation (Phase 8a): `port p : ~Fuel`.

A conjugated port is typed by the *conjugate* of a PortDefinition, modeled
faithfully (PortConjugation + ConjugatedPortDefinition + ConjugatedPortTyping).
Covers parse, map (materialize/reuse the conjugate), export back to `~Fuel`,
round-trip, validation, and delete cascade.
"""

from __future__ import annotations

from gaphor.core.modeling import ElementFactory
from gaphor.SysML2 import conjugation
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


def _port(factory, name: str) -> sysml2.PortUsage:
    return next(u for u in factory.select(sysml2.PortUsage) if u.declaredName == name)


# --- parse -------------------------------------------------------------------


def test_parse_sets_conjugated_flag():
    pkg = parse("port p : ~Fuel;\nport q : Fuel;")
    p = next(m for m in pkg.members if m.name == "p")
    q = next(m for m in pkg.members if m.name == "q")
    assert p.conjugated is True and p.type_name == ("Fuel",)
    assert q.conjugated is False and q.type_name == ("Fuel",)


# --- map ---------------------------------------------------------------------


def test_conjugated_typing_is_materialized_faithfully():
    factory, result = _map("port def Fuel;\nport p : ~Fuel;")
    assert not result.unresolved_types and not result.mistyped
    p = _port(factory, "p")
    typing = conjugation.conjugated_typing(p)
    assert isinstance(typing, sysml2.ConjugatedPortTyping)
    conjugate = kk._single(typing.conjugatedPortDefinition)
    assert isinstance(conjugate, sysml2.ConjugatedPortDefinition)
    original = conjugation.original_port_definition(conjugate)
    assert original.declaredName == "Fuel"


def test_conjugate_is_reused_across_typings():
    factory, _ = _map("port def Fuel;\nport p : ~Fuel;\nport q : ~Fuel;")
    assert len(list(factory.select(sysml2.ConjugatedPortDefinition))) == 1
    assert len(list(factory.select(sysml2.PortConjugation))) == 1
    assert len(list(factory.select(sysml2.ConjugatedPortTyping))) == 2


def test_conjugate_is_invisible_to_name_resolution_and_duplicates():
    # The conjugate is an unnamed owned member of the original; it must not break
    # the duplicate-name rule nor be resolvable by name.
    factory, _ = _map("port def Fuel;\nport p : ~Fuel;")
    assert not has_errors(validate(factory))


def test_plain_and_conjugated_typing_coexist():
    factory, result = _map("port def Fuel;\nport p : ~Fuel;\nport q : Fuel;")
    assert not result.mistyped
    assert conjugation.conjugated_typing(_port(factory, "p")) is not None
    assert conjugation.conjugated_typing(_port(factory, "q")) is None
    assert kk.feature_type(_port(factory, "q")).declaredName == "Fuel"


# --- export ------------------------------------------------------------------


def test_export_emits_tilde_and_hides_the_conjugate():
    _factory, result = _map("port def Fuel;\nport p : ~Fuel;")
    text = export_namespace(result.root)
    assert "port p : ~Fuel;" in text
    # The implicit conjugate is never emitted as a `port def`.
    assert text.count("port def") == 1


# --- round-trip --------------------------------------------------------------


def test_conjugated_port_round_trips():
    result = round_trip("port def Fuel;\nport p : ~Fuel;\nport q : Fuel;")
    assert result.preserved
    assert result.valid


def test_conjugated_port_round_trips_in_a_package():
    result = round_trip("package P { port def Fuel; port p : ~Fuel; }")
    assert result.preserved
    assert result.valid


def test_conjugated_and_plain_typing_are_distinct_fingerprints():
    # `: Fuel` and `: ~Fuel` must not collapse to the same canonical entry.
    conjugated = round_trip("port def Fuel;\nport p : ~Fuel;")
    plain = round_trip("port def Fuel;\nport p : Fuel;")
    assert conjugated.source_form != plain.source_form


# --- validation --------------------------------------------------------------


def test_conjugation_of_a_non_port_is_mistyped():
    factory, result = _map("part def D;\nport p : ~D;")
    p = _port(factory, "p")
    assert result.mistyped[p.id][0] == "~D"
    assert conjugation.conjugated_typing(p) is None


def test_conjugation_of_an_unresolved_name_is_recorded():
    factory, result = _map("port p : ~Missing;")
    assert result.unresolved_types[_port(factory, "p").id] == "~Missing"


def test_broken_conjugation_is_reported_model_derived():
    # Deleting the original cascades away the conjugate, leaving a dangling
    # conjugated typing -- caught with no mapping context.
    factory, _ = _map("port def Fuel;\nport p : ~Fuel;")
    fuel = next(
        d
        for d in factory.select(sysml2.PortDefinition)
        if d.declaredName == "Fuel"
    )
    fuel.unlink()
    diagnostics = validate(factory)
    assert any(d.rule == "broken-conjugation" for d in diagnostics)
    assert has_errors(diagnostics)


# --- delete cascade ----------------------------------------------------------


def test_deleting_original_cascades_to_conjugate_and_conjugation():
    factory, _ = _map("port def Fuel;\nport p : ~Fuel;")
    fuel = next(
        d
        for d in factory.select(sysml2.PortDefinition)
        if d.declaredName == "Fuel"
    )
    fuel.unlink()
    assert not list(factory.select(sysml2.ConjugatedPortDefinition))
    assert not list(factory.select(sysml2.PortConjugation))


def test_deleting_usage_keeps_the_shared_conjugate():
    factory, _ = _map("port def Fuel;\nport p : ~Fuel;\nport q : ~Fuel;")
    _port(factory, "p").unlink()
    # The conjugate is shared and owned by the original, so it survives.
    assert len(list(factory.select(sysml2.ConjugatedPortDefinition))) == 1
    assert len(list(factory.select(sysml2.ConjugatedPortTyping))) == 1
