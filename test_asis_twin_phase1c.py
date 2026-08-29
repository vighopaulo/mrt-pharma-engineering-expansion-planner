"""EXISTING FACILITY / AS-IS DIGITAL TWIN -- PHASE 1C controls & invariants.

Phase 1C strengthens the NORMALIZED AS-IS facility model: explicit facility
hierarchy, clinical-space classification (separate from geometry), engineering-
object identity vs placement bindings, connectivity/topology + route readiness,
operational-resource placeholders, field-level evidence conflicts, per-domain
completeness, and distinct readiness gates. Still PRE-SIMULATION: no routing
physics, no operational-state reconstruction, no LOCKDOWN/What-If.

These tests assert the Sec 25-29 controls and the governing invariants. They
never modify Phase 1B contracts (test_asis_twin_phase1b.py covers those).

Real catalog identities used (never fabricated):
  PET scanner   = GE_DISCOVERY_MI
  SPECT scanner = SIEMENS_SYMBIA_PRO_SPECTA
  cyclotron     = GE_PETTRACE_890
  generator     = CURIUM_TECHNELITE
"""

from __future__ import annotations

from existing_facility_asis_twin import (
    AsIsBuildingInput,
    AsIsConflictingEvidenceInput,
    AsIsEquipmentInput,
    AsIsEquipmentPlacementInput,
    AsIsFacilityIdentityInput,
    AsIsFloorInput,
    AsIsRoomInput,
    AsIsRouteOrConnectivityInput,
    AsIsStructuredFacilityInput,
    ExistingFacilityAsIsTwinResult,
    ingest_structured_facility,
)

PET_MODEL = "GE_DISCOVERY_MI"
SPECT_MODEL = "SIEMENS_SYMBIA_PRO_SPECTA"
CYCLOTRON_MODEL = "GE_PETTRACE_890"
GENERATOR_MODEL = "CURIUM_TECHNELITE"


def _domain(result: ExistingFacilityAsIsTwinResult, domain: str):
    return next(d for d in result.domain_completeness if d.domain == domain)


# ===========================================================================
# CONTROL A (Sec 25) -- STRUCTURED FACILITY WITH PARTIAL MODEL.
# ===========================================================================
def _control_a_input() -> AsIsStructuredFacilityInput:
    return AsIsStructuredFacilityInput(
        facility=AsIsFacilityIdentityInput(facility_id="FAC-A", facility_name="Alpha Nuclear", site_id="SITE-A"),
        buildings=(AsIsBuildingInput(building_id="B1", building_name="Main"),),
        floors=(
            AsIsFloorInput(building_id="B1", floor_id="F1", elevation_m=0.0),
            AsIsFloorInput(building_id="B1", floor_id="F2", elevation_m=4.0),
        ),
        rooms=(
            # Known geometry + known function.
            AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R-PET", room_function="PET_SCANNER",
                          length_m=6.0, width_m=5.0, height_m=3.0),
            AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R-INJ", room_function="INJECTION_ROOM",
                          length_m=4.0, width_m=3.0, height_m=3.0),
            # Known geometry + UNKNOWN function (at least one).
            AsIsRoomInput(building_id="B1", floor_id="F2", room_id="R-UNK", length_m=4.0, width_m=4.0, height_m=3.0),
        ),
        equipment=(
            # One placed, one unplaced.
            AsIsEquipmentInput(equipment_instance_id="SCN-PET-1", equipment_class="PET_SCANNER", catalog_model_id=PET_MODEL),
            AsIsEquipmentInput(equipment_instance_id="GEN-1", equipment_class="GENERATOR", catalog_model_id=GENERATOR_MODEL),
        ),
        equipment_placements=(
            AsIsEquipmentPlacementInput(equipment_instance_id="SCN-PET-1", room_id="R-PET"),
        ),
        # Partial topology: one link supplied of many possible.
        routes=(AsIsRouteOrConnectivityInput(from_object_id="R-PET", to_object_id="R-INJ", length_m=8.0),),
    )


