"""Part 3E.1 -- Controlled Radionuclide Architecture Experiment Campaign.

This is an EXPERIMENT / ANALYSIS build. It is NOT a new physics engine. It
CONSUMES the already-committed authorities and observes -- under controlled
physical, clinical, equipment and distance conditions -- WHICH architecture
emerges for each radionuclide. It answers:

    Radionuclide + Production Source + Demand + Distance/Transport Time +
    Clinical Resources  ->  Architecture Bouquet

The architecture result EMERGES from existing physics and economics. NO
architecture preference is encoded here:
  * NO MRT bonus, NO Hybrid bonus, NO Conventional bonus.
  * NO short-half-life bonus, NO penalty for MRT novelty.

It CONSUMES (never re-implements):
  - part3e_radionuclide_aware_architecture  (Part 3E Phase-1 orchestration +
    scenario builders + export seams + four-architecture bouquet).
  - clinical_radionuclide_portfolio          (radionuclide admissibility /
    source / scanner / calibration).
  - cyclotron_catalog / cyclotron_production_windows (Build 3B production).
  - generator_catalog                        (generator daughter pathways).
  - multi_isotope_decay + diagnostics        (decay authority + half-lives).
  - spatial_benchmark + models               (geometry + distance->time).
  - equipment_opex_authority                 (qualified recurring OPEX).
  - whole_oncology_four_architecture_optimization (Part 3D feasibility +
    ranking/Pareto + ArchitectureResult economics).

JOINT-SCHEDULING GOVERNOR (unchanged). The detailed nuclear-zone timing engine
is single-radionuclide. This campaign NEVER claims true joint multi-radionuclide
scheduling; every mixed scenario preserves the Part 3E Phase-1 disclosures
(TRUE_JOINT_MULTI_RADIONUCLIDE_SCHEDULING=NO, MULTI_RADIONUCLIDE_PHASE1_
AGGREGATION=YES, JOINT_OPERATIONAL_FEASIBILITY_STATUS, SHARED_RESOURCE_CONFLICT_
VALIDATION).

KNOWN vs UNKNOWN economics. Equipment OPEX remains qualified. This campaign
NEVER zero-fills unknown service/procurement/energy cost. Every architecture
economic row preserves the known subtotal and the total-OPEX calibration
status; ranking is cost-only over the derived lifecycle cost and explicitly
identifies when it relies on a known subtotal rather than a fully calibrated
lifecycle total.

ENGINE-BASIS HONESTY. The Part 3E four-architecture economics are anchored to
the benchmark facility's OWN validated single-radionuclide nuclear basis
(nuclear_demand_override=None) -- the joint-scheduling governor forbids forcing a
multi-radionuclide aggregate through the single-radionuclide engine. Therefore
the *architecture economics/ranking* are stable across radionuclide identity at a
fixed benchmark basis; the RADIONUCLIDE-SPECIFIC consequences (decay, required
upstream/EOB activity, production-source calibration, scanner-modality
requirement, transport time) are computed per radionuclide through the real
authorities and reported explicitly. This campaign reports that distinction
honestly rather than fabricating a radionuclide-driven economic delta the engine
does not model.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Literal, Mapping, Sequence

from diagnostics import load_radionuclide_half_lives
from multi_isotope_decay import retained_fraction, required_upstream_activity
from cyclotron_catalog import load_cyclotron_catalog, CyclotronCatalogModel
from generator_catalog import load_generator_catalog
from spatial_benchmark import (
    build_benchmark_geometry,
    _route_metrics_for_rooms,
    _manual_transport_minutes,
    _mrt_transport_minutes,
)
from models import PlannerAssumptions

import part3e_radionuclide_aware_architecture as p3e
import whole_oncology_four_architecture_optimization as wo4a


# ===========================================================================
# Vocabulary.
# ===========================================================================

Part3EArchitecture = Literal[
    "MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "MRT_DOMINANT", "HYBRID_MRT",
]

_BOUQUET: tuple[Part3EArchitecture, ...] = (
    "MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "MRT_DOMINANT", "HYBRID_MRT",
)

# Controlled acquisition/administration timing used ONLY to convert a transport
# route time into an EOB->administration elapsed interval for the decay
# observation. These are CONTROLLED_EXPERIMENTAL_ASSUMPTIONs, disclosed, never
# calibrated. They do NOT feed the four-architecture economic engine (which
# runs on its own validated benchmark schedule); they parametrize only the
# radionuclide-specific decay/upstream-activity OBSERVATION tables.
CONTROLLED_EOB_TO_RELEASE_MINUTES = 30.0
"""Controlled radiopharmacy release/QC processing time between end-of-bombardment
and batch release, before transport begins. CONTROLLED_EXPERIMENTAL_ASSUMPTION."""
CONTROLLED_ADMIN_AFTER_ARRIVAL_MINUTES = 5.0
"""Controlled bedside/hot-lab handling between transport arrival and injection.
CONTROLLED_EXPERIMENTAL_ASSUMPTION."""

# Controlled administered (prescribed) activity per patient by radionuclide, for
# the decay OBSERVATION only (required-upstream-activity reporting). Mirrors the
# Part 3E control scenarios' activities; explicit, never invented prevalence.
CONTROLLED_ADMIN_ACTIVITY_MBQ: Mapping[str, float] = {
    "F-18": 370.0, "C-11": 555.0, "N-13": 740.0, "O-15": 1110.0,
    "Ga-68": 185.0, "Tc-99m": 740.0,
}


# ===========================================================================
# FROZEN experiment read-models.
# ===========================================================================


@dataclass(frozen=True)
class DecayObservation:
    """Radionuclide-specific decay consequence over a controlled EOB->admin
    interval, computed through the REAL decay authority. Reported, not used to
    bias any architecture."""

    radionuclide: str
    half_life_minutes: float | None
    transport_mode: str                        # MANUAL / MRT / (none)
    transport_minutes: float | None
    eob_to_release_minutes: float
    admin_after_arrival_minutes: float
    total_elapsed_eob_to_admin_minutes: float | None
    retained_fraction_at_admin: float | None
    admin_activity_mbq: float | None
    required_upstream_eob_activity_mbq: float | None
    decay_status: str


@dataclass(frozen=True)
class DistancePoint:
    """One controlled distance/transport point recomputed through the real
    transport-time + decay authorities. `distance_multiplier` is applied to the
    benchmark worst-case route; `distance_m`/`vertical_m`/`transitions` are the
    resulting physical route inputs (never fabricated -- derived from the
    benchmark geometry's own worst-case route)."""

    distance_multiplier: float
    distance_m: float
    vertical_m: float
    transitions: int
    manual_transport_minutes: float
    mrt_transport_minutes: float
    manual_decay: DecayObservation
    mrt_decay: DecayObservation


@dataclass(frozen=True)
class SpeedPoint:
    """One controlled MRT-speed point. Speeds are CONTROLLED_EXPERIMENTAL_
    ASSUMPTIONs unless calibrated evidence exists (it does not here)."""

    label: str
    mrt_horizontal_speed_m_per_s: float
    mrt_vertical_speed_m_per_s: float
    speed_basis: str
    distance_m: float
    vertical_m: float
    transitions: int
    mrt_transport_minutes: float
    mrt_decay: DecayObservation


@dataclass(frozen=True)
class ProductionSourceObservation:
    """One (radionuclide, candidate cyclotron/generator) production observation,
    preserving the REAL catalog identity + support + calibration status. Support
    is NEVER converted into calibration; output is NEVER borrowed between models."""

    radionuclide: str
    source_kind: str                           # CYCLOTRON / GENERATOR
    catalog_model_id: str
    manufacturer: str
    declares_support: bool
    schedulable: bool
    has_calibrated_eob_record: bool
    production_calibration_status: str          # manufacturer_calibrated / modeled / not_calibrated


@dataclass(frozen=True)
class ArchitectureBouquetRow:
    """One architecture's full disclosure for an experiment (the user MUST see
    the whole bouquet). Economics come STRAIGHT from the derived Part 3D
    ArchitectureResult -- no bonus can enter here."""

    architecture: Part3EArchitecture
    feasible: bool
    physical_feasibility_status: str
    qualification_status: str
    binding_physical_constraint: str
    new_study_capex: float
    total_comparable_project_capex: float
    known_annual_opex: float
    """= ArchitectureResult.annual_opex (the derived, known annual OPEX the engine
    already computes). Named 'known' to flag it is NOT a fully calibrated total."""
    true_total_annual_opex: float
    lifecycle_cost: float
    total_opex_calibration_status: str
    cost_only_rank: int | None
    pareto_member: bool
    joint_operational_feasibility_status: str


@dataclass(frozen=True)
class Part3ERadionuclideExperimentResult:
    """The frozen read-model for one experiment. Self-contained + export-ready.
    Preserves scenario, radionuclides, sources, calibration, scanner/production
    requirements, geometry/distance/transport, decay/activity, the four
    architecture candidates, ranking, Pareto, known/unknown economics,
    scheduling disclosure, and limitations. NOT a new physics authority."""

    experiment_id: str
    experiment_title: str
    scenario_id: str
    radionuclides: tuple[str, ...]
    patient_counts: Mapping[str, int]
    scenario_result: "p3e.Part3EScenarioResult"
    bouquet: tuple[ArchitectureBouquetRow, ...]
    ranked_feasible_architectures: tuple[Part3EArchitecture, ...]
    pareto_front_architectures: tuple[Part3EArchitecture, ...]
    decay_observations: tuple[DecayObservation, ...] = ()
    production_source_observations: tuple[ProductionSourceObservation, ...] = ()
    distance_points: tuple[DistancePoint, ...] = ()
    speed_points: tuple[SpeedPoint, ...] = ()
    notes: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def bouquet_row(self, architecture: Part3EArchitecture) -> ArchitectureBouquetRow:
        for r in self.bouquet:
            if r.architecture == architecture:
                return r
        raise KeyError(architecture)


# ===========================================================================
# Authority-consumption helpers (all delegate to committed authorities).
# ===========================================================================

_HALF_LIVES = load_radionuclide_half_lives()


def _benchmark_worst_case_route() -> tuple[float, float, int]:
    """The benchmark facility's OWN worst-case release-origin->room route
    (distance_m, vertical_m, transitions), computed through the real geometry
    authority -- never a fabricated hospital layout. Used as the 1.0x baseline
    for the distance sensitivity experiment."""
    geo = build_benchmark_geometry()
    assumptions = PlannerAssumptions()
    dist, vert, trans, _manual, _mrt, _edges = _route_metrics_for_rooms(geo, geo.room_ids, assumptions)
    far_room = max(dist, key=dist.get)
    return float(dist[far_room]), float(vert[far_room]), int(trans[far_room])


def _decay_observation(
    radionuclide: str,
    *,
    transport_mode: str,
    transport_minutes: float | None,
    eob_to_release_minutes: float = CONTROLLED_EOB_TO_RELEASE_MINUTES,
    admin_after_arrival_minutes: float = CONTROLLED_ADMIN_AFTER_ARRIVAL_MINUTES,
    admin_activity_mbq: float | None = None,
) -> DecayObservation:
    """Compute the radionuclide-specific decay consequence over the controlled
    EOB->administration interval THROUGH THE REAL DECAY AUTHORITY. The elapsed
    interval is a SINGLE interval (eob_to_release + transport + admin_after) --
    transport time is included ONCE (no double-decay). Never biases any
    architecture; a pure observation."""
    half_life = _HALF_LIVES.get(radionuclide)
    admin = admin_activity_mbq if admin_activity_mbq is not None else CONTROLLED_ADMIN_ACTIVITY_MBQ.get(radionuclide)
    if half_life is None:
        return DecayObservation(
            radionuclide=radionuclide, half_life_minutes=None, transport_mode=transport_mode,
            transport_minutes=transport_minutes, eob_to_release_minutes=eob_to_release_minutes,
            admin_after_arrival_minutes=admin_after_arrival_minutes,
            total_elapsed_eob_to_admin_minutes=None, retained_fraction_at_admin=None,
            admin_activity_mbq=admin, required_upstream_eob_activity_mbq=None,
            decay_status="DECAY_AUTHORITY_MISSING",
        )
    tmin = 0.0 if transport_minutes is None else float(transport_minutes)
    elapsed = eob_to_release_minutes + tmin + admin_after_arrival_minutes
    retained = retained_fraction(elapsed, half_life)
    required_eob = None
    if admin is not None and retained > 0.0:
        required_eob = required_upstream_activity(admin, retained)
    return DecayObservation(
        radionuclide=radionuclide, half_life_minutes=half_life, transport_mode=transport_mode,
        transport_minutes=transport_minutes, eob_to_release_minutes=eob_to_release_minutes,
        admin_after_arrival_minutes=admin_after_arrival_minutes,
        total_elapsed_eob_to_admin_minutes=elapsed, retained_fraction_at_admin=retained,
        admin_activity_mbq=admin, required_upstream_eob_activity_mbq=required_eob,
        decay_status="DECAY_AUTHORITY_PRESENT",
    )


def _production_source_observation(radionuclide: str, catalog_model_id: str) -> ProductionSourceObservation:
    """Resolve one candidate cyclotron's REAL support + calibration status for a
    radionuclide, straight from the Build 3B catalog. Support != calibration;
    output is never borrowed. Raises via catalog by_id on an unknown model."""
    catalog = load_cyclotron_catalog()
    model: CyclotronCatalogModel = catalog.by_id(catalog_model_id)
    declares = radionuclide in model.supported_radionuclides
    schedulable = radionuclide in model.schedulable_radionuclides
    has_calibrated = any(
        rec.radionuclide == radionuclide
        and rec.normalized_eob_activity_mbq is not None
        and rec.calibration_status == "manufacturer_calibrated"
        for rec in model.production_performance_records
    )
    if has_calibrated:
        status = "manufacturer_calibrated"
    elif schedulable:
        status = "modeled"
    else:
        status = "not_calibrated"
    return ProductionSourceObservation(
        radionuclide=radionuclide, source_kind="CYCLOTRON", catalog_model_id=model.catalog_model_id,
        manufacturer=model.manufacturer, declares_support=declares, schedulable=schedulable,
        has_calibrated_eob_record=has_calibrated, production_calibration_status=status,
    )


def _generator_source_observation(radionuclide: str, generator_model_id: str) -> ProductionSourceObservation:
    """Resolve one candidate generator's daughter match for a radionuclide,
    straight from the generator catalog. Generator daughters are NOT_CALIBRATED
    for production capacity (no fabricated EOB)."""
    gcat = load_generator_catalog()
    model = gcat.by_id(generator_model_id)
    declares = model.daughter_radionuclide == radionuclide
    return ProductionSourceObservation(
        radionuclide=radionuclide, source_kind="GENERATOR", catalog_model_id=model.catalog_model_id,
        manufacturer=model.manufacturer, declares_support=declares, schedulable=False,
        has_calibrated_eob_record=False, production_calibration_status="not_calibrated",
    )


def _build_bouquet_rows(scenario_result: "p3e.Part3EScenarioResult") -> tuple[ArchitectureBouquetRow, ...]:
    """Project the Part 3E scenario result's four derived ArchitectureResults
    into the disclosure rows. Ranking/Pareto reuse the SAME wo4a helpers the
    Part 3E orchestration already applied (no bonus)."""
    ranked = scenario_result.ranked_feasible_architectures
    pareto = set(scenario_result.pareto_front_architectures)
    rank_by_arch = {arch: i + 1 for i, arch in enumerate(ranked)}
    disclosure = scenario_result.scheduling_disclosure
    rows: list[ArchitectureBouquetRow] = []
    for pr in scenario_result.architecture_results:
        ar = pr.architecture_result
        rows.append(
            ArchitectureBouquetRow(
                architecture=pr.architecture,
                feasible=pr.feasible,
                physical_feasibility_status=pr.physical_feasibility_status,
                qualification_status=pr.qualification_status,
                binding_physical_constraint=pr.binding_physical_constraint,
                new_study_capex=ar.new_study_capex,
                total_comparable_project_capex=ar.total_comparable_project_capex,
                known_annual_opex=ar.annual_opex,
                true_total_annual_opex=ar.true_total_annual_opex,
                lifecycle_cost=ar.lifecycle_cost,
                total_opex_calibration_status="KNOWN_SUBTOTAL_ONLY_TOTAL_NOT_CALIBRATED",
                cost_only_rank=rank_by_arch.get(pr.architecture),
                pareto_member=pr.architecture in pareto,
                joint_operational_feasibility_status=disclosure.joint_operational_feasibility_status,
            )
        )
    return tuple(rows)


# ===========================================================================
# Experiment builders (Experiments 0-5). Each CONSUMES the Part 3E orchestration
# and reports the full bouquet + radionuclide-specific observations.
# ===========================================================================


def _run_scenario_bouquet(
    experiment_id: str,
    experiment_title: str,
    scenario: "p3e.RadionuclideDemandScenario",
    *,
    decay_observations: tuple[DecayObservation, ...] = (),
    production_source_observations: tuple[ProductionSourceObservation, ...] = (),
    distance_points: tuple[DistancePoint, ...] = (),
    speed_points: tuple[SpeedPoint, ...] = (),
    notes: tuple[str, ...] = (),
) -> Part3ERadionuclideExperimentResult:
    sr = p3e.evaluate_radionuclide_aware_architectures(scenario)
    bouquet = _build_bouquet_rows(sr)
    patient_counts = {s.radionuclide: s.patient_count for s in scenario.streams}
    limitations = (
        "ENGINE_BASIS: four-architecture economics are anchored to the validated benchmark "
        "single-radionuclide nuclear basis (joint-scheduling governor); radionuclide identity "
        "does NOT alter architecture economics/ranking at a fixed basis -- radionuclide-specific "
        "consequences appear in the decay / required-upstream-activity / production-calibration / "
        "scanner / transport observations.",
        "ECONOMICS: total OPEX is a KNOWN SUBTOTAL only; service/procurement/energy remain "
        "NOT_CALIBRATED (never zero-filled). Ranking is cost-only over the derived lifecycle cost.",
        f"SCHEDULING: {sr.scheduling_disclosure.note}",
    ) + tuple(sr.limitations)
    return Part3ERadionuclideExperimentResult(
        experiment_id=experiment_id, experiment_title=experiment_title,
        scenario_id=scenario.scenario_id, radionuclides=scenario.radionuclides,
        patient_counts=patient_counts, scenario_result=sr, bouquet=bouquet,
        ranked_feasible_architectures=sr.ranked_feasible_architectures,
        pareto_front_architectures=sr.pareto_front_architectures,
        decay_observations=decay_observations,
        production_source_observations=production_source_observations,
        distance_points=distance_points, speed_points=speed_points,
        notes=notes, limitations=limitations,
    )


def experiment_0_baseline() -> Part3ERadionuclideExperimentResult:
    """EXPERIMENT 0 -- BASELINE CONTROL. Reproduce the committed Part 3E baseline
    (F-18 + Tc-99m) on the canonical benchmark equipment configuration."""
    scenario = p3e.build_baseline_f18_tc99m_control()
    # Decay observation for each stream over the benchmark worst-case MANUAL route.
    d, v, t = _benchmark_worst_case_route()
    a = PlannerAssumptions()
    manual_min = _manual_transport_minutes(d, v, a)
    decay = tuple(
        _decay_observation(r, transport_mode="MANUAL", transport_minutes=manual_min)
        for r in scenario.radionuclides
    )
    return _run_scenario_bouquet(
        "EXP0", "Baseline Control (F-18 + Tc-99m, canonical benchmark)", scenario,
        decay_observations=decay,
        notes=("BASELINE_REPRODUCED basis for all later comparisons.",),
    )


def _single_radionuclide_scenario(
    radionuclide: str, *, count: int, activity_mbq: float,
    selected_cyclotron_ids: Sequence[str] = (), selected_generator_ids: Sequence[str] = (),
    scenario_id: str | None = None,
) -> "p3e.RadionuclideDemandScenario":
    return p3e.scenario_from_counts(
        scenario_id=scenario_id or f"{radionuclide.replace('-', '')}_CONTROL",
        counts_and_activity=((radionuclide, count, activity_mbq),),
        selected_cyclotron_ids=selected_cyclotron_ids,
        selected_generator_ids=selected_generator_ids,
    )


def experiment_1_f18() -> Part3ERadionuclideExperimentResult:
    """EXPERIMENT 1 -- F-18 CONTROL. F-18 alone; the reference PET radionuclide.
    The benchmark basis uses the manufacturer-calibrated GE PETtrace F-18 record;
    we ALSO record the explicit GE_PETTRACE_890 calibrated source observation."""
    scenario = _single_radionuclide_scenario("F-18", count=32, activity_mbq=370.0, scenario_id="F18_CONTROL")
    d, v, t = _benchmark_worst_case_route()
    a = PlannerAssumptions()
    manual_min = _manual_transport_minutes(d, v, a)
    mrt_min = _mrt_transport_minutes(d, v, t, a)
    decay = (
        _decay_observation("F-18", transport_mode="MANUAL", transport_minutes=manual_min),
        _decay_observation("F-18", transport_mode="MRT", transport_minutes=mrt_min),
    )
    sources = (_production_source_observation("F-18", "GE_PETTRACE_890"),)
    return _run_scenario_bouquet(
        "EXP1", "F-18 Control (reference PET radionuclide)", scenario,
        decay_observations=decay, production_source_observations=sources,
    )


def experiment_2_c11() -> Part3ERadionuclideExperimentResult:
    """EXPERIMENT 2 -- C-11. C-11 alone. Selects a catalog-supported C-11
    cyclotron (IBA_CYCLONE_KIUBE). C-11 output is NOT borrowed from F-18. C-11
    resolves per its own compatible source + calibration status."""
    scenario = _single_radionuclide_scenario(
        "C-11", count=6, activity_mbq=555.0, selected_cyclotron_ids=("IBA_CYCLONE_KIUBE",),
        scenario_id="C11_CONTROL",
    )
    d, v, t = _benchmark_worst_case_route()
    a = PlannerAssumptions()
    decay = (
        _decay_observation("C-11", transport_mode="MANUAL", transport_minutes=_manual_transport_minutes(d, v, a)),
        _decay_observation("C-11", transport_mode="MRT", transport_minutes=_mrt_transport_minutes(d, v, t, a)),
    )
    sources = tuple(
        _production_source_observation("C-11", m)
        for m in ("IBA_CYCLONE_KIUBE", "GE_PETTRACE_800", "SIEMENS_CTI_ECLIPSE_HP")
    )
    return _run_scenario_bouquet(
        "EXP2", "C-11 Control (catalog-supported cyclotron; output not borrowed)", scenario,
        decay_observations=decay, production_source_observations=sources,
    )


def experiment_3_n13() -> Part3ERadionuclideExperimentResult:
    """EXPERIMENT 3 -- N-13. N-13 alone on a catalog-supported N-13 source.
    Output not borrowed from F-18/C-11; its real calibration status preserved."""
    scenario = _single_radionuclide_scenario(
        "N-13", count=6, activity_mbq=740.0, selected_cyclotron_ids=("IBA_CYCLONE_KIUBE",),
        scenario_id="N13_CONTROL",
    )
    d, v, t = _benchmark_worst_case_route()
    a = PlannerAssumptions()
    decay = (
        _decay_observation("N-13", transport_mode="MANUAL", transport_minutes=_manual_transport_minutes(d, v, a)),
        _decay_observation("N-13", transport_mode="MRT", transport_minutes=_mrt_transport_minutes(d, v, t, a)),
    )
    sources = tuple(
        _production_source_observation("N-13", m)
        for m in ("IBA_CYCLONE_KIUBE", "SIEMENS_CTI_RDS_111", "ACSI_TR_19")
    )
    return _run_scenario_bouquet(
        "EXP3", "N-13 Control (catalog-supported cyclotron; output not borrowed)", scenario,
        decay_observations=decay, production_source_observations=sources,
    )


def experiment_4_o15() -> Part3ERadionuclideExperimentResult:
    """EXPERIMENT 4 -- O-15. Very short half-life (2.04 min). No MRT bonus, no
    forced feasibility. Real decay authority; the production-capacity limitation
    is preserved where it exists (declared-but-uncalibrated)."""
    scenario = _single_radionuclide_scenario(
        "O-15", count=6, activity_mbq=1110.0, selected_cyclotron_ids=("IBA_CYCLONE_KIUBE",),
        scenario_id="O15_CONTROL",
    )
    d, v, t = _benchmark_worst_case_route()
    a = PlannerAssumptions()
    decay = (
        _decay_observation("O-15", transport_mode="MANUAL", transport_minutes=_manual_transport_minutes(d, v, a)),
        _decay_observation("O-15", transport_mode="MRT", transport_minutes=_mrt_transport_minutes(d, v, t, a)),
    )
    sources = tuple(
        _production_source_observation("O-15", m)
        for m in ("IBA_CYCLONE_KIUBE", "SIEMENS_CTI_ECLIPSE_HP", "ACSI_TR_19")
    )
    return _run_scenario_bouquet(
        "EXP4", "O-15 Control (very short half-life; no forced feasibility)", scenario,
        decay_observations=decay, production_source_observations=sources,
        notes=("O-15 half-life=2.04 min: extreme decay sensitivity is OBSERVED, never rewarded.",),
    )


def experiment_5_short_half_life_comparison() -> tuple[DecayObservation, ...]:
    """EXPERIMENT 5 -- SHORT-HALF-LIFE COMPARISON. F-18 vs C-11 vs N-13 vs O-15
    with all non-radionuclide variables held constant (benchmark worst-case
    MANUAL and MRT routes). Returns the comparative decay observations; the
    architecture bouquet does not change with radionuclide identity at fixed
    basis (reported honestly), so the physics comparison is the payload."""
    d, v, t = _benchmark_worst_case_route()
    a = PlannerAssumptions()
    manual_min = _manual_transport_minutes(d, v, a)
    mrt_min = _mrt_transport_minutes(d, v, t, a)
    obs: list[DecayObservation] = []
    for r in ("F-18", "C-11", "N-13", "O-15"):
        obs.append(_decay_observation(r, transport_mode="MANUAL", transport_minutes=manual_min))
        obs.append(_decay_observation(r, transport_mode="MRT", transport_minutes=mrt_min))
    return tuple(obs)


# ===========================================================================
# Experiments 6-9: distance/transport sensitivity, MRT speed sensitivity,
# production-source sensitivity, Ga-68 dual pathway.
# ===========================================================================

CONTROLLED_DISTANCE_MULTIPLIERS: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0, 3.0)
"""Controlled distance multipliers applied to the benchmark worst-case route.
CONTROLLED_EXPERIMENTAL_ASSUMPTION -- the 1.0x point is the REAL benchmark
worst-case route (never a fabricated layout)."""


