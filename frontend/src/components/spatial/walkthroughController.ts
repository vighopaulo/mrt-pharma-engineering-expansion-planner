/**
 * walkthroughController — Bentley runtime for the three camera modes. VIEW-ONLY:
 * it changes the viewport camera + a view clip; it NEVER writes the iModel, emits
 * engineering events, or creates changesets. Dynamically imported so tests / the
 * non-viewer bundle never pull @itwin.
 *
 * PLANNING: leave the existing orbit view as-is (camera off / standard).
 * WALKTHROUGH: first-person camera at eye height + pointer-lock look + WASD move,
 *   with a door-constrained collision step (resolveTraversal). Esc releases.
 * BIRDS_EYE_CUTAWAY: elevated oblique camera + a horizontal storey clip (view
 *   clip) that hides upper geometry so the selected level's interior is visible.
 */
import { IModelApp, type ScreenViewport, type ViewState3d } from '@itwin/core-frontend'
import { Point3d, Vector3d, ClipVector, Angle } from '@itwin/core-geometry'
import {
    WALKTHROUGH_EYE_HEIGHT_M,
    WALKTHROUGH_SPEED_M_PER_S,
    type CameraMode,
} from './cameraNav'
import { candidateEye, clampPitch, eyeZForFloor, resolveFirstPersonOrientation } from './firstPerson'
import {
    clampFovDegrees,
    normalizeWheelDolly,
    resolveKeyboardYaw,
    resolveStoreyCutaway,
    resolveWalkCollision,
    resolveWalkthroughFovDegrees,
    slideAlongWall,
    turnAroundYaw,
    type FovPreset,
    type Portal,
    type StoreyRange,
    type WalkCollisionStorey,
    type WallSegment,
} from './walkNav'

function vp(): ScreenViewport | undefined {
    return IModelApp.viewManager?.selectedView
}

function view3d(v: ScreenViewport): ViewState3d | undefined {
    const view = v.view
    return view.is3d() ? (view as ViewState3d) : undefined
}

// --- storey model (read from Bentley; see loadStoreys) ---
export interface StoreyInfo { id: string; label: string; zLow: number; zHigh: number }

let storeysCache: StoreyInfo[] | undefined

/**
 * Discover the clinic's storeys from the active iModel (BuildingSpatial:Story or
 * SpatialComposition composite ranges). Read-only; falls back to slicing the
 * model Z-extent into N bands if storey ranges are unavailable. Never fabricates
 * floor NAMES — uses the real UserLabel/CodeValue when present.
 */
export async function loadStoreys(): Promise<StoreyInfo[]> {
    if (storeysCache) return storeysCache
    const v = vp()
    if (!v) return []
    const iModel = v.iModel as unknown as { createQueryReader: (sql: string) => AsyncIterable<unknown[]> }

    // Count the ACTUAL storeys (BuildingSpatial:Story ONLY). We never fall back to
    // CompositeElement/Space here — that was the bug that produced ~269 "storey"
    // buttons (rooms/composites). The storey selector must be stories only.
    const stories: { id: string; label: string; elevation?: number }[] = []
    try {
        const r = iModel.createQueryReader(
            `SELECT ECInstanceId, UserLabel, CodeValue FROM BuildingSpatial.Story ORDER BY ECInstanceId`,
        )
        let i = 0
        for await (const row of r) {
            i += 1
            const label = (row[1] as string) ?? (row[2] as string) ?? `Level ${i}`
            stories.push({ id: String(row[0]), label })
        }
    } catch { /* Story class absent */ }

    // Model Z extent to band the storeys into (Story elements often lack a
    // placement bbox; deriving even Z bands across the real storey COUNT is an
    // honest elevation assignment for cutaway/entry, not a fabricated name).
    let zMin = 0, zMax = 0
    try {
        const range = v.view.computeFitRange()
        if (!range.isNull) { zMin = range.low.z; zMax = range.high.z }
    } catch { /* no range */ }

    const out: StoreyInfo[] = []
    const n = stories.length > 0 ? stories.length : (zMax > zMin ? 4 : 0)
    if (n > 0 && zMax > zMin) {
        const h = (zMax - zMin) / n
        for (let i = 0; i < n; i++) {
            const s = stories[i]
            out.push({
                id: s ? s.id : String(i),
                label: s ? s.label : `Level ${i + 1}`,
                zLow: zMin + i * h,
                zHigh: zMin + (i + 1) * h,
            })
        }
    }
    // Sorted by elevation (bands already ordered).
    storeysCache = out
    return out
}

