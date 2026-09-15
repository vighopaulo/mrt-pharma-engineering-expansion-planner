/**
 * appObjectPicking — EVI-MA-06 ONE authoritative application-object pick
 * resolution shared by left-click selection, left-drag, right-click context
 * menu, and the Delete key. Renderer/decorator OWNERSHIP is not lifecycle
 * authority: this module resolves a single `AppObjectPickTarget` from a world
 * ray against ALL application-owned families (equipment + clinical logistics
 * vestibule + legacy asset), so the interaction layer never needs to know which
 * decorator drew a visible object.
 *
 * DOCTRINE:
 *   - Native Bentley/iModel geometry (walls/floors/doors/furniture) and clinical
 *     PLANNING VOLUMES are NEVER application-owned pick targets — they are simply
 *     not in the candidate set, so they can never be returned.
 *   - Every visual subcomponent of one object maps back to ONE instance (the
 *     candidate carries the whole occupied volume for that instance).
 *   - Priority: (1) if the currently SELECTED app object is intersected by the
 *     ray, prefer it; else (2) the nearest valid app object along the ray. Never
 *     select a distant object through a nearer one.
 *
 * This module is PURE (no Bentley, no DOM) and fully unit-testable. The tool
 * builds candidates from the live stores and passes them in.
 */

/** The application-owned object families that support direct manipulation. */
export type AppObjectType = 'ASSET_INSTANCE' | 'EQUIPMENT_INSTANCE' | 'CLINICAL_LOGISTICS_VESTIBULE'

/** A stable reference to one application-owned object (type + id). */
export interface AppObjectRef {
    objectType: AppObjectType
    instanceId: string
}

/** The unified resolved pick target — the ONE result all interactions start from. */
export interface AppObjectPickTarget {
    objectType: AppObjectType
    instanceId: string
    /** Ray parameter t at the entry hit (world units along the ray direction). */
    distance: number
    parentBimSpaceId?: string
    /** May the object be dragged (freestanding move / wall slide)? */
    draggable: boolean
    /** May the object be deleted right now (false when locked)? */
    deletable: boolean
    hidden: boolean
    locked: boolean
}

/** A world pick ray (direction need not be normalized). */
export interface AppPickRay {
    origin: [number, number, number]
    direction: [number, number, number]
}

/** An axis-aligned box candidate volume. */
export interface AabbVolume {
    kind: 'AABB'
    minX: number; minY: number; minZ: number
    maxX: number; maxY: number; maxZ: number
}

/** An oriented (yaw about Z) box candidate volume. */
export interface ObbVolume {
    kind: 'OBB'
    centerX: number; centerY: number; centerZ: number
    halfX: number; halfY: number; halfZ: number
    /** Yaw about the vertical (Z) axis, radians. */
    yaw: number
}

export type CandidateVolume = AabbVolume | ObbVolume

/**
 * One application-owned pick candidate. `volume` is the WHOLE occupied volume of
 * the instance, so a ray hitting ANY visual subcomponent resolves the one
 * instance. `hidden` candidates are excluded from ray picking (their geometry is
 * not drawn) but the tool still includes them for other logic if it wishes.
 */
export interface AppObjectCandidate {
    objectType: AppObjectType
    instanceId: string
    parentBimSpaceId?: string
    volume: CandidateVolume
    hidden: boolean
    locked: boolean
    /** Family policy: can this object be dragged at all (when unlocked)? */
    draggableWhenUnlocked: boolean
    /** Family policy: can this object be deleted at all (when unlocked)? */
    deletableWhenUnlocked: boolean
}

// ---------------------------------------------------------------------------
// Ray/volume intersection (pure)
// ---------------------------------------------------------------------------

