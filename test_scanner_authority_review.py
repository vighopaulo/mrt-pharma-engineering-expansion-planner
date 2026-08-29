"""Scanner Authority Review — Part 3E Readiness (focused review test).

Locks the FACTUAL scanner authority physically present in the repository at the
time of the review (Section 54). These tests assert what the repository actually
implements/discloses — never invented scanner performance, pricing, or geometry.

Scope note: this is a REVIEW build. No scanner engine code is changed; these
tests pin the current honest authority state so a future Part 3E build cannot
silently regress it (e.g. by inventing model economics or letting a SPECT-only
pool satisfy PET demand).
"""

from __future__ import annotations

import pytest

from clinical_resource_identity import (
    ClinicalResource,
    ClinicalResourceInventory,
    build_modality_tagged_scanner_pool,
)
from oncology_pet_spect_scenario import (
    check_modality_capacity,
    required_scanner_count,
    required_scanner_counts_for_mixed_population,
)
from scanner_catalog import (
    ScannerCatalogModel,
    create_facility_scanner_instance,
    load_scanner_catalog,
)

from models import PlannerAssumptions

ASSUMPTIONS = PlannerAssumptions()

_PET_IDS = {"GE_DISCOVERY_MI", "SIEMENS_BIOGRAPH_VISION"}
_SPECT_IDS = {
    "SIEMENS_SYMBIA_PRO_SPECTA",
    "GE_NM_CT_870_DR",
    "GE_NM_CT_860",
    "PHILIPS_BRIGHTVIEW_XCT",
}


# ---------------------------------------------------------------------------
# 1-7: catalog loads + each required model physically exists
# ---------------------------------------------------------------------------


def test_01_scanner_catalog_loads():
    catalog = load_scanner_catalog()
    assert catalog.schema_version
    assert len(catalog.models) == 6


def test_02_siemens_symbia_prospecta_exists():
    assert load_scanner_catalog().by_id("SIEMENS_SYMBIA_PRO_SPECTA").model == "Symbia Pro.specta"


def test_03_siemens_biograph_vision_exists():
    assert load_scanner_catalog().by_id("SIEMENS_BIOGRAPH_VISION").model == "Biograph Vision"


def test_04_ge_nm_ct_870_dr_exists():
    assert load_scanner_catalog().by_id("GE_NM_CT_870_DR").model == "NM/CT 870 DR"


def test_05_ge_nm_ct_860_exists():
    assert load_scanner_catalog().by_id("GE_NM_CT_860").model == "NM/CT 860"


def test_06_ge_discovery_mi_exists():
    assert load_scanner_catalog().by_id("GE_DISCOVERY_MI").model == "Discovery MI"


def test_07_philips_brightview_xct_exists():
    assert load_scanner_catalog().by_id("PHILIPS_BRIGHTVIEW_XCT").model == "BrightView XCT"


# ---------------------------------------------------------------------------
# 8-12: identity preservation (manufacturer / model / modality / commercial)
# ---------------------------------------------------------------------------


def test_08_manufacturer_identity_preserved():
    catalog = load_scanner_catalog()
    assert catalog.by_id("SIEMENS_BIOGRAPH_VISION").manufacturer == "Siemens Healthineers"
    assert catalog.by_id("GE_DISCOVERY_MI").manufacturer == "GE HealthCare"
    assert catalog.by_id("PHILIPS_BRIGHTVIEW_XCT").manufacturer == "Philips"


def test_09_model_identity_preserved_not_collapsed_to_generic():
    # Manufacturers are NOT collapsed into a generic "PET scanner"/"SPECT scanner".
    models = {m.model for m in load_scanner_catalog().models}
    assert "PET scanner" not in models
    assert "SPECT scanner" not in models
    assert {"Biograph Vision", "Discovery MI", "Symbia Pro.specta"} <= models


def test_10_modality_identity_preserved():
    catalog = load_scanner_catalog()
    for mid in _PET_IDS:
        assert catalog.by_id(mid).modality == "PET"
    for mid in _SPECT_IDS:
        assert catalog.by_id(mid).modality == "SPECT"


