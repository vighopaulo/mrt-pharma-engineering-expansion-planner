"""Bentley Development Resource Adoption Build: focused tests proving the
discover -> classify -> reuse-or-create -> verify -> provision-iModel ->
verify workflow for the persistent (non-Test) development iTwin/iModel --
offline only, via a deterministic fake transport.

GOVERNANCE: this file tests ONLY the NEW classification/decision logic in
`bentley_access_recovery.py` plus the (additive) `status` field and
name-optional `list_imodels()` in `bentley_itwin_client.py`. It never
mutates Access Control, never executes a live create, and never modifies
canonical/OpenUSD/NVIDIA code.
"""

import inspect

import bentley_access_recovery as bar
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
        self.get_calls = []
        self.post_calls = []

    def get(self, *, path, params, access_token, accept=None, extra_headers=None):
        self.get_calls.append((path, params))
        return self._get_responses[path]

    def post(self, *, path, json_body, access_token, accept=None, extra_headers=None):
        self.post_calls.append((path, json_body))
        if path in self._post_errors:
            import urllib.error
            raise urllib.error.HTTPError(url=path, code=self._post_errors[path], msg="error", hdrs=None, fp=None)
        return self._post_responses[path]


def _client(get_responses=None, post_responses=None, post_errors=None, itwin_id="ITWIN-TEST", imodel_id="IMODEL-TEST"):
    transport = _FakeTransport(get_responses, post_responses, post_errors)
    config = bic.BentleyClientConfig(client_id="fake-client-id", itwin_id=itwin_id, imodel_id=imodel_id, access_token_provider=_FakeTokenProvider())
    return bic.BentleyItwinClient(config=config, transport=transport), transport


_TEST_ITWIN_ID = "ITWIN-TEST"
_DEV_ITWIN_ROW = {"id": "ITWIN-DEV-EXISTING", "displayName": "MRTway Development Twin", "class": "Endeavor", "status": "Active"}
_ACCOUNT_ROW = {"id": "ITWIN-ACCOUNT-ROOT", "displayName": "Acme Corp", "class": "Account", "status": "Active"}
_TEST_ROW = {"id": _TEST_ITWIN_ID, "displayName": "Test iTwin", "class": "Endeavor", "status": "Active"}
_INACTIVE_ROW = {"id": "ITWIN-OLD", "displayName": "Old Dev Twin", "class": "Endeavor", "status": "Inactive"}


# ===========================================================================
# Items 1-2: discovery before creation; suitable existing iTwin reused.
# ===========================================================================


def test_1_discovery_occurs_before_creation():
    client, transport = _client(get_responses={"/itwins": {"iTwins": [_TEST_ROW, _DEV_ITWIN_ROW]}})
    bar.discover_and_decide_development_itwin(client, configured_test_itwin_id=_TEST_ITWIN_ID)
    assert transport.get_calls == [("/itwins", {"includeInactive": "true"})]
    assert transport.post_calls == []


def test_2_suitable_existing_itwin_is_reused_even_with_different_display_name():
    client, _transport = _client(get_responses={"/itwins": {"iTwins": [_TEST_ROW, _DEV_ITWIN_ROW]}})
    decision = bar.discover_and_decide_development_itwin(client, configured_test_itwin_id=_TEST_ITWIN_ID)
    assert decision.action == "REUSE_EXISTING"
    assert decision.adopted_itwin.itwin_id == "ITWIN-DEV-EXISTING"
    assert decision.adopted_itwin.display_name == "MRTway Development Twin"  # NOT "MRT Pharma Development" -- adopted anyway


# ===========================================================================
# Items 3-4: Test-iTwin never mistaken for development iTwin; classification
# by ID/type/status, never name.
# ===========================================================================


