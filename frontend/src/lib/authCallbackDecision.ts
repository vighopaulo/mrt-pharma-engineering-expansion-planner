/**
 * authCallbackDecision — pure, Bentley-free decision seam for the /signin-callback
 * route. Distinguishes a legitimate first-time OIDC callback from a stale /
 * consumed callback URL being refreshed, so a hard refresh recovers to /viewer
 * instead of surfacing the raw "Could not load oidc settings from local storage"
 * library error.
 *
 * SECURITY: this module only inspects the PRESENCE of the one-time OIDC state
 * entry (metadata). It never reads, stores, or returns the authorization code,
 * tokens, PKCE verifier, or the state VALUE beyond deriving the storage key that
 * @itwin/browser-authorization itself uses.
 *
 * Storage-key derivation matches the installed @itwin/browser-authorization
 * static `handleSignInCallback` -> `loadSettingsFromStorage`, which reads
 * `localStorage["oidc." + <state>]`, where <state> is the URL `?state=` nonce.
 */

export type CallbackAction =
    | 'PROCESS_CALLBACK' // fresh callback: run handleSignInCallback()
    | 'RECOVER_STALE' // code/state present but one-time settings entry gone -> route to /viewer
    | 'RECOVER_EMPTY' // no code/state at all -> route to /viewer

/** The localStorage key the auth library expects for a given state nonce. */
export function oidcSettingsStorageKey(state: string): string {
    return `oidc.${state}`
}

/**
 * Decide how the callback route should behave.
 * @param params.code   the URL `code` param (or null)
 * @param params.state  the URL `state` param (or null)
 * @param params.settingsEntryPresent whether localStorage has the oidc.<state> entry
 */
export function decideCallbackAction(params: {
    code: string | null
    state: string | null
    settingsEntryPresent: boolean
}): CallbackAction {
    const { code, state, settingsEntryPresent } = params
    if (!code || !state) return 'RECOVER_EMPTY'
    if (!settingsEntryPresent) return 'RECOVER_STALE'
    return 'PROCESS_CALLBACK'
}

/**
 * Read the callback decision from the live browser environment (URL + storage).
 * Isolated here so the component stays thin and the decision is unit-testable.
 */
export function readCallbackActionFromEnv(
    loc: { search: string } = window.location,
    store: Pick<Storage, 'getItem'> = window.localStorage,
): { action: CallbackAction; hasCode: boolean; hasState: boolean; settingsEntryPresent: boolean } {
    const params = new URLSearchParams(loc.search)
    const code = params.get('code')
    const state = params.get('state')
    const settingsEntryPresent = !!state && store.getItem(oidcSettingsStorageKey(state)) !== null
    return {
        action: decideCallbackAction({ code, state, settingsEntryPresent }),
        hasCode: !!code,
        hasState: !!state,
        settingsEntryPresent,
    }
}
