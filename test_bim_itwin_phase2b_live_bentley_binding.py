"""BIM/iTwin Phase 2B: live Bentley element retrieval, canonical binding,
route-authority reuse, and MOVE_SCANNER reactivity proof.

Section 15: deterministic OFFLINE tests (always run, no network/secrets
needed) are separated from OPT-IN LIVE Bentley integration tests (skipped
unless BENTLEY_CLIENT_ID/BENTLEY_CLIENT_SECRET/BENTLEY_ITWIN_ID/
BENTLEY_IMODEL_ID are all present in the environment).
"""

from __future__ import annotations

import os

import pytest

import bentley_canonical_binding as bcb
import bentley_itwin_client as bic
import canonical_spatial_authority as csa

ITWIN_ID = "bdf29ecd-b4a4-404d-861a-ac3061c7b12f"
IMODEL_ID = "ea9c0558-45a3-40b8-91a9-f4075b826925"


def _build_existing_canonical_registry():
    """Section 6/8: an already-existing canonical registry (as if built once
    by Phase 1's `normalize_itwin_import`) containing ROOM-RP-101,
    ROOM-SCN-202, and SCN-001 -- exactly the objects Phase 2B must resolve
    to, never fabricate."""
    reg = csa.build_facility_hierarchy(facility_id="FAC-HOSP-A")
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    elements = [
        csa.BentleyElementRecord(itwin_id=ITWIN_ID, imodel_id=IMODEL_ID, element_id="EL-BLDG", element_class="BUILDING", building_id="BLDG-HOSP-A"),
        csa.BentleyElementRecord(itwin_id=ITWIN_ID, imodel_id=IMODEL_ID, element_id="EL-F1", element_class="FLOOR", building_id="BLDG-HOSP-A", floor_id="F1"),
        csa.BentleyElementRecord(itwin_id=ITWIN_ID, imodel_id=IMODEL_ID, element_id="EL-F2", element_class="FLOOR", building_id="BLDG-HOSP-A", floor_id="F2"),
        csa.BentleyElementRecord(itwin_id=ITWIN_ID, imodel_id=IMODEL_ID, element_id="EL-RP", element_class="ROOM", building_id="BLDG-HOSP-A", floor_id="F1", room_number="ROOM-RP-101", x=5.0, y=15.0, z=0.0),
        csa.BentleyElementRecord(itwin_id=ITWIN_ID, imodel_id=IMODEL_ID, element_id="EL-SCN-ROOM", element_class="ROOM", building_id="BLDG-HOSP-A", floor_id="F2", room_number="ROOM-SCN-202", x=24.0, y=6.0, z=4.0),
        csa.BentleyElementRecord(itwin_id=ITWIN_ID, imodel_id=IMODEL_ID, element_id="EL-SCN-EQ", element_class="PET_SCANNER", building_id="BLDG-HOSP-A", floor_id="F2", engineering_object_id="SCN-001"),
    ]
    csa.normalize_itwin_import(what_if.registry, facility_id="FAC-HOSP-A", elements=elements)
    return locked, what_if


class _FakeToken:
    def get_access_token(self) -> str:
        return "FAKE-LIVE-TOKEN"


class _FakeTransport:
    """Section 25-26: deterministic fake transport -- no network, no
    secrets. Mirrors the manually-observed real Bentley evidence (section 6)
    exactly (ObjectType/GlobalId values)."""

    def __init__(self, elements=None, changesets=None):
        self._elements = elements if elements is not None else [
            {"id": "LIVE-EL-9001", "class": "ifcspace", "label": "Scanner Room", "parentId": None, "properties": {"ObjectType": "ROOM-SCN-202", "GlobalId": "MRTWAYPROOFGUID0000027"}},
            {"id": "LIVE-EL-9002", "class": "ifcbuildingelementproxy", "label": "Scanner (test proxy)", "parentId": None, "properties": {"ObjectType": "SCN-001", "GlobalId": "MRTWAYPROOFGUID0000039"}},
            {"id": "LIVE-EL-9003", "class": "ifcspace", "label": "Radiopharmacy", "parentId": None, "properties": {"ObjectType": "ROOM-RP-101", "GlobalId": "MRTWAYPROOFGUID0000009"}},
        ]
        self._changesets = changesets if changesets is not None else [{"id": "CS-LIVE-001", "description": "initial sync"}]

    def get(self, *, path, params, access_token):
        assert access_token == "FAKE-LIVE-TOKEN"
        if path.endswith("/elements"):
            return {"elements": self._elements}
        if path.endswith("/changesets"):
            return {"changesets": self._changesets}
        raise AssertionError(f"unexpected path: {path}")


