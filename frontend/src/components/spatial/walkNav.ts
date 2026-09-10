/**
 * walkNav — pure, Bentley-free WALK COLLISION model + segment-crossing resolver,
 * continuous-heading helpers, FOV policy, and storey-cutaway policy. All
 * offline-testable (no Bentley / browser / viewport / network).
 *
 * This is NAVIGATION data derived from BIM geometry at runtime; it is NOT an
 * authoritative BIM modification and NOT equipment clearance.
 */

export interface Vec2 { x: number; y: number }

// ---------------------------------------------------------------------------
// Per-storey collision model
// ---------------------------------------------------------------------------

export interface WallSegment { id: string; a: Vec2; b: Vec2; thickness: number }
export interface Portal { id: string; wallId: string; center: Vec2; halfWidth: number; traversable: boolean }

export interface WalkCollisionStorey {
    storeyId: string
    elevation: number
    /** Wall/partition centerline segments. */
    wallBoundaries: WallSegment[]
    /** Door portals (traversable) keyed to a wall. */
    doorPortals: Portal[]
    /** Window boundaries (never traversable). */
    windowBoundaries: Portal[]
    /** Openings that could not be established as human-traversable. */
    nonTraversableOpenings: Portal[]
    /** Whether a walking surface exists (storey has a floor plane). */
    hasFloor: boolean
}

export type WalkResult =
    | 'ALLOW'
    | 'ALLOW_DOOR'
    | 'BLOCK_WALL'
    | 'BLOCK_WINDOW'
    | 'BLOCK_UNKNOWN_OPENING'
    | 'BLOCK_NO_FLOOR'
    | 'SLIDE_WALL'

// --- 2D geometry helpers ---

function sub(a: Vec2, b: Vec2): Vec2 { return { x: a.x - b.x, y: a.y - b.y } }
function dot(a: Vec2, b: Vec2): number { return a.x * b.x + a.y * b.y }
function len(a: Vec2): number { return Math.hypot(a.x, a.y) }

/** Segment intersection parameter test: do segments p1p2 and p3p4 cross? */
export function segmentsIntersect(p1: Vec2, p2: Vec2, p3: Vec2, p4: Vec2): boolean {
    const d = (p2.x - p1.x) * (p4.y - p3.y) - (p2.y - p1.y) * (p4.x - p3.x)
    if (Math.abs(d) < 1e-12) return false
    const t = ((p3.x - p1.x) * (p4.y - p3.y) - (p3.y - p1.y) * (p4.x - p3.x)) / d
    const u = ((p3.x - p1.x) * (p2.y - p1.y) - (p3.y - p1.y) * (p2.x - p1.x)) / d
    return t >= 0 && t <= 1 && u >= 0 && u <= 1
}

/** Point where the moving segment crosses a wall segment (approx: wall midpoint-nearest). */
function crossingPointOnWall(p1: Vec2, p2: Vec2, wall: WallSegment): Vec2 {
    // Approximate crossing by projecting the movement midpoint onto the wall.
    const mid = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 }
    const wa = wall.a, wb = wall.b
    const ab = sub(wb, wa)
    const t = Math.max(0, Math.min(1, dot(sub(mid, wa), ab) / Math.max(1e-9, dot(ab, ab))))
    return { x: wa.x + ab.x * t, y: wa.y + ab.y * t }
}

/** Nearest distance from a point to a segment. */
export function pointSegmentDistance(p: Vec2, a: Vec2, b: Vec2): number {
    const ab = sub(b, a)
    const t = Math.max(0, Math.min(1, dot(sub(p, a), ab) / Math.max(1e-9, dot(ab, ab))))
    const proj = { x: a.x + ab.x * t, y: a.y + ab.y * t }
    return len(sub(p, proj))
}

/** Is a crossing point covered by a traversable door portal on that wall? */
function crossingInDoorPortal(cross: Vec2, wall: WallSegment, portals: readonly Portal[], tolerance: number): boolean {
    return portals.some((portal) =>
        portal.wallId === wall.id &&
        portal.traversable &&
        len(sub(cross, portal.center)) <= portal.halfWidth + tolerance,
    )
}

