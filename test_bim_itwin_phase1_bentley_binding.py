"""BIM/iTwin Phase 1 focused tests: ExternalReference/Provenance extension,
Bentley element normalization, canonical binding precedence, transform
composition, serialization, and Phase 1-3 protection.
"""

from __future__ import annotations

import dataclasses

import pytest

import canonical_spatial_authority as csa


def _locked_and_what_if(facility_id: str = "FAC-BIM"):
    reg = csa.build_facility_hierarchy(facility_id=facility_id)
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    return locked, what_if


def _building_floor_room_elements(*, room_number: str = "ROOM-714", x: float = 1000.0, y: float = 2000.0, scale: float = 0.001):
    return [
        csa.BentleyElementRecord(itwin_id="ITWIN-1", imodel_id="IMODEL-1", element_id="EL-BLDG-A", element_class="BUILDING", building_id="BLDG-A"),
        csa.BentleyElementRecord(itwin_id="ITWIN-1", imodel_id="IMODEL-1", element_id="EL-F1", element_class="FLOOR", building_id="BLDG-A", floor_id="F1"),
        csa.BentleyElementRecord(
            itwin_id="ITWIN-1", imodel_id="IMODEL-1", element_id="EL-R01", element_class="ROOM", building_id="BLDG-A",
            floor_id="F1", room_number=room_number, x=x, y=y, z=0.0, source_scale_m_per_unit=scale,
        ),
    ]


# ---------------------------------------------------------------------------
# 1-2. Additive/backward-compatible ExternalReference
# ---------------------------------------------------------------------------


def test_1_new_external_reference_fields_default_to_none():
    ref = csa.ExternalReference()
    assert ref.external_project_id is None
    assert ref.external_model_id is None
    assert ref.change_reference is None


def test_2_old_external_reference_construction_remains_compatible():
    ref = csa.ExternalReference(ifc_guid="IFC-XYZ", usd_prim_path="/Fac/BldgA/F1/R01")
    assert ref.ifc_guid == "IFC-XYZ"
    assert ref.usd_prim_path == "/Fac/BldgA/F1/R01"
    assert ref.external_project_id is None


# ---------------------------------------------------------------------------
# 3. IMPORTED_ITWIN provenance
# ---------------------------------------------------------------------------


def test_3_imported_itwin_provenance_exists():
    _, what_if = _locked_and_what_if()
    result = csa.normalize_itwin_import(what_if.registry, facility_id="FAC-BIM", elements=_building_floor_room_elements())
    assert result.normalized.provenance == "IMPORTED_ITWIN"
    assert result.normalized.import_mode == "ITWIN"
    # old provenances remain untouched
    assert "IMPORTED_IFC" in csa.Provenance.__args__
    assert "IMPORTED_CAD" in csa.Provenance.__args__
    assert "API" in csa.Provenance.__args__


# ---------------------------------------------------------------------------
# 4. iTwin/iModel/element/change ID normalization
# ---------------------------------------------------------------------------


def test_4_itwin_imodel_element_change_ids_normalize_correctly():
    _, what_if = _locked_and_what_if()
    elements = _building_floor_room_elements()
    elements[-1] = dataclasses.replace(elements[-1], change_reference="CS-001")
    csa.normalize_itwin_import(what_if.registry, facility_id="FAC-BIM", elements=elements)
    room = what_if.registry.objects["ROOM-714"]
    assert room.external_reference.external_project_id == "ITWIN-1"
    assert room.external_reference.external_model_id == "IMODEL-1"
    assert room.external_reference.itwin_element_id == "EL-R01"
    assert room.external_reference.change_reference == "CS-001"


# ---------------------------------------------------------------------------
# 5-6. Same element -> same canonical object; idempotent re-import
# ---------------------------------------------------------------------------


def test_5_same_element_resolves_to_same_canonical_object():
    _, what_if = _locked_and_what_if()
    csa.normalize_itwin_import(what_if.registry, facility_id="FAC-BIM", elements=_building_floor_room_elements())
    found = csa.NativeJsonSpatialAdapter().resolve_selection(what_if.registry, "EL-R01", "itwin_element_id")
    assert found is not None
    assert found.mrtway_object_id == "ROOM-714"


