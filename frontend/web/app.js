const $ = (q, root = document) => root.querySelector(q);
const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const number = (value, digits = 2) => Number(value).toLocaleString("ru-RU", {minimumFractionDigits: digits, maximumFractionDigits: digits});
const signed = value => (value > 0 ? "+" : "") + number(value);
const icons = {
  city:'<path d="M3 21V9h6v12M9 21V3h7v18M16 21V12h5v9M1 21h22M12 7h1M12 11h1M12 15h1M5 12h1M5 16h1M18 15h1M18 18h1"/>',
  grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  chart:'<path d="M4 3v17h17M8 15v-4M13 15V7M18 15V4"/>',
  compare:'<path d="M5 4v16M19 4v16M8 8h8l-3-3M16 16H8l3 3"/>',
  help:'<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 0 1 5 0c0 2-2.5 2-2.5 4M12 17h.01"/>',
  transport:'<rect x="5" y="3" width="14" height="16" rx="3"/><path d="M5 10h14M8 19v2M16 19v2M9 6h6M8 14h1M15 14h1"/>',
  ecology:'<path d="M20 3C8 2 3 7 5 14c2 6 14 6 15-11ZM4 21 15 10"/>',
  social:'<path d="m2 9 10-6 10 6M5 8v13h14V8M10 21v-6h4v6M8 11h1M15 11h1"/>',
  safety:'<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="m8 12 3 3 5-6"/>',
  services:'<path d="m13 2-9 12h7l-1 8 10-13h-8Z"/>',
  arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
  close:'<path d="m6 6 12 12M6 18 18 6"/>',
  check:'<path d="m5 12 4 4L19 6"/>',
  pin:'<path d="M19 10c0 6-7 11-7 11S5 16 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  wallet:'<rect x="3" y="6" width="18" height="14" rx="3"/><path d="M3 8V5a2 2 0 0 1 2-2h12v3M16 11h5v5h-5a2 2 0 0 1 0-5Z"/>',
  spark:'<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5ZM20 2v4M18 4h4"/>',
  edit:'<path d="m15 4 5 5M3 21l5-1L21 7a2 2 0 0 0-4-4L4 16ZM13 21h8"/>',
  download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  upload:'<path d="M12 16V4m-5 5 5-5 5 5M4 16v5h16v-5"/>',
  north:'<path d="m12 3 7 18-7-5-7 5Z"/>',
  undo:'<path d="m8 3-5 5 5 5M3 8h11a7 7 0 0 1 0 14"/>',
  folder:'<path d="M3 7V4h6l3 3h9v13H3Z"/>',
};
const icon = name => '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">' + (icons[name] || icons.grid) + '</svg>';
const button = (label, action, className = "", extra = "") => '<button class="btn ' + className + '" data-action="' + action + '" ' + extra + '>' + label + '</button>';
const categoryIcon = direction => '<span class="category-icon ' + direction + '">' + icon(direction) + '</span>';
const DIR = {transport:"Транспорт",ecology:"Озеленение",social:"Социальная сфера",safety:"Безопасность",services:"Сервисы"};
const PREFIX = {transport:"T",ecology:"E",social:"S",safety:"B",services:"C"};
const DESCRIPTIONS = {
  M1:"Меньше пробок и доступнее общественный транспорт.",
  M2:"Плавнее движение на перекрёстках и безопаснее дороги.",
  M3:"Новая транспортная связь для выбранного района.",
  M4:"Больше зелёных пространств и чище воздух рядом с домом.",
  M5:"Чище воздух и надёжнее коммунальная инфраструктура.",
  M6:"Больше зелени и лучше качество воздуха во всём городе.",
  M7:"Больше мест в школах и детских садах района.",
  M8:"Доступнее поликлиники и первичная медицинская помощь.",
  M9:"Развитие социальной инфраструктуры и безопаснее дворы.",
  M10:"Лучше освещённые улицы и выше безопасность.",
  M11:"Безопаснее переходы и дороги рядом со школами.",
  M12:"Быстрее решение обращений жителей во всём городе.",
  M13:"Надёжнее тепло- и водоснабжение в выбранном районе.",
  M14:"Надёжнее ЖКХ и быстрее реакция на обращения.",
};
const STORAGE = "akim-workspace-v2";
const state = {city:null, plan:[], projection:null, view:"city", district:"nura", filter:"all", mapMode:"after", edit:null, result:null, report:null, recs:null, saved:[], scenarioName:"", busy:false, aiBusy:false, recBusy:false, revision:0};
let toastTimer, modalVersion = 0, modalMeasure = null, modalCandidate = null, lastFocus = null;
const measure = id => state.city.measures.find(m => m.id === id);
const district = id => state.city.districts.find(d => d.id === id);
const scenario = (plan = state.plan) => ({decisions:plan, ruleset:state.city.ruleset, dataset_version:state.city.version});
const targetName = d => d.district_id ? district(d.district_id).name : "Весь город";
const decisionName = d => measure(d.measure_id).title + " · " + targetName(d);
const remaining = () => state.city.budget - state.projection.spent;

async function api(path, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), path === "analyze" ? 55000 : 12000);
  try {
    const response = await fetch("/api/" + path, {method:body ? "POST" : "GET", headers:{"Content-Type":"application/json"}, body:body ? JSON.stringify(body) : undefined, signal:controller.signal});
    const data = await response.json();
    if (!response.ok) {
      const detail = data.detail;
      throw new Error(Array.isArray(detail) ? detail.map(e => e.message || e.msg).join(" ") : detail || "Не удалось выполнить запрос.");
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("Сервер не ответил вовремя. Попробуйте ещё раз.");
    if (error instanceof TypeError) throw new Error("Нет связи с сервером. Проверьте подключение и повторите.");
    throw error;
  } finally { clearTimeout(timeout); }
}

