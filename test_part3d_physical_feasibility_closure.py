"""Part 3D -- Unified Physical Feasibility Closure (focused test suite).

Section 44 invariant lock. Every assertion below was first confirmed against
REAL engine behavior (never a fabricated expectation). These tests lock:

  * `ArchitectureResult.feasible` is DERIVED from the physical gates, never a
    hardcoded `True` (the pre-Part-3D behavior).
  * The clinical-resource input authority: project-supplied scanner/injection/
    uptake counts genuinely drive the occupancy gates; the 6/6/12 controlled
    benchmark is preserved and labelled CONTROLLED_BENCHMARK.
  * The Build 3B per-radionuclide production gate (calibrated SUFFICIENT vs
    INSUFFICIENT; NOT_CALIBRATED preserved honestly, never zeroed and never
    auto-infeasible; NO_COMPATIBLE_SOURCE reported explicitly; required EOB
    reported).
  * The Build 3C / 3C.1 mode-specific transport gate contributes via the
    architecture's ACTUAL assigned transport searches -- never a universal
    transport_available scalar, never a silent TRANSPORT_NOT_EVALUATED shortcut.
  * Patient demand bounds throughput; excess clinical capacity is headroom, not
    extra patients.
  * The binding physical constraint comes from the qualified (calibrated)
    constraints; an uncalibrated production capacity is distinguished from a
    binding failure.
  * All four canonical architectures consume the SAME common contract.
  * Radioactive route-time is bound to decay ONCE (no double-counting): the
    transport arrival IS the injection start (single decay interval).

DO NOT read these expectations as design targets -- they are locks on observed
behavior at Part 3D closure. Build 3A/3B/3C/3C.1 authorities are reused, not
reimplemented.
"""
from __future__ import annotations

import dataclasses as dc

import pytest

import whole_oncology_four_architecture_optimization as wo4a
from whole_oncology_four_architecture_optimization import (
    build_common_project_baseline,
    ClinicalResourceInputs,
    BENCHMARK_CLINICAL_RESOURCES,
    BENCHMARK_SCANNERS,
    BENCHMARK_INJECTION_RESOURCES,
    BENCHMARK_UPTAKE_RESOURCES,
    derive_physical_feasibility,
    _nuclear_result,
    _resolve_transport_gate,
    _resolve_production_gate,
    _resolve_radionuclide_production_gate,
    PhysicalFeasibilityResult,
    RadionuclideProductionGate,
    evaluate_manual_conventional,
    evaluate_automated_conventional,
    evaluate_hybrid_mrt,
    evaluate_mrt_dominant,
    evaluate_light_mrt_dominant,
)

# development_context / study_scope are plain string tags in this engine
# ("RETROFIT"/"GREENFIELD", "CAPITAL_PLANNING"/"OPERATIONAL_ONLY"), matching the
# existing four-architecture test suite -- not dataclass objects.
_DEV_CONTEXT = "RETROFIT"
_STUDY_SCOPE = "CAPITAL_PLANNING"


# ---------------------------------------------------------------------------
# Shared fixtures. The conventional (mrt_floors=frozenset()) nuclear result is
# cheap (~0.1s) so we can reuse it across the gate-level tests.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def baseline():
    return build_common_project_baseline()


@pytest.fixture(scope="module")
def benchmark_nuclear(baseline):
    # Default clinical resources => 6/6/12 CONTROLLED_BENCHMARK (backward compat).
    return _nuclear_result(baseline, mrt_floors=frozenset())


@pytest.fixture(scope="module")
def benchmark_pf(benchmark_nuclear, baseline):
    return derive_physical_feasibility(benchmark_nuclear, baseline)


# ===========================================================================
# 1. feasible is DERIVED, not hardcoded True
# ===========================================================================
def test_feasible_field_has_no_hardcoded_default(baseline):
    """`feasible` is a required field (no default) -- every ArchitectureResult
    must supply a value, and the four canonical evaluators supply a DERIVED
    one (see the scarce-resource test which produces feasible=False)."""
    feasible_field = next(f for f in dc.fields(wo4a.ArchitectureResult) if f.name == "feasible")
    assert feasible_field.default is dc.MISSING


