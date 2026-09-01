import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import {
    authReducer,
    INITIAL_AUTH_STATE,
    browserAuthClientOptions,
    sanitizeAuthError,
    SPA_USES_PKCE,
} from '../lib/viewerAuth'
import {
    getViewerConfig,
    isViewerConfigured,
    KNOWN_ITWIN_ID,
    SPA_CLIENT_SECRET_REQUIRED,
    ViewerConfigError,
    FORBIDDEN_BROWSER_ENV_KEYS,
    type ViewerConfig,
} from '../lib/viewerConfig'
import {
    BASIC_CLIPPING_CAPABILITY,
    VIEWER_CAMERA_CAPABILITIES,
    VIEWER_LOAD_SEQUENCE,
    loadStateLabel,
    nextLoadState,
    stableIdentityKey,
    toBentleySourceIdentity,
    toPropertyRows,
    unboundResult,
} from '../lib/viewerSelection'

// --- SPA public configuration (Sec 7) -------------------------------------

describe('viewer configuration', () => {
    const OLD = { ...import.meta.env }
    beforeEach(() => {
        vi.stubEnv('VITE_BENTLEY_SPA_CLIENT_ID', 'mrtway-dev-viewer-spa')
        vi.stubEnv('VITE_BENTLEY_IMODEL_ID', 'imodel-abc-123')
    })
    afterEach(() => {
        vi.unstubAllEnvs()
        void OLD
    })

    it('1. builds a config from browser-safe VITE values', () => {
        const c = getViewerConfig()
        expect(c.clientId).toBe('mrtway-dev-viewer-spa')
        expect(c.iModelId).toBe('imodel-abc-123')
    })

    it('2. defaults iTwin id to the known live MRTway Development Twin', () => {
        expect(getViewerConfig().iTwinId).toBe(KNOWN_ITWIN_ID)
        expect(KNOWN_ITWIN_ID).toBe('bdf29ecd-b4a4-404d-861a-ac3061c7b12f')
    })

    it('3. uses PKCE responseType code and default itwin-platform scope', () => {
        const c = getViewerConfig()
        expect(c.responseType).toBe('code')
        expect(c.scope).toBe('itwin-platform')
    })

    it('4. default redirect URI matches the SPA localhost:3000 callback', () => {
        expect(getViewerConfig().redirectUri).toBe('http://localhost:3000/signin-callback')
    })

    it('5. missing client id throws an actionable ViewerConfigError (no fake id)', () => {
        vi.stubEnv('VITE_BENTLEY_SPA_CLIENT_ID', '')
        expect(() => getViewerConfig()).toThrow(ViewerConfigError)
    })

    it('6. missing iModel id throws (never substitutes a fake iModel)', () => {
        vi.stubEnv('VITE_BENTLEY_IMODEL_ID', '')
        expect(() => getViewerConfig()).toThrow(ViewerConfigError)
    })

    it('7. isViewerConfigured reflects presence of required values', () => {
        expect(isViewerConfigured()).toBe(true)
        vi.stubEnv('VITE_BENTLEY_SPA_CLIENT_ID', '')
        expect(isViewerConfigured()).toBe(false)
    })
})

// --- security boundary (Sec 6/30) -----------------------------------------

describe('SPA security boundary', () => {
    it('8. SPA requires NO client secret', () => {
        expect(SPA_CLIENT_SECRET_REQUIRED).toBe(false)
    })

    it('9. viewer config type carries no client secret field', () => {
        vi.stubEnv('VITE_BENTLEY_SPA_CLIENT_ID', 'x')
        vi.stubEnv('VITE_BENTLEY_IMODEL_ID', 'y')
        const c: ViewerConfig = getViewerConfig()
        expect(Object.keys(c)).not.toContain('clientSecret')
        vi.unstubAllEnvs()
    })

    it('10. forbidden secret env keys are documented and never VITE-prefixed', () => {
        for (const k of FORBIDDEN_BROWSER_ENV_KEYS) {
            expect(k.startsWith('VITE_')).toBe(false)
        }
    })

    it('11. PKCE auth options contain no secret', () => {
        const opts = browserAuthClientOptions({
            clientId: 'c', authority: 'a', scope: 's', redirectUri: 'r',
            postSignoutRedirectUri: 'p', responseType: 'code', iTwinId: 't', iModelId: 'i',
        })
        expect(opts.responseType).toBe('code')
        expect(Object.keys(opts)).not.toContain('clientSecret')
        expect(SPA_USES_PKCE).toBe(true)
    })
})

