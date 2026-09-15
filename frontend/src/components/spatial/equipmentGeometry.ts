/**
 * equipmentGeometry — renderer-INDEPENDENT generic equipment geometry recipe.
 *
 * This is the single shared "geometry recipe" seam described by the visual
 * doctrine: ONE generic recognizable visual model per equipment family. It is
 * Bentley-FREE and fully testable in vitest. Both the Bentley decorators
 * (SpatialAssetDecorator for AssetInstance, ClinicalProgramDecorator for the
 * app-owned EquipmentAssetInstance) consume the SAME primitive parts emitted
 * here; the OpenUSD exporter authors the SAME conceptual primitives (body +
 * shielding + service cabinet / hot cell + workbench + dispensing / gantry +
 * bore + table) in Python.
 *
 * DOCTRINE (why this module exists):
 *   - CANONICAL ENGINEERING IDENTITY (e.g. GE HealthCare PETtrace 890) stays in
 *     the canonical catalog and NEVER derives from this geometry.
 *   - VISUAL REPRESENTATION IDENTITY (e.g. GENERIC_MEDICAL_CYCLOTRON) is what
 *     this module produces. Many exact canonical models map to ONE generic
 *     visual family.
 *   - These are LOW-LOD, REPRESENTATIVE planning proxies — recognizably a
 *     cyclotron / PET-CT / hot-cell, NOT manufacturer-certified CAD. All
 *     proportions derive parametrically from the instance pose/dimensions so
 *     future calibrated dimensions apply without changing the architecture.
 *
 * Coordinate space: BENTLEY_WORLD_COORDINATES. Parts are laid out centered on a
 * world pose; yaw rotates the layout about the vertical (Z) axis (the only
 * meaningful DOF for floor-placed equipment). Box parts carry their yaw+center
 * so the renderer rotates the 8 corners; cylinder endpoints are pre-rotated.
 */
import type { AssetInstance } from '../../domain/assets'
import type { AssetFamily } from '../../domain/assets/types'
import type { CanonicalEquipmentClass } from './canonicalEquipmentCatalog'
import {
    applyYaw,
    buildScannerPartsFromPose,
    type ScannerPartGeometry,
    type WorldBox,
    type WorldCylinder,
} from './scannerGeometry'

// ---------------------------------------------------------------------------
// Generic VISUAL families (visual identity — distinct from canonical identity)
// ---------------------------------------------------------------------------

/**
 * The generic recognizable visual model families surfaced by this build. Each
 * value is a stable VISUAL REPRESENTATION IDENTITY that many exact canonical
 * models may share (e.g. GE PETtrace 890 and IBA Cyclone KIUBE both render as
 * GENERIC_MEDICAL_CYCLOTRON_V1).
 */
export type EquipmentVisualFamily =
    | 'GENERIC_PET_CT_SCANNER_V1'
    | 'GENERIC_MEDICAL_CYCLOTRON_V1'
    | 'GENERIC_MEDICAL_CYCLOTRON_V2'
    | 'GENERIC_RADIOPHARMACY_HOTCELL_V1'
    | 'GENERIC_MRT_RADIOPHARMACY_VESTIBULE_V1'
    // EVI-MA-05 — the ONE reusable wall-integrated clinical logistics vestibule.
    | 'CLINICAL_LOGISTICS_VESTIBULE_V1'

/** Parts of the generic parametric representations (superset across families). */
export type EquipmentPart =
    // PET/CT
    | 'GANTRY'
    | 'BORE'
    | 'PATIENT_TABLE'
    | 'TABLE_BASE'
    // Cyclotron (V1 low-LOD)
    | 'CYCLOTRON_BODY'
    | 'CYCLOTRON_SHIELDING'
    | 'CYCLOTRON_SERVICE_CABINET'
    // Cyclotron (V2 medium-LOD) — material-role part names
    | 'CYC_LOWER_SHELL'
    | 'CYC_UPPER_SHELL'
    | 'CYC_BASE_RING'
    | 'CYC_FOOT'
    | 'CYC_ACCESS_PANEL'
    | 'CYC_PANEL_HANDLE'
    | 'CYC_SERVICE_COLUMN'
    | 'CYC_UPPER_MODULE'
    | 'CYC_CONDUIT'
    | 'CYC_CABINET'
    | 'CYC_CABINET_BASE'
    | 'CYC_CABINET_VENT'
    | 'CYC_CONTROL_SCREEN'
    | 'CYC_ESTOP'
    | 'CYC_BRAND_ACCENT'
    // Radiopharmacy / hot cell
    | 'HOT_CELL'
    | 'WORKBENCH'
    | 'DISPENSING'
    // MRT Radiopharmacy Vestibule (medium-LOD, EVI-MA-04 legacy)
    | 'VEST_HOUSING'
    | 'VEST_BASE'
    | 'VEST_ACCESS_PANEL'
    | 'VEST_TRANSFER_INTERFACE'
    | 'VEST_STATUS_LIGHT'
    | 'VEST_CONTROL_PANEL'
    | 'VEST_TRANSFER_THROAT'
    | 'VEST_BRAND_ACCENT'
    // EVI-MA-05 Clinical Logistics Vestibule (CLV_*) — wall-integrated (ATM-like)
    // FRONT CLINICAL ACCESS FACE (toward the room interior, local -Y):
    | 'CLV_WALL_FASCIA'          // wall-integrated fascia/frame flush with the wall
    | 'CLV_HOUSING'             // the recessed housing body behind the fascia
    | 'CLV_TRANSFER_DOOR'       // shielded/controlled transfer door
    | 'CLV_TRANSFER_APERTURE'   // inset transfer aperture/chamber
    | 'CLV_HANDLE'              // substantial handle/latch
    | 'CLV_HMI'                 // HMI/control display
    | 'CLV_STATUS_GREEN'        // green status indicator
    | 'CLV_STATUS_AMBER'        // amber status indicator
    | 'CLV_STATUS_RED'          // red fault/emergency indicator
    | 'CLV_ESTOP'               // emergency stop
    | 'CLV_SERVICE_PANEL'       // lower service/access panel
    | 'CLV_SERVICE_LABEL'       // restrained service-class label/accent
    | 'CLV_BASE'                // base / plinth
    // WALL PENETRATION + REAR MANIFOLD (behind the wall, local +Y):
    | 'CLV_WALL_SLEEVE'         // the section passing through the wall
    | 'CLV_REAR_MANIFOLD'       // internal handoff region behind the wall
    // MRT rear branch: large section -> planar rectangular reducer -> trunk stub:
    | 'CLV_MRT_MANIFOLD_SECTION' // large rectangular transfer section
    | 'CLV_MRT_REDUCER_FACE'     // one of the 4 sloping PLANAR trapezoidal faces
    | 'CLV_MRT_TRUNK_STUB'       // smaller standard MRT trunk stub
    | 'CLV_MRT_TRUNK_PORT'       // MRT_TRUNK_CONNECTION_PORT face (visual)
    // PTS rear branch: compact adapter -> CIRCULAR tube stub -> port:
    | 'CLV_PTS_ADAPTER'          // compact adapter from the manifold
    | 'CLV_PTS_TUBE_STUB'        // circular pneumatic-tube stub
    | 'CLV_PTS_PORT'             // PTS_CONNECTION_PORT face (visual)
    // EVI-MA-05A hollowness — dark INNER-VOID cues so cutaway reads as hollow:
    | 'CLV_CHAMBER_VOID'         // vestibule internal transfer chamber recess
    | 'CLV_MRT_INNER_VOID'       // MRT inner free rectangular passage (hollow)
    | 'CLV_PTS_INNER_BORE'       // PTS inner circular bore (hollow)
    // EVI-MA-07 — TWO unmistakable FRONT-FACE openings, framed around actual void:
    | 'CLV_MRT_OPENING_FRAME'    // large RECTANGULAR MRT opening frame (thin bars)
    | 'CLV_MRT_OPENING_VOID'     // the empty rectangular MRT opening interior
    | 'CLV_PTS_OPENING_RING'     // small CIRCULAR PTS opening ring (annulus)
    | 'CLV_PTS_OPENING_VOID'     // the empty circular PTS bore interior
    | 'CLV_MRT_COVER'            // thin rectangular MRT access cover (optional)
    | 'CLV_PTS_COVER'            // thin circular PTS access cover (optional)

