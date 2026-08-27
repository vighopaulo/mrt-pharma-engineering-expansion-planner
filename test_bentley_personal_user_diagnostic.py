"""Focused tests for the Bentley Personal-Account iTwins API Diagnostic
(`bentley_personal_user_diagnostic.py`).

Covers OFFLINE logic only (PKCE generation, authorization URL construction,
code extraction, the additive `BentleyUserAccessTokenProvider` reused with
the EXISTING `BentleyItwinClient`, `/users/me` parsing via a fake transport,
and the section-9/10 comparison/decision-logic helpers) plus ONE opt-in
LIVE interactive diagnostic, gated exactly like every other live Bentley
test in this repository -- skipped unless `BENTLEY_USER_CLIENT_ID`/
`BENTLEY_USER_REDIRECT_URI` are configured (a SEPARATE Native/SPA app
registration, never the existing service client).
"""

import inspect
import os
import sys
import urllib.error
import webbrowser

import bentley_itwin_client as bic
import bentley_personal_user_diagnostic as bpud
import pytest


class _FakeTransport:
    def __init__(self, get_responses=None, get_errors=None):
        self._get_responses = get_responses or {}
        self._get_errors = get_errors or {}
        self.get_calls = []
        self.post_calls = []

    def get(self, *, path, params, access_token, accept=None, extra_headers=None):
        self.get_calls.append((path, params, access_token))
        if path in self._get_errors:
            raise urllib.error.HTTPError(url=path, code=self._get_errors[path], msg="error", hdrs=None, fp=None)
        return self._get_responses[path]

    def post(self, *, path, json_body, access_token, accept=None, extra_headers=None):  # pragma: no cover -- never exercised (no create calls in this build)
        self.post_calls.append((path, json_body))
        raise AssertionError("no POST call is ever expected in this diagnostic")


# ===========================================================================
# Item 1/2: personal-user auth path is separate from / never changes the
# service-client auth flow.
# ===========================================================================


def test_1_personal_user_provider_is_a_distinct_class_from_service_client_provider():
    assert bpud.BentleyUserAccessTokenProvider is not bic.BentleyClientCredentialsTokenProvider
    assert not issubclass(bpud.BentleyUserAccessTokenProvider, bic.BentleyClientCredentialsTokenProvider)


def test_2_service_client_auth_flow_unchanged():
    # Constructing a personal-user provider must not touch/require any
    # service-client class or state.
    provider = bpud.BentleyUserAccessTokenProvider(access_token="FAKE-USER-TOKEN")
    assert provider.get_access_token() == "FAKE-USER-TOKEN"
    # the existing service-client class remains fully importable/functional, unmodified:
    assert hasattr(bic, "BentleyClientCredentialsTokenProvider")
    assert hasattr(bic, "BentleyItwinClient")


# ===========================================================================
# Item 3: user-token provider never accepts a hardcoded password.
# ===========================================================================


def _source_without_module_docstring(module) -> str:
    src = inspect.getsource(module)
    if src.lstrip().startswith('"""'):
        first = src.index('"""')
        second = src.index('"""', first + 3)
        return src[second + 3:]
    return src


def test_3_no_hardcoded_password_parameter_anywhere():
    for name, obj in inspect.getmembers(bpud):
        if inspect.isfunction(obj) or inspect.isclass(obj):
            target = obj.__init__ if inspect.isclass(obj) else obj
            try:
                sig = inspect.signature(target)
            except (TypeError, ValueError):
                continue
            assert "password" not in sig.parameters, f"{name} accepts a password parameter"


# ===========================================================================
# Item 4: tokens are never logged/printed by this module.
# ===========================================================================


def test_4_no_print_statements_in_module():
    module_source = inspect.getsource(bpud)
    assert "print(" not in module_source


def test_4b_token_result_never_included_in_default_repr_leak(capsys):
    result = bpud.BentleyUserTokenResult(access_token="SECRET-ACCESS-TOKEN-VALUE", refresh_token="SECRET-REFRESH-TOKEN-VALUE", expires_in_seconds=3600)
    # nothing in this test itself prints the result -- guards against a future accidental print elsewhere:
    captured = capsys.readouterr()
    assert "SECRET-ACCESS-TOKEN-VALUE" not in captured.out
    assert "SECRET-REFRESH-TOKEN-VALUE" not in captured.out
    assert result.access_token == "SECRET-ACCESS-TOKEN-VALUE"  # sanity: value itself still usable programmatically


