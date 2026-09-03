# MRT Pharma — Page-Refresh Authentication Diagnosis (DIAGNOSIS ONLY)

Scope: DIAGNOSIS ONLY. No auth code was modified. `AUTH_FIX_IMPLEMENTED = NO`.
This documents the exact failure of a hard refresh on `/signin-callback` and a
recommended narrow correction for a future FIX prompt.

## Manual evidence (accepted)

After refreshing the viewer, the browser reached `/signin-callback` with
`code=<authorization code>` and `state=<state value>` in the query string, but
the page rendered: "Bentley sign-in / Sign-in could not complete: Could not load
oidc settings from local storage. Ensure the client is configured properly."
```
PAGE_REFRESH_AUTH_BUG        = CONFIRMED
REFRESH_FAILURE_ROUTE        = /signin-callback
OIDC_CODE_PRESENT            = YES
OIDC_STATE_PRESENT           = YES
AUTHORIZATION_REDIRECT_RETURNED = YES
OIDC_SETTINGS_REHYDRATION    = FAIL
```

## Source investigation

```
SIGNIN_CALLBACK_COMPONENT_FILE       = frontend/src/routes/SigninCallback.tsx
                                       -> frontend/src/components/viewer/SigninCallbackHandler.tsx (lazy, imports @itwin)
SIGNIN_CALLBACK_COMPLETION_API       = BrowserAuthorizationClient.handleSignInCallback()  (STATIC, configuration-less)
SIGNIN_CALLBACK_AUTH_CLIENT_SOURCE   = a throwaway `new BrowserAuthorizationClient({})` created INSIDE the static method
SIGNIN_CALLBACK_CLIENT_CREATION_PATH = library-internal (not the app's memoized viewer client)
SIGNIN_CALLBACK_STORAGE_DEPENDENCY   = window.localStorage key `oidc.<state-nonce>`

AUTH_CLIENT_FACTORY                  = frontend/src/components/viewer/LiveItwinViewer.tsx (useMemo over primitive config values)
AUTH_CLIENT_MEMOIZATION              = React useMemo keyed on clientId/authority/scope/redirectUri/postSignoutRedirectUri
AUTH_CLIENT_CONFIG_SOURCE            = getViewerConfig() / browserAuthClientOptions() (env-derived; redirectUri = http://localhost:3000/signin-callback)
AUTH_CLIENT_REHYDRATION_ON_HARD_REFRESH = the /viewer client is recreated on load; the /signin-callback route does NOT create the app client at all

OIDC_SETTINGS_ERROR_SOURCE_FILE      = node_modules/@itwin/browser-authorization/lib/cjs/Client.js
OIDC_SETTINGS_ERROR_SOURCE_PACKAGE   = @itwin/browser-authorization@2.0.4 (depends on oidc-client-ts@^3.5.0, resolved 3.5.0)
OIDC_SETTINGS_EXPECTED_STORAGE_KEY   = `oidc.${state}` where state = URL ?state= nonce
OIDC_SETTINGS_EXPECTED_STORAGE_TYPE  = LOCAL_STORAGE (library default; matches static handleSignInCallback default store)
```

Exact library logic (`Client.js`, static `handleSignInCallback(store = localStorage)`
→ `loadSettingsFromStorage`):
1. read `state` nonce from `window.location` query;
2. `store.getItem("oidc." + nonce)`;
3. if absent → throw "Could not load oidc settings from local storage…".

The `oidc.<nonce>` entry is written by `oidc-client-ts` when a sign-in redirect
is INITIATED. In this app that happens ONLY on the `/viewer` route
(`LiveItwinViewer` calls `authClient.signInRedirect('/viewer')` after a failed
silent sign-in). The `/signin-callback` route never writes it — it only calls
the static completer.

## Root cause

```
PAGE_REFRESH_AUTH_FAILURE_CLASS = E (CALLBACK_ROUTE_BOOTSTRAP_ORDER_DEFECT)
                                  + G (REFRESH_TRIGGERS_HANDLING_OF_A_STALE/CONSUMED CALLBACK)
```
`PAGE_REFRESH_AUTH_ROOT_CAUSE`: A hard refresh of `/signin-callback?code=…&state=<nonce>`
re-invokes `BrowserAuthorizationClient.handleSignInCallback()`, which requires
`localStorage["oidc.<nonce>"]`. That state entry is a ONE-TIME artifact written
by `signinRedirect` and consumed/removed by the first successful callback
completion (oidc-client-ts state-store semantics). On refresh no fresh redirect
was initiated, so the entry is gone (or was never present for this browser
session), and the library throws. The bug is that the callback route treats a
re-loaded, already-consumed callback URL as if it were a live first-time
callback, and surfaces the raw library error instead of recognizing a
stale/absent OIDC state and routing the user onward (e.g. to `/viewer`, which
would silently sign in or start a fresh redirect).

Not the cause: PKCE config is correct; the redirect URI matches; the app's
viewer client is properly configured. The failure is specific to re-running the
completion against consumed one-time state on a manual refresh of the callback
URL.

## Recommended NARROW correction (for a future FIX prompt — NOT applied)

In `SigninCallbackHandler`, before/around calling `handleSignInCallback()`,
detect the "no oidc settings for this state" condition and treat a stale/absent
callback as a non-fatal redirect to `/viewer` rather than an error screen:
- If `localStorage["oidc.<state>"]` is absent (or the library throws this
  specific settings error), navigate to `/viewer` (replace) and let the normal
  silent-sign-in / fresh-redirect path run — instead of rendering the raw error.
- Optionally strip the consumed `code`/`state` query params when redirecting so
  a subsequent refresh cannot resubmit them.
This stays within the callback component; it does NOT change PKCE, the auth
client factory/memoization, storage scope, or the redirect flow. It only makes a
refreshed/stale callback resolve gracefully.

## Systems that must remain closed (unchanged in any fix)

BrowserAuthorizationClient construction/options, PKCE, auth-client memoization,
StrictMode auth handling, storage scope (localStorage default), redirect URIs,
viewer lifecycle, ViewCreator3d, camera, ViewFlags, transparency, worker/WASM.

## Verification for this diagnosis pass

No runtime code changed for auth. Machine verification (typecheck / tests /
build / assets) run as part of the completion pass; see the spatial report.
```
AUTH_FIX_IMPLEMENTED = NO
AUTH_FLOW_CHANGED = NO   PKCE_CHANGED = NO   SIGNIN_CALLBACK_BEHAVIOR_CHANGED = NO
AUTH_CLIENT_MEMOIZATION_CHANGED = NO   VIEWER_LIFECYCLE_CHANGED = NO
IMODEL_MODIFIED = NO   BENTLEY_CHANGESET_CREATED = NO   BENTLEY_RESOURCE_MODIFIED = NO
CHECKPOINT = HOLD_FOR_AUTH_DIAGNOSIS_REVIEW
```