/** A single primitive part expressed in world coordinates (box or cylinder). */
export type EquipmentPartGeometry = WorldBox<EquipmentPart> | WorldCylinder<EquipmentPart>

/**
 * EVI-MA-04 — the SINGLE material palette by part role (RGB), shared by both
 * decorators so materials never diverge. Differentiated (never a single cyan
 * block): off-white housings, medium/dark structural grays, near-black
 * vents/handles, neutral metallic, dark control screens, restrained red e-stop,
 * restrained green brand accent. Selection is an OUTLINE only (see the
 * decorators) — these fills are ALWAYS used regardless of selection.
 */
export const EQUIPMENT_PART_COLOR: Record<EquipmentPart, [number, number, number]> = {
    // PET/CT
    GANTRY: [226, 230, 236],
    BORE: [56, 66, 84],
    PATIENT_TABLE: [200, 206, 214],
    TABLE_BASE: [150, 158, 170],
    // Cyclotron V1 (legacy low-LOD)
    CYCLOTRON_BODY: [196, 204, 214],
    CYCLOTRON_SHIELDING: [120, 130, 146],
    CYCLOTRON_SERVICE_CABINET: [168, 176, 188],
    // Cyclotron V2 (medium-LOD)
    CYC_LOWER_SHELL: [214, 216, 210],       // warm off-white shielded shell
    CYC_UPPER_SHELL: [198, 202, 206],       // slightly different light gray
    CYC_BASE_RING: [86, 92, 100],           // dark structural base
    CYC_FOOT: [70, 74, 80],                 // near-black leveling feet
    CYC_ACCESS_PANEL: [206, 208, 202],      // panel face (off-white)
    CYC_PANEL_HANDLE: [52, 56, 62],         // dark handle/latch
    CYC_SERVICE_COLUMN: [150, 156, 164],    // metallic gray
    CYC_UPPER_MODULE: [176, 182, 190],      // light gray module
    CYC_CONDUIT: [60, 64, 70],              // dark conduit
    CYC_CABINET: [222, 224, 220],           // off-white enclosure
    CYC_CABINET_BASE: [80, 86, 94],         // dark base
    CYC_CABINET_VENT: [44, 48, 54],         // near-black vent slot
    CYC_CONTROL_SCREEN: [40, 52, 66],       // dark display face
    CYC_ESTOP: [196, 60, 52],               // restrained red e-stop
    CYC_BRAND_ACCENT: [78, 168, 120],       // restrained green accent
    // Radiopharmacy / hot cell
    HOT_CELL: [150, 160, 176],
    WORKBENCH: [206, 210, 216],
    DISPENSING: [176, 186, 200],
    // MRT Radiopharmacy Vestibule (EVI-MA-04 legacy)
    VEST_HOUSING: [216, 218, 214],          // off-white housing
    VEST_BASE: [82, 88, 96],                // dark base
    VEST_ACCESS_PANEL: [58, 62, 68],        // dark access panel
    VEST_TRANSFER_INTERFACE: [150, 156, 164], // metallic interface
    VEST_STATUS_LIGHT: [96, 200, 130],      // status light (green)
    VEST_CONTROL_PANEL: [46, 58, 72],       // dark control panel
    VEST_TRANSFER_THROAT: [70, 76, 84],     // dark transfer throat
    VEST_BRAND_ACCENT: [78, 168, 120],      // restrained MRTway accent
    // EVI-MA-05 Clinical Logistics Vestibule — restrained MRTway clinical palette,
    // deliberately DISTINCT from the cyclotron (muted sage housing, not cyan).
    CLV_WALL_FASCIA: [180, 190, 182],       // pale clinical fascia frame
    CLV_HOUSING: [178, 196, 182],           // muted sage / pale clinical green housing
    CLV_TRANSFER_DOOR: [166, 172, 178],     // stainless / metallic gray door
    CLV_TRANSFER_APERTURE: [40, 46, 52],    // dark inset chamber
    CLV_HANDLE: [96, 102, 110],             // metallic handle/latch
    CLV_HMI: [34, 40, 48],                  // dark charcoal HMI
    CLV_STATUS_GREEN: [86, 190, 120],       // green status
    CLV_STATUS_AMBER: [216, 170, 66],       // amber status
    CLV_STATUS_RED: [196, 66, 58],          // red fault/emergency
    CLV_ESTOP: [190, 58, 50],               // emergency stop
    CLV_SERVICE_PANEL: [150, 158, 150],     // lower service panel (muted)
    CLV_SERVICE_LABEL: [78, 168, 120],      // restrained service-class accent
    CLV_BASE: [72, 78, 84],                 // dark neutral base
    CLV_WALL_SLEEVE: [138, 146, 150],       // neutral wall sleeve
    CLV_REAR_MANIFOLD: [140, 148, 156],     // metallic / neutral gray manifold
    CLV_MRT_MANIFOLD_SECTION: [150, 158, 166], // large rectangular MRT section
    CLV_MRT_REDUCER_FACE: [132, 140, 148],  // planar reducer faces
    CLV_MRT_TRUNK_STUB: [120, 128, 136],    // MRT trunk stub
    CLV_MRT_TRUNK_PORT: [92, 100, 108],     // MRT trunk connection port face
    CLV_PTS_ADAPTER: [156, 162, 168],       // PTS compact adapter
    CLV_PTS_TUBE_STUB: [176, 182, 188],     // circular PTS tube (lighter metallic)
    CLV_PTS_PORT: [96, 104, 112],           // PTS connection port face
    // Inner-void cues — near-black so a cutaway reads the passages as hollow.
    CLV_CHAMBER_VOID: [24, 28, 32],         // vestibule transfer chamber recess
    CLV_MRT_INNER_VOID: [20, 24, 30],       // MRT inner free rectangular passage
    CLV_PTS_INNER_BORE: [18, 22, 28],       // PTS inner circular bore
    // EVI-MA-07 front-face openings — bright metallic frames around near-black void.
    CLV_MRT_OPENING_FRAME: [150, 158, 166], // rectangular opening frame (metallic)
    CLV_MRT_OPENING_VOID: [12, 14, 18],     // the empty rectangular MRT opening
    CLV_PTS_OPENING_RING: [150, 158, 166],  // circular opening ring (metallic)
    CLV_PTS_OPENING_VOID: [12, 14, 18],     // the empty circular PTS bore
    CLV_MRT_COVER: [176, 182, 188],         // thin MRT access cover
    CLV_PTS_COVER: [176, 182, 188],         // thin PTS access cover
}

/** The restrained selection OUTLINE color (edge only; never a fill override). */
export const EQUIPMENT_SELECTION_OUTLINE: [number, number, number] = [90, 200, 220]

/**
 * The authoritative pose + envelope an instance provides to the geometry recipe.
 * width = local X, depth = local Y, height = local Z. `center` is the world XY
 * center at the FLOOR (base) Z. yawRadians rotates about vertical.
 */
export interface EquipmentPose {
    center: [number, number, number]
    width: number
    depth: number
    height: number
    yawRadians: number
}

const DEG2RAD = Math.PI / 180

// ---------------------------------------------------------------------------
// Visual-family resolution (canonical identity → visual identity)
// ---------------------------------------------------------------------------

/**
 * Resolve the generic VISUAL family for an app-owned equipment instance from
 * its canonical class (+ optional spatial family). This mapping is many-to-one:
 * every canonical cyclotron model resolves to GENERIC_MEDICAL_CYCLOTRON_V1, etc.
 * It NEVER inspects manufacturer/model identity to pick geometry — geometry is
 * a family concern only. Returns undefined when no recognizable family exists
 * (e.g. GENERATOR has no spatial geometry family).
 */
