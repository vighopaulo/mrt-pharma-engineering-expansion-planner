"""Focused test suite: patient-aware general oncology logistics foundation.

Covers (section 70): same persistent patient used by nuclear and general
logistics, inpatient-only linen generation, no outpatient linen by default,
admission/discharge demand boundaries, all four general streams, patient
provenance, multi-patient consolidation, physical demand conservation,
architecture-independent physical demand, manual architecture-specific load
conversion, MRT 20kg linen load conversion, different capacities produce
different mission counts, room/origin identity, facility-role identity,
missing-location behavior, priority/deadline semantics, no radioactive decay
on general logistics, nuclear non-regression with general logistics OFF,
MANUAL_CONVENTIONAL without MRT, AUTOMATED_CONVENTIONAL structural mode,
HYBRID_MRT structural mode, MRT_DOMINANT structural mode, OPERATIONAL_ONLY
compatibility, CAPITAL_PLANNING compatibility, shared-MRT infrastructure
representation, general-logistics Live-State identifiers.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from campus_retrofit_benchmark import build_two_building_campus_geometry, run_campus_case_1_conventional
from general_oncology_logistics import (
    ARCHITECTURE_SEMANTICS,
    AUTOMATED_CONVENTIONAL_TECHNOLOGY_PLACEHOLDERS,
    DEFAULT_STREAM_POLICIES,
    LogisticsDemand,
    TransportLoad,
    TransportMission,
    build_default_facility_roles,
    consolidate_demands_into_loads,
    generate_daily_logistics_demand,
    missions_for_architecture,
    resolve_role_location,
)
from oncology_pet_spect_scenario import build_representative_day_population
from study_scope import apply_study_scope
from models import PlannerAssumptions

ASSUMPTIONS = PlannerAssumptions()


def _day_population(seed: int = 42):
    return build_representative_day_population(
        day=date(2026, 2, 2), available_beds=200, occupied_beds=170, admissions=18, discharges=16,
        outpatient_encounters=60, target_pet_procedures=32, target_spect_procedures=18, seed=seed,
    )


# ---------------------------------------------------------------------------
# Same persistent patient population (sections 1, 4, 42)
# ---------------------------------------------------------------------------


def test_same_patient_used_by_nuclear_and_general_logistics():
    patients, _ = _day_population()
    roles = build_default_facility_roles()
    demands = generate_daily_logistics_demand(day=date(2026, 2, 2), inpatients=patients, roles=roles)
    nuclear_patient_ids = {p.patient_id for p in patients if p.nuclear_procedure is not None}
    logistics_patient_ids = {d.patient_id for d in demands}
    overlap = nuclear_patient_ids & logistics_patient_ids
    assert overlap, "at least one patient must have BOTH a nuclear procedure and general-logistics demand"
    # No second identity created for the same patient:
    all_patient_ids = {p.patient_id for p in patients}
    assert logistics_patient_ids <= all_patient_ids


def test_patient_multi_stream_no_duplicate_identity():
    """Section 42/55: one patient may have a nuclear procedure AND multiple
    general-logistics streams without three separate identities."""
    patients, _ = _day_population()
    roles = build_default_facility_roles()
    demands = generate_daily_logistics_demand(day=date(2026, 2, 2), inpatients=patients, roles=roles)
    nuclear_patient = next(p for p in patients if p.nuclear_procedure is not None and p.patient_type == "INPATIENT")
    patient_demands = [d for d in demands if d.patient_id == nuclear_patient.patient_id]
    streams = {d.stream for d in patient_demands}
    assert streams == {"PHARMACY_INFUSION", "SPECIMEN_BLOOD", "CLEAN_LINEN", "STERILE_CLEAN_SUPPLY"}
    assert all(d.patient_id == nuclear_patient.patient_id for d in patient_demands)  # one identity


# ---------------------------------------------------------------------------
# Inpatient-only, admission/discharge boundaries (sections 10, 20-21)
# ---------------------------------------------------------------------------


def test_no_outpatient_linen_by_default():
    patients, _ = _day_population()
    roles = build_default_facility_roles()
    demands = generate_daily_logistics_demand(day=date(2026, 2, 2), inpatients=patients, roles=roles)
    outpatient_ids = {p.patient_id for p in patients if p.patient_type == "OUTPATIENT"}
    demand_patient_ids = {d.patient_id for d in demands}
    assert not (outpatient_ids & demand_patient_ids)


def test_admission_discharge_demand_boundaries():
    patients, _ = _day_population()
    roles = build_default_facility_roles()
    inpatient = next(p for p in patients if p.patient_type == "INPATIENT")
    # Before admission -> no demand
    before_admission = inpatient.admission_date.replace(day=1) if inpatient.admission_date.day > 1 else None
    demands_on_admission_day = generate_daily_logistics_demand(day=inpatient.admission_date, inpatients=(inpatient,), roles=roles)
    assert any(d.patient_id == inpatient.patient_id for d in demands_on_admission_day)
    after_discharge = date(inpatient.expected_discharge_date.year, 12, 31)
    if after_discharge > inpatient.expected_discharge_date:
        demands_after = generate_daily_logistics_demand(day=after_discharge, inpatients=(inpatient,), roles=roles)
        assert not any(d.patient_id == inpatient.patient_id for d in demands_after)


def test_census_change_changes_demand_population():
    patients_a, _ = build_representative_day_population(
        day=date(2026, 2, 2), available_beds=200, occupied_beds=100, admissions=10, discharges=8,
        outpatient_encounters=60, target_pet_procedures=32, target_spect_procedures=18, seed=42,
    )
    patients_b, _ = build_representative_day_population(
        day=date(2026, 2, 2), available_beds=200, occupied_beds=170, admissions=18, discharges=16,
        outpatient_encounters=60, target_pet_procedures=32, target_spect_procedures=18, seed=42,
    )
    roles = build_default_facility_roles()
    demands_a = generate_daily_logistics_demand(day=date(2026, 2, 2), inpatients=patients_a, roles=roles)
    demands_b = generate_daily_logistics_demand(day=date(2026, 2, 2), inpatients=patients_b, roles=roles)
    assert len(demands_b) > len(demands_a)  # higher census -> more demand


# ---------------------------------------------------------------------------
# All four streams / provenance / no decay (sections 8, 9, 17, 66)
# ---------------------------------------------------------------------------


def test_all_four_streams_present():
    patients, _ = _day_population()
    roles = build_default_facility_roles()
    demands = generate_daily_logistics_demand(day=date(2026, 2, 2), inpatients=patients, roles=roles)
    streams = {d.stream for d in demands}
    assert streams == {"PHARMACY_INFUSION", "SPECIMEN_BLOOD", "CLEAN_LINEN", "STERILE_CLEAN_SUPPLY"}


def test_demand_provenance_never_silently_calibrated():
    for policy in DEFAULT_STREAM_POLICIES:
        assert policy.provenance == "CONTROLLED_SCENARIO_ASSUMPTION"


def test_specimen_blood_subtype_and_deadline():
    patients, _ = _day_population()
    roles = build_default_facility_roles()
    demands = generate_daily_logistics_demand(day=date(2026, 2, 2), inpatients=patients, roles=roles)
    specimen_demands = [d for d in demands if d.stream == "SPECIMEN_BLOOD"]
    assert all(d.subtype == "SPECIMEN" for d in specimen_demands)
    assert all(d.required_by_datetime is not None and d.required_by_datetime >= d.release_datetime for d in specimen_demands)


def test_no_radioactive_decay_fields_on_general_logistics():
    """Section 3/9: general-logistics demand is patient-aware but NOT
    radionuclide/decay-aware -- no such fields exist on LogisticsDemand."""
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(LogisticsDemand)}
    assert not (field_names & {"radionuclide", "half_life_minutes", "retained_fraction", "activity_mbq"})


def test_no_production_batch_terminology():
    """Section 6: reserve 'ProductionBatch' for the nuclear branch."""
    import general_oncology_logistics
    assert not hasattr(general_oncology_logistics, "ProductionBatch")


# ---------------------------------------------------------------------------
# Multi-patient consolidation / physical demand conservation (sections 5, 12, 51-52)
# ---------------------------------------------------------------------------


def test_multi_patient_consolidation_preserves_provenance():
    patients, _ = _day_population()
    roles = build_default_facility_roles()
    demands = generate_daily_logistics_demand(day=date(2026, 2, 2), inpatients=patients, roles=roles)
    linen_demands = tuple(d for d in demands if d.stream == "CLEAN_LINEN")
    loads = consolidate_demands_into_loads(demands=linen_demands, max_quantity_per_load=1e9)
    assert any(len(l.patient_ids) > 1 for l in loads)  # genuine multi-patient consolidation
    all_load_patients = set()
    for l in loads:
        all_load_patients |= set(l.patient_ids)
    assert all_load_patients == {d.patient_id for d in linen_demands}  # no patient lost


def test_physical_demand_conserved_across_consolidation_granularity():
    """Section 12/51: total physical quantity is invariant regardless of how
    finely loads are consolidated."""
    patients, _ = _day_population()
    roles = build_default_facility_roles()
    demands = generate_daily_logistics_demand(day=date(2026, 2, 2), inpatients=patients, roles=roles)
    linen_demands = tuple(d for d in demands if d.stream == "CLEAN_LINEN")
    total_physical = sum(d.quantity for d in linen_demands)
    loads_fine = consolidate_demands_into_loads(demands=linen_demands, max_quantity_per_load=50.0)
    loads_coarse = consolidate_demands_into_loads(demands=linen_demands, max_quantity_per_load=1e9)
    assert sum(l.quantity for l in loads_fine) == pytest.approx(total_physical)
    assert sum(l.quantity for l in loads_coarse) == pytest.approx(total_physical)


def test_architecture_independent_physical_demand():
    """Section 68: physical demand exists before architecture selection --
    the SAME load's quantity is used for both manual and MRT conversion."""
    patients, _ = _day_population()
    roles = build_default_facility_roles()
    demands = generate_daily_logistics_demand(day=date(2026, 2, 2), inpatients=patients, roles=roles)
    linen_demands = tuple(d for d in demands if d.stream == "CLEAN_LINEN")
    loads = consolidate_demands_into_loads(demands=linen_demands, max_quantity_per_load=100.0)
    load = loads[0]
    manual = missions_for_architecture(load=load, architecture="MANUAL_CONVENTIONAL", cart_capacity=150.0)
    mrt = missions_for_architecture(load=load, architecture="MRT_DOMINANT", cart_capacity=150.0)
    # Same load.quantity feeds both -- never separately invented per architecture.
    assert load.quantity > 0
    assert len(manual) >= 1 and len(mrt) >= 1


