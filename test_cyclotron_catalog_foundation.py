from __future__ import annotations

from cyclotron_catalog import (
    FacilityCyclotronInstance,
    build_cyclotron_asset_from_instance,
    build_fleet_from_instances,
    calculate_eob_activity_from_calibrated_record,
    create_facility_cyclotron_instance,
    find_production_records,
    list_models_grouped_by_manufacturer,
    load_cyclotron_catalog,
    migration_from_legacy_model_counts,
    resolve_effective_cycle_map,
    resolve_effective_supported_radionuclides,
)
from cyclotron_production_windows import schedule_cyclotron_fleet_production_windows
from patient_radionuclide_demand import RadionuclideBatchDemand


def test_catalog_loads_with_expected_schema_version() -> None:
    catalog = load_cyclotron_catalog()
    assert catalog.schema_version == "1.1"
    assert len(catalog.models) >= 16


def test_catalog_groups_models_by_manufacturer() -> None:
    catalog = load_cyclotron_catalog()
    grouped = list_models_grouped_by_manufacturer(catalog)
    assert "GE HealthCare" in grouped
    assert "IBA" in grouped
    assert "Sumitomo Heavy Industries" in grouped


def test_model_lookup_returns_distinct_ge_pettrace_variants() -> None:
    catalog = load_cyclotron_catalog()
    ids = {"GE_PETTRACE_840", "GE_PETTRACE_860", "GE_PETTRACE_880", "GE_PETTRACE_890"}
    names = {catalog.by_id(model_id).model for model_id in ids}
    assert names == {"PETtrace 840", "PETtrace 860", "PETtrace 880", "PETtrace 890"}


def test_iba_models_are_distinct_catalog_records() -> None:
    catalog = load_cyclotron_catalog()
    ids = {"IBA_CYCLONE_KEY", "IBA_CYCLONE_KIUBE", "IBA_CYCLONE_IKON", "IBA_CYCLONE_30XP"}
    names = {catalog.by_id(model_id).model for model_id in ids}
    assert names == {"Cyclone KEY", "Cyclone KIUBE", "Cyclone IKON", "Cyclone 30XP"}


def test_legacy_models_are_selectable_for_installed_equipment_but_not_new_purchase() -> None:
    catalog = load_cyclotron_catalog()
    eclipse = catalog.by_id("SIEMENS_CTI_ECLIPSE_HP")
    rds = catalog.by_id("SIEMENS_CTI_RDS_111")
    assert eclipse.commercial_status == "legacy"
    assert rds.commercial_status == "legacy"
    assert eclipse.installed_equipment_selectable is True
    assert rds.installed_equipment_selectable is True
    assert eclipse.new_purchase_candidate is False
    assert rds.new_purchase_candidate is False


def test_field_level_provenance_is_present_for_seed_models() -> None:
    catalog = load_cyclotron_catalog()
    model = catalog.by_id("GE_PETTRACE_840")
    identity = model.field_provenance["identity"]
    assert identity.source
    assert identity.evidence_type == "manufacturer_specification"
    assert identity.calibration_status == "manufacturer_calibrated"


def test_activity_unit_normalization_ci_to_mbq_is_supported() -> None:
    catalog = load_cyclotron_catalog()
    record = find_production_records(catalog=catalog, catalog_model_id="IBA_CYCLONE_KIUBE", radionuclide="F-18")[0]
    assert record.reported_eob_activity == 38.0
    assert record.reported_eob_activity_unit == "Ci"
    assert record.normalized_eob_activity_mbq == 1_406_000.0


def test_unknown_values_remain_unknown_in_catalog() -> None:
    catalog = load_cyclotron_catalog()
    model = catalog.by_id("BEST_14P")
    assert "maximum_current_ua" not in model.field_provenance
    assert model.production_performance_records == ()
    assert model.production_cycle_minutes_by_radionuclide == {}
    assert model.production_calibration_status == "not_calibrated"