function toast(message) {
  const el = $("#toast"); el.textContent = message; el.classList.add("visible");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove("visible"), 5500);
}
function persist() {
  try {
    localStorage.setItem(STORAGE, JSON.stringify({scenario:scenario(), saved:state.saved.map(s => ({name:s.name, scenario:s.scenario}))}));
  } catch { toast("Браузер не разрешил сохранение. Скачайте сценарий в JSON, чтобы не потерять его."); }
}
async function changePlan(plan) {
  const checked = await api("preview", scenario(plan));
  state.plan = plan; state.projection = checked.projection; state.result = null; state.report = null; state.recs = null;
  state.edit = null; state.revision++; state.aiBusy = false; state.recBusy = false;
  persist();
}
async function restoreStorage() {
  let stored;
  try { stored = JSON.parse(localStorage.getItem(STORAGE) || "null"); }
  catch { toast("Сохранение браузера недоступно. Можно загрузить сценарий из JSON."); return; }
  if (!stored) return;
  if (stored.scenario) {
    try {
      const value = await api("preview", stored.scenario);
      state.plan = stored.scenario.decisions; state.projection = value.projection;
    } catch { toast("Сохранённый план не удалось проверить. Загружено исходное состояние города."); }
  }
  const saved = Array.isArray(stored.saved) ? stored.saved.slice(-4) : [];
  for (const item of saved) {
    try {
      const result = await api("simulate", item.scenario);
      state.saved.push({name:String(item.name || "Сценарий").slice(0,60),scenario:result.scenario,result});
    } catch { /* Invalid saved scenarios never become trusted results. */ }
  }
}

function header() {
  const titles = {city:"Обзор города",initiatives:"Инициативы",results:"Результат",compare:"Сравнение",help:"Как это работает"};
  return '<aside class="sidebar"><a class="brand" href="#city" data-view="city"><div class="brand-mark">А</div><div><strong>Аким на 5 часов</strong><small>CITY LAB · ASTANA</small></div></a><div class="nav-label">ВАШ ГОРОД</div><nav class="nav" aria-label="Основная навигация">' +
    [["city","city","Обзор города"],["initiatives","grid","Инициативы"],["results","chart","Результат"],["compare","compare","Сравнение"]].map(([view,i,title]) =>
      '<button class="nav-button ' + (state.view === view ? "active" : "") + '" data-view="' + view + '" aria-label="' + title + '" ' + (state.view === view ? 'aria-current="page"' : '') + '>' + icon(i) + '<span>' + title + '</span>' + (view === "initiatives" ? '<span class="nav-count">14</span>' : '') + '</button>').join("") +
    '</nav><div class="sidebar-bottom"><button class="nav-button ' + (state.view === "help" ? "active" : "") + '" data-view="help" aria-label="Как это работает">' + icon("help") + '<span>Как это работает</span></button><div class="sandbox-note"><strong>Маленькая модель.<br>Большие решения.</strong>Исследуйте, как ваш выбор меняет жизнь города.</div><div class="team">HACKALEM AI · 3-MUSKETEERS</div></div></aside>' +
    '<div class="shell"><header class="topbar"><div class="breadcrumb"><span>Симулятор</span><span>/</span><strong>' + titles[state.view] + '</strong></div><div class="mobile-brand"><span class="brand-mark">А</span>Аким на 5 часов</div><div class="topbar-end"><span class="status">Учебная симуляция</span>' + button(icon("help") + "Правила", "help", "ghost small") + '<div class="avatar" title="Локальный сценарий">АК</div></div></header>';
}
function stats() {
  const p = state.projection, score = p.result.score, count = state.plan.length;
  return '<section class="budget-strip" aria-label="Бюджет и результат текущего плана"><div class="stat"><div class="stat-label">Осталось в бюджете' + icon("wallet") + '</div><div class="stat-value">' + remaining() + '<span class="suffix">/ ' + state.city.budget + '</span></div><div class="budget-track"><span style="width:' + p.spent / state.city.budget * 100 + '%"></span></div><div class="stat-note">Потрачено ' + p.spent + ' условных единиц</div></div><div class="stat"><div class="stat-label">Принято решений' + icon("check") + '</div><div class="stat-value">' + count + '<span class="suffix">из 5</span></div><div class="decision-track">' + Array.from({length:5},(_,i) => '<span class="' + (i < count ? "filled" : "") + '"></span>').join("") + '</div><div class="stat-note">' + (count === 5 ? "План готов к оценке" : "Осталось выбрать: " + (5-count)) + '</div></div><div class="stat"><div class="stat-label">' + (state.result ? "Итоговая оценка" : count ? "Прогноз качества жизни" : "Качество жизни сейчас") + icon("chart") + '</div><div class="stat-value">' + number(score) + (count ? '<span class="delta ' + (p.delta_score < 0 ? "down" : "") + '">' + signed(p.delta_score) + '</span>' : '') + '</div><div class="stat-note">Astana Quality of Life Score</div></div></section>';
}
function heading(eyebrow,title,description,action="") {
  return '<div class="page-heading"><div><div class="eyebrow">' + eyebrow + '</div><h1 tabindex="-1" id="page-title">' + title + '</h1><p>' + description + '</p></div>' + action + '</div>';
}
function render() {
  const active = document.activeElement;
  const focusKey = ["data-filter","data-district","data-map"].find(key => active?.hasAttribute(key));
  const focusValue = focusKey && active.getAttribute(focusKey);
  const views = {city:cityView, initiatives:catalogView, results:resultsView, compare:compareView, help:helpView};
  $("#app").innerHTML = header() + '<main class="workspace ' + (state.view === "initiatives" ? "catalog-workspace" : "") + '" id="content">' + views[state.view]() +
    '<footer class="footer"><span>Синтетический город · 5 районов · Горизонт: 2 года</span><span>Создавайте город, в котором хочется жить.</span></footer></main></div>';
  if (focusKey) document.querySelector("[" + focusKey + '="' + CSS.escape(focusValue) + '"]')?.focus({preventScroll:true});
  if ($("#scenario-name")) $("#scenario-name").value = state.scenarioName;
}
function navigate(view) {
  if (!["city","initiatives","results","compare","help"].includes(view)) return;
  state.view = view; render(); window.scrollTo({top:0});
  $("#page-title")?.focus({preventScroll:true});
}

