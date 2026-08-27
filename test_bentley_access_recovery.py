"""Focused tests for the Bentley Access Recovery Build: service-client
permission verification, Test-iTwin retry, and non-Test iTwin fallback.

Covers OFFLINE/UNIT logic only (section 23) -- permission parsing/
comparison, the fallback decision gate, idempotent creation, secret safety,
and preservation of canonical/OpenUSD boundaries. LIVE validation (section
24-25) is opt-in and gated by `bentley_itwin_client.
bentley_live_environment_available()`, exactly like the existing Phase 2B
live tests -- it is skipped in any environment without real Bentley
credentials configured.
"""

import os
import sys
import urllib.error

import bentley_access_recovery as bar
import bentley_canonical_binding as bcb
import bentley_itwin_client as bic
import pytest


class _FakeTokenProvider:
    def get_access_token(self) -> str:
        return "FAKE-TOKEN"


class _FakeTransport:
    def __init__(self, get_responses=None, post_responses=None, post_errors=None):
        self._get_responses = get_responses or {}
        self._post_responses = post_responses or {}
        self._post_errors = post_errors or {}
        self.post_calls = []
        self.get_calls = []
        self.get_accept_headers = []
        self.get_extra_headers = []

    def get(self, *, path, params, access_token, accept=None, extra_headers=None):
        assert access_token == "FAKE-TOKEN"
        self.get_calls.append((path, params))
        self.get_accept_headers.append(accept)
        self.get_extra_headers.append(extra_headers)
        return self._get_responses[path]

    def post(self, *, path, json_body, access_token, accept=None, extra_headers=None):
        assert access_token == "FAKE-TOKEN"
        self.post_calls.append((path, json_body))
        if path in self._post_errors:
            status_code = self._post_errors[path]
            raise urllib.error.HTTPError(url=path, code=status_code, msg="error", hdrs=None, fp=None)
        return self._post_responses[path]


def _client(get_responses=None, post_responses=None, post_errors=None, itwin_id="ITWIN-1", imodel_id="IMODEL-1"):
    transport = _FakeTransport(get_responses, post_responses, post_errors)
    config = bic.BentleyClientConfig(client_id="fake-client-id", itwin_id=itwin_id, imodel_id=imodel_id, access_token_provider=_FakeTokenProvider())
    return bic.BentleyItwinClient(config=config, transport=transport), transport


# ===========================================================================
# Section 23: CLIENT / PERMISSION LOGIC (offline, items 1-10)
# ===========================================================================


def test_1_service_client_permission_response_parsed_correctly():
    client, _transport = _client(get_responses={"/accesscontrol/itwins/ITWIN-1/permissions": {"permissions": ["imodels_read", "imodels_write"]}})
    result = client.get_itwin_permissions()
    assert result.itwin_id == "ITWIN-1"
    assert result.permissions == ("imodels_read", "imodels_write")


def test_2_expected_permission_comparison_identifies_missing_permissions():
    actual = ("imodels_read", "imodels_write")
    comparison = bar.compare_permission_sets(expected=bar.EXPECTED_SERVICE_CLIENT_PERMISSIONS, actual=actual)
    assert not comparison.all_expected_present
    assert "imodels_delete" in comparison.missing_expected_permissions
    assert comparison.expected_count == 14
    assert comparison.actual_count == 2


def test_3_extra_permissions_do_not_falsely_fail_comparison():
    actual = tuple(bar.EXPECTED_SERVICE_CLIENT_PERMISSIONS) + ("some_future_permission",)
    comparison = bar.compare_permission_sets(expected=bar.EXPECTED_SERVICE_CLIENT_PERMISSIONS, actual=actual)
    assert comparison.all_expected_present
    assert comparison.unexpected_extra_permissions == ("some_future_permission",)


def test_4_tokens_secrets_not_emitted_by_report_helpers():
    client, _transport = _client(get_responses={"/itwins/ITWIN-1": {"iTwin": {"id": "ITWIN-1", "displayName": "Test Twin", "class": "Project"}}})
    metadata = client.get_itwin_metadata()
    report_string = str(metadata)
    assert "FAKE-TOKEN" not in report_string
    assert "client_secret" not in report_string.lower()


def test_5_test_itwin_role_creation_is_not_attempted():
    assert bar.TEST_ITWIN_ROLE_CREATION_ATTEMPTED is False
    assert bar.TEST_ITWIN_ROLE_LIMITATION_ACCEPTED is True
    import inspect
    for module in (bar, bic):
        source = inspect.getsource(module)
        # Membership Diagnostic build (section 1/7) legitimately READS
        # documented role names via Get iTwin User Members -- so "role"
        # itself is no longer forbidden; only role CREATION/MUTATION is.
        assert "def create_role" not in source
        assert "def add_role" not in source
        assert "def assign_role" not in source
        assert "def update_role" not in source
        assert "def delete_role" not in source
        assert "def remove_role" not in source


def test_6_fallback_gate_does_not_create_new_itwin_when_test_itwin_succeeds():
    results = bar.AccessRecoveryCheckResults(
        service_authentication="SUCCESS", permission_check="SUCCESS", test_itwin_metadata="SUCCESS",
        test_imodel_access="SUCCESS", existing_live_proof="SUCCESS",
    )
    assert bar.determine_non_test_itwin_required(results) is False


