"""Focused tests for the Equipment OPEX Authority (Sections 43-44).

Protects the 34 invariants of Section 43 and provides the six explicit control
proofs of Section 44. These tests are behavioral: they assert the AUTHORITY's
honesty doctrine (no zero-fill, separate physical/monetary evidence, known
subtotal vs total, calendar-duty consumption, patient-identity boundary,
CYPRIS-not-GE preservation) — not incidental numeric constants.
"""

from __future__ import annotations

import dataclasses
import inspect
from datetime import date, timedelta

import pytest

import equipment_opex_authority as A
from equipment_energy_opex import EquipmentDailyEnergyResult
from cyclotron_catalog import load_cyclotron_catalog
from generator_catalog import load_generator_catalog, create_facility_generator_instance
from scanner_catalog import load_scanner_catalog


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

TARIFF = 0.15  # CONTROLLED_ASSUMPTION tariff (existing repo concept)


def _uncalibrated_scanner_daily(scanner_id: str = "SCN-001", n_days: int = 5) -> list[EquipmentDailyEnergyResult]:
    """Scanner duty exists but catalog power is NOT_CALIBRATED -> the energy
    authority yields calc_kwh=0.0 with a non-CALIBRATED status and preserved
    uncalibrated state-minutes (mirrors real catalog: active_power_kw=None)."""
    d0 = date(2026, 1, 1)
    return [
        EquipmentDailyEnergyResult(
            day=d0 + timedelta(days=i), equipment_id=scanner_id, equipment_class="SCANNER",
            manufacturer="Siemens Healthineers", model="Biograph Vision",
            state_durations_minutes={"SCANNING": 300.0, "STANDBY": 1140.0}, state_power_kw_used={},
            calculated_energy_kwh=0.0, uncalibrated_state_minutes=1440.0, calibration_status="NOT_CALIBRATED",
            electricity_opex=0.0, provenance="catalog active_power_kw NOT_CALIBRATED",
        )
        for i in range(n_days)
    ]


def _calibrated_scanner_daily(scanner_id: str = "SCN-CAL", n_days: int = 365, active_min: float = 300.0) -> list[EquipmentDailyEnergyResult]:
    d0 = date(2026, 1, 1)
    return [
        EquipmentDailyEnergyResult(
            day=d0 + timedelta(days=i), equipment_id=scanner_id, equipment_class="SCANNER",
            manufacturer="X", model="Y", state_durations_minutes={"SCANNING": active_min},
            state_power_kw_used={"SCANNING": 10.0}, calculated_energy_kwh=10.0 * (active_min / 60.0),
            uncalibrated_state_minutes=0.0, calibration_status="CALIBRATED_FOR_ENERGY",
            electricity_opex=10.0 * (active_min / 60.0) * TARIFF, provenance="calibrated",
        )
        for i in range(n_days)
    ]


# ---------------------------------------------------------------------------
# Section 43 invariants
# ---------------------------------------------------------------------------


def test_01_authority_imports_cleanly():
    assert hasattr(A, "compute_scanner_opex")
    assert hasattr(A, "compute_cyclotron_opex")
    assert hasattr(A, "compute_generator_opex")


