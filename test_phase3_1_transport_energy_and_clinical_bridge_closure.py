"""Phase 3.1 closure tests -- Part A (transport energy/maintenance) + Part B
(vendor-neutral clinical patient-demand schema completion).
"""

from __future__ import annotations

from datetime import date

import pytest

import mrt_transport_energy_maintenance_authority as mtem
import reactive_engineering_economic_consequence_authority as reac


_ECON_KW = dict(
    throughput_patients_per_day=30.0, revenue_per_scan=2000.0, operating_days_per_year=300,
    discount_rate_pct=8.0, analysis_years=10, baseline_capex=5_000_000.0, baseline_annual_opex=1_000_000.0,
)


# ---------------------------------------------------------------------------
# PART A: 1-9 Light-MRT design basis, moving power, route energy, napkin check
# ---------------------------------------------------------------------------


def test_1_light_mrt_loaded_mass_is_5kg():
    assert mtem.FULLY_LOADED_MRT_CARRIER_MASS_KG == pytest.approx(5.0)


def test_2_empty_mass_is_2kg():
    assert mtem.EMPTY_MRT_CARRIER_MASS_KG == pytest.approx(2.0)


def test_3_max_payload_is_3kg():
    assert mtem.MAX_MRT_PAYLOAD_KG == pytest.approx(3.0)
    assert mtem.EMPTY_MRT_CARRIER_MASS_KG + mtem.MAX_MRT_PAYLOAD_KG == pytest.approx(mtem.FULLY_LOADED_MRT_CARRIER_MASS_KG)


def test_4_mrt_carrier_capex_is_5000():
    assert mtem.MRT_CARRIER_CAPEX_USD.active_value == pytest.approx(5_000.0)


def test_5_mrt_guideway_capex_per_m_is_2000():
    assert mtem.MRT_GUIDEWAY_CAPEX_PER_M_USD == pytest.approx(2_000.0)


def test_6_carrier_and_guideway_costs_remain_separate():
    assert mtem.MRT_CARRIER_CAPEX_USD.active_value != mtem.MRT_GUIDEWAY_CAPEX_PER_M_USD
    assert mtem.MRT_CARRIER_CAPEX_USD.units == "USD per carrier"


def test_7_moving_power_default_is_editable():
    assert mtem.MRT_MOVING_POWER_KW.active_value == pytest.approx(0.75)
    assert mtem.MRT_MOVING_POWER_KW.user_editable is True
    overridden = mtem.MRT_MOVING_POWER_KW.with_override(1.0)
    assert overridden.active_value == pytest.approx(1.0)
    assert mtem.MRT_MOVING_POWER_KW.active_value == pytest.approx(0.75)  # original untouched


def test_8_mrt_route_energy_is_derived_not_hardcoded():
    short = mtem.compute_mrt_mission_energy(horizontal_m=10.0, vertical_m=0.0)
    long = mtem.compute_mrt_mission_energy(horizontal_m=100.0, vertical_m=0.0)
    assert long.one_way_energy_kwh > short.one_way_energy_kwh
    assert long.one_way_energy_kwh == pytest.approx(short.one_way_energy_kwh * 10.0)  # E=P*t is linear in distance at fixed speed


def test_9_napkin_route_reconciles():
    result = mtem.compute_mrt_mission_energy(horizontal_m=63.0, vertical_m=32.0)
    assert result.horizontal_time_s == pytest.approx(21.0)
    assert result.vertical_time_s == pytest.approx(21.333, abs=1e-2)
    assert result.one_way_time_s == pytest.approx(42.333, abs=1e-2)
    assert result.one_way_energy_kwh == pytest.approx(0.00882, abs=1e-4)
    assert result.round_trip_energy_kwh == pytest.approx(0.01764, abs=1e-4)
    cost = mtem.compute_mrt_mission_electricity_opex_usd(energy_kwh=result.round_trip_energy_kwh)
    assert cost == pytest.approx(0.00265, abs=1e-4)


# ---------------------------------------------------------------------------
# 10-14: maintenance authorities + geometry reactivity
# ---------------------------------------------------------------------------