def test_7_fallback_gate_allows_non_test_creation_only_after_verified_failure():
    results = bar.AccessRecoveryCheckResults(
        service_authentication="SUCCESS", permission_check="SUCCESS", test_itwin_metadata="FAILED",
        test_imodel_access="NOT_APPLICABLE", existing_live_proof="FAILED",
    )
    assert bar.determine_non_test_itwin_required(results) is True
    # an untested (NOT_ATTEMPTED) path is never treated as evidence of a blocker
    not_attempted_results = bar.AccessRecoveryCheckResults(
        service_authentication="NOT_ATTEMPTED", permission_check="NOT_ATTEMPTED", test_itwin_metadata="NOT_ATTEMPTED",
        test_imodel_access="NOT_ATTEMPTED", existing_live_proof="NOT_ATTEMPTED",
    )
    assert bar.determine_non_test_itwin_required(not_attempted_results) is False


def test_8_creation_logic_is_idempotent_where_supported():
    client, transport = _client(get_responses={
        "/itwins": {"iTwins": [{"id": "ITWIN-EXISTING", "displayName": "MRT Pharma Development", "class": "Endeavor"}]},
    })
    metadata, created = bar.find_or_create_development_itwin(client, display_name="MRT Pharma Development")
    assert created is False
    assert metadata.itwin_id == "ITWIN-EXISTING"
    assert transport.post_calls == []  # never calls create when a match already exists

    client2, transport2 = _client(
        get_responses={"/itwins": {"iTwins": []}},
        post_responses={"/itwins": {"iTwin": {"id": "ITWIN-NEW", "displayName": "MRT Pharma Development", "class": "Endeavor"}}},
    )
    metadata2, created2 = bar.find_or_create_development_itwin(client2, display_name="MRT Pharma Development")
    assert created2 is True
    assert metadata2.itwin_id == "ITWIN-NEW"
    assert len(transport2.post_calls) == 1


def test_9_bentley_canonical_binding_remains_unchanged():
    import inspect
    source = inspect.getsource(bcb)
    assert "bentley_access_recovery" not in source
    assert "accesscontrol" not in source.lower()


def test_10_openusd_not_imported_into_bentley_path():
    import inspect
    for module in (bar, bic, bcb):
        lines = [l.strip() for l in inspect.getsource(module).splitlines() if l.strip().startswith(("import ", "from "))]
        assert not any("openusd" in line.lower() or "pxr" in line.lower() or "omni" in line.lower() for line in lines)


# ---------------------------------------------------------------------------
# Section 16-17: canonical/OpenUSD preservation status constants
# ---------------------------------------------------------------------------


def test_11_community_tier_and_demo_reference_status_constants():
    assert bar.BENTLEY_COMMUNITY_TIER_SUPPORTED is True
    assert bar.JOHANNES_DEMO_USED_AS_REFERENCE_ONLY is True


def test_12_non_test_itwin_creation_is_never_duplicated_on_rerun():
    client, transport = _client(get_responses={
        "/itwins": {"iTwins": [{"id": "ITWIN-EXISTING", "displayName": "MRT Pharma Development", "class": "Endeavor"}]},
    })
    bar.find_or_create_development_itwin(client, display_name="MRT Pharma Development")
    bar.find_or_create_development_itwin(client, display_name="MRT Pharma Development")
    assert transport.post_calls == []


def test_13_imodel_idempotent_find_or_create():
    client, transport = _client(get_responses={
        "/imodels": {"iModels": [{"id": "IMODEL-EXISTING", "displayName": "MRT Pharma Development iModel"}]},
    })
    metadata, created = bar.find_or_create_development_imodel(client, itwin_id="ITWIN-1", display_name="MRT Pharma Development iModel")
    assert created is False
    assert metadata.imodel_id == "IMODEL-EXISTING"
    assert transport.post_calls == []


def test_14_get_imodel_metadata_parses_the_documented_imodel_envelope():
    """Live finding: `GET /imodels/{id}` wraps the object in an `"iModel"`
    envelope (confirmed against https://developer.bentley.com/apis/
    imodels-v2/operations/get-imodel-details/) -- a flat payload previously
    raised `KeyError: 'id'` against the real API."""
    client, _transport = _client(get_responses={
        "/imodels/IMODEL-1": {"iModel": {"id": "IMODEL-1", "iTwinId": "ITWIN-1", "displayName": "MRT Pharma Hospital Campus Development"}},
    })
    metadata = client.get_imodel_metadata()
    assert metadata.imodel_id == "IMODEL-1"
    assert metadata.itwin_id == "ITWIN-1"
    assert metadata.display_name == "MRT Pharma Hospital Campus Development"


def test_15_get_itwin_metadata_parses_the_documented_itwin_envelope():
    """Live finding: `GET /itwins/{id}` ALSO wraps the object in an
    `"iTwin"` envelope (confirmed against https://developer.bentley.com/
    apis/itwins/operations/get-itwin/) -- the SAME envelope pattern as
    `get_imodel_metadata`. The 404 `iTwinNotFound` observed live is a
    separate, non-parser issue (see report) -- this test only proves the
    parser is now correct for a 200 OK response."""
    client, _transport = _client(get_responses={
        "/itwins/ITWIN-1": {"iTwin": {"id": "ITWIN-1", "displayName": "MRT Pharma Development", "class": "Endeavor"}},
    })
    metadata = client.get_itwin_metadata()
    assert metadata.itwin_id == "ITWIN-1"
    assert metadata.display_name == "MRT Pharma Development"
    assert metadata.class_name == "Endeavor"


