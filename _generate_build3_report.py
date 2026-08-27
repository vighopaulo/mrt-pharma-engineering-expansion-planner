"""Build-3 report/CSV data generator (throwaway script, deleted after use).
Executes the REAL Representative Tuesday for all four architectures and
extracts live data -- never hand-typed mission counts/totals."""
from __future__ import annotations

import csv
import os
from datetime import datetime

import operational_day_orchestrator as ody
import mrt_service_class_authority as msc

OUT_DIR = "OPERATING_DAY_FINAL_CLOSURE_BUILD3_tables"
os.makedirs(OUT_DIR, exist_ok=True)


def write_csv(name, header, rows):
    with open(os.path.join(OUT_DIR, name), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"wrote {name}: {len(rows)} rows")


day_def = ody.build_controlled_representative_day()
day_start = datetime.combine(day_def.day, datetime.min.time()).replace(hour=7)
print("day_def.day:", day_def.day, "seed:", day_def.seed)
print("census:", day_def.census)
print("logistics_loads:", len(day_def.logistics_loads))

ARCHS = ("MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "HYBRID_MRT", "MRT_DOMINANT")
results = {}
for arch in ARCHS:
    results[arch] = ody.run_operating_day(day_def, architecture=arch, day_start=day_start)
    r = results[arch]
    print(f"\n=== {arch} ===")
    print("mission_count:", r.mission_count, "by_class:", dict(r.missions_by_service_class))
    print("on_time:", r.completed_on_time_count, "late:", r.completed_late_count, "unmet:", r.unmet_count,
          "not_calibrated:", r.not_calibrated_count, "conventional_completed:", r.conventional_completed_count)
    print("event_journal:", len(r.event_journal), "validation:", r.validation_status, "gaps:", r.calibration_gaps)
    chr_ = r.carrier_hardware_report
    if chr_:
        print("carrier fleet: nuclear=%d general=%d capex=%.2f blocked=%d" % (
            chr_.nuclear_shielded_carrier_count, chr_.general_light_carrier_count, chr_.carrier_fleet_capex_usd, chr_.blocked_mission_count))

# ---- Service class registry (colors/priority) ----
print("\n=== SERVICE CLASS REGISTRY ===")
for sc, profile in msc.SERVICE_CLASS_REGISTRY.items():
    print(sc, profile.activity_status, profile.default_priority, profile.default_speed_m_per_s, profile.configured_active_color, profile.effective_display_color())

# ---- CSV: 01 build identity ----
write_csv("01_build_identity.csv", ["Item", "Value"], [
    ["Build", "Build 3 -- Operating-Day Final Closure"],
    ["Purpose", "Make the operating-day simulation (Representative Tuesday) execute a coherent, authoritative, five-stream, four-architecture hospital day suitable for future NVIDIA Live 3D consumption"],
    ["Starting baseline", "Build 2 -- 2361 passed, 3 deselected, 0 failed, 2368.25s (0:39:28)"],
    ["Files modified", "operational_day_orchestrator.py (event journal closure)"],
    ["Files added", "test_operating_day_journal_and_identity_closure.py, OPERATING_DAY_FINAL_CLOSURE_BUILD3_REPORT.md + tables/"],
    ["Authorities reused", "operational_day_orchestrator (run_operating_day, execute_operating_day_architecture, build_controlled_representative_day), mrt_service_class_authority, conventional_transport_authority, canonical_spatial_authority, oncology_pet_spect_scenario, general_oncology_logistics"],
    ["Authorities modified", "operational_day_orchestrator.run_operating_day (merged whole-day event journal); validate_operating_day_result (orphan-journal check extended to conventional mission IDs)"],
    ["Authorities added", "operational_day_orchestrator.build_conventional_mission_journal"],
    ["Genuine gap found and closed", "Event journal was MRT-only (0 entries for MANUAL_CONVENTIONAL); now whole-day (66-107 entries across all 4 architectures)"],
    ["Genuine gap found and NOT closed (disclosed)", "operational_day_orchestrator.py implements its own production/clinical/mission scheduling, parallel to production_clinical_schedule.py's 'sole authoritative' scheduler used by whole_oncology_four_architecture_optimization.py/hybrid_optimization.py/decision_pipeline.py -- pre-existing from Parts A-D of this session, NOT introduced by Build 3, disclosed as DUPLICATED_AUTHORITY_TECH_DEBT rather than redesigned under time pressure"],
])

# ---- CSV 07: five-stream summary ----
STREAM_ROWS = []
for sc, profile in msc.SERVICE_CLASS_REGISTRY.items():
    if profile.activity_status != "ACTIVE":
        continue
    counts = {arch: results[arch].missions_by_service_class.get(sc, 0) for arch in ARCHS}
    STREAM_ROWS.append([sc, profile.display_name, profile.default_priority, profile.default_speed_m_per_s, profile.configured_active_color,
                         counts["MANUAL_CONVENTIONAL"], counts["AUTOMATED_CONVENTIONAL"], counts["HYBRID_MRT"], counts["MRT_DOMINANT"]])
write_csv("07_five_stream_summary.csv", ["Service Class", "Display Name", "Default Priority", "Default Speed (m/s)", "Color",
                                          "Missions (Manual)", "Missions (Automated)", "Missions (Hybrid)", "Missions (MRT Dominant)"], STREAM_ROWS)

# ---- CSV 06: all missions (per architecture) ----
for arch in ARCHS:
    r = results[arch]
    rows = []
    mrt_traj = {t.mission_id: t for t in r.trajectory_set.mrt_trajectories}
    conv_traces = {t.mission_id: t for t in r.trajectory_set.conventional_traces}
    for e in r.event_journal:
        pass
    # Build a per-mission row from whichever trace exists
    all_mission_ids = set(mrt_traj) | set(conv_traces)
    for mid in sorted(all_mission_ids):
        if mid in mrt_traj:
            t = mrt_traj[mid]
            rows.append([mid, t.service_class, "MRT", t.carrier_id, t.start_time_minutes, t.end_time_minutes, t.status])
        else:
            t = conv_traces[mid]
            rows.append([mid, "?", t.resource_type, t.resource_type, "-", t.total_minutes, t.route_status])
    write_csv(f"06_all_missions_{arch}.csv", ["Mission ID", "Service Class", "Mode", "Resource", "Start (min or -)", "End/Duration (min)", "Status"], rows)
    print(f"{arch}: total mission rows in CSV = {len(rows)}")

print("\nDONE PHASE 1")

# =====================================================================
# PHASE 2: REQUIRED CONTROL TRACES
# =====================================================================

# ---- One nuclear patient trace (MRT_DOMINANT, richest execution) ----
mrt_result = results["MRT_DOMINANT"]
nuclear_journal = [e for e in mrt_result.event_journal if e.service_class == "RADIOPHARMACEUTICAL_NUCLEAR"]
first_patient_id = next((e.patient_id for e in nuclear_journal if e.patient_id != "NOT_APPLICABLE"), None)
print("\n=== NUCLEAR PATIENT TRACE (patient_id=%s) ===" % first_patient_id)
patient_events = [e for e in nuclear_journal if e.patient_id == first_patient_id]
for e in sorted(patient_events, key=lambda x: x.simulation_time):
    print(e.simulation_time, e.mission_id, e.old_state, "->", e.new_state, e.origin, "->", e.destination, e.reason)

patient_rows = []
for e in sorted(patient_events, key=lambda x: x.simulation_time):
    patient_rows.append([first_patient_id, e.mission_id, e.simulation_time.isoformat(), e.old_state, e.new_state, e.origin, e.destination, e.resource_id, e.reason])
write_csv("14_nuclear_patient_trace.csv", ["Patient ID", "Mission ID", "Time", "Old State", "New State", "Origin", "Destination", "Resource", "Reason"], patient_rows)

# ---- One room trace ----
registry = ody.build_controlled_room_registry(day_def)
room_ids = [r.mrtway_object_id for r in registry.by_type("PATIENT_ROOM")]
sample_room = room_ids[0] if room_ids else None
print("\n=== ROOM TRACE (room=%s) ===" % sample_room)
room_events = [e for e in mrt_result.event_journal if e.origin == sample_room or e.destination == sample_room]
for e in sorted(room_events, key=lambda x: x.simulation_time):
    print(e.simulation_time, e.mission_id, e.service_class, e.old_state, "->", e.new_state)
room_rows = [[sample_room, e.mission_id, e.service_class, e.simulation_time.isoformat(), e.old_state, e.new_state, e.origin, e.destination] for e in sorted(room_events, key=lambda x: x.simulation_time)]
write_csv("15_room_trace.csv", ["Room ID", "Mission ID", "Service Class", "Time", "Old State", "New State", "Origin", "Destination"], room_rows)
print("total rooms in registry:", len(room_ids))

# ---- One MRT carrier trace ----
cts = mrt_result.carrier_hardware_report.cycle_traces
sample_carrier_id = cts[0].carrier_id if cts else None
carrier_missions = [t for t in cts if t.carrier_id == sample_carrier_id]
print("\n=== MRT CARRIER TRACE (carrier=%s), %d missions ===" % (sample_carrier_id, len(carrier_missions)))
carrier_rows = []
for t in carrier_missions:
    print(t.mission_id, t.service_class, t.payload_mass_kg, t.outbound_loaded_mass_kg, t.outbound_energy_j, t.return_moving_mass_kg, t.return_energy_j)
    carrier_rows.append([sample_carrier_id, t.hardware_class, t.mission_id, t.service_class, t.empty_mass_kg, t.payload_mass_kg, t.outbound_loaded_mass_kg,
                          t.outbound_distance_m, t.outbound_time_minutes, t.outbound_energy_j, t.return_moving_mass_kg, t.return_distance_m, t.return_time_minutes, t.return_energy_j, t.return_mode])
write_csv("16_mrt_carrier_trace.csv", ["Carrier ID", "Hardware Class", "Mission ID", "Service Class", "Empty Mass (kg)", "Payload Mass (kg)", "Outbound Loaded Mass (kg)",
                                        "Outbound Distance (m)", "Outbound Time (min)", "Outbound Energy (J)", "Return Moving Mass (kg)", "Return Distance (m)", "Return Time (min)", "Return Energy (J)", "Return Mode"], carrier_rows)
total_missions_carrier = len(carrier_missions)
total_loaded_distance = sum(t.outbound_distance_m for t in carrier_missions)
total_empty_distance = sum(t.return_distance_m for t in carrier_missions)
total_energy = sum(t.outbound_energy_j + t.return_energy_j for t in carrier_missions)
print("totals: missions=%d loaded_dist=%.1f empty_dist=%.1f total_energy=%.1f" % (total_missions_carrier, total_loaded_distance, total_empty_distance, total_energy))

# ---- One Automated Conventional mission trace ----
ac_result = results["AUTOMATED_CONVENTIONAL"]
ac_traces = ac_result.trajectory_set.conventional_traces
ac_sample = next((t for t in ac_traces if t.resource_type in ("AGV_AMR", "PTS")), None)
print("\n=== AUTOMATED CONVENTIONAL MISSION TRACE ===")
print(ac_sample)
ac_journal_entries = [e for e in ac_result.event_journal if e.mission_id == ac_sample.mission_id] if ac_sample else []
for e in ac_journal_entries:
    print(e.simulation_time, e.old_state, "->", e.new_state, e.reason)
if ac_sample:
    write_csv("17_automated_conventional_trace.csv",
              ["Mission ID", "Resource Type", "Total Minutes", "Residual Last-Mile Minutes", "Route Status", "Event Time", "Old State", "New State", "Reason"],
              [[ac_sample.mission_id, ac_sample.resource_type, ac_sample.total_minutes, ac_sample.residual_last_mile_minutes, ac_sample.route_status,
                e.simulation_time.isoformat(), e.old_state, e.new_state, e.reason] for e in ac_journal_entries])

# ---- One Manual Conventional mission trace ----
manual_result = results["MANUAL_CONVENTIONAL"]
manual_traces = manual_result.trajectory_set.conventional_traces
manual_sample = manual_traces[0] if manual_traces else None
print("\n=== MANUAL CONVENTIONAL MISSION TRACE ===")
print(manual_sample)
manual_journal_entries = [e for e in manual_result.event_journal if e.mission_id == manual_sample.mission_id] if manual_sample else []
for e in manual_journal_entries:
    print(e.simulation_time, e.old_state, "->", e.new_state, e.origin, "->", e.destination)
if manual_sample:
    write_csv("18_manual_trace.csv",
              ["Mission ID", "Resource Type", "Total Minutes", "Route Status", "Event Time", "Old State", "New State", "Origin", "Destination"],
              [[manual_sample.mission_id, manual_sample.resource_type, manual_sample.total_minutes, manual_sample.route_status,
                e.simulation_time.isoformat(), e.old_state, e.new_state, e.origin, e.destination] for e in manual_journal_entries])

# ---- One blood/specimen mission trace ----
blood_journal = [e for e in manual_result.event_journal if e.service_class == "SPECIMEN_BLOOD"]
blood_mission_id = blood_journal[0].mission_id if blood_journal else None
print("\n=== BLOOD/SPECIMEN MISSION TRACE (mission=%s) ===" % blood_mission_id)
blood_events = [e for e in manual_result.event_journal if e.mission_id == blood_mission_id]
for e in blood_events:
    print(e.simulation_time, e.patient_id, e.old_state, "->", e.new_state, e.origin, "->", e.destination)
write_csv("19_blood_specimen_trace.csv",
          ["Mission ID", "Patient ID", "Time", "Old State", "New State", "Origin", "Destination", "Service Class"],
          [[e.mission_id, e.patient_id, e.simulation_time.isoformat(), e.old_state, e.new_state, e.origin, e.destination, e.service_class] for e in blood_events])

# ---- One linen mission trace ----
linen_journal = [e for e in manual_result.event_journal if e.service_class == "LAUNDRY_CLEAN_LINEN"]
linen_mission_id = linen_journal[0].mission_id if linen_journal else None
print("\n=== LINEN MISSION TRACE (mission=%s) ===" % linen_mission_id)
linen_events = [e for e in manual_result.event_journal if e.mission_id == linen_mission_id]
for e in linen_events:
    print(e.simulation_time, e.patient_id, e.old_state, "->", e.new_state, e.origin, "->", e.destination)
write_csv("20_linen_trace.csv",
          ["Mission ID", "Patient ID", "Time", "Old State", "New State", "Origin", "Destination", "Service Class"],
          [[e.mission_id, e.patient_id, e.simulation_time.isoformat(), e.old_state, e.new_state, e.origin, e.destination, e.service_class] for e in linen_events])

print("\nDONE PHASE 2")

