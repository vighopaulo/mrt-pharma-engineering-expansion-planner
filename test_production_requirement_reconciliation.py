"""Controlled regression coverage for the PLANNED vs REALIZED production requirement
reconciliation pass (see decision_pipeline.py: ProductionRequirementReconciliation,
_build_production_requirement_reconciliation).

Proves:
- downstream scheduling timing differences from the provisional plan are detected and
  reported per cycle (not silently absorbed);
- a realized cycle that exceeds calibrated capacity is never considered finally
  reconciled feasible;
- a genuinely converged schedule (no capacity violations) reports a stable, bounded
  reconciliation with final_reconciled == realized;
- the old common-early-EOB diagnostic never becomes the final reconciled authority.
"""

from __future__ import annotations

from dataclasses import replace

from cyclotron_production_windows import CyclotronProductionCapability
from decision_pipeline import NativeDecisionPipelineScenario, run_native_decision_pipeline
from models import SharedNetworkAssumptions

import test_decision_pipeline as tdp


def _scenario(**overrides) -> NativeDecisionPipelineScenario:
    defaults = dict(
        project_name="Reconciliation Test",
        target_patients_per_day=30,
        radionuclide_mix={"F-18": 1.0},
        activity_distribution_by_radionuclide={"F-18": tdp.ActivityDemandModel("fixed", fixed_activity_mbq=370.0)},
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="F18-RECON",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 120.0},
            calibrated_eob_activity_mbq_by_radionuclide={"F-18": 648_000.0},
        ),
        conventional=tdp._conventional_pathway(),
        mrt=tdp._mrt_pathway(),
        planner_assumptions=replace(tdp._planner_assumptions(), default_clinical_administration_cohorts_per_day=6),
        shared_network_assumptions=SharedNetworkAssumptions(),
        day_type="typical",
        seed=20260914,
        operating_day_minutes=1080.0,
        production_start_time_minutes=-240.0,
        production_horizon_minutes=960.0,
        batch_target_patients_per_batch=20,
    )
    defaults.update(overrides)
    return NativeDecisionPipelineScenario(**defaults)


def test_planned_vs_realized_difference_is_detected_and_reported() -> None:
    """Section 19 / controlled test 19."""
    result = run_native_decision_pipeline(_scenario(target_patients_per_day=60))
    for pathway in (result.conventional, result.mrt):
        rec = pathway.operational_result.production_requirement_reconciliation
        assert rec is not None
        assert rec.realized_eob_activity_mbq != rec.planned_eob_activity_mbq
        divergent_statuses = {"RECONCILIATION_REQUIRED", "REALIZED_ONLY", "PLANNED_ONLY"}
        assert any(row.status in divergent_statuses for row in rec.per_cycle)


def test_realized_capacity_overflow_is_never_finally_reconciled_feasible() -> None:
    """Section 20 / controlled test 20: planned <= capacity but realized > capacity."""
    request = _scenario(
        target_patients_per_day=4,
        activity_distribution_by_radionuclide={"F-18": tdp.ActivityDemandModel("fixed", fixed_activity_mbq=600.0)},
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="F18-OVF",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 120.0},
            calibrated_eob_activity_mbq_by_radionuclide={"F-18": 500.0},
        ),
        planner_assumptions=replace(tdp._planner_assumptions(), default_clinical_administration_cohorts_per_day=1),
        production_start_time_minutes=0.0,
        production_horizon_minutes=600.0,
    )
    result = run_native_decision_pipeline(request)
    for pathway in (result.conventional, result.mrt):
        rec = pathway.operational_result.production_requirement_reconciliation
        diag = pathway.operational_result.production_schedule_diagnostic
        assert rec is not None
        # Since the plan-to-scheduler unification build, a cycle the planner marked
        # SCHEDULED_ACTIVITY_INFEASIBLE is vetoed outright (never executed with excess
        # activity) rather than being realized over capacity: it surfaces as an
        # unscheduled/rejected batch (PLANNED_ONLY), and whole-demand production is not
        # feasible as a result.
        assert diag.unscheduled_batch_count > 0
        assert any(row.status == "PLANNED_ONLY" for row in rec.per_cycle)


def test_stable_reconciliation_converges_with_bounded_iterations() -> None:
    """Section 21 / controlled test 21."""
    request = _scenario(
        target_patients_per_day=30,
        cyclotron_capability=CyclotronProductionCapability(
            cyclotron_id="F18-STABLE",
            supported_radionuclides=("F-18",),
            max_simultaneous_production_streams=1,
            production_cycle_minutes_by_radionuclide={"F-18": 30.0},
            calibrated_eob_activity_mbq_by_radionuclide={"F-18": 1_000_000.0},
        ),
        planner_assumptions=replace(tdp._planner_assumptions(), default_clinical_administration_cohorts_per_day=1),
        production_start_time_minutes=0.0,
        production_horizon_minutes=30.0,
    )
    result = run_native_decision_pipeline(request)
    for pathway in (result.conventional, result.mrt):
        rec = pathway.operational_result.production_requirement_reconciliation
        assert rec is not None
        assert rec.convergence_status == "CONVERGED"
        assert 1 <= rec.iterations_used <= 64
        assert all(row.status != "CAPACITY_EXCEEDED" for row in rec.per_cycle)
        assert rec.final_reconciled_eob_activity_mbq == rec.realized_eob_activity_mbq


def test_reconciliation_never_restores_common_early_eob_authority() -> None:
    """Section 22 / controlled test 22."""
    result = run_native_decision_pipeline(_scenario(target_patients_per_day=200))
    for pathway in (result.conventional, result.mrt):
        rec = pathway.operational_result.production_requirement_reconciliation
        assert rec is not None
        diagnostic_total = sum(
            pathway.operational_result.demand_result.non_authoritative_common_early_eob_activity_mbq_by_radionuclide.values()
        )
        # The old common-early-EOB diagnostic must remain far larger than (and structurally
        # disconnected from) the final reconciled authority.
        assert rec.final_reconciled_eob_activity_mbq < diagnostic_total
        assert rec.final_reconciled_eob_activity_mbq < diagnostic_total / 5.0
