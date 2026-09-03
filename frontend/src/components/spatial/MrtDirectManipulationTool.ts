/**
 * MrtDirectManipulationTool — bounded Bentley PrimitiveTool for DIRECT object
 * selection + fluid drag of MRT Pharma spatial assets.
 *
 * Interaction:
 *   data-button click on a scanner  -> resolve pickable id -> select (no move)
 *   press + exceed drag threshold    -> begin fluid drag (grab offset preserved)
 *   pointer motion during drag       -> update TRANSIENT preview (no event)
 *   release                          -> commit ONE authoritative move + ONE ASSET_MOVED
 *   reset / Esc / cleanup            -> cancel (no event, restore committed pos)
 *
 * CENTRAL DOCTRINE: preview is not commit. N pointer-move events -> N preview
 * updates -> 1 release -> 1 authoritative commit -> 1 ASSET_MOVED. No permanent
 * event per pointer frame. READ-ONLY wrt the iModel (requireWriteableTarget
 * false; no changeset). Fluid drag preserves start Z (X/Y planar movement) and
 * rotation; identity is immutable.
 *
 * Selection uses NATIVE Bentley decoration picking: the decorator draws pickable
 * WorldDecoration graphics with transient ids and implements testDecorationHit;
 * a located HitDetail.sourceId maps back to the assetInstanceId.
 */
import {
    IModelApp,
    PrimitiveTool,
    EventHandled,
    LocateResponse,
    LocateFilterStatus,
    type BeButtonEvent,
    type HitDetail,
    type ScreenViewport,
} from '@itwin/core-frontend'
import {
    beginDrag,
    beginGroupDrag,
    beginRotate,
    cancelDrag,
    cancelGroupDrag,
    cancelRotate,
    clearSelection,
    closeAssetContextMenu,
    commitDrag,
    commitGroupDrag,
    commitRotate,
    computeAssetScreenBounds,
    getSpatialDecorator,
    openAssetContextMenu,
    replaceSelection,
    setMarqueeRect,
    setRotationHandleHover,
    updateDragPreview,
    updateGroupDragPreview,
    updateRotatePreview,
    spatialAssetStore,
} from './spatialAssetOverlay'
import { marqueeSelect, normalizeScreenRect, screenDragDistance } from './assetPicking'
import {
    computePreviewYaw,
    decideHitAcceptance,
    pointerNearProjectedRing,
    rayIntersectZPlane,
    resolveMrtPickTarget,
    ringWorldSamples,
    type MrtPickTarget,
    type Ray3,
} from './assetPicking'

export class MrtDirectManipulationTool extends PrimitiveTool {
    public static override toolId = 'MrtPharma.DirectManipulation'

    /** Z of the drag plane, fixed when a drag begins (preserve start Z). */
    private dragPlaneZ = 0
    /** Z of the group-drag plane (the anchor's start Z; delta is X/Y only). */
    private groupPlaneZ = 0
    /** Active rotation gesture state (object-attached fluid yaw). */
    private rotateStartYaw = 0
    private rotateCenter: { x: number; y: number } = { x: 0, y: 0 }
    private rotateStartPoint: { x: number; y: number } = { x: 0, y: 0 }
    private rotatePlaneZ = 0
    /** Bounded per-gesture rotation-preview update log counter (first 5 only). */
    private rotatePreviewLogCount = 0
    /** Bounded group-preview update log counter (first 3 frames). */
    private groupPreviewLogCount = 0
    /** Active marquee (bounding-box) selection gesture state (view px). */
    private marqueeActive = false
    private marqueeStart: { x: number; y: number } = { x: 0, y: 0 }
    private marqueePriorSelection: string[] = []
    /** Minimum drag distance (px) before an empty-space drag becomes a marquee
     * rather than an empty click. */
    private static readonly MARQUEE_MIN_DRAG_PX = 5

    public override requireWriteableTarget(): boolean {
        return false
    }

    public override async onPostInstall(): Promise<void> {
        await super.onPostInstall()
        // Do NOT enable passive locate or AccuSnap. Passive locate-on-motion is
        // what surfaced "Element not valid for tool" (LocateFailure.ByApp) as
        // the cursor crossed BIM: AccuSnap runs the locate filter on hover, our
        // filterHit rejects the non-MRT hit, and ElementLocateManager sets the
        // ByApp reason which AccuSnap then displays. We instead locate EXPLICITLY
        // on click / drag-start via doLocate, so hovering BIM is completely
        // quiet. (AccuSnap is also what activated PrimitiveTool.isValidLocation's
        // project-extents check.)
        this.changeLocateState(/* enableLocate */ false, /* enableSnap */ false)
        // CRITICAL: our explicit doLocate must still accept transient
        // (decoration) geometry — the MRT scanners are pickable WorldDecorations,
        // not iModel elements. Without this, ElementLocateManager rejects with
        // "LocateFailure.Transient" ("Decoration is not valid for this tool").
        IModelApp.locateManager.options.allowDecorations = true
        IModelApp.notifications.outputPromptByKey?.('MrtPharma:tools.DirectManipulation.Prompts.SelectOrDrag')
    }