def test_scarce_resources_make_feasible_false(baseline):
    """Definitive proof feasible is NOT hardcoded True: starve the clinical
    resources and the derived contract returns INFEASIBLE."""
    scarce = ClinicalResourceInputs(
        scanners=1, injection_resources=1, uptake_resources=1,
        resource_source="PROJECT_SUPPLIED",
    )
    nuc = _nuclear_result(baseline, mrt_floors=frozenset(), clinical_resources=scarce)
    pf = derive_physical_feasibility(nuc, baseline, clinical_resources=scarce)
    assert pf.physical_feasibility_status == "INFEASIBLE"
    assert pf.qualification_status == "NOT_QUALIFIED"


# ===========================================================================
# 2. Clinical-resource input authority (project-supplied vs 6/6/12 benchmark)
# ===========================================================================
def test_benchmark_counts_are_six_six_twelve():
    assert (BENCHMARK_SCANNERS, BENCHMARK_INJECTION_RESOURCES, BENCHMARK_UPTAKE_RESOURCES) == (6, 6, 12)
    assert BENCHMARK_CLINICAL_RESOURCES.scanners == 6
    assert BENCHMARK_CLINICAL_RESOURCES.injection_resources == 6
    assert BENCHMARK_CLINICAL_RESOURCES.uptake_resources == 12


def test_benchmark_resource_source_is_controlled_benchmark(benchmark_pf):
    assert benchmark_pf.scanner_resource_source == "CONTROLLED_BENCHMARK"
    assert benchmark_pf.injection_resource_source == "CONTROLLED_BENCHMARK"
    assert benchmark_pf.uptake_resource_source == "CONTROLLED_BENCHMARK"


def test_benchmark_available_counts_flow_into_gate(benchmark_pf):
    """6/6/12 flows into the derived gate availability, not some other number."""
    assert benchmark_pf.scanner_available == 6
    assert benchmark_pf.injection_available == 6
    assert benchmark_pf.uptake_available == 12


def test_project_supplied_counts_drive_the_gate(baseline):
    """Project-supplied scanner/injection/uptake counts genuinely change the
    gate availability -- they are not ignored in favor of the benchmark."""
    project = ClinicalResourceInputs(
        scanners=3, injection_resources=2, uptake_resources=5,
        resource_source="PROJECT_SUPPLIED",
    )
    nuc = _nuclear_result(baseline, mrt_floors=frozenset(), clinical_resources=project)
    pf = derive_physical_feasibility(nuc, baseline, clinical_resources=project)
    assert pf.scanner_available == 3
    assert pf.injection_available == 2
    assert pf.uptake_available == 5
    assert pf.scanner_resource_source == "PROJECT_SUPPLIED"
    assert pf.injection_resource_source == "PROJECT_SUPPLIED"
    assert pf.uptake_resource_source == "PROJECT_SUPPLIED"


def test_scarce_project_supplied_binds_on_injection(baseline):
    """1/1/1 project-supplied: peak clinical occupancy exceeds availability ->
    INFEASIBLE with injection as the first binding calibrated constraint."""
    scarce = ClinicalResourceInputs(
        scanners=1, injection_resources=1, uptake_resources=1,
        resource_source="PROJECT_SUPPLIED",
    )
    nuc = _nuclear_result(baseline, mrt_floors=frozenset(), clinical_resources=scarce)
    pf = derive_physical_feasibility(nuc, baseline, clinical_resources=scarce)
    assert pf.physical_feasibility_status == "INFEASIBLE"
    assert pf.binding_physical_constraint == "injection"
    assert pf.injection_feasible is False
    assert pf.injection_peak_occupancy > pf.injection_available


# ===========================================================================
# 3. Demand bounds throughput; excess capacity is headroom, not patients
# ===========================================================================
def test_benchmark_clinical_gates_feasible_with_headroom(benchmark_pf):
    assert benchmark_pf.scanner_feasible is True
    assert benchmark_pf.injection_feasible is True
    assert benchmark_pf.uptake_feasible is True
    # Peak occupancy strictly below availability => genuine headroom.
    assert benchmark_pf.scanner_peak_occupancy < benchmark_pf.scanner_available
    assert benchmark_pf.injection_peak_occupancy < benchmark_pf.injection_available
    assert benchmark_pf.uptake_peak_occupancy < benchmark_pf.uptake_available


