"""KIRO Super-Build 3 -- Capital-Project Inheritance & Economic Scope Authority.

THE FUNDAMENTAL DOCTRINE (Sec 16): PHYSICAL INHERITANCE != ECONOMIC INHERITANCE.
Existing physical/operational information may be inherited by the digital twin
WITHOUT re-purchasing or re-constructing the existing facility. The engine
distinguishes WHAT EXISTS from WHAT THE PROJECT MUST PAY FOR.

This is a NEW authority that COMPOSES existing owners (it never re-implements a
second CapEx/OPEX/capacity engine):
  * project starting state / development context -> whole_oncology_four_architecture_optimization
    (ProjectStartingState, DevelopmentContext) -- LEGACY_PRESERVE, referenced.
  * existing-facility identity -> existing_facility_asis_twin -- referenced.
  * spatial asset_status / import provenance -> canonical_spatial_authority -- referenced.
  * incremental-quantity pattern -> infrastructure_capex._incremental_quantity -- reused pattern.
  * per-mode transport economics -> generalized_transport_optimizer.ModeEconomics -- referenced.

It establishes, additively:
  1. THREE canonical project classes (Sec 1): RETROFIT / EXPANSION / GREENFIELD.
  2. ONE capital-project scope object (Sec 7).
  3. SEVEN canonical asset economic states (Sec 8): INHERITED_EXISTING /
     RETAINED_NO_CHANGE / MODIFY / REPLACE / NEW / REMOVE / OUT_OF_SCOPE.
  4. A BIM economic-scope governor (Sec 18): BIM_OBJECT_PRESENT != NEW_CAPEX.
  5. Capacity-delta authority (Sec 21): incremental = max(target - retained, 0).
  6. Material / equipment / transport economic scope settings (Sec 31-38).
  7. Incremental CapEx + OPEX inheritance (Sec 39): baseline vs retained vs new
     vs modification-delta vs replacement-delta vs removed; savings preserved;
     no-silent-zero; NOT_CALIBRATED preserved.

Nothing here changes MRT canonical physics, Part 3E, equal_budget, or the SB1/
SB2 authorities. No stage/commit/push in this build.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Literal, Mapping, Sequence

# ===========================================================================
# 1. THREE canonical project classes (Sec 1-2).
# ===========================================================================

ProjectClass = Literal[
    "EXISTING_FACILITY_RETROFIT", "EXISTING_FACILITY_EXPANSION", "GREENFIELD_NEW_FACILITY",
]

CANONICAL_PROJECT_CLASSES: tuple[ProjectClass, ...] = (
    "EXISTING_FACILITY_RETROFIT", "EXISTING_FACILITY_EXPANSION", "GREENFIELD_NEW_FACILITY",
)

# Bridge to the LEGACY_PRESERVE development-context axis (CapEx attribution).
# EXPANSION had no first-class development context; it maps to RETROFIT-style
# inheritance (existing facility inherited) PLUS new construction scope.
PROJECT_CLASS_INHERITS_EXISTING: Mapping[ProjectClass, bool] = {
    "EXISTING_FACILITY_RETROFIT": True,
    "EXISTING_FACILITY_EXPANSION": True,
    "GREENFIELD_NEW_FACILITY": False,
}


# ===========================================================================
# 2a. TWO ORTHOGONAL AXES (clarification A): baseline PROVENANCE/ORIGIN vs
#     project ACTION. INHERITED_EXISTING and RETAINED_NO_CHANGE are NOT
#     competing mutually-exclusive facts -- they answer different questions:
#
#       AssetBaselineOrigin  -> "did this asset exist before the project?"
#       AssetProjectAction   -> "what does the project DO to it?"
#
#     An existing asset the project leaves alone is
#     origin=EXISTING_BASELINE + action=RETAINED_NO_CHANGE. An existing asset
#     the project modifies is origin=EXISTING_BASELINE + action=MODIFY, etc.
#     The 7-value `AssetEconomicState` below is preserved as the SINGLE
#     canonical cost-treatment vocabulary (backward compatible);
#     `AssetClassification` carries BOTH axes so neither concept is lost.
# ===========================================================================

AssetBaselineOrigin = Literal[
    "EXISTING_BASELINE",       # existed before the project (RETROFIT/EXPANSION baseline)
    "NEW_TO_PROJECT",          # introduced by this project
    "OUT_OF_BASELINE_SCOPE",   # may exist physically but outside economic baseline
]

CANONICAL_ASSET_BASELINE_ORIGINS: tuple[AssetBaselineOrigin, ...] = (
    "EXISTING_BASELINE", "NEW_TO_PROJECT", "OUT_OF_BASELINE_SCOPE",
)

AssetProjectAction = Literal[
    "RETAINED_NO_CHANGE", "MODIFY", "REPLACE", "NEW", "REMOVE", "OUT_OF_SCOPE",
]

CANONICAL_ASSET_PROJECT_ACTIONS: tuple[AssetProjectAction, ...] = (
    "RETAINED_NO_CHANGE", "MODIFY", "REPLACE", "NEW", "REMOVE", "OUT_OF_SCOPE",
)

# ===========================================================================
# 2. SEVEN canonical asset economic states (Sec 8-16). Preserved as the ONE
#    canonical cost-treatment vocabulary. Each decomposes deterministically
#    into an (origin, action) pair via `decompose_economic_state`, and an
#    (origin, action) pair normalizes to a state via `economic_state_of`.
# ===========================================================================

AssetEconomicState = Literal[
    "INHERITED_EXISTING", "RETAINED_NO_CHANGE", "MODIFY", "REPLACE", "NEW", "REMOVE", "OUT_OF_SCOPE",
]

CANONICAL_ASSET_ECONOMIC_STATES: tuple[AssetEconomicState, ...] = (
    "INHERITED_EXISTING", "RETAINED_NO_CHANGE", "MODIFY", "REPLACE", "NEW", "REMOVE", "OUT_OF_SCOPE",
)

# Deterministic (origin, action) decomposition of each economic state.
# INHERITED_EXISTING and RETAINED_NO_CHANGE share cost treatment ($0 new CapEx)
# yet are distinguishable: both are origin=EXISTING_BASELINE + action=
# RETAINED_NO_CHANGE, but the LABEL preserves emphasis (INHERITED_EXISTING = a
# generic baseline pass-through fact; RETAINED_NO_CHANGE = an explicit project
# decision). `AssetClassification` keeps the two axes so the distinction is
# never lost even though both normalize to the same cost treatment.
_STATE_DECOMPOSITION: Mapping[AssetEconomicState, tuple[AssetBaselineOrigin, AssetProjectAction]] = {
    "INHERITED_EXISTING": ("EXISTING_BASELINE", "RETAINED_NO_CHANGE"),
    "RETAINED_NO_CHANGE": ("EXISTING_BASELINE", "RETAINED_NO_CHANGE"),
    "MODIFY": ("EXISTING_BASELINE", "MODIFY"),
    "REPLACE": ("EXISTING_BASELINE", "REPLACE"),
    "NEW": ("NEW_TO_PROJECT", "NEW"),
    "REMOVE": ("EXISTING_BASELINE", "REMOVE"),
    "OUT_OF_SCOPE": ("OUT_OF_BASELINE_SCOPE", "OUT_OF_SCOPE"),
}


def decompose_economic_state(state: AssetEconomicState) -> tuple[AssetBaselineOrigin, AssetProjectAction]:
    """Clarification A: the (origin, action) pair for a canonical economic state."""
    return _STATE_DECOMPOSITION[state]


def economic_state_of(origin: AssetBaselineOrigin, action: AssetProjectAction) -> AssetEconomicState:
    """Clarification A: normalize an (origin, action) pair to the canonical
    cost-treatment state. A NEW_TO_PROJECT asset is always NEW; an
    EXISTING_BASELINE + RETAINED_NO_CHANGE normalizes to RETAINED_NO_CHANGE
    (the explicit-decision label; INHERITED_EXISTING remains available as the
    generic-origin synonym). OUT_OF_SCOPE/EXCLUDE dominates."""
    if action == "OUT_OF_SCOPE" or origin == "OUT_OF_BASELINE_SCOPE":
        return "OUT_OF_SCOPE"
    if origin == "NEW_TO_PROJECT" or action == "NEW":
        return "NEW"
    if action == "MODIFY":
        return "MODIFY"
    if action == "REPLACE":
        return "REPLACE"
    if action == "REMOVE":
        return "REMOVE"
    return "RETAINED_NO_CHANGE"


@dataclass(frozen=True)
class AssetClassification:
    """Clarification A: carries BOTH baseline-origin and project-action axes so
    provenance (did it exist?) and action (what does the project do?) are never
    forced into one mutually-exclusive field. `economic_state` derives the
    single canonical cost-treatment label."""

    origin: AssetBaselineOrigin
    action: AssetProjectAction

    def __post_init__(self) -> None:
        if self.origin not in CANONICAL_ASSET_BASELINE_ORIGINS:
            raise ValueError(f"unknown origin {self.origin}")
        if self.action not in CANONICAL_ASSET_PROJECT_ACTIONS:
            raise ValueError(f"unknown action {self.action}")
        # NEW_TO_PROJECT is incompatible with retain/modify/replace/remove of an
        # inherited asset (those imply an existing-baseline origin).
        if self.origin == "NEW_TO_PROJECT" and self.action in ("RETAINED_NO_CHANGE", "MODIFY", "REPLACE", "REMOVE"):
            raise ValueError(f"origin NEW_TO_PROJECT incompatible with action {self.action}")

    @property
    def economic_state(self) -> AssetEconomicState:
        return economic_state_of(self.origin, self.action)

# Whether the state charges acquisition/construction CapEx for the WHOLE object
# (Sec 9-15). MODIFY/REPLACE charge only the incremental/replacement work, never
# the whole inherited object -- represented by their own delta fields below.
_STATE_CHARGES_FULL_ACQUISITION: Mapping[AssetEconomicState, bool] = {
    "INHERITED_EXISTING": False,   # Sec 9: historical acquisition NOT charged again
    "RETAINED_NO_CHANGE": False,   # Sec 10: no new acquisition/installation
    "MODIFY": False,               # Sec 11: only modification work
    "REPLACE": True,               # Sec 12: replacement is a new purchase (displaces old)
    "NEW": True,                   # Sec 13: full project CapEx
    "REMOVE": False,               # Sec 14: removal only
    "OUT_OF_SCOPE": False,         # Sec 15: outside economic boundary
}

# Whether the object contributes usable operating capacity to the TARGET state.
_STATE_CONTRIBUTES_TARGET_CAPACITY: Mapping[AssetEconomicState, bool] = {
    "INHERITED_EXISTING": True,
    "RETAINED_NO_CHANGE": True,
    "MODIFY": True,
    "REPLACE": True,     # the replacement contributes; the old one is displaced
    "NEW": True,
    "REMOVE": False,     # Sec 14: removed capacity leaves target
    "OUT_OF_SCOPE": True,  # Sec 15: physically present (may still bear capacity/routes)
}

# Whether the object's ongoing OPEX continues in the target operational state.
_STATE_CONTRIBUTES_TARGET_OPEX: Mapping[AssetEconomicState, bool] = {
    "INHERITED_EXISTING": True,
    "RETAINED_NO_CHANGE": True,
    "MODIFY": True,
    "REPLACE": True,
    "NEW": True,
    "REMOVE": False,
    "OUT_OF_SCOPE": False,  # outside economic boundary -> excluded from project economics
}


def state_charges_full_acquisition_capex(state: AssetEconomicState) -> bool:
    return _STATE_CHARGES_FULL_ACQUISITION[state]


def state_contributes_target_capacity(state: AssetEconomicState) -> bool:
    return _STATE_CONTRIBUTES_TARGET_CAPACITY[state]


def state_contributes_target_opex(state: AssetEconomicState) -> bool:
    return _STATE_CONTRIBUTES_TARGET_OPEX[state]


# ===========================================================================
# 3. Material / system + equipment economic scope settings (Sec 31-33).
#    These control ECONOMIC participation only; they never delete geometry /
#    routing / capacity (Sec 32).
# ===========================================================================

MaterialSystemCategory = Literal[
    "STRUCTURE", "EXTERIOR_ENVELOPE", "INTERIOR_WALLS", "DOORS", "HVAC", "ELECTRICAL",
    "PLUMBING", "FIRE_LIFE_SAFETY", "SHIELDING", "VERTICAL_TRANSPORT", "IT_NETWORK",
    "CLINICAL_ROOMS", "EQUIPMENT", "TRANSPORT_INFRASTRUCTURE", "SITE_WORK", "OTHER",
]

CANONICAL_MATERIAL_SYSTEM_CATEGORIES: tuple[MaterialSystemCategory, ...] = (
    "STRUCTURE", "EXTERIOR_ENVELOPE", "INTERIOR_WALLS", "DOORS", "HVAC", "ELECTRICAL",
    "PLUMBING", "FIRE_LIFE_SAFETY", "SHIELDING", "VERTICAL_TRANSPORT", "IT_NETWORK",
    "CLINICAL_ROOMS", "EQUIPMENT", "TRANSPORT_INFRASTRUCTURE", "SITE_WORK", "OTHER",
)

EquipmentCategory = Literal[
    "SCANNER", "CYCLOTRON", "GENERATOR", "RADIOPHARMACY", "INJECTION", "UPTAKE",
    "CLINICAL", "TRANSPORT",
]


@dataclass(frozen=True)
class EconomicScopeSettings:
    """Sec 31-33: backend economic inclusion/exclusion by category. A category
    OFF means it does NOT participate in PROJECT ECONOMIC ANALYSIS; it does NOT
    delete the category from geometry/routing/capacity (Sec 32). Default: all
    categories economically IN scope (safe, explicit default)."""

    material_scope: Mapping[MaterialSystemCategory, bool] = field(
        default_factory=lambda: {c: True for c in CANONICAL_MATERIAL_SYSTEM_CATEGORIES}
    )
    equipment_scope: Mapping[EquipmentCategory, bool] = field(
        default_factory=lambda: {c: True for c in (
            "SCANNER", "CYCLOTRON", "GENERATOR", "RADIOPHARMACY", "INJECTION", "UPTAKE", "CLINICAL", "TRANSPORT",
        )}
    )

    def material_in_economic_scope(self, category: MaterialSystemCategory) -> bool:
        return self.material_scope.get(category, True)

    def equipment_in_economic_scope(self, category: EquipmentCategory) -> bool:
        return self.equipment_scope.get(category, True)

    def with_material_off(self, *categories: MaterialSystemCategory) -> "EconomicScopeSettings":
        new = dict(self.material_scope)
        for c in categories:
            new[c] = False
        return replace(self, material_scope=new)

    def with_equipment_off(self, *categories: EquipmentCategory) -> "EconomicScopeSettings":
        new = dict(self.equipment_scope)
        for c in categories:
            new[c] = False
        return replace(self, equipment_scope=new)


# ===========================================================================
# 4. ONE capital-project scope object (Sec 7).
# ===========================================================================

@dataclass(frozen=True)
class CapitalProjectScope:
    """Sec 7: the ONE authoritative project-scope object."""

    project_id: str
    project_class: ProjectClass
    baseline_facility_id: str | None
    target_state_id: str | None = None
    project_boundary: str = "WHOLE_FACILITY"
    economic_scope: EconomicScopeSettings = field(default_factory=EconomicScopeSettings)
    provenance: str = "PROJECT_SUPPLIED"
    completeness_status: str = "STRUCTURALLY_DEFINED"

    def __post_init__(self) -> None:
        if self.project_class not in CANONICAL_PROJECT_CLASSES:
            raise ValueError(f"Unknown project_class: {self.project_class}")
        # Sec 2: RETROFIT/EXPANSION require a baseline facility; GREENFIELD must not.
        if self.project_class in ("EXISTING_FACILITY_RETROFIT", "EXISTING_FACILITY_EXPANSION"):
            if self.baseline_facility_id is None:
                raise ValueError(f"{self.project_class} requires a baseline_facility_id")
        # GREENFIELD may reference an explicit reused external resource, but not a
        # whole inherited facility baseline (Sec 2/30).

    def inherits_existing_facility(self) -> bool:
        return PROJECT_CLASS_INHERITS_EXISTING[self.project_class]


# ===========================================================================
# 5. BIM economic-scope governor (Sec 17-18). BIM_OBJECT_PRESENT != NEW_CAPEX.
# ===========================================================================

# Multi-input geometry origins (Sec 17) that must NOT auto-imply NEW construction.
GeometryOrigin = Literal[
    "BIM", "CAD", "PDF", "IMAGE", "MANUAL", "API", "INTELLIGENT_RECONSTRUCTION",
]


def bim_object_default_economic_state(
    *, project_class: ProjectClass, is_project_intervention: bool = False,
) -> AssetEconomicState:
    """Sec 17-18: the DEFAULT economic state of an imported/present BIM object.
    Presence in a model NEVER implies NEW project CapEx. For an inheriting
    project class (RETROFIT/EXPANSION) an untouched imported object defaults to
    INHERITED_EXISTING; only an explicit project intervention makes it NEW/
    MODIFY/REPLACE. For GREENFIELD everything is NEW by definition."""
    if project_class == "GREENFIELD_NEW_FACILITY":
        return "NEW"
    if is_project_intervention:
        return "NEW"
    return "INHERITED_EXISTING"


def bim_object_charges_new_capex(state: AssetEconomicState) -> bool:
    """Sec 18: only NEW (or the replacement portion of REPLACE) charges new
    CapEx. Mere presence in the model does not."""
    return state in ("NEW", "REPLACE")


# ===========================================================================
# 6. Capacity-delta authority (Sec 21-26).
# ===========================================================================

@dataclass(frozen=True)
class CapacityDeltaInputs:
    resource: str
    existing_usable_units: int
    target_required_units: int
    removed_units: int = 0
    replaced_units: int = 0
    unit_capex_usd: float | None = None
    unit_annual_opex_usd: float | None = None

    def __post_init__(self) -> None:
        for name in ("existing_usable_units", "target_required_units", "removed_units", "replaced_units"):
            v = getattr(self, name)
            if not isinstance(v, int) or v < 0:
                raise ValueError(f"{name} must be a non-negative int (got {v!r})")
        if self.replaced_units > self.existing_usable_units:
            raise ValueError("replaced_units cannot exceed existing_usable_units")
        if self.removed_units > self.existing_usable_units:
            raise ValueError("removed_units cannot exceed existing_usable_units")


@dataclass(frozen=True)
class CapacityDeltaResult:
    resource: str
    existing_usable_units: int
    target_required_units: int
    retained_units: int
    removed_units: int
    replaced_units: int
    new_units_required: int
    acquisition_quantity: int
    new_capex_usd: float | None
    capex_status: str

    def acquisition_matches(self, expected: int) -> bool:
        return self.acquisition_quantity == expected


def compute_capacity_delta(inputs: CapacityDeltaInputs) -> CapacityDeltaResult:
    """Sec 21-25: INCREMENTAL_REQUIRED = max(TARGET_REQUIRED -
    RETAINED_USABLE_EXISTING, 0). Retained = existing usable that is neither
    removed nor replaced. Acquisition quantity = new (capacity growth) +
    replaced (like-for-like swaps). NEVER charge the full target quantity when
    existing usable capacity is inherited (Sec 22-23)."""
    retained = inputs.existing_usable_units - inputs.removed_units - inputs.replaced_units
    if retained < 0:
        raise ValueError("removed + replaced exceed existing usable units")
    # Growth beyond retained-usable capacity (retained + replaced both serve target).
    usable_toward_target = retained + inputs.replaced_units
    new_units_required = max(inputs.target_required_units - usable_toward_target, 0)
    # Acquisition = growth units + like-for-like replacements (Sec 23).
    acquisition_quantity = new_units_required + inputs.replaced_units

    if inputs.unit_capex_usd is None:
        new_capex: float | None = None
        capex_status = "NOT_CALIBRATED"  # Sec 39: never $0-filled when unknown
    else:
        new_capex = acquisition_quantity * inputs.unit_capex_usd
        capex_status = "CALIBRATED_FROM_UNIT_COST"

    return CapacityDeltaResult(
        resource=inputs.resource,
        existing_usable_units=inputs.existing_usable_units,
        target_required_units=inputs.target_required_units,
        retained_units=retained,
        removed_units=inputs.removed_units,
        replaced_units=inputs.replaced_units,
        new_units_required=new_units_required,
        acquisition_quantity=acquisition_quantity,
        new_capex_usd=new_capex,
        capex_status=capex_status,
    )


# ===========================================================================
# 7. Incremental CapEx aggregation across an asset register (Sec 22/28).
# ===========================================================================

@dataclass(frozen=True)
class AssetEconomicRecord:
    """One economically-relevant object classified into a project state, with
    its costs. `full_acquisition_capex` = cost to purchase/construct the whole
    object new (used only when the state charges it). `modification_capex` /
    `replacement_capex` are the incremental works for MODIFY/REPLACE."""

    asset_id: str
    category: str
    economic_state: AssetEconomicState
    full_acquisition_capex_usd: float | None = None
    modification_capex_usd: float | None = None
    replacement_capex_usd: float | None = None
    removal_capex_usd: float | None = None
    in_economic_scope: bool = True

    def charged_capex(self) -> tuple[float, str, tuple[str, ...]]:
        """Return (charged_capex, status, unknown_components). Sec 9-15: the
        charged CapEx depends on the economic state, NOT the object's age.
        Unknowns are surfaced separately, never $0-filled (Sec 39)."""
        if not self.in_economic_scope or self.economic_state == "OUT_OF_SCOPE":
            return 0.0, "OUT_OF_SCOPE_NO_PROJECT_CAPEX", ()
        unknown: list[str] = []
        if self.economic_state in ("INHERITED_EXISTING", "RETAINED_NO_CHANGE"):
            return 0.0, "INHERITED_NO_NEW_CAPEX", ()
        if self.economic_state == "NEW":
            if self.full_acquisition_capex_usd is None:
                return 0.0, "NOT_CALIBRATED", (f"{self.asset_id} NEW acquisition CapEx",)
            return self.full_acquisition_capex_usd, "NEW_ACQUISITION", ()
        if self.economic_state == "MODIFY":
            if self.modification_capex_usd is None:
                return 0.0, "NOT_CALIBRATED", (f"{self.asset_id} modification CapEx",)
            return self.modification_capex_usd, "MODIFICATION_ONLY", ()
        if self.economic_state == "REPLACE":
            # replacement purchase + optional removal; NOT the original historical purchase.
            total = 0.0
            if self.replacement_capex_usd is None:
                unknown.append(f"{self.asset_id} replacement CapEx")
            else:
                total += self.replacement_capex_usd
            if self.removal_capex_usd is not None:
                total += self.removal_capex_usd
            status = "REPLACEMENT" if not unknown else "NOT_CALIBRATED"
            return total, status, tuple(unknown)
        if self.economic_state == "REMOVE":
            if self.removal_capex_usd is None:
                return 0.0, "NOT_CALIBRATED", (f"{self.asset_id} removal CapEx",)
            return self.removal_capex_usd, "REMOVAL_ONLY", ()
        raise ValueError(f"unknown economic_state {self.economic_state}")


@dataclass(frozen=True)
class IncrementalCapexResult:
    project_class: ProjectClass
    total_incremental_capex_usd: float
    charged_by_state: Mapping[AssetEconomicState, float]
    inherited_asset_value_excluded_usd: float
    unknown_capex_components: tuple[str, ...]
    records: tuple[AssetEconomicRecord, ...]


def aggregate_incremental_capex(
    *, project_class: ProjectClass, records: Sequence[AssetEconomicRecord],
    economic_scope: EconomicScopeSettings | None = None,
) -> IncrementalCapexResult:
    """Sec 22/28: TOTAL_INCREMENTAL_CAPEX = sum of charged CapEx across records.
    Inherited/retained/out-of-scope objects contribute $0 new CapEx but their
    excluded acquisition value is disclosed (never hidden). Unknown costs are
    listed separately, never $0-filled into the total (Sec 39)."""
    total = 0.0
    by_state: dict[AssetEconomicState, float] = {s: 0.0 for s in CANONICAL_ASSET_ECONOMIC_STATES}
    inherited_excluded = 0.0
    unknown: list[str] = []
    for rec in records:
        charged, _status, unk = rec.charged_capex()
        total += charged
        by_state[rec.economic_state] = by_state.get(rec.economic_state, 0.0) + charged
        unknown.extend(unk)
        # disclose the inherited/retained acquisition value that was NOT charged
        if rec.economic_state in ("INHERITED_EXISTING", "RETAINED_NO_CHANGE") and rec.full_acquisition_capex_usd:
            inherited_excluded += rec.full_acquisition_capex_usd
    return IncrementalCapexResult(
        project_class=project_class,
        total_incremental_capex_usd=total,
        charged_by_state={s: v for s, v in by_state.items()},
        inherited_asset_value_excluded_usd=inherited_excluded,
        unknown_capex_components=tuple(unknown),
        records=tuple(records),
    )


# ===========================================================================
# 8. OPEX inheritance authority (Sec 39). Baseline vs incremental; savings
#    preserved (negative incremental); no-silent-zero; NOT_CALIBRATED kept.
# ===========================================================================

@dataclass(frozen=True)
class OpexInheritanceRecord:
    """One recurring-cost asset's OPEX under baseline and target. `None` means
    NOT_CALIBRATED (never assumed $0, Sec 39). `displaced_baseline_opex` is the
    baseline OPEX a REPLACE removes (so incremental = new - displaced)."""

    asset_id: str
    economic_state: AssetEconomicState
    baseline_annual_opex_usd: float | None = None
    target_annual_opex_usd: float | None = None

    def __post_init__(self) -> None:
        # NEW assets have no baseline; REMOVE assets have no target -- allowed None.
        pass


# Clarification B: ONE underlying unknown keeps ONE identity even when it
# appears in multiple reporting views. `source_asset_id` + the unknown KIND
# (baseline / target / incremental) identify the underlying uncertainty; the
# `reporting_view` is a label only. Distinct-source counting (never per-view
# counting) is used for any economic total.
@dataclass(frozen=True)
class UnknownOpexComponent:
    component_id: str        # stable: f"{source_asset_id}:{kind}"
    source_asset_id: str
    kind: Literal["BASELINE", "TARGET", "INCREMENTAL"]
    reporting_view: str      # human-readable view label (traceability only)


@dataclass(frozen=True)
class OpexInheritanceResult:
    existing_baseline_opex_usd: float | None
    retained_existing_opex_usd: float | None
    removed_existing_opex_usd: float | None
    new_asset_opex_usd: float | None
    modification_delta_opex_usd: float | None
    replacement_delta_opex_usd: float | None
    target_total_opex_usd: float | None
    incremental_project_opex_usd: float | None
    unknown_baseline_components: tuple[str, ...]      # reporting-view labels (traceability)
    unknown_incremental_components: tuple[str, ...]   # reporting-view labels (traceability)
    unknown_components: tuple[UnknownOpexComponent, ...]  # identity-preserving records
    opex_savings_present: bool
    reconciled: bool

    def distinct_unknown_source_ids(self) -> tuple[str, ...]:
        """Clarification B: the set of underlying uncertain SOURCES (by
        source_asset_id + kind), each counted ONCE regardless of how many
        reporting views mention it. This is what any economic total must use --
        never len(unknown_baseline_components)+len(unknown_incremental_components)."""
        return tuple(sorted({c.component_id for c in self.unknown_components}))

    def distinct_unknown_count(self) -> int:
        return len(self.distinct_unknown_source_ids())


def _add(acc: float | None, val: float | None, unknown_sink: list[str], label: str,
         *, source_asset_id: str | None = None, kind: str | None = None,
         component_sink: list[UnknownOpexComponent] | None = None) -> float | None:
    """Sum that preserves NOT_CALIBRATED: if a needed value is unknown, record
    it and keep the running total as a known-subtotal (never treat unknown as 0
    silently). Clarification B: also record an identity-preserving
    UnknownOpexComponent so the same underlying uncertainty (source_asset_id +
    kind) is de-dupable across reporting views rather than triple-counted."""
    if val is None:
        unknown_sink.append(label)
        if component_sink is not None and source_asset_id is not None and kind is not None:
            component_sink.append(UnknownOpexComponent(
                component_id=f"{source_asset_id}:{kind}", source_asset_id=source_asset_id,
                kind=kind, reporting_view=label,  # type: ignore[arg-type]
            ))
        return acc  # do not add a fabricated 0
    return (acc or 0.0) + val


def compute_opex_inheritance(records: Sequence[OpexInheritanceRecord]) -> OpexInheritanceResult:
    """Sec 39: decompose OPEX into baseline vs incremental.

    TARGET_TOTAL_OPEX = RETAINED_EXISTING + NEW + MODIFICATION_DELTA
                        + REPLACEMENT_NEW - REMOVED_EXISTING (savings via deltas).
    INCREMENTAL_PROJECT_OPEX = NEW + MODIFICATION_DELTA + REPLACEMENT_DELTA
                               - REMOVED_EXISTING.

    Inherited/retained baseline OPEX is NOT recharged as new (Sec 39). A REPLACE
    displaces its baseline OPEX so its incremental may be NEGATIVE (a saving). A
    MODIFY that lowers OPEX yields a negative modification delta (a saving).
    Unknown OPEX is surfaced, never $0-filled."""
    unknown_base: list[str] = []
    unknown_inc: list[str] = []
    unknown_components: list[UnknownOpexComponent] = []

    existing_baseline: float | None = None
    retained_existing: float | None = None
    removed_existing: float | None = None
    new_opex: float | None = None
    modification_delta: float | None = None
    replacement_delta: float | None = None
    target_total: float | None = None
    incremental: float | None = None

    for r in records:
        st = r.economic_state
        if st in ("INHERITED_EXISTING", "RETAINED_NO_CHANGE"):
            # Clarification B: ONE uncertainty (this asset's baseline OPEX) may
            # appear in baseline/retained/target reporting views, but it is the
            # SAME source (asset_id + BASELINE kind) -- recorded ONCE in
            # unknown_components so it is never counted 3x economically.
            existing_baseline = _add(existing_baseline, r.baseline_annual_opex_usd, unknown_base,
                                     f"{r.asset_id} baseline OPEX", source_asset_id=r.asset_id, kind="BASELINE",
                                     component_sink=unknown_components)
            retained_existing = _add(retained_existing, r.baseline_annual_opex_usd, unknown_base, f"{r.asset_id} retained OPEX")
            # retained target opex = baseline (no change) or explicit target if supplied
            tgt = r.target_annual_opex_usd if r.target_annual_opex_usd is not None else r.baseline_annual_opex_usd
            target_total = _add(target_total, tgt, unknown_base, f"{r.asset_id} target OPEX")
        elif st == "NEW":
            # ONE uncertainty (this asset's target OPEX) across new/target/incremental views.
            new_opex = _add(new_opex, r.target_annual_opex_usd, unknown_inc, f"{r.asset_id} new OPEX",
                            source_asset_id=r.asset_id, kind="TARGET", component_sink=unknown_components)
            target_total = _add(target_total, r.target_annual_opex_usd, unknown_inc, f"{r.asset_id} new target OPEX")
            incremental = _add(incremental, r.target_annual_opex_usd, unknown_inc, f"{r.asset_id} new incremental OPEX")
        elif st == "MODIFY":
            existing_baseline = _add(existing_baseline, r.baseline_annual_opex_usd, unknown_base, f"{r.asset_id} baseline OPEX")
            if r.baseline_annual_opex_usd is not None and r.target_annual_opex_usd is not None:
                delta = r.target_annual_opex_usd - r.baseline_annual_opex_usd
                modification_delta = (modification_delta or 0.0) + delta
                incremental = (incremental or 0.0) + delta
                target_total = _add(target_total, r.target_annual_opex_usd, unknown_base, f"{r.asset_id} target OPEX")
            else:
                unknown_inc.append(f"{r.asset_id} modification delta OPEX")
                unknown_components.append(UnknownOpexComponent(f"{r.asset_id}:INCREMENTAL", r.asset_id, "INCREMENTAL", f"{r.asset_id} modification delta OPEX"))
                target_total = _add(target_total, r.target_annual_opex_usd, unknown_base, f"{r.asset_id} target OPEX")
        elif st == "REPLACE":
            # displaced baseline leaves; replacement enters -> incremental = new - displaced
            existing_baseline = _add(existing_baseline, r.baseline_annual_opex_usd, unknown_base, f"{r.asset_id} baseline OPEX")
            if r.baseline_annual_opex_usd is not None and r.target_annual_opex_usd is not None:
                delta = r.target_annual_opex_usd - r.baseline_annual_opex_usd
                replacement_delta = (replacement_delta or 0.0) + delta
                incremental = (incremental or 0.0) + delta
                target_total = _add(target_total, r.target_annual_opex_usd, unknown_inc, f"{r.asset_id} replacement target OPEX")
            else:
                unknown_inc.append(f"{r.asset_id} replacement delta OPEX")
                unknown_components.append(UnknownOpexComponent(f"{r.asset_id}:INCREMENTAL", r.asset_id, "INCREMENTAL", f"{r.asset_id} replacement delta OPEX"))
        elif st == "REMOVE":
            existing_baseline = _add(existing_baseline, r.baseline_annual_opex_usd, unknown_base, f"{r.asset_id} baseline OPEX",
                                     source_asset_id=r.asset_id, kind="BASELINE", component_sink=unknown_components)
            removed_existing = _add(removed_existing, r.baseline_annual_opex_usd, unknown_inc, f"{r.asset_id} removed OPEX")
            # removal reduces incremental (a saving) and does not contribute to target
            if r.baseline_annual_opex_usd is not None:
                incremental = (incremental or 0.0) - r.baseline_annual_opex_usd
        elif st == "OUT_OF_SCOPE":
            # excluded from project economics entirely (Sec 15)
            continue

    savings_present = (incremental is not None and incremental < 0) or (
        replacement_delta is not None and replacement_delta < 0
    ) or (modification_delta is not None and modification_delta < 0)

    reconciled = not unknown_base and not unknown_inc

    return OpexInheritanceResult(
        existing_baseline_opex_usd=existing_baseline,
        retained_existing_opex_usd=retained_existing,
        removed_existing_opex_usd=removed_existing,
        new_asset_opex_usd=new_opex,
        modification_delta_opex_usd=modification_delta,
        replacement_delta_opex_usd=replacement_delta,
        target_total_opex_usd=target_total,
        incremental_project_opex_usd=incremental,
        unknown_baseline_components=tuple(unknown_base),
        unknown_incremental_components=tuple(unknown_inc),
        unknown_components=tuple(unknown_components),
        opex_savings_present=savings_present,
        reconciled=reconciled,
    )


# ===========================================================================
# 9. Transport resource inheritance (Sec 34-38). Existing installed transport
#    infrastructure is inherited (not re-bought); only incremental is charged.
# ===========================================================================

@dataclass(frozen=True)
class TransportResourceInheritance:
    resource: str  # e.g. "PTS stations", "AGV vehicles", "MRT guideway (m)"
    existing_quantity: int
    retained_quantity: int
    removed_quantity: int
    target_required_quantity: int
    unit_capex_usd: float | None = None
    shared_backbone_exists: bool = False  # e.g. inherited PTS backbone / AGV fleet-manager

    def __post_init__(self) -> None:
        if self.retained_quantity > self.existing_quantity:
            raise ValueError("retained cannot exceed existing")
        if self.removed_quantity > self.existing_quantity:
            raise ValueError("removed cannot exceed existing")


@dataclass(frozen=True)
class TransportInheritanceResult:
    resource: str
    existing_quantity: int
    retained_quantity: int
    removed_quantity: int
    target_required_quantity: int
    new_quantity: int
    replacement_quantity: int
    modified_quantity: int
    incremental_capex_usd: float | None
    incremental_capex_status: str
    shared_backbone_reused: bool


def compute_transport_inheritance(inp: TransportResourceInheritance, *, shared_backbone_capex_usd: float | None = None) -> TransportInheritanceResult:
    """Sec 36-38: inherited usable transport capacity contributes toward target;
    only the shortfall is NEW. An inherited shared backbone (PTS tube / AGV
    fleet-manager) is reused, not re-charged, unless expansion is required
    (Sec 37)."""
    new_quantity = max(inp.target_required_quantity - inp.retained_quantity, 0)
    # shared backbone: charged only if it does NOT already exist (Sec 37).
    backbone_reused = inp.shared_backbone_exists
    if inp.unit_capex_usd is None:
        inc: float | None = None
        status = "NOT_CALIBRATED"
    else:
        inc = new_quantity * inp.unit_capex_usd
        if shared_backbone_capex_usd is not None and not backbone_reused:
            inc += shared_backbone_capex_usd
        status = "CALIBRATED_FROM_UNIT_COST"
    return TransportInheritanceResult(
        resource=inp.resource,
        existing_quantity=inp.existing_quantity,
        retained_quantity=inp.retained_quantity,
        removed_quantity=inp.removed_quantity,
        target_required_quantity=inp.target_required_quantity,
        new_quantity=new_quantity,
        replacement_quantity=0,
        modified_quantity=0,
        incremental_capex_usd=inc,
        incremental_capex_status=status,
        shared_backbone_reused=backbone_reused,
    )


# ===========================================================================
# 10. Transport PACKAGE reconciliation (clarification C). A transport family's
#     project CapEx is the reconciliation of its COMPLETE resource package
#     (backbone/blower/controls/switches/stations/carriers/track/guideway/
#     endpoints/vehicles/chargers/integration...), each line inherited-or-new,
#     with shared components reused (not re-purchased) unless an UPGRADE is
#     required. A single line (e.g. guideway) is NEVER the package total.
# ===========================================================================

TransportLineRole = Literal[
    "SHARED_BACKBONE",   # PTS tube backbone / AGV fleet-manager / RTHS controls / MRT controls
    "SHARED_CAPACITY",   # PTS blower / network capacity that may need UPGRADE
    "DISCRETE_UNIT",     # stations / carriers / vehicles / endpoints / switches
    "LINEAR",            # guideway (m) / track (m)
    "INTEGRATION",       # installation / door / elevator / penetration integration
]


@dataclass(frozen=True)
class TransportLineItem:
    """One reconciled line of a transport family's resource package."""

    line: str                      # e.g. "PTS backbone", "PTS blower capacity", "PTS stations", "MRT guideway (m)"
    role: TransportLineRole
    existing_quantity: float
    retained_quantity: float
    target_required_quantity: float
    unit_capex_usd: float | None = None
    shared_exists_in_baseline: bool = False      # for SHARED_* lines
    upgrade_required: bool = False               # SHARED_* insufficient capacity -> charge upgrade
    upgrade_capex_usd: float | None = None

    def __post_init__(self) -> None:
        if self.retained_quantity > self.existing_quantity:
            raise ValueError(f"{self.line}: retained cannot exceed existing")

    def charged_capex(self) -> tuple[float, str, tuple[str, ...]]:
        """Return (charged, status, unknown). Shared existing lines are reused
        ($0) unless an upgrade is required; discrete/linear lines charge only
        the shortfall (target - retained)."""
        unknown: list[str] = []
        if self.role in ("SHARED_BACKBONE", "SHARED_CAPACITY"):
            if self.shared_exists_in_baseline and not self.upgrade_required:
                return 0.0, "INHERITED_SHARED_REUSED", ()
            if self.upgrade_required:
                if self.upgrade_capex_usd is None:
                    return 0.0, "NOT_CALIBRATED", (f"{self.line} upgrade CapEx",)
                return self.upgrade_capex_usd, "SHARED_UPGRADE_REQUIRED", ()
            # shared does not exist in baseline -> full new shared component
            if self.unit_capex_usd is None:
                return 0.0, "NOT_CALIBRATED", (f"{self.line} new shared CapEx",)
            return self.unit_capex_usd, "NEW_SHARED_COMPONENT", ()
        # DISCRETE_UNIT / LINEAR / INTEGRATION: charge shortfall beyond retained
        shortfall = max(self.target_required_quantity - self.retained_quantity, 0.0)
        if self.unit_capex_usd is None:
            return 0.0, "NOT_CALIBRATED", (f"{self.line} incremental CapEx",)
        return shortfall * self.unit_capex_usd, "INCREMENTAL_SHORTFALL", ()


