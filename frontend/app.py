"""Streamlit UI. Server owns prices, validation, scores and AI secrets."""
import json
import os

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Аким на 5 часов", page_icon="🏙️", layout="wide")
API_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
st.markdown("""
<style>
.block-container {padding-top:2rem; max-width:1440px}
h1 {letter-spacing:-.04em}
[data-testid="stMetric"] {background:white;border:1px solid #E0E8EF;border-radius:14px;padding:16px}
[data-testid="stMetricLabel"] {color:#516376}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:14px}
</style>
""", unsafe_allow_html=True)


def api(path, payload=None):
    try:
        response = requests.get(API_URL + path, timeout=(3, 10)) if payload is None else requests.post(API_URL + path, json=payload, timeout=(3, 45))
        data = response.json()
        if not response.ok:
            detail = data.get("detail", "Ошибка сервера")
            if isinstance(detail, list):
                detail = " · ".join(x.get("message", x.get("msg", "Некорректные данные")) for x in detail)
            return None, str(detail)
        return data, None
    except (requests.RequestException, ValueError):
        return None, "Сервер недоступен. Проверьте, запущен ли python run.py."


@st.cache_data(ttl=30)
def load_city(url):
    response = requests.get(url + "/api/data", timeout=(3, 10))
    response.raise_for_status()
    return response.json()


st.caption("ASTANA INNOVATIONS  /  УЧЕБНАЯ ГОРОДСКАЯ ЛАБОРАТОРИЯ")
st.title("Аким на 5 часов")
st.write("Пять решений. Один бюджет. Посмотрите, как ваш план меняет жизнь районов.")
st.caption("Синтетические данные · 100 условных единиц · Горизонт модели: 2 года")

try:
    city = load_city(API_URL)
except (requests.RequestException, ValueError):
    st.error("Не удалось загрузить город. Запустите приложение командой python run.py.")
    if st.button("Повторить подключение"):
        st.cache_data.clear()
        st.rerun()
    st.stop()

catalog = {m["id"]: m for m in city["measures"]}
districts = {d["id"]: d for d in city["districts"]}
indicator_names = city["indicators"]
directions = city["directions"]
ss = st.session_state
ss.setdefault("plan", [])
ss.setdefault("saved", [])
ss.setdefault("edit_index", None)


def payload(plan=None):
    return {"decisions": ss["plan"] if plan is None else plan, "ruleset": city["ruleset"], "dataset_version": city["version"]}


def invalidate():
    for key in ("result", "audit", "recommendations"):
        ss.pop(key, None)


def replace_plan(plan):
    ss["plan"] = plan
    ss["edit_index"] = None
    ss["pending_section"] = "Планирование"
    invalidate()


def label_decision(decision):
    title = catalog[decision["measure_id"]]["title"]
    target = districts[decision["district_id"]]["name"] if decision.get("district_id") else "Весь город"
    return f"{title} · {target}"


if "pending_plan" in ss:
    replace_plan(ss.pop("pending_plan"))
if "pending_edit" in ss:
    index = ss.pop("pending_edit")
    decision = ss["plan"][index]
    ss["edit_index"] = index
    ss["filter_direction"] = catalog[decision["measure_id"]]["direction"]
    ss["catalog_measure"] = decision["measure_id"]
    if decision.get("district_id"):
        ss["catalog_district"] = decision["district_id"]
if "pending_section" in ss:
    ss["section"] = ss.pop("pending_section")

toolbar = st.columns([1, 1, 3])
if toolbar[0].button("Загрузить пример", use_container_width=True):
    replace_plan(city["example"]["decisions"])
    st.rerun()
if toolbar[1].button("Очистить план", disabled=not ss["plan"], use_container_width=True):
    replace_plan([])
    st.rerun()
toolbar[2].caption("Ровно 5 разных мер · " + ("Не более 2 из одного направления" if city["ruleset"] == "dataset-v1" else "По одной мере из каждого направления"))

projection_response, preview_error = api("/api/preview", payload())
projection = projection_response["projection"] if projection_response else city["baseline"]
spent = sum(catalog[d["measure_id"]]["cost"] for d in ss["plan"])
metrics = st.columns(4)
metrics[0].metric("Бюджет использован", f"{spent} / 100")
metrics[1].metric("Осталось", f"{100-spent} усл. ед.")
metrics[2].metric("Решений", f"{len(ss['plan'])} / 5")
metrics[3].metric("Предварительный Score" if ss["plan"] else "Исходный Score", f"{projection['result']['score']:.2f}", delta=f"{projection['delta_score']:+.2f}" if ss["plan"] else None)
if preview_error:
    st.error(preview_error)
