"""Bentley Access Recovery Build: service-client permission verification,
Test-iTwin retry, and non-Test iTwin fallback decision logic.

GOVERNANCE: this module owns ONLY the offline-computable parts of the
access-recovery workflow -- expected-permission comparison, the
Test-iTwin/non-Test-iTwin fallback DECISION (given check results, never
performing the checks itself beyond delegating to the existing
`bentley_itwin_client.BentleyItwinClient`), and idempotent find-or-create
composition. It contains NO OAuth, NO canonical spatial/engineering
identity rules, and NO new HTTP transport -- it reuses
`bentley_itwin_client.BentleyItwinClient` exclusively (never a second
Bentley client, section 2).

TEST-ITWIN ROLE LIMITATION (section 7): this module NEVER attempts to
create or change a Test-iTwin role. `TEST_ITWIN_ROLE_CREATION_ATTEMPTED`
below is a fixed constant, not a runtime check -- there is no code path in
this repository that calls a role-creation endpoint.
"""

from __future__ import annotations

import urllib.error
from dataclasses import dataclass
from typing import Literal

from bentley_itwin_client import BentleyIModelMetadata, BentleyITwinMetadata, BentleyItwinClient

EXPECTED_SERVICE_CLIENT_PERMISSIONS: frozenset[str] = frozenset({
    "imodels_delete", "imodels_read", "imodels_write", "realitydata_assign", "realitydata_manage",
    "realitydata_use", "storage_read", "storage_write", "imodels_webview", "imodels_manage",
    "insights_view", "insights_modify", "SCENES_READ", "SCENES_WRITE",
})
"""Section 6: the exact permission set Bentley support (Johannes Renner,
CS0761877) stated the service client should have -- reused verbatim as the
comparison baseline, never silently altered."""

TEST_ITWIN_ROLE_CREATION_ATTEMPTED = False
TEST_ITWIN_ROLE_LIMITATION_ACCEPTED = True
BENTLEY_COMMUNITY_TIER_SUPPORTED = True
JOHANNES_DEMO_USED_AS_REFERENCE_ONLY = True

DEVELOPMENT_ITWIN_NAME = "MRT Pharma Development"
DEVELOPMENT_IMODEL_NAME = "MRT Pharma Development Model"
"""Section 6/10: the ONE deterministic development resource names --
reused on every provisioning attempt, never varied to avoid a duplicate
match (section 6: never "... 2"/"... Final"/"... Test")."""

LiveCheckOutcome = Literal["SUCCESS", "FAILED", "NOT_ATTEMPTED", "NOT_APPLICABLE"]
CreateAuthorizationStatus = Literal["AUTHORIZED", "NOT_AUTHORIZED", "NOT_VERIFIABLE"]
HttpFailureCategory = Literal[
    "AUTHENTICATION_FAILURE", "CREATE_NOT_AUTHORIZED", "ACCESS_DENIED",
    "RESOURCE_NOT_FOUND_OR_NOT_VISIBLE", "RESOURCE_ALREADY_EXISTS_CONFLICT", "OTHER_API_FAILURE",
]


class AmbiguousDevelopmentResourceError(RuntimeError):
    """Section 7-8/11: raised when more than one candidate matches the
    deterministic development display name -- creation/reuse is refused
    rather than choosing arbitrarily."""


def classify_http_error(status_code: int, *, context: Literal["CREATE", "READ"] = "READ") -> HttpFailureCategory:
    """Section 25: the exact HTTP-status -> failure-category mapping this
    build's reports use -- never a fabricated success category."""
    if status_code == 401:
        return "AUTHENTICATION_FAILURE"
    if status_code == 403:
        return "CREATE_NOT_AUTHORIZED" if context == "CREATE" else "ACCESS_DENIED"
    if status_code == 404:
        return "RESOURCE_NOT_FOUND_OR_NOT_VISIBLE"
    if status_code == 409:
        return "RESOURCE_ALREADY_EXISTS_CONFLICT"
    return "OTHER_API_FAILURE"


@dataclass(frozen=True)
class PermissionComparisonResult:
    expected_count: int
    actual_count: int
    missing_expected_permissions: tuple[str, ...]
    unexpected_extra_permissions: tuple[str, ...]

    @property
    def all_expected_present(self) -> bool:
        return len(self.missing_expected_permissions) == 0


