"""Study Scope Architecture: CAPITAL_PLANNING vs OPERATIONAL_ONLY.

StudyScope and TransportArchitecture are independent, composable axes.
StudyScope never removes physical assets/capacity/scheduling/staffing -- it
only controls whether NEW-PROJECT acquisition/construction CapEx enters the
study objective.

AUDIT (section 2): the repository already has a validated existing-asset
mechanism -- decision_pipeline.NativePathwayScenario /
infrastructure_capex.InfrastructureCapexInputs's `deployment_mode` +
`existing_*_units` fields (installed - existing = charged NEW capex quantity,
already reused via `_incremental_quantity`). OPERATIONAL_ONLY is implemented
by REUSING this mechanism (existing_X = installed_X for every asset category)
rather than inventing a second project-mode concept. The one genuine gap
found: `existing_mrt_carriers` did not exist on NativePathwayScenario (hard-
coded to 0 in decision_pipeline._build_capex_inputs) -- added as a proper
field (default 0, preserving all CAPITAL_PLANNING behavior unchanged) so MRT
carriers can also be marked pre-installed for OPERATIONAL_ONLY studies.

For Hybrid (whose CapEx is a flat formula in hybrid_optimization.py, not
routed through the installed/existing ledger mechanism), OPERATIONAL_ONLY is
applied at this layer: `study_capex = 0.0`, with the full computed CapEx
preserved separately as `installed_asset_reference_capex` for provenance
(section 18/19/20 -- asset value is not physically zero merely because study
CapEx is excluded).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

StudyScope = Literal["CAPITAL_PLANNING", "OPERATIONAL_ONLY"]
TransportArchitecture = Literal["CONVENTIONAL", "MRT", "HYBRID"]


@dataclass(frozen=True)
class StudyScopeEconomicResult:
    study_scope: StudyScope
    transport_architecture: TransportArchitecture
    qualified_throughput: int
    study_capex: float
    installed_asset_reference_capex: float
    annual_opex: float
    qualified_annual_value: float
    annual_operating_margin: float
    opex_per_qualified_patient: float | None
    capital_project_npv: float | None
    operating_horizon_present_value: float


def apply_study_scope(
    *,
    study_scope: StudyScope,
    transport_architecture: TransportArchitecture,
    qualified_throughput: int,
    reference_capex: float,
    annual_opex: float,
    revenue_per_scan: float,
    operating_days_per_year: int,
    discount_rate_pct: float,
    analysis_years: int,
) -> StudyScopeEconomicResult:
    """Section 3/6/7/18/21-24: ONE authoritative composition point. Physical
    quantities (qualified_throughput, annual_opex) must already reflect the
    installed/operational configuration and are never altered here -- this
    function only governs whether `reference_capex` enters the study
    objective as `study_capex`."""
    if study_scope not in ("CAPITAL_PLANNING", "OPERATIONAL_ONLY"):
        raise ValueError("study_scope must be CAPITAL_PLANNING or OPERATIONAL_ONLY")

    study_capex = 0.0 if study_scope == "OPERATIONAL_ONLY" else float(reference_capex)
    qualified_annual_value = qualified_throughput * revenue_per_scan * operating_days_per_year
    annual_operating_margin = qualified_annual_value - annual_opex
    opex_per_qualified_patient = (
        annual_opex / (qualified_throughput * operating_days_per_year) if qualified_throughput > 0 else None
    )

    discount_rate = discount_rate_pct / 100.0
    net_cash_flow = qualified_annual_value - annual_opex
    present_value = -study_capex
    for year in range(1, int(analysis_years) + 1):
        present_value += net_cash_flow / ((1.0 + discount_rate) ** year)

    return StudyScopeEconomicResult(
        study_scope=study_scope,
        transport_architecture=transport_architecture,
        qualified_throughput=qualified_throughput,
        study_capex=study_capex,
        installed_asset_reference_capex=float(reference_capex),
        annual_opex=annual_opex,
        qualified_annual_value=qualified_annual_value,
        annual_operating_margin=annual_operating_margin,
        opex_per_qualified_patient=opex_per_qualified_patient,
        capital_project_npv=(present_value if study_scope == "CAPITAL_PLANNING" else None),
        # Distinct name (section 24): meaningful under either scope, but the
        # primary operational metric under OPERATIONAL_ONLY (study_capex=0).
        operating_horizon_present_value=present_value,
    )


def build_installed_existing_pathway_scenario(pathway_layout: object) -> tuple[object, object]:
    """Section 8-15/41: derive the OPERATIONAL_ONLY (INSTALLED_EXISTING)
    variant of a pure Conventional/MRT candidate by reusing spatial_benchmark's
    validated pathway-scenario builder, then marking every asset category as
    fully existing (existing_X = installed/operated X) via the repository's
    established existing_facility_expansion mechanism -- never a new,
    parallel project-mode concept. Physical capacity/scheduling/staffing/
    retention are entirely unaffected (OPEX inputs use `operated_*`, not
    `existing_*`); only CapEx-relevant `existing_*` fields change.
    Returns (conventional_scenario, mrt_scenario) mirroring
    spatial_benchmark._build_pathway_scenarios's return shape.
    """
    from spatial_benchmark import _build_pathway_scenarios

    conventional, mrt = _build_pathway_scenarios(pathway_layout)

    operational_conventional = replace(
        conventional,
        deployment_mode="existing_facility_expansion",
        existing_scanners=conventional.scanners,
        existing_injection_resources=conventional.injection_resources,
        existing_uptake_resources=conventional.uptake_resources,
        existing_cyclotron_units=conventional.installed_cyclotron_units,
        existing_radiopharmacy_units=conventional.installed_radiopharmacy_units,
        existing_conventional_infrastructure_allowance_units=conventional.conventional_infrastructure_allowance_units,
    )
    operational_mrt = replace(
        mrt,
        deployment_mode="existing_facility_expansion",
        existing_scanners=mrt.scanners,
        existing_injection_resources=mrt.injection_resources,
        existing_uptake_resources=mrt.uptake_resources,
        existing_cyclotron_units=mrt.installed_cyclotron_units,
        existing_radiopharmacy_units=mrt.installed_radiopharmacy_units,
        existing_mrt_base_infrastructure_units=mrt.installed_mrt_base_infrastructure_units,
        existing_mrt_endpoints=mrt.installed_mrt_endpoints,
        existing_guideway_length_m=mrt.installed_guideway_length_m,
        existing_vertical_transitions=mrt.installed_vertical_transitions,
        existing_building_connections=mrt.installed_building_connections,
        existing_mrt_carriers=(mrt.installed_mrt_carriers or 0),
    )
    return operational_conventional, operational_mrt