def test_control_a_hierarchy_is_explicit_and_queryable():
    r = ingest_structured_facility(_control_a_input())
    hv = r.facility_hierarchy
    assert hv is not None
    assert hv.facility_id == "FAC-A"
    assert hv.site_id == "SITE-A"
    # Explicit levels present and queryable.
    assert {n.level for n in hv.nodes} == {"FACILITY", "BUILDING", "FLOOR", "ROOM"}
    # Room parentage explicit (R-PET -> its floor -> building).
    pet = hv.node("R-PET")
    assert pet is not None and pet.parent_object_id is not None
    # Building has floor children.
    building = next(n for n in hv.nodes_at_level("BUILDING"))
    assert len(building.child_object_ids) == 2


def test_control_a_partial_model_domains_are_independent():
    r = ingest_structured_facility(_control_a_input())
    # Some functions known, at least one unknown.
    assert _domain(r, "GEOMETRY").status == "COMPLETE"
    assert _domain(r, "CLINICAL_SPACE_CLASSIFICATION").status == "PARTIAL"
    # Equipment identity complete, placement partial.
    assert _domain(r, "ENGINEERING_OBJECT_IDENTITY").status == "COMPLETE"
    assert _domain(r, "EQUIPMENT_PLACEMENT").status == "PARTIAL"
    # Topology partial.
    assert _domain(r, "CONNECTIVITY_TOPOLOGY").status == "PARTIAL"


def test_control_a_provenance_and_calibration_independent():
    r = ingest_structured_facility(_control_a_input())
    # Provenance is present for every fact; calibration is a separate axis.
    assert _domain(r, "PROVENANCE").status == "COMPLETE"
    # A known-geometry room still yields KNOWN classification with its own provenance.
    pet_cls = next(c for c in r.space_classifications if c.spatial_object_id == "R-PET")
    assert pet_cls.status == "KNOWN"
    assert pet_cls.classification == "PET_SCANNER_ROOM"


def test_control_a_no_benchmark_fill():
    r = ingest_structured_facility(_control_a_input())
    # No benchmark cyclotron, MRT, clinical counts or population inserted.
    assert r.facility_cyclotron_count == 0
    assert r.benchmark_cyclotron_inserted is False
    assert r.mrt_infrastructure_count == 0
    assert r.benchmark_mrt_inserted is False
    op = _domain(r, "OPERATIONAL_RESOURCE_IDENTITY")
    # Staffing/transport identity absent (never benchmark-filled).
    assert op.status in ("PARTIAL", "NOT_MODELED")


# ===========================================================================
# CONTROL B (Sec 26) -- NO MRT.
# ===========================================================================
def test_control_b_no_mrt():
    si = AsIsStructuredFacilityInput(
        facility=AsIsFacilityIdentityInput(facility_id="FAC-B", facility_name="Beta"),
        buildings=(AsIsBuildingInput(building_id="B1"),),
        floors=(AsIsFloorInput(building_id="B1", floor_id="F1"),),
        rooms=(AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R1", room_function="PET_SCANNER",
                             length_m=6.0, width_m=5.0, height_m=3.0),),
        equipment=(AsIsEquipmentInput(equipment_instance_id="SCN-1", equipment_class="PET_SCANNER", catalog_model_id=PET_MODEL),),
        equipment_placements=(AsIsEquipmentPlacementInput(equipment_instance_id="SCN-1", room_id="R1"),),
    )
    r = ingest_structured_facility(si)
    assert r.mrt_infrastructure_count == 0            # MRT_INFRASTRUCTURE_COUNT = 0
    assert r.benchmark_mrt_inserted is False           # BENCHMARK_MRT_INSERTED = NO
    assert r.mrt_required_for_engineering_model_ready is False  # MRT not required
    # The engineering-object model can still be ready without any MRT.
    assert r.readiness_gates.engineering_object_model_ready is True