    public override async onRestartTool(): Promise<void> {
        await this.exitTool()
    }

    /**
     * The MRT scanner is application-owned OVERLAY geometry, not an iModel
     * element being placed. Bypass PrimitiveTool's default element-placement
     * validation (which rejects points outside the iModel project extents with
     * "Invalid location. All elements must fit within the volume defined by the
     * project extents."). Finite-point validation for the overlay move happens
     * in the store's move command. This does NOT globally disable project-extents
     * checks for other tools — it is scoped to this tool instance only.
     */
    public override isValidLocation(_ev: BeButtonEvent, _isButtonEvent: boolean): boolean {
        return true
    }

    /**
     * Accept ONLY hits that map to an MRT Pharma AssetInstance (pickable
     * decoration). BIM elements, reality models, and unrelated decorations are
     * rejected so the tool never starts a direct drag on non-owned geometry.
     */
    public override async filterHit(hit: HitDetail, _out?: LocateResponse): Promise<LocateFilterStatus> {
        const decorator = getSpatialDecorator()
        const decision = decideHitAcceptance(
            { sourceId: hit.sourceId, isElementHit: hit.isElementHit },
            (pickId) => decorator?.assetIdForPickId(pickId),
        )
        if (import.meta.env.DEV) {
            console.info('[direct-pick] sourceId=%s isDecoration=%s toolFilter=%s',
                hit.sourceId ?? '—', String(!hit.isElementHit), decision)
        }
        return decision === 'ACCEPT' ? LocateFilterStatus.Accept : LocateFilterStatus.Reject
    }

    /**
     * Build a world-space pick ray at the event's view point using the viewport
     * frustum: NPC (x,y,0) -> near, NPC (x,y,1) -> far.
     */
    private pickRay(ev: BeButtonEvent): Ray3 | undefined {
        const vp = ev.viewport
        if (!vp) return undefined
        const view = ev.viewPoint ?? vp.worldToView(ev.point)
        const npc = vp.viewToNpc(view)
        const near = vp.npcToWorld({ x: npc.x, y: npc.y, z: 0 })
        const far = vp.npcToWorld({ x: npc.x, y: npc.y, z: 1 })
        return {
            origin: [near.x, near.y, near.z],
            direction: [far.x - near.x, far.y - near.y, far.z - near.z],
        }
    }

    /** Locate the MRT pick target (body or rotation handle) under the event. */
    private async locatePickTarget(ev: BeButtonEvent): Promise<MrtPickTarget | undefined> {
        const vp: ScreenViewport | undefined = ev.viewport
        if (!vp) return undefined
        // allowDecorations is enabled in onPostInstall so the locate does not
        // reject the transient (decoration) hit.
        const hit = await IModelApp.locateManager.doLocate(new LocateResponse(), true, ev.point, vp, ev.inputSource)
        const decorator = getSpatialDecorator()
        const nativeTarget = hit
            ? resolveMrtPickTarget(
                { sourceId: hit.sourceId, isElementHit: hit.isElementHit },
                (id) => decorator?.handleAssetIdForPickId(id),
                (id) => decorator?.assetIdForPickId(id),
            )
            : undefined

        // Runtime raw-pick diagnostic (bounded). Reports the ACTUAL Bentley
        // sourceId and how it resolved, so A/B/C can be read from the browser.
        const selectedId = spatialAssetStore.getSnapshot().selectedAssetInstanceId
        if (import.meta.env.DEV) {
            const bodyAsset = hit?.sourceId ? decorator?.assetIdForPickId(hit.sourceId) : undefined
            const handleAsset = hit?.sourceId ? decorator?.handleAssetIdForPickId(hit.sourceId) : undefined
            MrtDirectManipulationTool.dbg(`[rotation-pick] sourceId=${hit?.sourceId ?? 'NONE'} isDecoration=${hit ? String(!hit.isElementHit) : 'false'} bodyAssetId=${bodyAsset ?? 'NONE'} handleAssetId=${handleAsset ?? 'NONE'} targetType=${nativeTarget?.type ?? 'UNKNOWN'} assetInstanceId=${nativeTarget?.assetInstanceId ?? 'NONE'} selected=${selectedId ?? 'NONE'}`)
            if (selectedId && decorator) {
                const bodyPickId = decorator.bodyPickIdForInstance(selectedId)
                const handlePickId = decorator.handlePickIdForInstance(selectedId)
                MrtDirectManipulationTool.dbg(`[rotation-handle-map] assetInstanceId=${selectedId} bodyPickId=${bodyPickId ?? 'NONE'} handlePickId=${handlePickId ?? 'NONE'} sameId=${String(!!bodyPickId && bodyPickId === handlePickId)} handleRegistered=${String(!!handlePickId)} generation=${decorator.getDecorateGeneration()}`)
            }
        }

        // If native locate already resolved the handle, use it.
        if (nativeTarget?.type === 'ROTATION_HANDLE') return nativeTarget

        // SCOPED FALLBACK (section 34): the thin torus can lose the native pick
        // to the body underneath it. ONLY for the currently selected asset that
        // actually has a rendered handle, test whether the pointer lies within a
        // small screen-space band of the projected rotation ring. If so, resolve
        // ROTATION_HANDLE for that asset. This never selects BIM, never applies
        // to unselected assets, and is keyed by assetInstanceId (not screen px).
        const handleFallback = this.tryScreenSpaceHandle(ev, vp, selectedId)
        if (handleFallback) {
            if (import.meta.env.DEV) {
                MrtDirectManipulationTool.dbg(`[rotation-pick] fallback=SCREEN_SPACE_RING targetType=ROTATION_HANDLE assetInstanceId=${handleFallback.assetInstanceId}`)
            }
            return handleFallback
        }

        if (import.meta.env.DEV) {
            console.info('[direct-pick] locate sourceId=%s isDecoration=%s target=%s assetInstanceId=%s',
                hit?.sourceId ?? '—', String(hit ? !hit.isElementHit : false), nativeTarget?.type ?? 'NONE', nativeTarget?.assetInstanceId ?? '—')
        }
        return nativeTarget
    }