def _build_client(**transport_kwargs):
    config = bic.BentleyClientConfig(client_id="fake-client", itwin_id=ITWIN_ID, imodel_id=IMODEL_ID, access_token_provider=_FakeToken())
    return bic.BentleyItwinClient(config=config, transport=_FakeTransport(**transport_kwargs))


# ---------------------------------------------------------------------------
# 1-3. Normalized live-element record supports required identity fields
# ---------------------------------------------------------------------------


def test_1_normalized_record_supports_external_itwin_imodel_identity():
    client = _build_client()
    live = client.find_live_element(object_type="ROOM-SCN-202")
    assert live.external_project_id == ITWIN_ID
    assert live.external_model_id == IMODEL_ID


def test_2_normalized_record_supports_external_element_id():
    client = _build_client()
    live = client.find_live_element(object_type="ROOM-SCN-202")
    assert live.external_element_id == "LIVE-EL-9001"


def test_3_normalized_record_supports_ifc_global_id():
    client = _build_client()
    live = client.find_live_element(object_type="ROOM-SCN-202")
    assert live.external_global_id == "MRTWAYPROOFGUID0000027"


# ---------------------------------------------------------------------------
# 4. Canonical reference extraction from ObjectType
# ---------------------------------------------------------------------------


def test_4_canonical_reference_extraction_from_object_type():
    client = _build_client()
    room = client.find_live_element(object_type="ROOM-SCN-202")
    scanner = client.find_live_element(object_type="SCN-001")
    assert room.canonical_reference_value == "ROOM-SCN-202"
    assert scanner.canonical_reference_value == "SCN-001"


# ---------------------------------------------------------------------------
# 5-8. Canonical binding, no duplicates
# ---------------------------------------------------------------------------


def test_5_room_scn_202_resolves_to_existing_canonical_room():
    _, what_if = _build_existing_canonical_registry()
    client = _build_client()
    live = client.find_live_element(object_type="ROOM-SCN-202")
    outcome = bcb.bind_live_bentley_element(what_if.registry, live)
    assert outcome.result == "BOUND_EXISTING"
    assert outcome.mrtway_object_id == "ROOM-SCN-202"


def test_6_scn_001_resolves_to_existing_scanner_engineering_object():
    _, what_if = _build_existing_canonical_registry()
    client = _build_client()
    live = client.find_live_element(object_type="SCN-001")
    outcome = bcb.bind_live_bentley_element(what_if.registry, live)
    assert outcome.result == "BOUND_EXISTING"
    assert outcome.mrtway_object_id == "SCN-001"
    assert what_if.registry.objects["SCN-001"].engineering_object_id == "SCN-001"


def test_7_no_duplicate_room_is_created():
    _, what_if = _build_existing_canonical_registry()
    client = _build_client()
    count_before = len(what_if.registry.objects)
    bcb.bind_live_bentley_element(what_if.registry, client.find_live_element(object_type="ROOM-SCN-202"))
    assert len(what_if.registry.objects) == count_before


def test_8_no_duplicate_scanner_is_created():
    _, what_if = _build_existing_canonical_registry()
    client = _build_client()
    count_before = len(what_if.registry.objects)
    bcb.bind_live_bentley_element(what_if.registry, client.find_live_element(object_type="SCN-001"))
    assert len(what_if.registry.objects) == count_before


# ---------------------------------------------------------------------------
# 9-12. Idempotency + external reference update
# ---------------------------------------------------------------------------