def test_6_repeated_import_is_idempotent():
    _, what_if = _locked_and_what_if()
    elements = _building_floor_room_elements()
    result1 = csa.normalize_itwin_import(what_if.registry, facility_id="FAC-BIM", elements=elements)
    count_after_first = len(what_if.registry.objects)
    result2 = csa.normalize_itwin_import(what_if.registry, facility_id="FAC-BIM", elements=elements)
    assert len(what_if.registry.objects) == count_after_first  # no duplicate objects created
    statuses1 = {b.element_id: b.status for b in result1.bindings}
    statuses2 = {b.element_id: b.status for b in result2.bindings}
    assert statuses1["EL-R01"] == "CREATED"
    assert statuses2["EL-R01"] == "REUSED_EXISTING"


# ---------------------------------------------------------------------------
# 7-9. Conflict rejection, deterministic precedence, no fuzzy matching
# ---------------------------------------------------------------------------


def test_7_conflicting_external_binding_is_rejected():
    _, what_if = _locked_and_what_if()
    csa.normalize_itwin_import(what_if.registry, facility_id="FAC-BIM", elements=_building_floor_room_elements())
    conflicting = csa.BentleyElementRecord(
        itwin_id="ITWIN-1", imodel_id="IMODEL-1", element_id="EL-OTHER", element_class="ROOM",
        building_id="BLDG-A", floor_id="F1", room_number="ROOM-714", x=5.0, y=5.0, z=0.0,
    )
    result = csa.normalize_itwin_import(what_if.registry, facility_id="FAC-BIM", elements=[conflicting])
    assert result.bindings[0].status == "CONFLICT"
    # existing binding preserved unchanged
    room = what_if.registry.objects["ROOM-714"]
    assert room.external_reference.itwin_element_id == "EL-R01"


def test_8_room_binding_precedence_is_deterministic():
    _, what_if = _locked_and_what_if()
    result = csa.normalize_itwin_import(what_if.registry, facility_id="FAC-BIM", elements=_building_floor_room_elements())
    room_binding = next(b for b in result.bindings if b.element_id == "EL-R01")
    assert room_binding.status == "CREATED"
    assert room_binding.mrtway_object_id == "ROOM-714"


def test_9_fuzzy_matching_is_not_introduced():
    _, what_if = _locked_and_what_if()
    csa.normalize_itwin_import(what_if.registry, facility_id="FAC-BIM", elements=_building_floor_room_elements())
    # A near-miss room number must NOT resolve to the existing room -- a genuinely new object is created instead.
    near_miss = csa.BentleyElementRecord(
        itwin_id="ITWIN-1", imodel_id="IMODEL-1", element_id="EL-NEARMISS", element_class="ROOM",
        building_id="BLDG-A", floor_id="F1", room_number="ROOM-71", x=1.0, y=2.0, z=0.0,
    )
    result = csa.normalize_itwin_import(what_if.registry, facility_id="FAC-BIM", elements=[near_miss])
    assert result.bindings[0].status == "CREATED"
    assert result.bindings[0].mrtway_object_id == "ROOM-71"
    assert "ROOM-71" != "ROOM-714"


# ---------------------------------------------------------------------------
# 10-11. Equipment binding reuses existing engineering identity
# ---------------------------------------------------------------------------


def test_10_scanner_binding_reuses_existing_engineering_identity():
    import canonical_entity_binding_authority as ceba

    _, what_if = _locked_and_what_if()
    element = csa.BentleyElementRecord(
        itwin_id="ITWIN-1", imodel_id="IMODEL-1", element_id="EL-SCN", element_class="PET_SCANNER",
        building_id="BLDG-A", floor_id="F1", engineering_object_id="SCN-002",
    )
    csa.normalize_itwin_import(what_if.registry, facility_id="FAC-BIM", elements=_building_floor_room_elements() + [element])
    assert "SCN-002" in what_if.registry.objects
    assert what_if.registry.objects["SCN-002"].engineering_object_id == "SCN-002"

    registry = ceba.EntityBindingRegistry()
    ceba.bind_equipment_room(registry, equipment_id="SCN-002", room_id="ROOM-714", equipment_kind="SCANNER")
    assert ceba.room_for_scanner(registry, "SCN-002") == "ROOM-714"