st.progress(min(spent / 100, 1.0))

section = st.radio("Раздел", ["Планирование", "Результаты и AI", "Сравнение", "Как устроена модель"],
                   horizontal=True, key="section", label_visibility="collapsed")

if section == "Планирование":
    left, right = st.columns([1, 1.15], gap="large")
    with left:
        editing = ss["edit_index"]
        st.subheader("Выберите инициативу" if editing is None else f"Замена решения {editing + 1}")
        if editing is not None and st.button("Отменить замену"):
            ss["edit_index"] = None
            st.rerun()
        direction = st.selectbox("Направление", list(directions), format_func=directions.get, key="filter_direction")
        options = [m["id"] for m in city["measures"] if m["direction"] == direction]
        if ss.get("catalog_measure") not in options:
            ss["catalog_measure"] = options[0]
        mid = st.selectbox("Мероприятие", options, format_func=lambda m: catalog[m]["title"], key="catalog_measure")
        measure = catalog[mid]
        with st.container(border=True):
            a, b, c = st.columns(3)
            a.write(f"**{measure['cost']}** усл. ед.")
            b.write(f"**{measure['lag']}** кв. до эффекта")
            c.write("**Весь город**" if measure["scope"] == "city" else "**Один район**")
            target = st.selectbox("Район реализации", list(districts), format_func=lambda d: districts[d]["name"], key="catalog_district") if measure["scope"] == "district" else None
            fraction = (city["horizon"] - measure["lag"]) / city["horizon"]
            st.caption(f"За горизонт модели реализуется {fraction:.1%} полного эффекта.")
            st.dataframe(pd.DataFrame([{"Показатель": indicator_names[k], "Полный эффект": f"{v:+g}", "За 2 года": f"{v*fraction:+g}"} for k, v in measure["effects"].items()]), hide_index=True, use_container_width=True)
            decision = {"measure_id": mid, "district_id": target}
            candidate = list(ss["plan"])
            if editing is None:
                candidate.append(decision)
            else:
                candidate[editing] = decision
            if len(candidate) > 5:
                candidate_error = "Пять решений уже выбраны. Удалите или замените одно из них."
            else:
                _, candidate_error = api("/api/preview", payload(candidate))
            if candidate_error:
                st.caption(candidate_error)
            if st.button("Добавить в план" if editing is None else "Применить замену", type="primary", disabled=bool(candidate_error), use_container_width=True):
                replace_plan(candidate)
                st.rerun()
        with st.expander("Все 14 мероприятий"):
            st.dataframe(pd.DataFrame([{"ID": m["id"], "Мероприятие": m["title"], "Стоимость": m["cost"], "Лаг": m["lag"], "Охват": "Город" if m["scope"] == "city" else "Район"} for m in city["measures"]]), hide_index=True, use_container_width=True)

    with right:
        st.subheader("Ваш план")
        if not ss["plan"]:
            st.info("Добавьте инициативу слева или загрузите готовый пример.")
        for index, decision in enumerate(ss["plan"]):
            with st.container(border=True):
                st.write(f"**{index+1}. {label_decision(decision)}**")
                price, edit, remove = st.columns([1, 1, 1])
                price.caption(f"{catalog[decision['measure_id']]['cost']} усл. ед.")
                if edit.button("Заменить", key=f"edit_{index}"):
                    ss["pending_edit"] = index
                    st.rerun()
                if remove.button("Убрать", key=f"remove_{index}"):
                    replace_plan(ss["plan"][:index] + ss["plan"][index+1:])
                    st.rerun()
        if st.button("Рассчитать итог", disabled=len(ss["plan"]) != 5 or bool(preview_error), type="primary", use_container_width=True):
            result, error = api("/api/simulate", payload())
            if error:
                st.error(error)
            else:
                ss["result"] = result
                ss["pending_section"] = "Результаты и AI"
                st.rerun()
        st.subheader("Районы: до и после")
        st.caption("Предварительное влияние текущего набора; итоговый сценарий требует пяти решений.")
        chart = pd.DataFrame([{"Район": d["name"], "До": d["score_before"], "После": d["score_after"]} for d in projection["districts"]]).set_index("Район")
        st.bar_chart(chart, stack=False, color=["#A6B6C8", "#087F8C"])
        for d in projection["districts"]:
            critical = [indicator_names[k] for k, v in d["after"].items() if v < 40]
            if critical:
                st.warning(f"{d['name']}: ниже 40 — {', '.join(critical)}.")

