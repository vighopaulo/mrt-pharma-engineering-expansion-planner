/**
 * /signin-callback — Bentley SPA (PKCE) redirect handler (Sec 11).
 *
 * This route component is PURE (no @itwin import) so unit tests can render it.
 * The actual PKCE code-exchange is performed by the lazy-loaded
 * `SigninCallbackHandler` (in components/viewer), which is the isolated
 * boundary that imports `@itwin/browser-authorization`. No token / refresh
 * token / Authorization header is logged.
 */
import { Suspense, lazy } from 'react'

const SigninCallbackHandler = lazy(() => import('../components/viewer/SigninCallbackHandler'))

export function SigninCallback() {
    return (
        <main style={{ padding: '2rem' }}>
            <h1>Bentley sign-in</h1>
            <Suspense fallback={<p>Completing Bentley authentication…</p>}>
                <SigninCallbackHandler />
            </Suspense>
        </main>
    )
}
