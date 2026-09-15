/**
 * clinicalLogisticsVestibule — EVI-MA-05 pure, Bentley-free CLINICAL LOGISTICS
 * VESTIBULE taxonomy + configuration + application-owned instance domain.
 *
 * DOCTRINE (authoritative — supersedes all earlier EVI-MA-05/05R vestibule
 * concepts):
 *
 *   - There is ONE reusable wall-integrated visual/spatial family,
 *     CLINICAL_LOGISTICS_VESTIBULE_V1. It is the controlled interface between a
 *     clinical/service room and the future automated transport infrastructure.
 *   - A SERVICE CLASS answers "WHAT CLINICAL LOGISTICS FUNCTION OCCURS HERE?"
 *     (Radiopharmacy, Pharmacy, Laboratory, Sterile/Clean Supply, Laundry/Linen).
 *   - A TRANSPORT PORT answers "HOW CAN PAYLOADS LEAVE OR ARRIVE?" — a distinct
 *     physical + logical interface on the vestibule's rear manifold behind the
 *     wall (MRT trunk stub, radiopharmaceutical-qualified PTS tube stub, etc.).
 *   - There is NOT one MRT vestibule + one PTS vestibule for the same service
 *     point. There is ONE clinical access vestibule → multiple permitted ports.
 *   - Nuclear / radiopharmaceutical PTS qualification is NEVER inherited
 *     automatically. Only the Radiopharmacy service class gets a
 *     RADIOPHARMACEUTICAL_QUALIFIED PTS port; Pharmacy/Laboratory get a
 *     CONVENTIONAL_CLINICAL PTS port.
 *
 * This module establishes the PHYSICAL INTERFACES ONLY. It contains NO hospital
 * transport routing, NO carrier/capsule animation, NO travel-time physics.
 * Those belong to Build 2.
 */

// ---------------------------------------------------------------------------
// Service-class taxonomy — origin/service nodes for future hospital logistics
// ---------------------------------------------------------------------------

/**
 * The clinical-logistics ORIGIN/SERVICE classes demonstrated by this build.
 * Extensible: optional future classes (CENTRAL_SUPPLY, MATERIALS_MANAGEMENT,
 * BLOOD_BANK, WASTE_SOILED_MATERIAL, KITCHEN_NUTRITION, ...) are intentionally
 * NOT modeled now but the taxonomy is open (see FUTURE_SERVICE_CLASSES).
 */
export type ServiceClass =
    | 'RADIOPHARMACY'
    | 'PHARMACY'
    | 'LABORATORY'
    | 'STERILE_CLEAN_SUPPLY'
    | 'LAUNDRY_LINEN'

/** The service classes fully configured for EVI-MA-05. */
export const SERVICE_CLASSES: readonly ServiceClass[] = [
    'RADIOPHARMACY',
    'PHARMACY',
    'LABORATORY',
    'STERILE_CLEAN_SUPPLY',
    'LAUNDRY_LINEN',
]

/**
 * Documented, NOT-yet-modeled future service classes. Kept as a string list only
 * so the taxonomy reads as extensible without over-building typed behavior now.
 */
export const FUTURE_SERVICE_CLASSES: readonly string[] = [
    'CENTRAL_SUPPLY',
    'MATERIALS_MANAGEMENT',
    'BLOOD_BANK',
    'WASTE_SOILED_MATERIAL',
    'KITCHEN_NUTRITION',
]

// ---------------------------------------------------------------------------
// EVI-MA-07 — the vestibule is a CANONICAL MRTway facility/logistics asset
// (NOT a UI-only special object, NOT manufacturer medical equipment like GE/IBA).
// ---------------------------------------------------------------------------

/** The canonical MRTway facility asset family for clinical logistics vestibules. */
export const MRTWAY_CLINICAL_LOGISTICS_VESTIBULE = 'MRTWAY_CLINICAL_LOGISTICS_VESTIBULE' as const

/** A canonical MRTway facility asset (owner MRTway Systems, not GE/IBA). */
export interface CanonicalMrtwayFacilityAsset {
    canonicalAssetId: typeof MRTWAY_CLINICAL_LOGISTICS_VESTIBULE
    family: 'CLINICAL_LOGISTICS_VESTIBULE'
    owner: 'MRTway Systems'
    visualFamily: typeof CLINICAL_LOGISTICS_VESTIBULE_VISUAL_FAMILY
    assetCategory: 'FACILITY_LOGISTICS_INTERFACE'
    displayName: 'Clinical Logistics Vestibule'
}

export const CANONICAL_CLINICAL_LOGISTICS_VESTIBULE_ASSET: CanonicalMrtwayFacilityAsset = {
    canonicalAssetId: MRTWAY_CLINICAL_LOGISTICS_VESTIBULE,
    family: 'CLINICAL_LOGISTICS_VESTIBULE',
    owner: 'MRTway Systems',
    visualFamily: 'CLINICAL_LOGISTICS_VESTIBULE_V1',
    assetCategory: 'FACILITY_LOGISTICS_INTERFACE',
    displayName: 'Clinical Logistics Vestibule',
}

/**
 * A canonical service CONFIGURATION derived from the ONE base facility family.
 * The configuration (service class + permitted ports) is INDEPENDENT of the
 * visual family — the same CLINICAL_LOGISTICS_VESTIBULE_V1 visual serves every
 * configuration.
 */
export interface CanonicalVestibuleConfig {
    canonicalConfigId: string
    canonicalAssetId: typeof MRTWAY_CLINICAL_LOGISTICS_VESTIBULE
    serviceClass: ServiceClass
    displayName: string
}

/** The canonical config id for a service class (e.g. MRTWAY_CLV_RADIOPHARMACY). */
export function canonicalVestibuleConfigId(serviceClass: ServiceClass): string {
    return `MRTWAY_CLV_${serviceClass}`
}

/** All canonical vestibule configurations (one per service class). */
export function canonicalVestibuleConfigs(): CanonicalVestibuleConfig[] {
    return SERVICE_CLASSES.map((serviceClass) => ({
        canonicalConfigId: canonicalVestibuleConfigId(serviceClass),
        canonicalAssetId: MRTWAY_CLINICAL_LOGISTICS_VESTIBULE,
        serviceClass,
        displayName: `${'Clinical Logistics Vestibule'} — ${serviceClassLabel(serviceClass)}`,
    }))
}

/** Human-readable label for a service class (front-face metadata / 2D marker). */
export function serviceClassLabel(serviceClass: ServiceClass): string {
    switch (serviceClass) {
        case 'RADIOPHARMACY': return 'Radiopharmacy'
        case 'PHARMACY': return 'Pharmacy'
        case 'LABORATORY': return 'Laboratory'
        case 'STERILE_CLEAN_SUPPLY': return 'Sterile / Clean Supply'
        case 'LAUNDRY_LINEN': return 'Laundry / Linen'
    }
}

// ---------------------------------------------------------------------------
// Transport-port taxonomy — HOW payloads leave/arrive (distinct from service)
// ---------------------------------------------------------------------------

/** The transport families a vestibule port may expose. */
export type TransportFamily = 'MRT' | 'PTS' | 'RTHS' | 'AGV_AMR'

/**
 * PTS qualification tiers. Radiopharmaceutical qualification is a DISTINCT,
 * never-auto-inherited capability — a conventional clinical PTS tube is NOT
 * radiopharmaceutical-qualified.
 */