export function resolveVisualFamilyForCanonical(input: {
    canonicalClass: CanonicalEquipmentClass
    assetFamily?: AssetFamily
}): EquipmentVisualFamily | undefined {
    switch (input.canonicalClass) {
        case 'CYCLOTRON':
            // EVI-MA-04 — upgraded medium-LOD cyclotron (recognizable machine,
            // ~20 differentiated components). Canonical identity is unchanged.
            return 'GENERIC_MEDICAL_CYCLOTRON_V2'
        case 'SCANNER':
            // Both PET/CT and SPECT/CT render as the recognizable scanner
            // gantry+bore+table representation in this build.
            return 'GENERIC_PET_CT_SCANNER_V1'
        case 'GENERATOR':
            // Radionuclide generator visual is DEFERRED (no recognizable
            // generator geometry exists yet; a generator carries no spatial
            // AssetFamily). It surfaces a recognizable radiopharmacy HOT CELL
            // only when explicitly bound to a hot-cell spatial family; a bare
            // GENERATOR (no family) is VISUAL_NOT_AVAILABLE, per the deferral.
            switch (input.assetFamily) {
                case 'HOT_CELL':
                case 'RADIOPHARMACY_WORKCELL':
                case 'DISPENSING_UNIT':
                    return 'GENERIC_RADIOPHARMACY_HOTCELL_V1'
                default:
                    return undefined
            }
        default:
            return undefined
    }
}

/**
 * Resolve the generic VISUAL family for a spatial AssetFamily (the fixture /
 * placement path where an AssetInstance carries a geometryRepresentationId that
 * maps to a family). Recognizable families only; others return undefined so the
 * caller can fall back to a plain envelope.
 */
export function resolveVisualFamilyForAssetFamily(family: AssetFamily): EquipmentVisualFamily | undefined {
    switch (family) {
        case 'PET_CT_SCANNER':
        case 'PET_MR_SCANNER':
        case 'SPECT_CT_SCANNER':
        case 'GAMMA_CAMERA':
            return 'GENERIC_PET_CT_SCANNER_V1'
        case 'CYCLOTRON':
            return 'GENERIC_MEDICAL_CYCLOTRON_V2'
        case 'MRT_RADIOPHARMACY_VESTIBULE':
            return 'GENERIC_MRT_RADIOPHARMACY_VESTIBULE_V1'
        case 'HOT_CELL':
        case 'RADIOPHARMACY_WORKCELL':
        case 'DISPENSING_UNIT':
            return 'GENERIC_RADIOPHARMACY_HOTCELL_V1'
        default:
            return undefined
    }
}

/**
 * Resolve the generic VISUAL family from a geometryRepresentationId. The generic
 * catalog uses GENERIC_PET_CT_SCANNER_V1 as the geometry representation id for
 * the scanner family; this keeps the fixture path (incl. the persisted GE
 * Discovery MI) resolving to recognizable PET/CT geometry automatically.
 */
export function resolveVisualFamilyForGeometryId(geometryRepresentationId: string): EquipmentVisualFamily | undefined {
    const id = geometryRepresentationId.toUpperCase()
    if (id.includes('VESTIBULE')) return 'GENERIC_MRT_RADIOPHARMACY_VESTIBULE_V1'
    if (id.includes('CYCLOTRON')) return 'GENERIC_MEDICAL_CYCLOTRON_V2'
    if (id.includes('HOTCELL') || id.includes('HOT_CELL') || id.includes('RADIOPHARMACY')) return 'GENERIC_RADIOPHARMACY_HOTCELL_V1'
    if (id.includes('PET_CT') || id.includes('PETCT') || id.includes('SCANNER') || id.includes('SPECT')) return 'GENERIC_PET_CT_SCANNER_V1'
    return undefined
}

// ---------------------------------------------------------------------------
// Family part builders (pure, deterministic, world coordinates)
// ---------------------------------------------------------------------------

/**
 * Build the recognizable parts for a given VISUAL family at a world pose. This
 * is the single dispatch both decorators use. Returns [] for an unknown family
 * so callers keep only the envelope (never a fabricated model).
 */
export function buildEquipmentParts(
    family: EquipmentVisualFamily,
    pose: EquipmentPose,
    options?: { vestibulePorts?: VestibulePortRenderOptions },
): EquipmentPartGeometry[] {
    switch (family) {
        case 'GENERIC_PET_CT_SCANNER_V1':
            return buildScannerPartsFromPose(pose) as EquipmentPartGeometry[]
        case 'GENERIC_MEDICAL_CYCLOTRON_V1':
            return buildCyclotronParts(pose)
        case 'GENERIC_MEDICAL_CYCLOTRON_V2':
            return buildCyclotronPartsV2(pose)
        case 'GENERIC_RADIOPHARMACY_HOTCELL_V1':
            return buildRadiopharmacyParts(pose)
        case 'GENERIC_MRT_RADIOPHARMACY_VESTIBULE_V1':
            return buildVestibuleParts(pose)
        case 'CLINICAL_LOGISTICS_VESTIBULE_V1':
            return buildClinicalLogisticsVestibuleParts(pose, options?.vestibulePorts)
        default:
            return []
    }
}

/**
 * Convenience: build parts for an AssetInstance via its geometryRepresentationId.
 * Falls back to the recognizable PET/CT scanner recipe when the id does not map
 * to a known family, so no previously-rendering instance ever disappears
 * (backward-compatible with the generic GENERIC_PET_CT_SCANNER_V1 fixtures).
 */
export function buildEquipmentPartsForInstance(inst: AssetInstance): EquipmentPartGeometry[] {
    const family = resolveVisualFamilyForGeometryId(inst.geometryRepresentationId) ?? 'GENERIC_PET_CT_SCANNER_V1'
    const p = inst.transform.position
    const s = inst.transform.scale
    const pose: EquipmentPose = {
        center: [p.x, p.y, p.z],
        width: inst.dimensions.width * s.x,
        depth: inst.dimensions.depth * s.y,
        height: inst.dimensions.height * s.z,
        yawRadians: inst.transform.rotation.yaw * DEG2RAD,
    }
    return buildEquipmentParts(family, pose)
}

/**
 * GENERIC_MEDICAL_CYCLOTRON_V1 — a recognizable low-LOD medical cyclotron:
 *   - CYCLOTRON_BODY: the vertical cylindrical magnet body (dominant mass).
 *   - CYCLOTRON_SHIELDING: a slightly larger, shorter concentric shielding
 *     ring around the body (the recognizable "shielded drum" silhouette).
 *   - CYCLOTRON_SERVICE_CABINET: a rectangular service cabinet beside the body.
 * Mirrors the representative_cyclotron.usda composition (Body + Shielding +
 * ServiceCabinet). Visually distinguishable as a cyclotron, NOT a plain box.
 */
export function buildCyclotronParts(pose: EquipmentPose): EquipmentPartGeometry[] {
    const [cx, cy, cz] = pose.center
    const { width: W, depth: D, height: H, yawRadians: yaw } = pose
    const center: [number, number, number] = [cx, cy, cz]

    // The cylindrical body occupies the rear ~70% of the footprint so a service
    // cabinet can sit to one side (in +X) — the classic recognizable pairing.
    const bodyRadius = Math.max(Math.min(W, D) * 0.32, 0.25)
    const bodyHeight = Math.max(H * 0.9, 0.3)
    // Body center shifted slightly toward -X to leave room for the cabinet.
    const bodyCenterX = cx - W * 0.12
    const body: WorldCylinder<EquipmentPart> = {
        kind: 'CYLINDER',
        centerA: applyYaw([bodyCenterX, cy, cz], center, yaw),
        centerB: applyYaw([bodyCenterX, cy, cz + bodyHeight], center, yaw),
        radius: bodyRadius,
        part: 'CYCLOTRON_BODY',
    }

    // Shielding: a shorter, larger-radius concentric drum around the body base.
    const shieldRadius = bodyRadius * 1.28
    const shieldHeight = bodyHeight * 0.78
    const shieldZ0 = cz + bodyHeight * 0.08
    const shielding: WorldCylinder<EquipmentPart> = {
        kind: 'CYLINDER',
        centerA: applyYaw([bodyCenterX, cy, shieldZ0], center, yaw),
        centerB: applyYaw([bodyCenterX, cy, shieldZ0 + shieldHeight], center, yaw),
        radius: shieldRadius,
        part: 'CYCLOTRON_SHIELDING',
    }

    // Service cabinet: a box to the +X side of the body.
    const cabWidth = Math.max(W * 0.24, 0.3)
    const cabDepth = Math.max(D * 0.4, 0.3)
    const cabHeight = Math.max(H * 0.8, 0.3)
    const cabCenterX = cx + W * 0.5 - cabWidth / 2
    const cabinet: WorldBox<EquipmentPart> = {
        kind: 'BOX',
        low: [cabCenterX - cabWidth / 2, cy - cabDepth / 2, cz],
        high: [cabCenterX + cabWidth / 2, cy + cabDepth / 2, cz + cabHeight],
        yawRadians: yaw,
        center,
        part: 'CYCLOTRON_SERVICE_CABINET',
    }

    return [body, shielding, cabinet]
}

