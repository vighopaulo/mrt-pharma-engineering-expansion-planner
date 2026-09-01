/**
 * spatialAssetOverlay — bounded controller that owns the MRT Pharma spatial
 * asset overlay lifecycle inside the live Bentley viewport.
 *
 * Responsibilities:
 *  - hold the current project-scoped AssetInstance[] (domain state);
 *  - register exactly ONE SpatialAssetDecorator with the viewManager;
 *  - build the generic PET/CT proof instance from the live model range;
 *  - show / hide / inspect for the DEV control.
 *
 * It does NOT modify the iModel, ViewFlags, camera, or transparency. The
 * decorator uses cached decorations, so nothing churns while idle. The overlay
 * is project-scoped: instances carry projectId and are only drawn for the
 * active dev-viewer project.
 */
import { IModelApp } from '@itwin/core-frontend'
import { SpatialAssetDecorator } from './SpatialAssetDecorator'
import {
    buildGenericPetCtTestAsset,
    serializeAssetInstance,
    TEST_PROJECT_ID,
    type AssetInstance,
    type ModelNeighborhood,
} from '../../domain/assets'

let instances: AssetInstance[] = []
let decorator: SpatialAssetDecorator | undefined
let removeDecorator: (() => void) | undefined
const activeProjectId = TEST_PROJECT_ID

/** Register the decorator once. Safe to call repeatedly (idempotent). */
export function ensureDecoratorRegistered(): void {
    if (decorator) return
    decorator = new SpatialAssetDecorator(() => instances.filter((i) => i.projectId === activeProjectId))
    removeDecorator = IModelApp.viewManager.addDecorator(decorator)
}

/** Remove the decorator + clear overlay state (call on viewer unmount). */
export function disposeOverlay(): void {
    if (removeDecorator) removeDecorator()
    removeDecorator = undefined
    decorator = undefined
    instances = []
}

function invalidateDecorations(): void {
    const vp = IModelApp.viewManager?.selectedView
    // Cached decorations must be invalidated when the instance set changes.
    vp?.invalidateCachedDecorations(decorator!)
}

/** Read the current model neighborhood (center + diagonal) from the live view. */
function currentNeighborhood(): ModelNeighborhood | undefined {
    const vp = IModelApp.viewManager?.selectedView
    if (!vp) return undefined
    const range = vp.view.computeFitRange()
    if (range.isNull) return undefined
    const c = range.center
    return { center: { x: c.x, y: c.y, z: c.z }, diagonal: range.diagonal().magnitude() }
}

export interface ShowResult {
    ok: boolean
    reason: string
    instanceId?: string
    serialized?: unknown
}

/** Build + show the ONE generic PET/CT proof asset near the model center. */
export function showGenericPetCt(): ShowResult {
    ensureDecoratorRegistered()
    const neigh = currentNeighborhood()
    if (!neigh) return { ok: false, reason: 'NO_ACTIVE_VIEWPORT_OR_RANGE' }

    const { result } = buildGenericPetCtTestAsset(neigh)
    if (!result.ok) {
        return { ok: false, reason: 'BUILD_FAILED: ' + result.errors.map((e) => `${e.field} ${e.message}`).join('; ') }
    }
    // Replace any existing instance with the same id (idempotent show).
    instances = instances.filter((i) => i.assetInstanceId !== result.instance.assetInstanceId)
    instances.push(result.instance)
    invalidateDecorations()

    if (import.meta.env.DEV) {
        console.info('[bentley-asset] SHOW instanceId=%s def=%s geo=%s label=%s pos=(%s,%s,%s)',
            result.instance.assetInstanceId, result.instance.assetDefinitionId, result.instance.geometryRepresentationId,
            result.instance.displayLabel,
            result.instance.transform.position.x.toFixed(2), result.instance.transform.position.y.toFixed(2),
            result.instance.transform.position.z.toFixed(2))
    }
    return { ok: true, reason: 'SHOWN', instanceId: result.instance.assetInstanceId, serialized: serializeAssetInstance(result.instance) }
}

/** Remove all overlay instances (hide). */
export function hideGenericPetCt(): void {
    instances = []
    invalidateDecorations()
    if (import.meta.env.DEV) console.info('[bentley-asset] HIDE')
}

/** Return sanitized metadata for the current proof instance (inspection). */
export function inspectGenericPetCt(): string {
    const inst = instances[0]
    if (!inst) return 'NO_ASSET_PLACED'
    const summary = [
        `assetInstanceId=${inst.assetInstanceId}`,
        `displayLabel=${inst.displayLabel}`,
        `assetDefinitionId=${inst.assetDefinitionId}`,
        `geometryRepresentationId=${inst.geometryRepresentationId}`,
        `dims=${inst.dimensions.width}x${inst.dimensions.depth}x${inst.dimensions.height}${inst.dimensions.unit}`,
        `pos=(${inst.transform.position.x.toFixed(2)},${inst.transform.position.y.toFixed(2)},${inst.transform.position.z.toFixed(2)})`,
        `room=${inst.roomAssignment.state}`,
        `state=${inst.installationState}`,
        `source=${inst.spatialSource}`,
    ].join(' | ')
    if (import.meta.env.DEV) console.info('[bentley-asset] INSPECT %s', summary)
    return summary
}
