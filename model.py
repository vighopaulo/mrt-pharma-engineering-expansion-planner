"""
MRT Pharma Decision-Support Digital Twin
Core calculation / optimization engine.

This module contains ONLY math and optimization logic -- no Streamlit,
no I/O -- so it can be imported and unit tested independently of the UI.

Implements the specification sections 1-27 exactly:
  - Conventional benchmark (single batch/day, proportional expansion)
  - MRT two-stage optimizer:
        Stage 1: minimize required production increase (U_m)
        Stage 2: at that minimum U_m, maximize NPV over feasible
                 (batches, additional dedicated rooms, MRT inpatient rooms)
  - Shared scanner-capacity sizing (Section 7: applies to BOTH options)
  - Shared financial engine (CapEx, OpEx, NCF, NPV, ROI, Payback)
  - Infeasibility diagnostics (Section 32)
"""

from dataclasses import dataclass, field
import math


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------

@dataclass
class Inputs:
    # Section 1: Hospital today and future target
    current_patients: float
    target_patients: float
    current_scanners: int
    operating_hours: float
    scanner_cycle_min: float
    scanner_availability: float          # fraction, e.g. 0.85
    current_injection_rooms: int
    current_uptake_rooms: int
    patients_per_dedicated_room: float
    current_doses_per_batch: float

    # Section 2: Transport and MRT limits
    conventional_delivery_time: float    # minutes
    mrt_delivery_time: float             # minutes
    isotope_half_life: float             # minutes
    max_mrt_batches_per_day: int
    max_mrt_inpatient_rooms: int
    patients_per_mrt_inpatient_room: float
    max_additional_mrt_dedicated_rooms: int
    supporting_mrt_destinations: int

    # Section 3: Economics
    capex_per_scanner: float
    capex_per_dedicated_room: float
    capex_conv_upgrade_per_10pct: float
    capex_mrt_upgrade_per_10pct: float
    capex_mrt_core: float
    capex_per_endpoint: float
    max_capex_budget: float
    net_contribution_per_patient: float
    opex_base_conventional: float
    opex_base_mrt: float
    opex_per_additional_scanner: float
    opex_per_additional_dedicated_room: float
    opex_mrt_maintenance: float
    opex_per_endpoint: float
    annual_cost_per_extra_daily_batch: float
    operating_days_per_year: float
    analysis_period_years: int
    discount_rate: float                 # e.g. 0.08

    # Search control (not user-facing "decision" variables -- just solver knobs)
    production_search_increment: float = 5.0   # percent


# --------------------------------------------------------------------------
# Shared building blocks (Sections 6-13)
# --------------------------------------------------------------------------

def round_up_increment(value, increment):
    if increment <= 0:
        return value
    return increment * math.ceil(round(value / increment, 9))


def retained_fraction(delivery_time, half_life):
    """Eta(t) = 2^(-t / T_half).  Section 12."""
    if half_life <= 0:
        return 0.0
    return 2 ** (-delivery_time / half_life)


def scanner_capacity_one(operating_hours, cycle_minutes, availability):
    """Patients/day one scanner can process.  Section 7."""
    if cycle_minutes <= 0:
        return 0.0
    return (60.0 * operating_hours / cycle_minutes) * availability


def scanner_requirement(target_patients, current_scanners, operating_hours,
                         cycle_minutes, availability):
    """Section 7 -- identical calculation for BOTH architectures."""
    cap_one = scanner_capacity_one(operating_hours, cycle_minutes, availability)
    if cap_one <= 0:
        required = math.inf
    else:
        required = math.ceil(target_patients / cap_one)
    additional = max(0, required - current_scanners) if math.isfinite(required) else math.inf
    total = current_scanners + additional if math.isfinite(additional) else math.inf
    total_capacity = total * cap_one if math.isfinite(total) else 0.0
    return {
        "capacity_per_scanner": cap_one,
        "required_scanners": required,
        "additional_scanners": additional,
        "total_scanners": total,
        "total_capacity": total_capacity,
    }


def conventional_production_increase(target_patients, doses_per_batch,
                                      eta_conventional, increment):
    """Section 6.  U_c = 100*(Qt/(D0*eta_c) - 1), rounded UP to increment."""
    if doses_per_batch <= 0 or eta_conventional <= 0:
        return math.inf
    raw = 100.0 * (target_patients / (doses_per_batch * eta_conventional) - 1.0)
    raw = max(raw, 0.0)
    return round_up_increment(raw, increment)


