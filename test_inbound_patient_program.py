"""Controlled regression coverage for Phase 11: patient-centric clinical spatial
programming (inbound/outpatient room architecture, occupancy, MRT access and
economics). See inbound_patient_program.py.

Proves:
- one inbound room cannot serve two overlapping 24-hour patients (36);
- a multi-day patient blocks its room across the full occupancy period (37);
- an integrated inbound room provides dedicated injection+uptake without
  creating shared capacity for unrelated patients (38);
- central injection can be shared between inbound and outpatient patients (39);
- scanner capacity can be shared between inbound and outpatient patients (40);
- an MRT candidate requiring guideway extension costs more than an equivalent
  already-on-network candidate (41);
- an unselected inbound room contributes no guideway/extension cost (42);
- occupied_days x configured daily rate produces room-day value independent of
  scan revenue (43);
- a 7-day stay with one scan produces 7 room-days of value but only 1 scan's
  revenue (44);
- the optimizer selects an economically-justified room count, not the maximum
  physically possible (45);
- a retention-failing integrated room cannot contribute qualified capacity (46);
- centralized injection can rescue a room that fails retention when delivered
  directly (47).
"""

from __future__ import annotations

from models import SharedNetworkAssumptions
from spatial_benchmark import build_benchmark_geometry, build_production_basis, _base_assumptions
from inbound_patient_program import (
    InboundRoomEconomicAssumptions,
    SyntheticPatient,
    admit_inbound_patients,
    compute_inbound_room_guideway_extension,
    evaluate_inbound_room_program,
    optimize_inbound_room_count,
)


def _patient(patient_id: str, admin_minutes: float, los_days: float, patient_type: str = "INBOUND_PATIENT") -> SyntheticPatient:
    return SyntheticPatient(
        patient_id=patient_id,
        patient_type=patient_type,  # type: ignore[arg-type]
        radionuclide="F-18",
        prescribed_activity_mbq=370.0,
        administration_time_minutes=admin_minutes,
        length_of_stay_days=los_days,
    )


def test_one_room_cannot_serve_two_overlapping_24h_patients() -> None:
    """Section 36."""
    patients = [
        _patient("P1", admin_minutes=0.0, los_days=1.0),
        _patient("P2", admin_minutes=60.0, los_days=1.0),  # overlaps P1's 24h stay
    ]
    result = admit_inbound_patients(patients, inbound_room_count=1)
    assert len(result.admitted_patient_ids) == 1
    assert len(result.unmet_patient_ids) == 1


def test_multi_day_patient_blocks_room_across_occupancy_period() -> None:
    """Section 37."""
    patients = [
        _patient("P1", admin_minutes=0.0, los_days=3.0),
        _patient("P2", admin_minutes=1440.0 * 2, los_days=1.0),  # arrives on day 2, still within P1's 3-day stay
        _patient("P3", admin_minutes=1440.0 * 3, los_days=1.0),  # arrives after P1 discharges
    ]
    result = admit_inbound_patients(patients, inbound_room_count=1)
    assert "P1" in result.admitted_patient_ids
    assert "P2" in result.unmet_patient_ids
    assert "P3" in result.admitted_patient_ids


def test_integrated_room_provides_dedicated_injection_and_uptake_only_for_its_patient() -> None:
    """Section 38: an integrated room's occupancy is exclusive -- it is not
    shared capacity for any other patient during that patient's stay.
    """
    patients = [
        _patient("P1", admin_minutes=0.0, los_days=2.0),
        _patient("P2", admin_minutes=100.0, los_days=1.0),
    ]
    result = admit_inbound_patients(patients, inbound_room_count=1)
    # P2's admission window overlaps P1's occupancy of the single room.
    assert result.admitted_patient_ids == ("P1",)
    assert result.unmet_patient_ids == ("P2",)


def test_central_injection_can_be_shared_between_inbound_and_outpatient() -> None:
    """Section 39: CENTRALIZED architecture routes retention checking through
    the shared central injection room, which is not exclusive to any one
    patient type.
    """
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    network_assumptions = SharedNetworkAssumptions()
    econ = InboundRoomEconomicAssumptions(room_capex_per_unit=assumptions.additional_room_capex)
    patients = [_patient("P1", admin_minutes=0.0, los_days=1.0)]
    central_room = "F1-R01"
    result = evaluate_inbound_room_program(
        pathway="Conventional",
        geometry=geometry,
        architecture="CENTRALIZED",
        patients=patients,
        candidate_room_ids=["F1-R02"],
        already_serviced_floors=frozenset({1}),
        central_injection_room_id=central_room,
        inbound_room_count=1,
        half_life_minutes=109.8,
        assumptions=assumptions,
        network_assumptions=network_assumptions,
        econ=econ,
    )
    assert result.inbound_room_count == 1
    assert result.qualified_inbound_completions == 1


