"""Capital Project API -- focused tests (`capital_project_api.py`).

Uses FastAPI's TestClient (in-process, no real server) to verify the
adapter boundary: health, project descriptor, cyclotron catalog
passthrough, both constraint modes calling the REAL engine, honest error
handling, and governance (no fabricated numbers, no secrets, no
Bentley/NVIDIA coupling).
"""

import math

from fastapi.testclient import TestClient

import capital_project_api as capi
import equal_budget as eb
from models import PlannerAssumptions, PlannerInputs

client = TestClient(capi.app)


def test_1_health_endpoint_reports_ok_without_secrets():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok", "service": "mrt-pharma-engine"}


def test_2_project_endpoint_returns_controlled_demo_descriptor():
    response = client.get("/api/capital/project/oncology-expansion-demo")
    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == "oncology-expansion-demo"
    assert body["project_type"] == "RETROFIT"
    assert "CONTROLLED_DEMO_INPUT" in body["provenance"]


def test_3_unknown_project_id_is_404_not_fabricated():
    response = client.get("/api/capital/project/does-not-exist")
    assert response.status_code == 404


def test_4_cyclotron_catalog_returns_real_catalog_models():
    response = client.get("/api/catalog/cyclotrons")
    assert response.status_code == 200
    models = response.json()
    assert len(models) > 0
    assert all({"catalog_model_id", "manufacturer", "model", "commercial_status"} <= model.keys() for model in models)


def _analyze(**overrides):
    payload = {
        "project_id": "oncology-expansion-demo",
        "project_type": "RETROFIT",
        "constraint_mode": "CAPACITY",
        "current_patients_per_day": 60,
        "target_patients_per_day": 120,
    }
    payload.update(overrides)
    return client.post("/api/capital/analyze", json=payload)


def test_5_capacity_constrained_mode_derives_budget_from_target():
    response = _analyze(constraint_mode="CAPACITY")
    assert response.status_code == 200
    body = response.json()
    assert body["budget_source"] == "conventional_target_cost_anchor"
    assert body["common_budget_usd"] > 0
    assert len(body["configurations"]) == 2
    assert {c["label"] for c in body["configurations"]} == {"Conventional", "MRT"}


def test_6_budget_constrained_mode_uses_explicit_budget():
    response = _analyze(constraint_mode="BUDGET", maximum_project_budget_usd=8_000_000)
    assert response.status_code == 200
    body = response.json()
    assert body["budget_source"] == "explicit_budget"
    assert body["common_budget_usd"] == 8_000_000.0


def test_7_budget_mode_without_budget_value_is_a_clear_error():
    response = _analyze(constraint_mode="BUDGET")
    assert response.status_code == 422
    assert "maximum_project_budget_usd" in response.json()["detail"]


def test_8_unknown_cyclotron_model_id_is_a_clear_error():
    response = _analyze(cyclotron_catalog_model_id="NOT-A-REAL-MODEL")
    assert response.status_code == 422
    assert "cyclotron_catalog_model_id" in response.json()["detail"]


def test_9_configuration_numbers_match_the_real_engine_verbatim():
    inputs = PlannerInputs(
        project_name="Capital Project — oncology-expansion-demo", current_patients_per_day=60.0,
        target_patients_per_day=120.0, maximum_expected_demand_per_day=120.0, current_scanners=2,
        current_injection_rooms=2, current_uptake_rooms=2, has_existing_cyclotron=False,
        current_usable_doses_per_day=60.0, current_average_transport_min=8.0, mrt_transport_min=3.0,
        existing_mrt_connectable_rooms=2, representative_radionuclide="F-18", representative_half_life_min=capi._DEMO_HALF_LIFE_MIN,
        conventional_transport_min=8.0, selected_cyclotron_radionuclide="F-18",
    )
    expected = eb.run_equal_budget_multibatch_optimization(inputs, PlannerAssumptions(), capi._DEMO_HALF_LIFE_MIN, explicit_budget=None)

    response = _analyze(constraint_mode="CAPACITY")
    body = response.json()
    conventional = next(c for c in body["configurations"] if c["label"] == "Conventional")
    assert conventional["patient_capacity_per_day"] == expected.conventional.achieved_capacity_per_day
    assert conventional["project_capex_usd"] == expected.conventional.capex_used
    assert conventional["annual_opex_usd"] == expected.conventional.total_annual_modelled_opex


def test_10_payback_years_never_serializes_as_infinity():
    response = _analyze(constraint_mode="BUDGET", maximum_project_budget_usd=100)
    assert response.status_code == 200
    for configuration in response.json()["configurations"]:
        assert configuration["payback_years"] is None or math.isfinite(configuration["payback_years"])


