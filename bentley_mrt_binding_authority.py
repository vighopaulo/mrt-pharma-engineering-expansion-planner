"""Bentley Live iModel -> MRT Pharma Binding Authority.

GOVERNING ARCHITECTURE:
  BENTLEY / iTWIN = BIM / spatial / geometry / element-identity / visualization
  MRT PHARMA      = engineering / clinical / nuclear / logistics / capacity /
                    optimization / CapEx / OPEX / project-inheritance authority.

Bentley reports SOURCE state. MRT Pharma decides ENGINEERING/ECONOMIC treatment.
This module is the deterministic binding seam between them. It COMPOSES existing
owners and NEVER duplicates them:
  * `bentley_itwin_client`          -- live read boundary (identity/metadata).
  * `canonical_spatial_authority`   -- ExternalReference + CanonicalSpatialObject.
  * `bentley_canonical_binding`     -- single-element bind-to-existing helper.
  * `capital_project_inheritance_authority` (Super-Build 3) -- economic states.

HARD DOCTRINES enforced here:
  * A Bentley object PRESENT in the iModel does NOT imply NEW project CapEx
    (Sec 15/38). Economic treatment is a SEPARATE MRT Pharma decision.
  * Display labels are NEVER primary identity (Sec 32). Stable Bentley
    identifiers (element/model/changeset/federation GUID) are the keys.
  * Source version (changeset) is preserved; a binding made against an older
    changeset can be detected STALE (Sec 36) -- never silently deleted.
  * A BIM-source deletion is NOT a capital-project REMOVE decision (Sec 37).
  * A Bentley geometry/property change does NOT auto-become MODIFY/REPLACE/NEW
    (Sec 38). Explicit reconciliation is required.

READ-ONLY: this module never writes to the live Bentley iModel. No secrets
are stored or printed here.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal, Mapping

import capital_project_inheritance_authority as cap

# ===========================================================================
# 1. Stable Bentley external reference (Sec 9/32). Identity from stable keys,
#    never the display label.
# ===========================================================================

SourcePlatform = Literal["BENTLEY_ITWIN"]


@dataclass(frozen=True)
class BentleyExternalReference:
    """Sec 9: the canonical external-reference record for a Bentley object.
    `element_id`/`model_id`/`changeset_id`/`federation_guid` are the stable
    identity keys. `label` is display-only and NEVER the binding key (Sec 32)."""

    itwin_id: str
    imodel_id: str
    changeset_id: str | None
    model_id: str | None
    element_id: str | None
    class_name: str | None
    federation_guid: str | None = None
    label: str | None = None  # display-only
    source_platform: SourcePlatform = "BENTLEY_ITWIN"
    source_provenance: str = "BENTLEY_ITWIN_LIVE_READ"

    def stable_identity_key(self) -> str | None:
        """Sec 32: the stable identity used for binding -- element_id preferred,
        federation_guid next, model_id last. Never the label."""
        return self.element_id or self.federation_guid or self.model_id

    def has_stable_identity(self) -> bool:
        return self.stable_identity_key() is not None


# ===========================================================================
# 2. Binding status vocabulary (Sec 14/36-37). No silent binding.
# ===========================================================================

BentleyBindingStatus = Literal[
    "BOUND",
    "UNBOUND",
    "IGNORED",
    "AMBIGUOUS",
    "UNSUPPORTED_CLASS",
    "MISSING_REQUIRED_PROPERTY",
    "STALE_SOURCE_VERSION",
    "SOURCE_ELEMENT_MISSING",
]

CANONICAL_BINDING_STATUSES: tuple[BentleyBindingStatus, ...] = (
    "BOUND", "UNBOUND", "IGNORED", "AMBIGUOUS", "UNSUPPORTED_CLASS",
    "MISSING_REQUIRED_PROPERTY", "STALE_SOURCE_VERSION", "SOURCE_ELEMENT_MISSING",
)

# EC classes MRT Pharma currently supports binding to an engineering object.
SUPPORTED_BINDABLE_CLASSES: frozenset[str] = frozenset({
    "IfcBuilding", "IfcBuildingStorey", "IfcSpace", "IfcWall", "IfcDoor",
    "IfcFurnishingElement", "IfcFlowTerminal", "IfcDistributionElement",
    "IfcTransportElement", "IfcSite", "PhysicalObject", "SpatialLocationElement",
})


# ===========================================================================
# 3. The binding record (Sec 13). Preserves Bentley identity + MRT identity +
#    source version + economic classification (via Super-Build 3).
# ===========================================================================

@dataclass(frozen=True)
class BentleyBinding:
    """Sec 13: one deterministic Bentley-object <-> MRT-Pharma-object binding.
    Carries BOTH the source (Bentley) identity/version AND the MRT Pharma
    engineering identity + economic classification. The economic classification
    is an INDEPENDENT MRT Pharma decision (Super-Build 3), never inferred from
    Bentley presence (Sec 15)."""

    external_reference: BentleyExternalReference
    mrt_object_id: str | None
    mrt_object_type: str | None
    binding_status: BentleyBindingStatus
    bound_at_changeset_id: str | None
    # Super-Build 3 economic classification (independent of Bentley presence).
    asset_classification: cap.AssetClassification | None = None
    detail: str = ""

    def economic_state(self) -> cap.AssetEconomicState | None:
        return self.asset_classification.economic_state if self.asset_classification else None

    def implies_new_capex(self) -> bool:
        """Sec 15/38: a bound Bentley object implies NEW CapEx ONLY if its
        MRT Pharma economic state is NEW/REPLACE -- NEVER because it is present
        in the iModel."""
        state = self.economic_state()
        return state is not None and cap.bim_object_charges_new_capex(state)


# ===========================================================================
# 4. Binding creation (Sec 13-16). Deterministic; no silent binding.
# ===========================================================================

def classify_bindability(ref: BentleyExternalReference) -> BentleyBindingStatus:
    """Sec 14: decide whether an element CAN be bound, before choosing an MRT
    object. Missing stable identity / unsupported class produce explicit
    non-BOUND statuses (never a silent guess)."""
    if not ref.has_stable_identity():
        return "MISSING_REQUIRED_PROPERTY"
    if ref.class_name is not None and ref.class_name not in SUPPORTED_BINDABLE_CLASSES:
        return "UNSUPPORTED_CLASS"
    return "UNBOUND"  # bindable, but not yet bound to an MRT object


def create_binding(
    *, external_reference: BentleyExternalReference, mrt_object_id: str | None,
    mrt_object_type: str | None = None,
    asset_classification: cap.AssetClassification | None = None,
    current_changeset_id: str | None = None,
) -> BentleyBinding:
    """Sec 13-16: create a binding from real Bentley metadata + an MRT object.

    - No stable identity -> MISSING_REQUIRED_PROPERTY.
    - Unsupported class -> UNSUPPORTED_CLASS.
    - No MRT object supplied -> UNBOUND (bindable but unbound; never silent).
    - Otherwise BOUND, recording the source changeset it was bound at.

    The `asset_classification` (Super-Build 3) is carried verbatim; a caller
    that supplies none leaves economic treatment UNDECIDED (never defaulted to
    NEW). Bentley presence NEVER sets NEW (Sec 15)."""
    bindability = classify_bindability(external_reference)
    if bindability in ("MISSING_REQUIRED_PROPERTY", "UNSUPPORTED_CLASS"):
        return BentleyBinding(
            external_reference=external_reference, mrt_object_id=None, mrt_object_type=None,
            binding_status=bindability, bound_at_changeset_id=external_reference.changeset_id,
            asset_classification=asset_classification,
            detail=f"not bound: {bindability}",
        )
    if mrt_object_id is None:
        return BentleyBinding(
            external_reference=external_reference, mrt_object_id=None, mrt_object_type=None,
            binding_status="UNBOUND", bound_at_changeset_id=external_reference.changeset_id,
            asset_classification=asset_classification,
            detail="bindable but no MRT engineering object supplied (never silently fabricated)",
        )
    return BentleyBinding(
        external_reference=external_reference, mrt_object_id=mrt_object_id, mrt_object_type=mrt_object_type,
        binding_status="BOUND", bound_at_changeset_id=external_reference.changeset_id or current_changeset_id,
        asset_classification=asset_classification, detail="bound to existing MRT engineering object",
    )


# ===========================================================================
# 5. Staleness + disappearance (Sec 36-37). Never auto-delete, never auto-REMOVE.
# ===========================================================================

def evaluate_source_version(binding: BentleyBinding, *, current_changeset_id: str | None) -> BentleyBinding:
    """Sec 36: if the live iModel has advanced past the changeset the binding
    was made at, mark STALE_SOURCE_VERSION -- do NOT delete the binding."""
    if binding.binding_status != "BOUND":
        return binding
    if (binding.bound_at_changeset_id is not None and current_changeset_id is not None
            and binding.bound_at_changeset_id != current_changeset_id):
        return replace(binding, binding_status="STALE_SOURCE_VERSION",
                       detail=f"bound at {binding.bound_at_changeset_id}, current {current_changeset_id} -- may be stale (not deleted)")
    return binding


def evaluate_element_presence(binding: BentleyBinding, *, element_present_in_current_source: bool,
                              current_changeset_id: str | None) -> BentleyBinding:
    """Sec 37: a bound element that no longer exists in the current source is
    SOURCE_ELEMENT_MISSING -- NOT automatically a project REMOVE. A BIM-source
    deletion and a capital-project removal decision are different concepts."""
    if element_present_in_current_source:
        return binding
    return replace(binding, binding_status="SOURCE_ELEMENT_MISSING",
                   bound_at_changeset_id=binding.bound_at_changeset_id,
                   detail=(f"source element absent at changeset {current_changeset_id} "
                           "-- classified SOURCE_ELEMENT_MISSING, NOT project REMOVE (Sec 37)"))


# ===========================================================================
# 6. Bentley change != project economic change (Sec 38). Explicit reconciliation.
# ===========================================================================

BentleySourceChange = Literal["ADDED", "GEOMETRY_CHANGED", "PROPERTY_CHANGED", "REMOVED", "UNCHANGED"]


@dataclass(frozen=True)
class SourceChangeReconciliation:
    source_change: BentleySourceChange
    proposed_project_action: cap.AssetProjectAction | None
    requires_explicit_decision: bool
    reason: str


def reconcile_source_change(source_change: BentleySourceChange) -> SourceChangeReconciliation:
    """Sec 38: a Bentley source change NEVER auto-maps to a project economic
    action. Every source change requires an EXPLICIT MRT Pharma decision; this
    function returns proposed_project_action=None and requires_explicit_decision
    =True for all economically-relevant changes (ADDED/GEOMETRY/PROPERTY/REMOVED)."""
    if source_change == "UNCHANGED":
        return SourceChangeReconciliation(source_change, None, False, "no source change; no reconciliation needed")
    return SourceChangeReconciliation(
        source_change, None, True,
        f"Bentley source change {source_change} does NOT imply a project economic action "
        "(NEW/MODIFY/REPLACE/REMOVE) -- explicit MRT Pharma reconciliation required (Sec 38)",
    )


def source_change_implies_project_action(source_change: BentleySourceChange) -> bool:
    """Hard governor: always False. Bentley source state never dictates project
    economics (Sec 38)."""
    return False
