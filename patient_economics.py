"""Patient Economic Episode Authority.

GOVERNANCE (sections 31-42, 67-71): introduces `PatientEconomicEpisode`,
distinct from `LogisticsDemand` (general_oncology_logistics.py) and the
nuclear `NuclearProcedureAssignment` (oncology_pet_spect_scenario.py) --
economics compose ON TOP of those, never duplicating patient identity.

AUDITED EXISTING VALUE (section 68, mandatory before any change): this
repository's authoritative nuclear scan revenue assumption, already used
throughout every campus/oncology benchmark this session
(`spatial_benchmark._base_assumptions()`), is `revenue_per_scan=2000.0`
(USD/scan) -- NOT the bare `PlannerAssumptions()` class default (300.0),
which is a different, older/simpler-planner default never used by the
campus/oncology benchmark family. This module PRESERVES the audited 2000.0
value exactly (`CONTROLLED_SCAN_REVENUE_ASSUMPTION`, provenance
`spatial_benchmark._base_assumptions`) and does NOT silently overwrite it.

Reuses -- never duplicates -- `study_scope.py`'s OPERATIONAL_ONLY/
CAPITAL_PLANNING authority for any CapEx composed alongside patient economics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Mapping, Sequence

PatientType = Literal["INPATIENT", "OUTPATIENT"]
PaymentContext = Literal["SEPARATELY_PAYABLE", "BUNDLED_IN_INPATIENT_EPISODE"]
EconomicMode = Literal["COST_ONLY", "REVENUE_AWARE"]
RevenueBasis = Literal[
    "PAYMENT_CALIBRATED", "CONTROLLED_EPISODE_VALUE", "COST_ONLY", "CONTROLLED_SCAN_REVENUE_ASSUMPTION", "NOT_CALIBRATED",
]

AUDITED_NUCLEAR_SCAN_REVENUE_USD = 2000.0
"""Section 37/68: the repository's ACTUAL authoritative value
(`spatial_benchmark._base_assumptions().revenue_per_scan`), audited and
preserved exactly -- not invented, not silently changed."""
AUDITED_NUCLEAR_SCAN_REVENUE_PROVENANCE = "spatial_benchmark._base_assumptions (audited existing repository value, section 68)"

CONTROLLED_ONCOLOGY_INPATIENT_EPISODE_VALUE_2026 = 30000.0
"""Project benchmark assumption for the primary controlled oncology inpatient
episode -- NOT claimed to be a universal U.S. reimbursement rate. User-
overridable (every builder accepting this value exposes it as a parameter),
sensitivity-testable (see `INPATIENT_EPISODE_VALUE_SENSITIVITY_USD`), and
provenance-tagged as `CONTROLLED_EPISODE_VALUE`."""
CONTROLLED_ONCOLOGY_INPATIENT_EPISODE_VALUE_PROVENANCE = "CONTROLLED_ONCOLOGY_INPATIENT_EPISODE_VALUE_2026 (project benchmark assumption)"

INPATIENT_EPISODE_VALUE_SENSITIVITY_USD: tuple[float, ...] = (20000.0, 30000.0, 40000.0)
"""Minimum required sensitivity band around the primary $30,000 benchmark --
30000 remains the primary value; the optimizer must never hard-code it."""

NOMINAL_INPATIENT_LENGTH_OF_STAY_DAYS = 7
"""For REPORTING ONLY where a patient record provides no actual LOS -- the
economic model itself always uses the actual admission/discharge/LOS where
available (never overwritten by this nominal value)."""


def equivalent_patient_day_value(
    *, episode_value: float = CONTROLLED_ONCOLOGY_INPATIENT_EPISODE_VALUE_2026,
    nominal_los_days: int = NOMINAL_INPATIENT_LENGTH_OF_STAY_DAYS,
) -> float:
    """Section 3: REPORTING-ONLY derived quantity (e.g. 30000/7 =
    4285.7142857 USD/inpatient-day) -- never treat as a literal daily room
    rent. The authoritative revenue object remains the per-episode value."""
    return episode_value / nominal_los_days


@dataclass(frozen=True)
class ClinicalStaffCostPolicy:
    """Section 35-36: minimal patient-day clinical staff cost interface --
    not a full medical billing engine."""

    physician_cost_per_patient_day: float | None
    nursing_cost_per_patient_day: float | None
    provenance: Literal["USER_SUPPLIED", "CONTROLLED_SCENARIO_ASSUMPTION", "NOT_CALIBRATED"] = "NOT_CALIBRATED"

    def total_per_patient_day(self) -> float:
        return (self.physician_cost_per_patient_day or 0.0) + (self.nursing_cost_per_patient_day or 0.0)


@dataclass(frozen=True)
class DailyFacilityCostPolicy:
    """Section 33: a controlled PER-DAY facility-cost component -- distinct
    from a 'room rent' revenue model. This is COST, not reimbursement."""

    facility_cost_per_patient_day: float | None
    provenance: Literal["USER_SUPPLIED", "CONTROLLED_SCENARIO_ASSUMPTION", "NOT_CALIBRATED"] = "NOT_CALIBRATED"


@dataclass(frozen=True)
class PatientEconomicEpisode:
    """Section 31-32: the minimum patient-episode economic abstraction --
    distinguishes INPATIENT episodes from OUTPATIENT nuclear visits (section
    67), never the same economic object/value."""

    patient_id: str
    patient_type: PatientType
    admission_date: date | None
    discharge_date: date | None
    length_of_stay_days: int
    payment_context: PaymentContext
    revenue_basis: RevenueBasis
    facility_episode_revenue: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    professional_revenue: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    separately_payable_procedure_revenue: float | Literal["NOT_CALIBRATED"] = "NOT_CALIBRATED"
    facility_cost: float = 0.0
    clinical_staff_cost: float = 0.0
    pharmacy_cost: float = 0.0
    linen_cost: float = 0.0
    specimen_blood_cost: float = 0.0
    sterile_supply_cost: float = 0.0
    general_logistics_transport_cost: float = 0.0
    nuclear_logistics_transport_cost: float = 0.0

    def total_cost(self) -> float:
        return (
            self.facility_cost + self.clinical_staff_cost + self.pharmacy_cost + self.linen_cost
            + self.specimen_blood_cost + self.sterile_supply_cost
            + self.general_logistics_transport_cost + self.nuclear_logistics_transport_cost
        )

    def total_revenue(self, *, mode: EconomicMode) -> float | Literal["NOT_CALIBRATED"]:
        """Section 39/41: COST_ONLY excludes revenue from architecture
        ranking entirely (returns NOT_CALIBRATED, never fabricated $0).

        REVENUE_AWARE (correction section 7): an individually-untracked
        optional component (e.g. `professional_revenue`, never separately
        calibrated by this model) contributes 0, not a fabricated value --
        but it must NOT nullify a genuinely calibrated component such as the
        controlled $30,000 inpatient episode value or the $2,000 outpatient
        scan value. Only if EVERY component is uncalibrated is the whole
        episode's revenue itself NOT_CALIBRATED."""
        if mode == "COST_ONLY":
            return "NOT_CALIBRATED"
        components = (self.facility_episode_revenue, self.professional_revenue, self.separately_payable_procedure_revenue)
        calibrated = [c for c in components if c != "NOT_CALIBRATED"]
        if not calibrated:
            return "NOT_CALIBRATED"
        return sum(calibrated)  # type: ignore[arg-type]

    def contribution_margin(self, *, mode: EconomicMode) -> float | Literal["NOT_CALIBRATED"]:
        """Section 41: Contribution Margin = Total Patient Revenue - Total
        Cost To Serve. Never counts transport savings as new clinical revenue."""
        revenue = self.total_revenue(mode=mode)
        if revenue == "NOT_CALIBRATED":
            return "NOT_CALIBRATED"
        return revenue - self.total_cost()  # type: ignore[operator]


