/**
 * ClinicalProgramDecorator — VIEW-ONLY MRT Pharma clinical-program overlay.
 *
 * Renders the pure clinical-program overlay MODEL (deriveClinicalProgramOverlay)
 * on top of the SAME authoritative BIM room footprints used by RoomPlanDecorator.
 * The decorator holds NO assignment / storey / priority policy — that all lives
 * in the pure clinicalProgramOverlay seam. Here we only draw the derived records.
 *
 * VISIBILITY CORRECTION: assigned-room accents are drawn with GraphicType.
 * WorldOverlay (rendered ON TOP of scene geometry, no depth occlusion) plus a
 * small VIEW-ONLY Z lift, so the accent + footprint outline are readable in
 * Bird's-eye/Cutaway even though the BIM has floors / ceilings / walls. The label
 * is an HTML decoration anchored to the room footprint centroid. Neither the Z
 * lift nor anything else mutates BIM geometry, room elevation, or Bentley identity.
 *
 * It is a Bentley DECORATION only: it creates NO iModel elements, writes NO
 * changeset, and mutates NO Bentley identity.
 */
import { GraphicType, type DecorateContext, type Decorator } from '@itwin/core-frontend'
import { Point3d } from '@itwin/core-geometry'
import { ColorDef, LinePixels } from '@itwin/core-common'
import type { SpatialRoomReference } from '../../domain/assets'
import type { StoreyZRange } from './planningPlan'
import {
    deriveClinicalProgramOverlay,
    type ClinicalProgramOverlayRoom,
} from './clinicalProgramOverlay'
import { buildOrientedPlanningPrism, type PrismParams, type ClinicalVolumeLifecycle } from './clinicalPlanningVolume'
import type { ViewerMode } from './planningVisuals'
import type { ClinicalProgramAssignment, ClinicalFunction } from './clinicalProgram'

// Restrained clinical-planning category tints (UI ONLY — not regulatory).
export type ProgramCategory = 'RADIOPHARMACEUTICAL_PRODUCTION' | 'PATIENT_PREPARATION' | 'IMAGING' | 'SUPPORT' | 'CIRCULATION'

const FUNCTION_CATEGORY: Partial<Record<ClinicalFunction, ProgramCategory>> = {
    RADIOPHARMACY: 'RADIOPHARMACEUTICAL_PRODUCTION',
    CYCLOTRON: 'RADIOPHARMACEUTICAL_PRODUCTION',
    HOT_CELL_SYNTHESIS: 'RADIOPHARMACEUTICAL_PRODUCTION',
    QUALITY_CONTROL: 'RADIOPHARMACEUTICAL_PRODUCTION',
    DOSE_DISPENSING: 'RADIOPHARMACEUTICAL_PRODUCTION',
    INJECTION_ROOM: 'PATIENT_PREPARATION',
    UPTAKE_ROOM: 'PATIENT_PREPARATION',
    PATIENT_PREPARATION: 'PATIENT_PREPARATION',
    RECOVERY: 'PATIENT_PREPARATION',
    PET_CT_SCANNER_ROOM: 'IMAGING',
    SPECT_CT_SCANNER_ROOM: 'IMAGING',
    CONTROL_ROOM: 'IMAGING',
    PATIENT_WAITING: 'CIRCULATION',
    CLINICAL_CORRIDOR: 'CIRCULATION',
    CLEAN_SUPPLY: 'SUPPORT',
    WASTE_DECAY_STORAGE: 'SUPPORT',
    STAFF_SUPPORT: 'SUPPORT',
    MECHANICAL_ELECTRICAL: 'SUPPORT',
    GENERAL_SUPPORT: 'SUPPORT',
}

const CATEGORY_TINT: Record<ProgramCategory, [number, number, number]> = {
    RADIOPHARMACEUTICAL_PRODUCTION: [86, 140, 120], // muted teal-green
    PATIENT_PREPARATION: [110, 130, 180], // muted indigo
    IMAGING: [150, 120, 170], // muted violet
    SUPPORT: [140, 130, 110], // muted khaki
    CIRCULATION: [110, 130, 140], // muted slate
}

export function categoryForFunction(fn: ClinicalFunction): ProgramCategory | undefined {
    return FUNCTION_CATEGORY[fn]
}