/** Sum bounded counts by architectural class-name search (walls/doors/windows). */
async function queryArchElements(
    iModel: { createQueryReader: (sql: string) => AsyncIterable<unknown[]> },
    terms: string[],
    limit: number,
): Promise<{ id: string; cx: number; cy: number; lx: number; ly: number; hx: number; hy: number }[]> {
    const out: { id: string; cx: number; cy: number; lx: number; ly: number; hx: number; hy: number }[] = []
    try {
        // Find matching classes, then read placement bboxes (bounded).
        const classes: string[] = []
        const cr = iModel.createQueryReader(`SELECT s.Name, c.Name FROM meta.ECClassDef c JOIN meta.ECSchemaDef s ON c.Schema.Id = s.ECInstanceId`)
        for await (const row of cr) {
            const cls = String(row[1]).toLowerCase()
            if (terms.some((t) => cls.includes(t))) classes.push(`${String(row[0])}.${String(row[1])}`)
        }
        for (const full of classes) {
            try {
                const r = iModel.createQueryReader(
                    `SELECT ECInstanceId, BBoxLow.X, BBoxLow.Y, BBoxHigh.X, BBoxHigh.Y, Origin.X, Origin.Y FROM ${full} LIMIT ${limit}`,
                )
                for await (const row of r) {
                    const ox = Number(row[5]) || 0, oy = Number(row[6]) || 0
                    const lx = Number(row[1]) + ox, ly = Number(row[2]) + oy
                    const hx = Number(row[3]) + ox, hy = Number(row[4]) + oy
                    if ([lx, ly, hx, hy].every(Number.isFinite)) {
                        out.push({ id: String(row[0]), cx: (lx + hx) / 2, cy: (ly + hy) / 2, lx, ly, hx, hy })
                    }
                    if (out.length >= limit) break
                }
            } catch { /* class not queryable */ }
            if (out.length >= limit) break
        }
    } catch { /* meta unavailable */ }
    return out
}

/**
 * Build a bounded per-storey walk-collision model from the active BIM: wall
 * segments (long axis of each wall bbox), door portals (door centers), window
 * boundaries. Read-only. Applies to the whole building (single storey plane) for
 * this first pass — sufficient for solid-wall + door-locality collision.
 */
export async function loadWalkCollision(): Promise<WalkCollisionStorey | undefined> {
    const v = vp()
    if (!v) return undefined
    const iModel = v.iModel as unknown as { createQueryReader: (sql: string) => AsyncIterable<unknown[]> }
    const walls = await queryArchElements(iModel, ['wall', 'partition'], 4000)
    const doors = await queryArchElements(iModel, ['door'], 2000)
    const windows = await queryArchElements(iModel, ['window', 'glaz'], 2000)

    const wallBoundaries: WallSegment[] = walls.map((w) => {
        // Segment along the longer horizontal axis of the wall bbox.
        const dx = w.hx - w.lx, dy = w.hy - w.ly
        const seg: WallSegment = dx >= dy
            ? { id: w.id, a: { x: w.lx, y: w.cy }, b: { x: w.hx, y: w.cy }, thickness: Math.max(0.1, dy) }
            : { id: w.id, a: { x: w.cx, y: w.ly }, b: { x: w.cx, y: w.hy }, thickness: Math.max(0.1, dx) }
        return seg
    })
    // Associate each door/window with the nearest wall for portal locality.
    const nearestWallId = (cx: number, cy: number): string => {
        let best = ''; let bestD = Infinity
        for (const w of wallBoundaries) {
            const d = pointSegmentDistance2d({ x: cx, y: cy }, w.a, w.b)
            if (d < bestD) { bestD = d; best = w.id }
        }
        return best
    }
    const doorPortals: Portal[] = doors.map((d) => ({ id: d.id, wallId: nearestWallId(d.cx, d.cy), center: { x: d.cx, y: d.cy }, halfWidth: Math.max(0.5, (d.hx - d.lx + d.hy - d.ly) / 4), traversable: true }))
    const windowBoundaries: Portal[] = windows.map((w) => ({ id: w.id, wallId: nearestWallId(w.cx, w.cy), center: { x: w.cx, y: w.cy }, halfWidth: Math.max(0.4, (w.hx - w.lx + w.hy - w.ly) / 4), traversable: false }))

    const model: WalkCollisionStorey = {
        storeyId: 'all', elevation: 0, wallBoundaries, doorPortals, windowBoundaries,
        nonTraversableOpenings: [], hasFloor: true,
    }
    return model
}