def test_3_test_itwin_never_adopted_solely_by_name():
    # A row NAMED like a development twin but whose ID equals the configured Test-iTwin must be rejected.
    disguised_test_row = {"id": _TEST_ITWIN_ID, "displayName": "MRT Pharma Development", "class": "Endeavor", "status": "Active"}
    client, _transport = _client(get_responses={"/itwins": {"iTwins": [disguised_test_row]}})
    decision = bar.discover_and_decide_development_itwin(client, configured_test_itwin_id=_TEST_ITWIN_ID)
    assert decision.action == "CREATE_NEW"  # the only candidate was rejected as the Test-iTwin, so nothing adoptable exists
    classifications = bar.classify_development_itwin_candidates((bic.BentleyITwinMetadata(itwin_id=_TEST_ITWIN_ID, display_name="MRT Pharma Development", class_name="Endeavor", status="Active"),), configured_test_itwin_id=_TEST_ITWIN_ID)
    assert classifications[0].relationship == "TEST_ITWIN"
    assert classifications[0].adoptable is False


def test_4_candidate_identity_determined_by_id_type_status_not_name():
    candidates = (
        bic.BentleyITwinMetadata(itwin_id="ITWIN-DEV-EXISTING", display_name="Totally Unrelated Name", class_name="Endeavor", status="Active"),
    )
    classified = bar.classify_development_itwin_candidates(candidates, configured_test_itwin_id=_TEST_ITWIN_ID)
    assert classified[0].relationship == "SEPARATE_DEVELOPMENT_ITWIN"
    assert classified[0].adoptable is True
    assert bar.RESOURCE_ADOPTION_BASED_ON_IDENTITY_AND_TYPE_NOT_NAME_ONLY is True


# ===========================================================================
# Items 5-8: no duplicate POST on rerun; ambiguity stops; exactly one
# create attempt when nothing suitable; failed POST never retried.
# ===========================================================================


def test_5_no_duplicate_itwin_post_on_rerun_when_existing_found():
    client, transport = _client(get_responses={"/itwins": {"iTwins": [_TEST_ROW, _DEV_ITWIN_ROW]}})
    bar.discover_and_decide_development_itwin(client, configured_test_itwin_id=_TEST_ITWIN_ID)
    bar.discover_and_decide_development_itwin(client, configured_test_itwin_id=_TEST_ITWIN_ID)
    assert transport.post_calls == []


def test_6_multiple_matching_itwins_stop_as_ambiguous():
    second_dev_row = {"id": "ITWIN-DEV-EXISTING-2", "displayName": "Another Dev Twin", "class": "Endeavor", "status": "Active"}
    client, transport = _client(get_responses={"/itwins": {"iTwins": [_TEST_ROW, _DEV_ITWIN_ROW, second_dev_row]}})
    decision = bar.discover_and_decide_development_itwin(client, configured_test_itwin_id=_TEST_ITWIN_ID)
    assert decision.action == "STOP_AMBIGUOUS"
    assert decision.adopted_itwin is None
    assert transport.post_calls == []


def test_7_no_suitable_itwin_permits_exactly_one_create_attempt():
    discovery_client, _discovery_transport = _client(get_responses={"/itwins": {"iTwins": [_TEST_ROW]}})
    decision = bar.discover_and_decide_development_itwin(discovery_client, configured_test_itwin_id=_TEST_ITWIN_ID)
    assert decision.action == "CREATE_NEW"

    # provision_development_itwin() performs its OWN exact-name search (empty here) before creating:
    provision_client, provision_transport = _client(
        get_responses={"/itwins": {"iTwins": []}},
        post_responses={"/itwins": {"iTwin": {"id": "ITWIN-NEW", "displayName": bar.DEVELOPMENT_ITWIN_NAME, "class": "Endeavor", "status": "Active"}}},
    )
    result = bar.provision_development_itwin(provision_client)
    assert result.created_this_call is True
    assert len(provision_transport.post_calls) == 1


def test_8_failed_or_uncertain_post_never_blindly_retried():
    client, transport = _client(get_responses={"/itwins": {"iTwins": []}}, post_errors={"/itwins": 403})
    result = bar.provision_development_itwin(client)
    assert result.create_authorization == "NOT_AUTHORIZED"
    assert len(transport.post_calls) == 1  # exactly one attempt, never retried
    result2 = bar.provision_development_itwin(client)
    assert len(transport.post_calls) == 2  # a SECOND independent call is a caller decision, not an internal retry


# ===========================================================================
# Items 9-10: adopted iTwin metadata ID matches; adopted iTwin differs from
# Test-iTwin.
# ===========================================================================


