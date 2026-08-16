from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

import streamlit as st

from cyclotron_catalog import (
    FacilityCyclotronInstance,
    build_fleet_from_instances,
    create_facility_cyclotron_instance,
    list_models_grouped_by_manufacturer,
    load_cyclotron_catalog,
    migration_from_legacy_model_counts,
)
from facility_engineering_model import (
    ALL_EQUIPMENT_CLASSES,
    CoordinateSystem,
    EquipmentClass,
    FacilityEngineeringObjectModel,
    ProjectSpatialMode,
    SpatialCoordinate,
    SpatialMaturity,
    SpatialSourceType,
    SubscriptionTier,
    build_default_facility_engineering_object_model,
    deserialize_facility_engineering_object_model,
    migrate_legacy_geometry_state,
    resolve_default_source_profile,
    resolve_subscription_capability_profile,
    serialize_facility_engineering_object_model,
    validate_facility_engineering_object_model,
)
from diagnostics import load_radionuclide_half_lives
from mrt_carrier_fleet import resolve_mrt_carrier_fleet
from stochastic_design_day import ActivityDemandModel, DesignDayDemandScenario, generate_design_day_demand

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
        ("demand_workflow_radionuclides", "Demand & Clinical Workflow"),
        ("production_cyclotron_external_supply", "Production / Cyclotron / External Supply"),
        ("geometry_floor_transport", "Spatial / Facility Engineering / Transport"),
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


def _render_build3_context_summary(library: ProjectLibrary, navigation: NavigationHistory, project: ProjectRecord) -> None:
    st.markdown("<div class='page-card'><div class='page-card-title'>Project Context</div>", unsafe_allow_html=True)
    mode = _project_mode(project)
    supply = _project_supply_architecture(project)
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**Project**\n\n{project.name}")
    c2.markdown(f"**Project Mode**\n\n{PROJECT_MODE_LABELS[mode]}")
    c3.markdown(f"**Supply Architecture**\n\n{SUPPLY_ARCHITECTURE_LABELS[supply]}")
    n1, n2 = st.columns(2)
    if n1.button("Edit Project Definition", key=f"build3_edit_definition_{project.project_id}", use_container_width=True):
        _navigate_to(library, navigation, "project_definition", project.project_id)
    if n2.button("Edit Facility Baseline", key=f"build3_edit_facility_{project.project_id}", use_container_width=True):
        _navigate_to(library, navigation, "facility_resources", project.project_id)
    st.markdown("</div>", unsafe_allow_html=True)


def _parse_positive_float(value: str, *, label: str, allow_zero: bool = False) -> tuple[float | None, str | None]:
    text = value.strip()
    if not text:
        return None, f"{label} is required."
    try:
        parsed = float(text)
    except ValueError:
        return None, f"{label} must be numeric."
    if parsed < 0.0 or (not allow_zero and parsed == 0.0):
        return None, f"{label} must be greater than zero."
    return parsed, None


def _default_activity_mbq(radionuclide: str) -> float:
    return {
        "F-18": 370.0,
        "Ga-68": 185.0,
        "C-11": 555.0,
        "N-13": 740.0,
        "O-15": 925.0,
        "Tc-99m": 740.0,
    }.get(radionuclide, 370.0)


def _build3_cyclotron_instances(project: ProjectRecord) -> list[FacilityCyclotronInstance]:
    raw = project.draft_state.get("build3::production::cyclotron_instances")
    if isinstance(raw, list) and raw:
        instances: list[FacilityCyclotronInstance] = []
        for item in raw:
            if isinstance(item, dict):
                try:
                    instances.append(FacilityCyclotronInstance.from_dict(item))
                except Exception:
                    continue
        if instances:
            return instances
    return list(migration_from_legacy_model_counts(project.draft_state))


def _build3_set_cyclotron_instances(project: ProjectRecord, instances: list[FacilityCyclotronInstance]) -> None:
    project.set_draft_value("build3::production::cyclotron_instances", [instance.to_dict() for instance in instances])


