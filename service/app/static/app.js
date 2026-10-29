/* АТИМ Управление — центральная страница. Без сборки и внешних библиотек, как СЭД и CRM. */
"use strict";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const initials = s => String(s || "").split(/[\s.]+/).filter(Boolean).slice(0, 2).map(x => x[0]).join("").toUpperCase();
function toast(t, ms = 3500) { const el = $("#toast"); el.textContent = t; el.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(() => el.hidden = true, ms); }

class ApiError extends Error {}
async function api(path, {method = "GET", body} = {}) {
  const opt = {method, headers: {}, credentials: "same-origin"};
  if (body !== undefined) { opt.body = JSON.stringify(body); opt.headers["Content-Type"] = "application/json"; }
  const r = await fetch(path, opt);
  const data = r.headers.get("content-type")?.includes("json") ? await r.json() : null;
  if (r.status === 401) throw new ApiError("401");
  if (!r.ok) throw new ApiError(data?.detail || `Ошибка ${r.status}`);
  return data;
}

const sv = p => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${p}</svg>`;
const ICON = {
  home: sv('<path d="M3 11 12 4l9 7"/><path d="M5 10v10h14V10"/>'),
  doc: sv('<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>'),
  map: sv('<circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M8.5 12h3c2 0 2-6 4-6M11.5 12c2 0 2 6 4 6"/>'),
  cal: sv('<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>'),
  task: sv('<rect x="4" y="4" width="16" height="16" rx="4"/><path d="m8.5 12 2.5 2.5 4.5-5"/>'),
  mega: sv('<path d="M3 11v2a1 1 0 0 0 1 1h2l5 4V6L6 10H4a1 1 0 0 0-1 1z"/><path d="M15 9a4 4 0 0 1 0 6M18 6a8 8 0 0 1 0 12"/>'),
  coin: sv('<ellipse cx="12" cy="7" rx="7" ry="3"/><path d="M5 7v5c0 1.7 3.1 3 7 3s7-1.3 7-3V7M5 12v5c0 1.7 3.1 3 7 3s7-1.3 7-3v-5"/>'),
  tender: sv('<path d="M4 20h16M6 20V9l6-5 6 5v11"/><path d="M10 20v-5h4v5"/>'),
  arrow: sv('<path d="M7 17 17 7M9 7h8v8"/>'),
  grip: sv('<circle cx="9" cy="6" r="1"/><circle cx="15" cy="6" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="9" cy="18" r="1"/><circle cx="15" cy="18" r="1"/>'),
  eye: sv('<path d="M3 3l18 18M10.6 6.1A9.6 9.6 0 0 1 12 6c5 0 9 6 9 6a17 17 0 0 1-3 3.6M6.6 7.6C4.4 9.2 3 12 3 12s4 6 9 6c1.4 0 2.7-.4 3.9-1"/>'),
  ok: sv('<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>'),
  refresh: sv('<path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/>'),
};
const MONTHS = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];
const WEEKDAYS = ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"];
const todayISO = () => { const d = new Date(); return new Date(d - d.getTimezoneOffset() * 6e4).toISOString().slice(0, 10); };
function fmtTime(v) {
  if (!v) return "";
  const [d, t] = String(v).split("T"), diff = Math.round((new Date(d) - new Date(todayISO())) / 864e5);
  const hm = t && !/^00:00/.test(t) ? t.slice(0, 5) : "";
  if (diff === 0) return hm || "сегодня";
  const [, m, dd] = d.split("-").map(Number);
  const day = diff === 1 ? "завтра" : diff === -1 ? "вчера" : `${dd} ${MONTHS[m - 1]}`;
  return hm ? `${day}, ${hm}` : day;
}
const toneOf = v => !v ? "" : String(v).slice(0, 10) < todayISO() ? "danger" : String(v).slice(0, 10) === todayISO() ? "warn" : "";

const S = {me: null, widgets: [], layout: {order: [], hidden: []}, loadedAt: null};

async function boot() {
  try { S.me = await api("/api/me"); } catch { return login(); }
  shell();
  S.layout = await api("/api/layout").catch(() => S.layout);
  renderSkeleton();
  await refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, 60000);
}

async function login() {
  const auth = await api("/api/auth").catch(() => ({mode: "dev"}));
  if (auth.mode === "sed" && !login.out) { location.href = auth.login_url; return; }
  $("#root").innerHTML = `<div class="login"><form onsubmit="return false"><img src="/static/logo-atim.png" alt="АТИМ" style="filter:none"><h1>АТИМ Управление</h1>
    ${auth.mode === "sed" ? `<a class="btn pri" style="justify-content:center" href="${esc(auth.login_url)}">Войти</a>` : `<p style="margin:0;text-align:center;color:var(--muted);font-size:13px">Режим разработки</p><a class="btn pri" style="justify-content:center" href="/api/dev/login/1">Войти как демо-сотрудник</a>`}
  </form></div>`;
}

function shell() {
  const u = S.me.user, L = S.me.links;
  $("#root").innerHTML = `<div class="app">
    <aside class="side">
      <div class="logo"><img src="/static/logo-atim.png" alt="АТИМ"><small aria-label="Управление">${[..."УПРАВЛЕНИЕ"].map(c => `<span>${c}</span>`).join("")}</small></div>
      <nav class="nav">
        <h4>Модули</h4>
        <button aria-current="page">${ICON.home}Главная</button>
        <button data-href="${esc(L.sed)}">${ICON.doc}Документооборот</button>
        <button data-href="${esc(L.crm)}">${ICON.map}Продажи</button>
        <button data-href="${esc(L.tender)}">${ICON.tender}Тендеры</button>
        <button disabled>${ICON.mega}Маркетинг<span class="soon">скоро</span></button>
        <button disabled>${ICON.coin}Финансы<span class="soon">скоро</span></button>
      </nav>
      <div class="foot"><span>Сотрудник</span>${esc(u.full_name)}<span style="margin-top:6px">Должность</span>${esc(u.position || "—")}</div>
    </aside>
    <div class="main">
      <header class="top"><div class="url"><i></i>${esc(location.host)}</div><span style="flex:1"></span>
        <div class="who"><div><b>${esc(u.short_name)}</b><br><span>${esc(u.position || "")}</span> · <button data-act="logout">выйти</button></div><div class="ava">${esc(initials(u.short_name))}</div></div></header>
      <main class="home">
        <div class="hello"><div><h1>${greeting()}, ${esc(firstName(u))}</h1><p>${esc(todayLine())}</p></div><span class="sp"></span>
          <div class="upd"><span id="upd"></span><button class="btn sm" data-act="refresh">${ICON.refresh.replace("<svg", '<svg style="width:14px;height:14px"')}Обновить</button></div></div>
        <div class="pulse" id="pulse"></div>
        <div class="grid" id="grid"></div>
        <div class="hiddenbar" id="hiddenbar"></div>
      </main>
    </div></div>`;
}
const firstName = u => (u.full_name || "").split(/\s+/)[1] || u.short_name || "";
function greeting() { const h = new Date().getHours(); return h < 5 ? "Доброй ночи" : h < 12 ? "Доброе утро" : h < 18 ? "Добрый день" : "Добрый вечер"; }
function todayLine() { const d = new Date(); return `Сегодня ${WEEKDAYS[d.getDay()]}, ${d.getDate()} ${MONTHS[d.getMonth()].replace("мая", "мая")} — что требует внимания в модулях`; }

function renderSkeleton() {
  $("#grid").innerHTML = Array.from({length: 6}, () => `<div class="w"><div class="wh"><div class="ic"></div><div class="skel" style="flex:1"></div></div><div class="skel" style="height:40px;width:40%"></div><div class="skel"></div><div class="skel" style="width:70%"></div></div>`).join("");
}

async function refresh() {
  try { S.widgets = await api("/api/widgets"); }
  catch (e) { if (e.message === "401") return login(); toast(e.message); return; }
  S.loadedAt = new Date();
  $("#upd").textContent = `Обновлено в ${String(S.loadedAt.getHours()).padStart(2, "0")}:${String(S.loadedAt.getMinutes()).padStart(2, "0")}`;
  render();
}

function ordered() {
  const byId = Object.fromEntries(S.widgets.map(w => [w.id, w]));
  const ids = [...S.layout.order.filter(id => byId[id]), ...S.widgets.map(w => w.id).filter(id => !S.layout.order.includes(id))];
  return ids.map(id => byId[id]);
}

function render() {
  const list = ordered(), hidden = new Set(S.layout.hidden);
  $("#grid").innerHTML = list.filter(w => !hidden.has(w.id)).map(card).join("");
  $("#pulse").innerHTML = list.filter(w => !hidden.has(w.id) && w.metric && ["ok", "empty"].includes(w.status)).map(w =>
    `<a href="${esc(w.url || "#")}" class="${esc(w.metric.tone || "")}"><b>${esc(w.metric.value)}</b><span>${esc(w.title)} · ${esc(w.metric.label)}</span></a>`).join("");
  const hid = list.filter(w => hidden.has(w.id));
  $("#hiddenbar").innerHTML = hid.length ? `Скрыто: ${hid.map(w => `<button class="chip" data-show="${w.id}">${esc(w.title)} — показать</button>`).join("")}` : "";
  bindDrag();
}

