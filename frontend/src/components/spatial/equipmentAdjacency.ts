/**
 * equipmentAdjacency — EVI-MA-04 pure, Bentley-free adjacency + vestibule-pose
 * logic. Proves the spatial doctrine:
 *
 *   cyclotron parent room  →  shared wall  →  adjoining room candidate  →
 *   MRT Radiopharmacy Vestibule placed wall-adjacent in that DIFFERENT room.
 *
 * This is intentionally NOT a routing optimizer and does NOT create MRT
 * transport. It is a deterministic nearest-adjoining-room query over room
 * footprints plus a wall-adjacent pose seed for the vestibule. Rendering and
 * lifecycle wiring stay in the overlay/decorator; this module is unit-testable.
 */

export interface Vec2 { x: number; y: number }

/** A room footprint for adjacency reasoning (world-XY outer loop + optional Z). */
export interface AdjacencyRoom {
    bimSpaceId: string
    outerLoop: readonly Vec2[]
    floorZ?: number
    ceilingZ?: number
}

/** Axis-aligned XY bounds of a ring. */
function boundsOf(ring: readonly Vec2[]): { minX: number; minY: number; maxX: number; maxY: number; cx: number; cy: number } | undefined {
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

/**
 * The length of shared wall (overlapping edge) between two axis-aligned room
 * bounds, plus the gap between them, considering them "adjoining" when they are
 * within `wallTolerance` on one axis AND overlap on the other. Returns the
 * shared-edge length (0 when not adjoining on that pairing).
 */
export interface AdjacencyEvaluation {
    bimSpaceId: string
    sharedWallLength: number
    gap: number
    /** Which side of the source room the candidate is on. */
    side: 'X_MIN' | 'X_MAX' | 'Y_MIN' | 'Y_MAX' | 'NONE'
}

export function evaluateAdjacency(source: AdjacencyRoom, candidate: AdjacencyRoom, wallTolerance = 0.6): AdjacencyEvaluation {
    const a = boundsOf(source.outerLoop)
    const b = boundsOf(candidate.outerLoop)
    const none: AdjacencyEvaluation = { bimSpaceId: candidate.bimSpaceId, sharedWallLength: 0, gap: Infinity, side: 'NONE' }
    if (!a || !b) return none

    // Candidate on +X side: b.minX is just beyond a.maxX; Y ranges overlap.
    const yOverlap = Math.min(a.maxY, b.maxY) - Math.max(a.minY, b.minY)
    const xOverlap = Math.min(a.maxX, b.maxX) - Math.max(a.minX, b.minX)

    const options: AdjacencyEvaluation[] = []
    // X_MAX (candidate to the +X of source)
    if (yOverlap > 0) {
        options.push({ bimSpaceId: candidate.bimSpaceId, sharedWallLength: yOverlap, gap: Math.abs(b.minX - a.maxX), side: 'X_MAX' })
        options.push({ bimSpaceId: candidate.bimSpaceId, sharedWallLength: yOverlap, gap: Math.abs(a.minX - b.maxX), side: 'X_MIN' })
    }
    if (xOverlap > 0) {
        options.push({ bimSpaceId: candidate.bimSpaceId, sharedWallLength: xOverlap, gap: Math.abs(b.minY - a.maxY), side: 'Y_MAX' })
        options.push({ bimSpaceId: candidate.bimSpaceId, sharedWallLength: xOverlap, gap: Math.abs(a.minY - b.maxY), side: 'Y_MIN' })
    }
    // The best pairing: smallest gap within tolerance, then longest shared wall.
    let best = none
    for (const o of options) {
        if (o.gap > wallTolerance) continue
        if (best.side === 'NONE' || o.gap < best.gap || (o.gap === best.gap && o.sharedWallLength > best.sharedWallLength)) {
            best = o
        }
    }
    return best
}

/**
 * Find the best adjoining room candidate for the vestibule: the neighbor that
 * shares the longest wall (within tolerance) with the source (cyclotron) room,
 * EXCLUDING the source room itself. Deterministic; ties break by longer shared
 * wall then by bimSpaceId. Returns undefined when nothing adjoins.
 */
export function findVestibuleAdjacentRoom(
    sourceRoomId: string,
    rooms: readonly AdjacencyRoom[],
    wallTolerance = 0.6,
): AdjacencyEvaluation | undefined {
    const source = rooms.find((r) => r.bimSpaceId === sourceRoomId)
    if (!source) return undefined
    let best: AdjacencyEvaluation | undefined
    for (const cand of rooms) {
        if (cand.bimSpaceId === sourceRoomId) continue // NEVER the same room
        const evalr = evaluateAdjacency(source, cand, wallTolerance)
        if (evalr.side === 'NONE' || evalr.sharedWallLength <= 0) continue
        if (!best
            || evalr.sharedWallLength > best.sharedWallLength
            || (evalr.sharedWallLength === best.sharedWallLength && evalr.bimSpaceId < best.bimSpaceId)) {
            best = evalr
        }
    }
    return best
}

export interface VestibulePose {
    centerX: number
    centerY: number
    zBase: number
    width: number
    depth: number
    height: number
    yaw: number
}

/**
 * Seed a wall-ADJACENT vestibule pose INSIDE the adjoining room, hugging the
 * wall shared with the source (cyclotron) room and facing away from it. The
 * vestibule is compact (not room-sized) and sits fully inside the adjoining
 * room footprint (never through the wall, never overlapping the cyclotron room).
 * `side` is the side of the SOURCE room the adjoining room is on.
 */
export function seedVestibulePoseInAdjoiningRoom(input: {
    adjoiningRoom: AdjacencyRoom
    side: AdjacencyEvaluation['side']
    width?: number
    depth?: number
    height?: number
}): VestibulePose | undefined {
    const b = boundsOf(input.adjoiningRoom.outerLoop)
    if (!b) return undefined
    const width = input.width ?? 1.1
    const depth = input.depth ?? 0.8
    const height = input.height ?? 1.6
    const inset = 0.15 // hug the wall but stay inside the room
    let cx = b.cx, cy = b.cy
    // Place against the wall shared with the source room. If the adjoining room
    // is on the source's X_MAX side, the shared wall is the adjoining room's
    // X_MIN edge; hug it.
    switch (input.side) {
        case 'X_MAX': cx = b.minX + depth / 2 + inset; cy = b.cy; break
        case 'X_MIN': cx = b.maxX - depth / 2 - inset; cy = b.cy; break
        case 'Y_MAX': cy = b.minY + depth / 2 + inset; cx = b.cx; break
        case 'Y_MIN': cy = b.maxY - depth / 2 - inset; cx = b.cx; break
        default: return undefined
    }
    // Yaw so the vestibule "front" (-Y) / throat (+Y) aligns toward the shared
    // wall. For X-side adjacency rotate 90°.
    const yaw = (input.side === 'X_MAX' || input.side === 'X_MIN') ? Math.PI / 2 : 0
    return {
        centerX: cx,
        centerY: cy,
        zBase: input.adjoiningRoom.floorZ ?? 0,
        width,
        depth,
        height,
        yaw,
    }
}