const ASSIGNED_OUTLINE: [number, number, number] = [120, 210, 185]
const SELECTED_OUTLINE: [number, number, number] = [240, 200, 110] // warm select ring
const ASSIGNED_LABEL_COLOR = '#e6faf1'
const MAX_LABELS = 24

// VIEW-ONLY vertical lift (meters) applied to the on-top overlay so the accent
// reads clearly above the floor slab it sits on. Does NOT change BIM geometry or
// room elevation — it is a rendering offset only.
const VIEW_ONLY_Z_LIFT = 0.15

export interface ClinicalProgramInputs {
    /** Enabled only in NORMAL_PLANNING + program mode on. */
    getEnabled: () => boolean
    getMode: () => ViewerMode
    getRooms: () => readonly SpatialRoomReference[]
    getAssignments: () => readonly ClinicalProgramAssignment[]
    /** Active storey/floor id for storey filtering (undefined => all building). */
    getActiveStoreyId: () => string | undefined
    /** The BIM space id currently selected for program editing. */
    getSelectedSpaceId: () => string | undefined
    /** Canonical storey Z-ranges for the explicit room→storey mapping. */
    getStoreyRanges: () => readonly StoreyZRange[]
    /**
     * The true authoritative room footprint (world coords) for a space, when the
     * exact IfcSpace geometry has been extracted. When present it REPLACES the
     * range rectangle for both the accent and the label anchor.
     */
    getAuthoritativeFootprint?: (bimSpaceId: string) => {
        outerLoop: { x: number; y: number }[]
        holes: { x: number; y: number }[][]
        floorZ: number
        interiorAnchor: { x: number; y: number; z: number }
    } | undefined
    /** View-only: whether to render the authoritative room-volume shell. */
    getShowRoomVolume?: () => boolean
    /** The retained authoritative world mesh for a space (view-only volume). */
    getRoomVolumeMesh?: (bimSpaceId: string) => { vertices: readonly { x: number; y: number; z: number }[]; triangles: readonly number[] } | undefined
    /** Whether to render the MRT clinical PLANNING volume (true 3D world prism). */
    getShowClinicalVolume?: () => boolean
    /** The planning volume for a parent space, if defined + visible. */
    getPlanningVolumeForSpace?: (bimSpaceId: string) => { params: PrismParams; lifecycleState: ClinicalVolumeLifecycle; displayName: string; selected: boolean } | undefined
}

/** Bounded instrumentation snapshot from the most recent decorate() call. */
export interface ClinicalDecoratorDiagnostics {
    decorateCount: number
    lastDecorateAt?: number
    assignmentCountSeen: number
    roomCountSeen: number
    storeyRangeCountSeen: number
    activeStoreySeen?: string
    overlayCountSeen: number
    lastEnabled: boolean
    lastMode: ViewerMode
    /** Per-target draw facts (keyed by bimSpaceId) from the last decorate. */
    footprintDrawnFor: Set<string>
    labelDrawnFor: Set<string>
    footprintGraphicCreatedFor: Set<string>
    htmlLabelAttachedFor: Set<string>
    graphicType: string
    zLift: number
}

export class ClinicalProgramDecorator implements Decorator {
    // Not cacheable: selection/assignments/storey change frequently.
    public readonly useCachedDecorations = undefined
    private readonly inputs: ClinicalProgramInputs

    /** Live diagnostics (view-only; no secrets). Reset each decorate call. */
    public readonly diag: ClinicalDecoratorDiagnostics = {
        decorateCount: 0,
        assignmentCountSeen: 0,
        roomCountSeen: 0,
        storeyRangeCountSeen: 0,
        overlayCountSeen: 0,
        lastEnabled: false,
        lastMode: 'NORMAL_PLANNING',
        footprintDrawnFor: new Set<string>(),
        labelDrawnFor: new Set<string>(),
        footprintGraphicCreatedFor: new Set<string>(),
        htmlLabelAttachedFor: new Set<string>(),
        graphicType: 'WorldOverlay',
        zLift: VIEW_ONLY_Z_LIFT,
    }

    constructor(inputs: ClinicalProgramInputs) { this.inputs = inputs }

