"""Redefinition of inherited features (`:>>`, Phase 5c-2).

`part x :>> y` REDEFINES an existing feature `y` (a KerML Redefinition, a Subsetting
subkind). The redefined feature resolves through owned/inherited/imported scopes
EXCLUDING the redefining feature itself, so a bare `:>> x` on a feature named `x`
redefines the INHERITED `x`. Declaring a redefining feature gives the type its own
member, which shadows an inherited-name conflict -- so a conflict that is
`ambiguous-name` when merely inherited (Phase 5c-1) is resolved by redefining one
supertype's feature (`:>> A::x`). Covers parse, map, bare/qualified/sibling
resolution, conflict resolution, ambiguity, unresolved/broken diagnostics, export,
round-trip, and persistence.
"""

from __future__ import annotations

from gaphor.core.modeling import ElementFactory
from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.export import export_namespace
from gaphor.SysML2.grammar import ast
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.roundtrip import round_trip
from gaphor.SysML2.validation import has_errors, validate


def _map(text: str):
    factory = ElementFactory()
    return factory, map_package(parse(text), factory)


def _validate(factory, result):
    return validate(
        factory,
        result.unresolved_types,
        result.mistyped,
        result.unresolved_ends,
        result.unresolved_frame_refs,
        result.ambiguous,
        result.unresolved_supertypes,
        result.unresolved_subsettings,
        result.unresolved_redefinitions,
    )


def _def(factory, name):
    return next(
        d for d in factory.select(sysml2.PartDefinition) if d.declaredName == name
    )


def _part_in(factory, name, owner):
    return next(
        u
        for u in factory.select(sysml2.PartUsage)
        if u.declaredName == name
        and (ns := kk.owning_namespace(u)) is not None
        and ns.declaredName == owner
    )


def _redefined(usage):
    return kk._single(next(iter(kk.redefinitions(usage))).redefinedFeature)


# --- parse -------------------------------------------------------------------


def test_parse_redefinition():
    a, b, c = parse(
        "part x :>> y;\npart z : T :>> A::w;\npart p :> s :>> r;"
    ).members
    assert a == ast.PartUsage(name="x", redefines=("y",))
    assert b == ast.PartUsage(name="z", type_name=("T",), redefines=("A", "w"))
    assert c == ast.PartUsage(name="p", subsets=("s",), redefines=("r",))


# --- map / resolution --------------------------------------------------------


def test_bare_redefinition_resolves_inherited_not_self():
    factory, result = _map(
        "part def Vehicle { part mass; }\n"
        "part def Car :> Vehicle { part mass :>> mass; }"
    )
    assert not has_errors(_validate(factory, result))
    car_mass = _part_in(factory, "mass", "Car")
    redefinition = next(iter(kk.redefinitions(car_mass)))
    assert type(redefinition) is kerml.Redefinition
    target = _redefined(car_mass)
    # The redefined feature is the INHERITED Vehicle::mass, never the redefining
    # feature itself.
    assert target is not car_mass
    assert kk.owning_namespace(target).declaredName == "Vehicle"


def test_qualified_redefinition_resolves():
    factory, result = _map(
        "part def A { part x; }\n"
        "part def C :> A { part x :>> A::x; }"
    )
    assert not has_errors(_validate(factory, result))
    assert kk.owning_namespace(_redefined(_part_in(factory, "x", "C"))).declaredName == "A"


def test_sibling_redefinition_resolves():
    factory, result = _map("part def C { part a; part b :>> a; }")
    assert not has_errors(_validate(factory, result))
    target = _redefined(_part_in(factory, "b", "C"))
    assert target.declaredName == "a"
    assert kk.owning_namespace(target).declaredName == "C"


def test_redefinition_resolves_inherited_conflict():
    # `x` is inherited from BOTH A and B; declaring `part x :>> A::x` gives C its own
    # `x`, which shadows the conflict, so a later `part y :> x` is NOT ambiguous.
    factory, result = _map(
        "part def A { part x; }\npart def B { part x; }\n"
        "part def C :> A, B { part x :>> A::x; part y :> x; }"
    )
    assert not has_errors(_validate(factory, result))
    assert not result.ambiguous
    # C's OWN redefining `x` shadows the inherited conflict, so `y :> x` binds it.
    own_x = kk.owned_member_named(_def(factory, "C"), "x")
    y = _part_in(factory, "y", "C")
    subsetted = kk._single(next(iter(kk.subsettings(y))).subsettedFeature)
    assert subsetted is own_x


