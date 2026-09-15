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
import { Box, Cone, Point3d, Range3d } from '@itwin/core-geometry'
import { ColorDef, LinePixels } from '@itwin/core-common'
import type { SpatialRoomReference } from '../../domain/assets'
import type { AssetFamily } from '../../domain/assets/types'
import type { StoreyZRange } from './planningPlan'
import {
    deriveClinicalProgramOverlay,
    type ClinicalProgramOverlayRoom,
} from './clinicalProgramOverlay'
import { buildOrientedPlanningPrism, type PrismParams, type ClinicalVolumeLifecycle } from './clinicalPlanningVolume'
import type { ViewerMode } from './planningVisuals'
import type { CameraMode } from './cameraNav'
import { resolveWalkthroughLabelVisibility } from './walkthroughLabelVisibility'
import type { ClinicalProgramAssignment, ClinicalFunction } from './clinicalProgram'
import type { CanonicalEquipmentClass } from './canonicalEquipmentCatalog'
import {
    applyYaw,
    buildEquipmentParts,
    resolveVisualFamilyForCanonical,
    EQUIPMENT_PART_COLOR,
    EQUIPMENT_SELECTION_OUTLINE,
    type EquipmentPart,
    type EquipmentPartGeometry,
    type EquipmentVisualFamily,
    type WorldBox,
} from './equipmentGeometry'

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
    getPlanningVolumeForSpace?: (bimSpaceId: string) => { params: PrismParams; lifecycleState: ClinicalVolumeLifecycle; displayName: string; selected: boolean; invalid?: boolean } | undefined
    /** Whether to render app-owned equipment envelopes (Build 1B). */
    getShowEquipment?: () => boolean
    /**
     * Build 1B — the app-owned equipment envelopes to render as true 3D world
     * boxes. Each carries its oriented-prism params (already floor-based),
     * lifecycle, selection, an invalid (containment FAIL) flag, and a honest
     * placeholder flag so the label can disclose a proxy envelope.
     */
    getEquipmentForRender?: () => readonly {
        id: string
        params: PrismParams
        lifecycleState: ClinicalVolumeLifecycle
        label: string
        selected: boolean
        invalid?: boolean
        placeholder?: boolean
        /** Canonical class → resolves the generic VISUAL family (never identity). */
        canonicalClass?: CanonicalEquipmentClass
        /** Spatial family (helps disambiguate; GENERATOR has none). */
        assetFamily?: AssetFamily
    }[]
    /**
     * EVI-MA-05A — the app-owned CLINICAL LOGISTICS VESTIBULE instances to render
     * as recognizable wall-integrated 3D geometry. Each carries its oriented-prism
     * params (front-face pose), the visual family, which rear ports are
     * fabricated, lifecycle, selection, and label. Rendered by the SAME
     * per-part-material + outline-only-selection path as equipment.
     */
    getVestibulesForRender?: () => readonly {
        id: string
        params: PrismParams
        family: EquipmentVisualFamily
        ports: { mrt?: boolean; mrtHeavy?: boolean; pts?: boolean }
        lifecycleState: ClinicalVolumeLifecycle
        label: string
        selected: boolean
    }[]
    /**
     * Whether to render the translucent engineering CONTAINMENT ENVELOPE around
     * recognizable equipment geometry. Defaults to true (envelope always drawn)
     * for backward compatibility. When recognizable geometry is present the
     * envelope stays authoritative for spatial validation but may be toggled.
     */
    getShowEquipmentEnvelope?: () => boolean
    /**
     * Build 1A label-occlusion: the active product CAMERA mode (PLANNING /
     * WALKTHROUGH / BIRDS_EYE_CUTAWAY). In WALKTHROUGH the planning-volume label
     * becomes visibility-aware (occlusion + behind-camera + off-screen +
     * proximity); PLANNING / BIRDS_EYE keep persistent labels. Defaults to
     * PLANNING when not supplied (backward compatible).
     */
    getCameraMode?: () => CameraMode
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

    /**
     * EVI-MA-02 — pickable transient id <-> equipmentInstanceId maps, rebuilt
     * each decorate(). The stable identity is the equipmentInstanceId; the
     * transient pick id is NEVER treated as identity. This makes the recognizable
     * equipment geometry + envelope directly selectable in the live 3D viewport
     * (mirrors the SpatialAssetDecorator pattern). One pick id per equipment
     * instance covers all of that instance's primitives (body + shielding +
     * cabinet + envelope), so any part of ONE cyclotron resolves to its id.
     */
    private readonly equipmentPickIdToInstance = new Map<string, string>()
    private readonly instanceToEquipmentPickId = new Map<string, string>()

    /**
     * EVI-MA-05A — the SAME pick-id doctrine for clinical logistics vestibules:
     * ONE transient pick id per vestibuleInstanceId covers ALL of that
     * vestibule's primitives (front fascia + door + HMI + rear manifold + MRT
     * reducer/stub + PTS adapter/tube), so any part resolves to the one
     * vestibuleInstanceId. Kept in a SEPARATE map so a vestibule pick never
     * resolves to an equipment id and vice versa.
     */
    private readonly vestibulePickIdToInstance = new Map<string, string>()
    private readonly instanceToVestibulePickId = new Map<string, string>()

    /** Bentley picking hook: does this pickable id belong to app-owned equipment/vestibule? */
    testDecorationHit(id: string): boolean {
        return this.equipmentPickIdToInstance.has(id) || this.vestibulePickIdToInstance.has(id)
    }

    /** Resolve a picked transient id to its stable equipmentInstanceId. */
    equipmentIdForPickId(pickId: string): string | undefined {
        return this.equipmentPickIdToInstance.get(pickId)
    }

    /** Resolve a picked transient id to its stable vestibuleInstanceId. */
    vestibuleIdForPickId(pickId: string): string | undefined {
        return this.vestibulePickIdToInstance.get(pickId)
    }

    /** Allocate/reuse a pickable transient id for an equipment instance this frame. */
    private equipmentPickIdFor(equipmentInstanceId: string, iModel: { transientIds: { getNext(): string } } | undefined): string | undefined {
        if (!iModel) return undefined
        const existing = this.instanceToEquipmentPickId.get(equipmentInstanceId)
        if (existing) return existing
        const id = iModel.transientIds.getNext()
        this.instanceToEquipmentPickId.set(equipmentInstanceId, id)
        this.equipmentPickIdToInstance.set(id, equipmentInstanceId)
        return id
    }

    /** Drop pick-map entries for equipment instances that no longer render. */
    private dropStaleEquipmentPickIds(liveIds: Set<string>): void {
        for (const [instId, pickId] of Array.from(this.instanceToEquipmentPickId)) {
            if (!liveIds.has(instId)) {
                this.instanceToEquipmentPickId.delete(instId)
                this.equipmentPickIdToInstance.delete(pickId)
            }
        }
    }

    /** Allocate/reuse a pickable transient id for a vestibule instance this frame. */
    private vestibulePickIdFor(vestibuleInstanceId: string, iModel: { transientIds: { getNext(): string } } | undefined): string | undefined {
        if (!iModel) return undefined
        const existing = this.instanceToVestibulePickId.get(vestibuleInstanceId)
        if (existing) return existing
        const id = iModel.transientIds.getNext()
        this.instanceToVestibulePickId.set(vestibuleInstanceId, id)
        this.vestibulePickIdToInstance.set(id, vestibuleInstanceId)
        return id
    }

    /** Drop pick-map entries for vestibule instances that no longer render. */
    private dropStaleVestibulePickIds(liveIds: Set<string>): void {
        for (const [instId, pickId] of Array.from(this.instanceToVestibulePickId)) {
            if (!liveIds.has(instId)) {
                this.instanceToVestibulePickId.delete(instId)
                this.vestibulePickIdToInstance.delete(pickId)
            }
        }
    }

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

        // EVI-MA-01 ROOT-CAUSE FIX: app-owned equipment is a FIRST-CLASS world
        // object. Its visibility must NOT be coupled to the clinical-program
        // overlay derivation (program-enabled state / active-storey overlay set /
        // whether the parent room produced an overlay row). Previously the
        // equipment block lived AFTER `if (!enabled) return`, `if (mode !=
        // NORMAL_PLANNING) return` and `if (overlay.length === 0) return`, so a
        // validly-placed cyclotron silently never reached Bentley whenever the
        // clinical overlay was empty for the active storey. Draw equipment FIRST,
        // gated only on its own visibility flag + the planning viewer mode
        // (world geometry, so it also shows through Walkthrough). The label
        // overlay still respects the camera mode inside drawEquipmentLabel.
        if (d.lastMode === 'NORMAL_PLANNING') {
            this.drawEquipment(context)
            // EVI-MA-05A — vestibules render alongside equipment (same class of
            // app-owned wall-integrated spatial object).
            this.drawVestibules(context)
        }

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
                this.drawPlanningPrism(context, planning.params, planning.lifecycleState, planning.selected, planning.invalid ?? false)
                this.drawPlanningLabel(context, planning, room.label, planning.invalid ?? false)
            } else {
                this.drawRoomAccent(context, room)
                this.drawLabel(context, room)
            }
        }

    }

    /**
     * EVI-MA-01 — draw app-owned equipment as first-class world objects,
     * INDEPENDENT of clinical-overlay derivation. For each instance: the
     * recognizable generic geometry (cyclotron / PET-CT / hot-cell) at the SAME
     * authoritative pose as the envelope, then the (toggleable, translucent)
     * containment envelope, then the world-anchored label. Both the recognizable
     * visual and the envelope derive from the ONE EquipmentAssetInstance pose.
     */
    private drawEquipment(context: DecorateContext): void {
        const showEquipment = this.inputs.getShowEquipment?.() ?? false
        const equipment = this.inputs.getEquipmentForRender?.() ?? []
        // Rebuild the equipment pick maps for the current visible set (drop stale
        // entries) BEFORE any early return so a hidden/removed instance never
        // leaves a dangling pick id resolving to a gone instance.
        this.dropStaleEquipmentPickIds(new Set(equipment.map((e) => e.id)))
        if (!showEquipment) return
        const iModel = context.viewport.iModel as unknown as { transientIds: { getNext(): string } }
        // The engineering envelope stays available; default ON so nothing
        // regresses. When a recognizable visual family resolves, the envelope
        // is drawn as a translucent clearance boundary AROUND the equipment.
        const showEnvelope = this.inputs.getShowEquipmentEnvelope?.() ?? true
        for (const e of equipment) {
            // ONE stable pickable id per equipment instance (covers all its
            // primitives + envelope), so any part of ONE cyclotron resolves to
            // its exact equipmentInstanceId — even when two cyclotrons overlap.
            const pickId = this.equipmentPickIdFor(e.id, iModel)
            const family = e.canonicalClass
                ? resolveVisualFamilyForCanonical({ canonicalClass: e.canonicalClass, assetFamily: e.assetFamily })
                : undefined
            // Recognizable equipment geometry (cyclotron / PET-CT / hot-cell)
            // at the SAME authoritative pose as the AssetInstance envelope.
            if (family) {
                this.drawEquipmentVisual(context, family, e.params, e.selected, e.invalid ?? false, pickId)
            }
            // Keep the containment envelope: authoritative for validation,
            // translucent so recognizable geometry reads through it. When a
            // recognizable family is present the envelope is drawn only if
            // enabled (toggleable); with no family it is always drawn (legacy
            // proxy-box behavior — never removed, so an unmapped family still
            // shows SOMETHING honest rather than nothing).
            if (!family || showEnvelope) {
                this.drawEquipmentEnvelope(context, e.params, e.lifecycleState, e.selected, e.invalid ?? false, family !== undefined, pickId)
            }
            this.drawEquipmentLabel(context, e.params, e.label, e.lifecycleState, e.invalid ?? false, (e.placeholder ?? false) && !family)
        }
    }

    /**
     * EVI-MA-05A — draw app-owned CLINICAL LOGISTICS VESTIBULES as first-class
     * wall-integrated world objects, mirroring drawEquipment. Each vestibule
     * renders the CLINICAL_LOGISTICS_VESTIBULE_V1 recipe (front access face +
     * wall sleeve + rear manifold + the CONFIGURED MRT/PTS port stubs) via the
     * SAME drawEquipmentVisual path (per-part materials, outline-only selection),
     * plus a translucent reserved-volume envelope and a world label. ONE pick id
     * per vestibule covers every primitive. Gated by getShowEquipment so the
     * equipment visibility toggle governs both (they are the same class of
     * app-owned spatial object).
     */
    private drawVestibules(context: DecorateContext): void {
        const showEquipment = this.inputs.getShowEquipment?.() ?? false
        const vestibules = this.inputs.getVestibulesForRender?.() ?? []
        // Rebuild the vestibule pick maps for the current visible set BEFORE any
        // early return so a hidden/removed vestibule leaves no dangling pick id.
        this.dropStaleVestibulePickIds(new Set(vestibules.map((v) => v.id)))
        if (!showEquipment) return
        const iModel = context.viewport.iModel as unknown as { transientIds: { getNext(): string } }
        const showEnvelope = this.inputs.getShowEquipmentEnvelope?.() ?? true
        for (const v of vestibules) {
            const pickId = this.vestibulePickIdFor(v.id, iModel)
            // Recognizable wall-integrated vestibule geometry at its front-face pose.
            this.drawEquipmentVisual(context, v.family, v.params, v.selected, false, pickId, v.ports)
            // Translucent reserved-volume envelope (the room-side clearance cue).
            if (showEnvelope) {
                this.drawEquipmentEnvelope(context, v.params, v.lifecycleState, v.selected, false, true, pickId)
            }
            this.drawEquipmentLabel(context, v.params, v.label, v.lifecycleState, false, false)
        }
    }

    /**
     * Build 1B — render an app-owned equipment envelope as TRUE 3D WORLD
     * GEOMETRY: an oriented box with translucent faces + solid edges in
     * BIM/world coordinates. INVALID (containment FAIL) = red + DASHED thick
     * edges (a non-color cue too); DRAFT = cool blue; LOCKED = green; SELECTED =
     * brighter. It is a proxy box (labeled honestly when placeholder), never a
     * fabricated detailed model.
     */
    private drawEquipmentEnvelope(context: DecorateContext, params: PrismParams, state: ClinicalVolumeLifecycle, selected: boolean, invalid: boolean, hasVisual = false, pickId?: string): void {
        const g = buildOrientedPlanningPrism(params)
        const V = g.vertices.map((p) => Point3d.create(p.x, p.y, p.z))
        const rgb: [number, number, number] = invalid ? [230, 90, 80] : selected ? [140, 190, 255] : state === 'LOCKED' ? [120, 205, 140] : [120, 160, 210]
        const edge = ColorDef.from(...rgb)
        // When recognizable geometry is present the envelope reads as a faint
        // clearance boundary (much more translucent) so it never masks the solid.
        const baseFill = invalid ? 160 : selected ? 165 : state === 'LOCKED' ? 195 : 185
        const fill = ColorDef.from(...rgb).withTransparency(hasVisual ? Math.min(baseFill + 45, 235) : baseFill)
        const faces: [number, number, number, number][] = [
            [0, 1, 2, 3], [4, 5, 6, 7],
            [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7],
        ]
        // Pickable face builder (3-arg form) so clicking the envelope also
        // resolves to the equipment instance — important when no recognizable
        // family renders (proxy-box case), so the box stays directly selectable.
        const faceBuilder = pickId
            ? context.createGraphicBuilder(GraphicType.WorldDecoration, undefined, pickId)
            : context.createGraphicBuilder(GraphicType.WorldDecoration)
        faceBuilder.setSymbology(edge, fill, 1)
        for (const [a, b, c, d] of faces) faceBuilder.addShape([V[a], V[b], V[c], V[d], V[a]])
        context.addDecorationFromBuilder(faceBuilder)

        const edgeBuilder = pickId
            ? context.createGraphicBuilder(GraphicType.WorldDecoration, undefined, pickId)
            : context.createGraphicBuilder(GraphicType.WorldDecoration)
        edgeBuilder.setSymbology(edge, edge, invalid ? 4 : selected ? 4 : state === 'LOCKED' ? 3 : 2, invalid ? LinePixels.Code2 : LinePixels.Solid)
        const edges: [number, number][] = [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]]
        for (const [a, b] of edges) edgeBuilder.addLineString([V[a], V[b]])
        context.addDecorationFromBuilder(edgeBuilder)
    }

    /**
     * Visual-integration — render the RECOGNIZABLE generic equipment geometry
     * (cyclotron / PET-CT / hot-cell) as true world solids at the SAME
     * authoritative pose as the AssetInstance envelope. The parts come from the
     * renderer-independent equipmentGeometry recipe; this method only emits them
     * as GraphicBuilder solids. It never invents geometry and never changes the
     * canonical identity — the identity is surfaced by the label/selection card.
     */
    private drawEquipmentVisual(context: DecorateContext, family: EquipmentVisualFamily, params: PrismParams, selected: boolean, invalid: boolean, pickId?: string, vestibulePorts?: { mrt?: boolean; mrtHeavy?: boolean; pts?: boolean }): void {
        // The envelope params carry the authoritative pose: XY center, floor Z,
        // extents, yaw. Recover them so the recognizable geometry follows the
        // instance pose EXACTLY (translation + yaw), together with the envelope.
        const center: [number, number, number] = [params.centerX, params.centerY, params.zLow]
        const pose = {
            center,
            width: params.width,
            depth: params.depth,
            height: params.zHigh - params.zLow,
            yawRadians: params.yaw,
        }
        const parts: EquipmentPartGeometry[] = buildEquipmentParts(family, pose, vestibulePorts ? { vestibulePorts } : undefined)
        if (parts.length === 0) return
        for (const part of parts) {
            // Pickable graphic (3-arg form) carries the equipment's transient id
            // so a click resolves back to its exact equipmentInstanceId.
            const builder = pickId
                ? context.createGraphicBuilder(GraphicType.WorldDecoration, undefined, pickId)
                : context.createGraphicBuilder(GraphicType.WorldDecoration)
            const [r, g, b] = EQUIPMENT_PART_COLOR[part.part]
            // EVI-MA-04 — the machine ALWAYS keeps its per-part material fill.
            // Selection adds only a thin restrained outline (edge) + slightly
            // heavier weight; it NEVER repaints the solid cyan (the translucent
            // containment envelope is the selection region cue). INVALID
            // (containment FAIL) is the only case that tints the fill (red), as a
            // strong non-color-only cue paired with the envelope's dashed edges.
            const fill = invalid ? ColorDef.from(230, 90, 80) : ColorDef.from(r, g, b)
            const line = selected ? ColorDef.from(...EQUIPMENT_SELECTION_OUTLINE) : fill
            builder.setSymbology(line, fill, selected ? 2 : 1)
            if (part.kind === 'BOX') {
                const box = this.buildEquipmentBox(part)
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

    /** Yaw the 8 corners of a WorldBox about its center, then build a range box. */
    private buildEquipmentBox(part: WorldBox<EquipmentPart>): Box | undefined {
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

    /** Build 1B — world-anchored equipment label; billboards; honest proxy disclosure. */
    private drawEquipmentLabel(context: DecorateContext, params: PrismParams, label: string, state: ClinicalVolumeLifecycle, invalid: boolean, placeholder: boolean): void {
        const g = buildOrientedPlanningPrism(params)
        const world = Point3d.create(g.interiorAnchor.x, g.interiorAnchor.y, params.zHigh + 0.1)
        const view = context.viewport.worldToView(world)
        if (!Number.isFinite(view.x) || !Number.isFinite(view.y)) return
        const cameraMode: CameraMode = this.inputs.getCameraMode?.() ?? 'PLANNING'
        if (cameraMode === 'WALKTHROUGH') {
            const vp = context.viewport
            const npc = vp.worldToNpc(world)
            const behindCamera = !Number.isFinite(npc.z) || npc.z < 0 || npc.z > 1
            const rect = vp.viewRect
            const onScreen = view.x >= rect.left && view.x <= rect.right && view.y >= rect.top && view.y <= rect.bottom
            let distance = Infinity
            try {
                const eye = (vp.view as unknown as { getEyePoint?: () => Point3d }).getEyePoint?.()
                if (eye) distance = eye.distance(world)
            } catch { /* no camera eye */ }
            const decision = resolveWalkthroughLabelVisibility({ cameraMode, behindCamera, onScreen, occluded: false, distance })
            if (!decision.visible) return
        }
        const suffix = invalid ? ' — OUTSIDE ROOM' : placeholder ? ' (proxy envelope)' : state === 'DRAFT' ? ' (draft)' : ''
        const div = document.createElement('div')
        div.className = invalid ? 'mrt-equipment-label mrt-equipment-label--invalid' : 'mrt-equipment-label'
        div.textContent = invalid ? `⚠ ${label}${suffix}` : `${label}${suffix}`
        div.style.position = 'absolute'
        div.style.left = `${Math.round(view.x)}px`
        div.style.top = `${Math.round(view.y)}px`
        div.style.transform = 'translate(-50%, -50%)'
        div.style.pointerEvents = 'none'
        div.style.whiteSpace = 'nowrap'
        div.style.font = '700 12px system-ui, sans-serif'
        div.style.color = invalid ? '#ffe6e2' : state === 'LOCKED' ? '#e4fae8' : '#e4eeff'
        div.style.padding = '2px 8px'
        div.style.borderRadius = '5px'
        div.style.background = invalid ? 'rgba(70,18,14,0.86)' : state === 'LOCKED' ? 'rgba(16,42,22,0.8)' : 'rgba(18,32,54,0.82)'
        div.style.border = `${invalid ? '2px dashed rgba(235,90,80,0.95)' : `1px solid ${state === 'LOCKED' ? 'rgba(120,205,140,0.9)' : 'rgba(120,160,210,0.9)'}`}`
        div.style.textShadow = '0 1px 3px rgba(0,0,0,0.95)'
        context.addHtmlDecoration?.(div)
    }

    /**
     * Render the MRT clinical PLANNING volume as TRUE 3D WORLD GEOMETRY: an
     * oriented prism with translucent faces + solid edges, built in BIM/world
     * coordinates. It is NOT a billboard — it rotates/foreshortens with the scene
     * exactly like other world geometry. DRAFT vs LOCKED are visually distinct.
     */
    private drawPlanningPrism(context: DecorateContext, params: PrismParams, state: ClinicalVolumeLifecycle, selected: boolean, invalid: boolean): void {
        const g = buildOrientedPlanningPrism(params)
        const V = g.vertices.map((p) => Point3d.create(p.x, p.y, p.z))
        // INVALID (containment FAIL) = red; DRAFT = warm amber; LOCKED = teal;
        // SELECTED = brighter blue-tinted edge. (Color is only ONE cue — the
        // invalid state also uses a DASHED edge pattern + thicker outline + an
        // OUTSIDE badge on the label, so it never relies on color alone.)
        const rgb: [number, number, number] = invalid ? [230, 90, 80] : selected ? [130, 180, 255] : state === 'LOCKED' ? [110, 200, 175] : [235, 190, 110]
        const edge = ColorDef.from(...rgb)
        const fill = ColorDef.from(...rgb).withTransparency(invalid ? 170 : selected ? 175 : state === 'LOCKED' ? 205 : 190)

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

        // Crisp world edges (selected/invalid = thicker for a non-color cue too;
        // invalid uses a DASHED pattern as an additional shape/pattern cue).
        const edgeBuilder = context.createGraphicBuilder(GraphicType.WorldDecoration)
        edgeBuilder.setSymbology(edge, edge, invalid ? 4 : selected ? 4 : state === 'LOCKED' ? 3 : 2, invalid ? LinePixels.Code2 : LinePixels.Solid)
        const edges: [number, number][] = [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]]
        for (const [a, b] of edges) edgeBuilder.addLineString([V[a], V[b]])
        context.addDecorationFromBuilder(edgeBuilder)

        this.diag.footprintDrawnFor.add('planning')
    }

    /** VIEW_ANNOTATION label for the planning volume — billboards; world-anchored. */
    private drawPlanningLabel(context: DecorateContext, planning: { params: PrismParams; lifecycleState: ClinicalVolumeLifecycle }, label: string, invalid: boolean): void {
        const g = buildOrientedPlanningPrism(planning.params)
        // World-space anchor (upper-center of the prism). NEVER moved toward the
        // camera — the label is anchored to the actual planning volume.
        const world = Point3d.create(g.interiorAnchor.x, g.interiorAnchor.y, planning.params.zHigh + 0.1)
        const view = context.viewport.worldToView(world)
        if (!Number.isFinite(view.x) || !Number.isFinite(view.y)) return

        // Build 1A label-occlusion policy. In WALKTHROUGH the label is visibility-
        // aware; PLANNING / BIRDS_EYE remain persistent. Anchor stays world-space.
        const cameraMode: CameraMode = this.inputs.getCameraMode?.() ?? 'PLANNING'
        if (cameraMode === 'WALKTHROUGH') {
            const vp = context.viewport
            // Behind-camera / off-screen from the view projection (npc.z outside
            // [0,1] => outside the frustum depth; view x/y outside the view rect
            // => off-screen).
            const npc = vp.worldToNpc(world)
            const behindCamera = !Number.isFinite(npc.z) || npc.z < 0 || npc.z > 1
            const rect = vp.viewRect
            const onScreen = view.x >= rect.left && view.x <= rect.right && view.y >= rect.top && view.y <= rect.bottom
            // Distance from the walk eye to the anchor (proximity policy).
            let distance = Infinity
            try {
                const eye = (vp.view as unknown as { getEyePoint?: () => Point3d }).getEyePoint?.()
                if (eye) distance = eye.distance(world)
            } catch { /* no camera eye */ }
            // Occlusion via the accepted viewer visibility authority: pick the
            // NEAREST visible geometry at the label pixel; if solid BIM geometry
            // is closer to the eye than the anchor, the label is occluded.
            let occluded = false
            try {
                const eye = (vp.view as unknown as { getEyePoint?: () => Point3d }).getEyePoint?.()
                const hit = (vp as unknown as { pickNearestVisibleGeometry?: (p: Point3d) => Point3d | undefined }).pickNearestVisibleGeometry?.(world)
                if (eye && hit) {
                    const hitDist = eye.distance(hit)
                    const anchorDist = eye.distance(world)
                    // A hit meaningfully nearer than the anchor => something solid
                    // is between the eye and the label => occluded.
                    occluded = hitDist + 0.25 < anchorDist
                }
            } catch { /* pick unavailable: treat as not occluded (fail-open to visible-nearby) */ }
            const decision = resolveWalkthroughLabelVisibility({ cameraMode, behindCamera, onScreen, occluded, distance })
            if (!decision.visible) { this.diag.labelDrawnFor.add(`planning:hidden:${decision.reason}`); return }
        }
        const div = document.createElement('div')
        div.className = invalid ? 'mrt-program-label mrt-program-label--invalid' : 'mrt-program-label mrt-program-label--assigned'
        // Invalid gets an explicit textual badge (a non-color cue).
        div.textContent = invalid ? `⚠ ${label} — OUTSIDE PARENT` : `${label}${planning.lifecycleState === 'DRAFT' ? ' (draft)' : ''}`
        div.style.position = 'absolute'
        div.style.left = `${Math.round(view.x)}px`
        div.style.top = `${Math.round(view.y)}px`
        div.style.transform = 'translate(-50%, -50%)'
        div.style.pointerEvents = 'none'
        div.style.whiteSpace = 'nowrap'
        div.style.font = '700 13px system-ui, sans-serif'
        div.style.color = invalid ? '#ffe6e2' : planning.lifecycleState === 'LOCKED' ? '#e6faf1' : '#fbf0d8'
        div.style.padding = '2px 8px'
        div.style.borderRadius = '5px'
        div.style.background = invalid ? 'rgba(70,18,14,0.86)' : planning.lifecycleState === 'LOCKED' ? 'rgba(16,42,36,0.8)' : 'rgba(60,44,12,0.8)'
        div.style.border = `${invalid ? '2px dashed rgba(235,90,80,0.95)' : `1px solid ${planning.lifecycleState === 'LOCKED' ? 'rgba(110,200,175,0.9)' : 'rgba(235,190,110,0.9)'}`}`
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