@dataclass(frozen=True)
class TransportPackageResult:
    family: str
    line_results: tuple[tuple[str, float, str], ...]  # (line, charged, status)
    known_incremental_capex_usd: float
    unknown_capex_components: tuple[str, ...]
    completeness: Literal["COMPLETE_PACKAGE", "PARTIAL_PACKAGE"]
    shared_lines_reused: tuple[str, ...]

    @property
    def is_total_project_capex(self) -> bool:
        """Clarification C: only a COMPLETE_PACKAGE reconciliation may be called
        the family's total project CapEx. A PARTIAL_PACKAGE never may."""
        return self.completeness == "COMPLETE_PACKAGE"


# The lines each family MUST reconcile for a COMPLETE_PACKAGE (clarification C).
REQUIRED_PACKAGE_LINES: Mapping[str, tuple[str, ...]] = {
    "PTS": ("PTS backbone", "PTS blower capacity", "PTS controls", "PTS switches/diverters", "PTS stations", "PTS carriers"),
    "RTHS": ("RTHS track", "RTHS stations", "RTHS switches", "RTHS vehicles", "RTHS controls", "RTHS vertical sections"),
    "AGV_AMR": ("AGV vehicles (light)", "AGV vehicles (heavy)", "AGV chargers", "AGV fleet-management platform", "AGV door integration", "AGV elevator integration", "AGV network/controls"),
    "MRT": ("MRT guideway (m)", "MRT carriers", "MRT endpoints", "MRT controls", "MRT installation/integration"),
}