function crossingInWindow(cross: Vec2, wall: WallSegment, windows: readonly Portal[], tolerance: number): boolean {
    return windows.some((w) => w.wallId === wall.id && len(sub(cross, w.center)) <= w.halfWidth + tolerance)
}
function crossingInUnknownOpening(cross: Vec2, wall: WallSegment, openings: readonly Portal[], tolerance: number): boolean {
    return openings.some((o) => o.wallId === wall.id && len(sub(cross, o.center)) <= o.halfWidth + tolerance)
}

export interface WalkCollisionInput {
    current: Vec2
    candidate: Vec2
    storey: WalkCollisionStorey
    collisionRadius: number
    tolerance?: number
}

/**
 * Resolve a walk step against the per-storey collision model. Tests the movement
 * SEGMENT (current->candidate) against every wall; also enforces the collision
 * radius so a step that merely grazes a wall corner is blocked. Door portals
 * allow passage ONLY at the local door region (locality enforced). Windows and
 * unknown openings never let you through. No floor => BLOCK_NO_FLOOR.
 */
export function resolveWalkCollision(input: WalkCollisionInput): WalkResult {
    const { current, candidate, storey, collisionRadius } = input
    const tol = input.tolerance ?? 0.05
    if (!storey.hasFloor) return 'BLOCK_NO_FLOOR'

    for (const wall of storey.wallBoundaries) {
        const crosses = segmentsIntersect(current, candidate, wall.a, wall.b)
        // Radius check: even without a mathematical crossing, if the candidate
        // ends within (radius + halfThickness) of the wall, treat as contact.
        const nearDist = pointSegmentDistance(candidate, wall.a, wall.b)
        const contact = crosses || nearDist <= collisionRadius + wall.thickness / 2
        if (!contact) continue

        const cross = crossingPointOnWall(current, candidate, wall)
        if (crossingInDoorPortal(cross, wall, storey.doorPortals, Math.max(tol, collisionRadius))) return 'ALLOW_DOOR'
        if (crossingInWindow(cross, wall, storey.windowBoundaries, tol)) return 'BLOCK_WINDOW'
        if (crossingInUnknownOpening(cross, wall, storey.nonTraversableOpenings, tol)) return 'BLOCK_UNKNOWN_OPENING'
        return 'BLOCK_WALL'
    }
    return 'ALLOW'
}

/**
 * Wall-sliding: given a blocked candidate, project the movement onto the wall
 * tangent so tangential motion continues. Returns the slid candidate, or the
 * current position if no valid slide exists.
 */
export function slideAlongWall(current: Vec2, candidate: Vec2, wall: WallSegment): Vec2 {
    const wallDir = sub(wall.b, wall.a)
    const wl = len(wallDir)
    if (wl < 1e-9) return current
    const unit = { x: wallDir.x / wl, y: wallDir.y / wl }
    const move = sub(candidate, current)
    const tangential = dot(move, unit)
    return { x: current.x + unit.x * tangential, y: current.y + unit.y * tangential }
}

// ---------------------------------------------------------------------------
// FOV policy
// ---------------------------------------------------------------------------

export type FovPreset = 'NORMAL' | 'WIDE' | 'ULTRA_WIDE'
export const FOV_PRESETS: readonly FovPreset[] = ['NORMAL', 'WIDE', 'ULTRA_WIDE']

/** Horizontal lens angle (degrees) per preset. Bounded well away from 180°. */
export function resolveWalkthroughFovDegrees(preset: FovPreset): number {
    switch (preset) {
        case 'WIDE': return 90
        case 'ULTRA_WIDE': return 110
        case 'NORMAL':
        default: return 70 // GENERIC_NAVIGATION_ASSUMPTION
    }
}

/** Clamp any FOV to safe camera limits (no 0/negative/near-180 singularity). */
export function clampFovDegrees(deg: number): number {
    if (!Number.isFinite(deg)) return 70
    return Math.max(35, Math.min(120, deg))
}

// ---------------------------------------------------------------------------
// Continuous heading + turn-around
// ---------------------------------------------------------------------------

/** Rotate a yaw by ~180° preserving position/pitch (turn-around). */
export function turnAroundYaw(yaw: number): number {
    return yaw + Math.PI
}

// ---------------------------------------------------------------------------
// Storey cutaway policy
// ---------------------------------------------------------------------------