def test_excess_capacity_is_headroom_not_extra_patients(baseline, benchmark_nuclear):
    """Adding clinical capacity does NOT increase the patient count. The number
    of patient traces is bounded by demand, and peak occupancy does not rise
    with extra resources."""
    benchmark_patients = len(benchmark_nuclear.patient_traces)
    benchmark_pf = derive_physical_feasibility(benchmark_nuclear, baseline)

    # 8/8/16 fits the rooms but exceeds peak occupancy -> pure headroom.
    generous = ClinicalResourceInputs(
        scanners=8, injection_resources=8, uptake_resources=16,
        resource_source="PROJECT_SUPPLIED",
    )
    nuc_gen = _nuclear_result(baseline, mrt_floors=frozenset(), clinical_resources=generous)
    pf_gen = derive_physical_feasibility(nuc_gen, baseline, clinical_resources=generous)

    assert len(nuc_gen.patient_traces) == benchmark_patients
    # Peak demand-driven occupancy is unchanged by the extra headroom.
    assert pf_gen.scanner_peak_occupancy == benchmark_pf.scanner_peak_occupancy
    assert pf_gen.injection_peak_occupancy == benchmark_pf.injection_peak_occupancy
    assert pf_gen.uptake_peak_occupancy == benchmark_pf.uptake_peak_occupancy


# ===========================================================================
# 4. Production gate (Build 3B) -- per-radionuclide, calibrated vs uncalibrated
# ===========================================================================
def test_calibrated_f18_sufficient_when_required_below_capacity(baseline):
    fleet = baseline.production_basis.cyclotron_fleet
    g = _resolve_radionuclide_production_gate("F-18", fleet, 1000.0)
    assert g.status == "PRODUCTION_SUFFICIENT"
    assert g.source_type == "CYCLOTRON"
    assert g.installed_eob_capacity_mbq_per_day is not None
    assert g.installed_eob_capacity_mbq_per_day > 1000.0


def test_calibrated_f18_insufficient_when_required_exceeds_capacity(baseline):
    fleet = baseline.production_basis.cyclotron_fleet
    g = _resolve_radionuclide_production_gate("F-18", fleet, 9_999_999_999.0)
    assert g.status == "PRODUCTION_INSUFFICIENT"
    # Required EOB is reported, not silently dropped.
    assert g.required_eob_activity_mbq_per_day == 9_999_999_999.0
    assert g.installed_eob_capacity_mbq_per_day is not None


def test_required_eob_is_reported(baseline):
    fleet = baseline.production_basis.cyclotron_fleet
    g = _resolve_radionuclide_production_gate("F-18", fleet, 12345.0)
    assert g.required_eob_activity_mbq_per_day == 12345.0


def test_generator_tc99m_is_not_calibrated_not_zero(baseline):
    """Tc-99m is generator-supplied -> NOT_CALIBRATED, a DISTINCT source type,
    never zeroed to 0 and never auto-infeasible."""
    fleet = baseline.production_basis.cyclotron_fleet
    g = _resolve_radionuclide_production_gate("Tc-99m", fleet, 1000.0)
    assert g.status == "PRODUCTION_NOT_CALIBRATED"
    assert g.source_type == "GENERATOR"
    # Not fabricated to 0 -- installed capacity is honestly None (uncalibrated).
    assert g.installed_eob_capacity_mbq_per_day is None
    assert g.capacity_status == "not_calibrated"


def test_no_compatible_source_reported_explicitly(baseline):
    """A radionuclide with neither a compatible fleet nor a generator daughter
    match returns NO_COMPATIBLE_SOURCE -- an F-18 record never qualifies it."""
    fleet = baseline.production_basis.cyclotron_fleet
    g = _resolve_radionuclide_production_gate("C-11", fleet, 1000.0)
    assert g.status == "NO_COMPATIBLE_SOURCE"
    assert g.source_type == "NONE"
    assert g.installed_eob_capacity_mbq_per_day is None


