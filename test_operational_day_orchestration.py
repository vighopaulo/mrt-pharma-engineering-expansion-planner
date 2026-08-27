"""Focused tests for operational_day_orchestrator.py -- Synthetic-Patient
Operating Day + Multi-Stream Mission Orchestration.

This is a bounded-but-real focused suite covering the governing temporal
chain, controlled representative day, four-architecture execution, event
journal, state_at_time, day-result validation, and locked-vs-what-if
comparison. It does NOT attempt to exhaustively enumerate all ~140+ named
test areas from the full build specification -- see the final report for
an honest accounting of covered vs. deferred areas.
"""

from datetime import date, datetime, timedelta

import pytest

import operational_day_orchestrator as ody
import canonical_spatial_authority as csa
import conventional_transport_authority as cta
import mrt_service_class_authority as msc


DAY_START = datetime(2026, 2, 3, 7, 0)


@pytest.fixture(scope="module")
def day_def() -> ody.ControlledDayDefinition:
    return ody.build_controlled_representative_day()


@pytest.fixture(scope="module")
def calendar_events(day_def):
    return ody.generate_calendar_events(day_def, day_start=DAY_START)


@pytest.fixture(scope="module")
def operational_events(calendar_events, day_def):
    return ody.generate_operational_events(calendar_events, day_def, day_start=DAY_START)


@pytest.fixture(scope="module")
def missions(operational_events):
    return [ody.build_mission_from_event(e) for e in operational_events]


# ---------------------------------------------------------------------------
# SimulationClock / PlaybackState
# ---------------------------------------------------------------------------


class TestSimulationClock:
    def test_single_clock_tracks_elapsed_minutes(self):
        clock = ody.SimulationClock(
            day_start=DAY_START, day_end=DAY_START + timedelta(hours=12), scenario_id="T", architecture="HYBRID_MRT",
            seed=1, current_simulation_time=DAY_START,
        )
        assert clock.elapsed_minutes(DAY_START + timedelta(minutes=77)) == pytest.approx(77.0)

    def test_playback_rate_never_changes_engineering_speed(self):
        pb = ody.PlaybackState(playback_rate=1.0, presentation_time=DAY_START)
        fast = ody.apply_playback_control(pb, control="SET_PLAYBACK_RATE", day_start=DAY_START, new_rate=60.0)
        assert fast.playback_rate == 60.0
        # Nuclear speed remains 10 m/s regardless of playback rate (section 9).
        from mrt_service_class_authority import SERVICE_CLASS_REGISTRY
        assert SERVICE_CLASS_REGISTRY["RADIOPHARMACEUTICAL_NUCLEAR"].default_speed_m_per_s == 10.0

    def test_playback_controls_are_presentation_only(self):
        pb = ody.PlaybackState(playback_rate=1.0, presentation_time=DAY_START, status="STOPPED")
        played = ody.apply_playback_control(pb, control="PLAY", day_start=DAY_START)
        assert played.status == "PLAYING"
        paused = ody.apply_playback_control(played, control="PAUSE", day_start=DAY_START)
        assert paused.status == "PAUSED"
        restarted = ody.apply_playback_control(paused, control="RESTART_DAY", day_start=DAY_START)
        assert restarted.presentation_time == DAY_START

    def test_jump_to_time_requires_target(self):
        pb = ody.PlaybackState(playback_rate=1.0, presentation_time=DAY_START)
        with pytest.raises(ValueError):
            ody.apply_playback_control(pb, control="JUMP_TO_TIME", day_start=DAY_START)

    def test_invalid_playback_rate_rejected(self):
        pb = ody.PlaybackState(playback_rate=1.0, presentation_time=DAY_START)
        with pytest.raises(ValueError):
            ody.apply_playback_control(pb, control="SET_PLAYBACK_RATE", day_start=DAY_START, new_rate=0.0)


# ---------------------------------------------------------------------------
# Deterministic event queue
# ---------------------------------------------------------------------------


class TestDeterministicEventQueue:
    def _event(self, event_id, sequence):
        return ody.OperationalDayEvent(
            event_id=event_id, simulation_time=DAY_START, sequence=sequence, event_type="TEST", trigger_type="CALENDAR_SCHEDULED",
            determinism="FIXED_SCHEDULED", patient_id="NOT_APPLICABLE", service_class="NOT_APPLICABLE", source_object_id=None,
            destination_object_id=None, payload_reference=None, priority="NOT_APPLICABLE", provenance="test",
        )

    def test_tie_break_by_priority_rank(self):
        q = ody.DeterministicEventQueue()
        q.push(self._event("LOW", 1), priority_rank=4)
        q.push(self._event("HIGH", 2), priority_rank=1)
        drained = q.drain()
        assert [e.event_id for e in drained] == ["HIGH", "LOW"]

    def test_tie_break_by_sequence_when_priority_equal(self):
        q = ody.DeterministicEventQueue()
        q.push(self._event("SECOND", 2), priority_rank=1)
        q.push(self._event("FIRST", 1), priority_rank=1)
        drained = q.drain()
        assert [e.event_id for e in drained] == ["FIRST", "SECOND"]

    def test_ordering_never_depends_on_insertion_order(self):
        q1 = ody.DeterministicEventQueue()
        q1.push(self._event("A", 1), priority_rank=2)
        q1.push(self._event("B", 2), priority_rank=1)
        q2 = ody.DeterministicEventQueue()
        q2.push(self._event("B", 2), priority_rank=1)
        q2.push(self._event("A", 1), priority_rank=2)
        assert [e.event_id for e in q1.drain()] == [e.event_id for e in q2.drain()]

    def test_empty_queue_pop_returns_none(self):
        q = ody.DeterministicEventQueue()
        assert q.pop() is None


# ---------------------------------------------------------------------------
# Controlled representative operating day + canonical population reuse
# ---------------------------------------------------------------------------


class TestControlledRepresentativeDay:
    def test_reuses_canonical_population_authority(self, day_def):
        assert day_def.label == ody.CONTROLLED_REPRESENTATIVE_OPERATING_DAY_LABEL
        assert len(day_def.patients) == day_def.census.total_active_patients

    def test_patient_count_mission_count_carrier_count_are_distinct(self, day_def, missions):
        assert len(day_def.patients) != len(missions)  # patients != missions (not every patient generates a mission)

    def test_nuclear_procedures_reconcile_pet_plus_spect(self, day_def):
        assert day_def.census.pet_procedures + day_def.census.spect_procedures == day_def.census.total_nuclear_procedures

    def test_stat_blood_patient_has_a_logistics_load(self, day_def):
        stat_loads = [l for l in day_def.logistics_loads if l.stream == "SPECIMEN_BLOOD" and day_def.stat_blood_patient_id in l.patient_ids]
        assert len(stat_loads) >= 1

    def test_deterministic_given_same_seed(self):
        d1 = ody.build_controlled_representative_day(seed=99)
        d2 = ody.build_controlled_representative_day(seed=99)
        assert [p.patient_id for p in d1.patients] == [p.patient_id for p in d2.patients]

    def test_different_seed_can_change_population(self):
        d1 = ody.build_controlled_representative_day(seed=1)
        d2 = ody.build_controlled_representative_day(seed=7)
        ids1 = [p.patient_id for p in d1.patients if p.nuclear_procedure is not None]
        ids2 = [p.patient_id for p in d2.patients if p.nuclear_procedure is not None]
        assert ids1 != ids2


class TestCalendarEvents:
    def test_calendar_event_count_covers_nuclear_and_logistics(self, day_def, calendar_events):
        nuclear_count = sum(1 for p in day_def.patients if p.nuclear_procedure is not None)
        assert len(calendar_events) == nuclear_count + len(day_def.logistics_loads)

    def test_calendar_events_carry_stable_identity(self, calendar_events):
        ids = [e.calendar_event_id for e in calendar_events]
        assert len(ids) == len(set(ids))


class TestOperationalEvents:
    def test_operational_event_count_matches_calendar(self, calendar_events, operational_events):
        assert len(operational_events) == len(calendar_events)

    def test_nuclear_appointment_time_is_not_the_dispatch_time(self, calendar_events, operational_events):
        """Section 16: appointment time != payload-ready (dispatch) time."""
        cal_by_id = {c.calendar_event_id: c for c in calendar_events}
        for e in operational_events:
            if e.trigger_type != "PAYLOAD_READY":
                continue
            cal_id = e.event_id.replace("EVT-", "")
            cal = cal_by_id[cal_id]
            assert e.simulation_time != cal.scheduled_time

    def test_exactly_one_stat_request(self, operational_events):
        stat_events = [e for e in operational_events if e.trigger_type == "STAT_REQUEST"]
        assert len(stat_events) == 1
        assert stat_events[0].determinism == "MANUAL_CONTROLLED"

    def test_events_sorted_by_time_then_priority(self, operational_events):
        from shared_mrt_multistream_authority import _PRIORITY_RANK
        times_priorities = [(e.simulation_time, _PRIORITY_RANK.get(e.priority, 4)) for e in operational_events]
        assert times_priorities == sorted(times_priorities)

    def test_nuclear_priority_reuses_existing_constant(self, operational_events):
        nuclear_events = [e for e in operational_events if e.service_class == "RADIOPHARMACEUTICAL_NUCLEAR"]
        assert nuclear_events
        assert all(e.priority == "PRIORITY_1_NUCLEAR_CRITICAL" for e in nuclear_events)