def test_9_adopted_itwin_metadata_id_matches():
    client, _transport = _client(get_responses={
        "/itwins": {"iTwins": [_TEST_ROW, _DEV_ITWIN_ROW]},
        "/itwins/ITWIN-DEV-EXISTING": {"iTwin": _DEV_ITWIN_ROW},
    })
    decision = bar.discover_and_decide_development_itwin(client, configured_test_itwin_id=_TEST_ITWIN_ID)
    verify_client, _t2 = _client(get_responses={"/itwins/ITWIN-DEV-EXISTING": {"iTwin": _DEV_ITWIN_ROW}}, itwin_id=decision.adopted_itwin.itwin_id)
    metadata = verify_client.get_itwin_metadata()
    assert metadata.itwin_id == decision.adopted_itwin.itwin_id


def test_10_adopted_itwin_differs_from_test_itwin():
    client, _transport = _client(get_responses={"/itwins": {"iTwins": [_TEST_ROW, _DEV_ITWIN_ROW]}})
    decision = bar.discover_and_decide_development_itwin(client, configured_test_itwin_id=_TEST_ITWIN_ID)
    assert decision.adopted_itwin.itwin_id != _TEST_ITWIN_ID


# ===========================================================================
# Item 11: permissions read but never mutated.
# ===========================================================================


def test_11_permissions_read_never_mutated():
    client, transport = _client(get_responses={"/accesscontrol/itwins/ITWIN-DEV-EXISTING/permissions": {"permissions": ["imodels_read"]}}, itwin_id="ITWIN-DEV-EXISTING")
    permissions = client.get_itwin_permissions()
    assert permissions.permissions == ("imodels_read",)
    assert transport.post_calls == []
    source = inspect.getsource(bar)
    for forbidden in ("add_itwin_user_member", "assign_role", "create_role", "change_permission"):
        assert forbidden not in source


# ===========================================================================
# Items 12-16: iModel discovery/reuse/create/ambiguity.
# ===========================================================================


def test_12_imodel_discovery_occurs_before_creation():
    client, transport = _client(get_responses={"/imodels": {"iModels": []}}, itwin_id="ITWIN-DEV-EXISTING")
    bar.discover_and_decide_development_imodel(client, itwin_id="ITWIN-DEV-EXISTING")
    assert transport.get_calls == [("/imodels", {"iTwinId": "ITWIN-DEV-EXISTING"})]
    assert transport.post_calls == []


def test_13_suitable_existing_imodel_is_reused():
    client, _transport = _client(get_responses={"/imodels": {"iModels": [{"id": "IMODEL-EXISTING", "displayName": "MRT Pharma Development Model"}]}}, itwin_id="ITWIN-DEV-EXISTING")
    decision = bar.discover_and_decide_development_imodel(client, itwin_id="ITWIN-DEV-EXISTING")
    assert decision.action == "REUSE_EXISTING"
    assert decision.adopted_imodel.imodel_id == "IMODEL-EXISTING"


def test_14_no_duplicate_imodel_post_on_rerun():
    client, transport = _client(get_responses={"/imodels": {"iModels": [{"id": "IMODEL-EXISTING", "displayName": "M"}]}}, itwin_id="ITWIN-DEV-EXISTING")
    bar.discover_and_decide_development_imodel(client, itwin_id="ITWIN-DEV-EXISTING")
    bar.discover_and_decide_development_imodel(client, itwin_id="ITWIN-DEV-EXISTING")
    assert transport.post_calls == []


def test_15_multiple_matching_imodels_stop_as_ambiguous():
    client, transport = _client(get_responses={"/imodels": {"iModels": [{"id": "IMODEL-A", "displayName": "M"}, {"id": "IMODEL-B", "displayName": "M2"}]}}, itwin_id="ITWIN-DEV-EXISTING")
    decision = bar.discover_and_decide_development_imodel(client, itwin_id="ITWIN-DEV-EXISTING")
    assert decision.action == "STOP_AMBIGUOUS"
    assert transport.post_calls == []