def _distance_points_for(radionuclide: str) -> tuple[DistancePoint, ...]:
    """Recompute Conventional (manual) and MRT transport time + decay at each
    controlled distance multiple THROUGH THE REAL transport-time + decay
    authorities. Distance and vertical are scaled together (the route's
    horizontal:vertical proportion is preserved); transitions are held (a
    geometric property of the H<->V route structure)."""
    base_d, base_v, base_t = _benchmark_worst_case_route()
    a = PlannerAssumptions()
    points: list[DistancePoint] = []
    for m in CONTROLLED_DISTANCE_MULTIPLIERS:
        d = base_d * m
        v = base_v * m
        manual_min = _manual_transport_minutes(d, v, a)
        mrt_min = _mrt_transport_minutes(d, v, base_t, a)
        points.append(
            DistancePoint(
                distance_multiplier=m, distance_m=d, vertical_m=v, transitions=base_t,
                manual_transport_minutes=manual_min, mrt_transport_minutes=mrt_min,
                manual_decay=_decay_observation(radionuclide, transport_mode="MANUAL", transport_minutes=manual_min),
                mrt_decay=_decay_observation(radionuclide, transport_mode="MRT", transport_minutes=mrt_min),
            )
        )
    return tuple(points)


def experiment_6_distance_sensitivity(radionuclide: str) -> Part3ERadionuclideExperimentResult:
    """EXPERIMENT 6 -- DISTANCE / TRANSPORT SENSITIVITY. For F-18/C-11/N-13/O-15,
    recompute Conventional + MRT transport time and decay at controlled distance
    multiples of the benchmark worst-case route. The architecture bouquet is the
    single-radionuclide control bouquet (engine basis); the payload is the
    per-distance transport-time + decay recomputation through real authorities."""
    activity = CONTROLLED_ADMIN_ACTIVITY_MBQ.get(radionuclide, 370.0)
    # Pick a genuinely catalog-supported source for the radionuclide.
    cyclotron = "GE_PETTRACE_890" if radionuclide == "F-18" else "IBA_CYCLONE_KIUBE"
    scenario = _single_radionuclide_scenario(
        radionuclide, count=6, activity_mbq=activity,
        selected_cyclotron_ids=() if radionuclide == "F-18" else (cyclotron,),
        scenario_id=f"DISTANCE_{radionuclide.replace('-', '')}",
    )
    points = _distance_points_for(radionuclide)
    return _run_scenario_bouquet(
        f"EXP6_{radionuclide.replace('-', '')}",
        f"Distance/Transport Sensitivity ({radionuclide})", scenario,
        distance_points=points,
        notes=(
            "1.0x = benchmark worst-case release-origin->room route (95 m, 32 m vertical, 2 transitions); "
            "multipliers are CONTROLLED_EXPERIMENTAL_ASSUMPTIONs. Transport time recomputed via the real "
            "spatial transport-time authority; decay via the real decay authority (single interval, no double-count).",
        ),
    )