    /**
     * Scoped screen-space rotation-handle resolution for the SELECTED asset only.
     * Projects the asset's rotation ring to view coordinates and returns a
     * ROTATION_HANDLE target when the pointer is within a small pixel tolerance
     * of the projected ring outline. Returns undefined otherwise. Requires a
     * live handle pick id (i.e. the handle is actually rendered).
     */
    private tryScreenSpaceHandle(
        ev: BeButtonEvent,
        vp: ScreenViewport,
        selectedId: string | undefined,
    ): MrtPickTarget | undefined {
        if (!selectedId) return undefined
        const decorator = getSpatialDecorator()
        if (!decorator) return undefined
        // Only if the handle is actually registered/rendered this frame.
        if (!decorator.handlePickIdForInstance(selectedId)) return undefined
        const inst = spatialAssetStore.getInstance(selectedId)
        if (!inst) return undefined
        const ring = decorator.rotationRingWorldFor(inst)
        const worldSamples = ringWorldSamples(ring.center, ring.radius, 40)
        const viewSamples = worldSamples.map((w) => {
            const v = vp.worldToView({ x: w[0], y: w[1], z: w[2] })
            return { x: v.x, y: v.y }
        })
        const pointerView = ev.viewPoint ?? vp.worldToView(ev.point)
        const tolerancePx = 14
        const near = pointerNearProjectedRing({ x: pointerView.x, y: pointerView.y }, viewSamples, tolerancePx)
        return near ? { type: 'ROTATION_HANDLE', assetInstanceId: selectedId } : undefined
    }

    /**
     * Data-button click: selection.
     *   plain click on an asset  -> REPLACE selection with it
     *   Shift + click on an asset -> TOGGLE it in the multi-selection
     *   click on empty/non-asset  -> CLEAR selection (+ close context menu)
     * Never moves anything. Any open context menu is dismissed.
     */
    public override async onDataButtonDown(ev: BeButtonEvent): Promise<EventHandled> {
        // If a manipulation is somehow active, a click commits it (safety).
        if (spatialAssetStore.isDragActive()) { commitDrag(); return EventHandled.Yes }
        if (spatialAssetStore.isRotationActive()) { commitRotate(); return EventHandled.Yes }
        if (spatialAssetStore.isGroupDragActive()) { commitGroupDrag(); return EventHandled.Yes }
        closeAssetContextMenu()
        const target = await this.locatePickTarget(ev)
        if (target) {
            if (ev.isShiftKey) {
                spatialAssetStore.toggleAsset(target.assetInstanceId)
            } else if (spatialAssetStore.isSelected(target.assetInstanceId)) {
                // Pressing an ALREADY-selected member must NOT collapse a
                // multi-selection here — otherwise a subsequent body drag would
                // start as SINGLE instead of GROUP (onDataButtonDown fires on
                // press, before onMouseStartDrag). Preserve the current selection;
                // a genuine click without drag keeps it selected (harmless), and a
                // drag proceeds as a group drag.
                MrtDirectManipulationTool.dbg(`[group-drag] stage=POINTER_DOWN target=${target.assetInstanceId} targetSelected=true validSelectedCount=${spatialAssetStore.getSelectedInstances().length} preserve-selection`)
            } else {
                // Pressing an UNSELECTED asset replaces the selection with it.
                spatialAssetStore.selectAsset(target.assetInstanceId)
            }
        } else {
            // Empty / non-application-owned target -> clear MRT selection.
            clearSelection()
        }
        return EventHandled.Yes
    }