# ===========================================================================
# Section 26: NON-TEST ITWIN PROVISIONING LOGIC (offline, items 1-16)
# ===========================================================================


def test_16_exact_development_itwin_name_constant():
    assert bar.DEVELOPMENT_ITWIN_NAME == "MRT Pharma Development"


def test_17_exact_development_imodel_name_constant():
    assert bar.DEVELOPMENT_IMODEL_NAME == "MRT Pharma Development Model"


def test_18_search_before_create_behavior():
    client, transport = _client(get_responses={"/itwins": {"iTwins": []}}, post_responses={"/itwins": {"iTwin": {"id": "ITWIN-NEW", "displayName": bar.DEVELOPMENT_ITWIN_NAME, "class": "Endeavor"}}})
    result = bar.provision_development_itwin(client)
    assert result.created_this_call is True
    assert len(transport.post_calls) == 1  # search happened first (via GET), create only after an empty search result


def test_19_existing_matching_itwin_is_reused():
    client, transport = _client(get_responses={"/itwins": {"iTwins": [{"id": "ITWIN-EXISTING", "displayName": bar.DEVELOPMENT_ITWIN_NAME, "class": "Endeavor"}]}})
    result = bar.provision_development_itwin(client)
    assert result.created_this_call is False
    assert result.itwin.itwin_id == "ITWIN-EXISTING"
    assert transport.post_calls == []


def test_20_existing_matching_imodel_is_reused():
    client, transport = _client(get_responses={"/imodels": {"iModels": [{"id": "IMODEL-EXISTING", "displayName": bar.DEVELOPMENT_IMODEL_NAME}]}})
    result = bar.provision_development_imodel(client, itwin_id="ITWIN-1")
    assert result.created_this_call is False
    assert result.imodel.imodel_id == "IMODEL-EXISTING"
    assert transport.post_calls == []


def test_21_duplicate_itwin_creation_is_prevented():
    client, transport = _client(get_responses={"/itwins": {"iTwins": [{"id": "ITWIN-EXISTING", "displayName": bar.DEVELOPMENT_ITWIN_NAME, "class": "Endeavor"}]}})
    bar.provision_development_itwin(client)
    bar.provision_development_itwin(client)
    assert transport.post_calls == []


def test_22_duplicate_imodel_creation_is_prevented():
    client, transport = _client(get_responses={"/imodels": {"iModels": [{"id": "IMODEL-EXISTING", "displayName": bar.DEVELOPMENT_IMODEL_NAME}]}})
    bar.provision_development_imodel(client, itwin_id="ITWIN-1")
    bar.provision_development_imodel(client, itwin_id="ITWIN-1")
    assert transport.post_calls == []


def test_23_ambiguous_duplicate_itwin_candidates_stop_creation():
    client, transport = _client(get_responses={"/itwins": {"iTwins": [
        {"id": "ITWIN-A", "displayName": bar.DEVELOPMENT_ITWIN_NAME, "class": "Endeavor"},
        {"id": "ITWIN-B", "displayName": bar.DEVELOPMENT_ITWIN_NAME, "class": "Endeavor"},
    ]}})
    with pytest.raises(bar.AmbiguousDevelopmentResourceError):
        bar.provision_development_itwin(client)
    assert transport.post_calls == []


def test_24_ambiguous_duplicate_imodel_candidates_stop_creation():
    client, transport = _client(get_responses={"/imodels": {"iModels": [
        {"id": "IMODEL-A", "displayName": bar.DEVELOPMENT_IMODEL_NAME},
        {"id": "IMODEL-B", "displayName": bar.DEVELOPMENT_IMODEL_NAME},
    ]}})
    with pytest.raises(bar.AmbiguousDevelopmentResourceError):
        bar.provision_development_imodel(client, itwin_id="ITWIN-1")
    assert transport.post_calls == []


def test_25_create_authorization_failure_does_not_trigger_repeated_post():
    client, transport = _client(get_responses={"/itwins": {"iTwins": []}}, post_errors={"/itwins": 403})
    result = bar.provision_development_itwin(client)
    assert result.create_authorization == "NOT_AUTHORIZED"
    assert result.failure_category == "CREATE_NOT_AUTHORIZED"
    assert result.itwin is None
    assert len(transport.post_calls) == 1  # exactly one attempt, never retried


def test_26_secrets_are_not_printed_by_provisioning_results():
    client, _transport = _client(get_responses={"/itwins": {"iTwins": [{"id": "ITWIN-EXISTING", "displayName": bar.DEVELOPMENT_ITWIN_NAME, "class": "Endeavor"}]}})
    result = bar.provision_development_itwin(client)
    assert "FAKE-TOKEN" not in str(result)
    assert "client_secret" not in str(result).lower()