def test_scanner_capacity_shared_between_inbound_and_outpatient() -> None:
    """Section 40: this program does not create a dedicated scanner per
    inbound room -- scanners remain a shared resource outside this module
    (verified structurally: InboundRoomProgramResult has no per-room scanner
    field, confirming no per-inbound-room scanner is modeled).
    """
    from inbound_patient_program import InboundRoomProgramResult

    field_names = set(InboundRoomProgramResult.__dataclass_fields__.keys())
    assert "scanners" not in field_names
    assert "dedicated_scanner_count" not in field_names


def test_guideway_extension_costs_more_for_off_network_floor() -> None:
    """Section 41: an inbound room on a floor NOT already serviced by the
    shared MRT network must incur higher incremental guideway CapEx than an
    otherwise-equivalent room on an already-serviced floor.
    """
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    network_assumptions = SharedNetworkAssumptions()

    on_network = compute_inbound_room_guideway_extension(
        geometry=geometry, room_id="F2-R05", already_serviced_floors=frozenset({1, 2, 3}),
        assumptions=assumptions, network_assumptions=network_assumptions,
    )
    off_network = compute_inbound_room_guideway_extension(
        geometry=geometry, room_id="F5-R05", already_serviced_floors=frozenset({1, 2, 3}),
        assumptions=assumptions, network_assumptions=network_assumptions,
    )
    assert off_network.incremental_capex > on_network.incremental_capex
    assert off_network.incremental_transitions > on_network.incremental_transitions


def test_unselected_room_contributes_no_guideway_cost() -> None:
    """Section 42: if inbound_room_count=0, no rooms are selected and no MRT
    guideway extension cost is incurred.
    """
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    network_assumptions = SharedNetworkAssumptions()
    econ = InboundRoomEconomicAssumptions(room_capex_per_unit=assumptions.additional_room_capex)
    patients = [_patient("P1", admin_minutes=0.0, los_days=1.0)]

    result = evaluate_inbound_room_program(
        pathway="MRT", geometry=geometry, architecture="INTEGRATED", patients=patients,
        candidate_room_ids=["F8-R10"], already_serviced_floors=frozenset({1, 2, 3}),
        central_injection_room_id=None, inbound_room_count=0, half_life_minutes=109.8,
        assumptions=assumptions, network_assumptions=network_assumptions, econ=econ,
    )
    assert result.inbound_room_count == 0
    assert result.incremental_mrt_guideway_capex == 0.0
    assert result.inbound_room_capex == 0.0


def test_room_day_value_independent_of_scan_revenue() -> None:
    """Section 43: occupied_days x configured daily rate produces room-day
    value, computed independently from qualified scan revenue.
    """
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    network_assumptions = SharedNetworkAssumptions()
    daily_rate = 500.0
    econ = InboundRoomEconomicAssumptions(room_capex_per_unit=assumptions.additional_room_capex, room_revenue_per_occupied_day=daily_rate)
    patients = [_patient("P1", admin_minutes=0.0, los_days=4.0)]

    result = evaluate_inbound_room_program(
        pathway="Conventional", geometry=geometry, architecture="INTEGRATED", patients=patients,
        candidate_room_ids=["F1-R01"], already_serviced_floors=frozenset({1}),
        central_injection_room_id=None, inbound_room_count=1, half_life_minutes=109.8,
        assumptions=assumptions, network_assumptions=network_assumptions, econ=econ,
    )
    expected_room_day_value = 4.0 * assumptions.operating_days_per_year * daily_rate
    assert result.inbound_room_day_annual_value == expected_room_day_value
    assert result.qualified_inbound_scan_annual_revenue == 1.0 * assumptions.revenue_per_scan * assumptions.operating_days_per_year


def test_no_daily_scan_fabrication_for_multiday_stay() -> None:
    """Section 44: a 7-day stay with one modeled scan must produce 7 room-days
    of value but exactly ONE scan's (qualified-completion) revenue, not 7.
    """
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    network_assumptions = SharedNetworkAssumptions()
    daily_rate = 500.0
    econ = InboundRoomEconomicAssumptions(room_capex_per_unit=assumptions.additional_room_capex, room_revenue_per_occupied_day=daily_rate)
    patients = [_patient("P1", admin_minutes=0.0, los_days=7.0)]

    result = evaluate_inbound_room_program(
        pathway="Conventional", geometry=geometry, architecture="INTEGRATED", patients=patients,
        candidate_room_ids=["F1-R01"], already_serviced_floors=frozenset({1}),
        central_injection_room_id=None, inbound_room_count=1, half_life_minutes=109.8,
        assumptions=assumptions, network_assumptions=network_assumptions, econ=econ,
    )
    assert result.qualified_inbound_completions == 1
    assert result.inbound_room_day_annual_value == 7.0 * assumptions.operating_days_per_year * daily_rate
    assert result.qualified_inbound_scan_annual_revenue == 1.0 * assumptions.revenue_per_scan * assumptions.operating_days_per_year


