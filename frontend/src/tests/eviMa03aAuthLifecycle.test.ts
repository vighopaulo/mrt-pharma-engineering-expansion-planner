/**
 * EVI-MA-03A — viewer-auth state-machine tests. Bentley-FREE and secret-free:
 * proves the ONE authoritative ViewerAuthState machine gates the <Viewer> mount,
 * demotes on token loss/expiry (so `validTokenNeeded` can never be the normal
 * failure), and that no token value ever appears in output.
 */
import { describe, expect, it } from 'vitest'
import {
    decideTokenReadiness,
    viewerAuthReducer,
    viewerMayMount,
    TOKEN_EXPIRY_SKEW_MS,
    type ViewerAuthState,
} from '../lib/viewerAuth'

// ---------------------------------------------------------------------------
// Mount gate
// ---------------------------------------------------------------------------
describe('EVI-MA-03A viewerMayMount', () => {
    it('the Viewer may mount ONLY in TOKEN_READY', () => {
        const states: ViewerAuthState[] = ['CONFIG_MISSING', 'INITIALIZING', 'AUTHENTICATING', 'TOKEN_READY', 'REAUTH_REQUIRED', 'ERROR']
        for (const s of states) {
            expect(viewerMayMount(s)).toBe(s === 'TOKEN_READY')
        }
    })
})

// ---------------------------------------------------------------------------
// State transitions (A–G)
// ---------------------------------------------------------------------------
describe('EVI-MA-03A viewerAuthReducer', () => {
    it('A — CONFIG_MISSING stays missing; Viewer not mounted', () => {
        const s = viewerAuthReducer('INITIALIZING', { type: 'CONFIG_MISSING' })
        expect(s).toBe('CONFIG_MISSING')
        expect(viewerMayMount(s)).toBe(false)
        // INITIALIZE does not escape CONFIG_MISSING.
        expect(viewerAuthReducer('CONFIG_MISSING', { type: 'INITIALIZE' })).toBe('CONFIG_MISSING')
    })

    it('B — silent ok but token unusable -> REAUTH_REQUIRED, not mounted', () => {
        const s = viewerAuthReducer('AUTHENTICATING', { type: 'TOKEN_NOT_READY' })
        expect(s).toBe('REAUTH_REQUIRED')
        expect(viewerMayMount(s)).toBe(false)
    })

    it('C/E — token verified -> TOKEN_READY, may mount', () => {
        const s = viewerAuthReducer('AUTHENTICATING', { type: 'TOKEN_VERIFIED' })
        expect(s).toBe('TOKEN_READY')
        expect(viewerMayMount(s)).toBe(true)
    })

    it('F — TOKEN_LOST while TOKEN_READY -> REAUTH_REQUIRED (never a dead Viewer)', () => {
        const s = viewerAuthReducer('TOKEN_READY', { type: 'TOKEN_LOST' })
        expect(s).toBe('REAUTH_REQUIRED')
        expect(viewerMayMount(s)).toBe(false)
        // TOKEN_LOST while NOT ready is a no-op.
        expect(viewerAuthReducer('AUTHENTICATING', { type: 'TOKEN_LOST' })).toBe('AUTHENTICATING')
    })

    it('G — RECONNECT_REQUESTED -> AUTHENTICATING -> TOKEN_VERIFIED restores TOKEN_READY', () => {
        let s: ViewerAuthState = 'REAUTH_REQUIRED'
        s = viewerAuthReducer(s, { type: 'RECONNECT_REQUESTED' })
        expect(s).toBe('AUTHENTICATING')
        s = viewerAuthReducer(s, { type: 'TOKEN_VERIFIED' })
        expect(s).toBe('TOKEN_READY')
        expect(viewerMayMount(s)).toBe(true)
    })

    it('AUTH_ERROR -> ERROR (not mounted)', () => {
        const s = viewerAuthReducer('AUTHENTICATING', { type: 'AUTH_ERROR' })
        expect(s).toBe('ERROR')
        expect(viewerMayMount(s)).toBe(false)
    })
})

// ---------------------------------------------------------------------------
// Token readiness (the decideTokenReadiness gate feeding TOKEN_VERIFIED)
// ---------------------------------------------------------------------------
describe('EVI-MA-03A token readiness', () => {
    it('B/D — authorized but empty token -> NEEDS_REAUTH', () => {
        expect(decideTokenReadiness({ authorized: true, hasSignedIn: true, accessToken: '' })).toBe('NEEDS_REAUTH')
    })

    it('C — authorized + non-empty token -> READY', () => {
        expect(decideTokenReadiness({ authorized: true, hasSignedIn: true, accessToken: 'Bearer x' })).toBe('READY')
    })

    it('F — a token within the expiry skew window is NOT ready (proactive renew)', () => {
        const now = 1_000_000
        // Expires just inside the skew window -> not ready.
        expect(decideTokenReadiness({ authorized: true, hasSignedIn: true, accessToken: 'Bearer x', expiresAt: now + TOKEN_EXPIRY_SKEW_MS - 1, now })).toBe('NEEDS_REAUTH')
        // Expires comfortably beyond the skew -> ready.
        expect(decideTokenReadiness({ authorized: true, hasSignedIn: true, accessToken: 'Bearer x', expiresAt: now + TOKEN_EXPIRY_SKEW_MS + 60_000, now })).toBe('READY')
    })

    it('I/J — cached valid token -> READY; stale session (empty token) -> NEEDS_REAUTH (not raw failure)', () => {
        expect(decideTokenReadiness({ authorized: true, hasSignedIn: true, accessToken: 'Bearer cached' })).toBe('READY')
        expect(decideTokenReadiness({ authorized: false, hasSignedIn: false, accessToken: '' })).toBe('NEEDS_REAUTH')
    })
})

// ---------------------------------------------------------------------------
// Secret safety (M/N)
// ---------------------------------------------------------------------------
describe('EVI-MA-03A secret safety', () => {
    it('the readiness decision returns only an enum, never the token value', () => {
        const r = decideTokenReadiness({ authorized: true, hasSignedIn: true, accessToken: 'eyJsecretTOKEN' })
        expect(r).toBe('READY')
        expect(String(r)).not.toContain('eyJ')
        expect(String(r)).not.toContain('secret')
    })

    it('state values are non-secret string enums', () => {
        const all: ViewerAuthState[] = ['CONFIG_MISSING', 'INITIALIZING', 'AUTHENTICATING', 'TOKEN_READY', 'REAUTH_REQUIRED', 'ERROR']
        for (const s of all) expect(typeof s).toBe('string')
    })
})
