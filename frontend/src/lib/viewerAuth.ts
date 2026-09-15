/**
 * Basic Bentley 3D Viewer — browser auth state machine + PKCE client factory.
 *
 * The `BrowserAuthorizationClient` (from `@itwin/browser-authorization`) is
 * imported lazily inside `createBrowserAuthClient` so unit tests (which never
 * perform real auth) do not require the heavy `@itwin/*` packages. The auth
 * STATE MACHINE and its transitions are pure and fully unit-tested.
 *
 * SECURITY: no token / refresh token / Authorization header is ever logged or
 * returned by this module (Sec 11).
 */

import type { ViewerConfig } from './viewerConfig'

export type AuthState = 'NOT_AUTHENTICATED' | 'AUTHENTICATING' | 'AUTHENTICATED' | 'AUTH_ERROR'

export type AuthEvent =
    | { type: 'SIGN_IN_REQUESTED' }
    | { type: 'AUTH_SUCCEEDED' }
    | { type: 'AUTH_FAILED'; message: string }
    | { type: 'SIGN_OUT' }

export interface AuthMachineState {
    state: AuthState
    errorMessage: string | null
}

export const INITIAL_AUTH_STATE: AuthMachineState = {
    state: 'NOT_AUTHENTICATED',
    errorMessage: null,
}

/** Pure transition function for the auth state machine (Sec 12). */
export function authReducer(current: AuthMachineState, event: AuthEvent): AuthMachineState {
    switch (event.type) {
        case 'SIGN_IN_REQUESTED':
            return { state: 'AUTHENTICATING', errorMessage: null }
        case 'AUTH_SUCCEEDED':
            return { state: 'AUTHENTICATED', errorMessage: null }
        case 'AUTH_FAILED':
            return { state: 'AUTH_ERROR', errorMessage: sanitizeAuthError(event.message) }
        case 'SIGN_OUT':
            return { state: 'NOT_AUTHENTICATED', errorMessage: null }
        default:
            return current
    }
}

/**
 * Never surface a raw token or Authorization header in an error message
 * (Sec 11/26). Redact anything that looks like a bearer token.
 */
export function sanitizeAuthError(message: string): string {
    return message
        .replace(/Bearer\s+[A-Za-z0-9._-]+/gi, 'Bearer [redacted]')
        .replace(/eyJ[A-Za-z0-9._-]{10,}/g, '[redacted-token]')
        .replace(/(access_token|refresh_token|id_token)=[^&\s]+/gi, '$1=[redacted]')
}

export interface BrowserAuthClientOptions {
    clientId: string
    authority: string
    scope: string
    redirectUri: string
    postSignoutRedirectUri: string
    responseType: 'code'
}

/** The exact PKCE options passed to BrowserAuthorizationClient (no secret). */
export function browserAuthClientOptions(config: ViewerConfig): BrowserAuthClientOptions {
    return {
        clientId: config.clientId,
        authority: config.authority,
        scope: config.scope,
        redirectUri: config.redirectUri,
        postSignoutRedirectUri: config.postSignoutRedirectUri,
        responseType: 'code', // Authorization Code + PKCE; NO client secret
    }
}

// NOTE: the real `BrowserAuthorizationClient` is constructed ONLY inside
// `components/viewer/LiveItwinViewer.tsx` (the isolated boundary that imports
// `@itwin/*`). This module stays pure so unit tests never resolve those
// packages. `browserAuthClientOptions` above is the exact PKCE option set that
// component passes to the client.

export const SPA_USES_PKCE = true

// ---------------------------------------------------------------------------
// EVI-MA-03 — token-readiness decision (pure, Bentley-free, testable)
// ---------------------------------------------------------------------------

/**
 * Whether the viewer may mount `<Viewer>`. A silent sign-in can RESOLVE without
 * a usable access token (stale/expired session, or the client reports authorized
 * before a token is actually available). Mounting the web-viewer in that state
 * shows the raw library string `baseViewerInitializer.validTokenNeeded` instead
 * of the 3D BIM. So we require a genuinely non-empty access token before
 * mounting; otherwise we must RE-AUTHENTICATE (interactive redirect).
 */
export type TokenReadiness = 'READY' | 'NEEDS_REAUTH'

/** Seconds before actual expiry at which a token is treated as no longer usable
 * (renew proactively; never mount the Viewer with an imminently-invalid token). */
