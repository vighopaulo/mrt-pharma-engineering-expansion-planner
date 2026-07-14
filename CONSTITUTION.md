# MRT Pharma™ Decision-Support Digital Twin V2
## Constitution and Complete Engineering Specification

### 1. Purpose
The software compares two ways of meeting one common radiopharmaceutical imaging target: Conventional Expansion and MRT Pharma Hybrid. It must be capable of recommending either option or neither. It is a planning digital twin, not a real-time patient or operations twin.

### 2. Governing sequence
Clinical objective → engineering constraints → capacity calculation → independent architecture optimization → finance → hospital-priority decision score → recommendation → diagnostics.

### 3. Project modes
**Expansion:** existing patients, scanners, rooms, and batches may be positive. Costs and revenue are incremental.
**Greenfield:** current patients, scanners, injection rooms, uptake rooms, and batches are automatically zero, visually disabled, and normalized to zero in the model. No equation may divide by current capacity.

### 4. Shared target
Both architectures are evaluated against the same target patients/day. Served patients are capped at the target. Reserve capacity is reported but not automatically monetized.

### 5. Physical capacity
Installed capacity is the minimum of usable-dose, scanner, injection, and uptake capacity. An option is physically feasible only when installed capacity meets the target.

### 6. Production
The input is a planning reference usable released-dose capacity per batch before internal transport decay. Each architecture independently searches production increase and batches/day. Batch count must fit the daily production window.

### 7. Decay
Retained activity is `2 ** (-transport_time / half_life)`. Conventional and MRT transport times are evaluated separately.

### 8. Scanners
Scanner capacity is `count × operating_minutes × availability / cycle_time`. MRT does not eliminate scanner requirements.

### 9. Rooms
Dedicated room capacity is `count × operating_minutes / service_time`. MRT may combine centralized room capacity with optional MRT-enabled inpatient-room capacity. Existing-room retrofit and new-room construction are separate costs. A room is counted once.

### 10. MRT endpoints
Endpoints follow the actual carrier path. Radiopharmacy, connected administration rooms, optional connected uptake rooms, MRT inpatient rooms, return/disposal, and other declared support points may be included. Scanners are not automatic endpoints.

### 11. Economics
Expansion uses incremental economics. Greenfield uses total project economics because the current baseline is zero. Annual revenue is `(target-current) × operating_days × contribution`. NCF, NPV, ROI, and payback are calculated identically for both architectures.

### 12. Batch cost
Additional recurring daily batches are `max(0, future_batches-current_batches)`. No existing batch is charged again in Expansion mode.

### 13. Internal optimization
Each architecture is optimized independently. Candidate ranking is: feasibility, positive NPV, highest NPV, lower CapEx, higher ROI, shorter payback. Hospital priorities never alter physics.

### 14. Feasibility gates
To compete in the final decision an architecture must meet target capacity, remain within budget, have positive annual net cash flow, and have positive NPV. An infeasible architecture cannot win through scoring.

### 15. Hospital priorities
The hospital chooses three distinct priorities. Priority 1 receives 30%, Priority 2 receives 20%, Priority 3 receives 15%, and the remaining 35% is shared equally among unselected metrics.

Available priorities:
- Net Present Value
- Lowest Capital Expenditure
- Highest ROI
- Fastest Payback
- Lowest Annual OpEx
- Highest Activity Retention
- Highest Reserve Capacity
- Greatest Batch Flexibility
- Lowest Production Increase
- Fewest Additional Dedicated Rooms
- Lowest Logistics Labor Burden
- Highest Resilience

### 16. Two conclusions
The model reports a **Financial Winner** based on NPV and an **Overall Recommendation** based on the selected hospital profile. If they differ, the software says so.

### 17. Sensitivity
The selected profile is compared with Financial Only, Capital Constrained, and Balanced profiles. Recommendation instability must be visible.

### 18. UI doctrine
The UI must use named arguments, reset and disable current-state fields in Greenfield, validate before running, show compact cards first, detailed comparison in expanders, weights, diagnostics, sensitivity, search statistics, and CSV/Excel exports.

### 19. Architecture
Domain objects, engineering, finance, optimization, decision scoring, diagnostics, and Streamlit presentation must be separated.

### 20. Required truth conditions
Tests must prove Greenfield zeros, no division by zero, Conventional can win, MRT can win, neither can win, batch baseline logic works, equal target revenue is preserved, endpoints are not double counted, and priority weights sum to one.

### 21. Governing principle
This is not an advocacy calculator. The recommendation must emerge from declared assumptions, physics, constraints, economics, and hospital priorities.
