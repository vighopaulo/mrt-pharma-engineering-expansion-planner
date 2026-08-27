"""Capital Project API -- narrow FastAPI adapter over the existing MRT Pharma
engineering engine.

GOVERNANCE (Capital Project UI Build 2, section 9): this module is an
ADAPTER ONLY. It never independently computes radioactive activity,
production capacity, room/scanner requirements, CapEx, OPEX, NPV, ROI, or
payback -- every number in a response is copied verbatim from an existing
authoritative Python result object
(`equal_budget.EqualBudgetMultiBatchResult`/`MultiBatchPathwayResult`,
themselves built from `models.PlannerInputs`/`PlannerAssumptions` and
`cyclotron_catalog`). It never imports NVIDIA/Omniverse, never touches
Bentley/OpenUSD/trajectory state, and never creates a second optimizer or
economics engine.

CONTROLLED DEMO INPUT (section 13): `_DEMO_PROJECT_ID` is a synthetic,
clearly-labeled project INPUT descriptor (current/target capacity, a
starting budget) -- never a fabricated engineering OUTPUT. It enters the
exact same engine path (`run_equal_budget_multibatch_optimization`) a real
customer project would.
"""

from __future__ import annotations

import json
import math
import os
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import cyclotron_catalog as cc
import equal_budget as eb
import finance
from models import PlannerAssumptions, PlannerInputs

app = FastAPI(title="MRT Pharma Engine API", version="1.0.0")

# Local-development-only CORS: explicit Vite dev server origins, never "*".
# Revisit before any hosted/production deployment.
_DEV_ORIGINS = [
    "http://localhost:5173", "http://127.0.0.1:5173",
    "http://localhost:5174", "http://127.0.0.1:5174",
    "http://localhost:5175", "http://127.0.0.1:5175",
]
app.add_middleware(
    CORSMiddleware, allow_origins=_DEV_ORIGINS, allow_credentials=False,
    allow_methods=["GET", "POST"], allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "mrt-pharma-engine"}


# ---------------------------------------------------------------------------
# Radionuclide physical constant, reused from the repository's own data file
# (never a second hardcoded half-life table).
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_REPO_ROOT, "radionuclides.json"), encoding="utf-8") as _handle:
    _RADIONUCLIDE_HALF_LIFE_MIN: dict[str, dict[str, float]] = json.load(_handle)

_DEMO_RADIONUCLIDE = "F-18"
_DEMO_HALF_LIFE_MIN = _RADIONUCLIDE_HALF_LIFE_MIN[_DEMO_RADIONUCLIDE]["half_life_min"]

_DEMO_PROJECT_ID = "oncology-expansion-demo"

ProjectType = Literal["GREENFIELD", "RETROFIT"]
ConstraintMode = Literal["BUDGET", "CAPACITY"]


class ProjectResponse(BaseModel):
    project_id: str
    project_type: ProjectType
    current_patients_per_day: float
    default_target_patients_per_day: float
    default_maximum_project_budget_usd: float
    geometry_basis: str
    provenance: str


def _controlled_demo_project() -> ProjectResponse:
    return ProjectResponse(
        project_id=_DEMO_PROJECT_ID,
        project_type="RETROFIT",
        current_patients_per_day=60.0,
        default_target_patients_per_day=120.0,
        default_maximum_project_budget_usd=8_000_000.0,
        geometry_basis="Conceptual geometry (flat engineering inputs; no BIM import connected)",
        provenance="CONTROLLED_DEMO_INPUT -- synthetic project input, not an engineering result",
    )