export type PtsQualification = 'CONVENTIONAL_CLINICAL' | 'RADIOPHARMACEUTICAL_QUALIFIED'

/**
 * The MRT trunk configuration a service class expects. STANDARD for
 * radiopharmacy/pharmacy/lab/sterile; HEAVY_GENERAL for bulky laundry/linen.
 */
export type MrtConfiguration = 'STANDARD' | 'HEAVY_GENERAL'

/** A future automated-transport interface exposed at the rear manifold. */
export type PortStatus = 'FUTURE_NETWORK' | 'UNCONNECTED'

/**
 * A permitted transport port CONFIGURATION for a service class (the design-time
 * template). The concrete placed port (with world position/orientation) is a
 * `VestibuleTransportPort` on an instance.
 */
export interface PermittedPortConfig {
    transportFamily: TransportFamily
    /** Present only for PTS ports. */
    ptsQualification?: PtsQualification
    /** Present only for MRT ports. */
    mrtConfiguration?: MrtConfiguration
    /**
     * Whether this port is physically fabricated in THIS build (a real stub) or
     * only reserved for a later automated-logistics system (RTHS / AGV / AMR).
     */
    fabricatedThisBuild: boolean
}

/**
 * The permitted transport ports for each service class. This is the single
 * authoritative port-configuration policy.
 *
 * Rules encoded here (do NOT silently upgrade PTS qualification):
 *   - RADIOPHARMACY       → MRT (standard) + RADIOPHARMACEUTICAL_QUALIFIED PTS.
 *   - PHARMACY            → MRT (standard) + CONVENTIONAL_CLINICAL PTS.
 *   - LABORATORY          → MRT (standard) + CONVENTIONAL_CLINICAL PTS.
 *   - STERILE_CLEAN_SUPPLY→ MRT (standard) only now; RTHS reserved (not a small
 *                            PTS tube for bulky sterile payloads).
 *   - LAUNDRY_LINEN       → MRT (heavy/general) only now; AGV/AMR + RTHS reserved
 *                            (never a small conventional PTS tube for linen).
 */
export function permittedPortsForServiceClass(serviceClass: ServiceClass): PermittedPortConfig[] {
    switch (serviceClass) {
        case 'RADIOPHARMACY':
            return [
                { transportFamily: 'MRT', mrtConfiguration: 'STANDARD', fabricatedThisBuild: true },
                { transportFamily: 'PTS', ptsQualification: 'RADIOPHARMACEUTICAL_QUALIFIED', fabricatedThisBuild: true },
            ]
        case 'PHARMACY':
            return [
                { transportFamily: 'MRT', mrtConfiguration: 'STANDARD', fabricatedThisBuild: true },
                { transportFamily: 'PTS', ptsQualification: 'CONVENTIONAL_CLINICAL', fabricatedThisBuild: true },
            ]
        case 'LABORATORY':
            return [
                { transportFamily: 'MRT', mrtConfiguration: 'STANDARD', fabricatedThisBuild: true },
                { transportFamily: 'PTS', ptsQualification: 'CONVENTIONAL_CLINICAL', fabricatedThisBuild: true },
            ]
        case 'STERILE_CLEAN_SUPPLY':
            return [
                { transportFamily: 'MRT', mrtConfiguration: 'STANDARD', fabricatedThisBuild: true },
                // RTHS reserved for later; NOT a small PTS tube for bulky sterile.
                { transportFamily: 'RTHS', fabricatedThisBuild: false },
            ]
        case 'LAUNDRY_LINEN':
            return [
                { transportFamily: 'MRT', mrtConfiguration: 'HEAVY_GENERAL', fabricatedThisBuild: true },
                // Heavy AGV/AMR + RTHS reserved for later; NEVER a small PTS tube.
                { transportFamily: 'AGV_AMR', fabricatedThisBuild: false },
                { transportFamily: 'RTHS', fabricatedThisBuild: false },
            ]
    }
}

/** Typical payload description for a service class (metadata only). */
export function typicalPayloadForServiceClass(serviceClass: ServiceClass): string {
    switch (serviceClass) {
        case 'RADIOPHARMACY': return 'radiopharmaceutical product'
        case 'PHARMACY': return 'medications, IV bags, infusion / pharmacy items'
        case 'LABORATORY': return 'blood, specimens, laboratory samples'
        case 'STERILE_CLEAN_SUPPLY': return 'sterile instruments, sterile packs, clean supplies'
        case 'LAUNDRY_LINEN': return 'linen, textiles, bulky lightweight clinical logistics'
    }
}

/**
 * The Radiopharmacy upstream condition is ABSTRACTED — the cyclotron does NOT
 * connect to the vestibule with a physical duct. The vestibule input is simply
 * declared available (synthesis / purification / QC / dispensing are abstracted
 * away). This is a stable marker, never a routed connection.
 */
export const RADIOPHARMACEUTICAL_INPUT_CONDITION = 'RADIOPHARMACEUTICAL_PRODUCT_AVAILABLE_AT_VESTIBULE_INPUT' as const

// ---------------------------------------------------------------------------
// Geometry / world types (kept local + minimal so this stays Bentley-free)
// ---------------------------------------------------------------------------

export interface Vec2 { x: number; y: number }

/** The visual family every clinical logistics vestibule renders as. */
export const CLINICAL_LOGISTICS_VESTIBULE_VISUAL_FAMILY = 'CLINICAL_LOGISTICS_VESTIBULE_V1' as const

/** A wall-integrated pose for a vestibule (front face toward room interior). */
export interface VestibulePose {
    centerX: number
    centerY: number
    /** Floor Z (base). */
    zBase: number
    width: number
    depth: number
    height: number
    /** Yaw about vertical; orients the -Y front face against the chosen wall. */
    yaw: number
}

/**
 * The plane of the room-facing front access face (world). `normal` points INTO
 * the room (away from the wall), so it is the direction a user faces the
 * vestibule from. Purely descriptive; no Bentley dependency.
 */
export interface FrontFacePlane {
    pointX: number
    pointY: number
    pointZ: number
    normalX: number
    normalY: number
}

/** Which wall of the parent room the vestibule is integrated into. */
export type WallSide = 'X_MIN' | 'X_MAX' | 'Y_MIN' | 'Y_MAX'

/**
 * EVI-MA-05B — an explicit local wall coordinate frame for the selected wall,
 * so the wall-integrated pose derives unambiguously (not from yaw guesses).
 * `roomInwardNormal` points from the wall INTO the cyclotron room;
 * `wallOutwardNormal = -roomInwardNormal` points THROUGH the wall (behind it),
 * the direction all service-side transport geometry extends along. Persisted so
 * the SAME pose reconstructs after reload.
 */
export interface WallFrame {
    /** A point on the room-side wall plane (world XY at floor Z). */
    originX: number
    originY: number
    /** Unit tangent along the wall (world XY). */
    tangentX: number
    tangentY: number
    /** Unit normal pointing from the wall INTO the room (world XY). */
    roomInwardX: number
    roomInwardY: number
    /** Unit normal pointing THROUGH the wall away from the room (= -roomInward). */
    wallOutwardX: number
    wallOutwardY: number
}

/** A reference to the room wall the vestibule integrates into (BIM immutable). */
export interface WallReference {
    parentBimSpaceId: string
    wallSide: WallSide
    /** World length of the wall segment used (for clearance reasoning). */
    wallLength: number
    /** EVI-MA-05B — the explicit wall frame the pose derives from (persisted). */
    frame?: WallFrame
}

