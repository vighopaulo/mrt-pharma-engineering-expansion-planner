/**
 * cameraNav — pure, Bentley-free camera-mode + walkthrough-traversal policy.
 *
 * Two product concerns, both fully unit-testable:
 *   1. resolveCameraModePolicy(mode): what each camera mode enables (pointer,
 *      keyboard movement, asset manipulation, collision, cutaway).
 *   2. resolveTraversal(...): whether a walkthrough movement step is ALLOWED,
 *      BLOCKED_WALL, ALLOWED_DOOR, or BLOCKED_NO_FLOOR — door-constrained.
 *
 * NAV vs CLEARANCE: the collision radius here is a HUMAN CAMERA navigation
 * volume. It is NOT equipment/scanner/MRT clearance and must never be reused as
 * such. All dimensions are generic planning assumptions (not calibrated).
 */

export type CameraMode = 'PLANNING' | 'WALKTHROUGH' | 'BIRDS_EYE_CUTAWAY'
export const CAMERA_MODES: readonly CameraMode[] = ['PLANNING', 'WALKTHROUGH', 'BIRDS_EYE_CUTAWAY']
export const DEFAULT_CAMERA_MODE: CameraMode = 'PLANNING'

/** Generic planning assumptions (configurable; NOT calibrated anthropometrics). */
export const WALKTHROUGH_EYE_HEIGHT_M = 1.65 // GENERIC_PLANNING_ASSUMPTION
export const WALKTHROUGH_SPEED_M_PER_S = 1.6 // UI_NAVIGATION_ASSUMPTION
export const WALKTHROUGH_COLLISION_RADIUS_M = 0.3 // camera nav volume (NOT clearance)

export interface CameraModePolicy {
    /** Pointer-lock / first-person look active. */
    pointerLook: boolean
    /** WASD / arrow keyboard movement active. */
    keyboardMovement: boolean
    /** Existing asset manipulation (drag/rotate/select) enabled. */
    assetManipulation: boolean
    /** Human navigation collision enabled. */
    collision: boolean
    /** Storey cutaway/clip enabled. */
    cutaway: boolean
    /** Elevated orbit/pan navigation (birds-eye). */
    elevatedNavigation: boolean
}

/**
 * The single source of truth for what a camera mode allows.
 *  - PLANNING: existing orbit + asset manipulation; no collision/cutaway.
 *  - WALKTHROUGH: first-person look + keyboard movement + collision; asset
 *    manipulation OFF (camera owns input, so a walk/look never drags equipment).
 *  - BIRDS_EYE_CUTAWAY: elevated navigation + cutaway; asset manipulation stays
 *    available (planning-style selection is compatible), no first-person/collision.
 */
export function resolveCameraModePolicy(mode: CameraMode): CameraModePolicy {
    switch (mode) {
        case 'WALKTHROUGH':
            return { pointerLook: true, keyboardMovement: true, assetManipulation: false, collision: true, cutaway: false, elevatedNavigation: false }
        case 'BIRDS_EYE_CUTAWAY':
            return { pointerLook: false, keyboardMovement: false, assetManipulation: true, collision: false, cutaway: true, elevatedNavigation: true }
        case 'PLANNING':
        default:
            return { pointerLook: false, keyboardMovement: false, assetManipulation: true, collision: false, cutaway: false, elevatedNavigation: false }
    }
}

// ---------------------------------------------------------------------------
// Walkthrough traversal policy (door-constrained)
// ---------------------------------------------------------------------------

export type TraversalResult = 'ALLOW' | 'ALLOW_DOOR' | 'BLOCK_WALL' | 'BLOCK_NO_FLOOR'

/** A traversable opening the movement path may pass through. */
export type OpeningKind = 'TRAVERSABLE_DOOR_OPENING' | 'NON_TRAVERSABLE_OPENING' | 'SOLID_BOUNDARY'

export interface Vec2 { x: number; y: number }

export interface TraversalInput {
    /** Whether the straight move from current->candidate crosses a solid wall. */
    crossesWall: boolean
    /**
     * Openings whose footprint the movement path passes through, each classified
     * by BIM semantics. A door only lets you pass if it is a traversable door
     * opening (a window / glazing / small penetration must NOT).
     */
    openingsOnPath: readonly OpeningKind[]
    /** Whether the candidate position has a supported walking surface below it. */
    hasFloorSupport: boolean
}

/**
 * Decide a walkthrough movement step:
 *   - no floor support -> BLOCK_NO_FLOOR (never free-float / fall through)
 *   - does not cross a wall -> ALLOW (same-room / open movement)
 *   - crosses a wall AND a TRAVERSABLE_DOOR_OPENING is on the path -> ALLOW_DOOR
 *   - crosses a wall with only windows / non-traversable openings -> BLOCK_WALL
 */
export function resolveTraversal(input: TraversalInput): TraversalResult {
    if (!input.hasFloorSupport) return 'BLOCK_NO_FLOOR'
    if (!input.crossesWall) return 'ALLOW'
    const hasDoor = input.openingsOnPath.some((o) => o === 'TRAVERSABLE_DOOR_OPENING')
    return hasDoor ? 'ALLOW_DOOR' : 'BLOCK_WALL'
}

/**
 * Classify a BIM opening by its ingested class/name into a traversal kind.
 * Doors -> traversable; windows/glazing/service penetrations -> non-traversable.
 * Conservative: unknown => NON_TRAVERSABLE (never auto-walkable).
 */
export function classifyOpening(bimClassOrName: string): OpeningKind {
    const s = bimClassOrName.toLowerCase()
    if (/window|glaz/.test(s)) return 'NON_TRAVERSABLE_OPENING'
    if (/door|doorway/.test(s)) return 'TRAVERSABLE_DOOR_OPENING'
    if (/opening/.test(s)) return 'NON_TRAVERSABLE_OPENING' // generic opening != door
    return 'SOLID_BOUNDARY'
}