def reconcile_transport_package(*, family: str, lines: Sequence[TransportLineItem]) -> TransportPackageResult:
    """Clarification C: reconcile a family's COMPLETE resource package. Sums the
    per-line charged CapEx (shared lines reused unless upgraded); flags whether
    the supplied lines COVER the required package (else PARTIAL_PACKAGE, which
    must never be labeled the total). Unknowns surfaced, never $0-filled."""
    total = 0.0
    line_results: list[tuple[str, float, str]] = []
    unknown: list[str] = []
    reused: list[str] = []
    supplied_lines = {li.line for li in lines}
    for li in lines:
        charged, status, unk = li.charged_capex()
        total += charged
        line_results.append((li.line, charged, status))
        unknown.extend(unk)
        if status == "INHERITED_SHARED_REUSED":
            reused.append(li.line)
    required = set(REQUIRED_PACKAGE_LINES.get(family, ()))
    completeness: Literal["COMPLETE_PACKAGE", "PARTIAL_PACKAGE"] = (
        "COMPLETE_PACKAGE" if required and required.issubset(supplied_lines) else "PARTIAL_PACKAGE"
    )
    return TransportPackageResult(
        family=family,
        line_results=tuple(line_results),
        known_incremental_capex_usd=total,
        unknown_capex_components=tuple(unknown),
        completeness=completeness,
        shared_lines_reused=tuple(reused),
    )