if section == "Результаты и AI":
    result = ss.get("result")
    if not result:
        st.info("Соберите пять решений и нажмите «Рассчитать итог» во вкладке планирования.")
    else:
        st.subheader("Astana Quality of Life Score")
        a, b, c = st.columns(3)
        a.metric("Итог", f"{result['result']['score']:.2f}", f"{result['delta_score']:+.2f} к базе")
        b.metric("Критических значений", str(result["result"]["critical_count"]), f"{result['result']['critical_count']-result['baseline']['critical_count']:+d}", delta_color="inverse")
        c.metric("Минимальный районный балл", f"{result['result']['minimum']:.2f}")
        st.caption("Слабейший район: " + ", ".join(districts[d]["name"] for d in result["result"]["weakest_ids"]))
        st.write("**Из чего складывается изменение Score**")
        st.dataframe(pd.DataFrame([
            {"Компонент": "Рост среднего по городу", "Вклад": result["decomposition"]["average"]},
            {"Компонент": "Улучшение минимального районного балла", "Вклад": result["decomposition"]["weakest"]},
            {"Компонент": "Изменение штрафа за значения ниже 40", "Вклад": result["decomposition"]["critical"]},
        ]).round(2), hide_index=True, use_container_width=True)
        with st.expander("Все показатели и вклад мероприятий", expanded=False):
            selected_d = st.selectbox("Посмотреть район", list(districts), format_func=lambda d: districts[d]["name"])
            row = next(d for d in result["districts"] if d["id"] == selected_d)
            st.dataframe(pd.DataFrame([{"Код": k, "Показатель": indicator_names[k], "До": row["before"][k], "После": row["after"][k], "Изменение": row["delta"][k]} for k in indicator_names]).round(2), hide_index=True, use_container_width=True)
            for contribution in result["contributions"]:
                st.write(f"**{contribution['title']}**")
                st.caption(" · ".join(f"{indicator_names[k]} {v:+g}" for k, v in contribution["effects"].items()))
            if result["synergies"]:
                st.write("**Синергии**")
                for s in result["synergies"]:
                    st.write(f"{' + '.join(s['pair'])} · {districts[s['district_id']]['name']}: " + ", ".join(f"{indicator_names[k]} {v:+g}" for k, v in s["effects"].items()))
            else:
                st.caption("Синергий в этом сценарии нет.")
            st.caption("Вклад мер показан в показателях. Вклады в Score нелинейны и не складываются отдельно.")

        st.subheader("Проверенные улучшения")
        if st.button("Найти лучшие замены одного решения"):
            with st.spinner("Сравниваем допустимые замены…"):
                value, error = api("/api/recommend", payload())
                if error:
                    st.error(error)
                else:
                    ss["recommendations"] = value
        recs = ss.get("recommendations")
        if recs:
            st.caption(f"Проверено допустимых альтернатив: {recs['checked']}. Поиск ограничен заменой одной меры, включая смену района.")
            if not recs["candidates"]:
                st.info("Среди проверенных замен улучшений не найдено. Это не доказательство глобального оптимума.")
            for candidate in recs["candidates"]:
                with st.container(border=True):
                    st.write(f"**Score {candidate['score']:.2f} · {candidate['gain']:+.2f} · Бюджет {candidate['spent']}/100**")
                    st.write("Убрать: " + label_decision(candidate["removed"]))
                    st.write("Добавить: " + label_decision(candidate["added"]))
                    st.caption(f"Критических значений: {candidate['critical_count']} · Минимальный районный балл: {candidate['minimum']:.2f}")
                    if st.button("Применить этот вариант", key=candidate["id"]):
                        ss["pending_plan"] = candidate["scenario"]["decisions"]
                        st.rerun()

        st.subheader("AI-советник")
        st.caption("AI объясняет факты расчёта. Вызов выполняется только по этой кнопке.")
        if st.button("Получить AI-анализ", type="primary"):
            with st.spinner("Готовим объяснение сценария…"):
                report, error = api("/api/analyze", payload())
                if error:
                    st.error(error)
                else:
                    ss["audit"] = report
        report = ss.get("audit")
        if report:
            if report["source"] != "openai":
                reasons = {"fallback_no_key": "ключ API не настроен", "fallback_no_model": "модель не настроена", "fallback_api_error": "AI-сервис недоступен или вернул неподтверждённый ответ"}
                st.info("Резервный аналитический отчёт. " + reasons.get(report["source"], "AI-сервис недоступен") + ". Это локальный отчёт, не ответ AI.")
            else:
                st.caption(f"Ответ OpenAI · {report['model']}" + (" · из кеша" if report["cached"] else ""))
            audit = report["audit"]
            def show_claim(claim):
                st.write(claim["text"])
                for evidence in claim["evidence_ids"]:
                    st.caption(report["facts"][evidence])
            show_claim(audit["summary"])
            for name, key in [("Сильные стороны", "strengths"), ("Компромиссы", "tradeoffs"), ("Оставшиеся проблемы", "remaining_problems")]:
                st.write(f"**{name}**")
                for claim in audit[key]:
                    show_claim(claim)
            if audit["recommendations"]:
                st.write("**Рекомендации по рассчитанным альтернативам**")
                for recommendation in audit["recommendations"]:
                    st.write(report["facts"]["candidate:" + recommendation["candidate_id"]])
            for limitation in audit["limitations"]:
                st.caption(limitation)

        st.download_button("Скачать сценарий JSON", json.dumps(payload(), ensure_ascii=False, indent=2), file_name="astana-scenario.json", mime="application/json")
        if st.button("Сохранить для сравнения"):
            saved = {"name": f"Сценарий {len(ss['saved'])+1}", "scenario": payload(), "result": result}
            ss["saved"] = [*ss["saved"], saved][-4:]
            st.success("Сохранено во вкладке «Сравнение» на время этой сессии.")