# ===========================================================================
# CONTROL C (Sec 27) -- GEOMETRY COMPLETE / FUNCTION UNKNOWN.
# ===========================================================================
def test_control_c_geometry_complete_function_unknown_are_decoupled():
    si = AsIsStructuredFacilityInput(
        facility=AsIsFacilityIdentityInput(facility_id="FAC-C", facility_name="Gamma"),
        buildings=(AsIsBuildingInput(building_id="B1"),),
        floors=(AsIsFloorInput(building_id="B1", floor_id="F1", elevation_m=0.0),),
        rooms=(
            # Fully known geometry, function deliberately absent.
            AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R1", length_m=6.0, width_m=5.0, height_m=3.0),
            AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R2", length_m=4.0, width_m=4.0, height_m=3.0),
        ),
    )
    r = ingest_structured_facility(si)
    # GEOMETRY may be COMPLETE ...
    assert _domain(r, "GEOMETRY").status == "COMPLETE"
    # ... while CLINICAL_SPACE_CLASSIFICATION is PARTIAL/NOT_MODELED (never coupled).
    assert _domain(r, "CLINICAL_SPACE_CLASSIFICATION").status in ("PARTIAL", "NOT_MODELED")
    # Every classification stays UNKNOWN; geometry object_type stays generic ROOM.
    assert all(c.status == "UNKNOWN" for c in r.space_classifications)
    assert all(r.spatial_registry.objects[c.spatial_object_id].object_type == "ROOM" for c in r.space_classifications)


# ===========================================================================
# CONTROL D (Sec 28) -- EQUIPMENT INVENTORY WITHOUT PLACEMENT.
# ===========================================================================
def test_control_d_equipment_identity_without_placement():
    si = AsIsStructuredFacilityInput(
        facility=AsIsFacilityIdentityInput(facility_id="FAC-D", facility_name="Delta"),
        buildings=(AsIsBuildingInput(building_id="B1"),),
        floors=(AsIsFloorInput(building_id="B1", floor_id="F1"),),
        rooms=(AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R1", room_function="PET_SCANNER"),),
        equipment=(
            AsIsEquipmentInput(equipment_instance_id="SCN-1", equipment_class="PET_SCANNER", catalog_model_id=PET_MODEL),
            AsIsEquipmentInput(equipment_instance_id="GEN-1", equipment_class="GENERATOR", catalog_model_id=GENERATOR_MODEL),
        ),
        # NO placements supplied.
    )
    r = ingest_structured_facility(si)
    # ENGINEERING_OBJECT_IDENTITY complete/partial ...
    assert _domain(r, "ENGINEERING_OBJECT_IDENTITY").status in ("COMPLETE", "PARTIAL")
    # ... while EQUIPMENT_PLACEMENT remains PARTIAL (nothing placed).
    assert _domain(r, "EQUIPMENT_PLACEMENT").status == "PARTIAL"
    # Unplaced equipment is NOT deleted; identity preserved in bindings.
    ids = {b.equipment_instance_id for b in r.equipment_bindings}
    assert ids == {"SCN-1", "GEN-1"}
    assert all(b.binding_status == "UNRESOLVED" and b.spatial_object_id is None for b in r.equipment_bindings)


def test_control_d_binding_move_preserves_identity_invariant():
    # A future drag/drop changes spatial_object_id WITHOUT changing instance id.
    r = ingest_structured_facility(_control_a_input())
    placed = next(b for b in r.equipment_bindings if b.equipment_instance_id == "SCN-PET-1")
    assert placed.binding_status == "BOUND"
    assert placed.spatial_object_id == "R-PET"
    unplaced = next(b for b in r.equipment_bindings if b.equipment_instance_id == "GEN-1")
    assert unplaced.binding_status == "UNRESOLVED"
    # Both retain their distinct, stable instance identity.
    assert placed.equipment_instance_id == "SCN-PET-1"
    assert unplaced.equipment_instance_id == "GEN-1"


# ===========================================================================
# CONTROL E (Sec 29) -- PARTIAL TOPOLOGY (no fabrication, no routing physics).
# ===========================================================================
def _control_e_input() -> AsIsStructuredFacilityInput:
    return AsIsStructuredFacilityInput(
        facility=AsIsFacilityIdentityInput(facility_id="FAC-E", facility_name="Epsilon"),
        buildings=(AsIsBuildingInput(building_id="B1"),),
        floors=(
            AsIsFloorInput(building_id="B1", floor_id="F1", elevation_m=0.0),
            AsIsFloorInput(building_id="B1", floor_id="F2", elevation_m=4.0),
        ),
        rooms=(
            AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R1", room_function="PET_SCANNER",
                          length_m=6.0, width_m=5.0, height_m=3.0),
            AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R2", room_function="INJECTION_ROOM",
                          length_m=4.0, width_m=3.0, height_m=3.0),
            AsIsRoomInput(building_id="B1", floor_id="F2", room_id="R3", room_function="UPTAKE_ROOM",
                          length_m=4.0, width_m=4.0, height_m=3.0),
        ),
        # Only R1<->R2 supplied; R3 has no connection. No vertical link fabricated.
        routes=(AsIsRouteOrConnectivityInput(from_object_id="R1", to_object_id="R2", length_m=7.0),),
    )