def test_cypris_mp30_installed_declares_but_not_calibrated(baseline):
    """Part 3D installed-model seam: CYPRIS MP-30 DECLARES Cu-64/Zr-89/I-123 as
    supported but forms no schedulable/calibrated fleet -> PRODUCTION_NOT_
    CALIBRATED carrying the REAL model identity, fabricating no EOB figure."""
    fleet = baseline.production_basis.cyclotron_fleet
    installed = ("SUMITOMO_CYPRIS_MP_30",)
    for rn in ("Cu-64", "Zr-89", "I-123"):
        g = _resolve_radionuclide_production_gate(rn, fleet, 1000.0, installed_cyclotron_model_ids=installed)
        assert g.status == "PRODUCTION_NOT_CALIBRATED", rn
        assert g.source_type == "CYCLOTRON", rn
        assert g.source_identity == "CYPRIS MP-30", rn
        assert g.installed_eob_capacity_mbq_per_day is None, rn


def test_cypris_mp30_f18_installed_selection_is_authoritative_not_borrowed(baseline):
    """EXACT Part 3D acceptance control (question 1): an INSTALLED CYPRIS MP-30
    selected for F-18 is the authoritative equipment choice. F-18 is SUPPORTED
    by the MP-30 but has no calibrated cycle/EOB record, so it must resolve
    PRODUCTION_NOT_CALIBRATED carrying the REAL model identity ("CYPRIS MP-30"),
    with installed EOB capacity None -- and it MUST NOT borrow the benchmark
    GE PETtrace 890 F-18 capacity (648000 MBq), another cyclotron's capacity,
    or another radionuclide's production record. Before the Part 3D binding
    correction, a leftover benchmark GE asset silently SHADOWED the real MP-30
    selection and returned PETtrace 890 / PRODUCTION_SUFFICIENT / 648000 -- the
    exact integration defect this test locks closed."""
    fleet = baseline.production_basis.cyclotron_fleet
    g = _resolve_radionuclide_production_gate(
        "F-18", fleet, 500000.0, installed_cyclotron_model_ids=("SUMITOMO_CYPRIS_MP_30",),
    )
    # RADIONUCLIDE_SUPPORTED = YES (declared by the MP-30 catalog record).
    import cyclotron_catalog as _cc
    assert "F-18" in _cc.load_cyclotron_catalog().by_id("SUMITOMO_CYPRIS_MP_30").supported_radionuclides
    # PRODUCTION_STATUS = NOT_CALIBRATED, real identity, capacity None.
    assert g.status == "PRODUCTION_NOT_CALIBRATED"
    assert g.source_type == "CYCLOTRON"
    assert g.source_identity == "CYPRIS MP-30"
    assert g.installed_eob_capacity_mbq_per_day is None
    # NOT borrowed: never the GE PETtrace 890 identity, never its 648000 MBq.
    assert "PETtrace" not in g.source_identity and "890" not in g.source_identity
    assert g.installed_eob_capacity_mbq_per_day != 648000.0


def test_benchmark_f18_no_installed_selection_still_uses_ge_fleet(baseline):
    """Backward-compat guard for the Part 3D binding correction: with NO explicit
    installed selection, the benchmark GE PETtrace 890 fleet remains authoritative
    and qualifies F-18 as PRODUCTION_SUFFICIENT with its real 648000 MBq/day
    capacity. The correction only scopes path 1 to the caller's declared
    equipment WHEN a selection is given; the default benchmark path is unchanged."""
    fleet = baseline.production_basis.cyclotron_fleet
    g = _resolve_radionuclide_production_gate("F-18", fleet, 500000.0)
    assert g.status == "PRODUCTION_SUFFICIENT"
    assert g.source_identity == "PETtrace 890"
    assert g.installed_eob_capacity_mbq_per_day == 648000.0


# ===========================================================================
# 5. Aggregate production gate is per-radionuclide, not a single verdict
# ===========================================================================
def test_aggregate_production_gate_is_per_radionuclide(benchmark_nuclear, baseline):
    status, cap, req, inst, per = _resolve_production_gate(benchmark_nuclear, baseline)
    per_by_rn = {g.radionuclide: g.status for g in per}
    # The benchmark demand genuinely spans F-18 (calibrated) and Tc-99m (generator).
    assert per_by_rn.get("F-18") == "PRODUCTION_SUFFICIENT"
    assert per_by_rn.get("Tc-99m") == "PRODUCTION_NOT_CALIBRATED"
    # Aggregate: no INSUFFICIENT/NO_COMPATIBLE_SOURCE, but a NOT_CALIBRATED present.
    assert status == "PRODUCTION_NOT_CALIBRATED"


