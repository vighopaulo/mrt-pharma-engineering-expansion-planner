/**
 * roomDiscoveryLifecycle — pure, Bentley-free lifecycle + commit policy for the
 * generic BIM room-discovery semantics cache (Build 1A.1 correction).
 *
 * Manual acceptance exposed a 200 → 0 runtime regression: the BIM stayed visibly
 * rendered, yet the room selector collapsed to 0 and showed "No BIM spaces
 * available yet". Source tracing found `refreshModelSemantics()` unconditionally
 * assigned `cachedModelSemantics = await buildModelSemantics()` — so a NOT-READY
 * refresh (the active viewport transiently unbound during a viewer lifecycle
 * event → `buildModelSemantics` returns EMPTY) OVERWROTE the previously-valid
 * 200-room cache, with no iModel ownership, no async-race guard, and no lifecycle
 * status to distinguish "loading/not-ready" from a legitimate READY-zero.
 *
 * This module holds the PURE decision policy so it is fully unit-testable without
 * @itwin / a viewport:
 *   - an explicit lifecycle status (NOT_BOUND / LOADING / READY / ERROR);
 *   - a COMMIT decision that (a) rejects stale completions from another iModel,
 *     (b) never lets a failed/not-ready refresh erase a current valid result,
 *     while (c) still accepting a LEGITIMATE current-iModel zero result.
 *
 * Nothing here imports @itwin or triggers extraction; the overlay wires the live
 * iModel identity + refresh results in.
 */

export type RoomDiscoveryStatus = 'NOT_BOUND' | 'LOADING' | 'READY' | 'ERROR'

/** The owned semantics-cache lifecycle state (minimal ownership metadata). */
export interface RoomDiscoveryState {
    /** The iModel the currently-committed semantics belong to (undefined = none). */
    ownerIModelId?: string
    /** Explicit lifecycle status. */
    status: RoomDiscoveryStatus
    /** Room count of the currently-committed semantics (0 until a READY commit). */
    roomCount: number
    /** Monotonic count of stale/failed refreshes that were discarded (diagnostic). */
    staleDiscardedCount: number
    /** Last refresh outcome class (diagnostic). */
    lastRefreshResult?: RefreshOutcome
    /** Last error class, if the last refresh failed (diagnostic). */
    lastRefreshErrorClass?: string
}

/** The initial, unbound lifecycle state. */
export const INITIAL_ROOM_DISCOVERY_STATE: RoomDiscoveryState = {
    ownerIModelId: undefined,
    status: 'NOT_BOUND',
    roomCount: 0,
    staleDiscardedCount: 0,
}

/** A completed refresh's outcome, as observed by the caller. */
export type RefreshOutcome =
    | 'READY_NONEMPTY' // buildModelSemantics returned N>0 rooms for the target iModel
    | 'READY_EMPTY' // buildModelSemantics returned 0 rooms for a genuinely-bound iModel
    | 'NOT_READY' // no iModel was bound when the refresh ran (viewport transiently unbound)
    | 'FAILED' // buildModelSemantics threw / errored

/** A completed refresh attempt, tagged with the iModel it targeted. */
export interface RefreshCompletion {
    /** The iModel id the refresh was STARTED for (captured at call time). */
    targetIModelId?: string
    /** The iModel id the refresh actually RAN against (from the live viewport). */
    ranAgainstIModelId?: string
    /** The observed outcome. */
    outcome: RefreshOutcome
    /** Room count produced (0 unless READY_NONEMPTY). */
    roomCount: number
    /** Error class when outcome === 'FAILED'. */
    errorClass?: string
}

/** Whether a legitimate zero-room result should be accepted as READY. */
export function isLegitimateZeroResult(outcome: RefreshOutcome): boolean {
    // Only a genuinely-bound iModel that produced 0 rooms is a legitimate zero.
    return outcome === 'READY_EMPTY'
}

/**
 * Decide whether a completed refresh may COMMIT its result into the cache, and
 * the resulting lifecycle state. Rules (Build 1A.1 §8/§9/§10):
 *
 *   1. STALE iModel: if the refresh ran against (or was started for) an iModel
 *      that is no longer the current active iModel, DISCARD it — it must never
 *      overwrite the current iModel's data.
 *   2. NOT_READY / FAILED: never erase a currently-valid (READY, non-empty)
 *      result. Map to ERROR (keep prior committed data) so the UI can show an
 *      honest not-ready/error state rather than a false READY-zero.
 *   3. READY_NONEMPTY: commit; status READY.
 *   4. READY_EMPTY: a legitimate current-iModel zero — commit 0 rooms; READY.
 *
 * `current` is the state BEFORE this completion; `activeIModelId` is the iModel
 * the app currently considers active (the room-discovery owner).
 */