def test_27_test_itwin_is_never_deleted():
    import inspect
    source = inspect.getsource(bar) + inspect.getsource(bic)
    assert "def delete_itwin" not in source
    assert ".delete(" not in source


def test_28_test_itwin_role_creation_is_never_attempted_provisioning():
    assert bar.TEST_ITWIN_ROLE_CREATION_ATTEMPTED is False
    import inspect
    assert "role" not in inspect.getsource(bar.provision_development_itwin).lower()
    assert "role" not in inspect.getsource(bar.provision_development_imodel).lower()


def test_29_canonical_bentley_binding_unchanged_by_provisioning():
    import inspect
    source = inspect.getsource(bcb)
    assert "provision_development" not in source
    assert "DEVELOPMENT_ITWIN_NAME" not in source


def test_30_openusd_not_imported_into_provisioning_path():
    import inspect
    lines = [l.strip() for l in inspect.getsource(bar).splitlines() if l.strip().startswith(("import ", "from "))]
    assert not any("openusd" in line.lower() or "pxr" in line.lower() or "omni" in line.lower() for line in lines)


def test_31_development_imodel_itwin_id_matches_selected_development_itwin():
    client, _transport = _client(get_responses={
        "/imodels": {"iModels": [{"id": "IMODEL-EXISTING", "displayName": bar.DEVELOPMENT_IMODEL_NAME}]},
        "/imodels/IMODEL-EXISTING": {"iModel": {"id": "IMODEL-EXISTING", "iTwinId": "ITWIN-DEV", "displayName": bar.DEVELOPMENT_IMODEL_NAME}},
    }, itwin_id="ITWIN-DEV", imodel_id="IMODEL-EXISTING")
    result = bar.provision_development_imodel(client, itwin_id="ITWIN-DEV")
    metadata = client.get_imodel_metadata()
    assert result.imodel.imodel_id == metadata.imodel_id
    assert metadata.itwin_id == "ITWIN-DEV"


def test_32_list_itwins_uses_live_proven_no_trailing_slash_path():
    """Client Contract Correction build: a controlled live experiment
    (reproducing Johannes Renner's actually-working `itwin-demo-apis`
    request byte-for-byte) proved `GET /itwins` (NO trailing slash) with
    `Accept: application/vnd.bentley.itwin-platform.v1+json` and
    `Prefer: return=representation` returns HTTP 200 and includes the
    configured Test-iTwin -- while the PREVIOUS `/itwins/` (trailing slash)
    + v2 media type request returned a live HTTP 404 `ResourceNotFound`
    ("Verify the API URL and the Accept header"). The prior offline
    assumption (Bentley's rendered docs UI showing a trailing slash) is
    now known to be a documentation-rendering artifact, not the real
    contract, for this collection endpoint."""
    client, transport = _client(get_responses={"/itwins": {"iTwins": []}})
    client.list_itwins(display_name="MRT Pharma Development")
    assert transport.get_calls == [("/itwins", {"displayName": "MRT Pharma Development"})]
    assert transport.get_accept_headers == [bic.ITWINS_MEDIA_TYPE_V1]
    assert transport.get_extra_headers == [{"Prefer": "return=representation"}]


# ===========================================================================
# Membership Diagnostic build (section 12): Get iTwin User Members, items 1-10
# ===========================================================================

_MEMBER_ROW_WITH_ROLES = {
    "id": "99cf5e21-735c-4598-99eb-fe3940f96353", "email": "John.Johnson@example.com", "givenName": "John",
    "surname": "Johnson", "organization": "Organization Corp.",
    "roles": [{"id": "5abbfcef-0eab-472a-b5f5-5c5a43df34b1", "displayName": "iModel External Developer", "description": "..."}],
}


def test_33_get_itwin_user_members_parses_documented_response():
    client, _transport = _client(get_responses={"/accesscontrol/itwins/ITWIN-1/members/users": {"members": [_MEMBER_ROW_WITH_ROLES]}})
    members = client.get_itwin_user_members()
    assert len(members) == 1
    assert members[0].member_id == "99cf5e21-735c-4598-99eb-fe3940f96353"
    assert members[0].email == "John.Johnson@example.com"


def test_34_get_itwin_user_members_empty_list():
    client, _transport = _client(get_responses={"/accesscontrol/itwins/ITWIN-1/members/users": {"members": []}})
    assert client.get_itwin_user_members() == ()


def test_35_get_itwin_user_members_multiple_members():
    second_row = {"id": "25407933-cad2-41a2-acf4-5a074c83046b", "email": "Maria.Miller@example.com", "givenName": "Maria", "surname": "Miller", "organization": "Organization Corp.", "roles": []}
    client, _transport = _client(get_responses={"/accesscontrol/itwins/ITWIN-1/members/users": {"members": [_MEMBER_ROW_WITH_ROLES, second_row]}})
    members = client.get_itwin_user_members()
    assert len(members) == 2
    assert members[1].member_id == "25407933-cad2-41a2-acf4-5a074c83046b"


def test_36_get_itwin_user_members_extracts_documented_role_fields():
    client, _transport = _client(get_responses={"/accesscontrol/itwins/ITWIN-1/members/users": {"members": [_MEMBER_ROW_WITH_ROLES]}})
    members = client.get_itwin_user_members()
    assert len(members[0].roles) == 1
    assert members[0].roles[0].display_name == "iModel External Developer"


