"""Unified Constraint & Optimization Authority -- system-wide engineering
governance registry and validation layer.

GOVERNANCE BUILD, NOT A NEW PHYSICS ENGINE. This module never re-implements
production/transport/retention/clinical-scheduling physics; it only:
  1. registers WHO owns each governing quantity/constraint (machine-readable
     metadata, section 3);
  2. validates already-computed candidate/study results against those
     constraints, reusing existing authoritative engines and result objects;
  3. returns a structured AuthorityValidationResult distinguishing physical
     feasibility from architecture purity, economic reconciliation, patient
     traceability, room exclusivity, and conservation -- never collapsed into
     a single boolean (section 59).

Every AuthorityRule points to its actual authoritative module/function so
future builds (multi-radionuclide, six-month planning, BIM, UI) can look up
"who decides this" instead of re-deriving or silently duplicating it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, Sequence

AuthorityCategory = Literal[
    "PATIENT", "PRODUCTION", "CYCLOTRON", "RETENTION", "GEOMETRY", "TRANSPORT",
    "CLINICAL_FLOW", "ROOM", "INBOUND", "STAFFING", "ARCHITECTURE", "STUDY_SCOPE",
    "ASSET", "ECONOMIC", "OPTIMIZATION", "CONSERVATION", "TRACEABILITY",
]

AuthorityClassification = Literal[
    "AUTHORITATIVE", "DERIVED_VIEW", "DIAGNOSTIC_ONLY", "LEGACY_COMPATIBILITY",
    "PROJECT_ASSUMPTION", "REQUIRES_CALIBRATION", "DEPRECATED_ACTIVE_RISK",
]

Severity = Literal["INFO", "WARNING", "VIOLATION"]

# Section 55: valid optimization stop reasons. COMPUTATIONAL_SEARCH_LIMIT
# alone never proves optimality (section 54).
VALID_OPTIMIZATION_STOP_REASONS = frozenset({
    "DEMAND_SATURATED", "SPACE_EXHAUSTED", "PRODUCTION_LIMIT", "RETENTION_LIMIT",
    "DOWNSTREAM_BOTTLENECK", "NO_QUALIFIED_THROUGHPUT_GAIN", "NPV_DECLINED",
    "PHYSICAL_LIMIT", "CLINICAL_DAY_LIMIT", "STAFFING_LIMIT", "COMPUTATIONAL_SEARCH_LIMIT",
})
OPTIMALITY_NOT_PROVEN_STOP_REASONS = frozenset({"COMPUTATIONAL_SEARCH_LIMIT"})


@dataclass(frozen=True)
class AuthorityRule:
    authority_id: str
    category: AuthorityCategory
    authoritative_owner: str  # "module.py::function_or_class"
    description: str
    applies_to: tuple[str, ...]  # e.g. ("Conventional", "MRT", "Hybrid")
    severity: Severity
    validation_mechanism: str  # human-readable pointer to the check, if automated
    classification: AuthorityClassification = "AUTHORITATIVE"


# Section 6-58: the registry. Metadata only -- no physics reimplemented here.
AUTHORITY_REGISTRY: tuple[AuthorityRule, ...] = (
    AuthorityRule(
        "PATIENT_IDENTITY", "PATIENT", "patient_radionuclide_demand.py::PatientRadionuclideDemand.patient_id",
        "Every modeled patient has one authoritative patient_id that survives demand->production->payload->transport->clinical->retention->economics.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_patient_traceability()",
    ),
    AuthorityRule(
        "PATIENT_NEED", "PATIENT", "patient_radionuclide_demand.py::PatientRadionuclideDemand",
        "Patient-specific radionuclide/activity/type/LOS must not collapse to a generic dose count where patient-level data exists.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "manual/schema audit",
    ),
    AuthorityRule(
        "INBOUND_OUTPATIENT_TYPE", "INBOUND", "inbound_patient_program.py::attach_patient_type_and_los",
        "Every patient has one authoritative type (INBOUND_PATIENT or OUTPATIENT) that propagates to room occupancy, clinical pathway, production demand, staffing, retention, and economics.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_patient_traceability()",
    ),
    AuthorityRule(
        "PRODUCTION_CHAIN", "PRODUCTION", "cycle_relative_production_requirement.py::derive_cycle_relative_requirement",
        "PATIENT NEED -> required administered activity -> required release activity -> required EOB activity -> production cycle -> cyclotron feasibility.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "existing cycle_relative_production_requirement tests",
    ),
    AuthorityRule(
        "PATIENT_CYCLE_MEMBERSHIP", "PRODUCTION", "cycle_relative_production_requirement.py::CycleRelativeRequirementResult.cycle_usages",
        "Each production-served patient retains one finalized production-cycle membership; downstream scheduling may not silently repartition it.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_patient_traceability()",
    ),
    AuthorityRule(
        "CYCLOTRON_ACTIVITY_CAPACITY", "CYCLOTRON", "cyclotron_production_windows.py / decision_pipeline.py::_apply_production_activity_capacity_guard",
        "Required EOB activity per cycle <= calibrated EOB capacity per cycle; NOT_CALIBRATED cycles are not fabricated capacity.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "existing decision_pipeline activity-capacity guard",
    ),
    AuthorityRule(
        "CYCLOTRON_TEMPORAL_CAPACITY", "CYCLOTRON", "cyclotron_production_windows.py::schedule_cyclotron_fleet_production_windows",
        "Production cycles must fit cycle duration, production horizon, release processing, and simultaneous-stream constraints.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "existing production window scheduler",
    ),
    AuthorityRule(
        "PRODUCTION_GAPS", "PRODUCTION", "production_clinical_schedule.py::ProductionBatchReleaseMapping.release_time_minutes",
        "Radiopharmaceutical availability is discontinuous where production/release timing is discontinuous; clinical scheduling must not assume continuous dose availability.",
        ("Conventional", "MRT", "Hybrid"), "WARNING", "manual/diagnostic audit (see test_clinical_bottleneck_authority.py)",
    ),
    AuthorityRule(
        "MULTI_RADIONUCLIDE_FORWARD", "PRODUCTION", "multi_isotope_decay.py / cyclotron_production_windows.py",
        "Production requirements are radionuclide-specific; future multi-isotope demand must route P_i -> radionuclide_i -> radionuclide-specific production cycle, never a system-level 'all patients = F-18' rule.",
        ("Conventional", "MRT", "Hybrid"), "WARNING", "forward-compatibility audit only, not enforced today",
    ),
    AuthorityRule(
        "RETENTION_AUTHORITY", "RETENTION", "multi_isotope_decay.py::retained_fraction",
        "Retention threshold is applied via the authoritative decay engine using the radionuclide's half-life and actual elapsed release->administration time; never a hard-coded universal minute value.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "spatial_benchmark._retention_time_budget_minutes derives the budget fresh each time",
    ),
    AuthorityRule(
        "QUALIFIED_THROUGHPUT", "RETENTION", "spatial_benchmark.py::_operational_retention_metrics / hybrid_optimization.py",
        "Qualified success requires clinical completion AND retention >= threshold; clinical completion alone is not qualification.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_qualified_throughput_gating()",
    ),
    AuthorityRule(
        "CONVENTIONAL_GEOMETRY", "GEOMETRY", "spatial_benchmark.py::_route_metrics_for_rooms / compute_retention_envelope",
        "Conventional transport uses the actual network route graph (horizontal + vertical/elevator + handoff), never Euclidean distance or MRT timing.",
        ("Conventional",), "VIOLATION", "test_cluster_distribution_authority.test_retention_envelope_uses_network_route_not_euclidean",
    ),
    AuthorityRule(
        "CONVENTIONAL_DESIGN", "ARCHITECTURE", "spatial_benchmark.py::optimize_pathway_layouts",
        "Pure Conventional architecture emerges from retention geometry + operations/logistics + space + staffing + economics; CLUSTERED is an output classification only, never a ranking input.",
        ("Conventional",), "VIOLATION", "test_cluster_distribution_authority.test_spatial_form_classification_never_referenced_by_ranking_or_dominance",
    ),
    AuthorityRule(
        "MRT_TRANSPORT", "TRANSPORT", "production_clinical_schedule.py::_resolve_mrt_route_profile / _schedule_mrt_carrier_transport_jobs",
        "Pure MRT uses guideway routing, carrier scheduling, station semantics, and validated physical H<->V transition semantics; never Conventional walking-speed timing.",
        ("MRT",), "VIOLATION", "validate_architecture_purity()",
    ),
    AuthorityRule(
        "MRT_DESIGN", "ARCHITECTURE", "spatial_benchmark.py::optimize_pathway_layouts",
        "Pure MRT architecture emerges from retention feasibility + operations/logistics + space + MRT CapEx/OPEX + staffing + demand; DISTRIBUTED is an output classification only.",
        ("MRT",), "VIOLATION", "test_cluster_distribution_authority.test_spatial_form_classification_never_referenced_by_ranking_or_dominance",
    ),
    AuthorityRule(
        "ARCHITECTURE_PURITY", "ARCHITECTURE", "asset_cost_ledger.py / infrastructure_capex.py / infrastructure_opex.py",
        "PURE CONVENTIONAL must contain no active MRT carriers/guideway/stations/transitions/support staff; PURE MRT must contain no active Conventional transporter labor/hand-carry timing.",
        ("Conventional", "MRT"), "VIOLATION", "validate_architecture_purity()",
    ),
    AuthorityRule(
        "HYBRID_UNION", "ARCHITECTURE", "hybrid_optimization.py::HybridZoneCandidate",
        "Hybrid is the non-duplicating union of Conventional and MRT transport zones; exclusive zones do not intersect; Hybrid coverage = Conventional_zone U MRT_zone.",
        ("Hybrid",), "VIOLATION", "validate_hybrid_zone_disjointness()",
    ),
    AuthorityRule(
        "HYBRID_SHARED_RESOURCES", "ARCHITECTURE", "hybrid_optimization.py::evaluate_hybrid_zone_candidate",
        "Hybrid has ONE copy of genuinely shared resources (patient population, CY-001, production cycles, shared injection/uptake/scanner, production staff, common clinical staff); pathway-specific resources apply only to their assigned workload.",
        ("Hybrid",), "VIOLATION", "test_hybrid_production_labor_reconciliation / test_staffing_authority_integration",
    ),
    AuthorityRule(
        "HYBRID_CLINICAL_SCHEDULE", "CLINICAL_FLOW", "hybrid_optimization.py::evaluate_hybrid_zone_candidate (joint_clinical_schedule)",
        "Hybrid uses mode-specific transport followed by ONE merged injection/uptake/scanner schedule; no isolated-mode clinical schedule may become final authority.",
        ("Hybrid",), "VIOLATION", "existing joint-schedule correction (Phase: Joint Hybrid Clinical Scheduling)",
    ),
    AuthorityRule(
        "PAYLOAD_AUTHORITY", "TRACEABILITY", "production_clinical_schedule.py::TransportPayload / hybrid_optimization.py",
        "Every payload preserves payload_id, source cycle, patient IDs, destination, transport mode; payload IDs are globally unique within the study (Hybrid uses CONV-/MRT- mode-prefix semantics).",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_patient_traceability()",
    ),
    AuthorityRule(
        "CLINICAL_FLOW_CHAIN", "CLINICAL_FLOW", "operating_day_scheduler.py::schedule_operating_day",
        "PRODUCTION -> TRANSPORT -> INJECTION -> UPTAKE -> SCANNER -> COMPLETION -> QUALIFICATION; no stage creates or silently drops patients.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_conservation_chain()",
    ),
    AuthorityRule(
        "INJECTION_AUTHORITY", "CLINICAL_FLOW", "operating_day_scheduler.py::_allocate_earliest (injection stage)",
        "Injection resources are physical scheduled resources; injection expansion improves retention only through real queue/timing effects and never creates patient demand.",
        ("Conventional", "MRT", "Hybrid"), "WARNING", "test_clinical_bottleneck_authority.py",
    ),
    AuthorityRule(
        "UPTAKE_AUTHORITY", "CLINICAL_FLOW", "operating_day_scheduler.py::_allocate_earliest (uptake stage)",
        "Every shared-uptake patient occupies one uptake resource for the configured (protocol-dependent, never hard-coded) uptake interval; no overlapping impossible occupancy.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "test_clinical_bottleneck_authority.test_uptake_room_cannot_host_overlapping_patients",
    ),
    AuthorityRule(
        "SCANNER_AUTHORITY", "CLINICAL_FLOW", "operating_day_scheduler.py::_allocate_earliest (scanner stage)",
        "Scanner resources have service duration/availability/capacity/schedule; no impossible parallel use; scanner count alone does not create patient readiness.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "test_clinical_bottleneck_authority.py scanner bottleneck tests",
    ),
    AuthorityRule(
        "CLINICAL_BOTTLENECK", "CLINICAL_FLOW", "spatial_benchmark.py / hybrid_optimization.py (coupled scheduling)",
        "Useful throughput emerges from the coupled production/transport/injection/uptake/scanner/retention/clinical-day system; no clinical resource is optimized as an isolated scalar.",
        ("Conventional", "MRT", "Hybrid"), "WARNING", "test_clinical_bottleneck_authority.py",
    ),
    AuthorityRule(
        "ROOM_INVENTORY", "ROOM", "spatial_benchmark.py::CandidateLayout.room_assignments",
        "There is one physical room inventory; a room may not independently exist as separate resources across spatial optimization, inbound analysis, Hybrid, and economics.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_room_exclusivity()",
    ),
    AuthorityRule(
        "ROOM_EXCLUSIVITY", "ROOM", "spatial_benchmark.py::_assign_rooms_for_candidate",
        "Unless intentionally multifunctional (integrated inbound), one physical room cannot simultaneously be shared injection, shared uptake, scanner, and inbound room.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_room_exclusivity()",
    ),
    AuthorityRule(
        "INTEGRATED_INBOUND_ROOM", "INBOUND", "inbound_patient_program.py::admit_inbound_patients",
        "Integrated inbound room = dedicated patient room + dedicated injection + dedicated uptake for ONE assigned inbound patient during occupancy; not shared clinical capacity.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "test_inbound_patient_program.py",
    ),
    AuthorityRule(
        "INBOUND_ROOM_NOT_DEDICATED_STAFF", "INBOUND", "radiopharm_workflow_staffing.py::compute_radiopharm_workflow_staffing",
        "Dedicated room does not imply dedicated continuous staff; inbound LOS controls room occupancy/room-day economics only, staffing arises from modeled tasks/interactions.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "test_radiopharm_workflow_staffing.test_inbound_dedicated_room_excluded_from_shared_staff_pools_regardless_of_los",
    ),
    AuthorityRule(
        "CENTRALIZED_INBOUND", "INBOUND", "inbound_patient_program.py (CENTRALIZED architecture)",
        "Centralized inbound uses shared injection then dedicated inbound-room uptake/occupancy; the room is never double-counted as shared uptake capacity.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "test_inbound_patient_program.py / test_inbound_pipeline_integration.py",
    ),
    AuthorityRule(
        "INBOUND_PRODUCTION", "INBOUND", "inbound_patient_program.py::attach_patient_type_and_los",
        "Inbound patients consume real radionuclide activity; inbound + outpatient requirements must reconcile to total production demand.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "test_engineering_authority_reconciliation.test_inbound_and_outpatient_activity_sum_to_total_demand",
    ),
    AuthorityRule(
        "STAFFING_AUTHORITY", "STAFFING", "radiopharm_workflow_staffing.py::compute_radiopharm_workflow_staffing",
        "Room count != peak staff != annual FTE; staffing follows actual workload/concurrency and established coverage assumptions.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "test_radiopharm_workflow_staffing.test_room_count_does_not_automatically_equal_fte",
    ),
    AuthorityRule(
        "COMMON_CLINICAL_STAFF", "STAFFING", "radiopharm_workflow_staffing.py",
        "Common staff pools (production, injection, uptake supervision, scanner) serve the whole facility; MRT does not eliminate clinical care staff.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "test_staffing_authority_integration.test_pure_mrt_with_active_throughput_has_nonzero_clinical_staff (via radiopharm module)",
    ),
    AuthorityRule(
        "CONVENTIONAL_TRANSPORT_LABOR", "STAFFING", "decision_pipeline.py::conventional_transport_staff_fte",
        "Conventional human radionuclide transport incurs workload-dependent labor OPEX; no free transporters.",
        ("Conventional", "Hybrid"), "VIOLATION", "existing conventional_transport_staff_fte = distribution_concurrency",
    ),
    AuthorityRule(
        "MRT_CARRIER_AUTHORITY", "ASSET", "mrt_carrier_fleet.py::resolve_mrt_carrier_fleet",
        "MRT carriers are equipment, not FTE; carrier CapEx/electricity/maintenance remain distinct from MRT support staff; no free carriers.",
        ("MRT", "Hybrid"), "VIOLATION", "test_study_scope_architecture.test_operational_mrt_carrier_capex_off_fleet_finite",
    ),
    AuthorityRule(
        "PRODUCTION_LABOR", "STAFFING", "spatial_benchmark.py::_build_pathway_scenarios (production_staff_fte) / hybrid_optimization.py",
        "Current benchmark production labor (2.0 FTE x $110,000) is LEGACY_FIXED_PRODUCTION_STAFF_ASSUMPTION until calibrated workload authority supersedes it; Hybrid with one CY-001 incurs exactly one production labor pool.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "test_hybrid_production_labor_reconciliation.py",
        classification="LEGACY_COMPATIBILITY",
    ),
    AuthorityRule(
        "CLINICAL_STAFF_ASSUMPTIONS", "STAFFING", "radiopharm_workflow_staffing.py",
        "common clinical loaded FTE cost=$85,000/yr, productive hours/FTE/yr=2,000, uptake supervision ratio=4 patients/staff are PROJECT_ASSUMPTION+REQUIRES_CALIBRATION, never presented as measured hospital facts.",
        ("Conventional", "MRT", "Hybrid"), "WARNING", "manual disclosure audit",
        classification="PROJECT_ASSUMPTION",
    ),
    AuthorityRule(
        "STUDY_SCOPE_INDEPENDENCE", "STUDY_SCOPE", "study_scope.py::StudyScope / TransportArchitecture",
        "CAPITAL_PLANNING and OPERATIONAL_ONLY are independent of transport architecture (Conventional/MRT/Hybrid); six valid combinations, no hidden fallback.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "test_study_scope_architecture.test_six_combination_matrix_all_succeed",
    ),
    AuthorityRule(
        "OPERATIONAL_CAPEX_OFF_ASSET_ON", "STUDY_SCOPE", "study_scope.py::apply_study_scope / build_installed_existing_pathway_scenario",
        "OPERATIONAL_ONLY excludes new-project acquisition/construction CapEx from the study objective; it never sets asset quantity/capacity to zero (CAPEX OFF != ASSET OFF).",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "test_study_scope_architecture.py CapEx-off/asset-on tests",
    ),
    AuthorityRule(
        "CAPEX_LEDGER_AUTHORITY", "ECONOMIC", "infrastructure_capex.py::calculate_infrastructure_capex",
        "Every new capital asset has quantity, unit cost, provenance, and asset state (installed vs existing); existing retained assets may have study CapEx=0 while remaining physically present.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "asset_cost_ledger.reconcile_capex_ledger",
    ),
    AuthorityRule(
        "OPEX_LEDGER_AUTHORITY", "ECONOMIC", "infrastructure_opex.py::calculate_infrastructure_opex",
        "Every active recurring operational resource has explicit OPEX or is flagged MISSING_ECONOMIC_TREATMENT; material recurring costs are never silently zero.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "asset_cost_ledger.reconcile_opex_ledger",
    ),
    AuthorityRule(
        "ECONOMIC_RECONCILIATION", "ECONOMIC", "asset_cost_ledger.py::reconcile_capex_ledger / reconcile_opex_ledger",
        "sum(CapEx ledger) == reported CapEx and sum(OPEX ledger) == reported annual OPEX; target residual 0.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_economic_reconciliation()",
    ),
    AuthorityRule(
        "QUALIFIED_VALUE_AUTHORITY", "ECONOMIC", "spatial_benchmark.py / inbound_patient_program.py",
        "Primary patient value uses retention-qualified completed procedures; inbound room-day value remains separate (one room-day is not one scan).",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "test_inbound_patient_program.py room-day value tests",
    ),
    AuthorityRule(
        "CAPITAL_ECONOMIC_AUTHORITY", "ECONOMIC", "lifecycle_economics.py::evaluate_lifecycle_economics",
        "Capital planning uses qualified NPV under the existing discount-rate/analysis-horizon economic model; not altered by StudyScope threading.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "test_study_scope_architecture.test_capital_planning_reference_values_unchanged_by_study_scope_threading",
    ),
    AuthorityRule(
        "OPERATIONAL_ECONOMIC_AUTHORITY", "ECONOMIC", "study_scope.py::apply_study_scope",
        "Operational-only reports qualified annual value, annual OPEX, annual operating margin, OPEX/qualified patient, and a clearly-named operating-horizon present value; never labeled 'capital project NPV'.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "test_study_scope_architecture.test_capital_project_npv_only_populated_for_capital_planning",
    ),
    AuthorityRule(
        "OPTIMIZATION_SEARCH_BOUND", "OPTIMIZATION", "hybrid_optimization.py::ResourceSearchDiagnostic",
        "A selected resource count is not proven optimal merely because it is the largest value tested (SEARCH BOUND != PHYSICAL LIMIT); COMPUTATIONAL_SEARCH_LIMIT alone means OPTIMALITY_NOT_PROVEN.",
        ("Conventional", "MRT", "Hybrid"), "WARNING", "validate_optimization_stop_reason()",
    ),
    AuthorityRule(
        "CONSERVATION_CHAIN", "CONSERVATION", "decision_pipeline.py::NativeOperationalResult",
        "Patients demanded -> production feasible -> transported -> administered -> uptake -> scanned -> completed -> qualified must be non-increasing at every stage, with explicit reasons for any drop.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_conservation_chain()",
    ),
    AuthorityRule(
        "ASSET_CONSERVATION", "ASSET", "asset_cost_ledger.py::build_asset_register",
        "One cyclotron/scanner/room/guideway-segment/carrier is not counted or charged twice; one common staff pool is not duplicated by transport mode.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_architecture_purity() / validate_economic_reconciliation()",
    ),

    # --- Multi-radionuclide / multi-cyclotron / spatial origin authority (new) ---
    AuthorityRule(
        "MULTI_RADIONUCLIDE_PATIENT_NEED", "PATIENT", "multi_cyclotron_authority.py::radionuclide_support_report / patient_radionuclide_demand.py",
        "Each patient's radionuclide-specific need is preserved individually; a mixed population is never collapsed to a generic dose count. Decay-model support (multi_isotope_decay half-life database) and cyclotron-production support (calibrated catalog capability) are distinct and must never be conflated.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "multi_cyclotron_authority.radionuclide_support_report()",
    ),
    AuthorityRule(
        "PROTOCOL_SPECIFIC_CLINICAL_REQUIREMENTS", "CLINICAL_FLOW", "models.py::PlannerAssumptions (uptake_cycle_min/scanner_cycle_min)",
        "Uptake/scanner requirements are protocol-configurable, never a universal hard-coded 45/60-minute constant; where no validated protocol-specific value exists, classify PROTOCOL_PARAMETER_NOT_CALIBRATED rather than inventing a clinical fact.",
        ("Conventional", "MRT", "Hybrid"), "WARNING", "manual audit; current benchmark uses one F-18 protocol (45 min uptake, 20 min scanner) for all patients",
        classification="REQUIRES_CALIBRATION",
    ),
    AuthorityRule(
        "CYCLOTRON_CONFIGURATION_STATE", "CYCLOTRON", "multi_cyclotron_authority.py::CyclotronScenarioState / ConfiguredCyclotron",
        "Each cyclotron has an independent ON/OFF scenario state (production capacity availability for a given run) that is distinct from its asset_state (EXISTING vs PROPOSED, per study_scope.py); OFF never deletes the asset record or patient demand.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "multi_cyclotron_authority.build_multi_cyclotron_scenario()",
    ),
    AuthorityRule(
        "CYCLOTRON_RADIONUCLIDE_COMPATIBILITY", "CYCLOTRON", "cyclotron_catalog.py::CyclotronCatalogModel.supported_radionuclides",
        "A cyclotron may only be assigned production for radionuclides it is calibrated to produce; a decay-model-known radionuclide with no calibrated catalog record remains NOT_CALIBRATED, never fabricated capacity.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "multi_cyclotron_authority.radionuclide_support_report()",
    ),
    AuthorityRule(
        "CYCLOTRON_SPATIAL_ORIGIN", "GEOMETRY", "multi_cyclotron_authority.py::CyclotronSpatialOrigin",
        "Each cyclotron has an explicit production/release origin coordinate/node; patient transport for that patient's produced dose begins at the cyclotron that actually produced it, not a single global default origin, once more than one cyclotron is active.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION",
        "production_clinical_schedule.py::ProductionClinicalScenario.cyclotron_radiopharmacy_origin_object_id_by_cyclotron_id "
        "wired into _resolve_conventional_route_components/_resolve_mrt_route_profile (Conventional and MRT transport jobs "
        "resolve origin per producing cyclotron via ProductionBatchReleaseMapping.assigned_cyclotron_id, verified in "
        "test_multi_origin_cyclotron_spatial_integration.py); validate_cyclotron_spatial_origin_traceability() detects "
        "wrong-origin routing.",
    ),
    AuthorityRule(
        "CYCLOTRON_RADIOPHARMACY_COLOCATION", "GEOMETRY", "multi_cyclotron_authority.py::CyclotronSpatialOrigin",
        "PROJECT_ASSUMPTION: coordinate(CY_k) == coordinate(RP_k) for every modeled cyclotron -- the cyclotron and its associated radiopharmacy are treated as co-located for transport-origin purposes; not a universal physical claim.",
        ("Conventional", "MRT", "Hybrid"), "INFO", "multi_cyclotron_authority.build_multi_cyclotron_scenario()",
        classification="PROJECT_ASSUMPTION",
    ),
    AuthorityRule(
        "MULTI_CYCLOTRON_PRODUCTION_ASSIGNMENT", "PRODUCTION", "decision_pipeline.py::_cycle_relative_requirement_by_radionuclide",
        "Each cyclotron's production cycles/EOB capacity/temporal constraints remain asset-specific (never pooled into one anonymous MBq total); patients are assigned to a specific compatible, available, capacity-feasible cyclotron and retain that cyclotron_id. Adding cyclotron capacity must never create patients or fabricate benefit where existing capacity was never the binding constraint.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "multi_cyclotron_authority.build_multi_cyclotron_scenario() + existing per-asset candidate-cycle generation",
    ),

    # --- Inbound clinical-resource unification authority (new) ---
    AuthorityRule(
        "CLINICAL_RESOURCE_MODE", "CLINICAL_FLOW", "patient_radionuclide_demand.py::PatientRadionuclideDemand.clinical_resource_mode",
        "Every patient/procedure carries exactly one clinical-resource mode (OUTPATIENT_SHARED, INBOUND_CENTRALIZED, INBOUND_INTEGRATED), independent of Conventional/MRT/Hybrid transport mode; the mode is never inferred from transport architecture.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_clinical_resource_mode_consistency()",
    ),
    AuthorityRule(
        "INBOUND_DEDICATED_RESOURCE_SEMANTICS", "INBOUND", "operating_day_scheduler.py::schedule_operating_day (dedicated-room bypass)",
        "INBOUND_CENTRALIZED consumes shared injection + dedicated inbound-room uptake/occupancy; INBOUND_INTEGRATED consumes dedicated inbound-room injection/uptake/occupancy only; both still compete for the shared scanner inventory.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_clinical_resource_mode_consistency()",
    ),
    AuthorityRule(
        "INTEGRATED_SHARED_QUEUE_EXCLUSION", "CLINICAL_FLOW", "operating_day_scheduler.py::schedule_operating_day (DEDICATED_ROOM_RESOURCE_INDEX)",
        "An INBOUND_INTEGRATED patient's injection/uptake never contributes to shared INJ-xxx/UP-xxx queue, utilization, concurrency, or workload -- those functions occur entirely in the patient's dedicated inbound room.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_clinical_resource_mode_consistency()",
    ),
    AuthorityRule(
        "CENTRALIZED_SHARED_UPTAKE_EXCLUSION", "CLINICAL_FLOW", "operating_day_scheduler.py::schedule_operating_day (DEDICATED_ROOM_RESOURCE_INDEX)",
        "An INBOUND_CENTRALIZED patient's uptake never contributes to shared UP-xxx queue/utilization/workload -- uptake occurs in the dedicated inbound room, while injection legitimately competes for shared INJ-xxx.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_clinical_resource_mode_consistency()",
    ),
    AuthorityRule(
        "INBOUND_ROOM_OCCUPANCY_EXCLUSIVITY", "ROOM", "long_horizon_operational_planning.py::validate_inbound_room_no_overlap",
        "One dedicated inbound room cannot contain two overlapping admission/discharge intervals; occupancy is determined by admission->discharge, not by injection/uptake/scan task duration.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_inbound_room_no_overlap()",
    ),

    # --- Vendor-neutral healthcare integration authority (new) ---
    AuthorityRule(
        "EXTERNAL_IDENTITY_UNIQUENESS", "TRACEABILITY", "healthcare_integration.py::CrossSourceIdentityRegistry",
        "One (source_system, external_reference) key resolves to exactly one canonical patient/procedure/device identity; a conflicting resolution attempt is recorded as an IdentityConflict, never silently overwritten or silently ignored.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "CrossSourceIdentityRegistry.identity_conflicts",
    ),
    AuthorityRule(
        "EVENT_IDEMPOTENCY", "TRACEABILITY", "healthcare_integration.py::CrossSourceIdentityRegistry.already_processed",
        "The same (source_system, source_event_id) received twice must produce zero additional canonical effect -- no duplicate patient, procedure, or resource is ever created from a re-delivered event.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "CrossSourceIdentityRegistry.already_processed()",
    ),
    AuthorityRule(
        "SOURCE_CONFLICT_VISIBILITY", "TRACEABILITY", "healthcare_integration.py::SourceConflict",
        "When two sources supply contradictory SOURCE_TRUTH values for the same canonical field, the conflict is recorded explicitly (never silently overwritten by source precedence) and remains queryable, not buried in a log string.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "CrossSourceIdentityRegistry.source_conflicts / run_integration_validation()",
    ),
    AuthorityRule(
        "VENDOR_BOUNDARY_ISOLATION", "ARCHITECTURE", "healthcare_adapters.py (adapter modules only)",
        "Vendor-specific interpretation (VARIAN_ARIA / GE_DOSEWATCH / SIEMENS_HEALTHINEERS / future adapters) terminates at the adapter boundary; production/transport/clinical-scheduling/staffing/economics modules contain no vendor-conditional branches and remain unaware of data source.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "manual/architectural audit -- no vendor-name string literals outside healthcare_integration.py / healthcare_adapters.py",
    ),
    AuthorityRule(
        "EXTERNAL_DEVICE_IDENTITY", "ASSET", "healthcare_integration.py::CrossSourceIdentityRegistry.resolve_device",
        "An external device reference may only resolve to an EXISTING, explicitly-supplied canonical physical resource (e.g. SCN-003); it never fabricates a new scanner/cyclotron identity, and multiple external device references may legitimately map to the same physical resource.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "CrossSourceIdentityRegistry.resolve_device()",
    ),
    AuthorityRule(
        "POWER_UNIT_SEMANTICS", "ECONOMIC", "healthcare_integration.py::PowerUnit / is_energy_usable_measurement",
        "kW (real power), kVA (apparent power/electrical service demand) and kWh (energy) are distinct units that are never silently converted or interchanged; only a kW value whose measurement_type genuinely represents an operating-state consumption may be multiplied by duration to produce kWh.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "healthcare_integration.is_energy_usable_measurement()",
    ),
    AuthorityRule(
        "ENERGY_CALIBRATION_STATUS", "ECONOMIC", "healthcare_integration.py::EquipmentIdentityRecord / equipment_energy_opex.py::compute_equipment_daily_energy",
        "Equipment energy calibration (CALIBRATED_FOR_ENERGY / PARTIALLY_CALIBRATED / NOT_CALIBRATED) is tracked independently of production/clinical calibration; an equipment identity that is fully production-calibrated (e.g. CY-001) may simultaneously be energy-NOT_CALIBRATED, and this must remain explicit rather than inferred from production status.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "equipment_energy_opex.compute_equipment_daily_energy()",
    ),
    AuthorityRule(
        "SCHEDULE_DERIVED_STATE_TIME", "PRODUCTION", "equipment_energy_opex.py::derive_cyclotron_state_minutes / derive_scanner_state_minutes",
        "Operating-state time (IRRADIATING/SCANNING vs STANDBY/IDLE/OFF) is derived from the actual persistent production/clinical schedule (production_plan_for_cyclotron / assignments_for_resource), never from an assumed utilization percentage; for every equipment/date the sum of state durations equals the modeled accounting horizon exactly, with no overlap or negative duration.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "equipment_energy_opex.derive_cyclotron_state_minutes() / derive_scanner_state_minutes()",
    ),
    AuthorityRule(
        "ENERGY_OPEX_NO_DOUBLE_COUNTING", "ECONOMIC", "equipment_energy_opex.py::reconcile_generic_energy_line_with_schedule_derived",
        "For calibrated equipment, a schedule-derived electricity OPEX figure REPLACES the corresponding generic annual-kWh OPEX line for the same physical consumption; it is never added alongside it, and the non-energy 'Cyclotron annual fixed O&M' / 'Radiopharmacy annual fixed O&M' lines remain unaffected.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "equipment_energy_opex.reconcile_generic_energy_line_with_schedule_derived()",
    ),
    AuthorityRule(
        "UNCALIBRATED_ENERGY_NOT_ZERO", "ECONOMIC", "equipment_energy_opex.py::EquipmentDailyEnergyResult / MRT_ENERGY_STATUS",
        "NOT_CALIBRATED energy (including MRT carrier/guideway energy, which remains uncalibrated in this repository) is never treated as, defaulted to, or displayed as $0 or 0 kWh; it is reported as an explicit uncalibrated status/duration distinct from any calculated figure.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "equipment_energy_opex.EquipmentDailyEnergyResult.uncalibrated_state_minutes / MRT_ENERGY_STATUS",
    ),
    AuthorityRule(
        "ECONOMIC_ENERGY_COMPARABILITY", "ECONOMIC", "equipment_energy_opex.py::summarize_horizon_equipment_energy",
        "A pathway comparison (Conventional vs MRT vs Hybrid) whose components include NOT_CALIBRATED energy must expose an explicit economic_comparability_status (FULLY_CALIBRATED / PARTIALLY_CALIBRATED / NOT_COMPARABLE_DUE_TO_UNCALIBRATED_ENERGY) rather than silently presenting an uncalibrated component as a cost advantage.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "equipment_energy_opex.summarize_horizon_equipment_energy()",
    ),
    AuthorityRule(
        "AUTHORITATIVE_ENERGY_LEDGER_INTEGRATION", "ECONOMIC", "infrastructure_opex.py::calculate_infrastructure_opex / equipment_energy_opex.py::build_ledger_energy_component",
        "Schedule-derived calibrated electricity enters the SAME authoritative OPEX ledger (infrastructure_opex.py) that already owns Conventional/MRT economics; it is never computed by a second, competing economics/OPEX authority.",
        ("Conventional", "MRT"), "VIOLATION", "validate_energy_ledger_integration()",
    ),
    AuthorityRule(
        "GENERIC_ENERGY_FALLBACK_VISIBILITY", "ECONOMIC", "infrastructure_opex.py::OpexLedgerItem.energy_provenance",
        "Every ENERGY-category ledger line exposes whether its billed kWh is SCHEDULE_DERIVED_CALIBRATION or GENERIC_ENERGY_FALLBACK; a generic fallback is never mislabeled as manufacturer-calibrated physics, and is never silently collapsed to 0 kWh/$0 merely because calibration is incomplete.",
        ("Conventional", "MRT"), "VIOLATION", "validate_energy_ledger_integration()",
    ),
    AuthorityRule(
        "ENERGY_TO_NPV_PROPAGATION", "ECONOMIC", "decision_pipeline.py::_build_pathway_result / lifecycle_economics.py::evaluate_lifecycle_economics",
        "Reconciled authoritative annual OPEX (including schedule-derived or generic-fallback electricity) propagates to NPV through the EXISTING lifecycle economics engine only; no independent NPV calculation is performed inside the energy module.",
        ("Conventional", "MRT"), "VIOLATION", "manual/architectural audit -- equipment_energy_opex.py contains no NPV/discounting logic",
    ),
    AuthorityRule(
        "HYBRID_AUTHORITATIVE_OPEX_LEDGER", "ECONOMIC", "hybrid_optimization.py::_build_hybrid_opex_result / infrastructure_opex.py::calculate_infrastructure_opex",
        "Hybrid OPEX is composed through the SAME authoritative infrastructure_opex.py ledger semantics Conventional/MRT use (via a narrow Hybrid -> InfrastructureOpexInputs adapter); the old bespoke Hybrid total_annual_opex formula is REMOVED_FROM_AUTHORITATIVE_PATH and never a second, competing final-OPEX authority.",
        ("Hybrid",), "VIOLATION", "validate_hybrid_opex_unification()",
    ),
    AuthorityRule(
        "HYBRID_SHARED_ASSET_SINGLE_CHARGE", "ECONOMIC", "hybrid_optimization.py::_build_hybrid_opex_result",
        "Shared physical assets/pools (production labor, cyclotron fixed O&M/electricity, scanner/injection/uptake O&M/electricity, merged clinical staffing) are charged exactly once per Hybrid candidate, independent of Conventional/MRT zone split -- never duplicated per transport mode.",
        ("Hybrid",), "VIOLATION", "validate_hybrid_opex_unification()",
    ),
    AuthorityRule(
        "HYBRID_MODE_SPECIFIC_OPEX_SEPARATION", "ECONOMIC", "hybrid_optimization.py::_build_hybrid_opex_result",
        "Conventional-specific (transport labor) and MRT-specific (support labor, carrier electricity/maintenance, base/endpoint O&M, guideway maintenance) OPEX appear only when that transport mode's workload is actually present in the Hybrid candidate, and never contaminate the other mode's or the shared portion's ledger rows.",
        ("Hybrid",), "VIOLATION", "validate_hybrid_opex_unification()",
    ),
    AuthorityRule(
        "PLANNED_ACTUAL_STATE_SEPARATION", "TRACEABILITY", "live_operational_state.py::OperationalStateStore / PlanVersion",
        "Planned operational state (a PlanVersion's daily_summary/patient_plans) and actual operational state (OperationalStateStore) are two separate representations; actual-state updates never overwrite a PlanVersion in place, and the original PLAN-0000 baseline remains queryable forever.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "manual/architectural audit -- PlanVersion is a frozen dataclass, never mutated",
    ),
    AuthorityRule(
        "STALE_EVENT_REJECTION", "TRACEABILITY", "live_operational_state.py::OperationalStateStore.record_event",
        "An incoming event whose effective_timestamp is older than the current recorded state's effective_timestamp for the same object is classified STALE_EVENT and rejected -- it never silently rewinds the actual-state twin.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "OperationalStateStore.record_event()",
    ),
    AuthorityRule(
        "PLAN_VERSION_TRACEABILITY", "TRACEABILITY", "live_operational_state.py::PlanVersion / _next_version_id",
        "Every accepted replan produces a new, deterministically-numbered PlanVersion (PLAN-0001, PLAN-0002, ...) with an explicit previous_version_id link; plan history is never rewritten or discarded.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "plan_history_for_patient() / compare_plan_versions()",
    ),
    AuthorityRule(
        "ROLLING_REOPTIMIZATION_LOCALITY", "OPTIMIZATION", "live_operational_state.py::analyze_event_impact / apply_event_and_replan",
        "Reoptimization scope is computed from impact analysis BEFORE any replan; events with no scheduling consequence are classified NONE and produce no plan changes; a localized event never silently triggers full-horizon reoptimization.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_live_state_consistency()",
    ),
    AuthorityRule(
        "COMPLETED_TASK_IMMUTABILITY", "CLINICAL_FLOW", "live_operational_state.py::OperationalStateStore.is_locked",
        "A patient with an actually-completed clinical stage is excluded from the rerun input and their previous plan entry is carried forward unchanged -- rolling optimization never reschedules a completed task.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_live_state_consistency()",
    ),
    AuthorityRule(
        "UNALTERED_ASSIGNMENT_PRESERVATION", "OPTIMIZATION", "live_operational_state.py::diff_patient_plans / compute_plan_stability",
        "Every patient's plan entry that is unaffected by a triggering event and its downstream consequences must be byte-for-byte identical (cyclotron/injection/uptake/scanner identity and timing windows) across plan versions -- never reshuffled merely because another mathematically equivalent solution exists.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_live_state_consistency()",
    ),
    AuthorityRule(
        "ROLLING_RESOURCE_IDENTITY_STICKINESS", "OPTIMIZATION", "operating_day_scheduler.py::_seed / long_horizon_operational_planning.py::run_operating_day_plan(preserve_resource_indices=...)",
        "A resource outage/reservation must never renumber or reset the availability of a resource index that a preserved (non-rerun) patient already occupies -- the affected-subset rerun is seeded with the preserved patients' actual busy-until times (resource_reservations) so no two patients are ever assigned overlapping time on the same physical resource identity.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_rolling_resource_identity_stickiness()",
    ),
    AuthorityRule(
        "PRESERVED_ASSIGNMENT_VALIDITY", "OPTIMIZATION", "live_operational_state.py::apply_event_and_replan (preserved_plans construction)",
        "A patient's plan entry may only be carried forward unchanged (preserved) if it remains genuinely feasible after the triggering event -- correct resource identity (not the outaged/removed resource), non-overlapping timing versus every other preserved and newly-scheduled assignment, and (where applicable) still-qualifying retention. An assignment is never preserved merely because it existed in the previous plan version.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_preserved_assignment_validity()",
    ),
    AuthorityRule(
        "UNNECESSARY_PLAN_DRIFT", "OPTIMIZATION", "live_operational_state.py::ModifiedAssignment.classification / diff_patient_plans",
        "A modified assignment classified COLLATERAL_CHANGE_REQUIRED_FOR_FEASIBILITY (i.e. NOT in the event's directly/downstream-affected set) must carry an explicit, non-empty reason, and must be rare: it is only acceptable when localized (LEVEL_1) reoptimization proved infeasible and the plan escalated. A collateral change with no recorded reason, or occurring without a recorded escalation, is unnecessary drift.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_unnecessary_plan_drift()",
    ),
    AuthorityRule(
        "EVENT_TO_REPLAN_COMPLETENESS", "TRACEABILITY", "live_operational_state.py::_DAY_ENGINE_REPLAN_EVENT_TYPES / apply_event_and_replan",
        "Every operational event kind that can render the current plan infeasible or materially suboptimal (patient cancellation/no-show/new-urgent, resource unavailability, cyclotron outage/release delay, actual-release-activity shortfall, transport delay, staff capacity change) must resolve to an authoritative day-engine replan (or an explicit, justified impact-analysis-only classification) -- it must never silently stop at impact-analysis while a technically available replan path exists.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_event_to_replan_completeness()",
    ),
    AuthorityRule(
        "ARCHITECTURE_LIVE_QUALIFICATION", "ARCHITECTURE", "live_operational_state.py::apply_event_and_replan / long_horizon_operational_planning.py::run_operating_day_plan",
        "A claim that the live-state/rolling-reoptimization architecture is qualified for Conventional, MRT, or Hybrid must be backed by an actually-executed, passing live-state scenario for that pathway (event applied, day-engine replan invoked, plan diffed) -- never inferred merely because the pathway shares code with an already-tested one.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_architecture_live_qualification()",
    ),
    AuthorityRule(
        "HYBRID_LIVE_STATE_ADAPTER", "ARCHITECTURE", "live_operational_state.py::HybridPlanVersion / build_hybrid_patient_operational_plans",
        "A Hybrid live-state plan represents ONE patient population via the SAME `PatientOperationalPlan` type Conventional/MRT use -- a patient/job identity must never appear duplicated once for Conventional and again for MRT, and shared INJ/UP/SCN/IR resource identities must never be duplicated per transport mode (e.g. CONV-SCN-001 vs MRT-SCN-001).",
        ("Hybrid",), "VIOLATION", "validate_hybrid_single_patient_population() / validate_hybrid_shared_resource_identity()",
    ),
    AuthorityRule(
        "HYBRID_MODE_SPECIFIC_IMPACT", "OPTIMIZATION", "live_operational_state.py::analyze_event_impact (impact_classification)",
        "A CONVENTIONAL_SPECIFIC_IMPACT event (e.g. Conventional transport shortage) must never directly affect an MRT-mode patient, and an MRT_SPECIFIC_IMPACT event (e.g. carrier failure) must never directly affect a Conventional-mode patient, unless a genuine SHARED_RESOURCE_IMPACT (physical INJ/UP/SCN/IR/cyclotron/staff resource) or an explicit, recorded downstream/mode-change reason is present.",
        ("Hybrid",), "VIOLATION", "validate_hybrid_mode_specific_impact()",
    ),
    AuthorityRule(
        "STAFF_SHORTFALL_PATIENT_TARGETING", "STAFFING", "live_operational_state.py::identify_staff_shortfall_patient_tasks",
        "A detected staff-capacity shortfall (required concurrency > available capacity) must identify the actual overlapping patient tasks from real scheduled windows and target the minimum necessary (non-locked) future subset for reoptimization -- it must never leave a genuine shortfall with zero patient-level targets, and must never mark every task in the operating day as affected when a smaller feasible release set exists.",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_staff_shortfall_patient_targeting()",
    ),
    AuthorityRule(
        "STAFF_CAPACITY_REPLAN", "STAFFING", "live_operational_state.py::apply_event_and_replan / apply_hybrid_event_and_replan (STAFF_CAPACITY_CHANGE)",
        "After a staff-capacity-targeted replan, the revised schedule's required concurrency for the constrained pool must not exceed the available capacity -- or the replan must report an explicit staffing-related unmet/infeasible result. Capacity itself is never fabricated/auto-increased by this replan (OPERATIONAL_ONLY never auto-hires).",
        ("Conventional", "MRT", "Hybrid"), "VIOLATION", "validate_staff_capacity_replan_result()",
    ),
)


@dataclass(frozen=True)
class AuthorityFinding:
    authority_id: str
    category: AuthorityCategory
    severity: Severity
    message: str
    affected_object_ids: tuple[str, ...]
    authoritative_owner: str
    recommended_action: str


@dataclass(frozen=True)
class AuthorityValidationResult:
    passed: bool
    violations: tuple[AuthorityFinding, ...]
    warnings: tuple[AuthorityFinding, ...]
    authority_checks: tuple[str, ...]
    constraint_checks: tuple[str, ...]
    conservation_checks: tuple[str, ...]
    traceability_checks: tuple[str, ...]
    economic_reconciliation: tuple[str, ...]
    optimality_status: str


def _lookup_rule(authority_id: str) -> AuthorityRule:
    for rule in AUTHORITY_REGISTRY:
        if rule.authority_id == authority_id:
            return rule
    raise KeyError(f"Unknown authority_id: {authority_id}")


def _finding(authority_id: str, message: str, affected_object_ids: Sequence[str] = ()) -> AuthorityFinding:
    rule = _lookup_rule(authority_id)
    recommended_action = {
        "VIOLATION": "Investigate and correct before accepting this candidate/study.",
        "WARNING": "Review; may be acceptable but should be disclosed.",
        "INFO": "No action required.",
    }[rule.severity]
    return AuthorityFinding(
        authority_id=authority_id, category=rule.category, severity=rule.severity, message=message,
        affected_object_ids=tuple(affected_object_ids), authoritative_owner=rule.authoritative_owner,
        recommended_action=recommended_action,
    )


def validate_architecture_purity(
    *, pathway: str, capex_ledger: Sequence[object], opex_ledger: Sequence[object],
) -> list[AuthorityFinding]:
    """Section 21/ARCHITECTURE_PURITY: pure pathways must never carry the
    other transport mode's cost lines."""
    findings: list[AuthorityFinding] = []
    components = [item.component.lower() for item in capex_ledger] + [item.component.lower() for item in opex_ledger]
    if pathway == "Conventional":
        for term in ("mrt", "carrier", "guideway"):
            leaked = [c for c in components if term in c]
            if leaked:
                findings.append(_finding("ARCHITECTURE_PURITY", f"Pure Conventional ledger contains MRT-related term '{term}': {leaked}", (pathway,)))
    elif pathway == "MRT":
        for term in ("conventional transport",):
            leaked = [c for c in components if term in c]
            if leaked:
                findings.append(_finding("ARCHITECTURE_PURITY", f"Pure MRT ledger contains Conventional-transport term '{term}': {leaked}", (pathway,)))
    return findings