/** Nearest positive ray-vs-AABB t (slab test), or undefined. */
export function rayHitAabb(ray: AppPickRay, b: AabbVolume): number | undefined {
    const lo = [b.minX, b.minY, b.minZ]
    const hi = [b.maxX, b.maxY, b.maxZ]
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

/** Nearest positive ray-vs-oriented-box t (transform ray into box-local frame). */
export function rayHitObb(ray: AppPickRay, b: ObbVolume): number | undefined {
    // Inverse yaw about Z into the box-local frame, centered on the box.
    const cos = Math.cos(-b.yaw), sin = Math.sin(-b.yaw)
    const ox = ray.origin[0] - b.centerX, oy = ray.origin[1] - b.centerY, oz = ray.origin[2] - b.centerZ
    const lo: [number, number, number] = [ox * cos - oy * sin, ox * sin + oy * cos, oz]
    const dx = ray.direction[0], dy = ray.direction[1], dz = ray.direction[2]
    const ld: [number, number, number] = [dx * cos - dy * sin, dx * sin + dy * cos, dz]
    const half = [b.halfX, b.halfY, b.halfZ]
    let tmin = -Infinity, tmax = Infinity
    for (let i = 0; i < 3; i++) {
        const o = lo[i], d = ld[i], h = half[i]
        if (Math.abs(d) < 1e-12) {
            if (o < -h || o > h) return undefined
        } else {
            let t1 = (-h - o) / d, t2 = (h - o) / d
            if (t1 > t2) { const tmp = t1; t1 = t2; t2 = tmp }
            if (t1 > tmin) tmin = t1
            if (t2 < tmax) tmax = t2
            if (tmin > tmax) return undefined
        }
    }
    return tmin >= 0 ? tmin : (tmax >= 0 ? tmax : undefined)
}

function rayHit(ray: AppPickRay, v: CandidateVolume): number | undefined {
    return v.kind === 'AABB' ? rayHitAabb(ray, v) : rayHitObb(ray, v)
}

// ---------------------------------------------------------------------------
// The ONE resolver
// ---------------------------------------------------------------------------

function targetFrom(c: AppObjectCandidate, distance: number): AppObjectPickTarget {
    return {
        objectType: c.objectType,
        instanceId: c.instanceId,
        distance,
        parentBimSpaceId: c.parentBimSpaceId,
        draggable: c.draggableWhenUnlocked && !c.locked,
        deletable: c.deletableWhenUnlocked && !c.locked,
        hidden: c.hidden,
        locked: c.locked,
    }
}

/**
 * Resolve the ONE application-object pick target under a world ray.
 *   1. If `selected` is intersected by the ray, prefer it (the user acts on what
 *      they already selected, even if another object is nearer).
 *   2. Otherwise the nearest valid app object along the ray.
 * Hidden candidates are never picked (their geometry is not visible). Returns
 * undefined for empty/BIM/planning-volume space (those are not candidates).
 * Pure + deterministic (ties resolve to smaller t, never array order).
 */
export function resolveAppObjectPickTarget(
    ray: AppPickRay,
    candidates: readonly AppObjectCandidate[],
    selected?: AppObjectRef,
): AppObjectPickTarget | undefined {
    // Rule 1 — selected-object preference.
    if (selected) {
        const sel = candidates.find(
            (c) => c.objectType === selected.objectType && c.instanceId === selected.instanceId && !c.hidden,
        )
        if (sel) {
            const t = rayHit(ray, sel.volume)
            if (t !== undefined) return targetFrom(sel, t)
        }
    }
    // Rule 2 — nearest valid app object.
    let best: { c: AppObjectCandidate; t: number } | undefined
    for (const c of candidates) {
        if (c.hidden) continue
        const t = rayHit(ray, c.volume)
        if (t === undefined) continue
        if (!best || t < best.t) best = { c, t }
    }
    return best ? targetFrom(best.c, best.t) : undefined
}

// ---------------------------------------------------------------------------
// Delete-key focus safety (pure predicate)
// ---------------------------------------------------------------------------

/**
 * True when the given active element is a TEXT-EDITING context (input, textarea,
 * select, or contenteditable), where a Delete/Backspace keystroke must NEVER
 * delete an application object. Pure over a minimal element shape so it is unit-
 * testable without a DOM. The tool passes `document.activeElement`.
 */
export function isTextEditingElement(el: {
    tagName?: string
    isContentEditable?: boolean
} | null | undefined): boolean {
    if (!el) return false
    if (el.isContentEditable) return true
    const tag = (el.tagName ?? '').toUpperCase()
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
}

/** DOM convenience: is the current document focus a text-editing element? */
export function isTextEditingFocus(): boolean {
    if (typeof document === 'undefined') return false
    return isTextEditingElement(document.activeElement as { tagName?: string; isContentEditable?: boolean } | null)
}