    /**
     * Start of a drag gesture (Bentley calls this once the drag threshold is
     * exceeded). Drag the BODY => fluid translate; drag the ROTATION HANDLE =>
     * fluid yaw rotation.
     */
    public override async onMouseStartDrag(ev: BeButtonEvent): Promise<EventHandled> {
        const target = await this.locatePickTarget(ev)
        if (!target) {
            // Empty 3D space => begin MARQUEE (bounding-box) selection. Claiming
            // the drag (EventHandled.Yes) suppresses camera orbit for this gesture.
            const vp = ev.viewport
            const view = ev.viewPoint ?? (vp ? vp.worldToView(ev.point) : undefined)
            if (!view) return EventHandled.No
            this.marqueeActive = true
            this.marqueeStart = { x: view.x, y: view.y }
            this.marqueePriorSelection = [...spatialAssetStore.getSelectedIds()]
            setMarqueeRect({ startX: view.x, startY: view.y, currentX: view.x, currentY: view.y })
            MrtDirectManipulationTool.dbg(`[interaction-pick] target=EMPTY gesture=MARQUEE`)
            return EventHandled.Yes
        }
        const inst = spatialAssetStore.getInstance(target.assetInstanceId)
        if (!inst) return EventHandled.No

        if (target.type === 'ROTATION_HANDLE') {
            MrtDirectManipulationTool.dbg(`[rotation-start] stage=INPUT sourceId=handle targetType=ROTATION_HANDLE assetInstanceId=${target.assetInstanceId} selectedAssetInstanceId=${spatialAssetStore.getSnapshot().selectedAssetInstanceId ?? 'NONE'} interactionBefore=${spatialAssetStore.getInteractionState()}`)
            // Begin object-attached fluid rotation about the instance center.
            this.rotatePlaneZ = inst.transform.position.z
            const ray = this.pickRay(ev)
            const hit = ray ? rayIntersectZPlane(ray, this.rotatePlaneZ) : undefined
            if (!hit) {
                MrtDirectManipulationTool.dbg(`[rotation-start] stage=STORE_BEGIN assetInstanceId=${target.assetInstanceId} result=INVALID_START_POINT failureReason=RAY_MISS interactionAfter=${spatialAssetStore.getInteractionState()} rotationPreviewActive=false`)
                return EventHandled.No
            }
            const ok = beginRotate(target.assetInstanceId)
            MrtDirectManipulationTool.dbg(`[rotation-start] stage=STORE_BEGIN assetInstanceId=${target.assetInstanceId} result=${ok ? 'SUCCESS' : 'FAILURE'} failureReason=${ok ? 'NONE' : 'BEGIN_ROTATE_REJECTED'} interactionAfter=${spatialAssetStore.getInteractionState()} rotationPreviewActive=${String(spatialAssetStore.isRotationActive())}`)
            if (!ok) return EventHandled.No
            this.rotateStartYaw = inst.transform.rotation.yaw
            this.rotateCenter = { x: inst.transform.position.x, y: inst.transform.position.y }
            this.rotateStartPoint = { x: hit[0], y: hit[1] }
            this.installSecondaryButtonGuard(ev.viewport)
            const startPointerAngle = Math.atan2(hit[1] - this.rotateCenter.y, hit[0] - this.rotateCenter.x) * (180 / Math.PI)
            MrtDirectManipulationTool.dbg(`[rotation-preview] stage=BEGIN assetInstanceId=${target.assetInstanceId} startYaw=${this.rotateStartYaw} previewYaw=${this.rotateStartYaw} center=${this.rotateCenter.x},${this.rotateCenter.y},${this.rotatePlaneZ} startPointerAngle=${startPointerAngle.toFixed(2)} previewActive=${String(spatialAssetStore.isRotationActive())}`)
            this.rotatePreviewLogCount = 0
            MrtDirectManipulationTool.diag('BEGIN_ROTATE', target.assetInstanceId)
            return EventHandled.Yes
        }

        // ASSET_BODY => translate. Drag plane at the asset's current Z.
        this.dragPlaneZ = inst.transform.position.z
        const ray = this.pickRay(ev)
        const grab = ray ? rayIntersectZPlane(ray, this.dragPlaneZ) : undefined
        const grabPoint = grab ? { x: grab[0], y: grab[1], z: grab[2] } : { ...inst.transform.position }

        // GROUP translate when the grabbed body is a selected member and more
        // than one asset is selected; otherwise SINGLE translate. Group members
        // come from the authoritative multi-selection (not visual overlap).
        // Count VALID selected members (existing app assets) — a stale/deleted id
        // must never block a legitimate drag.
        const validSelectedCount = spatialAssetStore.getSelectedInstances().length
        const isSelectedMember = spatialAssetStore.isSelected(target.assetInstanceId)
        const groupEligible = isSelectedMember && validSelectedCount > 1
        MrtDirectManipulationTool.dbg(`[group-drag] stage=POINTER_DOWN target=${target.assetInstanceId} targetSelected=${isSelectedMember} validSelectedCount=${validSelectedCount} gesture=${groupEligible ? 'GROUP_DRAG' : 'SINGLE_DRAG'}`)
        if (groupEligible) {
            this.groupPlaneZ = inst.transform.position.z
            const ok = beginGroupDrag(target.assetInstanceId, grabPoint)
            MrtDirectManipulationTool.dbg(`[group-drag] stage=BEGIN_ATTEMPT anchor=${target.assetInstanceId} result=${ok ? 'PASS' : 'FAIL'} interactionAfter=${spatialAssetStore.getInteractionState()} memberCount=${spatialAssetStore.getGroupDragPreview()?.assetInstanceIds.length ?? 0}`)
            if (ok) {
                this.groupPreviewLogCount = 0
                this.installSecondaryButtonGuard(ev.viewport)
                MrtDirectManipulationTool.diag('BEGIN', target.assetInstanceId)
                return EventHandled.Yes
            }
            // Group begin failed (e.g. selection resolved to <2 valid members):
            // FALL BACK to single translation of the grabbed asset so the drag
            // is never silently swallowed.
            MrtDirectManipulationTool.dbg('[group-drag] stage=FALLBACK group begin failed -> single drag')
        }

        // Single translation. Ensure the grabbed asset is the sole selection so
        // the single-drag path and UI are consistent (a plain body drag on an
        // asset selects it).
        const ok = beginDrag(target.assetInstanceId, grabPoint)
        if (!ok) return EventHandled.No
        // Scoped secondary-button guard (see comment in previous build): the
        // browser handles right-press as contextmenu during a primary drag.
        this.installSecondaryButtonGuard(ev.viewport)
        MrtDirectManipulationTool.diag('BEGIN', target.assetInstanceId)
        return EventHandled.Yes
    }