def test_11_health_response_never_exposes_filesystem_or_secrets():
    response = client.get("/api/health")
    text = response.text.lower()
    assert "bentley" not in text
    assert "token" not in text
    assert "secret" not in text
    assert "/users/" not in text


def test_12_no_bentley_or_nvidia_coupling_in_api_module():
    import inspect

    source = inspect.getsource(capi)
    import_lines = [line.strip() for line in source.splitlines() if line.strip().startswith(("import ", "from "))]
    joined = " ".join(import_lines).lower()
    assert "bentley" not in joined
    assert "nvidia" not in joined
    assert "omni" not in joined


def test_13_cors_never_allows_wildcard_origin():
    for middleware in capi.app.user_middleware:
        options = getattr(middleware, "kwargs", {})
        if "allow_origins" in options:
            assert "*" not in options["allow_origins"]


# ===========================================================================
# Build 3: Lockdown / What-If lineage (section 36).
# ===========================================================================


def _capacity_request(project_id: str, *, target: float = 120.0, current: float = 60.0):
    return {
        "project_id": project_id, "project_type": "RETROFIT", "constraint_mode": "CAPACITY",
        "current_patients_per_day": current, "target_patients_per_day": target,
    }


def _budget_request(project_id: str, *, budget: float, target: float = 120.0, current: float = 60.0):
    return {
        "project_id": project_id, "project_type": "RETROFIT", "constraint_mode": "BUDGET",
        "current_patients_per_day": current, "target_patients_per_day": target, "maximum_project_budget_usd": budget,
    }


def _lock(project_id: str, request: dict, *, candidate_label: str = "Conventional"):
    return client.post("/api/capital/lockdown", json={"project_id": project_id, "candidate_label": candidate_label, "request": request})


def _what_if(project_id: str, request: dict):
    return client.post("/api/capital/what-if", json={"project_id": project_id, "request": request})


def _reset(project_id: str):
    return client.post("/api/capital/what-if/reset", json={"project_id": project_id})


def test_14_cannot_lock_an_invalid_unsuccessful_analysis():
    """Section 36 item 1: a request that cannot produce a successful
    analysis (Budget mode with no budget value) is rejected -- and,
    because it was rejected, no baseline is ever stored for this project."""
    project_id = "test-cannot-lock"
    bad_request = {
        "project_id": project_id, "project_type": "RETROFIT", "constraint_mode": "BUDGET",
        "current_patients_per_day": 60.0, "target_patients_per_day": 120.0,
    }
    response = _lock(project_id, bad_request)
    assert response.status_code == 422
    # confirm no baseline was stored: a What-If against this project must fail too
    assert _what_if(project_id, _capacity_request(project_id)).status_code == 422


def test_15_successful_analysis_establishes_a_current_baseline():
    project_id = "test-establish-baseline"
    response = _lock(project_id, _capacity_request(project_id))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "CURRENT"
    assert body["parent_lockdown_id"] is None
    assert body["result"]["feasible"] is True


def test_16_baseline_stores_selected_candidate_identity():
    project_id = "test-candidate-identity"
    response = _lock(project_id, _capacity_request(project_id), candidate_label="MRT")
    assert response.status_code == 200
    assert response.json()["candidate_label"] == "MRT"
    assert response.json()["result"]["label"] == "MRT"


def test_17_what_if_branches_from_the_locked_baseline():
    project_id = "test-branch"
    lockdown = _lock(project_id, _capacity_request(project_id)).json()
    what_if = _what_if(project_id, _capacity_request(project_id, target=150.0)).json()
    assert what_if["parent_lockdown_id"] == lockdown["lockdown_id"]
    assert what_if["status"] == "ACTIVE"


def test_18_budget_baseline_accepts_a_changed_budget_what_if():
    project_id = "test-budget-whatif"
    _lock(project_id, _budget_request(project_id, budget=8_000_000))
    response = _what_if(project_id, _budget_request(project_id, budget=10_000_000))
    assert response.status_code == 200
    assert response.json()["common_budget_usd"] == 10_000_000.0


def test_19_capacity_baseline_accepts_a_changed_target_what_if():
    project_id = "test-capacity-whatif"
    _lock(project_id, _capacity_request(project_id, target=120.0))
    response = _what_if(project_id, _capacity_request(project_id, target=150.0))
    assert response.status_code == 200
    assert response.json()["request"]["target_patients_per_day"] == 150.0