def test_facility_instance_creation_generates_stable_incrementing_ids() -> None:
    first = create_facility_cyclotron_instance(catalog_model_id="GE_PETTRACE_800", existing_instances=())
    second = create_facility_cyclotron_instance(catalog_model_id="GE_PETTRACE_800", existing_instances=(first,))
    assert first.instance_id == "CY-001"
    assert second.instance_id == "CY-002"


def test_facility_instance_serialization_roundtrip() -> None:
    original = FacilityCyclotronInstance(
        instance_id="CY-007",
        catalog_model_id="GE_PETTRACE_800",
        site_supported_radionuclide_override=("F-18",),
        site_production_cycle_minutes_override={"F-18": 42.0},
        site_operating_current_ua=105.0,
        site_max_eob_capacity_mbq_per_day=620_000.0,
    )
    restored = FacilityCyclotronInstance.from_dict(original.to_dict())
    assert restored == original


def test_site_specific_override_precedence_for_supported_radionuclides() -> None:
    catalog = load_cyclotron_catalog()
    model = catalog.by_id("GE_PETTRACE_800")
    instance = FacilityCyclotronInstance(
        instance_id="CY-001",
        catalog_model_id=model.catalog_model_id,
        site_supported_radionuclide_override=("F-18", "Ga-68"),
    )
    effective = resolve_effective_supported_radionuclides(instance, model)
    assert effective == ("F-18", "Ga-68")


def test_site_specific_override_precedence_for_cycle_map() -> None:
    catalog = load_cyclotron_catalog()
    model = catalog.by_id("GE_PETTRACE_800")
    instance = FacilityCyclotronInstance(
        instance_id="CY-001",
        catalog_model_id=model.catalog_model_id,
        site_production_cycle_minutes_override={"F-18": 44.0, "Ga-68": 40.0},
    )
    cycle_map = resolve_effective_cycle_map(instance, model)
    assert cycle_map["F-18"] == 44.0
    assert cycle_map["Ga-68"] == 40.0


def test_radionuclide_capability_lookup_for_pettrace_800() -> None:
    catalog = load_cyclotron_catalog()
    model = catalog.by_id("GE_PETTRACE_800")
    assert set(model.supported_radionuclides) == {"F-18", "Ga-68", "N-13", "C-11", "O-15"}


def test_production_performance_lookup_by_model_and_isotope() -> None:
    catalog = load_cyclotron_catalog()
    records = find_production_records(catalog=catalog, catalog_model_id="GE_PETTRACE_880", radionuclide="F-18")
    assert len(records) == 1
    assert records[0].source.startswith("Authoritative GE PETtrace")


def test_build_fleet_from_instances_uses_only_calibrated_capability_models() -> None:
    catalog = load_cyclotron_catalog()
    good = FacilityCyclotronInstance(instance_id="CY-001", catalog_model_id="GE_PETTRACE_880")
    bad = FacilityCyclotronInstance(instance_id="CY-002", catalog_model_id="BEST_14P")
    fleet, warnings = build_fleet_from_instances(catalog=catalog, instances=(good, bad))
    assert fleet is not None
    assert len(fleet.assets) == 1
    assert fleet.assets[0].cyclotron_id == "CY-001"
    assert len(warnings) == 1


def test_not_calibrated_behavior_when_catalog_has_no_cycles() -> None:
    catalog = load_cyclotron_catalog()
    instance = FacilityCyclotronInstance(instance_id="CY-001", catalog_model_id="BEST_14P")
    model = catalog.by_id(instance.catalog_model_id)
    asset = build_cyclotron_asset_from_instance(instance=instance, model=model)
    assert asset is None


