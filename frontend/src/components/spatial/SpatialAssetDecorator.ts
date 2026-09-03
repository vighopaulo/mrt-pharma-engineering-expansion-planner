/**
 * SpatialAssetDecorator — renders MRT Pharma spatial asset instances as a
 * Bentley world-decoration OVERLAY inside the existing live viewport. It does
 * NOT modify the connected iModel, create changesets, or own asset identity.
 *
 * Relationship (per doctrine):
 *   AssetInstance[] → SpatialAssetDecorator → DecorateContext/GraphicBuilder → viewport graphics
 *
 * The decorator reads instances through a getter, so its identity is stable
 * across React renders. `useCachedDecorations = true` means Bentley only calls
 * decorate() when it must, keeping the overlay stable while idle.
 */
import { GraphicType, type DecorateContext, type Decorator } from '@itwin/core-frontend'
import { Arc3d, Box, Cone, Point3d, Range3d, TorusPipe } from '@itwin/core-geometry'
import { ColorDef } from '@itwin/core-common'
import type { AssetInstance } from '../../domain/assets'
import { applyYaw, buildScannerParts, type ScannerPart, type WorldBox } from './scannerGeometry'
import { resolveRotationHandleVisualState, type RotationHandleVisualState } from './assetPicking'

/** Sanitized, serializable snapshot of what the decorator would draw (for tests). */
export interface DecorationPlan {
    instanceId: string
    displayLabel: string
    parts: { part: ScannerPart; kind: 'BOX' | 'CYLINDER' }[]
}

const PART_COLOR: Record<ScannerPart, [number, number, number]> = {
    GANTRY: [180, 190, 205], // light steel
    BORE: [90, 110, 140], // darker inset
    PATIENT_TABLE: [210, 210, 215], // pale table
}

/** Highlight color for the directly-selected asset (application-owned render
 * state only — NOT a geometry-identity change and NOT transparency). */
const SELECTION_COLOR: [number, number, number] = [255, 196, 0] // amber outline
/** Object-attached rotation handle color (grey — NOT orange/yellow). Prominence
 * is controlled by the visual state (faint idle hint vs clear active). */
const HANDLE_COLOR: [number, number, number] = [150, 155, 160] // neutral grey ring

export class SpatialAssetDecorator implements Decorator {
    private readonly getInstances: () => readonly AssetInstance[]
    private readonly getSelectedId: () => string | undefined
    private readonly getDragActive: () => boolean
    private readonly getRotationActive: () => boolean
    private readonly getSelectedIds: () => readonly string[]
    private readonly getGroupDragActive: () => boolean
    private readonly getHandleHover: () => boolean

    /**
     * Cache decorations while IDLE (efficient) but NOT during an active fluid
     * drag, rotation, or GROUP drag. Bentley reads this getter each frame: while
     * manipulating we return undefined so active members rebuild from the
     * transient preview every frame; when idle we return true so nothing churns.
     */
    public get useCachedDecorations(): true | undefined {
        return (this.getDragActive() || this.getRotationActive() || this.getGroupDragActive()) ? undefined : true
    }

    /**
     * pickable transient Id64 <-> assetInstanceId maps, rebuilt each decorate().
     * The BODY map and the ROTATION HANDLE map are separate so a picked id can
     * be resolved to either an ASSET_BODY (translate) or a ROTATION_HANDLE
     * (rotate) target for the same assetInstanceId.
     */
    private readonly pickIdToInstance = new Map<string, string>()
    private readonly instanceToPickId = new Map<string, string>()
    private readonly handlePickIdToInstance = new Map<string, string>()
    private readonly instanceToHandlePickId = new Map<string, string>()

