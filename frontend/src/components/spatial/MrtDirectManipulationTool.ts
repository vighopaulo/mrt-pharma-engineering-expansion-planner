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
    beginRotate,
    cancelDrag,
    cancelRotate,
    commitDrag,
    commitRotate,
    getSpatialDecorator,
    updateDragPreview,
    updateRotatePreview,
    spatialAssetStore,
} from './spatialAssetOverlay'
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
    /** Active rotation gesture state (object-attached fluid yaw). */
    private rotateStartYaw = 0
    private rotateCenter: { x: number; y: number } = { x: 0, y: 0 }
    private rotateStartPoint: { x: number; y: number } = { x: 0, y: 0 }
    private rotatePlaneZ = 0
    /** Bounded per-gesture rotation-preview update log counter (first 5 only). */
    private rotatePreviewLogCount = 0

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

    /** Data-button click: select the asset under the cursor (no movement). */
    public override async onDataButtonDown(ev: BeButtonEvent): Promise<EventHandled> {
        // If a manipulation is somehow active, a click commits it (safety).
        if (spatialAssetStore.isDragActive()) { commitDrag(); return EventHandled.Yes }
        if (spatialAssetStore.isRotationActive()) { commitRotate(); return EventHandled.Yes }
        const target = await this.locatePickTarget(ev)
        // A click on either the body or the handle selects the asset (no move).
        if (target) spatialAssetStore.selectAsset(target.assetInstanceId)
        return EventHandled.Yes
    }

    /**
     * Start of a drag gesture (Bentley calls this once the drag threshold is
     * exceeded). Drag the BODY => fluid translate; drag the ROTATION HANDLE =>
     * fluid yaw rotation.
     */
    public override async onMouseStartDrag(ev: BeButtonEvent): Promise<EventHandled> {
        const target = await this.locatePickTarget(ev)
        if (!target) return EventHandled.No
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

        // ASSET_BODY => fluid translate. Drag plane at the asset's current Z.
        this.dragPlaneZ = inst.transform.position.z
        const ray = this.pickRay(ev)
        const grab = ray ? rayIntersectZPlane(ray, this.dragPlaneZ) : undefined
        const grabPoint = grab ? { x: grab[0], y: grab[1], z: grab[2] } : { ...inst.transform.position }
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
        if (!spatialAssetStore.isDragActive()) return
        const ray = this.pickRay(ev)
        const hit = ray ? rayIntersectZPlane(ray, this.dragPlaneZ) : undefined
        if (hit && hit.every((n) => Number.isFinite(n))) {
            updateDragPreview({ x: hit[0], y: hit[1], z: hit[2] })
        }
    }

    /** Release after a translate or rotate gesture: commit exactly one op. */
    public override async onMouseEndDrag(ev: BeButtonEvent): Promise<EventHandled> {
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
        const targetId = spatialAssetStore.getDragPreview()?.assetInstanceId ?? spatialAssetStore.getRotationPreview()?.assetInstanceId
        MrtDirectManipulationTool.dbg(`[direct-cancel] stage=ENTER input=${reason} assetInstanceId=${targetId ?? '—'} dragActiveBefore=${dragActive} rotateActiveBefore=${rotateActive} interactionBefore=${spatialAssetStore.getInteractionState()} selectedAssetInstanceId=${spatialAssetStore.getSnapshot().selectedAssetInstanceId ?? '—'}`)
        // Always drop the secondary-button guard when cancelling.
        this.removeSecondaryButtonGuard()
        if (!dragActive && !rotateActive) {
            MrtDirectManipulationTool.dbg(`[direct-cancel] stage=EXIT input=${reason} result=NO_ACTIVE_MANIPULATION`)
            return false
        }
        if (dragActive) cancelDrag() // clears preview -> IDLE; committed pos + selection retained
        if (rotateActive) cancelRotate() // clears preview -> IDLE; committed yaw + selection retained
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
        if (!spatialAssetStore.isDragActive()) return
        e.preventDefault()
        e.stopPropagation()
        MrtDirectManipulationTool.dbg(`[direct-secondary] callback=domPointerDown button=2 dragActive=true interaction=${spatialAssetStore.getInteractionState()} activeTool=${IModelApp.toolAdmin?.activeTool?.toolId ?? '—'}`)
        this.cancelActiveDirectDrag('RIGHT_CLICK')
    }
    private readonly onSecondaryContextMenu = (e: MouseEvent): void => {
        // Suppress the browser context menu ONLY while an MRT drag is active.
        if (spatialAssetStore.isDragActive()) {
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

    /** Reset / right-click cancels an active drag. Handle DOWN so cancellation
     * happens as early as possible during the gesture (UP is a safe no-op). */
    public override async onResetButtonDown(_ev: BeButtonEvent): Promise<EventHandled> {
        MrtDirectManipulationTool.dbg(`[direct-input] callback=onResetButtonDown dragActive=${spatialAssetStore.isDragActive()} interaction=${spatialAssetStore.getInteractionState()} activeTool=${IModelApp.toolAdmin?.activeTool?.toolId ?? '—'}`)
        return this.cancelActiveDirectDrag('RESET') ? EventHandled.Yes : EventHandled.No
    }

    public override async onResetButtonUp(_ev: BeButtonEvent): Promise<EventHandled> {
        MrtDirectManipulationTool.dbg(`[direct-input] callback=onResetButtonUp dragActive=${spatialAssetStore.isDragActive()} interaction=${spatialAssetStore.getInteractionState()} activeTool=${IModelApp.toolAdmin?.activeTool?.toolId ?? '—'}`)
        return this.cancelActiveDirectDrag('RESET') ? EventHandled.Yes : EventHandled.No
    }

    /** Esc cancels an active direct drag (ToolAdmin routes keys here). */
    public override async onKeyTransition(wentDown: boolean, keyEvent: KeyboardEvent): Promise<EventHandled> {
        MrtDirectManipulationTool.dbg(`[direct-input] callback=onKeyTransition key=${keyEvent.key} wentDown=${wentDown} dragActive=${spatialAssetStore.isDragActive()} interaction=${spatialAssetStore.getInteractionState()} activeTool=${IModelApp.toolAdmin?.activeTool?.toolId ?? '—'}`)
        if (wentDown && keyEvent.key === 'Escape' && (spatialAssetStore.isDragActive() || spatialAssetStore.isRotationActive())) {
            this.cancelActiveDirectDrag('ESC')
            return EventHandled.Yes
        }
        return EventHandled.No
    }

    /** Interruption safety: never leave a stale active manipulation; restore locate opts. */
    public override async onCleanup(): Promise<void> {
        MrtDirectManipulationTool.dbg(`[direct-input] callback=onCleanup dragActive=${spatialAssetStore.isDragActive()} rotateActive=${spatialAssetStore.isRotationActive()} interaction=${spatialAssetStore.getInteractionState()}`)
        if (spatialAssetStore.isDragActive() || spatialAssetStore.isRotationActive()) {
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