def test_control_e_partial_topology_report():
    r = ingest_structured_facility(_control_e_input())
    conn = r.connectivity
    assert conn is not None
    # GEOMETRY_STATUS = COMPLETE (all rooms fully dimensioned).
    assert _domain(r, "GEOMETRY").status == "COMPLETE"
    # CONNECTIVITY_TOPOLOGY_STATUS = PARTIAL.
    assert conn.route_readiness == "TOPOLOGY_PARTIAL"
    assert _domain(r, "CONNECTIVITY_TOPOLOGY").status == "PARTIAL"
    # SUPPLIED_CONNECTION_COUNT = 1; the supplied connection is preserved.
    assert conn.supplied_connection_count == 1
    assert any(l.from_object_id == "R1" and l.to_object_id == "R2" for l in conn.links)
    # MISSING_CONNECTIONS_INFERRED = NO / no fabricated portals / vertical links.
    assert conn.connectable_space_count == 2  # only R1, R2; R3 not inferred-connected
    # ROUTE_DISTANCE_FABRICATED = NO ; TRANSPORT_TIME_CALCULATED = NO.
    assert conn.route_distance_fabricated is False
    assert conn.transport_time_calculated is False
    # NORMALIZATION_SUCCEEDED = YES.
    assert isinstance(r, ExistingFacilityAsIsTwinResult)
    assert r.readiness_gates.normalization_succeeded is True
    # BASELINE_SIMULATION_READY = NO (topology insufficient + out of scope).
    assert r.readiness_gates.baseline_simulation_ready is False


def test_control_e_geometry_complete_does_not_imply_connectivity():
    r = ingest_structured_facility(_control_e_input())
    # Known coordinates != known connectivity: geometry COMPLETE, topology PARTIAL.
    assert _domain(r, "GEOMETRY").status == "COMPLETE"
    assert r.connectivity.route_readiness == "TOPOLOGY_PARTIAL"


def test_no_topology_supplied_is_not_modeled():
    si = AsIsStructuredFacilityInput(
        facility=AsIsFacilityIdentityInput(facility_id="F", facility_name="F"),
        buildings=(AsIsBuildingInput(building_id="B1"),),
        floors=(AsIsFloorInput(building_id="B1", floor_id="F1"),),
        rooms=(AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R1", room_function="PET_SCANNER",
                             length_m=6.0, width_m=5.0, height_m=3.0),),
    )
    r = ingest_structured_facility(si)
    assert r.connectivity.route_readiness == "TOPOLOGY_NOT_MODELED"
    assert r.connectivity.supplied_connection_count == 0


# ===========================================================================
# CONTRADICTION CONTROL (Sec 17) -- conflicting room-function evidence.
# ===========================================================================
def _contradiction_input() -> AsIsStructuredFacilityInput:
    return AsIsStructuredFacilityInput(
        facility=AsIsFacilityIdentityInput(facility_id="FAC-X", facility_name="Xray"),
        buildings=(AsIsBuildingInput(building_id="B1"),),
        floors=(AsIsFloorInput(building_id="B1", floor_id="F1"),),
        rooms=(AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R-101", room_function="STORAGE",
                             length_m=3.0, width_m=3.0, height_m=3.0),),
        # A department inventory disagrees: R-101 is a PET scanner room.
        conflicting_evidence=(AsIsConflictingEvidenceInput(
            object_id="R-101", field_name="room_function", candidate_value="PET_SCANNER_ROOM", source="FACILITY_SUPPLIED"),),
    )


