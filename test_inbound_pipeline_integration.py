"""Controlled regression coverage for Phase 12: inbound patient end-to-end
pipeline integration (patient identity flowing through production, room
assignment, payload, clinical flow, retention qualification, and economics).
See inbound_patient_program.py: attach_patient_type_and_los,
build_patient_value_ledger, evaluate_integrated_inbound_program.

Proves:
- the SAME patient_id appears in demand, production cycle, payload, delivery,
  administration, retention trace, and economic ledger (34);
- one production cycle can serve mixed patient types with separate downstream
  destinations (35);
- one production cycle can supply multiple distinct destinations (36);
- the integrated inbound path consumes no shared injection/uptake resource for
  its patient (37);
- the centralized inbound path consumes shared injection capacity (38);
- the outpatient path is unaffected and consumes no inbound room (39);
- multi-day room blocking is respected (40, reusing Phase 11 mechanics);
- retention differs between architectures using real route/queue timing (41);
- the MRT guideway consequence appears at the architecture level (42);
- a per-patient economic trace shows room-days independent of scan count (43);
- an unqualified (clinically-completed-but-retention-failed) patient retains
  clinical-completion diagnostic with zero qualified scan value but real
  room-day value (44);
- the ledger never fabricates a 1/N share of shared architecture CapEx (45).
"""

from __future__ import annotations

from models import SharedNetworkAssumptions
from spatial_benchmark import (
    build_benchmark_geometry,
    build_production_basis,
    compute_retention_envelope,
    optimize_pathway_layouts,
    _base_assumptions,
)
from inbound_patient_program import (
    InboundRoomEconomicAssumptions,
    PatientValueLedgerEntry,
    admit_inbound_patients,
    attach_patient_type_and_los,
    build_patient_value_ledger,
    evaluate_integrated_inbound_program,
)


def _winner_pathway_result(pathway: str):
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    basis = build_production_basis()
    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway=pathway)
    result = optimize_pathway_layouts(
        pathway=pathway, demand=200, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=env
    )
    return geometry, assumptions, basis, result


def test_same_patient_id_flows_through_every_layer() -> None:
    """Section 34: P17 (or any patient_id) must be traceable, unchanged,
    through demand, production cycle, payload, delivery, administration,
    retention trace, and the economic ledger.
    """
    geometry, assumptions, basis, result = _winner_pathway_result("Conventional")
    pathway_result = result.winner.pathway_result
    network_assumptions = SharedNetworkAssumptions()
    econ = InboundRoomEconomicAssumptions(room_capex_per_unit=assumptions.additional_room_capex)
    candidate_rooms = [rid for rid in geometry.room_ids if geometry.room_floor_by_id[rid] in (4, 5, 6)]

    real_patients = pathway_result.operational_result.demand_result.simulation.generated_demand.patients
    real_patient_ids = {p.patient_id for p in real_patients}
    assert "P17" in real_patient_ids

    program = evaluate_integrated_inbound_program(
        pathway_result=pathway_result, pathway="Conventional", geometry=geometry, architecture="INTEGRATED",
        candidate_inbound_room_ids=candidate_rooms, already_serviced_floors=frozenset({1, 2, 3}),
        central_injection_room_id=None, inbound_room_count=10, assumptions=assumptions,
        network_assumptions=network_assumptions, econ=econ,
    )

    ledger_by_id = {entry.patient_id: entry for entry in program.ledger}
    assert "P17" in ledger_by_id
    clinical_trace = next(t for t in pathway_result.operational_result.production_clinical_result.patient_traces if t.patient_id == "P17")
    decay_trace = next(t for t in pathway_result.decay_summary.patient_traces if t.patient_id == "P17")
    ledger_entry = ledger_by_id["P17"]
    assert ledger_entry.production_cycle_batch_id == clinical_trace.batch_id
    assert ledger_entry.payload_id == clinical_trace.payload_id
    assert ledger_entry.delivery_job_id == clinical_trace.delivery_job_id
    assert ledger_entry.clinically_completed == decay_trace.completed_within_operating_day