def test_11_commercial_status_preserved():
    catalog = load_scanner_catalog()
    # current new-purchase candidates
    assert catalog.by_id("GE_DISCOVERY_MI").commercial_status == "current"
    assert catalog.by_id("GE_DISCOVERY_MI").new_purchase_candidate is True


def test_12_brightview_xct_remains_legacy_installed_base():
    brightview = load_scanner_catalog().by_id("PHILIPS_BRIGHTVIEW_XCT")
    assert brightview.commercial_status == "LEGACY_INSTALLED_BASE"
    # legacy installed base must NOT be recommended as a new purchase
    assert brightview.new_purchase_candidate is False


# ---------------------------------------------------------------------------
# 13-15: scanner count != scanner model; PET != SPECT capacity
# ---------------------------------------------------------------------------


def test_13_scanner_count_is_not_scanner_model_authority():
    # A count is a plain integer requirement; it carries no model identity.
    count = required_scanner_count(
        patient_count=50, protocol_minutes=20.0,
        operating_hours_day=ASSUMPTIONS.operating_hours_per_day,
        availability_pct=ASSUMPTIONS.scanner_availability_pct,
    )
    assert isinstance(count, int)
    assert not isinstance(count, ScannerCatalogModel)
    # scaling patient load changes the COUNT, never selects a model
    more = required_scanner_count(
        patient_count=200, protocol_minutes=20.0,
        operating_hours_day=ASSUMPTIONS.operating_hours_per_day,
        availability_pct=ASSUMPTIONS.scanner_availability_pct,
    )
    assert more > count


def test_14_pet_demand_cannot_be_satisfied_by_spect_only_pool():
    # A SPECT-only pool has ZERO PET capacity: PET demand is infeasible.
    pet_check, spect_check = check_modality_capacity(
        pet_scanner_count=0, spect_scanner_count=6,
        pet_demand=30, spect_demand=0, assumptions=ASSUMPTIONS,
    )
    assert pet_check.scanner_count == 0
    assert pet_check.daily_capacity == 0.0
    assert pet_check.feasible is False  # SPECT scanners never serve PET demand


def test_15_spect_demand_cannot_be_satisfied_by_pet_only_pool():
    pet_check, spect_check = check_modality_capacity(
        pet_scanner_count=6, spect_scanner_count=0,
        pet_demand=0, spect_demand=30, assumptions=ASSUMPTIONS,
    )
    assert spect_check.scanner_count == 0
    assert spect_check.daily_capacity == 0.0
    assert spect_check.feasible is False  # PET scanners never serve SPECT demand


# ---------------------------------------------------------------------------
# 16-17: catalog carries no patient identity; scheduling is a separate layer
# ---------------------------------------------------------------------------


def test_16_scanner_catalog_does_not_require_patient_identity():
    model = load_scanner_catalog().by_id("GE_DISCOVERY_MI")
    field_names = set(vars(model).keys())
    for forbidden in ("patient_id", "patient_name", "patient_room", "patient"):
        assert forbidden not in field_names


def test_17_scanner_instance_has_no_patient_identity():
    inst = create_facility_scanner_instance(
        scanner_id="SCN-001", catalog_model_id="GE_DISCOVERY_MI", modality="PET",
    )
    field_names = set(vars(inst).keys())
    assert "patient_id" not in field_names
    # a scanner resource identity is separate from patient identity
    assert inst.scanner_id == "SCN-001"
    assert inst.catalog_model_id == "GE_DISCOVERY_MI"


# ---------------------------------------------------------------------------
# 18-19: excess scanner capacity/capability does not create demand
# ---------------------------------------------------------------------------