# ===========================================================================
# 11. Material/system economic-scope RUNTIME CONSUMER (clarification D). The
#     EconomicScopeSettings must actually GATE project cost while never
#     deleting the physical object / its capacity. This is the consumer that
#     proves the setting is not a dead backend object.
# ===========================================================================

@dataclass(frozen=True)
class ScopedAssetRecord:
    """An AssetEconomicRecord tagged with its material/system category and a
    PHYSICAL-PRESENCE flag distinct from ECONOMIC scope (clarification D/Sec 32)."""

    record: "AssetEconomicRecord"
    material_category: MaterialSystemCategory
    physically_present: bool = True
    contributes_operational_capacity: bool = True


@dataclass(frozen=True)
class ScopedCapexResult:
    total_project_capex_usd: float
    excluded_by_economic_scope_usd: float
    excluded_categories: tuple[MaterialSystemCategory, ...]
    physically_present_but_excluded: tuple[str, ...]  # asset_ids present yet cost-excluded
    unknown_capex_components: tuple[str, ...]


def apply_material_economic_scope(
    *, scoped_records: Sequence[ScopedAssetRecord], economic_scope: EconomicScopeSettings,
) -> ScopedCapexResult:
    """Clarification D: compute project CapEx while honoring material economic
    scope. A category set OFF is EXCLUDED FROM PROJECT COST but its objects
    remain physically present and keep operational capacity (never deleted).
    Turning a category ON restores its incremental (NEW/MODIFY) cost."""
    total = 0.0
    excluded_cost = 0.0
    excluded_cats: set[MaterialSystemCategory] = set()
    present_but_excluded: list[str] = []
    unknown: list[str] = []
    for sr in scoped_records:
        charged, _status, unk = sr.record.charged_capex()
        if economic_scope.material_in_economic_scope(sr.material_category):
            total += charged
            unknown.extend(unk)
        else:
            # economic OFF: cost excluded, physical object retained (Sec 32)
            excluded_cost += charged
            excluded_cats.add(sr.material_category)
            if sr.physically_present:
                present_but_excluded.append(sr.record.asset_id)
    return ScopedCapexResult(
        total_project_capex_usd=total,
        excluded_by_economic_scope_usd=excluded_cost,
        excluded_categories=tuple(sorted(excluded_cats)),
        physically_present_but_excluded=tuple(present_but_excluded),
        unknown_capex_components=tuple(unknown),
    )


