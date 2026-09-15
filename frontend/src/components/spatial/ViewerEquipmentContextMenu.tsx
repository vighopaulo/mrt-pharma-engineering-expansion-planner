/**
 * ViewerEquipmentContextMenu — compact right-click context menu for an
 * application-owned MRT EquipmentAssetInstance (cyclotron / PET-CT / hot-cell).
 *
 * Opened by the direct-manipulation tool, which resolves the exact
 * equipmentInstanceId (from the pickable decoration id — NEVER the model name)
 * and the screen position. This component only renders the menu and dispatches
 * through the existing overlay equipment API. It is UI-only, non-authoritative
 * state; the single selection authority remains `selectedEquipmentId`.
 *
 * Commands: Fit to Equipment · Lock/Unlock · Hide · Delete. All operate on the
 * ONE EquipmentAssetInstance by its stable id. Delete reuses the authoritative
 * deleteEquipment lifecycle (the SAME one the equipment card uses). The menu
 * auto-closes when its target no longer exists (deleted / project change), on a
 * command, on Escape (tool), on click elsewhere (tool), or when another
 * instance becomes selected.
 */
import { useEffect, useState, useSyncExternalStore } from 'react'
import {
    closeEquipmentContextMenu,
    deleteEquipment,
    fitViewToEquipment,
    getEquipmentContextMenu,
    getEquipmentInstances,
    getSelectedEquipmentId,
    lockEquipment,
    setEquipmentVisibility,
    subscribeClinicalProgram,
    subscribeEquipmentContextMenu,
    unlockEquipment,
} from './spatialAssetOverlay'
import { canonicalEquipmentById } from './canonicalEquipmentCatalog'

export function ViewerEquipmentContextMenu() {
    const menu = useSyncExternalStore(subscribeEquipmentContextMenu, getEquipmentContextMenu)
    // Re-render on any equipment/program change so a deleted target auto-closes
    // and lock/hide labels stay current.
    const programTick = useSyncExternalStore(subscribeClinicalProgram, getSelectedEquipmentId)

    const instances = getEquipmentInstances()
    const target = menu ? instances.find((e) => e.id === menu.equipmentInstanceId) : undefined

    // Auto-close if the target instance no longer exists (deleted / project change),
    // or if another instance became the selected one (select-other dismissal).
    useEffect(() => {
        if (!menu) return
        if (!target) { closeEquipmentContextMenu(); return }
        if (programTick && programTick !== menu.equipmentInstanceId) closeEquipmentContextMenu()
    }, [menu, target, programTick])

    if (!menu || !target) return null

    const isLocked = target.lifecycleState === 'LOCKED'
    const id = target.id
    // Title = the EXACT canonical model (manufacturer + model), never a generic
    // family. Falls back to the instance display label only if the canonical
    // model cannot be resolved (should not happen for a valid instance).
    const canonical = canonicalEquipmentById(target.canonicalEquipmentId)
    const title = canonical ? `${canonical.manufacturer} ${canonical.model}` : target.displayLabel

    const onFit = () => {
        closeEquipmentContextMenu()
        void fitViewToEquipment(id)
    }
    const onLockToggle = () => {
        closeEquipmentContextMenu()
        if (isLocked) unlockEquipment(id)
        else void lockEquipment(id)
    }
    const isHidden = target.hidden ?? false
    const onHideToggle = () => {
        closeEquipmentContextMenu()
        // hidden===false -> Hide (setVisibility false); hidden===true -> Show
        // (setVisibility true). One authoritative field; never traps hidden eqpt.
        setEquipmentVisibility(id, isHidden)
    }
    const [error, setError] = useState<string | null>(null)
    const onDelete = () => {
        // EVI-MA-02C — call the authoritative delete FIRST and process its
        // result. Do NOT gate on window.confirm: it is blocked (returns false)
        // in the embedded viewer host, which is exactly why Delete silently did
        // nothing while Hide (no confirm) worked. Same lifecycle as the card /
        // keyboard Delete. On success the menu closes (deleteEquipment also
        // clears the menu when its target is deleted); on failure keep the menu
        // open and show the returned reason.
        const res = deleteEquipment(id)
        if (res.ok) {
            closeEquipmentContextMenu()
            return
        }
        setError(res.message)
        if (import.meta.env.DEV) console.info('[equipment-context-menu] delete rejected: %s', res.reason)
    }

    return (
        <div
            className="mrt-context-menu mrt-equipment-context-menu"
            role="menu"
            style={{ left: menu.screenX, top: menu.screenY }}
            onContextMenu={(e) => e.preventDefault()}
        >
            <div className="mrt-context-menu-title" role="presentation">{title}</div>
            <button type="button" role="menuitem" onClick={onFit}>Fit to Equipment</button>
            <button type="button" role="menuitem" onClick={onLockToggle}>{isLocked ? 'Unlock' : 'Lock'}</button>
            <button type="button" role="menuitem" onClick={onHideToggle}>{isHidden ? 'Show' : 'Hide'}</button>
            <button
                type="button"
                role="menuitem"
                className="mrt-context-delete"
                onClick={onDelete}
                disabled={isLocked}
                title={isLocked ? 'Unlock before deleting' : 'Delete this equipment (BIM room kept)'}
            >
                Delete
            </button>
            {error && <div className="mrt-context-menu-error" role="alert">{error}</div>}
        </div>
    )
}