def test_20_what_if_reruns_the_real_engine_never_derives_from_baseline():
    project_id = "test-real-rerun"
    _lock(project_id, _capacity_request(project_id, target=120.0))
    response = _what_if(project_id, _capacity_request(project_id, target=150.0))
    body = response.json()

    inputs = PlannerInputs(
        project_name=f"Capital Project — {project_id}", current_patients_per_day=60.0, target_patients_per_day=150.0,
        maximum_expected_demand_per_day=150.0, current_scanners=2, current_injection_rooms=2, current_uptake_rooms=2,
        has_existing_cyclotron=False, current_usable_doses_per_day=60.0, current_average_transport_min=8.0,
        mrt_transport_min=3.0, existing_mrt_connectable_rooms=2, representative_radionuclide="F-18",
        representative_half_life_min=capi._DEMO_HALF_LIFE_MIN, conventional_transport_min=8.0, selected_cyclotron_radionuclide="F-18",
    )
    expected = eb.run_equal_budget_multibatch_optimization(inputs, PlannerAssumptions(), capi._DEMO_HALF_LIFE_MIN, explicit_budget=None)
    assert body["result"]["patient_capacity_per_day"] == expected.conventional.achieved_capacity_per_day
    assert body["result"]["project_capex_usd"] == expected.conventional.capex_used


def test_21_baseline_result_remains_unchanged_after_a_what_if():
    project_id = "test-baseline-immutable"
    lockdown = _lock(project_id, _capacity_request(project_id, target=120.0)).json()
    before = capi._LOCKDOWNS[lockdown["lockdown_id"]].result.model_dump()
    _what_if(project_id, _capacity_request(project_id, target=150.0))
    after = capi._LOCKDOWNS[lockdown["lockdown_id"]].result.model_dump()
    assert before == after
    assert capi._LOCKDOWNS[lockdown["lockdown_id"]].status == "CURRENT"


def test_22_what_if_result_differs_when_the_engine_response_differs():
    project_id = "test-differs"
    baseline = _lock(project_id, _capacity_request(project_id, target=120.0)).json()
    what_if = _what_if(project_id, _capacity_request(project_id, target=150.0)).json()
    assert what_if["result"]["patient_capacity_per_day"] != baseline["result"]["patient_capacity_per_day"]
    assert what_if["result"]["project_capex_usd"] != baseline["result"]["project_capex_usd"]


def test_23_reset_restores_the_baseline_input_and_discards_the_what_if():
    project_id = "test-reset"
    lockdown = _lock(project_id, _capacity_request(project_id, target=120.0)).json()
    what_if = _what_if(project_id, _capacity_request(project_id, target=150.0)).json()
    response = _reset(project_id)
    assert response.status_code == 200
    body = response.json()
    assert body["parent_lockdown_id"] == lockdown["lockdown_id"]
    assert body["baseline_request"]["target_patients_per_day"] == 120.0
    assert capi._WHAT_IFS[what_if["what_if_id"]].status == "DISCARDED"
    # the baseline itself is untouched by reset
    assert capi._LOCKDOWNS[lockdown["lockdown_id"]].status == "CURRENT"


def test_24_project_a_state_does_not_leak_into_project_b():
    project_a, project_b = "test-isolation-a", "test-isolation-b"
    lock_a = _lock(project_a, _capacity_request(project_a, target=120.0)).json()
    lock_b = _lock(project_b, _capacity_request(project_b, target=200.0)).json()
    assert lock_a["lockdown_id"] != lock_b["lockdown_id"]
    assert capi._CURRENT_LOCKDOWN_ID_BY_PROJECT[project_a] == lock_a["lockdown_id"]
    assert capi._CURRENT_LOCKDOWN_ID_BY_PROJECT[project_b] == lock_b["lockdown_id"]
    # a What-If against B must never reference A's lockdown
    what_if_b = _what_if(project_b, _capacity_request(project_b, target=210.0)).json()
    assert what_if_b["parent_lockdown_id"] == lock_b["lockdown_id"]


def test_25_invalid_or_unknown_project_ids_return_controlled_errors():
    unknown_project = "test-never-locked"
    assert _what_if(unknown_project, _capacity_request(unknown_project)).status_code == 422
    assert _reset(unknown_project).status_code == 422


def test_26_qualification_statuses_survive_serialization_never_fake_precision():
    project_id = "test-qualification"
    lockdown = _lock(project_id, _capacity_request(project_id)).json()
    # no cyclotron was selected -- the engine's own "not_calibrated" status must survive verbatim
    assert lockdown["result"]["cyclotron_capacity_status"] == "not_calibrated"


def test_27_no_secret_or_token_fields_in_lockdown_or_what_if_responses():
    project_id = "test-governance-check"
    lockdown_text = _lock(project_id, _capacity_request(project_id)).text.lower()
    what_if_text = _what_if(project_id, _capacity_request(project_id, target=130.0)).text.lower()
    for text in (lockdown_text, what_if_text):
        assert "token" not in text
        assert "secret" not in text
        assert "bentley" not in text