def test_02_result_types_are_immutable():
    assert dataclasses.is_dataclass(A.EquipmentOpexComponent)
    assert dataclasses.is_dataclass(A.EquipmentOpexResult)
    comp = A.build_opex_component(
        component_type="X", physical_quantity=1.0, physical_unit="u", physical_evidence_status="SITE_CALIBRATED",
        unit_cost_usd=1.0, unit_cost_basis="SITE_CALIBRATED", provenance="p",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        comp.annual_cost_usd = 999.0  # type: ignore[misc]


def test_03_scanners_supported():
    res = A.compute_scanner_opex(
        scanner_id="SCN-001", catalog_model_id="SIEMENS_BIOGRAPH_VISION",
        daily_energy_results=_uncalibrated_scanner_daily(), horizon_days=5, electricity_tariff_usd_per_kwh=TARIFF,
    )
    assert res.equipment_type == "SCANNER"


def test_04_cyclotrons_supported():
    util = A.derive_cyclotron_utilization_from_cycles(
        cyclotron_id="CY-001", cycle_intervals_minutes=[(60.0, 150.0)], scheduled_production_days=1,
    )
    res = A.compute_cyclotron_opex(utilization=util, catalog_model=None, horizon_days=1, electricity_tariff_usd_per_kwh=TARIFF)
    assert res.equipment_type == "CYCLOTRON"


def test_05_generators_supported():
    gcat = load_generator_catalog()
    model = gcat.by_id("CURIUM_TECHNELITE")
    inst = create_facility_generator_instance(instance_id="GEN-001", catalog_model_id="CURIUM_TECHNELITE")
    res, _sched = A.compute_generator_opex(instance=inst, model=model, horizon_days=365)
    assert res.equipment_type == "GENERATOR"


def test_06_existing_energy_authority_reused_not_duplicated():
    # The OPEX authority imports the energy authority's result type rather than
    # redefining a competing one, and defines no rival duty-cycle deriver.
    src = inspect.getsource(A)
    assert "from equipment_energy_opex import" in src
    assert "EquipmentDailyEnergyResult" in src


def test_07_no_duplicate_duty_cycle_engine():
    # No re-derivation of scanner/cyclotron state-minutes here; those live in
    # equipment_energy_opex. This module only CONSUMES their results.
    src = inspect.getsource(A)
    assert "derive_scanner_state_minutes" not in src
    assert "derive_cyclotron_state_minutes" not in src


def test_08_no_nameplate_times_8760_fallback():
    src = inspect.getsource(A)
    assert "8760" not in src


def test_09_unknown_power_not_zero_kwh():
    res = A.compute_scanner_opex(
        scanner_id="SCN-001", catalog_model_id="SIEMENS_BIOGRAPH_VISION",
        daily_energy_results=_uncalibrated_scanner_daily(), horizon_days=5, electricity_tariff_usd_per_kwh=TARIFF,
    )
    energy = next(c for c in res.components if c.component_type == "ELECTRICITY")
    assert energy.physical_quantity is None  # never a fabricated 0 kWh
    assert energy.annual_cost_usd is None    # never $0
    assert energy.calculation_status == "PHYSICAL_QUANTITY_NOT_CALIBRATED"


def test_10_unknown_unit_price_not_zero_dollars():
    gcat = load_generator_catalog()
    model = gcat.by_id("CURIUM_TECHNELITE")
    inst = create_facility_generator_instance(instance_id="GEN-001", catalog_model_id="CURIUM_TECHNELITE")
    res, _ = A.compute_generator_opex(instance=inst, model=model, horizon_days=365)
    proc = next(c for c in res.components if c.component_type == "GENERATOR_PROCUREMENT")
    assert proc.unit_cost_usd is None
    assert proc.annual_cost_usd is None  # not $0


def test_11_scanner_calendar_duty_consumed():
    # More scan-active minutes (calibrated) -> more derived energy quantity.
    low = A.build_scanner_energy_component(
        daily_energy_results=_calibrated_scanner_daily(active_min=120.0), horizon_days=365,
        electricity_tariff_usd_per_kwh=TARIFF, representative_horizon=True,
    )
    high = A.build_scanner_energy_component(
        daily_energy_results=_calibrated_scanner_daily(active_min=300.0), horizon_days=365,
        electricity_tariff_usd_per_kwh=TARIFF, representative_horizon=True,
    )
    assert high.physical_quantity > low.physical_quantity


def test_12_cyclotron_production_beam_duty_consumed():
    util = A.derive_cyclotron_utilization_from_cycles(
        cyclotron_id="CY-001", cycle_intervals_minutes=[(60.0, 150.0), (200.0, 290.0)], scheduled_production_days=1,
    )
    assert util.production_cycles == 2
    assert util.beam_on_minutes == pytest.approx(180.0)
    assert util.beam_on_hours == pytest.approx(3.0)


def test_13_generator_useful_life_consumed():
    gcat = load_generator_catalog()
    model = gcat.by_id("CURIUM_TECHNELITE")
    sched = A.derive_generator_replacement_schedule(model=model, horizon_days=365)
    assert sched.useful_life_days == 14.0
    assert sched.schedule_status == "CALCULABLE"


def test_14_generator_replacement_count_derivable():
    gcat = load_generator_catalog()
    model = gcat.by_id("CURIUM_TECHNELITE")
    sched = A.derive_generator_replacement_schedule(model=model, horizon_days=365)
    assert sched.generators_required is not None and sched.generators_required > 0


def test_15_generator_purchase_dollars_not_calibrated_when_price_absent():
    gcat = load_generator_catalog()
    model = gcat.by_id("CURIUM_TECHNELITE")
    inst = create_facility_generator_instance(instance_id="GEN-001", catalog_model_id="CURIUM_TECHNELITE")
    res, sched = A.compute_generator_opex(instance=inst, model=model, horizon_days=365)
    proc = next(c for c in res.components if c.component_type == "GENERATOR_PROCUREMENT")
    assert sched.schedule_status == "CALCULABLE"        # schedule in units
    assert proc.calculation_status == "UNIT_COST_NOT_CALIBRATED"  # dollars absent


def test_16_ge_pettrace_890_production_calibration_preserved():
    cat = load_cyclotron_catalog()
    ge = cat.by_id("GE_PETTRACE_890")
    assert ge.production_calibration_status == "manufacturer_calibrated"
    assert "F-18" in ge.schedulable_radionuclides


def test_17_cypris_mp30_production_remains_not_calibrated():
    cat = load_cyclotron_catalog()
    cypris = cat.by_id("SUMITOMO_CYPRIS_MP_30")
    assert cypris.production_calibration_status == "not_calibrated"
    assert cypris.schedulable_radionuclides == ()  # supported but no schedulable production data


def test_18_no_ge_capacity_borrowed_by_cypris():
    cat = load_cyclotron_catalog()
    cypris = cat.by_id("SUMITOMO_CYPRIS_MP_30")
    util = A.derive_cyclotron_utilization_from_cycles(
        cyclotron_id="CY-CYPRIS", cycle_intervals_minutes=[], scheduled_production_days=0,
    )
    res = A.compute_cyclotron_opex(utilization=util, catalog_model=cypris, horizon_days=1, electricity_tariff_usd_per_kwh=TARIFF)
    # The OPEX authority carries CYPRIS's own model identity and NOT_CALIBRATED
    # production status verbatim; it never substitutes GE's calibrated status.
    assert res.catalog_model_id == "SUMITOMO_CYPRIS_MP_30"
    assert any("not_calibrated" in lim for lim in res.limitations)
    energy = next(c for c in res.components if c.component_type == "ELECTRICITY")
    assert energy.annual_cost_usd is None


def test_19_scanner_opex_requires_no_patient_id():
    sig = inspect.signature(A.compute_scanner_opex)
    assert not any("patient" in p.lower() for p in sig.parameters)


def test_20_cyclotron_opex_requires_no_patient_id():
    sig = inspect.signature(A.compute_cyclotron_opex)
    assert not any("patient" in p.lower() for p in sig.parameters)
    sig2 = inspect.signature(A.derive_cyclotron_utilization_from_cycles)
    assert not any("patient" in p.lower() for p in sig2.parameters)


def test_21_generator_opex_requires_no_patient_id():
    sig = inspect.signature(A.compute_generator_opex)
    assert not any("patient" in p.lower() for p in sig.parameters)


def test_22_patient_aware_batch_boundary_preserved():
    # Utilization is derived from already-scheduled cycle intervals, not from
    # patient identities; the authority never accepts patient IDs.
    for field in dataclasses.fields(A.CyclotronUtilization):
        assert "patient" not in field.name.lower()


def test_23_electricity_tariff_evidence_class_preserved():
    # The tariff enters as a CONTROLLED_ASSUMPTION unit-cost basis and is never
    # promoted to MANUFACTURER_SPECIFIED.
    comp = A.build_scanner_energy_component(
        daily_energy_results=_calibrated_scanner_daily(), horizon_days=365,
        electricity_tariff_usd_per_kwh=TARIFF, tariff_basis="CONTROLLED_ASSUMPTION", representative_horizon=True,
    )
    assert comp.unit_cost_basis == "CONTROLLED_ASSUMPTION"


def test_24_scanner_power_not_calibrated_preserved():
    cat = load_scanner_catalog()
    for mid in ("SIEMENS_BIOGRAPH_VISION", "GE_DISCOVERY_MI", "PHILIPS_BRIGHTVIEW_XCT"):
        model = cat.by_id(mid)
        assert model.power_specification_status == "NOT_CALIBRATED"
        assert model.active_power_kw is None


def test_25_scanner_energy_dollars_not_calibrated_when_power_absent():
    res = A.compute_scanner_opex(
        scanner_id="SCN-001", catalog_model_id="SIEMENS_BIOGRAPH_VISION",
        daily_energy_results=_uncalibrated_scanner_daily(), horizon_days=5, electricity_tariff_usd_per_kwh=TARIFF,
    )
    energy = next(c for c in res.components if c.component_type == "ELECTRICITY")
    assert energy.annual_cost_usd is None


def test_26_known_subtotal_can_exist_while_total_not_calibrated():
    known = A.build_opex_component(
        component_type="GENERATOR_PROCUREMENT", physical_quantity=10.0, physical_unit="gen/yr",
        physical_evidence_status="LITERATURE_DERIVED", unit_cost_usd=5000.0, unit_cost_basis="CONTROLLED_ASSUMPTION",
        provenance="known",
    )
    unknown = A.build_opex_component(
        component_type="SERVICE_CONTRACT", physical_quantity=1.0, physical_unit="yr",
        physical_evidence_status="MODELED_ESTIMATE", unit_cost_usd=None, unit_cost_basis="NOT_CALIBRATED",
        provenance="unknown",
    )
    res = A._assemble_result(
        equipment_type="GENERATOR", equipment_id="GEN-X", catalog_model_id="M",
        planning_horizon_days=365, components=[known, unknown],
    )
    assert res.known_annual_opex_subtotal_usd == 50000.0
    assert res.total_annual_opex_usd is None
    assert res.total_annual_opex_status == "NOT_CALIBRATED"


def test_27_missing_service_cost_preserved_as_unknown():
    svc = A.build_scanner_service_component()
    assert svc.unit_cost_usd is None
    assert svc.calculation_status in ("UNIT_COST_NOT_CALIBRATED", "NOT_CALIBRATED")


def test_28_staffing_not_double_counted():
    # No component type refers to staffing/FTE/labor; staffing is owned by the
    # labor authority (Section 22).
    util = A.derive_cyclotron_utilization_from_cycles(
        cyclotron_id="CY-001", cycle_intervals_minutes=[(60.0, 150.0)], scheduled_production_days=1,
    )
    res = A.compute_cyclotron_opex(utilization=util, catalog_model=None, horizon_days=1, electricity_tariff_usd_per_kwh=TARIFF)
    for c in res.components:
        assert "STAFF" not in c.component_type.upper()
        assert "FTE" not in c.component_type.upper()
        assert "LABOR" not in c.component_type.upper()


def test_29_no_build_does_not_mean_zero_opex():
    # A NO-BUILD / retained-existing scanner whose power is uncalibrated still
    # yields NOT_CALIBRATED energy, never a $0 total that would imply zero OPEX.
    res = A.compute_scanner_opex(
        scanner_id="SCN-LEGACY", catalog_model_id="PHILIPS_BRIGHTVIEW_XCT",
        daily_energy_results=_uncalibrated_scanner_daily("SCN-LEGACY"), horizon_days=5, electricity_tariff_usd_per_kwh=TARIFF,
    )
    assert res.total_annual_opex_usd is None
    assert res.total_annual_opex_status == "NOT_CALIBRATED"


def test_30_existing_legacy_scanner_identity_preserved():
    cat = load_scanner_catalog()
    legacy = cat.by_id("PHILIPS_BRIGHTVIEW_XCT")
    assert legacy.commercial_status == "LEGACY_INSTALLED_BASE"
    assert legacy.new_purchase_candidate is False
    # The OPEX authority preserves the catalog_model_id it is given verbatim.
    res = A.compute_scanner_opex(
        scanner_id="SCN-LEGACY", catalog_model_id="PHILIPS_BRIGHTVIEW_XCT",
        daily_energy_results=_uncalibrated_scanner_daily("SCN-LEGACY"), horizon_days=5, electricity_tariff_usd_per_kwh=TARIFF,
    )
    assert res.catalog_model_id == "PHILIPS_BRIGHTVIEW_XCT"


def test_31_annualization_does_not_blindly_scale_unrepresentative_horizon():
    val, status = A.annualize_horizon_quantity(observed_quantity=100.0, horizon_days=3, representative=False)
    assert val is None
    assert "REPRESENTATIVE" in status  # HORIZON_NOT_REPRESENTATIVE_...


def test_32_comparability_status_exposes_incomplete_evidence():
    res = A.compute_scanner_opex(
        scanner_id="SCN-001", catalog_model_id="SIEMENS_BIOGRAPH_VISION",
        daily_energy_results=_uncalibrated_scanner_daily(), horizon_days=5, electricity_tariff_usd_per_kwh=TARIFF,
    )
    assert res.comparability_status in ("PARTIALLY_CALIBRATED", "NOT_COMPARABLE_DUE_TO_UNCALIBRATED_ENERGY")


def test_33_part3e_interface_no_patient_demand_mutation():
    # The Part 3E-facing result carries no method/field that mutates demand; it
    # is a frozen read-model of known/unknown OPEX.
    res = A.compute_scanner_opex(
        scanner_id="SCN-001", catalog_model_id="SIEMENS_BIOGRAPH_VISION",
        daily_energy_results=_uncalibrated_scanner_daily(), horizon_days=5, electricity_tariff_usd_per_kwh=TARIFF,
    )
    field_names = {f.name for f in dataclasses.fields(res)}
    assert "known_annual_opex_subtotal_usd" in field_names
    assert "total_annual_opex_status" in field_names
    assert "comparability_status" in field_names
    assert not any("demand" in n.lower() for n in field_names)


def test_34_part3e_phase1_possible_with_qualified_economics():
    # A result with a known subtotal but NOT_CALIBRATED total is still a usable
    # Part 3E Phase 1 read-model (qualified economics), not a hard failure.
    res = A.compute_scanner_opex(
        scanner_id="SCN-001", catalog_model_id="GE_DISCOVERY_MI",
        daily_energy_results=_uncalibrated_scanner_daily(), horizon_days=5, electricity_tariff_usd_per_kwh=TARIFF,
    )
    assert isinstance(res.known_annual_opex_subtotal_usd, float)
    assert res.total_annual_opex_status == "NOT_CALIBRATED"
    # applicable components are still enumerable for ranking-with-limitations
    assert res.applicable_component_count >= 1


# ---------------------------------------------------------------------------
# Section 44 — required control proofs
# ---------------------------------------------------------------------------


def test_proof_a_scanner_unknown_power():
    res = A.compute_scanner_opex(
        scanner_id="SCN-001", catalog_model_id="SIEMENS_BIOGRAPH_VISION",
        daily_energy_results=_uncalibrated_scanner_daily(), horizon_days=5, electricity_tariff_usd_per_kwh=TARIFF,
    )
    energy = next(c for c in res.components if c.component_type == "ELECTRICITY")
    # duty exists (uncalibrated minutes preserved in limitations), power NOT_CALIBRATED, $ not fabricated
    assert energy.physical_evidence_status == "NOT_CALIBRATED"
    assert energy.annual_cost_usd is None
    assert any("uncalibrated_state_minutes" in lim for lim in energy.limitations)


def test_proof_b_cyclotron_utilization_without_kw_from_beam_current():
    cat = load_cyclotron_catalog()
    ge = cat.by_id("GE_PETTRACE_890")
    util = A.derive_cyclotron_utilization_from_cycles(
        cyclotron_id="CY-001", cycle_intervals_minutes=[(60.0, 150.0), (200.0, 290.0)], scheduled_production_days=1,
    )
    res = A.compute_cyclotron_opex(utilization=util, catalog_model=ge, horizon_days=1, electricity_tariff_usd_per_kwh=TARIFF)
    energy = next(c for c in res.components if c.component_type == "ELECTRICITY")
    assert util.beam_on_hours == pytest.approx(3.0)      # utilization derived
    assert energy.annual_cost_usd is None                # no kW from beam current
    assert any("beam current is NOT facility electrical load" in lim for lim in energy.limitations)


def test_proof_c_cypris_preservation():
    cat = load_cyclotron_catalog()
    cypris = cat.by_id("SUMITOMO_CYPRIS_MP_30")
    assert cypris.production_calibration_status == "not_calibrated"
    assert cypris.schedulable_radionuclides == ()
    util = A.derive_cyclotron_utilization_from_cycles(
        cyclotron_id="CY-CYPRIS", cycle_intervals_minutes=[], scheduled_production_days=0,
    )
    res = A.compute_cyclotron_opex(utilization=util, catalog_model=cypris, horizon_days=1, electricity_tariff_usd_per_kwh=TARIFF)
    assert res.catalog_model_id == "SUMITOMO_CYPRIS_MP_30"  # real identity, no GE substitute
    energy = next(c for c in res.components if c.component_type == "ELECTRICITY")
    assert energy.annual_cost_usd is None


def test_proof_d_generator_replacement_dollars_withheld():
    gcat = load_generator_catalog()
    model = gcat.by_id("CURIUM_TECHNELITE")
    inst = create_facility_generator_instance(instance_id="GEN-001", catalog_model_id="CURIUM_TECHNELITE")
    res, sched = A.compute_generator_opex(instance=inst, model=model, horizon_days=365)
    assert sched.schedule_status == "CALCULABLE"
    assert sched.generators_required is not None and sched.generators_required > 0
    proc = next(c for c in res.components if c.component_type == "GENERATOR_PROCUREMENT")
    assert proc.annual_cost_usd is None  # procurement dollars NOT_CALIBRATED


def test_proof_e_known_subtotal_with_unknown_total():
    known = A.build_opex_component(
        component_type="GENERATOR_PROCUREMENT", physical_quantity=10.0, physical_unit="gen/yr",
        physical_evidence_status="LITERATURE_DERIVED", unit_cost_usd=5000.0, unit_cost_basis="CONTROLLED_ASSUMPTION",
        provenance="known",
    )
    unknown = A.build_opex_component(
        component_type="ELECTRICITY", physical_quantity=None, physical_unit="kWh/yr",
        physical_evidence_status="NOT_CALIBRATED", unit_cost_usd=TARIFF, unit_cost_basis="CONTROLLED_ASSUMPTION",
        provenance="unknown power",
    )
    res = A._assemble_result(
        equipment_type="GENERATOR", equipment_id="GEN-X", catalog_model_id="M",
        planning_horizon_days=365, components=[known, unknown],
    )
    assert res.known_annual_opex_subtotal_usd == 50000.0
    assert res.total_annual_opex_status == "NOT_CALIBRATED"


def test_proof_f_no_zero_fill():
    # A known-unknown scanner: service price and energy power both unknown ->
    # both remain unknown (None), never $0.
    res = A.compute_scanner_opex(
        scanner_id="SCN-001", catalog_model_id="SIEMENS_BIOGRAPH_VISION",
        daily_energy_results=_uncalibrated_scanner_daily(), horizon_days=5, electricity_tariff_usd_per_kwh=TARIFF,
    )
    service = next(c for c in res.components if c.component_type == "SERVICE_CONTRACT")
    energy = next(c for c in res.components if c.component_type == "ELECTRICITY")
    assert service.annual_cost_usd is None
    assert energy.annual_cost_usd is None
    assert service.unit_cost_usd is None