def validate_hybrid_zone_disjointness(
    *, conventional_floors: frozenset, mrt_floors: frozenset,
) -> list[AuthorityFinding]:
    """Section 22/HYBRID_UNION: exclusive zones must not intersect."""
    overlap = conventional_floors & mrt_floors
    if overlap:
        return [_finding("HYBRID_UNION", f"Conventional and MRT zones overlap on floors {sorted(overlap)}", tuple(str(f) for f in sorted(overlap)))]
    return []


def validate_economic_reconciliation(
    *, capex_ledger: Sequence[object], reported_capex: float, opex_ledger: Sequence[object], reported_opex: float,
    tolerance: float = 1e-6,
) -> list[AuthorityFinding]:
    """Section 50/ECONOMIC_RECONCILIATION."""
    findings: list[AuthorityFinding] = []
    capex_sum = sum(item.subtotal for item in capex_ledger)
    capex_diff = abs(capex_sum - reported_capex)
    if capex_diff > tolerance:
        findings.append(_finding("ECONOMIC_RECONCILIATION", f"CapEx ledger sum {capex_sum} != reported CapEx {reported_capex} (diff={capex_diff})"))
    opex_sum = sum(item.annual_cost for item in opex_ledger)
    opex_diff = abs(opex_sum - reported_opex)
    if opex_diff > tolerance:
        findings.append(_finding("ECONOMIC_RECONCILIATION", f"OPEX ledger sum {opex_sum} != reported annual OPEX {reported_opex} (diff={opex_diff})"))
    return findings


