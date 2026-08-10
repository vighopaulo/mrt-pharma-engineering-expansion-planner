from __future__ import annotations

import math

from engineering import required_rooms, required_scanners, retention, room_capacity, scanner_capacity
from finance import incremental_financials
from models import ConventionalPlan, MRTPlan, PlanFinancials, PlannerAssumptions, PlannerInputs


def _ledger_item(
    component: str,
    quantity: float,
    unit_cost: float,
    basis: str,
    assumption_source: str,
) -> dict[str, object]:
    return {
        "component": component,
        "quantity": quantity,
        "unit_cost": unit_cost,
        "subtotal": quantity * unit_cost,
        "basis": basis,
        "assumption_source": assumption_source,
    }


def _build_financials(
    capex: float,
    annual_incremental_opex: float,
    throughput_patients_per_day: float,
    assumptions: PlannerAssumptions,
) -> PlanFinancials:
    revenue, opex, ncf, npv, roi, payback = incremental_financials(
        capex=capex,
        annual_incremental_opex=annual_incremental_opex,
        throughput_patients_per_day=throughput_patients_per_day,
        revenue_per_scan=assumptions.revenue_per_scan,
        operating_days_per_year=assumptions.operating_days_per_year,
        discount_rate_pct=assumptions.discount_rate_pct,
        analysis_years=assumptions.analysis_years,
    )
    return PlanFinancials(
        annual_revenue=revenue,
        annual_incremental_opex=opex,
        annual_net_cash_flow=ncf,
        npv=npv,
        roi_pct=roi,
        payback_years=payback,
    )


def _conventional_transport_min(inputs: PlannerInputs) -> float:
    return inputs.conventional_transport_min if inputs.conventional_transport_min is not None else inputs.current_average_transport_min


def _base_day_capacities(
    scanners: int,
    injection_rooms: int,
    uptake_rooms: int,
    assumptions: PlannerAssumptions,
) -> tuple[float, float, float]:
    scanner_cap = scanner_capacity(
        scanners,
        assumptions.operating_hours_per_day,
        assumptions.scanner_cycle_min,
        assumptions.scanner_availability_pct,
    )
    injection_cap = room_capacity(
        injection_rooms,
        assumptions.operating_hours_per_day,
        assumptions.injection_cycle_min,
    )
    uptake_cap = room_capacity(
        uptake_rooms,
        assumptions.operating_hours_per_day,
        assumptions.uptake_cycle_min,
    )
    return scanner_cap, injection_cap, uptake_cap