def test_9_repeated_binding_is_idempotent():
    _, what_if = _build_existing_canonical_registry()
    client = _build_client()
    live = client.find_live_element(object_type="ROOM-SCN-202")
    outcome_1 = bcb.bind_live_bentley_element(what_if.registry, live)
    count_after_first = len(what_if.registry.objects)
    outcome_2 = bcb.bind_live_bentley_element(what_if.registry, live)
    assert len(what_if.registry.objects) == count_after_first
    assert outcome_1.mrtway_object_id == outcome_2.mrtway_object_id == "ROOM-SCN-202"


def test_10_external_reference_attaches_to_existing_canonical_object():
    _, what_if = _build_existing_canonical_registry()
    client = _build_client()
    live = client.find_live_element(object_type="ROOM-SCN-202")
    bcb.bind_live_bentley_element(what_if.registry, live)
    room = what_if.registry.objects["ROOM-SCN-202"]
    assert room.external_reference.itwin_element_id == "LIVE-EL-9001"


def test_11_external_project_model_ids_preserved():
    _, what_if = _build_existing_canonical_registry()
    client = _build_client()
    bcb.bind_live_bentley_element(what_if.registry, client.find_live_element(object_type="ROOM-SCN-202"))
    room = what_if.registry.objects["ROOM-SCN-202"]
    assert room.external_reference.external_project_id == ITWIN_ID
    assert room.external_reference.external_model_id == IMODEL_ID


def test_12_change_reference_preserved_if_supplied():
    _, what_if = _build_existing_canonical_registry()
    client = _build_client()
    bcb.bind_live_bentley_element(what_if.registry, client.find_live_element(object_type="ROOM-SCN-202"))
    room = what_if.registry.objects["ROOM-SCN-202"]
    assert room.external_reference.change_reference == "CS-LIVE-001"


# ---------------------------------------------------------------------------
# 13-15. Explicit failure -- never fabricate
# ---------------------------------------------------------------------------


def test_13_missing_canonical_reference_fails_explicitly():
    _, what_if = _build_existing_canonical_registry()
    bad_element = bic.BentleyLiveElementRecord(
        external_project_id=ITWIN_ID, external_model_id=IMODEL_ID, external_element_id="EL-NO-OBJECTTYPE",
        external_global_id=None, element_class="ifcspace", label="Unlabeled Room", canonical_reference_value=None,
        change_reference=None, placement_xyz_m=None,
    )
    outcome = bcb.bind_live_bentley_element(what_if.registry, bad_element)
    assert outcome.result == "MISSING_CANONICAL_REFERENCE"
    assert outcome.mrtway_object_id is None


def test_14_unknown_canonical_room_fails_explicitly():
    _, what_if = _build_existing_canonical_registry()
    unknown_room = bic.BentleyLiveElementRecord(
        external_project_id=ITWIN_ID, external_model_id=IMODEL_ID, external_element_id="EL-UNKNOWN-ROOM",
        external_global_id="MRTWAYPROOFGUID9999999", element_class="ifcspace", label="Mystery Room",
        canonical_reference_value="ROOM-DOES-NOT-EXIST", change_reference=None, placement_xyz_m=None,
    )
    outcome = bcb.bind_live_bentley_element(what_if.registry, unknown_room)
    assert outcome.result == "UNKNOWN_CANONICAL_ROOM"
    assert outcome.mrtway_object_id is None
    assert "ROOM-DOES-NOT-EXIST" not in what_if.registry.objects


def test_15_unknown_engineering_object_fails_explicitly():
    _, what_if = _build_existing_canonical_registry()
    unknown_equipment = bic.BentleyLiveElementRecord(
        external_project_id=ITWIN_ID, external_model_id=IMODEL_ID, external_element_id="EL-UNKNOWN-EQ",
        external_global_id="MRTWAYPROOFGUID9999998", element_class="ifcbuildingelementproxy", label="Mystery Equipment",
        canonical_reference_value="CY-999", change_reference=None, placement_xyz_m=None,
    )
    outcome = bcb.bind_live_bentley_element(what_if.registry, unknown_equipment)
    assert outcome.result == "UNKNOWN_ENGINEERING_OBJECT"
    assert outcome.mrtway_object_id is None
    assert "CY-999" not in what_if.registry.objects


