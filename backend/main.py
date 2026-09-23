import json
import logging
import os
from pathlib import Path
from statistics import mean
from typing import Annotated

from fastapi import Body, FastAPI, HTTPException
from openai import OpenAI, OpenAIError
from pydantic import BaseModel, ConfigDict, StrictStr


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "city_data.json"
CITY_DATA = json.loads(DATA_PATH.read_text(encoding="utf-8"))
SPHERES = ("transport", "greening", "social", "safety", "services")
CATALOG = {
    item["id"]: {**item, "sphere": sphere}
    for sphere, items in CITY_DATA["initiatives"].items()
    for item in items
}
logger = logging.getLogger(__name__)
app = FastAPI(title="Аким на 5 часов", version="1.0.0")


class Audit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strengths: list[str]
    risks: list[str]
    recommendations: list[str]


def district_score(district: dict) -> float:
    return mean(district[sphere] for sphere in SPHERES)


def generate_audit(statistics: dict, selected: list[dict]) -> tuple[dict, str]:
    weakest = min(statistics["districts"], key=lambda row: row["new_qol"])
    fallback = Audit(
        strengths=[
            "Выбрано по одному решению в каждой из пяти сфер.",
            f"Прирост QoL: {statistics['qol_delta']:.2f} балла; "
            f"остаток бюджета: {statistics['remaining_budget']} млн ₸.",
        ],
        risks=[
            "Бураны и морозы могут затруднить транспортное обслуживание и ремонт.",
            "Пробки и зимний уход за зелёными насаждениями требуют постоянных расходов.",
            "Игровая модель не учитывает сроки внедрения и эксплуатационные затраты.",
        ],
        recommendations=[
            f"При следующем планировании уделите внимание району {weakest['name']}: "
            f"его итоговый индекс — {weakest['new_qol']:.2f}.",
            "Подготовьте зимние резервы и контролируйте доступность маршрутов в бураны.",
        ],
    ).model_dump()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return fallback, "fallback_no_key"

    try:
        with OpenAI(api_key=api_key, timeout=20.0, max_retries=0) as client:
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.3,
                max_tokens=1200,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "city_audit",
                        "strict": True,
                        "schema": Audit.model_json_schema(),
                    },
                },
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты эксперт по городскому управлению Астаны. "
                            "Дай краткий аудит на русском: по 2–3 пункта в массивах "
                            "strengths, risks, recommendations. Учитывай зимний климат "
                            "Астаны, морозы, бураны, пробки и содержание инфраструктуры. "
                            "Числа уже рассчитаны Python: не пересчитывай и не придумывай их. "
                            "Опирайся на выбранные инициативы и изменения районов. "
                            "Цены и эффекты условные игровые, это не прогноз. "
                            "Климатические риски описывай качественно. "
                            "Не обещай меры дороже остатка бюджета."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"selected_initiatives": selected, "statistics": statistics},
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
        choice = completion.choices[0]
        if choice.finish_reason != "stop" or choice.message.refusal:
            return fallback, "fallback_api_error"
        audit = Audit.model_validate_json(choice.message.content or "")
        if not all((audit.strengths, audit.risks, audit.recommendations)):
            return fallback, "fallback_api_error"
        return audit.model_dump(), "openai"
    except (OpenAIError, ValueError, IndexError) as exc:
        logger.warning("AI-аудит недоступен: %s", type(exc).__name__)
        return fallback, "fallback_api_error"


@app.get("/api/data")
def get_data() -> dict:
    return CITY_DATA


@app.post("/api/simulate")
def simulate(
    initiative_ids: Annotated[list[StrictStr], Body(min_length=5, max_length=5)],
) -> dict:
    if len(set(initiative_ids)) != 5:
        raise HTTPException(400, "Повторы инициатив запрещены")
    if any(item_id not in CATALOG for item_id in initiative_ids):
        raise HTTPException(400, "Неизвестный ID инициативы")

    selected = [CATALOG[item_id] for item_id in initiative_ids]
    if {item["sphere"] for item in selected} != set(SPHERES):
        raise HTTPException(400, "Выберите ровно одну инициативу в каждой сфере")

    spent = sum(item["cost"] for item in selected)
    if spent > CITY_DATA["total_budget"]:
        raise HTTPException(400, "Превышен бюджет")

    # Эффекты суммируются и одинаково применяются ко всем пяти районам.
    impacts = {
        sphere: sum(item["impact"].get(sphere, 0) for item in selected)
        for sphere in SPHERES
    }
    districts = []
    for district in CITY_DATA["districts"]:
        before = {sphere: district[sphere] for sphere in SPHERES}
        after = {
            sphere: min(100, max(0, before[sphere] + impacts[sphere]))
            for sphere in SPHERES
        }
        old_score = district_score(before)
        new_score = district_score(after)
        districts.append({
            "name": district["name"],
            "before": before,
            "after": after,
            "old_qol": round(old_score, 2),
            "new_qol": round(new_score, 2),
            "delta": round(new_score - old_score, 2),
        })

    old_qol = mean(district_score(row["before"]) for row in districts)
    new_qol = mean(district_score(row["after"]) for row in districts)
    result = {
        "selected_ids": initiative_ids,
        "total_budget": CITY_DATA["total_budget"],
        "spent_budget": spent,
        "remaining_budget": CITY_DATA["total_budget"] - spent,
        "old_qol": round(old_qol, 2),
        "new_qol": round(new_qol, 2),
        "qol_delta": round(new_qol - old_qol, 2),
        "spending_efficiency": round((new_qol - old_qol) / spent, 4),
        "districts": districts,
    }
    audit, source = generate_audit(result, selected)
    return {**result, "ai_audit": audit, "ai_source": source}
