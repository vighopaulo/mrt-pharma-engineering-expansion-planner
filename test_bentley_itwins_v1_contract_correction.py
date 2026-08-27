"""Bentley Client Contract Correction Build: focused tests proving the
core iTwins API request-contract fix (List iTwins / Get iTwin / Create
iTwin audit) -- offline only, via a deterministic fake transport.

GOVERNANCE: this file tests ONLY `bentley_itwin_client.py`'s core iTwins
API methods. It never touches iModels/Access Control/Users behavior
(`GLOBAL_BENTLEY_MEDIA_TYPE_REPLACEMENT = NO`, verified below), never
mutates Access Control, never calls create_itwin/create_imodel with a real
network, and never modifies canonical/OpenUSD/NVIDIA code.
"""

import inspect

import bentley_access_recovery as bar
import bentley_itwin_client as bic
import bentley_personal_user_diagnostic as bpud


class _FakeTokenProvider:
    def get_access_token(self) -> str:
        return "FAKE-TOKEN"


class _FakeTransport:
    def __init__(self, get_responses=None, post_responses=None):
        self._get_responses = get_responses or {}
        self._post_responses = post_responses or {}
        self.get_calls = []
        self.post_calls = []

    def get(self, *, path, params, access_token, accept=None, extra_headers=None):
        self.get_calls.append((path, params, accept, extra_headers))
        return self._get_responses[path]

    def post(self, *, path, json_body, access_token, accept=None, extra_headers=None):
        self.post_calls.append((path, json_body, accept, extra_headers))
        return self._post_responses[path]


def _client(get_responses=None, post_responses=None, itwin_id="ITWIN-1", imodel_id="IMODEL-1"):
    transport = _FakeTransport(get_responses, post_responses)
    config = bic.BentleyClientConfig(client_id="fake-client-id", itwin_id=itwin_id, imodel_id=imodel_id, access_token_provider=_FakeTokenProvider())
    return bic.BentleyItwinClient(config=config, transport=transport), transport


# ===========================================================================
# Items 1-7: List iTwins corrected contract.
# ===========================================================================


def test_1_list_itwins_uses_get():
    client, transport = _client(get_responses={"/itwins": {"iTwins": []}})
    client.list_itwins(display_name="X")
    assert len(transport.get_calls) == 1  # only .get() was ever exercised, never .post()
    assert transport.post_calls == []


def test_2_list_itwins_path_has_no_trailing_slash():
    client, transport = _client(get_responses={"/itwins": {"iTwins": []}})
    client.list_itwins(display_name="X")
    path, _params, _accept, _extra = transport.get_calls[0]
    assert path == "/itwins"


def test_3_list_itwins_uses_v1_itwins_media_type():
    client, transport = _client(get_responses={"/itwins": {"iTwins": []}})
    client.list_itwins(display_name="X")
    _path, _params, accept, _extra = transport.get_calls[0]
    assert accept == bic.ITWINS_MEDIA_TYPE_V1 == "application/vnd.bentley.itwin-platform.v1+json"


def test_4_list_itwins_sends_prefer_return_representation():
    client, transport = _client(get_responses={"/itwins": {"iTwins": []}})
    client.list_itwins(display_name="X")
    _path, _params, _accept, extra = transport.get_calls[0]
    assert extra == {"Prefer": "return=representation"}


def test_5_list_itwins_can_send_include_inactive_true():
    client, transport = _client(get_responses={"/itwins": {"iTwins": []}})
    client.list_itwins(include_inactive=True)
    _path, params, _accept, _extra = transport.get_calls[0]
    assert params == {"includeInactive": "true"}


def test_6_list_itwins_parses_itwins_envelope():
    client, _transport = _client(get_responses={"/itwins": {"iTwins": [{"id": "ITWIN-A", "displayName": "A", "class": "Endeavor"}]}})
    rows = client.list_itwins(display_name="A")
    assert len(rows) == 1
    assert rows[0].itwin_id == "ITWIN-A"


def test_7_list_itwins_returns_typed_metadata():
    client, _transport = _client(get_responses={"/itwins": {"iTwins": [{"id": "ITWIN-A", "displayName": "A", "class": "Endeavor"}]}})
    rows = client.list_itwins(display_name="A")
    assert all(isinstance(r, bic.BentleyITwinMetadata) for r in rows)


# ===========================================================================
# Items 8-11: Get iTwin by ID corrected contract.
# ===========================================================================


