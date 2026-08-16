from __future__ import annotations

from typing import Any

import streamlit as st

from ui_foundation import (
    FIELD_STATE_NON_EQUIVALENCE_RULES,
    FUTURE_PAGE_ROUTES,
    PAGE_LABELS,
    AppActionResult,
    NavEntry,
    NavigationHistory,
    ProjectLibrary,
    ProjectRecord,
    RouteId,
    ValidationMessage,
    default_readiness_snapshot,
    deserialize_navigation,
    deserialize_project_library,
    run_safe_action,
    serialize_navigation,
    serialize_project_library,
)


st.set_page_config(page_title="MRTWay", page_icon="M", layout="wide")


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
        }
        .shell-subtitle {
            color: var(--mrt-gray-600);
            margin-top: 2px;
            margin-bottom: 0;
        }
        .brand-dot {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: var(--mrt-red);
            margin-right: 8px;
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
    st.markdown("<div class='shell'>", unsafe_allow_html=True)

    st.markdown("<p class='shell-title'><span class='brand-dot'></span>MRTWay</p>", unsafe_allow_html=True)
    st.markdown("<p class='shell-subtitle'>Engineering Expansion Planner</p>", unsafe_allow_html=True)

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

    st.markdown("</div>", unsafe_allow_html=True)

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
        ("project_definition", "Project Definition"),
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
    st.markdown("<div class='progress-grid'>", unsafe_allow_html=True)
    st.markdown(
        (
            "<div class='progress-box'><div class='progress-label'>Project State</div>"
            f"<div class='progress-value'>{status_text}</div></div>"
            f"<div class='progress-box'><div class='progress-label'>Draft Status</div><div class='progress-value'>{project.draft_status}</div></div>"
            f"<div class='progress-box'><div class='progress-label'>Last Modified</div><div class='progress-value'>{project.updated_at_iso}</div></div>"
            f"<div class='progress-box'><div class='progress-label'>Run State</div><div class='progress-value'>{project.run_status}</div></div>"
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
        _append_status("Draft note saved.", "success")
        st.rerun()

    if c2.button("Mark Latest Attempt Failed (Contract Test)", use_container_width=True, key=f"mark_failed_{project.project_id}"):
        project.set_run_failed()
        _persist_state(library, navigation)
        _append_status("Recorded failed attempt while preserving any previous success reference.", "warning")
        st.rerun()

    _render_field_semantics()

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
        _append_status(action_result.user_message, "error")
        st.session_state.ui_last_error = action_result.technical_details
        _render_error_boundary(library, navigation, action_result)


run()
