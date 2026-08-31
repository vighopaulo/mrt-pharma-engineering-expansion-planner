# BENTLEY LIVE iMODEL INSPECTION & MRT PHARMA BINDING — REPORT

First real Bentley → MRT Pharma digital-twin integration seam. Bentley owns
BIM/spatial/geometry/element-identity/visualization; MRT Pharma owns
engineering/clinical/nuclear/logistics/capacity/optimization/CapEx/OPEX/
project-inheritance. This build establishes the binding authority + the
3D-change → 2D-consequence CONTRACT, composing Super-Build 3. Live Bentley
access is READ-ONLY. No secret is exposed. Integration files are left
uncommitted; only the narrow `.gitignore` security commit was pushed.

Machine-readable data: `bentley_live_imodel_binding_data.json`.

## TABLE 1 — Repository / Security State

| Field | Value |
|---|---|
| Security commit | `570d3b1` "MRT Pharma: protect local Bentley credentials" (pushed) |
| .gitignore addition | `.env.bentley` (narrow; no broad `.env*`/`*.env`) |
| .env.bentley | present, ignored (line 11), untracked, uncommitted |
| SECRET_EXPOSED_IN_OUTPUT | NO |
| BENTLEY_ENV_FILE_COMMITTED | NO |
| Integration files | uncommitted (additive; 0 tracked source files modified) |
| AS_IS artifact | untracked (excluded) |

## TABLE 2 — Bentley Authority Trace

| Concept | Owner | Classification |
|---|---|---|
| Bentley auth / HTTP | `bentley_itwin_client` (token provider + injectable transport) | REUSE |
| iTwin/iModel binding metadata | `bentley_itwin_client` (get_itwin/imodel_metadata, list_imodels) | REUSE |
| single-element canonical bind | `bentley_canonical_binding.bind_live_bentley_element` | REUSE |
| ExternalReference / spatial object | `canonical_spatial_authority` | REUSE |
| Bentley→MRT binding record + statuses | (none unified) | GENUINE_GAP → NEW `bentley_mrt_binding_authority.py` |
| geometry-change (3D→2D) contract | (none) | GENUINE_GAP → NEW `geometry_change_contract.py` |
| economic classification | `capital_project_inheritance_authority` (Super-Build 3) | REUSE |
| viewer client | frontend placeholder viewport | NOT_IMPLEMENTED |

## TABLE 3 — Live Connection Proof

| Step | Result |
|---|---|
| TOKEN_ACQUIRED | YES (length only; value never shown) |
| ITWIN_DETAILS_SUCCESS | YES |
| LIST_IMODELS_SUCCESS | YES |
| IMODEL_COUNT | 1 (≥1) |
| IMODEL_DETAILS_SUCCESS | YES |
| RETURNED_ITWIN_ID_MATCHES_EXPECTED | YES |
| CHANGESET_ACCESS_SUCCESS | YES |

## TABLE 4 — iTwin Identity

| Field | Value |
|---|---|
| Name | MRTway Development Twin. |
| iTwin ID | bdf29ecd-b4a4-404d-861a-ac3061c7b12f |
| Status | Active |

## TABLE 5 — iModel Identity

| Field | Value |
|---|---|
| Name | MRTway Hospital Campus Development. |
| iModel ID (discovered dynamically) | ea9c0558-45a3-40b8-91a9-f4075b826925 |
| State | initialized |
| Data center | East US |

## TABLE 6 — Changeset / Version

| Field | Value |
|---|---|
| Changeset count | 13 |
| Latest changeset | 7e6500eeecf2507c486beb14a763f4056342775c |

## TABLE 7 — Model Inventory (live, honest)

| Item | Live finding | Classification |
|---|---|---|
| Changesets | 13 | PROVEN_LIVE |
| Mesh exports (geometry tiles) | 2, status Complete | PROVEN_LIVE (geometry exists / viewer-renderable) |
| Named versions | present (HTTP 200) | PROVEN_LIVE |
| REST `/elements` model/element listing | HTTP 404 | NOT_QUERYABLE_WITH_CURRENT_READ_PATH |
| Model/element counts via REST | unavailable on this path | NOT_QUERYABLE_WITH_CURRENT_READ_PATH |

The iModels-v2 REST API on this account does not expose an `/elements`
collection; per-element inventory requires an iTwin.js briefcase/ECSQL backend
not present in the thin client. Reported honestly, not fabricated.

## TABLE 8 — Element Inventory

| Category | Result |
|---|---|
| building / floor / space / wall / door / equipment / MEP / electrical / elevator / site | NOT_QUERYABLE_WITH_CURRENT_READ_PATH (REST `/elements` 404) |

Geometry exists as completed mesh exports, but per-element EC enumeration is not
available through the current read path. No elements were invented.

## TABLE 9 — Representative EC Classes

| Result |
|---|
| NOT_QUERYABLE_WITH_CURRENT_READ_PATH — EC class enumeration needs ECSQL/briefcase; not present in test read path |

## TABLE 10 — Stable Identity Fields

| Field | Role |
|---|---|
| element_id | primary stable identity |
| federation_guid | fallback identity |
| model_id | fallback identity |
| changeset_id | source version |
| class_name | binding-eligibility gate |
| itwin_id / imodel_id | scope identity |
| label | display only — NEVER identity (DISPLAY_LABEL_USED_AS_PRIMARY_IDENTITY = NO) |

## TABLE 11 — Representative Properties

| Source (Bentley) | MRT Pharma derived (separate) |
|---|---|
| element id / class / model / placement / dimensions / equipment tag / room association | transport eligibility / economic classification / clinical role / capacity contribution / project action / incremental CapEx |