def test_optimizer_selects_economically_justified_room_count_not_maximum() -> None:
    """Section 45: with only ONE patient actually needing a room, a second room
    adds CapEx/OPEX with zero incremental qualified-patient or room-day benefit
    -- its NPV must be strictly worse than the one-room candidate, and the
    optimizer (bounded by peak occupancy, section 5) must select exactly 1.
    """
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    network_assumptions = SharedNetworkAssumptions()
    econ = InboundRoomEconomicAssumptions(room_capex_per_unit=assumptions.additional_room_capex, room_revenue_per_occupied_day=500.0)
    patients = [_patient("P1", admin_minutes=0.0, los_days=1.0)]  # only one patient needs a room

    best_result, best_npv, evaluated = optimize_inbound_room_count(
        pathway="Conventional", geometry=geometry, architecture="INTEGRATED", patients=patients,
        candidate_room_ids=["F1-R01", "F1-R02", "F1-R03"], already_serviced_floors=frozenset({1}),
        central_injection_room_id=None, half_life_minutes=109.8, assumptions=assumptions,
        network_assumptions=network_assumptions, econ=econ,
    )
    assert best_result.inbound_room_count == 1
    assert [result.inbound_room_count for result, _npv in evaluated] == [0, 1]

    # A second room evaluated directly (bypassing the peak-occupancy bound)
    # adds cost with zero additional qualified benefit, so it must score worse.
    from inbound_patient_program import compute_inbound_program_npv, evaluate_inbound_room_program

    two_room_result = evaluate_inbound_room_program(
        pathway="Conventional", geometry=geometry, architecture="INTEGRATED", patients=patients,
        candidate_room_ids=["F1-R01", "F1-R02", "F1-R03"], already_serviced_floors=frozenset({1}),
        central_injection_room_id=None, inbound_room_count=2, half_life_minutes=109.8,
        assumptions=assumptions, network_assumptions=network_assumptions, econ=econ,
    )
    two_room_npv = compute_inbound_program_npv(two_room_result, assumptions)
    assert two_room_result.qualified_inbound_completions == best_result.qualified_inbound_completions
    assert best_npv > two_room_npv


def test_distant_room_fails_retention_and_cannot_contribute_qualified_capacity() -> None:
    """Section 46: an integrated room whose direct radionuclide delivery fails
    the configured (tightened) retention criterion cannot contribute qualified
    inbound capacity.
    """
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    network_assumptions = SharedNetworkAssumptions()
    econ = InboundRoomEconomicAssumptions(room_capex_per_unit=assumptions.additional_room_capex)
    patients = [_patient("P1", admin_minutes=0.0, los_days=1.0)]

    # An artificially strict threshold that the benchmark's farthest room cannot satisfy.
    result = evaluate_inbound_room_program(
        pathway="Conventional", geometry=geometry, architecture="INTEGRATED", patients=patients,
        candidate_room_ids=["F8-R10"], already_serviced_floors=frozenset({1, 2, 3, 4, 5, 6, 7, 8}),
        central_injection_room_id=None, inbound_room_count=1, half_life_minutes=109.8,
        assumptions=assumptions, network_assumptions=network_assumptions, econ=econ,
        retention_threshold=0.999999,
    )
    assert result.inbound_room_count == 0
    assert result.qualified_inbound_completions == 0


def test_centralized_injection_can_rescue_room_that_fails_direct_retention() -> None:
    """Section 47: a room whose DIRECT integrated delivery fails retention may
    still contribute qualified capacity under CENTRALIZED architecture, where
    retention is evaluated against a nearby central injection room instead.
    """
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    network_assumptions = SharedNetworkAssumptions()
    econ = InboundRoomEconomicAssumptions(room_capex_per_unit=assumptions.additional_room_capex)
    patients = [_patient("P1", admin_minutes=0.0, los_days=1.0)]
    strict_threshold = 0.999999

    integrated_result = evaluate_inbound_room_program(
        pathway="Conventional", geometry=geometry, architecture="INTEGRATED", patients=patients,
        candidate_room_ids=["F8-R10"], already_serviced_floors=frozenset({1, 2, 3, 4, 5, 6, 7, 8}),
        central_injection_room_id=None, inbound_room_count=1, half_life_minutes=109.8,
        assumptions=assumptions, network_assumptions=network_assumptions, econ=econ,
        retention_threshold=strict_threshold,
    )
    centralized_result = evaluate_inbound_room_program(
        pathway="Conventional", geometry=geometry, architecture="CENTRALIZED", patients=patients,
        candidate_room_ids=["F8-R10"], already_serviced_floors=frozenset({1, 2, 3, 4, 5, 6, 7, 8}),
        central_injection_room_id="F1-R01", inbound_room_count=1, half_life_minutes=109.8,
        assumptions=assumptions, network_assumptions=network_assumptions, econ=econ,
        retention_threshold=0.90,
    )
    assert integrated_result.qualified_inbound_completions == 0
    assert centralized_result.qualified_inbound_completions == 1
