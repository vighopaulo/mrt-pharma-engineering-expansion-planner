"""Thin Bentley iTwin API client boundary (BIM/iTwin Phase 1).

GOVERNANCE (section 24): this module's ONLY responsibilities are
authentication/request-boundary abstraction, iTwin/iModel metadata
retrieval, element/property retrieval, placement/transform retrieval, and
changeset metadata retrieval. It contains NO canonical spatial identity
rules, room/equipment matching, routing, installed-network calculation,
decay, production, clinical scheduling, economics, or simulation logic --
all of that remains exclusively in `canonical_spatial_authority.py` and the
existing engineering authorities.

NO LIVE CALL IN THIS PHASE (section 28): no HTTP request is ever made by
this module's own code outside of the injectable `BentleyTransport`
boundary, and no test in this repository supplies a real transport --
only a deterministic fake (section 25-26).

NO HARD-CODED CREDENTIALS (section 25): `BentleyClientConfig` requires the
caller to inject client ID, iTwin ID, iModel ID, and an access-token
provider -- none of these are literals in this file.

Raw vendor JSON terminates here (section 27): every public method returns a
typed result record, never a raw untyped dict, so vendor-shape details never
leak past this boundary.
"""

from __future__ import annotations

import json as _json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

DEFAULT_BENTLEY_MEDIA_TYPE = "application/vnd.bentley.itwin-platform.v2+json"
"""The pre-existing default `Accept` media type -- still used verbatim by
every Bentley API family NOT explicitly corrected in the Client Contract
Correction build (iModels, Access Control, Users): `GLOBAL_BENTLEY_MEDIA_
TYPE_REPLACEMENT = NO`."""

ITWINS_MEDIA_TYPE_V1 = "application/vnd.bentley.itwin-platform.v1+json"
"""Client Contract Correction build: the CORE iTwins API's proven-working
media type (Get iTwin, List iTwins, Create iTwin) -- confirmed live via a
controlled experiment reproducing Johannes Renner's actually-working
`itwin-demo-apis` request contract byte-for-byte (`GET /itwins?
includeInactive=true` + this media type + `Prefer: return=representation`
returned HTTP 200 and included the configured Test-iTwin, where the
previous v2-media-type/trailing-slash request returned HTTP 404
`ResourceNotFound`). Applies ONLY to the core iTwins API methods below --
never propagated to iModels/Access Control/Users (section 3)."""


class BentleyAccessTokenProvider(Protocol):
    """Injectable auth boundary -- this module never performs OAuth itself."""

    def get_access_token(self) -> str: ...


class BentleyTransport(Protocol):
    """Injectable HTTP boundary. Tests supply a deterministic fake
    implementation; no real network/SDK dependency is required for
    regression (section 26). `accept`/`extra_headers` (Client Contract
    Correction build) are OPTIONAL, additive per-call overrides -- omitted
    calls behave exactly as before (`DEFAULT_BENTLEY_MEDIA_TYPE`, no extra
    headers), so iModels/Access Control/Users callers are unaffected."""

    def get(
        self, *, path: str, params: Mapping[str, str] | None, access_token: str,
        accept: str | None = None, extra_headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, object]: ...

    # Bentley Access Recovery build: the smallest narrow addition needed to
    # reach the permissions/create-iTwin/create-iModel endpoints -- reuses
    # the SAME injectable-transport pattern as `get`, never a second HTTP boundary.
    def post(
        self, *, path: str, json_body: Mapping[str, object], access_token: str,
        accept: str | None = None, extra_headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, object]: ...


@dataclass(frozen=True)
class BentleyClientConfig:
    """No literal credentials -- every value is caller-injected (section 25)."""

    client_id: str
    itwin_id: str
    imodel_id: str
    access_token_provider: BentleyAccessTokenProvider
    base_url: str = "https://api.bentley.com"


