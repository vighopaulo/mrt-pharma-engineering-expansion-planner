/**
 * Build 1A.1 — room-discovery lifecycle policy tests.
 *
 * Proves the pure commit/lifecycle policy that fixes the 200 → 0 regression: a
 * not-ready / failed / stale refresh must NEVER erase a currently-valid cache,
 * while a legitimate current-iModel zero IS accepted, and NOT_BOUND / LOADING /
 * ERROR are never presented as a READY-zero.
 */
import { describe, it, expect } from 'vitest'
import {
    INITIAL_ROOM_DISCOVERY_STATE,
    decideSemanticsCommit,
    beginRefreshState,
    isLegitimateZeroResult,
    roomSelectorLabel,
    type RoomDiscoveryState,
    type RefreshCompletion,
} from '../components/spatial/roomDiscoveryLifecycle'

const ready = (iModelId: string, roomCount: number): RoomDiscoveryState => ({
    ownerIModelId: iModelId, status: 'READY', roomCount, staleDiscardedCount: 0,
})

const completion = (o: Partial<RefreshCompletion> & { outcome: RefreshCompletion['outcome'] }): RefreshCompletion => ({
    roomCount: 0, ...o,
})

// §21.1 — NOT_BOUND is not READY zero
describe('§21.1 NOT_BOUND ≠ READY zero', () => {
    it('initial state is NOT_BOUND with 0 rooms and is not READY', () => {
        expect(INITIAL_ROOM_DISCOVERY_STATE.status).toBe('NOT_BOUND')
        expect(INITIAL_ROOM_DISCOVERY_STATE.roomCount).toBe(0)
        expect(roomSelectorLabel({ status: 'NOT_BOUND', filteredRoomCount: 0 })).not.toContain('Select a room')
    })
})

// §21.2 — LOADING is not READY zero
describe('§21.2 LOADING ≠ READY zero', () => {
    it('beginRefreshState with a target and no prior data => LOADING', () => {
        const s = beginRefreshState({ current: INITIAL_ROOM_DISCOVERY_STATE, targetIModelId: 'imA' })
        expect(s.status).toBe('LOADING')
        expect(roomSelectorLabel({ status: 'LOADING', filteredRoomCount: 0 })).toBe('Loading rooms…')
    })
    it('beginRefreshState with a valid same-iModel cache keeps READY (no flicker to 0)', () => {
        const s = beginRefreshState({ current: ready('imA', 200), targetIModelId: 'imA' })
        expect(s.status).toBe('READY')
        expect(s.roomCount).toBe(200)
    })
    it('beginRefreshState with no target => NOT_BOUND', () => {
        const s = beginRefreshState({ current: INITIAL_ROOM_DISCOVERY_STATE, targetIModelId: undefined })
        expect(s.status).toBe('NOT_BOUND')
    })
})

// §21.3 — READY with 200 rooms reports 200
describe('§21.3 READY nonempty commits', () => {
    it('commits 200 rooms for the active iModel', () => {
        const d = decideSemanticsCommit({
            current: beginRefreshState({ current: INITIAL_ROOM_DISCOVERY_STATE, targetIModelId: 'imA' }),
            activeIModelId: 'imA',
            completion: completion({ targetIModelId: 'imA', ranAgainstIModelId: 'imA', outcome: 'READY_NONEMPTY', roomCount: 200 }),
        })
        expect(d.commit).toBe(true)
        expect(d.reason).toBe('COMMIT_READY_NONEMPTY')
        expect(d.next.status).toBe('READY')
        expect(d.next.roomCount).toBe(200)
        expect(d.next.ownerIModelId).toBe('imA')
        expect(roomSelectorLabel({ status: d.next.status, filteredRoomCount: 200 })).toBe('Select a room (200)')
    })
})