    /** The pure overlay model for the current inputs. The view-only Z lift is
     *  baked into displayAnchor here so the decorator applies it exactly once. */
    private buildOverlay(): ClinicalProgramOverlayRoom[] {
        return deriveClinicalProgramOverlay({
            rooms: this.inputs.getRooms(),
            assignments: this.inputs.getAssignments(),
            activeStoreyId: this.inputs.getActiveStoreyId(),
            selectedRoomId: this.inputs.getSelectedSpaceId(),
            storeys: this.inputs.getStoreyRanges(),
            maxLabels: MAX_LABELS,
            displayZOffset: VIEW_ONLY_Z_LIFT,
        })
    }

    /** Prefer the authoritative footprint (true room geometry) over the range. */
    private authoritativeRing(room: ClinicalProgramOverlayRoom): { ring: { x: number; y: number; z: number }[]; anchor: { x: number; y: number; z: number } } | undefined {
        const auth = this.inputs.getAuthoritativeFootprint?.(room.bimSpaceId)
        if (!auth || auth.outerLoop.length < 3) return undefined
        return {
            ring: auth.outerLoop.map((p) => ({ x: p.x, y: p.y, z: auth.floorZ })),
            anchor: auth.interiorAnchor,
        }
    }

    decorate(context: DecorateContext): void {
        // Record bounded diagnostics every call (view-only, no secrets).
        const d = this.diag
        d.decorateCount += 1
        d.lastDecorateAt = Date.now()
        d.lastEnabled = this.inputs.getEnabled()
        d.lastMode = this.inputs.getMode()
        d.assignmentCountSeen = this.inputs.getAssignments().length
        d.roomCountSeen = this.inputs.getRooms().length
        d.storeyRangeCountSeen = this.inputs.getStoreyRanges().length
        d.activeStoreySeen = this.inputs.getActiveStoreyId()
        d.footprintDrawnFor.clear()
        d.labelDrawnFor.clear()
        d.footprintGraphicCreatedFor.clear()
        d.htmlLabelAttachedFor.clear()

        if (!d.lastEnabled) { d.overlayCountSeen = 0; return }
        if (d.lastMode !== 'NORMAL_PLANNING') { d.overlayCountSeen = 0; return }
        const overlay = this.buildOverlay()
        d.overlayCountSeen = overlay.length
        if (overlay.length === 0) return
        // Draw lower-priority first so selected/assigned draw last (on top).
        const ordered = [...overlay].sort((a, b) => a.priority - b.priority)
        const showVolume = this.inputs.getShowRoomVolume?.() ?? false
        const showPlanning = this.inputs.getShowClinicalVolume?.() ?? false
        for (const room of ordered) {
            if (showVolume) this.drawRoomVolume(context, room)
            const planning = showPlanning ? this.inputs.getPlanningVolumeForSpace?.(room.bimSpaceId) : undefined
            if (planning) {
                // The PLANNING volume is the physical authority for the assigned
                // room: draw the true 3D prism and anchor the label to it. The old
                // range accent/footprint is suppressed for this room (no duplicate).
                this.drawPlanningPrism(context, planning.params, planning.lifecycleState, planning.selected)
                this.drawPlanningLabel(context, planning, room.label)
            } else {
                this.drawRoomAccent(context, room)
                this.drawLabel(context, room)
            }
        }
    }

    /**
     * Render the MRT clinical PLANNING volume as TRUE 3D WORLD GEOMETRY: an
     * oriented prism with translucent faces + solid edges, built in BIM/world
     * coordinates. It is NOT a billboard — it rotates/foreshortens with the scene
     * exactly like other world geometry. DRAFT vs LOCKED are visually distinct.
     */
    private drawPlanningPrism(context: DecorateContext, params: PrismParams, state: ClinicalVolumeLifecycle, selected: boolean): void {
        const g = buildOrientedPlanningPrism(params)
        const V = g.vertices.map((p) => Point3d.create(p.x, p.y, p.z))
        // DRAFT = warm amber; LOCKED = teal; SELECTED = brighter blue-tinted edge.
        const rgb: [number, number, number] = selected ? [130, 180, 255] : state === 'LOCKED' ? [110, 200, 175] : [235, 190, 110]
        const edge = ColorDef.from(...rgb)
        const fill = ColorDef.from(...rgb).withTransparency(selected ? 175 : state === 'LOCKED' ? 205 : 190)

        // Faces (true world geometry, depth-tested WorldDecoration so it reads as
        // a solid in the scene). Bottom, top, and 4 sides.
        const faces: [number, number, number, number][] = [
            [0, 1, 2, 3], // bottom
            [4, 5, 6, 7], // top
            [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7], // sides
        ]
        const faceBuilder = context.createGraphicBuilder(GraphicType.WorldDecoration)
        faceBuilder.setSymbology(edge, fill, 1)
        for (const [a, b, c, d] of faces) faceBuilder.addShape([V[a], V[b], V[c], V[d], V[a]])
        context.addDecorationFromBuilder(faceBuilder)

        // Crisp world edges (selected = thicker for a non-color cue too).
        const edgeBuilder = context.createGraphicBuilder(GraphicType.WorldDecoration)
        edgeBuilder.setSymbology(edge, edge, selected ? 4 : state === 'LOCKED' ? 3 : 2, LinePixels.Solid)
        const edges: [number, number][] = [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]]
        for (const [a, b] of edges) edgeBuilder.addLineString([V[a], V[b]])
        context.addDecorationFromBuilder(edgeBuilder)