// Small helpers for the medium-LOD recipes (all yaw about the pose center).
function boxPart(part: EquipmentPart, center: [number, number, number], yaw: number, lo: [number, number, number], hi: [number, number, number]): WorldBox<EquipmentPart> {
    return { kind: 'BOX', low: lo, high: hi, yawRadians: yaw, center, part }
}
function cylPart(part: EquipmentPart, center: [number, number, number], yaw: number, a: [number, number, number], b: [number, number, number], radius: number): WorldCylinder<EquipmentPart> {
    return { kind: 'CYLINDER', centerA: applyYaw(a, center, yaw), centerB: applyYaw(b, center, yaw), radius, part }
}

/**
 * GENERIC_MEDICAL_CYCLOTRON_V2 — REPRESENTATIVE MEDIUM-LOD clinical cyclotron.
 *
 * NOT manufacturer CAD. A recognizable ~20-primitive machine (rounded shielded
 * body with differentiated lower/upper shells, structural base ring + leveling
 * feet, segmented front access panels with handles, a restrained upper service
 * column + modules + a couple of conduits, and an adjacent service/electrical
 * cabinet with vents + a control screen + an e-stop). All primitives scale
 * parametrically from the instance's calibrated envelope pose; canonical
 * engineering identity is unchanged. Material differentiation is by part role
 * (see EQUIPMENT_PART_COLOR in the decorators).
 */
export function buildCyclotronPartsV2(pose: EquipmentPose): EquipmentPartGeometry[] {
    const [cx, cy, cz] = pose.center
    const { width: W, depth: D, height: H, yawRadians: yaw } = pose
    const center: [number, number, number] = [cx, cy, cz]
    const parts: EquipmentPartGeometry[] = []

    // The shielded body occupies the rear/left ~70% of the footprint so the
    // service cabinet sits to the +X side (the classic recognizable pairing).
    const bodyCx = cx - W * 0.14
    const bodyR = Math.max(Math.min(W * 0.7, D) * 0.36, 0.3)
    const baseH = Math.max(H * 0.08, 0.06)
    const lowerH = Math.max(H * 0.55, 0.4)
    const upperH = Math.max(H * 0.28, 0.25)

    // A — base ring (dark structural plinth) + leveling feet, sits on the floor.
    parts.push(cylPart('CYC_BASE_RING', center, yaw, [bodyCx, cy, cz], [bodyCx, cy, cz + baseH], bodyR * 1.12))
    const footR = Math.max(bodyR * 0.08, 0.05)
    for (const [fx, fy] of [[bodyR * 0.8, bodyR * 0.8], [-bodyR * 0.8, bodyR * 0.8], [bodyR * 0.8, -bodyR * 0.8], [-bodyR * 0.8, -bodyR * 0.8]] as const) {
        parts.push(cylPart('CYC_FOOT', center, yaw, [bodyCx + fx, cy + fy, cz], [bodyCx + fx, cy + fy, cz + baseH * 0.6], footR))
    }

    // Lower shell (broad shielded drum) + narrower stepped upper shell.
    const lowerZ0 = cz + baseH
    parts.push(cylPart('CYC_LOWER_SHELL', center, yaw, [bodyCx, cy, lowerZ0], [bodyCx, cy, lowerZ0 + lowerH], bodyR))
    const upperZ0 = lowerZ0 + lowerH
    parts.push(cylPart('CYC_UPPER_SHELL', center, yaw, [bodyCx, cy, upperZ0], [bodyCx, cy, upperZ0 + upperH], bodyR * 0.82))

    // B — segmented front access panels (front = -Y face of the body) with dark
    // handles. Four vertical panel segments across the front arc, approximated
    // as thin boxes tangent to the lower shell.
    const panelW = bodyR * 0.42
    const panelH = lowerH * 0.72
    const panelZ0 = lowerZ0 + lowerH * 0.12
    const panelY = cy - bodyR * 0.9
    for (let i = 0; i < 4; i++) {
        const px = bodyCx + (i - 1.5) * panelW * 1.02
        parts.push(boxPart('CYC_ACCESS_PANEL', center, yaw, [px - panelW / 2, panelY - 0.04, panelZ0], [px + panelW / 2, panelY + 0.04, panelZ0 + panelH]))
        // Dark handle/latch near panel mid-height.
        parts.push(boxPart('CYC_PANEL_HANDLE', center, yaw, [px + panelW * 0.18, panelY - 0.08, panelZ0 + panelH * 0.45], [px + panelW * 0.34, panelY + 0.02, panelZ0 + panelH * 0.6]))
    }

    // D — upper service structure: central service column + two small modules.
    const colTopZ = upperZ0 + upperH + Math.max(H * 0.12, 0.2)
    parts.push(boxPart('CYC_SERVICE_COLUMN', center, yaw, [bodyCx - bodyR * 0.14, cy - bodyR * 0.14, upperZ0 + upperH], [bodyCx + bodyR * 0.14, cy + bodyR * 0.14, colTopZ]))
    parts.push(boxPart('CYC_UPPER_MODULE', center, yaw, [bodyCx - bodyR * 0.5, cy - bodyR * 0.2, colTopZ - 0.15], [bodyCx - bodyR * 0.1, cy + bodyR * 0.2, colTopZ + 0.1]))
    parts.push(boxPart('CYC_UPPER_MODULE', center, yaw, [bodyCx + bodyR * 0.1, cy - bodyR * 0.2, colTopZ - 0.12], [bodyCx + bodyR * 0.45, cy + bodyR * 0.2, colTopZ + 0.08]))
    // F — a couple of restrained conduits from the upper structure down the back.
    for (const off of [-bodyR * 0.35, bodyR * 0.35]) {
        parts.push(cylPart('CYC_CONDUIT', center, yaw, [bodyCx + off, cy + bodyR * 0.7, upperZ0 + upperH], [bodyCx + off, cy + bodyR * 0.7, lowerZ0 + lowerH * 0.3], Math.max(bodyR * 0.05, 0.03)))
    }
    // Restrained brand accent stripe near the top of the lower shell (front).
    parts.push(boxPart('CYC_BRAND_ACCENT', center, yaw, [bodyCx - bodyR * 0.5, panelY - 0.02, lowerZ0 + lowerH * 0.92], [bodyCx + bodyR * 0.5, panelY + 0.05, lowerZ0 + lowerH * 0.98]))

    // E — side service / electrical cabinet on the +X side.
    const cabW = Math.max(W * 0.22, 0.4)
    const cabD = Math.max(D * 0.5, 0.4)
    const cabH = Math.max(H * 0.78, 0.6)
    const cabCx = cx + W * 0.5 - cabW / 2
    const cabBaseH = Math.max(cabH * 0.08, 0.05)
    parts.push(boxPart('CYC_CABINET_BASE', center, yaw, [cabCx - cabW / 2, cy - cabD / 2, cz], [cabCx + cabW / 2, cy + cabD / 2, cz + cabBaseH]))
    parts.push(boxPart('CYC_CABINET', center, yaw, [cabCx - cabW / 2, cy - cabD / 2, cz + cabBaseH], [cabCx + cabW / 2, cy + cabD / 2, cz + cabH]))
    // Ventilation grilles (two dark slots on the front -Y face).
    const cabFrontY = cy - cabD / 2
    for (const vz of [cabH * 0.6, cabH * 0.72]) {
        parts.push(boxPart('CYC_CABINET_VENT', center, yaw, [cabCx - cabW * 0.3, cabFrontY - 0.03, cz + vz], [cabCx + cabW * 0.3, cabFrontY + 0.02, cz + vz + cabH * 0.05]))
    }
    // Control display + emergency stop on the cabinet front.
    parts.push(boxPart('CYC_CONTROL_SCREEN', center, yaw, [cabCx - cabW * 0.28, cabFrontY - 0.03, cz + cabH * 0.42], [cabCx + cabW * 0.12, cabFrontY + 0.02, cz + cabH * 0.55]))
    parts.push(cylPart('CYC_ESTOP', center, yaw, [cabCx + cabW * 0.28, cabFrontY - 0.02, cz + cabH * 0.5], [cabCx + cabW * 0.28, cabFrontY + 0.04, cz + cabH * 0.5], Math.max(cabW * 0.06, 0.03)))

    return parts
}