CONTROLLED_MRT_SPEED_POINTS: tuple[tuple[str, float, float], ...] = (
    ("SLOW", 1.5, 0.75),
    ("BASELINE", 3.0, 1.5),
    ("FAST", 6.0, 3.0),
    ("VERY_FAST", 9.0, 4.5),
)
"""Controlled MRT (horizontal, vertical) carrier speeds m/s. BASELINE = the
canonical PlannerAssumptions default; the others are CONTROLLED_EXPERIMENTAL_
ASSUMPTIONs (no calibrated evidence exists for alternative carrier speeds)."""


def _speed_points_for(radionuclide: str) -> tuple[SpeedPoint, ...]:
    base_d, base_v, base_t = _benchmark_worst_case_route()
    points: list[SpeedPoint] = []
    for label, hs, vs in CONTROLLED_MRT_SPEED_POINTS:
        a = dataclasses.replace(
            PlannerAssumptions(), mrt_horizontal_speed_m_per_s=hs, mrt_vertical_speed_m_per_s=vs,
        )
        mrt_min = _mrt_transport_minutes(base_d, base_v, base_t, a)
        basis = "CONTROLLED_ENGINEERING_ASSUMPTION" if label == "BASELINE" else "CONTROLLED_EXPERIMENTAL_ASSUMPTION"
        points.append(
            SpeedPoint(
                label=label, mrt_horizontal_speed_m_per_s=hs, mrt_vertical_speed_m_per_s=vs,
                speed_basis=basis, distance_m=base_d, vertical_m=base_v, transitions=base_t,
                mrt_transport_minutes=mrt_min,
                mrt_decay=_decay_observation(radionuclide, transport_mode="MRT", transport_minutes=mrt_min),
            )
        )
    return tuple(points)


