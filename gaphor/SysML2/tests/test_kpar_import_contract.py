"""Phase 3a KPAR import design-contract consistency checks.

Phase 3a commits a design contract, not importer code. These tests anchor the
contract mechanically: the document must exist and must record a decision for
every area the roadmap requires, and the four decisions ratified at the review
gate must be the ones actually written down -- so the contract cannot silently
lose a section or drift from the decided policy.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "docs/sysml-v2/KPAR_IMPORT_CONTRACT.md"

REQUIRED_SECTIONS = (
    "## Status And Scope",
    "## Identity",
    "## Storage",
    "## Representation",
    "## Mutability And Read-Only Treatment",
    "## Dependency Closure",
    "## Duplicate, Re-Import, And Update",
    "## Unsupported Syntax And Partial Import",
    "## Provenance",
    "## Entry-Point Boundary",
    "## Verification",
)


def _contract_text() -> str:
    return CONTRACT.read_text(encoding="utf-8")


def test_contract_exists():
    assert CONTRACT.is_file()


@pytest.mark.parametrize("section", REQUIRED_SECTIONS)
def test_contract_records_each_decision_area(section):
    assert section in _contract_text(), f"contract missing required section: {section}"


def test_contract_records_the_decided_stances():
    # Collapse whitespace so phrase checks survive Markdown line-wrapping.
    compact = " ".join(_contract_text().split()).lower()
    # The four forks ratified at the Phase 3a review gate must be the ones written.
    # Representation/storage: ElementFactory-backed, regenerated, not persisted.
    assert "regenerated from the pinned kpar on load" in compact
    assert "not persisted into the user's `.gaphor`" in compact
    # Unsupported-syntax policy: never silently drop; explicit unresolved records.
    assert "never silently drop" in compact
    assert "unresolved/proxy record" in compact
    # Dependency policy: closed-world over the pinned set, missing dep is an error.
    assert "closed-world" in compact
    assert "fails with a diagnostic" in compact
    # Entry-point boundary for 3b: Python API only.
    assert "python api only" in compact


def test_contract_is_design_only():
    # 3a must explicitly state it adds no importer/semantic content yet.
    lowered = _contract_text().lower()
    assert "design-only" in lowered
    assert "no importer code" in lowered