def compare_permission_sets(*, expected: frozenset[str], actual: tuple[str, ...]) -> PermissionComparisonResult:
    """Section 6: missing permissions fail the comparison; EXTRA permissions
    never do (a superset is still compliant)."""
    actual_set = frozenset(actual)
    missing = tuple(sorted(expected - actual_set))
    extra = tuple(sorted(actual_set - expected))
    return PermissionComparisonResult(
        expected_count=len(expected), actual_count=len(actual_set),
        missing_expected_permissions=missing, unexpected_extra_permissions=extra,
    )


@dataclass(frozen=True)
class AccessRecoveryCheckResults:
    """Section 11: the INPUT to the fallback decision gate -- each field is
    a caller-supplied outcome of an already-executed check; this dataclass
    never runs the checks itself."""

    service_authentication: LiveCheckOutcome
    permission_check: LiveCheckOutcome
    test_itwin_metadata: LiveCheckOutcome
    test_imodel_access: LiveCheckOutcome
    existing_live_proof: LiveCheckOutcome


def determine_non_test_itwin_required(results: AccessRecoveryCheckResults) -> bool:
    """Section 11: a non-Test iTwin is required ONLY when the Test-iTwin
    path was actually attempted and did NOT fully succeed -- never
    triggered merely because Bentley support mentioned the option, and
    never triggered when any check was `NOT_ATTEMPTED` (an untested path is
    not evidence of a blocker)."""
    all_results = (results.service_authentication, results.permission_check, results.test_itwin_metadata, results.test_imodel_access, results.existing_live_proof)
    if any(r == "NOT_ATTEMPTED" for r in all_results):
        return False
    return not all(r == "SUCCESS" for r in all_results)


def find_or_create_development_itwin(client: BentleyItwinClient, *, display_name: str) -> tuple[BentleyITwinMetadata, bool]:
    """Section 14: idempotent -- searches for an existing iTwin with the
    exact `display_name` before creating a new one. Returns
    `(metadata, created_this_call)`. Refuses to choose among ambiguous
    matches (section 7-8)."""
    existing = client.list_itwins(display_name=display_name)
    if len(existing) > 1:
        raise AmbiguousDevelopmentResourceError(f"{len(existing)} iTwins match display_name={display_name!r} -- refusing to choose arbitrarily")
    if existing:
        return existing[0], False
    return client.create_itwin(display_name=display_name), True


def find_or_create_development_imodel(client: BentleyItwinClient, *, itwin_id: str, display_name: str) -> tuple[BentleyIModelMetadata, bool]:
    """Section 14: idempotent -- searches for an existing iModel with the
    exact `display_name` under `itwin_id` before creating a new one.
    Refuses to choose among ambiguous matches (section 11)."""
    existing = client.list_imodels(itwin_id=itwin_id, display_name=display_name)
    if len(existing) > 1:
        raise AmbiguousDevelopmentResourceError(f"{len(existing)} iModels match display_name={display_name!r} under iTwin {itwin_id} -- refusing to choose arbitrarily")
    if existing:
        return existing[0], False
    return client.create_imodel(itwin_id=itwin_id, display_name=display_name), True


@dataclass(frozen=True)
class DevelopmentItwinProvisioningResult:
    """Section 4/25/32: the authorization-aware outcome of ONE provisioning
    attempt -- never inferred from the Test-iTwin's own 14-permission list
    (section 4), only from an actual search/create attempt."""

    itwin: BentleyITwinMetadata | None
    created_this_call: bool
    create_authorization: CreateAuthorizationStatus
    failure_category: HttpFailureCategory | None
    detail: str


@dataclass(frozen=True)
class DevelopmentImodelProvisioningResult:
    imodel: BentleyIModelMetadata | None
    created_this_call: bool
    create_authorization: CreateAuthorizationStatus
    failure_category: HttpFailureCategory | None
    detail: str