def test_batch_production_can_consume_catalog_backed_instance_data() -> None:
    catalog = load_cyclotron_catalog()
    instance = FacilityCyclotronInstance(instance_id="CY-001", catalog_model_id="GE_PETTRACE_840")
    fleet, warnings = build_fleet_from_instances(catalog=catalog, instances=(instance,))
    assert fleet is not None
    assert warnings == ()

    batches = (
        RadionuclideBatchDemand(batch_id=1, radionuclide="F-18", patient_ids=("P1",), patient_count=1, total_prescribed_activity_mbq=370.0),
        RadionuclideBatchDemand(batch_id=2, radionuclide="F-18", patient_ids=("P2",), patient_count=1, total_prescribed_activity_mbq=185.0),
    )
    schedule = schedule_cyclotron_fleet_production_windows(batches, fleet)
    assert schedule.total_batches == 2
    assert schedule.all_batches_scheduled is True


def test_prevent_unconditional_use_of_calibration_point_without_explicit_modeling() -> None:
    catalog = load_cyclotron_catalog()
    record = find_production_records(catalog=catalog, catalog_model_id="GE_PETTRACE_880", radionuclide="F-18")[0]
    value, status = calculate_eob_activity_from_calibrated_record(
        record=record,
        beam_current_ua=100.0,
        irradiation_time_minutes=60.0,
        calibration_constant_k=None,
    )
    assert value is None
    assert status == "not_calibrated"


def test_returns_manufacturer_value_only_at_exact_calibration_point() -> None:
    catalog = load_cyclotron_catalog()
    record = find_production_records(catalog=catalog, catalog_model_id="GE_PETTRACE_860", radionuclide="F-18")[0]
    value, status = calculate_eob_activity_from_calibrated_record(
        record=record,
        beam_current_ua=100.0,
        irradiation_time_minutes=120.0,
        calibration_constant_k=None,
    )
    assert value == 403000.0
    assert status == "manufacturer_reported_calibration_point"


def test_modeled_relationship_is_explicit_when_calibration_constant_is_provided() -> None:
    catalog = load_cyclotron_catalog()
    record = find_production_records(catalog=catalog, catalog_model_id="GE_PETTRACE_880", radionuclide="F-18")[0]
    value, status = calculate_eob_activity_from_calibrated_record(
        record=record,
        beam_current_ua=100.0,
        irradiation_time_minutes=60.0,
        calibration_constant_k=1000.0,
    )
    assert value is not None
    assert status == "modeled"


def test_explicit_eob_capacity_field_is_separate_from_catalog_capability() -> None:
    instance = FacilityCyclotronInstance(
        instance_id="CY-001",
        catalog_model_id="GE_PETTRACE_800",
        site_max_eob_capacity_mbq_per_day=550_000.0,
    )
    assert instance.site_max_eob_capacity_mbq_per_day == 550_000.0


def test_legacy_production_block_keys_are_not_part_of_catalog_model_schema() -> None:
    catalog = load_cyclotron_catalog()
    model = catalog.by_id("GE_PETTRACE_800")
    assert "production_blocks" not in model.field_provenance


def test_migration_from_legacy_model_count_state_creates_instances() -> None:
    legacy_state = {
        "build3::production::model_count::PETTRACE_800": 1,
        "build3::production::model_count::COMPACT_F18_GA68": 2,
    }
    instances = migration_from_legacy_model_counts(legacy_state)
    assert len(instances) == 3
    assert instances[0].catalog_model_id == "GE_PETTRACE_800"


def test_customer_selectable_catalog_excludes_placeholder_classification_names() -> None:
    catalog = load_cyclotron_catalog()
    options = catalog.to_customer_model_options()
    labels = {label for _, label in options}
    assert all("COMPACT_F18_GA68" not in label for label in labels)
    assert all("RESEARCH_MULTI_ISOTOPE" not in label for label in labels)