if section == "Сравнение":
    st.subheader("Сравнение сценариев")
    st.caption("До четырёх сценариев в текущей сессии. Для сохранения между запусками используйте JSON.")
    if ss["saved"]:
        rows = [{"Сценарий": x["name"], "Score": x["result"]["result"]["score"], "Бюджет": x["result"]["spent"], "Критических": x["result"]["result"]["critical_count"], "Минимум района": x["result"]["result"]["minimum"]} for x in ss["saved"]]
        st.dataframe(pd.DataFrame(rows).round(2), hide_index=True, use_container_width=True)
        for index, saved in enumerate(ss["saved"]):
            with st.expander(saved["name"]):
                for d in saved["scenario"]["decisions"]:
                    st.write(label_decision(d))
                if st.button("Вернуть этот сценарий", key=f"restore_{index}"):
                    ss["pending_plan"] = saved["scenario"]["decisions"]
                    st.rerun()
    else:
        st.info("После расчёта сохраните результат для сравнения.")
    upload = st.file_uploader("Загрузить сценарий JSON", type=["json"])
    if upload is not None and st.button("Проверить и загрузить JSON"):
        try:
            if upload.size > 16384:
                raise ValueError("Файл больше 16 КБ.")
            imported = json.loads(upload.getvalue().decode("utf-8-sig"))
            checked, error = api("/api/simulate", imported)
            if error:
                st.error(error)
            else:
                ss["pending_plan"] = checked["scenario"]["decisions"]
                st.rerun()
        except (ValueError, UnicodeError):
            st.error("Не удалось прочитать файл сценария JSON.")

if section == "Как устроена модель":
    st.subheader("Прозрачный расчёт")
    st.code("I′ = clip(I + Σ(effect × (8 − lag) / 8) + synergy, 0, 100)\nD = Σ(weight × I′)\nScore = 0.7 × среднее_по_населению + 0.3 × минимум_района − N_crit")
    st.write("N_crit — число пар «район × показатель» со значением строго ниже 40. Значение 40 не штрафуется.")
    st.write("Эффекты суммируются до ограничения 0–100. Стоимость оплачивается полностью. Порядок решений не влияет на результат.")
    st.caption("Все показатели уже направлены одинаково: больше — лучше. Денежная единица условная, не тенге.")
    st.dataframe(pd.DataFrame([{"Код": k, "Показатель": indicator_names[k], "Вес": v} for k, v in city["weights"].items()]), hide_index=True, use_container_width=True)
    st.write("**Несовместимости**")
    for conflict in city["conflicts"]:
        st.write(conflict["reason"])
    st.caption("Основной режим следует подробному датасету: до двух мер направления. Требование по одной мере каждого направления включается организатором через настройку сервера.")
    st.caption("Синтетическая модель не учитывает эксплуатационные расходы, реальные причинные связи и неопределённость эффектов. Версия: " + city["version"])