SOURCE_AND_DERIVED_PROPERTIES_CONFLATED = NO. Live property retrieval:
NOT_QUERYABLE_WITH_CURRENT_READ_PATH for this iModel.

## TABLE 12 — Spatial Fields

| Field | Live availability |
|---|---|
| XYZ origin / placement / rotation / bounding range / extents / elevation / floor assoc / geolocation / coordinate system | NOT_QUERYABLE_WITH_CURRENT_READ_PATH (REST) / DERIVABLE from mesh-export tiles in a future iTwin.js reader |

No precise geometry inferred from labels or class names.

## TABLE 13 — Coordinate / Extents Status

| Field | Status |
|---|---|
| model extents / coordinate system | NOT_QUERYABLE via current REST path; geometry present in mesh export |

## TABLE 14 — Binding Schema

`BentleyExternalReference(itwin_id, imodel_id, changeset_id, model_id, element_id, class_name, federation_guid, label, source_platform=BENTLEY_ITWIN, source_provenance)` + `BentleyBinding(external_reference, mrt_object_id, mrt_object_type, binding_status, bound_at_changeset_id, asset_classification, detail)`.

## TABLE 15 — Binding Status

BOUND / UNBOUND / IGNORED / AMBIGUOUS / UNSUPPORTED_CLASS / MISSING_REQUIRED_PROPERTY / STALE_SOURCE_VERSION / SOURCE_ELEMENT_MISSING. No silent binding (unsupported class, missing identity, and no-MRT-object all produce explicit non-BOUND statuses).

## TABLE 16 — Live Binding Proof

| Field | Value |
|---|---|
| Classification | SUPPORTED_BUT_NOT_PRESENT_IN_TEST_IMODEL (REST element endpoint 404) |
| Deterministic binding from real iTwin/iModel/changeset ids | PASS (status BOUND, bound_at_changeset 7e6500ee…, economic_state RETAINED_NO_CHANGE, implies_new_capex False) |

The binding code path is proven with real Bentley identity; per-element binding awaits an element-queryable read path.

## TABLE 17 — Existing-vs-New Economic Composition (Super-Build 3)

| Bentley bound object economic state | New CapEx? |
|---|---|
| RETAINED_NO_CHANGE / INHERITED_EXISTING | NO |
| MODIFY | NO (only modification work) |
| REPLACE | YES (replacement, displaces old) |
| NEW | YES |
| REMOVE / OUT_OF_SCOPE | NO |

BENTLEY_OBJECT_PRESENT_IMPLIES_NEW_CAPEX = NO (verified across all states).

## TABLE 18 — Viewer Readiness

| Field | Value |
|---|---|
| VIEWER_CLIENT_PRESENT | NO (placeholder viewport only) |
| VIEWER_AUTH_FLOW | NOT_IMPLEMENTED |
| VIEWER_ITWIN/IMODEL_BINDING | NO / NO |
| VIEWER_MODEL_LOAD / SELECTION / PROPERTY_PANEL / CLIPPING | NO |
| VIEWER_READY_STATUS | NOT_READY (needs separate browser-auth viewer build) |

## TABLE 19 — Service-vs-Viewer Security

| Field | Value |
|---|---|
| SERVICE_SECRET_EXPOSED_TO_FRONTEND | NO |
| SERVICE_SECRET_PRESENT_IN_BUNDLE | NO |
| ENV_BENTLEY_IMPORTED_BY_FRONTEND | NO |
| SERVICE_CLIENT_REUSED_AS_BROWSER_SECRET_CLIENT | NO |
| frontend/.env contents | VITE_API_BASE_URL only (no secret) |

## TABLE 20 — Geometry Event Schema

`GeometryTransformEvent(scenario_id, mrt_object_id, transform_type, [source identity: itwin/imodel/changeset/element], absolute old+new state fields, version)`. Absolute old AND new state preserved (Sec 40).

## TABLE 21 — Supported Transform Classes

TRANSLATE, ROTATE, CHANGE_ELEVATION, CHANGE_BUILDING_SEPARATION, CHANGE_FLOOR_COUNT, CHANGE_FLOOR_HEIGHT, RESIZE_FOOTPRINT, RELOCATE_ROOM, RELOCATE_EQUIPMENT.

## TABLE 22 — 100→500 m Control

OLD_SEPARATION = 100 m, NEW_SEPARATION = 500 m, DELTA = +400 m. Absolute old+new preserved. PASS.

## TABLE 23 — 500→100 m Control

OLD = 500 m, NEW = 100 m, DELTA = −400 m. Reversible. PASS.

## TABLE 24 — 4→8 Floor Control

old_floor_count 4, new 8, delta +4. Composes Super-Build 3: existing 4 inherited ($0), 4 new charged (capacity-delta $12M at $3M/floor, not $24M). PASS.

## TABLE 25 — 8→12 Floor Control

old 8, new 12, delta +4. Absolute state preserved. PASS.

## TABLE 26 — No-Drift Control

100→500→100 returns final absolute exactly 100.0; ROUND_TRIP_GEOMETRY_DRIFT_PRESENT = NO. A 5-step sequence (100→500→250→900→100) also returns 100.0 (absolute state, never accumulated deltas). PASS.

## TABLE 27 — Building-Separation Consumer Trace

