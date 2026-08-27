"""Focused tests for canonical_entity_binding_authority.py -- Phase 1B
canonical entity identity, spatial binding, and end-to-end traceability.

Covers every item in the Phase 1B testing requirement: patient<->room,
patient<->scanner, scanner<->room, patient<->batch, batch<->cyclotron,
generator-source binding (kept distinct from cyclotron semantics),
batch<->payload, payload->patient identity preservation, clinical-resource-
index resolution, transport-interface<->room, legacy-field preservation,
serialization/reload, What-If binding non-mutation of the parent Lockdown,
no duplicate physical assets, and frozen-benchmark numerical invariance.
"""

from __future__ import annotations

import dataclasses

import pytest

import canonical_entity_binding_authority as ceba
import canonical_spatial_authority as csa
import lockdown_what_if_lineage_authority as lla
from clinical_resource_identity import ClinicalResource, resource_id_for_index
from decision_pipeline import run_native_decision_pipeline
from test_cyclotron_fleet_integration import _fleet_disjoint, _request


# ---------------------------------------------------------------------------
# 1. patient <-> room
# ---------------------------------------------------------------------------


def test_patient_room_resolves_both_directions():
    registry = ceba.EntityBindingRegistry()
    ceba.bind_patient_room(registry, patient_id="P1", room_id="IR-001")
    assert ceba.room_for_patient(registry, "P1") == "IR-001"
    assert ceba.patients_in_room(registry, "IR-001") == ("P1",)


# ---------------------------------------------------------------------------
# 2. patient <-> scanner
# ---------------------------------------------------------------------------


def test_patient_scanner_resolves_both_directions():
    registry = ceba.EntityBindingRegistry()
    ceba.bind_patient_scanner(registry, patient_id="P1", scanner_id="SCN-001")
    assert ceba.scanner_for_patient(registry, "P1") == "SCN-001"
    assert ceba.patients_for_scanner(registry, "SCN-001") == ("P1",)


# ---------------------------------------------------------------------------
# 3. scanner <-> room
# ---------------------------------------------------------------------------


def test_scanner_room_resolves_both_directions():
    registry = ceba.EntityBindingRegistry()
    ceba.bind_equipment_room(registry, equipment_id="SCN-001", room_id="BLDG-A-F1-R01", equipment_kind="SCANNER")
    assert ceba.room_for_scanner(registry, "SCN-001") == "BLDG-A-F1-R01"
    assert ceba.scanners_in_room(registry, "BLDG-A-F1-R01") == ("SCN-001",)


def test_scanner_room_also_resolves_via_clinical_resource_binding():
    registry = ceba.EntityBindingRegistry()
    resource = ClinicalResource(resource_id="SCN-001", resource_type="SCANNER", room_id="BLDG-A-F1-R02")
    ceba.bind_clinical_resource(registry, resource)
    assert ceba.room_for_scanner(registry, "SCN-001") == "BLDG-A-F1-R02"
    assert "SCN-001" in ceba.scanners_in_room(registry, "BLDG-A-F1-R02")


# ---------------------------------------------------------------------------
# 4. patient <-> batch (real production trace)
# ---------------------------------------------------------------------------


def _real_production_trace():
    result = run_native_decision_pipeline(_request(_fleet_disjoint()))
    return result.conventional.operational_result.production_clinical_result.patient_traces[0]


def test_patient_batch_resolves_both_directions_from_real_trace():
    trace = _real_production_trace()
    registry = ceba.EntityBindingRegistry()
    ceba.bind_production_clinical_trace(registry, trace)

    batch_id = str(trace.batch_id)
    assert ceba.batch_for_patient(registry, trace.patient_id) == batch_id
    assert trace.patient_id in ceba.patients_for_batch(registry, batch_id)


# ---------------------------------------------------------------------------
# 5. batch <-> cyclotron
# ---------------------------------------------------------------------------


def test_batch_cyclotron_resolves_both_directions_from_real_trace():
    trace = _real_production_trace()
    registry = ceba.EntityBindingRegistry()
    ceba.bind_production_clinical_trace(registry, trace)

    batch_id = str(trace.batch_id)
    assert ceba.cyclotron_for_batch(registry, batch_id) == trace.assigned_cyclotron_id
    assert batch_id in ceba.batches_for_cyclotron(registry, trace.assigned_cyclotron_id)


# ---------------------------------------------------------------------------
# 6. generator-source binding stays distinct from cyclotron semantics
# ---------------------------------------------------------------------------


def test_generator_source_binding_never_populates_cyclotron_index():
    registry = ceba.EntityBindingRegistry()
    ceba.bind_batch_or_supply_generator(registry, batch_or_supply_id="TC99M-BATCH-1", generator_id="GEN-001")

    assert ceba.generator_for_batch_or_supply(registry, "TC99M-BATCH-1") == "GEN-001"
    assert "TC99M-BATCH-1" in ceba.batches_or_supplies_for_generator(registry, "GEN-001")
    # The cyclotron index must remain entirely untouched by generator binding.
    assert ceba.cyclotron_for_batch(registry, "TC99M-BATCH-1") is None
    assert ceba.batches_for_cyclotron(registry, "GEN-001") == ()
    source = registry.batch_source["TC99M-BATCH-1"]
    assert source.source_type == "GENERATOR"
    assert source.cyclotron_id is None


