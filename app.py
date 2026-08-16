from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st

from ui_foundation import (
    FIELD_STATE_NON_EQUIVALENCE_RULES,
    FUTURE_PAGE_ROUTES,
    PAGE_LABELS,
    AppActionResult,
    InventoryStatus,
    NavEntry,
    NavigationHistory,
    PROJECT_MODE_LABELS,
    ProjectLibrary,
    ProjectMode,
    ProjectRecord,
    ProjectSupplyArchitecture,
    INVENTORY_STATUS_LABELS,
    RESOURCE_FIELD_LABELS,
    RouteId,
    SUPPLY_ARCHITECTURE_LABELS,
    ValidationMessage,
    cyclotron_inventory_semantics,
    default_readiness_snapshot,
    deserialize_navigation,
    deserialize_project_library,
    is_mode_supply_selection_complete,
    parse_non_negative_integer,
    run_safe_action,
    serialize_navigation,
    serialize_project_library,
    validate_mode_supply_selection,
    validate_resource_inventory,
)


st.set_page_config(page_title="MRT Pharma", page_icon="M", layout="wide")


def _inject_style() -> None:
    st.markdown(
        """
        <style>
        :root {
            --mrt-red: #b1141a;
            --mrt-red-soft: #fbe9ea;
            --mrt-black: #121212;
            --mrt-white: #ffffff;
            --mrt-gray-100: #f5f5f5;
            --mrt-gray-300: #d9d9d9;
            --mrt-gray-600: #5c5c5c;
        }
        .stApp {
            background: linear-gradient(145deg, #ffffff 0%, #f8f8f8 100%);
        }
        #MainMenu {
            visibility: hidden;
        }
        footer {
            visibility: hidden;
        }
        header {
            visibility: hidden;
        }
        [data-testid="stToolbar"] {
            display: none;
        }
        [data-testid="stDecoration"] {
            display: none;
        }
        [data-testid="stHeader"] {
            display: none;
        }
        [data-testid="collapsedControl"] {
            display: none;
        }
        .block-container {
            max-width: 1280px;
            padding-top: 1.0rem;
            padding-bottom: 2.0rem;
        }
        .shell {
            border: 1px solid var(--mrt-gray-300);
            border-radius: 14px;
            padding: 14px;
            margin-bottom: 14px;
            background: var(--mrt-white);
        }
        .shell-title {
            font-size: 1.8rem;
            font-weight: 800;
            color: var(--mrt-black);
            margin: 0;
            letter-spacing: -0.02em;
        }
        .shell-subtitle {
            color: var(--mrt-gray-600);
            margin-top: 2px;
            margin-bottom: 0;
        }
        .brand-word-mrt {
            color: var(--mrt-black);
        }
        .brand-word-pharma {
            color: var(--mrt-red);
            margin-left: 0.2rem;
        }
        .page-card {
            border: 1px solid var(--mrt-gray-300);
            border-radius: 12px;
            background: var(--mrt-white);
            padding: 14px;
            margin-bottom: 12px;
        }
        .page-card-title {
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--mrt-black);
            margin-bottom: 4px;
        }
        .status-pill {
            display: inline-block;
            border-radius: 999px;
            padding: 4px 10px;
            font-size: 0.8rem;
            font-weight: 700;
            color: #111;
            background: var(--mrt-red-soft);
            border: 1px solid #f0c2c5;
        }
        .stButton > button {
            min-height: 44px;
            border-radius: 10px;
            border: 1px solid #bdbdbd;
            font-weight: 700;
            font-size: 0.95rem;
        }
        .cta-large button {
            min-height: 54px !important;
            font-size: 1rem !important;
        }
        .mrt-primary button {
            background: var(--mrt-red) !important;
            color: var(--mrt-white) !important;
            border: 1px solid #7e0f13 !important;
        }
        .progress-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 10px;
        }
        .progress-box {
            border: 1px solid var(--mrt-gray-300);
            border-radius: 10px;
            padding: 10px;
            background: #fff;
        }
        .progress-label {
            color: var(--mrt-gray-600);
            font-size: 0.85rem;
            margin-bottom: 2px;
        }
        .progress-value {
            color: var(--mrt-black);
            font-size: 1.1rem;
            font-weight: 700;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _init_state() -> tuple[ProjectLibrary, NavigationHistory]:
    if "ui_project_library" not in st.session_state:
        st.session_state.ui_project_library = serialize_project_library(ProjectLibrary())
    if "ui_navigation" not in st.session_state:
        st.session_state.ui_navigation = serialize_navigation(NavigationHistory())
    if "ui_current_route" not in st.session_state:
        st.session_state.ui_current_route = "home"
    if "ui_current_project_id" not in st.session_state:
        st.session_state.ui_current_project_id = None
    if "ui_status_messages" not in st.session_state:
        st.session_state.ui_status_messages = []
    if "ui_last_error" not in st.session_state:
        st.session_state.ui_last_error = None
    if "ui_delete_confirm_project_id" not in st.session_state:
        st.session_state.ui_delete_confirm_project_id = None
    if "ui_rename_project_id" not in st.session_state:
        st.session_state.ui_rename_project_id = None
    st.session_state.setdefault("home_create_name", "")
    st.session_state.setdefault("projects_create_name", "")
    st.session_state.setdefault("home_create_name_input", st.session_state.home_create_name)
    st.session_state.setdefault("projects_create_name_input", st.session_state.projects_create_name)

    library = deserialize_project_library(st.session_state.ui_project_library)
    navigation = deserialize_navigation(st.session_state.ui_navigation)

    if navigation.current() is None:
        navigation.push(
            NavEntry(
                route=st.session_state.ui_current_route,
                project_id=st.session_state.ui_current_project_id,
            )
        )
        _persist_state(library, navigation)

    return library, navigation


def _persist_state(library: ProjectLibrary, navigation: NavigationHistory) -> None:
    st.session_state.ui_project_library = serialize_project_library(library)
    st.session_state.ui_navigation = serialize_navigation(navigation)


def _append_status(message: str, level: str = "info") -> None:
    messages = list(st.session_state.ui_status_messages)
    messages.append({"level": level, "message": message})
    st.session_state.ui_status_messages = messages[-6:]


def _clear_error_presentation_state() -> None:
    st.session_state.ui_last_error = None
    st.session_state.ui_status_messages = [
        message for message in st.session_state.ui_status_messages if message.get("level") != "error"
    ]


def _navigate_to(library: ProjectLibrary, navigation: NavigationHistory, route: RouteId, project_id: str | None = None) -> None:
    st.session_state.ui_current_route = route
    st.session_state.ui_current_project_id = project_id
    navigation.push(NavEntry(route=route, project_id=project_id))
    _persist_state(library, navigation)
    st.rerun()


def _apply_nav_entry(library: ProjectLibrary, navigation: NavigationHistory, entry: NavEntry) -> None:
    st.session_state.ui_current_route = entry.route
    st.session_state.ui_current_project_id = entry.project_id
    _persist_state(library, navigation)
    st.rerun()


def _resolve_open_project(library: ProjectLibrary) -> ProjectRecord | None:
    project_id = st.session_state.ui_current_project_id
    if not project_id:
        return None
    try:
        return library.get_project(project_id)
    except KeyError:
        st.session_state.ui_current_project_id = None
        return None


def _render_shell(library: ProjectLibrary, navigation: NavigationHistory, current_project: ProjectRecord | None) -> None:
    st.markdown(
        (
            "<div class='shell'>"
            "<p class='shell-title'><span class='brand-word-mrt'>MRT</span><span class='brand-word-pharma'>Pharma</span></p>"
            "<p class='shell-subtitle'>Digital Twin</p>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    n1, n2, n3, n4 = st.columns(4)
    back_disabled = not navigation.can_back()
    forward_disabled = not navigation.can_forward()

    if n1.button("Home", use_container_width=True):
        _navigate_to(library, navigation, "home", st.session_state.ui_current_project_id)

    if n2.button("Back", use_container_width=True, disabled=back_disabled):
        entry = navigation.back()
        if entry:
            _apply_nav_entry(library, navigation, entry)

    if n3.button("Forward", use_container_width=True, disabled=forward_disabled):
        entry = navigation.forward()
        if entry:
            _apply_nav_entry(library, navigation, entry)

    if n4.button("Projects", use_container_width=True):
        _navigate_to(library, navigation, "projects", st.session_state.ui_current_project_id)

    for item in st.session_state.ui_status_messages[-3:]:
        level = item.get("level", "info")
        message = item.get("message", "")
        if level == "error":
            st.error(message)
        elif level == "warning":
            st.warning(message)
        elif level == "success":
            st.success(message)
        else:
            st.info(message)


def _create_project_control(library: ProjectLibrary, navigation: NavigationHistory, key_prefix: str) -> None:
    input_key = f"{key_prefix}_create_name_input"
    if input_key not in st.session_state:
        st.session_state[input_key] = st.session_state.get(f"{key_prefix}_create_name", "")
    name = st.text_input("Project name", key=input_key)
    st.session_state[f"{key_prefix}_create_name"] = name
    st.markdown("<div class='cta-large mrt-primary'>", unsafe_allow_html=True)
    if st.button("Create Project", key=f"{key_prefix}_create_project", use_container_width=True):
        result, project = run_safe_action(lambda: library.create_project(name))
        if result.ok and project is not None:
            _append_status(f"Created project '{project.name}'.", "success")
            _navigate_to(library, navigation, "project_overview", project.project_id)
        else:
            _append_status(result.user_message, "error")
    st.markdown("</div>", unsafe_allow_html=True)


def _render_home(library: ProjectLibrary, navigation: NavigationHistory) -> None:
    st.title("Home")
    st.caption("Start work quickly: create a project with a name, or open an existing project.")

    left, right = st.columns([1.2, 1.0])
    with left:
        st.markdown("<div class='page-card'><div class='page-card-title'>Create Project</div>", unsafe_allow_html=True)
        _create_project_control(library, navigation, "home")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown("<div class='page-card'><div class='page-card-title'>Open Project</div>", unsafe_allow_html=True)
        active = [project for project in library.list_projects(include_archived=False)]
        if active:
            project_by_name = {f"{project.name} ({project.project_id})": project for project in active}
            selected_name = st.selectbox("Available projects", options=list(project_by_name.keys()))
            selected = project_by_name[selected_name]
            st.markdown("<div class='cta-large'>", unsafe_allow_html=True)
            if st.button("Open Project", use_container_width=True):
                _append_status(f"Opened project '{selected.name}'.", "success")
                _navigate_to(library, navigation, "project_overview", selected.project_id)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("No active projects yet.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.subheader("Recent Projects")
    recent = library.list_projects(include_archived=False)[:6]
    if not recent:
        st.info("No recent projects to display.")
        return

    for project in recent:
        c1, c2, c3, c4 = st.columns([2.0, 1.2, 1.0, 0.9])
        c1.write(project.name)
        c2.write(project.updated_at_iso)
        c3.write(project.status)
        if c4.button("Quick Open", key=f"home_open_{project.project_id}", use_container_width=True):
            _append_status(f"Opened project '{project.name}'.", "success")
            _navigate_to(library, navigation, "project_overview", project.project_id)


def _render_project_row(library: ProjectLibrary, navigation: NavigationHistory, project: ProjectRecord) -> None:
    row = st.columns([2.0, 1.2, 1.2, 0.9, 0.9, 0.9, 0.9, 0.9])
    row[0].write(project.name)
    row[1].write(project.project_mode)
    row[2].write(project.updated_at_iso)

    if row[3].button("Open", key=f"open_{project.project_id}", use_container_width=True):
        _append_status(f"Opened project '{project.name}'.", "success")
        _navigate_to(library, navigation, "project_overview", project.project_id)

    rename_active = st.session_state.ui_rename_project_id == project.project_id
    if not rename_active:
        if row[4].button("Rename", key=f"rename_btn_{project.project_id}", use_container_width=True):
            st.session_state.ui_rename_project_id = project.project_id
            st.rerun()
    else:
        row[4].write("Renaming")

    if row[5].button("Duplicate", key=f"duplicate_{project.project_id}", use_container_width=True):
        result, duplicate = run_safe_action(lambda: library.duplicate_project(project.project_id))
        if result.ok and duplicate is not None:
            _append_status(f"Duplicated as '{duplicate.name}'.", "success")
            _persist_state(library, navigation)
            st.rerun()
        else:
            _append_status(result.user_message, "error")

    archive_label = "Restore" if project.archived else "Archive"
    if row[6].button(archive_label, key=f"archive_{project.project_id}", use_container_width=True):
        library.archive_project(project.project_id, archived=not project.archived)
        state_label = "archived" if not project.archived else "restored"
        _append_status(f"Project '{project.name}' {state_label}.", "success")
        _persist_state(library, navigation)
        st.rerun()

    if row[7].button("Delete", key=f"delete_{project.project_id}", use_container_width=True):
        st.session_state.ui_delete_confirm_project_id = project.project_id
        st.rerun()

    if rename_active:
        rename_cols = st.columns([2.2, 1.0, 0.8])
        rename_key = f"rename_value_{project.project_id}"
        if rename_key not in st.session_state:
            st.session_state[rename_key] = project.name
        new_name = rename_cols[0].text_input(
            "New project name",
            key=rename_key,
            label_visibility="collapsed",
        )
        if rename_cols[1].button("Save Rename", key=f"rename_save_{project.project_id}", use_container_width=True):
            result, _ = run_safe_action(lambda: library.rename_project(project.project_id, new_name))
            if result.ok:
                _append_status("Project renamed and autosaved.", "success")
                st.session_state.ui_rename_project_id = None
                _persist_state(library, navigation)
                st.rerun()
            else:
                _append_status(result.user_message, "error")
        if rename_cols[2].button("Cancel", key=f"rename_cancel_{project.project_id}", use_container_width=True):
            st.session_state.ui_rename_project_id = None
            st.rerun()


def _render_delete_confirmation(library: ProjectLibrary, navigation: NavigationHistory) -> None:
    project_id = st.session_state.ui_delete_confirm_project_id
    if not project_id:
        return
    try:
        project = library.get_project(project_id)
    except KeyError:
        st.session_state.ui_delete_confirm_project_id = None
        return

    st.warning(f"Delete project '{project.name}'? This cannot be undone.")
    c1, c2 = st.columns(2)
    if c1.button("Confirm Delete", key=f"confirm_delete_{project_id}", use_container_width=True):
        result, _ = run_safe_action(lambda: library.delete_project(project_id, confirmed=True))
        if result.ok:
            if st.session_state.ui_current_project_id == project_id:
                st.session_state.ui_current_project_id = None
                st.session_state.ui_current_route = "projects"
            st.session_state.ui_delete_confirm_project_id = None
            _append_status("Project deleted.", "success")
            _persist_state(library, navigation)
            st.rerun()
        else:
            _append_status(result.user_message, "error")

    if c2.button("Cancel", key=f"cancel_delete_{project_id}", use_container_width=True):
        st.session_state.ui_delete_confirm_project_id = None
        st.rerun()


def _render_projects(library: ProjectLibrary, navigation: NavigationHistory) -> None:
    st.title("Projects")
    st.caption("Create, open, rename, duplicate, archive, or delete projects.")

    st.markdown("<div class='page-card'><div class='page-card-title'>Create Project</div>", unsafe_allow_html=True)
    _create_project_control(library, navigation, "projects")
    st.markdown("</div>", unsafe_allow_html=True)

    st.subheader("Active Projects")
    active = [project for project in library.list_projects(include_archived=True) if not project.archived]
    if not active:
        st.info("No active projects.")
    else:
        for project in active:
            _render_project_row(library, navigation, project)

    st.subheader("Archived Projects")
    archived = [project for project in library.list_projects(include_archived=True) if project.archived]
    if not archived:
        st.caption("No archived projects.")
    else:
        for project in archived:
            _render_project_row(library, navigation, project)

    _render_delete_confirmation(library, navigation)


def _workflow_cards() -> list[tuple[RouteId, str]]:
    return [
        ("project_definition", "Project Definition / Project Mode"),
        ("facility_resources", "Facility & Existing Resources"),
        ("demand_workflow_radionuclides", "Demand / Clinical Workflow / Radionuclides"),
        ("production_cyclotron_external_supply", "Production / Supply"),
        ("geometry_floor_transport", "Geometry / Transport"),
        ("mrt_infrastructure", "MRT Infrastructure"),
        ("economics_assumptions", "Economics"),
        ("review_run", "Review & Run"),
        ("results_executive", "Results"),
        ("master_engineering_data", "Master Engineering Data / Reports"),
    ]


def _render_field_semantics() -> None:
    st.markdown("<div class='page-card'><div class='page-card-title'>Field-State Semantics</div>", unsafe_allow_html=True)
    st.caption("Reusable field-state contract prepared for later form pages.")
    st.write(
        "REQUIRED, OPTIONAL, DEFAULT_MODEL_VALUE, USER_OVERRIDE, DERIVED, "
        "UNKNOWN, NOT_CALIBRATED, NOT_APPLICABLE, CONFLICTED, INVALID"
    )
    for rule in FIELD_STATE_NON_EQUIVALENCE_RULES:
        st.write(f"- {rule}")
    st.markdown("</div>", unsafe_allow_html=True)


def _project_mode(project: ProjectRecord) -> ProjectMode:
    return project.draft_state.get("project_mode_selection", project.project_mode)


def _project_supply_architecture(project: ProjectRecord) -> ProjectSupplyArchitecture:
    return project.draft_state.get("supply_architecture_selection", project.supply_architecture)


def _facility_baseline_complete(project: ProjectRecord) -> bool:
    value = project.saved_state.get("facility_baseline_complete", False)
    return bool(value)


def _humanize_run_status(status: str) -> str:
    return {
        "NO_RUN_YET": "Not run yet",
        "SUCCESS": "Successful",
        "FAILED_WITH_PREVIOUS_SUCCESS": "Failed after a previous success",
        "FAILED_NO_SUCCESS": "Failed",
    }.get(status, status.replace("_", " ").title())


def _humanize_draft_status(status: str) -> str:
    return {
        "SAVED": "Saved",
        "DRAFT": "Draft",
        "DIRTY_UNSAVED": "Unsaved changes",
    }.get(status, status.replace("_", " ").title())


def _humanize_timestamp(timestamp_iso: str) -> str:
    try:
        stamp = datetime.fromisoformat(timestamp_iso)
    except ValueError:
        return timestamp_iso
    return stamp.strftime("%b %-d, %Y, %-I:%M %p")


def _definition_edit_target_key(project: ProjectRecord) -> str:
    return f"definition_edit_target_{project.project_id}"


def _definition_edit_target(project: ProjectRecord) -> str:
    key = _definition_edit_target_key(project)
    target = st.session_state[key] if key in st.session_state else None
    if target in {"name", "mode", "supply", "summary"}:
        return target
    if _project_mode(project) == "UNSPECIFIED":
        return "mode"
    if _project_supply_architecture(project) == "UNSPECIFIED":
        return "supply"
    return "summary"


def _set_definition_edit_target(project: ProjectRecord, target: str) -> None:
    st.session_state[_definition_edit_target_key(project)] = target


def _clear_definition_edit_target(project: ProjectRecord) -> None:
    st.session_state.pop(_definition_edit_target_key(project), None)


def _mode_summary_label(project: ProjectRecord) -> str:
    return PROJECT_MODE_LABELS[_project_mode(project)]


def _supply_summary_label(project: ProjectRecord) -> str:
    return SUPPLY_ARCHITECTURE_LABELS[_project_supply_architecture(project)]


RESOURCE_HELP_TEXTS: dict[str, str] = {
    "cyclotron_units": "Number of cyclotron units currently installed at the facility.",
    "radiopharmacy_units": "Existing radiopharmacy preparation/processing units available to support the clinical workflow.",
    "scanner_resources": "Existing nuclear-medicine imaging scanner resources relevant to the planned workflow.",
    "injection_resources": "Existing patient injection stations/resources that can support radiopharmaceutical administration.",
    "uptake_resources": "Existing uptake spaces/resources used while patients wait between administration and imaging.",
    "distribution_concurrency": "Existing resources that determine how many radiopharmaceutical deliveries can be handled concurrently within the facility.",
    "mrt_endpoints": "Existing MRT delivery/receiving endpoints already installed at the facility.",
    "mrt_carriers": "Existing MRT carriers available for reuse in the proposed project.",
}

RETAINABLE_HELP_TEXT = (
    "Of the existing units, how many are currently operational and suitable to be retained in the proposed project?"
)
AUTO_RETAINABLE_HELP_TEMPLATE = "Assumed retainable: {quantity}. Adjust only if fewer units are operational."
ADJUST_RETAINABLE_LABEL = "Adjust retainable quantity"

GREENFIELD_EXISTING_ASSET_PROMPT = "This project is being modeled as a new facility. Existing-resource inheritance does not apply."

RESOURCE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Production", ("cyclotron_units", "radiopharmacy_units")),
    ("Clinical", ("scanner_resources", "injection_resources", "uptake_resources")),
    ("Distribution", ("distribution_concurrency",)),
    ("Existing MRT", ("mrt_endpoints", "mrt_carriers")),
)

MRT_NUMERIC_ONLY_RESOURCES: set[str] = {"mrt_endpoints", "mrt_carriers"}


def _definition_summary_row(label: str, value: str, project: ProjectRecord | None = None, target: str | None = None) -> None:
    if project is None or target is None:
        st.markdown(
            f"<div style='padding:0.15rem 0 0.35rem 0;'><div style='font-size:0.78rem;color:#5c5c5c;'>{label}</div><div style='font-weight:700;color:#121212;'>{value}</div></div>",
            unsafe_allow_html=True,
        )
        return

    value_col, edit_col = st.columns([0.75, 0.25])
    with value_col:
        st.markdown(
            f"<div style='padding:0.15rem 0 0.35rem 0;'><div style='font-size:0.78rem;color:#5c5c5c;'>{label}</div><div style='font-weight:700;color:#121212;'>{value}</div></div>",
            unsafe_allow_html=True,
        )
    with edit_col:
        st.markdown("<div style='padding-top:1.35rem;'>", unsafe_allow_html=True)
        if st.button("Edit", key=f"definition_summary_edit_{target}_{project.project_id}", use_container_width=True):
            _set_definition_edit_target(project, target)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def _resource_group_name(resource_key: str) -> str:
    for group_name, keys in RESOURCE_GROUPS:
        if resource_key in keys:
            return group_name
    return "Other"


def _inventory_status_from_widget(value: str) -> InventoryStatus:
    return {
        "NONE": "NONE",
        "KNOWN": "KNOWN",
        "UNKNOWN": "UNKNOWN",
    }[value]


def _inventory_inheritance_label(mode: ProjectMode, status: InventoryStatus, existing_quantity: int | None, retainable_quantity: int | None) -> str:
    if mode == "GREENFIELD":
        return "Not Applicable"
    if status == "UNKNOWN":
        return "Inventory Unknown"
    if status == "NONE":
        return "Confirmed None"
    if existing_quantity == 0:
        return "Confirmed None"
    if retainable_quantity is None:
        return "Existing"
    if retainable_quantity == 0:
        return "Existing — None Retainable"
    if retainable_quantity >= existing_quantity:
        return "Retained"
    return "Partially Retained"


def _render_resource_inventory_card(
    project: ProjectRecord,
    mode: ProjectMode,
    resource_key: str,
    resource_label: str,
    summary_rows: list[dict[str, Any]],
    field_errors: dict[str, str],
) -> None:
    st.markdown(f"<div class='page-card'><div class='page-card-title'>{resource_label}</div>", unsafe_allow_html=True)
    st.caption(RESOURCE_HELP_TEXTS[resource_key])

    status_key = _resource_status_key(resource_key)
    existing_key = _resource_existing_key(resource_key)
    usable_key = _resource_usable_key(resource_key)
    override_key = _resource_retainable_override_key(resource_key)
    mrt_numeric_only = mode == "EXISTING_FACILITY_RETROFIT" and resource_key in MRT_NUMERIC_ONLY_RESOURCES

    if mrt_numeric_only:
        if project.draft_state.get(status_key) != "KNOWN":
            project.set_draft_value(status_key, "KNOWN")

        existing_widget_key = f"facility_existing_{resource_key}_{project.project_id}"
        if existing_widget_key not in st.session_state:
            st.session_state[existing_widget_key] = str(project.draft_state.get(existing_key, ""))

        existing_label = "Existing MRT endpoints" if resource_key == "mrt_endpoints" else "Existing MRT carriers"
        existing_help = (
            "Number of MRT delivery/receiving endpoints currently installed at the facility. Enter 0 if none are installed."
            if resource_key == "mrt_endpoints"
            else "Number of MRT carriers currently available at the facility. Enter 0 if none are installed."
        )
        existing_input = st.text_input(
            existing_label,
            key=existing_widget_key,
            help=existing_help,
        )
        if project.draft_state.get(existing_key) != existing_input:
            project.set_draft_value(existing_key, existing_input)

        parsed_existing, existing_issue = parse_non_negative_integer(existing_input)
        if existing_issue:
            field_errors[existing_key] = f"{resource_label}: {existing_issue}"
            st.error(field_errors[existing_key])

        parsed_retainable: int | None = None
        retainable_display = "Not specified"
        if parsed_existing is not None and parsed_existing == 0:
            parsed_retainable = 0
            retainable_display = "0"
            _set_retainable_override(project, override_key, False)
            if project.draft_state.get(usable_key) != "0":
                project.set_draft_value(usable_key, "0")
            st.caption("No existing units are present.")
        elif parsed_existing is not None and parsed_existing > 0:
            override_widget_key = f"facility_retainable_override_{resource_key}_{project.project_id}"
            if override_widget_key not in st.session_state:
                st.session_state[override_widget_key] = _retainable_override_enabled(
                    project,
                    override_key,
                    usable_key,
                    parsed_existing,
                )
            override_enabled = st.checkbox(
                ADJUST_RETAINABLE_LABEL,
                key=override_widget_key,
                help="Open this only if the retainable quantity differs from the existing quantity.",
            )
            _set_retainable_override(project, override_key, override_enabled)
            if override_enabled:
                retainable_widget_key = f"facility_retainable_{resource_key}_{project.project_id}"
                if retainable_widget_key not in st.session_state:
                    st.session_state[retainable_widget_key] = str(project.draft_state.get(usable_key, parsed_existing))
                retainable_input = st.text_input(
                    "Retainable / operational quantity",
                    key=retainable_widget_key,
                    help=RETAINABLE_HELP_TEXT,
                )
                if project.draft_state.get(usable_key) != retainable_input:
                    project.set_draft_value(usable_key, retainable_input)
                if retainable_input.strip():
                    parsed_retainable, retainable_issue = parse_non_negative_integer(retainable_input)
                    if retainable_issue:
                        field_errors[usable_key] = f"{resource_label}: {retainable_issue}"
                        st.error(field_errors[usable_key])
                    elif parsed_retainable is not None and parsed_retainable > parsed_existing:
                        field_errors[usable_key] = f"{resource_label}: Retainable quantity cannot exceed existing quantity."
                        st.error(field_errors[usable_key])
                    else:
                        retainable_display = f"Adjusted ({parsed_retainable})"
                else:
                    retainable_display = "Adjusted"
            else:
                parsed_retainable = parsed_existing
                auto_retainable = str(parsed_existing)
                if project.draft_state.get(usable_key) != auto_retainable:
                    project.set_draft_value(usable_key, auto_retainable)
                retainable_display = f"Auto ({parsed_existing})"
                st.caption(AUTO_RETAINABLE_HELP_TEMPLATE.format(quantity=parsed_existing))

        existing_display = str(parsed_existing) if parsed_existing is not None else (existing_input or "Not specified")

        summary_rows.append(
            {
                "Resource": resource_label,
                "Inventory Status": INVENTORY_STATUS_LABELS["KNOWN"],
                "Existing": existing_display,
                "Retainable / Operational": retainable_display,
                "Inheritance Status": _inventory_inheritance_label("EXISTING_FACILITY_RETROFIT", "KNOWN", parsed_existing, parsed_retainable),
                "Notes": "",
            }
        )

        st.markdown("</div>", unsafe_allow_html=True)
        return

    if status_key not in project.draft_state:
        project.set_draft_value(status_key, "UNKNOWN" if mode == "EXISTING_FACILITY_RETROFIT" else "NONE")

    status_widget_key = f"facility_status_{resource_key}_{project.project_id}"
    if status_widget_key not in st.session_state:
        st.session_state[status_widget_key] = project.draft_state.get(status_key, "UNKNOWN")
    status_value = st.selectbox(
        "Inventory status",
        options=["NONE", "KNOWN", "UNKNOWN"],
        format_func=lambda value: INVENTORY_STATUS_LABELS[_inventory_status_from_widget(value)],
        key=status_widget_key,
        help="None means zero units currently exist. Known means the count is known. Unknown means the inventory has not yet been established.",
    )
    status = _inventory_status_from_widget(status_value)
    if project.draft_state.get(status_key) != status:
        project.set_draft_value(status_key, status)

    parsed_existing: int | None = None
    parsed_retainable: int | None = None
    existing_display: str
    retainable_display: str

    if status == "KNOWN":
        existing_widget_key = f"facility_existing_{resource_key}_{project.project_id}"
        if existing_widget_key not in st.session_state:
            st.session_state[existing_widget_key] = str(project.draft_state.get(existing_key, ""))
        existing_input = st.text_input(
            "Existing quantity",
            key=existing_widget_key,
            help="How many units physically exist at the facility today?",
        )
        if project.draft_state.get(existing_key) != existing_input:
            project.set_draft_value(existing_key, existing_input)
        parsed_existing, existing_issue = validate_resource_inventory(status=status, quantity_text=existing_input)
        if existing_issue:
            field_errors[existing_key] = f"{resource_label}: {existing_issue}"
            st.error(field_errors[existing_key])
        existing_display = str(parsed_existing if parsed_existing is not None else existing_input or "Not specified")
        if parsed_existing == 0:
            parsed_retainable = 0
            retainable_display = "0"
            _set_retainable_override(project, override_key, False)
            if project.draft_state.get(usable_key) != "0":
                project.set_draft_value(usable_key, "0")
            st.caption("No existing units are present.")
        elif parsed_existing is not None and parsed_existing > 0:
            override_widget_key = f"facility_retainable_override_{resource_key}_{project.project_id}"
            if override_widget_key not in st.session_state:
                st.session_state[override_widget_key] = _retainable_override_enabled(
                    project,
                    override_key,
                    usable_key,
                    parsed_existing,
                )
            override_enabled = st.checkbox(
                ADJUST_RETAINABLE_LABEL,
                key=override_widget_key,
                help="Open this only if the retainable quantity differs from the existing quantity.",
            )
            _set_retainable_override(project, override_key, override_enabled)

            if override_enabled:
                retainable_widget_key = f"facility_retainable_{resource_key}_{project.project_id}"
                if retainable_widget_key not in st.session_state:
                    st.session_state[retainable_widget_key] = str(project.draft_state.get(usable_key, parsed_existing))
                retainable_input = st.text_input(
                    "Retainable / operational quantity",
                    key=retainable_widget_key,
                    help=RETAINABLE_HELP_TEXT,
                )
                if project.draft_state.get(usable_key) != retainable_input:
                    project.set_draft_value(usable_key, retainable_input)
                if retainable_input.strip():
                    parsed_retainable, retainable_issue = parse_non_negative_integer(retainable_input)
                    if retainable_issue:
                        field_errors[usable_key] = f"{resource_label}: {retainable_issue}"
                        st.error(field_errors[usable_key])
                    elif parsed_existing is not None and parsed_retainable is not None and parsed_retainable > parsed_existing:
                        field_errors[usable_key] = f"{resource_label}: Retainable quantity cannot exceed existing quantity."
                        st.error(field_errors[usable_key])
                    else:
                        retainable_display = f"Adjusted ({parsed_retainable})"
                else:
                    retainable_display = "Adjusted"
            else:
                parsed_retainable = parsed_existing
                auto_retainable = str(parsed_existing)
                if project.draft_state.get(usable_key) != auto_retainable:
                    project.set_draft_value(usable_key, auto_retainable)
                retainable_display = f"Auto ({parsed_existing})"
                st.caption(AUTO_RETAINABLE_HELP_TEMPLATE.format(quantity=parsed_existing))
        else:
            retainable_display = "Pending"
    else:
        existing_display = "0" if status == "NONE" else "Unknown"
        retainable_display = "0" if status == "NONE" else "Unknown"
        _set_retainable_override(project, override_key, False)
        if status == "NONE" and project.draft_state.get(usable_key) != "0":
            project.set_draft_value(usable_key, "0")
        if status == "NONE":
            st.caption("No existing units are present.")
        else:
            st.caption("Current inventory has not been established.")

    if resource_key == "cyclotron_units" and mode == "EXISTING_FACILITY_RETROFIT":
        st.caption(cyclotron_inventory_semantics(status=status, quantity_text=existing_display if status == "KNOWN" else ""))

    summary_rows.append(
        {
            "Resource": resource_label,
            "Inventory Status": INVENTORY_STATUS_LABELS[status],
            "Existing": existing_display,
            "Retainable / Operational": retainable_display,
            "Inheritance Status": _inventory_inheritance_label(mode, status, parsed_existing, parsed_retainable),
            "Notes": "Confirmed none exist" if resource_key == "cyclotron_units" and status == "NONE" else "",
        }
    )

    st.markdown("</div>", unsafe_allow_html=True)


def _set_project_mode(project: ProjectRecord, mode: ProjectMode) -> bool:
    changed = project.project_mode != mode or project.draft_state.get("project_mode_selection") != mode
    project.project_mode = mode
    project.set_draft_value("project_mode_selection", mode)
    project.commit_draft_key("project_mode_selection")
    return changed


def _set_supply_architecture(project: ProjectRecord, supply_architecture: ProjectSupplyArchitecture) -> bool:
    changed = project.supply_architecture != supply_architecture or project.draft_state.get("supply_architecture_selection") != supply_architecture
    project.supply_architecture = supply_architecture
    project.set_draft_value("supply_architecture_selection", supply_architecture)
    project.commit_draft_key("supply_architecture_selection")
    return changed


def _resource_status_key(resource_key: str) -> str:
    return f"facility_resource::{resource_key}::status"


def _resource_existing_key(resource_key: str) -> str:
    return f"facility_resource::{resource_key}::existing"


def _resource_usable_key(resource_key: str) -> str:
    return f"facility_resource::{resource_key}::usable"


def _resource_retainable_override_key(resource_key: str) -> str:
    return f"facility_resource::{resource_key}::usable_override"


def _retainable_override_enabled(
    project: ProjectRecord,
    override_key: str,
    usable_key: str,
    parsed_existing: int | None,
) -> bool:
    value = project.draft_state.get(override_key)
    if value is None and parsed_existing is not None and parsed_existing > 0:
        usable_value = str(project.draft_state.get(usable_key, "")).strip()
        return bool(usable_value) and usable_value != str(parsed_existing)
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


def _set_retainable_override(project: ProjectRecord, override_key: str, enabled: bool) -> None:
    if project.draft_state.get(override_key) != enabled:
        project.set_draft_value(override_key, enabled)


def _apply_greenfield_resource_defaults(project: ProjectRecord) -> None:
    changed = False
    for resource_key, _ in RESOURCE_FIELD_LABELS:
        status_key = _resource_status_key(resource_key)
        existing_key = _resource_existing_key(resource_key)
        usable_key = _resource_usable_key(resource_key)
        if status_key not in project.draft_state:
            project.set_draft_value(status_key, "KNOWN")
            changed = True
        if existing_key not in project.draft_state:
            project.set_draft_value(existing_key, "0")
            changed = True
        if usable_key not in project.draft_state:
            project.set_draft_value(usable_key, "0")
            changed = True
    if changed:
        project.set_draft_value("facility_defaults_applied_for_greenfield", True)


def _mode_supply_consequence_text(mode: ProjectMode, supply_architecture: ProjectSupplyArchitecture) -> str:
    if mode == "EXISTING_FACILITY_RETROFIT" and supply_architecture == "EXTERNAL_SUPPLY_HUB_SPOKE":
        return (
            "Existing hospital resources will be inherited where known. "
            "Radiopharmaceutical supply may come from an external source. "
            "Existing on-site cyclotron assets, if any, are preserved and must be entered on the Facility & Existing Resources page."
        )
    if mode == "EXISTING_FACILITY_RETROFIT" and supply_architecture == "ON_SITE_PRODUCTION":
        return "Existing resources will be inherited and on-site production assets remain part of the expansion baseline."
    if mode == "GREENFIELD" and supply_architecture == "EXTERNAL_SUPPLY_HUB_SPOKE":
        return "This is a new facility pathway with external supply architecture and no assumed inherited hospital resource baseline."
    if mode == "GREENFIELD" and supply_architecture == "ON_SITE_PRODUCTION":
        return "This is a new facility pathway with planned on-site production and no assumed inherited hospital resource baseline."
    return "Select both project mode and supply architecture to complete setup."


def _render_project_definition(library: ProjectLibrary, navigation: NavigationHistory, project: ProjectRecord | None) -> None:
    st.title("Project Definition / Project Mode")
    if project is None:
        st.warning("Open a project to continue.")
        if st.button("Open from Projects", use_container_width=False):
            _navigate_to(library, navigation, "projects", None)
        return

    edit_target = _definition_edit_target(project)
    mode = _project_mode(project)
    supply_architecture = _project_supply_architecture(project)

    summary_col, workspace_col = st.columns([1.05, 1.95], gap="large")

    with summary_col:
        st.markdown("<div class='page-card'><div class='page-card-title'>Project Setup</div>", unsafe_allow_html=True)
        _definition_summary_row("Project Name", project.name, project, "name")
        _definition_summary_row(
            "Project Mode",
            _mode_summary_label(project),
            project,
            "mode",
        )
        _definition_summary_row(
            "Supply Architecture",
            _supply_summary_label(project),
            project,
            "supply",
        )
        baseline_value = "Next" if validate_mode_supply_selection(mode, supply_architecture) == () else "In progress"
        st.markdown(
            f"<div style='padding:0.35rem 0 0.15rem 0;'><div style='font-size:0.78rem;color:#5c5c5c;'>Facility Baseline</div><div style='font-weight:700;color:#121212;'>{baseline_value}</div></div>",
            unsafe_allow_html=True,
        )
        if validate_mode_supply_selection(mode, supply_architecture) == ():
            if st.button("Next", key=f"definition_summary_next_{project.project_id}", use_container_width=True):
                _clear_definition_edit_target(project)
                _navigate_to(library, navigation, "facility_resources", project.project_id)
        else:
            st.caption("Select project mode and supply architecture to continue.")
        st.markdown("</div>", unsafe_allow_html=True)

    with workspace_col:
        if edit_target == "name":
            st.markdown("<div class='page-card'><div class='page-card-title'>Project Name</div>", unsafe_allow_html=True)
            st.caption("Edit the project name without leaving this page.")
            name_key = f"definition_name_{project.project_id}"
            if name_key not in st.session_state:
                st.session_state[name_key] = project.name
            edited_name = st.text_input("Project name", key=name_key, help="This name appears throughout the workflow.")
            name_cols = st.columns(2)
            if name_cols[0].button("Save Name", key=f"definition_save_name_{project.project_id}", use_container_width=True):
                result, _ = run_safe_action(lambda: library.rename_project(project.project_id, edited_name))
                if result.ok:
                    _persist_state(library, navigation)
                    _clear_error_presentation_state()
                    _clear_definition_edit_target(project)
                    st.rerun()
                else:
                    _append_status(result.user_message, "error")
            if name_cols[1].button("Cancel", key=f"definition_cancel_name_{project.project_id}", use_container_width=True):
                _clear_definition_edit_target(project)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        elif edit_target == "mode":
            st.markdown("<div class='page-card'><div class='page-card-title'>Project Mode</div>", unsafe_allow_html=True)
            st.caption("What type of project are you planning?")
            left, right = st.columns(2)
            with left:
                st.markdown("**Greenfield**")
                st.caption("Plan a new facility with no inherited hospital resources unless entered explicitly.")
                if st.button("Select Greenfield", key=f"set_mode_greenfield_{project.project_id}", use_container_width=True):
                    changed = _set_project_mode(project, "GREENFIELD")
                    if changed:
                        _persist_state(library, navigation)
                        _clear_error_presentation_state()
                        st.rerun()
            with right:
                st.markdown("**Retrofit / Existing Facility Expansion**")
                st.caption("Expand an existing facility while retaining known usable resources.")
                if st.button("Select Retrofit", key=f"set_mode_retrofit_{project.project_id}", use_container_width=True):
                    changed = _set_project_mode(project, "EXISTING_FACILITY_RETROFIT")
                    if changed:
                        _persist_state(library, navigation)
                        _clear_error_presentation_state()
                        st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        elif edit_target == "supply":
            st.markdown("<div class='page-card'><div class='page-card-title'>Supply Architecture</div>", unsafe_allow_html=True)
            st.caption("How will radiopharmaceuticals be supplied?")
            left, right = st.columns(2)
            with left:
                st.markdown("**On-site Production**")
                if st.button("Select On-site Production", key=f"set_supply_onsite_{project.project_id}", use_container_width=True):
                    changed = _set_supply_architecture(project, "ON_SITE_PRODUCTION")
                    if changed:
                        _persist_state(library, navigation)
                        _clear_error_presentation_state()
                        st.rerun()
            with right:
                st.markdown("**External Supply / Hub-and-Spoke**")
                if st.button("Select External Supply / Hub-and-Spoke", key=f"set_supply_external_{project.project_id}", use_container_width=True):
                    changed = _set_supply_architecture(project, "EXTERNAL_SUPPLY_HUB_SPOKE")
                    if changed:
                        _persist_state(library, navigation)
                        _clear_error_presentation_state()
                        st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='page-card'><div class='page-card-title'>Combination Summary</div>", unsafe_allow_html=True)
            combo = f"{_mode_summary_label(project)} + {_supply_summary_label(project)}"
            st.write(combo)
            st.caption(_mode_supply_consequence_text(mode, supply_architecture))
            st.markdown("</div>", unsafe_allow_html=True)

            issues = validate_mode_supply_selection(mode, supply_architecture)
            for issue in issues:
                st.error(issue)

            if st.button(
                "Continue to Facility & Existing Resources",
                key=f"continue_to_facility_{project.project_id}",
                use_container_width=True,
                disabled=bool(issues),
            ):
                _clear_definition_edit_target(project)
                _navigate_to(library, navigation, "facility_resources", project.project_id)


def _render_facility_resources(library: ProjectLibrary, navigation: NavigationHistory, project: ProjectRecord | None) -> None:
    st.title("Facility & Existing Resources")
    if project is None:
        st.warning("Open a project to continue.")
        if st.button("Open from Projects", use_container_width=False):
            _navigate_to(library, navigation, "projects", None)
        return

    mode = _project_mode(project)
    supply_architecture = _project_supply_architecture(project)
    mode_issues = validate_mode_supply_selection(mode, supply_architecture)
    if mode_issues:
        for issue in mode_issues:
            st.error(issue)
        if st.button("Go to Project Definition / Project Mode", use_container_width=False):
            _navigate_to(library, navigation, "project_definition", project.project_id)
        return

    st.caption(f"Current setup: {PROJECT_MODE_LABELS[mode]} + {SUPPLY_ARCHITECTURE_LABELS[supply_architecture]}")

    if mode == "GREENFIELD":
        st.markdown("<div class='page-card'><div class='page-card-title'>New Facility</div>", unsafe_allow_html=True)
        st.info(GREENFIELD_EXISTING_ASSET_PROMPT)
        st.caption("No inherited resources are assumed.")
        st.write("Resource baseline: No inherited resources")

        greenfield_toggle_key = f"greenfield_existing_assets_enabled_{project.project_id}"
        if greenfield_toggle_key not in st.session_state:
            st.session_state[greenfield_toggle_key] = False
        if not st.session_state[greenfield_toggle_key]:
            if st.button("Include pre-existing equipment", key=f"enable_greenfield_existing_assets_{project.project_id}", use_container_width=False):
                st.session_state[greenfield_toggle_key] = True
                st.rerun()
        else:
            with st.expander("Advanced: Include pre-existing equipment", expanded=True):
                st.caption("Optional only. Use this if a nominally new facility still has explicitly identified pre-existing equipment.")
                field_errors: dict[str, str] = {}
                summary_rows: list[dict[str, Any]] = []
                tracked_keys: list[str] = []
                for group_name, group_keys in RESOURCE_GROUPS:
                    st.subheader(group_name)
                    for resource_key in group_keys:
                        resource_label = dict(RESOURCE_FIELD_LABELS)[resource_key]
                        _render_resource_inventory_card(project, mode, resource_key, resource_label, summary_rows, field_errors)
                        tracked_keys.extend(
                            (
                                _resource_status_key(resource_key),
                                _resource_existing_key(resource_key),
                                _resource_usable_key(resource_key),
                                _resource_retainable_override_key(resource_key),
                            )
                        )

                st.subheader("Optional Asset Summary")
                st.dataframe(summary_rows, hide_index=True, use_container_width=True)

                if field_errors:
                    for issue in field_errors.values():
                        st.error(issue)
                else:
                    st.success("Optional existing-asset entries are currently valid.")

                if st.button("Save Optional Existing Asset Entries", key=f"save_facility_greenfield_{project.project_id}", use_container_width=True):
                    if field_errors:
                        _append_status("Fix blocking resource errors before saving.", "error")
                    else:
                        for key in tracked_keys:
                            project.commit_draft_key(key)
                        project.set_draft_value("facility_baseline_complete", True)
                        project.commit_draft_key("facility_baseline_complete")
                        _persist_state(library, navigation)
                        _clear_error_presentation_state()
                        st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        nav_cols = st.columns(2)
        if nav_cols[0].button("Continue to Demand / Clinical Workflow / Radionuclides", key=f"continue_greenfield_{project.project_id}", use_container_width=True):
            project.set_draft_value("facility_baseline_complete", True)
            project.commit_draft_key("facility_baseline_complete")
            _persist_state(library, navigation)
            _navigate_to(library, navigation, "demand_workflow_radionuclides", project.project_id)
        return

    st.info(
        "Enter resources currently present at the facility. Resources that remain usable can be retained in the proposed expansion rather than purchased again."
    )

    field_errors: dict[str, str] = {}
    summary_rows: list[dict[str, Any]] = []
    tracked_keys: list[str] = []

    for group_name, group_keys in RESOURCE_GROUPS:
        st.subheader(group_name)
        for resource_key in group_keys:
            resource_label = dict(RESOURCE_FIELD_LABELS)[resource_key]
            _render_resource_inventory_card(project, mode, resource_key, resource_label, summary_rows, field_errors)
            tracked_keys.extend(
                (
                    _resource_status_key(resource_key),
                    _resource_existing_key(resource_key),
                    _resource_usable_key(resource_key),
                    _resource_retainable_override_key(resource_key),
                )
            )

    st.subheader("Retrofit Inheritance Summary")
    st.dataframe(summary_rows, hide_index=True, use_container_width=True)

    st.markdown("<div class='page-card'><div class='page-card-title'>Validation</div>", unsafe_allow_html=True)
    if field_errors:
        for issue in field_errors.values():
            st.error(issue)
    else:
        st.success("Resource baseline entries are currently valid.")
    st.markdown("</div>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    if c1.button("Save Resource Baseline", key=f"save_facility_{project.project_id}", use_container_width=True):
        if field_errors:
            _append_status("Fix blocking resource errors before saving.", "error")
        else:
            for key in tracked_keys:
                project.commit_draft_key(key)
            project.set_draft_value("facility_baseline_complete", True)
            project.commit_draft_key("facility_baseline_complete")
            _persist_state(library, navigation)
            _clear_error_presentation_state()
            st.rerun()

    if c2.button(
        "Continue to Demand / Clinical Workflow / Radionuclides",
        key=f"continue_facility_{project.project_id}",
        use_container_width=True,
        disabled=bool(field_errors),
    ):
        for key in tracked_keys:
            project.commit_draft_key(key)
        project.set_draft_value("facility_baseline_complete", True)
        project.commit_draft_key("facility_baseline_complete")
        _persist_state(library, navigation)
        _navigate_to(library, navigation, "demand_workflow_radionuclides", project.project_id)


def _render_project_overview(library: ProjectLibrary, navigation: NavigationHistory, project: ProjectRecord | None) -> None:
    if project is None:
        st.title("Project Overview")
        st.warning("No project is open. Open a project from Projects.")
        if st.button("Go to Projects", use_container_width=False):
            _navigate_to(library, navigation, "projects", None)
        return

    st.title("Project Overview")

    title_cols = st.columns([2.3, 1.0])
    overview_name_key = f"overview_name_{project.project_id}"
    if overview_name_key not in st.session_state:
        st.session_state[overview_name_key] = project.name
    new_name = title_cols[0].text_input("Project Name", key=overview_name_key)
    st.markdown("<div class='mrt-primary'>", unsafe_allow_html=True)
    if title_cols[1].button("Save Name", use_container_width=True, key=f"overview_save_name_{project.project_id}"):
        result, _ = run_safe_action(lambda: library.rename_project(project.project_id, new_name))
        if result.ok:
            _append_status("Project name saved.", "success")
            _persist_state(library, navigation)
            st.rerun()
        else:
            _append_status(result.user_message, "error")
    st.markdown("</div>", unsafe_allow_html=True)

    status_text = "Archived" if project.archived else "Active"
    mode_label = PROJECT_MODE_LABELS[_project_mode(project)]
    supply_label = SUPPLY_ARCHITECTURE_LABELS[_project_supply_architecture(project)]
    facility_baseline_label = "Complete" if _facility_baseline_complete(project) else "Incomplete"
    setup_progress = (
        "Ready for next stage"
        if _facility_baseline_complete(project)
        else ("Facility baseline pending" if validate_mode_supply_selection(_project_mode(project), _project_supply_architecture(project)) == () else "Project setup in progress")
    )
    st.markdown("<div class='progress-grid'>", unsafe_allow_html=True)
    st.markdown(
        (
            "<div class='progress-box'><div class='progress-label'>Project State</div>"
            f"<div class='progress-value'>{status_text}</div></div>"
            f"<div class='progress-box'><div class='progress-label'>Setup Progress</div><div class='progress-value'>{setup_progress}</div></div>"
            f"<div class='progress-box'><div class='progress-label'>Draft Status</div><div class='progress-value'>{_humanize_draft_status(project.draft_status)}</div></div>"
            f"<div class='progress-box'><div class='progress-label'>Last Modified</div><div class='progress-value'>{_humanize_timestamp(project.updated_at_iso)}</div></div>"
            f"<div class='progress-box'><div class='progress-label'>Run Status</div><div class='progress-value'>{_humanize_run_status(project.run_status)}</div></div>"
            f"<div class='progress-box'><div class='progress-label'>Project Mode</div><div class='progress-value'>{mode_label}</div></div>"
            f"<div class='progress-box'><div class='progress-label'>Supply Architecture</div><div class='progress-value'>{supply_label}</div></div>"
            f"<div class='progress-box'><div class='progress-label'>Facility Resource Baseline</div><div class='progress-value'>{facility_baseline_label}</div></div>"
        ),
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    draft_key = "overview_note"
    draft_value = project.draft_state.get(draft_key, "")
    overview_note_key = f"overview_note_{project.project_id}"
    if overview_note_key not in st.session_state:
        st.session_state[overview_note_key] = str(draft_value)
    note = st.text_area("Project notes (draft)", key=overview_note_key)
    if note != draft_value:
        project.set_draft_value(draft_key, note)
        _persist_state(library, navigation)

    c1, c2 = st.columns(2)
    if c1.button("Save Draft Note", use_container_width=True, key=f"save_note_{project.project_id}"):
        project.commit_draft_key(draft_key)
        _persist_state(library, navigation)
        st.rerun()

    st.subheader("Workflow Entry")
    st.caption("Use these large entry actions to continue the engineering workflow.")
    cards = _workflow_cards()
    cols = st.columns(2)
    for idx, (route, label) in enumerate(cards):
        with cols[idx % 2]:
            st.markdown("<div class='cta-large'>", unsafe_allow_html=True)
            if st.button(label, key=f"overview_route_{route}_{project.project_id}", use_container_width=True):
                _navigate_to(library, navigation, route, project.project_id)
            st.markdown("</div>", unsafe_allow_html=True)


def _render_validation_block(messages: tuple[ValidationMessage, ...], title: str) -> None:
    if not messages:
        return
    st.markdown(f"**{title}**")
    for message in messages:
        line = message.message
        if message.fix_route:
            line = f"{line} | Fix -> {PAGE_LABELS[message.fix_route]}"

        if message.severity == "ERROR":
            st.error(line)
        elif message.severity == "WARNING":
            st.warning(line)
        elif message.severity == "UNKNOWN_OR_NOT_CALIBRATED":
            st.info(f"UNKNOWN/NOT CALIBRATED: {line}")
        elif message.severity == "READY_VALID":
            st.success(line)
        else:
            st.caption(line)


def _render_placeholder(library: ProjectLibrary, navigation: NavigationHistory, route: RouteId, project: ProjectRecord | None) -> None:
    st.title(PAGE_LABELS[route])
    if project is None:
        st.warning("Open a project to continue.")
        if st.button("Open from Projects", use_container_width=False):
            _navigate_to(library, navigation, "projects", None)
        return

    st.markdown("<span class='status-pill'>Build 1 placeholder</span>", unsafe_allow_html=True)
    st.write("This page is intentionally scaffolded for a later UI build. Navigation, state, and safety contracts are active.")
    st.caption(f"Project in context: {project.name}")

    if route == "review_run":
        snapshot = default_readiness_snapshot()
        _render_validation_block(snapshot.blockers, "Blockers")
        _render_validation_block(snapshot.warnings, "Warnings")
        _render_validation_block(snapshot.unknown_or_not_calibrated, "Unknown / Not Calibrated")
        _render_validation_block(snapshot.information, "Information")
        _render_validation_block(snapshot.ready, "Ready / Valid")
        if snapshot.defaults_in_use:
            st.markdown("**Defaults in use**")
            for item in snapshot.defaults_in_use:
                st.write(f"- {item}")

    route_note_key = f"draft_note::{route}"
    route_note = project.draft_state.get(route_note_key, "")
    placeholder_note_key = f"placeholder_note_{route}_{project.project_id}"
    if placeholder_note_key not in st.session_state:
        st.session_state[placeholder_note_key] = str(route_note)
    edited = st.text_area(
        "Draft notes for this page",
        key=placeholder_note_key,
    )
    if edited != route_note:
        project.set_draft_value(route_note_key, edited)
        _persist_state(library, navigation)

    if st.button("Save Page Draft", key=f"save_page_draft_{route}_{project.project_id}", use_container_width=False):
        project.commit_draft_key(route_note_key)
        _persist_state(library, navigation)
        _append_status("Page draft saved.", "success")
        st.rerun()


def _render_error_boundary(library: ProjectLibrary, navigation: NavigationHistory, action_result: AppActionResult) -> None:
    st.error(action_result.user_message)
    nav1, nav2 = st.columns(2)
    if nav1.button("Return to Review", use_container_width=True):
        _navigate_to(library, navigation, "review_run", st.session_state.ui_current_project_id)
    if nav2.button("Fix Inputs (Project Overview)", use_container_width=True):
        _navigate_to(library, navigation, "project_overview", st.session_state.ui_current_project_id)

    with st.expander("Technical Details"):
        st.code(action_result.technical_details or "No technical details.")


def _render_current_page(library: ProjectLibrary, navigation: NavigationHistory, project: ProjectRecord | None) -> None:
    route = st.session_state.ui_current_route
    if route == "home":
        _render_home(library, navigation)
    elif route == "projects":
        _render_projects(library, navigation)
    elif route == "project_overview":
        _render_project_overview(library, navigation, project)
    elif route == "project_definition":
        _render_project_definition(library, navigation, project)
    elif route == "facility_resources":
        _render_facility_resources(library, navigation, project)
    elif route in FUTURE_PAGE_ROUTES:
        _render_placeholder(library, navigation, route, project)
    else:
        st.error(f"Unknown route: {route}")


def run() -> None:
    _inject_style()
    library, navigation = _init_state()
    current_project = _resolve_open_project(library)
    _render_shell(library, navigation, current_project)

    action_result, _ = run_safe_action(lambda: _render_current_page(library, navigation, current_project))
    if not action_result.ok:
        st.session_state.ui_last_error = action_result.technical_details
        _render_error_boundary(library, navigation, action_result)
    else:
        _clear_error_presentation_state()


run()