/**
 * GENERIC_MRT_RADIOPHARMACY_VESTIBULE_V1 — REPRESENTATIVE MEDIUM-LOD controlled
 * transfer cabinet: the interface between radiopharmaceutical handling and the
 * future MRT concealed-service transport network. NOT the cyclotron, NOT a
 * generic MRT endpoint. Compact wall-adjacent shielded cabinet (chest/waist
 * accessible) with a dark access panel, a metallic transfer interface, status
 * lights, a small control panel, and a small transfer-throat proxy toward the
 * back wall (+Y). Scales from the pose envelope.
 */
export function buildVestibuleParts(pose: EquipmentPose): EquipmentPartGeometry[] {
    const [cx, cy, cz] = pose.center
    const { width: W, depth: D, height: H, yawRadians: yaw } = pose
    const center: [number, number, number] = [cx, cy, cz]
    const parts: EquipmentPartGeometry[] = []

    const hW = Math.min(W, 1.2) / 2   // compact — not room-sized
    const hD = Math.min(D, 0.9) / 2
    const bodyH = Math.min(H, 1.6)
    const baseH = Math.max(bodyH * 0.08, 0.05)

    // Base + shielded housing.
    parts.push(boxPart('VEST_BASE', center, yaw, [cx - hW, cy - hD, cz], [cx + hW, cy + hD, cz + baseH]))
    parts.push(boxPart('VEST_HOUSING', center, yaw, [cx - hW, cy - hD, cz + baseH], [cx + hW, cy + hD, cz + bodyH]))
    // Dark access panel on the front (-Y) face.
    parts.push(boxPart('VEST_ACCESS_PANEL', center, yaw, [cx - hW * 0.7, cy - hD - 0.03, cz + bodyH * 0.35], [cx + hW * 0.7, cy - hD + 0.02, cz + bodyH * 0.8]))
    // Metallic transfer interface (a short cylinder centered on the front panel).
    parts.push(cylPart('VEST_TRANSFER_INTERFACE', center, yaw, [cx, cy - hD - 0.06, cz + bodyH * 0.58], [cx, cy - hD + 0.02, cz + bodyH * 0.58], Math.max(hW * 0.28, 0.12)))
    // Two small status lights above the access panel.
    for (const off of [-hW * 0.3, hW * 0.3]) {
        parts.push(cylPart('VEST_STATUS_LIGHT', center, yaw, [cx + off, cy - hD - 0.04, cz + bodyH * 0.85], [cx + off, cy - hD + 0.02, cz + bodyH * 0.85], Math.max(hW * 0.06, 0.03)))
    }
    // Small control panel to one side of the front.
    parts.push(boxPart('VEST_CONTROL_PANEL', center, yaw, [cx + hW * 0.4, cy - hD - 0.03, cz + bodyH * 0.5], [cx + hW * 0.66, cy - hD + 0.02, cz + bodyH * 0.68]))
    // Transfer-throat proxy toward the back wall (+Y) — the future controlled
    // transfer penetration. VISUAL CUE ONLY (no routing).
    parts.push(cylPart('VEST_TRANSFER_THROAT', center, yaw, [cx, cy + hD - 0.02, cz + bodyH * 0.6], [cx, cy + hD + Math.max(D * 0.2, 0.25), cz + bodyH * 0.6], Math.max(hW * 0.18, 0.08)))
    // Restrained MRTway accent stripe.
    parts.push(boxPart('VEST_BRAND_ACCENT', center, yaw, [cx - hW, cy - hD - 0.02, cz + bodyH * 0.82], [cx + hW, cy - hD + 0.04, cz + bodyH * 0.88]))

    return parts
}

/**
 * Which rear transport ports the CLINICAL_LOGISTICS_VESTIBULE_V1 recipe should
 * physically render behind the wall. Mirrors the fabricated ports resolved from
 * the service class (see clinicalLogisticsVestibule.permittedPortsForServiceClass).
 * Only fabricated stubs are drawn; reserved-for-later families (RTHS / AGV_AMR)
 * are metadata-only and produce no geometry in this build.
 */
export interface VestibulePortRenderOptions {
    /** Render the MRT rear branch (large section -> planar reducer -> trunk stub). */
    mrt?: boolean
    /** Whether the MRT branch is the larger heavy/general configuration. */
    mrtHeavy?: boolean
    /** Render the PTS rear branch (compact adapter -> circular tube stub). */
    pts?: boolean
}

/**
 * CLINICAL_LOGISTICS_VESTIBULE_V1 — the ONE reusable WALL-INTEGRATED (ATM-like)
 * clinical logistics vestibule. NOT manufacturer CAD. A recognizable medium-LOD
 * assembly (~20-30 primitives) that reads immediately as a CONTROLLED CLINICAL
 * LOGISTICS TRANSFER INTERFACE and is visually distinct from the cyclotron.
 *
 * Layout convention (local, before yaw):
 *   - FRONT CLINICAL ACCESS FACE toward the room interior = local -Y.
 *   - The assembly penetrates the wall and expands into the REAR MANIFOLD +
 *     transport-port stubs toward local +Y (behind the wall).
 *   - yaw orients the -Y face against the chosen room wall.
 *
 * Front face: wall fascia/frame, recessed housing, shielded transfer door with
 * an inset aperture/chamber, a substantial handle, an HMI display, green/amber/
 * red status indicators, an e-stop, a lower service panel, a restrained
 * service-class accent, and a base. Behind the wall: a wall sleeve, the rear
 * manifold, and the CONFIGURED transport-port stubs.
 *
 * `ports` selects which rear branches are fabricated (from the service-class
 * port policy). Ports are separate physical interfaces — the MRT branch is a
 * fabricated RECTANGULAR planar reducer to a trunk stub; the PTS branch is a
 * CIRCULAR pneumatic tube stub. They NEVER share one conduit.
 */