/**
 * Derive the explicit wall frame for a room-bounds wall side. `roomInwardNormal`
 * points into the room; `wallOutwardNormal` points through the wall. The origin
 * is the midpoint of the chosen wall segment (room-side plane).
 */
export function wallFrameForSide(footprint: readonly Vec2[], wallSide: WallSide): WallFrame | undefined {
    const b = boundsOfRing(footprint)
    if (!b) return undefined
    switch (wallSide) {
        // Room interior is toward -Y of a Y_MAX wall, +Y of a Y_MIN wall, etc.
        case 'Y_MAX': return { originX: b.cx, originY: b.maxY, tangentX: 1, tangentY: 0, roomInwardX: 0, roomInwardY: -1, wallOutwardX: 0, wallOutwardY: 1 }
        case 'Y_MIN': return { originX: b.cx, originY: b.minY, tangentX: 1, tangentY: 0, roomInwardX: 0, roomInwardY: 1, wallOutwardX: 0, wallOutwardY: -1 }
        case 'X_MAX': return { originX: b.maxX, originY: b.cy, tangentX: 0, tangentY: 1, roomInwardX: -1, roomInwardY: 0, wallOutwardX: 1, wallOutwardY: 0 }
        case 'X_MIN': return { originX: b.minX, originY: b.cy, tangentX: 0, tangentY: 1, roomInwardX: 1, roomInwardY: 0, wallOutwardX: -1, wallOutwardY: 0 }
    }
}

/**
 * The vestibule's wall relationship. The authoritative Bentley iModel wall is
 * NEVER cut/deleted/renamed; unless a genuine BIM opening exists the vestibule
 * only PROPOSES a penetration.
 */
export type WallRelationshipStatus = 'PROPOSED_WALL_PENETRATION' | 'EXISTING_BIM_OPENING'

/** An axis-aligned reserved volume (collision reservation) for the vestibule. */
export interface ReservedVolume {
    minX: number
    minY: number
    minZ: number
    maxX: number
    maxY: number
    maxZ: number
}

export type VestibuleLifecycle = 'DRAFT' | 'LOCKED'

// ---------------------------------------------------------------------------
// Transport ports (concrete, placed on an instance)
// ---------------------------------------------------------------------------

/** A cross-section descriptor for a transport port. */
export interface PortCrossSection {
    /** RECTANGULAR for MRT trunk; CIRCULAR for PTS tube. */
    shape: 'RECTANGULAR' | 'CIRCULAR'
    /** Rectangular OUTER extents (meters) — present for RECTANGULAR. */
    width?: number
    height?: number
    /** Tube OUTSIDE diameter (meters) — present for CIRCULAR. */
    diameter?: number
}

// ---------------------------------------------------------------------------
// HOLLOW passages + carrier clearance (supplemental EVI-MA-05A doctrine)
//
// Every transport branch is a carrier-TRAVERSABLE HOLLOW structure. We keep the
// OUTER (structural / collision) geometry SEPARATE from the INNER FREE (carrier-
// clearance) geometry. Carrier sizing is by EXPLICIT engineering clearance, NOT
// by visual appearance. The outer envelope is used for external collision; the
// inner free passage is used for carrier motion — they are different tests.
// ---------------------------------------------------------------------------

/** The free (carrier-traversable) INNER cross-section of a hollow passage. */
export interface InnerCrossSection {
    shape: 'RECTANGULAR' | 'CIRCULAR'
    /** Inner free width/height (meters) — RECTANGULAR. */
    freeWidth?: number
    freeHeight?: number
    /** Inner free bore diameter (meters) — CIRCULAR. */
    freeDiameter?: number
}

/** A carrier's outer moving envelope (the volume that must fit inside the bore). */
export interface CarrierEnvelope {
    kind: 'MRT_CARRIER' | 'PTS_PIG'
    /** MRT carrier rectangular moving envelope (meters). */
    width?: number
    height?: number
    /** PTS miniature carrier/pig outer diameter (meters). */
    diameter?: number
    /** The payload envelope the carrier must contain (informational). */
    payload?: {
        /** MRT payload (rectangular) or PTS vial (diameter). */
        width?: number
        height?: number
        diameter?: number
    }
}

/** Explicit engineering running clearances (meters) — never inferred visually. */
export interface CarrierClearance {
    /** MRT: per-side horizontal clearance. */
    side?: number
    /** MRT: per-side vertical clearance. */
    vertical?: number
    /** PTS: radial running clearance between pig OD and bore ID (per side). */
    radial?: number
}

// Explicit named engineering parameters. Representative planning values (NOT
// manufacturer-certified); the ARCHITECTURE (separate outer/inner + explicit
// clearance) is what matters — real calibrated values slot in unchanged.
/** MRT carrier moving envelope (meters). */
export const MRT_CARRIER_ENVELOPE = { width: 0.34, height: 0.34 } as const
/** MRT per-side clearances (meters). */
export const MRT_CLEARANCE_SIDE_M = 0.03
export const MRT_CLEARANCE_VERTICAL_M = 0.03
/** MRT structural wall thickness per side (meters). */
export const MRT_WALL_THICKNESS_M = 0.04
/** MRT payload envelope carried inside the MRT carrier (meters). */
export const MRT_PAYLOAD_ENVELOPE = { width: 0.26, height: 0.26 } as const

/** PTS shielded-vial payload envelope diameter (meters). */
export const PTS_VIAL_DIAMETER_M = 0.05
/** PTS miniature carrier / pig outer diameter (meters). */
export const PTS_PIG_DIAMETER_M = 0.09
/** PTS radial running clearance between pig OD and bore ID, per side (meters). */
export const PTS_RADIAL_CLEARANCE_M = 0.008
/** PTS tube wall thickness (meters). */
export const PTS_WALL_THICKNESS_M = 0.012

/** MRT inner free rectangular cross-section from carrier + explicit clearance. */
export function mrtInnerFreeCrossSection(): InnerCrossSection {
    return {
        shape: 'RECTANGULAR',
        freeWidth: MRT_CARRIER_ENVELOPE.width + 2 * MRT_CLEARANCE_SIDE_M,
        freeHeight: MRT_CARRIER_ENVELOPE.height + 2 * MRT_CLEARANCE_VERTICAL_M,
    }
}

/** MRT outer structural cross-section = inner free + wall thickness per side. */
export function mrtOuterCrossSection(inner = mrtInnerFreeCrossSection()): { width: number; height: number } {
    return {
        width: (inner.freeWidth ?? 0) + 2 * MRT_WALL_THICKNESS_M,
        height: (inner.freeHeight ?? 0) + 2 * MRT_WALL_THICKNESS_M,
    }
}

/** PTS inner bore diameter = pig OD + 2 * radial running clearance. */
export function ptsInnerBoreDiameter(): number {
    return PTS_PIG_DIAMETER_M + 2 * PTS_RADIAL_CLEARANCE_M
}

/** PTS tube outside diameter = inner bore + 2 * wall thickness. */
export function ptsOutsideDiameter(innerBore = ptsInnerBoreDiameter()): number {
    return innerBore + 2 * PTS_WALL_THICKNESS_M
}

