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

export class SpatialAssetDecorator implements Decorator {
    /** Cache decorations while idle — recreated only when the viewport asks. */
    public readonly useCachedDecorations = true as const

    private readonly getInstances: () => readonly AssetInstance[]

    /** Instances are pulled via a getter so React state can update the source
     * without recreating the decorator instance. */
    constructor(getInstances: () => readonly AssetInstance[]) {
        this.getInstances = getInstances
    }

    /** Pure planning (Bentley-free) used by tests to prove the mapping. */
    static planFor(instances: readonly AssetInstance[]): DecorationPlan[] {
        return instances.map((inst) => ({
            instanceId: inst.assetInstanceId,
            displayLabel: inst.displayLabel,
            parts: buildScannerParts(inst).map((p) => ({ part: p.part, kind: p.kind })),
        }))
    }

    decorate(context: DecorateContext): void {
        const instances = this.getInstances()
        if (!instances.length) return
        for (const inst of instances) {
            try {
                this.decorateInstance(context, inst)
            } catch {
                // A single bad instance must never break the whole overlay.
            }
        }
    }

    private decorateInstance(context: DecorateContext, inst: AssetInstance): void {
        const parts = buildScannerParts(inst)
        for (const part of parts) {
            const builder = context.createGraphicBuilder(GraphicType.WorldDecoration)
            const [r, g, b] = PART_COLOR[part.part]
            const color = ColorDef.from(r, g, b)
            builder.setSymbology(color, color, 1)

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