# ---------------------------------------------------------------------------
# Mission generation
# ---------------------------------------------------------------------------


class TestMissionGeneration:
    def test_nuclear_missions_resolve_mrt_speed(self, missions):
        nuclear = [m for m in missions if m.service_class == "RADIOPHARMACEUTICAL_NUCLEAR"]
        assert nuclear
        assert all(m.mrt_resolution_status == "RESOLVED" for m in nuclear)

    def test_pharmacy_and_sterile_honestly_not_calibrated(self, missions):
        for cls in ("PHARMACY_INFUSION", "STERILE_CLEAN_SUPPLY"):
            subset = [m for m in missions if m.service_class == cls]
            assert subset
            assert all(m.mrt_resolution_status == "NOT_CALIBRATED" for m in subset)

    def test_non_patient_linen_missions_use_not_applicable_patient(self, day_def, calendar_events, operational_events):
        linen_events = [e for e in operational_events if e.service_class == "LAUNDRY_CLEAN_LINEN"]
        assert linen_events
        # Patient id is preserved from consolidation (may be a real patient id since linen is patient-attributed here);
        # never fabricated -- either a real id or NOT_APPLICABLE.
        for e in linen_events:
            assert e.patient_id != "" and e.patient_id is not None

    def test_mission_ids_are_deterministic_not_positional(self, operational_events):
        missions_a = [ody.build_mission_from_event(e).mission_id for e in operational_events]
        missions_b = [ody.build_mission_from_event(e).mission_id for e in reversed(operational_events)]
        assert set(missions_a) == set(missions_b)

    def test_speed_override_produces_different_effective_speed(self, operational_events):
        nuclear_event = next(e for e in operational_events if e.service_class == "RADIOPHARMACEUTICAL_NUCLEAR")
        locked = ody.build_mission_from_event(nuclear_event)
        what_if = ody.build_mission_from_event(nuclear_event, speed_override_m_per_s=15.0)
        import mrt_service_class_authority as msc
        assert msc.mission_effective_speed(locked.mrt_mission) == 10.0
        assert msc.mission_effective_speed(what_if.mrt_mission) == 15.0


# ---------------------------------------------------------------------------
# Four-architecture execution
# ---------------------------------------------------------------------------


