/**
 * Isolated PKCE callback handler — imports `@itwin/browser-authorization`
 * (lazy-only; excluded from unit tests). Completes the Authorization Code +
 * PKCE exchange and returns the user to the viewer. No token is logged.
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BrowserAuthorizationClient } from '@itwin/browser-authorization'
import { sanitizeAuthError } from '../../lib/viewerAuth'

export default function SigninCallbackHandler() {
    const navigate = useNavigate()
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        let cancelled = false
        void (async () => {
            try {
                if (import.meta.env.DEV) console.info('[bentley-auth] AUTH_CALLBACK_ENTERED')
                // v2.0.4: the STATIC, configuration-less callback completer.
                // It pulls the PKCE config/verifier from storage (localStorage,
                // the library default) using the OIDC state nonce in the URL —
                // so we do NOT need to reconstruct the client here (which would
                // lose PKCE/session state). NOTE the capital "In": the instance
                // method is handleSigninCallback(); the static is
                // handleSignInCallback().
                await BrowserAuthorizationClient.handleSignInCallback()
                if (import.meta.env.DEV) console.info('[bentley-auth] AUTH_CALLBACK_COMPLETED RETURN_ROUTE=/viewer')
                if (!cancelled) navigate('/viewer', { replace: true })
            } catch (e) {
                const msg = sanitizeAuthError(e instanceof Error ? e.message : String(e))
                if (import.meta.env.DEV) console.error('[bentley-auth] AUTH_ERROR_CODE=callback_failed', msg)
                if (!cancelled) setError(msg)
            }
        })()
        return () => {
            cancelled = true
        }
    }, [navigate])

    return error ? <p role="alert">Sign-in could not complete: {error}</p> : <p>Completing Bentley authentication…</p>
}