    /** Motion during a translate or rotate gesture: update the transient preview
     * (no domain event). Invalid points are ignored (keep last valid preview). */
    public override async onMouseMotion(ev: BeButtonEvent): Promise<void> {
        if (this.marqueeActive) {
            const vp = ev.viewport
            const view = ev.viewPoint ?? (vp ? vp.worldToView(ev.point) : undefined)
            if (view) setMarqueeRect({ startX: this.marqueeStart.x, startY: this.marqueeStart.y, currentX: view.x, currentY: view.y })
            return
        }
        if (spatialAssetStore.isRotationActive()) {
            const ray = this.pickRay(ev)
            const hit = ray ? rayIntersectZPlane(ray, this.rotatePlaneZ) : undefined
            if (hit && hit.every((n) => Number.isFinite(n))) {
                const yaw = computePreviewYaw({
                    startYaw: this.rotateStartYaw,
                    center: this.rotateCenter,
                    startPoint: this.rotateStartPoint,
                    currentPoint: { x: hit[0], y: hit[1] },
                })
                if (yaw !== undefined) {
                    updateRotatePreview(yaw)
                    if (import.meta.env.DEV && this.rotatePreviewLogCount < 5) {
                        this.rotatePreviewLogCount += 1
                        const currentPointerAngle = Math.atan2(hit[1] - this.rotateCenter.y, hit[0] - this.rotateCenter.x) * (180 / Math.PI)
                        const eff = spatialAssetStore.getRotationPreview()?.previewYaw
                        console.info('[rotation-preview] stage=UPDATE pointerWorld=%s,%s center=%s,%s startYaw=%s currentPointerAngle=%s previewYaw=%s effectiveYaw=%s',
                            hit[0].toFixed(2), hit[1].toFixed(2), this.rotateCenter.x.toFixed(2), this.rotateCenter.y.toFixed(2),
                            this.rotateStartYaw, currentPointerAngle.toFixed(2), yaw.toFixed(2), eff !== undefined ? eff.toFixed(2) : '—')
                    }
                }
            }
            return
        }
        if (spatialAssetStore.isGroupDragActive()) {
            const ray = this.pickRay(ev)
            const hit = ray ? rayIntersectZPlane(ray, this.groupPlaneZ) : undefined
            if (hit && hit.every((n) => Number.isFinite(n))) {
                updateGroupDragPreview({ x: hit[0], y: hit[1], z: hit[2] })
                if (import.meta.env.DEV && this.groupPreviewLogCount < 3) {
                    this.groupPreviewLogCount += 1
                    const gp = spatialAssetStore.getGroupDragPreview()
                    console.info('[group-drag] stage=PREVIEW memberCount=%s delta=(%s,%s)',
                        String(gp?.assetInstanceIds.length ?? 0), gp ? gp.translationDelta.x.toFixed(2) : '—', gp ? gp.translationDelta.y.toFixed(2) : '—')
                }
            }
            return
        }
        if (!spatialAssetStore.isDragActive()) {
            // Idle: update rotation-handle hover prominence for the sole
            // selected asset (raises the faint idle handle to a subtle HOVER).
            this.updateRotationHandleHover(ev)
            return
        }
        const ray = this.pickRay(ev)
        const hit = ray ? rayIntersectZPlane(ray, this.dragPlaneZ) : undefined
        if (hit && hit.every((n) => Number.isFinite(n))) {
            updateDragPreview({ x: hit[0], y: hit[1], z: hit[2] })
        }
    }

