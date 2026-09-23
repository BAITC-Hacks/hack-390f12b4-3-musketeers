"""LLM explains server-calculated evidence; it never supplies the Score."""
from collections import OrderedDict
from copy import deepcopy
import json
import logging
import os
import re
from threading import Lock
from time import monotonic

from openai import OpenAI, OpenAIError
from pydantic import BaseModel, ConfigDict

from backend.engine import CATALOG, DATA, DISTRICTS, Scenario, canonical

logger = logging.getLogger(__name__)
PROMPT_VERSION = "evidence-v1"
CACHE = OrderedDict()
CACHE_LOCK = Lock()


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    evidence_ids: list[str]


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: str
    explanation: str


class Audit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: Claim
    strengths: list[Claim]
    tradeoffs: list[Claim]
    remaining_problems: list[Claim]
    recommendations: list[Recommendation]
    limitations: list[str]


def facts_for(result, recommendations):
    facts = {
        "score": f"Score: {result['baseline']['score']:.5f} → {result['result']['score']:.5f}; изменение {result['delta_score']:+.5f}.",
        "budget": f"Стоимость: {result['spent']}; остаток: {result['remaining']}. Остаток бонуса не даёт.",
        "critical": f"Критических значений (<40): {result['baseline']['critical_count']} → {result['result']['critical_count']}.",
        "weakest": f"Слабейшие районы: {', '.join(DISTRICTS[d]['name'] for d in result['result']['weakest_ids'])}; минимальный балл {result['result']['minimum']:.5f}.",
        "decomposition": f"Вклад среднего: {result['decomposition']['average']:+.5f}; минимума: {result['decomposition']['weakest']:+.5f}; снятия штрафа: {result['decomposition']['critical']:+.5f}.",
        "limits": "Данные синтетические. Горизонт — восемь кварталов; лаг учтён. Эксплуатационные расходы, реальные сроки и причинные эффекты не подтверждены.",
    }
    for district in result["districts"]:
        changes = "; ".join(f"{DATA['indicators'][k]}: {district['before'][k]} → {district['after'][k]}" for k in DATA["weights"] if district["delta"][k])
        facts["district:" + district["id"]] = f"{district['name']}: {district['score_before']:.5f} → {district['score_after']:.5f}. {changes or 'Изменений нет.'}"
    for i, measure in enumerate(result["contributions"]):
        effects = "; ".join(f"{DATA['indicators'][k]} {v:+g}" for k, v in measure["effects"].items())
        target = DISTRICTS[measure["district_id"]]["name"] if measure["district_id"] else "все районы"
        facts[f"measure:{i}"] = f"{measure['title']}, {target}, стоимость {measure['cost']}, лаг {measure['lag']}: {effects}."
    for i, synergy in enumerate(result["synergies"]):
        facts[f"synergy:{i}"] = f"Синергия {' + '.join(synergy['pair'])}, {DISTRICTS[synergy['district_id']]['name']}: {synergy['effects']}."
    for candidate in recommendations["candidates"]:
        def describe(decision):
            name = CATALOG[decision["measure_id"]]["title"]
            target = DISTRICTS[decision["district_id"]]["name"] if decision["district_id"] else "весь город"
            return f"«{name}» ({target})"
        facts["candidate:" + candidate["id"]] = f"Замена {describe(candidate['removed'])} на {describe(candidate['added'])}: Score {candidate['score']:.2f}, прирост {candidate['gain']:+.2f}, стоимость {candidate['spent']}, критических значений {candidate['critical_count']}."
    return facts