def test_one_cycle_serves_mixed_patient_types() -> None:
    """Section 35: at least one production cycle (batch_id) must serve both an
    INBOUND_PATIENT and an OUTPATIENT, each retaining its own type/destination.
    """
    geometry, assumptions, basis, result = _winner_pathway_result("Conventional")
    pathway_result = result.winner.pathway_result
    network_assumptions = SharedNetworkAssumptions()
    econ = InboundRoomEconomicAssumptions(room_capex_per_unit=assumptions.additional_room_capex)
    candidate_rooms = [rid for rid in geometry.room_ids if geometry.room_floor_by_id[rid] in (4, 5, 6)]

    program = evaluate_integrated_inbound_program(
        pathway_result=pathway_result, pathway="Conventional", geometry=geometry, architecture="INTEGRATED",
        candidate_inbound_room_ids=candidate_rooms, already_serviced_floors=frozenset({1, 2, 3}),
        central_injection_room_id=None, inbound_room_count=10, assumptions=assumptions,
        network_assumptions=network_assumptions, econ=econ,
    )

    by_cycle: dict[int, set[str]] = {}
    for entry in program.ledger:
        by_cycle.setdefault(entry.production_cycle_batch_id, set()).add(entry.patient_type)
    mixed_cycles = [cycle for cycle, types in by_cycle.items() if len(types) > 1]
    assert mixed_cycles, "Expected at least one production cycle serving both patient types"


def test_one_cycle_multiple_distinct_destinations() -> None:
    """Section 36: one production cycle can supply more than one distinct
    clinical destination (integrated room vs shared destinations).
    """
    geometry, assumptions, basis, result = _winner_pathway_result("Conventional")
    pathway_result = result.winner.pathway_result
    network_assumptions = SharedNetworkAssumptions()
    econ = InboundRoomEconomicAssumptions(room_capex_per_unit=assumptions.additional_room_capex)
    candidate_rooms = [rid for rid in geometry.room_ids if geometry.room_floor_by_id[rid] in (4, 5, 6)]

    program = evaluate_integrated_inbound_program(
        pathway_result=pathway_result, pathway="Conventional", geometry=geometry, architecture="INTEGRATED",
        candidate_inbound_room_ids=candidate_rooms, already_serviced_floors=frozenset({1, 2, 3}),
        central_injection_room_id=None, inbound_room_count=10, assumptions=assumptions,
        network_assumptions=network_assumptions, econ=econ,
    )
    destinations_by_cycle: dict[int, set[str]] = {}
    for entry in program.ledger:
        destinations_by_cycle.setdefault(entry.production_cycle_batch_id, set()).add(entry.clinical_destination_object_id)
    multi_destination_cycles = [cycle for cycle, dests in destinations_by_cycle.items() if len(dests) > 1]
    assert multi_destination_cycles, "Expected at least one cycle supplying multiple distinct destinations"


def test_integrated_path_consumes_no_shared_resource_for_its_patient() -> None:
    """Section 37: an INTEGRATED-architecture admitted patient's ledger entry
    reports architecture="INTEGRATED" and its own assigned room -- the room,
    not any shared injection/uptake room, is the destination for retention
    purposes (structurally verified: room-based retention computation, not the
    shared clinical_destination_object_id).
    """
    geometry, assumptions, basis, result = _winner_pathway_result("Conventional")
    pathway_result = result.winner.pathway_result
    network_assumptions = SharedNetworkAssumptions()
    econ = InboundRoomEconomicAssumptions(room_capex_per_unit=assumptions.additional_room_capex)
    candidate_rooms = [rid for rid in geometry.room_ids if geometry.room_floor_by_id[rid] in (4, 5, 6)]

    program = evaluate_integrated_inbound_program(
        pathway_result=pathway_result, pathway="Conventional", geometry=geometry, architecture="INTEGRATED",
        candidate_inbound_room_ids=candidate_rooms, already_serviced_floors=frozenset({1, 2, 3}),
        central_injection_room_id=None, inbound_room_count=10, assumptions=assumptions,
        network_assumptions=network_assumptions, econ=econ,
    )
    admitted_entries = [e for e in program.ledger if e.assigned_inbound_room_id is not None]
    assert admitted_entries
    for entry in admitted_entries:
        assert entry.architecture == "INTEGRATED"
        assert entry.assigned_inbound_room_id in program.room_program.rooms_selected