def test_11_cyclotron_binding_reuses_existing_engineering_identity():
    import canonical_entity_binding_authority as ceba

    _, what_if = _locked_and_what_if()
    element = csa.BentleyElementRecord(
        itwin_id="ITWIN-1", imodel_id="IMODEL-1", element_id="EL-CY", element_class="CYCLOTRON",
        building_id="BLDG-A", floor_id="F1", engineering_object_id="CY-001",
    )
    csa.normalize_itwin_import(what_if.registry, facility_id="FAC-BIM", elements=_building_floor_room_elements() + [element])
    assert what_if.registry.objects["CY-001"].engineering_object_id == "CY-001"

    registry = ceba.EntityBindingRegistry()
    ceba.bind_equipment_room(registry, equipment_id="CY-001", room_id="ROOM-714", equipment_kind="CYCLOTRON")
    assert ceba.room_for_cyclotron(registry, "CY-001") == "ROOM-714"


# ---------------------------------------------------------------------------
# 12-13. Unit normalization + transform composition
# ---------------------------------------------------------------------------


def test_12_source_units_normalize_to_meters():
    _, what_if = _locked_and_what_if()
    csa.normalize_itwin_import(what_if.registry, facility_id="FAC-BIM", elements=_building_floor_room_elements(x=10_000.0, y=0.0, scale=0.001))
    room = what_if.registry.objects["ROOM-714"]
    assert room.transform.position_x == pytest.approx(10.0)


def test_13_transform_composition_is_correct():
    parent = csa.Transform(position_x=100.0, position_y=50.0, position_z=0.0, rotation_z=90.0)
    result = csa.compose_project_global_transform(parent_transform=parent, local_x=10.0, local_y=0.0, local_z=0.0, scale_m_per_unit=1.0)
    # 90deg rotation of (10, 0) -> (0, 10); plus parent translation (100, 50) -> (100, 60)
    assert result.position_x == pytest.approx(100.0, abs=1e-6)
    assert result.position_y == pytest.approx(60.0, abs=1e-6)
    assert result.rotation_z == pytest.approx(90.0)


# ---------------------------------------------------------------------------
# 14. Parent hierarchy preserved
# ---------------------------------------------------------------------------


def test_14_parent_hierarchy_is_preserved():
    _, what_if = _locked_and_what_if()
    csa.normalize_itwin_import(what_if.registry, facility_id="FAC-BIM", elements=_building_floor_room_elements())
    building = what_if.registry.objects["BLDG-A"]
    floor = what_if.registry.objects["BLDG-A::F1"]
    room = what_if.registry.objects["ROOM-714"]
    assert building.parent_object_id == "FAC-BIM"
    assert floor.parent_object_id == "BLDG-A"
    assert room.parent_object_id == "BLDG-A::F1"


# ---------------------------------------------------------------------------
# 15-16. Serialization round-trip
# ---------------------------------------------------------------------------


def test_15_new_fields_serialize_and_reload():
    _, what_if = _locked_and_what_if()
    csa.normalize_itwin_import(what_if.registry, facility_id="FAC-BIM", elements=_building_floor_room_elements())
    payload = csa.registry_to_json(what_if.registry)
    reloaded = csa.registry_from_json(payload)
    room = reloaded.objects["ROOM-714"]
    assert room.mrtway_object_id == "ROOM-714"
    assert room.object_type == "ROOM"
    assert room.parent_object_id == "BLDG-A::F1"
    assert room.provenance == "IMPORTED_ITWIN"
    assert room.external_reference.external_project_id == "ITWIN-1"
    assert room.external_reference.external_model_id == "IMODEL-1"
    assert room.external_reference.itwin_element_id == "EL-R01"


def test_16_change_reference_survives_serialization():
    _, what_if = _locked_and_what_if()
    elements = _building_floor_room_elements()
    elements[-1] = dataclasses.replace(elements[-1], change_reference="CS-777")
    csa.normalize_itwin_import(what_if.registry, facility_id="FAC-BIM", elements=elements)
    payload = csa.registry_to_json(what_if.registry)
    reloaded = csa.registry_from_json(payload)
    assert reloaded.objects["ROOM-714"].external_reference.change_reference == "CS-777"


# ---------------------------------------------------------------------------
# 17. OpenUSD remains export-only
# ---------------------------------------------------------------------------