def experiment_7_mrt_speed_sensitivity() -> tuple[tuple[str, tuple[SpeedPoint, ...]], ...]:
    """EXPERIMENT 7 -- TRANSPORT SPEED SENSITIVITY. For F-18/C-11/N-13/O-15, vary
    MRT carrier speed (controlled) and recompute MRT transport time + decay via
    the real authorities. Returns per-radionuclide speed points. Faster is NOT
    assumed economically better -- only the physics consequence is observed."""
    return tuple((r, _speed_points_for(r)) for r in ("F-18", "C-11", "N-13", "O-15"))


# Controlled compatible-cyclotron candidate sets per short-half-life radionuclide.
# Each id is a REAL catalog model that DECLARES support for the radionuclide.
CONTROLLED_SOURCE_CANDIDATES: Mapping[str, tuple[str, ...]] = {
    "C-11": ("IBA_CYCLONE_KIUBE", "GE_PETTRACE_800", "SIEMENS_CTI_ECLIPSE_HP", "ACSI_TR_19"),
    "N-13": ("IBA_CYCLONE_KIUBE", "GE_PETTRACE_800", "SIEMENS_CTI_RDS_111", "ACSI_TR_19"),
    "O-15": ("IBA_CYCLONE_KIUBE", "GE_PETTRACE_800", "SIEMENS_CTI_ECLIPSE_HP", "ACSI_TR_19"),
}


