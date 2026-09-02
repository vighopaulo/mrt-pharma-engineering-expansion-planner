/**
 * MrtAssetMoveTool — bounded Bentley PrimitiveTool for controlled one-shot MOVE
 * of an existing MRT Pharma spatial asset.
 *
 * Mirrors the proven MrtAssetPlacementTool input pattern: it consumes the
 * already-active MoveIntent held by the application-owned SpatialAssetStore,
 * converts exactly ONE accepted data-button click into a world-space point,
 * asks the store to complete the move (updating ONLY the bound instance's
 * position — identity and rotation preserved), then exits. It never queries the
 * catalog and never creates an instance.
 *
 * READ-ONLY: requireWriteableTarget()=false; no iModel writes, no changeset.
 * Cancellation via reset button / Esc through the standard PrimitiveTool
 * lifecycle. The move is bound to the intent's assetInstanceId, so a UI
 * selection change while the tool is active cannot retarget the move.
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
import type { WorldPointSource } from './MrtAssetPlacementTool'

let lastMoveWorldPointSource: WorldPointSource | undefined
export function getLastMoveWorldPointSource(): WorldPointSource | undefined {
    return lastMoveWorldPointSource
}

export class MrtAssetMoveTool extends PrimitiveTool {
    public static override toolId = 'MrtPharma.AssetMove'

    public override requireWriteableTarget(): boolean {
        return false
    }

    public override async onPostInstall(): Promise<void> {
        await super.onPostInstall()
        IModelApp.notifications.outputPromptByKey?.('MrtPharma:tools.AssetMove.Prompts.ClickNewLocation')
    }

    public override async onRestartTool(): Promise<void> {
        await this.exitTool()
    }

    private resolveWorldPoint(ev: BeButtonEvent): { point: Point3d; source: WorldPointSource } {
        const vp: ScreenViewport | undefined = ev.viewport
        if (vp) {
            const hit = vp.pickNearestVisibleGeometry(ev.point)
            if (hit) return { point: hit, source: 'PICK_NEAREST_VISIBLE_GEOMETRY' }
        }
        return { point: ev.point.clone(), source: 'VIEW_PLANE_PROJECTION' }
    }

    public override async onDataButtonDown(ev: BeButtonEvent): Promise<EventHandled> {
        if (!spatialAssetStore.isMoveModeActive()) {
            await this.exitTool()
            return EventHandled.Yes
        }

        const { point, source } = this.resolveWorldPoint(ev)
        lastMoveWorldPointSource = source
        if (import.meta.env.DEV) {
            console.info('[mrt-move] MOVE_WORLD_POINT_RESOLVED source=%s x=%s y=%s z=%s',
                source, point.x.toFixed(3), point.y.toFixed(3), point.z.toFixed(3))
        }

        const result = spatialAssetStore.completeMoveAt({ x: point.x, y: point.y, z: point.z })
        if (import.meta.env.DEV) {
            if (result.ok) {
                console.info('[mrt-move] ASSET_MOVED assetInstanceId=%s', result.instance.assetInstanceId)
            } else {
                console.error('[mrt-move] MOVE_FAILED reason=%s message=%s', result.reason, result.message)
            }
        }

        await this.exitTool()
        if (import.meta.env.DEV) console.info('[mrt-move] MOVE_MODE_EXITED reason=%s', result.ok ? 'MOVED' : result.reason)
        return EventHandled.Yes
    }

    public override async onResetButtonUp(_ev: BeButtonEvent): Promise<EventHandled> {
        spatialAssetStore.cancelMove()
        await this.exitTool()
        if (import.meta.env.DEV) console.info('[mrt-move] MOVE_MODE_EXITED reason=CANCELLED_RESET')
        return EventHandled.Yes
    }

    public override async onCleanup(): Promise<void> {
        if (spatialAssetStore.isMoveModeActive()) {
            spatialAssetStore.cancelMove()
            if (import.meta.env.DEV) console.info('[mrt-move] MOVE_MODE_EXITED reason=CLEANUP')
        }
        await super.onCleanup()
    }
}

let registered = false
function ensureRegistered(): void {
    if (registered) return
    try {
        MrtAssetMoveTool.register('MrtPharma')
    } catch {
        // Already registered in this session — safe to ignore.
    }
    registered = true
}

/** Start the move tool. Returns false if there is no active viewport. */
export async function runMrtAssetMoveTool(): Promise<boolean> {
    ensureRegistered()
    const vp = IModelApp.viewManager?.selectedView
    if (!vp) return false
    return IModelApp.tools.run(MrtAssetMoveTool.toolId)
}

/** Exit the move tool if it is the active tool (idempotent). */
export async function exitMrtAssetMoveTool(): Promise<void> {
    const active = IModelApp.toolAdmin?.activeTool
    if (active instanceof MrtAssetMoveTool) {
        await active.exitTool()
    }
}
