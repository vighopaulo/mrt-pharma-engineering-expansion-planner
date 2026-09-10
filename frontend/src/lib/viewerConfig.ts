/**
 * Basic Bentley 3D Viewer — public SPA configuration (browser-safe).
 *
 * SECURITY BOUNDARY (Sec 6): this module reads ONLY browser-safe public values
 * from `import.meta.env.VITE_*`. It never reads, imports, or references the
 * backend Bentley Service client secret, `.env.bentley`, or any access token.
 * The SPA uses Authorization Code + PKCE (`responseType: "code"`) and requires
 * NO client secret in the browser.
 *
 * Known live resources (already verified by the backend build):
 *   iTwin  "MRTway Development Twin"            bdf29ecd-b4a4-404d-861a-ac3061c7b12f
 *   iModel "MRTway Hospital Campus Development" (id supplied via VITE_BENTLEY_IMODEL_ID)
 */

import { buildProjectBimRegistry, loadPersistedActiveBim, resolveActiveProjectBim } from './projectBim'

export interface ViewerConfig {
    clientId: string
    authority: string
    scope: string
    redirectUri: string
    postSignoutRedirectUri: string
    responseType: 'code'
    iTwinId: string
    /** The RESOLVED active iModel id the viewer opens (URL/persisted/default/legacy). */
    iModelId: string
    /** The RAW legacy fixture iModel id from env (VITE_BENTLEY_IMODEL_ID). This is
     * NOT the resolved active id; the Project BIM selector uses it to build the
     * registry so the fixture row keeps its own identity (never the clinic's).
     * Optional so ad-hoc ViewerConfig literals (auth options) need not set it. */
    legacyFixtureIModelId?: string
}

/** The known-live iTwin id (public identifier, safe in the browser). */
export const KNOWN_ITWIN_ID = 'bdf29ecd-b4a4-404d-861a-ac3061c7b12f'

export const DEFAULT_AUTHORITY = 'https://ims.bentley.com'
export const DEFAULT_SCOPE = 'itwin-platform'
export const DEFAULT_REDIRECT_URI = 'http://localhost:3000/signin-callback'
export const DEFAULT_POST_SIGNOUT_REDIRECT_URI = 'http://localhost:3000'

/** Names of env keys that MUST NEVER appear in the browser bundle (Sec 6/30). */
export const FORBIDDEN_BROWSER_ENV_KEYS = [
    'BENTLEY_CLIENT_SECRET',
    'BENTLEY_SERVICE_SECRET',
    'BENTLEY_ACCESS_TOKEN',
] as const

export class ViewerConfigError extends Error { }

function env(key: string): string | undefined {
    // import.meta.env is statically replaced by Vite; only VITE_-prefixed keys
    // are ever exposed to the browser bundle.
    const value = (import.meta.env as Record<string, string | undefined>)[key]
    return value && value.trim() !== '' ? value.trim() : undefined
}

/**
 * Build the public viewer configuration from browser-safe env values.
 * `clientId` and `iModelId` are required (no safe default exists); everything
 * else has a sensible public default. Throws `ViewerConfigError` with an
 * actionable message when a required value is missing — never silently falls
 * back to a fake id.
 */
export function getViewerConfig(): ViewerConfig {
    const clientId = env('VITE_BENTLEY_SPA_CLIENT_ID')
    if (!clientId) {
        throw new ViewerConfigError(
            'VITE_BENTLEY_SPA_CLIENT_ID is not set. Add the MRTway Development Viewer SPA client id to frontend/.env (browser-safe; NOT the service secret).',
        )
    }
    const fixtureIModelId = env('VITE_BENTLEY_IMODEL_ID')
    if (!fixtureIModelId) {
        throw new ViewerConfigError(
            'VITE_BENTLEY_IMODEL_ID is not set. Add the MRTway Hospital Campus Development iModel id to frontend/.env.',
        )
    }
    // PROJECT BIM SELECTION: which iModel /viewer opens is resolved by the pure
    // resolver with precedence URL_OVERRIDE > PERSISTED_SELECTION > PRODUCT_DEFAULT
    // (the Medical Clinic demo) > LEGACY_FALLBACK (the env fixture). This makes
    // the clinic the persistent normal-product default and removes the need for a
    // ?imodel= URL to return to it. The env fixture id is the legacy fallback.
    const configuredITwinId = env('VITE_BENTLEY_ITWIN_ID') ?? KNOWN_ITWIN_ID
    const override = readImodelOverrideFromUrl()
    const registry = buildProjectBimRegistry({ iTwinId: configuredITwinId, fixtureIModelId })
    const resolved = resolveActiveProjectBim({
        urlOverrideIModelId: override.iModelId,
        urlOverrideITwinId: override.iTwinId,
        persisted: loadPersistedActiveBim(),
        registry,
        legacyFallback: { iModelId: fixtureIModelId, iTwinId: configuredITwinId },
    })
    const iModelId = resolved.iModelId
    const iTwinId = resolved.iTwinId
    return {
        clientId,
        authority: env('VITE_BENTLEY_AUTHORITY') ?? DEFAULT_AUTHORITY,
        scope: env('VITE_BENTLEY_SCOPE') ?? DEFAULT_SCOPE,
        redirectUri: env('VITE_BENTLEY_REDIRECT_URI') ?? DEFAULT_REDIRECT_URI,
        postSignoutRedirectUri: env('VITE_BENTLEY_POST_SIGNOUT_REDIRECT_URI') ?? DEFAULT_POST_SIGNOUT_REDIRECT_URI,
        responseType: 'code',
        iTwinId,
        iModelId,
        legacyFixtureIModelId: fixtureIModelId,
    }
}

/** Conservative Bentley id shape: hex + dashes/underscores, bounded length. */
export function isPlausibleBentleyId(v: string): boolean {
    return /^[A-Za-z0-9\-_]{8,64}$/.test(v)
}

/**
 * Read an optional `?imodel=` / `?itwin=` override from the current URL. Returns
 * only values that pass `isPlausibleBentleyId`; otherwise undefined (fixture
 * default is used). Pure aside from reading window.location.
 */
export function readImodelOverrideFromUrl(): { iModelId?: string; iTwinId?: string } {
    if (typeof window === 'undefined' || !window.location?.search) return {}
    try {
        const params = new URLSearchParams(window.location.search)
        const rawImodel = params.get('imodel') ?? undefined
        const rawItwin = params.get('itwin') ?? undefined
        return {
            iModelId: rawImodel && isPlausibleBentleyId(rawImodel) ? rawImodel : undefined,
            iTwinId: rawItwin && isPlausibleBentleyId(rawItwin) ? rawItwin : undefined,
        }
    } catch {
        return {}
    }
}

/** True if the viewer configuration is present (used to gate the Sign-in CTA). */
export function isViewerConfigured(): boolean {
    try {
        getViewerConfig()
        return true
    } catch {
        return false
    }
}

/**
 * Security invariant (Sec 6/30): the SPA never requires a client secret and no
 * forbidden secret key is referenced. This is a structural guarantee — the SPA
 * config type has no `clientSecret` field, and only VITE_ public env is read.
 */
export const SPA_CLIENT_SECRET_REQUIRED = false
