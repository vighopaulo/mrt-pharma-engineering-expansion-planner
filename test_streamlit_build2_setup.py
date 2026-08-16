from __future__ import annotations

from streamlit.testing.v1 import AppTest

from ui_foundation import (
    NavEntry,
    NavigationHistory,
    ProjectLibrary,
    cyclotron_inventory_semantics,
    deserialize_project_library,
    is_mode_supply_selection_complete,
    serialize_navigation,
    serialize_project_library,
    validate_mode_supply_selection,
)


def _app() -> AppTest:
    return AppTest.from_file("app.py")


def _seed(
    *,
    route: str,
    mode: str = "UNSPECIFIED",
    supply: str = "UNSPECIFIED",
    draft_updates: dict[str, object] | None = None,
    saved_updates: dict[str, object] | None = None,
) -> tuple[AppTest, str]:
    library = ProjectLibrary()
    project = library.create_project("Build2")
    project.project_mode = mode
    project.supply_architecture = supply
    for key, value in (draft_updates or {}).items():
        project.draft_state[key] = value
    for key, value in (saved_updates or {}).items():
        project.saved_state[key] = value

    history = NavigationHistory(entries=[NavEntry(route=route, project_id=project.project_id)], cursor=0)
    at = _app()
    at.session_state["ui_project_library"] = serialize_project_library(library)
    at.session_state["ui_navigation"] = serialize_navigation(history)
    at.session_state["ui_current_route"] = route
    at.session_state["ui_current_project_id"] = project.project_id
    return at, project.project_id


def _all_text(at: AppTest) -> str:
    chunks: list[str] = []
    chunks.extend(node.value for node in at.title)
    chunks.extend(node.value for node in at.subheader)
    chunks.extend(node.value for node in at.caption)
    chunks.extend(node.value for node in at.info)
    chunks.extend(node.value for node in at.warning)
    chunks.extend(node.value for node in at.error)
    chunks.extend(node.value for node in at.success)
    chunks.extend(getattr(node, "value", "") for node in at.markdown)
    return "\n".join(chunks)


def _summary_records(at: AppTest) -> list[dict[str, object]]:
    if len(at.dataframe) == 0:
        return []
    return at.dataframe[0].value.to_dict("records")


def _summary_record(at: AppTest, resource: str) -> dict[str, object]:
    for record in _summary_records(at):
        if str(record.get("Resource")) == resource:
            return record
    raise AssertionError(f"Missing summary row for {resource}")


def _shell_text(at: AppTest) -> str:
    return "\n".join(getattr(node, "value", "") for node in at.markdown[:8])


def test_greenfield_on_site_is_allowed() -> None:
    issues = validate_mode_supply_selection("GREENFIELD", "ON_SITE_PRODUCTION")
    assert issues == ()
    assert is_mode_supply_selection_complete("GREENFIELD", "ON_SITE_PRODUCTION") is True


def test_greenfield_external_supply_is_allowed() -> None:
    issues = validate_mode_supply_selection("GREENFIELD", "EXTERNAL_SUPPLY_HUB_SPOKE")
    assert issues == ()
    assert is_mode_supply_selection_complete("GREENFIELD", "EXTERNAL_SUPPLY_HUB_SPOKE") is True


def test_retrofit_on_site_is_allowed() -> None:
    issues = validate_mode_supply_selection("EXISTING_FACILITY_RETROFIT", "ON_SITE_PRODUCTION")
    assert issues == ()
    assert is_mode_supply_selection_complete("EXISTING_FACILITY_RETROFIT", "ON_SITE_PRODUCTION") is True


def test_retrofit_external_supply_is_allowed() -> None:
    issues = validate_mode_supply_selection("EXISTING_FACILITY_RETROFIT", "EXTERNAL_SUPPLY_HUB_SPOKE")
    assert issues == ()
    assert is_mode_supply_selection_complete("EXISTING_FACILITY_RETROFIT", "EXTERNAL_SUPPLY_HUB_SPOKE") is True