def test_18_excess_scanner_capacity_does_not_create_patients():
    # Doubling scanners keeps demand fixed; capacity is headroom, not patients.
    few = check_modality_capacity(
        pet_scanner_count=2, spect_scanner_count=2, pet_demand=10, spect_demand=10,
        assumptions=ASSUMPTIONS,
    )
    many = check_modality_capacity(
        pet_scanner_count=20, spect_scanner_count=20, pet_demand=10, spect_demand=10,
        assumptions=ASSUMPTIONS,
    )
    assert few[0].demand == many[0].demand == 10  # PET demand unchanged
    assert few[1].demand == many[1].demand == 10  # SPECT demand unchanged
    assert many[0].daily_capacity > few[0].daily_capacity  # only headroom grows


def test_19_zero_patients_require_zero_scanners():
    # Scanner capability never manufactures radionuclide demand / patients.
    assert required_scanner_count(
        patient_count=0, protocol_minutes=20.0,
        operating_hours_day=ASSUMPTIONS.operating_hours_per_day,
        availability_pct=ASSUMPTIONS.scanner_availability_pct,
    ) == 0


# ---------------------------------------------------------------------------
# 20-21: economics honestly NOT_CALIBRATED; missing fields stay missing
# ---------------------------------------------------------------------------


def test_20_scanner_economics_not_falsely_manufacturer_calibrated():
    for model in load_scanner_catalog().models:
        for record in model.economics:
            # never a fabricated number and never falsely "manufacturer_calibrated"
            assert record.value == "NOT_CALIBRATED"
            assert record.calibration_status == "not_calibrated"


def test_21_model_specific_missing_fields_remain_honestly_missing():
    for model in load_scanner_catalog().models:
        assert model.power_specification_status == "NOT_CALIBRATED"
        assert model.active_power_kw is None
        assert model.idle_power_kw is None
        # dimensions are a free-text note, not a fabricated machine envelope
        assert model.dimensions_footprint_notes is None or "NOT_CALIBRATED" in model.dimensions_footprint_notes


# ---------------------------------------------------------------------------
# 22-23: Part 3D count gate preserved; model identity not silently lost
# ---------------------------------------------------------------------------


def test_22_part3d_scanner_count_gate_remains_count_based():
    # The Part 3D physical-feasibility scanner gate is a COUNT gate: peak
    # occupancy <= available count. It does not consume a scanner model.
    import inspect
    import whole_oncology_four_architecture_optimization as wo4a

    src = inspect.getsource(wo4a.compute_clinical_resource_peak_occupancy)
    assert "candidate.scanners" in src           # aggregate count input
    assert "scanner_peak" in src and "scanner_available" in src
    # the gate does not import/select a ScannerCatalogModel
    assert "ScannerCatalogModel" not in src
    assert "load_scanner_catalog" not in src


def test_23_scanner_model_identity_survives_where_model_authority_is_used():
    # Where the model-aware sizing path is used, model identity is preserved and
    # per-model acquisition minutes drive the count (not a generic constant).
    catalog = load_scanner_catalog()
    vision = catalog.by_id("SIEMENS_BIOGRAPH_VISION")
    discovery = catalog.by_id("GE_DISCOVERY_MI")
    # model-specific acquisition minutes genuinely differ
    assert vision.typical_acquisition_minutes_per_protocol["oncology_pet_ct"] \
        != discovery.typical_acquisition_minutes_per_protocol["oncology_pet_ct"]
    pet_count, spect_count = required_scanner_counts_for_mixed_population(
        pet_patient_count=32, spect_patient_count=18,
        pet_model=discovery, spect_model=catalog.by_id("GE_NM_CT_870_DR"),
        pet_protocol="oncology_pet_ct", spect_protocol="oncology_spect_ct",
        assumptions=ASSUMPTIONS,
    )
    assert pet_count >= 1 and spect_count >= 1


# ---------------------------------------------------------------------------
# 24: review readiness classification matches physical implementation
# ---------------------------------------------------------------------------


