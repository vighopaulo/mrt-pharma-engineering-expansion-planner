from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import traceback
import uuid
from typing import Any, Callable, Literal, Mapping, TypeVar


RouteId = Literal[
    "home",
    "projects",
    "project_overview",
    "project_definition",
    "facility_resources",
    "demand_workflow_radionuclides",
    "production_cyclotron_external_supply",
    "geometry_floor_transport",
    "mrt_infrastructure",
    "economics_assumptions",
    "review_run",
    "results_executive",
    "master_engineering_data",
]

Severity = Literal["ERROR", "WARNING", "UNKNOWN_OR_NOT_CALIBRATED", "INFORMATION", "READY_VALID"]
FieldState = Literal[
    "REQUIRED",
    "OPTIONAL",
    "DEFAULT_MODEL_VALUE",
    "USER_OVERRIDE",
    "DERIVED",
    "UNKNOWN",
    "NOT_CALIBRATED",
    "NOT_APPLICABLE",
    "CONFLICTED",
    "INVALID",
]
DraftStatus = Literal["SAVED", "DRAFT", "DIRTY_UNSAVED"]
RunStatus = Literal["NO_RUN_YET", "SUCCESS", "FAILED_WITH_PREVIOUS_SUCCESS", "FAILED_NO_SUCCESS"]
ProjectMode = Literal["UNSPECIFIED", "GREENFIELD", "EXISTING_FACILITY_RETROFIT"]
ProjectSupplyArchitecture = Literal["UNSPECIFIED", "ON_SITE_PRODUCTION", "EXTERNAL_SUPPLY_HUB_SPOKE"]
InventoryStatus = Literal["NONE", "KNOWN", "UNKNOWN"]


PAGE_LABELS: dict[RouteId, str] = {
    "home": "Home / Landing",
    "projects": "Projects",
    "project_overview": "Project Overview",
    "project_definition": "Project Definition / Project Mode",
    "facility_resources": "Facility & Existing Resources",
    "demand_workflow_radionuclides": "Demand & Clinical Workflow",
    "production_cyclotron_external_supply": "Production / Cyclotron / External Supply",
    "geometry_floor_transport": "Spatial / Facility Engineering / Transport",
    "mrt_infrastructure": "MRT Infrastructure",
    "economics_assumptions": "Economics & Assumptions",
    "review_run": "Review & Run",
    "results_executive": "Results / Executive Comparison",
    "master_engineering_data": "Master Engineering Data / Reports / Evidence / Exports",
}

FUTURE_PAGE_ROUTES: tuple[RouteId, ...] = (
    "project_definition",
    "facility_resources",
    "economics_assumptions",
    "review_run",
    "results_executive",
    "master_engineering_data",
)

FIELD_STATE_NON_EQUIVALENCE_RULES: tuple[str, ...] = (
    "UNKNOWN != ZERO",
    "NOT_CALIBRATED != ZERO",
    "NOT_APPLICABLE != MISSING",
    "DEFAULT_MODEL_VALUE != USER_OVERRIDE",
    "CONFLICTED != ACCEPTED",
)

RESOURCE_FIELD_LABELS: tuple[tuple[str, str], ...] = (
    ("cyclotron_units", "Cyclotron units"),
    ("radiopharmacy_units", "Radiopharmacy units"),
    ("scanner_resources", "PET/SPECT scanner resources"),
    ("injection_resources", "Injection resources"),
    ("uptake_resources", "Uptake resources"),
    ("distribution_concurrency", "Distribution concurrency/resources"),
    ("mrt_endpoints", "MRT endpoints already installed"),
    ("mrt_carriers", "MRT carriers already installed"),
)

PROJECT_MODE_LABELS: Mapping[ProjectMode, str] = {
    "UNSPECIFIED": "Unspecified",
    "GREENFIELD": "Greenfield",
    "EXISTING_FACILITY_RETROFIT": "Retrofit / Existing Facility Expansion",
}