def test_16_no_existing_imodel_permits_exactly_one_create_attempt():
    client, transport = _client(
        get_responses={"/imodels": {"iModels": []}},
        post_responses={"/imodels": {"iModel": {"id": "IMODEL-NEW", "iTwinId": "ITWIN-DEV-EXISTING", "displayName": bar.DEVELOPMENT_IMODEL_NAME}}},
        itwin_id="ITWIN-DEV-EXISTING",
    )
    decision = bar.discover_and_decide_development_imodel(client, itwin_id="ITWIN-DEV-EXISTING")
    assert decision.action == "CREATE_NEW"
    result = bar.provision_development_imodel(client, itwin_id="ITWIN-DEV-EXISTING")
    assert result.created_this_call is True
    assert len(transport.post_calls) == 1


# ===========================================================================
# Item 17: iModel metadata iTwinId matches development iTwin.
# ===========================================================================


def test_17_imodel_metadata_itwin_id_matches_development_itwin():
    client, _transport = _client(
        get_responses={"/imodels/IMODEL-EXISTING": {"iModel": {"id": "IMODEL-EXISTING", "iTwinId": "ITWIN-DEV-EXISTING", "displayName": "M"}}},
        itwin_id="ITWIN-DEV-EXISTING", imodel_id="IMODEL-EXISTING",
    )
    metadata = client.get_imodel_metadata()
    assert metadata.itwin_id == "ITWIN-DEV-EXISTING"


# ===========================================================================
# Item 18: empty iModel is not treated as access failure.
# ===========================================================================


def test_18_empty_imodel_is_not_treated_as_access_failure():
    client, _transport = _client(get_responses={"/imodels/IMODEL-EXISTING/elements": {"elements": []}}, imodel_id="IMODEL-EXISTING")
    elements = client.get_elements()
    assert elements == ()  # empty is a valid, successful result -- never raised as a failure


# ===========================================================================
# Item 19: environment variables are not overwritten.
# ===========================================================================


def test_19_environment_variables_not_overwritten(monkeypatch):
    monkeypatch.setenv("BENTLEY_ITWIN_ID", "ORIGINAL-TEST-ITWIN")
    monkeypatch.setenv("BENTLEY_IMODEL_ID", "ORIGINAL-TEST-IMODEL")
    client, _transport = _client(get_responses={"/itwins": {"iTwins": [_TEST_ROW, _DEV_ITWIN_ROW]}})
    bar.discover_and_decide_development_itwin(client, configured_test_itwin_id=_TEST_ITWIN_ID)
    import os
    assert os.environ["BENTLEY_ITWIN_ID"] == "ORIGINAL-TEST-ITWIN"
    assert os.environ["BENTLEY_IMODEL_ID"] == "ORIGINAL-TEST-IMODEL"
    source = inspect.getsource(bar)
    assert "os.environ[" not in source or "os.environ[\"BENTLEY_ITWIN_ID\"] =" not in source


# ===========================================================================
# Item 20: Test-iTwin is preserved.
# ===========================================================================


def test_20_test_itwin_preserved_no_delete_rename_role_calls():
    source = inspect.getsource(bar) + inspect.getsource(bic)
    assert "def delete_itwin" not in source
    assert ".delete(" not in source
    assert "def rename_itwin" not in source


# ===========================================================================
# Items 21-23: corrected core-iTwins/iModels/Access-Control contracts intact.
# ===========================================================================


def test_21_corrected_core_itwins_v1_contract_remains_intact():
    client, transport = _client(get_responses={"/itwins": {"iTwins": []}})
    client.list_itwins(include_inactive=True)
    assert transport.get_calls[0][0] == "/itwins"


def test_22_imodels_api_unchanged():
    client, transport = _client(get_responses={"/imodels/IMODEL-TEST": {"iModel": {"id": "IMODEL-TEST", "iTwinId": "ITWIN-TEST", "displayName": "M"}}})
    client.get_imodel_metadata()
    assert transport.get_calls == [("/imodels/IMODEL-TEST", None)]


def test_23_access_control_api_unchanged():
    client, transport = _client(get_responses={"/accesscontrol/itwins/ITWIN-TEST/permissions": {"permissions": []}})
    client.get_itwin_permissions()
    assert transport.get_calls == [("/accesscontrol/itwins/ITWIN-TEST/permissions", None)]


# ===========================================================================
# Items 24-26: auth flows unchanged; no secrets emitted.
# ===========================================================================