// §21.4 — READY with legitimate 0 rooms reports 0
describe('§21.4 legitimate READY-zero accepted', () => {
    it('a genuinely-bound iModel with 0 rooms commits READY-zero', () => {
        expect(isLegitimateZeroResult('READY_EMPTY')).toBe(true)
        const d = decideSemanticsCommit({
            current: beginRefreshState({ current: INITIAL_ROOM_DISCOVERY_STATE, targetIModelId: 'imEmpty' }),
            activeIModelId: 'imEmpty',
            completion: completion({ targetIModelId: 'imEmpty', ranAgainstIModelId: 'imEmpty', outcome: 'READY_EMPTY', roomCount: 0 }),
        })
        expect(d.commit).toBe(true)
        expect(d.reason).toBe('COMMIT_READY_EMPTY')
        expect(d.next.status).toBe('READY')
        expect(d.next.roomCount).toBe(0)
    })
})

// §21.5 — ERROR does not masquerade as READY zero
describe('§21.5 ERROR ≠ READY zero', () => {
    it('a FAILED refresh with no prior data => ERROR, no commit', () => {
        const d = decideSemanticsCommit({
            current: beginRefreshState({ current: INITIAL_ROOM_DISCOVERY_STATE, targetIModelId: 'imA' }),
            activeIModelId: 'imA',
            completion: completion({ targetIModelId: 'imA', outcome: 'FAILED', errorClass: 'QueryError' }),
        })
        expect(d.commit).toBe(false)
        expect(d.next.status).toBe('ERROR')
        expect(d.next.lastRefreshErrorClass).toBe('QueryError')
        expect(isLegitimateZeroResult('FAILED')).toBe(false)
    })
})

// §21.6 — stale refresh cannot overwrite current iModel
describe('§21.6 stale iModel refresh discarded', () => {
    it('a completion from a different iModel never overwrites the current one', () => {
        const current = ready('imB', 50)
        const d = decideSemanticsCommit({
            current,
            activeIModelId: 'imB',
            completion: completion({ targetIModelId: 'imA', ranAgainstIModelId: 'imA', outcome: 'READY_NONEMPTY', roomCount: 200 }),
        })
        expect(d.commit).toBe(false)
        expect(d.reason).toBe('DISCARD_STALE_IMODEL')
        expect(d.next.roomCount).toBe(50) // unchanged
        expect(d.next.ownerIModelId).toBe('imB')
        expect(d.next.staleDiscardedCount).toBe(1)
    })
})

// §21.7 — stale empty refresh cannot erase current valid rooms (THE regression)
describe('§21.7 not-ready/empty refresh cannot erase valid rooms', () => {
    it('NOT_READY (viewport unbound) keeps the prior 200-room READY cache', () => {
        const current = ready('imClinic', 200)
        const d = decideSemanticsCommit({
            current,
            activeIModelId: 'imClinic',
            completion: completion({ targetIModelId: 'imClinic', outcome: 'NOT_READY', roomCount: 0 }),
        })
        expect(d.commit).toBe(false)
        expect(d.reason).toBe('KEEP_PRIOR_NOT_READY')
        expect(d.next.status).toBe('READY') // stays READY
        expect(d.next.roomCount).toBe(200) // NOT erased — the 200→0 fix
        expect(d.next.staleDiscardedCount).toBe(1)
    })
    it('FAILED keeps the prior 200-room READY cache', () => {
        const current = ready('imClinic', 200)
        const d = decideSemanticsCommit({
            current,
            activeIModelId: 'imClinic',
            completion: completion({ targetIModelId: 'imClinic', outcome: 'FAILED', errorClass: 'Timeout' }),
        })
        expect(d.commit).toBe(false)
        expect(d.next.status).toBe('READY')
        expect(d.next.roomCount).toBe(200)
    })
})

// §21.8 — current valid empty result is accepted (already covered §21.4); reconfirm distinct from not-ready
describe('§21.8 valid-empty vs not-ready distinguished', () => {
    it('READY_EMPTY commits 0; NOT_READY does not', () => {
        const emptyCommit = decideSemanticsCommit({
            current: INITIAL_ROOM_DISCOVERY_STATE, activeIModelId: 'imA',
            completion: completion({ ranAgainstIModelId: 'imA', outcome: 'READY_EMPTY', roomCount: 0 }),
        })
        expect(emptyCommit.commit).toBe(true)
        const notReady = decideSemanticsCommit({
            current: INITIAL_ROOM_DISCOVERY_STATE, activeIModelId: 'imA',
            completion: completion({ targetIModelId: 'imA', outcome: 'NOT_READY', roomCount: 0 }),
        })
        expect(notReady.commit).toBe(false)
    })
})