def test_17_openusd_remains_export_only():
    import inspect
    import openusd_spatial_adapter

    source = inspect.getsource(openusd_spatial_adapter)
    for forbidden in ("BentleyItwinClient", "bentley_itwin_client", "normalize_itwin_import", "requests.", "oauth"):
        assert forbidden not in source, f"openusd_spatial_adapter.py must not reference {forbidden!r}"
    _, what_if = _locked_and_what_if()
    csa.normalize_itwin_import(what_if.registry, facility_id="FAC-BIM", elements=_building_floor_room_elements())
    path = openusd_spatial_adapter.build_deterministic_prim_path(what_if.registry.objects["ROOM-714"])
    assert path.startswith("/MRTwayCampus")


# ---------------------------------------------------------------------------
# 18-19. Routing protection
# ---------------------------------------------------------------------------


def test_18_manual_connectivity_graph_accepts_imported_canonical_rooms():
    _, what_if = _locked_and_what_if()
    csa.normalize_itwin_import(
        what_if.registry, facility_id="FAC-BIM",
        elements=_building_floor_room_elements() + [
            csa.BentleyElementRecord(itwin_id="ITWIN-1", imodel_id="IMODEL-1", element_id="EL-R02", element_class="ROOM", building_id="BLDG-A", floor_id="F1", room_number="ROOM-715", x=5.0, y=0.0, z=0.0),
        ],
    )
    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="E1", from_object_id="ROOM-714", to_object_id="ROOM-715", length_m=10.0, compatible_modes=frozenset({"PATIENT_MOVEMENT"})))
    assert graph.edges[0].from_object_id in what_if.registry.objects


def test_19_derive_shadow_route_works_unchanged_with_imported_rooms():
    import canonical_geometry_shadow_routing_authority as shadow

    _, what_if = _locked_and_what_if()
    csa.normalize_itwin_import(
        what_if.registry, facility_id="FAC-BIM",
        elements=_building_floor_room_elements() + [
            csa.BentleyElementRecord(itwin_id="ITWIN-1", imodel_id="IMODEL-1", element_id="EL-R02", element_class="ROOM", building_id="BLDG-A", floor_id="F1", room_number="ROOM-715", x=5.0, y=0.0, z=0.0),
        ],
    )
    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="E1", from_object_id="ROOM-714", to_object_id="ROOM-715", length_m=10.0, compatible_modes=frozenset({"PATIENT_MOVEMENT"})))
    imported_route = shadow.derive_shadow_route(graph, what_if.registry, request=shadow.CanonicalRouteRequest(
        route_request_id="R-IMPORTED", subject_type="PATIENT", subject_id="P1", transport_mode="PATIENT_WALK",
        origin_location_id="ROOM-714", destination_location_id="ROOM-715",
    ))

    manual_registry = csa.build_facility_hierarchy(facility_id="FAC-MANUAL")
    csa.add_building(manual_registry, facility_id="FAC-MANUAL", building_id="BLDG-M")
    csa.add_floor(manual_registry, facility_id="FAC-MANUAL", building_id="BLDG-M", floor_id="F1")
    csa.add_room(manual_registry, facility_id="FAC-MANUAL", building_id="BLDG-M", floor_id="F1", room_id="ROOM-714")
    csa.add_room(manual_registry, facility_id="FAC-MANUAL", building_id="BLDG-M", floor_id="F1", room_id="ROOM-715")
    manual_graph = csa.ConnectivityGraph()
    manual_graph.add_edge(csa.SpatialEdge(edge_id="E1", from_object_id="ROOM-714", to_object_id="ROOM-715", length_m=10.0, compatible_modes=frozenset({"PATIENT_MOVEMENT"})))
    manual_route = shadow.derive_shadow_route(manual_graph, manual_registry, request=shadow.CanonicalRouteRequest(
        route_request_id="R-MANUAL", subject_type="PATIENT", subject_id="P1", transport_mode="PATIENT_WALK",
        origin_location_id="ROOM-714", destination_location_id="ROOM-715",
    ))
    assert imported_route.total_distance_m == pytest.approx(manual_route.total_distance_m)
    assert imported_route.estimated_movement_time_minutes == pytest.approx(manual_route.estimated_movement_time_minutes)