def test_10_carrier_maintenance_defaults_to_10_percent():
    assert mtem.MRT_CARRIER_MAINTENANCE_FRACTION_PER_YEAR.active_value == pytest.approx(0.10)
    assert mtem.compute_mrt_carrier_annual_maintenance_usd(carrier_count=1) == pytest.approx(500.0)


def test_11_guideway_maintenance_defaults_to_10_percent():
    assert mtem.MRT_GUIDEWAY_MAINTENANCE_FRACTION_PER_YEAR.active_value == pytest.approx(0.10)
    assert mtem.compute_mrt_guideway_annual_maintenance_usd(installed_guideway_capex_usd=222.0 * 2_000.0) == pytest.approx(44_400.0)


def test_12_guideway_maintenance_uses_installed_network_not_mission_route():
    # Installed network changes, mission route constant -- maintenance MUST react.
    record_network_change = reac.evaluate_move_endpoint_consequence(
        change_id="T12A", endpoint_id="EP-01", what_if_id="W1", source_lockdown_id="L0",
        installed_network_before_m=222.0, installed_network_after_m=250.0, mission_route_before_m=95.0, mission_route_after_m=95.0,
        guideway_capex_per_m=mtem.MRT_GUIDEWAY_CAPEX_PER_M_USD, **_ECON_KW,
    )
    assert record_network_change.annual_maintenance_opex_delta_usd != 0.0
    # Mission route changes, installed network constant -- maintenance basis is unaffected by mission route alone.
    record_mission_only = reac.evaluate_move_endpoint_consequence(
        change_id="T12B", endpoint_id="EP-01", what_if_id="W1", source_lockdown_id="L0",
        installed_network_before_m=222.0, installed_network_after_m=222.0, mission_route_before_m=95.0, mission_route_after_m=150.0,
        guideway_capex_per_m=mtem.MRT_GUIDEWAY_CAPEX_PER_M_USD, **_ECON_KW,
    )
    assert record_mission_only.annual_maintenance_opex_delta_usd == 0.0


def test_13_mission_distance_affects_mrt_energy():
    inputs = mtem.MrtMissionEnergyInputs(
        horizontal_m_before=63.0, horizontal_m_after=100.0, vertical_m_before=32.0, vertical_m_after=32.0, missions_per_year=250.0,
    )
    delta = mtem.compute_mrt_mission_energy_annual_opex_delta_usd(inputs)
    assert delta > 0.0  # longer horizontal leg -> more annual mission electricity OPEX


def test_14_building_and_endpoint_changes_affect_legitimate_maintenance_and_energy():
    building_record = reac.evaluate_move_building_consequence(
        change_id="T14A", building_id="BLDG-B", what_if_id="W1", source_lockdown_id="L0",
        inter_building_distance_before_m=50.0, inter_building_distance_after_m=150.0, guideway_capex_per_m=mtem.MRT_GUIDEWAY_CAPEX_PER_M_USD,
        **_ECON_KW,
    )
    assert building_record.annual_maintenance_opex_delta_usd == pytest.approx(building_record.capex_delta_usd * 0.10)

    energy_inputs = mtem.MrtMissionEnergyInputs(
        horizontal_m_before=63.0, horizontal_m_after=163.0, vertical_m_before=32.0, vertical_m_after=32.0, missions_per_year=250.0,
    )
    endpoint_record = reac.evaluate_move_endpoint_consequence(
        change_id="T14B", endpoint_id="EP-01", what_if_id="W1", source_lockdown_id="L0",
        installed_network_before_m=222.0, installed_network_after_m=322.0, mission_route_before_m=95.0, mission_route_after_m=195.0,
        guideway_capex_per_m=mtem.MRT_GUIDEWAY_CAPEX_PER_M_USD, mrt_mission_energy_inputs=energy_inputs, **_ECON_KW,
    )
    assert endpoint_record.annual_maintenance_opex_delta_usd != 0.0
    assert endpoint_record.annual_energy_opex_delta_usd != 0.0
    assert endpoint_record.annual_opex_delta_usd == pytest.approx(
        endpoint_record.annual_maintenance_opex_delta_usd + endpoint_record.annual_energy_opex_delta_usd
    )


# ---------------------------------------------------------------------------
# 15-19: AGV/PTS/RP-PTS/Manual authority closure + $12,000/m provenance
# ---------------------------------------------------------------------------