// §21.14 — same-iModel refresh can legitimately update the room collection
describe('§21.14 same-iModel refresh updates legitimately', () => {
    it('a later READY_NONEMPTY for the same iModel commits the new count', () => {
        const current = ready('imA', 150)
        const d = decideSemanticsCommit({
            current, activeIModelId: 'imA',
            completion: completion({ ranAgainstIModelId: 'imA', outcome: 'READY_NONEMPTY', roomCount: 205 }),
        })
        expect(d.commit).toBe(true)
        expect(d.next.roomCount).toBe(205)
    })
})

// §21.9 — iModel switch clears/binds intentionally
describe('§21.9 iModel switch binds intentionally (no cross-iModel carryover)', () => {
    it('a switch resets to NOT_BOUND, then the new iModel binds on READY', () => {
        // Prior clinic cache.
        const clinic = ready('imClinic', 200)
        // Simulate the switch reset (overlay sets INITIAL state on a real id change).
        const afterSwitch = { ...INITIAL_ROOM_DISCOVERY_STATE }
        expect(afterSwitch.status).toBe('NOT_BOUND')
        expect(afterSwitch.ownerIModelId).toBeUndefined()
        // A fixture refresh now binds to the fixture, never inheriting clinic's 200.
        const d = decideSemanticsCommit({
            current: beginRefreshState({ current: afterSwitch, targetIModelId: 'imFixture' }),
            activeIModelId: 'imFixture',
            completion: completion({ ranAgainstIModelId: 'imFixture', outcome: 'READY_NONEMPTY', roomCount: 12 }),
        })
        expect(d.commit).toBe(true)
        expect(d.next.ownerIModelId).toBe('imFixture')
        expect(d.next.roomCount).toBe(12)
        // The prior clinic state object is untouched (no mutation across switch).
        expect(clinic.roomCount).toBe(200)
    })
    it('a late clinic refresh landing after the switch is discarded as stale', () => {
        const d = decideSemanticsCommit({
            current: ready('imFixture', 12),
            activeIModelId: 'imFixture',
            completion: completion({ targetIModelId: 'imClinic', ranAgainstIModelId: 'imClinic', outcome: 'READY_NONEMPTY', roomCount: 200 }),
        })
        expect(d.commit).toBe(false)
        expect(d.reason).toBe('DISCARD_STALE_IMODEL')
        expect(d.next.ownerIModelId).toBe('imFixture')
    })
})

// §21.10/12/13 — toggle / camera / developer mode do NOT touch the commit policy
describe('§21.10/12/13 discovery ownership is independent of UI toggles', () => {
    it('the commit policy has no input for program-toggle / camera-mode / dev-mode', () => {
        // The decision depends ONLY on {current, activeIModelId, completion}; there
        // is no parameter by which a Clinical Program toggle, camera mode, or
        // developer mode could clear or mutate committed discovery. A repeated
        // decision with an unchanged READY cache + no new completion is a no-op.
        const current = ready('imA', 200)
        // Re-affirm the same READY result (as a redundant same-iModel refresh):
        const d = decideSemanticsCommit({
            current, activeIModelId: 'imA',
            completion: completion({ ranAgainstIModelId: 'imA', outcome: 'READY_NONEMPTY', roomCount: 200 }),
        })
        expect(d.next.roomCount).toBe(200)
        expect(d.next.status).toBe('READY')
    })
})

// Selector label semantics (§18)
describe('§18 selector label is explicit per lifecycle', () => {
    it('maps each status to a distinct, honest label', () => {
        expect(roomSelectorLabel({ status: 'READY', filteredRoomCount: 42 })).toBe('Select a room (42)')
        expect(roomSelectorLabel({ status: 'LOADING', filteredRoomCount: 0 })).toBe('Loading rooms…')
        expect(roomSelectorLabel({ status: 'ERROR', filteredRoomCount: 0 })).toBe('Room discovery unavailable')
        expect(roomSelectorLabel({ status: 'NOT_BOUND', filteredRoomCount: 0 })).toBe('Open the model to discover rooms')
    })
})