def test_8_get_itwin_metadata_uses_id_path():
    client, transport = _client(get_responses={"/itwins/ITWIN-1": {"iTwin": {"id": "ITWIN-1", "displayName": "Test", "class": "Project"}}})
    client.get_itwin_metadata()
    path, _params, _accept, _extra = transport.get_calls[0]
    assert path == "/itwins/ITWIN-1"


def test_9_get_itwin_metadata_uses_v1_media_type():
    client, transport = _client(get_responses={"/itwins/ITWIN-1": {"iTwin": {"id": "ITWIN-1", "displayName": "Test", "class": "Project"}}})
    client.get_itwin_metadata()
    _path, _params, accept, _extra = transport.get_calls[0]
    assert accept == bic.ITWINS_MEDIA_TYPE_V1


def test_10_get_itwin_metadata_parses_itwin_envelope():
    client, _transport = _client(get_responses={"/itwins/ITWIN-1": {"iTwin": {"id": "ITWIN-1", "displayName": "Test Twin", "class": "Project"}}})
    metadata = client.get_itwin_metadata()
    assert metadata.itwin_id == "ITWIN-1"
    assert metadata.display_name == "Test Twin"
    assert metadata.class_name == "Project"


def test_11_get_itwin_metadata_sends_no_prefer_header():
    client, transport = _client(get_responses={"/itwins/ITWIN-1": {"iTwin": {"id": "ITWIN-1", "displayName": "Test", "class": "Project"}}})
    client.get_itwin_metadata()
    _path, _params, _accept, extra = transport.get_calls[0]
    assert extra is None


# ===========================================================================
# Items 12-13: iModels / Access Control media types and paths unchanged.
# ===========================================================================


def test_12_imodels_media_type_unchanged():
    client, transport = _client(get_responses={"/imodels/IMODEL-1": {"iModel": {"id": "IMODEL-1", "iTwinId": "ITWIN-1", "displayName": "M"}}})
    client.get_imodel_metadata()
    path, _params, accept, extra = transport.get_calls[0]
    assert path == "/imodels/IMODEL-1"
    assert accept is None  # BentleyHttpTransport defaults to DEFAULT_BENTLEY_MEDIA_TYPE (v2) -- never changed
    assert extra is None


def test_13_access_control_media_type_and_path_unchanged():
    client, transport = _client(get_responses={"/accesscontrol/itwins/ITWIN-1/permissions": {"permissions": ["imodels_read"]}})
    client.get_itwin_permissions()
    path, _params, accept, extra = transport.get_calls[0]
    assert path == "/accesscontrol/itwins/ITWIN-1/permissions"
    assert accept is None
    assert extra is None


# ===========================================================================
# Items 14-15: token providers unchanged/usable.
# ===========================================================================


def test_14_service_client_token_provider_unchanged():
    assert hasattr(bic, "BentleyClientCredentialsTokenProvider")
    sig = inspect.signature(bic.BentleyClientCredentialsTokenProvider.__init__)
    assert set(sig.parameters) >= {"self", "client_id", "client_secret", "authority_url", "scope"}


def test_15_personal_user_token_provider_still_usable_with_corrected_client():
    provider = bpud.BentleyUserAccessTokenProvider(access_token="FAKE-USER-TOKEN")
    transport = _FakeTransport(get_responses={"/itwins": {"iTwins": [{"id": "ITWIN-DEV", "displayName": "MRT Pharma Development", "class": "Endeavor"}]}})
    config = bic.BentleyClientConfig(client_id="unused", itwin_id="ITWIN-1", imodel_id="IMODEL-1", access_token_provider=provider)
    client = bic.BentleyItwinClient(config=config, transport=transport)
    rows = client.list_itwins(display_name="MRT Pharma Development")
    assert len(rows) == 1


# ===========================================================================
# Item 16: no secret logged.
# ===========================================================================


def test_16_no_authorization_value_logged(capsys):
    client, _transport = _client(get_responses={
        "/itwins": {"iTwins": [{"id": "ITWIN-A", "displayName": "A", "class": "Endeavor"}]},
        "/itwins/ITWIN-1": {"iTwin": {"id": "ITWIN-1", "displayName": "Test", "class": "Project"}},
    })
    client.list_itwins(display_name="A")
    client.get_itwin_metadata()
    captured = capsys.readouterr()
    assert "FAKE-TOKEN" not in captured.out
    assert "Bearer" not in captured.out


# ===========================================================================
# Items 17-19: no mutation triggered by read-only tests.
# ===========================================================================