# ---------------------------------------------------------------------------
# 16. Vendor-specific client objects do not leak into routing authority
# ---------------------------------------------------------------------------


def test_16_vendor_specific_objects_do_not_leak_into_routing_authority():
    import inspect
    import canonical_geometry_shadow_routing_authority as shadow

    source = inspect.getsource(shadow)
    assert "bentley_itwin_client" not in source
    assert "bentley_canonical_binding" not in source
    assert "BentleyLiveElementRecord" not in source


# ---------------------------------------------------------------------------
# 17-18. Existing routing/installed-network authorities unchanged
# ---------------------------------------------------------------------------


def test_17_derive_shadow_route_works_unchanged_after_live_style_binding():
    import canonical_geometry_shadow_routing_authority as shadow

    _, what_if = _build_existing_canonical_registry()
    client = _build_client()
    bcb.bind_live_bentley_element(what_if.registry, client.find_live_element(object_type="ROOM-SCN-202"))
    bcb.bind_live_bentley_element(what_if.registry, client.find_live_element(object_type="ROOM-RP-101"))

    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="E1", from_object_id="ROOM-RP-101", to_object_id="ROOM-SCN-202", length_m=25.0, compatible_modes=frozenset({"PATIENT_MOVEMENT"})))
    route = shadow.derive_shadow_route(graph, what_if.registry, request=shadow.CanonicalRouteRequest(
        route_request_id="R1", subject_type="PATIENT", subject_id="P1", transport_mode="PATIENT_WALK",
        origin_location_id="ROOM-RP-101", destination_location_id="ROOM-SCN-202",
    ))
    assert route.total_distance_m == pytest.approx(25.0)


def test_18_installed_network_authority_remains_unchanged():
    import authoritative_geometry_routing_activation as activation
    import canonical_geometry_shadow_routing_authority as shadow

    _, what_if = _build_existing_canonical_registry()
    graph = csa.ConnectivityGraph()
    graph.add_edge(csa.SpatialEdge(edge_id="E1", from_object_id="ROOM-RP-101", to_object_id="ROOM-SCN-202", length_m=25.0, compatible_modes=frozenset({"PATIENT_MOVEMENT"})))
    route = shadow.derive_shadow_route(graph, what_if.registry, request=shadow.CanonicalRouteRequest(
        route_request_id="R1", subject_type="GENERIC", subject_id="X", transport_mode="PATIENT_WALK",
        origin_location_id="ROOM-RP-101", destination_location_id="ROOM-SCN-202",
    ))
    installed = activation.compute_installed_network_union([route])
    assert installed.total_length_m == pytest.approx(25.0)


# ---------------------------------------------------------------------------
# 19-20. OpenUSD export-only + Lockdown preservation
# ---------------------------------------------------------------------------


def test_19_openusd_adapter_remains_export_only():
    import inspect
    import openusd_spatial_adapter

    source = inspect.getsource(openusd_spatial_adapter)
    for forbidden in ("bentley_itwin_client", "bentley_canonical_binding"):
        assert forbidden not in source


def test_20_lockdown_l0_remains_unchanged_after_w1_proof():
    locked, what_if = _build_existing_canonical_registry()
    client = _build_client()
    bcb.bind_live_bentley_element(what_if.registry, client.find_live_element(object_type="ROOM-SCN-202"))
    bcb.bind_live_bentley_element(what_if.registry, client.find_live_element(object_type="SCN-001"))
    assert "ROOM-SCN-202" not in locked.registry.objects
    assert "SCN-001" not in locked.registry.objects


# ---------------------------------------------------------------------------
# 21-22. MOVE_SCANNER reactivity
# ---------------------------------------------------------------------------


def test_21_move_scanner_evaluator_remains_unchanged():
    import inspect
    import reactive_engineering_economic_consequence_authority as reac

    assert "bentley" not in inspect.getsource(reac).lower()