def validate_patient_traceability(
    *, demand_patient_ids: Sequence[str], clinical_patient_ids: Sequence[str], decay_patient_ids: Sequence[str],
) -> list[AuthorityFinding]:
    """Section 6/PATIENT_IDENTITY: identity must survive every stage."""
    findings: list[AuthorityFinding] = []
    demand_set, clinical_set, decay_set = set(demand_patient_ids), set(clinical_patient_ids), set(decay_patient_ids)
    lost_before_clinical = demand_set - clinical_set
    if lost_before_clinical:
        findings.append(_finding("PATIENT_IDENTITY", f"{len(lost_before_clinical)} patients lost identity before clinical schedule", tuple(sorted(lost_before_clinical))[:10]))
    lost_before_decay = clinical_set - decay_set
    if lost_before_decay:
        findings.append(_finding("PATIENT_IDENTITY", f"{len(lost_before_decay)} patients lost identity before decay/retention evaluation", tuple(sorted(lost_before_decay))[:10]))
    fabricated = (clinical_set | decay_set) - demand_set
    if fabricated:
        findings.append(_finding("PATIENT_IDENTITY", f"{len(fabricated)} patient IDs appear downstream with no matching demand record", tuple(sorted(fabricated))[:10]))
    return findings


def validate_clinical_resource_mode_consistency(
    *,
    patient_ids: Sequence[str],
    clinical_resource_modes: Sequence[str],
    injection_resource_ids: Sequence[str],
    uptake_resource_ids: Sequence[str],
    inbound_room_ids: Sequence[str | None],
) -> list[AuthorityFinding]:
    """Sections 53-54: CLINICAL_RESOURCE_MODE / INBOUND_DEDICATED_RESOURCE_SEMANTICS
    / INTEGRATED_SHARED_QUEUE_EXCLUSION / CENTRALIZED_SHARED_UPTAKE_EXCLUSION --
    detects mode/resource-assignment inconsistencies that scheduler behavior
    alone must not be relied upon to prevent."""
    findings: list[AuthorityFinding] = []
    rows = list(zip(patient_ids, clinical_resource_modes, injection_resource_ids, uptake_resource_ids, inbound_room_ids))
    for patient_id, mode, injection_id, uptake_id, room_id in rows:
        if mode in ("INBOUND_CENTRALIZED", "INBOUND_INTEGRATED") and not room_id:
            findings.append(_finding("INBOUND_DEDICATED_RESOURCE_SEMANTICS", f"{patient_id} ({mode}) missing dedicated inbound room", (patient_id,)))
            continue
        if mode == "INBOUND_INTEGRATED":
            if injection_id != room_id:
                findings.append(_finding("INTEGRATED_SHARED_QUEUE_EXCLUSION", f"{patient_id} (INTEGRATED) injected in shared {injection_id} instead of dedicated room {room_id}", (patient_id, injection_id)))
            if uptake_id != room_id:
                findings.append(_finding("INTEGRATED_SHARED_QUEUE_EXCLUSION", f"{patient_id} (INTEGRATED) uptake in shared {uptake_id} instead of dedicated room {room_id}", (patient_id, uptake_id)))
        elif mode == "INBOUND_CENTRALIZED":
            if injection_id == room_id:
                findings.append(_finding("CLINICAL_RESOURCE_MODE", f"{patient_id} (CENTRALIZED) must use shared injection, not dedicated room {room_id}", (patient_id,)))
            if uptake_id != room_id:
                findings.append(_finding("CENTRALIZED_SHARED_UPTAKE_EXCLUSION", f"{patient_id} (CENTRALIZED) uptake in shared {uptake_id} instead of dedicated room {room_id}", (patient_id, uptake_id)))
        else:
            if room_id or injection_id == room_id or uptake_id == room_id:
                findings.append(_finding("CLINICAL_RESOURCE_MODE", f"{patient_id} (OUTPATIENT_SHARED) improperly assigned a dedicated inbound room", (patient_id,)))
    return findings


