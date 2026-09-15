/**
 * EVI-MA-03 — Bentley viewer auth/config recovery tests. Bentley-FREE: exercises
 * the pure token-readiness decision and the secret-free config-presence
 * diagnostic. No real credentials; no token values ever appear in output.
 */
import { describe, expect, it } from 'vitest'
import { decideTokenReadiness, sanitizeAuthError } from '../lib/viewerAuth'
import {
    resolveViewerConfigDiagnostic,
    REQUIRED_VIEWER_ENV_KEYS,
    OPTIONAL_VIEWER_ENV_KEYS,
} from '../lib/viewerConfig'

// ---------------------------------------------------------------------------
// Token readiness — gate <Viewer> on an actual access token
// ---------------------------------------------------------------------------
describe('EVI-MA-03 decideTokenReadiness', () => {
    it('READY when authorized, signed in, and a non-empty token is present', () => {
        expect(decideTokenReadiness({ authorized: true, hasSignedIn: true, accessToken: 'Bearer abc' })).toBe('READY')
    })

    it('NEEDS_REAUTH when authorized but the access token is EMPTY (the validTokenNeeded case)', () => {
        expect(decideTokenReadiness({ authorized: true, hasSignedIn: true, accessToken: '' })).toBe('NEEDS_REAUTH')
        expect(decideTokenReadiness({ authorized: true, hasSignedIn: true, accessToken: '   ' })).toBe('NEEDS_REAUTH')
        expect(decideTokenReadiness({ authorized: true, hasSignedIn: true, accessToken: undefined })).toBe('NEEDS_REAUTH')
        expect(decideTokenReadiness({ authorized: true, hasSignedIn: true, accessToken: null })).toBe('NEEDS_REAUTH')
    })

    it('NEEDS_REAUTH when not authorized / not signed in even if a token string exists', () => {
        expect(decideTokenReadiness({ authorized: false, hasSignedIn: true, accessToken: 'Bearer abc' })).toBe('NEEDS_REAUTH')
        expect(decideTokenReadiness({ authorized: true, hasSignedIn: false, accessToken: 'Bearer abc' })).toBe('NEEDS_REAUTH')
    })

    it('NEEDS_REAUTH when the token is already expired', () => {
        const now = 1_000_000
        expect(decideTokenReadiness({ authorized: true, hasSignedIn: true, accessToken: 'Bearer abc', expiresAt: now - 1, now })).toBe('NEEDS_REAUTH')
        expect(decideTokenReadiness({ authorized: true, hasSignedIn: true, accessToken: 'Bearer abc', expiresAt: now + 60_000, now })).toBe('READY')
    })

    it('never echoes the token value (the decision returns only a status enum)', () => {
        const result = decideTokenReadiness({ authorized: true, hasSignedIn: true, accessToken: 'eyJsecretTOKENvalue' })
        expect(result).toBe('READY')
        expect(String(result)).not.toContain('secret')
        expect(String(result)).not.toContain('eyJ')
    })
})

// ---------------------------------------------------------------------------
// Config-presence diagnostic — NAMES + PRESENT/MISSING only, no values
// ---------------------------------------------------------------------------
describe('EVI-MA-03 resolveViewerConfigDiagnostic', () => {
    const FULL: Record<string, string> = {
        VITE_BENTLEY_SPA_CLIENT_ID: 'client-id-value',
        VITE_BENTLEY_IMODEL_ID: 'imodel-id-value',
        VITE_BENTLEY_AUTHORITY: 'https://ims.bentley.com',
        VITE_BENTLEY_SCOPE: 'itwin-platform',
        VITE_BENTLEY_REDIRECT_URI: 'http://localhost:3000/signin-callback',
        VITE_BENTLEY_POST_SIGNOUT_REDIRECT_URI: 'http://localhost:3000',
        VITE_BENTLEY_ITWIN_ID: 'itwin-id-value',
    }
    const read = (env: Record<string, string | undefined>) => (k: string) => {
        const v = env[k]
        return v && v.trim() !== '' ? v : undefined
    }

    it('ready=true when all REQUIRED keys are present', () => {
        const d = resolveViewerConfigDiagnostic(read(FULL))
        expect(d.ready).toBe(true)
        expect(d.missingRequired).toEqual([])
        for (const k of REQUIRED_VIEWER_ENV_KEYS) {
            expect(d.keys.find((x) => x.key === k)?.present).toBe(true)
        }
    })

    it('CONFIG_MISSING when the SPA client id is absent', () => {
        const d = resolveViewerConfigDiagnostic(read({ ...FULL, VITE_BENTLEY_SPA_CLIENT_ID: '' }))
        expect(d.ready).toBe(false)
        expect(d.missingRequired).toContain('VITE_BENTLEY_SPA_CLIENT_ID')
    })

    it('CONFIG_MISSING when the iModel id is absent', () => {
        const d = resolveViewerConfigDiagnostic(read({ ...FULL, VITE_BENTLEY_IMODEL_ID: undefined }))
        expect(d.ready).toBe(false)
        expect(d.missingRequired).toContain('VITE_BENTLEY_IMODEL_ID')
    })

    it('reports optional keys as optional (never required)', () => {
        const d = resolveViewerConfigDiagnostic(read(FULL))
        for (const k of OPTIONAL_VIEWER_ENV_KEYS) {
            expect(d.keys.find((x) => x.key === k)?.required).toBe(false)
        }
    })

    it('NEVER includes any secret VALUE in the diagnostic output', () => {
        const d = resolveViewerConfigDiagnostic(read(FULL))
        const serialized = JSON.stringify(d)
        for (const value of Object.values(FULL)) {
            expect(serialized).not.toContain(value)
        }
        // Only key names + present/required booleans are present.
        expect(serialized).toContain('VITE_BENTLEY_SPA_CLIENT_ID')
        expect(serialized).toContain('present')
    })
})

// ---------------------------------------------------------------------------
// sanitizeAuthError never leaks bearer tokens (preserved behavior)
// ---------------------------------------------------------------------------
describe('EVI-MA-03 sanitizeAuthError', () => {
    it('redacts bearer + JWT-looking tokens', () => {
        const s = sanitizeAuthError('failed with Bearer eyJabc.def.ghi and access_token=zzz')
        expect(s).not.toContain('eyJabc')
        expect(s.toLowerCase()).toContain('redacted')
    })
})
