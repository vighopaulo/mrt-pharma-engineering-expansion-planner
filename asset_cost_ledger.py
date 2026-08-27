"""Pre-BOM/BOQ physical asset cost ledger and asset register (Phase 13 audit).

This module does NOT recompute any economics. It exposes the ALREADY validated,
ALREADY reconciled `InfrastructureCapexResult.ledger` / `InfrastructureOpexResult.ledger`
(both mathematically guaranteed by construction to sum to `total_capex` /
`total_annual_opex` -- see infrastructure_capex.py/_ledger_item and
infrastructure_opex.py) in a unified, forward-compatible schema that a future
BIM/IFC and downloadable BOM/BOQ report can consume: asset_category, asset_type,
building_id, quantity, unit, unit_cost, currency, extended_cost, cost_class,
provenance, pathway, notes.

Provenance is reported per repository-documented cost_basis strings already
attached to each ledger line (see PROVENANCE_BY_COMPONENT below) -- no new
costs, rates, or vendor prices are invented here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from decision_pipeline import NativePathwayResult
    from spatial_benchmark import CandidateOutcome, Pathway

CostClass = Literal["CAPEX", "OPEX"]
Provenance = Literal[
    "SOURCE_BACKED",
    "PROJECT_ASSUMPTION",
    "SYNTHETIC_BENCHMARK_ASSUMPTION",
    "DERIVED_CALCULATION",
    "LEGACY_COMPATIBILITY",
]
InterventionState = Literal["EXISTING_RETAIN", "EXISTING_MODIFY", "EXISTING_REMOVE", "NEW_ADD"]
AssetEconomicClassification = Literal[
    "CAPEX_ONLY", "OPEX_ONLY", "CAPEX_AND_OPEX", "NO_DIRECT_COST_JUSTIFIED", "MISSING_ECONOMIC_TREATMENT"
]

DEFAULT_BUILDING_ID = "BLDG-001"  # forward-compat placeholder (section 29); this benchmark is single-building.
DEFAULT_CURRENCY = "USD"  # section 7: preserve USD as the current project currency.

# Every CapEx/OPEX ledger component name currently produced by
# infrastructure_capex.py / infrastructure_opex.py, classified by provenance
# (section 5). None of these are claimed SOURCE_BACKED (vendor-quoted) unless
# the repository actually cites a source -- none currently do, so all rate
# assumptions here are PROJECT_ASSUMPTION (internal project planning figures).
PROVENANCE_BY_COMPONENT: dict[str, Provenance] = {
    "Scanners": "PROJECT_ASSUMPTION",
    "Injection resources": "PROJECT_ASSUMPTION",  # $25,000 additional_room_capex; see section 21 classification below.
    "Uptake resources": "PROJECT_ASSUMPTION",
    "Cyclotron purchase": "PROJECT_ASSUMPTION",
    "Cyclotron installation": "PROJECT_ASSUMPTION",
    "Radiopharmacy infrastructure": "PROJECT_ASSUMPTION",
    "Conventional infrastructure allowance": "PROJECT_ASSUMPTION",
    "MRT base infrastructure": "PROJECT_ASSUMPTION",
    "MRT endpoints": "PROJECT_ASSUMPTION",
    "MRT carriers": "PROJECT_ASSUMPTION",
    "MRT guideway": "PROJECT_ASSUMPTION",
    "Vertical transitions": "PROJECT_ASSUMPTION",
    "Building connections": "PROJECT_ASSUMPTION",
    "Scanner annual O&M": "PROJECT_ASSUMPTION",
    "Injection resource annual O&M": "PROJECT_ASSUMPTION",
    "Uptake resource annual O&M": "PROJECT_ASSUMPTION",
    "Cyclotron annual fixed O&M": "PROJECT_ASSUMPTION",
    "Radiopharmacy annual fixed O&M": "PROJECT_ASSUMPTION",
    "Production variable cost": "DERIVED_CALCULATION",
    "Scanner energy": "PROJECT_ASSUMPTION",
    "Cyclotron energy": "PROJECT_ASSUMPTION",
    "Other energy": "PROJECT_ASSUMPTION",
    "Clinical labor": "PROJECT_ASSUMPTION",
    "Production labor": "PROJECT_ASSUMPTION",
    "Consumables": "PROJECT_ASSUMPTION",
    "Conventional transport and handling allowance": "PROJECT_ASSUMPTION",
    "Conventional transport labor": "PROJECT_ASSUMPTION",
    "MRT energy": "PROJECT_ASSUMPTION",
    "MRT base annual O&M": "PROJECT_ASSUMPTION",
    "MRT endpoint annual O&M": "PROJECT_ASSUMPTION",
    "Guideway annual maintenance": "PROJECT_ASSUMPTION",
    "Vertical transition annual maintenance": "PROJECT_ASSUMPTION",
    "Building connection annual maintenance": "PROJECT_ASSUMPTION",
    "MRT support labor": "PROJECT_ASSUMPTION",
    "MRT carrier allocated electricity": "PROJECT_ASSUMPTION",
    "MRT carrier maintenance": "PROJECT_ASSUMPTION",
}

# section 21: classify what additional_room_capex ($25,000) represents. It is
# used identically for injection and uptake rooms in the existing repository
# code with no BIM/BOQ backing -- a generic incremental allowance, not a
# full-room or explicitly-scoped retrofit figure. Retained for regression
# compatibility; flagged for future calibration.
ADDITIONAL_ROOM_CAPEX_CLASSIFICATION = "C. GENERIC_INCREMENTAL_ROOM_ALLOWANCE"
ADDITIONAL_ROOM_CAPEX_NOTE = "REQUIRES_BIM_BOQ_CALIBRATION"

# section 8: MRT carrier acquisition CapEx audit verdict, confirmed by direct
# code trace of infrastructure_capex.py (_ledger_item("MRT carriers", quantity=
# charged_carriers, unit_cost=assumptions.mrt_carrier_capex_per_installed_unit))
# and by the existing test test_mrt_transport_separation_integration.py::
# test_mrt_economics_carrier_capex_and_opex_scale_with_carriers (1 carrier ->
# $10,000; 4 carriers -> $40,000; both carrier maintenance and allocated
# electricity OPEX also scale with carrier count).
CARRIER_CAPEX_AUDIT_CLASSIFICATION = "A. CARRIER_CAPEX_ALREADY_EXPLICIT"


@dataclass(frozen=True)
class AssetCostLedgerEntry:
    """One pre-BOM/BOQ cost line (section 6)."""

    asset_category: str
    asset_type: str
    asset_group: str
    building_id: str
    quantity: float
    unit: str
    unit_cost: float
    currency: str
    extended_cost: float
    cost_class: CostClass
    provenance: Provenance
    source_reference: str
    pathway: "Pathway"
    notes: str


def _asset_category_for_component(component: str) -> str:
    if component.startswith("MRT") or component in {"Vertical transitions", "Building connections", "Guideway annual maintenance"}:
        return "MRT"
    if component.startswith("Conventional"):
        return "CONVENTIONAL_TRANSPORT"
    if component.startswith("Cyclotron") or component == "Radiopharmacy infrastructure" or component == "Radiopharmacy annual fixed O&M":
        return "CYCLOTRON_PRODUCTION"
    if component in {"Scanners", "Scanner annual O&M", "Scanner energy"}:
        return "CLINICAL_SCANNER"
    if component in {"Injection resources", "Injection resource annual O&M"}:
        return "CLINICAL_INJECTION_ROOM"
    if component in {"Uptake resources", "Uptake resource annual O&M"}:
        return "CLINICAL_UPTAKE_ROOM"
    return "OTHER"


def build_asset_cost_ledger(
    pathway_result: "NativePathwayResult",
    *,
    pathway: "Pathway",
    building_id: str = DEFAULT_BUILDING_ID,
) -> tuple[AssetCostLedgerEntry, ...]:
    """Enrich the EXISTING, already-reconciled CapEx/OPEX ledgers into the
    unified pre-BOM schema. No cost is recomputed; every extended_cost is read
    directly from the authoritative ledger line's subtotal/annual_cost.
    """
    entries: list[AssetCostLedgerEntry] = []
    for item in pathway_result.capex_result.ledger:
        entries.append(
            AssetCostLedgerEntry(
                asset_category=_asset_category_for_component(item.component),
                asset_type=item.component,
                asset_group=item.category,
                building_id=building_id,
                quantity=float(item.quantity),
                unit=item.unit,
                unit_cost=float(item.unit_cost),
                currency=DEFAULT_CURRENCY,
                extended_cost=float(item.subtotal),
                cost_class="CAPEX",
                provenance=PROVENANCE_BY_COMPONENT.get(item.component, "LEGACY_COMPATIBILITY"),
                source_reference=item.cost_basis,
                pathway=pathway,
                notes=(ADDITIONAL_ROOM_CAPEX_NOTE if item.component in {"Injection resources", "Uptake resources"} else ""),
            )
        )
    for item in pathway_result.opex_result.ledger:
        entries.append(
            AssetCostLedgerEntry(
                asset_category=_asset_category_for_component(item.component),
                asset_type=item.component,
                asset_group=item.category,
                building_id=building_id,
                quantity=float(item.quantity),
                unit=item.unit,
                unit_cost=float(item.unit_cost),
                currency=DEFAULT_CURRENCY,
                extended_cost=float(item.annual_cost),
                cost_class="OPEX",
                provenance=PROVENANCE_BY_COMPONENT.get(item.component, "LEGACY_COMPATIBILITY"),
                source_reference=item.cost_basis,
                pathway=pathway,
                notes="",
            )
        )
    return tuple(entries)


def reconcile_capex_ledger(
    ledger: tuple[AssetCostLedgerEntry, ...], reported_total_capex: float, *, tolerance: float = 1e-6
) -> tuple[bool, float]:
    """Section 31/44: SUM(CAPEX ledger lines) must equal reported total CapEx."""
    ledger_total = sum(entry.extended_cost for entry in ledger if entry.cost_class == "CAPEX")
    diff = abs(ledger_total - reported_total_capex)
    return diff <= tolerance, diff


def reconcile_opex_ledger(
    ledger: tuple[AssetCostLedgerEntry, ...], reported_annual_opex: float, *, tolerance: float = 1e-6
) -> tuple[bool, float]:
    """Section 32/45: SUM(annual OPEX ledger lines) must equal reported annual OPEX."""
    ledger_total = sum(entry.extended_cost for entry in ledger if entry.cost_class == "OPEX")
    diff = abs(ledger_total - reported_annual_opex)
    return diff <= tolerance, diff


@dataclass(frozen=True)
class AssetRegisterEntry:
    """Physical asset inventory line (section 28), separate from cost -- this
    is what a future BIM object list would map onto.
    """

    asset_id: str
    asset_type: str
    pathway: "Pathway"
    quantity: float
    location: str
    intervention_state: InterventionState
    economic_classification: AssetEconomicClassification


def build_asset_register(outcome: "CandidateOutcome") -> tuple[AssetRegisterEntry, ...]:
    """Physical asset inventory for one winning candidate (section 3/28).
    Existing/new status: CY-001 and the production/radiopharmacy allowance are
    modeled as NEW project CapEx in every spatial_benchmark.py candidate (see
    installed_cyclotron_units=1, existing_cyclotron_units=0) -- i.e. this
    benchmark treats the cyclotron as newly acquired for the project, not a
    pre-existing zero-cost asset (section 19/41).
    """
    pathway = outcome.pathway
    layout = outcome.layout
    entries = [
        AssetRegisterEntry(
            asset_id="CY-001", asset_type="Cyclotron", pathway=pathway, quantity=1,
            location=DEFAULT_BUILDING_ID, intervention_state="NEW_ADD", economic_classification="CAPEX_AND_OPEX",
        ),
        AssetRegisterEntry(
            asset_id="SCANNERS", asset_type="Scanner", pathway=pathway, quantity=layout.scanners,
            location=DEFAULT_BUILDING_ID, intervention_state="NEW_ADD", economic_classification="CAPEX_AND_OPEX",
        ),
        AssetRegisterEntry(
            asset_id="INJECTION_ROOMS", asset_type="Injection room", pathway=pathway, quantity=layout.injection_resources,
            location=DEFAULT_BUILDING_ID, intervention_state="NEW_ADD", economic_classification="CAPEX_AND_OPEX",
        ),
        AssetRegisterEntry(
            asset_id="UPTAKE_ROOMS", asset_type="Uptake room", pathway=pathway, quantity=layout.uptake_resources,
            location=DEFAULT_BUILDING_ID, intervention_state="NEW_ADD", economic_classification="CAPEX_AND_OPEX",
        ),
    ]
    if pathway == "Conventional":
        entries.append(
            AssetRegisterEntry(
                asset_id="TRANSPORTERS", asset_type="Human transporter (labor resource)", pathway=pathway,
                quantity=outcome.manual_transporters, location=DEFAULT_BUILDING_ID,
                intervention_state="NEW_ADD", economic_classification="OPEX_ONLY",
            )
        )
    else:
        entries.extend(
            [
                AssetRegisterEntry(
                    asset_id="MRT_CARRIERS", asset_type="MRT carrier", pathway=pathway,
                    quantity=outcome.mrt_installed_carriers, location=DEFAULT_BUILDING_ID,
                    intervention_state="NEW_ADD", economic_classification="CAPEX_AND_OPEX",
                ),
                AssetRegisterEntry(
                    asset_id="MRT_GUIDEWAY_HORIZONTAL", asset_type="MRT horizontal guideway (m)", pathway=pathway,
                    quantity=layout.guideway_horizontal_length_m, location=DEFAULT_BUILDING_ID,
                    intervention_state="NEW_ADD", economic_classification="CAPEX_AND_OPEX",
                ),
                AssetRegisterEntry(
                    asset_id="MRT_GUIDEWAY_VERTICAL", asset_type="MRT vertical guideway (m)", pathway=pathway,
                    quantity=layout.guideway_vertical_length_m, location=DEFAULT_BUILDING_ID,
                    intervention_state="NEW_ADD", economic_classification="CAPEX_AND_OPEX",
                ),
                AssetRegisterEntry(
                    asset_id="MRT_TRANSITIONS", asset_type="MRT physical H<->V transitions", pathway=pathway,
                    quantity=layout.guideway_transition_count, location=DEFAULT_BUILDING_ID,
                    intervention_state="NEW_ADD", economic_classification="CAPEX_AND_OPEX",
                ),
                AssetRegisterEntry(
                    asset_id="MRT_ENDPOINTS", asset_type="MRT station/endpoint", pathway=pathway,
                    quantity=len(layout.destination_object_ids), location=DEFAULT_BUILDING_ID,
                    intervention_state="NEW_ADD", economic_classification="CAPEX_AND_OPEX",
                ),
            ]
        )
    return tuple(entries)


def build_finalist_unified_ledger(
    base_ledger: tuple[AssetCostLedgerEntry, ...],
    *,
    pathway: "Pathway",
    inbound_room_capex: float,
    inbound_room_annual_opex: float,
    inbound_mrt_guideway_capex: float,
    inbound_room_count: int,
    building_id: str = DEFAULT_BUILDING_ID,
) -> tuple[AssetCostLedgerEntry, ...]:
    """Section 32: combine the base architecture ledger (spatial candidate:
    scanners/injection/uptake/cyclotron/transporters-or-carriers/guideway) with
    the INCREMENTAL inbound-room-program ledger (inbound room CapEx/OPEX and,
    for MRT INTEGRATED destinations, incremental guideway/station extension)
    into one unified finalist ledger -- proving no overlap by construction:
    the base ledger's "Injection resources"/"Uptake resources"/"MRT guideway"
    lines price ONLY the shared candidate's own room/network counts (from
    spatial_benchmark.py's CandidateLayout), which never include inbound rooms
    or their guideway extension (those are computed separately in
    inbound_patient_program.py against a disjoint candidate_inbound_room_ids
    pool) -- so appending, rather than merging, is the correct, non-duplicating
    combination.
    """
    entries = list(base_ledger)
    if inbound_room_count > 0:
        entries.append(
            AssetCostLedgerEntry(
                asset_category="CLINICAL_INBOUND_ROOM",
                asset_type="Inbound rooms",
                asset_group="Clinical",
                building_id=building_id,
                quantity=float(inbound_room_count),
                unit="units",
                unit_cost=(inbound_room_capex / inbound_room_count) if inbound_room_count else 0.0,
                currency=DEFAULT_CURRENCY,
                extended_cost=inbound_room_capex,
                cost_class="CAPEX",
                provenance="PROJECT_ASSUMPTION",
                source_reference="InboundRoomEconomicAssumptions.room_capex_per_unit (reuses PlannerAssumptions.additional_room_capex)",
                pathway=pathway,
                notes=ADDITIONAL_ROOM_CAPEX_NOTE,
            )
        )
        entries.append(
            AssetCostLedgerEntry(
                asset_category="CLINICAL_INBOUND_ROOM",
                asset_type="Inbound room annual O&M",
                asset_group="Clinical",
                building_id=building_id,
                quantity=float(inbound_room_count),
                unit="units",
                unit_cost=(inbound_room_annual_opex / inbound_room_count) if inbound_room_count else 0.0,
                currency=DEFAULT_CURRENCY,
                extended_cost=inbound_room_annual_opex,
                cost_class="OPEX",
                provenance="PROJECT_ASSUMPTION",
                source_reference="InboundRoomEconomicAssumptions.room_annual_opex_per_unit",
                pathway=pathway,
                notes="",
            )
        )
    if pathway == "MRT" and inbound_mrt_guideway_capex > 0.0:
        entries.append(
            AssetCostLedgerEntry(
                asset_category="MRT",
                asset_type="MRT inbound guideway/station extension",
                asset_group="MRT",
                building_id=building_id,
                quantity=1.0,
                unit="lot",
                unit_cost=inbound_mrt_guideway_capex,
                currency=DEFAULT_CURRENCY,
                extended_cost=inbound_mrt_guideway_capex,
                cost_class="CAPEX",
                provenance="PROJECT_ASSUMPTION",
                source_reference="compute_inbound_room_guideway_extension (mrt_guideway_capex_per_m, vertical_transition_capex)",
                pathway=pathway,
                notes="Incremental network extension attributable solely to selected integrated inbound rooms.",
            )
        )
    return tuple(entries)