def build_outpatient_nuclear_episode(
    *, patient_id: str, scan_count: int = 1, revenue_per_scan: float = AUDITED_NUCLEAR_SCAN_REVENUE_USD,
    nuclear_logistics_transport_cost: float = 0.0,
) -> PatientEconomicEpisode:
    """Section 37-38: outpatient nuclear visit -- SEPARATELY_PAYABLE, carries
    the audited existing scan-revenue assumption. Distinct object/value from
    `build_inpatient_episode` (section 67) -- an outpatient never receives an
    inpatient facility/clinical-staff cost structure."""
    return PatientEconomicEpisode(
        patient_id=patient_id, patient_type="OUTPATIENT", admission_date=None, discharge_date=None,
        length_of_stay_days=0, payment_context="SEPARATELY_PAYABLE", revenue_basis="CONTROLLED_SCAN_REVENUE_ASSUMPTION",
        facility_episode_revenue=0.0, professional_revenue=0.0,
        separately_payable_procedure_revenue=scan_count * revenue_per_scan,
        nuclear_logistics_transport_cost=nuclear_logistics_transport_cost,
    )


def build_inpatient_episode(
    *,
    patient_id: str,
    admission_date: date,
    discharge_date: date,
    daily_facility_cost: DailyFacilityCostPolicy,
    clinical_staff_cost_policy: ClinicalStaffCostPolicy,
    daily_pharmacy_cost: float = 0.0,
    daily_linen_cost: float = 0.0,
    daily_specimen_blood_cost: float = 0.0,
    daily_sterile_supply_cost: float = 0.0,
    general_logistics_transport_cost: float = 0.0,
    nuclear_logistics_transport_cost: float = 0.0,
    has_nuclear_procedure: bool = False,
    nuclear_payment_context: PaymentContext = "BUNDLED_IN_INPATIENT_EPISODE",
    facility_episode_revenue: float | Literal["NOT_CALIBRATED"] = CONTROLLED_ONCOLOGY_INPATIENT_EPISODE_VALUE_2026,
    revenue_basis: RevenueBasis = "CONTROLLED_EPISODE_VALUE",
) -> PatientEconomicEpisode:
    """Section 32/34/38: costs accumulate ONLY over the actual LOS -- ALWAYS
    the real admission/discharge/LOS where available (never overwritten by
    the nominal 7-day reporting value, correction section 2). Defaults
    `facility_episode_revenue` to the controlled $30,000 primary benchmark
    (correction section 1) -- fully user-overridable (e.g. to one of
    `INPATIENT_EPISODE_VALUE_SENSITIVITY_USD`) or to "NOT_CALIBRATED" for a
    pure COST_ONLY study. A bundled inpatient nuclear procedure contributes
    ZERO separately-payable scan revenue -- prevents double counting
    (section 38/5)."""
    los_days = max(0, (discharge_date - admission_date).days)
    facility_cost = (daily_facility_cost.facility_cost_per_patient_day or 0.0) * los_days
    clinical_staff_cost = clinical_staff_cost_policy.total_per_patient_day() * los_days
    pharmacy_cost = daily_pharmacy_cost * los_days
    linen_cost = daily_linen_cost * los_days
    specimen_blood_cost = daily_specimen_blood_cost * los_days
    sterile_supply_cost = daily_sterile_supply_cost * los_days

    separately_payable = 0.0
    if has_nuclear_procedure and nuclear_payment_context == "SEPARATELY_PAYABLE":
        separately_payable = AUDITED_NUCLEAR_SCAN_REVENUE_USD  # section 38: only if explicitly NOT bundled

    return PatientEconomicEpisode(
        patient_id=patient_id, patient_type="INPATIENT", admission_date=admission_date, discharge_date=discharge_date,
        length_of_stay_days=los_days, payment_context=nuclear_payment_context, revenue_basis=revenue_basis,
        facility_episode_revenue=facility_episode_revenue, professional_revenue="NOT_CALIBRATED",
        separately_payable_procedure_revenue=separately_payable,
        facility_cost=facility_cost, clinical_staff_cost=clinical_staff_cost, pharmacy_cost=pharmacy_cost,
        linen_cost=linen_cost, specimen_blood_cost=specimen_blood_cost, sterile_supply_cost=sterile_supply_cost,
        general_logistics_transport_cost=general_logistics_transport_cost,
        nuclear_logistics_transport_cost=nuclear_logistics_transport_cost,
    )


