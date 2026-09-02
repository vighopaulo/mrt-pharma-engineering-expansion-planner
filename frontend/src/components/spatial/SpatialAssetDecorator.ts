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
import { Box, Cone, Point3d, Range3d } from '@itwin/core-geometry'
import { ColorDef } from '@itwin/core-common'
import type { AssetInstance } from '../../domain/assets'
import { applyYaw, buildScannerParts, type ScannerPart, type WorldBox } from './scannerGeometry'

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

export class SpatialAssetDecorator implements Decorator {
    private readonly getInstances: () => readonly AssetInstance[]
    private readonly getSelectedId: () => string | undefined
    private readonly getDragActive: () => boolean

    /**
     * Cache decorations while IDLE (efficient; recreated only when the viewport
     * asks) but NOT during an active fluid drag. Bentley reads this getter each
     * frame: while dragging we return false so the moving scanner is rebuilt
     * from the transient preview transform every frame; when idle we return true
     * so nothing churns. This is the narrow fix for the "marker moves but the
     * scanner geometry stays" defect — cached graphics were being reused at the
     * stale committed position during the drag.
     */
    public get useCachedDecorations(): true | undefined {
        // `true` => cache (idle); `undefined` => no caching so decorate() runs
        // every frame while dragging and the scanner follows the preview.
        return this.getDragActive() ? undefined : true
    }

    /**
     * pickable transient Id64 <-> assetInstanceId map, rebuilt each decorate().
     * Bentley calls testDecorationHit(id) with a picked pickable id; we map it
     * back to the application-owned assetInstanceId.
     */
    private readonly pickIdToInstance = new Map<string, string>()
    private readonly instanceToPickId = new Map<string, string>()

    /** Instances are pulled via a getter so React state can update the source
     * without recreating the decorator instance. Selection + drag-active are
     * also getters so the decorator reads live application state each frame. */
    constructor(
        getInstances: () => readonly AssetInstance[],
        getSelectedId?: () => string | undefined,
        getDragActive?: () => boolean,
    ) {
        this.getInstances = getInstances
        this.getSelectedId = getSelectedId ?? (() => undefined)
        this.getDragActive = getDragActive ?? (() => false)
    }

    /** Resolve a picked pickable id back to an application-owned asset id. */
    assetIdForPickId(pickId: string): string | undefined {
        return this.pickIdToInstance.get(pickId)
    }

    /** Bentley picking hook: does this pickable id belong to this decorator? */
    testDecorationHit(id: string): boolean {
        return this.pickIdToInstance.has(id)
    }

    /** Pure planning (Bentley-free) used by tests to prove the mapping. */
    static planFor(instances: readonly AssetInstance[]): DecorationPlan[] {
        return instances.map((inst) => ({
            instanceId: inst.assetInstanceId,
            displayLabel: inst.displayLabel,
            parts: buildScannerParts(inst).map((p) => ({ part: p.part, kind: p.kind })),
        }))
    }

    /** Allocate/reuse a pickable transient id for an instance for this frame. */
    private pickIdFor(inst: AssetInstance, iModel: { transientIds: { getNext(): string } } | undefined): string | undefined {
        if (!iModel) return undefined
        const existing = this.instanceToPickId.get(inst.assetInstanceId)
        if (existing) return existing
        const id = iModel.transientIds.getNext()
        this.instanceToPickId.set(inst.assetInstanceId, id)
        this.pickIdToInstance.set(id, inst.assetInstanceId)
        return id
    }

    decorate(context: DecorateContext): void {
        const instances = this.getInstances()
        // Rebuild the pick map for the current instance set (drop stale entries).
        const liveIds = new Set(instances.map((i) => i.assetInstanceId))
        for (const [instId, pickId] of Array.from(this.instanceToPickId)) {
            if (!liveIds.has(instId)) {
                this.instanceToPickId.delete(instId)
                this.pickIdToInstance.delete(pickId)
            }
        }
        if (!instances.length) return
        const iModel = context.viewport.iModel as unknown as { transientIds: { getNext(): string } }
        const selectedId = this.getSelectedId()
        for (const inst of instances) {
            try {
                const pickId = this.pickIdFor(inst, iModel)
                this.decorateInstance(context, inst, pickId, inst.assetInstanceId === selectedId)
            } catch {
                // A single bad instance must never break the whole overlay.
            }
        }
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