SUPPLY_ARCHITECTURE_LABELS: Mapping[ProjectSupplyArchitecture, str] = {
    "UNSPECIFIED": "Unspecified",
    "ON_SITE_PRODUCTION": "On-site Production",
    "EXTERNAL_SUPPLY_HUB_SPOKE": "External Supply / Hub-and-Spoke",
}

INVENTORY_STATUS_LABELS: Mapping[InventoryStatus, str] = {
    "NONE": "None",
    "KNOWN": "Known",
    "UNKNOWN": "Unknown",
}


@dataclass(frozen=True)
class ValidationMessage:
    code: str
    severity: Severity
    message: str
    field_key: str | None = None
    route: RouteId | None = None
    fix_route: RouteId | None = None


@dataclass(frozen=True)
class ReadinessSnapshot:
    blockers: tuple[ValidationMessage, ...]
    warnings: tuple[ValidationMessage, ...]
    unknown_or_not_calibrated: tuple[ValidationMessage, ...]
    information: tuple[ValidationMessage, ...]
    ready: tuple[ValidationMessage, ...]
    assumptions: tuple[str, ...]
    defaults_in_use: tuple[str, ...]
    overrides: tuple[str, ...]


@dataclass(frozen=True)
class NavEntry:
    route: RouteId
    project_id: str | None
    context: Mapping[str, str] = field(default_factory=dict)


@dataclass
class NavigationHistory:
    entries: list[NavEntry] = field(default_factory=list)
    cursor: int = -1

    def _same_entry(self, left: NavEntry, right: NavEntry) -> bool:
        return left.route == right.route and left.project_id == right.project_id and dict(left.context) == dict(right.context)

    def push(self, entry: NavEntry) -> None:
        if self.cursor >= 0 and self._same_entry(self.entries[self.cursor], entry):
            return
        if self.cursor < len(self.entries) - 1:
            self.entries = self.entries[: self.cursor + 1]
        self.entries.append(entry)
        self.cursor = len(self.entries) - 1

    def can_back(self) -> bool:
        return self.cursor > 0

    def can_forward(self) -> bool:
        return 0 <= self.cursor < len(self.entries) - 1

    def back(self) -> NavEntry | None:
        if not self.can_back():
            return None
        self.cursor -= 1
        return self.entries[self.cursor]

    def forward(self) -> NavEntry | None:
        if not self.can_forward():
            return None
        self.cursor += 1
        return self.entries[self.cursor]

    def current(self) -> NavEntry | None:
        if self.cursor < 0 or self.cursor >= len(self.entries):
            return None
        return self.entries[self.cursor]


@dataclass
class ProjectRecord:
    project_id: str
    name: str
    created_at_iso: str
    updated_at_iso: str
    archived: bool = False
    project_mode: ProjectMode = "UNSPECIFIED"
    supply_architecture: ProjectSupplyArchitecture = "UNSPECIFIED"
    status: str = "NEW"
    saved_state: dict[str, Any] = field(default_factory=dict)
    draft_state: dict[str, Any] = field(default_factory=dict)
    draft_status: DraftStatus = "SAVED"
    last_successful_result_ref: str | None = None
    run_status: RunStatus = "NO_RUN_YET"

    def touch(self) -> None:
        self.updated_at_iso = _timestamp_iso()

    def update_name(self, new_name: str) -> None:
        normalized = _normalize_project_name(new_name)
        self.name = normalized
        self.touch()

    def set_draft_value(self, key: str, value: Any) -> None:
        self.draft_state[key] = value
        self.draft_status = "DIRTY_UNSAVED" if self.saved_state.get(key) != value else "SAVED"
        self.touch()

    def commit_draft_key(self, key: str) -> None:
        if key in self.draft_state:
            self.saved_state[key] = self.draft_state[key]
            if self.saved_state == self.draft_state:
                self.draft_status = "SAVED"
            else:
                self.draft_status = "DRAFT"
            self.touch()

    def set_run_success(self, result_ref: str) -> None:
        self.last_successful_result_ref = result_ref
        self.run_status = "SUCCESS"
        self.touch()

    def set_run_failed(self) -> None:
        if self.last_successful_result_ref:
            self.run_status = "FAILED_WITH_PREVIOUS_SUCCESS"
        else:
            self.run_status = "FAILED_NO_SUCCESS"
        self.touch()