def test_24_review_readiness_matches_physical_implementation():
    catalog = load_scanner_catalog()
    # quantity-selection READY: requirement-derived sizing exists and scales
    assert required_scanner_count(
        patient_count=100, protocol_minutes=20.0, operating_hours_day=18.0, availability_pct=85.0,
    ) > required_scanner_count(
        patient_count=10, protocol_minutes=20.0, operating_hours_day=18.0, availability_pct=85.0,
    )
    # modality-selection READY: both pools populated, distinctly typed
    assert len(catalog.models_of_modality("PET")) >= 1
    assert len(catalog.models_of_modality("SPECT")) >= 1
    # model-selection NOT ready: every economics record is NOT_CALIBRATED
    assert all(
        rec.value == "NOT_CALIBRATED"
        for m in catalog.models for rec in m.economics
    )


# ---------------------------------------------------------------------------
# 25: no unrelated scanner values fabricated (modality-tagged pool honesty)
# ---------------------------------------------------------------------------


def test_25_no_fabricated_values_untagged_scanners_excluded_from_both_pools():
    # An untagged (modality=None) scanner must NOT silently count as PET or SPECT
    # capacity -- no fabricated modality assignment.
    untagged = ClinicalResource(resource_id="SCN-001", resource_type="SCANNER")
    inv = ClinicalResourceInventory(
        injection_rooms=(ClinicalResource(resource_id="INJ-001", resource_type="INJECTION_ROOM"),),
        uptake_rooms=(ClinicalResource(resource_id="UP-001", resource_type="UPTAKE_ROOM"),),
        scanners=(untagged,),
    )
    assert inv.scanners_of_modality("PET") == ()
    assert inv.scanners_of_modality("SPECT") == ()

    # A modality-tagged pool assigns exactly the requested counts, no extras.
    pool = build_modality_tagged_scanner_pool(pet_scanner_count=3, spect_scanner_count=2)
    assert sum(1 for s in pool if s.modality == "PET") == 3
    assert sum(1 for s in pool if s.modality == "SPECT") == 2
    assert len(pool) == 5


def test_25b_modality_may_only_tag_scanner_resources():
    # Guard: a non-SCANNER resource cannot carry a modality (no fabricated tags).
    with pytest.raises(ValueError):
        ClinicalResource(resource_id="INJ-001", resource_type="INJECTION_ROOM", modality="PET")


# ---------------------------------------------------------------------------
# 26-33: Hospital Master Calendar / Operations seam (Section N)
#
# These pin the FACTUAL calendar/operations authority state the scanner review
# documents in Section N. They assert what the repository actually implements
# (scanner resource identity in the calendar layer, per-date availability,
# patient->scanner traceability, the honest MAINTENANCE/downtime gap) so a
# future Operations build cannot silently regress or overstate it. No calendar
# engine is created or modified here.
# ---------------------------------------------------------------------------

from datetime import date

from clinical_resource_identity import (
    build_deterministic_resource_inventory,
    build_calendar_with_no_exceptions,
    ResourceAvailabilityCalendar,
)
from scanner_catalog import ScannerOperatingState


def test_26_long_horizon_operational_calendar_authority_exists():
    # The six-month / long-horizon operational master-plan authority physically
    # exists (Section N.0/N.1) -- it is NOT merely a single representative day.
    import long_horizon_operational_planning as lh

    assert hasattr(lh, "OperatingCalendar")
    assert hasattr(lh, "run_long_horizon_operational_plan")
    assert hasattr(lh, "LongHorizonMasterPlan")
    assert hasattr(lh, "PatientOperationalPlan")
    # horizon is data-driven (planning_start_date/planning_end_date), NOT a
    # hardcoded "six month" magic constant.
    cal = lh.OperatingCalendar(
        planning_start_date=date(2026, 1, 1), planning_end_date=date(2026, 6, 30),
    )
    operating = cal.operating_dates()
    assert len(operating) > 100  # ~6 months of weekdays, horizon honored
    assert cal.is_operating_day(date(2026, 1, 1)) in (True, False)  # weekday-driven