function card(w) {
  const st = w.status, wide = w.wide ? " wide" : "";
  const head = `<div class="wh"><div class="ic">${ICON[w.icon] || ICON.doc}</div><h3>${esc(w.title)}</h3>
    <button class="grip" draggable="true" title="Перетащите, чтобы поменять порядок">${ICON.grip}</button>
    <button class="grip" data-hide="${w.id}" title="Скрыть виджет">${ICON.eye}</button>
    ${w.url ? `<a class="go" href="${esc(w.url)}" title="Открыть модуль">${ICON.arrow}</a>` : ""}</div>`;
  if (st === "stub") return `<section class="w stub${wide}" data-id="${w.id}">${head}<div class="stubbox"><div class="bars">${[38, 62, 45, 80, 55, 70].map(h => `<span style="height:${h}%"></span>`).join("")}</div>
    <div><b style="color:var(--fg)">Модуль в разработке</b><br>Здесь появятся ключевые показатели, когда модуль подключится к платформе.</div></div></section>`;
  if (st === "pending") return `<section class="w pending${wide}" data-id="${w.id}">${head}<div class="stubbox"><div><b style="color:var(--fg)">Подключается</b><br>${esc(pendingText(w.id))}</div></div></section>`;
  const data = st === "offline" ? w.stale : w;
  const off = st === "offline" ? `<div class="offline">⚠ ${esc(w.message)}${w.stale_at ? ` — показаны данные на ${esc(w.stale_at)}` : ""}</div>` : "";
  if (!data) return `<section class="w${wide}" data-id="${w.id}">${head}${off}</section>`;
  const m = data.metric || {};
  const chips = [...(data.badges || []).filter(b => b.value).map(b => `<span class="c ${b.label === "просрочено" && b.value ? "danger" : b.label === "сегодня" && b.value ? "warn" : ""}">${esc(b.label)}<b>${esc(b.value)}</b></span>`),
    ...(data.secondary || []).filter(b => b.value).map(b => `<a class="c ${esc(b.tone || "")}" href="${esc(b.url || "#")}">${esc(b.label)}<b>${esc(typeof b.value === "number" && b.value > 9999 ? b.value.toLocaleString("ru-RU") : b.value)}</b></a>`)];
  const items = data.items || [];
  const rows = items.length ? `<div class="rows">${items.slice(0, w.wide ? 8 : 5).map(it => {
    const tone = it.tone || toneOf(it.time) || "normal";  // модуль сам знает, что срочно; иначе — по сроку
    return `<a href="${esc(it.url || data.url || "#")}"><i class="${tone}"></i><div class="t"><div>${it.source ? `<span class="src">${esc(it.source)}</span>` : ""}${esc(it.title)}</div>${it.subtitle ? `<small>${esc(it.subtitle)}</small>` : ""}</div><time class="${tone === "normal" ? "" : tone}">${esc(fmtTime(it.time))}</time></a>`;
  }).join("")}</div>` : (data.status === "empty" ? `<div class="calm">${ICON.ok}${esc(emptyText(w.id))}</div>` : "");
  return `<section class="w${wide}" data-id="${w.id}">${head}${off}
    <div class="big"><b class="${esc(m.tone || "")}">${esc(m.value ?? "—")}</b><span>${esc(m.label || "")}</span></div>
    ${chips.length ? `<div class="chips">${chips.join("")}</div>` : ""}${rows}
    <div class="wf">${(data.actions || []).map(a => `<a class="btn sm" href="${esc(a.url)}">${esc(a.label)}</a>`).join("")}${data.message ? `<span class="note">${esc(data.message)}</span>` : ""}</div></section>`;
}
const emptyText = id => ({"docs.mail": "Новых писем нет — очередь разобрана", "crm.tasks": "Открытых задач в CRM нет", "bot.today": "Сегодня встреч нет", tasks: "Все задачи выполнены"})[id] || "Всё спокойно";
const pendingText = id => ({"bot.today": "Встречи на сегодня из календаря команды появятся, когда у группового бота заработает API виджетов."})[id] || "Источник данных ещё не подключён к платформе.";

// ---------- порядок и скрытие ----------
const saveLayout = () => api("/api/layout", {method: "PUT", body: S.layout}).catch(() => {});
function bindDrag() {
  let dragId = null;
  $$(".w").forEach(el => {
    const grip = $(".grip[draggable]", el);
    if (!grip) return;
    grip.ondragstart = e => { dragId = el.dataset.id; el.classList.add("dragging"); e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setDragImage(el, 20, 20); };
    grip.ondragend = () => { el.classList.remove("dragging"); $$(".w.over").forEach(x => x.classList.remove("over")); };
    el.ondragover = e => { if (dragId && dragId !== el.dataset.id) { e.preventDefault(); el.classList.add("over"); } };
    el.ondragleave = () => el.classList.remove("over");
    el.ondrop = e => {
      e.preventDefault(); el.classList.remove("over");
      const ids = ordered().map(w => w.id), from = ids.indexOf(dragId), to = ids.indexOf(el.dataset.id);
      ids.splice(to, 0, ids.splice(from, 1)[0]);
      S.layout.order = ids; render(); saveLayout();
    };
  });
}

document.addEventListener("click", async e => {
  const h = e.target.closest("[data-href]"); if (h) { location.href = h.dataset.href; return; }
  const hide = e.target.closest("[data-hide]");
  if (hide) { S.layout.hidden = [...new Set([...S.layout.hidden, hide.dataset.hide])]; render(); saveLayout(); toast("Виджет скрыт — вернуть можно внизу страницы"); return; }
  const show = e.target.closest("[data-show]");
  if (show) { S.layout.hidden = S.layout.hidden.filter(x => x !== show.dataset.show); render(); saveLayout(); return; }
  const a = e.target.closest("[data-act]")?.dataset.act;
  if (a === "refresh") return refresh();
  if (a === "logout") { await api("/api/logout", {method: "POST"}); login.out = true; return login(); }
});

boot();