def test_22_controlled_move_scanner_proof_produces_fully_reactive():
    import canonical_geometry_shadow_routing_authority as shadow
    import reactive_engineering_economic_consequence_authority as reac

    locked, what_if = _build_existing_canonical_registry()
    client = _build_client()
    room_outcome = bcb.bind_live_bentley_element(what_if.registry, client.find_live_element(object_type="ROOM-SCN-202"))
    scanner_outcome = bcb.bind_live_bentley_element(what_if.registry, client.find_live_element(object_type="SCN-001"))
    assert room_outcome.result == "BOUND_EXISTING"
    assert scanner_outcome.result == "BOUND_EXISTING"

    graph_before = csa.ConnectivityGraph()
    graph_before.add_edge(csa.SpatialEdge(edge_id="E1", from_object_id="ROOM-RP-101", to_object_id="ROOM-SCN-202", length_m=25.0, compatible_modes=frozenset({"PATIENT_MOVEMENT"})))
    route_before = shadow.derive_shadow_route(graph_before, what_if.registry, request=shadow.CanonicalRouteRequest(
        route_request_id="BEFORE", subject_type="PATIENT", subject_id="P1", transport_mode="PATIENT_WALK",
        origin_location_id="ROOM-RP-101", destination_location_id="ROOM-SCN-202",
    ))

    graph_after = csa.ConnectivityGraph()
    graph_after.add_edge(csa.SpatialEdge(edge_id="E1", from_object_id="ROOM-RP-101", to_object_id="ROOM-SCN-202", length_m=40.0, compatible_modes=frozenset({"PATIENT_MOVEMENT"})))
    route_after = shadow.derive_shadow_route(graph_after, what_if.registry, request=shadow.CanonicalRouteRequest(
        route_request_id="AFTER", subject_type="PATIENT", subject_id="P1", transport_mode="PATIENT_WALK",
        origin_location_id="ROOM-RP-101", destination_location_id="ROOM-SCN-202",
    ))

    record = reac.evaluate_move_scanner_consequence(
        change_id="BIM2B-PROOF", scanner_id=scanner_outcome.mrtway_object_id, what_if_id="W1", source_lockdown_id="L0",
        route_distance_before_m=route_before.total_distance_m, route_distance_after_m=route_after.total_distance_m,
        travel_time_before_minutes=route_before.estimated_movement_time_minutes, travel_time_after_minutes=route_after.estimated_movement_time_minutes,
        throughput_patients_per_day=30.0, revenue_per_scan=2000.0, operating_days_per_year=300,
        discount_rate_pct=8.0, analysis_years=10, baseline_capex=5_000_000.0, baseline_annual_opex=1_000_000.0,
    )
    assert record.reactivity == "FULLY_REACTIVE"
    assert "ROOM-SCN-202" not in locked.registry.objects  # L0 still untouched after the full proof chain


# ---------------------------------------------------------------------------
# 23-24. Old normalizers remain green + client vendor boundary discipline
# ---------------------------------------------------------------------------


def test_23_old_ifc_cad_api_itwin_normalizers_remain_green():
    reg = csa.build_facility_hierarchy(facility_id="FAC-OLD")
    csa.add_building(reg, facility_id="FAC-OLD", building_id="BLDG-A")
    assert csa.normalize_ifc_bim_import(reg, source_version="IFC4").provenance == "IMPORTED_IFC"
    assert csa.normalize_cad_import(reg, source_layer="A-ROOM").provenance == "IMPORTED_CAD"
    assert csa.normalize_api_import(reg, source_system="SRC-1", source_timestamp="2026-01-01T00:00:00Z").provenance == "API"

    _, what_if = _build_existing_canonical_registry()
    assert what_if.registry.objects["ROOM-RP-101"].provenance == "IMPORTED_ITWIN"


