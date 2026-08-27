import operational_day_orchestrator as ody
from datetime import datetime

day_def = ody.build_controlled_representative_day()
print("day_def.day:", day_def.day, "seed:", day_def.seed)
print("patients:", len(day_def.patients))
print("census:", day_def.census)
print("logistics_loads:", len(day_def.logistics_loads))
print("stat_blood_patient_id:", day_def.stat_blood_patient_id)

day_start = datetime.combine(day_def.day, datetime.min.time()).replace(hour=7)
for arch in ("MANUAL_CONVENTIONAL", "AUTOMATED_CONVENTIONAL", "HYBRID_MRT", "MRT_DOMINANT"):
    result = ody.run_operating_day(day_def, architecture=arch, day_start=day_start)
    print(f"\n=== {arch} ===")
    print("mission_count:", result.mission_count, "missions_by_service_class:", dict(result.missions_by_service_class))
    print("on_time:", result.completed_on_time_count, "late:", result.completed_late_count, "unmet:", result.unmet_count, "not_calibrated:", result.not_calibrated_count, "conventional_completed:", result.conventional_completed_count)
    print("event_journal entries:", len(result.event_journal))
    print("validation_status:", result.validation_status, "calibration_gaps:", result.calibration_gaps)
    print("carrier_hardware_report:", result.carrier_hardware_report)