def validate_cyclotron_spatial_origin_traceability(
    *,
    payload_cyclotron_ids: Sequence[str],
    payload_origin_object_ids: Sequence[str],
    registered_origin_object_id_by_cyclotron_id: dict,
    mrt_network_connected_origin_object_ids: Sequence[str] | None = None,
) -> list[AuthorityFinding]:
    """Section 34/45: CYCLOTRON_SPATIAL_ORIGIN authority check -- every payload's
    claimed transport origin must match the radiopharmacy origin actually
    registered for the cyclotron that produced it (no CY-002 payload routed
    from RP-001); every payload's cyclotron must have a known registered
    origin; and (when an MRT-connectivity set is supplied) the origin must be
    part of the MRT network, not merely assumed connected."""
    findings: list[AuthorityFinding] = []
    if len(payload_cyclotron_ids) != len(payload_origin_object_ids):
        raise ValueError("payload_cyclotron_ids and payload_origin_object_ids must be the same length")
    mismatched: list[str] = []
    unknown_cyclotron: list[str] = []
    disconnected: list[str] = []
    for cyclotron_id, claimed_origin in zip(payload_cyclotron_ids, payload_origin_object_ids):
        registered_origin = registered_origin_object_id_by_cyclotron_id.get(cyclotron_id)
        if registered_origin is None:
            unknown_cyclotron.append(cyclotron_id)
            continue
        if claimed_origin != registered_origin:
            mismatched.append(cyclotron_id)
        if mrt_network_connected_origin_object_ids is not None and registered_origin not in mrt_network_connected_origin_object_ids:
            disconnected.append(registered_origin)
    if unknown_cyclotron:
        findings.append(_finding("CYCLOTRON_SPATIAL_ORIGIN", f"{len(unknown_cyclotron)} payload(s) produced by a cyclotron with no registered radiopharmacy origin", tuple(sorted(set(unknown_cyclotron)))[:10]))
    if mismatched:
        findings.append(_finding("CYCLOTRON_SPATIAL_ORIGIN", f"{len(mismatched)} payload(s) claim a transport origin that does not match their producing cyclotron's registered origin", tuple(sorted(set(mismatched)))[:10]))
    if disconnected:
        findings.append(_finding("CYCLOTRON_SPATIAL_ORIGIN", f"{len(set(disconnected))} origin(s) not connected to the MRT network", tuple(sorted(set(disconnected)))[:10]))
    return findings