# --- diagnostics -------------------------------------------------------------


def test_bare_redefinition_of_conflicting_inherited_is_ambiguous():
    # Without qualification, `:>> x` cannot pick between A::x and B::x -> ambiguous.
    factory, result = _map(
        "part def A { part x; }\npart def B { part x; }\n"
        "part def C :> A, B { part x :>> x; }"
    )
    assert _part_in(factory, "x", "C").id in result.ambiguous
    diagnostics = _validate(factory, result)
    assert any(d.rule == "ambiguous-name" for d in diagnostics)
    assert not list(kk.redefinitions(_part_in(factory, "x", "C")))


def test_unresolved_redefinition_is_reported():
    factory, result = _map("part def C { part x :>> missing; }")
    assert _part_in(factory, "x", "C").id in result.unresolved_redefinitions
    assert any(d.rule == "unresolved-redefinition" for d in _validate(factory, result))


def test_redefinition_target_must_be_a_feature():
    factory, result = _map("part def D;\npart def C { part x :>> D; }")
    # `D` resolves but is a definition, not a Feature -> no Redefinition.
    assert _part_in(factory, "x", "C").id in result.unresolved_redefinitions
    assert any(d.rule == "unresolved-redefinition" for d in _validate(factory, result))


def test_broken_persisted_redefinition_is_reported():
    factory = ElementFactory()
    x = factory.create(sysml2.PartUsage)
    redefinition = factory.create(kerml.Redefinition)
    redefinition.redefiningFeature = x
    x.ownedRelationship = redefinition
    redefinition.owningRelatedElement = x
    # No redefinedFeature -> broken (model-derived).
    assert any(d.rule == "broken-redefinition" for d in validate(factory))


def test_healthy_redefinition_has_no_broken_diagnostics():
    factory, result = _map(
        "part def Vehicle { part mass; }\n"
        "part def Car :> Vehicle { part mass :>> mass; }"
    )
    diagnostics = _validate(factory, result)
    assert not any(
        d.rule in {"broken-redefinition", "broken-subsetting"} for d in diagnostics
    )


# --- export / round-trip -----------------------------------------------------


def test_export_emits_bare_redefinition():
    _factory, result = _map(
        "part def Vehicle { part mass; }\n"
        "part def Car :> Vehicle { part mass :>> mass; }"
    )
    text = export_namespace(result.root)
    assert "part mass :>> mass;" in text


def test_redefinition_round_trips():
    assert round_trip(
        "part def Vehicle { part mass; }\n"
        "part def Car :> Vehicle { part mass :>> mass; }"
    ).preserved


def test_redefinition_conflict_resolution_round_trips():
    result = round_trip(
        "part def A { part x; }\npart def B { part x; }\n"
        "part def C :> A, B { part x :>> A::x; part y :> x; }"
    )
    assert result.preserved
    assert result.valid


def test_redefinition_changes_the_fingerprint():
    base = "part def V { part m; }\npart def C :> V { part m%s; }"
    assert round_trip(base % "").source_form != round_trip(
        base % " :>> m"
    ).source_form


# --- persistence -------------------------------------------------------------


def test_redefinition_survives_save_reload(element_factory, saver, loader):
    map_package(
        parse(
            "part def Vehicle { part mass; }\n"
            "part def Car :> Vehicle { part mass :>> mass; }"
        ),
        element_factory,
    )

    loader(saver())

    car_mass = next(
        u
        for u in element_factory.select(sysml2.PartUsage)
        if u.declaredName == "mass"
        and kk.owning_namespace(u).declaredName == "Car"
    )
    target = kk._single(next(iter(kk.redefinitions(car_mass))).redefinedFeature)
    assert kk.owning_namespace(target).declaredName == "Vehicle"