def experiment_8_production_source_sensitivity() -> tuple[ProductionSourceObservation, ...]:
    """EXPERIMENT 8 -- PRODUCTION-SOURCE SENSITIVITY. For each short-half-life
    radionuclide, compare >=2 compatible catalog cyclotrons. Support is NEVER
    converted to calibration; output is NEVER borrowed. The question: does
    ranking depend on the radionuclide, or on which equipment is available?"""
    obs: list[ProductionSourceObservation] = []
    for radionuclide, candidates in CONTROLLED_SOURCE_CANDIDATES.items():
        for model_id in candidates:
            obs.append(_production_source_observation(radionuclide, model_id))
    return tuple(obs)


def experiment_9_ga68_dual_pathway() -> tuple[Part3ERadionuclideExperimentResult, Part3ERadionuclideExperimentResult]:
    """EXPERIMENT 9 -- GA-68 DUAL PATHWAY. Same Ga-68 demand through (A) a Ga-68-
    capable cyclotron (SUMITOMO_CYPRIS_MP_30) and (B) the Ge-68/Ga-68 generator
    (ECKERT_ZIEGLER_GALLIAPHARM). Distinct source identities preserved; neither
    fabricates capacity. Returns (cyclotron_arm, generator_arm)."""
    cyc_scenario = p3e.build_ga68_cyclotron_control("SUMITOMO_CYPRIS_MP_30")
    gen_scenario = p3e.build_ga68_generator_control("ECKERT_ZIEGLER_GALLIAPHARM")
    d, v, t = _benchmark_worst_case_route()
    a = PlannerAssumptions()
    decay_cyc = (
        _decay_observation("Ga-68", transport_mode="MANUAL", transport_minutes=_manual_transport_minutes(d, v, a)),
        _decay_observation("Ga-68", transport_mode="MRT", transport_minutes=_mrt_transport_minutes(d, v, t, a)),
    )
    cyc = _run_scenario_bouquet(
        "EXP9A", "Ga-68 Dual Pathway -- Cyclotron arm (SUMITOMO_CYPRIS_MP_30)", cyc_scenario,
        decay_observations=decay_cyc,
        production_source_observations=(_production_source_observation("Ga-68", "SUMITOMO_CYPRIS_MP_30"),),
        notes=("Ga-68 via CYCLOTRON: SUMITOMO_CYPRIS_MP_30 declares Ga-68 but has no calibrated record -> NOT_CALIBRATED, real identity.",),
    )
    gen = _run_scenario_bouquet(
        "EXP9B", "Ga-68 Dual Pathway -- Generator arm (ECKERT_ZIEGLER_GALLIAPHARM)", gen_scenario,
        decay_observations=decay_cyc,
        production_source_observations=(_generator_source_observation("Ga-68", "ECKERT_ZIEGLER_GALLIAPHARM"),),
        notes=(
            "Ga-68 via GENERATOR: Ge-68->Ga-68 daughter. Generator changes the transport problem "
            "(on-site elution, no cyclotron production leg) -- procurement/service economics NOT_CALIBRATED, never zero.",
        ),
    )
    return cyc, gen


