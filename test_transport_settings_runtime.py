"""KIRO Super-Build 2 tests -- transport settings contract + family/subtype
ON/OFF + parent-child inheritance + serialization (Sec 6-7, 43-46).
"""
from __future__ import annotations

import pytest

from transport_settings_authority import (
    TransportSettings, CANONICAL_TRANSPORT_FAMILIES, FAMILY_SUBTYPES, SUBTYPE_PARENT,
    default_transport_settings, only_families, all_except_families, with_overrides,
)


# --- canonical taxonomy (Sec 5) -------------------------------------------

def test_exactly_five_canonical_families():
    assert CANONICAL_TRANSPORT_FAMILIES == ("MANUAL", "PTS", "RTHS", "AGV_AMR", "MRT")


def test_pts_has_two_subtypes():
    assert FAMILY_SUBTYPES["PTS"] == ("PTS_CONVENTIONAL", "PTS_NUCLEAR_QUALIFIED")


def test_agv_has_light_and_heavy_subtypes():
    assert FAMILY_SUBTYPES["AGV_AMR"] == ("AGV_AMR_LIGHT_CLINICAL", "AGV_AMR_HEAVY_LOGISTICS")


def test_manual_has_no_subtypes():
    assert FAMILY_SUBTYPES["MANUAL"] == ()


def test_every_subtype_has_a_parent_family():
    for sub, parent in SUBTYPE_PARENT.items():
        assert parent in CANONICAL_TRANSPORT_FAMILIES


# --- default (Sec 46) ------------------------------------------------------

def test_default_all_families_on():
    s = default_transport_settings()
    for fam in CANONICAL_TRANSPORT_FAMILIES:
        assert s.family_enabled(fam)


def test_default_all_subtypes_effectively_on():
    s = default_transport_settings()
    for sub in SUBTYPE_PARENT:
        assert s.subtype_effectively_enabled(sub)


def test_default_qualification_absent():
    s = default_transport_settings()
    assert s.radiopharm_qualification_supplied is False
    assert s.pts_sensitive_specimen_validated is False


# --- family ON/OFF (Sec 6, 43) --------------------------------------------

@pytest.mark.parametrize("fam", ["MANUAL", "PTS", "RTHS", "AGV_AMR", "MRT"])
def test_family_can_be_individually_disabled(fam):
    s = all_except_families(fam)
    assert not s.family_enabled(fam)
    for other in CANONICAL_TRANSPORT_FAMILIES:
        if other != fam:
            assert s.family_enabled(other)


@pytest.mark.parametrize("fam", ["MANUAL", "PTS", "RTHS", "AGV_AMR", "MRT"])
def test_only_that_family_enabled(fam):
    s = only_families(fam)
    assert s.family_enabled(fam)
    assert s.effectively_enabled_families() == (fam,)


# --- parent/child inheritance (Sec 7) -------------------------------------

def test_parent_off_forces_pts_children_off():
    s = TransportSettings(pts_enabled=False)  # both PTS subtypes own-flag True
    assert not s.subtype_effectively_enabled("PTS_CONVENTIONAL")
    assert not s.subtype_effectively_enabled("PTS_NUCLEAR_QUALIFIED")


def test_parent_off_forces_agv_children_off():
    s = TransportSettings(agv_amr_enabled=False)
    assert not s.subtype_effectively_enabled("AGV_AMR_LIGHT_CLINICAL")
    assert not s.subtype_effectively_enabled("AGV_AMR_HEAVY_LOGISTICS")


def test_child_cannot_override_disabled_parent():
    # child own-flag ON but parent OFF -> effectively OFF
    s = TransportSettings(pts_enabled=False, pts_conventional_enabled=True, pts_nuclear_qualified_enabled=True)
    assert not s.subtype_effectively_enabled("PTS_CONVENTIONAL")
    assert not s.subtype_effectively_enabled("PTS_NUCLEAR_QUALIFIED")


def test_child_off_with_parent_on():
    s = TransportSettings(pts_enabled=True, pts_nuclear_qualified_enabled=False)
    assert s.subtype_effectively_enabled("PTS_CONVENTIONAL")
    assert not s.subtype_effectively_enabled("PTS_NUCLEAR_QUALIFIED")