| Consequence | Authority | Readiness |
|---|---|---|
| Manual route distance | conventional_transport_authority | ADAPTER_AVAILABLE |
| PTS tube/network length | conventional_transport_authority | ADAPTER_AVAILABLE |
| RTHS track length | conventional_transport_authority RGHT | ADAPTER_AVAILABLE |
| AGV route distance | floor_agv_amr_authority | ADAPTER_AVAILABLE |
| MRT guideway length | mrt_canonical_configuration (READ-ONLY) | ADAPTER_AVAILABLE |
| Patient travel | spatial_benchmark | NOT_YET_INTEGRATED |
| Connection work CapEx | capital_project_inheritance_authority | ADAPTER_AVAILABLE |
| Incremental transport CapEx | generalized_transport_optimizer + inheritance | ADAPTER_AVAILABLE |
| Transport OPEX/energy | per-mode OPEX authorities | ADAPTER_AVAILABLE |
| Clinical timing | operating_day_scheduler | NOT_YET_INTEGRATED |
| Radionuclide decay | multi_isotope_decay | NOT_YET_INTEGRATED |

None falsely claimed RUNTIME_CONSUMED_NOW.

## TABLE 28 — Floor-Count Consumer Trace

13 consequence paths classified (floor geometry, vertical travel, elevator, beds/rooms, HVAC, electrical, structure, shielding, transport vertical segments, scanner demand, throughput, CapEx, OPEX) — each ADAPTER_AVAILABLE / NOT_YET_INTEGRATED / NOT_CALIBRATED (shielding). See data JSON `floor_count_consumers`.

## TABLE 29 — 2D Analytics Result Schema

`AnalyticalResult(scenario_id, baseline_scenario_id, geometry_change_id, version, changed_object_ids, metrics[], warnings, provenance)`; each `AnalyticalMetric(name, category, target_value, delta_vs_baseline, unit, status)`. Machine-readable; presentation is never the engineering authority.

## TABLE 30 — Absolute-vs-Delta Result Fields

Every metric carries BOTH target_value (absolute) and delta_vs_baseline (Sec 46). Example: building_separation target 500 m, delta +400 m.

## TABLE 31 — Unknown / Not-Calibrated Handling

Downstream engineering/economic metrics (incremental_transport_capex, target_opex, incremental_opex, patient_throughput, mrt_guideway_length) are emitted NOT_YET_INTEGRATED with `target_value=None` — never zero-filled. UNKNOWN_GEOMETRY_CONSEQUENCE_ZERO_FILLED = NO.

## TABLE 32 — Live-Mutation Status

LIVE_BENTLEY_GEOMETRY_MUTATION_IMPLEMENTED = NO. All live Bentley operations were READ-ONLY. The geometry contract describes PROPOSED local changes; no write-back to Bentley exists (verified: contract/binding modules import no HTTP transport and define no post/put/delete).

## TABLE 33 — Offline / Live Test Separation

| Field | Value |
|---|---|
| Offline deterministic tests | 68 (require no Bentley network/creds) |
| OFFLINE_TESTS_REQUIRE_BENTLEY_CREDENTIALS | NO |
| Live proof tests | gated (skip cleanly without creds; 4 skipped offline) |

## TABLE 34 — Regression

| Suite group | Count |
|---|--:|
| NEW Bentley binding + geometry tests | 68 passed |
| NEW movement-domain + radionuclide tests | 30 passed |
| Combined Bentley + movement-domain suite | 98 passed, 4 skipped (opt-in live) |
| SB1 + SB2 + SB3 + MRT preservation | 492 passed |
| Spatial route + facility-expansion authorities | 68 passed + 1 PRE_EXISTING_UNRELATED failure |
| Part 3E preservation | 145 passed |
| Generator baseline | 1 PRE_EXISTING_UNRELATED failure (catalog 4 vs 3) |

PRE_EXISTING_UNRELATED_BASELINE_FAILURE = YES (TWO proven pre-existing failures; 0 tracked source files changed → neither caused by this build):
1. `test_conventional_economic_calibration_and_intraday_scheduling.py::test_generator_benchmark_uniform_across_initial_models` — generator catalog 4 vs test-expects-3 (SB1-era documented).
2. `test_build3c1_spatial_route_authority.py::test_5_rght_lane_identity` — asserts `FLOOR_AGV_AMR_IMPLEMENTATION_STATUS == "NOT_IMPLEMENTED"`, but Super-Build 1 (committed `80fe545`) deliberately flipped it to `IMPLEMENTED`. This is a stale TEST_LOCKING_OLD_TRUTH superseded by SB1; `transport_technology_authority.py` is unmodified by this build (`git diff` empty).

## TABLE 35 — Physics / Economics Preservation

MRT_CANONICAL_CONFIGURATION_CHANGED = NO; MRT_RUNTIME_PHYSICS_CHANGED = NO; DECAY/CYCLOTRON/GENERATOR/SCANNER_TIMING_CHANGED = NO; PART3E_CHANGED = NO; EQUAL_BUDGET_CHANGED = NO; TRANSPORT_PARITY_PHYSICS_CHANGED = NO; CAPITAL_INHERITANCE_ECONOMICS_CHANGED = NO. Structurally guaranteed: `git diff --name-only` empty (only the already-committed narrow `.gitignore`).

## TABLE 36 — Remaining Gaps

| Gap | Status |
|---|---|
| Per-element EC inventory / property / spatial extraction | NOT_QUERYABLE_WITH_CURRENT_READ_PATH (needs iTwin.js briefcase/ECSQL reader) |
| Browser viewer client + user-auth flow | NOT_IMPLEMENTED (separate viewer build) |
| Reactive recomputation engine (geometry event → live recompute) | NOT_YET_INTEGRATED (contract established; consumers classified) |
| Live Bentley geometry write-back | NOT_IMPLEMENTED (out of scope) |

