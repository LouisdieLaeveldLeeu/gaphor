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


def test_qualified_names_survive_reload(element_factory, saver, loader):
    result = map_package(parse(TRACER), element_factory)
    result.root.declaredName = "Vehicles"
    ids = _ids(result)

    loader(saver())

    engine = element_factory.lookup(ids["Engine"])
    assert kk.qualified_name(engine) == "Vehicles::Engine"