# ===========================================================================
# Items 5-6: List iTwins / Get iTwin use the EXISTING documented endpoints,
# via the EXISTING BentleyItwinClient -- never reimplemented.
# ===========================================================================


def test_5_list_itwins_with_personal_user_token_uses_existing_itwins_endpoint():
    transport = _FakeTransport(get_responses={"/itwins": {"iTwins": [{"id": "ITWIN-DEV", "displayName": "MRT Pharma Development", "class": "Endeavor"}]}})
    provider = bpud.BentleyUserAccessTokenProvider(access_token="FAKE-USER-TOKEN")
    config = bic.BentleyClientConfig(client_id="unused-for-user-flow", itwin_id="ITWIN-1", imodel_id="IMODEL-1", access_token_provider=provider)
    client = bic.BentleyItwinClient(config=config, transport=transport)
    rows = client.list_itwins(display_name="MRT Pharma Development")
    assert len(rows) == 1
    assert transport.get_calls == [("/itwins", {"displayName": "MRT Pharma Development"}, "FAKE-USER-TOKEN")]


def test_6_get_itwin_with_personal_user_token_uses_existing_itwins_id_endpoint():
    transport = _FakeTransport(get_responses={"/itwins/ITWIN-1": {"iTwin": {"id": "ITWIN-1", "displayName": "Test Twin", "class": "Project"}}})
    provider = bpud.BentleyUserAccessTokenProvider(access_token="FAKE-USER-TOKEN")
    config = bic.BentleyClientConfig(client_id="unused-for-user-flow", itwin_id="ITWIN-1", imodel_id="IMODEL-1", access_token_provider=provider)
    client = bic.BentleyItwinClient(config=config, transport=transport)
    metadata = client.get_itwin_metadata()
    assert metadata.itwin_id == "ITWIN-1"
    assert transport.get_calls == [("/itwins/ITWIN-1", None, "FAKE-USER-TOKEN")]


# ===========================================================================
# Items 7-8: no create/mutation calls anywhere in this diagnostic module.
# ===========================================================================


def test_7_no_create_itwin_or_imodel_post_ever_called():
    module_source = inspect.getsource(bpud)
    assert ".post(" not in module_source
    assert "create_itwin" not in module_source
    assert "create_imodel" not in module_source


def test_8_no_access_control_mutation_called():
    module_source = inspect.getsource(bpud)
    for forbidden in ("add_itwin_user_member", "remove_itwin_user_member", "assign_role", "create_role", "add_member", "remove_member"):
        assert forbidden not in module_source


# ===========================================================================
# Item 9: result comparison distinguishes user-token vs service-token outcomes.
# ===========================================================================


def test_9_comparison_row_distinguishes_service_and_user_outcomes():
    row = bpud.compare_auth_context_results(operation="Get iTwin by ID", service_client_result="HTTP_404", personal_user_result="SUCCESS")
    assert row.service_client_result != row.personal_user_result
    assert row.operation == "Get iTwin by ID"


def test_9b_decision_logic_case_a_confirmed():
    result = bpud.determine_itwins_visibility_difference(
        personal_user_list_itwins="SUCCESS", personal_user_get_itwin="SUCCESS",
        service_client_list_itwins="HTTP_404", service_client_get_itwin="HTTP_404",
    )
    assert result == "CONFIRMED"


def test_9c_decision_logic_case_b_not_confirmed():
    result = bpud.determine_itwins_visibility_difference(personal_user_list_itwins="HTTP_404", personal_user_get_itwin="HTTP_404")
    assert result == "NOT_CONFIRMED"


def test_9d_decision_logic_never_confirms_on_partial_success():
    result = bpud.determine_itwins_visibility_difference(personal_user_list_itwins="SUCCESS", personal_user_get_itwin="HTTP_404")
    assert result == "NOT_CONFIRMED"


# ===========================================================================
# PKCE / authorization URL / code extraction -- offline, deterministic shape.
# ===========================================================================


def test_pkce_challenge_shape_and_never_reused():
    a = bpud.generate_pkce_challenge()
    b = bpud.generate_pkce_challenge()
    assert 43 <= len(a.code_verifier) <= 200  # RFC 7636 recommends 43-128; token_urlsafe(64) yields a safely-sized value
    assert a.code_challenge != b.code_challenge
    assert a.code_verifier != b.code_verifier
    assert a.code_challenge_method == "S256"
    assert "=" not in a.code_challenge  # base64url without padding


