/**
 * MRT Pharma — 3D Asset Domain (core types).
 *
 * GOVERNING DOCTRINE (see MRT_PHARMA_3D_ASSET_ARCHITECTURE_REPORT.md):
 *   ENGINEERING ASSET DEFINITION → SPATIAL ASSET INSTANCE → GEOMETRY REPRESENTATION
 *   → BENTLEY VIEWPORT OVERLAY → SIMULATION/ENGINEERING/ECONOMIC CONSUMERS
 *
 * The 3D object REPRESENTS the engineering asset. It never becomes the
 * authoritative source of engineering truth (manufacturer, capacity, CapEx,
 * simulation behavior, etc.) — that always comes from the engineering/catalog
 * layer, referenced (not duplicated) from here.
 *
 * Three separate identities are always kept distinct:
 *   1. ENGINEERING IDENTITY  → AssetDefinition.assetDefinitionId
 *   2. SPATIAL INSTANCE ID    → AssetInstance.assetInstanceId
 *   3. GEOMETRY REP IDENTITY  → GeometryRepresentation.geometryRepresentationId
 * A geometry representation may be shared by many engineering definitions.
 *
 * These are pure, serializable domain types — NO Bentley runtime objects
 * (Viewport, GraphicBuilder, Decorator) ever appear here.
 */

// ---------------------------------------------------------------------------
// Classification
// ---------------------------------------------------------------------------

/** Broad asset class (what kind of thing this is). */
export type AssetClass =
    | 'IMAGING'
    | 'RADIOPHARMACY_PRODUCTION'
    | 'PATIENT_CLINICAL'
    | 'ROOM_BUILDING'
    | 'MRT'
    | 'LOGISTICS'

/** Specific asset family (drives geometry-family compatibility). */
export type AssetFamily =
    // IMAGING
    | 'PET_CT_SCANNER'
    | 'PET_MR_SCANNER'
    | 'SPECT_CT_SCANNER'
    | 'GAMMA_CAMERA'
    // RADIOPHARMACY / PRODUCTION
    | 'CYCLOTRON'
    | 'SYNTHESIS_MODULE'
    | 'HOT_CELL'
    | 'DOSE_CALIBRATOR'
    | 'DISPENSING_UNIT'
    | 'RADIOPHARMACY_WORKCELL'
    // PATIENT / CLINICAL
    | 'INJECTION_CHAIR'
    | 'UPTAKE_CHAIR'
    | 'UPTAKE_BED'
    | 'PATIENT_BED'
    | 'STRETCHER'
    // ROOM / BUILDING
    | 'DOOR'
    | 'CONTROLLED_ACCESS_DOOR'
    | 'ELEVATOR'
    | 'PASS_THROUGH'
    | 'CLEAN_ROOM_INTERFACE'
    // MRT
    | 'MRT_GUIDEWAY_SEGMENT'
    | 'MRT_CARRIER'
    | 'MRT_ENDPOINT'
    | 'MRT_RADIOPHARMACY_VESTIBULE'
    | 'MRT_TRANSITION_SEGMENT'
    | 'MRT_VERTICAL_LIFT_SECTION'
    | 'MRT_JUNCTION'
    // LOGISTICS
    | 'LOGISTICS_ENDPOINT'
    | 'CLEAN_SUPPLY_ENDPOINT'
    | 'SPECIMEN_ENDPOINT'
    | 'LINEN_ENDPOINT'

/** Map of family → class, used for validation and grouping. */
export const ASSET_FAMILY_CLASS: Readonly<Record<AssetFamily, AssetClass>> = {
    PET_CT_SCANNER: 'IMAGING',
    PET_MR_SCANNER: 'IMAGING',
    SPECT_CT_SCANNER: 'IMAGING',
    GAMMA_CAMERA: 'IMAGING',
    CYCLOTRON: 'RADIOPHARMACY_PRODUCTION',
    SYNTHESIS_MODULE: 'RADIOPHARMACY_PRODUCTION',
    HOT_CELL: 'RADIOPHARMACY_PRODUCTION',
    DOSE_CALIBRATOR: 'RADIOPHARMACY_PRODUCTION',
    DISPENSING_UNIT: 'RADIOPHARMACY_PRODUCTION',
    RADIOPHARMACY_WORKCELL: 'RADIOPHARMACY_PRODUCTION',
    INJECTION_CHAIR: 'PATIENT_CLINICAL',
    UPTAKE_CHAIR: 'PATIENT_CLINICAL',
    UPTAKE_BED: 'PATIENT_CLINICAL',
    PATIENT_BED: 'PATIENT_CLINICAL',
    STRETCHER: 'PATIENT_CLINICAL',
    DOOR: 'ROOM_BUILDING',
    CONTROLLED_ACCESS_DOOR: 'ROOM_BUILDING',
    ELEVATOR: 'ROOM_BUILDING',
    PASS_THROUGH: 'ROOM_BUILDING',
    CLEAN_ROOM_INTERFACE: 'ROOM_BUILDING',
    MRT_GUIDEWAY_SEGMENT: 'MRT',
    MRT_CARRIER: 'MRT',
    MRT_ENDPOINT: 'MRT',
    MRT_RADIOPHARMACY_VESTIBULE: 'MRT',
    MRT_TRANSITION_SEGMENT: 'MRT',
    MRT_VERTICAL_LIFT_SECTION: 'MRT',
    MRT_JUNCTION: 'MRT',
    LOGISTICS_ENDPOINT: 'LOGISTICS',
    CLEAN_SUPPLY_ENDPOINT: 'LOGISTICS',
    SPECIMEN_ENDPOINT: 'LOGISTICS',
    LINEN_ENDPOINT: 'LOGISTICS',
}