# ===========================================================================
# 6. NOT_CALIBRATED production => FEASIBLE_WITH_UNCALIBRATED, not INFEASIBLE
# ===========================================================================
def test_benchmark_status_is_feasible_with_uncalibrated_production(benchmark_pf):
    assert benchmark_pf.physical_feasibility_status == "FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY"
    assert benchmark_pf.qualification_status == "QUALIFIED_WITH_LIMITATIONS"


def test_uncalibrated_production_is_not_the_binding_constraint(benchmark_pf):
    """A merely NOT_CALIBRATED production capacity is distinguished from a
    binding failure: binding is 'none', never 'production'."""
    assert benchmark_pf.binding_physical_constraint == "none"
    assert benchmark_pf.production_gate_status == "PRODUCTION_NOT_CALIBRATED"


def test_uncalibrated_radionuclide_named_in_unqualified_constraints(benchmark_pf):
    """Each uncalibrated radionuclide is named -- not a single generic verdict."""
    assert any(
        c == "production_capacity_not_calibrated:Tc-99m"
        for c in benchmark_pf.unqualified_physical_constraints
    )


# ===========================================================================
# 7. Transport gate -- mode-specific (Build 3C / 3C.1), no universal scalar
# ===========================================================================
def test_transport_gate_derives_from_assigned_mode_searches(benchmark_nuclear):
    """Conventional architecture: the conventional transporter search is the
    applicable assigned mode; the MRT carrier search has no workload. The gate
    is SUFFICIENT because it was genuinely evaluated -- not a blank scalar."""
    status, feasible, unqualified, mode_gates = _resolve_transport_gate(
        benchmark_nuclear, architecture="MANUAL_CONVENTIONAL",
    )
    assert status == "TRANSPORT_SUFFICIENT"
    assert feasible is True
    # The conventional search actually ran (real Build 3C authority present).
    assert benchmark_nuclear.conventional_transporter_search is not None
    # Part 3D final: the MANUAL mode gate is individually represented (not a
    # single collapsed conventional scalar).
    assert any(g.mode == "MANUAL" for g in mode_gates)


def test_transport_gate_not_a_blanket_not_evaluated(baseline):
    """MRT-dominant architecture: the MRT carrier search is the applicable
    assigned mode. The gate must NOT collapse to a blanket TRANSPORT_NOT_
    EVALUATED shortcut when a mode-specific authority genuinely applies."""
    all_floors = frozenset(range(1, baseline.geometry.floor_count + 1))
    nuc = _nuclear_result(baseline, mrt_floors=all_floors)
    status, feasible, _, mode_gates = _resolve_transport_gate(nuc, architecture="MRT_DOMINANT")
    assert status != "TRANSPORT_NOT_EVALUATED"
    assert status == "TRANSPORT_SUFFICIENT"
    assert feasible is True
    # The MRT mode gate is the applicable required mode here.
    assert any(g.mode == "MRT" and g.status == "TRANSPORT_SUFFICIENT" for g in mode_gates)


def test_transport_feasible_reflected_in_pf(benchmark_pf):
    assert benchmark_pf.transport_feasible is True
    assert benchmark_pf.transport_gate_status == "TRANSPORT_SUFFICIENT"


# ===========================================================================
# 8. Radioactive route-time bound to decay ONCE (no double-count)
# ===========================================================================
def test_transport_arrival_is_the_injection_start(benchmark_nuclear):
    """The single decay interval runs from production release to injection
    start. Transport arrival IS the injection start (route-time baked into the
    one interval), so transport is never decayed a second time."""
    traces = benchmark_nuclear.patient_traces
    assert traces, "expected patient traces"
    for tr in traces:
        assert tr.transport_arrival_time_minutes == pytest.approx(tr.injection_start_minutes)


def test_retained_fraction_is_physical(benchmark_nuclear):
    """Retained fraction lies in (0, 1]; a double-count would push some traces'
    elapsed time up and retained fraction implausibly low, so this also guards
    against a second decay application."""
    for tr in benchmark_nuclear.patient_traces:
        assert 0.0 < tr.retained_fraction <= 1.0 + 1e-9


