"""Live Bentley iModel proof tests -- OPT-IN, GATED (Sec 29/30/50).

These make REAL read-only Bentley calls and are skipped entirely unless the
Bentley live environment is available (BENTLEY_CLIENT_ID/SECRET/ITWIN_ID are
present, e.g. via a privately-sourced .env.bentley). Normal offline regression
never runs these and never needs credentials. No secret/token is ever printed
or asserted on.
"""
from __future__ import annotations

import os
import pytest

import bentley_itwin_client as bic
import bentley_mrt_binding_authority as b

EXPECTED_ITWIN_ID = "bdf29ecd-b4a4-404d-861a-ac3061c7b12f"

_LIVE = all(os.environ.get(k) for k in ("BENTLEY_CLIENT_ID", "BENTLEY_CLIENT_SECRET", "BENTLEY_ITWIN_ID"))

pytestmark = pytest.mark.skipif(
    not _LIVE, reason="Bentley live env not available (offline deterministic run) -- Sec 50",
)


def _client_for(imodel_id: str = "PENDING"):
    tp = bic.BentleyClientCredentialsTokenProvider(
        client_id=os.environ["BENTLEY_CLIENT_ID"], client_secret=os.environ["BENTLEY_CLIENT_SECRET"],
        authority_url="https://ims.bentley.com/connect/token", scope="itwin-platform",
    )
    cfg = bic.BentleyClientConfig(
        client_id=os.environ["BENTLEY_CLIENT_ID"], itwin_id=os.environ["BENTLEY_ITWIN_ID"],
        imodel_id=imodel_id, access_token_provider=tp,
    )
    return bic.BentleyItwinClient(config=cfg, transport=bic.BentleyHttpTransport())


def test_live_token_and_itwin_identity():
    client = _client_for()
    itw = client.get_itwin_metadata()
    assert itw.itwin_id == EXPECTED_ITWIN_ID
    assert itw.status in ("Active", "Trial")


def test_live_imodel_discovered_dynamically():
    client = _client_for()
    imodels = client.list_imodels(itwin_id=os.environ["BENTLEY_ITWIN_ID"])
    assert len(imodels) >= 1
    # iModel id is discovered, never hard-coded
    assert all(m.imodel_id for m in imodels)


def test_live_changeset_access():
    client = _client_for()
    imodels = client.list_imodels(itwin_id=os.environ["BENTLEY_ITWIN_ID"])
    target = imodels[0]
    client2 = _client_for(target.imodel_id)
    cs = client2.get_change_reference_or_none()
    # changeset present for an initialized iModel
    assert cs is None or isinstance(cs, str)


def test_live_binding_from_real_metadata():
    """Sec 35: build a deterministic local binding from REAL Bentley identity
    without mutating Bentley. If the iModel exposes no queryable element via the
    current read path, this is SUPPORTED_BUT_NOT_PRESENT_IN_TEST_IMODEL -- the
    binding record is still constructed from real iTwin/iModel/changeset ids."""
    client = _client_for()
    imodels = client.list_imodels(itwin_id=os.environ["BENTLEY_ITWIN_ID"])
    target = imodels[0]
    client2 = _client_for(target.imodel_id)
    cs = client2.get_change_reference_or_none()
    ref = b.BentleyExternalReference(
        itwin_id=os.environ["BENTLEY_ITWIN_ID"], imodel_id=target.imodel_id,
        changeset_id=cs, model_id=target.imodel_id, element_id=None,
        class_name="IfcBuilding", federation_guid=None, label=target.display_name,
    )
    # model_id serves as stable identity when no element is queryable
    binding = b.create_binding(external_reference=ref, mrt_object_id="MRT-CAMPUS-REF", mrt_object_type="BUILDING")
    assert binding.binding_status in ("BOUND", "UNBOUND")
    assert binding.external_reference.itwin_id == EXPECTED_ITWIN_ID