function pointSegmentDistance2d(p: { x: number; y: number }, a: { x: number; y: number }, b: { x: number; y: number }): number {
    const abx = b.x - a.x, aby = b.y - a.y
    const t = Math.max(0, Math.min(1, ((p.x - a.x) * abx + (p.y - a.y) * aby) / Math.max(1e-9, abx * abx + aby * aby)))
    const px = a.x + abx * t, py = a.y + aby * t
    return Math.hypot(p.x - px, p.y - py)
}

/**
 * Apply a horizontal storey cutaway: a view clip that keeps geometry from just
 * below the storey up to just above it, hiding upper floors/roof. VIEW-ONLY.
 */
export function applyStoreyCutaway(storey: StoreyInfo): boolean {
    const v = vp()
    const view = v && view3d(v)
    if (!v || !view) return false
    try {
        const storeyRanges: StoreyRange[] = (storeysCache ?? []).map((s) => ({ id: s.id, label: s.label, zLow: s.zLow, zHigh: s.zHigh }))
        const cut = resolveStoreyCutaway({ selectedStoreyId: storey.id, storeys: storeyRanges })
        const range = v.view.computeFitRange()
        if (cut.allBuilding || cut.clipLow === undefined || cut.clipHigh === undefined) {
            view.setViewClip(undefined)
        } else {
            const poly = [
                Point3d.create(range.low.x - 5, range.low.y - 5, 0),
                Point3d.create(range.high.x + 5, range.low.y - 5, 0),
                Point3d.create(range.high.x + 5, range.high.y + 5, 0),
                Point3d.create(range.low.x - 5, range.high.y + 5, 0),
            ]
            const clip = ClipVector.createEmpty()
            clip.appendShape(poly, cut.clipLow, cut.clipHigh)
            view.setViewClip(clip)
        }
        // Reframe: elevated three-quarter angle focused on the selected storey Z.
        const c = range.center
        const diag = range.low.distance(range.high)
        const focusZ = cut.focusZ ?? c.z
        const eye = Point3d.create(c.x - diag * 0.45, c.y - diag * 0.45, focusZ + diag * 0.6)
        view.lookAt({ eyePoint: eye, targetPoint: Point3d.create(c.x, c.y, focusZ), upVector: Vector3d.create(0, 0, 1), lensAngle: undefined })
        v.invalidateScene()
        v.synchWithView({ animateFrustumChange: true })
        return true
    } catch {
        return false
    }
}

/** Remove any storey cutaway clip (restore full-building view). VIEW-ONLY. */
export function clearStoreyCutaway(): void {
    const v = vp()
    const view = v && view3d(v)
    if (!v || !view) return
    try { view.setViewClip(undefined); v.invalidateScene(); v.synchWithView({ animateFrustumChange: false }) } catch { /* ignore */ }
}

/** Elevated oblique bird's-eye camera framing the whole facility. VIEW-ONLY. */
export function applyBirdsEye(): boolean {
    const v = vp()
    const view = v && view3d(v)
    if (!v || !view) return false
    try {
        const range = v.view.computeFitRange()
        const c = range.center
        const diag = range.low.distance(range.high)
        const eye = Point3d.create(c.x - diag * 0.4, c.y - diag * 0.4, c.z + diag * 0.7)
        view.lookAt({ eyePoint: eye, targetPoint: c, upVector: Vector3d.create(0, 0, 1), lensAngle: undefined })
        v.synchWithView({ animateFrustumChange: true })
        return true
    } catch {
        return false
    }
}

// --- walkthrough first-person state ---
let walkState: {
    yaw: number; pitch: number; pos: Point3d; startPos: Point3d;
    keys: Set<string>; raf: number; lastT: number; fovDeg: number;
    activeStoreyId: string | undefined;
    collisionModel: WalkCollisionStorey | undefined;
    dragging: boolean; lastDragX: number; lastDragY: number;
    applyCamera: () => void;
    applyMove: (input: { forward: number; strafe: number }, distance: number, kind: 'KEY' | 'WHEEL') => boolean;
    onKeyDown: (e: KeyboardEvent) => void; onKeyUp: (e: KeyboardEvent) => void;
    onMouseMove: (e: MouseEvent) => void; onPointerLockChange: () => void;
    onPointerDown: (e: PointerEvent) => void; onPointerUp: () => void;
    onWheel: (e: WheelEvent) => void;
    canvas: HTMLElement;
} | undefined