def test_15_agv_energy_maintenance_authority_closed():
    entries = {e.technology: e for e in mtem.audit_transport_energy_maintenance_authorities()}
    assert entries["AGV"].status in ("VALIDATED", "CONTROLLED_DEFAULT")
    assert mtem.compute_agv_distance_energy_kwh(distance_km=2.0) == pytest.approx(1.0)


def test_16_pts_energy_maintenance_authority_closed():
    entries = {e.technology: e for e in mtem.audit_transport_energy_maintenance_authorities()}
    assert entries["ORDINARY_PTS"].status in ("VALIDATED", "CONTROLLED_DEFAULT")
    assert mtem.compute_pts_distance_energy_kwh(distance_km=2.0) == pytest.approx(0.2)


def test_17_rp_pts_remains_distinct():
    from editable_default_authority import RP_PTS_ANNUAL_ENERGY_OPEX_USD, RP_PTS_ANNUAL_MAINTENANCE_OPEX_USD, RP_PTS_OPERATING_SPEED_M_PER_S
    from conventional_transport_authority import DEFAULT_PTS_NETWORK

    assert RP_PTS_OPERATING_SPEED_M_PER_S.active_value == pytest.approx(6.1)
    assert DEFAULT_PTS_NETWORK.speed_m_per_s == pytest.approx(6.0)
    assert RP_PTS_OPERATING_SPEED_M_PER_S.active_value != DEFAULT_PTS_NETWORK.speed_m_per_s
    assert RP_PTS_ANNUAL_ENERGY_OPEX_USD.parameter_id != "PTS_ANNUAL_ENERGY_OPEX_USD"  # separately identifiable name
    assert RP_PTS_ANNUAL_MAINTENANCE_OPEX_USD.parameter_id != "PTS_ANNUAL_MAINTENANCE_OPEX_USD"


def test_18_manual_propulsion_electricity_is_zero():
    assert mtem.MANUAL_PROPULSION_ELECTRICITY_OPEX_USD == 0.0


def test_19_12000_per_m_provenance_resolved():
    assert mtem.classify_12000_per_m_provenance() == "LEGITIMATE_OTHER_SCOPE"


def test_20_lifecycle_economics_consume_legitimate_opex_changes():
    record = reac.evaluate_move_building_consequence(
        change_id="T20", building_id="BLDG-B", what_if_id="W1", source_lockdown_id="L0",
        inter_building_distance_before_m=50.0, inter_building_distance_after_m=150.0, guideway_capex_per_m=mtem.MRT_GUIDEWAY_CAPEX_PER_M_USD,
        **_ECON_KW,
    )
    # NPV delta must now reflect BOTH the added CapEx and the added maintenance OPEX
    # (previously, before this phase, only CapEx was consumed -- annual_opex_delta_usd was hardcoded 0.0).
    assert record.annual_opex_delta_usd != 0.0
    assert record.npv_delta_usd != pytest.approx(-record.capex_delta_usd)  # no longer capex-only


# ---------------------------------------------------------------------------
# PART B: 21-32 clinical patient-demand schema completion
# ---------------------------------------------------------------------------


def test_21_external_patient_id_maps_to_canonical_patient_id():
    from healthcare_integration import CrossSourceIdentityRegistry
    from healthcare_adapters import ingest_aria_fixture

    registry = CrossSourceIdentityRegistry()
    result = ingest_aria_fixture(registry=registry)
    assert result.canonical_records[0].internal_model_patient_id.startswith("P-ARIA-")
    assert ("VARIAN_ARIA", "ARIA-PAT-001") in registry.external_references_for_patient(result.canonical_records[0].internal_model_patient_id)


def test_22_multiple_external_ids_represent_one_canonical_patient():
    from healthcare_integration import CrossSourceIdentityRegistry
    from healthcare_adapters import ingest_aria_fixture, ingest_ge_dosewatch_fixture

    registry = CrossSourceIdentityRegistry()
    aria_result = ingest_aria_fixture(registry=registry)
    canonical_id = aria_result.canonical_records[0].internal_model_patient_id
    ingest_ge_dosewatch_fixture(
        registry=registry, fixture=(
            {"fixture_label": "SYNTHETIC_TEST_FIXTURE", "event_type": "IMAGING_STUDY", "external_patient_reference": "DW-PAT-777", "external_procedure_reference": "DW-STUDY-777"},
        ),
        known_canonical_patient_id=canonical_id,
    )
    refs = registry.external_references_for_patient(canonical_id)
    assert ("VARIAN_ARIA", "ARIA-PAT-001") in refs
    assert ("GE_DOSEWATCH", "DW-PAT-777") in refs
    assert len(refs) == 2


