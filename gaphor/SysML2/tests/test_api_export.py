"""SysML v2 API alignment (completion-roadmap Phase 12).

Two pieces: a stable API-facing `elementId` (minted at creation, distinct from
Gaphor's `Base.id`, persisted, IGNORED by round-trip), and a Systems Modeling API
element JSON export (`@id`/`@type` + stored attributes/references-by-`@id`). The
whole repository is exported so no `@id` reference dangles.
"""

from __future__ import annotations

import json

import gaphor.storage as storage
from gaphor.core.modeling import ElementFactory
from gaphor.SysML2 import cli, kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.api_export import api_document, export_api_json
from gaphor.SysML2.element_id import element_id
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.kpar import read_kpar, write_kpar
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.roundtrip import canonical_form

_MODEL = (
    "package P {\n"
    "  part def Engine;\n"
    "  part e : Engine;\n"
    "  attribute t : Real;\n"
    "}"
)


def _map(text: str):
    factory = ElementFactory()
    result = map_package(parse(text), factory)
    return factory, result.root


def _one(factory, type_name: str):
    return next(x for x in factory.select() if type(x).__name__ == type_name)


# --- elementId identity ------------------------------------------------------


def test_element_id_defaults_to_base_id():
    factory, _root = _map(_MODEL)
    usage = _one(factory, "PartUsage")
    # The API identity defaults to Gaphor's creation-time Base.id (no parallel id).
    assert element_id(usage) == usage.id


def test_element_id_present_for_direct_factory_creation():
    # The finding's repro: an element created straight from a bare factory (no mapper,
    # no event manager, no sweep) STILL has an API identity immediately -- it is its
    # Base.id, present from creation.
    factory = ElementFactory()
    part_def = factory.create(sysml2.PartDefinition)
    assert element_id(part_def) == part_def.id


def test_explicit_element_id_override_wins():
    # An explicitly-assigned API id (e.g. imported from an external OMG API repository)
    # takes precedence over the Base.id default.
    factory = ElementFactory()
    part_def = factory.create(sysml2.PartDefinition)
    part_def.elementId = "api-1234"
    assert element_id(part_def) == "api-1234"


def test_element_id_stable_across_save_reload(element_factory, saver, loader):
    map_package(parse(_MODEL), element_factory)
    usage = _one(element_factory, "PartUsage")
    usage_id, eid = usage.id, element_id(usage)
    loader(saver())
    reloaded = element_factory.lookup(usage_id)
    assert reloaded is not None and element_id(reloaded) == eid  # stable across .gaphor


def test_element_id_is_ignored_by_canonical_form():
    # Two structurally-identical models have different element ids yet the same
    # canonical form -- round-trip equivalence stays purely structural.
    _f1, root1 = _map(_MODEL)
    _f2, root2 = _map(_MODEL)
    ids1 = {element_id(m) for m in kk.members(root1)}
    ids2 = {element_id(m) for m in kk.members(root2)}
    assert ids1.isdisjoint(ids2)
    assert canonical_form(root1) == canonical_form(root2)


# --- API element JSON --------------------------------------------------------


def test_api_document_shape():
    factory, _root = _map(_MODEL)
    doc = api_document(factory)
    assert doc["metamodel"] == "SysML2"
    assert doc["elementCount"] == len(doc["elements"]) > 0
    for payload in doc["elements"]:
        assert payload["@id"] and payload["@type"]  # every element is identified+typed


def test_api_references_are_by_id_and_never_dangle():
    factory, _root = _map(_MODEL)
    doc = api_document(factory)
    ids = {p["@id"] for p in doc["elements"]}

    def referenced_ids(value):
        if isinstance(value, dict) and "@id" in value:
            yield value["@id"]
        elif isinstance(value, list):
            for item in value:
                yield from referenced_ids(item)

    for payload in doc["elements"]:
        for key, value in payload.items():
            if key in ("@id", "@type"):
                continue
            for ref in referenced_ids(value):
                assert ref in ids, f"{payload['@type']}.{key} -> dangling {ref}"


def test_api_export_includes_typing_and_usage():
    factory, _root = _map(_MODEL)
    doc = api_document(factory)
    by_type = {p["@type"] for p in doc["elements"]}
    # A faithful repository dump: the usage, its definition, the FeatureTyping, and
    # the Real value-type proxy are all present (unlike text export, nothing is
    # omitted -- so references resolve).
    assert {"PartUsage", "PartDefinition", "FeatureTyping"} <= by_type
    usage = next(p for p in doc["elements"] if p["@type"] == "PartUsage")
    assert usage["declaredName"] == "e"


def test_export_api_json_is_valid_json():
    factory, _root = _map(_MODEL)
    parsed = json.loads(export_api_json(factory))
    assert parsed["metamodel"] == "SysML2" and parsed["elements"]


# --- CLI ---------------------------------------------------------------------


def test_api_export_cli(tmp_path):
    model = tmp_path / "m.gaphor"
    factory = ElementFactory()
    map_package(parse(_MODEL), factory)
    with open(model, "w", encoding="utf-8") as f:
        storage.save(f, factory)

    out = tmp_path / "model.api.json"
    args = cli.api_export_parser().parse_args([str(model), "-o", str(out)])
    assert args.command(args) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["metamodel"] == "SysML2" and doc["elementCount"] == len(doc["elements"])
    assert any(p["@type"] == "PartUsage" for p in doc["elements"])


# --- KPAR carries elementId --------------------------------------------------


def test_kpar_meta_carries_element_ids(tmp_path):
    factory, root = _map(_MODEL)
    path = tmp_path / "out.kpar"
    write_kpar(path, root, project_name="P")
    archive = read_kpar(path)
    # The reader tolerates the extra meta key; read it back from the raw descriptor.
    import zipfile

    with zipfile.ZipFile(path) as zf:
        meta = json.loads(zf.read(f"{archive.root}/.meta.json"))
    assert set(meta["elementIds"]) == {"P"}  # the single top-level member
    # The recorded id matches the model element's API identity.
    package = next(m for m in kk.members(root) if kk.effective_name(m) == "P")
    assert meta["elementIds"]["P"] == element_id(package)