/**
 * A concrete transport interface placed on a vestibule instance's rear manifold.
 * This build creates only SHORT STUBS with UNCONNECTED / FUTURE_NETWORK status —
 * no hospital-wide routing, no animation. The port carries BOTH the outer
 * (structural/collision) cross-section AND the inner free (carrier-clearance)
 * cross-section, the carrier envelope, the explicit clearance, and the carrier
 * motion centerline — the seam future transport physics uses (INNER geometry).
 */
export interface VestibuleTransportPort {
    portId: string
    vestibuleInstanceId: string
    transportFamily: TransportFamily
    /** Present only for PTS ports (never auto-upgraded to nuclear). */
    ptsQualification?: PtsQualification
    /** Present only for MRT ports. */
    mrtConfiguration?: MrtConfiguration
    /** World position of the port end face. */
    position: { x: number; y: number; z: number }
    /** Unit orientation the port faces (into the behind-wall service space). */
    orientation: { x: number; y: number; z: number }
    /** OUTER (structural/collision) cross-section. */
    crossSection: PortCrossSection
    /** INNER FREE (carrier-traversable) cross-section — the hollow passage. */
    innerCrossSection?: InnerCrossSection
    /** The carrier moving envelope this passage is sized to accept. */
    carrierEnvelope?: CarrierEnvelope
    /** The explicit engineering running clearance used to size the passage. */
    clearance?: CarrierClearance
    /** Two world points defining the carrier motion centerline (physics seam). */
    centerline?: { start: { x: number; y: number; z: number }; end: { x: number; y: number; z: number } }
    status: PortStatus
    /** False for reserved-for-later families (RTHS/AGV_AMR) not built now. */
    fabricated: boolean
}

/**
 * The vestibule's genuine HOLLOW internal transfer chamber — the physical volume
 * a payload/carrier passes through. Kept SEPARATE from the exterior housing:
 * internal free W/H/D differ from the housing extents by the shielded wall
 * thickness. NOT a solid block.
 */
export interface VestibuleInternalChamber {
    /** Exterior housing extents (meters). */
    housingWidth: number
    housingHeight: number
    housingDepth: number
    /** Shield/wall thickness applied on each side (meters). */
    wallThickness: number
    /** Internal FREE dimensions the carrier/payload traverses (meters). */
    internalFreeWidth: number
    internalFreeHeight: number
    internalFreeDepth: number
}

/** Shield/wall thickness of the vestibule housing (meters). */
export const VESTIBULE_WALL_THICKNESS_M = 0.08

/**
 * Derive the hollow internal transfer chamber from the housing (pose) extents.
 * The internal free volume is the housing minus the shielded wall on each side,
 * floored at a positive minimum so the chamber is always genuinely hollow.
 */
export function vestibuleInternalChamber(pose: VestibulePose, wallThickness = VESTIBULE_WALL_THICKNESS_M): VestibuleInternalChamber {
    const housingWidth = pose.width
    const housingHeight = pose.height
    const housingDepth = pose.depth
    const minFree = 0.05
    return {
        housingWidth,
        housingHeight,
        housingDepth,
        wallThickness,
        internalFreeWidth: Math.max(housingWidth - 2 * wallThickness, minFree),
        internalFreeHeight: Math.max(housingHeight - 2 * wallThickness, minFree),
        internalFreeDepth: Math.max(housingDepth - 2 * wallThickness, minFree),
    }
}

// ---------------------------------------------------------------------------
// Application-owned instance
// ---------------------------------------------------------------------------

/**
 * One application-owned CLINICAL LOGISTICS VESTIBULE instance. Independent
 * identity — even though many instances share the same visual family, each has
 * its own id, service class, parent room, pose, ports, visibility and lifecycle.
 * Serializable + safe to persist (no mesh, no secrets).
 */
export interface ClinicalLogisticsVestibuleInstance {
    vestibuleInstanceId: string
    iModelId: string
    /** EVI-MA-07 — canonical MRTway facility asset id (MRTWAY_CLINICAL_LOGISTICS_VESTIBULE). */
    canonicalAssetId: typeof MRTWAY_CLINICAL_LOGISTICS_VESTIBULE
    /** EVI-MA-07 — canonical service config id (e.g. MRTWAY_CLV_RADIOPHARMACY). */
    canonicalConfigId: string
    serviceClass: ServiceClass
    parentBimSpaceId: string
    /** The clinical context (e.g. the cyclotron/radiopharmacy room) this serves. */
    sourceClinicalContextId?: string
    displayLabel: string
    visualFamily: typeof CLINICAL_LOGISTICS_VESTIBULE_VISUAL_FAMILY
    wallReference: WallReference
    pose: VestibulePose
    frontFacePlane: FrontFacePlane
    reservedVolume: ReservedVolume
    /** View-only per-instance visibility (default visible when absent). */
    hidden?: boolean
    lifecycleState: VestibuleLifecycle
    wallRelationshipStatus: WallRelationshipStatus
    transportPorts: VestibuleTransportPort[]
}

// ---------------------------------------------------------------------------
// Wall placement (pure) — WALL-INTEGRATED, never room-centroid
// ---------------------------------------------------------------------------

function boundsOfRing(ring: readonly Vec2[]): { minX: number; minY: number; maxX: number; maxY: number; cx: number; cy: number } | undefined {
    if (ring.length < 3) return undefined
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    for (const p of ring) {
        if (!Number.isFinite(p.x) || !Number.isFinite(p.y)) continue
        if (p.x < minX) minX = p.x; if (p.x > maxX) maxX = p.x
        if (p.y < minY) minY = p.y; if (p.y > maxY) maxY = p.y
    }
    if (!Number.isFinite(minX)) return undefined
    return { minX, minY, maxX, maxY, cx: (minX + maxX) / 2, cy: (minY + maxY) / 2 }
}

/** A wall-placement candidate for a room. */
export interface WallCandidate {
    wallSide: WallSide
    /** Uninterrupted length of the wall segment (meters). */
    wallLength: number
    /** World center of the wall segment. */
    centerX: number
    centerY: number
}

/**
 * Enumerate the four axis-aligned wall candidates of a room footprint bounds,
 * longest first. WALL-INTEGRATED placement chooses one of these — NEVER the room
 * centroid. Deterministic (ties break by a stable wall-side order).
 */
export function enumerateWallCandidates(footprint: readonly Vec2[]): WallCandidate[] {
    const b = boundsOfRing(footprint)
    if (!b) return []
    const wX = b.maxX - b.minX
    const wY = b.maxY - b.minY
    const order: WallSide[] = ['X_MIN', 'X_MAX', 'Y_MIN', 'Y_MAX']
    const cands: WallCandidate[] = [
        { wallSide: 'X_MIN', wallLength: wY, centerX: b.minX, centerY: b.cy },
        { wallSide: 'X_MAX', wallLength: wY, centerX: b.maxX, centerY: b.cy },
        { wallSide: 'Y_MIN', wallLength: wX, centerX: b.cx, centerY: b.minY },
        { wallSide: 'Y_MAX', wallLength: wX, centerX: b.cx, centerY: b.maxY },
    ]
    return cands.sort((a, c) => (c.wallLength - a.wallLength) || (order.indexOf(a.wallSide) - order.indexOf(c.wallSide)))
}

/** Minimum uninterrupted wall width to host a vestibule (meters). */
export const MIN_VESTIBULE_WALL_WIDTH_M = 1.4
/** Minimum room floor-to-ceiling height to host a vestibule (meters). */
export const MIN_VESTIBULE_WALL_HEIGHT_M = 2.0