const mapShapes = {
  saryarka:{d:"M81 97 174 53 291 63 304 137 240 181 160 170 112 191 60 146Z",x:186,y:117},
  baikonur:{d:"M302 62 397 59 449 85 418 159 344 175 314 137Z",x:368,y:111},
  almaty:{d:"M454 91 511 135 548 221 468 258 415 222 427 163Z",x:483,y:187},
  yesil:{d:"M252 199 313 164 349 191 414 181 403 232 455 271 405 317 300 327 261 277Z",x:349,y:247},
  nura:{d:"M65 173 110 208 158 191 228 204 238 282 288 338 199 364 96 321 50 249Z",x:151,y:266},
};
function mapSvg() {
  return '<div class="map-wrap"><svg class="city-map" viewBox="0 0 600 405" aria-label="Условная интерактивная схема пяти районов"><defs><pattern id="mapgrid" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".65" fill="#dfe6ef"/></pattern></defs><rect width="600" height="405" fill="url(#mapgrid)"/><path d="M-15 174C98 194 111 235 199 199S299 134 346 172 389 169 431 171 478 272 625 265" stroke="#d4eaf6" stroke-width="13" fill="none"/><path d="M-15 174C98 194 111 235 199 199S299 134 346 172 389 169 431 171 478 272 625 265" stroke="#fff" stroke-opacity=".7" stroke-width="1.5" fill="none"/>' +
    state.projection.districts.map(d => {
      const shape = mapShapes[d.id], score = state.mapMode === "before" ? d.score_before : d.score_after;
      const color = score < 50 ? "#f1e8d7" : score < 58 ? "#dce9ed" : score < 65 ? "#d4e7f1" : "#c5dff1";
      return '<g><path class="map-district ' + (state.district === d.id ? 'selected' : '') + '" d="' + shape.d + '" fill="' + (state.district === d.id ? "#e1ebff" : color) + '" data-district="' + d.id + '" role="button" tabindex="0" aria-label="Район ' + escape(d.name) + ', оценка ' + number(score) + '" aria-pressed="' + (state.district === d.id) + '"/><text class="map-label ' + (state.district === d.id ? 'selected-label' : '') + '" x="' + shape.x + '" y="' + shape.y + '">' + escape(d.name) + '</text><text class="map-label map-score" x="' + shape.x + '" y="' + (shape.y+22) + '">' + number(score,1) + ' балла</text></g>';
    }).join("") + '<g stroke="#c8d3df" stroke-width="1" fill="none"><path d="M282 371h100m-83-9v18m67-18v18"/><path d="M556 299v43m-6-38h12m-12 31h12"/></g><text x="341" y="389" fill="#a8b7c8" font-size="8" text-anchor="middle" letter-spacing="2">ASTANA CITY LAB</text></svg><div class="map-compass">С' + icon("north") + '</div><span class="map-caption">УСЛОВНАЯ СХЕМА · НЕ ГЕОГРАФИЧЕСКАЯ КАРТА</span></div>';
}
function districtDetail() {
  const d = state.projection.districts.find(d => d.id === state.district);
  const values = state.mapMode === "before" ? d.before : d.after;
  const critical = Object.entries(values).filter(([,v]) => v < 40);
  return '<section class="panel district-detail"><div class="panel-body"><div class="detail-main"><div class="row between"><span class="eyebrow">В ФОКУСЕ</span><span class="pill ' + (critical.length ? "amber" : "green") + '">' + (critical.length ? "Нужна поддержка" : "Без критических значений") + '</span></div><div class="row between"><h2 class="district-title">' + escape(d.name) + '</h2><span class="district-number">' + number(state.mapMode === "before" ? d.score_before : d.score_after,1) + '</span></div><p class="district-profile">' + escape(d.profile) + '</p></div><div class="detail-meters">' +
    Object.keys(DIR).map(key => {
      const value = Object.entries(values).filter(([k]) => k.startsWith(PREFIX[key])).reduce((sum,[,v]) => sum+v,0)/2;
      return '<div class="category-meter"><div class="row between"><span class="row">' + icon(key) + DIR[key] + '</span><span>' + number(value,1) + '</span></div><div class="meter"><span class="' + (value < 45 ? "warn" : "") + '" style="width:' + value + '%"></span></div></div>';
    }).join("") + '</div><div class="district-action">' + (critical.length ? '<div class="callout warning"><strong>Что требует внимания</strong>' + critical.map(([k,v]) => escape(state.city.indicators[k]) + ': ' + number(v,0)).join(" · ") + '</div>' : '') + '<p class="subtle-note">Направления — среднее двух показателей, шкала 0–100.</p>' + button('Улучшить этот район ' + icon("arrow"),"district-initiatives","primary full") + '</div><details class="disclosure"><summary>Все 10 показателей района</summary>' + indicatorTable(d) + '</details></div></section>';
}
function cityView() {
  return heading("ВАША ОЧЕРЕДЬ МЕНЯТЬ ГОРОД","Город начинается с решений","Изучите районы, распределите бюджет и оцените перемены.",
    button(icon("spark") + "Готовый пример","example")) + stats() +
    '<div class="content-grid"><section class="panel"><div class="panel-head"><div><h2>Пять районов. Общий результат.</h2><p>Выберите район на схеме, чтобы узнать, что ему нужно.</p></div><div class="segmented" aria-label="Состояние карты"><button data-map="before" class="' + (state.mapMode === "before" ? "active" : "") + '" aria-pressed="' + (state.mapMode === "before") + '">Сейчас</button><button data-map="after" class="' + (state.mapMode === "after" ? "active" : "") + '" aria-pressed="' + (state.mapMode === "after") + '">С планом</button></div></div>' +
    mapSvg() + '<div class="map-legend"><span class="legend-item"><i class="dot amber"></i>Оценка ниже 50</span><span class="legend-item"><i class="dot blue"></i>Оценка от 50</span><span class="legend-last">Больше — лучше</span></div></section>' + districtDetail() + '</div>' +
    '<div class="steps"><div class="step"><span class="step-num">01</span><div><strong>Поймите свой город</strong><p>У каждого района свои сильные и слабые стороны.</p></div></div><div class="step"><span class="step-num">02</span><div><strong>Выберите пять инициатив</strong><p>100 единиц бюджета. Каждое решение имеет цену.</p></div></div><div class="step"><span class="step-num">03</span><div><strong>Посмотрите, что изменилось</strong><p>Оценка города и AI-разбор ваших решений.</p></div></div></div><div class="row between" style="margin-top:22px"><span class="muted small">' + (state.plan.length ? "В вашем плане: " + state.plan.length + " из 5 решений" : "Начните с самого уязвимого района — Нуры.") + '</span>' + button((state.plan.length === 5 ? "Посмотреть результат" : "Выбрать инициативы") + icon("arrow"),state.plan.length === 5 ? "calculate" : "initiatives","primary") + '</div>';
}
function indicatorTable(d) {
  return '<div class="table-wrap"><table><thead><tr><th>Показатель</th><th>Сейчас</th><th>С планом</th></tr></thead><tbody>' + Object.keys(state.city.indicators).map(k => '<tr><td>' + escape(state.city.indicators[k]) + '</td><td>' + number(d.before[k],1) + '</td><td class="' + (d.after[k] < 40 ? 'negative' : d.delta[k] > 0 ? 'positive' : '') + '">' + number(d.after[k],1) + '</td></tr>').join("") + '</tbody></table></div>';
}
function planPanel() {
  const limit = state.city.ruleset === "dataset-v1" ? "Не более двух мер из одного направления." : "По одной мере из каждого направления.";
  return '<aside class="panel plan-panel"><div class="panel-body"><div class="plan-head"><h2>Ваш план</h2><span class="pill neutral">' + state.plan.length + ' / 5</span></div>' +
    (!state.plan.length ? '<div class="empty-plan">' + icon("folder") + '<h3>Здесь появятся ваши решения</h3><p>Откройте инициативу, выберите район и добавьте её в план.</p></div>' : '') +
    state.plan.map((d,i) => '<div class="plan-item">' + categoryIcon(measure(d.measure_id).direction) + '<div class="grow"><h3>' + escape(measure(d.measure_id).title) + '</h3><p>' + escape(targetName(d)) + ' · ' + measure(d.measure_id).cost + ' ед.</p><div class="plan-item-actions">' + button(icon("edit") + "Заменить","edit","ghost small",'data-index="' + i + '"') + '<button class="icon-button" data-action="remove" data-index="' + i + '" aria-label="Убрать ' + escape(measure(d.measure_id).title) + '">' + icon("close") + '</button></div></div></div>').join("") +
    Array.from({length:5-state.plan.length},(_,i) => '<div class="empty-slot"><span>0' + (state.plan.length+i+1) + '</span>Место для инициативы</div>').join("") +
    '<div class="row between plan-total"><span class="muted">Стоимость плана</span><strong>' + state.projection.spent + ' <span class="muted small">/ 100</span></strong></div>' +
    button("Оценить мой план " + icon("arrow"),"calculate","primary full",state.plan.length !== 5 ? 'disabled' : '') +
    '<p class="subtle-note">Нужно ровно 5 разных инициатив. ' + limit + '</p>' +
    (state.plan.length ? '<div class="row between">' + button("Очистить","clear","ghost small") + button(icon("download") + "JSON","export","ghost small") + '</div>' : '') + '</div></aside>';
}
function catalogView() {
  const filtered = state.city.measures.filter(m => state.filter === "all" || m.direction === state.filter);
  return heading("ОТ ИДЕИ К ДЕЙСТВИЮ","Во что инвестируем?","Выбирайте инициативы. Их эффект и ограничения видны до добавления.",
    button(icon("spark") + "Готовый пример","example")) + stats() +
    (state.edit !== null ? '<div class="edit-banner"><span>Заменяем: <strong>' + escape(decisionName(state.plan[state.edit])) + '</strong></span>' + button("Отмена","cancel-edit","ghost small") + '</div>' : '') +
    '<div class="catalog-tools" aria-label="Фильтры инициатив">' + [["all","Все инициативы"],...Object.entries(DIR)].map(([key,title]) => '<button class="filter ' + (state.filter === key ? 'active' : '') + '" data-filter="' + key + '" aria-pressed="' + (state.filter === key) + '">' + (key === "all" ? '' : icon(key)) + title + '</button>').join("") + '</div><div class="content-grid"><div class="catalog-grid">' +
    filtered.map(m => {
      const added = state.plan.some((d,i) => d.measure_id === m.id && i !== state.edit);
      return '<article class="initiative"><div class="row between">' + categoryIcon(m.direction) + '<span class="pill ' + (added ? 'green' : 'neutral') + '">' + (added ? "В плане" : m.scope === "city" ? "Весь город" : "Один район") + '</span></div><h3>' + escape(m.title) + '</h3><p>' + escape(DESCRIPTIONS[m.id]) + '</p><div class="initiative-meta"><span>' + icon("clock") + 'Эффект через ' + m.lag + ' кв.</span><span>' + icon("pin") + (m.scope === "city" ? "5 районов" : "Район на выбор") + '</span></div><div class="initiative-footer"><span class="price">' + m.cost + ' <small>ед.</small></span>' + button(added ? icon("check") + "Добавлено" : "Подробнее " + icon("arrow"),"measure",added ? "small" : "soft small",'data-measure="' + m.id + '" ' + (added ? 'disabled' : '')) + '</div></article>';
    }).join("") + '</div>' + planPanel() + '</div><div class="mobile-plan"><span>План: ' + state.plan.length + ' / 5 · ' + state.projection.spent + ' ед.</span>' + button(state.plan.length === 5 ? "Оценить план" : "Открыть мой план", state.plan.length === 5 ? "calculate" : "show-plan","primary small") + '</div>';
}