    /** Idle hover: set the rotation-handle hover flag when the pointer is near
     * the sole selected asset's projected ring (discoverability without a bright
     * permanent ring). Cheap; only runs while IDLE. */
    private updateRotationHandleHover(ev: BeButtonEvent): void {
        const vp = ev.viewport
        const selectedId = spatialAssetStore.getSelectionCount() === 1
            ? spatialAssetStore.getSnapshot().selectedAssetInstanceId
            : undefined
        if (!vp || !selectedId) { setRotationHandleHover(false); return }
        const near = this.tryScreenSpaceHandle(ev, vp, selectedId)
        setRotationHandleHover(near !== undefined)
    }

    /** Release after a translate, rotate, group, or marquee gesture. */
    public override async onMouseEndDrag(ev: BeButtonEvent): Promise<EventHandled> {
        if (this.marqueeActive) {
            const vp = ev.viewport
            const view = ev.viewPoint ?? (vp ? vp.worldToView(ev.point) : undefined)
            const end = view ? { x: view.x, y: view.y } : this.marqueeStart
            const dist = screenDragDistance(this.marqueeStart, end)
            this.marqueeActive = false
            setMarqueeRect(undefined)
            if (dist < MrtDirectManipulationTool.MARQUEE_MIN_DRAG_PX) {
                // Below threshold: treat as an empty click -> clear selection.
                clearSelection()
                MrtDirectManipulationTool.dbg('[interaction-pick] gesture=MARQUEE below-threshold -> EMPTY_CLICK clear')
                return EventHandled.Yes
            }
            const rect = normalizeScreenRect(this.marqueeStart, end)
            const candidates = computeAssetScreenBounds()
            const selected = marqueeSelect(rect, candidates)
            replaceSelection(selected) // REPLACE policy; empty result clears
            MrtDirectManipulationTool.dbg(`[interaction-pick] gesture=MARQUEE selected=${selected.length}`)
            return EventHandled.Yes
        }
        if (spatialAssetStore.isRotationActive()) {
            const ray = this.pickRay(ev)
            const hit = ray ? rayIntersectZPlane(ray, this.rotatePlaneZ) : undefined
            if (hit && hit.every((n) => Number.isFinite(n))) {
                const yaw = computePreviewYaw({
                    startYaw: this.rotateStartYaw, center: this.rotateCenter,
                    startPoint: this.rotateStartPoint, currentPoint: { x: hit[0], y: hit[1] },
                })
                if (yaw !== undefined) updateRotatePreview(yaw)
            }
            const targetId = spatialAssetStore.getRotationPreview()?.assetInstanceId
            commitRotate()
            this.removeSecondaryButtonGuard()
            MrtDirectManipulationTool.diag('COMMIT_ROTATE', targetId)
            return EventHandled.Yes
        }
        if (spatialAssetStore.isGroupDragActive()) {
            const ray = this.pickRay(ev)
            const hit = ray ? rayIntersectZPlane(ray, this.groupPlaneZ) : undefined
            if (hit && hit.every((n) => Number.isFinite(n))) {
                updateGroupDragPreview({ x: hit[0], y: hit[1], z: hit[2] })
            }
            commitGroupDrag() // ONE ASSET_MOVED per moved member; selection retained
            this.removeSecondaryButtonGuard()
            MrtDirectManipulationTool.diag('COMMIT', spatialAssetStore.getSnapshot().selectedAssetInstanceId)
            return EventHandled.Yes
        }
        if (!spatialAssetStore.isDragActive()) return EventHandled.No
        const ray = this.pickRay(ev)
        const hit = ray ? rayIntersectZPlane(ray, this.dragPlaneZ) : undefined
        if (hit && hit.every((n) => Number.isFinite(n))) {
            updateDragPreview({ x: hit[0], y: hit[1], z: hit[2] })
        }
        const targetId = spatialAssetStore.getDragPreview()?.assetInstanceId
        commitDrag() // clears preview -> interaction returns to IDLE; selection retained
        this.removeSecondaryButtonGuard()
        MrtDirectManipulationTool.diag('COMMIT', targetId)
        return EventHandled.Yes
    }