/**
 * Seed a WALL-INTEGRATED vestibule pose against the chosen wall. The front
 * access face hugs the wall plane and faces INTO the room; the rear manifold
 * extends toward (and, as a proposed penetration, through) the wall. The pose
 * is NOT the room centroid. Yaw orients the local -Y front face toward the room
 * interior for the chosen wall side.
 */
export function seedWallIntegratedPose(input: {
    footprint: readonly Vec2[]
    zLow: number
    zHigh: number
    wallSide: WallSide
    width?: number
    depth?: number
    height?: number
}): VestibulePose | undefined {
    const frame = wallFrameForSide(input.footprint, input.wallSide)
    if (!frame) return undefined
    const width = input.width ?? 1.2
    const depth = input.depth ?? 0.9
    const roomH = Math.max(input.zHigh - input.zLow, MIN_VESTIBULE_WALL_HEIGHT_M)
    const height = Math.min(input.height ?? 2.0, roomH - 0.1)
    // EVI-MA-05B — WALL-INTEGRATED (ATM-like): the FRONT access face is flush
    // with the room-side wall plane and the body extends OUTWARD (behind the
    // wall) along wallOutwardNormal. So the pose center sits depth/2 BEHIND the
    // wall plane: center = wallOrigin + wallOutward * (depth/2). Only the shallow
    // fascia/door (drawn slightly forward of the front face) projects into the
    // room; the housing rear + sleeve + manifold + MRT/PTS ports are behind the
    // wall. (Previously the center sat depth/2 INSIDE the room, so the whole
    // assembly floated as a freestanding box in the cyclotron room — Defect A.)
    const centerX = frame.originX + frame.wallOutwardX * (depth / 2)
    const centerY = frame.originY + frame.wallOutwardY * (depth / 2)
    // Yaw orients the local -Y front face along roomInwardNormal. Rotating (0,-1)
    // by yaw gives (sin yaw, -cos yaw); set equal to (roomInwardX, roomInwardY).
    const yaw = Math.atan2(frame.roomInwardX, -frame.roomInwardY)
    return { centerX, centerY, zBase: input.zLow, width, depth, height, yaw }
}

/** Compute the room-facing front-face plane from a wall-integrated pose. */
export function frontFacePlaneFromPose(pose: VestibulePose): FrontFacePlane {
    // The local front face is at -Y (before yaw); its outward normal is the
    // local -Y unit vector rotated by yaw. Rotating (0,-1) by yaw gives
    // (sin yaw, -cos yaw). The face midpoint is the center shifted by depth/2
    // along that outward normal.
    const c = Math.cos(pose.yaw), s = Math.sin(pose.yaw)
    const normalX = s
    const normalY = -c
    const halfD = pose.depth / 2
    return {
        pointX: pose.centerX + normalX * halfD,
        pointY: pose.centerY + normalY * halfD,
        pointZ: pose.zBase + pose.height / 2,
        normalX,
        normalY,
    }
}

/**
 * Axis-aligned reserved volume for a wall-integrated pose (yaw-aware bounds).
 *
 * EVI-MA-05B — this is the ROOM-SIDE ACCESS occupancy used for equipment
 * collision: only the SHALLOW slab from the front-face (wall) plane projecting
 * `roomSideDepth` INTO the room (fascia/door/handle/HMI clearance). It does NOT
 * include the behind-wall sleeve/manifold/ports — those may cross the wall as a
 * PROPOSED_WALL_PENETRATION and must not register as an ordinary collision (§9).
 * Full width, full height, but only the room-side depth toward roomInwardNormal.
 */
export function reservedVolumeFromPose(pose: VestibulePose, roomSideDepth = 0.35): ReservedVolume {
    // Front face plane (flush with the wall) + a shallow projection into the room
    // along the room-inward normal (local -Y rotated by yaw = (sin, -cos)).
    const c = Math.cos(pose.yaw), s = Math.sin(pose.yaw)
    const inwardX = s, inwardY = -c
    const front = frontFacePlaneFromPose(pose)
    const hw = pose.width / 2
    // Tangent along the wall (perpendicular to inward) = (cos, sin).
    const tanX = c, tanY = s
    // The room-side slab spans [front .. front + inward*roomSideDepth] and
    // ±hw along the wall tangent from the front-face midpoint.
    const corners = [
        { x: front.pointX + tanX * hw, y: front.pointY + tanY * hw },
        { x: front.pointX - tanX * hw, y: front.pointY - tanY * hw },
        { x: front.pointX + tanX * hw + inwardX * roomSideDepth, y: front.pointY + tanY * hw + inwardY * roomSideDepth },
        { x: front.pointX - tanX * hw + inwardX * roomSideDepth, y: front.pointY - tanY * hw + inwardY * roomSideDepth },
    ]
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    for (const p of corners) {
        minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x)
        minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y)
    }
    return { minX, minY, minZ: pose.zBase, maxX, maxY, maxZ: pose.zBase + pose.height }
}

/**
 * The FULL occupied volume (room-side access + behind-wall assembly), for
 * reference/diagnostics only. NOT used for room-side equipment collision.
 */
export function fullOccupiedVolumeFromPose(pose: VestibulePose): ReservedVolume {
    const hw = pose.width / 2, hd = pose.depth / 2
    const c = Math.cos(pose.yaw), s = Math.sin(pose.yaw)
    const corners = [
        { x: -hw, y: -hd }, { x: hw, y: -hd }, { x: hw, y: hd }, { x: -hw, y: hd },
    ].map((q) => ({ x: pose.centerX + q.x * c - q.y * s, y: pose.centerY + q.x * s + q.y * c }))
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    for (const p of corners) {
        minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x)
        minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y)
    }
    return { minX, minY, minZ: pose.zBase, maxX, maxY, maxZ: pose.zBase + pose.height }
}

// ---------------------------------------------------------------------------
// Port construction (pure) — short stubs only, UNCONNECTED
// ---------------------------------------------------------------------------

/** Which rear branches are physically fabricated for a service class. */
export function vestibulePortRenderOptions(serviceClass: ServiceClass): { mrt: boolean; mrtHeavy: boolean; pts: boolean } {
    const permitted = permittedPortsForServiceClass(serviceClass)
    const mrt = permitted.find((p) => p.transportFamily === 'MRT' && p.fabricatedThisBuild)
    const pts = permitted.find((p) => p.transportFamily === 'PTS' && p.fabricatedThisBuild)
    return {
        mrt: !!mrt,
        mrtHeavy: mrt?.mrtConfiguration === 'HEAVY_GENERAL',
        pts: !!pts,
    }
}

/**
 * Build the concrete transport ports for a vestibule from its service-class
 * policy + pose. MRT ports carry a RECTANGULAR cross-section; PTS ports carry a
 * CIRCULAR cross-section. Reserved-for-later families are recorded as
 * non-fabricated ports (metadata) with no geometry. All ports are UNCONNECTED.
 */