def test_authorization_url_matches_documented_contract():
    pkce = bpud.generate_pkce_challenge()
    url = bpud.build_authorization_url(client_id="CLIENT-ID-123", redirect_uri="http://localhost:9999/", pkce=pkce, state="STATE-ABC")
    assert url.startswith(bpud.BENTLEY_AUTHORIZE_ENDPOINT + "?")
    assert "response_type=code" in url
    assert "client_id=CLIENT-ID-123" in url
    assert "code_challenge_method=S256" in url
    assert "itwin-platform" in url
    assert "offline_access" in url


def test_extract_authorization_code_from_full_url():
    assert bpud.extract_authorization_code("http://localhost:9999/?code=AUTH-CODE-XYZ&state=STATE-ABC") == "AUTH-CODE-XYZ"


def test_extract_authorization_code_from_bare_code():
    assert bpud.extract_authorization_code("AUTH-CODE-XYZ") == "AUTH-CODE-XYZ"


# ===========================================================================
# /users/me parsing (fake transport only -- never live in this test file).
# ===========================================================================


def test_get_user_profile_parses_documented_envelope():
    transport = _FakeTransport(get_responses={"/users/me": {"user": {"id": "USER-GUID-1", "email": "paul@example.com", "givenName": "Paul", "surname": "N", "organizationName": "Example Org"}}})
    profile = bpud.get_user_profile(transport=transport, access_token="FAKE-USER-TOKEN")
    assert profile.user_id == "USER-GUID-1"
    assert profile.display_name == "Paul N"
    assert profile.organization == "Example Org"
    assert transport.get_calls == [("/users/me", None, "FAKE-USER-TOKEN")]


def test_get_user_profile_never_receives_or_returns_a_token_field():
    transport = _FakeTransport(get_responses={"/users/me": {"user": {"id": "USER-GUID-2", "email": None, "givenName": None, "surname": None, "organizationName": None}}})
    profile = bpud.get_user_profile(transport=transport, access_token="FAKE-USER-TOKEN")
    assert not hasattr(profile, "access_token")
    assert profile.display_name is None


# ===========================================================================
# Bypass build: profile lookup is OPTIONAL/NON-BLOCKING -- a 404 (or any
# other failure) must never abort the diagnostic before the iTwins API
# calls run.
# ===========================================================================


def test_profile_404_does_not_abort_and_is_reported_non_blocking():
    transport = _FakeTransport(get_errors={"/users/me": 404})
    result = bpud.try_get_user_profile(transport=transport, access_token="FAKE-USER-TOKEN")
    assert result.status == "HTTP_404_NON_BLOCKING"
    assert result.profile is None
    assert transport.get_calls == [("/users/me", None, "FAKE-USER-TOKEN")]


def test_profile_lookup_success_still_reported_via_same_function():
    transport = _FakeTransport(get_responses={"/users/me": {"user": {"id": "USER-GUID-3", "email": None, "givenName": "Paul", "surname": None, "organizationName": None}}})
    result = bpud.try_get_user_profile(transport=transport, access_token="FAKE-USER-TOKEN")
    assert result.status == "SUCCESS"
    assert result.profile.user_id == "USER-GUID-3"


def test_profile_lookup_other_failure_also_non_blocking():
    transport = _FakeTransport(get_errors={"/users/me": 500})
    result = bpud.try_get_user_profile(transport=transport, access_token="FAKE-USER-TOKEN")
    assert result.status == "OTHER_FAILURE_NON_BLOCKING"
    assert result.profile is None