// --- auth state machine (Sec 12) ------------------------------------------

describe('auth state machine', () => {
    it('12. starts NOT_AUTHENTICATED', () => {
        expect(INITIAL_AUTH_STATE.state).toBe('NOT_AUTHENTICATED')
    })

    it('13. sign-in requested -> AUTHENTICATING', () => {
        expect(authReducer(INITIAL_AUTH_STATE, { type: 'SIGN_IN_REQUESTED' }).state).toBe('AUTHENTICATING')
    })

    it('14. success -> AUTHENTICATED', () => {
        const s = authReducer({ state: 'AUTHENTICATING', errorMessage: null }, { type: 'AUTH_SUCCEEDED' })
        expect(s.state).toBe('AUTHENTICATED')
    })

    it('15. failure -> AUTH_ERROR with sanitized message', () => {
        const s = authReducer(INITIAL_AUTH_STATE, { type: 'AUTH_FAILED', message: 'Bearer eyJabcdefghijklmno failed' })
        expect(s.state).toBe('AUTH_ERROR')
        expect(s.errorMessage).not.toContain('eyJabcdefghijklmno')
    })

    it('16. sign out -> NOT_AUTHENTICATED', () => {
        const s = authReducer({ state: 'AUTHENTICATED', errorMessage: null }, { type: 'SIGN_OUT' })
        expect(s.state).toBe('NOT_AUTHENTICATED')
    })

    it('17. sanitizeAuthError redacts tokens and headers', () => {
        expect(sanitizeAuthError('access_token=abc123&x')).toContain('[redacted]')
        expect(sanitizeAuthError('Bearer eyJ0123456789abc')).toContain('[redacted]')
    })
})

// --- selection transforms (Sec 19-20) -------------------------------------

describe('selection transforms', () => {
    it('18. stable identity prefers element id, never the label', () => {
        expect(stableIdentityKey({ elementId: 'E1', label: 'Door 3', federationGuid: 'F1' })).toBe('E1')
        expect(stableIdentityKey({ elementId: '', federationGuid: 'F1', label: 'x' })).toBe('F1')
    })

    it('19. source identity is normalized with nulls, not fabricated', () => {
        const id = toBentleySourceIdentity({ elementId: 'E1' })
        expect(id.elementId).toBe('E1')
        expect(id.className).toBeNull()
        expect(id.stableIdentityKey).toBe('E1')
    })

    it('20. property rows pass through source values, skipping nullish', () => {
        const rows = toPropertyRows({ Area: '12 m2', Height: null, Level: 3 })
        expect(rows).toContainEqual({ name: 'Area', value: '12 m2' })
        expect(rows.find((r) => r.name === 'Height')).toBeUndefined()
        expect(rows.find((r) => r.name === 'Level')?.value).toBe('3')
    })

    it('21. empty properties -> empty rows (never invented)', () => {
        expect(toPropertyRows(null)).toEqual([])
        expect(toPropertyRows({})).toEqual([])
    })
})

// --- MRT binding lookup + unbound (Sec 21-22) -----------------------------