export function buildTransportPortsForInstance(input: {
    vestibuleInstanceId: string
    serviceClass: ServiceClass
    pose: VestibulePose
}): VestibuleTransportPort[] {
    const { pose } = input
    // Behind-wall direction = the yawed local +Y (opposite the front-face normal).
    const c = Math.cos(pose.yaw), s = Math.sin(pose.yaw)
    const rearX = -s, rearY = c // local (0,+1) rotated by yaw
    const midZ = pose.zBase + pose.height * 0.57
    // A point behind the wall for stub end faces.
    const behind = (dist: number) => ({
        x: pose.centerX + rearX * (pose.depth / 2 + dist),
        y: pose.centerY + rearY * (pose.depth / 2 + dist),
        z: midZ,
    })
    const ports: VestibuleTransportPort[] = []
    let seq = 0
    for (const cfg of permittedPortsForServiceClass(input.serviceClass)) {
        seq += 1
        const portId = `${input.vestibuleInstanceId}:port:${cfg.transportFamily}:${seq}`
        if (cfg.transportFamily === 'MRT') {
            const heavy = cfg.mrtConfiguration === 'HEAVY_GENERAL'
            // Inner FREE cross-section from carrier + explicit clearance; outer
            // structural cross-section = inner + wall thickness per side. Heavy
            // general logistics scales both up (but stays a rectangular tract).
            const scale = heavy ? 1.6 : 1
            const inner: InnerCrossSection = {
                shape: 'RECTANGULAR',
                freeWidth: (MRT_CARRIER_ENVELOPE.width + 2 * MRT_CLEARANCE_SIDE_M) * scale,
                freeHeight: (MRT_CARRIER_ENVELOPE.height + 2 * MRT_CLEARANCE_VERTICAL_M) * scale,
            }
            const outer = mrtOuterCrossSection(inner)
            const portEnd = behind(heavy ? 1.1 : 0.9)
            ports.push({
                portId,
                vestibuleInstanceId: input.vestibuleInstanceId,
                transportFamily: 'MRT',
                mrtConfiguration: cfg.mrtConfiguration,
                position: portEnd,
                orientation: { x: rearX, y: rearY, z: 0 },
                // OUTER (structural/collision) cross-section.
                crossSection: { shape: 'RECTANGULAR', width: outer.width, height: outer.height },
                // INNER FREE (carrier-traversable) hollow passage.
                innerCrossSection: inner,
                carrierEnvelope: {
                    kind: 'MRT_CARRIER',
                    width: MRT_CARRIER_ENVELOPE.width * scale,
                    height: MRT_CARRIER_ENVELOPE.height * scale,
                    payload: { width: MRT_PAYLOAD_ENVELOPE.width * scale, height: MRT_PAYLOAD_ENVELOPE.height * scale },
                },
                clearance: { side: MRT_CLEARANCE_SIDE_M * scale, vertical: MRT_CLEARANCE_VERTICAL_M * scale },
                centerline: { start: behind(0), end: portEnd },
                status: 'UNCONNECTED',
                fabricated: cfg.fabricatedThisBuild,
            })
        } else if (cfg.transportFamily === 'PTS') {
            // Circular hollow bore sized for the miniature pig + running clearance;
            // OD = bore ID + 2 * wall. Substantially smaller than the MRT tract.
            const boreId = ptsInnerBoreDiameter()
            const od = ptsOutsideDiameter(boreId)
            const portEnd = behind(0.85)
            ports.push({
                portId,
                vestibuleInstanceId: input.vestibuleInstanceId,
                transportFamily: 'PTS',
                ptsQualification: cfg.ptsQualification, // NEVER auto-upgraded
                position: portEnd,
                orientation: { x: rearX, y: rearY, z: 0 },
                // OUTER = tube outside diameter (NOT the usable bore).
                crossSection: { shape: 'CIRCULAR', diameter: od },
                // INNER FREE = the traversable circular bore.
                innerCrossSection: { shape: 'CIRCULAR', freeDiameter: boreId },
                carrierEnvelope: {
                    kind: 'PTS_PIG',
                    diameter: PTS_PIG_DIAMETER_M,
                    payload: { diameter: PTS_VIAL_DIAMETER_M },
                },
                clearance: { radial: PTS_RADIAL_CLEARANCE_M },
                centerline: { start: behind(0), end: portEnd },
                status: 'UNCONNECTED',
                fabricated: cfg.fabricatedThisBuild,
            })
        } else {
            // RTHS / AGV_AMR — reserved for later; metadata port, no geometry.
            ports.push({
                portId,
                vestibuleInstanceId: input.vestibuleInstanceId,
                transportFamily: cfg.transportFamily,
                position: behind(0.7),
                orientation: { x: rearX, y: rearY, z: 0 },
                crossSection: { shape: 'RECTANGULAR', width: 0.8, height: 0.8 },
                status: 'FUTURE_NETWORK',
                fabricated: false,
            })
        }
    }
    return ports
}

// ---------------------------------------------------------------------------
// EVI-MA-06 — wall-slide drag (pure): slide ALONG the attached wall tangent only
// ---------------------------------------------------------------------------

/**
 * Slide a wall-integrated vestibule ALONG its attached wall to the wall-tangent
 * position nearest a target world point, clamped to the usable wall span. The
 * front face stays flush with the wall plane and the rear stays behind the wall
 * (the wall frame is authoritative — the vestibule can NEVER be pulled into the
 * middle of the room). Returns a new pose (same width/depth/height/yaw). Pure.
 *
 * candidateCenter = wallOrigin + wallTangent*s + wallOutwardNormal*(depth/2),
 * where s is the projection of (target - wallOrigin) onto wallTangent, clamped
 * to [-halfSpan+halfWidth, +halfSpan-halfWidth] so the body stays on the wall.
 */
export function slideVestibuleAlongWall(input: {
    pose: VestibulePose
    frame: WallFrame
    wallLength: number
    targetX: number
    targetY: number
}): VestibulePose {
    const { pose, frame } = input
    // Projection of the target onto the wall tangent, relative to the wall origin.
    const dx = input.targetX - frame.originX
    const dy = input.targetY - frame.originY
    let s = dx * frame.tangentX + dy * frame.tangentY
    // Clamp so the full width stays within the usable wall span (centered origin).
    const halfSpan = input.wallLength / 2
    const halfW = pose.width / 2
    const limit = Math.max(halfSpan - halfW, 0)
    if (s > limit) s = limit
    if (s < -limit) s = -limit
    const centerX = frame.originX + frame.tangentX * s + frame.wallOutwardX * (pose.depth / 2)
    const centerY = frame.originY + frame.tangentY * s + frame.wallOutwardY * (pose.depth / 2)
    return { ...pose, centerX, centerY }
}

/**
 * Evaluate whether a target world point is near enough to a DIFFERENT defensible
 * wall to warrant a deliberate wall-snap (explicit threshold + hysteresis). The
 * candidate wall must be within `snapDistance` of the target AND meaningfully
 * closer than the current wall (hysteresis) to avoid flicker. Returns the
 * candidate wall side, or undefined. Pure.
 */
export function evaluateWallSnap(input: {
    footprint: readonly Vec2[]
    currentWallSide: WallSide
    targetX: number
    targetY: number
    snapDistance?: number
    hysteresis?: number
}): WallSide | undefined {
    const snap = input.snapDistance ?? 0.5
    const hyst = input.hysteresis ?? 0.25
    const distToWall = (side: WallSide): number => {
        const f = wallFrameForSide(input.footprint, side)
        if (!f) return Infinity
        // Perpendicular distance from target to the wall plane (origin + tangent).
        const dx = input.targetX - f.originX, dy = input.targetY - f.originY
        // Component along roomInward is the perpendicular distance to the wall.
        return Math.abs(dx * f.roomInwardX + dy * f.roomInwardY)
    }
    const currentDist = distToWall(input.currentWallSide)
    let best: { side: WallSide; d: number } | undefined
    for (const side of ['X_MIN', 'X_MAX', 'Y_MIN', 'Y_MAX'] as WallSide[]) {
        if (side === input.currentWallSide) continue
        const d = distToWall(side)
        if (d <= snap && d < currentDist - hyst && (!best || d < best.d)) best = { side, d }
    }
    return best?.side
}