def validate_room_exclusivity(*, room_assignments: dict) -> list[AuthorityFinding]:
    """Section 32/ROOM_EXCLUSIVITY: each room maps to exactly one function
    (dict structure already guarantees this by construction; this check
    exists to catch any future violation if room_assignments is ever built
    by merging multiple independently-constructed dicts)."""
    findings: list[AuthorityFinding] = []
    seen: dict[str, str] = {}
    for room_id, function in room_assignments.items():
        if room_id in seen and seen[room_id] != function:
            findings.append(_finding("ROOM_EXCLUSIVITY", f"Room {room_id} assigned incompatible functions {seen[room_id]} and {function}", (room_id,)))
        seen[room_id] = function
    return findings


def validate_conservation_chain(*, stage_counts: Sequence[tuple[str, int]]) -> list[AuthorityFinding]:
    """Section 56/CONSERVATION_CHAIN: patient counts must be non-increasing
    stage over stage (no stage may fabricate patients)."""
    findings: list[AuthorityFinding] = []
    for (prev_name, prev_count), (next_name, next_count) in zip(stage_counts, stage_counts[1:]):
        if next_count > prev_count:
            findings.append(_finding(
                "CONSERVATION_CHAIN",
                f"Stage '{next_name}' count ({next_count}) exceeds upstream stage '{prev_name}' count ({prev_count}) -- patients fabricated",
            ))
    return findings