/** Configurable mouse-look sensitivity (radians per pixel). */
export const MOUSE_LOOK_SENSITIVITY = 0.0022
/** Collision radius (human navigation body). NOT equipment clearance. */
export const WALK_COLLISION_RADIUS_M = 0.35

/**
 * Build 1A walkthrough movement diagnostic — bounded, on-demand (never per-frame
 * console spam). Updated on each movement step; read via diagnoseWalkthroughMovement().
 */
interface WalkMovementDiag {
    active: boolean
    eye: { x: number; y: number; z: number }
    walkDir: { x: number; y: number }
    lastRequestedDirection: { forward: number; strafe: number }
    lastRequestedDisplacement: { dx: number; dy: number }
    lastCandidate: { x: number; y: number }
    lastCollisionResult: string
    lastMovementAccepted: boolean
    lastRejectionReason: string
    activeStorey: string
    // Build 1A incremental-zoom fields.
    lastWheelRawDelta?: number
    lastWheelDeltaMode?: number
    lastWheelNormalizedStep?: number
    lastZoomCameraBefore?: { x: number; y: number; z: number }
    lastZoomCameraAfter?: { x: number; y: number; z: number }
    lastZoomCollisionResult?: string
    lastZoomAccepted?: boolean
    lastZoomRejectionReason?: string
    zoomAnimationActive?: boolean
}
let lastWalkDiag: WalkMovementDiag | undefined

/** The current walkthrough eye position (world), or undefined when not walking. */
export function getWalkEye(): { x: number; y: number; z: number } | undefined {
    const s = walkState
    if (!s) return undefined
    return { x: s.pos.x, y: s.pos.y, z: s.pos.z }
}

/** On-demand bounded walkthrough movement diagnostic (no per-frame logging). */
export function diagnoseWalkthroughMovement(): string {
    const d = lastWalkDiag
    const L: string[] = ['=== WALKTHROUGH MOVEMENT ===']
    if (!d) { L.push('WALKTHROUGH_ACTIVE = NO (enter Walkthrough and move first)'); return L.join('\n') }
    L.push(`WALKTHROUGH_ACTIVE = ${d.active ? 'YES' : 'NO'}`)
    L.push(`EYE_POSITION = (${d.eye.x.toFixed(2)}, ${d.eye.y.toFixed(2)}, ${d.eye.z.toFixed(2)})`)
    L.push(`WALK_DIRECTION = (${d.walkDir.x.toFixed(3)}, ${d.walkDir.y.toFixed(3)})`)
    L.push(`LAST_REQUESTED_DIRECTION = forward ${d.lastRequestedDirection.forward} strafe ${d.lastRequestedDirection.strafe}`)
    L.push(`LAST_REQUESTED_DISPLACEMENT = (${d.lastRequestedDisplacement.dx.toFixed(3)}, ${d.lastRequestedDisplacement.dy.toFixed(3)})`)
    L.push(`LAST_CANDIDATE_POSITION = (${d.lastCandidate.x.toFixed(2)}, ${d.lastCandidate.y.toFixed(2)})`)
    L.push(`LAST_COLLISION_RESULT = ${d.lastCollisionResult}`)
    L.push(`LAST_MOVEMENT_ACCEPTED = ${d.lastMovementAccepted ? 'YES' : 'NO'}`)
    L.push(`LAST_REJECTION_REASON = ${d.lastRejectionReason || '(none)'}`)
    L.push(`ACTIVE_STOREY = ${d.activeStorey}`)
    L.push('--- zoom / dolly ---')
    L.push(`LAST_WHEEL_RAW_DELTA = ${d.lastWheelRawDelta ?? '(none)'}`)
    L.push(`LAST_WHEEL_DELTA_MODE = ${d.lastWheelDeltaMode ?? '(none)'}`)
    L.push(`LAST_WHEEL_NORMALIZED_STEP = ${d.lastWheelNormalizedStep !== undefined ? d.lastWheelNormalizedStep.toFixed(3) : '(none)'}`)
    L.push(`LAST_ZOOM_DOLLY_STEP = ${d.lastWheelNormalizedStep !== undefined ? d.lastWheelNormalizedStep.toFixed(3) : '(none)'}`)
    L.push(`LAST_ZOOM_CAMERA_BEFORE = ${d.lastZoomCameraBefore ? `(${d.lastZoomCameraBefore.x.toFixed(2)}, ${d.lastZoomCameraBefore.y.toFixed(2)}, ${d.lastZoomCameraBefore.z.toFixed(2)})` : '(none)'}`)
    L.push(`LAST_ZOOM_CAMERA_AFTER = ${d.lastZoomCameraAfter ? `(${d.lastZoomCameraAfter.x.toFixed(2)}, ${d.lastZoomCameraAfter.y.toFixed(2)}, ${d.lastZoomCameraAfter.z.toFixed(2)})` : '(none)'}`)
    L.push(`LAST_ZOOM_COLLISION_RESULT = ${d.lastZoomCollisionResult ?? '(none)'}`)
    L.push(`LAST_ZOOM_ACCEPTED = ${d.lastZoomAccepted === undefined ? '(none)' : d.lastZoomAccepted ? 'YES' : 'NO'}`)
    L.push(`LAST_ZOOM_REJECTION_REASON = ${d.lastZoomRejectionReason || '(none)'}`)
    L.push(`ZOOM_ANIMATION_ACTIVE = ${d.zoomAnimationActive ? 'YES' : 'NO'} (incremental; no inertia/spring-back)`)
    return L.join('\n')
}