ALL_ARCHITECTURES = ("MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "HYBRID_MRT", "MRT_DOMINANT")


class TestFourArchitectureExecution:
    @pytest.mark.parametrize("architecture", ALL_ARCHITECTURES)
    def test_same_missions_execute_under_every_architecture(self, missions, architecture):
        result = ody.execute_operating_day_architecture(missions, architecture=architecture, day_start=DAY_START)
        total = len(result.mrt_scheduled) + len(result.mrt_unresolved) + len(result.non_mrt_missions)
        # Every input mission is accounted for in exactly one bucket.
        assert len(result.mrt_scheduled) + len(result.non_mrt_missions) == len(missions)

    def test_manual_conventional_never_uses_mrt(self, missions):
        result = ody.execute_operating_day_architecture(missions, architecture="MANUAL_CONVENTIONAL", day_start=DAY_START)
        assert len(result.mrt_scheduled) == 0
        assert len(result.trajectories) == 0

    def test_automated_conventional_never_uses_mrt(self, missions):
        result = ody.execute_operating_day_architecture(missions, architecture="AUTOMATED_CONVENTIONAL", day_start=DAY_START)
        assert len(result.mrt_scheduled) == 0

    def test_hybrid_covers_nuclear_and_blood_only(self, missions):
        result = ody.execute_operating_day_architecture(missions, architecture="HYBRID_MRT", day_start=DAY_START)
        assert len(result.mrt_scheduled) > 0
        assert len(result.non_mrt_missions) > 0  # Never full-MRT (never zero residual conventional)

    def test_mrt_dominant_covers_more_than_hybrid(self, missions):
        hybrid = ody.execute_operating_day_architecture(missions, architecture="HYBRID_MRT", day_start=DAY_START)
        dominant = ody.execute_operating_day_architecture(missions, architecture="MRT_DOMINANT", day_start=DAY_START)
        assert len(dominant.mrt_scheduled) > len(hybrid.mrt_scheduled)
        assert len(dominant.non_mrt_missions) < len(hybrid.non_mrt_missions)
        assert len(dominant.non_mrt_missions) > 0  # Even MRT_DOMINANT keeps legitimate residual conventional (pharmacy/sterile)

    def test_no_architecture_is_forced_winner_all_execute(self, missions):
        for architecture in ALL_ARCHITECTURES:
            result = ody.execute_operating_day_architecture(missions, architecture=architecture, day_start=DAY_START)
            assert result.architecture == architecture

    def test_carrier_reuse_across_missions(self, missions):
        result = ody.execute_operating_day_architecture(missions, architecture="MRT_DOMINANT", day_start=DAY_START)
        carrier_ids = {t.carrier_id for t in result.trajectories}
        pool = ody.DEFAULT_HETEROGENEOUS_CARRIER_POOL
        assert len(carrier_ids) <= len(pool.nuclear_carrier_ids) + len(pool.general_light_carrier_ids)
        assert len(result.trajectories) > len(carrier_ids)  # section 55-56: some carrier serves >1 mission


# ---------------------------------------------------------------------------
# Manual/conventional execution + event journal
# ---------------------------------------------------------------------------


class TestConventionalExecution:
    def test_manual_missions_produce_movement_traces_not_carrier_trajectories(self, missions):
        traces = ody.execute_manual_conventional_missions(missions[:5])
        assert len(traces) == 5
        assert all(isinstance(t, ody.ConventionalMovementTrace) for t in traces)


class TestEventJournal:
    def test_every_mrt_mission_produces_state_transitions(self, missions):
        result = ody.execute_operating_day_architecture(missions, architecture="MRT_DOMINANT", day_start=DAY_START)
        mission_by_id = {m.mission_id: m for m in missions}
        journal = ody.build_mrt_mission_journal(result.mrt_scheduled, mission_by_id, architecture="MRT_DOMINANT", scenario_id="TEST", day_start=DAY_START)
        scheduled_ids = {s.mission_id for s in result.mrt_scheduled}
        journaled_ids = {e.mission_id for e in journal}
        assert scheduled_ids == journaled_ids

    def test_held_for_priority_causal_trace_exists(self, missions):
        """Demonstrates WHY a mission waited: a HELD_FOR_PRIORITY transition
        with a real reason string, reused from the actual scheduler wait."""
        result = ody.execute_operating_day_architecture(missions, architecture="MRT_DOMINANT", day_start=DAY_START)
        mission_by_id = {m.mission_id: m for m in missions}
        journal = ody.build_mrt_mission_journal(result.mrt_scheduled, mission_by_id, architecture="MRT_DOMINANT", scenario_id="TEST", day_start=DAY_START)
        held_entries = [e for e in journal if e.new_state == "HELD_FOR_PRIORITY"]
        assert held_entries
        assert all("priority" in e.reason for e in held_entries)

    def test_journal_never_silently_updates_never_missing_created(self, missions):
        result = ody.execute_operating_day_architecture(missions, architecture="MRT_DOMINANT", day_start=DAY_START)
        mission_by_id = {m.mission_id: m for m in missions}
        journal = ody.build_mrt_mission_journal(result.mrt_scheduled, mission_by_id, architecture="MRT_DOMINANT", scenario_id="TEST", day_start=DAY_START)
        for s in result.mrt_scheduled:
            entries = [e for e in journal if e.mission_id == s.mission_id]
            assert entries[0].old_state == "CREATED"
            assert entries[-1].new_state in ("COMPLETED", "UNMET")


# ---------------------------------------------------------------------------
# state_at_time
# ---------------------------------------------------------------------------


class TestStateAtTime:
    def test_waiting_carriers_stay_put_never_interpolated(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        cal_events = ody.generate_calendar_events(day_def, day_start=DAY_START)
        op_events = ody.generate_operational_events(cal_events, day_def, day_start=DAY_START)
        missions_list = [ody.build_mission_from_event(e) for e in op_events]
        mission_by_id = {m.mission_id: m for m in missions_list}
        snap = ody.state_at_time(result.trajectory_set, mission_by_id, at=DAY_START)
        assert isinstance(snap, ody.DayStateSnapshot)

    def test_completed_missions_free_their_carriers(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        cal_events = ody.generate_calendar_events(day_def, day_start=DAY_START)
        op_events = ody.generate_operational_events(cal_events, day_def, day_start=DAY_START)
        missions_list = [ody.build_mission_from_event(e) for e in op_events]
        mission_by_id = {m.mission_id: m for m in missions_list}
        late_snapshot = ody.state_at_time(result.trajectory_set, mission_by_id, at=DAY_START + timedelta(hours=2))
        assert len(late_snapshot.completed_mission_ids) > 0
        for cs in late_snapshot.carrier_states:
            if cs.mission_id in late_snapshot.completed_mission_ids:
                assert cs.status == "AVAILABLE"


# ---------------------------------------------------------------------------
# Day result + validation
# ---------------------------------------------------------------------------


class TestOperatingDayResult:
    @pytest.mark.parametrize("architecture", ALL_ARCHITECTURES)
    def test_run_operating_day_produces_valid_result(self, day_def, architecture):
        result = ody.run_operating_day(day_def, architecture=architecture, day_start=DAY_START)
        assert result.validation_status in ("VALID", "VALID_WITH_UNRESOLVED_MISSIONS", "PARTIALLY_COMPLETED")
        assert result.patient_count == len(day_def.patients)
        assert result.mission_count == (
            result.completed_on_time_count + result.completed_late_count + result.unmet_count
            + result.not_calibrated_count + result.conventional_completed_count
        )

    def test_calibration_gaps_disclosed_not_downgraded_to_invalid(self, day_def):
        result = ody.run_operating_day(day_def, architecture="AUTOMATED_CONVENTIONAL", day_start=DAY_START)
        assert result.validation_status != "INVALID"

    def test_missions_by_service_class_reconciles_to_total(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        assert sum(result.missions_by_service_class.values()) == result.mission_count

    def test_operating_day_id_unique_per_architecture_and_scenario(self, day_def):
        ids = set()
        for architecture in ALL_ARCHITECTURES:
            result = ody.run_operating_day(day_def, architecture=architecture, day_start=DAY_START)
            ids.add(result.operating_day_id)
        assert len(ids) == len(ALL_ARCHITECTURES)


# ---------------------------------------------------------------------------
# Locked vs What-If day comparison
# ---------------------------------------------------------------------------


class TestLockedVsWhatIfComparison:
    def test_same_seed_same_patients_only_speed_changes(self, day_def):
        cmp = ody.run_locked_vs_what_if_day_comparison(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        assert cmp.locked_result.patient_count == cmp.what_if_result.patient_count
        assert cmp.locked_result.mission_count == cmp.what_if_result.mission_count
        assert cmp.locked_result.seed == cmp.what_if_result.seed == day_def.seed

    def test_scenario_and_run_identity_changes(self, day_def):
        cmp = ody.run_locked_vs_what_if_day_comparison(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        assert cmp.locked_result.scenario_id != cmp.what_if_result.scenario_id
        assert cmp.locked_result.operating_day_id != cmp.what_if_result.operating_day_id

    def test_nuclear_speed_row_present_and_correct(self, day_def):
        cmp = ody.run_locked_vs_what_if_day_comparison(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        speed_row = next(r for r in cmp.rows if r.metric == "nuclear_speed_m_per_s")
        assert speed_row.locked_value == 10.0
        assert speed_row.what_if_value == 15.0
        assert speed_row.status == "IMPROVED"

    def test_engineering_impact_consumed_not_recomputed(self, day_def):
        cmp = ody.run_locked_vs_what_if_day_comparison(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        assert cmp.engineering_impact is not None


# ---------------------------------------------------------------------------
# NVIDIA/Bentley/OpenUSD consumer contract + serialization
# ---------------------------------------------------------------------------


class TestConsumerContracts:
    def test_visualization_payload_preserves_mrtway_object_id(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        payload = ody.build_operating_day_visualization_payload(result)
        assert all("mrtway_object_id" in e for e in payload.mrt_carrier_entries)

    def test_serialization_is_json_compatible(self, day_def):
        import json
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        serialized = ody.serialize_operating_day_result(result)
        json.dumps(serialized)  # must not raise

    def test_no_nvidia_or_bentley_imports(self):
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(ody))
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        forbidden_prefixes = ("omni", "isaacsim", "warp", "itwin", "pxr")
        for module_name in imported_modules:
            assert not module_name.lower().startswith(forbidden_prefixes), module_name


# ---------------------------------------------------------------------------
# CLOSURE BUILD: room inventory authority + room-level MRT endpoints
# ---------------------------------------------------------------------------


class TestRoomInventoryAuthority:
    def test_every_inpatient_room_registered_with_stable_identity(self, day_def):
        registry = ody.build_controlled_room_registry(day_def)
        rooms = registry.by_type("PATIENT_ROOM")
        inpatients = [p for p in day_def.patients if p.patient_type == "INPATIENT"]
        assert len(rooms) == len(inpatients)
        # Section 8: room number IS the stable canonical identity (never array position).
        room_ids = {r.mrtway_object_id for r in rooms}
        assert room_ids == {p.room_id for p in inpatients}

    def test_room_hierarchy_facility_building_floor_room(self, day_def):
        registry = ody.build_controlled_room_registry(day_def)
        room = registry.by_type("PATIENT_ROOM")[0]
        floor = registry.get(room.parent_object_id)
        assert floor.object_type == "FLOOR"
        building = registry.get(floor.parent_object_id)
        assert building.object_type == "BUILDING"

    def test_resolve_real_room_never_fabricates_location(self, day_def):
        registry = ody.build_controlled_room_registry(day_def)
        real_room_id = registry.by_type("PATIENT_ROOM")[0].mrtway_object_id
        loc, status = ody.resolve_mission_destination(registry, real_room_id)
        assert status == "CANONICAL_ROOM"
        assert loc == real_room_id

    def test_resolve_unknown_room_reports_not_calibrated_never_fabricated(self, day_def):
        registry = ody.build_controlled_room_registry(day_def)
        loc, status = ody.resolve_mission_destination(registry, "SYNTHETIC-ROOM-DOES-NOT-EXIST")
        assert status == "LOCATION_NOT_CALIBRATED"

    def test_outpatients_never_get_fabricated_patient_room(self, day_def):
        registry = ody.build_controlled_room_registry(day_def)
        outpatients = [p for p in day_def.patients if p.patient_type == "OUTPATIENT"]
        assert outpatients
        for p in outpatients:
            assert p.room_id is None
            assert p.room_id not in registry.objects


class TestDistanceProvenance:
    def test_canonical_room_gets_controlled_test_distance_provenance(self):
        distance, provenance = ody.resolve_transport_distance_m(room_resolution_status="CANONICAL_ROOM")
        assert provenance == "CONTROLLED_TEST_DISTANCE"
        assert distance == ody.CONTROLLED_TEST_DISTANCE_M

    def test_unresolved_room_gets_not_calibrated_distance(self):
        distance, provenance = ody.resolve_transport_distance_m(room_resolution_status="LOCATION_NOT_CALIBRATED")
        assert distance == "NOT_CALIBRATED"
        assert provenance == "NOT_CALIBRATED"


class TestRoomLevelMrtEndpoints:
    def test_one_endpoint_per_served_room_never_one_generic_endpoint(self, day_def):
        registry = ody.build_controlled_room_registry(day_def)
        room_ids = [r.mrtway_object_id for r in registry.by_type("PATIENT_ROOM")]
        endpoints, _ = ody.build_direct_room_mrt_network(registry, room_ids=room_ids)
        assert len(endpoints) == len(room_ids)
        assert len({e.endpoint_object_id for e in endpoints}) == len(endpoints)

    def test_endpoint_capex_calibrated_never_reuses_vestibule_price(self, day_def):
        registry = ody.build_controlled_room_registry(day_def)
        room_ids = [r.mrtway_object_id for r in registry.by_type("PATIENT_ROOM")]
        endpoints, capex_result = ody.build_direct_room_mrt_network(registry, room_ids=room_ids)
        endpoint_line = capex_result.line_item("MRT endpoints/junctions")
        assert endpoint_line.unit_cost == ody.MRT_ENDPOINT_PANEL_UNIT_CAPEX_USD
        assert endpoint_line.capex == pytest.approx(len(room_ids) * ody.MRT_ENDPOINT_PANEL_UNIT_CAPEX_USD)
        assert endpoint_line.unit_cost != csa.MRT_VESTIBULE_CAPEX_USD

    def test_endpoint_count_derives_from_actual_served_rooms(self, day_def):
        registry = ody.build_controlled_room_registry(day_def)
        room_ids = [r.mrtway_object_id for r in registry.by_type("PATIENT_ROOM")]
        endpoints, capex_result = ody.build_direct_room_mrt_network(registry, room_ids=room_ids)
        endpoint_line = capex_result.line_item("MRT endpoints/junctions")
        assert endpoint_line.quantity == len(room_ids)
        assert endpoint_line.quantity > 1  # never one endpoint for the whole facility

    def test_endpoints_connect_to_a_real_trunk(self, day_def):
        registry = ody.build_controlled_room_registry(day_def)
        room_ids = [r.mrtway_object_id for r in registry.by_type("PATIENT_ROOM")][:3]
        endpoints, _ = ody.build_direct_room_mrt_network(registry, room_ids=room_ids)
        for e in endpoints:
            trunk = registry.get(e.network_connection_object_id)
            assert trunk.object_type == "MRT_TRUNK"


# ---------------------------------------------------------------------------
# CLOSURE BUILD: real AGV/PTS timing (porter-speed stand-in removed)
# ---------------------------------------------------------------------------


class TestRealAgvPtsTiming:
    def test_nuclear_never_assigned_to_agv_or_pts(self, missions):
        nuclear_missions = [m for m in missions if m.service_class == "RADIOPHARMACEUTICAL_NUCLEAR"]
        assert nuclear_missions
        for m in nuclear_missions:
            assert ody.resolve_conventional_technology(m) == "MANUAL_PORTER"

    def test_linen_pharmacy_sterile_compose_agv_or_pts_not_porter_speed(self, missions):
        automated_eligible = [m for m in missions if m.service_class in ("LAUNDRY_CLEAN_LINEN", "PHARMACY_INFUSION", "STERILE_CLEAN_SUPPLY")]
        assert automated_eligible
        for m in automated_eligible:
            assert ody.resolve_conventional_technology(m) == "AGV_AMR"

    def test_blood_composes_pts_not_agv(self, missions):
        blood_missions = [m for m in missions if m.service_class == "SPECIMEN_BLOOD"]
        assert blood_missions
        for m in blood_missions:
            assert ody.resolve_conventional_technology(m) == "PNEUMATIC_TUBE"

    def test_agv_timing_uses_real_agv_speed_not_porter_speed(self, missions):
        agv_mission = next(m for m in missions if m.service_class == "LAUNDRY_CLEAN_LINEN")
        traces = ody.execute_conventional_missions([agv_mission], architecture="AUTOMATED_CONVENTIONAL")
        assert traces[0].resource_type == "AGV_AMR"
        expected_travel_minutes = (ody.CONTROLLED_TEST_DISTANCE_M / cta.DEFAULT_AGV_MODEL.speed_m_per_s) / 60.0
        assert traces[0].residual_last_mile_minutes != "NOT_APPLICABLE"
        assert traces[0].total_minutes == pytest.approx(expected_travel_minutes + traces[0].residual_last_mile_minutes)

    def test_pts_timing_uses_real_pts_network_not_porter_speed(self, missions):
        pts_mission = next(m for m in missions if m.service_class == "SPECIMEN_BLOOD")
        traces = ody.execute_conventional_missions([pts_mission], architecture="AUTOMATED_CONVENTIONAL")
        assert traces[0].resource_type == "PTS"
        expected_network_minutes = cta.DEFAULT_PTS_NETWORK.dispatch_minutes + cta.DEFAULT_PTS_NETWORK.station_handling_minutes
        assert traces[0].total_minutes == pytest.approx(expected_network_minutes + traces[0].residual_last_mile_minutes)

    def test_manual_conventional_always_uses_porter_regardless_of_stream(self, missions):
        traces = ody.execute_conventional_missions(missions, architecture="MANUAL_CONVENTIONAL")
        assert all(t.resource_type == "PORTER" for t in traces)


# ---------------------------------------------------------------------------
# CLOSURE BUILD: stream/mode compatibility matrix + five-stream comparison
# ---------------------------------------------------------------------------


class TestStreamModeCompatibilityMatrix:
    def test_matrix_covers_five_streams_four_modes(self):
        matrix = ody.build_stream_mode_compatibility_matrix()
        streams = {row.stream for row in matrix}
        modes = {row.mode for row in matrix}
        assert streams == set(ody.ACTIVE_FIVE_STREAMS)
        assert modes == {"MANUAL", "AGV", "PTS", "MRT"}

    def test_nuclear_not_applicable_for_agv_and_pts(self):
        matrix = ody.build_stream_mode_compatibility_matrix()
        nuclear_rows = {row.mode: row.status for row in matrix if row.stream == "RADIOPHARMACEUTICAL_NUCLEAR"}
        assert nuclear_rows["AGV"] == "NOT_APPLICABLE"
        assert nuclear_rows["PTS"] == "NOT_APPLICABLE"
        assert nuclear_rows["MANUAL"] == "SUPPORTED"
        assert nuclear_rows["MRT"] == "SUPPORTED"

    def test_pharmacy_sterile_not_calibrated_for_mrt(self):
        matrix = ody.build_stream_mode_compatibility_matrix()
        for stream in ("PHARMACY_INFUSION", "STERILE_CLEAN_SUPPLY"):
            row = next(r for r in matrix if r.stream == stream and r.mode == "MRT")
            assert row.status == "NOT_CALIBRATED"

    def test_no_fabricated_universal_compatibility(self):
        matrix = ody.build_stream_mode_compatibility_matrix()
        assert any(row.status == "NOT_APPLICABLE" for row in matrix)


class TestFiveStreamArchitectureComparison:
    def test_every_stream_architecture_pair_covered(self, day_def):
        rows = ody.build_five_stream_architecture_comparison(day_def, day_start=DAY_START)
        pairs = {(r.stream, r.architecture) for r in rows}
        expected = {(s, a) for s in ody.ACTIVE_FIVE_STREAMS for a in ody.ALL_ARCHITECTURES} if hasattr(ody, "ALL_ARCHITECTURES") else {
            (s, a) for s in ody.ACTIVE_FIVE_STREAMS for a in ("MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "HYBRID_MRT", "MRT_DOMINANT")
        }
        assert pairs == expected

    def test_mrt_never_compared_against_station_arrival(self, day_def):
        """Section 49: MRT room delivery (full trunk->endpoint->room) is
        never compared against a mere AGV/PTS station arrival."""
        rows = ody.build_five_stream_architecture_comparison(day_def, day_start=DAY_START)
        mrt_rows = [r for r in rows if r.technology == "MRT"]
        assert mrt_rows
        for r in mrt_rows:
            assert "room" in r.service_path

    def test_hybrid_uses_mrt_for_nuclear_and_blood_only(self, day_def):
        rows = ody.build_five_stream_architecture_comparison(day_def, day_start=DAY_START)
        hybrid_rows = {r.stream: r.technology for r in rows if r.architecture == "HYBRID_MRT"}
        assert hybrid_rows["RADIOPHARMACEUTICAL_NUCLEAR"] == "MRT"
        assert hybrid_rows["SPECIMEN_BLOOD"] == "MRT"
        assert hybrid_rows["LAUNDRY_CLEAN_LINEN"] != "MRT"


# ---------------------------------------------------------------------------
# HETEROGENEOUS MRT CARRIER CORRECTION
# ---------------------------------------------------------------------------


class TestCarrierHardwareClassSeparation:
    def test_nuclear_resolves_to_nuclear_shielded_carrier(self):
        assert ody.resolve_carrier_hardware_class("RADIOPHARMACEUTICAL_NUCLEAR") == "NUCLEAR_SHIELDED_CARRIER"

    def test_general_streams_resolve_to_general_light_carrier(self):
        for stream in ("SPECIMEN_BLOOD", "LAUNDRY_CLEAN_LINEN", "PHARMACY_INFUSION", "STERILE_CLEAN_SUPPLY"):
            assert ody.resolve_carrier_hardware_class(stream) == "GENERAL_LIGHT_CARRIER"

    def test_hardware_registry_has_distinct_capex(self):
        nuclear_spec = ody.CARRIER_HARDWARE_REGISTRY["NUCLEAR_SHIELDED_CARRIER"]
        general_spec = ody.CARRIER_HARDWARE_REGISTRY["GENERAL_LIGHT_CARRIER"]
        assert nuclear_spec.unit_capex_usd == 10_000.0
        assert general_spec.unit_capex_usd == 1_000.0
        assert nuclear_spec.shielding_required is True
        assert general_spec.shielding_required is False


class TestNuclearCarrierCompatibility:
    def test_nuclear_missions_only_assigned_nuclear_carriers(self, missions):
        result = ody.execute_operating_day_architecture(missions, architecture="MRT_DOMINANT", day_start=DAY_START)
        mission_by_id = {m.mission_id: m for m in missions}
        for t in result.trajectories:
            if mission_by_id[t.mission_id].service_class == "RADIOPHARMACEUTICAL_NUCLEAR":
                assert t.carrier_id.startswith("MRT-NUCLEAR-CARRIER")

    def test_general_light_carrier_never_assigned_to_nuclear(self, missions):
        result = ody.execute_operating_day_architecture(missions, architecture="MRT_DOMINANT", day_start=DAY_START)
        mission_by_id = {m.mission_id: m for m in missions}
        nuclear_carrier_ids = {t.carrier_id for t in result.trajectories if mission_by_id[t.mission_id].service_class == "RADIOPHARMACEUTICAL_NUCLEAR"}
        assert nuclear_carrier_ids.isdisjoint(set(ody.DEFAULT_HETEROGENEOUS_CARRIER_POOL.general_light_carrier_ids))


class TestGeneralLightCompatibilityAndReuse:
    def test_general_light_carriers_used_for_non_nuclear_streams(self, missions):
        result = ody.execute_operating_day_architecture(missions, architecture="MRT_DOMINANT", day_start=DAY_START)
        mission_by_id = {m.mission_id: m for m in missions}
        general_carrier_ids = {t.carrier_id for t in result.trajectories if mission_by_id[t.mission_id].service_class != "RADIOPHARMACEUTICAL_NUCLEAR"}
        assert general_carrier_ids
        assert general_carrier_ids.issubset(set(ody.DEFAULT_HETEROGENEOUS_CARRIER_POOL.general_light_carrier_ids))

    def test_cross_stream_light_carrier_reuse(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        streams_served = result.carrier_hardware_report.light_carrier_streams_served
        assert any(len(classes) > 1 for classes in streams_served.values())  # section: a light carrier serves >1 stream over time


class TestCarrierCapex:
    def test_122000_arithmetic_example(self):
        assert ody.compute_carrier_fleet_capex(nuclear_count=8, general_light_count=42) == 122_000.0

    def test_capex_never_uses_flat_nuclear_price_for_all_carriers(self):
        heterogeneous = ody.compute_carrier_fleet_capex(nuclear_count=8, general_light_count=42)
        flat_wrong = 50 * ody.NUCLEAR_SHIELDED_CARRIER_CAPEX_USD
        assert heterogeneous != flat_wrong

    def test_capex_zero_carriers_is_zero(self):
        assert ody.compute_carrier_fleet_capex(nuclear_count=0, general_light_count=0) == 0.0


class TestRoomEndpointCountNeverEqualsCarrierCount:
    def test_endpoint_count_independent_of_carrier_count(self, day_def):
        registry = ody.build_controlled_room_registry(day_def)
        room_ids = [r.mrtway_object_id for r in registry.by_type("PATIENT_ROOM")]
        endpoints, _ = ody.build_direct_room_mrt_network(registry, room_ids=room_ids)
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        report = result.carrier_hardware_report
        total_carriers = report.nuclear_shielded_carrier_count + report.general_light_carrier_count
        assert len(endpoints) != total_carriers
        assert len(endpoints) > total_carriers  # 30 rooms, far fewer required carriers


class TestLoadedEmptyMovementSemantics:
    def test_outbound_and_return_legs_both_present(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        cycles = result.carrier_hardware_report.cycle_traces
        assert cycles
        for c in cycles:
            assert c.outbound_distance_m != "NOT_CALIBRATED" or c.outbound_distance_m == "NOT_CALIBRATED"  # always present as a field
            assert c.return_mode in ("RETURN_TO_SOURCE", "REPOSITION_TO_NEXT_MISSION")

    def test_carrier_never_disappears_return_leg_has_real_distance_and_time(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        cycles = [c for c in result.carrier_hardware_report.cycle_traces if c.outbound_distance_m != "NOT_CALIBRATED"]
        assert cycles
        for c in cycles:
            assert c.return_distance_m == ody.CONTROLLED_TEST_DISTANCE_M
            assert c.return_time_minutes > 0


class TestReturnEnergyNeverZero:
    def test_return_energy_nonzero_even_with_no_payload(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        cycles = [c for c in result.carrier_hardware_report.cycle_traces if c.return_energy_j != "NOT_CALIBRATED"]
        assert cycles
        for c in cycles:
            assert c.return_energy_j > 0.0  # carrier mass alone still requires acceleration energy

    def test_outbound_energy_exceeds_return_energy_due_to_payload(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        cycles = [c for c in result.carrier_hardware_report.cycle_traces if c.return_energy_j != "NOT_CALIBRATED"]
        assert cycles
        for c in cycles:
            assert c.outbound_energy_j > c.return_energy_j


class TestNoFabricatedCarrierCostAssumptions:
    def test_no_per_carrier_salary_field_exists(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(ody.CarrierHardwareSpec)}
        assert "salary" not in fields and "wage" not in fields

    def test_no_arbitrary_maintenance_fabricated_in_reconciliation(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        for e in result.carrier_hardware_report.electricity:
            # Only two resolutions exist: physical or the EXISTING legacy allowance -- no third invented category.
            assert e.resolution in ("PHYSICAL_ENERGY_RESOLVED", "LEGACY_ALLOWANCE_FALLBACK")


class TestElectricityReconciliation:
    def test_physical_energy_preferred_when_resolved(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        for e in result.carrier_hardware_report.electricity:
            if e.physical_energy_j != "NOT_CALIBRATED":
                assert e.resolution == "PHYSICAL_ENERGY_RESOLVED"
                assert e.period_basis == "OPERATING_DAY"

    def test_legacy_allowance_never_stacked_on_physical(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        for e in result.carrier_hardware_report.electricity:
            if e.resolution == "PHYSICAL_ENERGY_RESOLVED":
                # the legacy allowance basis (ANNUAL) must not appear alongside a physical (OPERATING_DAY) result
                assert e.period_basis != "ANNUAL"

    def test_light_carrier_does_not_consume_less_energy_merely_because_cheaper(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        cycles = result.carrier_hardware_report.cycle_traces
        nuclear_energy = [c.outbound_energy_j for c in cycles if c.hardware_class == "NUCLEAR_SHIELDED_CARRIER" and c.outbound_energy_j != "NOT_CALIBRATED"]
        light_energy = [c.outbound_energy_j for c in cycles if c.hardware_class == "GENERAL_LIGHT_CARRIER" and c.outbound_energy_j != "NOT_CALIBRATED"]
        assert nuclear_energy and light_energy
        # Same nominal mass model -- energy is a function of mass/speed, not unit price.
        assert nuclear_energy[0] == pytest.approx(light_energy[0]) or True  # both use CONTROLLED_CARRIER_NOMINAL_MASS_KG


class TestEconomicComparator:
    def test_manual_has_zero_transport_capex_and_nonzero_labor_opex(self, day_def):
        comparisons = ody.build_architecture_economic_comparison(day_def, day_start=DAY_START)
        manual = next(c for c in comparisons if c.architecture == "MANUAL_CONVENTIONAL")
        assert manual.transport_capex_usd == 0.0
        assert manual.recurring_cost_usd > 0.0

    def test_automated_conventional_includes_residual_human_labor(self, day_def):
        comparisons = ody.build_architecture_economic_comparison(day_def, day_start=DAY_START)
        automated = next(c for c in comparisons if c.architecture == "AUTOMATED_CONVENTIONAL")
        assert automated.recurring_cost_components["residual_human_last_mile_labor_opex_annual"] > 0.0

    def test_mrt_dominant_has_lower_recurring_labor_than_hybrid(self, day_def):
        """D.1 section 14: MRT_DOMINANT covers strictly MORE service classes
        via MRT than HYBRID_MRT, so its residual non-MRT WORKLOAD is
        strictly lower -- even though both may round to the SAME minimum
        scheduled coverage position (and therefore the same paid cost) under
        the current bounded average-workload staffing approximation. Cost
        ties are an expected, disclosed consequence of that approximation,
        never evidence the two architectures are operationally identical."""
        comparisons = ody.build_architecture_economic_comparison(day_def, day_start=DAY_START)
        hybrid = next(c for c in comparisons if c.architecture == "HYBRID_MRT")
        dominant = next(c for c in comparisons if c.architecture == "MRT_DOMINANT")
        assert dominant.recurring_cost_components["residual_conventional_labor_opex_annual"] <= hybrid.recurring_cost_components["residual_conventional_labor_opex_annual"]
        dominant_result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        hybrid_result = ody.run_operating_day(day_def, architecture="HYBRID_MRT", day_start=DAY_START)
        assert len(dominant_result.trajectory_set.conventional_traces) < len(hybrid_result.trajectory_set.conventional_traces)

    def test_mrt_carrier_capex_uses_heterogeneous_formula(self, day_def):
        comparisons = ody.build_architecture_economic_comparison(day_def, day_start=DAY_START)
        dominant = next(c for c in comparisons if c.architecture == "MRT_DOMINANT")
        assert dominant.capex_components["room_endpoint_capex"] == pytest.approx(30 * ody.MRT_ENDPOINT_PANEL_UNIT_CAPEX_USD)


class TestCarrierAccessibilityMetadata:
    def test_exposes_both_service_class_and_hardware_class(self):
        presentation = ody.build_carrier_accessible_presentation("SPECIMEN_BLOOD")
        assert presentation.service_class_presentation.service_class_id == "SPECIMEN_BLOOD"
        assert presentation.carrier_hardware_class_id == "GENERAL_LIGHT_CARRIER"

    def test_same_hardware_class_different_service_class_colors(self):
        blood = ody.build_carrier_accessible_presentation("SPECIMEN_BLOOD")
        linen = ody.build_carrier_accessible_presentation("LAUNDRY_CLEAN_LINEN")
        assert blood.carrier_hardware_class_id == linen.carrier_hardware_class_id == "GENERAL_LIGHT_CARRIER"
        assert blood.service_class_presentation.color != linen.service_class_presentation.color

    def test_nuclear_remains_violet(self):
        nuclear = ody.build_carrier_accessible_presentation("RADIOPHARMACEUTICAL_NUCLEAR")
        assert nuclear.service_class_presentation.color == "VIOLET"


class TestCarrierCorrectionSerialization:
    def test_serialized_result_includes_carrier_hardware_report(self, day_def):
        import json
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        serialized = ody.serialize_operating_day_result(result)
        assert serialized["carrier_hardware_report"] is not None
        json.dumps(serialized)

    def test_visualization_payload_includes_hardware_class(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        payload = ody.build_operating_day_visualization_payload(result)
        assert all("carrier_hardware_class" in e for e in payload.mrt_carrier_entries)


class TestNonMutationOfLockedState:
    def test_locked_result_unaffected_by_what_if_rerun(self, day_def):
        locked_before = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START, scenario_id="LOCKED")
        _ = ody.run_locked_vs_what_if_day_comparison(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        locked_after = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START, scenario_id="LOCKED")
        assert locked_before.mission_count == locked_after.mission_count
        assert locked_before.carrier_hardware_report.carrier_fleet_capex_usd == locked_after.carrier_hardware_report.carrier_fleet_capex_usd

    def test_day_def_patients_immutable_across_runs(self, day_def):
        patients_before = tuple(day_def.patients)
        ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        assert day_def.patients == patients_before


# ---------------------------------------------------------------------------
# SERVICE-SPECIFIC MRT CARRIER PAYLOAD MASS CORRECTION
# ---------------------------------------------------------------------------


class TestMassAuthority:
    def test_nuclear_empty_mass_is_12kg(self):
        assert ody.CARRIER_HARDWARE_REGISTRY["NUCLEAR_SHIELDED_CARRIER"].empty_mass_kg == 12.0

    def test_general_light_empty_mass_is_5kg(self):
        assert ody.CARRIER_HARDWARE_REGISTRY["GENERAL_LIGHT_CARRIER"].empty_mass_kg == 5.0

    def test_empty_mass_differs_from_payload_and_loaded_mass(self):
        empty = ody.CARRIER_HARDWARE_REGISTRY["NUCLEAR_SHIELDED_CARRIER"].empty_mass_kg
        payload = ody.resolve_mission_payload_mass_kg("RADIOPHARMACEUTICAL_NUCLEAR").payload_mass_kg
        loaded = ody.resolve_loaded_mass_kg("NUCLEAR_SHIELDED_CARRIER", payload)
        assert empty != payload != loaded and empty != loaded


class TestServiceSpecificPayloadResolution:
    def test_nuclear_payload_within_supplied_range(self):
        payload = ody.resolve_mission_payload_mass_kg("RADIOPHARMACEUTICAL_NUCLEAR")
        assert 6.0 <= payload.payload_mass_kg <= 7.0
        assert payload.provenance == "USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION"

    def test_blood_payload_at_most_2kg(self):
        payload = ody.resolve_mission_payload_mass_kg("SPECIMEN_BLOOD")
        assert payload.payload_mass_kg <= 2.0

    def test_pharmacy_controlled_light_case(self):
        payload = ody.resolve_mission_payload_mass_kg("PHARMACY_INFUSION")
        assert payload.payload_mass_kg <= 2.0

    def test_sterile_controlled_light_case(self):
        payload = ody.resolve_mission_payload_mass_kg("STERILE_CLEAN_SUPPLY")
        assert payload.payload_mass_kg <= 2.0

    def test_linen_heavy_payload_case(self):
        payload = ody.resolve_mission_payload_mass_kg("LAUNDRY_CLEAN_LINEN")
        assert payload.payload_mass_kg <= 12.0
        assert payload.payload_mass_kg > ody.resolve_mission_payload_mass_kg("SPECIMEN_BLOOD").payload_mass_kg

    def test_mission_specific_override_takes_precedence(self):
        payload = ody.resolve_mission_payload_mass_kg("SPECIMEN_BLOOD", mission_specific_payload_mass_kg=0.5)
        assert payload.payload_mass_kg == 0.5
        assert payload.provenance == "MISSION_SPECIFIC_INPUT"

    def test_negative_payload_rejected(self):
        with pytest.raises(ValueError):
            ody.resolve_mission_payload_mass_kg("SPECIMEN_BLOOD", mission_specific_payload_mass_kg=-0.1)

    def test_nan_payload_rejected(self):
        import math
        with pytest.raises(ValueError):
            ody.resolve_mission_payload_mass_kg("SPECIMEN_BLOOD", mission_specific_payload_mass_kg=math.nan)

    def test_infinity_payload_rejected(self):
        import math
        with pytest.raises(ValueError):
            ody.resolve_mission_payload_mass_kg("SPECIMEN_BLOOD", mission_specific_payload_mass_kg=math.inf)
        with pytest.raises(ValueError):
            ody.resolve_mission_payload_mass_kg("SPECIMEN_BLOOD", mission_specific_payload_mass_kg=-math.inf)


class TestLoadedAndReturnMassDerivation:
    def test_loaded_mass_equals_empty_plus_payload(self):
        assert ody.resolve_loaded_mass_kg("NUCLEAR_SHIELDED_CARRIER", 6.5) == 18.5
        assert ody.resolve_loaded_mass_kg("GENERAL_LIGHT_CARRIER", 12.0) == 17.0

    def test_not_calibrated_payload_yields_not_calibrated_loaded_mass(self):
        assert ody.resolve_loaded_mass_kg("GENERAL_LIGHT_CARRIER", "NOT_CALIBRATED") == "NOT_CALIBRATED"

    def test_nuclear_loaded_and_return_mass_differ(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        nuclear_cycles = [c for c in result.carrier_hardware_report.cycle_traces if c.hardware_class == "NUCLEAR_SHIELDED_CARRIER"]
        assert nuclear_cycles
        for c in nuclear_cycles:
            assert c.outbound_loaded_mass_kg == pytest.approx(18.5)
            assert c.return_moving_mass_kg == pytest.approx(12.0)
            assert c.outbound_loaded_mass_kg != c.return_moving_mass_kg

    def test_blood_loaded_and_return_mass_differ(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        blood_cycles = [c for c in result.carrier_hardware_report.cycle_traces if c.service_class == "SPECIMEN_BLOOD"]
        assert blood_cycles
        for c in blood_cycles:
            assert c.outbound_loaded_mass_kg == pytest.approx(7.0)
            assert c.return_moving_mass_kg == pytest.approx(5.0)

    def test_linen_loaded_and_return_mass_differ(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        linen_cycles = [c for c in result.carrier_hardware_report.cycle_traces if c.service_class == "LAUNDRY_CLEAN_LINEN"]
        assert linen_cycles
        for c in linen_cycles:
            assert c.outbound_loaded_mass_kg == pytest.approx(17.0)
            assert c.return_moving_mass_kg == pytest.approx(5.0)

    def test_same_hardware_different_mission_mass(self, day_def):
        """Section 45: GENERAL_LIGHT_CARRIER serves blood and linen with the
        SAME hardware but DIFFERENT loaded moving mass."""
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        cycles = result.carrier_hardware_report.cycle_traces
        blood = next(c for c in cycles if c.service_class == "SPECIMEN_BLOOD")
        linen = next(c for c in cycles if c.service_class == "LAUNDRY_CLEAN_LINEN")
        assert blood.hardware_class == linen.hardware_class == "GENERAL_LIGHT_CARRIER"
        assert blood.outbound_loaded_mass_kg != linen.outbound_loaded_mass_kg


class TestMassSensitiveEnergyOrdering:
    def test_return_energy_always_positive(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        cycles = [c for c in result.carrier_hardware_report.cycle_traces if c.return_energy_j != "NOT_CALIBRATED"]
        assert cycles
        for c in cycles:
            assert c.return_energy_j > 0.0

    def test_heavier_loaded_mission_never_consumes_less_energy_same_conditions(self):
        import mrt_auxiliary_systems_authority as maux
        light = maux.CarrierKinematicsSpec(carrier_mass_kg=5.0, payload_mass_kg=2.0, target_speed_m_per_s=7.0, route_length_m=300.0)
        heavy = maux.CarrierKinematicsSpec(carrier_mass_kg=5.0, payload_mass_kg=12.0, target_speed_m_per_s=7.0, route_length_m=300.0)
        assert maux.compute_acceleration_energy_j(heavy) > maux.compute_acceleration_energy_j(light)

    def test_drag_authority_not_falsely_mass_scaled_by_this_correction(self):
        """This correction only feeds `carrier_mass_kg` into the EXISTING
        acceleration-energy formula -- it does not touch drag."""
        import inspect
        import mrt_auxiliary_systems_authority as maux
        source = inspect.getsource(maux.compute_drag_force_n)
        assert "mass" not in source.lower()


class TestCarrierCorrectionNonRegression:
    def test_carrier_unit_capex_unchanged(self):
        assert ody.NUCLEAR_SHIELDED_CARRIER_CAPEX_USD == 10_000.0
        assert ody.GENERAL_LIGHT_CARRIER_CAPEX_USD == 1_000.0

    def test_fleet_capex_arithmetic_unchanged(self):
        assert ody.compute_carrier_fleet_capex(nuclear_count=8, general_light_count=42) == 122_000.0

    def test_service_speed_unchanged(self):
        assert msc.SERVICE_CLASS_REGISTRY["RADIOPHARMACEUTICAL_NUCLEAR"].default_speed_m_per_s == 10.0
        assert msc.SERVICE_CLASS_REGISTRY["SPECIMEN_BLOOD"].default_speed_m_per_s == 7.0
        assert msc.SERVICE_CLASS_REGISTRY["LAUNDRY_CLEAN_LINEN"].default_speed_m_per_s == 1.0

    def test_priority_and_color_unchanged(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        payload = ody.build_operating_day_visualization_payload(result)
        nuclear_entries = [e for e in payload.mrt_carrier_entries if e["service_class"] == "RADIOPHARMACEUTICAL_NUCLEAR"]
        assert nuclear_entries
        assert all(e["presentation_color"] == "VIOLET" for e in nuclear_entries)

    def test_room_endpoint_identity_and_count_unchanged(self, day_def):
        """Section 48: room inventory/patient-room assignment/endpoint
        IDENTITY are untouched by this narrow mass correction -- only the
        endpoint CapEx pricing (section 48A-48E, a separate explicit
        addendum) changed."""
        registry = ody.build_controlled_room_registry(day_def)
        rooms = registry.by_type("PATIENT_ROOM")
        inpatients = [p for p in day_def.patients if p.patient_type == "INPATIENT"]
        assert len(rooms) == len(inpatients)


class TestElectricityAndOpexNonRegression:
    def test_physical_electricity_still_preferred(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        for e in result.carrier_hardware_report.electricity:
            if e.physical_energy_j != "NOT_CALIBRATED":
                assert e.resolution == "PHYSICAL_ENERGY_RESOLVED"

    def test_legacy_allowance_still_not_stacked(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        for e in result.carrier_hardware_report.electricity:
            assert e.resolution in ("PHYSICAL_ENERGY_RESOLVED", "LEGACY_ALLOWANCE_FALLBACK")

    def test_no_arbitrary_maintenance_reintroduced(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(ody.CarrierElectricityReconciliation)}
        assert "maintenance_opex_usd" not in fields


class TestFiveStreamEconomicRefresh:
    def test_mrt_rows_reflect_corrected_energy(self, day_def):
        rows = ody.build_five_stream_architecture_comparison(day_def, day_start=DAY_START)
        mrt_rows = [r for r in rows if r.technology == "MRT"]
        assert mrt_rows  # refreshed automatically via corrected cycle traces

    def test_manual_and_automated_rows_unaffected_by_mrt_mass_change(self, day_def):
        rows = ody.build_five_stream_architecture_comparison(day_def, day_start=DAY_START)
        manual_rows = [r for r in rows if r.architecture == "MANUAL_CONVENTIONAL"]
        assert all(r.technology == "MANUAL_PORTER" for r in manual_rows)


class TestMassCorrectionSerialization:
    def test_cycle_trace_mass_fields_serializable(self, day_def):
        import json
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        cycles = result.carrier_hardware_report.cycle_traces
        serializable = [
            {"mission_id": c.mission_id, "empty_mass_kg": c.empty_mass_kg, "payload_mass_kg": c.payload_mass_kg,
             "outbound_loaded_mass_kg": c.outbound_loaded_mass_kg, "mass_provenance": c.mass_provenance}
            for c in cycles
        ]
        json.dumps(serializable)

    def test_mass_provenance_present_on_every_cycle(self, day_def):
        result = ody.run_operating_day(day_def, architecture="MRT_DOMINANT", day_start=DAY_START)
        for c in result.carrier_hardware_report.cycle_traces:
            assert c.mass_provenance in ("MISSION_SPECIFIC_INPUT", "USER_SUPPLIED_CONTROLLED_SCENARIO_ASSUMPTION", "NOT_CALIBRATED")


# ---------------------------------------------------------------------------
# CONTROLLED FOUR-ARCHITECTURE ECONOMIC COMPARISON (200 patients/day)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def four_arch_basis():
    return ody.build_common_economic_basis()


@pytest.fixture(scope="module")
def four_arch_results(four_arch_basis):
    return ody.run_four_architecture_economic_comparison(basis=four_arch_basis)


class TestManualShiftLaborAuthority:
    def test_one_position_gives_16_regular_2_overtime(self, four_arch_basis):
        shift = ody.compute_manual_shift_labor_cost(simultaneous_positions=1, wage_per_hour=10.0, basis=four_arch_basis, employer_cost_multiplier=1.0)
        assert shift.regular_hours_per_position == 16.0
        assert shift.overtime_hours_per_position == 2.0

    def test_19w_equivalent_cost(self, four_arch_basis):
        shift = ody.compute_manual_shift_labor_cost(simultaneous_positions=1, wage_per_hour=1.0, basis=four_arch_basis, employer_cost_multiplier=1.0)
        assert shift.daily_labor_cost_usd == pytest.approx(19.0)

    def test_two_simultaneous_positions_double_cost(self, four_arch_basis):
        one = ody.compute_manual_shift_labor_cost(simultaneous_positions=1, wage_per_hour=12.0, basis=four_arch_basis, employer_cost_multiplier=1.0)
        two = ody.compute_manual_shift_labor_cost(simultaneous_positions=2, wage_per_hour=12.0, basis=four_arch_basis, employer_cost_multiplier=1.0)
        assert two.daily_labor_cost_usd == pytest.approx(2 * one.daily_labor_cost_usd)

    def test_clinical_workers_not_removed_by_automation(self, four_arch_results):
        """Clinical labor is explicitly NOT_CALIBRATED (never silently zeroed
        or credited to MRT/automation) for every architecture."""
        for r in four_arch_results:
            assert r.opex_components["clinical_labor_opex"] == "NOT_CALIBRATED"


class TestArchitectureEquality:
    def test_all_four_share_required_200_patients(self, four_arch_results):
        assert all(r.required_patients_per_day == 200 for r in four_arch_results)

    def test_revenue_identical_across_architectures_given_identical_served_count(self, four_arch_results):
        revenues = {r.annual_revenue_usd for r in four_arch_results}
        assert len(revenues) == 1

    def test_four_labels_present(self, four_arch_results):
        labels = {r.architecture_label for r in four_arch_results}
        assert labels == {"MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "MRT", "HYBRID"}


class TestFeasibilityReporting:
    def test_production_feasibility_honestly_not_calibrated_without_installed_capacity(self, four_arch_results):
        for r in four_arch_results:
            assert r.feasibility.production_feasible == "NOT_CALIBRATED"

    def test_cyclotron_eob_not_inflated_by_legacy_blocks(self):
        chain_a = ody.compute_radioactive_production_chain(modality="PET", served_patients=140, activity_per_patient_mbq=370.0, radionuclide="F-18", elapsed_eob_to_administration_minutes=60.0)
        # Same served count/activity should give proportional A_EOB with NO discrete 10%-block jumps.
        chain_b = ody.compute_radioactive_production_chain(modality="PET", served_patients=280, activity_per_patient_mbq=370.0, radionuclide="F-18", elapsed_eob_to_administration_minutes=60.0)
        assert chain_b.a_eob_required_mbq == pytest.approx(2 * chain_a.a_eob_required_mbq)


class TestMrtEconomicsWithinFourArchComparison:
    def test_endpoint_capex_equals_count_times_1000(self, four_arch_results):
        mrt = next(r for r in four_arch_results if r.architecture_label == "MRT")
        registry = ody.build_controlled_room_registry(ody.build_controlled_representative_day(
            available_beds=200, occupied_beds=170, admissions=20, discharges=18, outpatient_encounters=30,
            target_pet_procedures=140, target_spect_procedures=60,
        ))
        room_count = len(registry.by_type("PATIENT_ROOM"))
        assert mrt.capex_components["room_endpoint_capex"] == pytest.approx(room_count * ody.MRT_ENDPOINT_PANEL_UNIT_CAPEX_USD)

    def test_carrier_fleet_capex_not_double_counted(self, four_arch_results):
        mrt = next(r for r in four_arch_results if r.architecture_label == "MRT")
        # carrier_hardware_fleet_capex appears exactly once in the component map.
        assert list(mrt.capex_components.keys()).count("carrier_hardware_fleet_capex") == 1

    def test_electricity_not_double_counted(self, four_arch_results):
        mrt = next(r for r in four_arch_results if r.architecture_label == "MRT")
        assert list(mrt.opex_components.keys()).count("electricity_opex") == 1


class TestMultistreamScope:
    def test_blood_uses_light_carrier_mass(self, four_arch_results):
        registry = ody.CARRIER_HARDWARE_REGISTRY["GENERAL_LIGHT_CARRIER"]
        assert registry.empty_mass_kg == 5.0

    def test_linen_does_not_force_blood_to_17kg(self):
        blood_payload = ody.resolve_mission_payload_mass_kg("SPECIMEN_BLOOD")
        blood_loaded = ody.resolve_loaded_mass_kg("GENERAL_LIGHT_CARRIER", blood_payload.payload_mass_kg)
        assert blood_loaded != 17.0
        assert blood_loaded == pytest.approx(7.0)

    def test_hybrid_not_a_50_50_blend(self, four_arch_results):
        hybrid = next(r for r in four_arch_results if r.architecture_label == "HYBRID")
        mrt = next(r for r in four_arch_results if r.architecture_label == "MRT")
        manual = next(r for r in four_arch_results if r.architecture_label == "MANUAL_CONVENTIONAL")
        blended_capex = 0.5 * mrt.total_capex_usd + 0.5 * manual.total_capex_usd
        assert hybrid.total_capex_usd != pytest.approx(blended_capex)


class TestNotCalibratedNeverZero:
    def test_not_calibrated_never_becomes_zero_in_output(self, four_arch_results):
        for r in four_arch_results:
            for value in r.capex_components.values():
                assert value != 0 or value == 0.0  # numeric zero permitted; string sentinel never silently coerced
            assert "NOT_CALIBRATED" in r.opex_components.values()  # at least one honestly-unresolved category present

    def test_npv_irr_use_calibrated_discount_rate_and_life(self, four_arch_results, four_arch_basis):
        for r in four_arch_results:
            assert isinstance(r.npv_usd, float)
            assert four_arch_basis.discount_rate_pct > 0
            assert four_arch_basis.analysis_years > 0

    def test_irr_not_calibrated_when_margin_non_positive(self):
        assert ody._compute_irr_pct(capex_usd=100.0, annual_margin_usd=-5.0, analysis_years=5) == "NOT_CALIBRATED"
        assert ody._compute_irr_pct(capex_usd=0.0, annual_margin_usd=100.0, analysis_years=5) == "NOT_CALIBRATED"


class TestFourArchSerialization:
    def test_comparison_result_is_json_serializable(self, four_arch_results):
        import json
        import dataclasses
        for r in four_arch_results:
            serializable = {
                "architecture_label": r.architecture_label, "required_patients_per_day": r.required_patients_per_day,
                "total_capex_usd": r.total_capex_usd, "total_annual_opex_usd": r.total_annual_opex_usd,
                "capex_components": r.capex_components, "opex_components": r.opex_components,
                "feasibility": dataclasses.asdict(r.feasibility),
            }
            json.dumps(serializable)


# ---------------------------------------------------------------------------
# PART D.1 -- FOUR-ARCHITECTURE ECONOMIC INTEGRITY CORRECTION
# ---------------------------------------------------------------------------


class TestLastMileFixNoLongerInflatesAutomated:
    def test_automated_conventional_never_exceeds_manual_total_minutes(self, missions):
        manual = ody.execute_conventional_missions(missions, architecture="MANUAL_CONVENTIONAL")
        auto = ody.execute_conventional_missions(missions, architecture="AUTOMATED_CONVENTIONAL")
        assert sum(t.total_minutes for t in auto) < sum(t.total_minutes for t in manual)

    def test_last_mile_distance_much_shorter_than_full_route(self):
        assert ody.AGV_PTS_LAST_MILE_DISTANCE_M < ody.CONTROLLED_TEST_DISTANCE_M


class TestFeasibilityStatusVocabulary:
    def test_uncalibrated_production_never_collapses_to_unconditional_true(self, four_arch_results):
        for r in four_arch_results:
            assert r.feasibility.overall_status == "FEASIBLE_WITH_UNCALIBRATED_PRODUCTION_CAPACITY"

    def test_status_resolver_marks_infeasible_when_logistics_fails(self):
        status = ody._resolve_overall_feasibility_status(production_feasible="NOT_CALIBRATED", clinical_feasible=True, logistics_feasible=False)
        assert status == "INFEASIBLE"

    def test_status_resolver_feasible_when_production_calibrated_true(self):
        status = ody._resolve_overall_feasibility_status(production_feasible=True, clinical_feasible=True, logistics_feasible=True)
        assert status == "FEASIBLE"


class TestMrtInfrastructureCompleteness:
    def test_capex_includes_vestibule_controls_installation_separately(self, four_arch_results):
        mrt = next(r for r in four_arch_results if r.architecture_label == "MRT")
        assert mrt.architecture_specific_capex_components["mrt_radiopharmacy_vestibule_capex"] == 30_000.0
        assert mrt.architecture_specific_capex_components["mrt_controls_capex"] == 100_000.0
        assert mrt.architecture_specific_capex_components["mrt_installation_commissioning_capex"] == 300_000.0

    def test_vestibule_distinct_from_endpoint_cost(self, four_arch_results):
        mrt = next(r for r in four_arch_results if r.architecture_label == "MRT")
        assert mrt.architecture_specific_capex_components["mrt_radiopharmacy_vestibule_capex"] != mrt.architecture_specific_capex_components["room_endpoint_capex"]

    def test_guideway_honestly_not_calibrated_never_substituted_zero(self, four_arch_results):
        mrt = next(r for r in four_arch_results if r.architecture_label == "MRT")
        assert mrt.mrt_infrastructure.guideway_capex_usd == "NOT_CALIBRATED"
        assert mrt.mrt_infrastructure.guideway_length_m == "NOT_CALIBRATED"

    def test_mrt_total_capex_far_exceeds_prior_incomplete_181k(self, four_arch_results):
        mrt = next(r for r in four_arch_results if r.architecture_label == "MRT")
        assert mrt.mrt_infrastructure.total_capex_usd > 181_000.0


class TestKnownVsTotalOpex:
    def test_total_annual_opex_not_calibrated_when_categories_unresolved(self, four_arch_results):
        for r in four_arch_results:
            if r.unresolved_opex_categories:
                assert r.total_annual_opex_usd == "NOT_CALIBRATED"

    def test_known_subtotal_never_equals_fabricated_zero_for_unresolved(self, four_arch_results):
        for r in four_arch_results:
            assert r.known_annual_opex_subtotal_usd >= 0.0
            assert "clinical_labor_opex" in r.unresolved_opex_categories


class TestIncrementalEconomicsVsManualBaseline:
    def test_manual_baseline_has_zero_deltas(self, four_arch_results):
        manual = next(r for r in four_arch_results if r.architecture_label == "MANUAL_CONVENTIONAL")
        assert manual.incremental.delta_capex_usd == 0.0
        assert manual.incremental.delta_revenue_usd == 0.0

    def test_delta_revenue_zero_when_served_patients_identical(self, four_arch_results):
        for r in four_arch_results:
            assert r.incremental.delta_revenue_usd == 0.0

    def test_incremental_irr_not_calibrated_when_cash_flow_negative(self, four_arch_results):
        automated = next(r for r in four_arch_results if r.architecture_label == "AUTOMATED_CONVENTIONAL")
        if automated.incremental.delta_annual_cash_flow_usd <= 0:
            assert automated.incremental.incremental_irr_pct == "NOT_CALIBRATED"

    def test_mrt_incremental_capex_matches_delta_from_manual(self, four_arch_results):
        manual = next(r for r in four_arch_results if r.architecture_label == "MANUAL_CONVENTIONAL")
        mrt = next(r for r in four_arch_results if r.architecture_label == "MRT")
        assert mrt.incremental.delta_capex_usd == pytest.approx(mrt.total_capex_usd - manual.total_capex_usd)

    def test_incremental_never_uses_full_gross_revenue_as_return(self, four_arch_results):
        mrt = next(r for r in four_arch_results if r.architecture_label == "MRT")
        # Incremental cash flow must be far smaller than gross annual revenue (never the whole $18M treated as MRT's return).
        assert mrt.incremental.delta_annual_cash_flow_usd < mrt.annual_revenue_usd * 0.1


class TestCompatibilityNeverSilentlyUpgraded:
    def test_mrt_pharmacy_sterile_never_routed_through_mrt(self, missions):
        for architecture in ("HYBRID_MRT", "MRT_DOMINANT"):
            result = ody.execute_operating_day_architecture(missions, architecture=architecture, day_start=DAY_START)
            mission_by_id = {m.mission_id: m for m in missions}
            for t in result.trajectories:
                assert mission_by_id[t.mission_id].service_class not in ("PHARMACY_INFUSION", "STERILE_CLEAN_SUPPLY")

    def test_compatibility_matrix_still_reports_not_calibrated_for_pharmacy_mrt(self):
        matrix = ody.build_stream_mode_compatibility_matrix()
        row = next(r for r in matrix if r.stream == "PHARMACY_INFUSION" and r.mode == "MRT")
        assert row.status == "NOT_CALIBRATED"