def test_20_installed_network_authority_remains_unchanged():
    import authoritative_geometry_routing_activation as activation
    import canonical_geometry_shadow_routing_authority as shadow

    _, what_if = _locked_and_what_if()
    csa.normalize_itwin_import(
        what_if.registry, facility_id="FAC-BIM",
        elements=_building_floor_room_elements() + [
            csa.BentleyElementRecord(itwin_id="ITWIN-1", imodel_id="IMODEL-1", element_id="EL-R02", element_class="ROOM", building_id="BLDG-A", floor_id="F1", room_number="ROOM-715", x=5.0, y=0.0, z=0.0),
        ],
    )
    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="E1", from_object_id="ROOM-714", to_object_id="ROOM-715", length_m=10.0, compatible_modes=frozenset({"PATIENT_MOVEMENT"})))
    route = shadow.derive_shadow_route(graph, what_if.registry, request=shadow.CanonicalRouteRequest(
        route_request_id="R1", subject_type="GENERIC", subject_id="X", transport_mode="PATIENT_WALK",
        origin_location_id="ROOM-714", destination_location_id="ROOM-715",
    ))
    installed = activation.compute_installed_network_union([route])
    assert installed.total_length_m == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# 21. Phase 3 reactivity protection
# ---------------------------------------------------------------------------


def test_21_move_scanner_evaluator_consumes_imported_geometry_route_delta():
    import canonical_geometry_shadow_routing_authority as shadow
    import reactive_engineering_economic_consequence_authority as reac

    _, what_if = _locked_and_what_if()
    csa.normalize_itwin_import(
        what_if.registry, facility_id="FAC-BIM",
        elements=_building_floor_room_elements() + [
            csa.BentleyElementRecord(itwin_id="ITWIN-1", imodel_id="IMODEL-1", element_id="EL-R02", element_class="ROOM", building_id="BLDG-A", floor_id="F1", room_number="ROOM-715", x=5.0, y=0.0, z=0.0, source_scale_m_per_unit=1.0),
            csa.BentleyElementRecord(itwin_id="ITWIN-1", imodel_id="IMODEL-1", element_id="EL-R03", element_class="ROOM", building_id="BLDG-A", floor_id="F1", room_number="ROOM-716", x=20.0, y=0.0, z=0.0, source_scale_m_per_unit=1.0),
        ],
    )
    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="E1", from_object_id="ROOM-714", to_object_id="ROOM-715", length_m=10.0, compatible_modes=frozenset({"PATIENT_MOVEMENT"})))
    graph.add_edge(csa.SpatialEdge(edge_id="E2", from_object_id="ROOM-714", to_object_id="ROOM-716", length_m=25.0, compatible_modes=frozenset({"PATIENT_MOVEMENT"})))
    before = shadow.derive_shadow_route(graph, what_if.registry, request=shadow.CanonicalRouteRequest(
        route_request_id="BEFORE", subject_type="PATIENT", subject_id="P1", transport_mode="PATIENT_WALK",
        origin_location_id="ROOM-714", destination_location_id="ROOM-715",
    ))
    after = shadow.derive_shadow_route(graph, what_if.registry, request=shadow.CanonicalRouteRequest(
        route_request_id="AFTER", subject_type="PATIENT", subject_id="P1", transport_mode="PATIENT_WALK",
        origin_location_id="ROOM-714", destination_location_id="ROOM-716",
    ))
    record = reac.evaluate_move_scanner_consequence(
        change_id="BIM-C1", scanner_id="SCN-002", what_if_id="W1", source_lockdown_id="L0",
        route_distance_before_m=before.total_distance_m, route_distance_after_m=after.total_distance_m,
        travel_time_before_minutes=before.estimated_movement_time_minutes, travel_time_after_minutes=after.estimated_movement_time_minutes,
        throughput_patients_per_day=30.0, revenue_per_scan=2000.0, operating_days_per_year=300,
        discount_rate_pct=8.0, analysis_years=10, baseline_capex=5_000_000.0, baseline_annual_opex=1_000_000.0,
    )
    assert record.route_distance_before_m == pytest.approx(10.0)
    assert record.route_distance_after_m == pytest.approx(25.0)
    assert record.reactivity == "FULLY_REACTIVE"


# ---------------------------------------------------------------------------
# 22-23. Lockdown immutability
# ---------------------------------------------------------------------------


def test_22_l0_remains_immutable():
    locked, what_if = _locked_and_what_if()
    csa.normalize_itwin_import(what_if.registry, facility_id="FAC-BIM", elements=_building_floor_room_elements())
    assert "ROOM-714" not in locked.registry.objects


