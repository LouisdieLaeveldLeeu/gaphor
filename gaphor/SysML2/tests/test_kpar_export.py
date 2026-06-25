"""KPAR export and round-trip (completion-roadmap Phase 10).

The writer is the inverse of import: a Gaphor SysML2 model -> a `.kpar` archive
(single `.sysml` member). Interchange is proven by CANONICAL-FORM equivalence (not
byte-identity): `text -> Gaphor -> KPAR -> Gaphor` and `KPAR -> Gaphor -> KPAR ->
Gaphor` preserve the model's canonical form, and `text -> Gaphor -> KPAR -> Gaphor
-> text` re-exports identical text. Library proxies (value types, implicit bases)
and synthesized chain features are never written.
"""

from __future__ import annotations

import gaphor.storage as storage
from gaphor.core.modeling import ElementFactory
from gaphor.SysML2 import cli, kerml, sysml2
from gaphor.SysML2 import kerml_kernel as kk
from gaphor.SysML2.export import export_namespace
from gaphor.SysML2.grammar.parser import parse
from gaphor.SysML2.kpar import import_user_kpar, read_kpar, write_kpar
from gaphor.SysML2.kpar.reader import read_member_text
from gaphor.SysML2.mapping import map_package
from gaphor.SysML2.roundtrip import canonical_form

# A model exercising proxies (Real), implicit bases, heritage, a body, and a
# connection -- everything that must be omitted or preserved on export.
_MODEL = (
    "package P {\n"
    "  part def Engine;\n"
    "  part e : Engine;\n"
    "  attribute t : Real;\n"
    "  part def Car :> Engine { part wheel; }\n"
    "  connection c connect e to wheel;\n"
    "}"
)


def _root(factory) -> kerml.Namespace:
    return next(
        ns
        for ns in factory.select(kerml.Namespace)
        if type(ns) is kerml.Namespace and kk.owning_namespace(ns) is None
    )


def _map(text: str):
    factory = ElementFactory()
    result = map_package(parse(text), factory)
    return factory, result.root


def _import_root(path):
    result = import_user_kpar(path)
    return _root(result.factory)


# --- archive structure -------------------------------------------------------


def test_writer_produces_a_readable_archive(tmp_path):
    _factory, root = _map(_MODEL)
    path = tmp_path / "out.kpar"
    write_kpar(path, root, project_name="My Project", version="1.0.0")

    archive = read_kpar(path)
    assert archive.project.name == "My Project"
    assert archive.project.version == "1.0.0"
    assert [mf.name for mf in archive.model_files] == ["model.sysml"]
    # The index lists the real top-level member (the package P), not proxies.
    assert dict(archive.meta.index) == {"P": "model.sysml"}


def test_exported_member_omits_proxies_and_chains(tmp_path):
    chain_model = (
        "part def B { part c; }\n"
        "part def A { part b : B; }\n"
        "part a : A;\npart x;\nattribute t : Real;\n"
        "connection conn connect a.b.c to x;"
    )
    _factory, root = _map(chain_model)
    path = tmp_path / "out.kpar"
    write_kpar(path, root, project_name="P")
    archive = read_kpar(path)
    text = read_member_text(archive, "P/model.sysml")
    assert "connect a.b.c to x;" in text  # chain rendered as the dotted path
    assert "Real" in text  # value-type reference IS emitted
    assert "Anything" not in text and "things" not in text  # no implicit bases
    # The synthesized chain feature is anonymous and owned by the connector, so it is
    # never a top-level index member.
    assert set(dict(archive.meta.index)) == {"B", "A", "a", "x", "t", "conn"}


# --- round-trips -------------------------------------------------------------


def test_text_to_kpar_to_gaphor_preserves_canonical_form(tmp_path):
    factory, root = _map(_MODEL)
    before = canonical_form(root)
    path = tmp_path / "out.kpar"
    write_kpar(path, root, project_name="P")
    assert canonical_form(_import_root(path)) == before


def test_kpar_to_gaphor_to_kpar_is_stable(tmp_path):
    _factory, root = _map(_MODEL)
    write_kpar(tmp_path / "a.kpar", root, project_name="A")
    root2 = _import_root(tmp_path / "a.kpar")
    write_kpar(tmp_path / "b.kpar", root2, project_name="B")
    root3 = _import_root(tmp_path / "b.kpar")
    assert canonical_form(root2) == canonical_form(root3)


def test_text_to_gaphor_to_kpar_to_gaphor_to_text_is_identical(tmp_path):
    _factory, root = _map(_MODEL)
    text_before = export_namespace(root)
    write_kpar(tmp_path / "out.kpar", root, project_name="P")
    assert export_namespace(_import_root(tmp_path / "out.kpar")) == text_before


def test_gaphor_to_kpar(tmp_path, element_factory, saver, loader):
    # `.gaphor` -> KPAR: a model saved+reloaded as `.gaphor` exports to a valid KPAR.
    map_package(parse(_MODEL), element_factory)
    loader(saver())
    path = tmp_path / "out.kpar"
    write_kpar(path, _root(element_factory), project_name="P")
    archive = read_kpar(path)
    assert [mf.name for mf in archive.model_files] == ["model.sysml"]


# --- CLI ---------------------------------------------------------------------


def test_kpar_export_cli_round_trips(tmp_path):
    # Import text to a .gaphor, export it to a KPAR via the CLI, re-import, compare.
    model = tmp_path / "m.gaphor"
    factory = ElementFactory()
    map_package(parse(_MODEL), factory)
    with open(model, "w", encoding="utf-8") as f:
        storage.save(f, factory)
    canonical_before = canonical_form(_root(factory))

    archive = tmp_path / "out.kpar"
    parser = cli.kpar_export_parser()
    args = parser.parse_args([str(model), str(archive), "--name", "Proj"])
    assert args.command(args) == 0

    assert read_kpar(archive).project.name == "Proj"
    assert canonical_form(_import_root(archive)) == canonical_before


def test_kpar_export_then_import_cli(tmp_path):
    # The two CLIs compose: export a model, then import it back to a new .gaphor.
    model = tmp_path / "m.gaphor"
    factory = ElementFactory()
    map_package(parse("part def Engine;\npart e : Engine;"), factory)
    with open(model, "w", encoding="utf-8") as f:
        storage.save(f, factory)

    archive = tmp_path / "out.kpar"
    export_args = cli.kpar_export_parser().parse_args([str(model), str(archive)])
    assert export_args.command(export_args) == 0

    back = tmp_path / "back.gaphor"
    import_args = cli.kpar_import_parser().parse_args([str(archive), str(back)])
    assert import_args.command(import_args) == 0
    assert back.exists()


# --- project name sanitization ----------------------------------------------


def test_project_name_with_separators_is_sanitized(tmp_path):
    _factory, root = _map("part def Engine;")
    path = tmp_path / "out.kpar"
    write_kpar(path, root, project_name="a/b\\c")
    # A slash-bearing name must not create a nested project dir; read_kpar accepts it.
    archive = read_kpar(path)
    assert "/" not in archive.root
    assert archive.project.name == "a/b\\c"  # the declared name is preserved as-is