function resultsView() {
  let html = heading("КАЖДОЕ РЕШЕНИЕ ИМЕЕТ ЗНАЧЕНИЕ","Что изменит ваш план","Результаты расчёта, изменения районов и взгляд AI-советника.",
    button(icon("edit") + "Изменить план","initiatives")) + stats();
  if (!state.result) return html + '<div class="empty-state">' + icon("chart") + '<h2>' + (state.plan.length === 5 ? "Ваш план готов к оценке" : "Сначала соберём план города") + '</h2><p>' + (state.plan.length === 5 ? "Пять решений выбраны. Рассчитайте итог и получите объяснение результата." : "Выберите ровно пять инициатив в пределах бюджета. Прогноз уже отображается наверху.") + '</p>' + button(state.plan.length === 5 ? "Рассчитать результат" : "Перейти к инициативам",state.plan.length === 5 ? "calculate" : "initiatives","primary") + '</div>';
  const r = state.result;
  const gain = r.delta_score;
  return html + '<div class="content-grid"><div class="stack"><section class="score-hero"><div><span class="eyebrow">ASTANA QUALITY OF LIFE SCORE</span><h2>' + (gain > 0 ? "Город стал комфортнее" : gain < 0 ? "План требует пересмотра" : "Оценка города не изменилась") + '</h2><p>Бюджет — ' + r.spent + ' из 100. Критических значений: ' + r.result.critical_count + ' вместо ' + r.baseline.critical_count + '.</p></div><div><div class="score-big">' + number(r.result.score) + '</div><div class="score-delta">' + signed(gain) + ' к исходным ' + number(r.baseline.score) + '</div></div></section><div class="decomposition">' +
    [["average","Среднее по городу"],["weakest","Самый слабый район"],["critical","Снижение штрафа"]].map(([key,label]) => '<div class="decomp-item"><strong class="' + (r.decomposition[key] >= 0 ? "positive" : "negative") + '">' + signed(r.decomposition[key]) + '</strong><p>' + label + '</p></div>').join("") +
    '</div><section class="panel"><div class="panel-head"><div><h2>Перемены в каждом районе</h2><p>Районная оценка до и после ваших решений</p></div></div><div class="panel-body" style="padding-top:0">' +
    r.districts.map(d => '<div class="bar-row"><span class="district-name">' + escape(d.name) + '</span><div class="double-bar" role="img" aria-label="' + escape(d.name) + ': до ' + number(d.score_before) + ', после ' + number(d.score_after) + '"><div style="--size:' + d.score_before + '%"></div><div class="after" style="--size:' + d.score_after + '%"></div></div><strong>' + number(d.score_after,1) + '</strong></div>').join("") +
    '<div class="row muted small"><span class="legend-item"><i class="dot" style="background:#e4eaf3"></i>Сейчас</span><span class="legend-item"><i class="dot" style="background:#739aed"></i>С вашим планом</span></div><details class="disclosure"><summary>Подробные показатели и совместные эффекты</summary>' +
    r.districts.map(d => '<details class="disclosure"><summary>' + escape(d.name) + ' · ' + number(d.score_before) + ' → ' + number(d.score_after) + '</summary>' + indicatorTable(d) + '</details>').join("") +
    '<p class="subtle-note">' + (r.synergies.length ? "Совместные эффекты: " + r.synergies.map(s => escape(s.pair.join(" + ")) + ' · ' + escape(district(s.district_id).name) + ' · ' + Object.entries(s.effects).map(([k,v]) => escape(state.city.indicators[k]) + ' ' + signed(v)).join(", ")).join("; ") : "В этом плане нет дополнительных совместных эффектов.") + '</p></details></div></section>' +
    recommendationsView() + '</div><div class="stack"><section class="panel"><div class="panel-body"><div class="ai-header"><span class="ai-mark">' + icon("spark") + '</span><div><h2>Взгляд AI-советника</h2><p>Объясняет ваш результат</p></div></div>' + (state.report ? reportView() : '<p class="ai-copy">Что сработало? Чем пришлось пожертвовать? Советник разберёт ваш план на основе рассчитанных показателей.</p>') +
    button(state.aiBusy ? '<span class="spinner"></span> Анализируем решения…' : icon("spark") + (state.report ? "Обновить анализ" : "Получить AI-анализ"),"analyze","soft full",state.aiBusy ? "disabled" : "") +
    '<p class="subtle-note">Расчёт выполняет модель города. AI объясняет результат и может ошибаться в интерпретации.</p></div></section><section class="panel"><div class="panel-body"><h2 style="font-size:16px">Сохраните свой сценарий</h2><p class="ai-copy">Сравните с другим планом или возьмите результат на презентацию.</p><label class="small muted" for="scenario-name">Название сценария</label><input id="scenario-name" type="text" maxlength="60" placeholder="Например, «Забота о районах»" style="margin:9px 0 13px">' +
    button(icon("compare") + "Сохранить для сравнения","save","full") + '<div style="margin-top:9px">' + button(icon("download") + "Скачать сценарий","export","ghost full") + '</div><p class="subtle-note">До 4 сценариев хранятся в этом браузере. JSON позволяет перенести план на другое устройство.</p></div></section></div></div>';
}
function recommendationsView() {
  return '<section class="panel"><div class="panel-head"><div><h2>А можно ещё лучше?</h2><p>Проверим, что даст замена одного решения.</p></div></div><div class="panel-body" style="padding-top:0">' +
    (state.recs ? '<p class="subtle-note">Проверено допустимых вариантов: ' + state.recs.checked + '. Это поиск одной замены, а не глобального оптимума.</p>' +
      (state.recs.candidates.length ? state.recs.candidates.map((c,i) => '<article class="rec-card"><div class="row between"><span class="rec-gain">' + signed(c.gain) + ' к Score</span><span class="pill neutral">' + c.spent + ' / 100 ед.</span></div><p>Вместо <strong>' + escape(decisionName(c.removed)) + '</strong><br>выберите <strong>' + escape(decisionName(c.added)) + '</strong>.</p><div class="row between"><span class="small muted">Новый Score: ' + number(c.score) + '</span>' + button("Применить " + icon("arrow"),"apply-rec","soft small",'data-index="' + i + '"') + '</div></article>').join("") : '<div class="callout">Среди проверенных замен более выгодных не найдено. Попробуйте изменить несколько решений.</div>') :
      button(state.recBusy ? '<span class="spinner"></span> Сравниваем варианты…' : icon("spark") + "Найти улучшения","recommend","full",state.recBusy ? "disabled" : "")) + '</div></section>';
}
function reportView() {
  const report = state.report, audit = report.audit;
  const fallbackReasons = {fallback_no_key:"API-ключ не настроен.",fallback_no_model:"AI-модель не выбрана.",fallback_api_error:"AI-сервис недоступен или его ответ не прошёл проверку."};
  const claim = c => '<p>' + escape(c.text) + '</p><details><summary>На чём основан вывод</summary>' + c.evidence_ids.map(id => '<p>' + escape(report.facts[id]) + '</p>').join("") + '</details>';
  return '<div class="ai-source">' + (report.source === "openai" ? 'OpenAI · ' + escape(report.model) + (report.cached ? ' · сохранённый ответ' : '') :
    '<div class="callout warning"><strong>Резервный аналитический отчёт</strong>' + (fallbackReasons[report.source] || "AI сейчас недоступен.") + ' Показано локальное объяснение расчёта, не ответ AI.</div>') +
    '</div><div class="ai-report">' + claim(audit.summary) +
    [["strengths","Сильные стороны"],["tradeoffs","Компромиссы"],["remaining_problems","Что ещё требует внимания"]].map(([key,title]) => audit[key].length ? '<h3>' + title + '</h3>' + audit[key].map(claim).join("") : '').join("") +
    (audit.recommendations.length ? '<h3>Рекомендации</h3>' + audit.recommendations.map(r => '<p>' + escape(report.facts["candidate:" + r.candidate_id]) + '</p>').join("") : '') +
    '<details><summary>Ограничения анализа</summary>' + audit.limitations.map(t => '<p>' + escape(t) + '</p>').join("") + '</details></div>';
}
function compareView() {
  return heading("ИЩИТЕ ЛУЧШИЙ БАЛАНС","Несколько планов. Один город.","Сравните свои подходы на одинаковых исходных данных.",
    '<label class="btn file-label">' + icon("upload") + 'Загрузить JSON<input id="import-file" type="file" accept=".json,application/json" aria-label="Загрузить сценарий JSON"></label>') + stats() +
    (!state.saved.length ? '<div class="empty-state">' + icon("compare") + '<h2>Здесь встретятся ваши идеи</h2><p>Рассчитайте план и сохраните его на экране результата. Затем измените решения и сравните, какой сценарий лучше.</p>' + button("К моему плану","initiatives","primary") + '</div>' :
      '<div class="saved-cards">' + state.saved.map((s,i) => '<article class="saved-card"><div class="row between"><h3>' + escape(s.name) + '</h3><button class="icon-button" data-action="remove-saved" data-index="' + i + '" aria-label="Удалить сохранённый сценарий ' + escape(s.name) + '">' + icon("close") + '</button></div><div class="saved-score">' + number(s.result.result.score) + ' <span class="pill green">' + signed(s.result.delta_score) + '</span></div><div class="row wrap muted small"><span>Бюджет: ' + s.result.spent + ' / 100</span><span>Критических: ' + s.result.result.critical_count + '</span></div><ol>' + s.scenario.decisions.map(d => '<li>' + escape(decisionName(d)) + '</li>').join("") + '</ol>' + button(icon("undo") + "Открыть сценарий","restore","full",'data-index="' + i + '"') + '</article>').join("") + '</div>') +
    '<p class="subtle-note">Сохранения привязаны к этому браузеру. При очистке его данных они исчезнут; скачайте JSON для надёжного хранения.</p>';
}
function helpView() {
  return heading("ПОНЯТНЫЕ ПРАВИЛА","Как устроен симулятор","Одинаковый старт для всех. Прозрачные последствия каждого выбора.") +
    '<section class="panel help"><div class="panel-body"><h2 style="margin-top:0">Ваша задача</h2><p>Примите пять разных решений, чтобы улучшить жизнь города. У вас 100 условных единиц и пять направлений: транспорт, озеленение, социальная инфраструктура, безопасность и городские сервисы.</p><ul><li>' +
    (state.city.ruleset === "dataset-v1" ? 'В текущем режиме можно выбрать до двух мер из одного направления. Не обязательно выбирать все направления.' : 'В текущем режиме нужно выбрать по одной мере из каждого направления.') +
    '</li><li>Городские меры действуют на все районы, районные — на выбранный район.</li><li>Эффекты сравниваются через 2 года. Долгие проекты успевают реализовать меньшую часть эффекта.</li><li>Каждую меру можно выбрать один раз. Неизрасходованный бюджет сам по себе не повышает оценку.</li></ul><h2>Из чего складывается оценка</h2><div class="formula">Score = 70% × средняя оценка города<br>+ 30% × оценка самого слабого района<br>− число критических значений</div><p>Средняя оценка учитывает население районов. За каждый показатель ниже 40 баллов снимается один балл. Это позволяет учитывать не только общие улучшения, но и наиболее уязвимые районы.</p><details class="disclosure"><summary>Точная формула и веса показателей</summary><div class="formula">I′ = clip(I + Σ(эффект × (8 − лаг) / 8) + синергия, 0, 100)<br>D = Σ(вес × I′)</div><p>Лаг указан в кварталах. Эффекты суммируются до ограничения диапазоном 0–100. Значение ровно 40 не штрафуется. Расчёты идут без промежуточного округления.</p><div class="table-wrap"><table><thead><tr><th>Показатель</th><th>Вес</th></tr></thead><tbody>' +
    Object.entries(state.city.weights).map(([k,v]) => '<tr><td>' + escape(state.city.indicators[k]) + '</td><td>' + number(v,2) + '</td></tr>').join("") +
    '</tbody></table></div></details><h2>Некоторые решения несовместимы</h2><ul>' + state.city.conflicts.map(c => '<li>' + escape(c.reason) + '</li>').join("") +
    '</ul><h2>Что делает AI</h2><p>Советник получает рассчитанные показатели и проверенные альтернативы. Он объясняет сильные стороны и компромиссы, но не определяет цену, бюджет или итоговый Score. Если AI недоступен, приложение явно обозначает резервный локальный отчёт.</p><h2>Это учебная модель</h2><p>Районы, показатели и последствия заданы синтетическим датасетом. Схема районов условная и не повторяет реальные границы Астаны. Модель не прогнозирует реальную жизнь города, не учитывает эксплуатационные расходы и неопределённость эффектов.</p><div class="divider"></div>' +
    button("Попробовать на примере " + icon("arrow"),"example","primary") + '</div></section>';
}

