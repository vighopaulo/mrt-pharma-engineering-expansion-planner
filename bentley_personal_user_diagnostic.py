"""Bentley Personal-Account iTwins API Diagnostic: interactive user OAuth
(Authorization Code + PKCE) diagnostic path, additive and separate from the
existing service-client (client-credentials) flow.

GOVERNANCE: this module NEVER modifies `bentley_itwin_client.
BentleyClientCredentialsTokenProvider` or any other existing service-client
code -- it only ADDS a second, independent `BentleyAccessTokenProvider`
implementation (the SAME Protocol already defined in `bentley_itwin_client.
py`) so the EXISTING `BentleyItwinClient`/`BentleyClientConfig` can be
reused verbatim with a personal-user token instead of a service token.
`SERVICE_CLIENT_AUTH_FLOW_CHANGED = NO` (verified by tests scanning
`bentley_itwin_client.py`'s own source for zero changes to that class).

AUDIT (section 1, performed before writing this module):
  - Johannes's reference repo (github.com/Johannes-lab/itwin-demo-apis) is a
    TypeScript/React SPA registered as a "Single Page Application" in the
    iTwin Developer Portal, with redirect URIs `http://localhost:5173/`
    (dev) and scope `itwin-platform` (per its own README's Auth Scopes
    table) -- it is NOT copied wholesale (different language/stack; this
    repository is Python). What IS reused conceptually: interactive
    browser sign-in via Bentley's own hosted `/connect/authorize` page,
    `itwin-platform` scope, and testing identity via `/users/me`.
  - Bentley's OWN official docs (developer.bentley.com/apis/overview/
    authorization/native-spa/ and /tutorials/authorize-native/) document
    the EXACT flow this module implements for a Python (non-browser-native)
    client: OAuth 2.0 Authorization Code flow with PKCE (RFC 7636) --
    `GET https://ims.bentley.com/connect/authorize` (response_type=code,
    client_id, redirect_uri, scope, code_challenge, code_challenge_method
    =S256) followed by `POST https://ims.bentley.com/connect/token`
    (grant_type=authorization_code, code, code_verifier, redirect_uri,
    client_id). `GET https://api.bentley.com/users/me` (enveloped
    `{"user": {"id","email","givenName","surname","organizationName"}}`,
    confirmed via developer.bentley.com/apis/users/operations/get-user/'s
    identical response shape) proves the token represents a human user.

REGISTRATION REQUIREMENT (section 1/10, CASE C): per Bentley's own docs,
"Service applications without user interaction do not require a redirect
URI" -- the EXISTING `BENTLEY_CLIENT_ID` (a service/client-credentials
application) therefore CANNOT be reused for this interactive flow. A
SEPARATE Native/SPA app registration (its own `client_id`, with a
registered redirect URI) is required. This module NEVER invents a redirect
URI (section 15) -- it reads `BENTLEY_USER_CLIENT_ID`/
`BENTLEY_USER_REDIRECT_URI` from the environment and fails explicitly
(`BentleyUserOAuthConfigurationError`) if either is absent, which IS the
mechanism by which `PERSONAL_USER_OAUTH_REGISTRATION_REQUIRED` is
determined (section 10 CASE C) -- never assumed true or false without
checking.

SECRETS (section 13): no password is ever accepted as a parameter anywhere
in this module (interactive sign-in happens in the user's own browser,
never through this code); no access/refresh token is ever printed or
logged by any function here.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Literal
import json as _json
import os

from bentley_itwin_client import BentleyTransport

BENTLEY_AUTHORIZE_ENDPOINT = "https://ims.bentley.com/connect/authorize"
BENTLEY_TOKEN_ENDPOINT = "https://ims.bentley.com/connect/token"
BENTLEY_USER_SCOPE = "itwin-platform offline_access"

BENTLEY_USER_LIVE_ENV_VARS = ("BENTLEY_USER_CLIENT_ID", "BENTLEY_USER_REDIRECT_URI")
"""Section 15: `BENTLEY_USER_CLIENT_ID`/`BENTLEY_USER_REDIRECT_URI` must
reference an ALREADY-REGISTERED Native/SPA app + its ALREADY-REGISTERED
redirect URI -- never invented by this module."""


class BentleyUserOAuthConfigurationError(RuntimeError):
    """Raised when the interactive user flow is attempted without a
    registered Native/SPA client_id/redirect_uri (section 10 CASE C)."""


def bentley_user_live_environment_available() -> bool:
    return all(os.environ.get(name) for name in BENTLEY_USER_LIVE_ENV_VARS)


# ---------------------------------------------------------------------------
# Section 1/15: PKCE (RFC 7636) -- generated locally, never transmitted
# except as the documented code_challenge/code_verifier parameters.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PkceChallenge:
    code_verifier: str
    code_challenge: str
    code_challenge_method: str = "S256"


def generate_pkce_challenge() -> PkceChallenge:
    """Section 15: a fresh, cryptographically random `code_verifier` per
    RFC 7636 (43-128 URL-safe characters) -- NEVER reused across requests."""
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return PkceChallenge(code_verifier=code_verifier, code_challenge=code_challenge)


def generate_oauth_state() -> str:
    return secrets.token_urlsafe(24)


def build_authorization_url(
    *, client_id: str, redirect_uri: str, pkce: PkceChallenge, state: str,
    scope: str = BENTLEY_USER_SCOPE, authorize_endpoint: str = BENTLEY_AUTHORIZE_ENDPOINT,
) -> str:
    """Section 1: byte-for-byte matches Bentley's documented native/SPA
    authorization request (developer.bentley.com/tutorials/authorize-native/)."""
    params = {
        "response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri, "scope": scope,
        "state": state, "code_challenge": pkce.code_challenge, "code_challenge_method": pkce.code_challenge_method,
    }
    return f"{authorize_endpoint}?{urllib.parse.urlencode(params)}"


def extract_authorization_code(redirect_response: str) -> str:
    """Section 1: accepts either the full redirect URL (`...?code=...`) or
    a bare authorization code -- never assumes a browser automatically
    delivered it (manual copy/paste is a documented, valid path)."""
    if "code=" in redirect_response:
        parsed = urllib.parse.urlparse(redirect_response)
        query = urllib.parse.parse_qs(parsed.query)
        if "code" in query:
            return query["code"][0]
    return redirect_response.strip()


def prompt_for_authorization_code_manually(prompt: str = "Paste the full redirect URL (or bare code) after completing Bentley sign-in: ") -> str:  # pragma: no cover -- interactive only
    return extract_authorization_code(input(prompt))


# ---------------------------------------------------------------------------
# Section 4/15: authorization-code -> token exchange (live network only).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BentleyUserTokenResult:
    """Section 13: the access/refresh token VALUES themselves are never
    printed by any function in this module -- callers must exercise the
    same discipline."""

    access_token: str
    refresh_token: str | None
    expires_in_seconds: int


def exchange_authorization_code_for_token(
    *, client_id: str, redirect_uri: str, code: str, code_verifier: str, token_endpoint: str = BENTLEY_TOKEN_ENDPOINT,
) -> BentleyUserTokenResult:  # pragma: no cover -- exercised only by opt-in live tests
    body = urllib.parse.urlencode({
        "client_id": client_id, "grant_type": "authorization_code", "code": code,
        "redirect_uri": redirect_uri, "code_verifier": code_verifier,
    }).encode("utf-8")
    request = urllib.request.Request(token_endpoint, data=body, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 -- live opt-in path only
        payload = _json.loads(response.read().decode("utf-8"))
    return BentleyUserTokenResult(
        access_token=str(payload["access_token"]), refresh_token=payload.get("refresh_token"),
        expires_in_seconds=int(payload.get("expires_in", 3600)),
    )


def refresh_bentley_user_token(
    *, client_id: str, redirect_uri: str, refresh_token: str, token_endpoint: str = BENTLEY_TOKEN_ENDPOINT,
) -> BentleyUserTokenResult:  # pragma: no cover -- exercised only by opt-in live tests
    body = urllib.parse.urlencode({
        "client_id": client_id, "grant_type": "refresh_token", "refresh_token": refresh_token, "redirect_uri": redirect_uri,
    }).encode("utf-8")
    request = urllib.request.Request(token_endpoint, data=body, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 -- live opt-in path only
        payload = _json.loads(response.read().decode("utf-8"))
    return BentleyUserTokenResult(
        access_token=str(payload["access_token"]), refresh_token=payload.get("refresh_token"),
        expires_in_seconds=int(payload.get("expires_in", 3600)),
    )


def run_interactive_user_authorization(
    *, client_id: str, redirect_uri: str, scope: str = BENTLEY_USER_SCOPE,
    authorization_code_provider: Callable[[str], str] | None = None,
) -> BentleyUserTokenResult:
    """Section 4/15: the ONE end-to-end interactive-sign-in entry point --
    builds the authorization URL, obtains the code (via the supplied
    provider, e.g. a manual-paste prompt or a local-redirect catcher; NEVER
    a hardcoded password, section 4), and exchanges it for a token.
    Requires `BENTLEY_USER_CLIENT_ID`/`BENTLEY_USER_REDIRECT_URI` semantics
    to be honored by the CALLER (this function itself never reads env vars
    -- see `bentley_user_live_environment_available()` for that gate)."""
    if authorization_code_provider is None:
        authorization_code_provider = prompt_for_authorization_code_manually  # pragma: no cover
    pkce = generate_pkce_challenge()
    state = generate_oauth_state()
    auth_url = build_authorization_url(client_id=client_id, redirect_uri=redirect_uri, pkce=pkce, state=state, scope=scope)
    code = extract_authorization_code(authorization_code_provider(auth_url))
    return exchange_authorization_code_for_token(client_id=client_id, redirect_uri=redirect_uri, code=code, code_verifier=pkce.code_verifier)


# ---------------------------------------------------------------------------
# Section 3: reuses the EXISTING `BentleyAccessTokenProvider` Protocol
# (bentley_itwin_client.py) -- never a second Protocol.
# ---------------------------------------------------------------------------


class BentleyUserAccessTokenProvider:
    """Wraps an ALREADY-OBTAINED interactive user access token (from
    `run_interactive_user_authorization`) -- this class itself never
    performs sign-in; it satisfies `bentley_itwin_client.
    BentleyAccessTokenProvider` structurally (duck-typed), so the EXISTING
    `BentleyItwinClient` can be constructed unchanged with a personal-user
    identity instead of the service-client identity."""

    def __init__(self, *, access_token: str) -> None:
        self._access_token = access_token

    def get_access_token(self) -> str:
        return self._access_token


# ---------------------------------------------------------------------------
# Section 6: /users/me identity confirmation -- reuses the EXISTING
# `BentleyTransport` Protocol's `.get()` method, never a new transport type.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BentleyUserProfile:
    user_id: str
    display_name: str | None
    email: str | None
    organization: str | None


def get_user_profile(*, transport: BentleyTransport, access_token: str) -> BentleyUserProfile:
    """Section 6: GET `/users/me` -- confirmed enveloped as `{"user": {...}}`
    per developer.bentley.com/apis/users/operations/get-user/'s identical
    response shape (`id`/`email`/`givenName`/`surname`/`organizationName`)."""
    payload = transport.get(path="/users/me", params=None, access_token=access_token)
    row = payload["user"]  # type: ignore[index]
    given_name = row.get("givenName")  # type: ignore[union-attr]
    surname = row.get("surname")  # type: ignore[union-attr]
    display_name = f"{given_name} {surname}".strip() if (given_name or surname) else None
    return BentleyUserProfile(
        user_id=str(row["id"]), display_name=display_name,  # type: ignore[union-attr]
        email=row.get("email"), organization=row.get("organizationName"),  # type: ignore[union-attr]
    )


ProfileLookupStatus = Literal["SUCCESS", "HTTP_404_NON_BLOCKING", "OTHER_FAILURE_NON_BLOCKING"]


@dataclass(frozen=True)
class UserProfileLookupResult:
    """Bypass build: `/users/me` is diagnostic-only, never a prerequisite
    for the actual iTwins-visibility comparison (section 3) -- any failure
    here is captured and reported, never raised past this function."""

    status: ProfileLookupStatus
    profile: BentleyUserProfile | None
    detail: str


def try_get_user_profile(*, transport: BentleyTransport, access_token: str) -> UserProfileLookupResult:
    """Section 3: non-blocking `/users/me` lookup -- catches ANY failure
    (HTTP or parsing) and reports it as data, never lets it abort the
    caller's subsequent iTwins API calls."""
    try:
        profile = get_user_profile(transport=transport, access_token=access_token)
        return UserProfileLookupResult(status="SUCCESS", profile=profile, detail="")
    except urllib.error.HTTPError as exc:
        status: ProfileLookupStatus = "HTTP_404_NON_BLOCKING" if exc.code == 404 else "OTHER_FAILURE_NON_BLOCKING"
        return UserProfileLookupResult(status=status, profile=None, detail=f"HTTP {exc.code}")
    except Exception as exc:  # noqa: BLE001 -- diagnostic-only, never re-raised (section 3)
        return UserProfileLookupResult(status="OTHER_FAILURE_NON_BLOCKING", profile=None, detail=f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Sections 9-10: auth-context comparison + decision logic -- pure, testable,
# NEVER fabricates a live result; classifications are computed only from
# caller-supplied (i.e. actually-observed) outcomes.
# ---------------------------------------------------------------------------

AuthContextOutcome = Literal["SUCCESS", "HTTP_404", "HTTP_401", "HTTP_403", "NOT_ATTEMPTED", "OTHER_FAILURE"]


@dataclass(frozen=True)
class AuthContextComparisonRow:
    operation: str
    service_client_result: AuthContextOutcome
    personal_user_result: AuthContextOutcome


def compare_auth_context_results(
    *, operation: str, service_client_result: AuthContextOutcome, personal_user_result: AuthContextOutcome,
) -> AuthContextComparisonRow:
    return AuthContextComparisonRow(operation=operation, service_client_result=service_client_result, personal_user_result=personal_user_result)


VisibilityDifference = Literal["CONFIRMED", "NOT_CONFIRMED", "NOT_DETERMINABLE"]


def determine_itwins_visibility_difference(
    *, personal_user_list_itwins: AuthContextOutcome, personal_user_get_itwin: AuthContextOutcome,
    service_client_list_itwins: AuthContextOutcome = "HTTP_404", service_client_get_itwin: AuthContextOutcome = "HTTP_404",
) -> VisibilityDifference:
    """Section 10 CASE A/B, plus bypass-build addition: `NOT_DETERMINABLE`
    when any input was never actually attempted -- never silently treated
    as a failure or a success. CONFIRMED only when the personal-user token
    succeeds at BOTH operations while the service client fails at both --
    any other fully-attempted combination is NOT_CONFIRMED (never a false
    positive)."""
    all_outcomes = (personal_user_list_itwins, personal_user_get_itwin, service_client_list_itwins, service_client_get_itwin)
    if any(outcome == "NOT_ATTEMPTED" for outcome in all_outcomes):
        return "NOT_DETERMINABLE"
    if (
        personal_user_list_itwins == "SUCCESS" and personal_user_get_itwin == "SUCCESS"
        and service_client_list_itwins != "SUCCESS" and service_client_get_itwin != "SUCCESS"
    ):
        return "CONFIRMED"
    return "NOT_CONFIRMED"


# ---------------------------------------------------------------------------
# Wire-request diagnostic (section 3/4): captures the EXACT sanitized
# request contract and the FULL response body/headers Bentley returns --
# diagnostic-only, never changes `BentleyHttpTransport`'s own behavior
# (section 5). `urllib`'s default `HTTPError` discards the response body
# unless it is explicitly read via `.read()`, which this function does.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RawHttpDiagnosticResult:
    """Every field here is either structural (method/scheme/host/path/
    query/header NAMES) or the sanitized response body -- the actual
    `Authorization` header VALUE is never captured or exposed anywhere in
    this dataclass (section 3: only `authorization_header_present: bool`)."""

    method: str
    scheme: str
    host: str
    path: str
    query: str
    accept_header: str
    prefer_header: str | None
    content_type_header: str | None
    authorization_header_present: bool
    status_code: int | None
    reason: str | None
    response_headers: dict[str, str]
    response_body_text: str
    response_json: object | None


def diagnostic_raw_get(
    *, url: str, access_token: str, accept: str = "application/vnd.bentley.itwin-platform.v2+json",
    extra_headers: dict[str, str] | None = None,
) -> RawHttpDiagnosticResult:
    """Section 3-4: sends ONE GET request byte-for-byte matching
    `bentley_itwin_client.BentleyHttpTransport.get()`'s own header
    construction (same Accept media-type, same `Bearer` Authorization
    scheme) so the captured request is provably identical to the one that
    is actually failing -- and, unlike that transport, reads and returns
    the FULL response body/headers on both success and `HTTPError`.
    `extra_headers` (e.g. `Prefer`) are added verbatim, letting a caller
    reproduce a documented third-party request contract exactly."""
    parsed = urllib.parse.urlparse(url)
    request = urllib.request.Request(url, method="GET")
    request.add_header("Authorization", f"Bearer {access_token}")
    request.add_header("Accept", accept)
    for header_name, header_value in (extra_headers or {}).items():
        request.add_header(header_name, header_value)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 -- diagnostic-only live path
            body_bytes = response.read()
            status_code = response.status
            reason = response.reason
            response_headers = dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        body_bytes = exc.read()
        status_code = exc.code
        reason = exc.reason
        response_headers = dict(exc.headers.items()) if exc.headers else {}
    body_text = body_bytes.decode("utf-8", errors="replace")
    response_json: object | None
    try:
        response_json = _json.loads(body_text) if body_text.strip() else None
    except ValueError:
        response_json = None
    sanitized_headers = {k: v for k, v in response_headers.items() if k.lower() not in ("authorization", "set-cookie")}
    return RawHttpDiagnosticResult(
        method="GET", scheme=parsed.scheme, host=parsed.netloc, path=parsed.path, query=parsed.query,
        accept_header=accept, prefer_header=request.get_header("Prefer"),
        content_type_header=request.get_header("Content-type"), authorization_header_present=True,
        status_code=status_code, reason=reason, response_headers=sanitized_headers, response_body_text=body_text,
        response_json=response_json,
    )


# ---------------------------------------------------------------------------
# Controlled experiment (sections 2/6): reproduces Johannes Renner's
# documented, actually-working `itwin-demo-apis` List iTwins request
# EXACTLY -- method/URL/Accept/Prefer are hardcoded module constants, never
# caller-parameterized, so this function can never be misused to test any
# other header/path combination within this build ("change all three known
# request differences together ONLY").
# ---------------------------------------------------------------------------

JOHANNES_EXACT_LIST_ITWINS_URL = "https://api.bentley.com/itwins?includeInactive=true"
JOHANNES_EXACT_ACCEPT_HEADER = "application/vnd.bentley.itwin-platform.v1+json"
JOHANNES_EXACT_PREFER_HEADER = "return=representation"


def diagnostic_johannes_exact_list_itwins(*, access_token: str) -> RawHttpDiagnosticResult:
    """Section 2: literally reproduces Johannes's known-working request --
    no trailing slash, `includeInactive=true` (never `displayName`), Accept
    v1 (never v2), `Prefer: return=representation` present (never omitted)."""
    return diagnostic_raw_get(
        url=JOHANNES_EXACT_LIST_ITWINS_URL, access_token=access_token, accept=JOHANNES_EXACT_ACCEPT_HEADER,
        extra_headers={"Prefer": JOHANNES_EXACT_PREFER_HEADER},
    )
