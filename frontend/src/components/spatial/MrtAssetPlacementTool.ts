/**
 * MrtAssetPlacementTool — bounded Bentley PrimitiveTool for controlled
 * click-to-place of MRT Pharma spatial assets.
 *
 * This is the ONLY Bentley input concern in the placement path. It does NOT
 * query the catalog (Sec 32): it consumes the already-resolved PlacementIntent
 * held by the application-owned SpatialAssetStore, converts exactly ONE accepted
 * data-button click into a world-space point, asks the store to complete the
 * placement (which creates exactly one AssetInstance), then exits.
 *
 * READ-ONLY: requireWriteableTarget()=false; the tool never writes to the
 * iModel, never creates a changeset. It only reads a world point and updates
 * application-owned overlay state.
 *
 * Cancellation: reset button (right-click) or Esc exit the tool via the standard
 * PrimitiveTool lifecycle. When placement succeeds or is cancelled, the default
 * tool is restarted so this tool never lingers active.
 */
import {
    IModelApp,
    PrimitiveTool,
    EventHandled,
    type BeButtonEvent,
    type ScreenViewport,
} from '@itwin/core-frontend'
import { Point3d } from '@itwin/core-geometry'
import { spatialAssetStore } from './spatialAssetOverlay'

/** How the accepted world point was obtained (honest provenance for the report). */
export type WorldPointSource = 'PICK_NEAREST_VISIBLE_GEOMETRY' | 'VIEW_PLANE_PROJECTION'

let lastWorldPointSource: WorldPointSource | undefined
export function getLastWorldPointSource(): WorldPointSource | undefined {
    return lastWorldPointSource
}

export class MrtAssetPlacementTool extends PrimitiveTool {
    public static override toolId = 'MrtPharma.AssetPlacement'

    /** The connected iModel is READ-ONLY; this tool never writes to it. */
    public override requireWriteableTarget(): boolean {
        return false
    }

    public override async onPostInstall(): Promise<void> {
        await super.onPostInstall()
        // Prompt shown in the Bentley notification/prompt area.
        IModelApp.notifications.outputPromptByKey?.('MrtPharma:tools.AssetPlacement.Prompts.ClickToPlace')
    }

    /** Restart => just re-run (kept minimal; single-shot placement). */
    public override async onRestartTool(): Promise<void> {
        await this.exitTool()
    }

    /**
     * Resolve a world-space point from the button event. Prefer a point on
     * visible geometry (gives a sensible Z on the model); otherwise fall back to
     * the tool-adjusted view-plane point. No floor snapping is invented.
     */
    private resolveWorldPoint(ev: BeButtonEvent): { point: Point3d; source: WorldPointSource } {
        // pickNearestVisibleGeometry is a ScreenViewport method; ev.viewport is a
        // ScreenViewport. targetView (abstract Viewport) can't be used for it.
        const vp: ScreenViewport | undefined = ev.viewport
        if (vp) {
            const hit = vp.pickNearestVisibleGeometry(ev.point)
            if (hit) return { point: hit, source: 'PICK_NEAREST_VISIBLE_GEOMETRY' }
        }
        // ev.point is the tool-adjusted world point (view-plane projection when
        // no geometry depth is available). Honest: not floor-snapped.
        return { point: ev.point.clone(), source: 'VIEW_PLANE_PROJECTION' }
    }

    public override async onDataButtonDown(ev: BeButtonEvent): Promise<EventHandled> {
        // Guard: only act while a placement intent is active.
        if (!spatialAssetStore.isPlacementModeActive()) {
            await this.exitTool()
            return EventHandled.Yes
        }

        const { point, source } = this.resolveWorldPoint(ev)
        lastWorldPointSource = source
        if (import.meta.env.DEV) {
            console.info('[mrt-placement] WORLD_POINT_RESOLVED source=%s x=%s y=%s z=%s',
                source, point.x.toFixed(3), point.y.toFixed(3), point.z.toFixed(3))
        }

        // ONE accepted click => ONE instance (store consumes the intent once).
        const result = spatialAssetStore.completePlacementAt({ x: point.x, y: point.y, z: point.z })

        if (import.meta.env.DEV) {
            if (result.ok) {
                console.info('[mrt-placement] ASSET_INSTANCE_CREATED assetInstanceId=%s', result.instance.assetInstanceId)
                console.info('[mrt-placement] OVERLAY_INSERTION=SUCCESS')
            } else {
                console.error('[mrt-placement] PLACEMENT_FAILED reason=%s message=%s', result.reason, result.message)
            }
        }

        // Single-shot: exit the tool so it never lingers active or double-places.
        await this.exitTool()
        if (import.meta.env.DEV) console.info('[mrt-placement] PLACEMENT_MODE_EXITED reason=%s', result.ok ? 'PLACED' : result.reason)
        return EventHandled.Yes
    }

    /** Right-click / reset cancels placement. */
    public override async onResetButtonUp(_ev: BeButtonEvent): Promise<EventHandled> {
        spatialAssetStore.cancelPlacement()
        await this.exitTool()
        if (import.meta.env.DEV) console.info('[mrt-placement] PLACEMENT_MODE_EXITED reason=CANCELLED_RESET')
        return EventHandled.Yes
    }

    /** Esc (and other tool-cancel keystrokes) route through onReinitialize/exit. */
    public override async onCleanup(): Promise<void> {
        // If the tool is torn down while an intent is still active (e.g. Esc),
        // clear the intent so placement mode does not stay stuck.
        if (spatialAssetStore.isPlacementModeActive()) {
            spatialAssetStore.cancelPlacement()
            if (import.meta.env.DEV) console.info('[mrt-placement] PLACEMENT_MODE_EXITED reason=CLEANUP')
        }
        await super.onCleanup()
    }
}

let registered = false
/** Register the tool exactly once (idempotent; StrictMode-safe). */
function ensureRegistered(): void {
    if (registered) return
    // Register under a namespace; localization keys are optional for DEV.
    try {
        MrtAssetPlacementTool.register('MrtPharma')
    } catch {
        // Already registered in this session — safe to ignore.
    }
    registered = true
}

/**
 * Start the placement tool. Returns false if there is no active viewport (so the
 * caller can roll back placement mode). Uses IModelApp.tools.run so Bentley owns
 * the input lifecycle — no raw DOM listeners.
 */
export async function runMrtAssetPlacementTool(): Promise<boolean> {
    ensureRegistered()
    const vp = IModelApp.viewManager?.selectedView
    if (!vp) return false
    return IModelApp.tools.run(MrtAssetPlacementTool.toolId)
}

/** Exit the placement tool if it is the active tool (idempotent). */
export async function exitMrtAssetPlacementTool(): Promise<void> {
    const active = IModelApp.toolAdmin?.activeTool
    if (active instanceof MrtAssetPlacementTool) {
        await active.exitTool()
    }
}