def conventional_room_requirement(target_patients, current_rooms, patients_per_room):
    """Section 8 -- used for both injection and uptake (same formula)."""
    if patients_per_room <= 0:
        required = math.inf
    else:
        required = math.ceil(target_patients / patients_per_room)
    additional = max(0, required - current_rooms) if math.isfinite(required) else math.inf
    return required, additional


# --------------------------------------------------------------------------
# Conventional architecture (Section 6, 8, 16, 19)
# --------------------------------------------------------------------------

@dataclass
class ConventionalResult:
    feasible: bool
    infeasible_reasons: list = field(default_factory=list)
    U_c: float = 0.0
    eta_c: float = 0.0
    dose_capacity: float = 0.0
    scanner: dict = field(default_factory=dict)
    injection_required: float = 0.0
    injection_additional: float = 0.0
    uptake_required: float = 0.0
    uptake_additional: float = 0.0
    installed_capacity: float = 0.0
    served_patients: float = 0.0
    capex: float = 0.0
    opex: float = 0.0
    revenue: float = 0.0
    ncf: float = 0.0
    npv: float = 0.0
    roi: float = 0.0
    payback: float = None


def compute_conventional(inp: Inputs) -> ConventionalResult:
    eta_c = retained_fraction(inp.conventional_delivery_time, inp.isotope_half_life)

    U_c = conventional_production_increase(
        inp.target_patients, inp.current_doses_per_batch, eta_c,
        inp.production_search_increment,
    )

    dose_capacity = inp.current_doses_per_batch * (1 + U_c / 100.0) * eta_c

    scanner = scanner_requirement(
        inp.target_patients, inp.current_scanners, inp.operating_hours,
        inp.scanner_cycle_min, inp.scanner_availability,
    )

    inj_req, inj_add = conventional_room_requirement(
        inp.target_patients, inp.current_injection_rooms, inp.patients_per_dedicated_room)
    up_req, up_add = conventional_room_requirement(
        inp.target_patients, inp.current_uptake_rooms, inp.patients_per_dedicated_room)

    injection_capacity = (inp.current_injection_rooms + inj_add) * inp.patients_per_dedicated_room
    uptake_capacity = (inp.current_uptake_rooms + up_add) * inp.patients_per_dedicated_room

    installed_capacity = min(dose_capacity, scanner["total_capacity"],
                              injection_capacity, uptake_capacity)

    served = min(installed_capacity, inp.target_patients)

    # CapEx (Section 16)
    capex = (
        (U_c / 10.0) * inp.capex_conv_upgrade_per_10pct
        + scanner["additional_scanners"] * inp.capex_per_scanner
        + (inj_add + up_add) * inp.capex_per_dedicated_room
    )

    # OpEx (Section 19)
    opex = (
        inp.opex_base_conventional
        + scanner["additional_scanners"] * inp.opex_per_additional_scanner
        + (inj_add + up_add) * inp.opex_per_additional_dedicated_room
    )

    incremental_patients = max(0.0, served - inp.current_patients)
    revenue = incremental_patients * inp.operating_days_per_year * inp.net_contribution_per_patient
    ncf = revenue - opex

    npv = -capex
    for y in range(1, inp.analysis_period_years + 1):
        npv += ncf / ((1 + inp.discount_rate) ** y)

    roi = ((ncf * inp.analysis_period_years - capex) / capex * 100.0) if capex > 0 else 0.0
    payback = (capex / ncf) if ncf > 0 else None

    reasons = []
    if served < inp.target_patients:
        reasons.append("Insufficient installed capacity to reach target.")
    if capex > inp.max_capex_budget:
        reasons.append(f"CapEx exceeds budget by ${capex - inp.max_capex_budget:,.0f}.")
    if ncf <= 0:
        reasons.append("Annual net cash flow is negative or zero.")
    if npv <= 0:
        reasons.append("NPV is negative or zero.")

    feasible = (served >= inp.target_patients) and not reasons

    return ConventionalResult(
        feasible=feasible,
        infeasible_reasons=reasons,
        U_c=U_c, eta_c=eta_c, dose_capacity=dose_capacity, scanner=scanner,
        injection_required=inj_req, injection_additional=inj_add,
        uptake_required=up_req, uptake_additional=up_add,
        installed_capacity=installed_capacity, served_patients=served,
        capex=capex, opex=opex, revenue=revenue, ncf=ncf, npv=npv, roi=roi,
        payback=payback,
    )