# ===========================================================================
# 12. Expansion CONNECTION WORK (clarification E). Old building stays uncosted;
#     new wing + the connection work between old and new are charged. The
#     modification of the EXISTING building at the connection point is a MODIFY
#     (incremental) line, never a re-cost of the whole existing building.
# ===========================================================================

ConnectionWorkKind = Literal[
    "TRANSPORT_CONNECTION", "GUIDEWAY_EXTENSION", "TUBE_EXTENSION", "TRACK_EXTENSION",
    "UTILITY_CONNECTION", "ELECTRICAL_CONNECTION", "HVAC_CONNECTION", "NETWORK_CONTROLS_INTEGRATION",
    "PENETRATION_INTERFACE", "EXISTING_BUILDING_CONNECTION_MODIFICATION",
]


@dataclass(frozen=True)
class ConnectionWorkItem:
    kind: ConnectionWorkKind
    capex_usd: float | None
    # EXISTING_BUILDING_CONNECTION_MODIFICATION is a MODIFY on the inherited
    # building (incremental only); all others are NEW connection scope.
    economic_state: AssetEconomicState = "NEW"


@dataclass(frozen=True)
class ExpansionReconciliationResult:
    existing_building_charged_usd: float
    new_wing_charged_usd: float
    connection_work_charged_usd: float
    connection_work_items: tuple[tuple[str, float], ...]
    total_incremental_capex_usd: float
    unknown_capex_components: tuple[str, ...]
    existing_building_recharged: bool
    connection_work_identifiable: bool


