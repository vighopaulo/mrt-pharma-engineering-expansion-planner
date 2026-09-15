/**
 * ViewerVestibuleContextMenu — EVI-MA-05B compact right-click context menu for
 * an application-owned CLINICAL LOGISTICS VESTIBULE. Mirrors the equipment
 * context menu exactly (same interaction pattern) so right-click is a UNIVERSAL
 * property of application-owned assets. Opened by the direct-manipulation tool
 * which resolves the exact vestibuleInstanceId from the pickable decoration id.
 * UI-only; the single selection authority remains `selectedVestibuleId`, and all
 * commands dispatch to the SAME overlay vestibule lifecycle functions.
 *
 * Commands: Fit to Vestibule · Lock/Unlock · Hide/Show · Delete. Delete uses the
 * authoritative deleteVestibule lifecycle (no window.confirm — proven to fail in
 * the viewer host). Locked ⇒ Delete disabled + Unlock available (never a silent
 * no-op Delete).
 */
import { useEffect, useState, useSyncExternalStore } from 'react'
import {
    closeVestibuleContextMenu,
    deleteVestibule,
    fitViewToVestibule,
    getVestibuleContextMenu,
    getVestibuleInstances,
    getSelectedVestibuleId,
    lockVestibule,
    setVestibuleVisibility,
    subscribeClinicalProgram,
    subscribeVestibuleContextMenu,
    unlockVestibule,
} from './spatialAssetOverlay'
import { serviceClassLabel } from './clinicalLogisticsVestibule'

export function ViewerVestibuleContextMenu() {
    const menu = useSyncExternalStore(subscribeVestibuleContextMenu, getVestibuleContextMenu)
    // Re-render on any vestibule/program change so a deleted target auto-closes
    // and lock/hide labels stay current.
    const selectedTick = useSyncExternalStore(subscribeClinicalProgram, getSelectedVestibuleId)

    const instances = getVestibuleInstances()
    const target = menu ? instances.find((v) => v.vestibuleInstanceId === menu.vestibuleInstanceId) : undefined

    useEffect(() => {
        if (!menu) return
        if (!target) { closeVestibuleContextMenu(); return }
        if (selectedTick && selectedTick !== menu.vestibuleInstanceId) closeVestibuleContextMenu()
    }, [menu, target, selectedTick])

    const [error, setError] = useState<string | null>(null)

    if (!menu || !target) return null

    const isLocked = target.lifecycleState === 'LOCKED'
    const isHidden = target.hidden ?? false
    const id = target.vestibuleInstanceId
    const title = `${serviceClassLabel(target.serviceClass)} Logistics Vestibule`

    const onFit = () => { closeVestibuleContextMenu(); void fitViewToVestibule(id) }
    const onLockToggle = () => { closeVestibuleContextMenu(); if (isLocked) unlockVestibule(id); else lockVestibule(id) }
    const onHideToggle = () => { closeVestibuleContextMenu(); setVestibuleVisibility(id, isHidden) }
    const onDelete = () => {
        const res = deleteVestibule(id)
        if (res.ok) { closeVestibuleContextMenu(); return }
        setError(res.message)
        if (import.meta.env.DEV) console.info('[vestibule-context-menu] delete rejected: %s', res.reason)
    }

    return (
        <div
            className="mrt-context-menu mrt-vestibule-context-menu"
            role="menu"
            style={{ left: menu.screenX, top: menu.screenY }}
            onContextMenu={(e) => e.preventDefault()}
        >
            <div className="mrt-context-menu-title" role="presentation">{title}</div>
            <button type="button" role="menuitem" onClick={onFit}>Fit to Vestibule</button>
            <button type="button" role="menuitem" onClick={onLockToggle}>{isLocked ? 'Unlock' : 'Lock'}</button>
            <button type="button" role="menuitem" onClick={onHideToggle}>{isHidden ? 'Show' : 'Hide'}</button>
            <button
                type="button"
                role="menuitem"
                className="mrt-context-delete"
                onClick={onDelete}
                disabled={isLocked}
                title={isLocked ? 'Unlock before deleting' : 'Delete this vestibule (cyclotron + BIM wall kept)'}
            >
                Delete
            </button>
            {error && <div className="mrt-context-menu-error" role="alert">{error}</div>}
        </div>
    )
}
