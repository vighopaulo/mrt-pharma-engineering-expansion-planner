/**
 * firstPerson — pure, Bentley-free first-person navigation math + walk-movement
 * resolution. The authoritative nav state is EYE_POSITION + YAW + PITCH (never a
 * remote orbit target). Fully unit-testable.
 *
 * Turning changes the LOOK DIRECTION from the fixed eye position; it never
 * orbits the eye around a distant pivot. Forward/strafe translate the eye in the
 * horizontal plane. Movement is validated (wall/door/window/floor) BEFORE the
 * camera commits.
 */

export interface Vec3 { x: number; y: number; z: number }

/** Clamp pitch to avoid gimbal flip / looking past straight up/down. */
export const MAX_PITCH = 1.45 // ~83°
export function clampPitch(pitch: number): number {
    if (!Number.isFinite(pitch)) return 0
    return Math.max(-MAX_PITCH, Math.min(MAX_PITCH, pitch))
}

export interface Orientation {
    forward: Vec3 // unit look direction (includes pitch)
    forwardFlat: Vec3 // unit horizontal forward (walking)
    right: Vec3 // unit horizontal right (strafe)
    up: Vec3
}

/**
 * Resolve first-person orientation from yaw (around +Z) and pitch. Yaw 0 looks
 * along +Y; positive yaw turns left (toward -X). Pure; no eye position involved,
 * so changing yaw/pitch NEVER moves the eye.
 */
export function resolveFirstPersonOrientation(yaw: number, pitch: number): Orientation {
    const p = clampPitch(pitch)
    const cx = Math.cos(p)
    const forward: Vec3 = { x: cx * Math.sin(yaw), y: cx * Math.cos(yaw), z: Math.sin(p) }
    const forwardFlat: Vec3 = { x: Math.sin(yaw), y: Math.cos(yaw), z: 0 }
    const right: Vec3 = { x: Math.cos(yaw), y: -Math.sin(yaw), z: 0 }
    return { forward, forwardFlat, right, up: { x: 0, y: 0, z: 1 } }
}

export type MoveInput = { forward: number; strafe: number } // each in {-1,0,1}

/** Compute a candidate horizontal eye translation (does not apply floor/collision). */
export function candidateEye(eye: Vec3, yaw: number, input: MoveInput, stepDistance: number): Vec3 {
    const o = resolveFirstPersonOrientation(yaw, 0)
    const dx = o.forwardFlat.x * input.forward + o.right.x * input.strafe
    const dy = o.forwardFlat.y * input.forward + o.right.y * input.strafe
    const len = Math.hypot(dx, dy)
    if (len === 0) return { ...eye }
    return { x: eye.x + (dx / len) * stepDistance, y: eye.y + (dy / len) * stepDistance, z: eye.z }
}

// ---------------------------------------------------------------------------
// Walk-movement resolution (wall / door / window / floor)
// ---------------------------------------------------------------------------

export type WalkResult = 'ALLOW' | 'ALLOW_DOOR' | 'BLOCK_WALL' | 'BLOCK_WINDOW' | 'BLOCK_UNKNOWN_OPENING' | 'BLOCK_NO_FLOOR'

export type CrossingKind =
    | 'NONE' // path stays within the same open area (no solid boundary)
    | 'WALL' // crosses a solid wall/partition
    | 'DOOR' // crosses a wall at a traversable door portal
    | 'WINDOW' // crosses a wall at a window/glazing
    | 'UNKNOWN_OPENING' // crosses a wall at a void that is not an established door

export interface WalkInput {
    /** Classification of what the straight eye step crosses at a boundary. */
    crossing: CrossingKind
    /** Whether a supported walking surface exists beneath the candidate. */
    hasFloorSupport: boolean
}

/**
 * Resolve a walk step:
 *   - no floor support -> BLOCK_NO_FLOOR (highest precedence; never fly/fall)
 *   - NONE crossing -> ALLOW
 *   - DOOR -> ALLOW_DOOR
 *   - WINDOW -> BLOCK_WINDOW
 *   - WALL -> BLOCK_WALL
 *   - UNKNOWN_OPENING -> BLOCK_UNKNOWN_OPENING (conservative)
 */
export function resolveWalkMovement(input: WalkInput): WalkResult {
    if (!input.hasFloorSupport) return 'BLOCK_NO_FLOOR'
    switch (input.crossing) {
        case 'NONE': return 'ALLOW'
        case 'DOOR': return 'ALLOW_DOOR'
        case 'WINDOW': return 'BLOCK_WINDOW'
        case 'UNKNOWN_OPENING': return 'BLOCK_UNKNOWN_OPENING'
        case 'WALL':
        default: return 'BLOCK_WALL'
    }
}

/** Eye Z is always walking-surface elevation + generic eye height (no drift). */
export function eyeZForFloor(floorElevation: number, eyeHeight: number): number {
    return floorElevation + eyeHeight
}

// ---------------------------------------------------------------------------
// Storey selector source policy (storeys only; never rooms/spaces)
// ---------------------------------------------------------------------------

export interface StoreyCandidate { id: string; label: string; kind: 'STORY' | 'SPACE' | 'COMPOSITE' }

/**
 * The bird's-eye / walkthrough storey selector must contain ONLY actual
 * BuildingSpatial:Story entries — never the hundreds of BuildingSpatial:Space
 * (room) identities. Filters a candidate inventory to stories only.
 */
export function storeySelectorEntries(candidates: readonly StoreyCandidate[]): StoreyCandidate[] {
    return candidates.filter((c) => c.kind === 'STORY')
}