export function buildClinicalLogisticsVestibuleParts(
    pose: EquipmentPose,
    ports: VestibulePortRenderOptions = { mrt: true, pts: true },
): EquipmentPartGeometry[] {
    const [cx, cy, cz] = pose.center
    const { width: W, depth: D, height: H, yawRadians: yaw } = pose
    const center: [number, number, number] = [cx, cy, cz]
    const parts: EquipmentPartGeometry[] = []

    // Wall-integrated proportions. The visible front section is shallow (like an
    // ATM face); the assembly then extends back through the wall.
    const hW = Math.max(Math.min(W, 1.4) / 2, 0.4)   // half-width of the face
    const bodyH = Math.max(Math.min(H, 2.2), 0.9)
    const frontY = cy - D / 2                         // the room-facing wall plane
    const faceDepth = Math.max(D * 0.28, 0.22)        // shallow visible housing depth
    const faceRearY = frontY + faceDepth
    const baseH = Math.max(bodyH * 0.08, 0.06)

    // A — base / plinth.
    parts.push(boxPart('CLV_BASE', center, yaw, [cx - hW, frontY, cz], [cx + hW, faceRearY, cz + baseH]))
    // Wall fascia/frame: a thin frame flush with the wall plane, slightly wider.
    const fasciaW = hW * 1.08
    parts.push(boxPart('CLV_WALL_FASCIA', center, yaw, [cx - fasciaW, frontY - 0.03, cz + baseH], [cx + fasciaW, frontY + 0.03, cz + bodyH]))
    // Recessed housing behind the fascia.
    parts.push(boxPart('CLV_HOUSING', center, yaw, [cx - hW, frontY, cz + baseH], [cx + hW, faceRearY, cz + bodyH]))

    // EVI-MA-07 — SIMPLIFIED front face: an obvious shallow access door plus TWO
    // unmistakable HOLLOW transport openings. The room side reads as a shallow
    // clinical wall unit, NOT a manifold.
    // B — shallow shielded access door (upper band of the face).
    const doorZ0 = cz + bodyH * 0.44
    const doorZ1 = cz + bodyH * 0.8
    const doorW = hW * 0.55
    parts.push(boxPart('CLV_TRANSFER_DOOR', center, yaw, [cx - doorW, frontY - 0.03, doorZ0], [cx + doorW, frontY + 0.01, doorZ1]))
    parts.push(boxPart('CLV_HANDLE', center, yaw, [cx + doorW * 0.55, frontY - 0.07, doorZ0 + (doorZ1 - doorZ0) * 0.4], [cx + doorW * 0.72, frontY - 0.01, doorZ0 + (doorZ1 - doorZ0) * 0.6]))

    // Genuine HOLLOW internal transfer chamber behind the access door.
    {
        const wall = 0.08
        const chFrontY = frontY + faceDepth * 0.5
        const chRearY = faceRearY + Math.max(D * 0.15, 0.12)
        parts.push(boxPart('CLV_CHAMBER_VOID', center, yaw,
            [cx - hW + wall, chFrontY, cz + baseH + wall],
            [cx + hW - wall, chRearY, cz + bodyH - wall]))
    }

    // OPENING A — LARGE RECTANGULAR MRT carrier opening (left of the face), only
    // when an MRT port is configured. A metallic frame box surrounds an EMPTY
    // rectangular void recessed back toward the chamber, so the room side reads
    // as actual hollow space you can see into (not a dark painted surface).
    if (ports.mrt !== false) {
        const mrtOpW = hW * 0.5, mrtOpH = bodyH * 0.2
        const mrtCx = cx - hW * 0.42, mrtCz = cz + bodyH * 0.24
        // Thin frame (a shallow box footprint at the wall plane around the void).
        parts.push(boxPart('CLV_MRT_OPENING_FRAME', center, yaw, [mrtCx - mrtOpW, frontY - 0.03, mrtCz - mrtOpH], [mrtCx + mrtOpW, frontY + 0.02, mrtCz + mrtOpH]))
        // The EMPTY rectangular opening interior, recessed toward the chamber.
        parts.push(boxPart('CLV_MRT_OPENING_VOID', center, yaw, [mrtCx - mrtOpW * 0.86, frontY + 0.015, mrtCz - mrtOpH * 0.86], [mrtCx + mrtOpW * 0.86, frontY + faceDepth * 0.95, mrtCz + mrtOpH * 0.86]))
    }

    // OPENING B — SMALL CIRCULAR RP-PTS opening (right of the face), only when a
    // PTS port is configured. Clearly a different SHAPE + much smaller than MRT:
    // a thin metallic ring around an empty circular bore you can see into.
    if (ports.pts !== false) {
        const ptsR = hW * 0.16
        const ptsCx = cx + hW * 0.5, ptsCz = cz + bodyH * 0.28
        parts.push(cylPart('CLV_PTS_OPENING_RING', center, yaw, [ptsCx, frontY - 0.02, ptsCz], [ptsCx, frontY + 0.02, ptsCz], ptsR * 1.18))
        parts.push(cylPart('CLV_PTS_OPENING_VOID', center, yaw, [ptsCx, frontY + 0.015, ptsCz], [ptsCx, frontY + faceDepth * 0.95, ptsCz], ptsR))
    }

    // C — HMI display to the upper-left; status indicators; e-stop.
    parts.push(boxPart('CLV_HMI', center, yaw, [cx - hW * 0.86, frontY - 0.04, cz + bodyH * 0.5], [cx - hW * 0.4, frontY + 0.02, cz + bodyH * 0.72]))
    const statusZ = cz + bodyH * 0.86
    parts.push(cylPart('CLV_STATUS_GREEN', center, yaw, [cx - hW * 0.5, frontY - 0.05, statusZ], [cx - hW * 0.5, frontY + 0.01, statusZ], Math.max(hW * 0.05, 0.03)))
    parts.push(cylPart('CLV_STATUS_AMBER', center, yaw, [cx - hW * 0.3, frontY - 0.05, statusZ], [cx - hW * 0.3, frontY + 0.01, statusZ], Math.max(hW * 0.05, 0.03)))
    parts.push(cylPart('CLV_STATUS_RED', center, yaw, [cx - hW * 0.1, frontY - 0.05, statusZ], [cx - hW * 0.1, frontY + 0.01, statusZ], Math.max(hW * 0.05, 0.03)))
    // Emergency stop (recognizable mushroom button) on the right of the face.
    parts.push(cylPart('CLV_ESTOP', center, yaw, [cx + hW * 0.66, frontY - 0.06, cz + bodyH * 0.62], [cx + hW * 0.66, frontY + 0.01, cz + bodyH * 0.62], Math.max(hW * 0.07, 0.04)))

    // D — lower service/access panel + restrained service-class label/accent.
    parts.push(boxPart('CLV_SERVICE_PANEL', center, yaw, [cx - hW * 0.8, frontY - 0.03, cz + baseH], [cx + hW * 0.8, frontY + 0.02, cz + bodyH * 0.38]))
    parts.push(boxPart('CLV_SERVICE_LABEL', center, yaw, [cx - hW * 0.8, frontY - 0.04, cz + bodyH * 0.3], [cx + hW * 0.2, frontY + 0.02, cz + bodyH * 0.36]))

    // E — WALL PENETRATION: a sleeve section from the face rear back through the
    // wall to the rear manifold. Represents building INTO the wall.
    const wallRearY = cy + D / 2                       // behind-wall side
    const sleeveRearY = wallRearY                       // sleeve reaches the wall's back plane
    const manifoldW = hW * 0.9
    parts.push(boxPart('CLV_WALL_SLEEVE', center, yaw, [cx - manifoldW, faceRearY, cz + bodyH * 0.28], [cx + manifoldW, sleeveRearY, cz + bodyH * 0.86]))

    // F — REAR MANIFOLD: the internal handoff region behind the wall from which
    // the permitted transport-port branches originate.
    const manDepth = Math.max(D * 0.35, 0.3)
    const manFrontY = sleeveRearY
    const manRearY = manFrontY + manDepth
    parts.push(boxPart('CLV_REAR_MANIFOLD', center, yaw, [cx - manifoldW, manFrontY, cz + bodyH * 0.24], [cx + manifoldW, manRearY, cz + bodyH * 0.9]))

    // ---- MRT rear branch (rectangular section -> PLANAR reducer -> trunk stub)
    if (ports.mrt !== false) {
        const heavy = ports.mrtHeavy === true
        // Large rectangular transfer section on the -X half of the manifold rear.
        const mrtCx = cx - manifoldW * 0.4
        const bigHalfW = manifoldW * (heavy ? 0.5 : 0.38)
        const bigHalfH = bodyH * (heavy ? 0.34 : 0.28)
        const midZ = cz + bodyH * 0.56
        const secFrontY = manRearY
        const secRearY = secFrontY + Math.max(manDepth * 0.5, 0.2)
        parts.push(boxPart('CLV_MRT_MANIFOLD_SECTION', center, yaw,
            [mrtCx - bigHalfW, secFrontY, midZ - bigHalfH], [mrtCx + bigHalfW, secRearY, midZ + bigHalfH]))
        // Rectangular PLANAR reducer: 4 sloping trapezoidal faces from the large
        // section cross-section to the smaller trunk cross-section. Fabricated
        // (planar) — NOT a cone / rounded nozzle / chamfer.
        const smallHalfW = bigHalfW * 0.5
        const smallHalfH = bigHalfH * 0.5
        const redFrontY = secRearY
        const redRearY = redFrontY + Math.max(manDepth * 0.45, 0.18)
        // Each reducer face is a thin quad approximated as a thin box spanning
        // from a large-section edge to the corresponding trunk edge.
        // TOP face (slopes inward+down toward the trunk).
        parts.push(boxPart('CLV_MRT_REDUCER_FACE', center, yaw,
            [mrtCx - bigHalfW, redFrontY, midZ + smallHalfH], [mrtCx + bigHalfW, redRearY, midZ + bigHalfH]))
        // BOTTOM face.
        parts.push(boxPart('CLV_MRT_REDUCER_FACE', center, yaw,
            [mrtCx - bigHalfW, redFrontY, midZ - bigHalfH], [mrtCx + bigHalfW, redRearY, midZ - smallHalfH]))
        // LEFT face.
        parts.push(boxPart('CLV_MRT_REDUCER_FACE', center, yaw,
            [mrtCx - bigHalfW, redFrontY, midZ - bigHalfH], [mrtCx - smallHalfW, redRearY, midZ + bigHalfH]))
        // RIGHT face.
        parts.push(boxPart('CLV_MRT_REDUCER_FACE', center, yaw,
            [mrtCx + smallHalfW, redFrontY, midZ - bigHalfH], [mrtCx + bigHalfW, redRearY, midZ + bigHalfH]))
        // Smaller standard MRT trunk stub (short) + the connection-port end face.
        const trunkFrontY = redRearY
        const trunkRearY = trunkFrontY + Math.max(manDepth * 0.5, 0.25)
        parts.push(boxPart('CLV_MRT_TRUNK_STUB', center, yaw,
            [mrtCx - smallHalfW, trunkFrontY, midZ - smallHalfH], [mrtCx + smallHalfW, trunkRearY, midZ + smallHalfH]))
        parts.push(boxPart('CLV_MRT_TRUNK_PORT', center, yaw,
            [mrtCx - smallHalfW, trunkRearY - 0.02, midZ - smallHalfH], [mrtCx + smallHalfW, trunkRearY + 0.03, midZ + smallHalfH]))
        // HOLLOW inner free passage — a continuous dark void running through the
        // large section, the reducer, and the trunk, INSET from the outer shells
        // by the wall thickness so the four planar reducer faces read as walls
        // SURROUNDING a hollow passage (not a solid tapered block). The passage
        // narrows from the large opening to the trunk opening (approximated as
        // two constant segments: large through the section, small through the
        // reducer+trunk — both strictly smaller than their outer shells).
        const wall = 0.03
        const bigInW = bigHalfW - wall, bigInH = bigHalfH - wall
        const smInW = smallHalfW - wall, smInH = smallHalfH - wall
        // Large free segment (section).
        parts.push(boxPart('CLV_MRT_INNER_VOID', center, yaw,
            [mrtCx - bigInW, secFrontY + 0.005, midZ - bigInH], [mrtCx + bigInW, redFrontY, midZ + bigInH]))
        // Narrowed free segment (reducer + trunk) — smaller cross-section.
        parts.push(boxPart('CLV_MRT_INNER_VOID', center, yaw,
            [mrtCx - smInW, redFrontY, midZ - smInH], [mrtCx + smInW, trunkRearY - 0.005, midZ + smInH]))
    }

    // ---- PTS rear branch (compact adapter -> CIRCULAR tube stub -> port) ------
    if (ports.pts !== false) {
        // Compact adapter on the +X half of the manifold rear.
        const ptsCx = cx + manifoldW * 0.45
        const tubeR = Math.max(manifoldW * 0.16, 0.06)
        const midZ = cz + bodyH * 0.58
        const adFrontY = manRearY
        const adRearY = adFrontY + Math.max(manDepth * 0.4, 0.15)
        parts.push(boxPart('CLV_PTS_ADAPTER', center, yaw,
            [ptsCx - tubeR * 1.6, adFrontY, midZ - tubeR * 1.6], [ptsCx + tubeR * 1.6, adRearY, midZ + tubeR * 1.6]))
        // Circular pneumatic-tube stub (short) reads clearly as a tube system.
        const tubeFrontY = adRearY
        const tubeRearY = tubeFrontY + Math.max(manDepth * 0.7, 0.3)
        parts.push(cylPart('CLV_PTS_TUBE_STUB', center, yaw,
            [ptsCx, tubeFrontY, midZ], [ptsCx, tubeRearY, midZ], tubeR))
        // PTS connection-port end face (a slightly larger ring at the stub end).
        parts.push(cylPart('CLV_PTS_PORT', center, yaw,
            [ptsCx, tubeRearY - 0.02, midZ], [ptsCx, tubeRearY + 0.03, midZ], tubeR * 1.25))
        // HOLLOW inner circular bore — a dark, smaller-radius cylinder running the
        // length of the tube so a cutaway reads the tube outer wall + a distinct
        // circular internal bore (OD > ID). Sized as a visual fraction of the
        // tube radius; the AUTHORITATIVE bore/OD/pig/clearance quantities live on
        // the persisted port (see clinicalLogisticsVestibule port model).
        const boreR = tubeR * 0.62
        parts.push(cylPart('CLV_PTS_INNER_BORE', center, yaw,
            [ptsCx, adFrontY + 0.005, midZ], [ptsCx, tubeRearY - 0.005, midZ], boreR))
    }

    return parts
}

