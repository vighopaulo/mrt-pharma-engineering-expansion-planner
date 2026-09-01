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
