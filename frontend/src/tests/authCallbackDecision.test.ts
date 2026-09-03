/**
 * Offline tests for the pure /signin-callback decision seam. No @itwin, no
 * network — proves stale-vs-fresh callback classification and storage-key
 * derivation used for graceful hard-refresh recovery.
 */
import { describe, expect, it } from 'vitest'
import {
    decideCallbackAction,
    oidcSettingsStorageKey,
    readCallbackActionFromEnv,
    type CallbackAction,
} from '../lib/authCallbackDecision'

describe('oidcSettingsStorageKey', () => {
    it('matches the @itwin/browser-authorization key format oidc.<state>', () => {
        expect(oidcSettingsStorageKey('abc123')).toBe('oidc.abc123')
    })
})

describe('decideCallbackAction', () => {
    it('FRESH_CALLBACK_DETECTION — code+state present and settings entry present -> PROCESS_CALLBACK', () => {
        const a: CallbackAction = decideCallbackAction({ code: 'C', state: 'S', settingsEntryPresent: true })
        expect(a).toBe('PROCESS_CALLBACK')
    })

    it('STALE_CALLBACK_DETECTION — code+state present but settings entry absent -> RECOVER_STALE', () => {
        expect(decideCallbackAction({ code: 'C', state: 'S', settingsEntryPresent: false })).toBe('RECOVER_STALE')
    })

    it('EMPTY_CALLBACK — no code/state -> RECOVER_EMPTY', () => {
        expect(decideCallbackAction({ code: null, state: null, settingsEntryPresent: false })).toBe('RECOVER_EMPTY')
        expect(decideCallbackAction({ code: 'C', state: null, settingsEntryPresent: false })).toBe('RECOVER_EMPTY')
        expect(decideCallbackAction({ code: null, state: 'S', settingsEntryPresent: true })).toBe('RECOVER_EMPTY')
    })
})

describe('readCallbackActionFromEnv', () => {
    const store = (entries: Record<string, string>): Pick<Storage, 'getItem'> => ({
        getItem: (k: string) => (k in entries ? entries[k] : null),
    })

    it('fresh: URL has code+state and oidc.<state> present -> PROCESS_CALLBACK', () => {
        const r = readCallbackActionFromEnv(
            { search: '?code=fresh&state=nonce1' },
            store({ 'oidc.nonce1': '{"client_id":"x"}' }),
        )
        expect(r.action).toBe('PROCESS_CALLBACK')
        expect(r.hasCode).toBe(true); expect(r.hasState).toBe(true); expect(r.settingsEntryPresent).toBe(true)
    })

    it('stale refresh: URL has code+state but oidc.<state> was consumed -> RECOVER_STALE', () => {
        const r = readCallbackActionFromEnv(
            { search: '?code=consumed&state=nonce2' },
            store({}), // entry removed after first completion
        )
        expect(r.action).toBe('RECOVER_STALE')
        expect(r.settingsEntryPresent).toBe(false)
    })

    it('empty: no query params -> RECOVER_EMPTY', () => {
        const r = readCallbackActionFromEnv({ search: '' }, store({}))
        expect(r.action).toBe('RECOVER_EMPTY')
    })

    it('does not read any secret value — only presence of the state entry', () => {
        // The store spy only ever receives the derived key, never a token.
        const seenKeys: string[] = []
        const spy: Pick<Storage, 'getItem'> = { getItem: (k) => { seenKeys.push(k); return null } }
        readCallbackActionFromEnv({ search: '?code=c&state=nonce3' }, spy)
        expect(seenKeys).toEqual(['oidc.nonce3'])
    })
})