    /** Instances are pulled via a getter so React state can update the source
     * without recreating the decorator instance. Selection + drag-active +
     * rotation-active are getters so the decorator reads live state each frame. */
    constructor(
        getInstances: () => readonly AssetInstance[],
        getSelectedId?: () => string | undefined,
        getDragActive?: () => boolean,
        getRotationActive?: () => boolean,
        getSelectedIds?: () => readonly string[],
        getGroupDragActive?: () => boolean,
        getHandleHover?: () => boolean,
    ) {
        this.getInstances = getInstances
        this.getSelectedId = getSelectedId ?? (() => undefined)
        this.getDragActive = getDragActive ?? (() => false)
        this.getRotationActive = getRotationActive ?? (() => false)
        this.getSelectedIds = getSelectedIds ?? (() => {
            const id = this.getSelectedId()
            return id ? [id] : []
        })
        this.getGroupDragActive = getGroupDragActive ?? (() => false)
        this.getHandleHover = getHandleHover ?? (() => false)
    }

    /** Resolve a picked BODY pick id to an application-owned asset id. */
    assetIdForPickId(pickId: string): string | undefined {
        return this.pickIdToInstance.get(pickId)
    }

    /** Resolve a picked ROTATION HANDLE pick id to its asset id. */
    handleAssetIdForPickId(pickId: string): string | undefined {
        return this.handlePickIdToInstance.get(pickId)
    }

    /** Bentley picking hook: does this pickable id belong to this decorator
     * (either an asset body or a rotation handle)? */
    testDecorationHit(id: string): boolean {
        return this.pickIdToInstance.has(id) || this.handlePickIdToInstance.has(id)
    }

    /**
     * DIAGNOSIS/FALLBACK SUPPORT: expose the selected asset's current body +
     * handle pick ids (read-only). The tool uses this to (a) log the runtime
     * handle-map generation and (b) resolve a scoped screen-space handle pick
     * when native locate returns the body instead of the thin torus. Keyed by
     * assetInstanceId — transient pick ids are never treated as identity.
     */
    handlePickIdForInstance(assetInstanceId: string): string | undefined {
        return this.instanceToHandlePickId.get(assetInstanceId)
    }
    bodyPickIdForInstance(assetInstanceId: string): string | undefined {
        return this.instanceToPickId.get(assetInstanceId)
    }
    /** Monotonic generation counter, bumped every decorate() rebuild. */
    private decorateGeneration = 0
    getDecorateGeneration(): number {
        return this.decorateGeneration
    }
    /**
     * Geometry of the selected asset's rotation ring in WORLD space, for the
     * scoped screen-space fallback. center = ring center (x,y,z), radius = the
     * ring major radius. Returns undefined if the id isn't the current handle.
     */
    rotationRingWorldFor(inst: AssetInstance): { center: [number, number, number]; radius: number } {
        const p = inst.transform.position
        const s = inst.transform.scale
        const w = inst.dimensions.width * s.x
        const d = inst.dimensions.depth * s.y
        const h = inst.dimensions.height * s.z
        const majorRadius = Math.max(Math.hypot(w, d) * 0.5 * 1.15, 1.5)
        const ringZ = p.z + h + 0.3
        return { center: [p.x, p.y, ringZ], radius: majorRadius }
    }

    /** Pure planning (Bentley-free) used by tests to prove the mapping. */
    static planFor(instances: readonly AssetInstance[]): DecorationPlan[] {
        return instances.map((inst) => ({
            instanceId: inst.assetInstanceId,
            displayLabel: inst.displayLabel,
            parts: buildScannerParts(inst).map((p) => ({ part: p.part, kind: p.kind })),
        }))
    }

    /** Allocate/reuse a pickable BODY transient id for an instance this frame. */
    private pickIdFor(inst: AssetInstance, iModel: { transientIds: { getNext(): string } } | undefined): string | undefined {
        if (!iModel) return undefined
        const existing = this.instanceToPickId.get(inst.assetInstanceId)
        if (existing) return existing
        const id = iModel.transientIds.getNext()
        this.instanceToPickId.set(inst.assetInstanceId, id)
        this.pickIdToInstance.set(id, inst.assetInstanceId)
        return id
    }