def test_24_bentley_client_contains_no_route_economic_clinical_imports():
    import inspect

    source = inspect.getsource(bic)
    forbidden = (
        "canonical_geometry_shadow_routing_authority", "reactive_engineering_economic_consequence_authority",
        "production_clinical_schedule", "patient_radionuclide_demand", "decision_pipeline",
        "authoritative_geometry_routing_activation", "canonical_entity_binding_authority",
    )
    for term in forbidden:
        assert term not in source


# ---------------------------------------------------------------------------
# 25-26. External identity distinct from canonical identity; rebinding
# ---------------------------------------------------------------------------


def test_25_external_identity_remains_distinct_from_canonical_identity():
    _, what_if = _build_existing_canonical_registry()
    client = _build_client()
    outcome = bcb.bind_live_bentley_element(what_if.registry, client.find_live_element(object_type="ROOM-SCN-202"))
    room = what_if.registry.objects[outcome.mrtway_object_id]
    assert room.mrtway_object_id == "ROOM-SCN-202"  # canonical identity
    assert room.external_reference.itwin_element_id == "LIVE-EL-9001"  # external identity -- distinct value
    assert room.mrtway_object_id != room.external_reference.itwin_element_id


def test_26_changing_external_element_id_does_not_create_new_canonical_object():
    _, what_if = _build_existing_canonical_registry()
    client_v1 = _build_client()
    bcb.bind_live_bentley_element(what_if.registry, client_v1.find_live_element(object_type="ROOM-SCN-202"))
    count_before = len(what_if.registry.objects)

    # A future synchronization changes the Bentley element ID but the canonical reference is unchanged.
    client_v2 = _build_client(elements=[
        {"id": "LIVE-EL-REBOUND-9001", "class": "ifcspace", "label": "Scanner Room", "parentId": None, "properties": {"ObjectType": "ROOM-SCN-202", "GlobalId": "MRTWAYPROOFGUID-REV2"}},
    ])
    outcome_v2 = bcb.bind_live_bentley_element(what_if.registry, client_v2.find_live_element(object_type="ROOM-SCN-202"))
    assert outcome_v2.mrtway_object_id == "ROOM-SCN-202"
    assert len(what_if.registry.objects) == count_before  # no second canonical object
    assert what_if.registry.objects["ROOM-SCN-202"].external_reference.itwin_element_id == "LIVE-EL-REBOUND-9001"


# ---------------------------------------------------------------------------
# 27-28. Serialization + Phase 2A/2A.1 asset protection
# ---------------------------------------------------------------------------


def test_27_serialization_round_trip_preserves_updated_bentley_external_reference():
    _, what_if = _build_existing_canonical_registry()
    client = _build_client()
    bcb.bind_live_bentley_element(what_if.registry, client.find_live_element(object_type="ROOM-SCN-202"))
    payload = csa.registry_to_json(what_if.registry)
    reloaded = csa.registry_from_json(payload)
    room = reloaded.objects["ROOM-SCN-202"]
    assert room.external_reference.itwin_element_id == "LIVE-EL-9001"
    assert room.external_reference.external_project_id == ITWIN_ID
    assert room.external_reference.external_model_id == IMODEL_ID
    assert room.external_reference.change_reference == "CS-LIVE-001"


def test_28_phase2a_proof_assets_remain_unchanged_by_phase2b_code():
    import inspect

    for module in (bic, bcb):
        source = inspect.getsource(module)
        assert "ifc_hospital_proof_model_generator" not in source
        assert "write_hospital_proof_model" not in source


# ---------------------------------------------------------------------------
# Section 17: opt-in LIVE Bentley integration tests -- skipped unless
# real credentials/configuration are present in the environment.
# ---------------------------------------------------------------------------

_LIVE_AVAILABLE = bic.bentley_live_environment_available()
_live_skip_reason = "BENTLEY_CLIENT_ID/BENTLEY_CLIENT_SECRET/BENTLEY_ITWIN_ID/BENTLEY_IMODEL_ID not set -- live Bentley tests are opt-in only"
live_bentley = pytest.mark.skipif(not _LIVE_AVAILABLE, reason=_live_skip_reason)