def test_retrofit_external_supply_does_not_force_cyclotron_zero() -> None:
    at, _ = _seed(
        route="facility_resources",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="EXTERNAL_SUPPLY_HUB_SPOKE",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "EXTERNAL_SUPPLY_HUB_SPOKE",
            "facility_resource::cyclotron_units::status": "KNOWN",
            "facility_resource::cyclotron_units::existing": "2",
        },
    )
    at.run(timeout=10)
    text = _all_text(at)
    assert "2 on-site cyclotrons currently exist." in text


def test_shared_header_displays_mrt_pharma_digital_twin_branding() -> None:
    at = _app()
    at.run()

    shell_text = _shell_text(at)
    assert "<span class='brand-word-mrt'>MRT</span><span class='brand-word-pharma'>Pharma</span>" in shell_text
    assert "Digital Twin" in shell_text
    assert "MRTWay" not in shell_text
    assert "Engineering Expansion Planner" not in shell_text


def test_known_zero_vs_unknown_cyclotron_inventory_remains_distinct() -> None:
    known_zero = cyclotron_inventory_semantics(status="KNOWN", quantity_text="0")
    unknown = cyclotron_inventory_semantics(status="UNKNOWN", quantity_text="")
    assert known_zero != unknown
    assert "confirmed" in known_zero.lower()
    assert "not been established" in unknown.lower()


def test_existing_cyclotron_count_can_be_positive_under_external_supply() -> None:
    at, _ = _seed(
        route="facility_resources",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="EXTERNAL_SUPPLY_HUB_SPOKE",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "EXTERNAL_SUPPLY_HUB_SPOKE",
            "facility_resource::cyclotron_units::status": "KNOWN",
            "facility_resource::cyclotron_units::existing": "3",
        },
    )
    at.run()
    text = _all_text(at)
    assert "3 on-site cyclotrons currently exist." in text
    assert "Project mode is required" not in text


def test_greenfield_baseline_does_not_fabricate_inherited_assets() -> None:
    at, _ = _seed(
        route="facility_resources",
        mode="GREENFIELD",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "GREENFIELD",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
        },
    )
    at.run()
    text = _all_text(at)
    assert "new facility" in text.lower()
    assert "inheritance does not apply" in text.lower()
    assert "Retrofit Inheritance Summary" not in text


def test_retrofit_resource_values_persist_across_navigation_state() -> None:
    library = ProjectLibrary()
    project = library.create_project("Persist")
    project.project_mode = "EXISTING_FACILITY_RETROFIT"
    project.supply_architecture = "EXTERNAL_SUPPLY_HUB_SPOKE"
    project.set_draft_value("facility_resource::cyclotron_units::status", "KNOWN")
    project.set_draft_value("facility_resource::cyclotron_units::existing", "0")

    before = dict(project.draft_state)
    history = NavigationHistory(entries=[NavEntry(route="facility_resources", project_id=project.project_id)], cursor=0)
    history.push(NavEntry(route="project_definition", project_id=project.project_id))
    history.push(NavEntry(route="facility_resources", project_id=project.project_id))
    after = dict(project.draft_state)
    assert before == after


def test_invalid_numeric_input_does_not_crash() -> None:
    at, _ = _seed(
        route="facility_resources",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
            "facility_resource::cyclotron_units::status": "KNOWN",
            "facility_resource::cyclotron_units::existing": "ABC",
        },
    )
    at.run()
    assert [node.value for node in at.title] == ["Facility & Existing Resources"]
    assert any("whole number" in node.value.lower() for node in at.error)


def test_negative_resource_quantity_is_rejected() -> None:
    at, _ = _seed(
        route="facility_resources",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
            "facility_resource::cyclotron_units::status": "KNOWN",
            "facility_resource::cyclotron_units::existing": "-1",
        },
    )
    at.run()
    assert any("cannot be negative" in node.value.lower() for node in at.error)


def test_known_status_with_blank_quantity_blocks_continuation() -> None:
    at, _ = _seed(
        route="facility_resources",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
            "facility_resource::cyclotron_units::status": "KNOWN",
            "facility_resource::cyclotron_units::existing": "",
        },
    )
    at.run()
    assert any("required when status is known" in node.value.lower() for node in at.error)