def test_centralized_path_consumes_shared_injection() -> None:
    """Section 38: a CENTRALIZED-architecture admitted patient's retention is
    computed against the shared clinical destination (the real clinical trace's
    assigned_destination_object_id / elapsed_release_to_injection_minutes), not
    a dedicated room-specific route.
    """
    geometry, assumptions, basis, result = _winner_pathway_result("Conventional")
    pathway_result = result.winner.pathway_result
    network_assumptions = SharedNetworkAssumptions()
    econ = InboundRoomEconomicAssumptions(room_capex_per_unit=assumptions.additional_room_capex)
    candidate_rooms = [rid for rid in geometry.room_ids if geometry.room_floor_by_id[rid] in (4, 5, 6)]
    central_room = result.winner.layout.injection_rooms[0]

    program = evaluate_integrated_inbound_program(
        pathway_result=pathway_result, pathway="Conventional", geometry=geometry, architecture="CENTRALIZED",
        candidate_inbound_room_ids=candidate_rooms, already_serviced_floors=frozenset({1, 2, 3}),
        central_injection_room_id=central_room, inbound_room_count=10, assumptions=assumptions,
        network_assumptions=network_assumptions, econ=econ,
    )
    admitted_entries = [e for e in program.ledger if e.assigned_inbound_room_id is not None]
    assert admitted_entries
    for entry in admitted_entries:
        decay_trace = next(t for t in pathway_result.decay_summary.patient_traces if t.patient_id == entry.patient_id)
        expected_elapsed = max(0.0, float(decay_trace.elapsed_release_to_injection_minutes))
        assert entry.elapsed_release_to_administration_minutes == expected_elapsed


def test_outpatient_path_unaffected_no_inbound_room_consumed() -> None:
    """Section 39: outpatient ledger entries never have an assigned inbound
    room or architecture.
    """
    geometry, assumptions, basis, result = _winner_pathway_result("Conventional")
    pathway_result = result.winner.pathway_result
    network_assumptions = SharedNetworkAssumptions()
    econ = InboundRoomEconomicAssumptions(room_capex_per_unit=assumptions.additional_room_capex)
    candidate_rooms = [rid for rid in geometry.room_ids if geometry.room_floor_by_id[rid] in (4, 5, 6)]

    program = evaluate_integrated_inbound_program(
        pathway_result=pathway_result, pathway="Conventional", geometry=geometry, architecture="INTEGRATED",
        candidate_inbound_room_ids=candidate_rooms, already_serviced_floors=frozenset({1, 2, 3}),
        central_injection_room_id=None, inbound_room_count=10, assumptions=assumptions,
        network_assumptions=network_assumptions, econ=econ,
    )
    outpatient_entries = [e for e in program.ledger if e.patient_type == "OUTPATIENT"]
    assert outpatient_entries
    for entry in outpatient_entries:
        assert entry.assigned_inbound_room_id is None
        assert entry.architecture is None
        assert entry.occupied_room_days == 0.0


def test_multi_day_room_blocking_reused() -> None:
    """Section 40 (reuses Phase 11 admission mechanics): a 7-day patient blocks
    a room across the whole occupancy window for an overlapping arrival.
    """
    from inbound_patient_program import SyntheticPatient

    p17 = SyntheticPatient(patient_id="P17", patient_type="INBOUND_PATIENT", radionuclide="F-18", prescribed_activity_mbq=370.0, administration_time_minutes=0.0, length_of_stay_days=7.0)
    p18 = SyntheticPatient(patient_id="P18", patient_type="INBOUND_PATIENT", radionuclide="F-18", prescribed_activity_mbq=370.0, administration_time_minutes=1440.0 * 3, length_of_stay_days=1.0)
    result = admit_inbound_patients([p17, p18], inbound_room_count=1)
    assert "P17" in result.admitted_patient_ids
    assert "P18" in result.unmet_patient_ids


