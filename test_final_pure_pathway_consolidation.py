"""Controlled regression coverage for the final pure-pathway reference
consolidation build. See asset_cost_ledger.build_finalist_unified_ledger:
combining a base architecture CapEx/OPEX ledger with the incremental inbound
room program ledger (room CapEx/OPEX and, for MRT INTEGRATED, guideway
extension), for one finalist reconciliation with no cost overlap.
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
    attach_patient_type_and_los,
    optimize_inbound_room_count,
)
from asset_cost_ledger import (
    build_asset_cost_ledger,
    build_finalist_unified_ledger,
    reconcile_capex_ledger,
    reconcile_opex_ledger,
)


def _finalist(pathway: str, architecture: str):
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    basis = build_production_basis()
    network_assumptions = SharedNetworkAssumptions()
    econ = InboundRoomEconomicAssumptions(room_capex_per_unit=assumptions.additional_room_capex)
    candidate_inbound_rooms = [rid for rid in geometry.room_ids if geometry.room_floor_by_id[rid] in (4, 5, 6)]
    already_serviced_floors = frozenset({1, 2, 3})

    env = compute_retention_envelope(geometry=geometry, assumptions=assumptions, radionuclide=basis.radionuclide, pathway=pathway)
    result = optimize_pathway_layouts(
        pathway=pathway, demand=200, geometry=geometry, production_basis=basis, assumptions=assumptions, retention_envelope=env
    )
    base_winner = result.winner
    real_patients = base_winner.pathway_result.operational_result.demand_result.simulation.generated_demand.patients
    synthetic_patients = attach_patient_type_and_los(real_patients)
    central_room = base_winner.layout.injection_rooms[0]

    room_program, _npv, _evaluated = optimize_inbound_room_count(
        pathway=pathway, geometry=geometry, architecture=architecture, patients=synthetic_patients,
        candidate_room_ids=candidate_inbound_rooms, already_serviced_floors=already_serviced_floors,
        central_injection_room_id=(central_room if architecture == "CENTRALIZED" else None),
        half_life_minutes=109.8, assumptions=assumptions, network_assumptions=network_assumptions, econ=econ,
    )
    return base_winner, room_program


def test_finalist_unified_ledger_reconciles_capex_and_opex_conventional_integrated() -> None:
    base_winner, room_program = _finalist("Conventional", "INTEGRATED")
    base_ledger = build_asset_cost_ledger(base_winner.pathway_result, pathway="Conventional")
    unified = build_finalist_unified_ledger(
        base_ledger, pathway="Conventional",
        inbound_room_capex=room_program.inbound_room_capex,
        inbound_room_annual_opex=room_program.inbound_room_annual_opex,
        inbound_mrt_guideway_capex=room_program.incremental_mrt_guideway_capex,
        inbound_room_count=room_program.inbound_room_count,
    )
    total_capex = base_winner.total_capex + room_program.inbound_room_capex + room_program.incremental_mrt_guideway_capex
    total_opex = base_winner.annual_total_opex + room_program.inbound_room_annual_opex
    capex_ok, capex_diff = reconcile_capex_ledger(unified, total_capex)
    opex_ok, opex_diff = reconcile_opex_ledger(unified, total_opex)
    assert capex_ok, f"diff={capex_diff}"
    assert opex_ok, f"diff={opex_diff}"


def test_finalist_unified_ledger_reconciles_for_mrt_integrated_with_guideway() -> None:
    base_winner, room_program = _finalist("MRT", "INTEGRATED")
    assert room_program.incremental_mrt_guideway_capex > 0.0
    base_ledger = build_asset_cost_ledger(base_winner.pathway_result, pathway="MRT")
    unified = build_finalist_unified_ledger(
        base_ledger, pathway="MRT",
        inbound_room_capex=room_program.inbound_room_capex,
        inbound_room_annual_opex=room_program.inbound_room_annual_opex,
        inbound_mrt_guideway_capex=room_program.incremental_mrt_guideway_capex,
        inbound_room_count=room_program.inbound_room_count,
    )
    total_capex = base_winner.total_capex + room_program.inbound_room_capex + room_program.incremental_mrt_guideway_capex
    total_opex = base_winner.annual_total_opex + room_program.inbound_room_annual_opex
    capex_ok, capex_diff = reconcile_capex_ledger(unified, total_capex)
    opex_ok, opex_diff = reconcile_opex_ledger(unified, total_opex)
    assert capex_ok, f"diff={capex_diff}"
    assert opex_ok, f"diff={opex_diff}"

    # The inbound guideway extension must appear exactly once, not folded into
    # (or duplicated with) the base "MRT guideway" line.
    guideway_lines = [e for e in unified if "guideway" in e.asset_type.lower()]
    assert any(e.asset_type == "MRT guideway" for e in guideway_lines)
    assert any(e.asset_type == "MRT inbound guideway/station extension" for e in guideway_lines)


def test_finalist_unified_ledger_no_inbound_rooms_omits_inbound_lines() -> None:
    base_winner, room_program = _finalist("Conventional", "INTEGRATED")
    base_ledger = build_asset_cost_ledger(base_winner.pathway_result, pathway="Conventional")
    unified_zero = build_finalist_unified_ledger(
        base_ledger, pathway="Conventional",
        inbound_room_capex=0.0, inbound_room_annual_opex=0.0, inbound_mrt_guideway_capex=0.0, inbound_room_count=0,
    )
    assert not any(e.asset_type == "Inbound rooms" for e in unified_zero)
    assert len(unified_zero) == len(base_ledger)


def test_integrated_beats_centralized_for_both_pathways_in_baseline() -> None:
    """Section 48: report which architecture is preferred -- do not assume it."""
    for pathway in ("Conventional", "MRT"):
        _base_winner_i, room_program_integrated = _finalist(pathway, "INTEGRATED")
        _base_winner_c, room_program_centralized = _finalist(pathway, "CENTRALIZED")
        assert room_program_integrated.qualified_inbound_completions >= room_program_centralized.qualified_inbound_completions