def test_unknown_status_permits_no_numeric_quantity() -> None:
    at, _ = _seed(
        route="facility_resources",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
            "facility_resource::cyclotron_units::status": "UNKNOWN",
            "facility_resource::cyclotron_units::existing": "",
        },
    )
    at.run()
    cyclotron_errors = [node.value for node in at.error if "Cyclotron units" in node.value]
    assert cyclotron_errors == []


def test_retrofit_existing_mrt_uses_numeric_fields_without_unknown_selector() -> None:
    at, _ = _seed(
        route="facility_resources",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
        },
    )
    at.run()

    selectbox_keys = [selectbox.key for selectbox in at.selectbox]
    assert not any("mrt_endpoints" in key for key in selectbox_keys)
    assert not any("mrt_carriers" in key for key in selectbox_keys)
    assert any(text_input.label == "Existing MRT endpoints" for text_input in at.text_input)
    assert any(text_input.label == "Existing MRT carriers" for text_input in at.text_input)


def test_known_existing_resource_defaults_retainable_to_existing_without_forcing_extra_input() -> None:
    at, project_id = _seed(
        route="facility_resources",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
            "facility_resource::scanner_resources::status": "KNOWN",
            "facility_resource::scanner_resources::existing": "3",
        },
    )
    at.run()

    library = deserialize_project_library(at.session_state["ui_project_library"])
    project = library.get_project(project_id)
    assert project.draft_state["facility_resource::scanner_resources::usable"] == "3"
    assert project.draft_state["facility_resource::scanner_resources::usable_override"] is False
    assert all(text_input.label != "Retainable / operational quantity" for text_input in at.text_input)
    assert any(checkbox.label == "Adjust retainable quantity" for checkbox in at.checkbox)

    scanner_row = _summary_record(at, "PET/SPECT scanner resources")
    assert scanner_row["Retainable / Operational"] == "Auto (3)"
    assert scanner_row["Inheritance Status"] == "Retained"


def test_adjust_control_exposes_retainable_field_and_persists_override() -> None:
    at, project_id = _seed(
        route="facility_resources",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
            "facility_resource::scanner_resources::status": "KNOWN",
            "facility_resource::scanner_resources::existing": "3",
        },
    )
    at.run()

    at.checkbox(key=f"facility_retainable_override_scanner_resources_{project_id}").set_value(True)
    at.run()
    assert any(text_input.label == "Retainable / operational quantity" for text_input in at.text_input)

    at.text_input(key=f"facility_retainable_scanner_resources_{project_id}").set_value("2")
    at.run()

    library = deserialize_project_library(at.session_state["ui_project_library"])
    project = library.get_project(project_id)
    assert project.draft_state["facility_resource::scanner_resources::usable"] == "2"
    assert project.draft_state["facility_resource::scanner_resources::usable_override"] is True

    scanner_row = _summary_record(at, "PET/SPECT scanner resources")
    assert scanner_row["Retainable / Operational"] == "Adjusted (2)"
    assert scanner_row["Inheritance Status"] == "Partially Retained"


def test_none_status_hides_unnecessary_retainable_entry() -> None:
    at, project_id = _seed(
        route="facility_resources",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
            "facility_resource::scanner_resources::status": "NONE",
        },
    )
    at.run()

    library = deserialize_project_library(at.session_state["ui_project_library"])
    project = library.get_project(project_id)
    assert project.draft_state["facility_resource::scanner_resources::usable"] == "0"
    assert all(text_input.label != "Retainable / operational quantity" for text_input in at.text_input)
    assert all(checkbox.label != "Adjust retainable quantity" for checkbox in at.checkbox)


def test_unknown_status_hides_retainable_entry_and_preserves_unknown_semantics() -> None:
    at, project_id = _seed(
        route="facility_resources",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
            "facility_resource::scanner_resources::status": "UNKNOWN",
        },
    )
    at.run()

    library = deserialize_project_library(at.session_state["ui_project_library"])
    project = library.get_project(project_id)
    assert project.draft_state.get("facility_resource::scanner_resources::usable_override", False) is False
    assert all(text_input.label != "Retainable / operational quantity" for text_input in at.text_input)
    assert all(checkbox.label != "Adjust retainable quantity" for checkbox in at.checkbox)

    scanner_row = _summary_record(at, "PET/SPECT scanner resources")
    assert scanner_row["Inventory Status"] == "Unknown"
    assert scanner_row["Inheritance Status"] == "Inventory Unknown"


