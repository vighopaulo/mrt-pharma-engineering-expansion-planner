/**
 * ViewerAssetContextMenu — compact right-click context menu for an
 * application-owned MRT AssetInstance. Opened by the direct-manipulation tool
 * (which resolves the concrete assetInstanceId + screen position); this
 * component only renders the menu and dispatches actions through the existing
 * overlay product API. It is UI-only, non-authoritative state.
 *
 * Actions: unselected target -> SELECT + DELETE; selected target -> DESELECT +
 * DELETE. DELETE reuses the existing controlled delete (confirmation + guard).
 * The menu auto-closes when its target no longer exists (stale), on action, on
 * empty-space click (handled by the tool), or on Esc.
 */
import { useEffect, useSyncExternalStore } from 'react'
import type { SpatialAssetSnapshot } from '../../domain/assets'
import {
    clearSelection,
    closeAssetContextMenu,
    deleteAsset,
    deselectAsset,
    getContextMenu,
    selectAsset,
    spatialAssetStore,
    subscribeContextMenu,
    subscribeSpatialAssets,
} from './spatialAssetOverlay'

export function ViewerAssetContextMenu() {
    const menu = useSyncExternalStore(subscribeContextMenu, getContextMenu)
    const snapshot = useSyncExternalStore(subscribeSpatialAssets, () => spatialAssetStore.getSnapshot()) as SpatialAssetSnapshot

    // Auto-close if the target instance no longer exists (deleted / project change).
    const targetExists = !!menu && snapshot.instances.some((i) => i.assetInstanceId === menu.assetInstanceId)
    useEffect(() => {
        if (menu && !targetExists) closeAssetContextMenu()
    }, [menu, targetExists])

    if (!menu || !targetExists) return null

    const isSelected = snapshot.selectedAssetInstanceIds.includes(menu.assetInstanceId)
    const targetId = menu.assetInstanceId

    const onSelectOrDeselect = () => {
        if (isSelected) deselectAsset(targetId)
        else selectAsset(targetId) // REPLACE selection with the target
        closeAssetContextMenu()
    }
    const onDelete = () => {
        // Reuse the existing controlled delete (confirmation + USER_PLACED guard).
        closeAssetContextMenu()
        const inst = snapshot.instances.find((i) => i.assetInstanceId === targetId)
        const label = inst?.displayLabel ?? targetId
        if (!window.confirm(`Delete ${label}? This removes the placed asset instance only.`)) return
        const res = deleteAsset(targetId)
        if (!res.ok && import.meta.env.DEV) console.info('[context-menu] delete rejected: %s', res.reason)
    }

    return (
        <div
            className="mrt-context-menu"
            role="menu"
            style={{ left: menu.screenX, top: menu.screenY }}
            // Prevent the browser context menu on the menu itself.
            onContextMenu={(e) => e.preventDefault()}
        >
            <button type="button" role="menuitem" onClick={onSelectOrDeselect}>
                {isSelected ? 'Deselect' : 'Select'}
            </button>
            <button type="button" role="menuitem" className="mrt-context-delete" onClick={onDelete}>
                Delete
            </button>
        </div>
    )
}

/** Empty-space handler consumers may call to dismiss + clear (kept for symmetry). */
export function dismissContextAndSelection() {
    closeAssetContextMenu()
    clearSelection()
}