// ---------------------------------------------------------------------------
// Identity + factory
// ---------------------------------------------------------------------------

export function makeVestibuleInstanceId(iModelId: string, parentBimSpaceId: string, serviceClass: ServiceClass, seq: number): string {
    return `vestibule:${iModelId}:${parentBimSpaceId}:${serviceClass}:${seq}`
}

export type CreateVestibuleResult =
    | { ok: true; instance: ClinicalLogisticsVestibuleInstance }
    | { ok: false; reason: string }

/**
 * Create a DRAFT clinical logistics vestibule bound to a parent service room,
 * WALL-INTEGRATED against a defensible wall. Ports derive from the service-class
 * policy (radiopharmacy → MRT + radiopharmaceutical-qualified PTS; pharmacy/lab
 * → MRT + conventional PTS; sterile → MRT only; laundry → MRT heavy only). The
 * BIM wall is never modified — the relationship is a PROPOSED_WALL_PENETRATION.
 */
export function createVestibuleInstance(input: {
    iModelId: string
    serviceClass: ServiceClass
    parentBimSpaceId: string
    sourceClinicalContextId?: string
    footprint: readonly Vec2[]
    zLow: number
    zHigh: number
    seq: number
    /** Optional explicit wall; otherwise the longest defensible wall is chosen. */
    wallSide?: WallSide
    displayLabelOverride?: string
}): CreateVestibuleResult {
    if (!input.iModelId) return { ok: false, reason: 'NO_IMODEL' }
    if (!input.parentBimSpaceId) return { ok: false, reason: 'NO_PARENT_ROOM' }
    const roomH = input.zHigh - input.zLow
    if (!(roomH >= MIN_VESTIBULE_WALL_HEIGHT_M - 1e-6)) return { ok: false, reason: 'ROOM_TOO_SHORT' }

    const candidates = enumerateWallCandidates(input.footprint)
    const defensible = candidates.filter((w) => w.wallLength >= MIN_VESTIBULE_WALL_WIDTH_M)
    if (defensible.length === 0) return { ok: false, reason: 'NO_DEFENSIBLE_WALL' }
    const chosen = input.wallSide
        ? (defensible.find((w) => w.wallSide === input.wallSide) ?? defensible[0])
        : defensible[0]

    const pose = seedWallIntegratedPose({
        footprint: input.footprint, zLow: input.zLow, zHigh: input.zHigh, wallSide: chosen.wallSide,
    })
    if (!pose) return { ok: false, reason: 'POSE_SEED_FAILED' }

    const vestibuleInstanceId = makeVestibuleInstanceId(input.iModelId, input.parentBimSpaceId, input.serviceClass, input.seq)
    const transportPorts = buildTransportPortsForInstance({ vestibuleInstanceId, serviceClass: input.serviceClass, pose })

    const instance: ClinicalLogisticsVestibuleInstance = {
        vestibuleInstanceId,
        iModelId: input.iModelId,
        canonicalAssetId: MRTWAY_CLINICAL_LOGISTICS_VESTIBULE,
        canonicalConfigId: canonicalVestibuleConfigId(input.serviceClass),
        serviceClass: input.serviceClass,
        parentBimSpaceId: input.parentBimSpaceId,
        sourceClinicalContextId: input.sourceClinicalContextId,
        displayLabel: input.displayLabelOverride?.trim() || `${serviceClassLabel(input.serviceClass)} Logistics Vestibule`,
        visualFamily: CLINICAL_LOGISTICS_VESTIBULE_VISUAL_FAMILY,
        wallReference: {
            parentBimSpaceId: input.parentBimSpaceId,
            wallSide: chosen.wallSide,
            wallLength: chosen.wallLength,
            frame: wallFrameForSide(input.footprint, chosen.wallSide),
        },
        pose,
        frontFacePlane: frontFacePlaneFromPose(pose),
        reservedVolume: reservedVolumeFromPose(pose),
        lifecycleState: 'DRAFT',
        wallRelationshipStatus: 'PROPOSED_WALL_PENETRATION',
        transportPorts,
    }
    return { ok: true, instance }
}

// ---------------------------------------------------------------------------
// Safe persistence (localStorage; iModel-scoped) — mirrors equipmentInstance
// ---------------------------------------------------------------------------

const STORAGE_PREFIX = 'mrtpharma.vestibule.v1.'
const FORBIDDEN_KEYS = ['token', 'accessToken', 'refreshToken', 'authorization', 'Authorization', 'clientSecret', 'pkce', 'verifier', 'mesh', 'vertices', 'triangles']
const INSTANCE_KEYS = new Set([
    'vestibuleInstanceId', 'iModelId', 'canonicalAssetId', 'canonicalConfigId', 'serviceClass', 'parentBimSpaceId', 'sourceClinicalContextId',
    'displayLabel', 'visualFamily', 'wallReference', 'pose', 'frontFacePlane', 'reservedVolume',
    'hidden', 'lifecycleState', 'wallRelationshipStatus', 'transportPorts',
])

function isFiniteNum(v: unknown): v is number { return typeof v === 'number' && Number.isFinite(v) }

function isSafePose(p: unknown): p is VestibulePose {
    if (!p || typeof p !== 'object') return false
    const o = p as Record<string, unknown>
    return isFiniteNum(o.centerX) && isFiniteNum(o.centerY) && isFiniteNum(o.zBase)
        && isFiniteNum(o.width) && isFiniteNum(o.depth) && isFiniteNum(o.height) && isFiniteNum(o.yaw)
        && o.width as number > 0 && o.depth as number > 0 && o.height as number > 0
}

export function isSafeVestibulePayload(v: unknown): v is ClinicalLogisticsVestibuleInstance[] {
    if (!Array.isArray(v)) return false
    return v.every((a) => {
        if (!a || typeof a !== 'object') return false
        const keys = Object.keys(a as Record<string, unknown>)
        if (keys.some((k) => FORBIDDEN_KEYS.includes(k))) return false
        if (!keys.every((k) => INSTANCE_KEYS.has(k))) return false
        const o = a as ClinicalLogisticsVestibuleInstance
        if (typeof o.vestibuleInstanceId !== 'string' || typeof o.iModelId !== 'string') return false
        if (typeof o.parentBimSpaceId !== 'string') return false
        if (!SERVICE_CLASSES.includes(o.serviceClass)) return false
        if (o.visualFamily !== CLINICAL_LOGISTICS_VESTIBULE_VISUAL_FAMILY) return false
        if (!isSafePose(o.pose)) return false
        if (!Array.isArray(o.transportPorts)) return false
        return true
    })
}