def provision_development_itwin(client: BentleyItwinClient, *, display_name: str = DEVELOPMENT_ITWIN_NAME) -> DevelopmentItwinProvisioningResult:
    """Section 4/8/33-34: search-before-create (section 7), never retries a
    failed POST (section 25), and reports the ACTUAL create-authorization
    outcome only when a create was genuinely attempted -- reusing an
    existing resource never exercises (and therefore never reports on)
    create authorization."""
    existing = client.list_itwins(display_name=display_name)
    if len(existing) > 1:
        raise AmbiguousDevelopmentResourceError(f"{len(existing)} iTwins match display_name={display_name!r} -- refusing to choose arbitrarily")
    if existing:
        return DevelopmentItwinProvisioningResult(
            itwin=existing[0], created_this_call=False, create_authorization="NOT_VERIFIABLE", failure_category=None,
            detail="Reused existing development iTwin; create authorization was not exercised.",
        )
    try:
        metadata = client.create_itwin(display_name=display_name)
    except urllib.error.HTTPError as exc:
        category = classify_http_error(exc.code, context="CREATE")
        auth_status: CreateAuthorizationStatus = "NOT_AUTHORIZED" if category == "CREATE_NOT_AUTHORIZED" else "NOT_VERIFIABLE"
        return DevelopmentItwinProvisioningResult(itwin=None, created_this_call=False, create_authorization=auth_status, failure_category=category, detail=str(exc))
    return DevelopmentItwinProvisioningResult(itwin=metadata, created_this_call=True, create_authorization="AUTHORIZED", failure_category=None, detail="Created successfully.")


def provision_development_imodel(client: BentleyItwinClient, *, itwin_id: str, display_name: str = DEVELOPMENT_IMODEL_NAME) -> DevelopmentImodelProvisioningResult:
    """Section 11-13: the iModel equivalent of `provision_development_itwin`."""
    existing = client.list_imodels(itwin_id=itwin_id, display_name=display_name)
    if len(existing) > 1:
        raise AmbiguousDevelopmentResourceError(f"{len(existing)} iModels match display_name={display_name!r} under iTwin {itwin_id} -- refusing to choose arbitrarily")
    if existing:
        return DevelopmentImodelProvisioningResult(
            imodel=existing[0], created_this_call=False, create_authorization="NOT_VERIFIABLE", failure_category=None,
            detail="Reused existing development iModel; create authorization was not exercised.",
        )
    try:
        metadata = client.create_imodel(itwin_id=itwin_id, display_name=display_name)
    except urllib.error.HTTPError as exc:
        category = classify_http_error(exc.code, context="CREATE")
        auth_status: CreateAuthorizationStatus = "NOT_AUTHORIZED" if category == "CREATE_NOT_AUTHORIZED" else "NOT_VERIFIABLE"
        return DevelopmentImodelProvisioningResult(imodel=None, created_this_call=False, create_authorization=auth_status, failure_category=category, detail=str(exc))
    return DevelopmentImodelProvisioningResult(imodel=metadata, created_this_call=True, create_authorization="AUTHORIZED", failure_category=None, detail="Created successfully.")


# ===========================================================================
# Membership Diagnostic build: Test-iTwin service-account membership check.
# ===========================================================================

MembershipStatus = Literal["CONFIRMED", "NOT_FOUND", "NOT_DETERMINABLE_FROM_USER_MEMBERS_ENDPOINT"]
Itwin404RootCause = Literal[
    "UNRESOLVED_PLATFORM_OR_API_VISIBILITY_CONDITION",
    "SERVICE_ACCOUNT_NOT_PRESENT_IN_TEST_ITWIN_MEMBERSHIP",
    "NOT_DETERMINABLE_FROM_USER_MEMBERS_ENDPOINT",
]

GET_ITWIN_USER_MEMBERS_REPRESENTS_SERVICE_APPLICATIONS = False
"""Section 1/4: confirmed against https://developer.bentley.com/apis/
access-control-v2/operations/get-itwin-user-members/ -- this operation is
documented as USER members only (`/members/users`), and its member schema
(`id`/`email`/`givenName`/`surname`/`organization`/`roles`) has NO
client-ID/service-application field. A structural, documentation-derived
fact, never a runtime guess."""


def determine_service_account_membership(*, member_count: int) -> MembershipStatus:
    """Section 6: never forces a false client-ID comparison (section 4) --
    since Get iTwin User Members cannot represent service applications at
    all (per the documented contract above), the honest answer is always
    NOT_DETERMINABLE_FROM_USER_MEMBERS_ENDPOINT, regardless of how many
    human members are returned."""
    if not GET_ITWIN_USER_MEMBERS_REPRESENTS_SERVICE_APPLICATIONS:
        return "NOT_DETERMINABLE_FROM_USER_MEMBERS_ENDPOINT"
    return "CONFIRMED" if member_count > 0 else "NOT_FOUND"


