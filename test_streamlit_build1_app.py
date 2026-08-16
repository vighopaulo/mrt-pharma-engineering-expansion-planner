from __future__ import annotations

from streamlit.testing.v1 import AppTest

from ui_foundation import NavEntry, NavigationHistory, ProjectLibrary, serialize_navigation, serialize_project_library


def _app() -> AppTest:
    return AppTest.from_file("app.py")


def _seed_project_view(route: str = "project_overview") -> tuple[AppTest, str]:
    library = ProjectLibrary()
    project = library.create_project("Alpha")
    history = NavigationHistory(entries=[NavEntry(route=route, project_id=project.project_id)], cursor=0)

    at = _app()
    at.session_state["ui_project_library"] = serialize_project_library(library)
    at.session_state["ui_navigation"] = serialize_navigation(history)
    at.session_state["ui_current_route"] = route
    at.session_state["ui_current_project_id"] = project.project_id
    return at, project.project_id


def test_home_page_renders_and_create_project_routes_to_overview() -> None:
    at = _app()
    at.run()

    assert [node.value for node in at.title] == ["Home"]
    assert "Home / Landing" not in "\n".join(node.value for node in at.title)
    assert any(getattr(button, "label", None) == "Create Project" for button in at.button)

    at.text_input[0].set_value("Alpha")
    for button in at.button:
        if getattr(button, "label", None) == "Create Project":
            button.click().run()
            break

    assert [node.value for node in at.title] == ["Project Overview"]
    assert any("Created project 'Alpha'." in node.value for node in at.success)


def test_projects_page_renders_project_library_actions() -> None:
    library = ProjectLibrary()
    library.create_project("Alpha")
    at = _app()
    at.session_state["ui_project_library"] = serialize_project_library(library)
    at.session_state["ui_current_route"] = "projects"
    at.run()

    assert [node.value for node in at.title] == ["Projects"]
    labels = [getattr(button, "label", None) for button in at.button]
    for expected in ["Create Project", "Open", "Rename", "Duplicate", "Archive", "Delete"]:
        assert expected in labels


def test_project_overview_renders_workflow_entry_cards() -> None:
    at, _ = _seed_project_view("project_overview")
    at.run()

    assert [node.value for node in at.title] == ["Project Overview"]
    labels = [getattr(button, "label", None) for button in at.button]
    for expected in [
        "Project Definition / Project Mode",
        "Facility & Existing Resources",
        "Demand / Clinical Workflow / Radionuclides",
        "Production / Supply",
        "Geometry / Transport",
        "MRT Infrastructure",
        "Economics",
        "Review & Run",
        "Results",
        "Master Engineering Data / Reports",
    ]:
        assert expected in labels


def test_placeholder_page_preserves_project_identity_and_scaffold_message() -> None:
    at, project_id = _seed_project_view("review_run")
    at.run()

    assert [node.value for node in at.title] == ["Review & Run"]
    assert at.session_state["ui_current_project_id"] == project_id
    caption_text = "\n".join(node.value for node in at.caption)
    info_text = "\n".join(node.value for node in at.info)
    assert "Build 1 provides readiness scaffolding" in caption_text
    assert "Project in context: Alpha" in caption_text
    assert "Not calibrated values will be routed here" in info_text


def test_shell_navigation_controls_render_on_primary_routes() -> None:
    for route in ["home", "projects", "project_overview", "review_run"]:
        if route == "home":
            at = _app()
        elif route == "projects":
            at = _app()
            at.session_state["ui_current_route"] = route
        else:
            at, _ = _seed_project_view(route)
        at.run()
        labels = [getattr(button, "label", None) for button in at.button]
        assert labels[:4] == ["Home", "Back", "Forward", "Projects"]

        shell_text = "\n".join(node.value for node in at.markdown[:6])
        assert "Page: Home / Landing" not in shell_text
        assert "Project: No project open" not in shell_text


def test_shared_shell_uses_mrt_pharma_branding() -> None:
    at = _app()
    at.run()

    shell_text = "\n".join(node.value for node in at.markdown[:6])
    assert "<span class='brand-word-mrt'>MRT</span><span class='brand-word-pharma'>Pharma</span>" in shell_text
    assert "Digital Twin" in shell_text
    assert ".brand-word-mrt" in shell_text
    assert ".brand-word-pharma" in shell_text
    assert "MRTWay" not in shell_text
    assert "Engineering Expansion Planner" not in shell_text


def test_project_overview_preserves_internal_project_context_without_global_header() -> None:
    at, project_id = _seed_project_view("project_overview")
    at.run()

    assert [node.value for node in at.title] == ["Project Overview"]
    assert at.session_state["ui_current_project_id"] == project_id
    shell_text = "\n".join(node.value for node in at.markdown[:6])
    assert "Page: Project Overview" not in shell_text
    assert "Project: Alpha" not in shell_text