@dataclass
class ProjectLibrary:
    projects: dict[str, ProjectRecord] = field(default_factory=dict)

    def create_project(self, name: str) -> ProjectRecord:
        normalized = _normalize_project_name(name)
        project = ProjectRecord(
            project_id=_new_project_id(),
            name=normalized,
            created_at_iso=_timestamp_iso(),
            updated_at_iso=_timestamp_iso(),
        )
        self.projects[project.project_id] = project
        return project

    def list_projects(self, *, include_archived: bool = True) -> list[ProjectRecord]:
        items = list(self.projects.values())
        if not include_archived:
            items = [item for item in items if not item.archived]
        return sorted(items, key=lambda item: item.updated_at_iso, reverse=True)

    def get_project(self, project_id: str) -> ProjectRecord:
        if project_id not in self.projects:
            raise KeyError(f"Unknown project: {project_id}")
        return self.projects[project_id]

    def rename_project(self, project_id: str, new_name: str) -> ProjectRecord:
        project = self.get_project(project_id)
        project.update_name(new_name)
        return project

    def duplicate_project(self, project_id: str, new_name: str | None = None) -> ProjectRecord:
        source = self.get_project(project_id)
        duplicate = ProjectRecord(
            project_id=_new_project_id(),
            name=_normalize_project_name(new_name or f"{source.name} Copy"),
            created_at_iso=_timestamp_iso(),
            updated_at_iso=_timestamp_iso(),
            archived=False,
            project_mode=source.project_mode,
            supply_architecture=source.supply_architecture,
            status=source.status,
            saved_state=dict(source.saved_state),
            draft_state=dict(source.draft_state),
            draft_status=source.draft_status,
            last_successful_result_ref=source.last_successful_result_ref,
            run_status=source.run_status,
        )
        self.projects[duplicate.project_id] = duplicate
        return duplicate

    def archive_project(self, project_id: str, archived: bool = True) -> ProjectRecord:
        project = self.get_project(project_id)
        project.archived = bool(archived)
        project.touch()
        return project

    def delete_project(self, project_id: str, *, confirmed: bool) -> None:
        if not confirmed:
            raise ValueError("Deleting a project requires explicit confirmation")
        if project_id not in self.projects:
            raise KeyError(f"Unknown project: {project_id}")
        del self.projects[project_id]


@dataclass(frozen=True)
class AppActionResult:
    ok: bool
    user_message: str
    technical_details: str | None = None


T = TypeVar("T")


def _is_streamlit_control_flow_exception(exc: Exception) -> bool:
    """Identify Streamlit rerun/stop exceptions across Streamlit versions."""
    class_name = type(exc).__name__
    module_name = type(exc).__module__
    return class_name in {"RerunException", "StopException", "ScriptControlException"} and (
        "streamlit.runtime.scriptrunner" in module_name
    )


def run_safe_action(
    action: Callable[[], T],
    *,
    user_message_on_error: str = "The requested action could not be completed. Your project has been preserved.",
) -> tuple[AppActionResult, T | None]:
    try:
        value = action()
        return AppActionResult(ok=True, user_message="OK"), value
    except Exception as exc:  # noqa: BLE001
        if _is_streamlit_control_flow_exception(exc):
            raise
        details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        return AppActionResult(ok=False, user_message=user_message_on_error, technical_details=details), None


def validate_mode_supply_selection(
    mode: ProjectMode,
    supply_architecture: ProjectSupplyArchitecture,
) -> tuple[str, ...]:
    issues: list[str] = []
    if mode == "UNSPECIFIED":
        issues.append("Project mode is required.")
    if supply_architecture == "UNSPECIFIED":
        issues.append("Supply architecture is required.")
    return tuple(issues)


def is_mode_supply_selection_complete(
    mode: ProjectMode,
    supply_architecture: ProjectSupplyArchitecture,
) -> bool:
    return mode != "UNSPECIFIED" and supply_architecture != "UNSPECIFIED"


