"""Definition bodies, subclassification & inherited members (Phase 5c).

A `part def` may carry a body of nested members and specialize supertypes
(`part def Car :> Vehicle { ... }`, a Subclassification). A member reachable through
a supertype is INHERITED: it resolves from a specializing type wherever a name
resolves there -- used here through a usage subsetting an inherited feature
(`part spare :> wheel;`) and a usage typed by an inherited nested definition. Own
members shadow inherited; private members are not inherited. Covers parse, map,
inherited resolution (subsetting + typing), multiple/transitive supertypes,
shadowing, diagnostics, export, round-trip, and persistence.
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
    )


def _def(factory, name):
    return next(
        d for d in factory.select(sysml2.PartDefinition) if d.declaredName == name
    )


def _part(factory, name):
    return next(
        u for u in factory.select(sysml2.PartUsage) if u.declaredName == name
    )


# --- parse -------------------------------------------------------------------


def test_parse_definition_body_and_specialization():
    pkg = parse("part def Car :> Vehicle, Other { part wheel; }")
    (car,) = pkg.members
    assert car.specializes == (("Vehicle",), ("Other",))
    assert car.members == (ast.PartUsage(name="wheel"),)


def test_parse_usage_subsetting():
    pkg = parse("part spare :> wheel;\npart driven : Engine :> motor;")
    spare, driven = pkg.members
    assert spare == ast.PartUsage(name="spare", subsets=("wheel",))
    assert driven == ast.PartUsage(
        name="driven", type_name=("Engine",), subsets=("motor",)
    )


# --- map ---------------------------------------------------------------------


def test_subclassification_mapped():
    factory, _ = _map("part def Vehicle;\npart def Car :> Vehicle;")
    car = _def(factory, "Car")
    sc = next(iter(kk.subclassifications(car)))
    assert type(sc) is kerml.Subclassification
    assert kk._single(sc.superclassifier).declaredName == "Vehicle"
    assert [kk.effective_name(s) for s in kk.supertypes(car)] == ["Vehicle"]


def test_definition_body_features_owned_via_feature_membership():
    factory, _ = _map("part def Vehicle { part wheel; part def Inner; }")
    vehicle = _def(factory, "Vehicle")
    wheel = _part(factory, "wheel")
    # A usage (Feature) is owned via FeatureMembership; a nested definition (a
    # non-Feature) via a plain OwningMembership.
    wheel_ms = kk._single(wheel.owningRelationship)
    assert isinstance(wheel_ms, kerml.FeatureMembership)
    inner = _def(factory, "Inner")
    inner_ms = kk._single(inner.owningRelationship)
    assert type(inner_ms) is kerml.OwningMembership
    assert kk.owning_namespace(wheel) is vehicle


# --- inherited resolution ----------------------------------------------------


def test_subsetting_resolves_inherited_member():
    factory, result = _map(
        "part def Vehicle { part wheel; }\n"
        "part def Car :> Vehicle { part spare :> wheel; }"
    )
    assert not has_errors(_validate(factory, result))
    spare = _part(factory, "spare")
    target = kk._single(next(iter(kk.subsettings(spare))).subsettedFeature)
    assert target.declaredName == "wheel"
    assert kk.owning_namespace(target).declaredName == "Vehicle"


def test_typing_resolves_inherited_nested_definition():
    # A nested definition is inherited too: `x : Inner` resolves Inner through the
    # supertype (inherited resolution via the TYPING path, not just subsetting).
    factory, result = _map(
        "part def Outer { part def Inner; }\n"
        "part def Sub :> Outer { part x : Inner; }"
    )
    assert not has_errors(_validate(factory, result))
    assert kk.feature_type(_part(factory, "x")).declaredName == "Inner"


def test_inheritance_is_transitive():
    factory, result = _map(
        "part def A { part deep; }\n"
        "part def B :> A;\n"
        "part def C :> B { part p :> deep; }"
    )
    assert not has_errors(_validate(factory, result))
    p = _part(factory, "p")
    target = kk._single(next(iter(kk.subsettings(p))).subsettedFeature)
    assert target.declaredName == "deep"
    assert kk.owning_namespace(target).declaredName == "A"


def test_multiple_supertypes_each_contribute_inherited_members():
    factory, result = _map(
        "part def A { part a; }\n"
        "part def B { part b; }\n"
        "part def C :> A, B { part pa :> a; part pb :> b; }"
    )
    assert not has_errors(_validate(factory, result))
    assert {kk.effective_name(s) for s in kk.supertypes(_def(factory, "C"))} == {
        "A",
        "B",
    }


def test_own_member_shadows_inherited():
    factory, result = _map(
        "part def Vehicle { part wheel; }\n"
        "part def Car :> Vehicle { part wheel; part spare :> wheel; }"
    )
    car = _def(factory, "Car")
    own_wheel = kk.owned_member_named(car, "wheel")
    spare = _part(factory, "spare")
    target = kk._single(next(iter(kk.subsettings(spare))).subsettedFeature)
    # `spare :> wheel` binds Car's OWN wheel, not Vehicle's inherited one.
    assert target is own_wheel
    assert kk.owning_namespace(target).declaredName == "Car"


def test_private_member_is_not_inherited():
    factory, result = _map(
        "part def Vehicle { private part secret; }\n"
        "part def Car :> Vehicle { part s :> secret; }"
    )
    # `secret` is private -> not inherited -> the subsetting does not resolve.
    assert _part(factory, "s").id in result.unresolved_subsettings
    assert any(d.rule == "unresolved-subsetting" for d in _validate(factory, result))


# --- diagnostics -------------------------------------------------------------


def test_unresolved_supertype_is_reported():
    factory, result = _map("part def Car :> Missing;")
    assert _def(factory, "Car").id in result.unresolved_supertypes
    assert any(
        d.rule == "unresolved-specialization" for d in _validate(factory, result)
    )
    assert not list(kk.subclassifications(_def(factory, "Car")))


def test_supertype_must_be_a_definition_not_a_usage():
    factory, result = _map("part thing;\npart def Car :> thing;")
    # `thing` resolves but is a usage (Feature), not a Classifier -> no heritage.
    assert _def(factory, "Car").id in result.unresolved_supertypes
    assert any(
        d.rule == "unresolved-specialization" for d in _validate(factory, result)
    )


def test_unresolved_subsetting_is_reported():
    factory, result = _map("part def Car { part spare :> missing; }")
    assert _part(factory, "spare").id in result.unresolved_subsettings
    assert any(d.rule == "unresolved-subsetting" for d in _validate(factory, result))


def test_ambiguous_supertype_is_ambiguous_not_unresolved():
    factory, result = _map(
        "package A { part def T; }\npackage B { part def T; }\n"
        "package C { import A::*; import B::*; part def Car :> T; }"
    )
    diagnostics = _validate(factory, result)
    assert any(d.rule == "ambiguous-name" for d in diagnostics)
    assert not any(d.rule == "unresolved-specialization" for d in diagnostics)


# --- export / round-trip -----------------------------------------------------


def test_export_emits_specialization_body_and_subsetting():
    _factory, result = _map(
        "part def Vehicle { part wheel; }\n"
        "part def Car :> Vehicle { part spare :> wheel; }"
    )
    text = export_namespace(result.root)
    assert "part def Vehicle {" in text
    assert "part def Car :> Vehicle {" in text
    assert "part spare :> wheel;" in text


def test_inheritance_round_trips():
    result = round_trip(
        "package P {\n"
        "  part def Engine;\n"
        "  part def Vehicle { part wheel; part eng : Engine; }\n"
        "  part def Car :> Vehicle { part spare :> wheel; }\n"
        "}"
    )
    assert result.preserved
    assert result.valid


def test_subclassification_changes_the_fingerprint():
    base = "part def Vehicle;\npart def Car"
    assert round_trip(base + ";").source_form != round_trip(
        base + " :> Vehicle;"
    ).source_form


def test_subsetting_changes_the_fingerprint():
    base = "part def Car { part wheel; part spare%s; }"
    assert round_trip(base % "").source_form != round_trip(
        base % " :> wheel"
    ).source_form


# --- persistence -------------------------------------------------------------


def test_inheritance_survives_save_reload(element_factory, saver, loader):
    map_package(
        parse(
            "part def Vehicle { part wheel; }\n"
            "part def Car :> Vehicle { part spare :> wheel; }"
        ),
        element_factory,
    )

    loader(saver())

    car = next(
        d
        for d in element_factory.select(sysml2.PartDefinition)
        if d.declaredName == "Car"
    )
    assert [kk.effective_name(s) for s in kk.supertypes(car)] == ["Vehicle"]
    # Inherited-member resolution still works through the reloaded supertype link.
    assert kk.inherited_member_named(car, "wheel").declaredName == "wheel"
    spare = next(
        u
        for u in element_factory.select(sysml2.PartUsage)
        if u.declaredName == "spare"
    )
    target = kk._single(next(iter(kk.subsettings(spare))).subsettedFeature)
    assert kk.owning_namespace(target).declaredName == "Vehicle"