// ---------------------------------------------------------------------------
// Dimensions & spatial transform
// ---------------------------------------------------------------------------

/** Canonical internal spatial unit for MRT Pharma 3D assets. */
export type SpatialUnit = 'METERS'

/** Provenance of a set of dimensions. */
export type DimensionProvenance =
    | 'CALIBRATED'
    | 'CATALOG'
    | 'GENERIC_ENGINEERING_PLACEHOLDER'
    | 'USER_DEFINED'
    | 'NOT_CALIBRATED'

/** Physical bounding dimensions (axis-aligned in the asset's local frame). */
export interface AssetDimensions {
    width: number // local X
    depth: number // local Y
    height: number // local Z
    unit: SpatialUnit
    provenance: DimensionProvenance
}

export interface SpatialPosition {
    x: number
    y: number
    z: number
}

/** Rotation in degrees. Yaw about Z, pitch about Y, roll about X. */
export interface SpatialRotation {
    yaw: number
    pitch: number
    roll: number
}

export interface SpatialScale {
    x: number
    y: number
    z: number
}

/** The coordinate space a transform/position is expressed in. */
export type CoordinateSpace = 'BENTLEY_WORLD_COORDINATES' | 'MODEL_LOCAL'

/** Deterministic placement of an instance. Position is in BENTLEY_WORLD_COORDINATES. */
export interface SpatialTransform {
    position: SpatialPosition
    rotation: SpatialRotation
    scale: SpatialScale
    coordinateSpace: CoordinateSpace
}

export const IDENTITY_SCALE: SpatialScale = { x: 1, y: 1, z: 1 }
export const ZERO_ROTATION: SpatialRotation = { yaw: 0, pitch: 0, roll: 0 }

// ---------------------------------------------------------------------------
// Geometry representation
// ---------------------------------------------------------------------------

export type GeometryRepresentationType =
    | 'GENERIC'
    | 'MANUFACTURER_SPECIFIC'
    | 'PARAMETRIC'
    | 'IMPORTED'
    | 'BENTLEY_NATIVE'

export type GeometrySourceFormat =
    | 'PARAMETRIC_BENTLEY_GRAPHICS' // built at runtime via GraphicBuilder
    | 'IFC'
    | 'RVT'
    | 'DGN'
    | 'IMODEL'
    | 'OBJ'
    | 'GLTF'
    | 'GLB'
    | 'FBX'
    | 'BENTLEY_COMPONENTS_CENTER'
    | 'NONE'

export type GeometrySource =
    | 'GENERATED_GENERIC'
    | 'MANUFACTURER_BIM_CAD'
    | 'BENTLEY_LIBRARY'
    | 'IMPORTED_EXTERNAL'
    | 'MRT_PHARMA'

export type GeometryRepresentationStatus =
    | 'AVAILABLE'
    | 'PLACEHOLDER'
    | 'NOT_CALIBRATED'
    | 'DEPRECATED'

export type LevelOfDetail = 'LOW' | 'MEDIUM' | 'HIGH'

/** Reusable visual representation metadata. Contains NO binary geometry. */
export interface GeometryRepresentation {
    geometryRepresentationId: string
    assetFamily: AssetFamily
    representationType: GeometryRepresentationType
    source: GeometrySource
    sourceFormat: GeometrySourceFormat
    nativeDimensions: AssetDimensions
    unit: SpatialUnit
    lod: LevelOfDetail
    manufacturerSpecific: boolean
    /** Free-text provenance/license note (never contains secrets). */
    provenance: string
    status: GeometryRepresentationStatus
}

// ---------------------------------------------------------------------------
// Connection points & clearance envelopes (architecture only)
// ---------------------------------------------------------------------------

export type ConnectionPointType =
    | 'SERVICE_FACE'
    | 'PATIENT_ENTRY'
    | 'MRT_ENDPOINT'
    | 'POWER_CONNECTION'
    | 'COOLING_CONNECTION'
    | 'MAINTENANCE_ACCESS'
    | 'GUIDEWAY_CONNECTION'

/** Named anchor on an asset representation (local coordinates, meters). */
export interface AssetConnectionPoint {
    name: string
    type: ConnectionPointType
    localPosition: SpatialPosition
}

export type EnvelopeType =
    | 'PHYSICAL_EQUIPMENT'
    | 'SERVICE_CLEARANCE'
    | 'MAINTENANCE_CLEARANCE'
    | 'PATIENT_ACCESS_CLEARANCE'
    | 'RADIATION_CONTROL_BOUNDARY'