## TABLE 37 — Bentley-vs-NVIDIA Decision Readiness

Bentley live read chain PROVEN; geometry tiles exist; identity/changeset/binding contract complete; viewer + element-query paths are the remaining Bentley-side work. This provides an honest basis to compare a Bentley iTwin.js viewer path against an NVIDIA/OpenUSD path in a future bakeoff — but no bakeoff is begun here.

## TABLE 38 — Movement-Domain Model (ADDITIVE clarification)

Owner: NEW `transport_movement_domain_authority.py`, composing `canonical_spatial_authority.resolve_route` (mode-compatible BFS). NETWORK_BOUND: MRT (guideway), RTHS (rail/RGHT edge), PTS_CONVENTIONAL/PTS_NUCLEAR_QUALIFIED (tube). NAVIGABLE_SPACE_BOUND: AGV light/heavy, MANUAL (corridors/doors/elevators). No second routing engine.

## TABLE 39 — Confinement Governors

MRT_CARRIER_OFF_GUIDEWAY = NO · RTHS_VEHICLE_OFF_TRACK = NO · PTS_CAPSULE_OUTSIDE_TUBE = NO · AGV_CROSSES_WALL = NO · MANUAL_ROUTE_CROSSES_WALL = NO. `route_leaves_movement_domain()` always False on a feasible confined route (each path edge proven legal). Verified across all 7 modes.

## TABLE 40 — Topological vs Euclidean Routing

Route length derives from each mode's legal path, not one straight line. Control (A→B): MRT 80 m, PTS 90 m, MANUAL 100 m, AGV 110 m — distinct per-mode lengths ⇒ topological. GEOMETRIC_SEPARATION_EQUALS_ALL_TRANSPORT_ROUTE_LENGTHS = NO.

## TABLE 41 — Disconnected-Network Infeasibility

MRT to a node not on the guideway → INFEASIBLE_DISCONNECTED_NETWORK; no guideway edge → INFEASIBLE_NO_NETWORK; network-bound modes are never silently bridged onto an incompatible edge.

## TABLE 42 — All-Mode Stretch / Compression / Floor

100→500 m stretch increases every mode's confined route length; 500→100 compression returns to baseline; 100→500→100 round-trip drift = 0 (geometry contract, absolute state); 4→8→12 floor events valid (deltas +4/+4).

## TABLE 43 — Intelligent Network Extension

SMART_CONNECTION_POINT_LIES_ON_VALID_NETWORK = YES; MRT_CONNECTION_RESTARTS_FROM_SOURCE_BY_DEFAULT = NO. Candidate principle: prefer facing-side + same-level, then nearest; must lie on the existing legal network. No eligible node → extension INFEASIBLE (never restarts from cyclotron/source). Navigable modes use free-space connection.

## TABLE 44 — Radionuclide Visual Identity

Color belongs to the radionuclide (isotope): F-18 F18_LIME, Tc-99m TC99M_CYAN, Ga-68 GA68_MAGENTA, Lu-177 LU177_ORANGE, I-131 I131_YELLOW, unknown UNKNOWN_GRAY. Reuses the `mrt_service_class_authority` doctrine "color is a property of the substance, not the route/lane" extended to isotope level.

## TABLE 45 — Radionuclide Color Invariance

RADIONUCLIDE_COLOR_CHANGES_WITH_TRANSPORT_MODE = NO; RADIONUCLIDE_COLOR_PERSISTS_ACROSS_MODE_TRANSFER = YES; decay changes activity, not identity color; Tc-99m ≠ F-18. F-18 = F18_LIME across Manual → PTS-nuclear → RTHS → AGV → MRT and after decay.

## TABLE 46 — Three Separate Visual-Identity Layers

RADIONUCLIDE (isotope identity color), PAYLOAD_CONTAINER (container id), TRANSPORT_MODE (mode) are structurally independent. Mode transfer changes only the transport layer; radionuclide identity color + payload lineage preserved.

## TABLE 47 — Movement-Domain Consumer Trace

Mode-confined routing / confinement governors / network extension / radionuclide color = RUNTIME_CONSUMED_NOW (by tests). Reactive geometry→recompute wiring = NOT_YET_INTEGRATED (honest; reactive engine later).

## TABLE 48 — Interactive Route-Authoring Contract (ADDITIVE)

Owner: NEW `interactive_route_authoring_authority.py`, composing `transport_movement_domain_authority.resolve_confined_route` + `canonical_spatial_authority.ConnectivityGraph`. The auto-generated network is an editable engineering proposal (Sec A): in What-If the user may add / remove / extend / reroute / constrain individual routes without returning to project-input forms. No new routing engine.

## TABLE 49 — Pinned Endpoint Semantics

`RouteEndpoint(endpoint_id, role=ORIGIN|DESTINATION, locked=True)`. Moving an intermediate control never moves a pinned endpoint. PINNED_ENDPOINT_MOVES_WITH_INTERMEDIATE_WAYPOINT = NO (verified: endpoints unchanged after move/insert/delete).

## TABLE 50 — Waypoint / Control-Point Semantics

`RouteControlPoint(control_id, node_id, kind ∈ {BEND, REQUIRED_PASSAGE, PREFERRED_CORRIDOR, REQUIRED_DOOR, REQUIRED_ELEVATOR})`. Operations insert/move/delete; every edit revalidates connectivity + confinement and re-routes. USER_CAN_REROUTE_WITH_INTERMEDIATE_CONTROL_POINTS = YES.

## TABLE 51 — Auto-Route Behavior