def reconcile_expansion(
    *, existing_building: Sequence["AssetEconomicRecord"],
    new_wing: Sequence["AssetEconomicRecord"],
    connection_work: Sequence[ConnectionWorkItem],
) -> ExpansionReconciliationResult:
    """Clarification E: EXISTING building inherited ($0 new); NEW wing charged;
    connection work SEPARATELY identifiable. Existing-building connection-point
    changes are MODIFY (incremental), not a whole-building re-cost."""
    unknown: list[str] = []
    existing_charged = 0.0
    for r in existing_building:
        c, _s, u = r.charged_capex()
        existing_charged += c
        unknown.extend(u)
    new_charged = 0.0
    for r in new_wing:
        c, _s, u = r.charged_capex()
        new_charged += c
        unknown.extend(u)
    conn_items: list[tuple[str, float]] = []
    conn_charged = 0.0
    for w in connection_work:
        if w.capex_usd is None:
            unknown.append(f"{w.kind} connection CapEx")
            conn_items.append((w.kind, 0.0))
            continue
        conn_charged += w.capex_usd
        conn_items.append((w.kind, w.capex_usd))
    total = existing_charged + new_charged + conn_charged
    return ExpansionReconciliationResult(
        existing_building_charged_usd=existing_charged,
        new_wing_charged_usd=new_charged,
        connection_work_charged_usd=conn_charged,
        connection_work_items=tuple(conn_items),
        total_incremental_capex_usd=total,
        unknown_capex_components=tuple(unknown),
        existing_building_recharged=existing_charged > 0.0,
        connection_work_identifiable=len(conn_items) > 0,
    )