function closeModal() {
  modalVersion++; modalCandidate = null; modalMeasure = null;
  $("#measure-dialog").close(); lastFocus?.focus();
}
function openMeasure(id) {
  const m = measure(id);
  if (!m) return;
  lastFocus = document.activeElement; modalMeasure = id; modalCandidate = null;
  const dialog = $("#measure-dialog");
  dialog.innerHTML = '<div class="dialog-top"><div><div class="row">' + categoryIcon(m.direction) + '<span class="eyebrow">' + DIR[m.direction] + '</span></div><h2 id="dialog-title">' + escape(m.title) + '</h2></div><button class="icon-button" data-action="close-modal" aria-label="Закрыть">' + icon("close") + '</button></div><div class="dialog-body"><p>Стоимость: <strong>' + m.cost + ' ед.</strong> · Начало эффекта через ' + m.lag + ' кв.</p>' +
    (m.scope === "district" ? '<label for="district-select">Где реализуем инициативу?</label><select id="district-select" class="select">' + state.city.districts.map(d => '<option value="' + d.id + '" ' + (d.id === state.district ? 'selected' : '') + '>' + escape(d.name) + '</option>').join("") + '</select>' : '<div class="callout" style="margin-top:18px">Инициатива затрагивает все пять районов города.</div>') +
    '<div class="effect-list">' + Object.entries(m.effects).map(([k,v]) => '<div class="effect-row"><span>' + escape(state.city.indicators[k]) + '</span><strong class="' + (v >= 0 ? 'positive' : 'negative') + '">' + signed(v*(state.city.horizon-m.lag)/state.city.horizon) + '</strong></div>').join("") + '</div><p class="subtle-note">Изменение показателей за 2 года. Итог также учитывает совместные эффекты и предел 100 баллов.</p><div id="candidate-preview" aria-live="polite"></div><div class="dialog-actions">' +
    button("Отмена","close-modal") + button(state.edit === null ? "Добавить в план" : "Применить замену","add","primary",'id="add-decision" disabled') + '</div></div>';
  dialog.showModal(); previewMeasure();
}
async function previewMeasure() {
  const version = ++modalVersion, revision = state.revision;
  const m = measure(modalMeasure), target = m.scope === "district" ? $("#district-select").value : null;
  const candidate = state.plan.map(d => ({...d}));
  const decision = {measure_id:m.id, district_id:target};
  if (state.edit === null) candidate.push(decision); else candidate[state.edit] = decision;
  $("#add-decision").disabled = true; modalCandidate = null;
  $("#candidate-preview").innerHTML = '<div class="preview-box"><span class="spinner"></span>Проверяем бюджет и влияние на город…</div>';
  try {
    if (candidate.length > 5) throw new Error("Пять решений уже выбраны. Сначала нажмите «Заменить» или уберите одну инициативу из плана.");
    const checked = await api("preview",scenario(candidate));
    if (version !== modalVersion || revision !== state.revision || !$("#measure-dialog").open) return;
    modalCandidate = candidate;
    const diff = checked.projection.result.score - state.projection.result.score;
    $("#candidate-preview").innerHTML = '<div class="preview-box"><div>Оценка города после ' + (state.edit === null ? 'добавления' : 'замены') + '<br><strong>' + number(checked.projection.result.score) + '</strong> <span class="' + (diff >= 0 ? "positive" : "negative") + '">' + signed(diff) + '</span></div><div>Останется в бюджете<br><strong>' + checked.projection.remaining + ' <small>ед.</small></strong></div></div>';
    $("#add-decision").disabled = false;
  } catch (e) {
    if (version === modalVersion && $("#measure-dialog").open) $("#candidate-preview").innerHTML = '<div class="error" role="alert">' + escape(e.message) + '</div>';
  }
}
function confirmAction(title, text, action, label="Продолжить") {
  const dialog = $("#confirm-dialog");
  dialog.innerHTML = '<div class="dialog-top"><h2 id="confirm-title">' + escape(title) + '</h2></div><div class="dialog-body"><p>' + escape(text) + '</p><div class="dialog-actions">' + button("Отмена","close-confirm") + button(label,action,"primary") + '</div></div>';
  dialog.showModal();
}
async function calculate() {
  const result = await api("simulate",scenario());
  state.result = result; navigate("results");
}
function exportPlan() {
  const link = document.createElement("a");
  link.href = "/download/scenario?" + new URLSearchParams({payload:JSON.stringify(scenario())});
  link.download = "astana-scenario.json";
  document.body.append(link); link.click(); link.remove();
  toast("Сценарий подготовлен для скачивания. Импорт доступен в разделе «Сравнение».");
}
async function analysis() {
  if (state.aiBusy || !state.result) return;
  state.aiBusy = true; const revision = state.revision; render();
  try {
    const report = await api("analyze",scenario());
    if (revision === state.revision) { state.report = report; toast("Разбор вашего сценария готов."); }
  } catch (e) { if (revision === state.revision) toast(e.message); }
  finally { if (revision === state.revision) { state.aiBusy = false; render(); } }
}
async function findRecommendations() {
  if (state.recBusy || !state.result) return;
  state.recBusy = true; const revision = state.revision; render();
  try { const value = await api("recommend",scenario()); if (revision === state.revision) state.recs = value; }
  catch (e) { if (revision === state.revision) toast(e.message); }
  finally { if (revision === state.revision) { state.recBusy = false; render(); } }
}