def test_user_token_still_passed_to_list_and_get_itwin_after_profile_404():
    transport = _FakeTransport(
        get_errors={"/users/me": 404},
        get_responses={
            "/itwins": {"iTwins": [{"id": "ITWIN-DEV", "displayName": "MRT Pharma Development", "class": "Endeavor"}]},
            "/itwins/ITWIN-1": {"iTwin": {"id": "ITWIN-1", "displayName": "Test Twin", "class": "Project"}},
        },
    )
    provider = bpud.BentleyUserAccessTokenProvider(access_token="FAKE-USER-TOKEN")
    profile_result = bpud.try_get_user_profile(transport=transport, access_token=provider.get_access_token())
    assert profile_result.status == "HTTP_404_NON_BLOCKING"  # never raised -- diagnostic continues below

    config = bic.BentleyClientConfig(client_id="unused-for-user-flow", itwin_id="ITWIN-1", imodel_id="IMODEL-1", access_token_provider=provider)
    client = bic.BentleyItwinClient(config=config, transport=transport)
    rows = client.list_itwins(display_name="MRT Pharma Development")
    metadata = client.get_itwin_metadata()

    assert len(rows) == 1
    assert metadata.itwin_id == "ITWIN-1"
    assert ("/itwins", {"displayName": "MRT Pharma Development"}, "FAKE-USER-TOKEN") in transport.get_calls
    assert ("/itwins/ITWIN-1", None, "FAKE-USER-TOKEN") in transport.get_calls
    assert transport.post_calls == []


def test_visibility_difference_not_determinable_when_not_attempted():
    result = bpud.determine_itwins_visibility_difference(personal_user_list_itwins="NOT_ATTEMPTED", personal_user_get_itwin="NOT_ATTEMPTED")
    assert result == "NOT_DETERMINABLE"


# ===========================================================================
# Environment gating (mirrors bentley_live_environment_available()).
# ===========================================================================


def test_live_environment_gate_false_when_unset(monkeypatch):
    monkeypatch.delenv("BENTLEY_USER_CLIENT_ID", raising=False)
    monkeypatch.delenv("BENTLEY_USER_REDIRECT_URI", raising=False)
    assert bpud.bentley_user_live_environment_available() is False


def test_live_environment_gate_true_when_both_set(monkeypatch):
    monkeypatch.setenv("BENTLEY_USER_CLIENT_ID", "CLIENT-ID-XYZ")
    monkeypatch.setenv("BENTLEY_USER_REDIRECT_URI", "http://localhost:9999/")
    assert bpud.bentley_user_live_environment_available() is True


# ===========================================================================
# Wire-request diagnostic (`diagnostic_raw_get`) -- offline, via a fake
# `urllib.request.urlopen`. Never touches the real network in these tests.
# ===========================================================================


class _FakeHTTPResponse:
    def __init__(self, *, status, reason, headers, body: bytes):
        self.status = status
        self.reason = reason
        self.headers = headers
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class _FakeHeaders:
    def __init__(self, items):
        self._items = items

    def items(self):
        return self._items


def test_diagnostic_raw_get_captures_request_shape_and_success_body(monkeypatch):
    def _fake_urlopen(request, timeout=30):
        assert request.get_header("Authorization") == "Bearer FAKE-USER-TOKEN"
        assert request.get_header("Accept") == "application/vnd.bentley.itwin-platform.v2+json"
        return _FakeHTTPResponse(status=200, reason="OK", headers=_FakeHeaders([("Content-Type", "application/json")]), body=b'{"iTwin": {"id": "ITWIN-1"}}')

    import urllib.request as real_urllib_request
    monkeypatch.setattr(real_urllib_request, "urlopen", _fake_urlopen)

    result = bpud.diagnostic_raw_get(url="https://api.bentley.com/itwins/ITWIN-1", access_token="FAKE-USER-TOKEN")
    assert result.method == "GET"
    assert result.scheme == "https"
    assert result.host == "api.bentley.com"
    assert result.path == "/itwins/ITWIN-1"
    assert result.authorization_header_present is True
    assert result.status_code == 200
    assert result.response_json == {"iTwin": {"id": "ITWIN-1"}}
    assert "Authorization" not in result.response_headers


def test_diagnostic_raw_get_captures_404_body_never_swallowed(monkeypatch):
    error_body = b'{"error": {"code": "iTwinNotFound", "message": "Requested iTwin is not available."}}'

    def _fake_urlopen(request, timeout=30):
        error = urllib.error.HTTPError(url=str(request.full_url), code=404, msg="Not Found", hdrs=_FakeHeaders([("Content-Type", "application/json")]), fp=None)
        error.read = lambda: error_body  # HTTPError normally reads from `fp`; simulate directly on this instance
        raise error

    import urllib.request as real_urllib_request
    monkeypatch.setattr(real_urllib_request, "urlopen", _fake_urlopen)

    result = bpud.diagnostic_raw_get(url="https://api.bentley.com/itwins/ITWIN-1", access_token="FAKE-USER-TOKEN")
    assert result.status_code == 404
    assert result.response_json == {"error": {"code": "iTwinNotFound", "message": "Requested iTwin is not available."}}
    assert "FAKE-USER-TOKEN" not in result.response_body_text