def test_23_earliest_latest_scheduled_date_bounds_serialize_and_validate():
    from long_horizon_operational_planning import CanonicalOperationalPatientRecord

    record = CanonicalOperationalPatientRecord(
        internal_model_patient_id="P-W1", demand_status="COMMITTED", patient_type="OUTPATIENT", radionuclide="F-18",
        prescribed_activity_mbq=200.0, scheduled_date=date(2026, 10, 5), source_provenance="EHR",
        scheduled_date_mutability="OPTIMIZABLE_WITHIN_WINDOW",
        earliest_scheduled_date=date(2026, 10, 3), latest_scheduled_date=date(2026, 10, 7),
    )
    assert record.earliest_scheduled_date == date(2026, 10, 3)
    assert record.latest_scheduled_date == date(2026, 10, 7)
    with pytest.raises(ValueError):
        CanonicalOperationalPatientRecord(
            internal_model_patient_id="P-W2", demand_status="COMMITTED", patient_type="OUTPATIENT", radionuclide="F-18",
            prescribed_activity_mbq=200.0, scheduled_date=date(2026, 10, 5), source_provenance="EHR",
            scheduled_date_mutability="OPTIMIZABLE_WITHIN_WINDOW",
            earliest_scheduled_date=date(2026, 10, 9), latest_scheduled_date=date(2026, 10, 7),
        )


def test_24_fixed_clinical_date_remains_fixed_even_with_window_fields_present():
    from healthcare_integration import CrossSourceIdentityRegistry
    from healthcare_adapters import ingest_aria_fixture

    registry = CrossSourceIdentityRegistry()
    result = ingest_aria_fixture(registry=registry)
    outpatient = next(r for r in result.canonical_records if r.patient_type == "OUTPATIENT")
    assert outpatient.scheduled_date_mutability == "FIXED"
    assert outpatient.scheduled_date == date(2026, 10, 5)  # governing clinical date, unaffected by (absent) window fields
    assert outpatient.earliest_scheduled_date is None and outpatient.latest_scheduled_date is None


def test_25_flexible_window_preserved_not_invented():
    from long_horizon_operational_planning import CanonicalOperationalPatientRecord

    record = CanonicalOperationalPatientRecord(
        internal_model_patient_id="P-W3", demand_status="COMMITTED", patient_type="OUTPATIENT", radionuclide="F-18",
        prescribed_activity_mbq=200.0, scheduled_date=date(2026, 10, 5), source_provenance="EHR",
        scheduled_date_mutability="OPTIMIZABLE_WITHIN_WINDOW",
        earliest_scheduled_date=date(2026, 10, 3), latest_scheduled_date=date(2026, 10, 7),
    )
    assert record.earliest_scheduled_date == date(2026, 10, 3)
    assert record.latest_scheduled_date == date(2026, 10, 7)
    # Backward compatibility: default (both None) is preserved.
    record_no_window = CanonicalOperationalPatientRecord(
        internal_model_patient_id="P-W4", demand_status="COMMITTED", patient_type="OUTPATIENT", radionuclide="F-18",
        prescribed_activity_mbq=200.0, scheduled_date=date(2026, 10, 5), source_provenance="USER_ENTERED",
    )
    assert record_no_window.earliest_scheduled_date is None
    assert record_no_window.latest_scheduled_date is None