def validate_qualified_throughput_gating(*, clinically_completed: bool, retention_pass: bool, qualified: bool) -> list[AuthorityFinding]:
    """Section 16/QUALIFIED_THROUGHPUT: qualified requires BOTH conditions."""
    expected = clinically_completed and retention_pass
    if qualified != expected:
        return [_finding("QUALIFIED_THROUGHPUT", f"qualified={qualified} but clinically_completed={clinically_completed} and retention_pass={retention_pass} imply {expected}")]
    return []


def validate_optimization_stop_reason(*, dimension: str, stop_reason: str) -> list[AuthorityFinding]:
    """Section 54/55/OPTIMIZATION_SEARCH_BOUND."""
    findings: list[AuthorityFinding] = []
    if stop_reason not in VALID_OPTIMIZATION_STOP_REASONS:
        findings.append(_finding("OPTIMIZATION_SEARCH_BOUND", f"'{dimension}' stopped for unrecognized reason '{stop_reason}'", (dimension,)))
    elif stop_reason in OPTIMALITY_NOT_PROVEN_STOP_REASONS:
        findings.append(_finding("OPTIMIZATION_SEARCH_BOUND", f"'{dimension}' stopped only due to {stop_reason}: OPTIMALITY_NOT_PROVEN", (dimension,)))
    return findings


def validate_energy_ledger_integration(*, ledger: Sequence[object]) -> list[AuthorityFinding]:
    """Section 53/AUTHORITATIVE_ENERGY_LEDGER_INTEGRATION /
    GENERIC_ENERGY_FALLBACK_VISIBILITY: detects (a) a duplicate ENERGY-category
    ledger component (generic + schedule-derived both billed for the same
    physical consumption -- double counting), and (b) accidental removal of
    the "Cyclotron annual fixed O&M" fixed-cost line by energy integration."""
    findings: list[AuthorityFinding] = []
    energy_rows = [row for row in ledger if getattr(row, "category", None) == "ENERGY"]
    seen_components: set[str] = set()
    for row in energy_rows:
        if row.component in seen_components:
            findings.append(_finding(
                "AUTHORITATIVE_ENERGY_LEDGER_INTEGRATION",
                f"Duplicate ENERGY ledger component '{row.component}' -- generic and schedule-derived electricity must never both be billed for the same physical consumption.",
                (row.component,),
            ))
        seen_components.add(row.component)
    fixed_om = next((row for row in ledger if getattr(row, "component", None) == "Cyclotron annual fixed O&M"), None)
    if fixed_om is None:
        findings.append(_finding(
            "AUTHORITATIVE_ENERGY_LEDGER_INTEGRATION",
            "Cyclotron annual fixed O&M ledger line is missing -- fixed O&M must never be removed by energy ledger integration.",
        ))
    return findings