describe('MRT binding lookup', () => {
    afterEach(() => {
        vi.restoreAllMocks()
    })

    it('22. unbound result is truthful, never a fabricated binding', () => {
        const r = unboundResult({ elementId: 'E1', className: 'IfcWall' })
        expect(r.bindingStatus).toBe('UNBOUND')
        expect(r.mrtObjectId).toBeNull()
        expect(r.isBound).toBe(false)
    })

    it('23. resolveMrtBinding returns UNBOUND on backend 404', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ status: 404, ok: false }))
        const { resolveMrtBinding } = await import('../lib/viewerSelection')
        const r = await resolveMrtBinding({ elementId: 'E1', className: 'IfcWall' })
        expect(r.bindingStatus).toBe('UNBOUND')
        expect(r.isBound).toBe(false)
    })

    it('24. resolveMrtBinding returns BOUND from backend authority result', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
            status: 200, ok: true,
            json: async () => ({ binding_status: 'BOUND', mrt_object_id: 'MRT-OBJ-1', mrt_object_type: 'MRT_ENDPOINT', source_provenance: 'BENTLEY_ITWIN_LIVE_READ' }),
        }))
        const { resolveMrtBinding } = await import('../lib/viewerSelection')
        const r = await resolveMrtBinding({ elementId: 'E1', className: 'IfcTransportElement' })
        expect(r.bindingStatus).toBe('BOUND')
        expect(r.mrtObjectId).toBe('MRT-OBJ-1')
        expect(r.isBound).toBe(true)
    })

    it('25. resolveMrtBinding returns UNBOUND when backend unreachable', async () => {
        vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')))
        const { resolveMrtBinding } = await import('../lib/viewerSelection')
        const r = await resolveMrtBinding({ elementId: 'E1' })
        expect(r.isBound).toBe(false)
    })

    it('26. missing stable identity -> MISSING_REQUIRED_PROPERTY (no binding)', async () => {
        const { resolveMrtBinding } = await import('../lib/viewerSelection')
        const r = await resolveMrtBinding({ elementId: '' })
        expect(r.bindingStatus).toBe('MISSING_REQUIRED_PROPERTY')
    })
})

// --- loading states + camera + clipping (Sec 15/24/27) --------------------

describe('viewer loading state machine', () => {
    it('27. load sequence ends at READY', () => {
        expect(VIEWER_LOAD_SEQUENCE[VIEWER_LOAD_SEQUENCE.length - 1]).toBe('READY')
    })

    it('28. nextLoadState advances then saturates at READY', () => {
        expect(nextLoadState('AUTHENTICATING')).toBe('CONNECTING_TO_ITWIN')
        expect(nextLoadState('LOADING_VIEWPORT')).toBe('READY')
        expect(nextLoadState('READY')).toBe('READY')
    })

    it('29. every load state has a user-facing label (no blank screen)', () => {
        for (const s of VIEWER_LOAD_SEQUENCE) {
            expect(loadStateLabel(s).length).toBeGreaterThan(0)
        }
    })

    it('30. camera capabilities declare orbit/pan/zoom/fit/reset available', () => {
        expect(VIEWER_CAMERA_CAPABILITIES.orbit).toBe(true)
        expect(VIEWER_CAMERA_CAPABILITIES.pan).toBe(true)
        expect(VIEWER_CAMERA_CAPABILITIES.zoom).toBe(true)
        expect(VIEWER_CAMERA_CAPABILITIES.fitView).toBe(true)
        expect(VIEWER_CAMERA_CAPABILITIES.resetView).toBe(true)
    })

    it('31. basic clipping capability is PASS or NOT_YET_INTEGRATED', () => {
        expect(['PASS', 'NOT_YET_INTEGRATED']).toContain(BASIC_CLIPPING_CAPABILITY)
    })
})

// --- viewer route renders without loading the heavy @itwin stack ----------

describe('viewer route', () => {
    it('32. /viewer renders a sign-in CTA when unconfigured (no @itwin import)', () => {
        // no VITE client id stubbed -> unconfigured CTA, never a blank viewport
        render(
            <MemoryRouter initialEntries={['/viewer']}>
                <App />
            </MemoryRouter>,
        )
        expect(screen.getByText('MRTway Development Viewer')).toBeInTheDocument()
    })

    it('33. /signin-callback route renders the callback handler', () => {
        render(
            <MemoryRouter initialEntries={['/signin-callback']}>
                <App />
            </MemoryRouter>,
        )
        expect(screen.getByRole('heading', { name: 'Bentley sign-in' })).toBeInTheDocument()
    })
})