export interface StoreyRange { id: string; label: string; zLow: number; zHigh: number }

export interface CutawayInstruction {
    allBuilding: boolean
    /** When not allBuilding: clip below/above to isolate the storey (+headroom). */
    clipLow?: number
    clipHigh?: number
    /** Target elevation for the reframe camera. */
    focusZ?: number
    storeyId?: string
}

export const ALL_BUILDING_ID = 'ALL_BUILDING'

/**
 * Resolve a view-only cutaway instruction. ALL_BUILDING => no clip. A storey =>
 * clip from just below the storey to just above it (so upper floors are hidden)
 * and focus the camera at the storey. Keyed by storey IDENTITY, not index.
 */
export function resolveStoreyCutaway(input: { selectedStoreyId: string; storeys: readonly StoreyRange[]; headroom?: number }): CutawayInstruction {
    if (input.selectedStoreyId === ALL_BUILDING_ID) return { allBuilding: true }
    const s = input.storeys.find((x) => x.id === input.selectedStoreyId)
    if (!s) return { allBuilding: true }
    const headroom = input.headroom ?? 0.5
    return {
        allBuilding: false,
        clipLow: s.zLow - headroom,
        clipHigh: s.zHigh + headroom,
        focusZ: (s.zLow + s.zHigh) / 2,
        storeyId: s.id,
    }
}

/** Sort storeys by actual elevation (never source-array order). */
export function storeysByElevation(storeys: readonly StoreyRange[]): StoreyRange[] {
    return [...storeys].sort((a, b) => a.zLow - b.zLow)
}

// ---------------------------------------------------------------------------
// Keyboard yaw (MacBook fine steering) — time-based, frame-rate independent
// ---------------------------------------------------------------------------

/** Generic navigation yaw rate (radians/second). Configurable; not calibrated. */
export const KEYBOARD_YAW_RATE_RAD_PER_S = 1.4

/**
 * Integrate continuous yaw from held arrow keys over elapsed time. Left and
 * right simultaneously => neutral (no change). Frame-rate independent: total
 * yaw depends only on total held time, not update count. No quantization.
 */
export function resolveKeyboardYaw(input: {
    yaw: number
    turnLeft: boolean
    turnRight: boolean
    deltaSeconds: number
    yawRate?: number
}): number {
    const rate = input.yawRate ?? KEYBOARD_YAW_RATE_RAD_PER_S
    const dt = Math.max(0, input.deltaSeconds)
    let dir = 0
    if (input.turnLeft) dir += 1
    if (input.turnRight) dir -= 1
    return input.yaw + dir * rate * dt
}

// ---------------------------------------------------------------------------
// Navigation acceptance policy (freeze gate)
// ---------------------------------------------------------------------------

export const NAVIGATION_MANDATORY_ITEMS = [
    'TRUE_FIRST_PERSON_WALKTHROUGH_CAMERA',
    'MACBOOK_SMALL_ANGLE_STEERING',
    'FORWARD_INTERIOR_NAVIGATION',
    'HARD_WALL_COLLISION',
    'REAL_DOOR_PASS',
    'DOOR_LOCALITY_PROOF',
    'WINDOW_BLOCK',
    'TURN_AROUND',
    'FOV_CONTROLS',
    'BIRDS_EYE_STOREY_SELECTOR',
    'FIRST_FLOOR_CUTAWAY',
    'SECOND_FLOOR_CUTAWAY',
    'RETURN_TO_PLANNING',
] as const

export type NavigationItem = typeof NAVIGATION_MANDATORY_ITEMS[number]
export type NavigationAcceptance = 'ACCEPTED' | 'NOT_ACCEPTED'

/**
 * Resolve navigation freeze acceptance: ACCEPTED only when every mandatory item
 * is PASS; otherwise NOT_ACCEPTED with the explicit failing/missing blockers.
 */
export function resolveNavigationAcceptance(results: Partial<Record<NavigationItem, 'PASS' | 'FAIL'>>): { acceptance: NavigationAcceptance; blockers: NavigationItem[] } {
    const blockers = NAVIGATION_MANDATORY_ITEMS.filter((item) => results[item] !== 'PASS')
    return { acceptance: blockers.length === 0 ? 'ACCEPTED' : 'NOT_ACCEPTED', blockers }
}