def test_retrofit_mrt_zero_maps_to_known_zero_and_confirmed_none() -> None:
    at, project_id = _seed(
        route="facility_resources",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
            "facility_resource::mrt_endpoints::existing": "0",
            "facility_resource::mrt_carriers::existing": "0",
        },
    )
    at.run()

    library = deserialize_project_library(at.session_state["ui_project_library"])
    project = library.get_project(project_id)
    assert project.draft_state["facility_resource::mrt_endpoints::status"] == "KNOWN"
    assert project.draft_state["facility_resource::mrt_endpoints::existing"] == "0"
    assert project.draft_state["facility_resource::mrt_endpoints::usable"] == "0"
    assert project.draft_state["facility_resource::mrt_carriers::status"] == "KNOWN"
    assert project.draft_state["facility_resource::mrt_carriers::existing"] == "0"
    assert project.draft_state["facility_resource::mrt_carriers::usable"] == "0"

    endpoint_row = _summary_record(at, "MRT endpoints already installed")
    carrier_row = _summary_record(at, "MRT carriers already installed")
    assert endpoint_row["Inventory Status"] == "Known"
    assert endpoint_row["Inheritance Status"] == "Confirmed None"
    assert endpoint_row["Retainable / Operational"] == "0"
    assert carrier_row["Inventory Status"] == "Known"
    assert carrier_row["Inheritance Status"] == "Confirmed None"
    assert carrier_row["Retainable / Operational"] == "0"


def test_retrofit_positive_mrt_counts_persist_and_allow_partial_retention() -> None:
    at, project_id = _seed(
        route="facility_resources",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="EXTERNAL_SUPPLY_HUB_SPOKE",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "EXTERNAL_SUPPLY_HUB_SPOKE",
            "facility_resource::mrt_endpoints::existing": "2",
            "facility_resource::mrt_endpoints::usable": "1",
            "facility_resource::mrt_carriers::existing": "2",
            "facility_resource::mrt_carriers::usable": "2",
        },
    )
    at.run()

    library = deserialize_project_library(at.session_state["ui_project_library"])
    project = library.get_project(project_id)
    assert project.draft_state["facility_resource::mrt_endpoints::existing"] == "2"
    assert project.draft_state["facility_resource::mrt_endpoints::usable"] == "1"
    assert project.draft_state["facility_resource::mrt_carriers::existing"] == "2"
    assert project.draft_state["facility_resource::mrt_carriers::usable"] == "2"

    endpoint_row = _summary_record(at, "MRT endpoints already installed")
    carrier_row = _summary_record(at, "MRT carriers already installed")
    assert endpoint_row["Retainable / Operational"] == "Adjusted (1)"
    assert endpoint_row["Inheritance Status"] == "Partially Retained"
    assert carrier_row["Retainable / Operational"] == "Auto (2)"
    assert carrier_row["Inheritance Status"] == "Retained"


def test_existing_mrt_defaults_retainable_to_existing_without_forcing_extra_input() -> None:
    at, project_id = _seed(
        route="facility_resources",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="EXTERNAL_SUPPLY_HUB_SPOKE",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "EXTERNAL_SUPPLY_HUB_SPOKE",
            "facility_resource::mrt_endpoints::existing": "2",
        },
    )
    at.run()

    library = deserialize_project_library(at.session_state["ui_project_library"])
    project = library.get_project(project_id)
    assert project.draft_state["facility_resource::mrt_endpoints::usable"] == "2"
    assert project.draft_state["facility_resource::mrt_endpoints::usable_override"] is False
    assert all(text_input.label != "Retainable / operational quantity" for text_input in at.text_input)

    endpoint_row = _summary_record(at, "MRT endpoints already installed")
    assert endpoint_row["Retainable / Operational"] == "Auto (2)"
    assert endpoint_row["Inheritance Status"] == "Retained"


def test_retrofit_mrt_retainable_cannot_exceed_existing() -> None:
    at, _ = _seed(
        route="facility_resources",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
            "facility_resource::mrt_endpoints::existing": "2",
            "facility_resource::mrt_endpoints::usable": "3",
        },
    )
    at.run()
    assert any("retainable quantity cannot exceed existing quantity" in node.value.lower() for node in at.error)