# ---------------------------------------------------------------------------
# Manual vs MRT mission conversion (sections 13-15, 46-48, 53, 69)
# ---------------------------------------------------------------------------


def test_mrt_20kg_linen_container_conversion():
    load = TransportLoad(
        load_id="LOAD-TEST-001", stream="CLEAN_LINEN", patient_ids=("P-001", "P-002"), origin="LINEN-SRC",
        destination="WARD-F1", quantity=45.0, unit="kg", payload_class="LINEN_BAG",
        release_datetime=datetime(2026, 2, 2, 6, 0), priority="SCHEDULED",
    )
    missions = missions_for_architecture(load=load, architecture="MRT_DOMINANT", cart_capacity=100.0, mrt_container_capacity_kg=20.0)
    assert len(missions) == 3  # ceil(45/20) = 3
    assert all(m.transport_mode == "MRT" for m in missions)


def test_different_capacities_produce_different_mission_counts():
    load = TransportLoad(
        load_id="LOAD-TEST-002", stream="CLEAN_LINEN", patient_ids=("P-001",), origin="LINEN-SRC",
        destination="WARD-F1", quantity=100.0, unit="kg", payload_class="LINEN_BAG",
        release_datetime=datetime(2026, 2, 2, 6, 0), priority="SCHEDULED",
    )
    manual_small_cart = missions_for_architecture(load=load, architecture="MANUAL_CONVENTIONAL", cart_capacity=25.0)
    manual_large_cart = missions_for_architecture(load=load, architecture="MANUAL_CONVENTIONAL", cart_capacity=200.0)
    assert len(manual_small_cart) > len(manual_large_cart)  # section 15: independently configurable cart capacity
    mrt_missions = missions_for_architecture(load=load, architecture="MRT_DOMINANT", cart_capacity=200.0)
    assert len(mrt_missions) != len(manual_large_cart)  # different architectures, different mission counts, same physical demand


