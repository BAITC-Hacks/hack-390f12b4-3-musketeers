"""Optional, deterministic training shocks; the official dataset stays immutable."""
from copy import deepcopy

EVENTS = [
    {"id": "none", "title": "Обычный сценарий", "description": "Исходные условия официального датасета.", "shocks": []},
    {"id": "winter-v1", "title": "Суровая зима", "description": "Учебное событие: надёжность ЖКХ снижается в Алматы на 15, в Сарыарке на 10 пунктов. Пересмотрите приоритеты в прежнем бюджете.",
     "shocks": [{"district": "almaty", "indicator": "C1", "delta": -15}, {"district": "saryarka", "indicator": "C1", "delta": -10}]},
    {"id": "growth-v1", "title": "Рост нового района", "description": "Учебное событие: в Нуре доступность транспорта и образования снижается на 10 пунктов. Бюджет остаётся равным 100.",
     "shocks": [{"district": "nura", "indicator": "T2", "delta": -10}, {"district": "nura", "indicator": "S1", "delta": -10}]},
]


def event_data(data, event_id):
    event = next(e for e in EVENTS if e["id"] == event_id)
    adjusted = deepcopy(data)
    for shock in event["shocks"]:
        district = next(d for d in adjusted["districts"] if d["id"] == shock["district"])
        key = shock["indicator"]
        district["values"][key] = max(0, min(100, district["values"][key] + shock["delta"]))
    return adjusted
