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
PROMPT_VERSION = "evidence-v6"
CACHE = OrderedDict()
CACHE_LOCK = Lock()


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    evidence_ids: list[str]


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_id: str


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
        "budget": f"Общий бюджет фиксирован: 100, он не изменился. Расход: {result['spent']}; остаток: {result['remaining']}. Остаток бонуса не даёт.",
        "critical": f"Критических значений (<40): {result['baseline']['critical_count']} → {result['result']['critical_count']}. Выход из критической зоны модели не означает полного решения реальных проблем.",
        "weakest": f"Слабейшие районы после мер: {', '.join(DISTRICTS[d]['name'] for d in result['result']['weakest_ids'])}; минимум по городу {result['baseline']['minimum']:.5f} → {result['result']['minimum']:.5f}.",
        "decomposition": f"Вклад среднего: {result['decomposition']['average']:+.5f}; минимума: {result['decomposition']['weakest']:+.5f}; снятия штрафа: {result['decomposition']['critical']:+.5f}.",
        "limits": "Данные синтетические. Горизонт — восемь кварталов; лаг учтён. Эксплуатационные расходы, реальные сроки и причинные эффекты не подтверждены. Порог комфортности не задан; есть только порог критичности. Будущие последствия вне горизонта не моделируются.",
        "rules": "Сценарий уже завершён: выбрано ровно пять решений. Добавлять шестое нельзя. Остаток бюджета не финансирует дополнительные проекты в этом сценарии; доступны только проверенные замены из списка кандидатов. Улучшение показателя не означает полного решения проблемы.",
    }
    covered = sorted({CATALOG[m["measure_id"]]["direction"] for m in result["contributions"]})
    facts["coverage"] = "Выбранные направления: " + ", ".join(DATA["directions"][d] for d in covered) + ". Нельзя называть эти направления неохваченными. Районный охват указан отдельно у каждой меры."
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
        changes = "; ".join(f"{DISTRICTS[c['district_id']]['name']}: {DATA['indicators'][c['indicator']]} {c['delta']:+g}" for c in candidate["changes"])
        facts["candidate:" + candidate["id"]] = f"Замена {describe(candidate['removed'])} на {describe(candidate['added'])}: Score {candidate['score']:.2f}, прирост {candidate['gain']:+.2f}, стоимость {candidate['spent']}, критических значений {candidate['critical_count']}. Изменения относительно текущего плана: {changes}."
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
        "recommendations": [{"candidate_id": c["id"]} for c in recommendations["candidates"]],
        "limitations": ["Синтетическая учебная модель; эксплуатационные расходы не учитываются. Результат не является прогнозом для реальной Астаны."],
    }


def validate_audit(audit: Audit, facts: dict, candidates: list[dict]):
    claims = [audit.summary, *audit.strengths, *audit.tradeoffs, *audit.remaining_problems]
    if not audit.strengths or not audit.tradeoffs or not audit.limitations:
        raise ValueError("Empty required analysis sections")
    for claim in claims:
        if not claim.text.strip() or len(claim.text) > 1500 or not claim.evidence_ids or not set(claim.evidence_ids) <= facts.keys() or any(key.startswith("candidate:") for key in claim.evidence_ids):
            raise ValueError("Unsupported evidence reference")
    allowed = {c["id"] for c in candidates}
    if any(r.candidate_id not in allowed for r in audit.recommendations):
        raise ValueError("Unverified recommendation")
    # Generated numbers may only quote their cited facts, including display rounding.
    def numbers(text):
        return [float(n.replace(",", ".")) for n in re.findall(r"[+-]?\d+(?:[.,]\d+)?", text)]
    for claim in claims:
        known = numbers(" ".join(facts[key] for key in claim.evidence_ids))
        allowed_numbers = {value for n in known for value in (n, round(n, 2))}
        if any(n not in allowed_numbers for n in numbers(claim.text)):
            raise ValueError("Generated numerical claim")
    if any(re.search(r"\d", text) or len(text) > 1500 for text in audit.limitations):
        raise ValueError("Unsupported limitation")