def test_contradiction_control_both_facts_survive_no_autoresolution():
    r = ingest_structured_facility(_contradiction_input())
    # CONFLICT_CREATED = YES
    assert len(r.evidence_conflicts) == 1
    c = r.evidence_conflicts[0]
    # CANDIDATE_VALUES_PRESERVED = YES (both, neither discarded)
    assert set(c.candidate_values) == {"STORAGE", "PET_SCANNER_ROOM"}
    # AUTO_RESOLUTION_OCCURRED = NO
    assert c.resolution_status == "UNRESOLVED"
    assert c.selected_value is None
    assert c.resolution_source is None
    # READINESS_IMPACT = non-zero (reduces readiness)
    assert c.impact_on_readiness == "REDUCES_READINESS"


def test_contradiction_control_room_identity_survives_and_reduces_readiness():
    r = ingest_structured_facility(_contradiction_input())
    # Room identity survives.
    assert "R-101" in r.spatial_registry.objects
    # The classification binding is marked CONFLICTED (not silently overwritten).
    binding = next(c for c in r.space_classifications if c.spatial_object_id == "R-101")
    assert binding.status == "CONFLICTED"
    # Simulation readiness is reduced: the engineering-object model is NOT ready
    # while the conflict is unresolved, though structural reconstruction remains.
    assert r.readiness_gates.structural_reconstruction_ready is True
    assert r.readiness_gates.engineering_object_model_ready is False
    assert _domain(r, "EVIDENCE_CONFLICTS").status == "CONFLICTED"


def test_agreeing_evidence_is_not_a_conflict():
    si = AsIsStructuredFacilityInput(
        facility=AsIsFacilityIdentityInput(facility_id="F", facility_name="F"),
        buildings=(AsIsBuildingInput(building_id="B1"),),
        floors=(AsIsFloorInput(building_id="B1", floor_id="F1"),),
        rooms=(AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R1",
                             clinical_space_classification="PET_SCANNER_ROOM",
                             length_m=6.0, width_m=5.0, height_m=3.0),),
        conflicting_evidence=(AsIsConflictingEvidenceInput(
            object_id="R1", field_name="room_function", candidate_value="PET_SCANNER_ROOM", source="FACILITY_SUPPLIED"),),
    )
    r = ingest_structured_facility(si)
    assert len(r.evidence_conflicts) == 0


# ===========================================================================
# CLINICAL-SPACE CLASSIFICATION AUTHORITY (Sec 6-7).
# ===========================================================================
def test_classification_is_separate_axis_from_geometry():
    # Explicit classification supplied on its own axis.
    si = AsIsStructuredFacilityInput(
        facility=AsIsFacilityIdentityInput(facility_id="F", facility_name="F"),
        buildings=(AsIsBuildingInput(building_id="B1"),),
        floors=(AsIsFloorInput(building_id="B1", floor_id="F1"),),
        rooms=(AsIsRoomInput(building_id="B1", floor_id="F1", room_id="R1",
                             clinical_space_classification="COMBINED_INJECTION_UPTAKE",
                             length_m=5.0, width_m=4.0, height_m=3.0),),
    )
    r = ingest_structured_facility(si)
    binding = next(c for c in r.space_classifications if c.spatial_object_id == "R1")
    assert binding.classification == "COMBINED_INJECTION_UPTAKE"
    assert binding.status == "KNOWN"
    # Classification does NOT depend on geometry object_type (room stays generic ROOM).
    assert r.spatial_registry.objects["R1"].object_type == "ROOM"