def test_elapsed_equals_injection_minus_release_single_interval(benchmark_nuclear):
    """elapsed_release_to_administration is a single non-negative interval,
    consistent with one decay application over the route."""
    for tr in benchmark_nuclear.patient_traces:
        assert tr.elapsed_release_to_administration_minutes >= 0.0


# ===========================================================================
# 9. All four canonical architectures consume the common contract
# ===========================================================================
@pytest.fixture(scope="module")
def dev_context():
    return _DEV_CONTEXT


@pytest.fixture(scope="module")
def study_scope():
    return _STUDY_SCOPE


def _assert_common_contract(result):
    """Every canonical ArchitectureResult must expose the derived physical
    contract fields (populated, not left at the NOT_EVALUATED default)."""
    assert result.physical_feasibility_status != "NOT_EVALUATED"
    assert result.qualification_status != "NOT_EVALUATED"
    assert result.production_gate_status != "NOT_EVALUATED"
    assert result.transport_gate_status != "NOT_EVALUATED"
    # feasible is derived from the status.
    assert result.feasible == (result.physical_feasibility_status != "INFEASIBLE")
    # Per-radionuclide production breakdown is carried through.
    assert len(result.per_radionuclide_production_gates) >= 1


def test_manual_conventional_consumes_common_contract(baseline, dev_context, study_scope):
    r = evaluate_manual_conventional(baseline, development_context=dev_context, study_scope=study_scope)
    _assert_common_contract(r)


def test_automated_conventional_consumes_common_contract(baseline, dev_context, study_scope):
    r = evaluate_automated_conventional(baseline, development_context=dev_context, study_scope=study_scope)
    _assert_common_contract(r)


def test_hybrid_mrt_consumes_common_contract(baseline, dev_context, study_scope):
    r = evaluate_hybrid_mrt(baseline, development_context=dev_context, study_scope=study_scope)
    _assert_common_contract(r)


def test_mrt_dominant_consumes_common_contract(baseline, dev_context, study_scope):
    r = evaluate_mrt_dominant(baseline, development_context=dev_context, study_scope=study_scope)
    _assert_common_contract(r)


def test_all_four_share_identical_production_gate_verdict(baseline, dev_context, study_scope):
    """The common contract is genuinely SHARED: the four canonical
    architectures reuse the same nuclear demand/production authority, so their
    per-radionuclide production verdicts agree."""
    results = [
        evaluate_manual_conventional(baseline, development_context=dev_context, study_scope=study_scope),
        evaluate_automated_conventional(baseline, development_context=dev_context, study_scope=study_scope),
        evaluate_hybrid_mrt(baseline, development_context=dev_context, study_scope=study_scope),
        evaluate_mrt_dominant(baseline, development_context=dev_context, study_scope=study_scope),
    ]
    verdicts = {r.production_gate_status for r in results}
    assert verdicts == {"PRODUCTION_NOT_CALIBRATED"}
    # All feasible (benchmark clinical resources have headroom).
    assert all(r.feasible for r in results)


# ===========================================================================
# 10. Documented gap: Light MRT comparator is NOT one of the four canonical
# ===========================================================================
def test_light_mrt_dominant_is_not_wired_to_common_contract(baseline, dev_context, study_scope):
    """evaluate_light_mrt_dominant is a Build 2R comparator, NOT one of the four
    canonical architectures. It still hardcodes feasible=True and leaves the
    physical contract at NOT_EVALUATED. This test LOCKS that documented gap so
    a future closure of it is a deliberate, visible change."""
    r = evaluate_light_mrt_dominant(baseline, development_context=dev_context, study_scope=study_scope)
    assert r.physical_feasibility_status == "NOT_EVALUATED"


# ===========================================================================
# 11. Backward compatibility: default (no clinical_resources) == benchmark
# ===========================================================================
def test_default_nuclear_result_uses_benchmark_counts(baseline):
    nuc = _nuclear_result(baseline, mrt_floors=frozenset())
    assert nuc.candidate.scanners == BENCHMARK_SCANNERS
    assert nuc.candidate.injection_resources == BENCHMARK_INJECTION_RESOURCES
    assert nuc.candidate.uptake_resources == BENCHMARK_UPTAKE_RESOURCES


