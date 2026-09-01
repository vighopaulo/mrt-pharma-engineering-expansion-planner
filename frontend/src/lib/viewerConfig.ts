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

export interface ViewerConfig {
    clientId: string
    authority: string
    scope: string
    redirectUri: string
    postSignoutRedirectUri: string
    responseType: 'code'
    iTwinId: string
    iModelId: string
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

export class ViewerConfigError extends Error {}

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
    const iModelId = env('VITE_BENTLEY_IMODEL_ID')
    if (!iModelId) {
        throw new ViewerConfigError(
            'VITE_BENTLEY_IMODEL_ID is not set. Add the MRTway Hospital Campus Development iModel id to frontend/.env.',
        )
    }
    return {
        clientId,
        authority: env('VITE_BENTLEY_AUTHORITY') ?? DEFAULT_AUTHORITY,
        scope: env('VITE_BENTLEY_SCOPE') ?? DEFAULT_SCOPE,
        redirectUri: env('VITE_BENTLEY_REDIRECT_URI') ?? DEFAULT_REDIRECT_URI,
        postSignoutRedirectUri: env('VITE_BENTLEY_POST_SIGNOUT_REDIRECT_URI') ?? DEFAULT_POST_SIGNOUT_REDIRECT_URI,
        responseType: 'code',
        iTwinId: env('VITE_BENTLEY_ITWIN_ID') ?? KNOWN_ITWIN_ID,
        iModelId,
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