def parse_non_negative_integer(value: str) -> tuple[int | None, str | None]:
    text = value.strip()
    if text == "":
        return None, "Quantity is required when status is KNOWN."
    try:
        parsed = int(text)
    except ValueError:
        return None, "Quantity must be a whole number."
    if parsed < 0:
        return None, "Quantity cannot be negative."
    return parsed, None


def validate_resource_inventory(
    *,
    status: InventoryStatus,
    quantity_text: str,
) -> tuple[int | None, str | None]:
    if status == "UNKNOWN":
        return None, None
    if status == "NONE":
        return 0, None
    return parse_non_negative_integer(quantity_text)


def cyclotron_inventory_semantics(
    *,
    status: InventoryStatus,
    quantity_text: str,
) -> str:
    if status == "UNKNOWN":
        return "Current on-site cyclotron inventory has not been established."
    if status == "NONE":
        return "There are confirmed to be no on-site cyclotrons."
    quantity, issue = parse_non_negative_integer(quantity_text)
    if issue:
        return issue
    if quantity == 0:
        return "There are confirmed to be no on-site cyclotrons."
    if quantity == 1:
        return "One on-site cyclotron currently exists."
    return f"{quantity} on-site cyclotrons currently exist."


def default_readiness_snapshot() -> ReadinessSnapshot:
    return ReadinessSnapshot(
        blockers=(),
        warnings=(),
        unknown_or_not_calibrated=(
            ValidationMessage(
                code="RR-NC-001",
                severity="UNKNOWN_OR_NOT_CALIBRATED",
                message="Readiness infrastructure active: Not calibrated values will be routed here.",
                route="review_run",
            ),
        ),
        information=(
            ValidationMessage(
                code="RR-INFO-001",
                severity="INFORMATION",
                message="Build 1 provides readiness scaffolding; engineering-run wiring is delivered in later builds.",
                route="review_run",
            ),
        ),
        ready=(
            ValidationMessage(
                code="RR-READY-001",
                severity="READY_VALID",
                message="Validation framework initialized.",
                route="review_run",
            ),
        ),
        assumptions=(),
        defaults_in_use=("Revenue per scan uses default model value until overridden.",),
        overrides=(),
    )


def serialize_project_library(library: ProjectLibrary) -> dict[str, Any]:
    return {
        "projects": {
            project_id: asdict(project)
            for project_id, project in library.projects.items()
        }
    }


def deserialize_project_library(payload: Mapping[str, Any] | None) -> ProjectLibrary:
    if not payload or "projects" not in payload:
        return ProjectLibrary()
    projects: dict[str, ProjectRecord] = {}
    for project_id, project_payload in dict(payload["projects"]).items():
        projects[project_id] = ProjectRecord(**project_payload)
    return ProjectLibrary(projects=projects)


def serialize_navigation(history: NavigationHistory) -> dict[str, Any]:
    return {
        "cursor": history.cursor,
        "entries": [
            {
                "route": entry.route,
                "project_id": entry.project_id,
                "context": dict(entry.context),
            }
            for entry in history.entries
        ],
    }


def deserialize_navigation(payload: Mapping[str, Any] | None) -> NavigationHistory:
    if not payload:
        return NavigationHistory()
    entries = [
        NavEntry(
            route=entry["route"],
            project_id=entry.get("project_id"),
            context=entry.get("context") or {},
        )
        for entry in payload.get("entries", [])
    ]
    cursor = int(payload.get("cursor", len(entries) - 1))
    if entries and (cursor < 0 or cursor >= len(entries)):
        cursor = len(entries) - 1
    if not entries:
        cursor = -1
    return NavigationHistory(entries=entries, cursor=cursor)


def _normalize_project_name(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError("Project name must be text")
    normalized = name.strip()
    if not normalized:
        raise ValueError("Project name is required")
    return normalized


def _timestamp_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_project_id() -> str:
    return f"PRJ-{uuid.uuid4().hex[:10].upper()}"