# --------------------------------------------------------------------------
# MRT architecture (Sections 5, 9-12, 17-18, 20)
# --------------------------------------------------------------------------

def mrt_min_batches(target_patients, doses_per_batch, U_m, eta_m, max_batches):
    """Smallest B_m meeting dose target at this production level, or None."""
    denom = doses_per_batch * (1 + U_m / 100.0) * eta_m
    if denom <= 0:
        return None
    b_min = max(1, math.ceil(target_patients / denom))
    if b_min > max_batches:
        return None
    return b_min


def mrt_room_combinations(target_patients, current_injection_rooms,
                           current_uptake_rooms, patients_per_dedicated_room,
                           max_additional_dedicated, max_mrt_rooms,
                           patients_per_mrt_room):
    """
    Section 9: enumerate (R_a, R_m) combinations that satisfy BOTH injection
    and uptake capacity, using the minimum R_m for each R_a (R_m is the
    cheaper lever -- no dedicated-room construction cost -- so minimizing it
    for a given R_a is always cost optimal; increasing it further can only
    hurt CapEx/OpEx). Returns a list of (R_a, R_m) feasible pairs.
    """
    r0_min = min(current_injection_rooms, current_uptake_rooms)
    combos = []
    for r_a in range(0, int(max_additional_dedicated) + 1):
        base = (r0_min + r_a) * patients_per_dedicated_room
        needed = target_patients - base
        if needed <= 0:
            r_m = 0
        else:
            if patients_per_mrt_room <= 0:
                continue
            r_m = math.ceil(needed / patients_per_mrt_room)
        if r_m <= max_mrt_rooms:
            combos.append((r_a, r_m))
    return combos


@dataclass
class MRTResult:
    feasible: bool
    infeasible_reasons: list = field(default_factory=list)
    diagnostic_best_served: float = None
    diagnostic_binding_constraint: str = None
    U_m: float = 0.0
    eta_m: float = 0.0
    B_m: int = 0
    R_a: int = 0
    R_m: int = 0
    dose_capacity: float = 0.0
    scanner: dict = field(default_factory=dict)
    injection_capacity: float = 0.0
    uptake_capacity: float = 0.0
    installed_capacity: float = 0.0
    served_patients: float = 0.0
    n_endpoints: int = 0
    capex: float = 0.0
    opex: float = 0.0
    revenue: float = 0.0
    ncf: float = 0.0
    npv: float = 0.0
    roi: float = 0.0
    payback: float = None


def _mrt_config_financials(inp: Inputs, U_m, B_m, R_a, R_m, eta_m, scanner,
                            served):
    injection_capacity = (min(inp.current_injection_rooms, inp.current_uptake_rooms) + R_a) \
        * inp.patients_per_dedicated_room + R_m * inp.patients_per_mrt_inpatient_room
    # (see mrt_room_combinations: this equals capacity at the binding side)

    n_endpoints = (
        inp.current_injection_rooms + inp.current_uptake_rooms
        + R_a + R_a + R_m
        + scanner["total_scanners"]
        + inp.supporting_mrt_destinations
    )

    capex = (
        (U_m / 10.0) * inp.capex_mrt_upgrade_per_10pct
        + scanner["additional_scanners"] * inp.capex_per_scanner
        + (R_a + R_a) * inp.capex_per_dedicated_room
        + inp.capex_mrt_core
        + n_endpoints * inp.capex_per_endpoint
    )

    opex = (
        inp.opex_base_mrt
        + inp.opex_mrt_maintenance
        + scanner["additional_scanners"] * inp.opex_per_additional_scanner
        + (R_a + R_a) * inp.opex_per_additional_dedicated_room
        + n_endpoints * inp.opex_per_endpoint
        + (B_m - 1) * inp.annual_cost_per_extra_daily_batch
    )

    incremental_patients = max(0.0, served - inp.current_patients)
    revenue = incremental_patients * inp.operating_days_per_year * inp.net_contribution_per_patient
    ncf = revenue - opex

    npv = -capex
    for y in range(1, inp.analysis_period_years + 1):
        npv += ncf / ((1 + inp.discount_rate) ** y)

    roi = ((ncf * inp.analysis_period_years - capex) / capex * 100.0) if capex > 0 else 0.0
    payback = (capex / ncf) if ncf > 0 else None

    return {
        "n_endpoints": n_endpoints, "capex": capex, "opex": opex,
        "revenue": revenue, "ncf": ncf, "npv": npv, "roi": roi,
        "payback": payback,
    }