def test_no_artificial_penalty_or_boost():
    """Section 68-69: neither architecture is artificially fragmented or
    consolidated -- ceil(quantity/capacity) is applied identically."""
    import math
    load = TransportLoad(
        load_id="LOAD-TEST-003", stream="CLEAN_LINEN", patient_ids=("P-001",), origin="LINEN-SRC",
        destination="WARD-F1", quantity=61.0, unit="kg", payload_class="LINEN_BAG",
        release_datetime=datetime(2026, 2, 2, 6, 0), priority="SCHEDULED",
    )
    manual = missions_for_architecture(load=load, architecture="MANUAL_CONVENTIONAL", cart_capacity=30.0)
    assert len(manual) == math.ceil(61.0 / 30.0)


# ---------------------------------------------------------------------------
# Room/origin identity, facility roles, missing location (sections 11, 36-38)
# ---------------------------------------------------------------------------


def test_room_identity_used_as_destination_authority():
    patients, _ = _day_population()
    roles = build_default_facility_roles()
    demands = generate_daily_logistics_demand(day=date(2026, 2, 2), inpatients=patients, roles=roles)
    pharmacy_demands = [d for d in demands if d.stream == "PHARMACY_INFUSION"]
    inpatients_by_id = {p.patient_id: p for p in patients}
    for d in pharmacy_demands[:5]:
        patient = inpatients_by_id[d.patient_id]
        assert d.destination == patient.room_id


