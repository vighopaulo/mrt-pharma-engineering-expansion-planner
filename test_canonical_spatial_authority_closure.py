"""Focused tests for the CANONICAL SPATIAL AUTHORITY CLOSURE build.

Covers: MRT economic-authority audit, no duplicate MRT economic model,
user-supplied vestibule/controls/installation reconciliation, guideway/
carrier cost authority reconciliation, endpoint economics honest calibration,
transport-only CapEx exclusion of common clinical/nuclear assets, controlled
500m/50-carrier reconciliation, complete MRT builders (trunk/branch/junction/
endpoint/carrier/container), multiple vestibules, five-building hierarchy +
floor-ID non-collision, five-building routing (A->B/A->C/A->E/C->E),
multi-building MRT/Manual/AGV/PTS routing, production-source generality,
Hybrid spatial coverage, Retrofit/Greenfield N-building semantics, canonical
patient spatial consumption (PET/SPECT, inpatient/outpatient), route-feeds-
existing-physics interface, all 7 input-normalization contracts, locked/
what-if non-regression, camera vs engineering rotation, connectivity-aware
transforms, selection/group/bounding-volume contracts, spatial economic
deltas, serialization, validation, and component non-regression.
"""

import dataclasses

import pytest

import canonical_spatial_authority as csa
from whole_oncology_four_architecture_optimization import (
    build_common_project_baseline,
    _nuclear_result,
    resolve_hybrid_nuclear_spatial_context,
)


# ---------------------------------------------------------------------------
# 1. MRT economic-authority audit + no duplicate economic model
# ---------------------------------------------------------------------------


def test_mrt_economic_audit_returns_structured_entries():
    audit = csa.audit_mrt_economic_authority()
    assert len(audit) >= 10
    components = {e.component for e in audit}
    assert "Guideway/conduit unit cost" in components
    assert "Carrier unit cost" in components
    assert "Vestibule CapEx (this build)" in components


def test_audit_reuses_models_planner_assumptions_never_redeclares():
    from models import PlannerAssumptions
    a = PlannerAssumptions()
    audit = csa.audit_mrt_economic_authority()
    guideway_entry = next(e for e in audit if e.component == "Guideway/conduit unit cost")
    assert f"${a.mrt_guideway_capex_per_m:,.0f}/m" == guideway_entry.value
    carrier_entry = next(e for e in audit if e.component == "Carrier unit cost")
    assert f"${a.mrt_carrier_capex_per_installed_unit:,.0f}/carrier" == carrier_entry.value


def test_no_second_carrier_or_guideway_constant_declared_in_spatial_module():
    """canonical_spatial_authority.py must not redeclare its own guideway/
    carrier unit cost constants -- compute_mrt_transport_only_capex() always
    falls back to models.PlannerAssumptions when not explicitly overridden."""
    result_default = csa.compute_mrt_transport_only_capex(guideway_length_m=10.0, carrier_count=1)
    from models import PlannerAssumptions
    a = PlannerAssumptions()
    guideway_line = result_default.line_item("MRT guideway/trunk/branch/segment")
    carrier_line = result_default.line_item("MRT carriers")
    assert guideway_line.unit_cost == a.mrt_guideway_capex_per_m
    assert carrier_line.unit_cost == a.mrt_carrier_capex_per_installed_unit


def test_prior_43000_vestibule_value_is_superseded_not_a_second_authority():
    audit = csa.audit_mrt_economic_authority()
    superseded = next(e for e in audit if "PRIOR spatial-build value" in e.component)
    assert superseded.actively_used is False
    assert "SUPERSEDED" in superseded.provenance


# ---------------------------------------------------------------------------
# 2. User-supplied vestibule/controls/installation assumptions
# ---------------------------------------------------------------------------


def test_user_supplied_vestibule_capex_is_30000():
    assert csa.MRT_VESTIBULE_CAPEX_USD == 30_000.0
    assert csa.CONTROLLED_VESTIBULE_ECONOMICS.total_capex() == 30_000.0
    assert "USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION" in csa.CONTROLLED_VESTIBULE_ECONOMICS.provenance


def test_controls_and_installation_constants_labeled_user_supplied():
    assert csa.MRT_CONTROLS_CAPEX_USD == 100_000.0
    assert csa.MRT_INSTALLATION_COMMISSIONING_CAPEX_USD == 300_000.0


def test_controls_charged_once_never_multiplied_by_scale():
    small = csa.compute_mrt_transport_only_capex(guideway_length_m=10.0, carrier_count=1, include_controls=True)
    large = csa.compute_mrt_transport_only_capex(guideway_length_m=5000.0, carrier_count=500, vestibule_count=10, include_controls=True)
    assert small.line_item("MRT controls (system/network, once)").capex == 100_000.0
    assert large.line_item("MRT controls (system/network, once)").capex == 100_000.0


def test_installation_charged_once_never_multiplied_by_scale():
    small = csa.compute_mrt_transport_only_capex(guideway_length_m=10.0, carrier_count=1, include_installation_commissioning=True)
    large = csa.compute_mrt_transport_only_capex(guideway_length_m=5000.0, carrier_count=500, vestibule_count=10, include_installation_commissioning=True)
    assert small.line_item("MRT installation/commissioning (project, once)").capex == 300_000.0
    assert large.line_item("MRT installation/commissioning (project, once)").capex == 300_000.0


def test_controls_and_installation_absent_when_flags_false():
    result = csa.compute_mrt_transport_only_capex(guideway_length_m=100.0, carrier_count=5)
    assert result.line_item("MRT controls (system/network, once)").capex == 0.0
    assert result.line_item("MRT installation/commissioning (project, once)").capex == 0.0


def test_second_vestibule_adds_exactly_30k_not_controls_or_installation():
    one = csa.compute_mrt_transport_only_capex(vestibule_count=1)
    two = csa.compute_mrt_transport_only_capex(vestibule_count=2)
    assert two.line_item("MRT vestibules").capex - one.line_item("MRT vestibules").capex == pytest.approx(30_000.0)
    # controls/installation remain zero (flags not set) regardless of vestibule count
    assert one.line_item("MRT controls (system/network, once)").capex == 0.0
    assert two.line_item("MRT controls (system/network, once)").capex == 0.0