def test_37_service_account_identity_never_forced_against_undocumented_field():
    # Get iTwin User Members has NO documented client-ID field -- membership
    # is always NOT_DETERMINABLE regardless of how many human members exist.
    assert bar.determine_service_account_membership(member_count=0) == "NOT_DETERMINABLE_FROM_USER_MEMBERS_ENDPOINT"
    assert bar.determine_service_account_membership(member_count=5) == "NOT_DETERMINABLE_FROM_USER_MEMBERS_ENDPOINT"


def test_38_inability_to_determine_membership_is_reported_honestly():
    root_cause = bar.determine_itwin_404_root_cause(
        service_account_membership="NOT_DETERMINABLE_FROM_USER_MEMBERS_ENDPOINT",
        permission_check_success=True, itwin_id_matches_imodel=True, get_itwin_404=True,
    )
    assert root_cause == "NOT_DETERMINABLE_FROM_USER_MEMBERS_ENDPOINT"
    assert bar.determine_service_account_role("NOT_DETERMINABLE_FROM_USER_MEMBERS_ENDPOINT") == "NOT_DETERMINABLE_FROM_USER_MEMBERS_ENDPOINT"


def test_39_secrets_never_emitted_by_membership_result(capsys):
    client, _transport = _client(get_responses={"/accesscontrol/itwins/ITWIN-1/members/users": {"members": [_MEMBER_ROW_WITH_ROLES]}})
    members = client.get_itwin_user_members()
    print(members)
    captured = capsys.readouterr()
    assert "FAKE-TOKEN" not in captured.out
    assert "client_secret" not in captured.out.lower()


def test_40_no_membership_mutation_method_exists():
    import inspect
    source = inspect.getsource(bic)
    assert "def add_itwin_user_member" not in source
    assert "def remove_itwin_user_member" not in source
    assert "def add_member" not in source
    assert "def remove_member" not in source


def test_41_membership_diagnostic_never_calls_create_itwin():
    client, transport = _client(get_responses={"/accesscontrol/itwins/ITWIN-1/members/users": {"members": []}})
    client.get_itwin_user_members()
    assert transport.post_calls == []


def test_42_membership_diagnostic_never_calls_create_imodel():
    client, transport = _client(get_responses={"/accesscontrol/itwins/ITWIN-1/members/users": {"members": [_MEMBER_ROW_WITH_ROLES]}})
    client.get_itwin_user_members()
    assert all("/imodels" not in call[0] for call in transport.post_calls)
    assert transport.post_calls == []


def test_43_case_a_root_cause_requires_all_four_conditions():
    assert bar.determine_itwin_404_root_cause(
        service_account_membership="CONFIRMED", permission_check_success=True, itwin_id_matches_imodel=True, get_itwin_404=True,
    ) == "UNRESOLVED_PLATFORM_OR_API_VISIBILITY_CONDITION"


def test_44_case_b_root_cause_when_membership_not_found():
    assert bar.determine_itwin_404_root_cause(
        service_account_membership="NOT_FOUND", permission_check_success=True, itwin_id_matches_imodel=True, get_itwin_404=True,
    ) == "SERVICE_ACCOUNT_NOT_PRESENT_IN_TEST_ITWIN_MEMBERSHIP"



# ===========================================================================
# Section 24-25: opt-in LIVE Bentley access-recovery checks -- skipped
# unless real credentials/configuration are present in the environment.
# ===========================================================================

_LIVE_AVAILABLE = bic.bentley_live_environment_available()
_live_skip_reason = "BENTLEY_CLIENT_ID/BENTLEY_CLIENT_SECRET/BENTLEY_ITWIN_ID/BENTLEY_IMODEL_ID not set -- live Bentley checks are opt-in only"
live_bentley = pytest.mark.skipif(not _LIVE_AVAILABLE, reason=_live_skip_reason)


def _build_live_client():
    token_provider = bic.BentleyClientCredentialsTokenProvider(
        client_id=os.environ["BENTLEY_CLIENT_ID"], client_secret=os.environ["BENTLEY_CLIENT_SECRET"],
        authority_url=os.environ.get("BENTLEY_AUTHORITY_URL", "https://ims.bentley.com/connect/token"),
        scope=os.environ.get("BENTLEY_SCOPE", "itwin-platform"),
    )
    config = bic.build_config_from_environment(access_token_provider=token_provider)
    return bic.BentleyItwinClient(config=config, transport=bic.BentleyHttpTransport())


@live_bentley
def test_live_1_service_client_permission_check():
    client = _build_live_client()
    permissions = client.get_itwin_permissions()
    comparison = bar.compare_permission_sets(expected=bar.EXPECTED_SERVICE_CLIENT_PERMISSIONS, actual=permissions.permissions)
    assert comparison.expected_count == 14


@live_bentley
def test_live_2_test_itwin_metadata_retry():
    client = _build_live_client()
    client.get_itwin_metadata()


@live_bentley
def test_live_3_test_imodel_access_retry():
    client = _build_live_client()
    client.get_imodel_metadata()