def test_classification_not_inferred_from_name():
    si = AsIsStructuredFacilityInput(
        facility=AsIsFacilityIdentityInput(facility_id="F", facility_name="F"),
        buildings=(AsIsBuildingInput(building_id="B1"),),
        floors=(AsIsFloorInput(building_id="B1", floor_id="F1"),),
        rooms=(AsIsRoomInput(building_id="B1", floor_id="F1", room_id="Cyclotron Vault",
                             length_m=6.0, width_m=6.0, height_m=4.0),),
    )
    r = ingest_structured_facility(si)
    binding = r.space_classifications[0]
    assert binding.classification == "UNKNOWN"  # not guessed from "Cyclotron" in the id


# ===========================================================================
# READINESS GATES (Sec 20) -- distinct + monotonic + pre-simulation.
# ===========================================================================
def test_readiness_gates_are_distinct_and_monotonic():
    r = ingest_structured_facility(_control_a_input())
    g = r.readiness_gates
    assert g is not None
    # Distinct concepts; a later gate implies all earlier ones.
    gates = [
        g.normalization_succeeded,
        g.structural_reconstruction_ready,
        g.engineering_object_model_ready,
        g.operational_state_reconstruction_ready,
        g.baseline_simulation_ready,
    ]
    # Monotonic: once False, stays False (no later gate True after a False).
    seen_false = False
    for gate in gates:
        if not gate:
            seen_false = True
        elif seen_false:
            raise AssertionError("readiness gates are not monotonic")
    # Pre-simulation: the last two gates are always False in Phase 1C.
    assert g.operational_state_reconstruction_ready is False
    assert g.baseline_simulation_ready is False


def test_readiness_level_matches_highest_gate():
    r = ingest_structured_facility(_control_a_input())
    assert r.readiness_gates.overall_readiness_level == "ENGINEERING_MODEL_PARTIAL"


# ===========================================================================
# OUT-OF-SCOPE DISCLOSURE FLAGS (Sec 21-24).
# ===========================================================================
def test_operational_state_and_simulation_out_of_scope():
    r = ingest_structured_facility(_control_a_input())
    assert r.operational_state_reconstruction_implemented is False
    assert r.patient_state_ingestion_implemented is False
    assert r.appointment_ingestion_implemented is False
    assert r.scanner_calendar_ingestion_implemented is False
    assert r.staff_roster_ingestion_implemented is False
    assert r.production_schedule_ingestion_implemented is False
    assert r.live_equipment_state_ingestion_implemented is False
    assert r.asis_baseline_simulation_implemented is False
    assert r.simulation_run_during_phase_1c is False


def test_lockdown_what_if_out_of_scope_seam_preserved():
    r = ingest_structured_facility(_control_a_input())
    assert r.lockdown_created is False
    assert r.what_if_created is False
    assert r.lockdown_authority_duplicated is False
    assert r.existing_lockdown_lineage_seam_preserved is True


# ===========================================================================
# DOMAIN COMPLETENESS (Sec 18-19) -- never one collapsed count.
# ===========================================================================
def test_domain_completeness_covers_all_domains():
    r = ingest_structured_facility(_control_a_input())
    domains = {d.domain for d in r.domain_completeness}
    expected = {
        "FACILITY_IDENTITY", "SPATIAL_HIERARCHY", "GEOMETRY", "CLINICAL_SPACE_CLASSIFICATION",
        "ENGINEERING_OBJECT_IDENTITY", "EQUIPMENT_PLACEMENT", "CONNECTIVITY_TOPOLOGY",
        "OPERATIONAL_RESOURCE_IDENTITY", "PROVENANCE", "CALIBRATION", "EVIDENCE_CONFLICTS",
        "OPERATIONAL_STATE", "SIMULATION_READINESS",
    }
    assert domains == expected


def test_no_silent_benchmark_operational_state_domain():
    r = ingest_structured_facility(_control_a_input())
    # OPERATIONAL_STATE stays NOT_MODELED and blocking (never benchmark-filled).
    op_state = _domain(r, "OPERATIONAL_STATE")
    assert op_state.status == "NOT_MODELED"
    assert op_state.readiness_impact == "BLOCKING"