# ---------------------------------------------------------------------------
# 3. Guideway/carrier cost authority reconciliation (audit BEFORE change)
# ---------------------------------------------------------------------------


def test_guideway_authoritative_default_is_5000_per_meter_not_6000_not_100():
    """Genuine conflict finding: the repo's actual PlannerAssumptions default
    is $5,000/m -- NOT the user's recalled $6,000/m (which does not exist
    anywhere in the repository), and NOT the prior report's $100/m smoke-test
    example (never a stored constant)."""
    from models import PlannerAssumptions
    a = PlannerAssumptions()
    assert a.mrt_guideway_capex_per_m == 5_000.0
    assert a.mrt_guideway_capex_per_m != 6_000.0
    assert a.mrt_guideway_capex_per_m != 100.0


def test_carrier_authoritative_default_matches_user_assumption_exactly():
    from models import PlannerAssumptions
    a = PlannerAssumptions()
    assert a.mrt_carrier_capex_per_installed_unit == 10_000.0


def test_endpoint_generic_campus_economics_honestly_not_calibrated():
    result = csa.compute_mrt_transport_only_capex(endpoint_count=3)
    endpoint_line = result.line_item("MRT endpoints/junctions")
    assert endpoint_line.capex == "NOT_CALIBRATED"
    assert endpoint_line.economic_category == "NOT_CALIBRATED"


def test_endpoint_line_excluded_from_total_when_not_calibrated_never_fabricated():
    result = csa.compute_mrt_transport_only_capex(guideway_length_m=100.0, carrier_count=1, endpoint_count=5)
    # total must be a real float, excluding the NOT_CALIBRATED endpoint line
    assert isinstance(result.total_capex, float)
    from models import PlannerAssumptions
    a = PlannerAssumptions()
    expected = 100.0 * a.mrt_guideway_capex_per_m + 1 * a.mrt_carrier_capex_per_installed_unit
    assert result.total_capex == pytest.approx(expected)


# ---------------------------------------------------------------------------
# 4. Transport-only CapEx excludes common clinical/nuclear assets
# ---------------------------------------------------------------------------


def test_transport_only_capex_excludes_cyclotron_generator_pet_spect():
    result = csa.compute_mrt_transport_only_capex(guideway_length_m=500.0, carrier_count=50, vestibule_count=1, include_controls=True, include_installation_commissioning=True)
    components = {li.component for li in result.line_items}
    assert not any("cyclotron" in c.lower() for c in components)
    assert not any("generator" in c.lower() for c in components)
    assert not any("pet scanner" in c.lower() for c in components)
    assert not any("spect scanner" in c.lower() for c in components)


def test_common_cost_exclusion_classification_table():
    classification = csa.classify_common_vs_architecture_specific_costs()
    common = {c.asset for c in classification if c.category == "COMMON_CLINICAL_NUCLEAR_BASELINE"}
    architecture_specific = {c.asset for c in classification if c.category == "ARCHITECTURE_SPECIFIC_TRANSPORT_CAPEX"}
    assert any("Cyclotron" in a for a in common)
    assert any("generator" in a.lower() for a in common)
    assert any("PET scanner" in a for a in common)
    assert any("SPECT scanner" in a for a in common)
    assert any("guideway" in a.lower() for a in architecture_specific)
    assert any("vestibule" in a.lower() for a in architecture_specific)
    for c in classification:
        if c.category == "COMMON_CLINICAL_NUCLEAR_BASELINE":
            assert c.included_in_mrt_transport_only_capex is False


def test_agv_pts_transport_subsystem_not_compared_against_whole_mrt_project():
    classification = csa.classify_common_vs_architecture_specific_costs()
    agv_pts = next(c for c in classification if "AGV/PTS" in c.asset)
    assert agv_pts.category == "ARCHITECTURE_SPECIFIC_TRANSPORT_CAPEX"
    assert agv_pts.included_in_mrt_transport_only_capex is False


# ---------------------------------------------------------------------------
# 5. Controlled 500m/50-carrier reconciliation
# ---------------------------------------------------------------------------


def test_controlled_500m_50carrier_reconciliation_uses_authoritative_default():
    """Per section 13's explicit conditional: only force $3,930,000 if the
    audit confirms $6,000/m and $10,000/carrier remain legitimate. Since
    $6,000/m does NOT exist as a current authority, the reconciled subtotal
    correctly uses the ACTUAL default ($5,000/m), giving $3,430,000 --
    never a fabricated third value."""
    result = csa.compute_mrt_transport_only_capex(
        guideway_length_m=500.0, carrier_count=50, vestibule_count=1,
        include_controls=True, include_installation_commissioning=True,
    )
    assert result.line_item("MRT guideway/trunk/branch/segment").capex == pytest.approx(2_500_000.0)
    assert result.line_item("MRT carriers").capex == pytest.approx(500_000.0)
    assert result.line_item("MRT vestibules").capex == pytest.approx(30_000.0)
    assert result.line_item("MRT controls (system/network, once)").capex == pytest.approx(100_000.0)
    assert result.line_item("MRT installation/commissioning (project, once)").capex == pytest.approx(300_000.0)
    assert result.total_capex == pytest.approx(3_430_000.0)


def test_controlled_reconciliation_with_hypothetical_6000_per_m_override():
    """If a caller explicitly supplies $6,000/m (not silently assumed), the
    user's originally-suggested $3,930,000 figure IS reproducible -- proving
    the function is flexible without inventing a hidden default."""
    result = csa.compute_mrt_transport_only_capex(
        guideway_length_m=500.0, guideway_unit_cost_per_m=6_000.0, carrier_count=50, vestibule_count=1,
        include_controls=True, include_installation_commissioning=True,
    )
    assert result.total_capex == pytest.approx(3_930_000.0)


# ---------------------------------------------------------------------------
# 6. Complete MRT first-class builders
# ---------------------------------------------------------------------------


def _fresh_registry_with_facility():
    return csa.build_facility_hierarchy(facility_id="FAC-001")