    /** Allocate/reuse a pickable ROTATION HANDLE transient id for the selected
     * instance this frame (only the selected asset has a handle). */
    private handlePickIdFor(inst: AssetInstance, iModel: { transientIds: { getNext(): string } } | undefined): string | undefined {
        if (!iModel) return undefined
        const existing = this.instanceToHandlePickId.get(inst.assetInstanceId)
        if (existing) return existing
        const id = iModel.transientIds.getNext()
        this.instanceToHandlePickId.set(inst.assetInstanceId, id)
        this.handlePickIdToInstance.set(id, inst.assetInstanceId)
        return id
    }

    private dropStale(map: Map<string, string>, reverse: Map<string, string>, liveIds: Set<string>): void {
        for (const [instId, pickId] of Array.from(map)) {
            if (!liveIds.has(instId)) {
                map.delete(instId)
                reverse.delete(pickId)
            }
        }
    }

    decorate(context: DecorateContext): void {
        this.decorateGeneration += 1
        const instances = this.getInstances()
        const selectedIds = new Set(this.getSelectedIds())
        // The rotation handle owner: the SOLE selected app asset (multi-select
        // hides the single-object handle; there is no group rotation).
        const handleOwnerId = selectedIds.size === 1 ? Array.from(selectedIds)[0] : undefined
        // Rebuild the pick maps for the current instance set (drop stale entries).
        const liveIds = new Set(instances.map((i) => i.assetInstanceId))
        this.dropStale(this.instanceToPickId, this.pickIdToInstance, liveIds)
        // Handle map: keep only the single handle-owner + live instance.
        const liveHandleIds = new Set(handleOwnerId && liveIds.has(handleOwnerId) ? [handleOwnerId] : [])
        this.dropStale(this.instanceToHandlePickId, this.handlePickIdToInstance, liveHandleIds)
        if (!instances.length) return
        const iModel = context.viewport.iModel as unknown as { transientIds: { getNext(): string } }
        // Rotation-handle visual state for the sole selected asset.
        const handleState: RotationHandleVisualState = resolveRotationHandleVisualState({
            isOwnedAppAsset: true, // decorator draws only application-owned instances
            isThisSelected: handleOwnerId !== undefined,
            selectedCount: selectedIds.size,
            hover: this.getHandleHover(),
            rotating: this.getRotationActive(),
        })
        for (const inst of instances) {
            try {
                const selected = selectedIds.has(inst.assetInstanceId)
                const pickId = this.pickIdFor(inst, iModel)
                this.decorateInstance(context, inst, pickId, selected)
                if (inst.assetInstanceId === handleOwnerId && handleState !== 'HIDDEN') {
                    // Grey object-attached rotation handle for the SOLE selected
                    // asset only, prominence per visual state. Pick id stays
                    // allocated so the scoped screen-space fallback works.
                    const handlePickId = this.handlePickIdFor(inst, iModel)
                    this.decorateRotationHandle(context, inst, handlePickId, handleState)
                }
            } catch {
                // A single bad instance must never break the whole overlay.
            }
        }
    }