def test_26_optional_modality_preserved_via_adapter():
    from healthcare_integration import CrossSourceIdentityRegistry
    from healthcare_adapters import ingest_aria_fixture

    fixture = (
        {"fixture_label": "SYNTHETIC_TEST_FIXTURE", "event_type": "PATIENT", "external_patient_reference": "ARIA-PAT-500", "patient_type": "OUTPATIENT"},
        {"fixture_label": "SYNTHETIC_TEST_FIXTURE", "event_type": "PROCEDURE_ORDER", "external_patient_reference": "ARIA-PAT-500", "external_procedure_reference": "ARIA-ORD-500", "radionuclide": "F-18", "prescribed_activity_mbq": 200.0, "modality": "PET"},
        {"fixture_label": "SYNTHETIC_TEST_FIXTURE", "event_type": "APPOINTMENT", "external_patient_reference": "ARIA-PAT-500", "scheduled_date": date(2026, 10, 5), "appointment_mutability": "FIXED"},
    )
    registry = CrossSourceIdentityRegistry()
    result = ingest_aria_fixture(registry=registry, fixture=fixture)
    assert result.canonical_records[0].modality == "PET"


def test_27_missing_modality_is_not_guessed():
    from healthcare_integration import CrossSourceIdentityRegistry
    from healthcare_adapters import ingest_aria_fixture

    registry = CrossSourceIdentityRegistry()
    result = ingest_aria_fixture(registry=registry)  # default fixture never supplies modality
    assert all(r.modality is None for r in result.canonical_records)


def test_28_optional_clinical_priority_preserved():
    from healthcare_integration import CrossSourceIdentityRegistry
    from healthcare_adapters import ingest_aria_fixture

    fixture = (
        {"fixture_label": "SYNTHETIC_TEST_FIXTURE", "event_type": "PATIENT", "external_patient_reference": "ARIA-PAT-501", "patient_type": "OUTPATIENT"},
        {"fixture_label": "SYNTHETIC_TEST_FIXTURE", "event_type": "PROCEDURE_ORDER", "external_patient_reference": "ARIA-PAT-501", "external_procedure_reference": "ARIA-ORD-501", "radionuclide": "F-18", "prescribed_activity_mbq": 200.0, "clinical_priority": "URGENT"},
        {"fixture_label": "SYNTHETIC_TEST_FIXTURE", "event_type": "APPOINTMENT", "external_patient_reference": "ARIA-PAT-501", "scheduled_date": date(2026, 10, 5), "appointment_mutability": "FIXED"},
    )
    registry = CrossSourceIdentityRegistry()
    result = ingest_aria_fixture(registry=registry, fixture=fixture)
    assert result.canonical_records[0].clinical_priority == "URGENT"
    # missing case remains None/unresolved
    default_registry = CrossSourceIdentityRegistry()
    default_result = ingest_aria_fixture(registry=default_registry)
    assert all(r.clinical_priority is None for r in default_result.canonical_records)


def test_29_multiple_future_events_for_one_patient_remain_supported():
    from long_horizon_operational_planning import CanonicalOperationalPatientRecord

    events = [
        CanonicalOperationalPatientRecord(
            internal_model_patient_id="P-017", demand_status="COMMITTED", patient_type="OUTPATIENT", radionuclide="F-18",
            prescribed_activity_mbq=200.0, scheduled_date=date(2026, 9, 1), source_provenance="EHR", protocol_id="ORD-SEP",
        ),
        CanonicalOperationalPatientRecord(
            internal_model_patient_id="P-017", demand_status="COMMITTED", patient_type="OUTPATIENT", radionuclide="Tc-99m",
            prescribed_activity_mbq=740.0, scheduled_date=date(2026, 10, 1), source_provenance="EHR", protocol_id="ORD-OCT",
        ),
        CanonicalOperationalPatientRecord(
            internal_model_patient_id="P-017", demand_status="COMMITTED", patient_type="OUTPATIENT", radionuclide="F-18",
            prescribed_activity_mbq=200.0, scheduled_date=date(2026, 12, 1), source_provenance="EHR", protocol_id="ORD-DEC",
        ),
    ]
    from long_horizon_operational_planning import validate_no_duplicate_committed_scheduling
    findings = validate_no_duplicate_committed_scheduling(events)
    assert findings == []  # distinct protocol_id/date pairs for the SAME patient are legitimate, not a conservation violation
    assert len({e.internal_model_patient_id for e in events}) == 1
    assert len(events) == 3


