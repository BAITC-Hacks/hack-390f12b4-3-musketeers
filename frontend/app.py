import os

import pandas as pd
import requests
import streamlit as st


st.set_page_config(page_title="Аким на 5 часов", page_icon="🏙️", layout="wide")
API_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
SPHERES = {
    "transport": "Транспорт",
    "greening": "Озеленение",
    "social": "Соцсфера",
    "safety": "Безопасность",
    "services": "Городские сервисы",
}


@st.cache_data(ttl=60)
def load_data(api_url: str) -> dict:
    response = requests.get(f"{api_url}/api/data", timeout=(3, 10))
    response.raise_for_status()
    return response.json()


st.title("🏙️ Аким на 5 часов")
st.caption("Astana Innovations · 100 млн ₸ · 5 решений · 5 районов")
st.caption(
    "Учебная модель: цены и эффекты условные. Эффект каждой инициативы "
    "применяется ко всем районам; QoL — среднее 25 показателей."
)

try:
    city = load_data(API_URL)
except (requests.RequestException, ValueError):
    st.error("Не удалось загрузить данные. Запустите FastAPI на порту 8000.")
    st.code("python -m uvicorn backend.main:app --reload")
    if st.button("Повторить подключение"):
        st.rerun()
    st.stop()

left, right = st.columns([1.2, 1.8], gap="large")
with left:
    st.subheader("Ваши решения")
    selected_ids = []
    spent = 0
    for sphere, label in SPHERES.items():
        options = {item["id"]: item for item in city["initiatives"][sphere]}
        labels = {
            item_id: f"{item['title']} — {item['cost']} млн ₸"
            for item_id, item in options.items()
        }
        selected_id = st.selectbox(
            label,
            options=list(options),
            format_func=labels.__getitem__,
            key=f"choice_{sphere}",
        )
        selected_ids.append(selected_id)
        spent += options[selected_id]["cost"]

    remaining = city["total_budget"] - spent
    st.metric("Потраченный бюджет", f"{spent} / {city['total_budget']} млн ₸")
    st.caption(f"Остаток: {remaining} млн ₸")
    st.progress(min(spent / city["total_budget"], 1.0))
    if remaining < 0:
        st.error(f"Превышен бюджет на {-remaining} млн ₸. Измените решения.")

    # При изменении выбора предыдущий результат больше не показывается
    if st.session_state.get("result", {}).get("selected_ids") != selected_ids:
        st.session_state.pop("result", None)

    if st.button(
        "Запустить AI-симуляцию",
        type="primary",
        disabled=remaining < 0,
        use_container_width=True,
    ):
        st.session_state.pop("result", None)
        with st.spinner("Рассчитываем показатели и готовим аудит…"):
            try:
                response = requests.post(
                    f"{API_URL}/api/simulate",
                    json=selected_ids,
                    timeout=(3, 45),
                )
                if response.ok:
                    st.session_state["result"] = response.json()
                else:
                    detail = response.json().get("detail", "Ошибка симуляции")
                    st.error(f"Симуляция отклонена: {detail}")
            except (requests.RequestException, ValueError):
                st.error("Не удалось выполнить симуляцию. Проверьте бэкенд и повторите.")

with right:
    result = st.session_state.get("result")
    if not result:
        st.info("Выберите пять инициатив и запустите симуляцию.")
    else:
        st.subheader("Результаты управления")
        metric1, metric2, metric3 = st.columns(3)
        metric1.metric(
            "Astana QoL Score",
            f"{result['new_qol']:.2f}",
            delta=f"{result['qol_delta']:+.2f} балла",
        )
        metric2.metric("Базовый уровень", f"{result['old_qol']:.2f}")
        metric3.metric("Эффективность расходов", f"{result['spending_efficiency']:.3f}")
        st.caption(
            "Эффективность = прирост QoL / потраченные млн ₸. "
            f"Потрачено: {result['spent_budget']} млн ₸; "
            f"остаток: {result['remaining_budget']} млн ₸."
        )

        st.subheader("Индексы районов: до и после")
        chart = pd.DataFrame([
            {"Район": row["name"], "До": row["old_qol"], "После": row["new_qol"]}
            for row in result["districts"]
        ]).set_index("Район")
        st.bar_chart(chart, stack=False, color=["#94a3b8", "#10b981"])

        with st.expander("Показатели районов по сферам"):
            table = pd.DataFrame([
                {
                    "Район": row["name"],
                    **{label: row["after"][sphere] for sphere, label in SPHERES.items()},
                    "Прирост QoL": row["delta"],
                }
                for row in result["districts"]
            ]).set_index("Район")
            st.dataframe(table, use_container_width=True)

        st.subheader("Экспертное AI-заключение")
        if result["ai_source"] == "fallback_no_key":
            st.info("Демо-заключение: OPENAI_API_KEY не задан. Расчёты выполнены полностью.")
        elif result["ai_source"] == "fallback_api_error":
            st.warning("OpenAI недоступен или вернул некорректный ответ. Показан локальный аудит.")
        else:
            st.caption("Аудит подготовлен gpt-4o-mini на основе рассчитанных показателей.")
        tabs = st.tabs(["Сильные стороны", "Риски", "Рекомендации"])
        for tab, key in zip(tabs, ("strengths", "risks", "recommendations")):
            with tab:
                for item in result["ai_audit"][key]:
                    st.markdown(f"- {item}")