def test_retrofit_mrt_invalid_counts_are_rejected_without_crash() -> None:
    at, _ = _seed(
        route="facility_resources",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
            "facility_resource::mrt_endpoints::existing": "abc",
            "facility_resource::mrt_carriers::existing": "1.7",
        },
    )
    at.run()
    assert [node.value for node in at.title] == ["Facility & Existing Resources"]
    text = "\n".join(node.value.lower() for node in at.error)
    assert "whole number" in text or "required" in text


def test_retrofit_mrt_negative_count_is_rejected() -> None:
    at, _ = _seed(
        route="facility_resources",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="EXTERNAL_SUPPLY_HUB_SPOKE",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "EXTERNAL_SUPPLY_HUB_SPOKE",
            "facility_resource::mrt_endpoints::existing": "-1",
        },
    )
    at.run()
    assert any("cannot be negative" in node.value.lower() for node in at.error)


def test_retrofit_external_supply_with_mrt_counts_has_no_inventory_unknown_for_mrt_rows() -> None:
    at, _ = _seed(
        route="facility_resources",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="EXTERNAL_SUPPLY_HUB_SPOKE",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "EXTERNAL_SUPPLY_HUB_SPOKE",
            "facility_resource::mrt_endpoints::existing": "2",
            "facility_resource::mrt_endpoints::usable": "1",
            "facility_resource::mrt_carriers::existing": "0",
        },
    )
    at.run()
    endpoint_row = _summary_record(at, "MRT endpoints already installed")
    carrier_row = _summary_record(at, "MRT carriers already installed")
    assert endpoint_row["Inventory Status"] == "Known"
    assert carrier_row["Inventory Status"] == "Known"
    assert endpoint_row["Inheritance Status"] != "Inventory Unknown"
    assert carrier_row["Inheritance Status"] != "Inventory Unknown"


def test_retrofit_navigation_away_and_back_preserves_mrt_counts() -> None:
    at, project_id = _seed(
        route="facility_resources",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
            "facility_resource::mrt_endpoints::existing": "2",
            "facility_resource::mrt_endpoints::usable": "1",
            "facility_resource::mrt_carriers::existing": "0",
        },
    )
    at.run()
    for button in at.button:
        if getattr(button, "label", None) == "Home":
            button.click().run()
            break
    for button in at.button:
        if getattr(button, "label", None) == "Back":
            button.click().run()
            break

    library = deserialize_project_library(at.session_state["ui_project_library"])
    project = library.get_project(project_id)
    assert at.session_state["ui_current_route"] == "facility_resources"
    assert project.draft_state["facility_resource::mrt_endpoints::existing"] == "2"
    assert project.draft_state["facility_resource::mrt_endpoints::usable"] == "1"
    assert project.draft_state["facility_resource::mrt_endpoints::usable_override"] is True
    assert project.draft_state["facility_resource::mrt_carriers::existing"] == "0"


def test_one_invalid_field_does_not_erase_valid_fields() -> None:
    at, project_id = _seed(
        route="facility_resources",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
            "facility_resource::cyclotron_units::status": "KNOWN",
            "facility_resource::cyclotron_units::existing": "ABC",
            "facility_resource::scanner_resources::status": "KNOWN",
            "facility_resource::scanner_resources::existing": "4",
        },
    )
    at.run()
    library = deserialize_project_library(at.session_state["ui_project_library"])
    project = library.get_project(project_id)
    assert project.draft_state["facility_resource::scanner_resources::existing"] == "4"


def test_project_overview_reflects_project_mode() -> None:
    at, _ = _seed(
        route="project_overview",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="EXTERNAL_SUPPLY_HUB_SPOKE",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "EXTERNAL_SUPPLY_HUB_SPOKE",
        },
        saved_updates={"facility_baseline_complete": False},
    )
    at.run()
    text = _all_text(at)
    assert "Retrofit / Existing Facility Expansion" in text


def test_project_overview_reflects_supply_architecture() -> None:
    at, _ = _seed(
        route="project_overview",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="EXTERNAL_SUPPLY_HUB_SPOKE",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "EXTERNAL_SUPPLY_HUB_SPOKE",
        },
        saved_updates={"facility_baseline_complete": True},
    )
    at.run()
    text = _all_text(at)
    assert "External Supply / Hub-and-Spoke" in text