def validate_hybrid_opex_unification(
    *, ledger: Sequence[object], total_annual_opex: float, economic_comparability_status: object,
    mrt_active: bool, tolerance: float = 1e-6,
) -> list[AuthorityFinding]:
    """Section 72/HYBRID_AUTHORITATIVE_OPEX_LEDGER /
    HYBRID_SHARED_ASSET_SINGLE_CHARGE / HYBRID_MODE_SPECIFIC_OPEX_SEPARATION:
    detects (a) reported total not equal to the ledger sum (no separate
    hand-built total, section 35); (b) any component name appearing more than
    once in the ledger (shared-asset double charge, e.g. scanner/cyclotron/
    production-labor/clinical-labor); (c) MRT-specific rows present while
    `mrt_active` is False, or absent while True; (d) calibration/comparability
    status lost (None) despite energy rows being present."""
    findings: list[AuthorityFinding] = []
    ledger_sum = sum(getattr(row, "annual_cost", 0.0) for row in ledger)
    if abs(ledger_sum - total_annual_opex) > tolerance:
        findings.append(_finding(
            "HYBRID_AUTHORITATIVE_OPEX_LEDGER",
            f"Hybrid total_annual_opex ({total_annual_opex}) != ledger sum ({ledger_sum}) -- a separate hand-built total is not authoritative.",
        ))
    component_counts: dict[str, int] = {}
    for row in ledger:
        component = getattr(row, "component", None)
        component_counts[component] = component_counts.get(component, 0) + 1
    duplicated = [component for component, count in component_counts.items() if count > 1]
    if duplicated:
        findings.append(_finding(
            "HYBRID_SHARED_ASSET_SINGLE_CHARGE",
            f"Ledger component(s) {sorted(duplicated)} appear more than once -- shared asset/pool charged twice.",
            tuple(sorted(duplicated)),
        ))
    mrt_support_present = "MRT support labor" in component_counts
    if mrt_active and not mrt_support_present:
        findings.append(_finding(
            "HYBRID_MODE_SPECIFIC_OPEX_SEPARATION",
            "MRT transport workload is present but no MRT-specific OPEX (e.g. MRT support labor) appears in the ledger.",
        ))
    if not mrt_active and mrt_support_present:
        findings.append(_finding(
            "HYBRID_MODE_SPECIFIC_OPEX_SEPARATION",
            "No MRT transport workload is present, but MRT-specific OPEX appears in the ledger (contaminating an ALL_CONVENTIONAL candidate).",
        ))
    energy_rows_present = any(getattr(row, "category", None) == "ENERGY" for row in ledger)
    if energy_rows_present and economic_comparability_status is None:
        findings.append(_finding(
            "HYBRID_AUTHORITATIVE_OPEX_LEDGER",
            "Energy ledger rows are present but economic_comparability_status is None -- calibration status was lost before reaching final economics.",
        ))
    return findings


def validate_live_state_consistency(
    *,
    unaffected_patient_ids: Sequence[str],
    old_plans_by_patient_id: Mapping[str, object],
    new_plans_by_patient_id: Mapping[str, object],
    reoptimization_required: bool,
    plan_changed: bool,
    completed_patient_ids: Sequence[str] = (),
    modified_patient_ids: Sequence[str] = (),
) -> list[AuthorityFinding]:
    """Section 118/ROLLING_REOPTIMIZATION_LOCALITY /
    UNALTERED_ASSIGNMENT_PRESERVATION / COMPLETED_TASK_IMMUTABILITY: detects
    (a) an event with no reoptimization consequence that nonetheless produced
    a plan change (unnecessary replan, section 61/119); (b) any nominally
    "unaffected" patient whose plan entry actually differs before/after
    (localization violated); (c) any completed-task-locked patient appearing
    in the modified set (immutability violated)."""
    findings: list[AuthorityFinding] = []
    if not reoptimization_required and plan_changed:
        findings.append(_finding(
            "ROLLING_REOPTIMIZATION_LOCALITY",
            "Event was classified as not requiring reoptimization, but the plan changed -- unexplained plan drift.",
        ))
    drifted: list[str] = []
    for patient_id in unaffected_patient_ids:
        old_plan = old_plans_by_patient_id.get(patient_id)
        new_plan = new_plans_by_patient_id.get(patient_id)
        if old_plan is None or new_plan is None:
            continue
        if old_plan != new_plan:
            drifted.append(patient_id)
    if drifted:
        findings.append(_finding(
            "UNALTERED_ASSIGNMENT_PRESERVATION",
            f"{len(drifted)} nominally unaffected patient(s) had their plan entry change: {sorted(drifted)[:10]}",
            tuple(sorted(drifted))[:10],
        ))
    locked_but_modified = sorted(set(completed_patient_ids) & set(modified_patient_ids))
    if locked_but_modified:
        findings.append(_finding(
            "COMPLETED_TASK_IMMUTABILITY",
            f"{len(locked_but_modified)} completed-task-locked patient(s) appear in the modified set: {locked_but_modified[:10]}",
            tuple(locked_but_modified)[:10],
        ))
    return findings


def validate_rolling_resource_identity_stickiness(
    *,
    plans: Sequence[object],
    unavailable_resource_ids: Sequence[str] = (),
) -> list[AuthorityFinding]:
    """ROLLING_RESOURCE_IDENTITY_STICKINESS: detects (a) any plan entry
    assigned to a resource_id that is currently UNAVAILABLE (the outaged
    resource identity must never be reused just because its array index
    became free), and (b) any two plan entries sharing the same
    injection/uptake/scanner resource_id with overlapping time windows
    (identity-sticky reservations must guarantee exclusivity)."""
    findings: list[AuthorityFinding] = []
    unavailable = set(unavailable_resource_ids)
    for stage_attr, window_attr in (
        ("injection_resource_id", "injection_window_minutes"),
        ("uptake_resource_id", "uptake_window_minutes"),
        ("scanner_resource_id", "scan_window_minutes"),
    ):
        by_resource: dict[str, list[tuple[float, float]]] = {}
        leaked_ids: list[str] = []
        for plan in plans:
            resource_id = getattr(plan, stage_attr, None)
            if resource_id is None:
                continue
            if resource_id in unavailable:
                leaked_ids.append(getattr(plan, "internal_model_patient_id", "?"))
            window = getattr(plan, window_attr, None)
            if window is not None:
                by_resource.setdefault(resource_id, []).append(window)
        if leaked_ids:
            findings.append(_finding(
                "ROLLING_RESOURCE_IDENTITY_STICKINESS",
                f"{len(leaked_ids)} patient(s) assigned to a resource marked UNAVAILABLE via {stage_attr}: {sorted(leaked_ids)[:10]}",
                tuple(sorted(leaked_ids))[:10],
            ))
        for resource_id, windows in by_resource.items():
            ordered = sorted(windows)
            for (s1, e1), (s2, e2) in zip(ordered, ordered[1:]):
                if s2 < e1:
                    findings.append(_finding(
                        "ROLLING_RESOURCE_IDENTITY_STICKINESS",
                        f"Overlapping {stage_attr} windows on resource {resource_id}: ({s1}, {e1}) vs ({s2}, {e2})",
                        (resource_id,),
                    ))
    return findings


def validate_preserved_assignment_validity(
    *,
    preserved_patient_ids: Sequence[str],
    plans_by_patient_id: Mapping[str, object],
    unavailable_resource_ids: Sequence[str] = (),
) -> list[AuthorityFinding]:
    """PRESERVED_ASSIGNMENT_VALIDITY: a patient may only be carried forward
    unchanged if their preserved plan entry does not reference any resource
    that is now UNAVAILABLE. Existence in the previous plan version is never
    sufficient grounds for preservation."""
    findings: list[AuthorityFinding] = []
    unavailable = set(unavailable_resource_ids)
    invalid: list[str] = []
    for patient_id in preserved_patient_ids:
        plan = plans_by_patient_id.get(patient_id)
        if plan is None:
            continue
        resource_ids = (
            getattr(plan, "injection_resource_id", None),
            getattr(plan, "uptake_resource_id", None),
            getattr(plan, "scanner_resource_id", None),
        )
        if unavailable.intersection({r for r in resource_ids if r is not None}):
            invalid.append(patient_id)
    if invalid:
        findings.append(_finding(
            "PRESERVED_ASSIGNMENT_VALIDITY",
            f"{len(invalid)} preserved patient(s) reference a now-unavailable resource and should not have been preserved: {sorted(invalid)[:10]}",
            tuple(sorted(invalid))[:10],
        ))
    return findings


def validate_unnecessary_plan_drift(
    *,
    modified_assignments: Sequence[object],
    escalated: bool,
) -> list[AuthorityFinding]:
    """UNNECESSARY_PLAN_DRIFT: a COLLATERAL_CHANGE_REQUIRED_FOR_FEASIBILITY
    modification must carry an explicit reason, and must only occur when the
    replan actually escalated beyond LEVEL_1 (localized reoptimization proved
    infeasible). A collateral change with no reason, or occurring while
    `escalated` is False, is unexplained/unnecessary drift."""
    findings: list[AuthorityFinding] = []
    unexplained: list[str] = []
    unescalated_collateral: list[str] = []
    for assignment in modified_assignments:
        if getattr(assignment, "classification", None) != "COLLATERAL_CHANGE_REQUIRED_FOR_FEASIBILITY":
            continue
        patient_id = getattr(assignment, "patient_id", "?")
        if not getattr(assignment, "reason", None):
            unexplained.append(patient_id)
        if not escalated:
            unescalated_collateral.append(patient_id)
    if unexplained:
        findings.append(_finding(
            "UNNECESSARY_PLAN_DRIFT",
            f"{len(unexplained)} collateral change(s) have no recorded reason: {sorted(unexplained)[:10]}",
            tuple(sorted(unexplained))[:10],
        ))
    if unescalated_collateral:
        findings.append(_finding(
            "UNNECESSARY_PLAN_DRIFT",
            f"{len(unescalated_collateral)} collateral change(s) occurred without the replan escalating beyond LEVEL_1: {sorted(unescalated_collateral)[:10]}",
            tuple(sorted(unescalated_collateral))[:10],
        ))
    return findings


