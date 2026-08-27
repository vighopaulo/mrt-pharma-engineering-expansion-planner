import whole_oncology_four_architecture_optimization as w
from dataclasses import replace

baseline = w.build_common_project_baseline()
all_floors = frozenset(range(1, baseline.geometry.floor_count + 1))

mrt_c, conv_c = w.resolve_nuclear_floor_envelopes(baseline, mrt_floors=all_floors)
print("Default threshold 0.9: MRT retention-feasible floors:", sorted(mrt_c.retention_feasible_floors))

strict_assumptions = replace(baseline.assumptions, minimum_release_to_administration_retention_fraction=0.999)
strict_baseline = replace(baseline, assumptions=strict_assumptions)
mrt_c2, conv_c2 = w.resolve_nuclear_floor_envelopes(strict_baseline, mrt_floors=all_floors)
print("Strict threshold 0.999: MRT retention-feasible floors:", sorted(mrt_c2.retention_feasible_floors))
print("Strict threshold 0.999: MRT dropped floors:", sorted(mrt_c2.dropped_floors))
active_before = sorted(mrt_c.active_floors)
active_after = sorted(mrt_c2.active_floors)
print("Active floors before:", active_before)
print("Active floors after:", active_after)
changed = active_before != active_after
print("Active floors changed:", changed)