def test_navigation_controls_still_available() -> None:
    at, _ = _seed(
        route="project_definition",
        mode="GREENFIELD",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "GREENFIELD",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
        },
    )
    at.run()
    labels = [getattr(button, "label", None) for button in at.button]
    assert labels[:4] == ["Home", "Back", "Forward", "Projects"]


def test_project_definition_progresses_mode_then_supply_and_allows_edit() -> None:
    at, project_id = _seed(
        route="project_definition",
        mode="UNSPECIFIED",
        supply="UNSPECIFIED",
    )
    at.run()

    assert [text.label for text in at.text_input] == []
    assert any(getattr(button, "label", None) == "Select Greenfield" for button in at.button)
    assert any("Project Setup" in getattr(text, "value", "") for text in at.markdown)

    for button in at.button:
        if getattr(button, "label", None) == "Select Retrofit":
            button.click().run()
            break

    assert any(getattr(button, "label", None) == "Select On-site Production" for button in at.button)
    assert any(getattr(button, "label", None) == "Select External Supply / Hub-and-Spoke" for button in at.button)
    assert "Retrofit / Existing Facility Expansion" in _all_text(at)

    for button in at.button:
        if getattr(button, "label", None) == "Select External Supply / Hub-and-Spoke":
            button.click().run()
            break

    assert [node.value for node in at.title] == ["Project Definition / Project Mode"]
    assert "Retrofit / Existing Facility Expansion + External Supply / Hub-and-Spoke" in _all_text(at)
    assert any(getattr(button, "label", None) == "Continue to Facility & Existing Resources" for button in at.button)

    at.button(key=f"definition_summary_edit_mode_{project_id}").click().run()
    assert any(getattr(button, "label", None) == "Select Retrofit" for button in at.button)


def test_reselecting_same_project_mode_does_not_add_duplicate_messages() -> None:
    at, project_id = _seed(
        route="project_definition",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="UNSPECIFIED",
    )
    at.run()

    at.button(key=f"definition_summary_edit_mode_{project_id}").click().run()
    at.button(key=f"set_mode_retrofit_{project_id}").click().run()

    assert at.session_state["ui_current_route"] == "project_definition"
    assert len(at.success) == 0
    assert at.session_state["ui_last_error"] is None


def test_greenfield_facility_page_is_concise_by_default() -> None:
    at, _ = _seed(
        route="facility_resources",
        mode="GREENFIELD",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "GREENFIELD",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
        },
    )
    at.run()
    text = _all_text(at)
    assert "This project is being modeled as a new facility" in text
    assert "No inherited resources are assumed" in text
    assert "Retrofit Inheritance Summary" not in text
    assert "Inventory status" not in text
    assert "Existing quantity" not in text
    assert "Adjust retainable quantity" not in text
    assert len(at.selectbox) == 0
    assert len(at.text_input) == 0


def test_switching_retrofit_to_greenfield_hides_retrofit_resource_form_without_losing_draft() -> None:
    at, project_id = _seed(
        route="project_definition",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
            "facility_resource::mrt_endpoints::existing": "2",
            "facility_resource::mrt_endpoints::usable": "1",
            "facility_resource::mrt_endpoints::usable_override": True,
        },
    )
    at.run()

    at.button(key=f"definition_summary_edit_mode_{project_id}").click().run()
    at.button(key=f"set_mode_greenfield_{project_id}").click().run()
    at.button(key=f"definition_summary_next_{project_id}").click().run()

    greenfield_text = _all_text(at)
    assert "Existing MRT" not in greenfield_text
    assert "Adjust retainable quantity" not in greenfield_text

    for button in at.button:
        if getattr(button, "label", None) == "Back":
            button.click().run()
            break

    at.button(key=f"definition_summary_edit_mode_{project_id}").click().run()
    at.button(key=f"set_mode_retrofit_{project_id}").click().run()
    at.button(key=f"definition_summary_next_{project_id}").click().run()

    retrofit_text = _all_text(at)
    assert "Existing MRT" in retrofit_text
    library = deserialize_project_library(at.session_state["ui_project_library"])
    project = library.get_project(project_id)
    assert project.draft_state["facility_resource::mrt_endpoints::existing"] == "2"
    assert project.draft_state["facility_resource::mrt_endpoints::usable"] == "1"


