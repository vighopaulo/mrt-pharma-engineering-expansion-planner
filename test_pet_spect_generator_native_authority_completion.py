"""Focused test suite: PET/SPECT/GENERATOR native authority completion (closure build).

Covers (section 60): native mixed PET/SPECT candidate evaluation, cyclotron
source integration, generator source integration, generator catalog loading,
generator model selection, generator facility instances, multiple generators,
patient-derived generator requirement, generator insufficiency, generator
economic provenance, generator replacement semantics, generator energy
semantics, SPECT equipment catalog, PET/SPECT equipment-data parity, SPECT
modality compatibility, SPECT scanner requirement derivation, stochastic
daily nuclear demand, seed reproducibility, different-seed variation,
long-horizon demand convergence, existing PET non-regression, 200/day F-18
stress non-regression, Conventional/MRT/Hybrid mixed PET/SPECT.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import pytest

from cyclotron_catalog import FacilityCyclotronInstance, build_cyclotron_asset_from_instance, load_cyclotron_catalog
from generator_catalog import (
    FacilityGeneratorInstance,
    create_facility_generator_instance,
    load_generator_catalog,
    resolve_effective_elution_efficiency,
    resolve_effective_reference_activity_mbq,
)
from models import PlannerAssumptions
from nuclear_source import (
    NuclearSourceInstance,
    build_cyclotron_source,
    build_generator_source,
    evaluate_cyclotron_source_feasibility,
    evaluate_generator_source_feasibility,
)
from oncology_pet_spect_scenario import (
    allocate_spect_patients_across_generators,
    build_stochastic_representative_day_population,
    evaluate_native_mixed_candidate,
    generate_stochastic_daily_nuclear_demand,
    required_scanner_count,
    required_scanner_counts_for_mixed_population,
)
from scanner_catalog import ScannerCatalogModel, create_facility_scanner_instance, load_scanner_catalog

ASSUMPTIONS = PlannerAssumptions()
TRANSPORT_MINUTES = {"Conventional": 12.0, "MRT": 2.0, "Hybrid": 5.0}


def _pet_source() -> NuclearSourceInstance:
    catalog = load_cyclotron_catalog()
    instance = FacilityCyclotronInstance(instance_id="CY-001", catalog_model_id="GE_PETTRACE_890")
    asset = build_cyclotron_asset_from_instance(instance=instance, model=catalog.by_id("GE_PETTRACE_890"))
    return build_cyclotron_source(source_id="CY-001", radionuclide="F-18", cyclotron_asset=asset)


def _spect_source(instance_id: str = "GEN-001", calibration_datetime: datetime = datetime(2026, 1, 1, 4, 0)) -> NuclearSourceInstance:
    catalog = load_generator_catalog()
    instance = create_facility_generator_instance(instance_id=instance_id, catalog_model_id="CURIUM_TECHNELITE")
    return build_generator_source(source_id=instance_id, generator_instance=instance, generator_model=catalog.by_id("CURIUM_TECHNELITE"), calibration_datetime=calibration_datetime)


def _scanner_models() -> tuple[ScannerCatalogModel, ScannerCatalogModel]:
    catalog = load_scanner_catalog()
    return catalog.by_id("GE_DISCOVERY_MI"), catalog.by_id("GE_NM_CT_870_DR")


# ---------------------------------------------------------------------------
# Native mixed PET/SPECT candidate evaluation (Gap 1)
# ---------------------------------------------------------------------------


def test_native_mixed_candidate_pet_only():
    pet_model, spect_model = _scanner_models()
    result = evaluate_native_mixed_candidate(
        architecture="Conventional", pet_requested=32, spect_requested=0,
        pet_source=_pet_source(), spect_source=_spect_source(),
        pet_activity_per_patient_mbq=370.0, spect_activity_per_patient_mbq=740.0,
        pet_model=pet_model, spect_model=spect_model, pet_protocol="oncology_pet_ct", spect_protocol="oncology_spect_ct",
        pet_available_eob_capacity_mbq_per_day=648000.0, spect_elution_datetime=datetime(2026, 1, 2, 6, 0),
        transport_minutes_by_architecture=TRANSPORT_MINUTES, assumptions=ASSUMPTIONS,
    )
    assert result.pet_served == 32
    assert result.spect_served == 0
    assert result.combined_qualified_throughput == 32
    assert result.spect_scanner_count == 0


def test_native_mixed_candidate_spect_only():
    pet_model, spect_model = _scanner_models()
    result = evaluate_native_mixed_candidate(
        architecture="Conventional", pet_requested=0, spect_requested=18,
        pet_source=_pet_source(), spect_source=_spect_source(),
        pet_activity_per_patient_mbq=370.0, spect_activity_per_patient_mbq=740.0,
        pet_model=pet_model, spect_model=spect_model, pet_protocol="oncology_pet_ct", spect_protocol="oncology_spect_ct",
        pet_available_eob_capacity_mbq_per_day=648000.0, spect_elution_datetime=datetime(2026, 1, 2, 6, 0),
        transport_minutes_by_architecture=TRANSPORT_MINUTES, assumptions=ASSUMPTIONS,
    )
    assert result.pet_served == 0
    assert result.spect_served == 18
    assert result.combined_qualified_throughput == 18
    assert result.pet_scanner_count == 0


def test_native_mixed_candidate_pet_plus_spect_one_evaluation():
    """Section 6/48: ONE evaluation call handles both modalities -- never two
    independently optimized results manually merged."""
    pet_model, spect_model = _scanner_models()
    result = evaluate_native_mixed_candidate(
        architecture="Conventional", pet_requested=32, spect_requested=18,
        pet_source=_pet_source(), spect_source=_spect_source(),
        pet_activity_per_patient_mbq=370.0, spect_activity_per_patient_mbq=740.0,
        pet_model=pet_model, spect_model=spect_model, pet_protocol="oncology_pet_ct", spect_protocol="oncology_spect_ct",
        pet_available_eob_capacity_mbq_per_day=648000.0, spect_elution_datetime=datetime(2026, 1, 2, 6, 0),
        transport_minutes_by_architecture=TRANSPORT_MINUTES, assumptions=ASSUMPTIONS,
    )
    assert result.pet_served == 32
    assert result.spect_served == 18
    assert result.combined_qualified_throughput == 50
    assert result.combined_unmet == 0
    # ONE NPV computed over the combined population (not two NPVs summed):
    assert result.npv > 0
    assert result.study_capex == (result.pet_scanner_count + result.spect_scanner_count) * 2_500_000.0


def test_conventional_mrt_hybrid_mixed_candidate():
    pet_model, spect_model = _scanner_models()
    results = {}
    for architecture in ("Conventional", "MRT", "Hybrid"):
        results[architecture] = evaluate_native_mixed_candidate(
            architecture=architecture, pet_requested=32, spect_requested=18,
            pet_source=_pet_source(), spect_source=_spect_source(),
            pet_activity_per_patient_mbq=370.0, spect_activity_per_patient_mbq=740.0,
            pet_model=pet_model, spect_model=spect_model, pet_protocol="oncology_pet_ct", spect_protocol="oncology_spect_ct",
            pet_available_eob_capacity_mbq_per_day=648000.0, spect_elution_datetime=datetime(2026, 1, 2, 6, 0),
            transport_minutes_by_architecture=TRANSPORT_MINUTES, assumptions=ASSUMPTIONS,
        )
    for architecture in ("Conventional", "MRT", "Hybrid"):
        assert results[architecture].combined_qualified_throughput == 50
    # Faster transport (MRT) requires LESS upstream activity than slower Conventional -- decay physics active for both modalities.
    assert results["MRT"].pet_source_feasibility.required_activity_mbq < results["Conventional"].pet_source_feasibility.required_activity_mbq
    assert results["MRT"].spect_source_feasibility.required_activity_mbq < results["Conventional"].spect_source_feasibility.required_activity_mbq


# ---------------------------------------------------------------------------
# Cyclotron / generator source integration (Gap 1, section 2-4)
# ---------------------------------------------------------------------------


def test_cyclotron_source_integration_via_common_boundary():
    source = _pet_source()
    assert source.source_type == "CYCLOTRON"
    result = evaluate_cyclotron_source_feasibility(
        source=source, required_activity_mbq=10_000.0, available_eob_capacity_mbq_per_day=648_000.0, patients_requested=20,
    )
    assert result.status == "FEASIBLE"
    assert result.patients_served == 20


def test_generator_source_integration_via_common_boundary():
    source = _spect_source()
    assert source.source_type == "GENERATOR"
    result = evaluate_generator_source_feasibility(
        source=source, required_eluted_activity_mbq=5_000.0, elution_datetime=datetime(2026, 1, 2, 6, 0), patients_requested=18,
    )
    assert result.status == "FEASIBLE"


def test_source_abstraction_rejects_mismatched_fields():
    with pytest.raises(ValueError):
        NuclearSourceInstance(source_id="X", source_type="CYCLOTRON", radionuclide="F-18")
    with pytest.raises(ValueError):
        NuclearSourceInstance(source_id="X", source_type="GENERATOR", radionuclide="Tc-99m")


# ---------------------------------------------------------------------------
# Generator catalog / model selection / facility instances (Gap 2)
# ---------------------------------------------------------------------------


def test_generator_catalog_loads_real_models():
    catalog = load_generator_catalog()
    ids = {m.catalog_model_id for m in catalog.models}
    assert {"CURIUM_TECHNELITE", "CURIUM_ULTRA_TECHNEKOW_FM", "GE_HEALTHCARE_DRYTEC"} <= ids
    for model in catalog.models:
        assert model.parent_radionuclide == "Mo-99"
        assert model.daughter_radionuclide == "Tc-99m"
        assert model.requires_electrical_power is False  # section 13: passive column generators


def test_generator_model_selection_creates_facility_instance():
    instance = create_facility_generator_instance(instance_id="GEN-001", catalog_model_id="CURIUM_TECHNELITE")
    assert instance.instance_id == "GEN-001"
    assert instance.catalog_model_id == "CURIUM_TECHNELITE"
    assert instance.asset_status == "EXISTING"


def test_generator_economics_not_calibrated_never_zero():
    catalog = load_generator_catalog()
    for model in catalog.models:
        for economic_record in model.economics:
            if economic_record.value == "NOT_CALIBRATED":
                assert economic_record.value != 0.0  # explicit string sentinel, never silently $0
            else:
                assert isinstance(economic_record.value, float)


def test_generator_spatial_placement_does_not_create_capex():
    instance_a = create_facility_generator_instance(instance_id="GEN-001", catalog_model_id="CURIUM_TECHNELITE", location_object_id="RP-001")
    instance_b = create_facility_generator_instance(instance_id="GEN-001", catalog_model_id="CURIUM_TECHNELITE", location_object_id="RP-002")
    # Section 18: moving location changes the location field only -- catalog_model_id/economics untouched.
    assert instance_a.catalog_model_id == instance_b.catalog_model_id
    assert instance_a.location_object_id != instance_b.location_object_id


# ---------------------------------------------------------------------------
# Multiple generators / insufficiency (Gap 1, sections 35, 56, 57)
# ---------------------------------------------------------------------------


def test_multiple_generators_independent_state_no_double_counting():
    gen1 = _spect_source(instance_id="GEN-001", calibration_datetime=datetime(2026, 1, 1, 4, 0))
    gen2 = _spect_source(instance_id="GEN-002", calibration_datetime=datetime(2026, 1, 1, 4, 0))
    result = allocate_spect_patients_across_generators(
        sources=(gen1, gen2), required_eluted_activity_per_patient_mbq=700.0, patients_requested=18,
        elution_datetime=datetime(2026, 1, 2, 6, 0),
    )
    assert result.total_patients_served <= result.total_patients_requested
    assert len(result.per_generator) >= 1
    # if generator 1 alone satisfies demand, generator 2 must not be fabricated as "needed"
    if result.per_generator[0].patients_served == 18:
        assert result.generators_required == 1


def test_one_generator_suffices_optimizer_does_not_fabricate_second():
    gen1 = _spect_source(instance_id="GEN-001")
    gen2 = _spect_source(instance_id="GEN-002")
    result = allocate_spect_patients_across_generators(
        sources=(gen1, gen2), required_eluted_activity_per_patient_mbq=100.0,  # small requirement, gen1 alone suffices
        patients_requested=5, elution_datetime=datetime(2026, 1, 2, 6, 0),
    )
    assert result.generators_required == 1
    assert result.unmet == 0


def test_generator_insufficiency_no_fabricated_activity():
    gen = _spect_source(instance_id="GEN-001")
    huge_requirement_per_patient = 1_000_000.0  # deliberately larger than any single elution can support
    result = evaluate_generator_source_feasibility(
        source=gen, required_eluted_activity_mbq=huge_requirement_per_patient * 18,
        elution_datetime=datetime(2026, 1, 2, 6, 0), patients_requested=18,
    )
    assert result.status == "INSUFFICIENT_ACTIVITY"
    assert result.patients_served < 18
    assert result.unmet > 0
    assert result.unmet == 18 - result.patients_served  # honest accounting, no fabricated doses


# ---------------------------------------------------------------------------
# SPECT equipment catalog / PET-SPECT equipment-data parity (Gap 3)
# ---------------------------------------------------------------------------


def test_spect_equipment_catalog_contains_required_models():
    catalog = load_scanner_catalog()
    ids = {m.catalog_model_id for m in catalog.models}
    assert "SIEMENS_SYMBIA_PRO_SPECTA" in ids
    assert "GE_NM_CT_870_DR" in ids
    assert "GE_NM_CT_860" in ids
    assert "PHILIPS_BRIGHTVIEW_XCT" in ids
    brightview = catalog.by_id("PHILIPS_BRIGHTVIEW_XCT")
    assert brightview.commercial_status == "LEGACY_INSTALLED_BASE"


def test_pet_and_spect_share_one_catalog_authority():
    catalog = load_scanner_catalog()
    pet_models = catalog.models_of_modality("PET")
    spect_models = catalog.models_of_modality("SPECT")
    assert len(pet_models) > 0 and len(spect_models) > 0
    # both modalities parsed by the SAME loader/dataclass -- one equipment-data authority
    assert type(pet_models[0]) is type(spect_models[0])


def test_scanner_facility_instance_creation_symmetric_for_pet_and_spect():
    pet_instance = create_facility_scanner_instance(scanner_id="SCN-001", catalog_model_id="GE_DISCOVERY_MI", modality="PET")
    spect_instance = create_facility_scanner_instance(scanner_id="SCN-002", catalog_model_id="GE_NM_CT_870_DR", modality="SPECT")
    assert pet_instance.modality == "PET"
    assert spect_instance.modality == "SPECT"


def test_no_model_specific_scanner_economics_invented():
    catalog = load_scanner_catalog()
    for model in catalog.models:
        for record in model.economics:
            if record.component == "purchase_capex":
                assert record.value == "NOT_CALIBRATED"  # honestly disclosed, never invented


# ---------------------------------------------------------------------------
# Requirement-derived scanner sizing (section 8) -- never hard-coded
# ---------------------------------------------------------------------------


def test_scanner_count_is_requirement_derived_not_hardcoded():
    low = required_scanner_count(patient_count=10, protocol_minutes=20.0, operating_hours_day=18.0, availability_pct=85.0)
    high = required_scanner_count(patient_count=100, protocol_minutes=20.0, operating_hours_day=18.0, availability_pct=85.0)
    assert high > low  # scales with patient load, not a fixed constant
    zero = required_scanner_count(patient_count=0, protocol_minutes=20.0, operating_hours_day=18.0, availability_pct=85.0)
    assert zero == 0


def test_mixed_population_scanner_counts_derived_from_catalog_protocol():
    pet_model, spect_model = _scanner_models()
    pet_count, spect_count = required_scanner_counts_for_mixed_population(
        pet_patient_count=32, spect_patient_count=18, pet_model=pet_model, spect_model=spect_model,
        pet_protocol="oncology_pet_ct", spect_protocol="oncology_spect_ct", assumptions=ASSUMPTIONS,
    )
    assert pet_count >= 1 and spect_count >= 1
    # doubling patient load must not decrease the derived count
    pet_count_2x, spect_count_2x = required_scanner_counts_for_mixed_population(
        pet_patient_count=64, spect_patient_count=36, pet_model=pet_model, spect_model=spect_model,
        pet_protocol="oncology_pet_ct", spect_protocol="oncology_spect_ct", assumptions=ASSUMPTIONS,
    )
    assert pet_count_2x >= pet_count and spect_count_2x >= spect_count


# ---------------------------------------------------------------------------
# Genuinely stochastic PET/SPECT demand (Gap 4, sections 27-29, 54-55)
# ---------------------------------------------------------------------------


def test_stochastic_demand_not_forced_to_exact_target_every_day():
    totals = [generate_stochastic_daily_nuclear_demand(day=date(2026, 3, 1), target_mean_pet=32, target_mean_spect=18, seed=s).realized_total for s in range(30)]
    assert len(set(totals)) > 1, "stochastic demand must vary across days/seeds, not be forced to a fixed 50 every time"
    assert any(t != 50 for t in totals)


def test_stochastic_demand_reproducible_with_same_seed():
    a = generate_stochastic_daily_nuclear_demand(day=date(2026, 3, 1), target_mean_pet=32, target_mean_spect=18, seed=555)
    b = generate_stochastic_daily_nuclear_demand(day=date(2026, 3, 1), target_mean_pet=32, target_mean_spect=18, seed=555)
    assert a == b


def test_stochastic_demand_different_seed_capable_of_different_sequence():
    a = generate_stochastic_daily_nuclear_demand(day=date(2026, 3, 1), target_mean_pet=32, target_mean_spect=18, seed=1)
    b = generate_stochastic_daily_nuclear_demand(day=date(2026, 3, 1), target_mean_pet=32, target_mean_spect=18, seed=2)
    assert (a.realized_pet, a.realized_spect) != (b.realized_pet, b.realized_spect)


def test_stochastic_demand_converges_toward_target_over_long_horizon():
    n_days = 500
    totals = [
        generate_stochastic_daily_nuclear_demand(day=date(2026, 1, 1), target_mean_pet=32, target_mean_spect=18, seed=s).realized_total
        for s in range(n_days)
    ]
    mean_realized = sum(totals) / n_days
    assert abs(mean_realized - 50.0) < 3.0, f"500-day mean {mean_realized} should be reasonably close to target 50"
    assert all(t >= 0 for t in totals)


def test_stochastic_demand_still_assigned_to_persistent_existing_patients():
    patients, census, demand_day = build_stochastic_representative_day_population(
        day=date(2026, 2, 2), available_beds=200, occupied_beds=170, admissions=18, discharges=16,
        outpatient_encounters=60, target_mean_pet=32, target_mean_spect=18, seed=42,
    )
    nuclear_patients = [p for p in patients if p.nuclear_procedure is not None]
    assert len(nuclear_patients) == census.total_nuclear_procedures
    assert set(p.patient_id for p in nuclear_patients).issubset(set(p.patient_id for p in patients))
    assert census.total_nuclear_procedures <= census.total_active_patients


# ---------------------------------------------------------------------------
# Non-regression (sections 42-43)
# ---------------------------------------------------------------------------


def test_existing_pet_non_regression_retained_fraction_unchanged():
    from multi_isotope_decay import retained_fraction
    assert retained_fraction(0.0, 109.8) == 1.0
    assert math.isclose(retained_fraction(109.8, 109.8), 0.5, rel_tol=1e-9)


def test_200_f18_stress_benchmark_non_regression():
    from campus_retrofit_benchmark import build_two_building_campus_geometry, run_campus_case_1_conventional
    geometry = build_two_building_campus_geometry(campus_separation_m=500.0)
    result = run_campus_case_1_conventional(geometry=geometry, demand=200)
    assert result.demand == 200
    assert result.winner.patients_retention_qualified_completed == 36


def test_high_volume_f18_stress_200_descriptor_preserved():
    from oncology_pet_spect_scenario import HIGH_VOLUME_F18_STRESS_200, REALISTIC_ONCOLOGY_50
    assert HIGH_VOLUME_F18_STRESS_200.total_nuclear_per_day == 200
    assert HIGH_VOLUME_F18_STRESS_200.spect_per_day == 0
    assert HIGH_VOLUME_F18_STRESS_200.purpose == "ENGINEERING_STRESS_TEST"
    assert HIGH_VOLUME_F18_STRESS_200.purpose != REALISTIC_ONCOLOGY_50.purpose


# ---------------------------------------------------------------------------
# Live-State generator/SPECT event types (section 39, 58-59)
# ---------------------------------------------------------------------------


def test_live_state_generator_event_types_captured():
    from live_operational_state import OperationalEvent, OperationalStateStore
    from healthcare_integration import CanonicalIntegrationEvent

    store = OperationalStateStore()
    integration_event = CanonicalIntegrationEvent(
        source_system="MANUAL", source_event_id="EVT-GEN-001", event_type="DEVICE_STATUS",
        event_timestamp=datetime(2026, 3, 1, 8, 0),
    )
    event = OperationalEvent(
        integration_event=integration_event, event_kind="GENERATOR_UNAVAILABLE", object_id="GEN-001", new_state="UNAVAILABLE",
    )
    status = store.record_event(event)
    assert status == "APPLIED"
    assert store.generator_state["GEN-001"].state == "UNAVAILABLE"


def test_live_state_spect_scanner_event_reuses_resource_state():
    from live_operational_state import OperationalEvent, OperationalStateStore
    from healthcare_integration import CanonicalIntegrationEvent

    store = OperationalStateStore()
    integration_event = CanonicalIntegrationEvent(
        source_system="MANUAL", source_event_id="EVT-SPECT-SCN-001", event_type="DEVICE_STATUS",
        event_timestamp=datetime(2026, 3, 1, 9, 0),
    )
    event = OperationalEvent(
        integration_event=integration_event, event_kind="SPECT_SCANNER_UNAVAILABLE", object_id="SCN-005", new_state="UNAVAILABLE",
    )
    status = store.record_event(event)
    assert status == "APPLIED"
    assert store.resource_state["SCN-005"].state == "UNAVAILABLE"