def test_27_scanner_resource_carries_stable_identity_in_calendar_layer():
    # A scanner is a first-class resource with a persistent SCN-xxx identity the
    # calendar references (Section N.2) -- distinct from equipment catalog data.
    inv = build_deterministic_resource_inventory(
        injection_room_count=2, uptake_room_count=2, scanner_count=3,
    )
    scanner_ids = [s.resource_id for s in inv.scanners]
    assert len(scanner_ids) == 3
    assert all(sid.startswith("SCN-") for sid in scanner_ids)
    assert len(set(scanner_ids)) == 3  # unique, stable identities


def test_28_scanner_availability_is_date_level_and_never_deletes_identity():
    # Per-DATE availability exists; an UNAVAILABLE scanner is EXCLUDED from that
    # date's active set but its identity is preserved (Section N.2/N.5).
    inv = build_deterministic_resource_inventory(
        injection_room_count=1, uptake_room_count=1, scanner_count=2,
    )
    down_scanner = inv.scanners[0].resource_id
    day = date(2026, 3, 2)
    cal = ResourceAvailabilityCalendar(
        inventory=inv, unavailable_by_date={day: frozenset({down_scanner})},
    )
    active = cal.active_resource_ids_for_date(resource_type="SCANNER", day=day)
    assert down_scanner not in active            # excluded that date
    assert len(active) == 1                       # the other scanner remains
    # identity is NOT deleted -- still resolvable in the inventory
    assert inv.by_id(down_scanner).resource_id == down_scanner
    # and AVAILABLE again on a day with no exception
    open_cal = build_calendar_with_no_exceptions(inv)
    assert len(open_cal.active_resource_ids_for_date(resource_type="SCANNER", day=day)) == 2


def test_29_scanner_operating_state_has_maintenance_but_no_intraday_window():
    # MAINTENANCE is a representable operating state (Section N.5), but downtime
    # is date-level / state-level only -- there is deliberately NO intra-day
    # maintenance time-window field on the scanner instance.
    from scanner_catalog import create_facility_scanner_instance
    import typing

    states = set(typing.get_args(ScannerOperatingState))
    assert {"AVAILABLE", "IN_USE", "MAINTENANCE", "UNAVAILABLE"} <= states

    inst = create_facility_scanner_instance(
        scanner_id="SCN-001", catalog_model_id="GE_DISCOVERY_MI", modality="PET",
    )
    fields = set(vars(inst).keys())
    # honest gap: no intra-day maintenance start/end window is modeled
    for absent in (
        "maintenance_start_minute", "maintenance_end_minute",
        "downtime_window", "service_window_minutes",
    ):
        assert absent not in fields


def test_30_patient_operational_plan_binds_patient_to_scanner_and_scan_window():
    # The calendar/plan layer binds a committed patient to a persistent scanner
    # resource identity + scan window (Section N.4 traceability).
    from long_horizon_operational_planning import PatientOperationalPlan
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(PatientOperationalPlan)}
    assert "scanner_resource_id" in field_names
    assert "scan_window_minutes" in field_names
    # and the full production traceability keys are present on the same plan row
    for key in ("radionuclide", "cyclotron_id", "batch_id", "production_window_id", "release_time_minutes"):
        assert key in field_names


def test_31_production_clinical_trace_carries_full_patient_to_scanner_chain():
    # PATIENT -> RADIONUCLIDE -> cyclotron/batch/window -> release -> transport
    # -> injection -> uptake -> scan is physically present on one trace row.
    from production_clinical_schedule import ProductionClinicalPatientTrace
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(ProductionClinicalPatientTrace)}
    required_chain = {
        "patient_id", "radionuclide", "assigned_cyclotron_id", "batch_id",
        "production_window_id", "batch_release_time_minutes",
        "payload_id", "delivery_job_id", "transport_arrival_time_minutes",
        "injection_start", "injection_end", "uptake_start", "uptake_end",
        "scan_start", "scan_end",
    }
    missing = required_chain - field_names
    assert not missing, f"traceability chain missing links: {sorted(missing)}"