def test_17_no_create_itwin_post_invoked_by_list_get_reads():
    client, transport = _client(get_responses={
        "/itwins": {"iTwins": []},
        "/itwins/ITWIN-1": {"iTwin": {"id": "ITWIN-1", "displayName": "Test", "class": "Project"}},
    })
    client.list_itwins(display_name="X")
    client.get_itwin_metadata()
    assert transport.post_calls == []


def test_18_no_create_imodel_post_invoked_by_list_get_reads():
    client, transport = _client(get_responses={"/imodels/IMODEL-1": {"iModel": {"id": "IMODEL-1", "iTwinId": "ITWIN-1", "displayName": "M"}}})
    client.get_imodel_metadata()
    assert transport.post_calls == []


def test_19_no_access_control_mutation_invoked():
    source = inspect.getsource(bic)
    for forbidden in ("add_itwin_user_member", "remove_itwin_user_member", "assign_role", "create_role", "add_member", "remove_member"):
        assert forbidden not in source


# ===========================================================================
# Item 20: prior trailing-slash fake-transport assumptions removed.
# ===========================================================================


def test_20_prior_trailing_slash_assumption_removed_from_access_recovery_tests():
    with open("test_bentley_access_recovery.py") as handle:
        source = handle.read()
    assert '"/itwins/":' not in source
    assert 'get_calls == [("/itwins/",' not in source


# ===========================================================================
# Items 21-22: production-client end-to-end correctness.
# ===========================================================================


def test_21_production_client_list_result_finds_configured_test_itwin():
    client, _transport = _client(get_responses={"/itwins": {"iTwins": [
        {"id": "SOME-OTHER-ITWIN", "displayName": "Other", "class": "Endeavor"},
        {"id": "ITWIN-1", "displayName": "Configured Test Twin", "class": "Project"},
    ]}})
    rows = client.list_itwins(include_inactive=True)
    assert any(r.itwin_id == "ITWIN-1" for r in rows)


def test_22_production_client_metadata_result_id_matches_configured_id():
    client, _transport = _client(get_responses={"/itwins/ITWIN-1": {"iTwin": {"id": "ITWIN-1", "displayName": "Configured Test Twin", "class": "Project"}}}, itwin_id="ITWIN-1")
    metadata = client.get_itwin_metadata()
    assert metadata.itwin_id == "ITWIN-1"


# ===========================================================================
# Item 23: diagnostic helpers remain non-authoritative.
# ===========================================================================


def test_23_diagnostic_helpers_never_used_by_production_client_or_access_recovery():
    assert "diagnostic_raw_get" not in inspect.getsource(bic)
    assert "diagnostic_johannes_exact_list_itwins" not in inspect.getsource(bic)
    assert "diagnostic_raw_get" not in inspect.getsource(bar)
    assert "diagnostic_johannes_exact_list_itwins" not in inspect.getsource(bar)


# ===========================================================================
# Items 24-26: canonical/OpenUSD/NVIDIA untouched.
# ===========================================================================


def _import_lines(module) -> list[str]:
    return [l.strip() for l in inspect.getsource(module).splitlines() if l.strip().startswith(("import ", "from "))]


def test_24_canonical_spatial_authority_untouched():
    assert not any("canonical_spatial_authority" in line for line in _import_lines(bic))


def test_25_openusd_untouched():
    lines = _import_lines(bic)
    assert not any("pxr" in line.lower() or "openusd_spatial_adapter" in line.lower() for line in lines)


def test_26_nvidia_untouched():
    lines = _import_lines(bic)
    assert not any("omni" in line.lower() or "nvidia" in line.lower() for line in lines)


# ===========================================================================
# Section 3 governance: no global media-type replacement.
# ===========================================================================


def test_global_media_type_replacement_did_not_happen():
    client, transport = _client(get_responses={
        "/imodels/IMODEL-1": {"iModel": {"id": "IMODEL-1", "iTwinId": "ITWIN-1", "displayName": "M"}},
        "/accesscontrol/itwins/ITWIN-1/permissions": {"permissions": []},
        "/accesscontrol/itwins/ITWIN-1/members/users": {"members": []},
    })
    client.get_imodel_metadata()
    client.get_itwin_permissions()
    client.get_itwin_user_members()
    accepts_used = [accept for (_path, _params, accept, _extra) in transport.get_calls]
    assert all(accept is None for accept in accepts_used)  # none of these were switched to v1