# ===========================================================================
# 13. Greenfield over-inheritance sentinel (clarification F). GREENFIELD must
#     NOT inherit any zero-cost building/equipment/transport from a baseline.
#     A deliberately reused external resource must be EXPLICITLY project-supplied.
# ===========================================================================

@dataclass(frozen=True)
class GreenfieldInheritanceAudit:
    zero_cost_inherited_assets: tuple[str, ...]
    explicitly_reused_external: tuple[str, ...]
    over_inheritance_detected: bool
    required_new_scope_costed: bool


def audit_greenfield_inheritance(
    *, records: Sequence["AssetEconomicRecord"],
    explicitly_reused_external_ids: frozenset[str] = frozenset(),
) -> GreenfieldInheritanceAudit:
    """Clarification F: flag any INHERITED_EXISTING/RETAINED_NO_CHANGE asset in a
    GREENFIELD project that is NOT an explicitly project-supplied reused external
    resource. Such silent inheritance is over-inheritance (a defect)."""
    zero_cost_inherited: list[str] = []
    reused: list[str] = []
    any_new_costed = False
    for r in records:
        if r.economic_state in ("INHERITED_EXISTING", "RETAINED_NO_CHANGE"):
            if r.asset_id in explicitly_reused_external_ids:
                reused.append(r.asset_id)
            else:
                zero_cost_inherited.append(r.asset_id)
        if r.economic_state == "NEW":
            charged, _s, _u = r.charged_capex()
            if charged > 0.0:
                any_new_costed = True
    return GreenfieldInheritanceAudit(
        zero_cost_inherited_assets=tuple(zero_cost_inherited),
        explicitly_reused_external=tuple(reused),
        over_inheritance_detected=len(zero_cost_inherited) > 0,
        required_new_scope_costed=any_new_costed,
    )