def _render_demand_workflow(library: ProjectLibrary, navigation: NavigationHistory, project: ProjectRecord | None) -> None:
    st.title("Demand & Clinical Workflow")
    if project is None:
        st.warning("Open a project to continue.")
        return
    _render_build3_context_summary(library, navigation, project)

    st.markdown("<div class='page-card'><div class='page-card-title'>Design Basis</div>", unsafe_allow_html=True)
    st.caption("Use compact design-basis inputs. Patient radionuclide assignment is generated from project-active radionuclides.")

    demand_key = f"build3_demand_expected_{project.project_id}"
    hours_key = f"build3_demand_hours_{project.project_id}"
    days_key = f"build3_demand_days_{project.project_id}"
    seed_key = f"build3_demand_seed_{project.project_id}"
    day_type_key = f"build3_demand_day_type_{project.project_id}"

    st.session_state.setdefault(demand_key, str(project.draft_state.get("build3::demand::expected_patients_per_day", "180")))
    st.session_state.setdefault(hours_key, str(project.draft_state.get("build3::demand::operating_hours_per_day", "12")))
    st.session_state.setdefault(days_key, str(project.draft_state.get("build3::demand::operating_days_per_year", "300")))
    st.session_state.setdefault(seed_key, str(project.draft_state.get("build3::demand::seed", "42")))
    st.session_state.setdefault(day_type_key, str(project.draft_state.get("build3::demand::day_type", "typical")))

    expected = st.text_input("Expected patient demand per day", key=demand_key, help="Default: 180")
    hours = st.text_input("Operating hours per day", key=hours_key, help="Default: 12")
    days = st.text_input("Operating days per year", key=days_key, help="Default: 300")
    day_type = st.selectbox("Design day type", options=["typical", "peak"], key=day_type_key)
    seed = st.text_input("Demand generation seed", key=seed_key, help="Default: 42")

    errors: list[str] = []
    expected_patients, issue = parse_non_negative_integer(expected)
    if issue or expected_patients in (None, 0):
        errors.append("Expected patient demand per day must be a whole number greater than zero.")
    operating_hours, hours_issue = _parse_positive_float(hours, label="Operating hours per day")
    if hours_issue:
        errors.append(hours_issue)
    operating_days, days_issue = parse_non_negative_integer(days)
    if days_issue or operating_days in (None, 0):
        errors.append("Operating days per year must be a whole number greater than zero.")
    seed_value, seed_issue = parse_non_negative_integer(seed)
    if seed_issue:
        errors.append(f"Demand generation seed: {seed_issue}")

    mode = _project_mode(project)
    supply = _project_supply_architecture(project)
    if mode == "UNSPECIFIED" or supply == "UNSPECIFIED":
        st.error("Complete Project Definition before configuring demand.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    if supply == "ON_SITE_PRODUCTION":
        active_radionuclides = tuple(project.draft_state.get("build3::production::active_radionuclides", ()))
    else:
        active_radionuclides = tuple(project.draft_state.get("build3::external_supply::active_radionuclides", ()))
    if not active_radionuclides:
        active_radionuclides = ("F-18",)

    st.write(f"**Project-active radionuclides**: {', '.join(active_radionuclides)}")
    st.caption("Generated / Derived demand mix uses the active subset above. No manual patient-level radionuclide selection is required.")

    if errors:
        for error in errors:
            st.error(error)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    mix = {radionuclide: 1.0 for radionuclide in active_radionuclides}
    models = {
        radionuclide: ActivityDemandModel(model_type="fixed", fixed_activity_mbq=_default_activity_mbq(radionuclide))
        for radionuclide in active_radionuclides
    }
    scenario = DesignDayDemandScenario(
        target_patients_per_day=int(expected_patients),
        radionuclide_mix=mix,
        activity_distribution_by_radionuclide=models,
        day_type=day_type,
        available_radionuclides=active_radionuclides,
        unsupported_radionuclide_policy="reject",
        seed=int(seed_value),
    )
    generated = generate_design_day_demand(scenario)

    rows = []
    for radionuclide in sorted(generated.patient_count_by_radionuclide):
        rows.append(
            {
                "Radionuclide": radionuclide,
                "Patients": int(generated.patient_count_by_radionuclide[radionuclide]),
                "Total Activity (MBq/day)": round(float(generated.total_activity_by_radionuclide[radionuclide]), 2),
            }
        )
    st.write("**Generated Clinical Demand Mix (Derived)**")
    st.dataframe(rows, hide_index=True, use_container_width=True)

    project.set_draft_value("build3::demand::expected_patients_per_day", str(expected_patients))
    project.set_draft_value("build3::demand::operating_hours_per_day", str(operating_hours))
    project.set_draft_value("build3::demand::operating_days_per_year", str(operating_days))
    project.set_draft_value("build3::demand::seed", str(seed_value))
    project.set_draft_value("build3::demand::day_type", day_type)
    project.set_draft_value("build3::demand::generated_mix", rows)

    if st.button("Save Demand Draft", key=f"save_build3_demand_{project.project_id}", use_container_width=True):
        for key in (
            "build3::demand::expected_patients_per_day",
            "build3::demand::operating_hours_per_day",
            "build3::demand::operating_days_per_year",
            "build3::demand::seed",
            "build3::demand::day_type",
            "build3::demand::generated_mix",
        ):
            project.commit_draft_key(key)
        _persist_state(library, navigation)
        _append_status("Demand workflow draft saved.", "success")
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _render_production_supply(library: ProjectLibrary, navigation: NavigationHistory, project: ProjectRecord | None) -> None:
    st.title("Production / Cyclotron / External Supply")
    if project is None:
        st.warning("Open a project to continue.")
        return
    _render_build3_context_summary(library, navigation, project)

    supply = _project_supply_architecture(project)
    if supply == "UNSPECIFIED":
        st.error("Select supply architecture in Project Definition first.")
        return

    if supply == "ON_SITE_PRODUCTION":
        st.markdown("<div class='page-card'><div class='page-card-title'>On-site Cyclotron Fleet</div>", unsafe_allow_html=True)
        st.caption("Add individual cyclotron instances from the catalog. Manufacturer/model definitions stay separate from facility instances.")

        catalog = load_cyclotron_catalog()
        grouped = list_models_grouped_by_manufacturer(catalog)
        instances = _build3_cyclotron_instances(project)

        selector_col1, selector_col2 = st.columns(2)
        manufacturers = list(grouped.keys())
        selected_manufacturer = selector_col1.selectbox(
            "Select manufacturer",
            options=manufacturers,
            key=f"build3_catalog_manufacturer_{project.project_id}",
        )
        model_options = grouped.get(selected_manufacturer, ())
        selected_model = selector_col2.selectbox(
            "Select model",
            options=[model.catalog_model_id for model in model_options],
            format_func=lambda model_id: next((model.model for model in model_options if model.catalog_model_id == model_id), model_id),
            key=f"build3_catalog_model_{project.project_id}",
        )
        if st.button("Add Cyclotron", key=f"build3_add_cyclotron_{project.project_id}", use_container_width=False):
            instances.append(
                create_facility_cyclotron_instance(
                    catalog_model_id=selected_model,
                    existing_instances=instances,
                )
            )
            _build3_set_cyclotron_instances(project, instances)
            _persist_state(library, navigation)
            st.rerun()

        if instances:
            st.write("**Configured facility cyclotrons**")
            rows: list[dict[str, Any]] = []
            for idx, instance in enumerate(instances):
                model = catalog.by_id(instance.catalog_model_id)
                rows.append(
                    {
                        "Instance ID": instance.instance_id,
                        "Manufacturer": model.manufacturer,
                        "Model": model.model,
                        "Commercial Status": model.commercial_status,
                        "State": instance.operating_state,
                        "Capability Status": model.production_calibration_status,
                    }
                )
                if st.button(
                    f"Remove {instance.instance_id}",
                    key=f"build3_remove_cyclotron_{project.project_id}_{idx}",
                    use_container_width=False,
                ):
                    instances.pop(idx)
                    _build3_set_cyclotron_instances(project, instances)
                    _persist_state(library, navigation)
                    st.rerun()
            st.dataframe(rows, hide_index=True, use_container_width=True)

        if not instances:
            st.error("At least one cyclotron instance is required for On-site Production.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        fleet, warnings = build_fleet_from_instances(catalog=catalog, instances=instances)
        for warning in warnings:
            st.warning(warning)

        supported_union = tuple() if fleet is None else tuple(fleet.fleet_supported_radionuclides)
        if not supported_union:
            st.info("No calibrated radionuclide-cycle capability has been provided yet for selected cyclotrons.")
        st.write(f"**Facility production capability (union)**: {', '.join(supported_union)}")

        active_default = tuple(project.draft_state.get("build3::production::active_radionuclides", supported_union))
        valid_active_default = tuple(item for item in active_default if item in supported_union)
        if valid_active_default != active_default:
            st.warning("Previously active radionuclides were revalidated after fleet changes and unsupported items were removed.")
        if supported_union:
            active_subset = st.multiselect(
                "Radionuclides active for this project",
                options=list(supported_union),
                default=list(valid_active_default or supported_union),
                key=f"build3_active_subset_{project.project_id}",
                help="Active subset must be supported by the selected cyclotron fleet.",
            )
            if not active_subset:
                st.error("Select at least one active radionuclide.")
                st.markdown("</div>", unsafe_allow_html=True)
                return
        else:
            active_subset = []

        eob_key = f"build3_eob_capacity_{project.project_id}"
        st.session_state.setdefault(eob_key, str(project.draft_state.get("build3::production::eob_capacity_mbq_day", "")))
        eob_text = st.text_input(
            "Confirmed calibrated EOB capacity (MBq/day) [optional]",
            key=eob_key,
            help="Leave blank if not calibrated.",
        )
        if eob_text.strip():
            eob_value, eob_issue = _parse_positive_float(eob_text, label="EOB capacity", allow_zero=False)
            if eob_issue:
                st.error(eob_issue)
            else:
                st.success(f"Calibrated EOB capacity: {eob_value:.2f} MBq/day")
        else:
            st.info("Cyclotron capacity: Not calibrated")

        st.caption("Selecting a smaller active radionuclide subset does not remove selected cyclotron equipment or its physical/economic consequences.")

        _build3_set_cyclotron_instances(project, instances)
        project.set_draft_value("build3::production::supported_union", supported_union)
        project.set_draft_value("build3::production::fleet_asset_ids", tuple() if fleet is None else tuple(asset.cyclotron_id for asset in fleet.assets))
        project.set_draft_value("build3::production::active_radionuclides", tuple(active_subset))
        project.set_draft_value("build3::production::eob_capacity_mbq_day", eob_text.strip())
        project.set_draft_value("build3::production::capacity_status", "CALIBRATED" if eob_text.strip() else "NOT_CALIBRATED")

        if st.button("Save Production Draft", key=f"save_build3_production_{project.project_id}", use_container_width=True):
            keys = [
                "build3::production::cyclotron_instances",
                "build3::production::supported_union",
                "build3::production::fleet_asset_ids",
                "build3::production::active_radionuclides",
                "build3::production::eob_capacity_mbq_day",
                "build3::production::capacity_status",
            ]
            for key in keys:
                project.commit_draft_key(key)
            _persist_state(library, navigation)
            _append_status("Production draft saved.", "success")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    st.markdown("<div class='page-card'><div class='page-card-title'>External Supply / Hub-and-Spoke</div>", unsafe_allow_html=True)
    st.caption("Configure source capability and transport assumptions. On-site cyclotron selection is not required in external-supply mode.")
    isotopes = list(load_radionuclide_half_lives().keys())
    source_supported = st.multiselect(
        "Source-supported radionuclides",
        options=isotopes,
        default=list(project.draft_state.get("build3::external_supply::source_supported_radionuclides", ("F-18",))),
        key=f"build3_external_supported_{project.project_id}",
    )
    if not source_supported:
        st.error("Select at least one source-supported radionuclide.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    default_active = tuple(item for item in project.draft_state.get("build3::external_supply::active_radionuclides", source_supported) if item in source_supported)
    active_subset = st.multiselect(
        "Radionuclides active for this project",
        options=source_supported,
        default=list(default_active or tuple(source_supported)),
        key=f"build3_external_active_{project.project_id}",
    )
    if not active_subset:
        st.error("Select at least one active radionuclide.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    last_mile_key = f"build3_external_last_mile_{project.project_id}"
    st.session_state.setdefault(last_mile_key, str(project.draft_state.get("build3::external_supply::airport_to_hospital_minutes", "20")))
    last_mile = st.text_input(
        "Airport-to-hospital transfer time (minutes)",
        key=last_mile_key,
        help="This basis can be aligned across conventional and MRT pathways for controlled comparison.",
    )
    _, issue = _parse_positive_float(last_mile, label="Airport-to-hospital transfer time", allow_zero=False)
    if issue:
        st.error(issue)

    existing_cyclotron_status = project.draft_state.get("facility_resource::cyclotron_units::status", "UNKNOWN")
    existing_cyclotron_qty = project.draft_state.get("facility_resource::cyclotron_units::existing", "")
    st.caption(f"Retrofit inherited on-site cyclotron context is preserved: {existing_cyclotron_status} ({existing_cyclotron_qty or 'unspecified'}).")

    project.set_draft_value("build3::external_supply::source_supported_radionuclides", tuple(source_supported))
    project.set_draft_value("build3::external_supply::active_radionuclides", tuple(active_subset))
    project.set_draft_value("build3::external_supply::airport_to_hospital_minutes", last_mile.strip())

    if st.button("Save External Supply Draft", key=f"save_build3_external_{project.project_id}", use_container_width=True):
        for key in (
            "build3::external_supply::source_supported_radionuclides",
            "build3::external_supply::active_radionuclides",
            "build3::external_supply::airport_to_hospital_minutes",
        ):
            project.commit_draft_key(key)
        _persist_state(library, navigation)
        _append_status("External supply draft saved.", "success")
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _render_geometry_transport(library: ProjectLibrary, navigation: NavigationHistory, project: ProjectRecord | None) -> None:
    st.title("Spatial / Facility Engineering / Transport")
    if project is None:
        st.warning("Open a project to continue.")
        return
    _render_build3_context_summary(library, navigation, project)

    existing_model = migrate_legacy_geometry_state(project.draft_state)
    if existing_model is None:
        existing_model = build_default_facility_engineering_object_model(
            facility_id=project.project_id,
            facility_name=project.name,
            project_spatial_mode="GREENFIELD" if _project_mode(project) == "GREENFIELD" else "RETROFIT",
            source_type="MANUAL",
            subscription_tier="BASIC",
            coordinate_system=CoordinateSystem(coordinate_system_id="LOCAL-1", name="Local engineering coordinates", building="Building A", storey="Level 1", local_coordinate_system="LOCAL", source_coordinate_reference="manual facility definition", scale_m_per_unit=1.0),
        )

    source_key = f"build3_facility_source_{project.project_id}"
    evidence_key = f"build3_facility_evidence_{project.project_id}"
    maturity_key = f"build3_facility_maturity_{project.project_id}"
    tier_key = f"build3_facility_tier_{project.project_id}"
    mode_key = f"build3_facility_mode_{project.project_id}"
    facility_name_key = f"build3_facility_name_{project.project_id}"
    building_name_key = f"build3_facility_building_{project.project_id}"
    storey_name_key = f"build3_facility_storey_{project.project_id}"
    space_name_key = f"build3_facility_space_{project.project_id}"
    equipment_class_key = f"build3_facility_equipment_class_{project.project_id}"
    equipment_name_key = f"build3_facility_equipment_name_{project.project_id}"
    instance_id_key = f"build3_facility_instance_id_{project.project_id}"
    coord_id_key = f"build3_facility_coordinate_system_id_{project.project_id}"
    coord_name_key = f"build3_facility_coordinate_system_name_{project.project_id}"
    coord_building_key = f"build3_facility_coordinate_building_{project.project_id}"
    coord_storey_key = f"build3_facility_coordinate_storey_{project.project_id}"
    local_coord_key = f"build3_facility_local_coordinate_{project.project_id}"
    source_coord_key = f"build3_facility_source_reference_{project.project_id}"
    scale_key = f"build3_facility_scale_{project.project_id}"
    x_key = f"build3_facility_x_{project.project_id}"
    y_key = f"build3_facility_y_{project.project_id}"
    z_key = f"build3_facility_z_{project.project_id}"
    orientation_key = f"build3_facility_orientation_{project.project_id}"
    route_distance_key = f"build3_facility_route_distance_{project.project_id}"
    vertical_change_key = f"build3_facility_vertical_change_{project.project_id}"
    floors_key = f"build3_facility_floors_{project.project_id}"

    source_options_by_tier = {
        "BASIC": ["MANUAL", "TEMPLATE", "BENCHMARK"],
        "PROFESSIONAL": ["MANUAL", "TEMPLATE", "BENCHMARK", "PDF", "IMAGE", "DWG", "DXF"],
        "ENTERPRISE": ["MANUAL", "TEMPLATE", "BENCHMARK", "PDF", "IMAGE", "DWG", "DXF", "IFC", "REVIT_BIM"],
    }

    st.markdown("<div class='page-card'><div class='page-card-title'>Evidence Spectrum</div>", unsafe_allow_html=True)
    st.caption("Subscription level only changes which spatial evidence sources are available. It does not alter physics.")

    st.session_state.setdefault(tier_key, str(existing_model.subscription_tier))
    subscription_tier = st.selectbox("Subscription tier", options=["BASIC", "PROFESSIONAL", "ENTERPRISE"], key=tier_key)
    allowed_sources = source_options_by_tier[subscription_tier]

    default_source = existing_model.source_type if existing_model.source_type in allowed_sources else allowed_sources[0]
    st.session_state.setdefault(source_key, str(default_source))
    source_type = st.selectbox("Spatial input source", options=allowed_sources, key=source_key)
    evidence_class_default, maturity_default, _ = resolve_default_source_profile(source_type)
    st.session_state.setdefault(evidence_key, str(existing_model.evidence_class if existing_model.evidence_class else evidence_class_default))
    st.session_state.setdefault(maturity_key, str(existing_model.maturity if existing_model.maturity else maturity_default))
    evidence_class = st.selectbox(
        "Evidence class",
        options=["BIM_AUTHORITATIVE", "CAD_ENGINEERING", "PLAN_DERIVED", "USER_SUPPLIED", "TEMPLATE_DERIVED", "BENCHMARK_ASSUMED", "DERIVED_GEOMETRY"],
        key=evidence_key,
    )
    maturity = st.selectbox("Spatial maturity", options=["CONCEPTUAL", "PRELIMINARY", "ENGINEERING", "BIM_VERIFIED"], key=maturity_key)
    capability_profile = resolve_subscription_capability_profile(subscription_tier)
    st.write(f"**Allowed source methods**: {', '.join(capability_profile.allowed_spatial_sources)}")
    st.write(f"**Available analysis**: {', '.join(capability_profile.allowed_analysis_modes)}")

    st.markdown("<div class='page-card'><div class='page-card-title'>Canonical Facility Object Model</div>", unsafe_allow_html=True)
    st.caption("This page stores a canonical facility engineering object model; IFC, CAD, PDF, manual, template, and benchmark inputs all normalize into the same downstream structure.")

    project_mode_default = "RETROFIT" if _project_mode(project) == "EXISTING_FACILITY_RETROFIT" else "GREENFIELD"
    st.session_state.setdefault(mode_key, project_mode_default)
    project_spatial_mode = st.selectbox("Spatial project mode", options=["RETROFIT", "GREENFIELD"], key=mode_key)

    st.session_state.setdefault(facility_name_key, str(existing_model.facility_name or project.name))
    st.session_state.setdefault(building_name_key, str(existing_model.coordinate_system.building or "Building A"))
    st.session_state.setdefault(storey_name_key, str(existing_model.coordinate_system.storey or "Level 1"))
    st.session_state.setdefault(space_name_key, str(existing_model.spaces[0].name if existing_model.spaces else "Primary Room"))
    st.session_state.setdefault(equipment_class_key, str(existing_model.equipment[0].equipment_class if existing_model.equipment else "Cyclotron"))
    st.session_state.setdefault(equipment_name_key, str(existing_model.equipment[0].name if existing_model.equipment else "Facility Equipment"))
    st.session_state.setdefault(instance_id_key, str(existing_model.equipment[0].facility_instance_id if existing_model.equipment else ""))
    st.session_state.setdefault(coord_id_key, str(existing_model.coordinate_system.coordinate_system_id))
    st.session_state.setdefault(coord_name_key, str(existing_model.coordinate_system.name))
    st.session_state.setdefault(coord_building_key, str(existing_model.coordinate_system.building or "Building A"))
    st.session_state.setdefault(coord_storey_key, str(existing_model.coordinate_system.storey or "Level 1"))
    st.session_state.setdefault(local_coord_key, str(existing_model.coordinate_system.local_coordinate_system or "LOCAL"))
    st.session_state.setdefault(source_coord_key, str(existing_model.coordinate_system.source_coordinate_reference or source_type))
    st.session_state.setdefault(scale_key, "1.0" if existing_model.coordinate_system.scale_m_per_unit is None else str(existing_model.coordinate_system.scale_m_per_unit))
    st.session_state.setdefault(x_key, "" if existing_model.spaces[0].coordinate is None or existing_model.spaces[0].coordinate.x_m is None else str(existing_model.spaces[0].coordinate.x_m))
    st.session_state.setdefault(y_key, "" if existing_model.spaces[0].coordinate is None or existing_model.spaces[0].coordinate.y_m is None else str(existing_model.spaces[0].coordinate.y_m))
    st.session_state.setdefault(z_key, "" if existing_model.spaces[0].coordinate is None or existing_model.spaces[0].coordinate.z_m is None else str(existing_model.spaces[0].coordinate.z_m))
    st.session_state.setdefault(orientation_key, "" if existing_model.spaces[0].coordinate is None or existing_model.spaces[0].coordinate.orientation_deg is None else str(existing_model.spaces[0].coordinate.orientation_deg))
    st.session_state.setdefault(route_distance_key, str(project.draft_state.get("build3::geometry::route_distance_m", "")))
    st.session_state.setdefault(vertical_change_key, str(project.draft_state.get("build3::geometry::vertical_transfer_m", "0")))
    st.session_state.setdefault(floors_key, str(project.draft_state.get("build3::geometry::floors", "1")))

    facility_name = st.text_input("Facility name", key=facility_name_key)
    building_name = st.text_input("Building name", key=building_name_key)
    storey_name = st.text_input("Storey / floor name", key=storey_name_key)
    space_name = st.text_input("Room / space name", key=space_name_key)
    equipment_class = st.selectbox("Primary spatial equipment type", options=list(ALL_EQUIPMENT_CLASSES), key=equipment_class_key)
    equipment_name = st.text_input("Primary spatial equipment label", key=equipment_name_key)
    facility_instance_id = st.text_input("Equipment instance / catalog reference", key=instance_id_key, help="References the equipment instance catalog identity, not manufacturer physics.")

    coord_id = st.text_input("Coordinate system ID", key=coord_id_key)
    coord_name = st.text_input("Coordinate system name", key=coord_name_key)
    coord_building = st.text_input("Coordinate system building", key=coord_building_key)
    coord_storey = st.text_input("Coordinate system storey", key=coord_storey_key)
    local_coordinate_system = st.text_input("Local coordinate system", key=local_coord_key)
    source_coordinate_reference = st.text_input("Source coordinate reference", key=source_coord_key)
    scale_text = st.text_input("Source scale (m per drawing unit)", key=scale_key)

    c1, c2, c3, c4 = st.columns(4)
    x_text = c1.text_input("x (m)", key=x_key)
    y_text = c2.text_input("y (m)", key=y_key)
    z_text = c3.text_input("z (m)", key=z_key)
    orientation_text = c4.text_input("Orientation (deg)", key=orientation_key)

    route_distance = st.text_input("Network route distance (m)", key=route_distance_key, help="Geometry only; carrier travel time is handled later.")
    vertical_change = st.text_input("Vertical change (m)", key=vertical_change_key, help="Use 0 if the route is planar.")
    floors = st.text_input("Number of storeys represented", key=floors_key, help="Whole number. Supports multi-storey facilities.")

    errors: list[str] = []
    _, route_issue = _parse_positive_float(route_distance, label="Network route distance", allow_zero=False)
    if route_issue:
        errors.append(route_issue)
    floors_value, floors_issue = parse_non_negative_integer(floors)
    if floors_issue or floors_value in (None, 0):
        errors.append("Number of storeys represented must be a whole number greater than zero.")
    _, vertical_issue = _parse_positive_float(vertical_change, label="Vertical change", allow_zero=True)
    if vertical_issue:
        errors.append(vertical_issue)

    if errors:
        for error in errors:
            st.error(error)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    coordinate = SpatialCoordinate(
        x_m=_safe_float(x_text),
        y_m=_safe_float(y_text),
        z_m=_safe_float(z_text),
        building=coord_building or None,
        storey=coord_storey or None,
        orientation_deg=_safe_float(orientation_text),
        local_coordinate_system=local_coordinate_system or None,
        source_coordinate_reference=source_coordinate_reference or None,
        scale_m_per_unit=_safe_float(scale_text),
    )

    model = build_default_facility_engineering_object_model(
        facility_id=project.project_id,
        facility_name=facility_name,
        project_spatial_mode=project_spatial_mode,
        source_type=source_type,
        subscription_tier=subscription_tier,
        coordinate_system=CoordinateSystem(
            coordinate_system_id=coord_id,
            name=coord_name,
            building=coord_building or None,
            storey=coord_storey or None,
            local_coordinate_system=local_coordinate_system or None,
            source_coordinate_reference=source_coordinate_reference or None,
            scale_m_per_unit=_safe_float(scale_text),
        ),
        facility_instance_id=facility_instance_id or None,
        building_name=building_name,
        storey_name=storey_name,
        space_name=space_name,
        equipment_class=equipment_class,  # type: ignore[arg-type]
        equipment_name=equipment_name or None,
        route_distance_m=_safe_float(route_distance),
        vertical_change_m=_safe_float(vertical_change),
        room_coordinate=coordinate,
        notes=(f"Spatial maturity: {maturity}", f"Storeys represented: {floors.strip() or '1'}"),
    )
    model = replace(model, evidence_class=evidence_class, maturity=maturity, subscription_tier=subscription_tier)
    validation_issues = validate_facility_engineering_object_model(model)
    if validation_issues:
        st.markdown("**Spatial validation**")
        for issue in validation_issues:
            if issue.severity == "ERROR":
                st.error(issue.message)
            elif issue.severity == "WARNING":
                st.warning(issue.message)
            else:
                st.info(issue.message)

    st.write("**Canonical object summary**")
    st.write(f"Facility: {model.facility_name}")
    st.write(f"Evidence class: {model.evidence_class}")
    st.write(f"Maturity: {model.maturity}")
    st.write(f"Facility objects: {len(model.buildings) + len(model.storeys) + len(model.spaces) + len(model.equipment)}")
    st.write(f"Spatial nodes: {len(model.nodes)}")
    st.write(f"Spatial edges: {len(model.edges)}")

    project.set_draft_value("build3::geometry::route_distance_m", route_distance.strip())
    project.set_draft_value("build3::geometry::floors", floors.strip() or "1")
    project.set_draft_value("build3::geometry::vertical_transfer_m", vertical_change.strip())
    project.set_draft_value("build3::facility_engineering::model", serialize_facility_engineering_object_model(model))
    project.set_draft_value("build3::facility_engineering::source_type", source_type)
    project.set_draft_value("build3::facility_engineering::subscription_tier", subscription_tier)
    project.set_draft_value("build3::facility_engineering::project_spatial_mode", project_spatial_mode)
    project.set_draft_value("build3::facility_engineering::facility_name", facility_name)
    project.set_draft_value("build3::facility_engineering::building_name", building_name)
    project.set_draft_value("build3::facility_engineering::storey_name", storey_name)
    project.set_draft_value("build3::facility_engineering::space_name", space_name)
    project.set_draft_value("build3::facility_engineering::equipment_class", equipment_class)
    project.set_draft_value("build3::facility_engineering::equipment_name", equipment_name)

    if st.button("Save Spatial Draft", key=f"save_build3_geometry_{project.project_id}", use_container_width=True):
        for key in (
            "build3::geometry::route_distance_m",
            "build3::geometry::floors",
            "build3::geometry::vertical_transfer_m",
            "build3::facility_engineering::model",
            "build3::facility_engineering::source_type",
            "build3::facility_engineering::subscription_tier",
            "build3::facility_engineering::project_spatial_mode",
            "build3::facility_engineering::facility_name",
            "build3::facility_engineering::building_name",
            "build3::facility_engineering::storey_name",
            "build3::facility_engineering::space_name",
            "build3::facility_engineering::equipment_class",
            "build3::facility_engineering::equipment_name",
        ):
            project.commit_draft_key(key)
        _persist_state(library, navigation)
        _append_status("Spatial foundation draft saved.", "success")
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _render_mrt_infrastructure(library: ProjectLibrary, navigation: NavigationHistory, project: ProjectRecord | None) -> None:
    st.title("MRT Infrastructure")
    if project is None:
        st.warning("Open a project to continue.")
        return
    _render_build3_context_summary(library, navigation, project)

    mode = _project_mode(project)
    st.markdown("<div class='page-card'><div class='page-card-title'>MRT Engineering Inputs</div>", unsafe_allow_html=True)

    if mode == "EXISTING_FACILITY_RETROFIT":
        inherited_endpoints = project.draft_state.get("facility_resource::mrt_endpoints::usable", "0")
        inherited_carriers = project.draft_state.get("facility_resource::mrt_carriers::usable", "0")
        st.write(f"**Inherited MRT endpoints (operational)**: {inherited_endpoints}")
        st.write(f"**Inherited MRT carriers (operational)**: {inherited_carriers}")
    else:
        st.info("Greenfield: configure planned MRT infrastructure only. Existing MRT baseline is not inherited.")

    dist_key = f"build3_mrt_distribution_{project.project_id}"
    st.session_state.setdefault(
        dist_key,
        str(project.draft_state.get("build3::mrt::distribution_concurrency", project.draft_state.get("facility_resource::distribution_concurrency::usable", "1") or "1")),
    )
    distribution_concurrency = st.text_input(
        "Planned MRT distribution concurrency",
        key=dist_key,
        help="Used by native MRT carrier fleet contract.",
    )
    dist_value, dist_issue = parse_non_negative_integer(distribution_concurrency)
    if dist_issue or dist_value in (None, 0):
        st.error("Planned MRT distribution concurrency must be a whole number greater than zero.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    carriers_result = resolve_mrt_carrier_fleet(distribution_concurrency=int(dist_value))
    st.write(f"**MRT carriers (auto-derived)**: {carriers_result.installed_carriers}")
    st.caption("Carrier quantity is derived from MRT distribution concurrency in the current native contract.")

    endpoints_key = f"build3_mrt_endpoints_planned_{project.project_id}"
    st.session_state.setdefault(endpoints_key, str(project.draft_state.get("build3::mrt::planned_endpoints", "")))
    planned_endpoints = st.text_input(
        "Planned MRT endpoints",
        key=endpoints_key,
        help="Bounded manual input. Auto-sizing for endpoints is not yet calibrated.",
    )
    endpoint_value, endpoint_issue = parse_non_negative_integer(planned_endpoints)
    if endpoint_issue:
        st.error(f"Planned MRT endpoints: {endpoint_issue}")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    guideway_key = f"build3_mrt_guideway_{project.project_id}"
    st.session_state.setdefault(guideway_key, str(project.draft_state.get("build3::mrt::planned_guideway_length_m", "")))
    guideway_length = st.text_input(
        "Planned guideway length (m)",
        key=guideway_key,
        help="Bounded manual input. Spatial auto-derivation is not yet available.",
    )
    guideway_value, guideway_issue = _parse_positive_float(guideway_length, label="Planned guideway length", allow_zero=True)
    if guideway_issue:
        st.error(guideway_issue)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    project.set_draft_value("build3::mrt::distribution_concurrency", str(dist_value))
    project.set_draft_value("build3::mrt::auto_carriers", carriers_result.installed_carriers)
    project.set_draft_value("build3::mrt::planned_endpoints", str(endpoint_value))
    project.set_draft_value("build3::mrt::planned_guideway_length_m", str(guideway_value))

    if st.button("Save MRT Infrastructure Draft", key=f"save_build3_mrt_{project.project_id}", use_container_width=True):
        for key in (
            "build3::mrt::distribution_concurrency",
            "build3::mrt::auto_carriers",
            "build3::mrt::planned_endpoints",
            "build3::mrt::planned_guideway_length_m",
        ):
            project.commit_draft_key(key)
        _persist_state(library, navigation)
        _append_status("MRT infrastructure draft saved.", "success")
        st.rerun()
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
    elif route == "demand_workflow_radionuclides":
        _render_demand_workflow(library, navigation, project)
    elif route == "production_cyclotron_external_supply":
        _render_production_supply(library, navigation, project)
    elif route == "geometry_floor_transport":
        _render_geometry_transport(library, navigation, project)
    elif route == "mrt_infrastructure":
        _render_mrt_infrastructure(library, navigation, project)
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