/**
 * GENERIC_RADIOPHARMACY_HOTCELL_V1 — a recognizable radiopharmacy / hot-cell
 * workstation arrangement:
 *   - HOT_CELL: a tall shielded cabinet (dominant mass, rear of the footprint).
 *   - WORKBENCH: a low bench slab extending forward from the hot cell.
 *   - DISPENSING: a small dispensing/handling station box on the bench.
 * Mirrors the representative_radiopharmacy.usda composition (HotCell +
 * Workbench + Dispensing). Visually distinguishable as radiopharmacy equipment.
 */
export function buildRadiopharmacyParts(pose: EquipmentPose): EquipmentPartGeometry[] {
    const [cx, cy, cz] = pose.center
    const { width: W, depth: D, height: H, yawRadians: yaw } = pose
    const center: [number, number, number] = [cx, cy, cz]

    // Hot cell: tall shielded cabinet occupying the rear ~45% of the depth,
    // roughly 60% of the width, full height.
    const cellDepth = D * 0.45
    const cellWidth = W * 0.6
    const cellRearY = cy + D / 2
    const hotCell: WorldBox<EquipmentPart> = {
        kind: 'BOX',
        low: [cx - cellWidth / 2, cellRearY - cellDepth, cz],
        high: [cx + cellWidth / 2, cellRearY, cz + H],
        yawRadians: yaw,
        center,
        part: 'HOT_CELL',
    }

    // Workbench: a low slab in front of the hot cell at ~40% height.
    const benchTopZ = cz + Math.max(H * 0.42, 0.3)
    const benchThickness = Math.max(H * 0.06, 0.05)
    const benchFrontY = cy - D / 2
    const benchRearY = cellRearY - cellDepth
    const bench: WorldBox<EquipmentPart> = {
        kind: 'BOX',
        low: [cx - W * 0.42, benchFrontY, benchTopZ - benchThickness],
        high: [cx + W * 0.42, benchRearY, benchTopZ],
        yawRadians: yaw,
        center,
        part: 'WORKBENCH',
    }

    // Dispensing station: a small box sitting on the bench toward the front.
    const dispW = Math.max(W * 0.18, 0.2)
    const dispD = Math.max(D * 0.18, 0.2)
    const dispH = Math.max(H * 0.22, 0.2)
    const dispCenterY = benchFrontY + (benchRearY - benchFrontY) * 0.4
    const dispensing: WorldBox<EquipmentPart> = {
        kind: 'BOX',
        low: [cx - dispW / 2, dispCenterY - dispD / 2, benchTopZ],
        high: [cx + dispW / 2, dispCenterY + dispD / 2, benchTopZ + dispH],
        yawRadians: yaw,
        center,
        part: 'DISPENSING',
    }

    return [hotCell, bench, dispensing]
}