BENTLEY_LIVE_ENV_VARS = ("BENTLEY_CLIENT_ID", "BENTLEY_CLIENT_SECRET", "BENTLEY_ITWIN_ID", "BENTLEY_IMODEL_ID")
"""Section 3/16: the exact environment-variable convention this phase reuses
-- no second convention invented. `BENTLEY_SCOPE` is optional (has a
sensible default in `BentleyClientCredentialsTokenProvider`)."""


class BentleyConfigurationError(RuntimeError):
    """Section 4: raised when required live Bentley environment/configuration
    is absent -- a controlled, explicit failure, never a fabricated fallback."""


def bentley_live_environment_available() -> bool:
    """Section 15: the opt-in gate live tests use to decide whether to run
    at all -- never attempts a network call itself."""
    return all(os.environ.get(name) for name in BENTLEY_LIVE_ENV_VARS)


def build_config_from_environment(*, access_token_provider: BentleyAccessTokenProvider) -> BentleyClientConfig:
    """Section 4: builds a `BentleyClientConfig` from environment variables
    only -- fails with `BentleyConfigurationError` (never silently falls back
    to a fabricated ID) when any required variable is missing."""
    missing = [name for name in BENTLEY_LIVE_ENV_VARS if not os.environ.get(name)]
    if missing:
        raise BentleyConfigurationError(f"Missing required Bentley live environment variable(s): {', '.join(missing)}")
    return BentleyClientConfig(
        client_id=os.environ["BENTLEY_CLIENT_ID"], itwin_id=os.environ["BENTLEY_ITWIN_ID"],
        imodel_id=os.environ["BENTLEY_IMODEL_ID"], access_token_provider=access_token_provider,
    )


class BentleyClientCredentialsTokenProvider:
    """Section 3/26: OAuth2 client-credentials token acquisition using only
    the Python standard library (`urllib`) -- no new dependency, no
    hardcoded secret (client_secret is caller-injected, read from
    environment by the caller, never a literal here)."""

    def __init__(self, *, client_id: str, client_secret: str, authority_url: str, scope: str = "itwin-platform") -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._authority_url = authority_url
        self._scope = scope

    def get_access_token(self) -> str:  # pragma: no cover -- exercised only by opt-in live tests
        body = urllib.parse.urlencode({
            "grant_type": "client_credentials", "client_id": self._client_id, "client_secret": self._client_secret,
            "scope": self._scope,
        }).encode("utf-8")
        request = urllib.request.Request(self._authority_url, data=body, method="POST")
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 -- live opt-in path only
            payload = _json.loads(response.read().decode("utf-8"))
        return str(payload["access_token"])


class BentleyHttpTransport:
    """Section 26: a real `BentleyTransport` implementation using only the
    standard library -- exercised ONLY by opt-in live tests (section 15);
    never used by the offline/deterministic test suite."""

    def __init__(self, *, base_url: str = "https://api.bentley.com") -> None:
        self._base_url = base_url.rstrip("/")

    def get(
        self, *, path: str, params: Mapping[str, str] | None, access_token: str,
        accept: str | None = None, extra_headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, object]:  # pragma: no cover
        url = f"{self._base_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, method="GET")
        request.add_header("Authorization", f"Bearer {access_token}")
        request.add_header("Accept", accept or DEFAULT_BENTLEY_MEDIA_TYPE)
        for header_name, header_value in (extra_headers or {}).items():
            request.add_header(header_name, header_value)
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 -- live opt-in path only
            return _json.loads(response.read().decode("utf-8"))

    def post(
        self, *, path: str, json_body: Mapping[str, object], access_token: str,
        accept: str | None = None, extra_headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, object]:  # pragma: no cover
        url = f"{self._base_url}{path}"
        body = _json.dumps(json_body).encode("utf-8")
        request = urllib.request.Request(url, data=body, method="POST")
        request.add_header("Authorization", f"Bearer {access_token}")
        request.add_header("Accept", accept or DEFAULT_BENTLEY_MEDIA_TYPE)
        request.add_header("Content-Type", "application/json")
        for header_name, header_value in (extra_headers or {}).items():
            request.add_header(header_name, header_value)
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 -- live opt-in path only
            return _json.loads(response.read().decode("utf-8"))


