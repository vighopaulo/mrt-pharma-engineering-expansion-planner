from __future__ import annotations

from dataclasses import dataclass

from models import ConventionalPlan, MRTPlan


@dataclass(frozen=True)
class DecisionSummary:
    recommended_option: str
    reason: str


def recommend(conventional: ConventionalPlan, mrt: MRTPlan) -> DecisionSummary:
    if mrt.capex < conventional.capex:
        return DecisionSummary(
            recommended_option="MRT-enabled Expansion",
            reason="Lower feasible CapEx under constrained optimization.",
        )
    if conventional.capex < mrt.capex:
        return DecisionSummary(
            recommended_option="Conventional Expansion",
            reason="Lower expansion CapEx under linear scaling.",
        )
    return DecisionSummary(
        recommended_option="Tie",
        reason="Both options have equal CapEx; review reserve and retention deltas.",
    )
