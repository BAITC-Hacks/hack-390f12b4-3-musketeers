"""Deterministic scoring, validation and bounded search. No network/UI."""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

from backend.events import event_data

from pydantic import BaseModel, ConfigDict, Field, StrictStr

DATA = json.loads((Path(__file__).resolve().parents[1] / "data/city_data.json").read_text(encoding="utf-8"))
CATALOG = {m["id"]: m for m in DATA["measures"]}
DISTRICTS = {d["id"]: d for d in DATA["districts"]}
RULESETS = ("dataset-v1", "one-per-direction-v1")


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    measure_id: StrictStr = Field(max_length=8)
    district_id: StrictStr | None = Field(default=None, max_length=24)


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    decisions: list[Decision] = Field(max_length=5)
    ruleset: Literal["dataset-v1", "one-per-direction-v1"] = "dataset-v1"
    dataset_version: Literal["dataset-v1"] = "dataset-v1"
    event_id: Literal["none", "winter-v1", "growth-v1"] = "none"


def canonical(scenario: Scenario) -> str:
    payload = scenario.model_dump()
    payload["decisions"] = sorted(payload["decisions"], key=lambda d: (d["measure_id"], d["district_id"] or ""))
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def validate(scenario: Scenario, *, final: bool = True) -> list[dict]:
    errors = []
    decisions = scenario.decisions

    def error(code, message, ids=()):
        errors.append({"code": code, "message": message, "affectedDecisionIds": list(ids)})

    if final and len(decisions) != 5:
        error("count", "Для завершения сценария выберите ровно пять решений.")
    ids = [d.measure_id for d in decisions]
    repeated = [key for key, count in Counter(ids).items() if count > 1]
    if repeated:
        error("duplicate", "Каждое мероприятие можно выбрать только один раз.", repeated)
    unknown = [key for key in ids if key not in CATALOG]
    if unknown:
        error("unknown_measure", "Неизвестное мероприятие.", unknown)
        return errors
    spent = sum(CATALOG[key]["cost"] for key in ids)
    if spent > DATA["budget"]:
        error("budget", f"Бюджет превышен на {spent - DATA['budget']} усл. ед.")
    counts = Counter(CATALOG[key]["direction"] for key in ids)
    limit = 1 if scenario.ruleset == "one-per-direction-v1" else 2
    if any(count > limit for count in counts.values()):
        error("direction_limit", f"В одном направлении допускается не более {limit} мер.")
    for decision in decisions:
        measure = CATALOG[decision.measure_id]
        if measure["scope"] == "district" and decision.district_id not in DISTRICTS:
            error("district_required", f"{decision.measure_id}: выберите существующий район.", [decision.measure_id])
        if measure["scope"] == "city" and decision.district_id is not None:
            error("city_district", f"{decision.measure_id}: для городской меры район не указывается.", [decision.measure_id])
    by_id = {d.measure_id: d for d in decisions}
    for conflict in DATA["conflicts"]:
        a, b = conflict["pair"]
        if a in by_id and b in by_id:
            if conflict["scope"] == "global" or by_id[a].district_id == by_id[b].district_id:
                error("conflict", conflict["reason"], [a, b])
    return errors


def aggregate(values: dict, data: dict) -> dict:
    scores = {d["id"]: sum(data["weights"][k] * values[d["id"]][k] for k in data["weights"]) for d in data["districts"]}
    average = sum(d["population"] * scores[d["id"]] for d in data["districts"])
    minimum = min(scores.values())
    critical = [{"district_id": d, "indicator": k, "value": v} for d, row in values.items() for k, v in row.items() if v < 40]
    return {
        "score": .7 * average + .3 * minimum - len(critical),
        "average": average, "minimum": minimum, "district_scores": scores,
        "weakest_ids": [d for d, score in scores.items() if score == minimum],
        "critical": critical, "critical_count": len(critical),
    }


