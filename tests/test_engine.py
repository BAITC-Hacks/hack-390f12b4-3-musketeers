from copy import deepcopy
from itertools import permutations

import pytest
from pydantic import ValidationError

from backend.engine import DATA, EXAMPLE, Decision, Scenario, canonical, project, recommend, simulate, validate


def choice(mid, district="nura"):
    return Decision(measure_id=mid, district_id=None if mid in ("M2", "M6", "M12", "M14") else district)


def scenario(*ids):
    return Scenario(decisions=[choice(mid) for mid in ids])


def codes(value, final=True):
    return {e["code"] for e in validate(value, final=final)}


def test_baseline_and_example():
    assert sum(DATA["weights"].values()) == pytest.approx(1)
    assert sum(d["population"] for d in DATA["districts"]) == pytest.approx(1)
    baseline = project([])["result"]
    assert baseline["score"] == pytest.approx(52.55768)
    assert baseline["average"] == pytest.approx(56.8624)
    assert baseline["district_scores"] == pytest.approx(dict(yesil=62.99, almaty=57.06, saryarka=54.65, baikonur=56.63, nura=49.18))
    result = simulate(EXAMPLE)
    assert (result["spent"], result["remaining"]) == (95, 5)
    assert result["result"]["score"] == pytest.approx(56.54307)
    assert result["delta_score"] == pytest.approx(3.98539)
    assert result["result"]["critical_count"] == 0
    assert sum(result["decomposition"].values()) == pytest.approx(result["delta_score"])
    nura = next(d for d in result["districts"] if d["id"] == "nura")["after"]
    assert nura["S1"] == 48
    assert nura["S2"] == 43.75
    assert nura["B1"] == 67.5
    assert nura["B2"] == 51.75
    assert nura["C2"] == 54.375


def test_permutations_and_immutable_data():
    before = deepcopy(DATA)
    expected = simulate(EXAMPLE)
    for permutation in permutations(EXAMPLE.decisions):
        value = Scenario(decisions=list(permutation))
        assert canonical(value) == canonical(EXAMPLE)
        assert simulate(value)["result"] == expected["result"]
    assert DATA == before


@pytest.mark.parametrize("ids,code", [
    (("M7", "M8", "M10", "M12"), "count"),
    (("M3", "M5", "M7", "M10", "M14"), "budget"),
    (("M9", "M7", "M8", "M11", "M12"), "direction_limit"),
    (("M1", "M3", "M9", "M11", "M12"), "conflict"),
    (("M4", "M7", "M9", "M11", "M12"), "conflict"),
    (("M5", "M13", "M9", "M11", "M12"), "conflict"),
    (("M1", "M1", "M9", "M11", "M12"), "duplicate"),
    (("M99", "M7", "M9", "M11", "M12"), "unknown_measure"),
])
def test_invalid_sets(ids, code):
    value = scenario(*ids)
    assert code in codes(value)
    with pytest.raises(ValueError):
        simulate(value)


def test_exact_budget_and_city_scope():
    value = scenario("M3", "M6", "M7", "M10", "M12")
    assert not validate(value)
    assert simulate(value)["spent"] == 100
    city = project([choice("M2")])
    assert city["spent"] == 22
    assert all(d["delta"]["T1"] == 3 and d["delta"]["B2"] == 2.25 for d in city["districts"])
    local = project([choice("M11")])
    assert local["districts"][-1]["delta"]["T1"] == -1.75
    assert all(d["delta"]["T1"] == 0 for d in local["districts"][:-1])


@pytest.mark.parametrize("decision,code", [
    (Decision(measure_id="M1"), "district_required"),
    (Decision(measure_id="M1", district_id="missing"), "district_required"),
    (Decision(measure_id="M2", district_id="nura"), "city_district"),
])
def test_district_validation(decision, code):
    assert code in codes(Scenario(decisions=[decision]), final=False)


def test_district_conflicts_and_global_conflict():
    for a, b in [("M4", "M7"), ("M5", "M13")]:
        value = Scenario(decisions=[choice(a), choice(b, "yesil")])
        assert not validate(value, final=False)
    value = Scenario(decisions=[choice("M1"), choice("M3", "yesil")])
    assert "conflict" in codes(value, final=False)


@pytest.mark.parametrize("first,second,key,expected", [
    ("M1", "M2", "T1", 9.5), ("M10", "M12", "B1", 12.5), ("M5", "M6", "E2", 12.25)
])
def test_synergies_unscaled(first, second, key, expected):
    result = project([choice(first), choice(second)])
    assert result["districts"][-1]["delta"][key] == expected
    assert len(result["synergies"]) == 1


def test_clip_after_sum_threshold_and_new_weakest():
    data = deepcopy(DATA)
    data["districts"][-1]["values"]["T1"] = 99
    result = project([choice("M1"), choice("M11")], data)
    assert result["districts"][-1]["after"]["T1"] == 100
    # Values of exactly 40 must not attract a penalty.
    data["districts"][-1]["values"]["S1"] = 40
    data["districts"][-1]["values"]["S2"] = 40
    assert project([], data)["result"]["critical_count"] == 0
    data["districts"][-1]["values"] = {k: 90 for k in data["weights"]}
    assert project([], data)["result"]["weakest_ids"] == ["saryarka"]
    # A negative value is clipped only at indicator level; final Score isn't clamped.
    data["districts"][0]["values"]["T1"] = 0
    assert project([choice("M11", "yesil")], data)["districts"][0]["after"]["T1"] == 0


def test_partial_ruleset_schema_and_no_client_prices():
    assert not validate(Scenario(decisions=[]), final=False)
    assert "count" in codes(Scenario(decisions=[]))
    strict = EXAMPLE.model_copy(update={"ruleset": "one-per-direction-v1"})
    assert "direction_limit" in codes(strict)
    for invalid in [
        {"decisions": [d.model_dump() for d in EXAMPLE.decisions] + [choice("M1").model_dump()]},
        {"decisions": [{"measure_id": "M1", "district_id": "nura", "cost": 0}]},
        {"decisions": [], "score": 100},
        {"decisions": [], "dataset_version": "unknown"},
    ]:
        with pytest.raises(ValidationError):
            Scenario.model_validate(invalid)


def test_recommendations_are_feasible_replacements():
    candidates = recommend(EXAMPLE)
    assert candidates["checked"] > 0
    assert 0 < len(candidates["candidates"]) <= 3
    for candidate in candidates["candidates"]:
        value = Scenario.model_validate(candidate["scenario"])
        assert not validate(value)
        result = simulate(value)
        assert result["result"]["score"] == candidate["score"]
        assert candidate["score"] > simulate(EXAMPLE)["result"]["score"]
        old = {(d.measure_id, d.district_id) for d in EXAMPLE.decisions}
        new = {(d.measure_id, d.district_id) for d in value.decisions}
        assert len(old - new) == len(new - old) == 1