    /**
     * Draw the object-attached yaw rotation handle: a horizontal torus (ring)
     * centered on the instance, slightly above its top, pickable with its own
     * transient id. It follows the instance's (possibly previewed) position.
     *
     * IMPORTANT: the handle is a SOLID torus on a WorldDecoration builder — the
     * SAME reliable pick path as the scanner body. A prior hairline Arc3d on a
     * WorldOverlay builder had negligible pick area and did not participate in
     * locate the same way, so clicking the ring resolved to the body underneath
     * (translate) instead of the handle (rotate). The torus gives a real,
     * grabbable pick surface while remaining a thin ring (body drag stays
     * available inside/outside it).
     */
    private decorateRotationHandle(
        context: DecorateContext,
        inst: AssetInstance,
        handlePickId: string | undefined,
        visualState: RotationHandleVisualState,
    ): void {
        const p = inst.transform.position
        const s = inst.transform.scale
        const w = inst.dimensions.width * s.x
        const d = inst.dimensions.depth * s.y
        const h = inst.dimensions.height * s.z
        // Ring radius a bit larger than the footprint half-diagonal; sits just
        // above the top of the scanner so it is easy to grab.
        const majorRadius = Math.max(Math.hypot(w, d) * 0.5 * 1.15, 1.5)
        const minorRadius = Math.max(majorRadius * 0.09, 0.18) // tube thickness (pick surface)
        const ringZ = p.z + h + 0.3
        const center = Point3d.create(p.x, p.y, ringZ)
        const arc = Arc3d.createXY(center, majorRadius)
        const torus = TorusPipe.createAlongArc(arc, minorRadius, true /* capped */)
        // Prominence via transparency (0=opaque, 255=fully transparent). The
        // handle geometry (and thus pick surface) is always drawn so it stays
        // discoverable; only its visibility changes. IDLE_HINT is very faint.
        const transparency = visualState === 'ACTIVE_ROTATION' ? 0
            : visualState === 'HOVER' ? 70
                : 205 // IDLE_HINT: extremely faint grey
        const color = ColorDef.from(...HANDLE_COLOR).withTransparency(transparency)
        const builder = handlePickId
            ? context.createGraphicBuilder(GraphicType.WorldDecoration, undefined, handlePickId)
            : context.createGraphicBuilder(GraphicType.WorldDecoration)
        builder.setSymbology(color, color, 2)
        if (torus) {
            builder.addSolidPrimitive(torus)
        } else {
            // Fallback to a line ring if the torus could not be built.
            builder.addArc(arc, false, false)
        }
        context.addDecorationFromBuilder(builder)
    }

    private decorateInstance(context: DecorateContext, inst: AssetInstance, pickId: string | undefined, selected: boolean): void {
        const parts = buildScannerParts(inst)
        for (const part of parts) {
            // Pickable graphics carry the transient id so a click resolves back
            // to this instance via testDecorationHit + HitDetail.sourceId.
            const builder = pickId
                ? context.createGraphicBuilder(GraphicType.WorldDecoration, undefined, pickId)
                : context.createGraphicBuilder(GraphicType.WorldDecoration)
            const [r, g, b] = PART_COLOR[part.part]
            const fill = ColorDef.from(r, g, b)
            // Selected assets get an amber outline (line color) + heavier weight.
            // This is render state only; geometry identity is unchanged and no
            // transparency is introduced.
            const line = selected ? ColorDef.from(...SELECTION_COLOR) : fill
            builder.setSymbology(line, fill, selected ? 4 : 1)

            if (part.kind === 'BOX') {
                const box = this.buildBox(part)
                if (box) builder.addSolidPrimitive(box)
            } else {
                const cone = Cone.createAxisPoints(
                    Point3d.create(...part.centerA),
                    Point3d.create(...part.centerB),
                    part.radius,
                    part.radius,
                    true,
                )
                if (cone) builder.addSolidPrimitive(cone)
            }
            context.addDecorationFromBuilder(builder)
        }
    }

    private buildBox(part: WorldBox): Box | undefined {
        // Apply yaw to the 8 corners about the instance center, then build a
        // range from the rotated corners. (LOW-LOD generic representation: a
        // yaw-rotated axis-aligned range is sufficient and deterministic.)
        const [lx, ly, lz] = part.low
        const [hx, hy, hz] = part.high
        const corners: [number, number, number][] = [
            [lx, ly, lz], [hx, ly, lz], [lx, hy, lz], [hx, hy, lz],
            [lx, ly, hz], [hx, ly, hz], [lx, hy, hz], [hx, hy, hz],
        ]
        const range = Range3d.createNull()
        for (const c of corners) {
            const [wx, wy, wz] = applyYaw(c, part.center, part.yawRadians)
            range.extendXYZ(wx, wy, wz)
        }
        if (range.isNull) return undefined
        return Box.createRange(range, true)
    }
}