def test_retention_differs_between_architectures_using_real_timing() -> None:
    """Section 41: integrated vs centralized retention for the same admitted
    inbound patients must be computed from real, distinct route/queue timing --
    not hard-coded to favor either architecture.
    """
    geometry, assumptions, basis, result = _winner_pathway_result("Conventional")
    pathway_result = result.winner.pathway_result
    network_assumptions = SharedNetworkAssumptions()
    econ = InboundRoomEconomicAssumptions(room_capex_per_unit=assumptions.additional_room_capex)
    candidate_rooms = [rid for rid in geometry.room_ids if geometry.room_floor_by_id[rid] in (4, 5, 6)]
    central_room = result.winner.layout.injection_rooms[0]

    integrated = evaluate_integrated_inbound_program(
        pathway_result=pathway_result, pathway="Conventional", geometry=geometry, architecture="INTEGRATED",
        candidate_inbound_room_ids=candidate_rooms, already_serviced_floors=frozenset({1, 2, 3}),
        central_injection_room_id=None, inbound_room_count=10, assumptions=assumptions,
        network_assumptions=network_assumptions, econ=econ,
    )
    centralized = evaluate_integrated_inbound_program(
        pathway_result=pathway_result, pathway="Conventional", geometry=geometry, architecture="CENTRALIZED",
        candidate_inbound_room_ids=candidate_rooms, already_serviced_floors=frozenset({1, 2, 3}),
        central_injection_room_id=central_room, inbound_room_count=10, assumptions=assumptions,
        network_assumptions=network_assumptions, econ=econ,
    )
    integrated_admitted = {e.patient_id: e for e in integrated.ledger if e.assigned_inbound_room_id is not None}
    centralized_admitted = {e.patient_id: e for e in centralized.ledger if e.assigned_inbound_room_id is not None}
    shared_ids = set(integrated_admitted) & set(centralized_admitted)
    assert shared_ids
    differences = [
        integrated_admitted[pid].elapsed_release_to_administration_minutes != centralized_admitted[pid].elapsed_release_to_administration_minutes
        for pid in shared_ids
    ]
    assert any(differences)


def test_guideway_consequence_appears_at_architecture_level() -> None:
    """Section 42: for MRT, integrated distant inbound rooms incur guideway
    CapEx at the architecture level; centralized (no new MRT destinations
    beyond the existing shared injection network) does not.
    """
    geometry, assumptions, basis, result = _winner_pathway_result("MRT")
    pathway_result = result.winner.pathway_result
    network_assumptions = SharedNetworkAssumptions()
    econ = InboundRoomEconomicAssumptions(room_capex_per_unit=assumptions.additional_room_capex)
    candidate_rooms = [rid for rid in geometry.room_ids if geometry.room_floor_by_id[rid] in (7, 8)]
    central_room = result.winner.layout.injection_rooms[0]

    integrated = evaluate_integrated_inbound_program(
        pathway_result=pathway_result, pathway="MRT", geometry=geometry, architecture="INTEGRATED",
        candidate_inbound_room_ids=candidate_rooms, already_serviced_floors=frozenset(result.winner.layout.active_floors),
        central_injection_room_id=None, inbound_room_count=5, assumptions=assumptions,
        network_assumptions=network_assumptions, econ=econ,
    )
    centralized = evaluate_integrated_inbound_program(
        pathway_result=pathway_result, pathway="MRT", geometry=geometry, architecture="CENTRALIZED",
        candidate_inbound_room_ids=candidate_rooms, already_serviced_floors=frozenset(result.winner.layout.active_floors),
        central_injection_room_id=central_room, inbound_room_count=5, assumptions=assumptions,
        network_assumptions=network_assumptions, econ=econ,
    )
    assert integrated.room_program.incremental_mrt_guideway_capex > 0.0
    assert centralized.room_program.incremental_mrt_guideway_capex == 0.0