def conventional(inputs: PlannerInputs, assumptions: PlannerAssumptions, half_life_min: float) -> ConventionalPlan:
    transport_min = _conventional_transport_min(inputs)
    retained = retention(transport_min, half_life_min)

    growth_factor = inputs.target_patients_per_day / inputs.current_patients_per_day

    proportional_scanners = math.ceil(inputs.current_scanners * growth_factor)
    proportional_injection = math.ceil(inputs.current_injection_rooms * growth_factor)
    proportional_uptake = math.ceil(inputs.current_uptake_rooms * growth_factor)
    required_usable_doses_per_day = inputs.target_patients_per_day
    required_gross_doses_per_day = required_usable_doses_per_day / max(retained, 1e-9)

    required_total_scanners = proportional_scanners
    scanner_cap = scanner_capacity(
        required_total_scanners,
        assumptions.operating_hours_per_day,
        assumptions.scanner_cycle_min,
        assumptions.scanner_availability_pct,
    )
    while scanner_cap + 1e-9 < inputs.target_patients_per_day:
        required_total_scanners += 1
        scanner_cap = scanner_capacity(
            required_total_scanners,
            assumptions.operating_hours_per_day,
            assumptions.scanner_cycle_min,
            assumptions.scanner_availability_pct,
        )

    required_total_injection = proportional_injection
    injection_cap = room_capacity(
        required_total_injection,
        assumptions.operating_hours_per_day,
        assumptions.injection_cycle_min,
    )
    while injection_cap + 1e-9 < inputs.target_patients_per_day:
        required_total_injection += 1
        injection_cap = room_capacity(
            required_total_injection,
            assumptions.operating_hours_per_day,
            assumptions.injection_cycle_min,
        )

    required_total_uptake = proportional_uptake
    uptake_cap = room_capacity(
        required_total_uptake,
        assumptions.operating_hours_per_day,
        assumptions.uptake_cycle_min,
    )
    while uptake_cap + 1e-9 < inputs.target_patients_per_day:
        required_total_uptake += 1
        uptake_cap = room_capacity(
            required_total_uptake,
            assumptions.operating_hours_per_day,
            assumptions.uptake_cycle_min,
        )

    additional_scanners = max(0, required_total_scanners - inputs.current_scanners)
    additional_injection = max(0, required_total_injection - inputs.current_injection_rooms)
    additional_uptake = max(0, required_total_uptake - inputs.current_uptake_rooms)
    additional_doses_per_day = max(0.0, required_gross_doses_per_day - inputs.current_usable_doses_per_day)

    if inputs.current_patients_per_day > 0:
        capacity_increase_pct = (
            (inputs.target_patients_per_day - inputs.current_patients_per_day)
            / inputs.current_patients_per_day
            * 100.0
        )
    else:
        capacity_increase_pct = 100.0

    production_increase_pct = max(
        0.0,
        (required_gross_doses_per_day / max(1.0, inputs.current_usable_doses_per_day) - 1.0) * 100.0,
    )

    cyclotron_required = (not inputs.has_existing_cyclotron) and additional_doses_per_day > 0
    production_expansion_blocks = math.ceil(production_increase_pct / 10.0)
    expanded_gross_production_capacity = inputs.current_usable_doses_per_day * (1.0 + production_expansion_blocks * 0.1)
    expanded_usable_capacity_at_destination = expanded_gross_production_capacity * retained

    capex = (
        additional_scanners * assumptions.scanner_capex
        + (additional_injection + additional_uptake) * assumptions.additional_room_capex
        + production_expansion_blocks * assumptions.production_expansion_capex_per_10pct
        + (
            assumptions.cyclotron_purchase_capex + assumptions.cyclotron_installation_capex
            if cyclotron_required
            else 0.0
        )
    )

    annual_incremental_opex = (
        additional_scanners * assumptions.scanner_incremental_opex
        + (additional_injection + additional_uptake) * assumptions.room_incremental_opex
    )

    achieved = min(scanner_cap, injection_cap, uptake_cap, expanded_usable_capacity_at_destination)

    financials = _build_financials(
        capex,
        annual_incremental_opex,
        throughput_patients_per_day=inputs.target_patients_per_day,
        assumptions=assumptions,
    )

    ledger = {
        "proportional_scanner_estimate": proportional_scanners,
        "proportional_injection_room_estimate": proportional_injection,
        "proportional_uptake_room_estimate": proportional_uptake,
        "required_total_scanners": required_total_scanners,
        "required_total_injection_rooms": required_total_injection,
        "required_total_uptake_rooms": required_total_uptake,
        "conventional_transport_time": transport_min,
        "conventional_transport_time_unit": "minutes",
        "growth_factor": growth_factor,
        "required_usable_doses_per_day": required_usable_doses_per_day,
        "required_gross_doses_per_day": required_gross_doses_per_day,
        "expanded_gross_production_capacity_per_day": expanded_gross_production_capacity,
        "expanded_usable_capacity_at_destination_per_day": expanded_usable_capacity_at_destination,
        "additional_doses_per_day": additional_doses_per_day,
        "half_life_for_retention": half_life_min,
        "half_life_unit": "minutes",
        "retained_activity_fraction": retained,
        "retention_formula": "2^(-transport_min / half_life_min)",
        "transport_only_retention_fraction": retained,
        "common_administration_wait_min": assumptions.common_administration_wait_min,
        "administration_decay_endpoint_min": (
            transport_min + assumptions.common_administration_wait_min
        ),
        "administration_retention_fraction": retention(
            transport_min + assumptions.common_administration_wait_min,
            half_life_min,
        ),
        "scanner_capacity_patients_per_day": scanner_cap,
        "injection_capacity_patients_per_day": injection_cap,
        "uptake_capacity_patients_per_day": uptake_cap,
        "production_expansion_blocks_10pct": production_expansion_blocks,
        "conventional_achieved_capacity_patients_per_day": achieved,
        "conventional_revenue_throughput_patients_per_day": inputs.target_patients_per_day,
    }

    capex_ledger = [
        _ledger_item(
            "Additional scanners",
            float(additional_scanners),
            assumptions.scanner_capex,
            "final_required_scanners - current_scanners",
            "PlannerAssumptions.scanner_capex",
        ),
        _ledger_item(
            "Additional injection rooms",
            float(additional_injection),
            assumptions.additional_room_capex,
            "final_required_injection_rooms - current_injection_rooms",
            "PlannerAssumptions.additional_room_capex",
        ),
        _ledger_item(
            "Additional uptake rooms",
            float(additional_uptake),
            assumptions.additional_room_capex,
            "final_required_uptake_rooms - current_uptake_rooms",
            "PlannerAssumptions.additional_room_capex",
        ),
        _ledger_item(
            "Production expansion blocks (10%)",
            float(production_expansion_blocks),
            assumptions.production_expansion_capex_per_10pct,
            "ceil(production_increase_pct/10)",
            "PlannerAssumptions.production_expansion_capex_per_10pct",
        ),
        _ledger_item(
            "Cyclotron purchase",
            1.0 if cyclotron_required else 0.0,
            assumptions.cyclotron_purchase_capex,
            "charged only when cyclotron_required is true",
            "PlannerAssumptions.cyclotron_purchase_capex",
        ),
        _ledger_item(
            "Cyclotron installation",
            1.0 if cyclotron_required else 0.0,
            assumptions.cyclotron_installation_capex,
            "charged only when cyclotron_required is true",
            "PlannerAssumptions.cyclotron_installation_capex",
        ),
    ]

    return ConventionalPlan(
        capacity_increase_pct=max(0.0, capacity_increase_pct),
        required_production_increase_pct=production_increase_pct,
        additional_scanners=additional_scanners,
        additional_injection_rooms=additional_injection,
        additional_uptake_rooms=additional_uptake,
        cyclotron_required=cyclotron_required,
        retained_activity_pct=retained * 100.0,
        achieved_capacity_per_day=achieved,
        reserve_capacity_per_day=max(0.0, achieved - inputs.target_patients_per_day),
        revenue_generating_throughput_per_day=inputs.target_patients_per_day,
        capex=capex,
        financials=financials,
        capex_ledger=capex_ledger,
        ledger=ledger,
    )