def _build_live_client():
    token_provider = bic.BentleyClientCredentialsTokenProvider(
        client_id=os.environ["BENTLEY_CLIENT_ID"], client_secret=os.environ["BENTLEY_CLIENT_SECRET"],
        authority_url=os.environ.get("BENTLEY_AUTHORITY_URL", "https://ims.bentley.com/connect/token"),
        scope=os.environ.get("BENTLEY_SCOPE", "itwin-platform"),
    )
    config = bic.build_config_from_environment(access_token_provider=token_provider)
    return bic.BentleyItwinClient(config=config, transport=bic.BentleyHttpTransport())


@live_bentley
def test_live_1_service_authentication_succeeds():
    client = _build_live_client()
    client.get_itwin_metadata()  # raises if authentication fails


@live_bentley
def test_live_2_itwin_metadata_can_be_retrieved():
    client = _build_live_client()
    metadata = client.get_itwin_metadata()
    assert metadata.itwin_id == ITWIN_ID


@live_bentley
def test_live_3_imodel_metadata_can_be_retrieved():
    client = _build_live_client()
    metadata = client.get_imodel_metadata()
    assert metadata.imodel_id == IMODEL_ID


@live_bentley
def test_live_4_scanner_room_element_can_be_found():
    client = _build_live_client()
    element = client.find_element(object_type="ROOM-SCN-202")
    assert element is not None


@live_bentley
def test_live_5_scanner_room_canonical_reference_resolves():
    client = _build_live_client()
    live = client.find_live_element(object_type="ROOM-SCN-202")
    assert live is not None
    assert live.canonical_reference_value == "ROOM-SCN-202"


@live_bentley
def test_live_6_scanner_room_external_identity_captured():
    client = _build_live_client()
    live = client.find_live_element(object_type="ROOM-SCN-202")
    assert live.external_element_id  # non-empty, never asserted to a specific secret-adjacent value


@live_bentley
def test_live_7_scanner_equipment_element_can_be_found():
    client = _build_live_client()
    element = client.find_element(object_type="SCN-001")
    assert element is not None


@live_bentley
def test_live_8_scanner_canonical_reference_resolves():
    client = _build_live_client()
    live = client.find_live_element(object_type="SCN-001")
    assert live is not None
    assert live.canonical_reference_value == "SCN-001"


@live_bentley
def test_live_9_scanner_external_identity_captured():
    client = _build_live_client()
    live = client.find_live_element(object_type="SCN-001")
    assert live.external_element_id


@live_bentley
def test_live_10_live_elements_bind_without_duplication():
    _, what_if = _build_existing_canonical_registry()
    client = _build_live_client()
    room_live = client.find_live_element(object_type="ROOM-SCN-202")
    scanner_live = client.find_live_element(object_type="SCN-001")
    count_before = len(what_if.registry.objects)
    bcb.bind_live_bentley_element(what_if.registry, room_live)
    bcb.bind_live_bentley_element(what_if.registry, scanner_live)
    assert len(what_if.registry.objects) == count_before


@live_bentley
def test_live_11_optional_radiopharmacy_retrieval_succeeds():
    client = _build_live_client()
    live = client.find_live_element(object_type="ROOM-RP-101")
    assert live is not None
    assert live.canonical_reference_value == "ROOM-RP-101"


@live_bentley
def test_live_12_placement_matches_manifest_if_available():
    client = _build_live_client()
    live = client.find_live_element(object_type="ROOM-SCN-202")
    if live.placement_xyz_m is None:
        pytest.skip("LIVE_BENTLEY_PLACEMENT_RETRIEVAL = NOT_AVAILABLE_IN_SELECTED_ENDPOINT")
    assert live.placement_xyz_m == pytest.approx((24.0, 6.0, 4.0))


@live_bentley
def test_live_13_no_secret_appears_in_assertion_output(capsys):
    client = _build_live_client()
    client.get_itwin_metadata()
    captured = capsys.readouterr()
    assert os.environ["BENTLEY_CLIENT_SECRET"] not in captured.out
    assert os.environ["BENTLEY_CLIENT_SECRET"] not in captured.err
