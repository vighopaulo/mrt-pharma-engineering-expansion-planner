/**
 * RoomPlanDecorator — VIEW-ONLY derived hospital planning context.
 *
 * CONTEXT (Visual Planning Foundation — Correction 2): the connected iModel is a
 * spatial-semantic model (BuildingSpatial:Space ranges) with limited detailed
 * architecture. Rather than hiding those volumes (which removed all context) or
 * rendering them as dominant translucent boxes, this decorator draws a restrained
 * PLAN-LIKE context DERIVED from the authoritative room ranges:
 *   - a thin room-perimeter outline + very light fill at a planning elevation,
 *   - the room's own BIM label (restrained, low clutter),
 *   - only for footprints visible at the active planning elevation.
 *
 * It is a Bentley DECORATION only: it creates NO iModel elements, writes NO
 * changeset, and mutates NO engineering/association state. The derived footprints
 * come from the pure planningPlan seams applied to the cached SpatialModelSemantics
 * (the source of truth). It never becomes the association authority.
 *
 * Normal mode: draws the derived plan. Developer mode: draws nothing (the raw BIM
 * volumes + diagnostics remain the developer representation), so the two modes do
 * not double-render.
 */
import { GraphicType, type DecorateContext, type Decorator } from '@itwin/core-frontend'
import { Point3d } from '@itwin/core-geometry'
import { ColorDef } from '@itwin/core-common'
import type { SpatialRoomReference } from '../../domain/assets'
import {
    deriveRoomPlan,
    resolvePlanningElevation,
    visibleFootprintsAtElevation,
    type PlanFootprint,
} from './planningPlan'
import type { ViewerMode } from './planningVisuals'

// Restrained hospital-planning palette (view-only).
const ROOM_OUTLINE: [number, number, number] = [120, 150, 190] // muted blue-grey
const ROOM_FILL: [number, number, number] = [90, 120, 160]
const ROOM_FILL_TRANSPARENCY = 210 // 0=opaque, 255=invisible; very light fill
const LABEL_COLOR: [number, number, number] = [200, 214, 230]

export interface RoomPlanInputs {
    /** The active viewer mode; the plan is drawn only in NORMAL_PLANNING. */
    getMode: () => ViewerMode
    /** The cached, authoritative BIM room references (source of truth). */
    getRooms: () => readonly SpatialRoomReference[]
    /** An honest planning elevation source: the selected/placed asset Z if any. */
    getSelectedAssetZ: () => number | undefined
    /** Whether to render restrained room labels. */
    getShowLabels?: () => boolean
}

export class RoomPlanDecorator implements Decorator {
    public readonly useCachedDecorations = true
    private readonly inputs: RoomPlanInputs

    constructor(inputs: RoomPlanInputs) {
        this.inputs = inputs
    }

    /** Derive the footprints visible at the active planning elevation (pure). */
    private computeVisibleFootprints(): { footprints: PlanFootprint[]; elevation: number } {
        const rooms = this.inputs.getRooms()
        const all = deriveRoomPlan(rooms)
        const { elevation } = resolvePlanningElevation({
            selectedAssetZ: this.inputs.getSelectedAssetZ(),
            footprints: all,
        })
        return { footprints: visibleFootprintsAtElevation(all, elevation), elevation }
    }

    decorate(context: DecorateContext): void {
        // Normal planning mode only. Developer mode keeps the raw BIM volumes.
        if (this.inputs.getMode() !== 'NORMAL_PLANNING') return
        const { footprints } = this.computeVisibleFootprints()
        if (footprints.length === 0) return

        const showLabels = this.inputs.getShowLabels?.() ?? true
        for (const fp of footprints) {
            this.drawFootprint(context, fp)
            if (showLabels) this.drawLabel(context, fp)
        }
    }

    private drawFootprint(context: DecorateContext, fp: PlanFootprint): void {
        if (fp.ring.length < 3) return
        const builder = context.createGraphicBuilder(GraphicType.WorldDecoration)
        const outline = ColorDef.from(...ROOM_OUTLINE)
        const fill = ColorDef.from(...ROOM_FILL).withTransparency(ROOM_FILL_TRANSPARENCY)
        builder.setSymbology(outline, fill, 2)
        const loop = fp.ring.map((p) => Point3d.create(p.x, p.y, fp.elevation))
        // Very light plan fill (closed shape) — no tall translucent volume.
        builder.addShape([...loop, loop[0]])
        // Crisp thin perimeter on top for legibility.
        const outlineBuilder = context.createGraphicBuilder(GraphicType.WorldDecoration)
        outlineBuilder.setSymbology(outline, outline, 2)
        outlineBuilder.addLineString([...loop, loop[0]])
        context.addDecorationFromBuilder(builder)
        context.addDecorationFromBuilder(outlineBuilder)
    }

    private drawLabel(context: DecorateContext, fp: PlanFootprint): void {
        if (!fp.label) return
        // Centroid of the footprint at the planning elevation.
        const cx = fp.ring.reduce((s, p) => s + p.x, 0) / fp.ring.length
        const cy = fp.ring.reduce((s, p) => s + p.y, 0) / fp.ring.length
        const world = Point3d.create(cx, cy, fp.elevation)
        const view = context.viewport.worldToView(world)
        // Restrained screen label at the room centroid. Skip if off-screen.
        if (!Number.isFinite(view.x) || !Number.isFinite(view.y)) return
        const div = document.createElement('div')
        div.className = 'mrt-room-label'
        div.textContent = fp.label
        div.style.position = 'absolute'
        div.style.left = `${Math.round(view.x)}px`
        div.style.top = `${Math.round(view.y)}px`
        div.style.transform = 'translate(-50%, -50%)'
        div.style.pointerEvents = 'none'
        div.style.font = '11px system-ui, sans-serif'
        div.style.color = `rgb(${LABEL_COLOR[0]},${LABEL_COLOR[1]},${LABEL_COLOR[2]})`
        div.style.textShadow = '0 1px 2px rgba(0,0,0,0.8)'
        div.style.whiteSpace = 'nowrap'
        context.addHtmlDecoration?.(div)
    }
}
