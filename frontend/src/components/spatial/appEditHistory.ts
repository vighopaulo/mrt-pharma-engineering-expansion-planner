/**
 * appEditHistory — EVI-MA-07 bounded, application-owned Undo/Redo command stack.
 *
 * A real spatial engineering editor must provide Undo. This is a pure command/
 * history model over APPLICATION-OWNED state only. It NEVER snapshots the Bentley
 * iModel, camera, or native BIM geometry — only app-owned object state
 * (equipment placement, vestibule pose/hidden/lock, delete/restore payloads).
 *
 * The store injects `apply(command, direction)` handlers; this module owns only
 * the stack discipline (push, undo, redo, bound, clear) and is unit-testable in
 * isolation. Records carry a `beforeState`/`afterState` so undo/redo are exact
 * inverses and a restored DELETE reuses the SAME instance id (never a new id).
 */

export type AppEditCommandType =
    | 'DELETE'
    | 'HIDE'
    | 'SHOW'
    | 'MOVE'
    | 'ROTATE'
    | 'LOCK'
    | 'UNLOCK'

export type AppEditObjectType = 'ASSET_INSTANCE' | 'EQUIPMENT_INSTANCE' | 'CLINICAL_LOGISTICS_VESTIBULE'

/**
 * One reversible application-object edit. `beforeState`/`afterState` are opaque,
 * serializable app-owned payloads the store's apply-handler understands (e.g. a
 * full instance snapshot for DELETE, a placement/pose for MOVE). Never BIM.
 */
export interface AppEditCommand {
    type: AppEditCommandType
    objectType: AppEditObjectType
    instanceId: string
    beforeState: unknown
    afterState: unknown
    timestamp: number
    /** Optional human label for a toast ("IBA Cyclone KIUBE deleted — Undo"). */
    label?: string
}

/** Max retained commands (bounded so history never grows without limit). */
export const APP_EDIT_HISTORY_LIMIT = 100

/**
 * A pure history stack. `undo`/`redo` return the command to reverse/replay; the
 * caller applies it (direction-aware) against the authoritative store. Recording
 * a new command clears the redo stack (standard linear-history semantics).
 */
export class AppEditHistory {
    private undoStack: AppEditCommand[] = []
    private redoStack: AppEditCommand[] = []
    private readonly limit: number
    constructor(limit: number = APP_EDIT_HISTORY_LIMIT) { this.limit = Math.max(1, limit) }

    /** Record a newly-performed command (clears redo). */
    record(command: AppEditCommand): void {
        this.undoStack.push(command)
        if (this.undoStack.length > this.limit) this.undoStack.shift()
        this.redoStack = []
    }

    canUndo(): boolean { return this.undoStack.length > 0 }
    canRedo(): boolean { return this.redoStack.length > 0 }

    /** Peek the command that undo would reverse (without popping). */
    peekUndo(): AppEditCommand | undefined { return this.undoStack[this.undoStack.length - 1] }
    peekRedo(): AppEditCommand | undefined { return this.redoStack[this.redoStack.length - 1] }

    /**
     * Pop the top undo command and move it to the redo stack. Returns the command
     * so the caller can apply its `beforeState` (reverse). Undefined when empty.
     */
    popUndo(): AppEditCommand | undefined {
        const c = this.undoStack.pop()
        if (!c) return undefined
        this.redoStack.push(c)
        if (this.redoStack.length > this.limit) this.redoStack.shift()
        return c
    }

    /**
     * Pop the top redo command and move it back to the undo stack. Returns the
     * command so the caller can apply its `afterState` (replay). Undefined empty.
     */
    popRedo(): AppEditCommand | undefined {
        const c = this.redoStack.pop()
        if (!c) return undefined
        this.undoStack.push(c)
        if (this.undoStack.length > this.limit) this.undoStack.shift()
        return c
    }

    /** Drop all history (e.g. on iModel switch). */
    clear(): void { this.undoStack = []; this.redoStack = [] }

    /** Bounded snapshot for diagnostics/UI (counts only; never leaks payloads). */
    counts(): { undo: number; redo: number } { return { undo: this.undoStack.length, redo: this.redoStack.length } }
}