def validate_event_to_replan_completeness(
    *,
    event_kind: str,
    reoptimization_required: bool,
    day_engine_replan_invoked: bool,
    material_event_kinds: Sequence[str],
) -> list[AuthorityFinding]:
    """EVENT_TO_REPLAN_COMPLETENESS: an event kind classified as `material`
    (can render the plan infeasible/suboptimal) that actually required
    reoptimization must invoke the day-engine replan -- it must not stop at
    impact-analysis-only."""
    if event_kind in material_event_kinds and reoptimization_required and not day_engine_replan_invoked:
        return [_finding(
            "EVENT_TO_REPLAN_COMPLETENESS",
            f"Event kind '{event_kind}' required reoptimization but no day-engine replan was invoked -- stopped at impact-analysis-only.",
            (event_kind,),
        )]
    return []


def validate_architecture_live_qualification(
    *,
    qualified_pathways: Sequence[str],
    executed_pathways: Sequence[str],
) -> list[AuthorityFinding]:
    """ARCHITECTURE_LIVE_QUALIFICATION: a pathway may only be claimed
    qualified if a live-state scenario was actually executed for it -- never
    inferred from another pathway's passing test merely because code is
    shared."""
    unexecuted = sorted(set(qualified_pathways) - set(executed_pathways))
    if unexecuted:
        return [_finding(
            "ARCHITECTURE_LIVE_QUALIFICATION",
            f"Pathway(s) {unexecuted} claimed qualified but no live-state scenario was actually executed for them.",
            tuple(unexecuted),
        )]
    return []


def validate_hybrid_single_patient_population(
    *, patient_ids: Sequence[str],
) -> list[AuthorityFinding]:
    """HYBRID_LIVE_STATE_ADAPTER (part 1): a Hybrid plan is ONE patient
    population -- no patient_id may appear more than once (e.g. once per
    transport mode)."""
    seen: set[str] = set()
    duplicated: set[str] = set()
    for pid in patient_ids:
        if pid in seen:
            duplicated.add(pid)
        seen.add(pid)
    if duplicated:
        return [_finding(
            "HYBRID_LIVE_STATE_ADAPTER",
            f"{len(duplicated)} patient(s) appear more than once in the Hybrid plan (duplicated population): {sorted(duplicated)[:10]}",
            tuple(sorted(duplicated))[:10],
        )]
    return []


def validate_hybrid_shared_resource_identity(
    *, injection_resource_ids: Sequence[str], uptake_resource_ids: Sequence[str], scanner_resource_ids: Sequence[str],
) -> list[AuthorityFinding]:
    """HYBRID_LIVE_STATE_ADAPTER (part 2): shared clinical resource identities
    must never be duplicated per transport mode (e.g. a "CONV-SCN-001" and a
    separate "MRT-SCN-001" for what should be ONE physical scanner)."""
    findings: list[AuthorityFinding] = []
    for label, ids in (("injection", injection_resource_ids), ("uptake", uptake_resource_ids), ("scanner", scanner_resource_ids)):
        mode_prefixed = sorted({rid for rid in ids if rid and ("CONV-" in rid.upper() or "MRT-" in rid.upper())})
        if mode_prefixed:
            findings.append(_finding(
                "HYBRID_LIVE_STATE_ADAPTER",
                f"Mode-prefixed {label} resource id(s) found -- shared resource duplicated per transport mode: {mode_prefixed[:10]}",
                tuple(mode_prefixed)[:10],
            ))
    return findings


def validate_hybrid_mode_specific_impact(
    *,
    impact_classification: str,
    directly_affected_transport_modes: Sequence[str],
) -> list[AuthorityFinding]:
    """HYBRID_MODE_SPECIFIC_IMPACT: a CONVENTIONAL_SPECIFIC_IMPACT event must
    never directly affect an MRT-mode patient, and vice versa, unless the
    event is genuinely SHARED_RESOURCE_IMPACT."""
    if impact_classification == "CONVENTIONAL_SPECIFIC_IMPACT" and "MRT" in directly_affected_transport_modes:
        return [_finding(
            "HYBRID_MODE_SPECIFIC_IMPACT",
            "A CONVENTIONAL_SPECIFIC_IMPACT event directly affected an MRT-mode patient with no shared-resource justification.",
        )]
    if impact_classification == "MRT_SPECIFIC_IMPACT" and "Conventional" in directly_affected_transport_modes:
        return [_finding(
            "HYBRID_MODE_SPECIFIC_IMPACT",
            "An MRT_SPECIFIC_IMPACT event directly affected a Conventional-mode patient with no shared-resource justification.",
        )]
    return []


def validate_staff_shortfall_patient_targeting(
    *, max_required_concurrency: float, available_capacity: float, released_patient_ids: Sequence[str], candidate_patient_ids: Sequence[str],
) -> list[AuthorityFinding]:
    """STAFF_SHORTFALL_PATIENT_TARGETING: a genuine shortfall (required >
    available) must target at least one, but never MORE than the candidate
    set active during the shortfall interval (never every task in the day)."""
    findings: list[AuthorityFinding] = []
    genuine_shortfall = max_required_concurrency > available_capacity + 1e-9
    if genuine_shortfall and not released_patient_ids:
        findings.append(_finding(
            "STAFF_SHORTFALL_PATIENT_TARGETING",
            f"Required concurrency {max_required_concurrency} exceeds available capacity {available_capacity} but no patient task was targeted.",
        ))
    over_targeted = set(released_patient_ids) - set(candidate_patient_ids)
    if over_targeted:
        findings.append(_finding(
            "STAFF_SHORTFALL_PATIENT_TARGETING",
            f"{len(over_targeted)} released patient(s) were not part of the shortfall interval's candidate set (over-targeting): {sorted(over_targeted)[:10]}",
            tuple(sorted(over_targeted))[:10],
        ))
    return findings


def validate_staff_capacity_replan_result(
    *, final_concurrency: float, available_capacity: float, feasible: bool,
) -> list[AuthorityFinding]:
    """STAFF_CAPACITY_REPLAN: after a targeted replan, either the revised
    concurrency satisfies capacity, or the result is explicitly reported
    infeasible -- never a silent over-capacity result claimed as resolved."""
    if feasible and final_concurrency > available_capacity + 1e-9:
        return [_finding(
            "STAFF_CAPACITY_REPLAN",
            f"Replan reported feasible=True but final concurrency {final_concurrency} still exceeds available capacity {available_capacity}.",
        )]
    return []


def run_full_authority_validation(
    *,
    pathway: str,
    capex_ledger: Sequence[object] = (),
    opex_ledger: Sequence[object] = (),
    reported_capex: float | None = None,
    reported_opex: float | None = None,
    conventional_floors: frozenset = frozenset(),
    mrt_floors: frozenset = frozenset(),
    demand_patient_ids: Sequence[str] = (),
    clinical_patient_ids: Sequence[str] = (),
    decay_patient_ids: Sequence[str] = (),
    room_assignments: dict | None = None,
    stage_counts: Sequence[tuple[str, int]] = (),
    payload_cyclotron_ids: Sequence[str] = (),
    payload_origin_object_ids: Sequence[str] = (),
    registered_origin_object_id_by_cyclotron_id: dict | None = None,
) -> AuthorityValidationResult:
    """Top-level orchestrator (section 59): runs the applicable checks for a
    given candidate/study and returns ONE structured result distinguishing
    physical feasibility from architecture purity, economic reconciliation,
    patient traceability, room exclusivity, and conservation."""
    all_findings: list[AuthorityFinding] = []
    authority_checks: list[str] = []
    constraint_checks: list[str] = []
    conservation_checks: list[str] = []
    traceability_checks: list[str] = []
    economic_reconciliation_checks: list[str] = []

    if capex_ledger or opex_ledger:
        all_findings.extend(validate_architecture_purity(pathway=pathway, capex_ledger=capex_ledger, opex_ledger=opex_ledger))
        authority_checks.append("ARCHITECTURE_PURITY")

    if pathway == "Hybrid" and (conventional_floors or mrt_floors):
        all_findings.extend(validate_hybrid_zone_disjointness(conventional_floors=conventional_floors, mrt_floors=mrt_floors))
        authority_checks.append("HYBRID_UNION")

    if reported_capex is not None and reported_opex is not None and (capex_ledger or opex_ledger):
        all_findings.extend(validate_economic_reconciliation(capex_ledger=capex_ledger, reported_capex=reported_capex, opex_ledger=opex_ledger, reported_opex=reported_opex))
        economic_reconciliation_checks.append("ECONOMIC_RECONCILIATION")

    if demand_patient_ids or clinical_patient_ids or decay_patient_ids:
        all_findings.extend(validate_patient_traceability(demand_patient_ids=demand_patient_ids, clinical_patient_ids=clinical_patient_ids, decay_patient_ids=decay_patient_ids))
        traceability_checks.append("PATIENT_IDENTITY")

    if room_assignments:
        all_findings.extend(validate_room_exclusivity(room_assignments=room_assignments))
        constraint_checks.append("ROOM_EXCLUSIVITY")

    if stage_counts:
        all_findings.extend(validate_conservation_chain(stage_counts=stage_counts))
        conservation_checks.append("CONSERVATION_CHAIN")

    if payload_cyclotron_ids and registered_origin_object_id_by_cyclotron_id is not None:
        all_findings.extend(validate_cyclotron_spatial_origin_traceability(
            payload_cyclotron_ids=payload_cyclotron_ids,
            payload_origin_object_ids=payload_origin_object_ids,
            registered_origin_object_id_by_cyclotron_id=registered_origin_object_id_by_cyclotron_id,
        ))
        traceability_checks.append("CYCLOTRON_SPATIAL_ORIGIN")

    violations = tuple(f for f in all_findings if f.severity == "VIOLATION")
    warnings = tuple(f for f in all_findings if f.severity == "WARNING")

    optimality_status = "NOT_EVALUATED"

    return AuthorityValidationResult(
        passed=len(violations) == 0,
        violations=violations,
        warnings=warnings,
        authority_checks=tuple(authority_checks),
        constraint_checks=tuple(constraint_checks),
        conservation_checks=tuple(conservation_checks),
        traceability_checks=tuple(traceability_checks),
        economic_reconciliation=tuple(economic_reconciliation_checks),
        optimality_status=optimality_status,
    )