`auto_route` routes each successive constraint pair (origin → C1 → … → destination) through the mode's LEGAL topology; total = sum of legal-leg lengths; never Euclidean interpolation through prohibited geometry (Sec E). Controls: MRT direct 60 m; via-M2 waypoint changes length; PTS S1→S3 = 80 m; RTHS T0→T2 via T1 = 140 m.

## TABLE 52 — Orthogonal Skeleton vs Physical Bend Geometry

A graphical orthogonal vertex is a PLANNING skeleton point only; the real physical transition (bend radius/elbow/curved tube/switch/junction/H-V) is owned by the technology authority (`physical_bend_authority_owner` per mode). GRAPHICAL_ORTHOGONAL_VERTEX_OVERRIDES_PHYSICAL_BEND_AUTHORITY = NO.

## TABLE 53 — Segment Add / Delete

`add_segment` / `delete_segment` return NEW graphs (non-mutating, local scenario). Deleting a required segment genuinely disconnects downstream → NO_CONNECTED_PATH; never auto-bridged (Sec I). Adding re-enables a disconnected route.

## TABLE 54 — Restore Automatic Route

`restore_auto_route` discards user control points and marks the route AUTO_GENERATED_SCENARIO_NETWORK (no project restart). RESTORE_AUTO_ROUTE_AVAILABLE = YES.

## TABLE 55 — Route-Edit → Full Recomputation

`build_recompute_request(COMMITTED_ROUTE_EDIT)` exposes 17 targets (route_length, travel_time, cycle, fleet/FTE, capacity, energy, radionuclide_decay, required_upstream_activity, production_activity, batch_requirement, cyclotron/generator capacity, scanner/clinical, incremental_capex, target_opex, incremental_opex, feasibility) — not just displayed length (Sec L). ROUTE_EDIT_RECOMPUTES_ENGINEERING_CONSEQUENCES = YES.

## TABLE 56 — Real-Time Preview vs Committed Recompute

DRAG_PREVIEW → lightweight geometry-only (route_length, travel_time); COMMITTED_ROUTE_EDIT → full engineering recompute (Sec U). Committed position triggers authoritative recomputation; simulation not run per mouse pixel.

## TABLE 57 — Route-Edit Scenario Provenance

RouteNetworkState ∈ {BASELINE_NETWORK, AUTO_GENERATED_SCENARIO_NETWORK, USER_EDITED_WHATIF_NETWORK} distinguishable (Sec K). Edits default USER_EDITED_WHATIF; never overwrite baseline / Bentley source / LOCKDOWN. WHATIF_ROUTE_EDIT_MUTATES_LIVE_BENTLEY = NO.

## TABLE 58 — Edit History (undo / redo / restore)

`RouteEditHistory(states, cursor)` gives reproducible undo/redo; `restore_auto_route` returns the optimized route (Sec V). Immutable route states, not a new global history engine.

## TABLE 59 — Payload Stream Origin/Destination Authority (ADDITIVE)

Owner: NEW `payload_endpoint_authority.py`. Endpoints derive from stream + direction (Sec M). Streams: RADIOPHARMACEUTICAL, CONVENTIONAL_MEDICATION, CLEAN_LINEN, STERILE_SUPPLY, SPECIMEN, LAB_SUPPLY. PAYLOAD_STREAM_ENDPOINT_AUTHORITY_COMPLETE = YES.

## TABLE 60 — Default Endpoints by Stream / Direction

| Stream (direction) | Origin | Destination |
|---|---|---|
| RADIOPHARMACEUTICAL (OUTBOUND) | RADIOPHARMACY_RELEASE | PATIENT_CLINICAL_ROOM |
| CONVENTIONAL_MEDICATION (OUTBOUND) | CENTRAL_PHARMACY | PATIENT_CLINICAL_ROOM |
| CLEAN_LINEN (OUTBOUND / RETURN) | LAUNDRY / room | room / LAUNDRY |
| STERILE_SUPPLY (OUTBOUND) | CSSD_STERILE_PROCESSING | PATIENT_CLINICAL_ROOM |
| SPECIMEN (OUTBOUND) | COLLECTION_POINT | LABORATORY |
| LAB_SUPPLY (OUTBOUND) | LABORATORY | PATIENT_CLINICAL_ROOM |

## TABLE 61 — Radiopharmaceutical Production vs Transport Origin

Chain: CYCLOTRON/GENERATOR PRODUCTION → RADIOPHARMACY (synthesis/QC/release) → TRANSPORT ORIGIN → CLINICAL DESTINATION. For a finished dose the transport origin is the qualified radiopharmacy release, NOT the cyclotron. RADIOPHARMACEUTICAL_PRODUCTION_ORIGIN_EQUALS_TRANSPORT_ORIGIN_BY_DEFAULT = NO.

## TABLE 62 — Specimen Directionality

Specimen: COLLECTION_POINT/patient → LABORATORY (lab is destination). Lab-originating supply travels the opposite direction (LAB_SUPPLY origin = LABORATORY). SPECIMEN_ORIGIN_ALWAYS_LAB = NO.

## TABLE 63 — Linen / Sterile Origins

Clean linen origin = LAUNDRY_LINEN_SERVICE; sterile supply origin = CSSD_STERILE_PROCESSING. STERILE_SUPPLY_ORIGIN_ALWAYS_LAUNDRY = NO. Reverse logistics preserved (linen return room→laundry).

## TABLE 64 — Endpoint Validation (pre-auto-route)

`validate_endpoints` rejects: radiopharm on conventional PTS; nuclear channel without qualification; MRT to a room with no MRT endpoint; RTHS to an unconnected station; bulk stream on PTS/MRT. Valid pairs pass. No invalid mission routes (Sec S).

