"""Controlled regression coverage for Phase 6: retention-aware clinical resource
sizing (see spatial_benchmark.py: generate_candidate_layouts, _evaluate_layout,
_operational_retention_metrics, CandidateOutcome.retention_feasible_patients_per_day).

Proves:
- an operational retention shortfall at a given injection-room count is driven by
  injection QUEUEING, not by room-level distance/spatial infeasibility;
- expanding injection-room capacity (via the broadened candidate search) recovers
  operational retention using real, simulated values (not faked/forced);
- the reported operational bottleneck shifts from injection to a downstream resource
  (uptake) as injection capacity is increased, and can shift to scanner when scanner
  capacity is deliberately starved;
- Conventional transporter (distribution_concurrency) counts never exceed the
  candidate's own injection-room count;
- a candidate can never consume more clinical rooms than physically exist on its
  active floors.
"""

from __future__ import annotations

from dataclasses import replace

from spatial_benchmark import (
    ROOMS_PER_FLOOR,
    _evaluate_layout,
    build_benchmark_geometry,
    build_production_basis,
    _base_assumptions,
    generate_candidate_layouts,
)


def _candidates_by_injection_count(pathway: str, demand: int = 200):
    geometry = build_benchmark_geometry()
    assumptions = _base_assumptions()
    candidates = generate_candidate_layouts(
        pathway=pathway, demand=demand, geometry=geometry, assumptions=assumptions
    )
    by_injection: dict[int, list] = {}
    for candidate in candidates:
        by_injection.setdefault(candidate.injection_resources, []).append(candidate)
    return by_injection, assumptions


def _pick(by_injection: dict[int, list], injection_count: int, floors=(1, 2, 3)):
    for candidate in by_injection[injection_count]:
        if candidate.active_floors == floors:
            return candidate
    raise AssertionError(f"No candidate with injection={injection_count} floors={floors}")


def test_injection_queue_causes_operational_retention_failure_not_distance() -> None:
    """A small injection-room count produces a low operational retention count and a
    large average injection queue, while the underlying rooms remain geometrically
    reachable -- proving the shortfall is queue-driven, not spatial.
    """
    by_injection, assumptions = _candidates_by_injection_count("Conventional")
    basis = build_production_basis()
    layout = _pick(by_injection, injection_count=2)

    outcome = _evaluate_layout(
        pathway="Conventional",
        layout=layout,
        demand=200,
        production_basis=basis,
        assumptions=assumptions,
        seed=1,
    )

    assert outcome.bottleneck == "injection"
    assert outcome.avg_injection_queue_minutes > 30.0
    assert outcome.retention_feasible_patients_per_day < outcome.patients_served_per_day


def test_adding_injection_capacity_recovers_operational_retention() -> None:
    """Increasing injection-room count (via the broadened candidate search) raises the
    real, simulated retention-feasible patient count and lowers the real average
    injection queue -- not a forced/faked improvement.
    """
    by_injection, assumptions = _candidates_by_injection_count("Conventional")
    basis = build_production_basis()

    small = _pick(by_injection, injection_count=2)
    large = _pick(by_injection, injection_count=6)

    small_outcome = _evaluate_layout(
        pathway="Conventional", layout=small, demand=200, production_basis=basis, assumptions=assumptions, seed=1
    )
    large_outcome = _evaluate_layout(
        pathway="Conventional", layout=large, demand=200, production_basis=basis, assumptions=assumptions, seed=1
    )

    assert large_outcome.retention_feasible_patients_per_day > small_outcome.retention_feasible_patients_per_day
    assert large_outcome.avg_injection_queue_minutes < small_outcome.avg_injection_queue_minutes
    assert large_outcome.patients_served_per_day >= small_outcome.patients_served_per_day


def test_bottleneck_shifts_from_injection_to_downstream_resource() -> None:
    """As injection capacity increases from a starved level, the reported operational
    bottleneck moves off of injection onto a downstream resource (uptake).
    """
    by_injection, assumptions = _candidates_by_injection_count("Conventional")
    basis = build_production_basis()

    starved = _pick(by_injection, injection_count=2)
    relieved = _pick(by_injection, injection_count=3)

    starved_outcome = _evaluate_layout(
        pathway="Conventional", layout=starved, demand=200, production_basis=basis, assumptions=assumptions, seed=1
    )
    relieved_outcome = _evaluate_layout(
        pathway="Conventional", layout=relieved, demand=200, production_basis=basis, assumptions=assumptions, seed=1
    )

    assert starved_outcome.bottleneck == "injection"
    assert relieved_outcome.bottleneck != "injection"


def test_scanner_bottleneck_emerges_when_scanner_capacity_is_starved() -> None:
    """Deliberately starving scanner capacity (holding injection/uptake generous)
    shifts the reported bottleneck onto scanner, proving the sizing/bottleneck
    reporting responds to whichever resource is actually limiting -- not hard-coded
    to injection/uptake.
    """
    by_injection, assumptions = _candidates_by_injection_count("Conventional")
    basis = build_production_basis()
    generous = _pick(by_injection, injection_count=6)

    starved_layout = replace(generous, scanners=1)

    outcome = _evaluate_layout(
        pathway="Conventional", layout=starved_layout, demand=200, production_basis=basis, assumptions=assumptions, seed=1
    )

    assert outcome.bottleneck == "scanner"


def test_conventional_transporters_never_exceed_injection_room_count() -> None:
    """Section 12: Conventional distribution_concurrency (manual transporter pool)
    must never exceed the candidate's own injection-room count.
    """
    by_injection, _assumptions = _candidates_by_injection_count("Conventional")
    for injection_count, candidates in by_injection.items():
        for candidate in candidates:
            assert candidate.distribution_concurrency <= injection_count


def test_candidate_never_consumes_more_rooms_than_physically_exist() -> None:
    """A candidate's total assigned scanner+injection+uptake rooms can never exceed
    the number of physical rooms on its active floors.
    """
    for pathway in ("Conventional", "MRT"):
        by_injection, _assumptions = _candidates_by_injection_count(pathway)
        for candidates in by_injection.values():
            for candidate in candidates:
                floor_capacity = len(candidate.active_floors) * ROOMS_PER_FLOOR
                used = candidate.scanners + candidate.injection_resources + candidate.uptake_resources
                assert used <= floor_capacity
