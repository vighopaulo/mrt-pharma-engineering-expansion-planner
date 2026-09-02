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
    cancelDrag,
    commitDrag,
    selectByPickId,
    getSpatialDecorator,
    updateDragPreview,
    spatialAssetStore,
} from './spatialAssetOverlay'
import { decideHitAcceptance, rayIntersectZPlane, type Ray3 } from './assetPicking'

export class MrtDirectManipulationTool extends PrimitiveTool {
    public static override toolId = 'MrtPharma.DirectManipulation'

    /** Z of the drag plane, fixed when a drag begins (preserve start Z). */
    private dragPlaneZ = 0

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

    /** Locate the MRT asset (if any) under the event; returns its assetInstanceId. */
    private async locateAssetId(ev: BeButtonEvent): Promise<string | undefined> {
        const vp: ScreenViewport | undefined = ev.viewport
        if (!vp) return undefined
        // allowDecorations is enabled in onPostInstall so the locate does not
        // reject the transient (decoration) hit.
        const hit = await IModelApp.locateManager.doLocate(new LocateResponse(), true, ev.point, vp, ev.inputSource)
        const accepts = !!hit?.sourceId && !!getSpatialDecorator()?.testDecorationHit(hit.sourceId)
        if (import.meta.env.DEV) {
            console.info('[direct-pick] locate sourceId=%s isDecoration=%s decoratorAccepts=%s',
                hit?.sourceId ?? '—', String(hit ? !hit.isElementHit : false), String(accepts))
        }
        if (accepts && hit) {
            const assetId = selectByPickId(hit.sourceId)
            if (import.meta.env.DEV) console.info('[direct-pick] assetInstanceId=%s', assetId ?? '—')
            return assetId
        }
        return undefined
    }

    /** Data-button click: select the asset under the cursor (no movement). */
    public override async onDataButtonDown(ev: BeButtonEvent): Promise<EventHandled> {
        // If a drag is somehow active, a click commits it (safety); else select.
        if (spatialAssetStore.isDragActive()) {
            commitDrag()
            return EventHandled.Yes
        }
        await this.locateAssetId(ev)
        return EventHandled.Yes
    }

    /**
     * Start of a drag gesture (Bentley calls this once the drag threshold is
     * exceeded, so click vs drag is distinguished by the platform). Begin a
     * fluid drag if the pressed point is on an MRT asset.
     */
    public override async onMouseStartDrag(ev: BeButtonEvent): Promise<EventHandled> {
        const assetId = await this.locateAssetId(ev)
        if (!assetId) return EventHandled.No
        const inst = spatialAssetStore.getInstance(assetId)
        if (!inst) return EventHandled.No

        // Drag plane at the asset's current Z; grab point = ray ∩ plane.
        this.dragPlaneZ = inst.transform.position.z
        const ray = this.pickRay(ev)
        const grab = ray ? rayIntersectZPlane(ray, this.dragPlaneZ) : undefined
        const grabPoint = grab ? { x: grab[0], y: grab[1], z: grab[2] } : { ...inst.transform.position }
        const ok = beginDrag(assetId, grabPoint)
        if (!ok) return EventHandled.No
        // NOTE: no beginDynamics() — the preview is rendered by the
        // SpatialAssetDecorator (invalidated on each preview update), so we do
        // not use Bentley tool dynamics. This keeps the drag lifecycle simple:
        // there is no separate dynamics state that could linger after the drag.
        // Install the scoped secondary-button guard: during a PRIMARY-button
        // drag the browser fires contextmenu on right-press and Bentley never
        // delivers a Reset callback to this tool (proven by console trace — a
        // right-click ended as DRAG_COMMIT, no onResetButtonDown/Up). So while a
        // drag is active we listen for the secondary button on the viewport
        // element ONLY and route it to the same cancel pipeline.
        this.installSecondaryButtonGuard(ev.viewport)
        MrtDirectManipulationTool.diag('BEGIN', assetId)
        return EventHandled.Yes
    }

    /** Motion during drag: update the transient preview (no domain event). If a
     * pointer update cannot resolve a finite drag-plane point, ignore it and
     * keep the last valid preview (never commit or error on it). */
    public override async onMouseMotion(ev: BeButtonEvent): Promise<void> {
        if (!spatialAssetStore.isDragActive()) return
        const ray = this.pickRay(ev)
        const hit = ray ? rayIntersectZPlane(ray, this.dragPlaneZ) : undefined
        if (hit && hit.every((n) => Number.isFinite(n))) {
            updateDragPreview({ x: hit[0], y: hit[1], z: hit[2] })
        }
    }

    /** Release after drag (primary button): commit exactly one authoritative move. */
    public override async onMouseEndDrag(ev: BeButtonEvent): Promise<EventHandled> {
        if (!spatialAssetStore.isDragActive()) return EventHandled.No
        // Final preview update from the release point (if finite), then one commit.
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
        const active = spatialAssetStore.isDragActive()
        const targetId = spatialAssetStore.getDragPreview()?.assetInstanceId
        MrtDirectManipulationTool.dbg(`[direct-cancel] stage=ENTER input=${reason} assetInstanceId=${targetId ?? '—'} previewActiveBefore=${active} interactionBefore=${spatialAssetStore.getInteractionState()} selectedAssetInstanceId=${spatialAssetStore.getSnapshot().selectedAssetInstanceId ?? '—'}`)
        // Always drop the secondary-button guard when cancelling.
        this.removeSecondaryButtonGuard()
        if (!active) {
            MrtDirectManipulationTool.dbg(`[direct-cancel] stage=EXIT input=${reason} result=NO_ACTIVE_DRAG`)
            return false
        }
        cancelDrag() // clears preview -> interaction IDLE; committed pos + selection retained
        MrtDirectManipulationTool.dbg(`[direct-cancel] stage=EXIT input=${reason} previewActiveAfter=${spatialAssetStore.isDragActive()} interactionAfter=${spatialAssetStore.getInteractionState()} selectedAssetInstanceId=${spatialAssetStore.getSnapshot().selectedAssetInstanceId ?? '—'} assetMovedEvents=0`)
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
        if (wentDown && keyEvent.key === 'Escape' && spatialAssetStore.isDragActive()) {
            this.cancelActiveDirectDrag('ESC')
            return EventHandled.Yes
        }
        return EventHandled.No
    }

    /** Interruption safety: never leave a stale active drag; restore locate opts. */
    public override async onCleanup(): Promise<void> {
        MrtDirectManipulationTool.dbg(`[direct-input] callback=onCleanup dragActive=${spatialAssetStore.isDragActive()} interaction=${spatialAssetStore.getInteractionState()}`)
        if (spatialAssetStore.isDragActive()) {
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
    private static diag(event: 'BEGIN' | 'COMMIT' | 'CANCEL' | 'CLEANUP', assetInstanceId: string | undefined): void {
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