def fallback(result, recommendations):
    direction = "улучшает" if result["delta_score"] > 0 else "изменяет"
    problems = [{"text": "В сценарии остаются критические значения.", "evidence_ids": ["critical"]}] if result["result"]["critical_count"] else []
    problems.append({"text": "Район с минимальным баллом остаётся приоритетом следующего сравнения.", "evidence_ids": ["weakest"]})
    tradeoffs = [{"text": "Остаток бюджета не повышает оценку; учитывается результат принятых мер.", "evidence_ids": ["budget"]}]
    for i, measure in enumerate(result["contributions"]):
        if any(v < 0 for v in measure["effects"].values()):
            tradeoffs.append({"text": "У выбранной меры есть отрицательный эффект, который также входит в расчёт.", "evidence_ids": [f"measure:{i}"]})
    return {
        "summary": {"text": f"Выбранный сценарий {direction} качество городской среды в рамках учебной модели.", "evidence_ids": ["score", "decomposition"]},
        "strengths": [{"text": "Расчёт учитывает средний результат, положение слабейшего района и критические показатели.", "evidence_ids": ["decomposition", "critical"]}],
        "tradeoffs": tradeoffs,
        "remaining_problems": problems,
        "recommendations": [{"candidate_id": c["id"], "explanation": "Эта замена проверена движком: правила соблюдены, итоговый балл выше."} for c in recommendations["candidates"]],
        "limitations": ["Синтетическая учебная модель; эксплуатационные расходы не учитываются. Результат не является прогнозом для реальной Астаны."],
    }


def validate_audit(audit: Audit, facts: dict, candidates: list[dict]):
    claims = [audit.summary, *audit.strengths, *audit.tradeoffs, *audit.remaining_problems]
    if not audit.strengths or not audit.tradeoffs or not audit.limitations:
        raise ValueError("Empty required analysis sections")
    for claim in claims:
        if not claim.text.strip() or len(claim.text) > 1500 or not claim.evidence_ids or not set(claim.evidence_ids) <= facts.keys():
            raise ValueError("Unsupported evidence reference")
    allowed = {c["id"] for c in candidates}
    if any(r.candidate_id not in allowed for r in audit.recommendations):
        raise ValueError("Unverified recommendation")
    # Numbers are rendered from evidence, never from generated prose.
    texts = [c.text for c in claims] + [r.explanation for r in audit.recommendations] + audit.limitations
    if any(re.search(r"\d", text) or len(text) > 1500 for text in texts):
        raise ValueError("Generated numerical claim")


def analyze(scenario: Scenario, result: dict, recommendations: dict) -> dict:
    facts = facts_for(result, recommendations)
    base = {"facts": facts, "audit": fallback(result, recommendations), "source": "fallback_no_key", "cached": False, "model": None}
    key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip()
    if not key:
        return base
    if not model:
        return {**base, "source": "fallback_no_model"}
    cache_key = canonical(scenario) + "|" + model + "|" + PROMPT_VERSION
    # One in-flight call for this prototype; identical requests reuse the result.
    with CACHE_LOCK:
        cached = CACHE.get(cache_key)
        if cached and monotonic() - cached[0] < 900:
            return {**deepcopy(cached[1]), "cached": True}
        try:
            with OpenAI(api_key=key, timeout=20.0, max_retries=0) as client:
                response = client.responses.create(
                    model=model, store=False, max_output_tokens=2200,
                    instructions=(
                        "Ты аналитик синтетического городского симулятора. Пиши кратко по-русски. "
                        "Объясни сильные стороны, компромиссы и оставшиеся проблемы. "
                        "Каждый тезис связывай с существующими evidence_ids из facts. "
                        "Не вычисляй и не придумывай чисел: текст должен быть без цифр, "
                        "пользователь видит числовые факты отдельно. Не называй коды мер в тексте. "
                        "Рекомендуй только candidate_id из verified_candidates. "
                        "Если кандидатов нет, верни пустой recommendations. "
                        "Не представляй эффект реальным прогнозом, не обещай исчезновения проблем. "
                        "Различай факты расчёта и ограничения модели. До трёх пунктов в каждой секции."
                    ),
                    input=json.dumps({"facts": facts, "verified_candidates": recommendations["candidates"]}, ensure_ascii=False),
                    text={"format": {"type": "json_schema", "name": "city_analysis",
                                     "strict": True, "schema": Audit.model_json_schema()}},
                )
            if response.status != "completed":
                raise ValueError("Incomplete response")
            audit = Audit.model_validate_json(response.output_text)
            validate_audit(audit, facts, recommendations["candidates"])
            output = {**base, "audit": audit.model_dump(), "source": "openai", "model": model}
            CACHE[cache_key] = (monotonic(), deepcopy(output))
            CACHE.move_to_end(cache_key)
            while len(CACHE) > 128:
                CACHE.popitem(last=False)
            return output
        except (OpenAIError, ValueError, TypeError) as exc:
            logger.warning("AI analysis unavailable: %s", type(exc).__name__)
            return {**base, "source": "fallback_api_error"}