## TABLE 65 — AGV / Manual Navigable-Space Route Editing

AGV/AMR and Manual use navigable-space waypoints (waypoint / preferred-corridor / required-door / required-elevator), never a fake fixed track/porter rail (Sec T). A waypoint in wall/non-navigable space → NO_CONNECTED_PATH. AGV_FAKE_FIXED_TRACK_PRESENT = NO; MANUAL_FAKE_FIXED_TRACK_PRESENT = NO.

## TABLE 66 — Whole-Building Placement Policy vs Engine 6-DOF (ADDITIVE)

Owner: NEW `building_placement_policy_authority.py`. The spatial ENGINE is 6-DOF-capable, but NORMAL whole-building user placement is NOT unrestricted 6-DOF — it is FREE PLANAR PLACEMENT + YAW ROTATION + SUPPORT-AWARE ELEVATION + UPRIGHT EQUILIBRIUM.

| Field | Value |
|---|---|
| UNDERLYING_SPATIAL_ENGINE_6DOF_CAPABLE | YES (canonical Transform: position x/y/z + rotation x/y/z) |
| WHOLE_BUILDING_UNRESTRICTED_6DOF_UX | NO |
| WHOLE_BUILDING_TRANSLATION_X | FREE |
| WHOLE_BUILDING_TRANSLATION_Y | FREE |
| WHOLE_BUILDING_TRANSLATION_Z | SUPPORT-AWARE / CONSTRAINED (never invents ground level → SUPPORT_ELEVATION_NOT_CALIBRATED) |
| WHOLE_BUILDING_YAW | FREE (0..360; triggers connection recompute) |
| WHOLE_BUILDING_ROLL | LOCKED (upright equilibrium, target 0) |
| WHOLE_BUILDING_PITCH | LOCKED (upright equilibrium, target 0) |
| Engine keeps roll/pitch for other object classes (equipment/pipes/track/sloped structure) | YES (only whole-building USER policy locks them) |
| INTERACTIVE_PREVIEW_POSE distinct from COMMITTED_ENGINEERING_POSE | YES (authoritative state never computed from a tilted preview) |

## TABLE 67 — 6-DOF Anchor/Movable Pose Orchestration (ADDITIVE)

Owner: NEW `spatial_pose_orchestration_authority.py`, composing `canonical_spatial_authority` 6-DOF primitives (`Transform`, `apply_rigid_transform`, `resolve_global_position`, `replace_transform`). No duplicate transform engine.

| Field | Value |
|---|---|
| SPATIAL_TRANSFORM_SUPPORTS_6DOF | YES (position x/y/z + rotation x/y/z) |
| BUILDING_TRANSLATION_RESTRICTED_TO_SINGLE_AXIS | NO |
| ANCHOR / MOVABLE roles | explicit; anchor never drifts when movable moves |
| CHILD_CONNECTION_POINT_TRANSFORM_FOLLOWS_PARENT | YES |
| BUILDING_ROTATION_IGNORED_BY_CONNECTION_ENGINE | NO |
| NON_AXIS_ALIGNED_TRANSLATION (B→(300,400,0)) | PASS (separation 500 m) |
| XYZ_SEPARATION (B=(300,400,120)) | PASS (Δx/Δy/Δz preserved) |
| ROTATION_WITH_FIXED_ORIGIN (yaw 90°) | PASS (center fixed, interfaces move) |
| SIX_DOF_ROUND_TRIP_DRIFT_PRESENT | NO |

## TABLE 68 — Multi-Building Campus Graph (ADDITIVE)

Owner: NEW `campus_multibuilding_authority.py`. Each building has its own absolute campus pose; N buildings (1..N) supported; Building 1 is never the global parent.

| Field | Value |
|---|---|
| BUILDING_1_IS_GLOBAL_PARENT_OF_ALL_BUILDINGS | NO |
| Pairwise relationships R_ij = F(B_i,B_j) | DERIVED on demand (never stored ownership) |
| Supports 1/2/3/4/5/N buildings | YES |

## TABLE 69 — Per-Mode Connectivity Components

| Mode | Example component (graph A-B-D-E / A-B / B-C) |
|---|---|
| MRT | {A,B,D,E} |
| PTS_CONVENTIONAL | {A,B} |
| RTHS | {B,C} |

ALL_TRANSPORT_MODES_SHARE_IDENTICAL_CONNECTIVITY_GRAPH = NO.

## TABLE 70 — New/Moved-Building Connection

| Field | Value |
|---|---|
| NEW_BUILDING_ALWAYS_CONNECTS_TO_BUILDING_1 | NO |
| NEAREST_BUILDING_ALWAYS_SELECTED_AS_CONNECTION_PARENT | NO |
| Candidate principle | eligible existing-network node; prefer facing-side+same-level then nearest |
| No eligible network node | INFEASIBLE (never forced to Building 1) |
| BUILDING_NETWORK_ATTACHMENT_CAN_CHANGE_AFTER_MOVE | YES |

## TABLE 71 — Single vs Group Movement

| Field | Value |
|---|---|
| MOVE_SINGLE_BUILDING | only that building + its children move |
| MOVING_BUILDING_C_AUTOMATICALLY_MOVES_A_OR_B | NO |
| MOVE_BUILDING_GROUP {B,C} | members move together, internal geometry preserved; non-members fixed |
| GROUP_MOVE_REBUILDS_ALL_INTERNAL_CONNECTIONS_BY_DEFAULT | NO |
| TRANSPORT_CONNECTIVITY_IMPLIES_MOVEMENT_GROUP | NO |
| ENGINEERING_REACTION_IMPLIES_PHYSICAL_MOVEMENT | NO |