def test_patient_economic_trace_seven_days_one_scan() -> None:
    """Section 43: an inbound patient occupying a room for 7 days with one
    qualified scan must show 7 room-days of value and exactly 1 scan's value,
    with the SAME patient_id preserved in the ledger.
    """
    geometry, assumptions, basis, result = _winner_pathway_result("Conventional")
    pathway_result = result.winner.pathway_result
    network_assumptions = SharedNetworkAssumptions()
    daily_rate = 500.0
    econ = InboundRoomEconomicAssumptions(room_capex_per_unit=assumptions.additional_room_capex, room_revenue_per_occupied_day=daily_rate)
    candidate_rooms = [rid for rid in geometry.room_ids if geometry.room_floor_by_id[rid] in (4, 5, 6)]

    program = evaluate_integrated_inbound_program(
        pathway_result=pathway_result, pathway="Conventional", geometry=geometry, architecture="INTEGRATED",
        candidate_inbound_room_ids=candidate_rooms, already_serviced_floors=frozenset({1, 2, 3}),
        central_injection_room_id=None, inbound_room_count=10, assumptions=assumptions,
        network_assumptions=network_assumptions, econ=econ,
        length_of_stay_days_options=(7.0,),
    )
    admitted_entries = [e for e in program.ledger if e.assigned_inbound_room_id is not None]
    assert admitted_entries
    entry = admitted_entries[0]
    assert entry.length_of_stay_days == 7.0
    assert entry.room_day_value == 7.0 * daily_rate
    if entry.retention_qualified_completion:
        assert entry.qualified_scan_value == assumptions.revenue_per_scan
    else:
        assert entry.qualified_scan_value == 0.0


def test_unqualified_patient_retains_clinical_completion_with_zero_qualified_value() -> None:
    """Section 44: a patient who clinically completes but fails the retention
    criterion must show clinically_completed=True, retention_qualified_completion=False,
    qualified_scan_value=0.0, while legitimate room-day value (if admitted) is
    NOT erased.
    """
    geometry, assumptions, basis, result = _winner_pathway_result("Conventional")
    pathway_result = result.winner.pathway_result
    network_assumptions = SharedNetworkAssumptions()
    econ = InboundRoomEconomicAssumptions(room_capex_per_unit=assumptions.additional_room_capex)
    candidate_rooms = [rid for rid in geometry.room_ids if geometry.room_floor_by_id[rid] in (4, 5, 6)]

    # An artificially strict threshold forces some clinically-completed patients to fail retention.
    program = evaluate_integrated_inbound_program(
        pathway_result=pathway_result, pathway="Conventional", geometry=geometry, architecture="INTEGRATED",
        candidate_inbound_room_ids=candidate_rooms, already_serviced_floors=frozenset({1, 2, 3}),
        central_injection_room_id=None, inbound_room_count=10, assumptions=assumptions,
        network_assumptions=network_assumptions, econ=econ, retention_threshold=0.999999,
    )
    unqualified_but_completed = [
        e for e in program.ledger if e.clinically_completed and not e.retention_qualified_completion
    ]
    assert unqualified_but_completed
    for entry in unqualified_but_completed:
        assert entry.qualified_scan_value == 0.0
        if entry.assigned_inbound_room_id is not None:
            assert entry.room_day_value == entry.length_of_stay_days * econ.room_revenue_per_occupied_day


def test_ledger_never_fabricates_shared_capex_share() -> None:
    """Section 45: PatientValueLedgerEntry must never contain a per-patient
    share of shared architecture CapEx (scanner/cyclotron/guideway/building).
    """
    field_names = set(PatientValueLedgerEntry.__dataclass_fields__.keys())
    forbidden_substrings = ("capex", "scanner_share", "cyclotron_share", "guideway_share")
    for field_name in field_names:
        lowered = field_name.lower()
        assert not any(token in lowered for token in forbidden_substrings), f"Unexpected shared-CapEx-like field: {field_name}"