function toSafeInstance(i: ClinicalLogisticsVestibuleInstance): ClinicalLogisticsVestibuleInstance {
    return {
        vestibuleInstanceId: i.vestibuleInstanceId,
        iModelId: i.iModelId,
        canonicalAssetId: i.canonicalAssetId,
        canonicalConfigId: i.canonicalConfigId,
        serviceClass: i.serviceClass,
        parentBimSpaceId: i.parentBimSpaceId,
        sourceClinicalContextId: i.sourceClinicalContextId,
        displayLabel: i.displayLabel,
        visualFamily: i.visualFamily,
        wallReference: { ...i.wallReference, frame: i.wallReference.frame ? { ...i.wallReference.frame } : undefined },
        pose: { ...i.pose },
        frontFacePlane: { ...i.frontFacePlane },
        reservedVolume: { ...i.reservedVolume },
        hidden: i.hidden,
        lifecycleState: i.lifecycleState,
        wallRelationshipStatus: i.wallRelationshipStatus,
        transportPorts: i.transportPorts.map((p) => ({
            ...p,
            position: { ...p.position },
            orientation: { ...p.orientation },
            crossSection: { ...p.crossSection },
            innerCrossSection: p.innerCrossSection ? { ...p.innerCrossSection } : undefined,
            carrierEnvelope: p.carrierEnvelope
                ? { ...p.carrierEnvelope, payload: p.carrierEnvelope.payload ? { ...p.carrierEnvelope.payload } : undefined }
                : undefined,
            clearance: p.clearance ? { ...p.clearance } : undefined,
            centerline: p.centerline ? { start: { ...p.centerline.start }, end: { ...p.centerline.end } } : undefined,
        })),
    }
}

export function toSafeVestibulePayload(instances: readonly ClinicalLogisticsVestibuleInstance[]): ClinicalLogisticsVestibuleInstance[] {
    return instances.map(toSafeInstance)
}

export function loadVestibuleInstances(iModelId: string, storage?: Pick<Storage, 'getItem'>): ClinicalLogisticsVestibuleInstance[] {
    const s = storage ?? (typeof window !== 'undefined' ? window.localStorage : undefined)
    if (!s || !iModelId) return []
    try {
        const raw = s.getItem(STORAGE_PREFIX + iModelId)
        if (!raw) return []
        const parsed = JSON.parse(raw) as unknown
        if (!isSafeVestibulePayload(parsed)) return []
        // EVI-MA-07 — backfill canonical identity on instances persisted before
        // canonicalization (derived deterministically from the service class).
        return parsed.map((v) => ({
            ...v,
            canonicalAssetId: v.canonicalAssetId ?? MRTWAY_CLINICAL_LOGISTICS_VESTIBULE,
            canonicalConfigId: v.canonicalConfigId ?? canonicalVestibuleConfigId(v.serviceClass),
        }))
    } catch { return [] }
}

export function saveVestibuleInstances(iModelId: string, instances: readonly ClinicalLogisticsVestibuleInstance[], storage?: Pick<Storage, 'setItem'>): void {
    const s = storage ?? (typeof window !== 'undefined' ? window.localStorage : undefined)
    if (!s || !iModelId) return
    try { s.setItem(STORAGE_PREFIX + iModelId, JSON.stringify(toSafeVestibulePayload(instances))) } catch { /* unavailable */ }
}

// ---------------------------------------------------------------------------
// Collision — the room-side reserved volume must not overlap other volumes
// ---------------------------------------------------------------------------

/** An axis-aligned 3D box for collision reasoning (meters). */
export interface Aabb {
    minX: number; minY: number; minZ: number
    maxX: number; maxY: number; maxZ: number
}

/** The vestibule's reserved volume is already an AABB. */
export function reservedVolumeAsAabb(rv: ReservedVolume): Aabb {
    return { minX: rv.minX, minY: rv.minY, minZ: rv.minZ, maxX: rv.maxX, maxY: rv.maxY, maxZ: rv.maxZ }
}

/**
 * Do two AABBs overlap beyond a small tolerance? Used to test the vestibule's
 * ROOM-SIDE reserved volume against equipment occupied volumes. The rear
 * manifold / wall sleeve deliberately may cross the wall (PROPOSED_WALL_PENETRATION)
 * and is NOT part of the reserved volume, so a legitimate wall penetration never
 * registers as a collision.
 */
export function aabbsOverlap(a: Aabb, b: Aabb, tolerance = 0.02): boolean {
    return (
        a.maxX - tolerance > b.minX && b.maxX - tolerance > a.minX &&
        a.maxY - tolerance > b.minY && b.maxY - tolerance > a.minY &&
        a.maxZ - tolerance > b.minZ && b.maxZ - tolerance > a.minZ
    )
}

/**
 * Test the vestibule's room-side reserved volume against a set of existing
 * occupied AABBs (equipment envelopes, other vestibules). Returns the first
 * conflicting id, or undefined when clear. Pure.
 */
export function findVestibuleCollision(
    reserved: ReservedVolume,
    existing: readonly { id: string; aabb: Aabb }[],
    tolerance = 0.02,
): string | undefined {
    const rv = reservedVolumeAsAabb(reserved)
    for (const e of existing) {
        if (aabbsOverlap(rv, e.aabb, tolerance)) return e.id
    }
    return undefined
}

// ---------------------------------------------------------------------------
// EVI-MA-05B — context pick (ray vs the vestibule's FULL occupied volume)
// ---------------------------------------------------------------------------

export interface VestibulePickRay {
    origin: [number, number, number]
    direction: [number, number, number]
}

/** Nearest positive ray-vs-AABB t (slab test), or undefined. Pure. */
export function rayIntersectAabb(ray: VestibulePickRay, box: Aabb): number | undefined {
    const lo = [box.minX, box.minY, box.minZ]
    const hi = [box.maxX, box.maxY, box.maxZ]
    let tmin = -Infinity, tmax = Infinity
    for (let i = 0; i < 3; i++) {
        const o = ray.origin[i], d = ray.direction[i]
        if (Math.abs(d) < 1e-12) {
            if (o < lo[i] || o > hi[i]) return undefined
        } else {
            let t1 = (lo[i] - o) / d, t2 = (hi[i] - o) / d
            if (t1 > t2) { const tmp = t1; t1 = t2; t2 = tmp }
            if (t1 > tmin) tmin = t1
            if (t2 < tmax) tmax = t2
            if (tmin > tmax) return undefined
        }
    }
    return tmin >= 0 ? tmin : (tmax >= 0 ? tmax : undefined)
}

/**
 * Resolve the vestibuleInstanceId a context pick targets. The pick tests the
 * FULL occupied volume (room-side access + behind-wall assembly) so a right
 * click on ANY visible component (fascia, door, HMI, sleeve, manifold, MRT
 * reducer/stub, PTS adapter/tube) resolves the ONE vestibuleInstanceId.
 * Selection-aware: prefer the currently selected vestibule when the ray hits it,
 * else the nearest. Hidden vestibules are excluded. Pure.
 */
export function pickVestibuleForContext(
    ray: VestibulePickRay,
    vestibules: readonly { vestibuleInstanceId: string; hidden?: boolean; pose: VestibulePose }[],
    selectedId: string | undefined,
): string | undefined {
    const occ = (p: VestibulePose): Aabb => reservedVolumeAsAabb(fullOccupiedVolumeFromPose(p))
    if (selectedId) {
        const sel = vestibules.find((v) => v.vestibuleInstanceId === selectedId && !v.hidden)
        if (sel && rayIntersectAabb(ray, occ(sel.pose)) !== undefined) return sel.vestibuleInstanceId
    }
    let bestId: string | undefined
    let bestT = Infinity
    for (const v of vestibules) {
        if (v.hidden) continue
        const t = rayIntersectAabb(ray, occ(v.pose))
        if (t !== undefined && t < bestT) { bestT = t; bestId = v.vestibuleInstanceId }
    }
    return bestId
}