def test_32_operational_patient_record_is_patient_aware_but_catalog_is_not():
    # The calendar/scheduling record is patient-aware (identity, appointment,
    # radionuclide); the scanner CATALOG stays equipment-only (Section N.3).
    from long_horizon_operational_planning import CanonicalOperationalPatientRecord
    import dataclasses

    rec_fields = {f.name for f in dataclasses.fields(CanonicalOperationalPatientRecord)}
    assert {"internal_model_patient_id", "external_patient_reference",
            "radionuclide", "scheduled_date", "existing_scanner_appointment_minute"} <= rec_fields

    # scanner catalog model carries NO patient identity (the boundary holds)
    model = load_scanner_catalog().by_id("SIEMENS_BIOGRAPH_VISION")
    for forbidden in ("patient_id", "external_patient_reference", "appointment", "scheduled_date"):
        assert forbidden not in set(vars(model).keys())


def test_33_scanner_double_booking_validator_exists_for_calendar_horizon():
    # The horizon authority enforces that a physical scanner is not assigned two
    # overlapping patient intervals on the same date (Section N.2 occupancy).
    import inspect
    import long_horizon_operational_planning as lh

    assert hasattr(lh, "validate_no_double_resource_assignment")
    src = inspect.getsource(lh.validate_no_double_resource_assignment)
    # SCANNER is one of the resource types guarded against double assignment
    assert "SCANNER" in src


# ---------------------------------------------------------------------------
# 34-40: FINAL Part 3E readiness conclusions (Sections 16, 28-31, H.1, M.7)
#
# These lock the review's FINAL determination against the physical repository
# so a future build cannot silently regress or overstate it. They assert only
# what physically exists today (no aspirational behavior).
# ---------------------------------------------------------------------------


def test_34_part3d_feasible_derived_for_canonical_four_but_not_light_mrt_variant():
    # Section H.1 (honest correction): the FOUR canonical evaluators derive
    # `feasible` via the Part 3D contract, while the separate Light-MRT-dominant
    # VARIANT and the zonal-hybrid CANDIDATE still hardcode feasible=True.
    import inspect
    import whole_oncology_four_architecture_optimization as wo4a

    # canonical four consume the derivation seam
    for fn_name in (
        "evaluate_manual_conventional",
        "evaluate_automated_conventional",
        "_evaluate_mrt_style_architecture",
    ):
        src = inspect.getsource(getattr(wo4a, fn_name))
        assert "_physical_feasibility_result_fields" in src, fn_name
        assert "derive_physical_feasibility" in src, fn_name

    # the derivation seam sets feasible from the derived status (not a literal)
    seam = inspect.getsource(wo4a._physical_feasibility_result_fields)
    assert 'pf.physical_feasibility_status != "INFEASIBLE"' in seam

    # the Light-MRT-dominant VARIANT does NOT consume the contract (documented gap)
    light = inspect.getsource(wo4a.evaluate_light_mrt_dominant)
    assert "derive_physical_feasibility" not in light
    assert "feasible=True" in light  # hardcoded (OG-SCN-2)


def test_35_scanner_quantity_selection_ready():
    # PART_3E_SCANNER_QUANTITY_SELECTION_READY = YES: requirement-derived sizing
    # exists, scales with demand, and is a plain integer (no model needed).
    small = required_scanner_count(
        patient_count=20, protocol_minutes=20.0, operating_hours_day=18.0, availability_pct=85.0,
    )
    large = required_scanner_count(
        patient_count=120, protocol_minutes=20.0, operating_hours_day=18.0, availability_pct=85.0,
    )
    assert isinstance(small, int) and isinstance(large, int)
    assert large > small