## TABLE 72 — Dependency-Based Localized Reconciliation

Move only E (campus A—B—C, B—D—E): CHANGED={E}; A↔B UNCHANGED; only E-incident connections reconcile; C (different component) unchanged. UNRELATED_NETWORK_SEGMENTS_REBUILT_AFTER_LOCAL_MOVE = NO. Contract sets: CHANGED / AFFECTED / UNCHANGED / RECONCILED.

## TABLE 73 — Full-Path Mission Physics

Route A→B→D→E (A→B→D inherited, D→E incremental):

| Metric | Value |
|---|---|
| Full route length | 345 m (200 inherited + 145 incremental) |
| Incremental CapEx length | 145 m only |
| Full-path travel time @10 m/s | 34.5 s (full route, NOT 14.5 s) |
| INHERITED_NETWORK_ZERO_NEW_CAPEX | ALLOWED |
| INHERITED_NETWORK_ZERO_TRAVEL_TIME | NO |
| DECAY_CALCULATED_ONLY_ON_INCREMENTAL_SEGMENT | NO |

## TABLE 74 — Payload-Specific Campus Routing

Missions originate in different buildings (radiopharm A→E, specimen E→C, linen D→E, sterile B→E). BUILDING_A_IS_UNIVERSAL_LOGISTICS_ORIGIN = NO.

## TABLE 75 — Named Multi-Building Controls

| Control | Result |
|---|---|
| THREE_BUILDING (C connects via B, not A) | PASS |
| THREE_BUILDING_DYNAMIC_RECONNECTION (C near B → near A) | PASS |
| FOUR_BUILDING (two components {A,B}/{C,D}; new joins via existing node) | PASS |
| FIVE_BUILDING_LOCALIZED_MOVE (move E; A/B/C/D fixed; A↔B unchanged; full A→E route updated) | PASS |
| FULL_PATH_DECAY (full-route decay; incremental CapEx = D→E only) | PASS |
| GROUP_MOVE {B,C} (internal preserved; A/D fixed; connectivity≠group) | PASS |

## TABLE 76 — Meshed-Topology / Multi-Interface Readiness

| Field | Value |
|---|---|
| Campus topology must be a tree | NO (disjoint per-mode components already supported) |
| Meshed/loop/redundant multi-connection topology | NOT_YET_INTEGRATED (honest; not prohibited as doctrine) |
| Multiple interfaces per building | candidate-level supported; full multi-interface routing NOT_YET_INTEGRATED |

## TABLE 77 — Final Hard Gates