    /**
     * ONE application cancellation path for an active direct drag. Both the
     * reset button (right-click) and Esc converge here. Discards the transient
     * preview (committed position + selection retained), returns to IDLE, emits
     * 0 ASSET_MOVED. No-op when no drag is active. Returns whether a drag was
     * actually cancelled (so callers can decide EventHandled).
     */
    private cancelActiveDirectDrag(reason: 'RESET' | 'RIGHT_CLICK' | 'ESC' | 'CLEANUP'): boolean {
        const dragActive = spatialAssetStore.isDragActive()
        const rotateActive = spatialAssetStore.isRotationActive()
        const groupActive = spatialAssetStore.isGroupDragActive()
        const targetId = spatialAssetStore.getDragPreview()?.assetInstanceId ?? spatialAssetStore.getRotationPreview()?.assetInstanceId
        MrtDirectManipulationTool.dbg(`[direct-cancel] stage=ENTER input=${reason} assetInstanceId=${targetId ?? '—'} dragActiveBefore=${dragActive} rotateActiveBefore=${rotateActive} groupActiveBefore=${groupActive} interactionBefore=${spatialAssetStore.getInteractionState()} selectedAssetInstanceId=${spatialAssetStore.getSnapshot().selectedAssetInstanceId ?? '—'}`)
        // Always drop the secondary-button guard when cancelling.
        this.removeSecondaryButtonGuard()
        if (!dragActive && !rotateActive && !groupActive) {
            MrtDirectManipulationTool.dbg(`[direct-cancel] stage=EXIT input=${reason} result=NO_ACTIVE_MANIPULATION`)
            return false
        }
        if (dragActive) cancelDrag() // clears preview -> IDLE; committed pos + selection retained
        if (rotateActive) cancelRotate() // clears preview -> IDLE; committed yaw + selection retained
        if (groupActive) cancelGroupDrag() // clears group preview -> IDLE; committed pos + selection retained
        MrtDirectManipulationTool.dbg(`[direct-cancel] stage=EXIT input=${reason} interactionAfter=${spatialAssetStore.getInteractionState()} selectedAssetInstanceId=${spatialAssetStore.getSnapshot().selectedAssetInstanceId ?? '—'} events=0`)
        MrtDirectManipulationTool.diag('CANCEL', targetId)
        return true
    }

    // --- Scoped secondary-button (right-click) guard ---------------------------
    // During a primary-button drag, the browser handles the secondary button as
    // a contextmenu and Bentley does not deliver a Reset callback to this tool.
    // We therefore attach a narrowly-scoped listener to the ACTIVE VIEWPORT
    // element ONLY while a drag is in progress. It is removed on commit, cancel,
    // and cleanup. No global/context-menu suppression is installed.
    private secondaryGuardTarget: HTMLElement | undefined
    private readonly onSecondaryPointerDown = (e: PointerEvent | MouseEvent): void => {
        if (e.button !== 2) return // secondary button only
        // During an active gesture, secondary press is ignored/deferred (Esc is
        // the authoritative cancel). We only suppress the browser menu so it does
        // not pop over an in-progress drag.
        if (spatialAssetStore.isDragActive() || spatialAssetStore.isGroupDragActive() || spatialAssetStore.isRotationActive()) {
            e.preventDefault()
            e.stopPropagation()
            MrtDirectManipulationTool.dbg(`[direct-secondary] callback=domPointerDown button=2 gestureActive=true interaction=${spatialAssetStore.getInteractionState()} (ignored; Esc cancels)`)
        }
    }
    private readonly onSecondaryContextMenu = (e: MouseEvent): void => {
        // Suppress the browser context menu ONLY while an MRT gesture is active.
        if (spatialAssetStore.isDragActive() || spatialAssetStore.isGroupDragActive() || spatialAssetStore.isRotationActive()) {
            e.preventDefault()
            e.stopPropagation()
        }
    }

    private installSecondaryButtonGuard(vp: ScreenViewport | undefined): void {
        this.removeSecondaryButtonGuard() // never double-install (StrictMode-safe)
        const el = vp?.parentDiv
        if (!el) return
        this.secondaryGuardTarget = el
        // Capture phase so we intercept before Bentley's own handlers / default.
        el.addEventListener('pointerdown', this.onSecondaryPointerDown, { capture: true })
        el.addEventListener('contextmenu', this.onSecondaryContextMenu, { capture: true })
    }

    private removeSecondaryButtonGuard(): void {
        const el = this.secondaryGuardTarget
        if (!el) return
        el.removeEventListener('pointerdown', this.onSecondaryPointerDown, { capture: true } as EventListenerOptions)
        el.removeEventListener('contextmenu', this.onSecondaryContextMenu, { capture: true } as EventListenerOptions)
        this.secondaryGuardTarget = undefined
    }

    /**
     * Reset / right-click. Right-click is now the OBJECT CONTEXT MENU surface
     * (not the drag-cancel mechanism — Esc is authoritative cancel). During an
     * active gesture, right-click is ignored (the DOM guard suppresses the
     * browser menu). When idle, a right-click on an application-owned asset
     * opens the context menu targeting that assetInstanceId; on empty/BIM it
     * closes any open menu.
     */
    public override async onResetButtonUp(ev: BeButtonEvent): Promise<EventHandled> {
        MrtDirectManipulationTool.dbg(`[direct-input] callback=onResetButtonUp interaction=${spatialAssetStore.getInteractionState()} activeTool=${IModelApp.toolAdmin?.activeTool?.toolId ?? '—'}`)
        // Ignore during an active gesture (Esc cancels).
        if (spatialAssetStore.isDragActive() || spatialAssetStore.isGroupDragActive() || spatialAssetStore.isRotationActive()) {
            return EventHandled.Yes
        }
        const target = await this.locatePickTarget(ev)
        if (target) {
            const vp = ev.viewport
            const view = ev.viewPoint ?? (vp ? vp.worldToView(ev.point) : undefined)
            openAssetContextMenu({
                assetInstanceId: target.assetInstanceId,
                screenX: view ? Math.round(view.x) : 0,
                screenY: view ? Math.round(view.y) : 0,
            })
            MrtDirectManipulationTool.dbg(`[context-menu] open assetInstanceId=${target.assetInstanceId}`)
        } else {
            closeAssetContextMenu()
        }
        return EventHandled.Yes
    }