async function action(name, el) {
  if (name === "show-plan") return $(".plan-panel").scrollIntoView({behavior:"smooth",block:"start"});
  if (name === "help") return navigate("help");
  if (name === "initiatives") return navigate("initiatives");
  if (name === "close-modal") return closeModal();
  if (name === "close-confirm") return $("#confirm-dialog").close();
  if (name === "export") return exportPlan();
  if (name === "measure") return openMeasure(el.dataset.measure);
  if (name === "district-initiatives") { state.filter = "all"; navigate("initiatives"); return; }
  if (name === "edit") { state.edit = Number(el.dataset.index); state.filter = measure(state.plan[state.edit].measure_id).direction; state.district = state.plan[state.edit].district_id || state.district; render(); return; }
  if (name === "cancel-edit") { state.edit = null; render(); return; }
  if (name === "clear") return confirmAction("Начать новый план?","Текущие решения будут убраны. Сохранённые сценарии останутся в разделе сравнения.","clear-confirmed","Очистить план");
  if (name === "example" && state.plan.length) return confirmAction("Открыть готовый пример?","Он заменит текущий план. Сохранённые сценарии останутся доступны.","example-confirmed","Открыть пример");
  if (name === "analyze") return analysis();
  if (name === "recommend") return findRecommendations();
  if (state.busy) return;
  state.busy = true; if (el) {el.disabled = true; el.setAttribute("aria-busy","true");}
  try {
    if (name === "example" || name === "example-confirmed") {
      $("#confirm-dialog").close(); await changePlan(state.city.example.decisions.map(d => ({...d}))); navigate("initiatives"); toast("Пример загружен. Можно заменить любое решение.");
    } else if (name === "clear-confirmed") {
      $("#confirm-dialog").close(); await changePlan([]); render(); toast("План очищен.");
    } else if (name === "add") {
      if (!modalCandidate) return;
      const candidate = modalCandidate; await changePlan(candidate); closeModal(); render(); toast("Решение добавлено. Прогноз города обновлён.");
    } else if (name === "remove") {
      await changePlan(state.plan.filter((_,i) => i !== Number(el.dataset.index))); render(); toast("Инициатива убрана из плана.");
    } else if (name === "calculate") { await calculate(); }
    else if (name === "apply-rec") {
      const candidate = state.recs.candidates[Number(el.dataset.index)];
      await changePlan(candidate.scenario.decisions); await calculate(); toast("Альтернатива применена. Результат пересчитан.");
    } else if (name === "save") {
      if (state.saved.length >= 4) throw new Error("Уже сохранено 4 сценария. Удалите ненужный в разделе «Сравнение».");
      const name = $("#scenario-name").value.trim() || "Сценарий " + (state.saved.length + 1);
      const result = await api("simulate",scenario());
      state.saved.push({name,scenario:result.scenario,result}); persist(); toast("Сценарий «" + name + "» сохранён для сравнения.");
    } else if (name === "restore") {
      const saved = state.saved[Number(el.dataset.index)];
      await changePlan(saved.scenario.decisions); await calculate(); toast("Сценарий открыт и пересчитан.");
    } else if (name === "remove-saved") {
      const removed = state.saved.splice(Number(el.dataset.index),1)[0]; persist(); render(); toast("Убрано из сравнения: " + removed.name);
    }
  } catch (e) { toast(e.message); }
  finally { state.busy = false; if (el?.isConnected) { el.disabled = false; el.removeAttribute("aria-busy"); } }
}