def build_inpatient_sensitivity_episodes(
    *, patient_id: str, admission_date: date, discharge_date: date,
    daily_facility_cost: DailyFacilityCostPolicy, clinical_staff_cost_policy: ClinicalStaffCostPolicy,
    episode_values: tuple[float, ...] = INPATIENT_EPISODE_VALUE_SENSITIVITY_USD, **kwargs,
) -> tuple[PatientEconomicEpisode, ...]:
    """Section 10: the optimizer must never hard-code 30000 -- at minimum
    20000/30000/40000 must be supportable. Same LOS/cost basis, revenue
    swept across the sensitivity band."""
    return tuple(
        build_inpatient_episode(
            patient_id=patient_id, admission_date=admission_date, discharge_date=discharge_date,
            daily_facility_cost=daily_facility_cost, clinical_staff_cost_policy=clinical_staff_cost_policy,
            facility_episode_revenue=value, **kwargs,
        )
        for value in episode_values
    )


# ---------------------------------------------------------------------------
# Mission-cost allocation (sections 43, 65) -- conservation-preserving
# ---------------------------------------------------------------------------


def allocate_mission_cost_to_patients(
    *, mission_cost: float, patient_quantities: Mapping[str, float],
) -> dict[str, float]:
    """Section 43/65: allocates a consolidated mission's cost across its
    patients by physical-demand share (equal share when all quantities are
    equal) -- NEVER duplicates the full mission cost against every patient.
    Guarantees sum(allocation) == mission_cost (up to floating-point
    tolerance, verified by callers/tests)."""
    total_quantity = sum(patient_quantities.values())
    if total_quantity <= 0:
        raise ValueError("patient_quantities must sum to a positive total")
    return {pid: mission_cost * (qty / total_quantity) for pid, qty in patient_quantities.items()}