def test_23_w1_can_hold_changed_bentley_derived_geometry():
    locked, what_if = _locked_and_what_if()
    csa.normalize_itwin_import(what_if.registry, facility_id="FAC-BIM", elements=_building_floor_room_elements(x=1000.0, y=2000.0))
    original_x = what_if.registry.objects["ROOM-714"].transform.position_x
    # simulate a changed Bentley revision (moved room, new change_reference)
    changed_elements = _building_floor_room_elements(x=5000.0, y=2000.0)
    changed_elements[-1] = dataclasses.replace(changed_elements[-1], change_reference="CS-002")
    csa.normalize_itwin_import(what_if.registry, facility_id="FAC-BIM", elements=changed_elements)
    updated_room = what_if.registry.objects["ROOM-714"]
    assert updated_room.transform.position_x != pytest.approx(original_x)
    assert updated_room.external_reference.change_reference == "CS-002"
    assert "ROOM-714" not in locked.registry.objects  # L0 still untouched


# ---------------------------------------------------------------------------
# 24-26. Bentley client: no live call, injectable fake transport, no credentials
# ---------------------------------------------------------------------------


class _FakeTokenProvider:
    def get_access_token(self) -> str:
        return "FAKE-TOKEN"


class _FakeTransport:
    def __init__(self, responses):
        self._responses = responses

    def get(self, *, path, params, access_token, accept=None, extra_headers=None):
        assert access_token == "FAKE-TOKEN"
        return self._responses[path]


def test_24_25_bentley_client_uses_injectable_fake_transport_no_live_call():
    import bentley_itwin_client as bic

    fake_transport = _FakeTransport({
        "/itwins/ITWIN-1": {"iTwin": {"id": "ITWIN-1", "displayName": "MRTway Development Twin", "class": "Project"}},
        "/imodels/IMODEL-1": {"iModel": {"id": "IMODEL-1", "iTwinId": "ITWIN-1", "displayName": "MRTway Hospital Campus Development"}},
        "/imodels/IMODEL-1/elements": {"elements": [{"id": "EL-R01", "class": "Room", "label": "ROOM-714", "parentId": "EL-F1", "properties": {}}]},
        "/imodels/IMODEL-1/changesets": {"changesets": [{"id": "CS-001", "description": "initial sync"}]},
    })
    config = bic.BentleyClientConfig(
        client_id="fake-client-id", itwin_id="ITWIN-1", imodel_id="IMODEL-1", access_token_provider=_FakeTokenProvider(),
    )
    client = bic.BentleyItwinClient(config=config, transport=fake_transport)

    itwin_meta = client.get_itwin_metadata()
    assert itwin_meta.itwin_id == "ITWIN-1"
    assert itwin_meta.display_name == "MRTway Development Twin"

    imodel_meta = client.get_imodel_metadata()
    assert imodel_meta.imodel_id == "IMODEL-1"

    elements = client.get_elements()
    assert len(elements) == 1
    assert elements[0].element_id == "EL-R01"

    changeset = client.get_latest_changeset()
    assert changeset.change_reference == "CS-001"


def test_26_no_credentials_stored_in_source():
    import inspect
    import bentley_itwin_client as bic

    source = inspect.getsource(bic)
    for forbidden in ("client_secret=", "access_token=\"", "Bearer ey", "api_key="):
        assert forbidden not in source


# ---------------------------------------------------------------------------
# 27. Old IFC/CAD/API normalizers remain green
# ---------------------------------------------------------------------------


def test_27_old_ifc_cad_api_normalizers_remain_green():
    reg = csa.build_facility_hierarchy(facility_id="FAC-OLD")
    csa.add_building(reg, facility_id="FAC-OLD", building_id="BLDG-A")
    ifc_result = csa.normalize_ifc_bim_import(reg, source_version="IFC4")
    assert ifc_result.provenance == "IMPORTED_IFC"
    cad_result = csa.normalize_cad_import(reg, source_layer="A-ROOM")
    assert cad_result.provenance == "IMPORTED_CAD"
    api_result = csa.normalize_api_import(reg, source_system="SRC-1", source_timestamp="2026-01-01T00:00:00Z")
    assert api_result.provenance == "API"
