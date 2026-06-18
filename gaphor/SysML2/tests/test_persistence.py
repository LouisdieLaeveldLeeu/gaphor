"""M2 sub-step 3: persistence of the mapped Part model through `.gaphor`.

Proves the tracer model survives save/reload with the typing relation intact,
and that relationship ownership is correct: the usage owns its FeatureTyping
(deleting the usage cascades to the typing), while the definition is only the
non-owning `type` target and is never cascade-deleted.
"""

from __future__ import annotations

from gaphor.SysML2 import kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.mapping import map_package

TRACER = "part def Engine;\npart vehicleEngine : Engine;"


def _ids(result):
    return {name: el.id for name, el in result.elements_by_name.items()}


def test_part_model_persists_and_reloads(element_factory, saver, loader):
    result = map_package(parse(TRACER), element_factory)
    ids = _ids(result)

    loader(saver())

    engine = element_factory.lookup(ids["Engine"])
    usage = element_factory.lookup(ids["vehicleEngine"])
    assert isinstance(engine, sysml2.PartDefinition)
    assert isinstance(usage, sysml2.PartUsage)
    assert engine.declaredName == "Engine"
    assert usage.declaredName == "vehicleEngine"


def test_typing_relation_survives_reload(element_factory, saver, loader):
    result = map_package(parse(TRACER), element_factory)
    ids = _ids(result)

    loader(saver())

    engine = element_factory.lookup(ids["Engine"])
    usage = element_factory.lookup(ids["vehicleEngine"])
    typings = element_factory.lselect(kerml.FeatureTyping)
    assert len(typings) == 1
    typing = typings[0]
    assert usage in list(typing.typedFeature)
    assert engine in list(typing.type)


def test_typing_is_owned_by_the_usage_after_reload(element_factory, saver, loader):
    result = map_package(parse(TRACER), element_factory)
    ids = _ids(result)

    loader(saver())

    usage = element_factory.lookup(ids["vehicleEngine"])
    typing = element_factory.lselect(kerml.FeatureTyping)[0]
    # The usage owns the typing through the containment spine.
    assert typing in list(usage.ownedRelationship)
    assert usage in list(typing.owningRelatedElement)


def test_deleting_usage_cascades_to_typing_but_not_definition(element_factory):
    result = map_package(parse(TRACER), element_factory)
    engine = result.elements_by_name["Engine"]
    usage = result.elements_by_name["vehicleEngine"]
    typing = element_factory.lselect(kerml.FeatureTyping)[0]
    engine_id, typing_id = engine.id, typing.id

    usage.unlink()

    # The owned typing is cascade-deleted; the definition (non-owning `type`
    # target) survives.
    assert element_factory.lookup(typing_id) is None
    assert element_factory.lookup(engine_id) is not None


def test_deleting_definition_does_not_delete_usage_or_typing(element_factory):
    result = map_package(parse(TRACER), element_factory)
    engine = result.elements_by_name["Engine"]
    usage = result.elements_by_name["vehicleEngine"]
    typing = element_factory.lselect(kerml.FeatureTyping)[0]
    usage_id, typing_id = usage.id, typing.id

    engine.unlink()

    # The definition is only referenced (non-owning) by the typing, so deleting
    # it leaves the usage and the typing relationship in place.
    assert element_factory.lookup(usage_id) is not None
    assert element_factory.lookup(typing_id) is not None


def test_nested_package_persists_and_reloads(element_factory, saver, loader):
    src = "package Outer { package Inner { part def Engine; } }"
    result = map_package(parse(src), element_factory)
    result.root.declaredName = "Root"
    outer_id = result.elements_by_name["Outer"].id
    engine_id = kk.owned_member_named(
        kk.owned_member_named(result.elements_by_name["Outer"], "Inner"), "Engine"
    ).id

    loader(saver())

    outer = element_factory.lookup(outer_id)
    engine = element_factory.lookup(engine_id)
    assert isinstance(outer, kerml.Package)
    assert engine is not None
    # Nesting + qualified name survive the round-trip through .gaphor.
    assert kk.qualified_name(engine) == "Root::Outer::Inner::Engine"


def test_action_tracer_persists_with_typing(element_factory, saver, loader):
    result = map_package(
        parse("action def Brake;\naction emergencyBrake : Brake;"), element_factory
    )
    ids = _ids(result)

    loader(saver())

    brake = element_factory.lookup(ids["Brake"])
    emergency = element_factory.lookup(ids["emergencyBrake"])
    assert isinstance(brake, sysml2.ActionDefinition)
    assert isinstance(emergency, sysml2.ActionUsage)
    typings = element_factory.lselect(kerml.FeatureTyping)
    assert len(typings) == 1
    assert emergency in list(typings[0].typedFeature)
    assert brake in list(typings[0].type)


def test_requirement_tracer_persists_with_typing(element_factory, saver, loader):
    result = map_package(
        parse(
            "constraint def Limit;\nconstraint c : Limit;\n"
            "requirement def MassReq;\nrequirement r : MassReq;"
        ),
        element_factory,
    )
    ids = _ids(result)

    loader(saver())

    limit = element_factory.lookup(ids["Limit"])
    c = element_factory.lookup(ids["c"])
    req_def = element_factory.lookup(ids["MassReq"])
    r = element_factory.lookup(ids["r"])
    assert isinstance(limit, sysml2.ConstraintDefinition)
    assert isinstance(c, sysml2.ConstraintUsage)
    assert isinstance(req_def, sysml2.RequirementDefinition)
    assert isinstance(r, sysml2.RequirementUsage)
    typings = element_factory.lselect(kerml.FeatureTyping)
    assert len(typings) == 2
    typed = {kk._single(t.typedFeature): kk._single(t.type) for t in typings}
    assert typed[c] is limit
    assert typed[r] is req_def


def test_port_tracer_persists_with_typing(element_factory, saver, loader):
    result = map_package(
        parse("port def Fuel;\nport p : Fuel;"), element_factory
    )
    ids = _ids(result)

    loader(saver())

    fuel = element_factory.lookup(ids["Fuel"])
    p = element_factory.lookup(ids["p"])
    assert isinstance(fuel, sysml2.PortDefinition)
    assert isinstance(p, sysml2.PortUsage)
    typings = element_factory.lselect(kerml.FeatureTyping)
    assert len(typings) == 1
    assert p in list(typings[0].typedFeature)
    assert fuel in list(typings[0].type)


def test_qualified_names_survive_reload(element_factory, saver, loader):
    result = map_package(parse(TRACER), element_factory)
    result.root.declaredName = "Vehicles"
    ids = _ids(result)

    loader(saver())

    engine = element_factory.lookup(ids["Engine"])
    assert kk.qualified_name(engine) == "Vehicles::Engine"