```
BENTLEY_LIVE_IMODEL_BUILD = COMPLETE
LIVE_BENTLEY_CONNECTION = PASS
LIVE_IMODEL_INSPECTED = YES
LIVE_MODEL_INVENTORY_COMPLETE_OR_QUALIFIED = YES (qualified: REST /elements 404 documented)
LIVE_ELEMENT_INVENTORY_COMPLETE_OR_QUALIFIED = YES (qualified: NOT_QUERYABLE_WITH_CURRENT_READ_PATH)
STABLE_BENTLEY_IDENTITY_CONTRACT_COMPLETE = YES
CANONICAL_BENTLEY_BINDING_COMPLETE = YES
LIVE_BENTLEY_BINDING_PROOF = QUALIFIED (SUPPORTED_BUT_NOT_PRESENT_IN_TEST_IMODEL at element level; real-id binding PASS)
BENTLEY_OBJECT_PRESENT_IMPLIES_NEW_CAPEX = NO
SERVICE_SECRET_EXPOSED_TO_FRONTEND = NO
VIEWER_READINESS_TRACED = YES
GEOMETRY_CHANGE_CONTRACT_COMPLETE = YES
BUILDING_SEPARATION_CONTROL = PASS
MOVE_BACK_CONTROL = PASS
FLOOR_COUNT_CONTROL = PASS
ROUND_TRIP_GEOMETRY_DRIFT_PRESENT = NO
3D_ACTION_2D_CONSEQUENCE_CONTRACT_COMPLETE = YES
UNKNOWN_GEOMETRY_CONSEQUENCE_ZERO_FILLED = NO
LIVE_BENTLEY_GEOMETRY_MUTATION_IMPLEMENTED = NO
NEW_BENTLEY_TESTS = 68 (>= 50)
OFFLINE_TESTS_REQUIRE_BENTLEY_CREDENTIALS = NO
REGRESSION = PASS (2 proven pre-existing unrelated failures: generator catalog 4-vs-3; test_5_rght_lane_identity locks pre-SB1 NOT_IMPLEMENTED, superseded by SB1 at 80fe545)
REPORT_DATA_MATERIAL_DISCREPANCIES = 0
MISSING_REQUIRED_REPORT_TABLES = 0
SECRET_EXPOSED_IN_OUTPUT = NO
BENTLEY_ENV_FILE_COMMITTED = NO
MRT_CARRIER_OFF_GUIDEWAY = NO
RTHS_VEHICLE_OFF_TRACK = NO
PTS_CAPSULE_OUTSIDE_TUBE = NO
AGV_CROSSES_WALL = NO
MANUAL_ROUTE_CROSSES_WALL = NO
DISCONNECTED_NETWORK_TREATED_AS_FEASIBLE = NO
ROUTE_LENGTH_IS_TOPOLOGICAL_NOT_EUCLIDEAN = YES
GEOMETRIC_SEPARATION_EQUALS_ALL_TRANSPORT_ROUTE_LENGTHS = NO
SMART_CONNECTION_POINT_LIES_ON_VALID_NETWORK = YES
MRT_CONNECTION_RESTARTS_FROM_SOURCE_BY_DEFAULT = NO
RADIONUCLIDE_COLOR_CHANGES_WITH_TRANSPORT_MODE = NO
RADIONUCLIDE_COLOR_PERSISTS_ACROSS_MODE_TRANSFER = YES
USER_CAN_CREATE_FIXED_NETWORK_ROUTE = YES
USER_CAN_INSERT_ROUTE_WAYPOINT = YES
USER_CAN_MOVE_ROUTE_WAYPOINT = YES
USER_CAN_DELETE_ROUTE_SEGMENT = YES
PINNED_ENDPOINT_MOVES_WITH_INTERMEDIATE_WAYPOINT = NO
AUTO_ROUTE_AVAILABLE = YES
RESTORE_AUTO_ROUTE_AVAILABLE = YES
ORTHOGONAL_UI_VERTEX_OVERRIDES_PHYSICAL_BEND_GEOMETRY = NO
ROUTE_EDIT_RECOMPUTES_ENGINEERING_CONSEQUENCES = YES
RADIOPHARMACEUTICAL_PRODUCTION_ORIGIN_EQUALS_TRANSPORT_ORIGIN_BY_DEFAULT = NO
SPECIMEN_ORIGIN_ALWAYS_LAB = NO
STERILE_SUPPLY_ORIGIN_ALWAYS_LAUNDRY = NO
PAYLOAD_STREAM_ENDPOINT_AUTHORITY_COMPLETE = YES
AGV_FAKE_FIXED_TRACK_PRESENT = NO
MANUAL_FAKE_FIXED_TRACK_PRESENT = NO
WHATIF_ROUTE_EDIT_MUTATES_LIVE_BENTLEY = NO
NEW_MOVEMENT_DOMAIN_TESTS = 30
NEW_INTERACTIVE_ROUTING_TESTS = 38
NEW_CAMPUS_MULTIBUILDING_TESTS = 32
UNDERLYING_SPATIAL_ENGINE_6DOF_CAPABLE = YES
SPATIAL_TRANSFORM_SUPPORTS_6DOF = YES
WHOLE_BUILDING_UNRESTRICTED_6DOF_UX = NO
WHOLE_BUILDING_ROLL_LOCKED = YES
WHOLE_BUILDING_PITCH_LOCKED = YES
WHOLE_BUILDING_YAW_FREE = YES
WHOLE_BUILDING_Z_SUPPORT_AWARE = YES
BUILDING_TRANSLATION_RESTRICTED_TO_SINGLE_AXIS = NO
NON_AXIS_ALIGNED_TRANSLATION_CONTROL = PASS
XYZ_SEPARATION_CONTROL = PASS
ROTATION_WITH_FIXED_ORIGIN_CONTROL = PASS
SIX_DOF_ROUND_TRIP_DRIFT_PRESENT = NO
CHILD_CONNECTION_POINT_TRANSFORM_FOLLOWS_PARENT = YES
BUILDING_ROTATION_IGNORED_BY_CONNECTION_ENGINE = NO
BUILDING_1_IS_GLOBAL_PARENT_OF_ALL_BUILDINGS = NO
ALL_TRANSPORT_MODES_SHARE_IDENTICAL_CONNECTIVITY_GRAPH = NO
NEW_BUILDING_ALWAYS_CONNECTS_TO_BUILDING_1 = NO
NEAREST_BUILDING_ALWAYS_SELECTED_AS_CONNECTION_PARENT = NO
BUILDING_NETWORK_ATTACHMENT_CAN_CHANGE_AFTER_MOVE = YES
MOVING_BUILDING_C_AUTOMATICALLY_MOVES_A_OR_B = NO
ENGINEERING_REACTION_IMPLIES_PHYSICAL_MOVEMENT = NO
TRANSPORT_CONNECTIVITY_IMPLIES_MOVEMENT_GROUP = NO
GROUP_MOVE_REBUILDS_ALL_INTERNAL_CONNECTIONS_BY_DEFAULT = NO
UNRELATED_NETWORK_SEGMENTS_REBUILT_AFTER_LOCAL_MOVE = NO
INHERITED_NETWORK_ZERO_TRAVEL_TIME = NO
DECAY_CALCULATED_ONLY_ON_INCREMENTAL_SEGMENT = NO
BUILDING_A_IS_UNIVERSAL_LOGISTICS_ORIGIN = NO
THREE_BUILDING_DYNAMIC_RECONNECTION_CONTROL = PASS
FOUR_BUILDING_CONTROL = PASS
FIVE_BUILDING_LOCALIZED_MOVE_CONTROL = PASS
FULL_PATH_DECAY_CONTROL = PASS
GROUP_MOVE_CONTROL = PASS
READY_FOR_REACTIVE_3D_ENGINE_BUILD = YES
READY_FOR_BENTLEY_VIEWER_BUILD = YES
READY_FOR_NVIDIA_BAKEOFF = YES (honest basis established; not begun)
```

**BENTLEY_LIVE_IMODEL_BUILD = COMPLETE (with additive movement-domain / topology-confinement, radionuclide visual-identity, interactive route-authoring, and payload origin/destination clarifications).** STOP — integration files left uncommitted for review; only the narrow `.gitignore` security commit was pushed. No live Bentley mutation, no viewer UI, no reactive engine, no NVIDIA, no LOCKDOWN/What-If begun.