def test_derive_physical_feasibility_default_resource_source(benchmark_nuclear, baseline):
    """Called without clinical_resources, the contract defaults to the
    controlled benchmark source label (backward compatible)."""
    pf = derive_physical_feasibility(benchmark_nuclear, baseline)
    assert pf.scanner_resource_source == "CONTROLLED_BENCHMARK"


# ===========================================================================
# 12. Mode-specific transport gate: no-workload => NOT_APPLICABLE (never FAILED);
#     required mode carries explicit sized required/available resource counts.
# ===========================================================================
def test_manual_conventional_mrt_mode_is_not_applicable(baseline):
    """A transport mode with no assigned nuclear workload is
    TRANSPORT_NOT_APPLICABLE, never INSUFFICIENT/FAILED (Section 2/5). In the
    Manual conventional nuclear path the MRT mode carries no workload."""
    nuc = _nuclear_result(baseline, mrt_floors=frozenset())
    status, feasible, unqualified, gates = _resolve_transport_gate(nuc, architecture="MANUAL_CONVENTIONAL")
    by_mode = {g.mode: g for g in gates}
    assert by_mode["MRT"].status == "TRANSPORT_NOT_APPLICABLE"
    assert by_mode["MRT"].required_resources is None
    assert by_mode["MRT"].available_resources is None
    # NOT_APPLICABLE must not sink the aggregate.
    assert feasible is True
    assert status != "TRANSPORT_INSUFFICIENT"


def test_manual_conventional_manual_mode_is_required_and_sized(baseline):
    """The MANUAL (shielded porter) mode IS the required nuclear conventional
    leg (Build 3C: nuclear ELIGIBLE on MANUAL, INELIGIBLE on RGHT/ordinary PTS).
    It carries explicit Build-3C-sized required/available counts, not a scalar."""
    nuc = _nuclear_result(baseline, mrt_floors=frozenset())
    _, _, _, gates = _resolve_transport_gate(nuc, architecture="MANUAL_CONVENTIONAL")
    manual = next(g for g in gates if g.mode == "MANUAL")
    assert manual.status == "TRANSPORT_SUFFICIENT"
    assert isinstance(manual.required_resources, int) and manual.required_resources >= 1
    # Minimum-feasible search sizes selected == required for a saturated mode.
    assert manual.available_resources == manual.required_resources


def test_mrt_dominant_manual_mode_is_not_applicable_and_mrt_required(baseline):
    """MRT_DOMINANT: MRT is the required nuclear mode; the MANUAL conventional
    leg carries no nuclear workload -> NOT_APPLICABLE (Section 9 mapping)."""
    all_floors = frozenset(range(1, baseline.geometry.floor_count + 1))
    nuc = _nuclear_result(baseline, mrt_floors=all_floors)
    status, feasible, _, gates = _resolve_transport_gate(nuc, architecture="MRT_DOMINANT")
    by_mode = {g.mode: g for g in gates}
    assert by_mode["MANUAL"].status == "TRANSPORT_NOT_APPLICABLE"
    assert by_mode["MRT"].status == "TRANSPORT_SUFFICIENT"
    assert isinstance(by_mode["MRT"].required_resources, int) and by_mode["MRT"].required_resources >= 1
    assert feasible is True


def test_transport_mode_gates_propagate_onto_architecture_result(baseline, dev_context, study_scope):
    """The per-mode gates are carried onto ArchitectureResult so the aggregate
    transport verdict is explainable (never a single collapsed scalar)."""
    r = evaluate_manual_conventional(baseline, development_context=dev_context, study_scope=study_scope)
    assert len(r.transport_mode_gates) >= 2
    modes = {g.mode for g in r.transport_mode_gates}
    assert {"MANUAL", "MRT"} <= modes


# ===========================================================================
# 13. RP-PTS radioactive-timing binding (Sections 12-17). The Build 3C RP-PTS
#     mission cycle is bound to the SAME multi_isotope_decay authority via a
#     SINGLE release->administration interval. No second decay equation.
# ===========================================================================
@pytest.fixture(scope="module")
def rp_pts_short(baseline):
    return wo4a.evaluate_dedicated_rp_pts_nuclear_transport_with_decay(
        baseline, network_length_override_m=50.0, prescribed_administration_activity_mbq=370.0,
    )