def test_project_overview_is_customer_facing_and_human_readable() -> None:
    at, project_id = _seed(
        route="project_overview",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="EXTERNAL_SUPPLY_HUB_SPOKE",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "EXTERNAL_SUPPLY_HUB_SPOKE",
        },
        saved_updates={"facility_baseline_complete": False},
    )
    at.run()
    text = _all_text(at)

    library = deserialize_project_library(at.session_state["ui_project_library"])
    project = library.get_project(project_id)

    assert "Field-State Semantics" not in text
    assert "Mark Latest Attempt Failed" not in text
    assert "Not run yet" in text
    assert project.updated_at_iso not in text
    assert "T" not in text.split("Last Modified")[-1]


def test_project_identity_preserved_on_build2_pages() -> None:
    at, project_id = _seed(
        route="project_definition",
        mode="GREENFIELD",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "GREENFIELD",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
        },
    )
    at.run()
    assert at.session_state["ui_current_project_id"] == project_id


def test_home_create_project_routes_to_overview_with_single_project_and_build2_defaults() -> None:
    at = _app()
    at.session_state["ui_last_error"] = "stale technical error"
    at.session_state["ui_status_messages"] = [{"level": "error", "message": "stale preserved-state banner"}]
    at.run(timeout=10)

    at.text_input(key="home_create_name_input").set_value("Build 2 Test")
    at.button(key="home_create_project").click()
    at.run(timeout=10)

    assert [node.value for node in at.title] == ["Project Overview"]
    assert at.session_state["ui_current_route"] == "project_overview"

    library = deserialize_project_library(at.session_state["ui_project_library"])
    assert len(library.projects) == 1

    current_project_id = at.session_state["ui_current_project_id"]
    assert current_project_id in library.projects
    project = library.get_project(current_project_id)

    assert project.project_mode == "UNSPECIFIED"
    assert project.supply_architecture == "UNSPECIFIED"
    assert isinstance(project.saved_state, dict)
    assert isinstance(project.draft_state, dict)

    all_errors = [node.value for node in at.error]
    assert (
        "The requested action could not be completed. Your project has been preserved." not in "\n".join(all_errors)
    )
    assert at.session_state["ui_last_error"] is None
    assert all(message.get("level") != "error" for message in at.session_state["ui_status_messages"])


def test_single_safe_error_banner_for_one_controlled_failure_and_state_preservation() -> None:
    at, project_id = _seed(
        route="project_overview",
        mode="GREENFIELD",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "INVALID_MODE",
        },
    )

    seeded_library = deserialize_project_library(at.session_state["ui_project_library"])
    seeded_project = seeded_library.get_project(project_id)
    seeded_project.last_successful_result_ref = "RUN-001"
    seeded_project.run_status = "SUCCESS"
    at.session_state["ui_project_library"] = serialize_project_library(seeded_library)

    at.run(timeout=10)

    primary_error = "The requested action could not be completed. Your project has been preserved."
    error_matches = [node.value for node in at.error if primary_error in node.value]
    assert len(error_matches) == 1

    labels = [getattr(button, "label", None) for button in at.button]
    assert labels[:4] == ["Home", "Back", "Forward", "Projects"]
    assert "Technical Details" in [expander.label for expander in at.expander]

    post_library = deserialize_project_library(at.session_state["ui_project_library"])
    assert len(post_library.projects) == 1
    post_project = post_library.get_project(project_id)
    assert post_project.last_successful_result_ref == "RUN-001"
    assert post_project.run_status == "SUCCESS"