    /** Esc cancels an active gesture (ToolAdmin routes keys here). Also closes
     * any open context menu. */
    public override async onKeyTransition(wentDown: boolean, keyEvent: KeyboardEvent): Promise<EventHandled> {
        MrtDirectManipulationTool.dbg(`[direct-input] callback=onKeyTransition key=${keyEvent.key} wentDown=${wentDown} interaction=${spatialAssetStore.getInteractionState()} activeTool=${IModelApp.toolAdmin?.activeTool?.toolId ?? '—'}`)
        if (wentDown && keyEvent.key === 'Escape') {
            closeAssetContextMenu()
            if (this.marqueeActive) {
                // Discard the marquee; restore the selection that existed before it began.
                this.marqueeActive = false
                setMarqueeRect(undefined)
                replaceSelection(this.marqueePriorSelection)
                MrtDirectManipulationTool.dbg('[interaction-pick] gesture=MARQUEE esc-cancel restore-prior')
                return EventHandled.Yes
            }
            if (spatialAssetStore.isDragActive() || spatialAssetStore.isRotationActive() || spatialAssetStore.isGroupDragActive()) {
                this.cancelActiveDirectDrag('ESC')
                return EventHandled.Yes
            }
        }
        return EventHandled.No
    }

    /** Interruption safety: never leave a stale active manipulation; restore locate opts. */
    public override async onCleanup(): Promise<void> {
        MrtDirectManipulationTool.dbg(`[direct-input] callback=onCleanup dragActive=${spatialAssetStore.isDragActive()} rotateActive=${spatialAssetStore.isRotationActive()} groupActive=${spatialAssetStore.isGroupDragActive()} interaction=${spatialAssetStore.getInteractionState()}`)
        if (this.marqueeActive) {
            this.marqueeActive = false
            setMarqueeRect(undefined)
        }
        if (spatialAssetStore.isDragActive() || spatialAssetStore.isRotationActive() || spatialAssetStore.isGroupDragActive()) {
            this.cancelActiveDirectDrag('CLEANUP')
        }
        // Always drop the secondary-button guard on cleanup (StrictMode-safe).
        this.removeSecondaryButtonGuard()
        // Restore default locate behavior so other tools are unaffected.
        IModelApp.locateManager.options.allowDecorations = false
        await super.onCleanup()
    }

    /** Bounded DEV lifecycle diagnostic (first few transitions only). */
    private static diagCount = 0
    private static diag(event: 'BEGIN' | 'COMMIT' | 'CANCEL' | 'CLEANUP' | 'BEGIN_ROTATE' | 'COMMIT_ROTATE', assetInstanceId: string | undefined): void {
        if (!import.meta.env.DEV || MrtDirectManipulationTool.diagCount >= 20) return
        MrtDirectManipulationTool.diagCount += 1
        const snap = spatialAssetStore.getSnapshot()
        console.info('[direct-drag] event=%s assetInstanceId=%s interaction=%s previewActive=%s selectionPreserved=%s',
            event, assetInstanceId ?? '—', snap.interaction, String(snap.dragActive),
            String(snap.selectedAssetInstanceId !== undefined))
    }

    /** Bounded raw DEV input diagnostic (first N lines only, never per-frame). */
    private static dbgCount = 0
    private static dbg(line: string): void {
        if (!import.meta.env.DEV || MrtDirectManipulationTool.dbgCount >= 40) return
        MrtDirectManipulationTool.dbgCount += 1
        console.info(line)
    }
}

let registered = false
function ensureRegistered(): void {
    if (registered) return
    try {
        MrtDirectManipulationTool.register('MrtPharma')
    } catch {
        // Already registered — safe to ignore.
    }
    registered = true
}

/** Start the direct-manipulation tool. Returns false if there is no viewport. */
export async function runMrtDirectManipulationTool(): Promise<boolean> {
    ensureRegistered()
    const vp = IModelApp.viewManager?.selectedView
    if (!vp) return false
    return IModelApp.tools.run(MrtDirectManipulationTool.toolId)
}

/** Exit the tool if it is active (idempotent). */
export async function exitMrtDirectManipulationTool(): Promise<void> {
    const active = IModelApp.toolAdmin?.activeTool
    if (active instanceof MrtDirectManipulationTool) {
        await active.exitTool()
    }
}
