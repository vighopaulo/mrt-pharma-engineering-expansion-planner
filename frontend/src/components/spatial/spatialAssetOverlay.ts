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
    buildGeDiscoveryMiCatalogTestAsset,
    buildGenericPetCtTestAsset,
    CATALOG_TEST_ASSET_INSTANCE_ID,
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
    if (decorator && removeDecorator) return
    if (!decorator) {
        decorator = new SpatialAssetDecorator(() => instances.filter((i) => i.projectId === activeProjectId))
    }
    removeDecorator = IModelApp.viewManager.addDecorator(decorator)
}

/**
 * Detach the decorator from the viewManager (Bentley cleanup on viewer unmount).
 *
 * IMPORTANT: this does NOT clear the application-owned `instances` state. The
 * decorator is a rendering attachment; the overlay's domain state is authoritative
 * and must survive a transient detach/re-attach (e.g. React StrictMode
 * mount→cleanup→mount, or a viewer remount). Previously this wiped `instances`,
 * so an asset shown before a remount vanished from overlay state — which is the
 * proven cause of NO_CATALOG_ASSET_PLACED. Re-registration reuses the same
 * decorator + the retained instances.
 */
export function disposeOverlay(): void {
    if (removeDecorator) removeDecorator()
    removeDecorator = undefined
    // Keep `decorator` and `instances` so re-registration restores the overlay.
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

/** Build + show the catalog-backed GE Discovery MI PET/CT proof asset. */
export function showCatalogPetCt(): ShowResult {
    ensureDecoratorRegistered()
    const neigh = currentNeighborhood()
    if (!neigh) return { ok: false, reason: 'NO_ACTIVE_VIEWPORT_OR_RANGE' }

    const before = instances.length
    const { result } = buildGeDiscoveryMiCatalogTestAsset(neigh)
    if (!result.ok) {
        if (import.meta.env.DEV) {
            console.error('[catalog-asset] FAILURE_STAGE=build FAILURE_CODE=%s message=%s', result.reason, result.message)
        }
        return { ok: false, reason: `${result.reason}: ${result.message}` }
    }

    // Dedupe by assetInstanceId ONLY (never by geometry/definition/family) so the
    // generic and catalog scanners coexist despite sharing GENERIC_PET_CT_SCANNER_V1.
    instances = instances.filter((i) => i.assetInstanceId !== result.instance.assetInstanceId)
    instances.push(result.instance)
    invalidateDecorations()

    const present = instances.some((i) => i.assetInstanceId === result.instance.assetInstanceId)
    if (import.meta.env.DEV) {
        console.info('[catalog-asset] CATALOG_RECORD_FOUND=YES CATALOG_RECORD_ID=GE_DISCOVERY_MI ADAPTER_RESULT=SUCCESS ASSET_DEFINITION_ID=%s ASSET_FAMILY=%s GEOMETRY_RESOLUTION=%s DIMENSION_PROVENANCE=%s INSTANCE_CREATION=SUCCESS INSTANCE_ID=%s OVERLAY_INSTANCE_COUNT_BEFORE=%d OVERLAY_INSTANCE_COUNT_AFTER=%d OVERLAY_INSERTION=%s',
            result.instance.assetDefinitionId, result.definition.assetFamily, result.instance.geometryRepresentationId,
            result.instance.dimensions.provenance, result.instance.assetInstanceId, before, instances.length, present ? 'SUCCESS' : 'FAILED')
    }
    return { ok: true, reason: 'SHOWN', instanceId: result.instance.assetInstanceId, serialized: serializeAssetInstance(result.instance) }
}

/** Remove the catalog-backed instance only. */
export function hideCatalogPetCt(): void {
    instances = instances.filter((i) => i.assetInstanceId !== CATALOG_TEST_ASSET_INSTANCE_ID)
    invalidateDecorations()
    if (import.meta.env.DEV) console.info('[bentley-asset] HIDE_CATALOG')
}

/** Sanitized metadata for the catalog-backed instance. */
export function inspectCatalogPetCt(): string {
    const inst = instances.find((i) => i.assetInstanceId === CATALOG_TEST_ASSET_INSTANCE_ID)
    if (!inst) return 'NO_CATALOG_ASSET_PLACED'
    const summary = [
        `assetInstanceId=${inst.assetInstanceId}`,
        `displayLabel=${inst.displayLabel}`,
        `assetDefinitionId=${inst.assetDefinitionId}`,
        `geometryRepresentationId=${inst.geometryRepresentationId}`,
        `createdFrom=${inst.createdFrom ?? '—'}`,
        `dims=${inst.dimensions.width}x${inst.dimensions.depth}x${inst.dimensions.height}${inst.dimensions.unit}`,
        `dimProvenance=${inst.dimensions.provenance}`,
        `pos=(${inst.transform.position.x.toFixed(2)},${inst.transform.position.y.toFixed(2)},${inst.transform.position.z.toFixed(2)})`,
        `room=${inst.roomAssignment.state}`,
        `state=${inst.installationState}`,
        `source=${inst.spatialSource}`,
    ].join(' | ')
    if (import.meta.env.DEV) console.info('[bentley-asset] INSPECT_CATALOG %s', summary)
    return summary
}

/** Remove all overlay instances (hide). */
export function hideGenericPetCt(): void {
    instances = instances.filter((i) => i.assetInstanceId !== 'PETCT-TEST-01')
    invalidateDecorations()
    if (import.meta.env.DEV) console.info('[bentley-asset] HIDE')
}

/** Return sanitized metadata for the current proof instance (inspection). */
export function inspectGenericPetCt(): string {
    const inst = instances.find((i) => i.assetInstanceId === 'PETCT-TEST-01') ?? instances[0]
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