def test_build3_pages_6_to_9_are_active_and_page_10_remains_placeholder() -> None:
    for route, expected_title in [
        ("demand_workflow_radionuclides", "Demand & Clinical Workflow"),
        ("production_cyclotron_external_supply", "Production / Cyclotron / External Supply"),
        ("geometry_floor_transport", "Spatial / Facility Engineering / Transport"),
        ("mrt_infrastructure", "MRT Infrastructure"),
    ]:
        at, _ = _seed(
            route=route,
            mode="GREENFIELD",
            supply="ON_SITE_PRODUCTION",
            draft_updates={
                "project_mode_selection": "GREENFIELD",
                "supply_architecture_selection": "ON_SITE_PRODUCTION",
            },
        )
        at.run()
        text = _all_text(at)
        assert [node.value for node in at.title] == [expected_title]
        assert "Build 1 placeholder" not in text

    at, _ = _seed(
        route="economics_assumptions",
        mode="GREENFIELD",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "GREENFIELD",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
        },
    )
    at.run()
    assert [node.value for node in at.title] == ["Economics & Assumptions"]
    assert "Build 1 placeholder" in _all_text(at)


def test_build3_demand_uses_generated_mix_without_patient_isotope_picker() -> None:
    at, _ = _seed(
        route="demand_workflow_radionuclides",
        mode="GREENFIELD",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "GREENFIELD",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
            "build3::production::active_radionuclides": ("F-18", "Ga-68"),
        },
    )
    at.run()
    text = _all_text(at).lower()
    assert "generated clinical demand mix" in text
    assert "patient radionuclide assignment" in text
    labels = [multiselect.label.lower() for multiselect in at.multiselect]
    assert all("patient" not in label for label in labels)


def test_build3_production_on_site_shows_fleet_model_controls() -> None:
    at, _ = _seed(
        route="production_cyclotron_external_supply",
        mode="GREENFIELD",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "GREENFIELD",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
            "build3::production::model_count::PETTRACE_800": 1,
        },
    )
    at.run()
    text = _all_text(at)
    assert "On-site Cyclotron Fleet" in text
    assert any(selectbox.label == "Select manufacturer" for selectbox in at.selectbox)
    assert any(selectbox.label == "Select model" for selectbox in at.selectbox)
    assert any(getattr(button, "label", None) == "Add Cyclotron" for button in at.button)
    assert "Configured facility cyclotrons" in text
    assert any(multiselect.label == "Radionuclides active for this project" for multiselect in at.multiselect)
    assert "Airport-to-hospital transfer time (minutes)" not in [node.label for node in at.text_input]


def test_build3_production_external_supply_shows_source_transport_controls() -> None:
    at, _ = _seed(
        route="production_cyclotron_external_supply",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="EXTERNAL_SUPPLY_HUB_SPOKE",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "EXTERNAL_SUPPLY_HUB_SPOKE",
            "facility_resource::cyclotron_units::status": "KNOWN",
            "facility_resource::cyclotron_units::existing": "2",
        },
    )
    at.run()
    labels = [node.label for node in at.text_input]
    text = _all_text(at)
    assert "External Supply / Hub-and-Spoke" in text
    assert "Airport-to-hospital transfer time (minutes)" in labels
    assert not any(selectbox.label == "Select manufacturer" for selectbox in at.selectbox)
    assert not any(getattr(button, "label", None) == "Add Cyclotron" for button in at.button)
    assert "preserved: KNOWN (2)" in text


def test_build3_mrt_page_reflects_greenfield_vs_retrofit_context() -> None:
    retrofit, _ = _seed(
        route="mrt_infrastructure",
        mode="EXISTING_FACILITY_RETROFIT",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "EXISTING_FACILITY_RETROFIT",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
            "facility_resource::mrt_endpoints::usable": "3",
            "facility_resource::mrt_carriers::usable": "2",
        },
    )
    retrofit.run()
    retrofit_text = _all_text(retrofit)
    assert "Inherited MRT endpoints (operational)" in retrofit_text
    assert "Inherited MRT carriers (operational)" in retrofit_text
    assert ": 3" in retrofit_text
    assert ": 2" in retrofit_text

    greenfield, _ = _seed(
        route="mrt_infrastructure",
        mode="GREENFIELD",
        supply="ON_SITE_PRODUCTION",
        draft_updates={
            "project_mode_selection": "GREENFIELD",
            "supply_architecture_selection": "ON_SITE_PRODUCTION",
        },
    )
    greenfield.run()
    greenfield_text = _all_text(greenfield)
    assert "Greenfield: configure planned MRT infrastructure only" in greenfield_text