def test_mrt_trunk_builder_has_full_identity_fields():
    reg = _fresh_registry_with_facility()
    trunk = csa.build_mrt_trunk(reg, trunk_id="TRUNK-1", facility_id="FAC-001", length_m=100.0)
    assert trunk.object_type == "MRT_TRUNK"
    assert trunk.facility_id == "FAC-001"
    assert trunk.parent_object_id == "FAC-001"
    assert trunk.spatial_status == "CALIBRATED"
    assert trunk.asset_status == "PROPOSED"
    assert trunk.operational_state == "AVAILABLE"
    assert trunk.provenance == "USER_CREATED"


def test_mrt_trunk_not_calibrated_geometry_status():
    reg = _fresh_registry_with_facility()
    trunk = csa.build_mrt_trunk(reg, trunk_id="TRUNK-NC", facility_id="FAC-001")
    assert trunk.spatial_status == "GEOMETRY_NOT_CALIBRATED"


def test_mrt_branch_must_connect_legitimately_no_orphans():
    reg = _fresh_registry_with_facility()
    trunk = csa.build_mrt_trunk(reg, trunk_id="TRUNK-1", facility_id="FAC-001", length_m=50.0)
    branch = csa.build_mrt_branch(reg, branch_id="BRANCH-1", facility_id="FAC-001", connects_to_object_id=trunk.mrtway_object_id, length_m=25.0)
    assert branch.parent_object_id == trunk.mrtway_object_id
    with pytest.raises(ValueError):
        csa.build_mrt_branch(reg, branch_id="BRANCH-ORPHAN", facility_id="FAC-001", connects_to_object_id="DOES-NOT-EXIST")
    with pytest.raises(ValueError):
        csa.build_mrt_branch(reg, branch_id="BRANCH-BAD-TYPE", facility_id="FAC-001", connects_to_object_id="FAC-001")


def test_mrt_junction_no_auto_capex():
    reg = _fresh_registry_with_facility()
    junction = csa.build_mrt_junction(reg, junction_id="JCT-1", facility_id="FAC-001")
    assert junction.object_type == "MRT_JUNCTION"
    # no CapEx field on the object itself; compute_mrt_transport_only_capex has no per-junction line at all
    assert not hasattr(junction, "capex")