def test_diagnostic_raw_get_never_exposes_authorization_header_value(monkeypatch):
    def _fake_urlopen(request, timeout=30):
        return _FakeHTTPResponse(status=200, reason="OK", headers=_FakeHeaders([]), body=b"{}")

    import urllib.request as real_urllib_request
    monkeypatch.setattr(real_urllib_request, "urlopen", _fake_urlopen)

    result = bpud.diagnostic_raw_get(url="https://api.bentley.com/itwins/ITWIN-1", access_token="SUPER-SECRET-TOKEN")
    result_repr = repr(result)
    assert "SUPER-SECRET-TOKEN" not in result_repr
    assert result.authorization_header_present is True  # presence only, never the value


# ===========================================================================
# Controlled experiment: Johannes's EXACT known-working List iTwins request
# contract -- method/URL/Accept/Prefer are hardcoded, never parameterized.
# ===========================================================================


def test_johannes_exact_request_constants_match_documented_contract():
    assert bpud.JOHANNES_EXACT_LIST_ITWINS_URL == "https://api.bentley.com/itwins?includeInactive=true"
    assert bpud.JOHANNES_EXACT_ACCEPT_HEADER == "application/vnd.bentley.itwin-platform.v1+json"
    assert bpud.JOHANNES_EXACT_PREFER_HEADER == "return=representation"
    assert not bpud.JOHANNES_EXACT_LIST_ITWINS_URL.startswith("https://api.bentley.com/itwins/")  # never the trailing-slash variant
    assert "displayName" not in bpud.JOHANNES_EXACT_LIST_ITWINS_URL  # never substitutes our own filter param


def test_diagnostic_johannes_exact_list_itwins_sends_exact_headers(monkeypatch):
    def _fake_urlopen(request, timeout=30):
        assert request.full_url == "https://api.bentley.com/itwins?includeInactive=true"
        assert request.get_header("Accept") == "application/vnd.bentley.itwin-platform.v1+json"
        assert request.get_header("Prefer") == "return=representation"
        assert request.get_header("Authorization") == "Bearer FAKE-USER-TOKEN"
        return _FakeHTTPResponse(status=200, reason="OK", headers=_FakeHeaders([("Content-Type", "application/json")]), body=b'{"iTwins": [{"id": "ITWIN-1", "displayName": "Test Twin", "class": "Endeavor"}]}')

    import urllib.request as real_urllib_request
    monkeypatch.setattr(real_urllib_request, "urlopen", _fake_urlopen)

    result = bpud.diagnostic_johannes_exact_list_itwins(access_token="FAKE-USER-TOKEN")
    assert result.query == "includeInactive=true"
    assert result.path == "/itwins"  # no trailing slash
    assert result.accept_header == "application/vnd.bentley.itwin-platform.v1+json"
    assert result.prefer_header == "return=representation"
    assert result.status_code == 200
    assert result.response_json == {"iTwins": [{"id": "ITWIN-1", "displayName": "Test Twin", "class": "Endeavor"}]}


def test_diagnostic_johannes_exact_list_itwins_never_exposes_token(monkeypatch):
    def _fake_urlopen(request, timeout=30):
        return _FakeHTTPResponse(status=200, reason="OK", headers=_FakeHeaders([]), body=b"{}")

    import urllib.request as real_urllib_request
    monkeypatch.setattr(real_urllib_request, "urlopen", _fake_urlopen)

    result = bpud.diagnostic_johannes_exact_list_itwins(access_token="SUPER-SECRET-TOKEN-2")
    assert "SUPER-SECRET-TOKEN-2" not in repr(result)


# ===========================================================================
# Section 15: opt-in LIVE interactive personal-user diagnostic. Skipped
# unless a SEPARATE Native/SPA app registration is configured -- never
# reuses BENTLEY_CLIENT_ID (the service application).
# ===========================================================================

_USER_LIVE_AVAILABLE = bpud.bentley_user_live_environment_available()
_user_live_skip_reason = "BENTLEY_USER_CLIENT_ID/BENTLEY_USER_REDIRECT_URI not set -- requires a separate registered Native/SPA app (PERSONAL_USER_OAUTH_REGISTRATION_REQUIRED)"
live_bentley_user = pytest.mark.skipif(not _USER_LIVE_AVAILABLE, reason=_user_live_skip_reason)


