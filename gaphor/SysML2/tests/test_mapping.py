"""M2 sub-step 2: AST -> semantic model mapping for the tracer pair."""

from __future__ import annotations

from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package


def test_part_definition_becomes_partdefinition(element_factory):
    result = map_package(parse("part def Engine;"), element_factory)

    engine = result.elements_by_name["Engine"]
    assert isinstance(engine, sysml2.PartDefinition)
    assert engine.declaredName == "Engine"
    # Owned by the root namespace.
    assert engine in list(kk.members(result.root))


def test_part_usage_becomes_partusage(element_factory):
    result = map_package(parse("part vehicleEngine;"), element_factory)

    usage = result.elements_by_name["vehicleEngine"]
    assert isinstance(usage, sysml2.PartUsage)
    assert usage.declaredName == "vehicleEngine"
    assert usage in list(kk.members(result.root))


def test_typed_usage_is_typed_by_its_definition(element_factory):
    result = map_package(
        parse("part def Engine;\npart vehicleEngine : Engine;"), element_factory
    )

    engine = result.elements_by_name["Engine"]
    usage = result.elements_by_name["vehicleEngine"]

    typings = element_factory.lselect(kerml.FeatureTyping)
    assert len(typings) == 1
    typing = typings[0]
    assert usage in list(typing.typedFeature)
    assert engine in list(typing.type)


def test_qualified_names_reflect_ownership(element_factory):
    result = map_package(parse("part def Engine;"), element_factory)
    result.root.declaredName = "Vehicles"
    engine = result.elements_by_name["Engine"]
    assert kk.qualified_name(engine) == "Vehicles::Engine"


def test_package_becomes_a_namespace_owning_its_members(element_factory):
    result = map_package(
        parse("package Vehicles { part def Engine; }"), element_factory
    )
    vehicles = result.elements_by_name["Vehicles"]
    assert isinstance(vehicles, kerml.Package)
    assert isinstance(vehicles, kerml.Namespace)
    engine = kk.owned_member_named(vehicles, "Engine")
    assert engine is not None and isinstance(engine, sysml2.PartDefinition)


def test_nested_package_ownership_and_qualified_names(element_factory):
    result = map_package(
        parse("package Outer { package Inner { part def Engine; } }"),
        element_factory,
    )
    result.root.declaredName = "Root"
    outer = result.elements_by_name["Outer"]
    inner = kk.owned_member_named(outer, "Inner")
    engine = kk.owned_member_named(inner, "Engine")
    assert engine is not None
    # Qualified name spans the full nesting chain.
    assert kk.qualified_name(engine) == "Root::Outer::Inner::Engine"


def test_usage_typed_within_its_package(element_factory):
    result = map_package(
        parse("package P { part def Engine; part e : Engine; }"), element_factory
    )
    p = result.elements_by_name["P"]
    engine = kk.owned_member_named(p, "Engine")
    usage = kk.owned_member_named(p, "e")
    typings = element_factory.lselect(kerml.FeatureTyping)
    assert len(typings) == 1
    assert usage in list(typings[0].typedFeature)
    assert engine in list(typings[0].type)


def test_attribute_usage_typed_by_attribute_definition(element_factory):
    result = map_package(
        parse("attribute def Mass;\nattribute m : Mass;"), element_factory
    )
    mass = result.elements_by_name["Mass"]
    m = result.elements_by_name["m"]
    assert isinstance(mass, sysml2.AttributeDefinition)
    assert isinstance(m, sysml2.AttributeUsage)
    typings = element_factory.lselect(kerml.FeatureTyping)
    assert len(typings) == 1
    assert m in list(typings[0].typedFeature)
    assert mass in list(typings[0].type)


def test_action_usage_typed_by_action_definition(element_factory):
    result = map_package(
        parse("action def Brake;\naction emergencyBrake : Brake;"), element_factory
    )
    brake = result.elements_by_name["Brake"]
    emergency = result.elements_by_name["emergencyBrake"]
    assert isinstance(brake, sysml2.ActionDefinition)
    assert isinstance(emergency, sysml2.ActionUsage)
    # The action usage is a KerML Feature on the kernel chain.
    assert isinstance(emergency, kerml.Feature)
    typings = element_factory.lselect(kerml.FeatureTyping)
    assert len(typings) == 1
    assert emergency in list(typings[0].typedFeature)
    assert brake in list(typings[0].type)


def test_unresolved_type_leaves_usage_untyped(element_factory):
    # Forward/undefined reference: no FeatureTyping is created; validation (a
    # later sub-step) is responsible for reporting it.
    result = map_package(parse("part p : Missing;"), element_factory)
    assert element_factory.lselect(kerml.FeatureTyping) == []
    assert "p" in result.elements_by_name