export type EnvelopeProvenance = 'CALIBRATED' | 'CATALOG' | 'USER_DEFINED' | 'NOT_CALIBRATED'

export interface ClearanceEnvelope {
    type: EnvelopeType
    dimensions: AssetDimensions
    provenance: EnvelopeProvenance
}

// ---------------------------------------------------------------------------
// MRT-specific + generic capabilities (extensible, typed)
// ---------------------------------------------------------------------------

/**
 * Optional typed capability metadata. Kept open-ended per-key but each known
 * key is documented; unknown engineering values must reference the engineering
 * layer rather than being invented here.
 */
export interface AssetCapabilities {
    mrtEndpointRequired?: boolean
    mrtEndpointType?: string
    payloadClass?: string
    carrierCompatibility?: string[]
    deliverySide?: string
    controlledSpaceBoundary?: boolean
    radiopharmacyVestibuleRequired?: boolean
    guidewayConnectionPoint?: boolean
    connectionPoints?: AssetConnectionPoint[]
    clearanceEnvelopes?: ClearanceEnvelope[]
}

// ---------------------------------------------------------------------------
// Engineering / catalog linkage (reference, never duplicate)
// ---------------------------------------------------------------------------

/**
 * Reference to authoritative engineering/catalog data living OUTSIDE this
 * spatial domain. `resolved: false` means the reference is not yet wired to a
 * real engineering catalog entry — an explicit unresolved state, never
 * fabricated values.
 */
export interface EngineeringMetadataReference {
    /** e.g. a catalog id in the engineering layer, or a generic test marker. */
    catalogReference: string
    /** Whether this points at a real engineering catalog entry. */
    resolved: boolean
    /** Optional note describing where the authoritative data lives. */
    note?: string
}

export const GENERIC_MANUFACTURER = 'GENERIC'
export const NOT_APPLICABLE_MANUFACTURER = 'NOT_APPLICABLE'

/** Reusable engineering identity/type. Ten scanners of one model → one definition. */
export interface AssetDefinition {
    assetDefinitionId: string
    assetClass: AssetClass
    assetFamily: AssetFamily
    displayName: string
    /** GENERIC / NOT_APPLICABLE for generic definitions; a real name otherwise. */
    manufacturer: string
    model: string
    catalogReference: string
    engineeringMetadataReference: EngineeringMetadataReference
    defaultGeometryRepresentationId: string
    defaultDimensions: AssetDimensions
    capabilities: AssetCapabilities
}

// ---------------------------------------------------------------------------
// Spatial instance
// ---------------------------------------------------------------------------

/** Provenance of a spatial object (who owns it). */
export type SpatialSource =
    | 'BENTLEY_IMODEL'
    | 'MRT_PHARMA'
    | 'IMPORTED_EXTERNAL'
    | 'CATALOG'
    | 'GENERATED_GENERIC'

/** Installation / lifecycle state — never inferred from geometry visibility. */
export type AssetInstallationState =
    | 'CATALOG_ONLY'
    | 'AVAILABLE_FOR_PLACEMENT'
    | 'PLANNED'
    | 'PLACED'
    | 'INSTALLED'
    | 'EXISTING'
    | 'PROPOSED'
    | 'REMOVED'

export type RoomAssignmentState = 'NOT_ASSIGNED' | 'NOT_CALIBRATED' | 'ASSIGNED'

/** Association of an instance with project/building/floor/room. */
export interface RoomAssignment {
    state: RoomAssignmentState
    projectId?: string
    buildingId?: string
    floorId?: string
    roomId?: string
}

export const ROOM_NOT_ASSIGNED: RoomAssignment = { state: 'NOT_ASSIGNED' }

/**
 * Optional scenario/version provenance so instances can integrate with the
 * existing LOCKDOWN / What-If architecture without this domain owning a
 * competing scenario engine.
 */
export interface ScenarioProvenance {
    scenarioId?: string
    scenarioState?: 'LOCKDOWN' | 'WHAT_IF' | 'DRAFT'
    originScenarioId?: string
}

/** One physical placement of an asset in one project. Fully serializable. */
export interface AssetInstance {
    assetInstanceId: string
    assetDefinitionId: string
    projectId: string
    displayLabel: string
    geometryRepresentationId: string
    transform: SpatialTransform
    dimensions: AssetDimensions
    roomAssignment: RoomAssignment
    installationState: AssetInstallationState
    spatialSource: SpatialSource
    scenario?: ScenarioProvenance
    /** Optional provenance describing how this instance came to exist. */
    createdFrom?: string
}

// ---------------------------------------------------------------------------
// Resolution + validation result types
// ---------------------------------------------------------------------------

export type GeometryResolution =
    | { status: 'RESOLVED'; representation: GeometryRepresentation }
    | { status: 'GEOMETRY_NOT_AVAILABLE'; requestedId: string }

export interface ValidationError {
    field: string
    message: string
}

export type ValidationResult =
    | { ok: true }
    | { ok: false; errors: ValidationError[] }