def test_effectively_enabled_families_excludes_family_with_all_children_off():
    s = TransportSettings(pts_conventional_enabled=False, pts_nuclear_qualified_enabled=False)
    # PTS family flag still True, but no effective subtype -> not effectively active
    assert "PTS" not in s.effectively_enabled_families()


def test_effectively_enabled_subtypes_reflects_inheritance():
    s = TransportSettings(agv_amr_enabled=False, mrt_enabled=False)
    subs = s.effectively_enabled_subtypes()
    assert "AGV_AMR_LIGHT_CLINICAL" not in subs
    assert "AGV_AMR_HEAVY_LOGISTICS" not in subs
    assert "MRT_CANONICAL_COMPACT" not in subs
    assert "PTS_CONVENTIONAL" in subs


# --- serialization round-trip (Sec 45) ------------------------------------

def test_settings_dict_roundtrip_default():
    s = default_transport_settings()
    assert TransportSettings.from_dict(s.to_dict()) == s


def test_settings_json_roundtrip_complex():
    s = TransportSettings(
        mrt_enabled=False, pts_nuclear_qualified_enabled=False,
        agv_amr_heavy_logistics_enabled=False, radiopharm_qualification_supplied=True,
    )
    restored = TransportSettings.from_json(s.to_json())
    assert restored == s


def test_serialization_preserves_family_switches():
    s = all_except_families("MRT")
    d = s.to_dict()
    assert d["mrt_enabled"] is False
    assert d["manual_enabled"] is True


def test_serialization_preserves_subtype_switches():
    s = TransportSettings(pts_nuclear_qualified_enabled=False)
    d = s.to_dict()
    assert d["pts_nuclear_qualified_enabled"] is False
    assert d["pts_conventional_enabled"] is True


def test_serialization_preserves_qualification_flags():
    s = TransportSettings(radiopharm_qualification_supplied=True, pts_sensitive_specimen_validated=True)
    restored = TransportSettings.from_dict(s.to_dict())
    assert restored.radiopharm_qualification_supplied
    assert restored.pts_sensitive_specimen_validated


def test_from_dict_rejects_unknown_key():
    with pytest.raises(ValueError):
        TransportSettings.from_dict({"bogus_flag": True})


def test_json_is_deterministic_sorted():
    s = default_transport_settings()
    assert s.to_json() == s.to_json()
    # keys sorted
    import json
    keys = list(json.loads(s.to_json()).keys())
    assert keys == sorted(keys)


# --- with_overrides (Sec 6) -----------------------------------------------

def test_with_overrides_is_additive():
    base = default_transport_settings()
    modified = with_overrides(base, mrt_enabled=False)
    assert base.mrt_enabled is True   # base unchanged (frozen)
    assert modified.mrt_enabled is False


# --- subtype-scope matrix (Sec 44) ----------------------------------------

def test_subtype_scope_pts_conventional_only():
    s = TransportSettings(pts_nuclear_qualified_enabled=False)
    assert s.subtype_effectively_enabled("PTS_CONVENTIONAL")
    assert not s.subtype_effectively_enabled("PTS_NUCLEAR_QUALIFIED")


def test_subtype_scope_agv_light_only():
    s = TransportSettings(agv_amr_heavy_logistics_enabled=False)
    assert s.subtype_effectively_enabled("AGV_AMR_LIGHT_CLINICAL")
    assert not s.subtype_effectively_enabled("AGV_AMR_HEAVY_LOGISTICS")


def test_subtype_scope_agv_heavy_only():
    s = TransportSettings(agv_amr_light_clinical_enabled=False)
    assert not s.subtype_effectively_enabled("AGV_AMR_LIGHT_CLINICAL")
    assert s.subtype_effectively_enabled("AGV_AMR_HEAVY_LOGISTICS")


def test_subtype_scope_both_pts_subtypes():
    s = default_transport_settings()
    assert s.subtype_effectively_enabled("PTS_CONVENTIONAL")
    assert s.subtype_effectively_enabled("PTS_NUCLEAR_QUALIFIED")