# ---------------------------------------------------------------------------
# 7. batch <-> payload
# ---------------------------------------------------------------------------


def test_batch_payload_resolves_both_directions_from_real_trace():
    trace = _real_production_trace()
    registry = ceba.EntityBindingRegistry()
    ceba.bind_production_clinical_trace(registry, trace)

    batch_id = str(trace.batch_id)
    assert trace.payload_id in ceba.payloads_for_batch(registry, batch_id)
    assert ceba.batch_for_payload(registry, trace.payload_id) == batch_id


# ---------------------------------------------------------------------------
# 8. payload -> patient preserves patient identity
# ---------------------------------------------------------------------------


def test_payload_patient_preserves_identity_from_real_trace():
    trace = _real_production_trace()
    registry = ceba.EntityBindingRegistry()
    ceba.bind_production_clinical_trace(registry, trace)

    assert ceba.patient_for_payload(registry, trace.payload_id) == trace.patient_id
    assert trace.patient_id in ceba.patients_for_payload(registry, trace.payload_id)
    assert ceba.payloads_for_patient(registry, trace.patient_id) == (trace.payload_id,)


# ---------------------------------------------------------------------------
# 9. clinical resource index -> resource ID -> canonical room
# ---------------------------------------------------------------------------


def test_clinical_resource_index_resolves_id_and_room():
    registry = ceba.EntityBindingRegistry()
    injection_resource = ClinicalResource(resource_id=resource_id_for_index("INJECTION_ROOM", 0), resource_type="INJECTION_ROOM", room_id="BLDG-A-F1-R03")
    ceba.bind_clinical_resource(registry, injection_resource)

    resolution = ceba.resolve_clinical_event_location(registry, injection_resource_index=0)
    assert resolution.injection_resource_id == "INJ-001"
    assert resolution.injection_room_id == "BLDG-A-F1-R03"


# ---------------------------------------------------------------------------
# 10. transport interface <-> room
# ---------------------------------------------------------------------------


def test_transport_interface_room_resolves_both_directions():
    registry = ceba.EntityBindingRegistry()
    ceba.bind_transport_interface_room(registry, interface_id="MRT-ENDPOINT-01", room_id="BLDG-A-F1-R01", interface_kind="MRT")
    assert ceba.room_for_transport_interface(registry, "MRT-ENDPOINT-01") == "BLDG-A-F1-R01"
    assert ceba.transport_interfaces_for_room(registry, "BLDG-A-F1-R01") == ("MRT-ENDPOINT-01",)


def test_manual_delivery_point_resolution_never_fabricates_a_room():
    known_rooms = {"IR-001", "IR-002"}
    assert ceba.resolve_manual_delivery_point(known_rooms, "IR-001") == "IR-001"
    assert ceba.resolve_manual_delivery_point(known_rooms, "LOCATION_NOT_CALIBRATED") == ceba.UNRESOLVED_LEGACY_LOCATION_REFERENCE


# ---------------------------------------------------------------------------
# 11. legacy fields remain unchanged
# ---------------------------------------------------------------------------


def test_binding_never_mutates_the_source_trace_or_resource():
    trace = _real_production_trace()
    original = dataclasses.replace(trace)
    registry = ceba.EntityBindingRegistry()
    ceba.bind_production_clinical_trace(registry, trace)
    assert trace == original  # every legacy field (batch_id, assigned_cyclotron_id, payload_id, ...) untouched

    resource = ClinicalResource(resource_id="SCN-001", resource_type="SCANNER", room_id="R-01")
    original_resource = dataclasses.replace(resource)
    ceba.bind_clinical_resource(registry, resource)
    assert resource == original_resource


# ---------------------------------------------------------------------------
# 12. serialization / reload preserves bindings
# ---------------------------------------------------------------------------


def test_entity_bindings_survive_serialize_and_deserialize():
    registry = ceba.EntityBindingRegistry()
    ceba.bind_patient_room(registry, patient_id="P1", room_id="IR-001")
    ceba.bind_patient_batch(registry, patient_id="P1", batch_id="1")
    ceba.bind_batch_cyclotron(registry, batch_id="1", cyclotron_id="CY-A")
    ceba.bind_payload_patient(registry, payload_id="PL-1", patient_id="P1")

    payload = ceba.serialize_entity_bindings(registry)
    reloaded = ceba.deserialize_entity_bindings(payload)

    assert ceba.room_for_patient(reloaded, "P1") == "IR-001"
    assert ceba.batch_for_patient(reloaded, "P1") == "1"
    assert ceba.cyclotron_for_batch(reloaded, "1") == "CY-A"
    assert ceba.patient_for_payload(reloaded, "PL-1") == "P1"