@app.get("/api/capital/project/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str) -> ProjectResponse:
    if project_id != _DEMO_PROJECT_ID:
        raise HTTPException(status_code=404, detail="Unknown project_id")
    return _controlled_demo_project()


# ---------------------------------------------------------------------------
# Cyclotron catalog -- read-only passthrough of the existing catalog module.
# ---------------------------------------------------------------------------


class CyclotronModelSummary(BaseModel):
    catalog_model_id: str
    manufacturer: str
    model: str
    commercial_status: str


@app.get("/api/catalog/cyclotrons", response_model=list[CyclotronModelSummary])
def list_cyclotron_models() -> list[CyclotronModelSummary]:
    catalog = cc.load_cyclotron_catalog()
    grouped = cc.list_models_grouped_by_manufacturer(catalog)
    summaries: list[CyclotronModelSummary] = []
    for models in grouped.values():
        for model in models:
            summaries.append(
                CyclotronModelSummary(
                    catalog_model_id=model.catalog_model_id,
                    manufacturer=model.manufacturer,
                    model=model.model,
                    commercial_status=model.commercial_status,
                )
            )
    return summaries


# ---------------------------------------------------------------------------
# Capital analysis -- the important endpoint. Calls the existing engine
# (`equal_budget.run_equal_budget_multibatch_optimization`) and serializes
# its result verbatim.
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    project_id: str
    project_type: ProjectType
    constraint_mode: ConstraintMode
    current_patients_per_day: float = Field(ge=0)
    target_patients_per_day: float = Field(gt=0)
    maximum_project_budget_usd: float | None = Field(default=None, gt=0)
    cyclotron_catalog_model_id: str | None = None


class PathwayConfiguration(BaseModel):
    label: Literal["Conventional", "MRT"]
    feasible: bool
    patient_capacity_per_day: float
    project_capex_usd: float
    budget_usd: float
    budget_used_usd: float
    budget_headroom_usd: float
    annual_revenue_usd: float
    annual_opex_usd: float
    npv_usd: float
    roi_pct: float
    payback_years: float | None
    additional_scanners: int
    binding_constraint: str
    reserve_capacity_per_day: float
    cyclotron_utilization_pct: float
    cyclotron_capacity_status: str


class AnalyzeResponse(BaseModel):
    project_id: str
    constraint_mode: ConstraintMode
    budget_source: str
    common_budget_usd: float
    configurations: list[PathwayConfiguration]
    cyclotron_catalog_model_id: str | None
    cyclotron_warnings: list[str]
    provenance: str


def _build_planner_inputs(payload: AnalyzeRequest, cyclotron_fleet: object | None) -> PlannerInputs:
    is_retrofit = payload.project_type == "RETROFIT"
    current = payload.current_patients_per_day if is_retrofit else 0.0
    return PlannerInputs(
        project_name=f"Capital Project — {payload.project_id}",
        current_patients_per_day=current,
        target_patients_per_day=payload.target_patients_per_day,
        maximum_expected_demand_per_day=payload.target_patients_per_day,
        current_scanners=2 if is_retrofit else 0,
        current_injection_rooms=2 if is_retrofit else 0,
        current_uptake_rooms=2 if is_retrofit else 0,
        # A retained (already-owned) cyclotron is never charged as new-project
        # CapEx (see whole_oncology_four_architecture_optimization.py's
        # EXISTING_RETAINED doctrine); a Greenfield project has nothing
        # existing to retain.
        has_existing_cyclotron=is_retrofit and cyclotron_fleet is not None,
        current_usable_doses_per_day=current,
        current_average_transport_min=8.0,
        mrt_transport_min=3.0,
        conventional_transport_min=8.0,
        existing_mrt_connectable_rooms=2 if is_retrofit else 0,
        representative_radionuclide=_DEMO_RADIONUCLIDE,
        representative_half_life_min=_DEMO_HALF_LIFE_MIN,
        selected_cyclotron_radionuclide=_DEMO_RADIONUCLIDE,
        cyclotron_fleet=cyclotron_fleet,
    )


def _to_configuration(pathway: "eb.MultiBatchPathwayResult", assumptions: PlannerAssumptions) -> PathwayConfiguration:
    # `run_equal_budget_multibatch_optimization` leaves `pathway.npv`/`.roi_pct`/
    # `.payback_years` at their unpopulated dataclass defaults (0.0/0.0/inf) --
    # verified against the engine directly. Real NPV/ROI/payback are instead
    # computed here via `finance.incremental_financials`, the SAME existing
    # authoritative function the engine itself calls internally elsewhere
    # (never a second/new economics engine).
    annual_revenue, _annual_opex, _net_cash_flow, npv, roi_pct, payback = finance.incremental_financials(
        capex=pathway.capex_used,
        annual_incremental_opex=pathway.total_annual_modelled_opex,
        throughput_patients_per_day=pathway.revenue_generating_throughput_per_day,
        revenue_per_scan=assumptions.revenue_per_scan,
        operating_days_per_year=assumptions.operating_days_per_year,
        discount_rate_pct=assumptions.discount_rate_pct,
        analysis_years=assumptions.analysis_years,
    )
    payback_years = None if math.isinf(payback) else payback
    return PathwayConfiguration(
        label=pathway.pathway,  # type: ignore[arg-type]
        feasible=pathway.operating_day_feasible,
        patient_capacity_per_day=pathway.achieved_capacity_per_day,
        project_capex_usd=pathway.capex_used,
        budget_usd=pathway.budget,
        budget_used_usd=pathway.capex_used,
        budget_headroom_usd=pathway.unused_budget,
        annual_revenue_usd=annual_revenue,
        annual_opex_usd=pathway.total_annual_modelled_opex,
        npv_usd=npv,
        roi_pct=roi_pct,
        payback_years=payback_years,
        additional_scanners=pathway.additional_scanners,
        binding_constraint=pathway.binding_constraint,
        reserve_capacity_per_day=pathway.reserve_capacity_above_expected_demand_per_day,
        cyclotron_utilization_pct=pathway.cyclotron_utilization_pct,
        cyclotron_capacity_status=pathway.cyclotron_activity_capacity_status,
    )


def _execute_analysis(payload: "AnalyzeRequest") -> "AnalyzeResponse":
    """The one authoritative analysis call path -- shared verbatim by
    `/api/capital/analyze`, `/api/capital/lockdown` and `/api/capital/
    what-if` (Build 3 section 32: lockdown/what-if must rerun this, never
    derive a result from a previously-stored one)."""
    if payload.constraint_mode == "BUDGET" and payload.maximum_project_budget_usd is None:
        raise HTTPException(status_code=422, detail="maximum_project_budget_usd is required when constraint_mode is BUDGET")

    catalog = cc.load_cyclotron_catalog()
    cyclotron_fleet = None
    cyclotron_warnings: tuple[str, ...] = ()
    if payload.cyclotron_catalog_model_id:
        try:
            catalog.by_id(payload.cyclotron_catalog_model_id)
        except KeyError as exc:
            raise HTTPException(status_code=422, detail=f"Unknown cyclotron_catalog_model_id: {payload.cyclotron_catalog_model_id!r}") from exc
        instance = cc.create_facility_cyclotron_instance(catalog_model_id=payload.cyclotron_catalog_model_id, existing_instances=())
        cyclotron_fleet, cyclotron_warnings = cc.build_fleet_from_instances(catalog=catalog, instances=(instance,))

    inputs = _build_planner_inputs(payload, cyclotron_fleet)
    assumptions = PlannerAssumptions()
    explicit_budget = payload.maximum_project_budget_usd if payload.constraint_mode == "BUDGET" else None

    try:
        result = eb.run_equal_budget_multibatch_optimization(
            inputs, assumptions, _DEMO_HALF_LIFE_MIN, explicit_budget=explicit_budget,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"NO_FEASIBLE_CONFIGURATION: {exc}") from exc

    return AnalyzeResponse(
        project_id=payload.project_id,
        constraint_mode=payload.constraint_mode,
        budget_source=result.budget_source,
        common_budget_usd=result.common_budget,
        configurations=[_to_configuration(result.conventional, assumptions), _to_configuration(result.mrt, assumptions)],
        cyclotron_catalog_model_id=payload.cyclotron_catalog_model_id,
        cyclotron_warnings=list(cyclotron_warnings),
        provenance="equal_budget.run_equal_budget_multibatch_optimization (existing MRT Pharma engine, unmodified)",
    )


@app.post("/api/capital/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    return _execute_analysis(payload)


# ---------------------------------------------------------------------------
# Build 3: Lockdown / What-If lineage.
#
# AUDIT FINDING (section 2/43): `lockdown_what_if_lineage_authority.py`'s
# `CanonicalLockdownRecord.spatial_state` and `mrt_auxiliary_systems_
# authority.branch_what_if_scenario` BOTH require a real
# `canonical_spatial_authority.LockedSpatialState` -- built from a
# `SpatialObjectRegistry`. The controlled Capital Project analysis path
# (`_execute_analysis` above) is flat/scalar ("Conceptual geometry (flat
# engineering inputs; no BIM import connected)" -- see `ProjectResponse.
# geometry_basis`) and has NO canonical spatial registry at all. Forcing a
# fake empty registry into that authority purely to satisfy its type would
# be exactly the "fabricate a building solely to make the UI move
# something" anti-pattern this build explicitly forbids.
#
# LOCKDOWN_AUTHORITY_REUSED = NO (root cause above)
# WHAT_IF_AUTHORITY_REUSED = NO (same root cause)
# PARAMETER_CHANGE_AUTHORITY = AUDITED -- mrt_auxiliary_systems_authority.
#   record_parameter_change exists but only operates on a
#   UnifiedWhatIfScenario, itself only constructible via
#   branch_what_if_scenario(locked: LockedSpatialState, ...)
# SPATIAL_CHANGE_AUTHORITY = NOT APPLICABLE -- no canonical spatial object
#   exists for this controlled project (section 20 audit;
#   CONTROLLED_PROJECT_SPATIAL_OBJECT_AVAILABLE = NO)
# DELTA_AUTHORITY_REUSED = NO existing authority compares two flat capital
#   analysis runs (SystemDeltaRow/ChangeConsequenceRecord are scoped to
#   spatial move/consequence operations). The Baseline/What-If/Delta
#   comparison below is PRESENTATION-ONLY subtraction of two
#   already-authoritative engine outputs (section 13's explicit fallback
#   allowance), never a second engineering computation.
#
# This module therefore implements a narrow, IN-MEMORY, project_id-keyed
# lineage store that reuses the EXISTING authority's naming/status
# vocabulary and immutability discipline (status supersession, never
# mutate a locked record in place, explicit promotion only) without
# instantiating its spatial-coupled dataclasses. This is demo-only
# process-memory state -- it is lost on restart, never a database, and is
# isolated behind the two functions below so real persistence can replace
# it later without changing the route contracts.
# ---------------------------------------------------------------------------

CandidateLabel = Literal["Conventional", "MRT"]
LockdownStatus = Literal["CURRENT", "SUPERSEDED"]
WhatIfStatus = Literal["ACTIVE", "DISCARDED"]


class CapitalLockdown(BaseModel):
    lockdown_id: str
    project_id: str
    parent_lockdown_id: str | None
    status: LockdownStatus
    created_at: str
    candidate_label: CandidateLabel
    request: AnalyzeRequest
    result: "PathwayConfiguration"
    common_budget_usd: float
    budget_source: str


class CapitalWhatIf(BaseModel):
    what_if_id: str
    project_id: str
    parent_lockdown_id: str
    status: WhatIfStatus
    created_at: str
    candidate_label: CandidateLabel
    request: AnalyzeRequest
    result: "PathwayConfiguration"
    common_budget_usd: float
    budget_source: str


_LOCKDOWNS: dict[str, CapitalLockdown] = {}
_WHAT_IFS: dict[str, CapitalWhatIf] = {}
_CURRENT_LOCKDOWN_ID_BY_PROJECT: dict[str, str] = {}
_ACTIVE_WHAT_IF_ID_BY_PROJECT: dict[str, str] = {}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _select_configuration(response: "AnalyzeResponse", candidate_label: CandidateLabel) -> "PathwayConfiguration":
    for configuration in response.configurations:
        if configuration.label == candidate_label:
            return configuration
    raise HTTPException(status_code=422, detail=f"Analysis did not return a {candidate_label!r} configuration")


class LockdownRequest(BaseModel):
    project_id: str
    candidate_label: CandidateLabel
    request: AnalyzeRequest


@app.post("/api/capital/lockdown", response_model=CapitalLockdown)
def create_lockdown(payload: LockdownRequest) -> CapitalLockdown:
    """Section 5-6/30-31: establishes an explicit, immutable baseline by
    RERUNNING the authoritative engine with the caller-supplied request and
    selected candidate -- never trusts a client-supplied result value.
    Superseding a prior lockdown for this `project_id` never mutates the
    old record in place (mirrors `lockdown_what_if_lineage_authority.py`'s
    own supersession discipline)."""
    if payload.request.project_id != payload.project_id:
        raise HTTPException(status_code=422, detail="project_id mismatch between lockdown request and analysis request")

    analysis = _execute_analysis(payload.request)
    configuration = _select_configuration(analysis, payload.candidate_label)

    previous_lockdown_id = _CURRENT_LOCKDOWN_ID_BY_PROJECT.get(payload.project_id)
    if previous_lockdown_id is not None:
        previous = _LOCKDOWNS[previous_lockdown_id]
        _LOCKDOWNS[previous_lockdown_id] = previous.model_copy(update={"status": "SUPERSEDED"})

    lockdown = CapitalLockdown(
        lockdown_id=_new_id("LOCKDOWN"),
        project_id=payload.project_id,
        parent_lockdown_id=previous_lockdown_id,
        status="CURRENT",
        created_at=_timestamp(),
        candidate_label=payload.candidate_label,
        request=payload.request,
        result=configuration,
        common_budget_usd=analysis.common_budget_usd,
        budget_source=analysis.budget_source,
    )
    _LOCKDOWNS[lockdown.lockdown_id] = lockdown
    _CURRENT_LOCKDOWN_ID_BY_PROJECT[payload.project_id] = lockdown.lockdown_id
    _ACTIVE_WHAT_IF_ID_BY_PROJECT.pop(payload.project_id, None)
    return lockdown


class WhatIfRequest(BaseModel):
    project_id: str
    request: AnalyzeRequest


@app.post("/api/capital/what-if", response_model=CapitalWhatIf)
def create_what_if(payload: WhatIfRequest) -> CapitalWhatIf:
    """Section 7-11/17/32: branches from the project's CURRENT lockdown and
    RERUNS the authoritative engine with the modified request -- the
    baseline record itself is never read back into the response and is
    never mutated. Rejects a What-If that changes the constraint mode
    (section 10) or targets a project with no lockdown yet."""
    lockdown_id = _CURRENT_LOCKDOWN_ID_BY_PROJECT.get(payload.project_id)
    if lockdown_id is None:
        raise HTTPException(status_code=422, detail="No locked baseline exists for this project_id -- lock a configuration first")
    lockdown = _LOCKDOWNS[lockdown_id]

    if payload.request.project_id != payload.project_id:
        raise HTTPException(status_code=422, detail="project_id mismatch between what-if request and analysis request")
    if payload.request.constraint_mode != lockdown.request.constraint_mode:
        raise HTTPException(status_code=422, detail="A What-If must stay within the baseline's primary constraint mode")

    analysis = _execute_analysis(payload.request)
    configuration = _select_configuration(analysis, lockdown.candidate_label)

    what_if = CapitalWhatIf(
        what_if_id=_new_id("WHATIF"),
        project_id=payload.project_id,
        parent_lockdown_id=lockdown.lockdown_id,
        status="ACTIVE",
        created_at=_timestamp(),
        candidate_label=lockdown.candidate_label,
        request=payload.request,
        result=configuration,
        common_budget_usd=analysis.common_budget_usd,
        budget_source=analysis.budget_source,
    )
    _WHAT_IFS[what_if.what_if_id] = what_if
    _ACTIVE_WHAT_IF_ID_BY_PROJECT[payload.project_id] = what_if.what_if_id
    return what_if


class WhatIfResetRequest(BaseModel):
    project_id: str


class WhatIfResetResponse(BaseModel):
    project_id: str
    parent_lockdown_id: str
    baseline_request: AnalyzeRequest


@app.post("/api/capital/what-if/reset", response_model=WhatIfResetResponse)
def reset_what_if(payload: WhatIfResetRequest) -> WhatIfResetResponse:
    """Section 18: discards the project's active What-If (never the
    baseline) and returns the locked baseline's own input so the frontend
    can restore its editable fields -- no engine call, since no new result
    is being computed."""
    lockdown_id = _CURRENT_LOCKDOWN_ID_BY_PROJECT.get(payload.project_id)
    if lockdown_id is None:
        raise HTTPException(status_code=422, detail="No locked baseline exists for this project_id")
    lockdown = _LOCKDOWNS[lockdown_id]

    active_what_if_id = _ACTIVE_WHAT_IF_ID_BY_PROJECT.pop(payload.project_id, None)
    if active_what_if_id is not None and active_what_if_id in _WHAT_IFS:
        active = _WHAT_IFS[active_what_if_id]
        _WHAT_IFS[active_what_if_id] = active.model_copy(update={"status": "DISCARDED"})

    return WhatIfResetResponse(project_id=payload.project_id, parent_lockdown_id=lockdown.lockdown_id, baseline_request=lockdown.request)