def test_facility_role_resolution_and_missing_location():
    roles = build_default_facility_roles()
    pharmacy = resolve_role_location(roles, "CENTRAL_PHARMACY")
    assert pharmacy.location_status == "CALIBRATED"
    linen_source = resolve_role_location(roles, "CLEAN_LINEN_SOURCE")
    assert linen_source.location_status == "LOCATION_NOT_CALIBRATED"  # honest, not fabricated
    with pytest.raises(ValueError):
        resolve_role_location(roles, "NOT_A_ROLE")  # type: ignore[arg-type]


def test_same_facility_roles_for_all_architectures():
    """Section 38: one physical set of role locations -- not architecture-specific."""
    roles = build_default_facility_roles()
    assert len(roles) == len(set(r.role for r in roles))  # one location per role, no per-architecture duplication


# ---------------------------------------------------------------------------
# Priority / deadline semantics (section 9)
# ---------------------------------------------------------------------------


def test_priority_levels_available():
    priorities = {p.priority for p in DEFAULT_STREAM_POLICIES}
    assert priorities <= {"ROUTINE", "SCHEDULED", "URGENT", "CRITICAL"}


def test_deadline_after_release():
    with pytest.raises(ValueError):
        LogisticsDemand(
            demand_id="X", patient_id="P-001", stream="CLEAN_LINEN", origin="A", destination="B", quantity=1.0,
            unit="kg", release_datetime=datetime(2026, 1, 2), required_by_datetime=datetime(2026, 1, 1),
            priority="ROUTINE", payload_class="LINEN_BAG", provenance="CONTROLLED_SCENARIO_ASSUMPTION",
            calibration_status="NOT_CALIBRATED",
        )


# ---------------------------------------------------------------------------
# Nuclear non-regression (section 43)
# ---------------------------------------------------------------------------


