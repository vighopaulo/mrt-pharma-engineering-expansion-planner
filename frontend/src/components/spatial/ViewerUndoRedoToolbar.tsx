/**
 * ViewerUndoRedoToolbar — EVI-MA-07 visible Undo / Redo controls + keyboard
 * shortcuts (Ctrl/Cmd+Z undo, Ctrl/Cmd+Shift+Z redo) for the application-owned
 * edit history. Buttons are disabled when the respective stack is empty. Undo/
 * Redo apply ONLY app-owned object state (never Bentley/BIM/camera). The
 * keyboard listener ignores keystrokes while focus is in a text field.
 */
import { useEffect, useSyncExternalStore } from 'react'
import {
    subscribeAppHistory,
    getAppHistoryCounts,
    canUndoAppEdit,
    canRedoAppEdit,
    undoLastAppEdit,
    redoLastAppEdit,
} from './spatialAssetOverlay'
import { isTextEditingElement } from './appObjectPicking'

function historySnapshot(): string {
    const c = getAppHistoryCounts()
    return `${c.undo}|${c.redo}`
}

export function ViewerUndoRedoToolbar() {
    useSyncExternalStore(subscribeAppHistory, historySnapshot)

    useEffect(() => {
        const onKey = (e: KeyboardEvent) => {
            if (!(e.metaKey || e.ctrlKey)) return
            if (e.key !== 'z' && e.key !== 'Z') return
            if (isTextEditingElement(document.activeElement as { tagName?: string; isContentEditable?: boolean } | null)) return
            e.preventDefault()
            if (e.shiftKey) redoLastAppEdit()
            else undoLastAppEdit()
        }
        window.addEventListener('keydown', onKey)
        return () => window.removeEventListener('keydown', onKey)
    }, [])

    const undoEnabled = canUndoAppEdit()
    const redoEnabled = canRedoAppEdit()

    return (
        <div className="mrt-undo-redo-toolbar" role="toolbar" aria-label="Undo and redo">
            <button type="button" onClick={() => undoLastAppEdit()} disabled={!undoEnabled} title="Undo (Ctrl/Cmd+Z)">↶ Undo</button>
            <button type="button" onClick={() => redoLastAppEdit()} disabled={!redoEnabled} title="Redo (Ctrl/Cmd+Shift+Z)">↷ Redo</button>
        </div>
    )
}