// ---------------------------------------------------------------------------
// World bounds (for Fit-to-Equipment camera locatability) — pure + testable
// ---------------------------------------------------------------------------

/** An axis-aligned world-space bounding box (meters). */
export interface WorldBounds {
    low: [number, number, number]
    high: [number, number, number]
}

/** True when a bounds is finite and has strictly positive extent on every axis. */
export function isNonDegenerateBounds(b: WorldBounds): boolean {
    const vals = [...b.low, ...b.high]
    if (!vals.every(Number.isFinite)) return false
    return b.high[0] > b.low[0] && b.high[1] > b.low[1] && b.high[2] > b.low[2]
}

/** Extend a mutable [lo,hi] pair by a yawed box's 8 corners. */
function extendByBox(lo: number[], hi: number[], box: WorldBox<EquipmentPart>): void {
    const [lx, ly, lz] = box.low
    const [hx, hy, hz] = box.high
    const corners: [number, number, number][] = [
        [lx, ly, lz], [hx, ly, lz], [lx, hy, lz], [hx, hy, lz],
        [lx, ly, hz], [hx, ly, hz], [lx, hy, hz], [hx, hy, hz],
    ]
    for (const c of corners) {
        const [wx, wy, wz] = applyYaw(c, box.center, box.yawRadians)
        lo[0] = Math.min(lo[0], wx); lo[1] = Math.min(lo[1], wy); lo[2] = Math.min(lo[2], wz)
        hi[0] = Math.max(hi[0], wx); hi[1] = Math.max(hi[1], wy); hi[2] = Math.max(hi[2], wz)
    }
}

/**
 * Extend a mutable [lo,hi] pair by a cylinder. The radius is padded ONLY on the
 * axes perpendicular to the cylinder axis, so a floor-standing vertical (Z-axis)
 * cylinder never dips below its base cap. The axis is inferred from the endpoint
 * that differs; a degenerate (zero-length) cylinder pads all axes.
 */
function extendByCylinder(lo: number[], hi: number[], cyl: WorldCylinder<EquipmentPart>): void {
    const [ax, ay, az] = cyl.centerA
    const [bx, by, bz] = cyl.centerB
    const dx = Math.abs(bx - ax), dy = Math.abs(by - ay), dz = Math.abs(bz - az)
    const eps = 1e-9
    // Pad radius on an axis only when the cylinder axis is (approximately) NOT
    // aligned with it — i.e. the cross-section spans that axis.
    const padX = !(dx > eps && dy <= eps && dz <= eps) ? cyl.radius : 0
    const padY = !(dy > eps && dx <= eps && dz <= eps) ? cyl.radius : 0
    const padZ = !(dz > eps && dx <= eps && dy <= eps) ? cyl.radius : 0
    for (const ep of [cyl.centerA, cyl.centerB]) {
        lo[0] = Math.min(lo[0], ep[0] - padX); lo[1] = Math.min(lo[1], ep[1] - padY); lo[2] = Math.min(lo[2], ep[2] - padZ)
        hi[0] = Math.max(hi[0], ep[0] + padX); hi[1] = Math.max(hi[1], ep[1] + padY); hi[2] = Math.max(hi[2], ep[2] + padZ)
    }
}

/**
 * Compute the authoritative world-space bounds that Fit-to-Equipment frames.
 * Unions the recognizable visual parts AND the authoritative envelope box (so
 * even a family with no recognizable geometry still yields a fittable range).
 * Pure and deterministic — no Bentley. Returns undefined only when there is no
 * geometry at all AND no envelope (should not happen for a valid instance).
 */
export function computeEquipmentWorldBounds(input: {
    pose: EquipmentPose
    family?: EquipmentVisualFamily
    vestibulePorts?: VestibulePortRenderOptions
}): WorldBounds | undefined {
    const lo = [Infinity, Infinity, Infinity]
    const hi = [-Infinity, -Infinity, -Infinity]

    // Visual parts (if a family resolves).
    if (input.family) {
        for (const part of buildEquipmentParts(input.family, input.pose, { vestibulePorts: input.vestibulePorts })) {
            if (part.kind === 'BOX') extendByBox(lo, hi, part)
            else extendByCylinder(lo, hi, part)
        }
    }

    // Authoritative envelope box (yaw about center) — always unioned so the
    // fit range is at least the engineering clearance envelope.
    const { center, width: W, depth: D, height: H, yawRadians } = input.pose
    const [cx, cy, cz] = center
    const envelope: WorldBox<EquipmentPart> = {
        kind: 'BOX',
        low: [cx - W / 2, cy - D / 2, cz],
        high: [cx + W / 2, cy + D / 2, cz + H],
        yawRadians,
        center,
        part: 'GANTRY',
    }
    extendByBox(lo, hi, envelope)

    if (![...lo, ...hi].every(Number.isFinite)) return undefined
    return { low: [lo[0], lo[1], lo[2]], high: [hi[0], hi[1], hi[2]] }
}

// ---------------------------------------------------------------------------
// Diagnostic — one-shot visual/render snapshot for an equipment instance
// ---------------------------------------------------------------------------

/**
 * A pure, serializable diagnostic that makes a visual failure diagnosable
 * without reading multiple modules. `renderable` is true when a recognizable
 * family resolves AND its bounds are non-degenerate. When no family resolves,
 * `visualFamily` is `VISUAL_NOT_AVAILABLE` and only the envelope bounds remain.
 */
export interface EquipmentVisualDiagnostic {
    equipmentInstanceId: string
    canonicalModelId: string
    canonicalClass: CanonicalEquipmentClass
    visualFamily: EquipmentVisualFamily | 'VISUAL_NOT_AVAILABLE'
    parentRoomId: string
    x: number
    y: number
    zBase: number
    yaw: number
    envelopeBounds: WorldBounds | undefined
    visualBounds: WorldBounds | undefined
    primitiveCount: number
    renderable: boolean
}

export function buildEquipmentVisualDiagnostic(input: {
    equipmentInstanceId: string
    canonicalModelId: string
    canonicalClass: CanonicalEquipmentClass
    assetFamily?: AssetFamily
    parentRoomId: string
    pose: EquipmentPose
}): EquipmentVisualDiagnostic {
    const family = resolveVisualFamilyForCanonical({ canonicalClass: input.canonicalClass, assetFamily: input.assetFamily })
    const parts = family ? buildEquipmentParts(family, input.pose) : []
    const visualBounds = family ? computeEquipmentWorldBounds({ pose: input.pose, family }) : undefined
    // Envelope-only bounds (no family) so the diagnostic always reports the
    // engineering clearance box even when no recognizable geometry exists.
    const envelopeBounds = computeEquipmentWorldBounds({ pose: input.pose })
    const renderable = family !== undefined && parts.length > 0 && !!visualBounds && isNonDegenerateBounds(visualBounds)
    return {
        equipmentInstanceId: input.equipmentInstanceId,
        canonicalModelId: input.canonicalModelId,
        canonicalClass: input.canonicalClass,
        visualFamily: family ?? 'VISUAL_NOT_AVAILABLE',
        parentRoomId: input.parentRoomId,
        x: input.pose.center[0],
        y: input.pose.center[1],
        zBase: input.pose.center[2],
        yaw: input.pose.yawRadians,
        envelopeBounds,
        visualBounds,
        primitiveCount: parts.length,
        renderable,
    }
}

// Re-export the shared primitive types + yaw helper so consumers import from a
// single geometry module.
export type { ScannerPartGeometry, WorldBox, WorldCylinder }
export { applyYaw }