@live_bentley
def test_live_4_no_secret_in_permission_check_output(capsys):
    client = _build_live_client()
    client.get_itwin_permissions()
    captured = capsys.readouterr()
    assert os.environ["BENTLEY_CLIENT_SECRET"] not in captured.out
    assert os.environ["BENTLEY_CLIENT_SECRET"] not in captured.err


@live_bentley
def test_live_7_service_client_list_itwins_uses_corrected_contract(capsys):
    """Client Contract Correction build (section 12): re-validates the
    corrected core iTwins contract with the EXISTING service-client token
    -- reports the result independently, never assuming it must match the
    personal-user outcome (section 12: "Do not assume the service client
    must behave identically merely because the request contract is
    fixed")."""
    client = _build_live_client()
    try:
        rows = client.list_itwins(include_inactive=True)
        print("PRODUCTION_CLIENT_SERVICE_LIST_ITWINS = SUCCESS")
        print("COUNT =", len(rows))
        configured_itwin_id = os.environ["BENTLEY_ITWIN_ID"]
        print("CONFIGURED_TEST_ITWIN_VISIBLE_TO_SERVICE_CLIENT =", "YES" if any(r.itwin_id == configured_itwin_id for r in rows) else "NO")
    except Exception as exc:  # noqa: BLE001 -- live diagnostic, reports exact failure honestly
        print("PRODUCTION_CLIENT_SERVICE_LIST_ITWINS = FAILURE")
        print(type(exc).__name__, str(exc))
    captured = capsys.readouterr()
    assert os.environ["BENTLEY_CLIENT_SECRET"] not in captured.out


# ---------------------------------------------------------------------------
# Section 27: opt-in LIVE non-Test iTwin provisioning sequence (section 18).
# Creates AT MOST one development iTwin and one development iModel, only if
# none already exist under the deterministic development names -- never
# touches or deletes the configured Test-iTwin.
# ---------------------------------------------------------------------------


@live_bentley
def test_live_5_non_test_itwin_provisioning_sequence(capsys):
    client = _build_live_client()

    itwin_result = bar.provision_development_itwin(client)
    print("DEVELOPMENT_ITWIN_CREATE_AUTHORIZATION =", itwin_result.create_authorization)
    print("DEVELOPMENT_ITWIN_CREATED_THIS_CALL =", itwin_result.created_this_call)
    if itwin_result.itwin is None:
        pytest.skip(f"BENTLEY_ITWIN_CREATE_AUTHORIZATION = {itwin_result.create_authorization} ({itwin_result.failure_category}) -- service account cannot provision a development iTwin")

    print("DEVELOPMENT_ITWIN_ID =", itwin_result.itwin.itwin_id)
    dev_itwin_config = bic.BentleyClientConfig(
        client_id=client._config.client_id, itwin_id=itwin_result.itwin.itwin_id, imodel_id="",
        access_token_provider=client._config.access_token_provider,
    )
    dev_client = bic.BentleyItwinClient(config=dev_itwin_config, transport=bic.BentleyHttpTransport())
    dev_permissions = dev_client.get_itwin_permissions()
    assert dev_permissions.itwin_id == itwin_result.itwin.itwin_id

    itwin_metadata = dev_client.get_itwin_metadata()
    assert itwin_metadata.itwin_id == itwin_result.itwin.itwin_id

    imodel_result = bar.provision_development_imodel(dev_client, itwin_id=itwin_result.itwin.itwin_id)
    print("DEVELOPMENT_IMODEL_CREATE_AUTHORIZATION =", imodel_result.create_authorization)
    print("DEVELOPMENT_IMODEL_CREATED_THIS_CALL =", imodel_result.created_this_call)
    if imodel_result.imodel is None:
        pytest.skip(f"BENTLEY_IMODEL_CREATE_AUTHORIZATION = {imodel_result.create_authorization} ({imodel_result.failure_category})")

    print("DEVELOPMENT_IMODEL_ID =", imodel_result.imodel.imodel_id)
    dev_full_config = bic.BentleyClientConfig(
        client_id=client._config.client_id, itwin_id=itwin_result.itwin.itwin_id, imodel_id=imodel_result.imodel.imodel_id,
        access_token_provider=client._config.access_token_provider,
    )
    dev_full_client = bic.BentleyItwinClient(config=dev_full_config, transport=bic.BentleyHttpTransport())
    imodel_metadata = dev_full_client.get_imodel_metadata()
    assert imodel_metadata.itwin_id == itwin_result.itwin.itwin_id  # DEVELOPMENT_IMODEL_ITWIN_ID_MATCH = YES

    # rerun -- must reuse, never duplicate
    rerun_itwin_result = bar.provision_development_itwin(client)
    assert rerun_itwin_result.created_this_call is False
    assert rerun_itwin_result.itwin.itwin_id == itwin_result.itwin.itwin_id
    rerun_imodel_result = bar.provision_development_imodel(dev_client, itwin_id=itwin_result.itwin.itwin_id)
    assert rerun_imodel_result.created_this_call is False
    assert rerun_imodel_result.imodel.imodel_id == imodel_result.imodel.imodel_id

    captured = capsys.readouterr()
    assert os.environ["BENTLEY_CLIENT_SECRET"] not in captured.out