export interface CommitDecision {
    commit: boolean
    /** The next lifecycle state (whether or not the semantics are replaced). */
    next: RoomDiscoveryState
    /** Why the decision was made (diagnostic). */
    reason:
        | 'COMMIT_READY_NONEMPTY'
        | 'COMMIT_READY_EMPTY'
        | 'DISCARD_STALE_IMODEL'
        | 'KEEP_PRIOR_NOT_READY'
        | 'KEEP_PRIOR_FAILED'
}

export function decideSemanticsCommit(input: {
    current: RoomDiscoveryState
    activeIModelId: string | undefined
    completion: RefreshCompletion
}): CommitDecision {
    const { current, activeIModelId, completion } = input

    // 1. Stale-iModel guard. A completion whose target/ran iModel is not the
    //    current active iModel must never overwrite current data.
    const completionIModel = completion.ranAgainstIModelId ?? completion.targetIModelId
    const isStale =
        !!activeIModelId &&
        !!completionIModel &&
        completionIModel !== activeIModelId
    if (isStale) {
        return {
            commit: false,
            reason: 'DISCARD_STALE_IMODEL',
            next: {
                ...current,
                staleDiscardedCount: current.staleDiscardedCount + 1,
                lastRefreshResult: completion.outcome,
            },
        }
    }

    // 2. NOT_READY: no iModel was bound. Never map to READY-zero; keep prior
    //    committed data and surface an honest non-ready status.
    if (completion.outcome === 'NOT_READY') {
        return {
            commit: false,
            reason: 'KEEP_PRIOR_NOT_READY',
            next: {
                ...current,
                // If we had valid data, keep READY; else reflect NOT_BOUND/LOADING.
                status: current.status === 'READY' && current.roomCount > 0 ? 'READY' : (activeIModelId ? 'LOADING' : 'NOT_BOUND'),
                staleDiscardedCount: current.staleDiscardedCount + 1,
                lastRefreshResult: completion.outcome,
            },
        }
    }

    // 3. FAILED: never erase a currently-valid result; surface ERROR.
    if (completion.outcome === 'FAILED') {
        return {
            commit: false,
            reason: 'KEEP_PRIOR_FAILED',
            next: {
                ...current,
                status: current.status === 'READY' && current.roomCount > 0 ? 'READY' : 'ERROR',
                staleDiscardedCount: current.staleDiscardedCount + 1,
                lastRefreshResult: completion.outcome,
                lastRefreshErrorClass: completion.errorClass ?? 'UNKNOWN',
            },
        }
    }

    // 4. READY (empty or non-empty) for the current iModel: commit.
    return {
        commit: true,
        reason: completion.outcome === 'READY_NONEMPTY' ? 'COMMIT_READY_NONEMPTY' : 'COMMIT_READY_EMPTY',
        next: {
            ownerIModelId: activeIModelId ?? completionIModel,
            status: 'READY',
            roomCount: completion.roomCount,
            staleDiscardedCount: current.staleDiscardedCount,
            lastRefreshResult: completion.outcome,
            lastRefreshErrorClass: undefined,
        },
    }
}

/**
 * The lifecycle state at the START of a refresh for `targetIModelId`. Moves to
 * LOADING (or NOT_BOUND when no iModel), without touching committed data.
 */
export function beginRefreshState(input: {
    current: RoomDiscoveryState
    targetIModelId: string | undefined
}): RoomDiscoveryState {
    if (!input.targetIModelId) {
        return { ...input.current, status: 'NOT_BOUND' }
    }
    // A same-iModel re-refresh keeps prior READY data visible while LOADING only
    // when we have nothing valid yet; if we already have valid rooms, stay READY
    // (a legitimate same-iModel refresh can still update on commit).
    const keepReady = input.current.status === 'READY' && input.current.ownerIModelId === input.targetIModelId && input.current.roomCount > 0
    return { ...input.current, status: keepReady ? 'READY' : 'LOADING' }
}

/**
 * The UI-facing room-selector count semantics (Build 1A.1 §18). Returns the
 * label the selector should show for the current lifecycle + filtered count.
 */
export function roomSelectorLabel(input: {
    status: RoomDiscoveryStatus
    filteredRoomCount: number
}): string {
    switch (input.status) {
        case 'NOT_BOUND': return 'Open the model to discover rooms'
        case 'LOADING': return 'Loading rooms…'
        case 'ERROR': return 'Room discovery unavailable'
        case 'READY': return `Select a room (${input.filteredRoomCount})`
    }
}