def test_ge_differentiation_f18_calibration_points() -> None:
    catalog = load_cyclotron_catalog()
    expected = {
        "GE_PETTRACE_840": (60.0, 240000.0),
        "GE_PETTRACE_860": (100.0, 403000.0),
        "GE_PETTRACE_880": (130.0, 524000.0),
        "GE_PETTRACE_890": (160.0, 648000.0),
    }
    for model_id, (current, mbq) in expected.items():
        record = find_production_records(catalog=catalog, catalog_model_id=model_id, radionuclide="F-18")[0]
        assert record.beam_current_ua == current
        assert record.irradiation_time_minutes == 120.0
        assert record.normalized_eob_activity_mbq == mbq


def test_ge_model_selection_changes_normalized_record_values() -> None:
    catalog = load_cyclotron_catalog()
    low = find_production_records(catalog=catalog, catalog_model_id="GE_PETTRACE_840", radionuclide="F-18")[0]
    high = find_production_records(catalog=catalog, catalog_model_id="GE_PETTRACE_890", radionuclide="F-18")[0]
    assert low.normalized_eob_activity_mbq != high.normalized_eob_activity_mbq
    assert low.normalized_eob_activity_mbq == 240000.0
    assert high.normalized_eob_activity_mbq == 648000.0


def test_iba_key_core_specs_and_provenance() -> None:
    catalog = load_cyclotron_catalog()
    model = catalog.by_id("IBA_CYCLONE_KEY")
    assert model.field_provenance["proton_energy_mev"].value == 9.2
    assert model.field_provenance["maximum_beam_current_ua"].value == 100.0
    assert model.field_provenance["number_of_exits"].value == 1
    assert model.field_provenance["maximum_targets"].value == 3
    assert set(model.supported_radionuclides) == {"F-18", "N-13", "C-11"}
    f18 = find_production_records(catalog=catalog, catalog_model_id="IBA_CYCLONE_KEY", radionuclide="F-18")[0]
    assert f18.irradiation_time_minutes == 120.0
    assert f18.normalized_eob_activity_mbq == 111000.0
    assert f18.evidence_type == "manufacturer_performance_data"


def test_kiube_upgrade_levels_and_conversion_context() -> None:
    catalog = load_cyclotron_catalog()
    model = catalog.by_id("IBA_CYCLONE_KIUBE")
    assert model.field_provenance["proton_energy_mev"].value == 18.0
    assert model.field_provenance["supported_current_upgrade_levels_ua"].value == [100, 150, 180, 300]
    f18 = find_production_records(catalog=catalog, catalog_model_id="IBA_CYCLONE_KIUBE", radionuclide="F-18")[0]
    assert f18.reported_eob_activity == 38.0
    assert f18.reported_eob_activity_unit == "Ci"
    assert f18.normalized_eob_activity_mbq == 1406000.0
    assert f18.irradiation_time_minutes == 120.0


def test_cyclone_30xp_keeps_particles_separate() -> None:
    catalog = load_cyclotron_catalog()
    model = catalog.by_id("IBA_CYCLONE_30XP")
    assert model.field_provenance["proton_energy_min_mev"].value == 15.0
    assert model.field_provenance["proton_energy_max_mev"].value == 30.0
    assert model.field_provenance["proton_maximum_current_ua"].value == 400.0
    assert model.field_provenance["deuteron_energy_min_mev"].value == 8.0
    assert model.field_provenance["deuteron_energy_max_mev"].value == 15.0
    assert model.field_provenance["deuteron_maximum_current_ua"].value == 50.0
    assert model.field_provenance["alpha_energy_mev"].value == 30.0
    assert model.field_provenance["alpha_maximum_current_ua"].value == 50.0


def test_provenance_classes_differentiate_manufacturer_and_literature() -> None:
    catalog = load_cyclotron_catalog()
    ge = catalog.by_id("GE_PETTRACE_880")
    rds = catalog.by_id("SIEMENS_CTI_RDS_111")
    assert ge.field_provenance["proton_energy_mev"].evidence_type == "manufacturer_specification"
    assert rds.field_provenance["proton_energy_mev"].evidence_type == "technical_literature"