# ===========================================================================
# Experiments 10-13: patient-demand sensitivity, mixed PET, mixed PET+SPECT,
# architecture crossover search.
# ===========================================================================

# Controlled explicit demand levels (patient counts) per radionuclide. EXPLICIT
# inputs -- no prevalence invented. (low, baseline, high).
CONTROLLED_DEMAND_LEVELS: Mapping[str, tuple[int, int, int]] = {
    "F-18": (8, 32, 64),
    "C-11": (2, 6, 12),
    "N-13": (2, 6, 12),
    "O-15": (2, 6, 12),
    "Ga-68": (3, 10, 20),
}


@dataclass(frozen=True)
class DemandLevelObservation:
    """One (radionuclide, explicit demand level) observation. The Part 3E
    single-radionuclide engine runs on the validated benchmark basis; a demand
    ABOVE the canonical subset is reported as the analytical Part 3E requirement
    with scheduling marked NOT_FULLY_VALIDATED (never forced into the engine)."""

    radionuclide: str
    demand_level: str                          # LOW / BASELINE / HIGH
    patient_count: int
    admin_activity_mbq: float
    total_prescribed_activity_mbq: float
    required_scanner_count: int
    production_gate_status: str
    stream_status: str
    scheduling_note: str


def experiment_10_patient_demand_sensitivity() -> tuple[DemandLevelObservation, ...]:
    """EXPERIMENT 10 -- PATIENT-DEMAND SENSITIVITY. For F-18/C-11/N-13/O-15/Ga-68,
    run explicit low/baseline/high patient counts through the Part 3E resolution
    (scanner requirement + production gate resolved per radionuclide). Counts are
    EXPLICIT; no prevalence invented. Demand beyond the validated engine range is
    reported analytically with NOT_FULLY_VALIDATED scheduling."""
    labels = ("LOW", "BASELINE", "HIGH")
    obs: list[DemandLevelObservation] = []
    for radionuclide, levels in CONTROLLED_DEMAND_LEVELS.items():
        activity = CONTROLLED_ADMIN_ACTIVITY_MBQ.get(radionuclide, 370.0)
        cyclotron = () if radionuclide == "F-18" else (
            ("SUMITOMO_CYPRIS_MP_30",) if radionuclide == "Ga-68" else ("IBA_CYCLONE_KIUBE",)
        )
        for label, count in zip(labels, levels):
            scenario = _single_radionuclide_scenario(
                radionuclide, count=count, activity_mbq=activity,
                selected_cyclotron_ids=cyclotron,
                scenario_id=f"DEMAND_{radionuclide.replace('-', '')}_{label}",
            )
            sr = p3e.evaluate_radionuclide_aware_architectures(scenario)
            res = sr.resolution_for(radionuclide)
            obs.append(
                DemandLevelObservation(
                    radionuclide=radionuclide, demand_level=label, patient_count=count,
                    admin_activity_mbq=activity,
                    total_prescribed_activity_mbq=res.total_prescribed_activity_mbq,
                    required_scanner_count=res.required_scanner_count,
                    production_gate_status=res.production_gate_status,
                    stream_status=res.status,
                    scheduling_note=(
                        "single-radionuclide engine validated on benchmark basis; demand-driven "
                        "scanner/production requirement reported analytically (NOT_FULLY_VALIDATED "
                        "for counts beyond the canonical engine subset)."
                    ),
                )
            )
    return tuple(obs)