def test_36_scanner_modality_selection_ready_pet_spect_pools_distinct():
    # PART_3E_SCANNER_MODALITY_SELECTION_READY = YES: both modality pools exist
    # and are enforced-distinct (adding SPECT demand never adds PET capacity).
    catalog = load_scanner_catalog()
    assert len(catalog.models_of_modality("PET")) >= 1
    assert len(catalog.models_of_modality("SPECT")) >= 1
    pet_a, _ = check_modality_capacity(
        pet_scanner_count=3, spect_scanner_count=3, pet_demand=10, spect_demand=10, assumptions=ASSUMPTIONS,
    )
    pet_b, _ = check_modality_capacity(
        pet_scanner_count=3, spect_scanner_count=30, pet_demand=10, spect_demand=10, assumptions=ASSUMPTIONS,
    )
    # PET capacity is identical regardless of SPECT pool size (no cross-feed)
    assert pet_a.daily_capacity == pet_b.daily_capacity


def test_37_scanner_model_selection_not_ready_no_rankable_economics_or_power():
    # PART_3E_SCANNER_MODEL_SELECTION_READY = NO: models are NOT_YET_RANKABLE --
    # every economics record and every power spec is NOT_CALIBRATED.
    for model in load_scanner_catalog().models:
        assert model.power_specification_status == "NOT_CALIBRATED"
        assert all(rec.value == "NOT_CALIBRATED" for rec in model.economics)


def test_38_equipment_energy_authority_exists_but_scanner_energy_not_calibrated():
    # Section M.7 correction: a SCHEDULE-DERIVED equipment energy authority
    # physically exists (duty from the actual plan), but scanner energy is
    # honestly NOT_CALIBRATED because no per-model power spec exists -- the
    # money is gated by construction, never fabricated to $0-with-a-number.
    import equipment_energy_opex as eeo

    assert hasattr(eeo, "derive_scanner_state_minutes")   # duty IS derived
    assert hasattr(eeo, "compute_scanner_energy_for_plan")
    assert hasattr(eeo, "compute_equipment_daily_energy")
    # a record with no power spec yields NOT_CALIBRATED + zero calculated kWh,
    # with the duration preserved as uncalibrated minutes (never silent zero).
    import inspect
    src = inspect.getsource(eeo.compute_equipment_daily_energy)
    assert "uncalibrated_minutes" in src
    assert "NOT_CALIBRATED" in src
    assert "is_energy_usable_measurement" in src  # only measured kW contributes


def test_39_scanner_catalog_carries_existing_new_retain_replace_authority():
    # Existing/new/retain/replace/legacy authority is first-class (Section 10).
    from scanner_catalog import ScannerAssetStatus, create_facility_scanner_instance
    import typing

    statuses = set(typing.get_args(ScannerAssetStatus))
    assert {"EXISTING", "PROPOSED", "UPGRADE", "REPLACEMENT"} <= statuses
    # legacy installed base is retained as installed-selectable but not a new buy
    brightview = load_scanner_catalog().by_id("PHILIPS_BRIGHTVIEW_XCT")
    assert brightview.installed_equipment_selectable is True
    assert brightview.new_purchase_candidate is False
    inst = create_facility_scanner_instance(
        scanner_id="SCN-010", catalog_model_id="PHILIPS_BRIGHTVIEW_XCT", modality="SPECT",
        asset_status="EXISTING",
    )
    assert inst.asset_status == "EXISTING"


def test_40_part3e_phase1_ready_at_class_and_modality_level():
    # PART_3E_PHASE_1_READY = YES at CLASS_AND_MODALITY level: quantity + modality
    # authority is sufficient; model-specific ranking is deferred (NOT blocking).
    catalog = load_scanner_catalog()
    quantity_ready = required_scanner_count(
        patient_count=50, protocol_minutes=20.0, operating_hours_day=18.0, availability_pct=85.0,
    ) >= 1
    modality_ready = (
        len(catalog.models_of_modality("PET")) >= 1 and len(catalog.models_of_modality("SPECT")) >= 1
    )
    model_rankable = any(
        rec.value != "NOT_CALIBRATED" for m in catalog.models for rec in m.economics
    )
    assert quantity_ready is True
    assert modality_ready is True
    assert model_rankable is False  # honest: model ranking deferred