document.addEventListener("click", e => {
  const el = e.target.closest("[data-action],[data-view],[data-district],[data-filter],[data-map]");
  if (!el || el.disabled || state.busy) return;
  e.preventDefault();
  if (el.dataset.view) return navigate(el.dataset.view);
  if (el.dataset.district) { state.district = el.dataset.district; render(); return; }
  if (el.dataset.filter) { state.filter = el.dataset.filter; render(); return; }
  if (el.dataset.map) { state.mapMode = el.dataset.map; render(); return; }
  action(el.dataset.action,el);
});
document.addEventListener("keydown", e => {
  if (e.target.matches("[data-district]") && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); e.target.dispatchEvent(new MouseEvent("click",{bubbles:true})); }
});
$("#measure-dialog").addEventListener("cancel", () => { modalVersion++; modalCandidate = null; });
document.addEventListener("change", async e => {
  if (e.target.id === "district-select") return previewMeasure();
  if (e.target.id !== "import-file" || !e.target.files[0] || state.busy) return;
  const file = e.target.files[0]; state.busy = true;
  try {
    if (file.size > 16384) throw new Error("Сценарий не должен превышать 16 КБ.");
    let data;
    try { data = JSON.parse((await file.text()).replace(/^\uFEFF/,"")); } catch { throw new Error("Не удалось прочитать JSON. Выберите файл экспортированного сценария."); }
    const checked = await api("preview",data);
    // Validate the original object (including version/ruleset) before using its plan.
    await changePlan(data.decisions);
    state.projection = checked.projection; navigate("initiatives"); toast("Сценарий проверен и загружен.");
  } catch (e) { toast(e.message); }
  finally { state.busy = false; }
});
document.addEventListener("input", e => {
  if (e.target.id === "scenario-name") state.scenarioName = e.target.value.slice(0,60);
});

async function init() {
  try {
    state.city = await api("data"); state.projection = state.city.baseline;
    await restoreStorage(); render();
  } catch (e) {
    $("#app").innerHTML = '<div class="boot"><div class="boot-mark">А</div><h1>Город пока недоступен</h1><p>' + escape(e.message) + '</p><button class="btn primary" id="retry">Попробовать снова</button></div>';
    $("#retry").addEventListener("click",init);
  }
}
init();