@dataclass(frozen=True)
class BentleyITwinMetadata:
    """Development Resource Adoption build: `status` (`"Active"`/
    `"Inactive"`/`"Trial"`/`"Unknown"`) added -- needed to classify a
    candidate development iTwin honestly (section 4/9) without inventing a
    second lookup. Additive/backward-compatible default."""

    itwin_id: str
    display_name: str
    class_name: str = "Unknown"
    status: str = "Unknown"


@dataclass(frozen=True)
class BentleyIModelMetadata:
    imodel_id: str
    itwin_id: str
    display_name: str


@dataclass(frozen=True)
class BentleyItwinPermissions:
    """Bentley Access Recovery build (section 5-6): the service-client's
    permission set on ONE iTwin -- vendor JSON terminates here, like every
    other method on this client (section 27)."""

    itwin_id: str
    permissions: tuple[str, ...]


@dataclass(frozen=True)
class BentleyItwinRole:
    """Membership Diagnostic build: one role assignment on an iTwin User
    Member, per https://developer.bentley.com/apis/access-control-v2/
    operations/get-itwin-user-members/."""

    role_id: str
    display_name: str


@dataclass(frozen=True)
class BentleyItwinUserMember:
    """Membership Diagnostic build: one row from Get iTwin User Members.
    This endpoint is documented as USER members only (`/members/users`) --
    fields are human-identity fields (email/givenName/surname/organization),
    with NO documented client-ID/service-application field. `member_id` is
    the Bentley-assigned member `id`, never assumed equal to an OAuth
    `client_id` (section 4 of the diagnostic prompt)."""

    member_id: str
    email: str | None
    given_name: str | None
    surname: str | None
    organization: str | None
    roles: tuple[BentleyItwinRole, ...]


@dataclass(frozen=True)
class BentleyElementRecordRaw:
    """Raw vendor-shaped element payload (section 27) -- terminates at this
    client boundary; callers normalize it into
    `canonical_spatial_authority.BentleyElementRecord` before it ever
    reaches canonical spatial identity/binding logic."""

    element_id: str
    class_name: str
    label: str | None
    parent_element_id: str | None
    properties: Mapping[str, object]


@dataclass(frozen=True)
class BentleyChangesetMetadata:
    change_reference: str
    imodel_id: str
    description: str = ""


@dataclass(frozen=True)
class BentleyLiveElementRecord:
    """Section 7: vendor-neutral NORMALIZED shape for one live-retrieved
    Bentley element -- still lives at the CLIENT boundary (no canonical
    identity decision is made here); `canonical_reference_value` is
    extracted from the synchronized IFC `ObjectType` property (section 7),
    never guessed -- None if the source element does not carry one."""

    external_project_id: str
    external_model_id: str
    external_element_id: str
    external_global_id: str | None
    element_class: str
    label: str | None
    canonical_reference_value: str | None
    change_reference: str | None
    placement_xyz_m: tuple[float, float, float] | None


def normalize_live_element(
    raw: BentleyElementRecordRaw, *, itwin_id: str, imodel_id: str, change_reference: str | None = None,
) -> BentleyLiveElementRecord:
    """Section 7: normalizes one raw Bentley element into the vendor-neutral
    `BentleyLiveElementRecord` shape. `ObjectType` (case-insensitive) is the
    canonical-reference source (section 7); `GlobalId` is verification
    evidence only, never the binding key (section 6)."""
    object_type = raw.properties.get("ObjectType", raw.properties.get("objecttype"))
    global_id = raw.properties.get("GlobalId", raw.properties.get("globalId"))
    placement = raw.properties.get("placement_xyz_m")
    return BentleyLiveElementRecord(
        external_project_id=itwin_id, external_model_id=imodel_id, external_element_id=raw.element_id,
        external_global_id=str(global_id) if global_id is not None else None, element_class=raw.class_name,
        label=raw.label, canonical_reference_value=str(object_type) if object_type is not None else None,
        change_reference=change_reference, placement_xyz_m=tuple(placement) if placement is not None else None,  # type: ignore[arg-type]
    )