def project(decisions: list[Decision], data: dict = DATA) -> dict:
    """Internal projection. Public final scoring must validate first."""
    catalog = {m["id"]: m for m in data["measures"]}
    before = {d["id"]: dict(d["values"]) for d in data["districts"]}
    changes = {d: {k: 0.0 for k in data["weights"]} for d in before}
    contributions = []
    ordered = sorted(decisions, key=lambda d: (d.measure_id, d.district_id or ""))
    by_id = {d.measure_id: d for d in ordered}
    for decision in ordered:
        measure = catalog[decision.measure_id]
        fraction = (data["horizon"] - measure["lag"]) / data["horizon"]
        effects = {k: v * fraction for k, v in measure["effects"].items()}
        targets = list(before) if measure["scope"] == "city" else [decision.district_id]
        for target in targets:
            for key, value in effects.items():
                changes[target][key] += value
        contributions.append({**decision.model_dump(), "title": measure["title"],
                              "cost": measure["cost"], "lag": measure["lag"],
                              "fraction": fraction, "effects": effects, "targets": targets})
    synergies = []
    for synergy in data["synergies"]:
        first, second = synergy["pair"]
        if first in by_id and second in by_id:
            target = by_id[first].district_id
            for key, value in synergy["effects"].items():
                changes[target][key] += value
            synergies.append({**deepcopy(synergy), "district_id": target})
    raw = {d: {k: before[d][k] + changes[d][k] for k in before[d]} for d in before}
    after = {d: {k: min(100, max(0, v)) for k, v in row.items()} for d, row in raw.items()}
    baseline, result = aggregate(before, data), aggregate(after, data)
    spent = sum(catalog[d.measure_id]["cost"] for d in ordered)
    return {
        "baseline": baseline, "result": result, "spent": spent, "remaining": data["budget"] - spent,
        "delta_score": result["score"] - baseline["score"],
        "decomposition": {
            "average": .7 * (result["average"] - baseline["average"]),
            "weakest": .3 * (result["minimum"] - baseline["minimum"]),
            "critical": baseline["critical_count"] - result["critical_count"],
        },
        "districts": [
            {**deepcopy(d), "before": before[d["id"]], "after": after[d["id"]],
             "delta": {k: after[d["id"]][k] - before[d["id"]][k] for k in data["weights"]},
             "clipping_adjustment": {k: after[d["id"]][k] - raw[d["id"]][k] for k in data["weights"]},
             "score_before": baseline["district_scores"][d["id"]],
             "score_after": result["district_scores"][d["id"]]}
            for d in data["districts"]
        ],
        "contributions": contributions, "synergies": synergies,
    }


def simulate(scenario: Scenario) -> dict:
    errors = validate(scenario)
    if errors:
        raise ValueError(errors)
    return {**project(scenario.decisions, event_data(DATA, scenario.event_id)), "scenario": scenario.model_dump()}


def recommend(scenario: Scenario) -> dict:
    current = simulate(scenario)
    seen = {canonical(scenario)}
    improvements = []
    checked = 0
    for index, removed in enumerate(scenario.decisions):
        rest = scenario.decisions[:index] + scenario.decisions[index + 1:]
        used = {d.measure_id for d in rest}
        for measure in DATA["measures"]:
            if measure["id"] in used:
                continue
            targets = [None] if measure["scope"] == "city" else list(DISTRICTS)
            for target in targets:
                added = Decision(measure_id=measure["id"], district_id=target)
                candidate = Scenario(decisions=[*rest, added], ruleset=scenario.ruleset, event_id=scenario.event_id)
                key = canonical(candidate)
                if key in seen or validate(candidate):
                    continue
                seen.add(key)
                checked += 1
                calculated = project(candidate.decisions, event_data(DATA, candidate.event_id))
                gain = calculated["result"]["score"] - current["result"]["score"]
                if gain > 1e-9:
                    improvements.append({
                        "id": sha256(key.encode()).hexdigest()[:16],
                        "removed": removed.model_dump(), "added": added.model_dump(),
                        "scenario": candidate.model_dump(),
                        "score": calculated["result"]["score"], "gain": gain,
                        "spent": calculated["spent"], "remaining": calculated["remaining"],
                        "critical_count": calculated["result"]["critical_count"],
                        "minimum": calculated["result"]["minimum"],
                        "changes": [
                            {"district_id": after["id"], "indicator": key,
                             "delta": after["after"][key] - before["after"][key]}
                            for before, after in zip(current["districts"], calculated["districts"])
                            for key in DATA["weights"]
                            if after["after"][key] != before["after"][key]
                        ],
                    })
    improvements.sort(key=lambda c: (-c["score"], c["spent"], c["id"]))
    return {"candidates": improvements[:3], "checked": checked, "search": "single-replacement"}


EXAMPLE = Scenario(decisions=[
    Decision(measure_id="M7", district_id="nura"), Decision(measure_id="M8", district_id="nura"),
    Decision(measure_id="M10", district_id="nura"), Decision(measure_id="M12"),
    Decision(measure_id="M5", district_id="saryarka"),
])