def determine_service_account_role(service_account_membership: MembershipStatus) -> str:
    """Section 7: a role can only be attributed to a membership that was
    actually identified -- never fabricated from an unrelated member row."""
    if service_account_membership != "CONFIRMED":
        return "NOT_DETERMINABLE_FROM_USER_MEMBERS_ENDPOINT"
    return "NOT_DETERMINABLE_FROM_USER_MEMBERS_ENDPOINT"  # no documented service-account row to read a role from, even when CONFIRMED


def determine_itwin_404_root_cause(
    *, service_account_membership: MembershipStatus, permission_check_success: bool,
    itwin_id_matches_imodel: bool, get_itwin_404: bool,
) -> Itwin404RootCause:
    """Section 9: the exact CASE A/B/C interpretation -- conservative,
    evidence-only, never changes client code merely to make a test pass."""
    if service_account_membership == "NOT_FOUND":
        return "SERVICE_ACCOUNT_NOT_PRESENT_IN_TEST_ITWIN_MEMBERSHIP"
    if service_account_membership == "NOT_DETERMINABLE_FROM_USER_MEMBERS_ENDPOINT":
        return "NOT_DETERMINABLE_FROM_USER_MEMBERS_ENDPOINT"
    if service_account_membership == "CONFIRMED" and permission_check_success and itwin_id_matches_imodel and get_itwin_404:
        return "UNRESOLVED_PLATFORM_OR_API_VISIBILITY_CONDITION"
    return "NOT_DETERMINABLE_FROM_USER_MEMBERS_ENDPOINT"


# ===========================================================================
# Development Resource Adoption build: discover existing iTwins/iModels
# FIRST (broad, never name-filtered), classify each candidate by
# ID/class/status (NEVER by display name alone, section 6), and decide
# reuse-vs-create-vs-stop -- pure, offline-testable logic. Reuses
# `BentleyItwinClient.list_itwins()`/`list_imodels()` exclusively (never a
# second discovery path).
# ===========================================================================

DevelopmentItwinRelationship = Literal[
    "TEST_ITWIN", "SEPARATE_DEVELOPMENT_ITWIN", "ACCOUNT_OR_CONTAINER", "INACTIVE_OR_UNSUITABLE", "AMBIGUOUS_FROM_METADATA",
]

RESOURCE_ADOPTION_BASED_ON_IDENTITY_AND_TYPE_NOT_NAME_ONLY = True
"""Section 6: `classify_development_itwin_candidates` below never inspects
`display_name` for its relationship/adoptability decision -- only
`itwin_id` (vs. the configured Test-iTwin), `class_name`, and `status`."""


@dataclass(frozen=True)
class DevelopmentItwinCandidateClassification:
    itwin: BentleyITwinMetadata
    relationship: DevelopmentItwinRelationship
    adoptable: bool
    reason: str


def classify_development_itwin_candidates(
    candidates: tuple[BentleyITwinMetadata, ...], *, configured_test_itwin_id: str,
) -> tuple[DevelopmentItwinCandidateClassification, ...]:
    """Sections 4-6: classification uses ONLY `itwin_id`/`class_name`/
    `status` -- `display_name` is never consulted here (an existing iTwin
    named nothing like "MRT Pharma Development" is still adoptable if it is
    a distinct, active, non-account-class iTwin)."""
    results = []
    for candidate in candidates:
        if candidate.itwin_id == configured_test_itwin_id:
            results.append(DevelopmentItwinCandidateClassification(
                itwin=candidate, relationship="TEST_ITWIN", adoptable=False,
                reason="itwin_id equals the configured BENTLEY_ITWIN_ID (Test-iTwin) -- never adopted as the persistent development resource",
            ))
            continue
        if candidate.class_name.strip().lower() == "account":
            results.append(DevelopmentItwinCandidateClassification(
                itwin=candidate, relationship="ACCOUNT_OR_CONTAINER", adoptable=False,
                reason="class=Account -- a container/root object, never a development iTwin itself",
            ))
            continue
        if candidate.status.strip().lower() not in ("active", "unknown"):
            results.append(DevelopmentItwinCandidateClassification(
                itwin=candidate, relationship="INACTIVE_OR_UNSUITABLE", adoptable=False, reason=f"status={candidate.status!r} (not Active)",
            ))
            continue
        if candidate.class_name == "Unknown" or not candidate.display_name:
            results.append(DevelopmentItwinCandidateClassification(
                itwin=candidate, relationship="AMBIGUOUS_FROM_METADATA", adoptable=False,
                reason="insufficient metadata (missing class/displayName) to classify safely",
            ))
            continue
        results.append(DevelopmentItwinCandidateClassification(
            itwin=candidate, relationship="SEPARATE_DEVELOPMENT_ITWIN", adoptable=True,
            reason="distinct from the Test-iTwin, Active status, non-Account class -- suitable for adoption",
        ))
    return tuple(results)