def test_lockdown_serialization_round_trips_entity_bindings():
    lineage_registry = lla.LockdownLineageRegistry()
    spatial_locked = csa.LockedSpatialState(registry=csa.build_facility_hierarchy(facility_id="FAC-001"))
    entity_registry = ceba.EntityBindingRegistry()
    ceba.bind_patient_room(entity_registry, patient_id="P1", room_id="IR-001")

    l0 = lla.create_first_lockdown(lineage_registry, locked=spatial_locked, entity_bindings=ceba.serialize_entity_bindings(entity_registry))

    payload = lla.lineage_registry_to_json(lineage_registry)
    reloaded_lineage_registry = lla.lineage_registry_from_json(payload)
    reloaded_l0 = reloaded_lineage_registry.lockdown(l0.lockdown_id)
    reloaded_entity_registry = ceba.deserialize_entity_bindings(reloaded_l0.entity_bindings)
    assert ceba.room_for_patient(reloaded_entity_registry, "P1") == "IR-001"


# ---------------------------------------------------------------------------
# 13. What-If binding changes do not mutate the parent Lockdown
# ---------------------------------------------------------------------------


def test_what_if_entity_binding_edit_never_mutates_parent_lockdown():
    lineage_registry = lla.LockdownLineageRegistry()
    spatial_locked = csa.LockedSpatialState(registry=csa.build_facility_hierarchy(facility_id="FAC-001"))
    parent_bindings = ceba.EntityBindingRegistry()
    ceba.bind_patient_room(parent_bindings, patient_id="P1", room_id="IR-001")
    l0 = lla.create_first_lockdown(lineage_registry, locked=spatial_locked, entity_bindings=parent_bindings)

    w1 = lla.branch_what_if(lineage_registry, parent_lockdown_id=l0.lockdown_id)
    branched_bindings = ceba.branch_entity_bindings(l0.entity_bindings)
    ceba.bind_patient_room(branched_bindings, patient_id="P1", room_id="IR-002")  # what-if: move patient
    lla.update_what_if_results(lineage_registry, w1.what_if_id, entity_bindings=branched_bindings)

    assert ceba.room_for_patient(l0.entity_bindings, "P1") == "IR-001"  # parent untouched
    assert ceba.room_for_patient(lineage_registry.what_if(w1.what_if_id).entity_bindings, "P1") == "IR-002"


# ---------------------------------------------------------------------------
# 14. no duplicate physical assets are created
# ---------------------------------------------------------------------------


def test_binding_equipment_to_room_creates_no_new_spatial_object():
    reg = csa.build_facility_hierarchy(facility_id="FAC-001")
    csa.add_building(reg, facility_id="FAC-001", building_id="BLDG-A")
    csa.add_floor(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1")
    csa.add_room(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1", room_id="BLDG-A-F1-R01")
    object_count_before = len(reg.objects)

    registry = ceba.EntityBindingRegistry()
    resolved = ceba.bind_equipment_room_from_spatial_registry(registry, reg, equipment_id="CY-001", equipment_kind="CYCLOTRON")

    assert resolved is None  # no spatial object bridges to CY-001 yet -- honestly unresolved, nothing fabricated
    assert len(reg.objects) == object_count_before  # zero new objects created
    ceba.bind_equipment_room(registry, equipment_id="CY-001", room_id="BLDG-A-F1-R01", equipment_kind="CYCLOTRON")
    assert len(reg.objects) == object_count_before  # manual binding still creates no spatial object
    assert ceba.room_for_cyclotron(registry, "CY-001") == "BLDG-A-F1-R01"


# ---------------------------------------------------------------------------
# 15. frozen benchmark numerical invariance
# ---------------------------------------------------------------------------


def test_frozen_eight_floor_benchmark_patient_count_unaffected_by_phase_1b():
    from whole_oncology_four_architecture_optimization import build_eight_floor_bed_matched_baseline

    baseline = build_eight_floor_bed_matched_baseline()
    assert len(baseline.patients) == 80  # 80 occupied beds, per Section 35 -- Phase 1B never touches this module


# ---------------------------------------------------------------------------
# Worked trace example (section 38) -- honest UNRESOLVED hops disclosed
# ---------------------------------------------------------------------------


def test_worked_patient_traceability_chain_reports_honest_unresolved_hops():
    trace = _real_production_trace()
    registry = ceba.EntityBindingRegistry()
    ceba.bind_production_clinical_trace(registry, trace)
    ceba.bind_equipment_room(registry, equipment_id=trace.assigned_cyclotron_id, room_id="BLDG-A-F1-R99", equipment_kind="CYCLOTRON")

    chain = ceba.resolve_patient_radionuclide_chain(registry, trace.patient_id)
    assert chain.radionuclide_status == "RESOLVED"
    assert chain.batch_id == str(trace.batch_id)
    assert chain.source_type == "CYCLOTRON"
    assert chain.source_equipment_id == trace.assigned_cyclotron_id
    assert chain.source_room_id == "BLDG-A-F1-R99"
    assert chain.payload_id == trace.payload_id
    # No TransportMission correlation exists in the repository for this trace today.
    assert chain.mission_id is None
    assert chain.mission_status != "RESOLVED"