def analyze(scenario: Scenario, result: dict, recommendations: dict) -> dict:
    facts = facts_for(result, recommendations)
    if scenario.event_id != "none":
        from backend.events import EVENTS
        event = next(e for e in EVENTS if e["id"] == scenario.event_id)
        facts["event"] = event["description"] + " Изменения плана сравниваются с состоянием после события."
    base = {"facts": facts, "audit": fallback(result, recommendations), "source": "fallback_no_key", "cached": False, "model": None}
    key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip()
    if not key:
        return base
    if not model:
        return {**base, "source": "fallback_no_model"}
    cache_key = canonical(scenario) + "|" + model + "|" + PROMPT_VERSION
    current_facts = {k: v for k, v in facts.items() if not k.startswith("candidate:")}
    schema = Audit.model_json_schema()
    schema["$defs"]["Claim"]["properties"]["evidence_ids"]["items"]["enum"] = list(current_facts)
    candidate_metrics = [{k: c[k] for k in ("id", "score", "gain", "spent", "critical_count", "minimum")} for c in recommendations["candidates"]]
    # One in-flight call for this prototype; identical requests reuse the result.
    with CACHE_LOCK:
        cached = CACHE.get(cache_key)
        if cached and monotonic() - cached[0] < 900:
            return {**deepcopy(cached[1]), "cached": True}
        from backend.leaderboard import reserve_ai_call
        if not reserve_ai_call():
            return {**base, "source": "fallback_daily_limit", "reason": "daily_limit"}
        try:
            with OpenAI(api_key=key, timeout=20.0, max_retries=0) as client:
                response = client.responses.create(
                    model=model, store=False, max_output_tokens=2200,
                    instructions=(
                        "Ты аналитик синтетического городского симулятора. Пиши кратко по-русски. "
                        "Объясни сильные стороны, компромиссы и оставшиеся проблемы. "
                        "Каждый тезис связывай с существующими evidence_ids из facts. "
                        "Не вычисляй и не придумывай чисел. Предпочитай качественное объяснение: "
                        "пользователь видит числовые факты отдельно. Если число необходимо, "
                        "копируй его из цитируемого факта без арифметики. "
                        "Называй Score баллом, а не коэффициентом. Не называй коды мер в тексте. "
                        "Рекомендуй только candidate_id из verified_candidates. "
                        "Если кандидатов нет, верни пустой recommendations. "
                        "Не представляй эффект реальным прогнозом, не обещай исчезновения проблем. "
                        "Сценарий уже содержит все разрешённые решения: не предлагай добавлять новые "
                        "проекты на остаток бюджета. Разрешены только проверенные замены. "
                        "Не называй выбранные направления неохваченными: смотри coverage и меры. "
                        "Не выдумывай ухудшение или причинный эффект в районах, на которые мера не действует. "
                        "Не делай выводов о последствиях вне горизонта модели. "
                        "Не придумывай субъективное восприятие, общественное мнение или новые проблемы. "
                        "Каждый тезис должен прямо следовать из цитируемого факта. "
                        "Рекомендации содержат только выбранные candidate_id: описание конкретных "
                        "эффектов сформирует сервер. Не описывай эффект альтернатив в других секциях. "
                        "Различай факты расчёта и ограничения модели. Один-два коротких пункта в каждой секции. "
                        "Не повторяй одни и те же мысли в разных секциях."
                    ),
                    input=json.dumps({"facts": current_facts, "verified_candidates": candidate_metrics}, ensure_ascii=False),
                    text={"format": {"type": "json_schema", "name": "city_analysis",
                                     "strict": True, "schema": schema}},
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
            return {**base, "source": "fallback_api_error", "reason": type(exc).__name__}