# ---------------------------------------------------------------------------
# Membership Diagnostic build (section 13): opt-in LIVE Test-iTwin
# service-account membership check. Read-only -- never mutates Access
# Control, never creates any iTwin/iModel.
# ---------------------------------------------------------------------------


@live_bentley
def test_live_6_test_itwin_service_account_membership(capsys):
    client = _build_live_client()

    permissions = client.get_itwin_permissions()
    comparison = bar.compare_permission_sets(expected=bar.EXPECTED_SERVICE_CLIENT_PERMISSIONS, actual=permissions.permissions)
    print("SERVICE_CLIENT_PERMISSION_COUNT =", comparison.actual_count)
    print("SERVICE_CLIENT_EXPECTED_PERMISSIONS_PRESENT =", comparison.all_expected_present)

    imodel_metadata = client.get_imodel_metadata()
    itwin_id_matches_imodel = imodel_metadata.itwin_id == client._config.itwin_id
    print("CONFIGURED_ITWIN_ID_MATCHES_IMODEL_ITWIN_ID =", itwin_id_matches_imodel)

    try:
        members = client.get_itwin_user_members()
        member_count = len(members)
        get_itwin_user_members_status = "SUCCESS"
        print("GET_ITWIN_USER_MEMBERS =", get_itwin_user_members_status)
        print("TEST_ITWIN_MEMBER_COUNT =", member_count)
        for member in members:
            role_names = ", ".join(role.display_name for role in member.roles) or "(none)"
            print(f"MEMBER member_id={member.member_id} organization={member.organization} roles=[{role_names}]")
    except urllib.error.HTTPError as exc:
        member_count = 0
        get_itwin_user_members_status = f"FAILED ({exc.code})"
        print("GET_ITWIN_USER_MEMBERS =", get_itwin_user_members_status)

    membership = bar.determine_service_account_membership(member_count=member_count)
    print("SERVICE_ACCOUNT_TEST_ITWIN_MEMBERSHIP =", membership)
    print("SERVICE_ACCOUNT_TEST_ITWIN_ROLE =", bar.determine_service_account_role(membership))

    get_itwin_404 = False
    try:
        client.get_itwin_metadata()
    except urllib.error.HTTPError as exc:
        get_itwin_404 = exc.code == 404

    root_cause = bar.determine_itwin_404_root_cause(
        service_account_membership=membership, permission_check_success=comparison.all_expected_present,
        itwin_id_matches_imodel=itwin_id_matches_imodel, get_itwin_404=get_itwin_404,
    )
    print("BENTLEY_ITWIN_404_ROOT_CAUSE =", root_cause)

    captured = capsys.readouterr()
    assert os.environ["BENTLEY_CLIENT_SECRET"] not in captured.out
    assert os.environ["BENTLEY_CLIENT_SECRET"] not in captured.err


# ---------------------------------------------------------------------------
# Development Resource Adoption build: DISCOVER -> CLASSIFY -> REUSE-OR-
# CREATE -> VERIFY -> PROVISION/REUSE IMODEL -> VERIFY. Read-only discovery
# first; creates AT MOST one iTwin and one iModel, ONLY if genuinely
# absent/ambiguous-free. Never touches or deletes the configured Test-iTwin.
# ---------------------------------------------------------------------------