class BentleyItwinClient:
    """Thin retrieval boundary. Every method delegates entirely to the
    injected `BentleyTransport` -- no canonical spatial/engineering
    knowledge exists in this class."""

    def __init__(self, *, config: BentleyClientConfig, transport: BentleyTransport) -> None:
        self._config = config
        self._transport = transport

    def get_itwin_metadata(self) -> BentleyITwinMetadata:
        """Client Contract Correction build: uses `ITWINS_MEDIA_TYPE_V1`
        (`application/vnd.bentley.itwin-platform.v1+json`) -- the previous
        v2 media type produced a live HTTP 404 `ResourceNotFound` ("Verify
        the API URL and the Accept header"); no `Prefer` header is sent
        (never documented/required for single-resource GET, section 6)."""
        payload = self._transport.get(
            path=f"/itwins/{self._config.itwin_id}", params=None, accept=ITWINS_MEDIA_TYPE_V1,
            access_token=self._config.access_token_provider.get_access_token(),
        )
        # Bentley's "Get iTwin" response wraps the object in an "iTwin"
        # envelope (confirmed against https://developer.bentley.com/apis/
        # itwins/operations/get-itwin/) -- never a flat payload.
        row = payload["iTwin"]  # type: ignore[index]
        return BentleyITwinMetadata(
            itwin_id=str(row["id"]), display_name=str(row.get("displayName", "")),  # type: ignore[union-attr]
            class_name=str(row.get("class", "Unknown")), status=str(row.get("status", "Unknown")),  # type: ignore[union-attr]
        )

    def get_imodel_metadata(self) -> BentleyIModelMetadata:
        payload = self._transport.get(
            path=f"/imodels/{self._config.imodel_id}", params=None,
            access_token=self._config.access_token_provider.get_access_token(),
        )
        # Bentley's "Get iModel" response wraps the object in an "iModel"
        # envelope (confirmed against https://developer.bentley.com/apis/
        # imodels-v2/operations/get-imodel-details/) -- never a flat payload.
        row = payload["iModel"]  # type: ignore[index]
        return BentleyIModelMetadata(
            imodel_id=str(row["id"]), itwin_id=str(row.get("iTwinId", self._config.itwin_id)),  # type: ignore[union-attr]
            display_name=str(row.get("displayName", "")),  # type: ignore[union-attr]
        )

    def get_itwin_permissions(self) -> BentleyItwinPermissions:
        """Bentley Access Recovery build (section 5): GET Access Control v2
        `/accesscontrol/itwins/{id}/permissions` -- reuses the SAME
        `.get()` transport boundary as every other retrieval method."""
        payload = self._transport.get(
            path=f"/accesscontrol/itwins/{self._config.itwin_id}/permissions", params=None,
            access_token=self._config.access_token_provider.get_access_token(),
        )
        return BentleyItwinPermissions(itwin_id=self._config.itwin_id, permissions=tuple(str(p) for p in payload.get("permissions", ())))

    def get_itwin_user_members(self) -> tuple[BentleyItwinUserMember, ...]:
        """Membership Diagnostic build: GET Access Control v2
        `/accesscontrol/itwins/{id}/members/users` -- confirmed against
        https://developer.bentley.com/apis/access-control-v2/operations/
        get-itwin-user-members/. Read-only; never mutates membership. This
        is a USER-members endpoint only -- it does not represent service
        applications, so `member_id` is never compared to an OAuth
        `client_id` here (that comparison belongs to the caller, if at
        all, with a documented identifier)."""
        payload = self._transport.get(
            path=f"/accesscontrol/itwins/{self._config.itwin_id}/members/users", params=None,
            access_token=self._config.access_token_provider.get_access_token(),
        )
        rows = payload.get("members", ())
        return tuple(
            BentleyItwinUserMember(
                member_id=str(row["id"]), email=row.get("email"), given_name=row.get("givenName"),
                surname=row.get("surname"), organization=row.get("organization"),
                roles=tuple(BentleyItwinRole(role_id=str(r["id"]), display_name=str(r.get("displayName", ""))) for r in row.get("roles", ())),
            )
            for row in rows  # type: ignore[union-attr]
        )

    def list_itwins(self, *, display_name: str | None = None, include_inactive: bool = False) -> tuple[BentleyITwinMetadata, ...]:
        """Client Contract Correction build: corrected to the LIVE-PROVEN
        core iTwins API contract -- `GET /itwins` (NO trailing slash;
        `/itwins/` was an undocumented path that produced a live HTTP 404),
        `Accept: {ITWINS_MEDIA_TYPE_V1}`, `Prefer: return=representation`
        (both reproduced byte-for-byte from Johannes Renner's actually-
        working `itwin-demo-apis` request, which returned HTTP 200 and
        included the configured Test-iTwin). `display_name` remains an
        optional documented filter (section 4); `include_inactive` adds the
        exact `includeInactive=true` parameter proven live."""
        params: dict[str, str] = {}
        if display_name is not None:
            params["displayName"] = display_name
        if include_inactive:
            params["includeInactive"] = "true"
        payload = self._transport.get(
            path="/itwins", params=params or None, accept=ITWINS_MEDIA_TYPE_V1, extra_headers={"Prefer": "return=representation"},
            access_token=self._config.access_token_provider.get_access_token(),
        )
        rows = payload.get("iTwins", ())
        return tuple(
            BentleyITwinMetadata(
                itwin_id=str(row["id"]), display_name=str(row.get("displayName", "")),
                class_name=str(row.get("class", "Unknown")), status=str(row.get("status", "Unknown")),
            )
            for row in rows  # type: ignore[union-attr]
        )

    def create_itwin(self, *, display_name: str, class_name: str = "Endeavor", subclass: str = "Project") -> BentleyITwinMetadata:
        """Bentley Access Recovery build (section 12): the fallback path
        used ONLY when the configured Test-iTwin remains the verified
        blocker (section 11 decision gate); never called merely because
        Bentley support mentioned it as an option. Client Contract
        Correction build (section 8, audit-only -- NEVER executed live in
        that build): path corrected to `POST /itwins` (no trailing slash,
        matching Johannes's working `createITwin()` and the SAME collection
        resource the proven List iTwins fix applies to) and
        `Accept: application/vnd.bentley.itwin-platform.v1+json` (same
        core-iTwins media type); NO `Prefer` header (never demonstrated for
        this operation)."""
        payload = self._transport.post(
            path="/itwins", json_body={"class": class_name, "subClass": subclass, "displayName": display_name, "status": "Active"},
            accept=ITWINS_MEDIA_TYPE_V1, access_token=self._config.access_token_provider.get_access_token(),
        )
        row = payload["iTwin"]  # type: ignore[index]
        return BentleyITwinMetadata(
            itwin_id=str(row["id"]), display_name=str(row.get("displayName", "")),  # type: ignore[union-attr]
            class_name=str(row.get("class", class_name)), status=str(row.get("status", "Active")),  # type: ignore[union-attr]
        )

    def list_imodels(self, *, itwin_id: str, display_name: str | None = None) -> tuple[BentleyIModelMetadata, ...]:
        """Bentley Access Recovery build (section 14): idempotent
        find-before-create check for development iModels. Development
        Resource Adoption build: `display_name` is now OPTIONAL -- omitted
        entirely, this becomes a broad discovery call (all iModels under
        `itwin_id`), needed to discover pre-existing development iModels
        that were never named via this exact filter (section 11)."""
        params: dict[str, str] = {"iTwinId": itwin_id}
        if display_name is not None:
            params["name"] = display_name
        payload = self._transport.get(
            path="/imodels", params=params,
            access_token=self._config.access_token_provider.get_access_token(),
        )
        rows = payload.get("iModels", ())
        return tuple(
            BentleyIModelMetadata(imodel_id=str(row["id"]), itwin_id=itwin_id, display_name=str(row.get("displayName", "")))
            for row in rows  # type: ignore[union-attr]
        )

    def create_imodel(self, *, itwin_id: str, display_name: str) -> BentleyIModelMetadata:
        """Bentley Access Recovery build (section 14): POST `/imodels` --
        creates ONE development iModel under the given iTwin."""
        payload = self._transport.post(
            path="/imodels", json_body={"iTwinId": itwin_id, "displayName": display_name},
            access_token=self._config.access_token_provider.get_access_token(),
        )
        row = payload["iModel"]  # type: ignore[index]
        return BentleyIModelMetadata(imodel_id=str(row["id"]), itwin_id=itwin_id, display_name=str(row.get("displayName", "")))  # type: ignore[union-attr]

    def get_elements(self, *, class_names: Sequence[str] | None = None) -> tuple[BentleyElementRecordRaw, ...]:
        params = {"classNames": ",".join(class_names)} if class_names else None
        payload = self._transport.get(
            path=f"/imodels/{self._config.imodel_id}/elements", params=params,
            access_token=self._config.access_token_provider.get_access_token(),
        )
        rows = payload.get("elements", ())
        return tuple(
            BentleyElementRecordRaw(
                element_id=str(row["id"]), class_name=str(row.get("class", "Unknown")),
                label=row.get("label"), parent_element_id=row.get("parentId"),
                properties=row.get("properties", {}),
            )
            for row in rows  # type: ignore[union-attr]
        )

    def get_latest_changeset(self) -> BentleyChangesetMetadata:
        payload = self._transport.get(
            path=f"/imodels/{self._config.imodel_id}/changesets", params={"$top": "1"},
            access_token=self._config.access_token_provider.get_access_token(),
        )
        changesets = payload.get("changesets", ())
        if not changesets:
            raise ValueError(f"No changesets found for iModel {self._config.imodel_id}")
        latest = changesets[0]  # type: ignore[index]
        return BentleyChangesetMetadata(
            change_reference=str(latest["id"]), imodel_id=self._config.imodel_id,
            description=str(latest.get("description", "")),
        )

    def get_change_reference_or_none(self) -> str | None:
        """Section 20: best-effort changeset capture -- returns None (never
        fabricated) when the endpoint has no changesets yet."""
        try:
            return self.get_latest_changeset().change_reference
        except (ValueError, KeyError):
            return None

    def find_element(
        self, *, object_type: str | None = None, global_id: str | None = None, label: str | None = None,
    ) -> BentleyElementRecordRaw | None:
        """Section 18: controlled lookup order -- (1) exact `ObjectType`
        (canonical reference) match, (2) exact `GlobalId` match as
        verification fallback, (3) exact label match as diagnostic fallback
        only. NEVER fuzzy text matching."""
        elements = self.get_elements()
        if object_type is not None:
            for element in elements:
                candidate = element.properties.get("ObjectType", element.properties.get("objecttype"))
                if candidate is not None and str(candidate) == object_type:
                    return element
        if global_id is not None:
            for element in elements:
                candidate = element.properties.get("GlobalId", element.properties.get("globalId"))
                if candidate is not None and str(candidate) == global_id:
                    return element
        if label is not None:
            for element in elements:
                if element.label == label:
                    return element
        return None

    def find_live_element(
        self, *, object_type: str | None = None, global_id: str | None = None, label: str | None = None,
        capture_change_reference: bool = True,
    ) -> BentleyLiveElementRecord | None:
        """Section 7/20: `find_element` + normalization + best-effort
        changeset capture in one convenience call."""
        raw = self.find_element(object_type=object_type, global_id=global_id, label=label)
        if raw is None:
            return None
        change_reference = self.get_change_reference_or_none() if capture_change_reference else None
        return normalize_live_element(
            raw, itwin_id=self._config.itwin_id, imodel_id=self._config.imodel_id, change_reference=change_reference,
        )