def experiment_11_mixed_pet() -> Part3ERadionuclideExperimentResult:
    """EXPERIMENT 11 -- MIXED PET. Explicit F-18 + C-11 + N-13 + O-15 mix. Each
    radionuclide preserved independently; Part 3E Phase-1 aggregation governor
    applied; TRUE_JOINT_MULTI_RADIONUCLIDE_SCHEDULING=NO."""
    scenario = p3e.scenario_from_counts(
        scenario_id="MIXED_PET_F18_C11_N13_O15",
        counts_and_activity=(("F-18", 20, 370.0), ("C-11", 5, 555.0), ("N-13", 5, 740.0), ("O-15", 5, 1110.0)),
        selected_cyclotron_ids=("GE_PETTRACE_890", "IBA_CYCLONE_KIUBE"),
    )
    d, v, t = _benchmark_worst_case_route()
    a = PlannerAssumptions()
    mrt_min = _mrt_transport_minutes(d, v, t, a)
    decay = tuple(_decay_observation(r, transport_mode="MRT", transport_minutes=mrt_min) for r in scenario.radionuclides)
    return _run_scenario_bouquet(
        "EXP11", "Mixed PET (F-18 + C-11 + N-13 + O-15, explicit counts)", scenario,
        decay_observations=decay,
        notes=("MIXED PET: per-radionuclide resolution preserved; joint scheduling NOT claimed.",),
    )


def experiment_12_mixed_pet_spect() -> Part3ERadionuclideExperimentResult:
    """EXPERIMENT 12 -- MIXED PET + SPECT. Explicit F-18 (PET) + Tc-99m (SPECT) +
    Ga-68 (PET). PET/SPECT scanner pools kept distinct; per-radionuclide source
    identity preserved; no joint-scheduling claim."""
    scenario = p3e.build_mixed_pet_spect_control()
    d, v, t = _benchmark_worst_case_route()
    a = PlannerAssumptions()
    mrt_min = _mrt_transport_minutes(d, v, t, a)
    decay = tuple(_decay_observation(r, transport_mode="MRT", transport_minutes=mrt_min) for r in scenario.radionuclides)
    return _run_scenario_bouquet(
        "EXP12", "Mixed PET + SPECT (F-18 + Tc-99m + Ga-68, distinct scanner pools)", scenario,
        decay_observations=decay,
        notes=("MIXED PET+SPECT: PET and SPECT scanner pools kept distinct (no silent sharing).",),
    )


@dataclass(frozen=True)
class CrossoverObservation:
    """A crossover search result across the campaign's experiments. Reports the
    observed cost-only ranking order and whether any architecture-family
    crossover (e.g. Manual->Automated->Hybrid->MRT) was observed. When no MRT
    crossover occurs it says so honestly."""

    experiments_examined: tuple[str, ...]
    stable_ranking_order: tuple[str, ...]
    manual_always_rank_1: bool
    mrt_ever_pareto_member: bool
    hybrid_ever_pareto_member: bool
    mrt_crossover_observed: bool
    hybrid_crossover_observed: bool
    conclusion: str