def test_mrt_endpoint_requires_network_connection_and_optional_served_zone():
    reg = _fresh_registry_with_facility()
    trunk = csa.build_mrt_trunk(reg, trunk_id="TRUNK-1", facility_id="FAC-001", length_m=50.0)
    csa.add_building(reg, facility_id="FAC-001", building_id="BLDG-A")
    csa.add_floor(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1")
    csa.add_room(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1", room_id="ROOM-1")
    endpoint = csa.build_mrt_endpoint(reg, endpoint_id="EP-1", facility_id="FAC-001", connected_network_object_id=trunk.mrtway_object_id, served_object_id="ROOM-1")
    assert endpoint.parent_object_id == trunk.mrtway_object_id
    assert endpoint.space_id == "ROOM-1"
    assert endpoint.building_id == "BLDG-A"
    with pytest.raises(ValueError):
        csa.build_mrt_endpoint(reg, endpoint_id="EP-BAD", facility_id="FAC-001", connected_network_object_id="DOES-NOT-EXIST")


def test_mrt_carrier_builder_distinct_from_container_and_shared_fleet_preserved():
    reg = _fresh_registry_with_facility()
    trunk = csa.build_mrt_trunk(reg, trunk_id="TRUNK-1", facility_id="FAC-001", length_m=50.0)
    carriers = csa.build_mrt_carrier_fleet_spatial_objects(reg, facility_id="FAC-001", network_object_id=trunk.mrtway_object_id, carrier_count=5)
    assert len(carriers) == 5
    assert all(c.object_type == "MRT_CARRIER" for c in carriers)
    assert len({c.mrtway_object_id for c in carriers}) == 5  # each carrier keeps its own stable ID -- never one shared object


def test_mrt_container_distinct_from_carrier_preserves_payload_class():
    reg = _fresh_registry_with_facility()
    trunk = csa.build_mrt_trunk(reg, trunk_id="TRUNK-1", facility_id="FAC-001", length_m=50.0)
    container = csa.build_mrt_container(reg, container_id="CNT-1", facility_id="FAC-001", container_class_id="NUCLEAR_SHIELDED_CONTAINER", network_object_id=trunk.mrtway_object_id)
    assert container.object_type == "MRT_CONTAINER"
    assert container.object_type != "MRT_CARRIER"
    assert container.engineering_object_id == "NUCLEAR_SHIELDED_CONTAINER"
    with pytest.raises(ValueError):
        csa.build_mrt_container(reg, container_id="CNT-BAD", facility_id="FAC-001", container_class_id="UNKNOWN_CLASS")


# ---------------------------------------------------------------------------
# 7. Multiple vestibules
# ---------------------------------------------------------------------------


def test_multiple_vestibules_zero_one_two_supported():
    reg = _fresh_registry_with_facility()
    csa.build_nuclear_engineering_objects(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id="F1")
    trunk = csa.build_mrt_trunk(reg, trunk_id="TRUNK-1", facility_id="FAC-001", length_m=50.0)
    assert len(reg.by_type("MRT_VESTIBULE")) == 0
    csa.build_mrt_vestibule(reg, vestibule_id="VEST-001", facility_id="FAC-001", radiopharmacy_object_id="RP-001", connected_mrt_segment_id=trunk.mrtway_object_id)
    assert len(reg.by_type("MRT_VESTIBULE")) == 1
    csa.build_mrt_vestibule(reg, vestibule_id="VEST-002", facility_id="FAC-001", radiopharmacy_object_id="RP-001", connected_mrt_segment_id=trunk.mrtway_object_id)
    assert len(reg.by_type("MRT_VESTIBULE")) == 2


# ---------------------------------------------------------------------------
# 8. Five-building hierarchy + floor-ID non-collision + routing
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def five_building_campus():
    return csa.build_five_building_controlled_campus()


def test_five_building_hierarchy(five_building_campus):
    reg, _ = five_building_campus
    buildings = reg.by_type("BUILDING")
    assert {b.mrtway_object_id for b in buildings} == {"BLDG-A", "BLDG-B", "BLDG-C", "BLDG-D", "BLDG-E"}
    rooms = reg.by_type("ROOM")
    assert len(rooms) == 5


def test_five_building_floor_ids_never_collide(five_building_campus):
    reg, _ = five_building_campus
    floors = reg.by_type("FLOOR")
    floor_ids = [f.mrtway_object_id for f in floors]
    assert len(floor_ids) == len(set(floor_ids)) == 5
    assert all("::" in fid for fid in floor_ids)


def test_five_building_route_a_to_b(five_building_campus):
    reg, graph = five_building_campus
    route = csa.resolve_route(graph, origin_object_id="BLDG-A", destination_object_id="BLDG-B", mode="WALKING_PORTER")
    assert route.calibration_status == "CALIBRATED"


def test_five_building_route_a_to_c(five_building_campus):
    reg, graph = five_building_campus
    route = csa.resolve_route(graph, origin_object_id="BLDG-A", destination_object_id="BLDG-C", mode="WALKING_PORTER")
    assert route.calibration_status == "CALIBRATED"
    assert route.distance_m == 200.0


def test_five_building_route_a_to_e(five_building_campus):
    reg, graph = five_building_campus
    route = csa.resolve_route(graph, origin_object_id="BLDG-A", destination_object_id="BLDG-E", mode="WALKING_PORTER")
    assert route.calibration_status == "CALIBRATED"
    assert route.distance_m == 300.0


def test_five_building_route_c_to_e(five_building_campus):
    reg, graph = five_building_campus
    route = csa.resolve_route(graph, origin_object_id="BLDG-C", destination_object_id="BLDG-E", mode="WALKING_PORTER")
    assert route.calibration_status == "CALIBRATED"


def test_route_derived_from_explicit_graph_never_euclidean_proximity(five_building_campus):
    """BLDG-C and BLDG-D are Euclidean-close (both near x=100-200) but have
    NO direct edge -- proving routes come only from explicit connectivity."""
    reg, graph = five_building_campus
    direct_edge_exists = any({e.from_object_id, e.to_object_id} == {"BLDG-C", "BLDG-D"} for e in graph.edges)
    assert direct_edge_exists is False


# ---------------------------------------------------------------------------
# 9. Multi-building MRT/Manual/AGV/PTS routing
# ---------------------------------------------------------------------------


def test_multi_building_mrt_route_no_teleportation(five_building_campus):
    reg, graph = five_building_campus
    route = csa.resolve_route(graph, origin_object_id="RP-A-001", destination_object_id="MRT-ENDPOINT-E", mode="MRT")
    assert route.calibration_status == "CALIBRATED"
    assert len(route.path_edge_ids) == 7  # every explicit hop traversed, never a shortcut
    assert route.distance_m == 410.0


def test_mrt_route_never_shares_building_to_building_edges(five_building_campus):
    reg, graph = five_building_campus
    route = csa.resolve_route(graph, origin_object_id="BLDG-A", destination_object_id="BLDG-E", mode="MRT")
    assert route.calibration_status == "ROUTE_NOT_CALIBRATED"


def test_multi_building_manual_route_uses_corridor_edges_only(five_building_campus):
    reg, graph = five_building_campus
    route = csa.resolve_route(graph, origin_object_id="BLDG-B", destination_object_id="BLDG-D", mode="WALKING_PORTER")
    assert route.calibration_status == "CALIBRATED"
    manual_edges = {e.edge_id for e in graph.edges if "WALKING_PORTER" in e.compatible_modes}
    assert set(route.path_edge_ids) <= manual_edges


def test_agv_route_never_assumes_all_pedestrian_paths_agv_compatible(five_building_campus):
    reg, graph = five_building_campus
    # B<->D corridor exists for pedestrians but NOT for AGV
    agv_route = csa.resolve_route(graph, origin_object_id="BLDG-B", destination_object_id="BLDG-D", mode="AGV_AMR")
    assert agv_route.calibration_status == "ROUTE_NOT_CALIBRATED"
    walking_route = csa.resolve_route(graph, origin_object_id="BLDG-B", destination_object_id="BLDG-D", mode="WALKING_PORTER")
    assert walking_route.calibration_status == "CALIBRATED"


def test_agv_route_works_where_agv_edges_exist(five_building_campus):
    reg, graph = five_building_campus
    route = csa.resolve_route(graph, origin_object_id="BLDG-A", destination_object_id="BLDG-C", mode="AGV_AMR")
    assert route.calibration_status == "CALIBRATED"


def test_pts_remains_its_own_network_never_shares_edges(five_building_campus):
    """Section 30: PTS has NO edges in the shared graph at all -- proving it
    never silently uses normal corridors/MRT/AGV paths."""
    reg, graph = five_building_campus
    pts_edges = [e for e in graph.edges if "PNEUMATIC_TUBE" in e.compatible_modes]
    assert pts_edges == []
    route = csa.resolve_route(graph, origin_object_id="BLDG-A", destination_object_id="BLDG-B", mode="PNEUMATIC_TUBE")
    assert route.calibration_status == "ROUTE_NOT_CALIBRATED"


def test_mode_incompatibility_never_silently_routes_wrong_mode(five_building_campus):
    reg, graph = five_building_campus
    route = csa.resolve_route(graph, origin_object_id="BLDG-D", destination_object_id="BLDG-E", mode="AGV_AMR")
    assert route.calibration_status == "CALIBRATED"  # D<->E IS AGV-capable
    route2 = csa.resolve_route(graph, origin_object_id="BLDG-B", destination_object_id="BLDG-D", mode="MRT")
    assert route2.calibration_status == "ROUTE_NOT_CALIBRATED"  # no MRT edge between B and D directly


# ---------------------------------------------------------------------------
# 10. Production-source location generality + multiple sources
# ---------------------------------------------------------------------------


def test_production_source_in_arbitrary_building_not_special_cased():
    reg = csa.build_facility_hierarchy(facility_id="FAC-001")
    for b in ("BLDG-A", "BLDG-B", "BLDG-C", "BLDG-D"):
        csa.add_building(reg, facility_id="FAC-001", building_id=b)
        csa.add_floor(reg, facility_id="FAC-001", building_id=b, floor_id="F1")
    objs = csa.build_nuclear_engineering_objects(
        reg, facility_id="FAC-001", building_id="BLDG-C", floor_id="F1",
        cyclotron_id="CY-001", pet_scanner_id="SCN-PET-C-001", radiopharmacy_id="RP-C-001",
    )
    cyclotron = next(o for o in objs if o.object_type == "CYCLOTRON")
    assert cyclotron.building_id == "BLDG-C"  # never forced to "Building A"


def test_multiple_cyclotrons_and_generators_in_one_campus():
    reg = csa.build_facility_hierarchy(facility_id="FAC-001")
    for b in ("BLDG-A", "BLDG-B", "BLDG-C", "BLDG-D"):
        csa.add_building(reg, facility_id="FAC-001", building_id=b)
        csa.add_floor(reg, facility_id="FAC-001", building_id=b, floor_id="F1")
    csa.build_nuclear_engineering_objects(
        reg, facility_id="FAC-001", building_id="BLDG-C", floor_id="F1",
        cyclotron_id="CY-001", pet_scanner_id="SCN-PET-C-001", radiopharmacy_id="RP-D-001",
    )
    csa.build_nuclear_engineering_objects(
        reg, facility_id="FAC-001", building_id="BLDG-B", floor_id="F1",
        cyclotron_id="CY-002", generator_id="GEN-001", pet_scanner_id="SCN-PET-B-001", radiopharmacy_id="RP-B-001",
    )
    cyclotrons = reg.by_type("CYCLOTRON")
    generators = reg.by_type("MO99_TC99M_GENERATOR")
    assert {c.mrtway_object_id for c in cyclotrons} == {"CY-001", "CY-002"}
    assert {g.building_id for g in generators} == {"BLDG-B"}
    assert len(generators) == 1


# ---------------------------------------------------------------------------
# 11. Hybrid spatial coverage + Retrofit/Greenfield N-building
# ---------------------------------------------------------------------------


def test_hybrid_spatial_coverage_across_five_buildings(five_building_campus):
    coverage = csa.build_hybrid_spatial_coverage_map({
        "BLDG-A": "CONVENTIONAL", "BLDG-B": "MRT", "BLDG-C": "MRT", "BLDG-D": "CONVENTIONAL", "BLDG-E": "MRT",
    })
    assert coverage.coverage_for("BLDG-A") == "CONVENTIONAL"
    assert coverage.coverage_for("BLDG-B") == "MRT"
    assert coverage.coverage_for("BLDG-E") == "MRT"
    assert coverage.coverage_for("BLDG-NOT-PRESENT") is None


def test_hybrid_coverage_floor_level_variation_no_schema_change():
    coverage = csa.build_hybrid_spatial_coverage_map({"BLDG-B::F1": "MRT", "BLDG-B::F2": "CONVENTIONAL"})
    assert coverage.coverage_for("BLDG-B::F1") == "MRT"
    assert coverage.coverage_for("BLDG-B::F2") == "CONVENTIONAL"


def test_retrofit_n_building_preserves_identity_and_count(five_building_campus):
    reg, _ = five_building_campus
    retrofit_reg = csa.tag_asset_status_for_development_context(reg, development_context="RETROFIT", proposed_object_ids=frozenset({"BLDG-E"}))
    assert set(retrofit_reg.objects.keys()) == set(reg.objects.keys())
    assert retrofit_reg.objects["BLDG-E"].asset_status == "PROPOSED"
    assert retrofit_reg.objects["BLDG-A"].asset_status == "EXISTING"
    # original registry never mutated -- both buildings remain EXISTING (their original builder default)
    assert reg.objects["BLDG-E"].asset_status == "EXISTING"
    assert reg.objects["BLDG-A"].asset_status == "EXISTING"


def test_greenfield_n_building_all_proposed_preserves_identity(five_building_campus):
    reg, _ = five_building_campus
    greenfield_reg = csa.tag_asset_status_for_development_context(reg, development_context="GREENFIELD")
    assert set(greenfield_reg.objects.keys()) == set(reg.objects.keys())
    assert all(o.asset_status == "PROPOSED" for o in greenfield_reg.objects.values())


# ---------------------------------------------------------------------------
# 12. Canonical patient spatial consumption (PET/SPECT inpatient/outpatient)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def baseline():
    return build_common_project_baseline()


@pytest.fixture(scope="module")
def populated_registry(baseline):
    reg = csa.build_facility_hierarchy(facility_id="FAC-001")
    csa.add_building(reg, facility_id="FAC-001", building_id="BLDG-A")
    for i in range(1, 7):
        csa.add_floor(reg, facility_id="FAC-001", building_id="BLDG-A", floor_id=f"F{i}")
    for p in baseline.patients:
        if p.patient_type == "INPATIENT" and p.room_id is not None and p.room_id not in reg.objects:
            csa.add_room(reg, facility_id="FAC-001", building_id=p.building_id, floor_id=p.floor_id, room_id=p.room_id)
    return reg


def test_canonical_inpatient_pet_spatial_consumption(baseline, populated_registry):
    inpatient_pet = next(p for p in baseline.patients if p.patient_type == "INPATIENT" and p.nuclear_procedure is not None and p.nuclear_procedure.modality == "PET")
    resolution = csa.resolve_patient_spatial_object(inpatient_pet, populated_registry)
    assert resolution.resolved_object_id == inpatient_pet.room_id
    assert resolution.spatial_status == "CALIBRATED"


def test_canonical_inpatient_spect_spatial_resolution_not_forced_through_pet(baseline, populated_registry):
    inpatient_spect = next((p for p in baseline.patients if p.patient_type == "INPATIENT" and p.nuclear_procedure is not None and p.nuclear_procedure.modality == "SPECT"), None)
    assert inpatient_spect is not None, "expected at least one inpatient SPECT patient in the baseline"
    resolution = csa.resolve_patient_spatial_object(inpatient_spect, populated_registry)
    assert resolution.resolved_object_id == inpatient_spect.room_id
    assert resolution.spatial_status == "CALIBRATED"


def test_outpatient_pet_no_fabricated_inpatient_room(baseline, populated_registry):
    outpatient_pet = next(p for p in baseline.patients if p.patient_type == "OUTPATIENT" and p.nuclear_procedure is not None and p.nuclear_procedure.modality == "PET")
    resolution = csa.resolve_patient_spatial_object(outpatient_pet, populated_registry)
    assert resolution.resolved_object_id is None
    assert resolution.spatial_status == "LOCATION_NOT_CALIBRATED"
    assert resolution.resolved_object_id not in {p.room_id for p in baseline.patients if p.patient_type == "INPATIENT"}


def test_outpatient_spect_no_fabricated_room(baseline, populated_registry):
    outpatient_spect = next((p for p in baseline.patients if p.patient_type == "OUTPATIENT" and p.nuclear_procedure is not None and p.nuclear_procedure.modality == "SPECT"), None)
    assert outpatient_spect is not None
    resolution = csa.resolve_patient_spatial_object(outpatient_spect, populated_registry)
    assert resolution.resolved_object_id is None
    assert resolution.spatial_status == "LOCATION_NOT_CALIBRATED"


def test_canonical_patient_spatial_consumption_at_composition_boundary(baseline, populated_registry):
    nuclear = _nuclear_result(baseline, mrt_floors=frozenset({1, 2, 3, 4}))
    results = resolve_hybrid_nuclear_spatial_context(baseline, nuclear, populated_registry)
    assert len(results) > 0
    assert all(r.resync_status == "RESYNCED_TO_CANONICAL_LOCATION" for r in results)
    # read-only: the trace objects themselves are unaffected
    assert all(hasattr(t, "destination_room_id") for t in nuclear.patient_traces)


def test_route_feeds_existing_transport_physics_interface(five_building_campus):
    """Section 46: calibrated route distance/time is consumable by existing
    transport authorities -- never a second decay/transport engine. Here we
    just confirm the route result exposes the numeric distance existing
    authorities (e.g. hybrid_optimization's mrt speed-based timing) can consume."""
    reg, graph = five_building_campus
    route = csa.resolve_route(graph, origin_object_id="RP-A-001", destination_object_id="MRT-ENDPOINT-E", mode="MRT")
    assert isinstance(route.distance_m, float)
    from models import PlannerAssumptions
    a = PlannerAssumptions()
    travel_seconds = route.distance_m / a.mrt_horizontal_speed_m_per_s
    assert travel_seconds > 0


# ---------------------------------------------------------------------------
# 13. Input normalization contracts (all 7 modes, common result)
# ---------------------------------------------------------------------------


def _blank_registry():
    return csa.build_facility_hierarchy(facility_id="FAC-IMPORT")


def test_all_seven_input_normalization_contracts_return_common_type():
    reg = _blank_registry()
    results = [
        csa.normalize_blank_manual_import(reg),
        csa.normalize_template_import(reg, template_id="TPL-1"),
        csa.normalize_ifc_bim_import(reg, source_version="IFC4"),
        csa.normalize_cad_import(reg, source_layer="A-WALL"),
        csa.normalize_pdf_image_import(reg, source_document_id="DOC-1"),
        csa.normalize_api_import(reg, source_system="SRC-1", source_timestamp="2026-01-01T00:00:00Z"),
        csa.normalize_intelligent_reconstruction_import(reg, source_evidence="photo"),
    ]
    assert len(results) == 7
    assert all(isinstance(r, csa.NormalizedImportResult) for r in results)
    modes = {r.import_mode for r in results}
    assert modes == {"BLANK_MANUAL", "ASSISTED_TEMPLATE", "IFC_BIM", "CAD", "PDF_IMAGE", "API", "INTELLIGENT_RECONSTRUCTION"}


def test_common_normalized_result_carries_registry_provenance_confidence_validation():
    reg = _blank_registry()
    result = csa.normalize_ifc_bim_import(reg, source_version="IFC4X3")
    assert result.registry is reg
    assert result.provenance == "IMPORTED_IFC"
    assert result.confidence in ("high", "medium", "low", "unknown")
    assert isinstance(result.validation_issues, tuple)


def test_template_identity_never_becomes_permanent_engineering_identity():
    reg = _blank_registry()
    result = csa.normalize_template_import(reg, template_id="TPL-XYZ")
    assert "TPL-XYZ" not in reg.objects
    assert result.source_metadata["template_id"] == "TPL-XYZ"


def test_intelligent_reconstruction_never_represented_as_measured_geometry():
    reg = _blank_registry()
    result = csa.normalize_intelligent_reconstruction_import(reg, source_evidence="floor plan photo")
    assert result.provenance == "RECONSTRUCTED"
    assert result.confidence == "low"


# ---------------------------------------------------------------------------
# 14. Locked/what-if non-regression
# ---------------------------------------------------------------------------


def test_locked_state_immutability_non_regression(five_building_campus):
    reg, _ = five_building_campus
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    moved = dataclasses.replace(what_if.registry.get("BLDG-C"), transform=csa.Transform(position_x=999.0))
    csa.apply_changeset(what_if, change_id="C1", operation="MOVE_OBJECT", object_id="BLDG-C", new_object=moved)
    assert locked.registry.get("BLDG-C").transform.position_x == 200.0


def test_reset_to_locked_non_regression(five_building_campus):
    reg, _ = five_building_campus
    locked = csa.LockedSpatialState(registry=reg)
    what_if = csa.WhatIfSpatialState.branch_from(locked)
    moved = dataclasses.replace(what_if.registry.get("BLDG-C"), transform=csa.Transform(position_x=999.0, rotation_z=45.0))
    csa.apply_changeset(what_if, change_id="C1", operation="MOVE_OBJECT", object_id="BLDG-C", new_object=moved)
    what_if.reset_to_locked()
    assert what_if.registry.get("BLDG-C").transform.position_x == 200.0
    assert what_if.registry.get("BLDG-C").transform.rotation_z == 0.0


def test_undo_non_regression(five_building_campus):
    reg, _ = five_building_campus
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    original = what_if.registry.get("BLDG-D")
    moved = dataclasses.replace(original, transform=csa.Transform(position_x=1.0))
    csa.apply_changeset(what_if, change_id="C1", operation="MOVE_OBJECT", object_id="BLDG-D", new_object=moved)
    what_if.undo_last_change()
    assert what_if.registry.get("BLDG-D") == original


def test_promotion_explicit_non_regression(five_building_campus):
    reg, _ = five_building_campus
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    moved = dataclasses.replace(what_if.registry.get("BLDG-D"), transform=csa.Transform(position_x=1.0))
    csa.apply_changeset(what_if, change_id="C1", operation="MOVE_OBJECT", object_id="BLDG-D", new_object=moved)
    assert what_if.promoted is False
    csa.promote_what_if_to_simulation_input(what_if)
    assert what_if.promoted is True


# ---------------------------------------------------------------------------
# 15. Camera vs engineering rotation
# ---------------------------------------------------------------------------


def test_camera_rotation_economics_neutral():
    impact = csa.apply_camera_rotation(yaw_degrees=180.0, pitch_degrees=45.0)
    assert impact.delta_capex == 0.0
    assert impact.delta_opex == 0.0
    assert impact.delta_route_geometry_m == 0.0
    assert impact.delta_engineering_transform is False


def test_engineering_rotation_distinct_from_camera_rotation(five_building_campus):
    reg, _ = five_building_campus
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    changeset, impact = csa.apply_engineering_rotation(what_if, object_id="BLDG-C", new_rotation=csa.Transform(rotation_z=90.0), change_id="ROT-1")
    assert impact.rotation_kind == "ENGINEERING_OBJECT_ROTATION"
    assert impact.delta_engineering_transform is True
    assert what_if.registry.get("BLDG-C").transform.rotation_z == 90.0


# ---------------------------------------------------------------------------
# 16. Connectivity-aware transforms
# ---------------------------------------------------------------------------


def test_connection_impact_identifies_all_affected_edges(five_building_campus):
    reg, graph = five_building_campus
    impacts = csa.find_affected_connections(graph, "BLDG-B")
    assert len(impacts) >= 3  # B connects to A, C, D at minimum
    connected_others = {i.to_object_id if i.from_object_id == "BLDG-B" else i.from_object_id for i in impacts}
    assert {"BLDG-A", "BLDG-C", "BLDG-D"} <= connected_others


def test_preserve_connection_records_delta(five_building_campus):
    reg, graph = five_building_campus
    result = csa.resolve_connection_preserve(graph, connection_id="CORRIDOR-01", new_length_m=150.0)
    assert result.resolution == "PRESERVE_CONNECTION"
    assert result.delta_length_m == 50.0
    assert result.resulting_status == "CONNECTED"


def test_disconnect_reports_honest_status_no_alternate_route_invented(five_building_campus):
    reg, graph = five_building_campus
    disconnect_edges = [e.edge_id for e in graph.edges if {e.from_object_id, e.to_object_id} == {"BLDG-D", "BLDG-E"} and "WALKING_PORTER" in e.compatible_modes]
    assert disconnect_edges
    result = csa.resolve_connection_disconnect(graph, connection_id=disconnect_edges[0])
    assert result.resulting_status == "DISCONNECTED"
    route = csa.resolve_route(graph, origin_object_id="BLDG-D", destination_object_id="BLDG-E", mode="WALKING_PORTER")
    assert route.calibration_status == "ROUTE_NOT_CALIBRATED"


def test_move_connected_assembly_preserves_internal_geometry():
    reg, graph = csa.build_five_building_controlled_campus()
    group = csa.group_objects(group_id="GRP-DE", member_object_ids=("BLDG-D", "BLDG-E"))
    what_if = csa.WhatIfSpatialState.branch_from(csa.LockedSpatialState(registry=reg))
    d_before = what_if.registry.get("BLDG-D").transform.position_y
    e_before = what_if.registry.get("BLDG-E").transform.position_y
    csa.move_connected_assembly(what_if, group=group, delta=csa.Transform(position_y=25.0), change_id_prefix="MOVE")
    d_after = what_if.registry.get("BLDG-D").transform.position_y
    e_after = what_if.registry.get("BLDG-E").transform.position_y
    assert d_after - d_before == pytest.approx(25.0)
    assert e_after - e_before == pytest.approx(25.0)
    assert (e_after - d_after) == pytest.approx(e_before - d_before)  # relative geometry preserved


def test_sub_campus_transform_identifies_boundary_connections():
    reg, graph = csa.build_five_building_controlled_campus()
    group = csa.group_objects(group_id="GRP-CDE", member_object_ids=("BLDG-C", "BLDG-D", "BLDG-E"))
    boundary = csa.find_boundary_connections(graph, group)
    boundary_pairs = {frozenset({i.from_object_id, i.to_object_id}) for i in boundary}
    assert frozenset({"BLDG-B", "BLDG-C"}) in boundary_pairs or any("BLDG-B" in p for p in boundary_pairs)
    assert frozenset({"BLDG-C", "BLDG-D"}) not in boundary_pairs  # internal to the group, excluded


def test_selection_set_identity_and_scope():
    reg, _ = csa.build_five_building_controlled_campus()
    selection = csa.box_select(reg, selection_id="SEL-1", object_ids=("BLDG-A", "BLDG-B"))
    assert selection.selection_scope == "MULTI_OBJECT"
    assert selection.selected_object_ids == ("BLDG-A", "BLDG-B")
    with pytest.raises(ValueError):
        csa.box_select(reg, selection_id="SEL-BAD", object_ids=("DOES-NOT-EXIST",))


def test_group_retains_object_ids_ungroup_returns_same_members():
    group = csa.group_objects(group_id="GRP-1", member_object_ids=("BLDG-A", "BLDG-B"))
    members = csa.ungroup(group)
    assert members == ("BLDG-A", "BLDG-B")


def test_bounding_volume_contract_coarse_estimate():
    reg, _ = csa.build_five_building_controlled_campus()
    bv = csa.compute_bounding_volume(reg, ["BLDG-A", "BLDG-B", "BLDG-C", "BLDG-D", "BLDG-E"])
    assert bv.calibration_status == "COARSE_ESTIMATE"
    assert bv.max_x >= bv.min_x
    assert bv.max_y >= bv.min_y


def test_bounding_volume_empty_selection_not_calibrated():
    bv = csa.compute_bounding_volume(csa.build_facility_hierarchy(), [])
    assert bv.calibration_status == "NOT_CALIBRATED"


# ---------------------------------------------------------------------------
# 17. Spatial economic deltas
# ---------------------------------------------------------------------------


def test_segment_length_economic_delta_only_affects_guideway():
    delta = csa.compute_segment_length_capex_delta(locked_length_m=100.0, what_if_length_m=150.0)
    from models import PlannerAssumptions
    a = PlannerAssumptions()
    assert delta == pytest.approx(50.0 * a.mrt_guideway_capex_per_m)


def test_segment_length_delta_never_recharges_controls_or_installation():
    # the function signature has no controls/installation parameter at all --
    # structurally impossible to recharge them here.
    import inspect
    sig = inspect.signature(csa.compute_segment_length_capex_delta)
    assert "include_controls" not in sig.parameters
    assert "include_installation_commissioning" not in sig.parameters


def test_vestibule_count_delta_adds_exactly_30k_per_vestibule():
    delta = csa.compute_vestibule_count_capex_delta(locked_count=1, what_if_count=2)
    assert delta == pytest.approx(30_000.0)


def test_vestibule_count_delta_never_recharges_controls_or_installation():
    import inspect
    sig = inspect.signature(csa.compute_vestibule_count_capex_delta)
    assert "include_controls" not in sig.parameters
    assert "include_installation_commissioning" not in sig.parameters


# ---------------------------------------------------------------------------
# 18. Serialization + validation + component non-regression
# ---------------------------------------------------------------------------


def test_serialization_of_simple_new_dataclasses():
    audit_entry = csa.audit_mrt_economic_authority()[0]
    d = dataclasses.asdict(audit_entry)
    assert d["component"] == audit_entry.component

    line_item = csa.compute_mrt_transport_only_capex(guideway_length_m=10.0).line_items[0]
    d2 = dataclasses.asdict(line_item)
    assert d2["component"] == line_item.component

    selection = csa.build_selection_set(selection_id="SEL-X", selected_object_ids=("A", "B"), selection_scope="MULTI_OBJECT")
    d3 = dataclasses.asdict(selection)
    assert d3["selection_id"] == "SEL-X"


def test_serialization_registry_round_trip_still_works(five_building_campus):
    reg, _ = five_building_campus
    payload = csa.registry_to_json(reg)
    restored = csa.registry_from_json(payload)
    assert set(restored.objects.keys()) == set(reg.objects.keys())


def test_validation_extension_orphan_mrt_branch():
    reg = csa.build_facility_hierarchy(facility_id="FAC-001")
    trunk = csa.build_mrt_trunk(reg, trunk_id="TRUNK-1", facility_id="FAC-001", length_m=10.0)
    branch = csa.build_mrt_branch(reg, branch_id="BRANCH-1", facility_id="FAC-001", connects_to_object_id=trunk.mrtway_object_id, length_m=10.0)
    # force an orphan by bypassing the builder's validation via direct registry mutation
    reg.objects["BRANCH-1"] = dataclasses.replace(branch, parent_object_id="GONE")
    issues = csa.validate_spatial_registry(reg)
    assert any(i.issue_type == "ORPHAN_MRT_BRANCH" for i in issues)


def test_validation_extension_carrier_and_container_reference_checks():
    reg = csa.build_facility_hierarchy(facility_id="FAC-001")
    trunk = csa.build_mrt_trunk(reg, trunk_id="TRUNK-1", facility_id="FAC-001", length_m=10.0)
    carrier = csa.build_mrt_carrier(reg, carrier_id="CARRIER-1", facility_id="FAC-001", network_object_id=trunk.mrtway_object_id)
    reg.objects["CARRIER-1"] = dataclasses.replace(carrier, parent_object_id="GONE")
    issues = csa.validate_spatial_registry(reg)
    assert any(i.issue_type == "CARRIER_INVALID_NETWORK_REFERENCE" for i in issues)


def test_validation_extension_junction_and_endpoint_without_connection(five_building_campus):
    reg, graph = five_building_campus
    orphan_junction = csa.build_mrt_junction(reg, junction_id="JCT-ORPHAN", facility_id="FAC-CAMPUS5")
    issues = csa.validate_spatial_registry(reg, graph=graph)
    assert any(i.issue_type == "JUNCTION_WITHOUT_CONNECTED_EDGES" and i.object_id == "JCT-ORPHAN" for i in issues)


def test_validation_extension_broken_five_building_graph_connection(five_building_campus):
    reg, graph = five_building_campus
    graph.add_edge(csa.SpatialEdge(edge_id="BAD-EDGE", from_object_id="BLDG-A", to_object_id="GHOST-OBJECT", length_m=1.0, compatible_modes=frozenset({"MRT"})))
    issues = csa.validate_spatial_registry(reg, graph=graph)
    assert any(i.issue_type == "BROKEN_GRAPH_CONNECTION" for i in issues)
    graph.edges.pop()  # clean up for other tests sharing the module-scoped fixture


def test_component_non_regression_hybrid_patient_trace_unaffected(baseline):
    nuclear = _nuclear_result(baseline, mrt_floors=frozenset({1, 2, 3, 4}))
    assert all(hasattr(t, "canonical_patient_id") for t in nuclear.patient_traces)
    assert all(hasattr(t, "destination_room_id") for t in nuclear.patient_traces)


def test_component_non_regression_general_oncology_logistics_roles_unchanged():
    from general_oncology_logistics import build_default_facility_roles
    roles = build_default_facility_roles()
    assert {"CENTRAL_PHARMACY", "LABORATORY", "BLOOD_BANK", "CLEAN_LINEN_SOURCE", "STERILE_CLEAN_SUPPLY"} <= {r.role for r in roles}


def test_component_non_regression_shared_mrt_container_classes_unchanged():
    from shared_mrt_multistream_authority import DEFAULT_NUCLEAR_SHIELDED_CONTAINER, DEFAULT_LINEN_CONTAINER
    assert DEFAULT_NUCLEAR_SHIELDED_CONTAINER.container_class_id == "NUCLEAR_SHIELDED_CONTAINER"
    assert DEFAULT_LINEN_CONTAINER.container_class_id == "LINEN_CONTAINER"