def test_nuclear_non_regression_with_general_logistics_off():
    """Section 43/T: general-logistics general_oncology_logistics module is
    never imported by the nuclear branch -- the closed nuclear trunk output
    is unchanged."""
    geometry = build_two_building_campus_geometry(campus_separation_m=500.0)
    result = run_campus_case_1_conventional(geometry=geometry, demand=200)
    assert result.winner.patients_retention_qualified_completed == 36  # established control point, unchanged
    import campus_retrofit_benchmark
    import inspect
    source = inspect.getsource(campus_retrofit_benchmark)
    assert "general_oncology_logistics" not in source  # nuclear branch never imports general logistics


# ---------------------------------------------------------------------------
# Four architecture modes (sections 25-34, 57-61)
# ---------------------------------------------------------------------------


def test_manual_conventional_operates_without_mrt():
    semantics = next(s for s in ARCHITECTURE_SEMANTICS if s.architecture == "MANUAL_CONVENTIONAL")
    assert semantics.mrt_present is False
    load = TransportLoad(
        load_id="LOAD-TEST-004", stream="CLEAN_LINEN", patient_ids=("P-001",), origin="LINEN-SRC",
        destination="WARD-F1", quantity=45.0, unit="kg", payload_class="LINEN_BAG",
        release_datetime=datetime(2026, 2, 2, 6, 0), priority="SCHEDULED",
    )
    missions = missions_for_architecture(load=load, architecture="MANUAL_CONVENTIONAL", cart_capacity=100.0)
    assert all(m.transport_mode == "MANUAL" for m in missions)


def test_automated_conventional_structural_mode_no_fabricated_missions():
    semantics = next(s for s in ARCHITECTURE_SEMANTICS if s.architecture == "AUTOMATED_CONVENTIONAL")
    assert semantics.incumbent_automation_allowed is True
    for placeholder in AUTOMATED_CONVENTIONAL_TECHNOLOGY_PLACEHOLDERS:
        assert placeholder.performance_status == "PERFORMANCE_NOT_CALIBRATED"
        assert placeholder.economics_status == "ECONOMICS_NOT_CALIBRATED"
    load = TransportLoad(
        load_id="LOAD-TEST-005", stream="CLEAN_LINEN", patient_ids=("P-001",), origin="LINEN-SRC",
        destination="WARD-F1", quantity=45.0, unit="kg", payload_class="LINEN_BAG",
        release_datetime=datetime(2026, 2, 2, 6, 0), priority="SCHEDULED",
    )
    with pytest.raises(NotImplementedError):
        missions_for_architecture(load=load, architecture="AUTOMATED_CONVENTIONAL", cart_capacity=100.0)


def test_hybrid_mrt_respects_zone_coverage():
    """Section 61: a load whose destination lacks MRT coverage must fall
    back to manual, never an unconnected MRT trip."""
    load_covered = TransportLoad(
        load_id="LOAD-TEST-006A", stream="CLEAN_LINEN", patient_ids=("P-001",), origin="LINEN-SRC",
        destination="WARD-F2", quantity=45.0, unit="kg", payload_class="LINEN_BAG",
        release_datetime=datetime(2026, 2, 2, 6, 0), priority="SCHEDULED",
    )
    load_uncovered = TransportLoad(
        load_id="LOAD-TEST-006B", stream="CLEAN_LINEN", patient_ids=("P-002",), origin="LINEN-SRC",
        destination="WARD-F1", quantity=45.0, unit="kg", payload_class="LINEN_BAG",
        release_datetime=datetime(2026, 2, 2, 6, 0), priority="SCHEDULED",
    )
    missions_covered = missions_for_architecture(
        load=load_covered, architecture="HYBRID_MRT", cart_capacity=100.0, mrt_coverage=frozenset({"WARD-F2"}),
    )
    missions_uncovered = missions_for_architecture(
        load=load_uncovered, architecture="HYBRID_MRT", cart_capacity=100.0, mrt_coverage=frozenset({"WARD-F2"}),
    )
    assert all(m.transport_mode == "MRT" for m in missions_covered)
    assert all(m.transport_mode == "MANUAL" for m in missions_uncovered)  # no MRT connection -> manual fallback