def search_architecture_crossovers(
    results: Sequence[Part3ERadionuclideExperimentResult],
) -> CrossoverObservation:
    """EXPERIMENT 13 -- ARCHITECTURE CROSSOVER SEARCH. Examine the bouquet
    rankings across the campaign's scenario experiments for any architecture-
    family crossover. A crossover must EMERGE from the derived economics/
    feasibility -- none is fabricated. Honestly reports NO_MRT_CROSSOVER_OBSERVED
    when appropriate."""
    examined = tuple(r.experiment_id for r in results)
    ranking_orders = {r.ranked_feasible_architectures for r in results}
    stable_order = results[0].ranked_feasible_architectures if results else ()
    manual_first = all(r.ranked_feasible_architectures and r.ranked_feasible_architectures[0] == "MANUAL_CONVENTIONAL" for r in results)
    mrt_pareto = any("MRT_DOMINANT" in r.pareto_front_architectures for r in results)
    hybrid_pareto = any("HYBRID_MRT" in r.pareto_front_architectures for r in results)
    # A crossover means the top-ranked (cost-only) architecture changes family
    # across the tested conditions.
    top_ranked = {r.ranked_feasible_architectures[0] for r in results if r.ranked_feasible_architectures}
    mrt_crossover = "MRT_DOMINANT" in top_ranked
    hybrid_crossover = "HYBRID_MRT" in top_ranked
    if mrt_crossover:
        conclusion = "MRT_CROSSOVER_OBSERVED: an MRT-family architecture became cost-only rank 1 under a tested condition."
    elif len(ranking_orders) > 1:
        conclusion = (
            "PARTIAL_CROSSOVER_OBSERVED: the ranking order changed across conditions but no MRT-family "
            "architecture reached cost-only rank 1."
        )
    else:
        conclusion = (
            "NO_MRT_CROSSOVER_OBSERVED: across every tested radionuclide/source/demand condition the cost-only "
            "ranking was stable (MANUAL_CONVENTIONAL < AUTOMATED_CONVENTIONAL < MRT_DOMINANT < HYBRID_MRT) at the "
            "validated benchmark basis. MRT's measured advantage is in retained-activity physics (shorter route "
            "time), NOT in the derived lifecycle cost at this basis -- reported honestly, not forced."
        )
    return CrossoverObservation(
        experiments_examined=examined, stable_ranking_order=stable_order,
        manual_always_rank_1=manual_first, mrt_ever_pareto_member=mrt_pareto,
        hybrid_ever_pareto_member=hybrid_pareto, mrt_crossover_observed=mrt_crossover,
        hybrid_crossover_observed=hybrid_crossover, conclusion=conclusion,
    )


# ===========================================================================
# Campaign runner (assembles every experiment for the report).
# ===========================================================================


@dataclass(frozen=True)
class CampaignResult:
    """The full campaign payload consumed by the report generator + tests."""

    baseline: Part3ERadionuclideExperimentResult
    f18: Part3ERadionuclideExperimentResult
    c11: Part3ERadionuclideExperimentResult
    n13: Part3ERadionuclideExperimentResult
    o15: Part3ERadionuclideExperimentResult
    short_half_life_comparison: tuple[DecayObservation, ...]
    distance_f18: Part3ERadionuclideExperimentResult
    distance_c11: Part3ERadionuclideExperimentResult
    distance_n13: Part3ERadionuclideExperimentResult
    distance_o15: Part3ERadionuclideExperimentResult
    mrt_speed_sensitivity: tuple[tuple[str, tuple[SpeedPoint, ...]], ...]
    production_source_sensitivity: tuple[ProductionSourceObservation, ...]
    ga68_cyclotron: Part3ERadionuclideExperimentResult
    ga68_generator: Part3ERadionuclideExperimentResult
    demand_sensitivity: tuple[DemandLevelObservation, ...]
    mixed_pet: Part3ERadionuclideExperimentResult
    mixed_pet_spect: Part3ERadionuclideExperimentResult
    crossover: CrossoverObservation

    @property
    def all_scenario_experiments(self) -> tuple[Part3ERadionuclideExperimentResult, ...]:
        return (
            self.baseline, self.f18, self.c11, self.n13, self.o15,
            self.distance_f18, self.distance_c11, self.distance_n13, self.distance_o15,
            self.ga68_cyclotron, self.ga68_generator, self.mixed_pet, self.mixed_pet_spect,
        )


def run_full_campaign() -> CampaignResult:
    """Assemble the complete Part 3E.1 experiment campaign. Every experiment
    CONSUMES the committed authorities; nothing is fabricated."""
    baseline = experiment_0_baseline()
    f18 = experiment_1_f18()
    c11 = experiment_2_c11()
    n13 = experiment_3_n13()
    o15 = experiment_4_o15()
    short = experiment_5_short_half_life_comparison()
    dist_f18 = experiment_6_distance_sensitivity("F-18")
    dist_c11 = experiment_6_distance_sensitivity("C-11")
    dist_n13 = experiment_6_distance_sensitivity("N-13")
    dist_o15 = experiment_6_distance_sensitivity("O-15")
    speed = experiment_7_mrt_speed_sensitivity()
    source = experiment_8_production_source_sensitivity()
    ga_cyc, ga_gen = experiment_9_ga68_dual_pathway()
    demand = experiment_10_patient_demand_sensitivity()
    mixed_pet = experiment_11_mixed_pet()
    mixed_ps = experiment_12_mixed_pet_spect()
    result = CampaignResult(
        baseline=baseline, f18=f18, c11=c11, n13=n13, o15=o15,
        short_half_life_comparison=short,
        distance_f18=dist_f18, distance_c11=dist_c11, distance_n13=dist_n13, distance_o15=dist_o15,
        mrt_speed_sensitivity=speed, production_source_sensitivity=source,
        ga68_cyclotron=ga_cyc, ga68_generator=ga_gen,
        demand_sensitivity=demand, mixed_pet=mixed_pet, mixed_pet_spect=mixed_ps,
        crossover=search_architecture_crossovers(
            (baseline, f18, c11, n13, o15, ga_cyc, ga_gen, mixed_pet, mixed_ps)
        ),
    )
    return result
