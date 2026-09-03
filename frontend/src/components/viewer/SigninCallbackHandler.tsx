/**
 * Isolated PKCE callback handler — imports `@itwin/browser-authorization`
 * (lazy-only; excluded from unit tests). Completes the Authorization Code +
 * PKCE exchange and returns the user to the viewer. No token is logged.
 *
 * Hard-refresh recovery: a refresh of /signin-callback re-loads a callback URL
 * whose one-time OIDC state (`localStorage["oidc.<state>"]`) may already have
 * been consumed by the first successful completion. Re-running the completer
 * then throws "Could not load oidc settings from local storage". We detect that
 * case via a pure decision seam (readCallbackActionFromEnv) and recover to
 * /viewer instead of surfacing the raw error. A genuine first-time callback is
 * still completed normally; a genuine completion FAILURE (when settings ARE
 * present) is preserved, not swallowed.
 */
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BrowserAuthorizationClient } from '@itwin/browser-authorization'
import { sanitizeAuthError } from '../../lib/viewerAuth'
import { readCallbackActionFromEnv } from '../../lib/authCallbackDecision'

export default function SigninCallbackHandler() {
    const navigate = useNavigate()
    const [error, setError] = useState<string | null>(null)
    // StrictMode / re-entry guard: complete the callback at most once per mount
    // lifetime of this handler (dev StrictMode double-invokes effects).
    const startedRef = useRef(false)

    useEffect(() => {
        if (startedRef.current) return
        startedRef.current = true
        let cancelled = false
        void (async () => {
            const { action, hasCode, hasState, settingsEntryPresent } = readCallbackActionFromEnv()
            if (import.meta.env.DEV) {
                // Bounded, secret-free: presence metadata only (never code/state/token).
                console.info('[auth-callback] stage=DECIDE hasCode=%s hasState=%s stateEntryPresent=%s decision=%s',
                    String(hasCode), String(hasState), String(settingsEntryPresent), action)
            }

            if (action !== 'PROCESS_CALLBACK') {
                // RECOVER_EMPTY (no code/state) or RECOVER_STALE (consumed one-time
                // state on refresh): do NOT replay the callback; route to /viewer,
                // whose normal auth bootstrap uses the existing session or starts a
                // fresh sign-in as needed. Use replace so the stale callback URL
                // leaves history.
                if (import.meta.env.DEV) console.info('[auth-callback] stage=RECOVER decision=%s -> /viewer', action)
                if (!cancelled) navigate('/viewer', { replace: true })
                return
            }

            try {
                if (import.meta.env.DEV) console.info('[auth-callback] stage=COMPLETE_START')
                // Static, configuration-less completer: pulls PKCE config/verifier
                // from storage using the OIDC state nonce in the URL.
                await BrowserAuthorizationClient.handleSignInCallback()
                if (import.meta.env.DEV) console.info('[auth-callback] stage=COMPLETE_SUCCESS RETURN_ROUTE=/viewer')
                if (!cancelled) navigate('/viewer', { replace: true })
            } catch (e) {
                // Settings WERE present, so this is a genuine callback/token/
                // validation failure — preserve it, do not silently recover.
                const msg = sanitizeAuthError(e instanceof Error ? e.message : String(e))
                if (import.meta.env.DEV) console.error('[auth-callback] stage=COMPLETE_FAILURE', msg)
                if (!cancelled) setError(msg)
            }
        })()
        return () => {
            cancelled = true
        }
    }, [navigate])

    return error ? <p role="alert">Sign-in could not complete: {error}</p> : <p>Completing Bentley authentication…</p>
}