def test_24_service_client_authentication_unchanged():
    assert hasattr(bic, "BentleyClientCredentialsTokenProvider")


def test_25_personal_user_oauth_unchanged():
    import bentley_personal_user_diagnostic as bpud
    assert hasattr(bpud, "BentleyUserAccessTokenProvider")
    assert hasattr(bpud, "run_interactive_user_authorization")


def test_26_no_secrets_emitted(capsys):
    client, _transport = _client(get_responses={"/itwins": {"iTwins": [_TEST_ROW, _DEV_ITWIN_ROW]}})
    decision = bar.discover_and_decide_development_itwin(client, configured_test_itwin_id=_TEST_ITWIN_ID)
    print(decision)
    captured = capsys.readouterr()
    assert "FAKE-TOKEN" not in captured.out


# ===========================================================================
# Items 27-29: canonical/OpenUSD/NVIDIA untouched.
# ===========================================================================


def _import_lines(module) -> list[str]:
    return [l.strip() for l in inspect.getsource(module).splitlines() if l.strip().startswith(("import ", "from "))]


def test_27_canonical_spatial_authority_untouched():
    assert not any("canonical_spatial_authority" in line for line in _import_lines(bar))
    assert not any("canonical_spatial_authority" in line for line in _import_lines(bic))


def test_28_openusd_untouched():
    lines = _import_lines(bar) + _import_lines(bic)
    assert not any("pxr" in line.lower() or "openusd_spatial_adapter" in line.lower() for line in lines)


def test_29_nvidia_untouched():
    lines = _import_lines(bar) + _import_lines(bic)
    assert not any("omni" in line.lower() or "nvidia" in line.lower() for line in lines)


# ===========================================================================
# Item 30: idempotent on rerun (full discover->decide sequence twice).
# ===========================================================================


def test_30_full_sequence_idempotent_on_rerun():
    client, transport = _client(
        get_responses={"/itwins": {"iTwins": [_TEST_ROW, _DEV_ITWIN_ROW]}, "/imodels": {"iModels": [{"id": "IMODEL-EXISTING", "displayName": "M"}]}},
    )
    first_itwin = bar.discover_and_decide_development_itwin(client, configured_test_itwin_id=_TEST_ITWIN_ID)
    first_imodel = bar.discover_and_decide_development_imodel(client, itwin_id=first_itwin.adopted_itwin.itwin_id)
    second_itwin = bar.discover_and_decide_development_itwin(client, configured_test_itwin_id=_TEST_ITWIN_ID)
    second_imodel = bar.discover_and_decide_development_imodel(client, itwin_id=second_itwin.adopted_itwin.itwin_id)
    assert first_itwin.action == second_itwin.action == "REUSE_EXISTING"
    assert first_imodel.action == second_imodel.action == "REUSE_EXISTING"
    assert first_itwin.adopted_itwin.itwin_id == second_itwin.adopted_itwin.itwin_id
    assert transport.post_calls == []


# ===========================================================================
# Additional: inactive/account rows correctly rejected; status field present.
# ===========================================================================


def test_inactive_candidate_rejected():
    classified = bar.classify_development_itwin_candidates(
        (bic.BentleyITwinMetadata(itwin_id="ITWIN-OLD", display_name="Old Dev Twin", class_name="Endeavor", status="Inactive"),),
        configured_test_itwin_id=_TEST_ITWIN_ID,
    )
    assert classified[0].relationship == "INACTIVE_OR_UNSUITABLE"
    assert classified[0].adoptable is False


def test_account_container_rejected():
    classified = bar.classify_development_itwin_candidates(
        (bic.BentleyITwinMetadata(itwin_id="ITWIN-ACCOUNT-ROOT", display_name="Acme Corp", class_name="Account", status="Active"),),
        configured_test_itwin_id=_TEST_ITWIN_ID,
    )
    assert classified[0].relationship == "ACCOUNT_OR_CONTAINER"
    assert classified[0].adoptable is False


def test_itwin_metadata_status_field_parsed():
    client, _transport = _client(get_responses={"/itwins/ITWIN-TEST": {"iTwin": {"id": "ITWIN-TEST", "displayName": "T", "class": "Project", "status": "Active"}}})
    metadata = client.get_itwin_metadata()
    assert metadata.status == "Active"
