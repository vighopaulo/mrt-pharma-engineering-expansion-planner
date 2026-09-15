/**
 * ViewerAppObjectMenu — EVI-MA-07 the ONE local action popover for the currently
 * SELECTED application object (scanner / cyclotron / vestibule). It replaces the
 * family-specific floating controls' ambiguity with a single menu that:
 *   - belongs to the ONE authoritative SelectedAppObject (never hover);
 *   - is anchored NEAR the object (the click/right-click point);
 *   - dispatches every action against the CAPTURED {objectType, instanceId} —
 *     it NEVER re-raycasts, so moving the cursor to a button cannot retarget it;
 *   - stops event propagation so clicking a button never reaches the viewport
 *     (the root cause of "click Hide → hides the object behind the button");
 *   - records Undo for Delete/Hide/Show/Lock/Unlock and shows an Undo toast on
 *     Delete (no browser alert).
 * Left-click selection AND right-click both open this same menu (right-click
 * only changes the anchor). It stays visible while the object stays selected.
 */
import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import {
    subscribeClinicalProgram,
    getSelectedAppObjectView,
    getSelectedAppObjectAnchor,
    deleteCapturedAppObject,
    setCapturedAppObjectVisibility,
    setCapturedAppObjectLock,
    fitCapturedAppObject,
    undoLastAppEdit,
    type SelectedAppObjectView,
} from './spatialAssetOverlay'

/** Composite snapshot so the menu re-renders on selection/hidden/lock/anchor change. */
function menuSnapshot(): string {
    const v = getSelectedAppObjectView()
    const a = getSelectedAppObjectAnchor()
    if (!v) return ''
    return `${v.objectType}|${v.instanceId}|${v.hidden ? 'h' : 'v'}|${v.locked ? 'l' : 'u'}|${a ? `${a.x},${a.y}` : ''}`
}

interface DeleteToast { label: string }

export function ViewerAppObjectMenu() {
    useSyncExternalStore(subscribeClinicalProgram, menuSnapshot)
    const view = getSelectedAppObjectView()
    const anchor = getSelectedAppObjectAnchor()
    const [toast, setToast] = useState<DeleteToast | null>(null)
    const toastTimer = useRef<number | undefined>(undefined)

    useEffect(() => () => { if (toastTimer.current) window.clearTimeout(toastTimer.current) }, [])

    if (!view) return null

    // CAPTURE the target for THIS render's handlers. Actions close over this
    // exact {objectType, instanceId} — never a fresh raycast.
    const target = { objectType: view.objectType, instanceId: view.instanceId }
    const v: SelectedAppObjectView = view

    // Anchor the popover near the object; clamp within the viewport.
    const left = anchor ? Math.min(Math.max(anchor.x + 12, 8), window.innerWidth - 240) : 16
    const top = anchor ? Math.min(Math.max(anchor.y - 8, 8), window.innerHeight - 140) : 16

    // Stop propagation so a button click never reaches the Bentley viewport.
    const swallow = (e: React.SyntheticEvent) => { e.stopPropagation() }

    const onFit = (e: React.MouseEvent) => { swallow(e); void fitCapturedAppObject(target) }
    const onHideToggle = (e: React.MouseEvent) => { swallow(e); setCapturedAppObjectVisibility(target, v.hidden) }
    const onLockToggle = (e: React.MouseEvent) => { swallow(e); void setCapturedAppObjectLock(target, !v.locked) }
    const onDelete = (e: React.MouseEvent) => {
        swallow(e)
        if (v.locked) return
        const res = deleteCapturedAppObject(target)
        if (res.ok) {
            setToast({ label: `${v.title} deleted` })
            if (toastTimer.current) window.clearTimeout(toastTimer.current)
            toastTimer.current = window.setTimeout(() => setToast(null), 8000)
        }
    }
    const onToastUndo = (e: React.MouseEvent) => { swallow(e); undoLastAppEdit(); setToast(null) }

    return (
        <>
            <div
                className="mrt-appobject-menu"
                role="menu"
                aria-label="Selected object actions"
                style={{ left, top }}
                onPointerDown={swallow}
                onMouseDown={swallow}
                onClick={swallow}
                onContextMenu={(e) => e.preventDefault()}
            >
                <div className="mrt-appobject-menu-title">{v.title}{v.hidden ? ' · Hidden' : ''}{v.locked ? ' · Locked' : ''}</div>
                <div className="mrt-appobject-menu-actions">
                    <button type="button" role="menuitem" onClick={onFit}>{v.fitLabel}</button>
                    <button type="button" role="menuitem" onClick={onHideToggle}>{v.hidden ? 'Show' : 'Hide'}</button>
                    <button type="button" role="menuitem" onClick={onLockToggle}>{v.locked ? 'Unlock' : 'Lock'}</button>
                    <button
                        type="button"
                        role="menuitem"
                        className="mrt-appobject-menu-delete"
                        disabled={v.locked}
                        title={v.locked ? 'Unlock before deleting' : 'Delete this object'}
                        onClick={onDelete}
                    >
                        Delete
                    </button>
                </div>
            </div>
            {toast && (
                <div className="mrt-delete-toast" role="status" onPointerDown={swallow} onClick={swallow}>
                    <span>{toast.label}</span>
                    <button type="button" onClick={onToastUndo}>Undo</button>
                </div>
            )}
        </>
    )
}
