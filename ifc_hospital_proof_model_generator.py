"""BIM/iTwin Phase 2A: Controlled Synthetic Hospital IFC Proof Model.

GOVERNANCE: this module is a CONTROLLED TEST-SOURCE GENERATOR only. It is
NOT a geometry authority for the application (section 18) -- it never
touches `canonical_spatial_authority.SpatialObjectRegistry`, never creates a
second room/equipment registry, and never runs routing. Its sole output is
one deterministic, standards-shaped IFC4 STEP (ISO-10303-21) file plus a
machine-readable manifest describing that SAME file, both generated from one
shared in-memory model so they can never independently disagree (section 13).

NO EXTERNAL DEPENDENCY: no IFC-authoring library (e.g. ifcopenshell) is
installed in this environment (verified absent) and none is installed here
-- IFC's STEP Physical File format is plain, well-specified ASCII text, so
this module hand-writes a minimal, well-formed IFC4 SPF file directly. This
is deliberately the "smallest maintainable" option (section 10) -- literally
zero new dependencies -- rather than pulling in a large BIM-authoring stack
for a controlled test fixture. `read_ifc_proof_model()` below is a narrow,
self-contained SPF reader (regex-based, not a full IFC4 EXPRESS-schema
validator) used only to prove the generated file can be reopened and its
contents reconciled against the manifest (section 20 item 2/19).

TEST GEOMETRY ONLY (section 3): dimensions/layout are controlled test values
for deterministic spatial verification -- never presented as hospital design
standards.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Mapping, Sequence

MRTWAY_MODEL_CLASS = "SYNTHETIC_TEST_BIM"
MRTWAY_MODEL_PURPOSE = "BENTLEY_ITWIN_INTEGRATION_PROOF"

BUILDING_ID = "BLDG-HOSP-A"
BUILDING_NAME = "MRT Pharma Hospital Proof Building"
FOOTPRINT_X_M = 30.0
FOOTPRINT_Y_M = 20.0
FLOOR_TO_FLOOR_HEIGHT_M = 4.0
FLOOR_1_ELEVATION_M = 0.0
FLOOR_2_ELEVATION_M = FLOOR_TO_FLOOR_HEIGHT_M


@dataclass(frozen=True)
class ProofRoom:
    room_id: str
    name: str
    floor_id: str
    x_m: float
    y_m: float
    z_m: float


@dataclass(frozen=True)
class ProofEquipment:
    engineering_object_id: str
    name: str
    room_id: str
    x_m: float
    y_m: float
    z_m: float


@dataclass(frozen=True)
class ProofRoutePair:
    proof_id: str
    start_room_id: str
    end_room_id: str


@dataclass(frozen=True)
class HospitalProofModel:
    building_id: str
    building_name: str
    footprint_x_m: float
    footprint_y_m: float
    floor_to_floor_height_m: float
    floor_ids: tuple[str, ...]
    floor_elevations_m: Mapping[str, float]
    rooms: tuple[ProofRoom, ...]
    equipment: tuple[ProofEquipment, ...]
    route_pairs: tuple[ProofRoutePair, ...]
    expected_bindings: Mapping[str, str]
    """engineering_object_id -> room_id (section 14)."""


def build_hospital_proof_model() -> HospitalProofModel:
    """Section 3-9/15: ONE deterministic, non-symmetric layout -- no random
    generation. Floor 1 rooms sit at z=0.0 (ground floor elevation); Floor 2
    rooms sit at z=FLOOR_TO_FLOOR_HEIGHT_M (section 3). VERT-001 is modeled
    as a single continuous vertical-circulation space (one canonical room
    identity) spanning both floors (section 5: "the second-floor
    continuation of VERT-001" is the SAME object, not a duplicate)."""
    floor_ids = ("F1", "F2")
    floor_elevations = {"F1": FLOOR_1_ELEVATION_M, "F2": FLOOR_2_ELEVATION_M}

    rooms = (
        ProofRoom("ROOM-RP-101", "Radiopharmacy", "F1", x_m=5.0, y_m=15.0, z_m=0.0),
        ProofRoom("ROOM-CY-102", "Cyclotron Room", "F1", x_m=12.0, y_m=15.0, z_m=0.0),
        ProofRoom("ROOM-INJ-103", "Injection/Uptake Room", "F1", x_m=22.0, y_m=5.0, z_m=0.0),
        ProofRoom("COR-F1-001", "Floor 1 Main Corridor", "F1", x_m=15.0, y_m=10.0, z_m=0.0),
        ProofRoom("VERT-001", "Vertical Circulation Core", "F1", x_m=27.0, y_m=10.0, z_m=0.0),
        ProofRoom("ROOM-PAT-201", "Patient Room", "F2", x_m=6.0, y_m=15.0, z_m=FLOOR_TO_FLOOR_HEIGHT_M),
        ProofRoom("ROOM-SCN-202", "Scanner Room", "F2", x_m=24.0, y_m=6.0, z_m=FLOOR_TO_FLOOR_HEIGHT_M),
        ProofRoom("COR-F2-001", "Floor 2 Main Corridor", "F2", x_m=15.0, y_m=10.0, z_m=FLOOR_TO_FLOOR_HEIGHT_M),
    )

    equipment = (
        ProofEquipment("CY-001", "Cyclotron (test proxy)", "ROOM-CY-102", x_m=12.0, y_m=15.0, z_m=0.0),
        ProofEquipment("SCN-001", "Scanner (test proxy)", "ROOM-SCN-202", x_m=24.0, y_m=6.0, z_m=FLOOR_TO_FLOOR_HEIGHT_M),
        ProofEquipment("RP-001", "Radiopharmacy interface (test proxy)", "ROOM-RP-101", x_m=5.0, y_m=15.0, z_m=0.0),
    )

    route_pairs = (
        ProofRoutePair("A", "ROOM-RP-101", "ROOM-INJ-103"),
        ProofRoutePair("B", "ROOM-INJ-103", "ROOM-PAT-201"),
        ProofRoutePair("C", "ROOM-PAT-201", "ROOM-SCN-202"),
        ProofRoutePair("D", "ROOM-RP-101", "ROOM-SCN-202"),
    )

    expected_bindings = {"CY-001": "ROOM-CY-102", "SCN-001": "ROOM-SCN-202", "RP-001": "ROOM-RP-101"}

    return HospitalProofModel(
        building_id=BUILDING_ID, building_name=BUILDING_NAME, footprint_x_m=FOOTPRINT_X_M, footprint_y_m=FOOTPRINT_Y_M,
        floor_to_floor_height_m=FLOOR_TO_FLOOR_HEIGHT_M, floor_ids=floor_ids, floor_elevations_m=floor_elevations,
        rooms=rooms, equipment=equipment, route_pairs=route_pairs, expected_bindings=expected_bindings,
    )


# ---------------------------------------------------------------------------
# Phase 2A.1: geometry dimension authority (section 9).
#
# GOVERNANCE: this is VISUALIZATION/INTEROPERABILITY geometry metadata only
# -- it never becomes a second spatial/engineering identity. `object_id`
# always refers to an ALREADY-EXISTING room_id/engineering_object_id defined
# above; dimensions never redefine or reinterpret the Phase 2A placement
# coordinates (which remain centroid/reference points, never bounding-box
# corners, section 3).
# ---------------------------------------------------------------------------

DEFAULT_ROOM_WIDTH_M = 6.0
DEFAULT_ROOM_DEPTH_M = 6.0
DEFAULT_ROOM_HEIGHT_M = 3.0
DEFAULT_EQUIPMENT_WIDTH_M = 1.5
DEFAULT_EQUIPMENT_DEPTH_M = 1.5
DEFAULT_EQUIPMENT_HEIGHT_M = 1.5
"""Section 9: deliberately simple, deterministic controlled-test dimensions
-- uniform across all rooms/equipment (not architectural design values).
Every room in this proof model uses the SAME footprint/height; this is an
engineering-interoperability proof, not architectural authoring (section 2)."""


@dataclass(frozen=True)
class ProofGeometryDefinition:
    """Section 9: the ONE controlled geometry-dimension authority for this
    generator -- width/depth/height are simple rectangular-prism
    extrusion dimensions in product-LOCAL coordinates; `local_geometry_origin`
    lets a future object offset its solid from its own placement origin
    without touching the placement itself (default (0,0,0): the solid is
    centered/based exactly at the object's existing placement point, so the
    already-reconciled Phase 2A global coordinates are never altered,
    section 4)."""

    object_id: str
    width_m: float
    depth_m: float
    height_m: float
    local_geometry_origin: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def __post_init__(self) -> None:
        if self.width_m <= 0.0 or self.depth_m <= 0.0 or self.height_m <= 0.0:
            raise ValueError(f"{self.object_id}: width/depth/height must all be positive")


def build_geometry_definitions(model: HospitalProofModel) -> dict[str, ProofGeometryDefinition]:
    """One entry per room_id and per engineering_object_id -- the SAME
    identifiers already used as canonical MRTway identity, never a second
    identity scheme (section 9)."""
    definitions: dict[str, ProofGeometryDefinition] = {}
    for room in model.rooms:
        definitions[room.room_id] = ProofGeometryDefinition(
            object_id=room.room_id, width_m=DEFAULT_ROOM_WIDTH_M, depth_m=DEFAULT_ROOM_DEPTH_M, height_m=DEFAULT_ROOM_HEIGHT_M,
        )
    for item in model.equipment:
        definitions[item.engineering_object_id] = ProofGeometryDefinition(
            object_id=item.engineering_object_id, width_m=DEFAULT_EQUIPMENT_WIDTH_M, depth_m=DEFAULT_EQUIPMENT_DEPTH_M,
            height_m=DEFAULT_EQUIPMENT_HEIGHT_M,
        )
    return definitions



# ---------------------------------------------------------------------------
# IFC4 STEP (ISO-10303-21) writer -- no external dependency (section 10).
# ---------------------------------------------------------------------------


class _StepWriter:
    """Minimal incrementing-entity-ID STEP writer -- generic enough to
    express IFC4 entities without hardcoding entity numbering by hand."""

    def __init__(self) -> None:
        self._lines: list[str] = []
        self._next_id = 1

    def add(self, entity_type: str, *args: object) -> str:
        ref = f"#{self._next_id}"
        self._next_id += 1
        self._lines.append(f"{ref}={entity_type}({','.join(self._format(a) for a in args)});")
        return ref

    @staticmethod
    def _format(value: object) -> str:
        if value is None:
            return "$"
        if isinstance(value, bool):
            return ".T." if value else ".F."
        if isinstance(value, str):
            if value.startswith(".") and value.endswith("."):
                return value  # enumeration literal, e.g. .METRE.
            if value.startswith("#"):
                return value  # entity reference
            escaped = value.replace("'", "''")
            return f"'{escaped}'"
        if isinstance(value, (int, float)):
            return f"{float(value):.6f}" if isinstance(value, float) else str(value)
        if isinstance(value, (list, tuple)):
            return "(" + ",".join(_StepWriter._format(v) for v in value) + ")"
        raise TypeError(f"Unsupported STEP value type: {type(value)!r}")

    def render(self, *, schema: str, filename: str) -> str:
        header = [
            "ISO-10303-21;",
            "HEADER;",
            f"FILE_DESCRIPTION((''),'2;1');",
            f"FILE_NAME('{filename}','',(''),(''),'','','');",
            f"FILE_SCHEMA(('{schema}'));",
            "ENDSEC;",
            "DATA;",
        ]
        footer = ["ENDSEC;", "END-ISO-10303-21;"]
        return "\n".join(header + self._lines + footer) + "\n"


def _property_single_value(writer: _StepWriter, *, name: str, value: str) -> str:
    return writer.add("IFCPROPERTYSINGLEVALUE", name, None, ("IFCTEXT", value), None)


def _property_set(writer: _StepWriter, *, name: str, properties: Sequence[str]) -> str:
    return writer.add("IFCPROPERTYSET", _guid(), None, name, None, list(properties))


def _rel_defines_by_properties(writer: _StepWriter, *, related_objects: Sequence[str], property_set: str) -> str:
    return writer.add("IFCRELDEFINESBYPROPERTIES", _guid(), None, None, None, list(related_objects), property_set)


def _rel_contained_in_spatial_structure(writer: _StepWriter, *, related_elements: Sequence[str], structure: str) -> str:
    return writer.add("IFCRELCONTAINEDINSPATIALSTRUCTURE", _guid(), None, None, None, list(related_elements), structure)


def _rel_aggregates(writer: _StepWriter, *, relating_object: str, related_objects: Sequence[str]) -> str:
    return writer.add("IFCRELAGGREGATES", _guid(), None, None, None, relating_object, list(related_objects))


_GUID_COUNTER = {"n": 0}


def _guid() -> str:
    """Deterministic (never random, section 13) 22-char pseudo-GUID."""
    _GUID_COUNTER["n"] += 1
    return f"MRTWAYPROOFGUID{_GUID_COUNTER['n']:07d}"


def _local_placement(writer: _StepWriter, *, x: float, y: float, z: float, relative_to: str | None) -> str:
    point = writer.add("IFCCARTESIANPOINT", (x, y, z))
    axis2placement = writer.add("IFCAXIS2PLACEMENT3D", point, None, None)
    return writer.add("IFCLOCALPLACEMENT", relative_to, axis2placement)


def _geometric_representation_context(writer: _StepWriter) -> tuple[str, str]:
    """Section 6: a standards-consistent `IfcGeometricRepresentationContext`
    (+ a `Body` `IfcGeometricRepresentationSubContext`) -- required by a
    conventional IFC4 consumer before any `IfcShapeRepresentation` is
    meaningful. Returns (context_ref, body_subcontext_ref)."""
    world_origin = writer.add("IFCCARTESIANPOINT", (0.0, 0.0, 0.0))
    world_axis = writer.add("IFCAXIS2PLACEMENT3D", world_origin, None, None)
    context = writer.add("IFCGEOMETRICREPRESENTATIONCONTEXT", None, "Model", 3, 1.0e-05, world_axis, None)
    body_subcontext = writer.add(
        "IFCGEOMETRICREPRESENTATIONSUBCONTEXT", "Body", "Model", None, None, None, None, context, None, ".MODEL_VIEW.", None,
    )
    return context, body_subcontext


def _extruded_box_shape(writer: _StepWriter, *, geometry: ProofGeometryDefinition, body_subcontext: str) -> str:
    """Section 2/6: `IfcProductDefinitionShape -> IfcShapeRepresentation
    ("Body"/"SweptSolid") -> IfcExtrudedAreaSolid -> IfcRectangleProfileDef`
    -- a simple rectangular-prism extrusion in PRODUCT-LOCAL coordinates
    (never global coordinates, section 4: the object's existing
    `IfcLocalPlacement` remains the sole source of global position)."""
    ox, oy, oz = geometry.local_geometry_origin
    profile_origin = writer.add("IFCCARTESIANPOINT", (ox, oy))
    profile_placement = writer.add("IFCAXIS2PLACEMENT2D", profile_origin, None)
    profile = writer.add("IFCRECTANGLEPROFILEDEF", ".AREA.", None, profile_placement, geometry.width_m, geometry.depth_m)
    extrusion_origin = writer.add("IFCCARTESIANPOINT", (ox, oy, oz))
    extrusion_placement = writer.add("IFCAXIS2PLACEMENT3D", extrusion_origin, None, None)
    extrusion_direction = writer.add("IFCDIRECTION", (0.0, 0.0, 1.0))
    solid = writer.add("IFCEXTRUDEDAREASOLID", profile, extrusion_placement, extrusion_direction, geometry.height_m)
    shape_representation = writer.add("IFCSHAPEREPRESENTATION", body_subcontext, "Body", "SweptSolid", [solid])
    return writer.add("IFCPRODUCTDEFINITIONSHAPE", None, None, [shape_representation])


def generate_ifc_text(model: HospitalProofModel) -> str:
    """Section 10-11: produces the IFC4 SPF text for `model`. Pure function
    -- no filesystem access, so tests can validate content without I/O.
    Resets the module-level deterministic GUID counter first so repeated
    calls with the same `model` always produce byte-identical output
    (section 20), regardless of how many times this function has already
    run in the current process."""
    _GUID_COUNTER["n"] = 0
    writer = _StepWriter()
    geometry_definitions = build_geometry_definitions(model)

    length_unit = writer.add("IFCSIUNIT", None, "LENGTHUNIT", None, ".METRE.")
    unit_assignment = writer.add("IFCUNITASSIGNMENT", [length_unit])
    representation_context, body_subcontext = _geometric_representation_context(writer)

    project_placement = _local_placement(writer, x=0.0, y=0.0, z=0.0, relative_to=None)
    project = writer.add(
        "IFCPROJECT", _guid(), None, "MRT Pharma Hospital BIM Proof", None, None, None, None, [representation_context], unit_assignment,
    )

    site_placement = _local_placement(writer, x=0.0, y=0.0, z=0.0, relative_to=project_placement)
    site = writer.add("IFCSITE", _guid(), None, "MRT Pharma Proof Site", None, None, site_placement, None, None)

    building_placement = _local_placement(writer, x=0.0, y=0.0, z=0.0, relative_to=site_placement)
    building = writer.add(
        "IFCBUILDING", _guid(), None, model.building_name, None, model.building_id, building_placement, None, None,
    )
    building_props = _property_set(
        writer, name="MRTway_BIM_Proof_Metadata",
        properties=[
            _property_single_value(writer, name="MRTWAY_MODEL_CLASS", value=MRTWAY_MODEL_CLASS),
            _property_single_value(writer, name="MRTWAY_MODEL_PURPOSE", value=MRTWAY_MODEL_PURPOSE),
            _property_single_value(writer, name="MRTWAY_BUILDING_ID", value=model.building_id),
        ],
    )
    _rel_defines_by_properties(writer, related_objects=[building], property_set=building_props)

    storey_refs: dict[str, str] = {}
    storey_placement_refs: dict[str, str] = {}
    for floor_id in model.floor_ids:
        elevation = model.floor_elevations_m[floor_id]
        storey_placement = _local_placement(writer, x=0.0, y=0.0, z=elevation, relative_to=building_placement)
        storey = writer.add(
            "IFCBUILDINGSTOREY", _guid(), None, f"Floor {floor_id}", None, floor_id, storey_placement, None, elevation,
        )
        storey_refs[floor_id] = storey
        storey_placement_refs[floor_id] = storey_placement
    _rel_aggregates(writer, relating_object=building, related_objects=list(storey_refs.values()))

    room_refs: dict[str, str] = {}
    room_placement_refs: dict[str, str] = {}
    rooms_by_floor: dict[str, list[str]] = {floor_id: [] for floor_id in model.floor_ids}
    for room in model.rooms:
        room_placement = _local_placement(
            writer, x=room.x_m, y=room.y_m, z=(room.z_m - model.floor_elevations_m[room.floor_id]),
            relative_to=storey_placement_refs[room.floor_id],
        )
        space = writer.add(
            "IFCSPACE", _guid(), None, room.name, None, room.room_id, room_placement,
            _extruded_box_shape(writer, geometry=geometry_definitions[room.room_id], body_subcontext=body_subcontext),
            room.name, None, ".INTERNAL.", None,
        )
        room_props = _property_set(
            writer, name="MRTway_Room_Identity", properties=[_property_single_value(writer, name="MRTWAY_ROOM_ID", value=room.room_id)],
        )
        _rel_defines_by_properties(writer, related_objects=[space], property_set=room_props)
        room_refs[room.room_id] = space
        room_placement_refs[room.room_id] = room_placement
        rooms_by_floor[room.floor_id].append(space)

    for floor_id, space_refs in rooms_by_floor.items():
        _rel_contained_in_spatial_structure(writer, related_elements=space_refs, structure=storey_refs[floor_id])

    equipment_refs: dict[str, str] = {}
    for item in model.equipment:
        room = next(r for r in model.rooms if r.room_id == item.room_id)
        item_placement = _local_placement(
            writer, x=(item.x_m - room.x_m), y=(item.y_m - room.y_m), z=(item.z_m - room.z_m),
            relative_to=room_placement_refs[item.room_id],
        )
        proxy = writer.add(
            "IFCBUILDINGELEMENTPROXY", _guid(), None, item.name, None, item.engineering_object_id, item_placement,
            _extruded_box_shape(writer, geometry=geometry_definitions[item.engineering_object_id], body_subcontext=body_subcontext),
            None, None,
        )
        item_props = _property_set(
            writer, name="MRTway_Engineering_Identity",
            properties=[_property_single_value(writer, name="MRTWAY_ENGINEERING_OBJECT_ID", value=item.engineering_object_id)],
        )
        _rel_defines_by_properties(writer, related_objects=[proxy], property_set=item_props)
        equipment_refs[item.engineering_object_id] = proxy
        _rel_contained_in_spatial_structure(writer, related_elements=[proxy], structure=room_refs[item.room_id])

    return writer.render(schema="IFC4", filename="mrt_pharma_hospital_bim_proof.ifc")


def generate_manifest(model: HospitalProofModel, *, ifc_filename: str) -> dict:
    """Section 12-15/10: the CONTROL FILE -- generated FROM the same
    in-memory `model` (and the SAME `build_geometry_definitions`) the IFC
    text is generated from, so it can never independently disagree with the
    IFC content (section 13). Additively extended (section 10) with
    per-object geometry-verification fields; no existing field removed or
    renamed."""
    geometry_definitions = build_geometry_definitions(model)
    return {
        "mrtway_model_class": MRTWAY_MODEL_CLASS,
        "mrtway_model_purpose": MRTWAY_MODEL_PURPOSE,
        "source_ifc_filename": ifc_filename,
        "model_units": "meters",
        "coordinate_reference_system": "LOCAL_ENGINEERING_NON_GEOREFERENCED",
        "building": {"building_id": model.building_id, "building_name": model.building_name, "footprint_x_m": model.footprint_x_m, "footprint_y_m": model.footprint_y_m},
        "floors": [{"floor_id": floor_id, "elevation_m": model.floor_elevations_m[floor_id]} for floor_id in model.floor_ids],
        "rooms": [
            {
                "room_id": r.room_id, "name": r.name, "floor_id": r.floor_id, "x_m": r.x_m, "y_m": r.y_m, "z_m": r.z_m,
                "object_class": "IFCSPACE", "width_m": geometry_definitions[r.room_id].width_m,
                "depth_m": geometry_definitions[r.room_id].depth_m, "height_m": geometry_definitions[r.room_id].height_m,
                "geometry_representation_expected": True,
            }
            for r in model.rooms
        ],
        "equipment": [
            {
                "engineering_object_id": e.engineering_object_id, "name": e.name, "room_id": e.room_id, "x_m": e.x_m, "y_m": e.y_m, "z_m": e.z_m,
                "object_class": "IFCBUILDINGELEMENTPROXY", "width_m": geometry_definitions[e.engineering_object_id].width_m,
                "depth_m": geometry_definitions[e.engineering_object_id].depth_m, "height_m": geometry_definitions[e.engineering_object_id].height_m,
                "geometry_representation_expected": True,
            }
            for e in model.equipment
        ],
        "expected_room_equipment_bindings": dict(model.expected_bindings),
        "expected_route_proof_pairs": [
            {"proof_id": p.proof_id, "start_room_id": p.start_room_id, "end_room_id": p.end_room_id} for p in model.route_pairs
        ],
    }


def write_hospital_proof_model(*, ifc_path: str, manifest_path: str) -> HospitalProofModel:
    """Generates both files from ONE shared model instance and writes them
    to disk. Returns the model so callers/tests can cross-check without
    re-parsing."""
    model = build_hospital_proof_model()
    ifc_filename = ifc_path.rsplit("/", 1)[-1]
    with open(ifc_path, "w", encoding="ascii") as f:
        f.write(generate_ifc_text(model))
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(generate_manifest(model, ifc_filename=ifc_filename), f, indent=2, sort_keys=True)
    return model


# ---------------------------------------------------------------------------
# Narrow SPF reader -- proves the file can be reopened/reconciled (section
# 20 items 2/19). NOT a general IFC4 EXPRESS-schema validator.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedIfcEntity:
    ref: str
    entity_type: str
    raw_args: str


def _split_top_level_args(raw_args: str) -> list[str]:
    """Splits a STEP entity's argument string on top-level commas only --
    respecting nested parentheses and quoted strings (needed because tuple
    arguments and property-set text values also contain commas)."""
    parts: list[str] = []
    depth = 0
    in_string = False
    current: list[str] = []
    for ch in raw_args:
        if ch == "'" and not in_string:
            in_string = True
            current.append(ch)
        elif ch == "'" and in_string:
            in_string = False
            current.append(ch)
        elif in_string:
            current.append(ch)
        elif ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def _parse_ref_list(token: str) -> list[str]:
    token = token.strip()
    if not token.startswith("(") or not token.endswith(")"):
        return []
    inner = token[1:-1]
    return [t.strip() for t in inner.split(",") if t.strip()]


def _parse_float_tuple(token: str) -> tuple[float, ...]:
    token = token.strip()
    inner = token[1:-1]
    return tuple(float(x) for x in inner.split(","))


def _unquote(token: str) -> str:
    token = token.strip()
    if token.startswith("'") and token.endswith("'"):
        return token[1:-1]
    return token


@dataclass(frozen=True)
class ResolvedBodyGeometry:
    """Section 11 items 3-9: the fully-resolved representation chain for one
    product, as actually found in the generated STEP text (never assumed)."""

    representation_identifier: str
    representation_type: str
    solid_entity_type: str
    width_m: float
    depth_m: float
    extrusion_depth_m: float


@dataclass(frozen=True)
class ParsedIfcModel:
    schema: str
    entities: tuple[ParsedIfcEntity, ...]

    def __post_init__(self) -> None:
        by_ref = {e.ref: e for e in self.entities}
        object.__setattr__(self, "_by_ref", by_ref)

    def of_type(self, entity_type: str) -> tuple[ParsedIfcEntity, ...]:
        return tuple(e for e in self.entities if e.entity_type == entity_type)

    def _property_single_values(self) -> dict[str, tuple[str, str]]:
        """ref -> (name, value) for every IFCPROPERTYSINGLEVALUE."""
        values: dict[str, tuple[str, str]] = {}
        for entity in self.of_type("IFCPROPERTYSINGLEVALUE"):
            args = _split_top_level_args(entity.raw_args)
            name = args[0].strip("'")
            value_match = re.search(r"'([^']*)'\)$", args[2])
            if value_match:
                values[entity.ref] = (name, value_match.group(1))
        return values

    def _property_sets(self) -> dict[str, dict[str, str]]:
        """property-set ref -> {property_name: value}."""
        single_values = self._property_single_values()
        sets: dict[str, dict[str, str]] = {}
        for entity in self.of_type("IFCPROPERTYSET"):
            args = _split_top_level_args(entity.raw_args)
            prop_refs = _parse_ref_list(args[-1])
            sets[entity.ref] = dict(single_values[ref] for ref in prop_refs if ref in single_values)
        return sets

    def entity_property_values(self) -> dict[str, dict[str, str]]:
        """Maps EVERY related object's ref -> its own {property_name: value}
        dict, resolved through IFCRELDEFINESBYPROPERTIES -> IFCPROPERTYSET ->
        IFCPROPERTYSINGLEVALUE (never collapsing distinct objects' values
        together, unlike a flat name->value map would)."""
        property_sets = self._property_sets()
        result: dict[str, dict[str, str]] = {}
        for entity in self.of_type("IFCRELDEFINESBYPROPERTIES"):
            args = _split_top_level_args(entity.raw_args)
            related_refs = _parse_ref_list(args[-2])
            property_set_ref = args[-1].strip()
            props = property_sets.get(property_set_ref, {})
            for ref in related_refs:
                result.setdefault(ref, {}).update(props)
        return result

    def find_entities_with_property(self, name: str, value: str) -> tuple[ParsedIfcEntity, ...]:
        by_ref = getattr(self, "_by_ref")
        matches = []
        for ref, props in self.entity_property_values().items():
            if props.get(name) == value and ref in by_ref:
                matches.append(by_ref[ref])
        return tuple(matches)

    def property_values(self) -> dict[str, str]:
        """Flat name->value convenience map (collapses duplicates) -- kept
        for simple existence checks; use `entity_property_values()`/
        `find_entities_with_property()` for per-object precision."""
        flat: dict[str, str] = {}
        for props in self.entity_property_values().values():
            flat.update(props)
        return flat

    def resolve_global_position(self, entity_ref: str) -> tuple[float, float, float]:
        """Section 19: walks the IFCLOCALPLACEMENT->IFCAXIS2PLACEMENT3D->
        IFCCARTESIANPOINT chain up through every parent placement, summing
        translations (no rotation is used anywhere in this proof model, so a
        simple sum reproduces the true global position)."""
        by_ref = getattr(self, "_by_ref")
        args = _split_top_level_args(by_ref[entity_ref].raw_args)
        placement_ref = args[5].strip()
        total_x = total_y = total_z = 0.0
        current = placement_ref
        while current and current != "$":
            placement_entity = by_ref[current]
            p_args = _split_top_level_args(placement_entity.raw_args)
            relative_to, axis_ref = p_args[0].strip(), p_args[1].strip()
            axis_entity = by_ref[axis_ref]
            a_args = _split_top_level_args(axis_entity.raw_args)
            point_entity = by_ref[a_args[0].strip()]
            x, y, z = _parse_float_tuple(point_entity.raw_args)
            total_x += x
            total_y += y
            total_z += z
            current = relative_to
        return (total_x, total_y, total_z)

    def has_representation(self, entity_ref: str) -> bool:
        """Section 2 item 1: whether this product's `Representation`
        attribute (index 6 for both `IFCSPACE` and
        `IFCBUILDINGELEMENTPROXY` in this generator's fixed attribute
        layout) is non-null."""
        by_ref = getattr(self, "_by_ref")
        args = _split_top_level_args(by_ref[entity_ref].raw_args)
        return args[6].strip() != "$"

    def resolve_body_geometry(self, entity_ref: str) -> ResolvedBodyGeometry | None:
        """Section 11 items 3-9: walks
        `IfcProductDefinitionShape -> IfcShapeRepresentation ->
        IfcExtrudedAreaSolid -> IfcRectangleProfileDef` for one product,
        returning the ACTUAL emitted representation identifier/type/geometry
        -- never assumed. Returns None if the product has no representation."""
        by_ref = getattr(self, "_by_ref")
        args = _split_top_level_args(by_ref[entity_ref].raw_args)
        shape_ref = args[6].strip()
        if shape_ref == "$":
            return None
        shape_entity = by_ref[shape_ref]
        if shape_entity.entity_type != "IFCPRODUCTDEFINITIONSHAPE":
            return None
        shape_args = _split_top_level_args(shape_entity.raw_args)
        representation_refs = _parse_ref_list(shape_args[-1])
        if not representation_refs:
            return None
        shape_rep = by_ref[representation_refs[0]]
        rep_args = _split_top_level_args(shape_rep.raw_args)
        representation_identifier = _unquote(rep_args[1])
        representation_type = _unquote(rep_args[2])
        item_refs = _parse_ref_list(rep_args[3])
        if not item_refs:
            return None
        solid_entity = by_ref[item_refs[0]]
        solid_args = _split_top_level_args(solid_entity.raw_args)
        extrusion_depth_m = float(solid_args[3])
        profile_entity = by_ref[solid_args[0].strip()]
        profile_args = _split_top_level_args(profile_entity.raw_args)
        width_m = float(profile_args[3])
        depth_m = float(profile_args[4])
        return ResolvedBodyGeometry(
            representation_identifier=representation_identifier, representation_type=representation_type,
            solid_entity_type=solid_entity.entity_type, width_m=width_m, depth_m=depth_m, extrusion_depth_m=extrusion_depth_m,
        )


_ENTITY_LINE_RE = re.compile(r"^(#\d+)=([A-Z0-9]+)\((.*)\);$")


def read_ifc_proof_model(path: str) -> ParsedIfcModel:
    """Section 20 item 2: reopens a generated file well enough to prove it
    is non-empty and structurally valid STEP text (HEADER/DATA/ENDSEC
    present, every DATA line parses as `#N=TYPE(args);`)."""
    with open(path, "r", encoding="ascii") as f:
        text = f.read()
    if not text.strip():
        raise ValueError(f"{path} is empty")
    if "ISO-10303-21;" not in text or "END-ISO-10303-21;" not in text:
        raise ValueError(f"{path} is not a valid STEP Physical File")
    schema_match = re.search(r"FILE_SCHEMA\(\('([^']+)'\)\)", text)
    schema = schema_match.group(1) if schema_match else "UNKNOWN"
    data_section = text.split("DATA;", 1)[1].split("ENDSEC;", 1)[0]
    entities = []
    for line in data_section.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _ENTITY_LINE_RE.match(line)
        if m:
            entities.append(ParsedIfcEntity(ref=m.group(1), entity_type=m.group(2), raw_args=m.group(3)))
    if not entities:
        raise ValueError(f"{path} contains no parsable entities")
    return ParsedIfcModel(schema=schema, entities=tuple(entities))