def test_30_synthetic_and_external_demand_converge_on_same_downstream_engine():
    from datetime import date as _date
    from healthcare_integration import CrossSourceIdentityRegistry
    from healthcare_adapters import ingest_aria_fixture
    from long_horizon_operational_planning import (
        CanonicalOperationalPatientRecord, CyclotronCalendar, OperatingCalendar, run_long_horizon_operational_plan,
    )
    from models import PlannerAssumptions
    from multi_cyclotron_authority import build_controlled_dual_origin_geometry, build_multi_cyclotron_scenario
    from clinical_resource_identity import build_calendar_with_no_exceptions, build_deterministic_resource_inventory

    registry = CrossSourceIdentityRegistry()
    aria_result = ingest_aria_fixture(registry=registry)
    synthetic_record = CanonicalOperationalPatientRecord(
        internal_model_patient_id="P-SYNTH-30", demand_status="COMMITTED", patient_type="OUTPATIENT", radionuclide="F-18",
        prescribed_activity_mbq=200.0, scheduled_date=_date(2026, 10, 5), source_provenance="USER_ENTERED",
    )
    records = list(aria_result.canonical_records) + [synthetic_record]

    _, configured = build_multi_cyclotron_scenario(cy001_scenario_state="ON", cy002_scenario_state="ON")
    geometry = build_controlled_dual_origin_geometry()
    assumptions = PlannerAssumptions()
    calendar = OperatingCalendar(planning_start_date=_date(2026, 10, 5), planning_end_date=_date(2026, 10, 5))
    cyclotron_calendar = CyclotronCalendar(configured_cyclotrons=configured)
    inventory = build_deterministic_resource_inventory(injection_room_count=2, uptake_room_count=2, scanner_count=2, inbound_room_count=2)
    resource_calendar = build_calendar_with_no_exceptions(inventory)

    plan = run_long_horizon_operational_plan(
        operating_calendar=calendar, records=records, cyclotron_calendar=cyclotron_calendar, pathway="Conventional",
        geometry=geometry, assumptions=assumptions, resource_calendar=resource_calendar, distribution_concurrency=2,
    )
    assert plan.horizon_passed
    assert plan.committed_patient_count == 3  # 2 ARIA + 1 synthetic, same engine call


def test_31_patient_aware_production_remains_intact():
    from patient_radionuclide_demand import FacilityDayPatientDemand, PatientRadionuclideDemand, partition_facility_day_patient_demand

    demand = FacilityDayPatientDemand(patients=(
        PatientRadionuclideDemand(patient_id="P1", radionuclide="F-18", prescribed_activity_mbq=200.0),
        PatientRadionuclideDemand(patient_id="P2", radionuclide="F-18", prescribed_activity_mbq=200.0),
    ))
    batches = partition_facility_day_patient_demand(demand, requested_batch_count_by_radionuclide={"F-18": 1})
    assert len(batches) == 1
    assert set(batches[0].patient_ids) == {"P1", "P2"}


def test_32_no_vendor_specific_downstream_branches_introduced():
    import inspect
    import production_clinical_schedule
    import patient_radionuclide_demand
    import decision_pipeline

    vendor_terms = ("VARIAN_ARIA", "GE_DOSEWATCH", "SIEMENS_HEALTHINEERS")
    for module in (production_clinical_schedule, patient_radionuclide_demand, decision_pipeline):
        source = inspect.getsource(module)
        for term in vendor_terms:
            assert term not in source, f"{module.__name__} contains vendor-specific term {term}"


# ---------------------------------------------------------------------------
# 33: Lockdown immutability preserved (reconfirmed, not re-implemented)
# ---------------------------------------------------------------------------


def test_33_lockdown_immutability_preserved():
    import lockdown_what_if_lineage_authority as lla
    import canonical_spatial_authority as csa

    registry = lla.LockdownLineageRegistry()
    spatial_locked = csa.LockedSpatialState(registry=csa.build_facility_hierarchy(facility_id="FAC-PHASE31"))
    l0 = lla.create_first_lockdown(registry, locked=spatial_locked, economic_result={"capex": 1.0})
    w1 = lla.branch_what_if(registry, parent_lockdown_id=l0.lockdown_id)
    lla.update_what_if_results(registry, w1.what_if_id, economic_result={"capex": 2.0})
    assert registry.lockdown(l0.lockdown_id).economic_result == {"capex": 1.0}