export const TOKEN_EXPIRY_SKEW_MS = 30_000

/**
 * Decide readiness from the post-silent-sign-in signals. `accessToken` is the
 * value returned by `authClient.getAccessToken()` (may be empty). This function
 * NEVER stores, logs, or returns the token — it only inspects whether a
 * non-empty bearer value is present. A token is considered present when it is a
 * non-empty string (optionally already prefixed with "Bearer ").
 */
export function decideTokenReadiness(input: {
    authorized: boolean
    hasSignedIn: boolean
    accessToken: string | undefined | null
    expiresAt?: Date | number | undefined
    now?: number
    skewMs?: number
}): TokenReadiness {
    const token = (input.accessToken ?? '').trim()
    if (!input.authorized || !input.hasSignedIn) return 'NEEDS_REAUTH'
    if (token.length === 0) return 'NEEDS_REAUTH'
    // An access token whose expiry is already in the past (or within the skew
    // window) is not usable.
    if (input.expiresAt !== undefined) {
        const exp = input.expiresAt instanceof Date ? input.expiresAt.getTime() : Number(input.expiresAt)
        const now = input.now ?? Date.now()
        const skew = input.skewMs ?? TOKEN_EXPIRY_SKEW_MS
        if (Number.isFinite(exp) && exp - skew <= now) return 'NEEDS_REAUTH'
    }
    return 'READY'
}

// ---------------------------------------------------------------------------
// EVI-MA-03A — ONE authoritative viewer-auth state machine (pure, testable)
// ---------------------------------------------------------------------------

/**
 * The single source of truth for whether the Bentley `<Viewer>` may mount. No
 * other flag (ready/authenticated/hasSignedIn/isAuthorized/tokenPresent) is
 * allowed to drift independently — the component derives everything from this.
 */
export type ViewerAuthState =
    | 'CONFIG_MISSING'
    | 'INITIALIZING'
    | 'AUTHENTICATING'
    | 'TOKEN_READY'
    | 'REAUTH_REQUIRED'
    | 'ERROR'

/** The `<Viewer>` may mount ONLY in TOKEN_READY. */
export function viewerMayMount(state: ViewerAuthState): boolean {
    return state === 'TOKEN_READY'
}

export type ViewerAuthEvent =
    | { type: 'CONFIG_MISSING' }
    | { type: 'INITIALIZE' }
    | { type: 'AUTHENTICATING' }
    | { type: 'TOKEN_VERIFIED' } // getAccessToken succeeded + not expired
    | { type: 'TOKEN_NOT_READY' } // silent resolved but no usable token / expired
    | { type: 'AUTH_ERROR' }
    | { type: 'RECONNECT_REQUESTED' } // user clicked Reconnect Bentley 3D
    | { type: 'TOKEN_LOST' } // token expired / became invalid after TOKEN_READY

/**
 * Pure transition for the viewer-auth state machine. Deterministic; no side
 * effects; no secrets. Key invariants:
 *   - TOKEN_READY is only reachable via TOKEN_VERIFIED.
 *   - TOKEN_LOST while TOKEN_READY -> REAUTH_REQUIRED (never leave a dead Viewer
 *     showing the raw `validTokenNeeded`).
 *   - RECONNECT_REQUESTED -> AUTHENTICATING (drive the existing PKCE flow).
 */
export function viewerAuthReducer(current: ViewerAuthState, event: ViewerAuthEvent): ViewerAuthState {
    switch (event.type) {
        case 'CONFIG_MISSING':
            return 'CONFIG_MISSING'
        case 'INITIALIZE':
            return current === 'CONFIG_MISSING' ? current : 'INITIALIZING'
        case 'AUTHENTICATING':
            return 'AUTHENTICATING'
        case 'TOKEN_VERIFIED':
            return 'TOKEN_READY'
        case 'TOKEN_NOT_READY':
            return 'REAUTH_REQUIRED'
        case 'AUTH_ERROR':
            return 'ERROR'
        case 'RECONNECT_REQUESTED':
            return 'AUTHENTICATING'
        case 'TOKEN_LOST':
            // Demote out of TOKEN_READY so the Viewer is unmounted and the app
            // shows a reconnect affordance instead of the raw Bentley string.
            return current === 'TOKEN_READY' ? 'REAUTH_REQUIRED' : current
        default:
            return current
    }
}