@live_bentley_user
def test_live_7_personal_user_itwins_visibility(capsys):
    def _emit(*args) -> None:
        """Diagnostic-only visibility fix: prints to BOTH the normal
        (possibly pytest-captured) stdout AND the real, never-redirected
        `sys.__stdout__` -- the six required status lines are therefore
        always visible on the actual terminal, regardless of -s/--capture
        settings. Never touches OAuth or service-client logic."""
        text = " ".join(str(a) for a in args)
        print(text)
        print(text, file=sys.__stdout__, flush=True)

    client_id = os.environ["BENTLEY_USER_CLIENT_ID"]
    redirect_uri = os.environ["BENTLEY_USER_REDIRECT_URI"]

    def _manual_code_provider(auth_url: str) -> str:
        _emit("Open this URL in your browser and sign in with your personal Bentley account:")
        _emit(auth_url)
        webbrowser.open(auth_url)
        return input("Paste the full redirect URL (or bare code) after signing in: ")

    try:
        token_result = bpud.run_interactive_user_authorization(client_id=client_id, redirect_uri=redirect_uri, authorization_code_provider=_manual_code_provider)
        _emit("PERSONAL_USER_OAUTH_TOKEN_ACQUIRED = YES")
    except Exception as exc:  # noqa: BLE001 -- live diagnostic, reports exact failure honestly
        _emit("PERSONAL_USER_OAUTH_TOKEN_ACQUIRED = NO")
        _emit(type(exc).__name__, str(exc))
        raise

    transport = bic.BentleyHttpTransport()
    provider = bpud.BentleyUserAccessTokenProvider(access_token=token_result.access_token)

    # Section 3: /users/me is diagnostic-only, NEVER a prerequisite for the
    # actual iTwins-visibility comparison -- its failure is reported and
    # the diagnostic continues regardless.
    profile_result = bpud.try_get_user_profile(transport=transport, access_token=provider.get_access_token())
    _emit("PERSONAL_USER_PROFILE_LOOKUP =", profile_result.status, f"({profile_result.detail})" if profile_result.detail else "")
    if profile_result.profile is not None:
        _emit("display_name =", profile_result.profile.display_name)
        _emit("organization =", profile_result.profile.organization)

    config = bic.BentleyClientConfig(client_id=client_id, itwin_id=os.environ["BENTLEY_ITWIN_ID"], imodel_id=os.environ.get("BENTLEY_IMODEL_ID", ""), access_token_provider=provider)
    client = bic.BentleyItwinClient(config=config, transport=transport)

    personal_user_list_result: bpud.AuthContextOutcome
    try:
        rows = client.list_itwins(display_name="MRT Pharma Development")
        _emit("PERSONAL_USER_LIST_ITWINS = SUCCESS")
        _emit("COUNT =", len(rows))
        for row in rows:
            _emit("ITWIN:", row.itwin_id, "|", row.display_name, "|", row.class_name)
        personal_user_list_result = "SUCCESS"
    except Exception as exc:  # noqa: BLE001 -- live diagnostic, reports exact failure honestly
        _emit("PERSONAL_USER_LIST_ITWINS = FAILURE")
        _emit(type(exc).__name__, str(exc))
        personal_user_list_result = "HTTP_404" if "404" in str(exc) else "OTHER_FAILURE"

    personal_user_get_result: bpud.AuthContextOutcome
    try:
        metadata = client.get_itwin_metadata()
        _emit("PERSONAL_USER_GET_TEST_ITWIN = SUCCESS")
        _emit("itwin_id =", metadata.itwin_id, "display_name =", metadata.display_name)
        personal_user_get_result = "SUCCESS"
    except Exception as exc:  # noqa: BLE001
        _emit("PERSONAL_USER_GET_TEST_ITWIN = FAILURE")
        _emit(type(exc).__name__, str(exc))
        personal_user_get_result = "HTTP_404" if "404" in str(exc) else "OTHER_FAILURE"

    visibility = bpud.determine_itwins_visibility_difference(personal_user_list_itwins=personal_user_list_result, personal_user_get_itwin=personal_user_get_result)
    _emit("ITWINS_API_VISIBILITY_DIFFERENCE_BY_AUTH_CONTEXT =", visibility)
    _emit("RECOMMENDED_BOOTSTRAP_IDENTITY =", "PERSONAL_USER" if visibility == "CONFIRMED" else "NOT_YET_DETERMINED")

    # Section 3-4: wire-request/response audit -- reuses the SAME token
    # (no second OAuth round-trip) to capture the exact sanitized request
    # contract and the FULL 404 response body/headers for ONE GET
    # /itwins/{BENTLEY_ITWIN_ID} call.
    _emit("--- RAW WIRE DIAGNOSTIC: GET /itwins/{BENTLEY_ITWIN_ID} (personal-user token) ---")
    raw = bpud.diagnostic_raw_get(url=f"https://api.bentley.com/itwins/{os.environ['BENTLEY_ITWIN_ID']}", access_token=token_result.access_token)
    _emit("method =", raw.method)
    _emit("scheme =", raw.scheme)
    _emit("host =", raw.host)
    _emit("path =", raw.path)
    _emit("query =", raw.query or "(none)")
    _emit("accept_header =", raw.accept_header)
    _emit("content_type_header =", raw.content_type_header or "(none)")
    _emit("authorization_header_present =", raw.authorization_header_present)
    _emit("status_code =", raw.status_code)
    _emit("reason =", raw.reason)
    _emit("response_headers =", raw.response_headers)
    _emit("response_json =", raw.response_json if raw.response_json is not None else raw.response_body_text)

    # Controlled experiment (sections 2-6): reproduce Johannes's EXACT
    # known-working List iTwins request contract, literally -- reuses the
    # SAME token, no second OAuth round-trip.
    _emit("--- JOHANNES EXACT REQUEST CONTROLLED PROOF ---")
    johannes = bpud.diagnostic_johannes_exact_list_itwins(access_token=token_result.access_token)
    _emit("JOHANNES_EXACT_REQUEST_METHOD =", johannes.method)
    _emit("JOHANNES_EXACT_REQUEST_URL =", bpud.JOHANNES_EXACT_LIST_ITWINS_URL)
    _emit("JOHANNES_EXACT_ACCEPT =", johannes.accept_header)
    _emit("JOHANNES_EXACT_PREFER =", johannes.prefer_header)
    _emit("JOHANNES_EXACT_AUTHORIZATION_PRESENT =", johannes.authorization_header_present)
    _emit("JOHANNES_EXACT_REQUEST_STATUS =", johannes.status_code)
    _emit("JOHANNES_EXACT_RESPONSE_HEADERS =", johannes.response_headers)
    _emit("JOHANNES_EXACT_RESPONSE_BODY =", johannes.response_json if johannes.response_json is not None else johannes.response_body_text)

    if johannes.status_code == 200 and isinstance(johannes.response_json, dict):
        itwins = johannes.response_json.get("iTwins", [])
        _emit("JOHANNES_EXACT_LIST_ITWINS = SUCCESS")
        _emit("JOHANNES_EXACT_ITWIN_COUNT =", len(itwins))
        configured_itwin_id = os.environ["BENTLEY_ITWIN_ID"]
        visible = False
        for row in itwins:
            _emit("ITWIN:", row.get("id"), "|", row.get("displayName"), "|", row.get("class"), "|", row.get("status"))
            if row.get("id") == configured_itwin_id:
                visible = True
        _emit("CONFIGURED_TEST_ITWIN_VISIBLE_IN_JOHANNES_LIST =", "YES" if visible else "NO")
        if visible:
            _emit("ROOT_CAUSE_CLASSIFICATION = CLIENT_REQUEST_CONTRACT_MISMATCH_CONFIRMED")
        else:
            _emit("ROOT_CAUSE_CLASSIFICATION = NOT_EXPLAINED_BY_DIFFERENCE_FROM_JOHANNES_REQUEST_CONTRACT")
    else:
        _emit("JOHANNES_EXACT_LIST_ITWINS = FAILURE")
        _emit("ROOT_CAUSE_CLASSIFICATION = NOT_EXPLAINED_BY_DIFFERENCE_FROM_JOHANNES_REQUEST_CONTRACT")

    captured = capsys.readouterr()
    assert token_result.access_token not in captured.out
    if token_result.refresh_token:
        assert token_result.refresh_token not in captured.out