        this.diag.footprintDrawnFor.add('planning')
    }

    /** VIEW_ANNOTATION label for the planning volume — billboards; world-anchored. */
    private drawPlanningLabel(context: DecorateContext, planning: { params: PrismParams; lifecycleState: ClinicalVolumeLifecycle }, label: string): void {
        const g = buildOrientedPlanningPrism(planning.params)
        const world = Point3d.create(g.interiorAnchor.x, g.interiorAnchor.y, planning.params.zHigh + 0.1)
        const view = context.viewport.worldToView(world)
        if (!Number.isFinite(view.x) || !Number.isFinite(view.y)) return
        const div = document.createElement('div')
        div.className = 'mrt-program-label mrt-program-label--assigned'
        div.textContent = `${label}${planning.lifecycleState === 'DRAFT' ? ' (draft)' : ''}`
        div.style.position = 'absolute'
        div.style.left = `${Math.round(view.x)}px`
        div.style.top = `${Math.round(view.y)}px`
        div.style.transform = 'translate(-50%, -50%)'
        div.style.pointerEvents = 'none'
        div.style.whiteSpace = 'nowrap'
        div.style.font = '700 13px system-ui, sans-serif'
        div.style.color = planning.lifecycleState === 'LOCKED' ? '#e6faf1' : '#fbf0d8'
        div.style.padding = '2px 8px'
        div.style.borderRadius = '5px'
        div.style.background = planning.lifecycleState === 'LOCKED' ? 'rgba(16,42,36,0.8)' : 'rgba(60,44,12,0.8)'
        div.style.border = `1px solid ${planning.lifecycleState === 'LOCKED' ? 'rgba(110,200,175,0.9)' : 'rgba(235,190,110,0.9)'}`
        div.style.textShadow = '0 1px 3px rgba(0,0,0,0.95)'
        context.addHtmlDecoration?.(div)
        this.diag.labelDrawnFor.add('planning')
    }

    /** Restrained translucent shell of the authoritative IfcSpace volume (view-only). */
    private drawRoomVolume(context: DecorateContext, room: ClinicalProgramOverlayRoom): void {
        const mesh = this.inputs.getRoomVolumeMesh?.(room.bimSpaceId)
        if (!mesh || mesh.triangles.length < 3) return
        const builder = context.createGraphicBuilder(GraphicType.WorldDecoration)
        const shell = ColorDef.from(...ASSIGNED_OUTLINE).withTransparency(225) // very light
        builder.setSymbology(ColorDef.from(...ASSIGNED_OUTLINE), shell, 1)
        const V = mesh.vertices
        const T = mesh.triangles
        for (let t = 0; t + 2 < T.length; t += 3) {
            const a = V[T[t]], b = V[T[t + 1]], c = V[T[t + 2]]
            if (!a || !b || !c) continue
            builder.addShape([Point3d.create(a.x, a.y, a.z), Point3d.create(b.x, b.y, b.z), Point3d.create(c.x, c.y, c.z), Point3d.create(a.x, a.y, a.z)])
        }
        context.addDecorationFromBuilder(builder)
    }

    /**
     * On-top footprint accent: translucent category fill + a crisp outline drawn
     * with WorldOverlay (no depth occlusion). Vertices come from the overlay's
     * world-coordinate boundary (facility geometry) + the view-only Z lift — the
     * facility coordinates themselves are never mutated by the lift.
     */
    private drawRoomAccent(context: DecorateContext, room: ClinicalProgramOverlayRoom): void {
        // Prefer the true authoritative footprint; else the world-coordinate
        // boundary; else the range footprint ring.
        const auth = this.authoritativeRing(room)
        const ring = auth?.ring ?? room.boundary ?? room.footprint.ring.map((p) => ({ x: p.x, y: p.y, z: room.footprint.elevation }))
        if (ring.length < 3) return
        // The view-only lift is applied once (same as displayAnchor.z - facilityAnchor.z).
        const loop = ring.map((p) => Point3d.create(p.x, p.y, p.z + VIEW_ONLY_Z_LIFT))
        const closed = [...loop, loop[0]]

        // Translucent identification fill (on top of geometry).
        const cat = room.clinicalFunction ? FUNCTION_CATEGORY[room.clinicalFunction] : undefined
        const tint = cat ? CATEGORY_TINT[cat] : ASSIGNED_OUTLINE
        const outlineColor = ColorDef.from(...(room.selected ? SELECTED_OUTLINE : ASSIGNED_OUTLINE))
        const fillBuilder = context.createGraphicBuilder(GraphicType.WorldOverlay)
        fillBuilder.setSymbology(outlineColor, ColorDef.from(...tint).withTransparency(170), 2)
        fillBuilder.addShape(closed)
        context.addDecorationFromBuilder(fillBuilder)

        // Crisp perimeter on top (thicker for the selected room).
        const ringBuilder = context.createGraphicBuilder(GraphicType.WorldOverlay)
        ringBuilder.setSymbology(outlineColor, outlineColor, room.selected ? 5 : 3, LinePixels.Solid)
        ringBuilder.addLineString(closed)
        context.addDecorationFromBuilder(ringBuilder)
        this.diag.footprintDrawnFor.add(room.bimSpaceId)
        this.diag.footprintGraphicCreatedFor.add(room.bimSpaceId)
    }

    private drawLabel(context: DecorateContext, room: ClinicalProgramOverlayRoom): void {
        if (!room.label) return
        this.diag.labelDrawnFor.add(room.bimSpaceId)
        // Prefer the true room-local interior anchor when authoritative geometry
        // is available; else the display anchor (facility + view-only lift).
        const auth = this.authoritativeRing(room)
        const anchor = auth ? { x: auth.anchor.x, y: auth.anchor.y, z: auth.anchor.z + VIEW_ONLY_Z_LIFT } : room.displayAnchor
        const world = Point3d.create(anchor.x, anchor.y, anchor.z)
        const view = context.viewport.worldToView(world)
        if (!Number.isFinite(view.x) || !Number.isFinite(view.y)) return
        const div = document.createElement('div')
        div.className = room.assigned ? 'mrt-program-label mrt-program-label--assigned' : 'mrt-program-label'
        div.textContent = room.label
        div.style.position = 'absolute'
        div.style.left = `${Math.round(view.x)}px`
        div.style.top = `${Math.round(view.y)}px`
        div.style.transform = 'translate(-50%, -50%)'
        div.style.pointerEvents = 'none'
        div.style.whiteSpace = 'nowrap'
        div.style.textShadow = '0 1px 3px rgba(0,0,0,0.95)'
        if (room.assigned) {
            // Readable at normal Bird's-eye programming scale; billboarded (screen
            // space) so it stays upright as the camera rotates.
            div.style.font = '700 13px system-ui, sans-serif'
            div.style.color = ASSIGNED_LABEL_COLOR
            div.style.padding = '2px 8px'
            div.style.borderRadius = '5px'
            div.style.background = room.selected ? 'rgba(70,54,16,0.82)' : 'rgba(16,42,36,0.78)'
            div.style.border = room.selected ? '1px solid rgba(240,200,110,0.9)' : '1px solid rgba(120,210,185,0.7)'
            div.style.boxShadow = '0 2px 6px rgba(0,0,0,0.45)'
        } else {
            div.style.font = '11px system-ui, sans-serif'
            div.style.color = '#b7c4d2'
        }
        context.addHtmlDecoration?.(div)
        this.diag.htmlLabelAttachedFor.add(room.bimSpaceId)
    }
}