DevelopmentItwinAction = Literal["REUSE_EXISTING", "CREATE_NEW", "STOP_AMBIGUOUS", "STOP_CLASSIFICATION_REQUIRED"]


@dataclass(frozen=True)
class DevelopmentItwinDecision:
    action: DevelopmentItwinAction
    candidates: tuple[DevelopmentItwinCandidateClassification, ...]
    adopted_itwin: BentleyITwinMetadata | None


def decide_development_itwin_action(candidates: tuple[DevelopmentItwinCandidateClassification, ...]) -> DevelopmentItwinDecision:
    """Section 7: exactly one adoptable candidate -> reuse; more than one
    -> stop ambiguous (never chosen arbitrarily); an unclassifiable
    candidate (and no adoptable one) -> stop for manual classification;
    otherwise (nothing adoptable, nothing ambiguous) -> create new."""
    adoptable = [c for c in candidates if c.adoptable]
    if len(adoptable) == 1:
        return DevelopmentItwinDecision(action="REUSE_EXISTING", candidates=candidates, adopted_itwin=adoptable[0].itwin)
    if len(adoptable) > 1:
        return DevelopmentItwinDecision(action="STOP_AMBIGUOUS", candidates=candidates, adopted_itwin=None)
    if any(c.relationship == "AMBIGUOUS_FROM_METADATA" for c in candidates):
        return DevelopmentItwinDecision(action="STOP_CLASSIFICATION_REQUIRED", candidates=candidates, adopted_itwin=None)
    return DevelopmentItwinDecision(action="CREATE_NEW", candidates=candidates, adopted_itwin=None)


def discover_and_decide_development_itwin(client: BentleyItwinClient, *, configured_test_itwin_id: str) -> DevelopmentItwinDecision:
    """Section 3/7: broad discovery (NO display-name filter) via the
    EXISTING `list_itwins(include_inactive=True)` -- never a second
    discovery path -- followed by classification and decision."""
    candidates = client.list_itwins(include_inactive=True)
    classified = classify_development_itwin_candidates(candidates, configured_test_itwin_id=configured_test_itwin_id)
    return decide_development_itwin_action(classified)


DevelopmentImodelAction = Literal["REUSE_EXISTING", "CREATE_NEW", "STOP_AMBIGUOUS"]


@dataclass(frozen=True)
class DevelopmentImodelDecision:
    action: DevelopmentImodelAction
    candidates: tuple[BentleyIModelMetadata, ...]
    adopted_imodel: BentleyIModelMetadata | None


def decide_development_imodel_action(candidates: tuple[BentleyIModelMetadata, ...]) -> DevelopmentImodelDecision:
    """Section 12: iModel candidates are already scoped to ONE iTwin (via
    `list_imodels(itwin_id=...)`), so no further classification is needed
    beyond count: exactly one -> reuse, more than one -> stop ambiguous,
    zero -> create new."""
    if len(candidates) == 1:
        return DevelopmentImodelDecision(action="REUSE_EXISTING", candidates=candidates, adopted_imodel=candidates[0])
    if len(candidates) > 1:
        return DevelopmentImodelDecision(action="STOP_AMBIGUOUS", candidates=candidates, adopted_imodel=None)
    return DevelopmentImodelDecision(action="CREATE_NEW", candidates=candidates, adopted_imodel=None)


def discover_and_decide_development_imodel(client: BentleyItwinClient, *, itwin_id: str) -> DevelopmentImodelDecision:
    """Section 11: broad discovery (NO display-name filter) via the
    EXISTING `list_imodels(itwin_id=...)` -- never a second discovery path."""
    candidates = client.list_imodels(itwin_id=itwin_id)
    return decide_development_imodel_action(candidates)