def compute_mrt(inp: Inputs, U_c: float) -> MRTResult:
    eta_m = retained_fraction(inp.mrt_delivery_time, inp.isotope_half_life)

    scanner = scanner_requirement(
        inp.target_patients, inp.current_scanners, inp.operating_hours,
        inp.scanner_cycle_min, inp.scanner_availability,
    )
    scanner_feasible = scanner["total_capacity"] >= inp.target_patients

    room_combos = mrt_room_combinations(
        inp.target_patients, inp.current_injection_rooms, inp.current_uptake_rooms,
        inp.patients_per_dedicated_room, inp.max_additional_mrt_dedicated_rooms,
        inp.max_mrt_inpatient_rooms, inp.patients_per_mrt_inpatient_room,
    )
    rooms_feasible = len(room_combos) > 0

    # ---------------- Stage 1: minimize U_m ----------------
    increment = inp.production_search_increment
    U_m_min = None
    B_m_at_min = None
    steps = int(math.floor(U_c / increment)) + 1 if U_c >= 0 else 0
    for i in range(steps + 1):
        U_m_candidate = min(i * increment, U_c)
        b_min = mrt_min_batches(inp.target_patients, inp.current_doses_per_batch,
                                 U_m_candidate, eta_m, inp.max_mrt_batches_per_day)
        dose_feasible = b_min is not None
        if dose_feasible and rooms_feasible and scanner_feasible:
            U_m_min = U_m_candidate
            B_m_at_min = b_min
            break
        if U_m_candidate >= U_c:
            break

    if U_m_min is None:
        # ---------- infeasible: build diagnostics at the most generous
        # allowable settings (U_m = U_c, max batches, max rooms) ----------
        reasons = []
        b_at_uc = mrt_min_batches(inp.target_patients, inp.current_doses_per_batch,
                                   U_c, eta_m, inp.max_mrt_batches_per_day)
        if b_at_uc is None:
            b_used = inp.max_mrt_batches_per_day
            reasons.append("Insufficient usable dose capacity (max batches too low).")
        else:
            b_used = b_at_uc
        dose_cap = b_used * inp.current_doses_per_batch * (1 + U_c / 100.0) * eta_m

        if not scanner_feasible:
            reasons.append("Insufficient scanner capacity.")
        if not rooms_feasible:
            reasons.append("Maximum MRT inpatient rooms / additional dedicated "
                            "rooms too low to reach target.")

        best_ra, best_rm = (inp.max_additional_mrt_dedicated_rooms,
                             inp.max_mrt_inpatient_rooms)
        r0_min = min(inp.current_injection_rooms, inp.current_uptake_rooms)
        best_room_capacity = (r0_min + best_ra) * inp.patients_per_dedicated_room \
            + best_rm * inp.patients_per_mrt_inpatient_room

        best_installed = min(dose_cap, scanner["total_capacity"], best_room_capacity)
        binding = min(
            [("dose capacity", dose_cap), ("scanner capacity", scanner["total_capacity"]),
             ("injection/uptake room capacity", best_room_capacity)],
            key=lambda t: t[1],
        )[0]
        served_diag = min(best_installed, inp.target_patients)
        fin = _mrt_config_financials(inp, U_c, b_used, best_ra, best_rm, eta_m,
                                      scanner, served_diag)

        return MRTResult(
            feasible=False,
            infeasible_reasons=reasons or ["Best configuration does not reach target."],
            diagnostic_best_served=served_diag,
            diagnostic_binding_constraint=binding,
            U_m=U_c, eta_m=eta_m, B_m=b_used, R_a=best_ra, R_m=best_rm,
            dose_capacity=dose_cap, scanner=scanner,
            installed_capacity=best_installed,
            served_patients=served_diag,
            n_endpoints=fin["n_endpoints"], capex=fin["capex"], opex=fin["opex"],
            revenue=fin["revenue"], ncf=fin["ncf"], npv=fin["npv"], roi=fin["roi"],
            payback=fin["payback"],
        )

    # ---------------- Stage 2: maximize NPV at U_m_min ----------------
    dose_capacity = B_m_at_min * inp.current_doses_per_batch * (1 + U_m_min / 100.0) * eta_m

    candidates = []
    for (r_a, r_m) in room_combos:
        r0_min = min(inp.current_injection_rooms, inp.current_uptake_rooms)
        room_capacity = (r0_min + r_a) * inp.patients_per_dedicated_room \
            + r_m * inp.patients_per_mrt_inpatient_room
        installed = min(dose_capacity, scanner["total_capacity"], room_capacity)
        served = min(installed, inp.target_patients)
        if served < inp.target_patients:
            continue
        fin = _mrt_config_financials(inp, U_m_min, B_m_at_min, r_a, r_m, eta_m,
                                      scanner, served)
        capex = fin["capex"]
        if capex > inp.max_capex_budget:
            continue
        if fin["ncf"] <= 0 or fin["npv"] <= 0:
            continue
        candidates.append({
            "R_a": r_a, "R_m": r_m, "installed": installed, "served": served,
            "room_capacity": room_capacity, **fin,
        })

    if not candidates:
        # Feasible on capacity, but every combo violates budget/NPV/NCF.
        reasons = []
        # Report the cheapest combo (min rooms) for diagnostics.
        r_a, r_m = min(room_combos, key=lambda c: c[0] + c[1])
        r0_min = min(inp.current_injection_rooms, inp.current_uptake_rooms)
        room_capacity = (r0_min + r_a) * inp.patients_per_dedicated_room \
            + r_m * inp.patients_per_mrt_inpatient_room
        installed = min(dose_capacity, scanner["total_capacity"], room_capacity)
        served = min(installed, inp.target_patients)
        fin = _mrt_config_financials(inp, U_m_min, B_m_at_min, r_a, r_m, eta_m,
                                      scanner, served)
        if fin["capex"] > inp.max_capex_budget:
            reasons.append(f"CapEx exceeds budget by "
                            f"${fin['capex'] - inp.max_capex_budget:,.0f}.")
        if fin["ncf"] <= 0:
            reasons.append("Annual net cash flow is negative or zero.")
        if fin["npv"] <= 0:
            reasons.append("NPV is negative or zero.")
        return MRTResult(
            feasible=False,
            infeasible_reasons=reasons or ["No configuration satisfies budget/NPV constraints."],
            diagnostic_best_served=served,
            diagnostic_binding_constraint="budget / financial return",
            U_m=U_m_min, eta_m=eta_m, B_m=B_m_at_min, R_a=r_a, R_m=r_m,
            dose_capacity=dose_capacity, scanner=scanner,
            installed_capacity=installed, served_patients=served,
            n_endpoints=fin["n_endpoints"], capex=fin["capex"], opex=fin["opex"],
            revenue=fin["revenue"], ncf=fin["ncf"], npv=fin["npv"], roi=fin["roi"],
            payback=fin["payback"],
        )

    # Lexicographic selection: highest NPV, then lower CapEx, then lower
    # OpEx, then fewer new dedicated rooms (Section 5 / Section 30 rules).
    best = sorted(
        candidates,
        key=lambda c: (-c["npv"], c["capex"], c["opex"], c["R_a"] + c["R_m"]),
    )[0]

    return MRTResult(
        feasible=True,
        U_m=U_m_min, eta_m=eta_m, B_m=B_m_at_min, R_a=best["R_a"], R_m=best["R_m"],
        dose_capacity=dose_capacity, scanner=scanner,
        injection_capacity=best["room_capacity"], uptake_capacity=best["room_capacity"],
        installed_capacity=best["installed"], served_patients=best["served"],
        n_endpoints=best["n_endpoints"], capex=best["capex"], opex=best["opex"],
        revenue=best["revenue"], ncf=best["ncf"], npv=best["npv"], roi=best["roi"],
        payback=best["payback"],
    )


# --------------------------------------------------------------------------
# Top-level orchestration
# --------------------------------------------------------------------------

@dataclass
class ComparisonResult:
    conventional: ConventionalResult
    mrt: MRTResult
    winner: str   # "conventional" | "mrt" | "neither"


def run_comparison(inp: Inputs) -> ComparisonResult:
    conv = compute_conventional(inp)
    mrt = compute_mrt(inp, conv.U_c)

    if conv.feasible and mrt.feasible:
        winner = "mrt" if mrt.npv > conv.npv else "conventional"
    elif conv.feasible:
        winner = "conventional"
    elif mrt.feasible:
        winner = "mrt"
    else:
        winner = "neither"

    return ComparisonResult(conventional=conv, mrt=mrt, winner=winner)