@live_bentley
def test_live_8_development_resource_adoption_sequence(capsys):
    def _emit(*args) -> None:
        """Prints to both the normal (possibly pytest-captured) stdout and
        the real, never-redirected `sys.__stdout__` -- guarantees these
        results are visible on the actual terminal regardless of
        -s/--capture settings."""
        text = " ".join(str(a) for a in args)
        print(text)
        print(text, file=sys.__stdout__, flush=True)

    client = _build_live_client()
    configured_test_itwin_id = os.environ["BENTLEY_ITWIN_ID"]

    # --- iTwin discovery + classification ---
    itwin_decision = bar.discover_and_decide_development_itwin(client, configured_test_itwin_id=configured_test_itwin_id)
    _emit("--- ITWIN DISCOVERY TABLE ---")
    for c in itwin_decision.candidates:
        _emit(f"ITWIN id={c.itwin.itwin_id} displayName={c.itwin.display_name!r} class={c.itwin.class_name} status={c.itwin.status} relationship={c.relationship} adoptable={c.adoptable} reason={c.reason}")
    _emit("DEVELOPMENT_ITWIN_ACTION =", itwin_decision.action)

    if itwin_decision.action in ("STOP_AMBIGUOUS", "STOP_CLASSIFICATION_REQUIRED"):
        pytest.skip(f"DEVELOPMENT_ITWIN_ACTION = {itwin_decision.action} -- manual resolution required, no resource created")

    development_itwin_created_this_build = False
    if itwin_decision.action == "REUSE_EXISTING":
        adopted_itwin = itwin_decision.adopted_itwin
        _emit("DEVELOPMENT_ITWIN_REUSED_EXISTING = YES")
    else:
        provision_result = bar.provision_development_itwin(client)
        _emit("DEVELOPMENT_ITWIN_CREATE_AUTHORIZATION =", provision_result.create_authorization)
        if provision_result.itwin is None:
            pytest.skip(f"DEVELOPMENT_ITWIN_ACTION = CREATE_NEW but authorization/creation failed: {provision_result.failure_category} -- {provision_result.detail}")
        adopted_itwin = provision_result.itwin
        development_itwin_created_this_build = provision_result.created_this_call
        _emit("DEVELOPMENT_ITWIN_CREATED_THIS_BUILD =", development_itwin_created_this_build)

    _emit("RECOMMENDED_BENTLEY_ITWIN_ID =", adopted_itwin.itwin_id)
    _emit("EXISTING_DEVELOPMENT_ITWIN_EQUALS_TEST_ITWIN =", "YES" if adopted_itwin.itwin_id == configured_test_itwin_id else "NO")

    # --- verify adopted iTwin through a client scoped to it ---
    dev_config = bic.BentleyClientConfig(client_id=client._config.client_id, itwin_id=adopted_itwin.itwin_id, imodel_id="", access_token_provider=client._config.access_token_provider)
    dev_client = bic.BentleyItwinClient(config=dev_config, transport=bic.BentleyHttpTransport())
    verified_metadata = dev_client.get_itwin_metadata()
    _emit("DEVELOPMENT_ITWIN_METADATA = SUCCESS")
    _emit("verified id =", verified_metadata.itwin_id, "displayName =", verified_metadata.display_name, "class =", verified_metadata.class_name, "status =", verified_metadata.status)

    permissions = dev_client.get_itwin_permissions()
    comparison = bar.compare_permission_sets(expected=bar.EXPECTED_SERVICE_CLIENT_PERMISSIONS, actual=permissions.permissions)
    _emit("--- DEVELOPMENT ITWIN PERMISSION TABLE ---")
    for expected_permission in sorted(bar.EXPECTED_SERVICE_CLIENT_PERMISSIONS):
        _emit(f"PERMISSION {expected_permission} present={expected_permission in permissions.permissions}")
    _emit("DEVELOPMENT_ITWIN_PERMISSION_CHECK =", "SUCCESS" if comparison.all_expected_present else f"MISSING: {comparison.missing_expected_permissions}")

    # --- iModel discovery + classification ---
    imodel_decision = bar.discover_and_decide_development_imodel(dev_client, itwin_id=adopted_itwin.itwin_id)
    _emit("--- IMODEL DISCOVERY TABLE ---")
    for row in imodel_decision.candidates:
        _emit(f"IMODEL id={row.imodel_id} displayName={row.display_name!r} itwinId={row.itwin_id}")
    _emit("DEVELOPMENT_IMODEL_ACTION =", imodel_decision.action)

    if imodel_decision.action == "STOP_AMBIGUOUS":
        pytest.skip("DEVELOPMENT_IMODEL_ACTION = STOP_AMBIGUOUS -- manual resolution required, no resource created")

    development_imodel_created_this_build = False
    if imodel_decision.action == "REUSE_EXISTING":
        adopted_imodel = imodel_decision.adopted_imodel
        _emit("DEVELOPMENT_IMODEL_REUSED_EXISTING = YES")
    else:
        imodel_provision_result = bar.provision_development_imodel(dev_client, itwin_id=adopted_itwin.itwin_id)
        _emit("DEVELOPMENT_IMODEL_CREATE_AUTHORIZATION =", imodel_provision_result.create_authorization)
        if imodel_provision_result.imodel is None:
            pytest.skip(f"DEVELOPMENT_IMODEL_ACTION = CREATE_NEW but authorization/creation failed: {imodel_provision_result.failure_category} -- {imodel_provision_result.detail}")
        adopted_imodel = imodel_provision_result.imodel
        development_imodel_created_this_build = imodel_provision_result.created_this_call
        _emit("DEVELOPMENT_IMODEL_CREATED_THIS_BUILD =", development_imodel_created_this_build)

    _emit("RECOMMENDED_BENTLEY_IMODEL_ID =", adopted_imodel.imodel_id)

    # --- verify adopted iModel ---
    dev_full_config = bic.BentleyClientConfig(client_id=client._config.client_id, itwin_id=adopted_itwin.itwin_id, imodel_id=adopted_imodel.imodel_id, access_token_provider=client._config.access_token_provider)
    dev_full_client = bic.BentleyItwinClient(config=dev_full_config, transport=bic.BentleyHttpTransport())
    imodel_metadata = dev_full_client.get_imodel_metadata()
    _emit("DEVELOPMENT_IMODEL_METADATA = SUCCESS")
    _emit("DEVELOPMENT_IMODEL_ITWIN_ID_MATCH =", "YES" if imodel_metadata.itwin_id == adopted_itwin.itwin_id else "NO")

    try:
        elements = dev_full_client.get_elements()
        _emit("DEVELOPMENT_IMODEL_CONTENT_STATUS =", "EMPTY_NOT_YET_POPULATED" if not elements else f"POPULATED ({len(elements)} elements)")
    except Exception as exc:  # noqa: BLE001 -- content check is informational only, never blocking
        _emit("DEVELOPMENT_IMODEL_CONTENT_STATUS = NOT_CHECKED", type(exc).__name__)

    _emit("TEST_ITWIN_PRESERVED = YES")

    captured = capsys.readouterr()
    assert os.environ["BENTLEY_CLIENT_SECRET"] not in captured.out
    assert os.environ["BENTLEY_CLIENT_SECRET"] not in captured.err
