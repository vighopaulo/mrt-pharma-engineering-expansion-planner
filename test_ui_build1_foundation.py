from __future__ import annotations

from ui_foundation import (
    NavEntry,
    NavigationHistory,
    ProjectLibrary,
    default_readiness_snapshot,
    deserialize_navigation,
    deserialize_project_library,
    run_safe_action,
    serialize_navigation,
    serialize_project_library,
)


def test_project_create_rename_duplicate_archive_delete_flow() -> None:
    library = ProjectLibrary()

    created = library.create_project("Alpha")
    assert created.name == "Alpha"

    renamed = library.rename_project(created.project_id, "Alpha Prime")
    assert renamed.project_id == created.project_id
    assert renamed.name == "Alpha Prime"

    duplicate = library.duplicate_project(created.project_id)
    assert duplicate.project_id != created.project_id
    assert duplicate.name.startswith("Alpha Prime")

    archived = library.archive_project(created.project_id, archived=True)
    assert archived.archived is True

    restored = library.archive_project(created.project_id, archived=False)
    assert restored.archived is False

    try:
        library.delete_project(created.project_id, confirmed=False)
        assert False, "delete without confirmation should fail"
    except ValueError:
        pass

    library.delete_project(created.project_id, confirmed=True)
    assert created.project_id not in library.projects


def test_project_state_isolation_between_projects() -> None:
    library = ProjectLibrary()
    a = library.create_project("Project A")
    b = library.create_project("Project B")

    a.set_draft_value("overview_note", "A note")
    b.set_draft_value("overview_note", "B note")

    assert a.draft_state["overview_note"] == "A note"
    assert b.draft_state["overview_note"] == "B note"


def test_navigation_history_back_forward_and_deduplication() -> None:
    history = NavigationHistory()
    history.push(NavEntry(route="home", project_id=None))
    history.push(NavEntry(route="projects", project_id=None))
    history.push(NavEntry(route="project_overview", project_id="PRJ-1"))
    history.push(NavEntry(route="project_overview", project_id="PRJ-1"))

    assert len(history.entries) == 3
    assert history.current() is not None
    assert history.current().route == "project_overview"

    back = history.back()
    assert back is not None
    assert back.route == "projects"

    forward = history.forward()
    assert forward is not None
    assert forward.route == "project_overview"


def test_placeholder_navigation_preserves_open_project_identity() -> None:
    history = NavigationHistory()
    history.push(NavEntry(route="project_overview", project_id="PRJ-42"))
    history.push(NavEntry(route="review_run", project_id="PRJ-42"))
    history.push(NavEntry(route="master_engineering_data", project_id="PRJ-42"))

    assert history.current() is not None
    assert history.current().project_id == "PRJ-42"

    back = history.back()
    assert back is not None
    assert back.route == "review_run"
    assert back.project_id == "PRJ-42"

    back = history.back()
    assert back is not None
    assert back.route == "project_overview"
    assert back.project_id == "PRJ-42"


def test_home_and_projects_routes_are_meaningful_navigation_targets() -> None:
    history = NavigationHistory()
    history.push(NavEntry(route="home", project_id=None))
    history.push(NavEntry(route="projects", project_id=None))
    history.push(NavEntry(route="project_overview", project_id="PRJ-88"))

    assert history.entries[0].route == "home"
    assert history.entries[1].route == "projects"
    assert history.entries[2].project_id == "PRJ-88"


def test_navigation_state_roundtrip() -> None:
    history = NavigationHistory()
    history.push(NavEntry(route="home", project_id=None))
    history.push(NavEntry(route="projects", project_id=None))
    history.push(NavEntry(route="project_overview", project_id="PRJ-2", context={"tab": "summary"}))

    payload = serialize_navigation(history)
    restored = deserialize_navigation(payload)

    assert restored.cursor == history.cursor
    assert len(restored.entries) == 3
    assert restored.current() is not None
    assert restored.current().route == "project_overview"
    assert restored.current().context["tab"] == "summary"


def test_project_library_roundtrip_preserves_open_project_data() -> None:
    library = ProjectLibrary()
    p = library.create_project("Retention")
    p.set_draft_value("k", "v")
    p.commit_draft_key("k")

    payload = serialize_project_library(library)
    restored = deserialize_project_library(payload)

    loaded = restored.get_project(p.project_id)
    assert loaded.name == "Retention"
    assert loaded.saved_state["k"] == "v"


def test_draft_preservation_and_invalid_state_preservation_contract() -> None:
    library = ProjectLibrary()
    p = library.create_project("Draft Test")

    p.set_draft_value("valid_field", "kept")
    p.set_draft_value("invalid_field", "ABC")

    assert p.draft_status == "DIRTY_UNSAVED"
    assert p.draft_state["valid_field"] == "kept"
    assert p.draft_state["invalid_field"] == "ABC"

    # Simulate correcting only one field; unrelated field remains preserved.
    p.set_draft_value("invalid_field", "123")
    assert p.draft_state["valid_field"] == "kept"


def test_safe_action_wrapper_returns_user_readable_error() -> None:
    result, value = run_safe_action(lambda: 42)
    assert result.ok is True
    assert value == 42

    def _explode() -> int:
        raise RuntimeError("boom")

    result, value = run_safe_action(_explode)
    assert result.ok is False
    assert value is None
    assert "preserved" in result.user_message.lower()
    assert result.technical_details is not None


def test_last_successful_result_preservation_contract() -> None:
    library = ProjectLibrary()
    p = library.create_project("Run State")

    p.set_run_failed()
    assert p.run_status == "FAILED_NO_SUCCESS"
    assert p.last_successful_result_ref is None

    p.set_run_success("RUN-001")
    assert p.run_status == "SUCCESS"
    assert p.last_successful_result_ref == "RUN-001"

    p.set_run_failed()
    assert p.run_status == "FAILED_WITH_PREVIOUS_SUCCESS"
    assert p.last_successful_result_ref == "RUN-001"


def test_readiness_infrastructure_snapshot_contract() -> None:
    snapshot = default_readiness_snapshot()

    assert snapshot.blockers == ()
    assert snapshot.warnings == ()
    assert len(snapshot.unknown_or_not_calibrated) == 1
    assert len(snapshot.information) == 1
    assert len(snapshot.ready) == 1
    assert snapshot.defaults_in_use