/**
 * Enter first-person walkthrough. Places the camera at eye height near the model
 * center on the lowest storey, enables pointer-lock look + WASD movement gated by
 * a door-constrained collision probe. Requires an explicit user gesture (the
 * caller invokes this from a click). Esc releases pointer lock.
 */
export async function enterWalkthrough(startStoreyId?: string, fovPreset: FovPreset = 'NORMAL'): Promise<boolean> {
    const v = vp()
    const view = v && view3d(v)
    if (!v || !view) return false
    clearStoreyCutaway()
    try {
        const range = v.view.computeFitRange()
        const storeys = await loadStoreys()
        const chosen = (startStoreyId ? storeys.find((s) => s.id === startStoreyId) : undefined) ?? storeys[0]
        const floorZ = chosen ? chosen.zLow : range.low.z
        const start = Point3d.create(range.center.x, range.center.y, floorZ + WALKTHROUGH_EYE_HEIGHT_M)
        const canvas = v.canvas as HTMLElement
        const collisionModel = await loadWalkCollision()

        const state = {
            yaw: 0, pitch: 0, pos: start, startPos: start.clone(), keys: new Set<string>(),
            raf: 0, lastT: performance.now(), fovDeg: clampFovDegrees(resolveWalkthroughFovDegrees(fovPreset)),
            activeStoreyId: chosen ? chosen.id : undefined as string | undefined,
            collisionModel, dragging: false, lastDragX: 0, lastDragY: 0,
            applyCamera: () => { /* set below */ },
            applyMove: (_i: { forward: number; strafe: number }, _d: number, _k: 'KEY' | 'WHEEL') => false, // set below
            canvas,
            // Build 1A incremental zoom/dolly: MRT Pharma OWNS the wheel during
            // walkthrough (preventDefault stops Bentley's rapid/eased zoom-to-target
            // + spring-back). Each event => one BOUNDED incremental forward/back
            // dolly through the SAME collision + floor-constrained path. No inertia,
            // no animation, no queue — the camera stops and the user steers next.
            onWheel: (e: WheelEvent) => {
                e.preventDefault()
                e.stopPropagation()
                const stepM = normalizeWheelDolly({ deltaY: e.deltaY, deltaMode: e.deltaMode })
                // Record raw wheel facts on the diagnostic even when the step is 0.
                lastWalkDiag = {
                    ...(lastWalkDiag ?? {
                        active: true, eye: { x: state.pos.x, y: state.pos.y, z: state.pos.z },
                        walkDir: { x: 0, y: 0 }, lastRequestedDirection: { forward: 0, strafe: 0 },
                        lastRequestedDisplacement: { dx: 0, dy: 0 }, lastCandidate: { x: state.pos.x, y: state.pos.y },
                        lastCollisionResult: '(none)', lastMovementAccepted: false, lastRejectionReason: '',
                        activeStorey: state.activeStoreyId ?? '(entry)',
                    }),
                    lastWheelRawDelta: e.deltaY,
                    lastWheelDeltaMode: e.deltaMode,
                    lastWheelNormalizedStep: stepM,
                    zoomAnimationActive: false,
                }
                if (stepM === 0) return
                // + step = forward/zoom-in; − = backward. Shift = faster (bounded).
                const dir = stepM > 0 ? 1 : -1
                const dist = Math.abs(stepM) * (state.keys.has('shift') ? 2 : 1)
                state.applyMove({ forward: dir, strafe: 0 }, dist, 'WHEEL')
                state.applyCamera() // immediate; no animation frame wait
            },
            onKeyDown: (e: KeyboardEvent) => {
                const k = e.key.toLowerCase()
                state.keys.add(k)
                if (e.key === 'Escape') exitPointerLock()
                // Prevent the page scrolling on arrow keys during walkthrough.
                if (k === 'arrowup' || k === 'arrowdown' || k === 'arrowleft' || k === 'arrowright') e.preventDefault()
            },
            onKeyUp: (e: KeyboardEvent) => { state.keys.delete(e.key.toLowerCase()) },
            onMouseMove: (e: MouseEvent) => {
                // Two look paths (both first-person yaw/pitch, never orbit):
                //  1. pointer-lock movementX/Y (external mouse), when locked;
                //  2. click-drag delta (MacBook trackpad friendly), when dragging.
                // Build 1A walkthrough final UX: pitch is clamped by the single
                // named authority clampPitch (±MAX_PITCH). Dragging/moving UP
                // (negative movementY) increases pitch => look up; DOWN => look
                // down. Symmetric up/down; never inverts the camera. Pitch only
                // changes the LOOK direction — translation stays horizontal
                // (candidateEye ignores pitch), so looking up/down never drives
                // the pedestrian vertically.
                if (document.pointerLockElement === canvas) {
                    state.yaw -= e.movementX * MOUSE_LOOK_SENSITIVITY
                    state.pitch = clampPitch(state.pitch - e.movementY * MOUSE_LOOK_SENSITIVITY)
                } else if (state.dragging) {
                    const dx = e.clientX - state.lastDragX
                    const dy = e.clientY - state.lastDragY
                    state.lastDragX = e.clientX
                    state.lastDragY = e.clientY
                    state.yaw -= dx * MOUSE_LOOK_SENSITIVITY
                    state.pitch = clampPitch(state.pitch - dy * MOUSE_LOOK_SENSITIVITY)
                }
            },
            onPointerDown: (e: PointerEvent) => {
                // Click-drag look fallback: begin dragging from the canvas.
                state.dragging = true
                state.lastDragX = e.clientX
                state.lastDragY = e.clientY
            },
            onPointerUp: () => { state.dragging = false },
            onPointerLockChange: () => { /* released via Esc -> movement mouse ignored */ },
        }
        walkState = state

        // Fixed floor elevation for this walkthrough session (eye tracks it, no drift).
        const floorElevation = floorZ

        const applyCamera = () => {
            const o = resolveFirstPersonOrientation(state.yaw, state.pitch)
            // TRUE first-person: target is placed FAR ahead along the look
            // direction (10 m), so the eye->target distance is always large. This
            // eliminates the "Too close to target" error. Eye Z pinned to floor +
            // eye height (no drift). Lens angle = current FOV preset.
            const TARGET_DIST = 10
            state.pos = Point3d.create(state.pos.x, state.pos.y, eyeZForFloor(floorElevation, WALKTHROUGH_EYE_HEIGHT_M))
            const target = Point3d.create(
                state.pos.x + o.forward.x * TARGET_DIST,
                state.pos.y + o.forward.y * TARGET_DIST,
                state.pos.z + o.forward.z * TARGET_DIST,
            )
            try {
                view.lookAt({
                    eyePoint: state.pos,
                    targetPoint: target,
                    upVector: Vector3d.create(0, 0, 1),
                    lensAngle: Angle.createDegrees(state.fovDeg),
                    frontDistance: 0.1,
                    backDistance: 5000,
                })
                v.synchWithView({ animateFrustumChange: false })
            } catch { /* transient camera error: skip this frame */ }
        }
        state.applyCamera = applyCamera

        /**
         * Shared move-apply: translate the eye by a bounded horizontal step in the
         * requested walk direction, through the SAME collision + floor-constrained
         * path used by both keyboard walking and wheel dolly. `distance` in meters.
         * Returns whether the move was accepted. Records the movement diagnostic.
         * Floor-constrained (z pinned by applyCamera); never vertical free flight.
         */
        const applyMove = (input: { forward: number; strafe: number }, distance: number, kind: 'KEY' | 'WHEEL'): boolean => {
            const cand = candidateEye({ x: state.pos.x, y: state.pos.y, z: state.pos.z }, state.yaw, input, distance)
            const model = state.collisionModel
            const cur2 = { x: state.pos.x, y: state.pos.y }
            const cand2 = { x: cand.x, y: cand.y }
            const oFlat = resolveFirstPersonOrientation(state.yaw, 0)
            const before = { x: state.pos.x, y: state.pos.y, z: state.pos.z }
            let accepted = false
            let collisionResult = 'NO_MODEL'
            let rejection = ''
            if (!model) {
                state.pos = Point3d.create(cand.x, cand.y, cand.z)
                accepted = true; collisionResult = 'ALLOW'
            } else {
                const decision = resolveWalkCollision({ current: cur2, candidate: cand2, storey: model, collisionRadius: WALK_COLLISION_RADIUS_M })
                collisionResult = decision
                if (decision === 'ALLOW' || decision === 'ALLOW_DOOR') {
                    state.pos = Point3d.create(cand.x, cand.y, cand.z)
                    accepted = true
                } else if (decision === 'BLOCK_WALL') {
                    let bestWall: WallSegment | undefined; let bestD = Infinity
                    for (const w of model.wallBoundaries) {
                        const d = pointSegmentDistance2d(cand2, w.a, w.b)
                        if (d < bestD) { bestD = d; bestWall = w }
                    }
                    if (bestWall) {
                        const slid = slideAlongWall(cur2, cand2, bestWall)
                        const slideOk = resolveWalkCollision({ current: cur2, candidate: slid, storey: model, collisionRadius: WALK_COLLISION_RADIUS_M })
                        if (slideOk === 'ALLOW' || slideOk === 'ALLOW_DOOR') {
                            state.pos = Point3d.create(slid.x, slid.y, cand.z)
                            accepted = true; collisionResult = `${decision}->SLIDE_${slideOk}`
                        } else { rejection = 'BLOCK_WALL (no slide)' }
                    } else { rejection = 'BLOCK_WALL' }
                } else {
                    rejection = decision // BLOCK_WINDOW / BLOCK_UNKNOWN_OPENING / BLOCK_NO_FLOOR => no move.
                }
            }
            const base: WalkMovementDiag = {
                active: true,
                eye: { x: state.pos.x, y: state.pos.y, z: state.pos.z },
                walkDir: { x: oFlat.forwardFlat.x, y: oFlat.forwardFlat.y },
                lastRequestedDirection: { forward: input.forward, strafe: input.strafe },
                lastRequestedDisplacement: { dx: cand.x - cur2.x, dy: cand.y - cur2.y },
                lastCandidate: { x: cand.x, y: cand.y },
                lastCollisionResult: collisionResult,
                lastMovementAccepted: accepted,
                lastRejectionReason: rejection,
                activeStorey: state.activeStoreyId ?? '(entry)',
                // Preserve prior zoom fields unless THIS was a wheel move.
                ...(lastWalkDiag ? {
                    lastWheelRawDelta: lastWalkDiag.lastWheelRawDelta,
                    lastWheelDeltaMode: lastWalkDiag.lastWheelDeltaMode,
                    lastWheelNormalizedStep: lastWalkDiag.lastWheelNormalizedStep,
                } : {}),
            }
            if (kind === 'WHEEL') {
                base.lastZoomCameraBefore = before
                base.lastZoomCameraAfter = { x: state.pos.x, y: state.pos.y, z: state.pos.z }
                base.lastZoomCollisionResult = collisionResult
                base.lastZoomAccepted = accepted
                base.lastZoomRejectionReason = rejection
                base.zoomAnimationActive = false // incremental: never an active animation
            }
            lastWalkDiag = base
            return accepted
        }
        state.applyMove = applyMove

        const step = () => {
            const now = performance.now()
            const dt = Math.min(0.1, (now - state.lastT) / 1000)
            state.lastT = now
            // MacBook fine steering: continuous, time-based arrow-key yaw (does
            // NOT translate the eye). Frame-rate independent; no quantization.
            state.yaw = resolveKeyboardYaw({
                yaw: state.yaw,
                turnLeft: state.keys.has('arrowleft'),
                turnRight: state.keys.has('arrowright'),
                deltaSeconds: dt,
            })
            const speed = WALKTHROUGH_SPEED_M_PER_S * (state.keys.has('shift') ? 2 : 1) * dt
            // Arrow up/down remain forward/back (accepted); W/S too. A/D strafe.
            const input = {
                forward: (state.keys.has('w') || state.keys.has('arrowup') ? 1 : 0) - (state.keys.has('s') || state.keys.has('arrowdown') ? 1 : 0),
                strafe: (state.keys.has('d') ? 1 : 0) - (state.keys.has('a') ? 1 : 0),
            }
            if (input.forward !== 0 || input.strafe !== 0) applyMove(input, speed, 'KEY')
            applyCamera()
            state.raf = requestAnimationFrame(step)
        }

        window.addEventListener('keydown', state.onKeyDown)
        window.addEventListener('keyup', state.onKeyUp)
        window.addEventListener('mousemove', state.onMouseMove)
        canvas.addEventListener('pointerdown', state.onPointerDown)
        window.addEventListener('pointerup', state.onPointerUp)
        document.addEventListener('pointerlockchange', state.onPointerLockChange)
        // { passive: false } so preventDefault stops Bentley's default wheel zoom.
        canvas.addEventListener('wheel', state.onWheel, { passive: false })
        // Do NOT force pointer lock (unreliable on MacBook trackpads). The user
        // steers with arrow keys and/or click-drag look; an external mouse can
        // still request lock by clicking the canvas if desired.
        applyCamera()
        state.raf = requestAnimationFrame(step)
        return true
    } catch {
        return false
    }
}

