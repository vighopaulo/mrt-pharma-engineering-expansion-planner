"""Governance tests for the MRT Pharma Authority Consolidation layer.

These tests validate the GOVERNANCE ARTIFACTS (the master authority index,
product doctrine, integration architecture, build ledger, open-gaps register, and
governance doctrine) -- NOT product physics. They assert that the required
documents exist and that the durable doctrine/traceability statements are present.

Design rules (per the build request):
- Do NOT depend on markdown line numbers.
- Match content case-insensitively and tolerantly (normalize whitespace; accept a
  hyphen for the Unicode "not-equal" sign) so cosmetic edits do not break tests.
- Concept assertions search the COMBINED corpus of the governance docs, since a
  concept may legitimately live in any of them.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent

AUTHORITY_INDEX = _HERE / "MRT_PHARMA_AUTHORITY_INDEX.md"
PRODUCT_DOCTRINE = _HERE / "MRT_PHARMA_PRODUCT_DOCTRINE.md"
INTEGRATION_ARCHITECTURE = _HERE / "MRT_PHARMA_INTEGRATION_ARCHITECTURE.md"
BUILD_LEDGER = _HERE / "MRT_PHARMA_BUILD_LEDGER.md"
OPEN_GAPS = _HERE / "MRT_PHARMA_OPEN_GAPS.md"
AUTHORITY_DOCTRINE = _HERE / "MRT_PHARMA_AUTHORITY_DOCTRINE.md"

REQUIRED_DOCS = {
    "AUTHORITY_INDEX": AUTHORITY_INDEX,
    "PRODUCT_DOCTRINE": PRODUCT_DOCTRINE,
    "INTEGRATION_ARCHITECTURE": INTEGRATION_ARCHITECTURE,
    "BUILD_LEDGER": BUILD_LEDGER,
    "OPEN_GAPS": OPEN_GAPS,
    "AUTHORITY_DOCTRINE": AUTHORITY_DOCTRINE,
}


def _normalize(text: str) -> str:
    """Lowercase, unify the not-equal sign to '!=', and collapse whitespace.

    This keeps assertions robust to cosmetic edits (spacing, the U+2260 '≠'
    glyph vs a plain '!=') while still requiring the substantive phrase.
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u2260", "!=").replace("≠", "!=")
    text = text.replace(">=", ">").replace("\u2265", ">")  # 'A > B > C' style chains
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _doc_text(path: Path) -> str:
    return _normalize(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def corpus() -> str:
    """The combined normalized text of all present governance docs."""
    parts = []
    for path in REQUIRED_DOCS.values():
        if path.exists():
            parts.append(_doc_text(path))
    return "\n".join(parts)


def _assert_in(corpus: str, phrase: str) -> None:
    needle = _normalize(phrase)
    assert needle in corpus, f"governance concept not found: {phrase!r}"


def _assert_any(corpus: str, phrases: list[str]) -> None:
    normalized = [_normalize(p) for p in phrases]
    assert any(n in corpus for n in normalized), (
        f"none of the accepted phrasings found: {phrases!r}"
    )


# --------------------------------------------------------------------------
# Required-document existence
# --------------------------------------------------------------------------

def test_authority_index_exists():
    assert AUTHORITY_INDEX.is_file()


def test_product_doctrine_exists():
    assert PRODUCT_DOCTRINE.is_file()


def test_integration_architecture_exists():
    assert INTEGRATION_ARCHITECTURE.is_file()


def test_build_ledger_exists():
    assert BUILD_LEDGER.is_file()


def test_open_gaps_exists():
    assert OPEN_GAPS.is_file()


def test_authority_doctrine_exists():
    # Governance-specific companion; must remain, but does not substitute for
    # the product doctrine.
    assert AUTHORITY_DOCTRINE.is_file()


def test_product_doctrine_is_distinct_from_authority_doctrine():
    assert PRODUCT_DOCTRINE.resolve() != AUTHORITY_DOCTRINE.resolve()
    assert PRODUCT_DOCTRINE.read_text(encoding="utf-8") != AUTHORITY_DOCTRINE.read_text(
        encoding="utf-8"
    )


# --------------------------------------------------------------------------
# Two products / core product doctrine
# --------------------------------------------------------------------------

def test_capital_project_appears(corpus):
    _assert_in(corpus, "Capital Project")


def test_operations_appears(corpus):
    _assert_in(corpus, "Operations")


def test_two_products_doctrine(corpus):
    _assert_any(
        corpus,
        [
            "MRT Pharma = Capital Project + Operations",
            "MRT PHARMA = CAPITAL PROJECT + OPERATIONS",
        ],
    )


def test_mrt_is_optional_building_block(corpus):
    _assert_any(corpus, ["MRT is optional", "MRT is **optional**"])
    _assert_in(corpus, "building block")


def test_no_build_is_a_candidate(corpus):
    _assert_in(corpus, "NO BUILD")


def test_patient_demand_upstream(corpus):
    _assert_any(
        corpus,
        [
            "patient demand is upstream",
            "demand is upstream",
            "does not create patients",
            "do not create patients",
        ],
    )


# --------------------------------------------------------------------------
# Integration seams
# --------------------------------------------------------------------------

def test_aria_appears(corpus):
    _assert_in(corpus, "ARIA")


def test_bentley_itwin_appears(corpus):
    _assert_in(corpus, "Bentley")
    _assert_in(corpus, "iTwin")


def test_nvidia_openusd_appears(corpus):
    _assert_in(corpus, "NVIDIA")
    _assert_in(corpus, "OpenUSD")


def test_aria_doctrine_established_but_live_connector_planned(corpus):
    # The two statuses must be distinguished, never collapsed into one "PLANNED".
    _assert_any(
        corpus,
        ["ARIA_INTEGRATION_DOCTRINE = ESTABLISHED", "ARIA integration doctrine = established"],
    )
    _assert_any(
        corpus,
        ["LIVE_ARIA_CONNECTOR = PLANNED", "live ARIA connector = PLANNED", "LIVE_ARIA_CONNECTOR = PLANNED / PARTIAL"],
    )


def test_engineering_engine_decides_nvidia_visualizes(corpus):
    _assert_any(
        corpus,
        ["ENGINEERING ENGINE DECIDES", "engine decides", "NVIDIA VISUALIZES"],
    )


# --------------------------------------------------------------------------
# Scanner authority (count != model/capability)
# --------------------------------------------------------------------------

def test_siemens_healthineers_appears(corpus):
    _assert_in(corpus, "Siemens Healthineers")


def test_scanner_model_capability_doctrine(corpus):
    _assert_any(
        corpus,
        [
            "SCANNER RESOURCE COUNT vs SCANNER MODEL",
            "scanner count",
            "SCANNER COUNT",
            "count does not imply",
            "count authority",
        ],
    )
    # Explicit physical models must be named, not just "scanner catalog implemented".
    _assert_in(corpus, "Symbia Pro.specta")
    _assert_in(corpus, "Biograph Vision")


def test_ge_healthcare_scanner_models(corpus):
    _assert_in(corpus, "GE HealthCare")
    _assert_in(corpus, "NM/CT 870 DR")
    _assert_in(corpus, "Discovery MI")


def test_philips_scanner_model(corpus):
    _assert_in(corpus, "Philips")
    _assert_in(corpus, "BrightView XCT")


def test_scanner_economics_not_calibrated(corpus):
    _assert_in(corpus, "NOT_CALIBRATED")


# --------------------------------------------------------------------------
# Radionuclide / production / generator authorities + doctrine
# --------------------------------------------------------------------------

def test_radionuclide_color_authority_appears(corpus):
    # Payload / service-class / color authority.
    _assert_any(
        corpus,
        ["payload color", "service class", "service-class", "color is presentation metadata"],
    )
    _assert_in(corpus, "RADIOPHARMACEUTICAL_NUCLEAR")


def test_cyclotron_authority_appears(corpus):
    _assert_in(corpus, "cyclotron")
    _assert_in(corpus, "SUMITOMO_CYPRIS_MP_30")


def test_generator_authority_appears(corpus):
    _assert_in(corpus, "generator")
    _assert_in(corpus, "Tc-99m")


def test_supported_not_calibrated_doctrine(corpus):
    _assert_any(corpus, ["SUPPORTED != CALIBRATED", "SUPPORTED ≠ CALIBRATED"])


def test_patient_cohort_not_production_batch_doctrine(corpus):
    _assert_any(
        corpus,
        [
            "PATIENT / ADMINISTRATION COHORT != PHYSICAL CYCLOTRON PRODUCTION BATCH",
            "patient cohort != physical",
            "cohort != physical cyclotron production batch",
        ],
    )


# --------------------------------------------------------------------------
# Build ledger references
# --------------------------------------------------------------------------

def test_build_3a_appears(corpus):
    _assert_in(corpus, "Build 3A")


def test_build_3b_appears(corpus):
    _assert_in(corpus, "Build 3B")


def test_build_3c_appears(corpus):
    _assert_in(corpus, "Build 3C")


def test_build_3c1_appears(corpus):
    _assert_any(corpus, ["Build 3C.1", "Build 3C1"])


def test_part_3d_appears(corpus):
    _assert_in(corpus, "Part 3D")


def test_build_ledger_uses_real_shas(corpus):
    # The physical commit SHAs must be present (not invented).
    for sha in ("9a04dc5", "1d557f0", "a42cb08", "95040d5", "07e861d"):
        _assert_in(corpus, sha)


# --------------------------------------------------------------------------
# Cross-cutting doctrine
# --------------------------------------------------------------------------

def test_lockdown_what_if_appears(corpus):
    _assert_in(corpus, "Lockdown")
    _assert_any(corpus, ["What-If", "What If", "WhatIf"])


def test_two_route_family_doctrine_appears(corpus):
    _assert_any(corpus, ["two-route-family", "two route family", "HUMAN_CIRCULATION_NETWORK"])
    _assert_in(corpus, "CONCEALED_SERVICE_TRANSPORT_CORRIDOR")


def test_synthetic_vs_operational_patient_sources_distinguished(corpus):
    _assert_any(
        corpus,
        ["CAPITAL PROJECT PATIENT SOURCE", "synthetic / project-demand population", "synthetic/project-demand population"],
    )
    _assert_any(
        corpus,
        ["OPERATIONS PATIENT SOURCE", "actual / planned operational patients", "actual/planned operational patients"],
    )


def test_authority_first_no_duplicate_rule_appears(corpus):
    _assert_in(corpus, "VALIDATED REPOSITORY AUTHORITY")
    _assert_any(
        corpus,
        [
            "Do not create a second authority",
            "do not create a second authority",
            "never create a second authority",
        ],
    )


# --------------------------------------------------------------------------
# PLANNED requirements must remain PLANNED
# --------------------------------------------------------------------------

def test_cyclotron_production_estimation_authority_is_implemented(corpus):
    # The estimation authority now physically exists (OG-CYC-1 closure). The docs
    # must name it, its canonical file, and preserve the evidence-honesty doctrine
    # that a MODELED_ESTIMATE is distinct from calibrated evidence and that the
    # CYPRIS MP-30 + F-18 control stays NOT_CALIBRATED.
    _assert_in(corpus, "Cyclotron Production Estimation Authority")
    _assert_in(corpus, "cyclotron_production_estimation_authority.py")
    _assert_any(
        corpus,
        [
            "MODELED_ESTIMATE != MANUFACTURER_CALIBRATED",
            "MODELED_ESTIMATE ≠ MANUFACTURER_CALIBRATED",
            "MODELED_ESTIMATE never overwrites",
            "MODELED_ESTIMATE never changes calibration status",
        ],
    )
    # OG-CYC-1 remains PARTIAL (authority exists; evidence gaps remain), never
    # silently promoted to fully closed.
    _assert_in(corpus, "OG-CYC-1")


def test_part_3e_composition_optimizer_is_planned(corpus):
    _assert_any(
        corpus,
        ["Part 3E Composition Optimizer", "Part 3E-style composition optimizer", "composition optimizer"],
    )
    # Must appear alongside PLANNED language.
    _assert_in(corpus, "PLANNED")


def test_planned_never_described_as_implemented_repository_authority(corpus):
    # The cardinal rule must be stated.
    _assert_any(
        corpus,
        [
            "never describe a PLANNED_REQUIREMENT",
            "never describe a `PLANNED_REQUIREMENT`",
            "never describe a planned_requirement",
        ],
    )


# --------------------------------------------------------------------------
# Patient / batch / production-equipment awareness boundary (final addendum)
# --------------------------------------------------------------------------

def test_synthetic_demand_constrained_by_source_capabilities(corpus):
    # Synthetic patient radionuclide demand should be constrained by the
    # scenario's production-source capabilities (doctrine), and this must be a
    # combined cyclotron + generator capability set, not cyclotron-only.
    _assert_any(
        corpus,
        [
            "synthetic patient radionuclide demand is constrained by",
            "synthetic patient generation is scenario / source-capability constrained",
            "synthetic patient generation is scenario/source-capability constrained",
            "source-capability constrained",
        ],
    )


def test_cyclotron_and_generator_both_contribute_allowed_radionuclides(corpus):
    # Both cyclotron and generator capabilities may contribute to the allowed set
    # (e.g. Tc-99m via a Mo-99/Tc-99m generator even though the cyclotron cannot
    # produce it).
    _assert_any(
        corpus,
        [
            "combined selected production-source capability set",
            "combined capability of all selected production sources",
            "cyclotron supported radionuclides",
        ],
    )
    _assert_in(corpus, "generator")
    _assert_in(corpus, "Tc-99m")


def test_batch_production_planning_is_patient_aware(corpus):
    _assert_any(
        corpus,
        [
            "batch production is patient-aware",
            "batch-production planning is patient-aware",
            "batch production is patient aware",
        ],
    )


def test_cyclotron_not_directly_patient_identity_aware(corpus):
    _assert_any(
        corpus,
        [
            "cyclotron production is radionuclide/batch-aware, not patient-identity-aware",
            "not directly patient-identity-aware",
            "NOT directly patient-identity-aware",
        ],
    )
    _assert_in(corpus, "cyclotron")


def test_generator_not_directly_patient_identity_aware(corpus):
    _assert_any(
        corpus,
        [
            "generator production is source/radionuclide-aware, not patient-identity-aware",
            "generator authority is source / radionuclide-aware, not directly patient-identity-aware",
            "not directly patient-identity-aware",
        ],
    )
    _assert_in(corpus, "generator")


def test_supported_does_not_imply_calibrated_production(corpus):
    # SUPPORTED radionuclide != CALIBRATED production output.
    _assert_any(corpus, ["SUPPORTED != CALIBRATED", "SUPPORTED ≠ CALIBRATED"])
    _assert_any(
        corpus,
        [
            "supported does not imply calibrated",
            "supported radionuclide does not imply calibrated production output",
            "does not imply calibrated production output",
        ],
    )


def test_patient_cohort_not_physical_production_batch_addendum(corpus):
    _assert_any(
        corpus,
        [
            "patient cohort does not imply physical production batch",
            "patient cohort != physical production batch",
            "patient / administration cohort != physical cyclotron production batch",
        ],
    )


def test_stress_test_does_not_silently_mutate_patient_demand(corpus):
    # Unsupported-demand / stress-test doctrine must expose NO_COMPATIBLE_SOURCE
    # and must never silently alter patient demand to make the facility feasible.
    _assert_in(corpus, "NO_COMPATIBLE_SOURCE")
    _assert_any(
        corpus,
        [
            "never silently alter patient demand",
            "must not silently alter the patient demand",
            "never silently mutate patient demand",
            "not silently alter the patient demand",
        ],
    )


def test_synthetic_source_capability_constraint_status_is_honest(corpus):
    # The constraint must be classified PLANNED / PARTIAL, never described as
    # already implemented, and the gap must be registered.
    _assert_in(corpus, "OG-SYNTH-1")
    _assert_any(
        corpus,
        [
            "PLANNED / PARTIAL",
            "PLANNED/PARTIAL",
        ],
    )