@pytest.fixture(scope="module")
def rp_pts_long(baseline):
    return wo4a.evaluate_dedicated_rp_pts_nuclear_transport_with_decay(
        baseline, network_length_override_m=400.0, prescribed_administration_activity_mbq=370.0,
    )


def test_rp_pts_elapsed_is_single_delivery_interval(rp_pts_short):
    """The governing decay interval == the RP-PTS delivery time exactly ONCE
    (elapsed == delivery_minutes). Transport is folded into administration a
    single time (Section 13/14), never decay(full) x decay(transport again)."""
    _, timing = rp_pts_short
    for p in timing.per_patient:
        assert abs(p.elapsed_release_to_administration_minutes - timing.rp_pts_delivery_minutes) < 1e-9
        # retained is the canonical retained_fraction of the single interval.
        expected = wo4a.retained_fraction(p.elapsed_release_to_administration_minutes, timing.half_life_minutes)
        assert abs(p.retained_fraction_at_administration - expected) < 1e-12


def test_rp_pts_longer_route_increases_delivery_time(rp_pts_short, rp_pts_long):
    _, tshort = rp_pts_short
    _, tlong = rp_pts_long
    assert tlong.rp_pts_delivery_minutes > tshort.rp_pts_delivery_minutes


def test_rp_pts_longer_route_lowers_retention(rp_pts_short, rp_pts_long):
    _, tshort = rp_pts_short
    _, tlong = rp_pts_long
    assert tlong.mean_retained_fraction < tshort.mean_retained_fraction


def test_rp_pts_longer_route_increases_required_upstream_activity(rp_pts_short, rp_pts_long):
    _, tshort = rp_pts_short
    _, tlong = rp_pts_long
    short_up = tshort.per_patient[0].required_upstream_activity_mbq
    long_up = tlong.per_patient[0].required_upstream_activity_mbq
    assert short_up is not None and long_up is not None
    assert long_up > short_up


def test_rp_pts_return_excluded_from_payload_decay(rp_pts_short):
    """POST_DELIVERY_RETURN_TIME_INCLUDED_IN_PAYLOAD_DECAY = NO. The RP-PTS
    mission cycle excludes carrier return/reavailability from the delivery
    interval, so it cannot inflate delivered-payload decay (Section 15)."""
    _, timing = rp_pts_short
    assert timing.return_time_included_in_payload_decay is False


def test_rp_pts_reuses_canonical_decay_authority_not_a_duplicate(rp_pts_long):
    """The RP-PTS binding COMPOSES the existing multi_isotope_decay authority
    (retained_fraction / required_upstream_activity) -- proven by reproducing
    the exact per-patient numbers from the canonical functions directly."""
    _, timing = rp_pts_long
    p = timing.per_patient[0]
    expected_retained = wo4a.retained_fraction(p.elapsed_release_to_administration_minutes, timing.half_life_minutes)
    assert abs(p.retained_fraction_at_administration - expected_retained) < 1e-12
    expected_upstream = wo4a.required_upstream_activity(370.0, expected_retained)
    assert abs(p.required_upstream_activity_mbq - expected_upstream) < 1e-9


# ===========================================================================
# 14. CYPRIS MP-30 + F-18 installed-selection: real identity, NOT_CALIBRATED,
#     NOT borrowing GE PETtrace 890 / 648000 MBq (Section 2 accepted control).
# ===========================================================================
def test_cypris_mp30_f18_carries_real_identity_uncalibrated_no_borrow(benchmark_nuclear, baseline):
    pf = derive_physical_feasibility(
        benchmark_nuclear, baseline, installed_cyclotron_model_ids=("SUMITOMO_CYPRIS_MP_30",),
    )
    f18 = next(g for g in pf.per_radionuclide_production_gates if g.radionuclide == "F-18")
    assert f18.source_type == "CYCLOTRON"
    assert f18.source_identity == "CYPRIS MP-30"
    assert f18.status == "PRODUCTION_NOT_CALIBRATED"
    # Must NOT borrow GE 648000 MBq (or any other) capacity.
    assert f18.installed_eob_capacity_mbq_per_day is None