/** Set the walkthrough FOV preset live (view-only; no engineering side effects). */
export function setWalkthroughFov(preset: FovPreset): void {
    const s = walkState
    if (!s) return
    s.fovDeg = clampFovDegrees(resolveWalkthroughFovDegrees(preset))
    s.applyCamera()
}

/** Turn the camera ~180° in place (preserve eye position, pitch, storey). */
export function turnAround(): void {
    const s = walkState
    if (!s) return
    s.yaw = turnAroundYaw(s.yaw)
    s.applyCamera()
}

function exitPointerLock(): void {
    try { if (document.pointerLockElement) document.exitPointerLock() } catch { /* ignore */ }
}

/** Recover walkthrough: return the eye to the validated entry position. */
export function resetWalkthrough(): void {
    const s = walkState
    if (!s) return
    s.pos = s.startPos.clone()
    s.yaw = 0
    s.pitch = 0
}

/** Exit walkthrough: release pointer, remove listeners, stop the loop. */
export function exitWalkthrough(): void {
    const s = walkState
    if (!s) return
    cancelAnimationFrame(s.raf)
    window.removeEventListener('keydown', s.onKeyDown)
    window.removeEventListener('keyup', s.onKeyUp)
    window.removeEventListener('mousemove', s.onMouseMove)
    s.canvas.removeEventListener('pointerdown', s.onPointerDown)
    window.removeEventListener('pointerup', s.onPointerUp)
    document.removeEventListener('pointerlockchange', s.onPointerLockChange)
    s.canvas.removeEventListener('wheel', s.onWheel)
    exitPointerLock()
    walkState = undefined
    if (lastWalkDiag) lastWalkDiag = { ...lastWalkDiag, active: false }
}

/** Apply a camera mode. Returns whether it took effect. VIEW-ONLY. */
export async function applyCameraMode(mode: CameraMode, opts?: { storey?: StoreyInfo; startStoreyId?: string; fovPreset?: FovPreset }): Promise<boolean> {
    // Always tear down walkthrough listeners when leaving it.
    if (mode !== 'WALKTHROUGH') exitWalkthrough()
    if (mode !== 'BIRDS_EYE_CUTAWAY') clearStoreyCutaway()
    switch (mode) {
        case 'WALKTHROUGH':
            return enterWalkthrough(opts?.startStoreyId, opts?.fovPreset ?? 'NORMAL')
        case 'BIRDS_EYE_CUTAWAY': {
            const ok = applyBirdsEye()
            if (opts?.storey) applyStoreyCutaway(opts.storey)
            else clearStoreyCutaway()
            return ok
        }
        case 'PLANNING':
        default: {
            // Restore a conventional orbit view (clip cleared above; camera/orbit
            // controls are the viewer default — no forced frustum change needed).
            const v = vp()
            try { v?.synchWithView({ animateFrustumChange: false }) } catch { /* ignore */ }
            return true
        }
    }
}