def mrt(inputs: PlannerInputs, assumptions: PlannerAssumptions, half_life_min: float) -> MRTPlan:
    mrt_transport_min = (
        assumptions.mrt_transport_default_min
        if inputs.mrt_transport_min is None
        else inputs.mrt_transport_min
    )
    retained = retention(mrt_transport_min, half_life_min)

    current_total_rooms = inputs.current_injection_rooms + inputs.current_uptake_rooms
    required_total_scanners = required_scanners(
        inputs.target_patients_per_day,
        assumptions.operating_hours_per_day,
        assumptions.scanner_cycle_min,
        assumptions.scanner_availability_pct,
    )
    required_total_rooms = required_rooms(
        inputs.target_patients_per_day,
        1,
        assumptions.operating_hours_per_day,
        assumptions.uptake_cycle_min,
    )

    best: MRTPlan | None = None
    for production_increase_pct in range(0, 401, 10):
        production_cap = (
            inputs.current_usable_doses_per_day
            * (1.0 + production_increase_pct / 100.0)
            * retained
        )

        for add_scanners in range(max(0, required_total_scanners - inputs.current_scanners), 8):
            total_scanners = inputs.current_scanners + add_scanners
            scanner_cap = scanner_capacity(
                total_scanners,
                assumptions.operating_hours_per_day,
                assumptions.scanner_cycle_min,
                assumptions.scanner_availability_pct,
            )

            for new_rooms in range(0, 16):
                connectable_rooms = inputs.existing_mrt_connectable_rooms + new_rooms
                total_rooms = current_total_rooms + connectable_rooms
                add_rooms = max(0, total_rooms - current_total_rooms)
                if total_rooms < required_total_rooms:
                    continue

                for infra_units in range(1, 5):
                    guideway_segments = infra_units + max(1, connectable_rooms // 4)
                    endpoints = 2 + connectable_rooms

                    room_cap = room_capacity(
                        total_rooms,
                        assumptions.operating_hours_per_day,
                        assumptions.uptake_cycle_min,
                    )
                    guideway_cap = endpoints * (8.0 + 2.0 * infra_units)

                    achieved = min(production_cap, scanner_cap, room_cap, guideway_cap)
                    if achieved + 1e-9 < inputs.target_patients_per_day:
                        continue

                    cyclotron_required = (not inputs.has_existing_cyclotron) and production_increase_pct > 0
                    production_blocks = math.ceil(production_increase_pct / 10.0)

                    capex = (
                        assumptions.mrt_infrastructure_capex
                        + guideway_segments * assumptions.guideway_segment_capex
                        + endpoints * assumptions.endpoint_capex
                        + add_scanners * assumptions.scanner_capex
                        + add_rooms * assumptions.additional_room_capex
                        + production_blocks * assumptions.production_expansion_capex_per_10pct
                        + (
                            assumptions.cyclotron_purchase_capex + assumptions.cyclotron_installation_capex
                            if cyclotron_required
                            else 0.0
                        )
                    )

                    annual_incremental_opex = (
                        add_scanners * assumptions.scanner_incremental_opex
                        + add_rooms * assumptions.room_incremental_opex
                        + endpoints * assumptions.endpoint_incremental_opex
                        + infra_units * assumptions.guideway_incremental_opex
                    )

                    revenue_throughput = min(achieved, inputs.maximum_expected_demand_per_day)
                    financials = _build_financials(
                        capex,
                        annual_incremental_opex,
                        throughput_patients_per_day=revenue_throughput,
                        assumptions=assumptions,
                    )
                    reserve = max(0.0, achieved - inputs.target_patients_per_day)

                    candidate = MRTPlan(
                        production_increase_pct=production_increase_pct,
                        additional_scanners=add_scanners,
                        new_mrt_rooms=new_rooms,
                        additional_injection_rooms=0,
                        additional_uptake_rooms=add_rooms,
                        guideway_segments=guideway_segments,
                        endpoints=endpoints,
                        infrastructure_units=infra_units,
                        retained_activity_pct=retained * 100.0,
                        achieved_capacity_per_day=achieved,
                        reserve_capacity_per_day=reserve,
                        revenue_generating_throughput_per_day=revenue_throughput,
                        capex=capex,
                        financials=financials,
                        capex_ledger=[
                            _ledger_item(
                                "MRT base infrastructure",
                                1.0,
                                assumptions.mrt_infrastructure_capex,
                                "Base central MRT platform; excludes variable guideway/endpoints",
                                "PlannerAssumptions.mrt_infrastructure_capex",
                            ),
                            _ledger_item(
                                "Guideway segments",
                                float(guideway_segments),
                                assumptions.guideway_segment_capex,
                                "infra_units + max(1, connectable_rooms // 4)",
                                "PlannerAssumptions.guideway_segment_capex",
                            ),
                            _ledger_item(
                                "Endpoints",
                                float(endpoints),
                                assumptions.endpoint_capex,
                                "2 + connectable_rooms",
                                "PlannerAssumptions.endpoint_capex",
                            ),
                            _ledger_item(
                                "Additional scanners",
                                float(add_scanners),
                                assumptions.scanner_capex,
                                "total_scanners - current_scanners",
                                "PlannerAssumptions.scanner_capex",
                            ),
                            _ledger_item(
                                "Additional rooms",
                                float(add_rooms),
                                assumptions.additional_room_capex,
                                "total_rooms - current_total_rooms",
                                "PlannerAssumptions.additional_room_capex",
                            ),
                            _ledger_item(
                                "Production expansion blocks (10%)",
                                float(production_blocks),
                                assumptions.production_expansion_capex_per_10pct,
                                "ceil(production_increase_pct/10)",
                                "PlannerAssumptions.production_expansion_capex_per_10pct",
                            ),
                            _ledger_item(
                                "Cyclotron purchase",
                                1.0 if cyclotron_required else 0.0,
                                assumptions.cyclotron_purchase_capex,
                                "charged only when cyclotron_required is true",
                                "PlannerAssumptions.cyclotron_purchase_capex",
                            ),
                            _ledger_item(
                                "Cyclotron installation",
                                1.0 if cyclotron_required else 0.0,
                                assumptions.cyclotron_installation_capex,
                                "charged only when cyclotron_required is true",
                                "PlannerAssumptions.cyclotron_installation_capex",
                            ),
                        ],
                        ledger={
                            "mrt_transport_time": mrt_transport_min,
                            "mrt_transport_time_unit": "minutes",
                            "half_life_for_retention": half_life_min,
                            "half_life_unit": "minutes",
                            "retained_activity_fraction": retained,
                            "retention_formula": "2^(-transport_min / half_life_min)",
                            "production_capacity_patients_per_day": production_cap,
                            "scanner_capacity_patients_per_day": scanner_cap,
                            "room_capacity_patients_per_day": room_cap,
                            "guideway_capacity_patients_per_day": guideway_cap,
                            "mrt_revenue_throughput_patients_per_day": revenue_throughput,
                            "guideway_segments": guideway_segments,
                            "guideway_unit_cost": assumptions.guideway_segment_capex,
                            "guideway_subtotal": guideway_segments * assumptions.guideway_segment_capex,
                            "endpoint_count": endpoints,
                            "endpoint_unit_cost": assumptions.endpoint_capex,
                            "endpoint_subtotal": endpoints * assumptions.endpoint_capex,
                        },
                    )

                    if best is None:
                        best = candidate
                        continue

                    current_rank = (
                        candidate.capex,
                        candidate.new_mrt_rooms,
                        candidate.infrastructure_units,
                        candidate.additional_scanners,
                        -candidate.retained_activity_pct,
                        -candidate.reserve_capacity_per_day,
                    )
                    best_rank = (
                        best.capex,
                        best.new_mrt_rooms,
                        best.infrastructure_units,
                        best.additional_scanners,
                        -best.retained_activity_pct,
                        -best.reserve_capacity_per_day,
                    )
                    if current_rank < best_rank:
                        best = candidate

    if best is None:
        raise ValueError("No feasible MRT configuration found for the requested target capacity.")

    return best