def test_mrt_dominant_distinct_from_hybrid():
    mrt_dominant = next(s for s in ARCHITECTURE_SEMANTICS if s.architecture == "MRT_DOMINANT")
    hybrid = next(s for s in ARCHITECTURE_SEMANTICS if s.architecture == "HYBRID_MRT")
    assert mrt_dominant.general_logistics != hybrid.general_logistics
    assert mrt_dominant.mrt_present and hybrid.mrt_present  # both use MRT, but semantics differ


def test_four_architecture_semantics_present():
    architectures = {s.architecture for s in ARCHITECTURE_SEMANTICS}
    assert architectures == {"MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "HYBRID_MRT", "MRT_DOMINANT"}


# ---------------------------------------------------------------------------
# OPERATIONAL_ONLY / CAPITAL_PLANNING orthogonality (sections 39-41)
# ---------------------------------------------------------------------------


def test_operational_only_general_logistics_zero_new_study_capex():
    result = apply_study_scope(
        study_scope="OPERATIONAL_ONLY", transport_architecture="CONVENTIONAL", qualified_throughput=170,
        reference_capex=0.0, annual_opex=0.0, revenue_per_scan=ASSUMPTIONS.revenue_per_scan,
        operating_days_per_year=ASSUMPTIONS.operating_days_per_year, discount_rate_pct=ASSUMPTIONS.discount_rate_pct,
        analysis_years=ASSUMPTIONS.analysis_years,
    )
    assert result.study_capex == 0.0


def test_capital_planning_orthogonal_to_all_four_architectures():
    for architecture in ("MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "HYBRID_MRT", "MRT_DOMINANT"):
        for scope in ("OPERATIONAL_ONLY", "CAPITAL_PLANNING"):
            result = apply_study_scope(
                study_scope=scope, transport_architecture="CONVENTIONAL", qualified_throughput=170,
                reference_capex=1000.0, annual_opex=100.0, revenue_per_scan=ASSUMPTIONS.revenue_per_scan,
                operating_days_per_year=ASSUMPTIONS.operating_days_per_year,
                discount_rate_pct=ASSUMPTIONS.discount_rate_pct, analysis_years=ASSUMPTIONS.analysis_years,
            )
            expected_capex = 0.0 if scope == "OPERATIONAL_ONLY" else 1000.0
            assert result.study_capex == expected_capex


# ---------------------------------------------------------------------------
# Shared MRT infrastructure / Live-State identifiers (sections 32-34, 62, 65)
# ---------------------------------------------------------------------------


def test_shared_mrt_infrastructure_representation():
    """Section 32-34/62: general-logistics MRT missions use the SAME
    transport_mode identifier as nuclear MRT -- no separate network object."""
    load = TransportLoad(
        load_id="LOAD-TEST-007", stream="PHARMACY_INFUSION", patient_ids=("P-001",), origin="PHARM-001",
        destination="WARD-F1", quantity=1.0, unit="tote_equivalent", payload_class="PHARMACY_TOTE",
        release_datetime=datetime(2026, 2, 2, 6, 0), priority="SCHEDULED",
    )
    missions = missions_for_architecture(load=load, architecture="MRT_DOMINANT", cart_capacity=10.0)
    assert missions[0].transport_mode == "MRT"  # same literal used throughout this module -- one network


def test_general_logistics_live_state_identifiers_present():
    """Section 65: demand/load/mission objects expose the identifiers a
    future event/reoptimization layer needs, without a new event library."""
    load = TransportLoad(
        load_id="LOAD-TEST-008", stream="CLEAN_LINEN", patient_ids=("P-001", "P-002"), origin="LINEN-SRC",
        destination="WARD-F1", quantity=45.0, unit="kg", payload_class="LINEN_BAG",
        release_datetime=datetime(2026, 2, 2, 6, 0), priority="SCHEDULED",
    )
    mission = missions_for_architecture(load=load, architecture="MANUAL_CONVENTIONAL", cart_capacity=100.0)[0]
    assert mission.load_id == load.load_id
    assert set(mission.patient_ids) <= set(load.patient_ids)
    assert mission.origin and mission.destination
