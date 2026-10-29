"""АТИМ Управление — центральная страница (виджеты модулей). Контракт виджетов — docs/widgets.md."""
import asyncio
import json
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature, SignatureExpired, URLSafeSerializer, URLSafeTimedSerializer

from . import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("portal")
STATIC = Path(__file__).resolve().parent / "static"
COOKIE = "upr_session"
_signer = URLSafeSerializer(config.SECRET_KEY, salt="portal-session")

app = FastAPI(title="АТИМ Управление", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


# ---------- хранилище: только раскладки сотрудников ----------
def _db():
    if str(config.DB_PATH) != ":memory:":
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(config.DB_PATH)
    c.execute("CREATE TABLE IF NOT EXISTS layouts (user_id INTEGER PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL)")
    return c


# ---------- сотрудники из справочника СЭД ----------
_users: dict[int, tuple[float, dict | None]] = {}

DEMO_USERS = [{"id": 1, "full_name": "Журавлёв Илья", "short_name": "Журавлёв И.", "position": "Руководитель", "active": True}]


def sed_user(uid: int) -> dict | None:
    hit = _users.get(uid)
    if hit and time.time() - hit[0] < 30:
        return hit[1]
    if not config.SED_TOKEN:
        u = next((x for x in DEMO_USERS if x["id"] == uid), None)
    else:
        try:
            r = httpx.get(f"{config.SED_API_URL}/api/v1/directory/users/{uid}", timeout=5,
                          headers={"Authorization": f"Bearer {config.SED_TOKEN}"})
            u = r.json() if r.status_code == 200 else None
        except httpx.HTTPError:
            if hit:  # СЭД недоступен — не выкидываем вошедшего сотрудника
                return hit[1]
            raise HTTPException(503, "СЭД недоступен") from None
    _users[uid] = (time.time(), u)
    return u


def current_user(request: Request) -> dict:
    raw = request.cookies.get(COOKIE)
    try:
        uid = _signer.loads(raw) if raw else None
    except BadSignature:
        uid = None
    u = sed_user(uid) if uid else None
    if not u or not u.get("active", True):
        raise HTTPException(401, "Требуется вход")
    return u


def _login(uid: int, to: str = "/"):
    r = RedirectResponse(to, status_code=303)
    r.set_cookie(COOKIE, _signer.dumps(uid), httponly=True, samesite="lax", secure=config.COOKIE_SECURE, max_age=12 * 3600)
    return r


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def index():
    ver = str(int(max(p.stat().st_mtime for p in STATIC.glob("*.*"))))
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    html = html.replace('.css"', f'.css?v={ver}"').replace('.js"', f'.js?v={ver}"')
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})


@app.get("/api/auth")
def auth_info():
    return {"mode": config.AUTH_MODE, "login_url": f"{config.SED_URL}/sso?client=portal" if config.AUTH_MODE == "sed" else None}


_used: dict[str, float] = {}


@app.get("/sso")
def sso(token: str):
    if config.AUTH_MODE != "sed" or not config.SSO_SECRET:
        raise HTTPException(404)
    try:
        data = URLSafeTimedSerializer(config.SSO_SECRET, salt="atim-sso").loads(token, max_age=60)
    except (BadSignature, SignatureExpired):
        raise HTTPException(401, "Пропуск недействителен — войдите снова") from None
    now = time.time()
    for k, t in list(_used.items()):
        if now - t > 120:
            _used.pop(k, None)
    if data.get("n") in _used:
        raise HTTPException(401, "Пропуск уже использован")
    _used[data.get("n")] = now
    u = sed_user(int(data["u"]))
    if not u or not u.get("active", True):
        raise HTTPException(403, "Нет доступа")
    return _login(u["id"])


@app.get("/api/dev/login/{uid}")
def dev_login(uid: int):
    if config.AUTH_MODE != "dev":
        raise HTTPException(404)
    if not sed_user(uid):
        raise HTTPException(404, "Сотрудник не найден")
    return _login(uid)


@app.post("/api/logout")
def logout():
    r = JSONResponse({"ok": True})
    r.delete_cookie(COOKIE)
    return r


@app.get("/api/me")
def me(u=Depends(current_user)):
    return {"user": u, "auth_mode": config.AUTH_MODE,
            "links": {"sed": config.SED_URL, "crm": config.CRM_URL, "tender": config.TENDER_URL}}


# ---------- виджеты ----------
# Порядок по умолчанию. source: откуда брать; stub — модуль ещё в разработке.
CATALOG = [
    {"id": "docs.mail", "title": "Документооборот", "icon": "doc", "source": "sed"},
    {"id": "crm.tasks", "title": "Mind CRM", "icon": "map", "source": "crm"},
    {"id": "tasks", "title": "Задачи", "icon": "task", "source": "combined", "wide": True},
    {"id": "bot.today", "title": "Календарь", "icon": "cal", "source": "bot"},
    {"id": "marketing", "title": "Маркетинг", "icon": "mega", "source": "stub"},
    {"id": "finance", "title": "Финансы", "icon": "coin", "source": "stub"},
]
_cache: dict[tuple[str, int], tuple[float, dict]] = {}


def _source(src: str):
    return {"sed": (config.SED_API_URL, config.SED_TOKEN), "crm": (config.CRM_API_URL, config.CRM_TOKEN),
            "bot": (config.BOT_API_URL, config.BOT_TOKEN)}.get(src, ("", ""))


async def _fetch(client: httpx.AsyncClient, src: str, wid: str, uid: int) -> dict:
    url, token = _source(src)
    if not url or not token:
        return {"id": wid, "status": "pending", "message": "Источник ещё не подключён"}
    key = (wid, uid)
    try:
        r = await client.get(f"{url}/api/v1/widget", params={"id": wid}, timeout=config.TIMEOUT,
                             headers={"Authorization": f"Bearer {token}", "X-Atim-User": str(uid)})
        if r.status_code != 200:
            raise httpx.HTTPError(f"{r.status_code}")
        data = r.json()
        _cache[key] = (time.time(), data)
        return data
    except (httpx.HTTPError, ValueError) as e:
        log.warning("widget %s: %s", wid, e)
        old = _cache.get(key)
        return {"id": wid, "status": "offline", "message": "Нет связи с модулем",
                "stale": old[1] if old else None, "stale_at": datetime.fromtimestamp(old[0]).strftime("%H:%M") if old else None}


def _combine_tasks(parts: list[dict]) -> dict:
    """Все мои задачи: поручения СЭД и задачи CRM одним списком, просроченные сверху."""
    items, overdue, today_n, offline = [], 0, 0, []
    for p, label in parts:
        if p.get("status") == "pending":
            continue  # источник ещё не подключён — не ошибка
        if p.get("status") == "offline":
            offline.append(label)
            continue
        for it in p.get("items", []):
            items.append({**it, "source": it.get("source") or label})
    today = datetime.now().strftime("%Y-%m-%d")
    for it in items:
        d = (it.get("time") or "")[:10]
        if d and d < today:
            overdue += 1
        elif d == today:
            today_n += 1
    items.sort(key=lambda it: ((it.get("time") or "9999")[:10], it.get("title", "")))
    return {"id": "tasks", "title": "Задачи", "status": "ok" if items else "empty",
            "metric": {"value": len(items), "label": "задач и поручений", "tone": "danger" if overdue else "warn" if today_n else "normal"},
            "badges": [b for b in ({"label": "просрочено", "value": overdue} if overdue else None,
                                   {"label": "сегодня", "value": today_n} if today_n else None) if b],
            "items": items[:8], "message": ("Нет связи: " + ", ".join(offline)) if offline else "",
            "updated_at": datetime.now().replace(microsecond=0).isoformat() + "+03:00"}


@app.get("/api/widgets")
async def widgets(u=Depends(current_user)):
    uid = u["id"]
    async with httpx.AsyncClient() as client:
        jobs = {
            "docs.mail": _fetch(client, "sed", "docs.mail", uid),
            "crm.tasks": _fetch(client, "crm", "crm.tasks", uid),
            "bot.today": _fetch(client, "bot", "bot.today", uid),
            "docs.tasks": _fetch(client, "sed", "docs.tasks", uid),
            "crm.tasklist": _fetch(client, "crm", "crm.tasks", uid),
            "bot.tasks": _fetch(client, "bot", "bot.tasks", uid),
        }
        res = dict(zip(jobs, await asyncio.gather(*jobs.values())))
    out = []
    for w in CATALOG:
        if w["source"] == "stub":
            data = {"status": "stub", "message": "Модуль в разработке"}
        elif w["id"] == "tasks":
            data = _combine_tasks([(res["docs.tasks"], "СЭД"), (res["crm.tasklist"], "CRM"), (res["bot.tasks"], "Telegram")])
        else:
            data = res[w["id"]]
        out.append({**data, "id": w["id"], "title": w["title"], "icon": w["icon"], "wide": w.get("wide", False)})
    return out


@app.get("/api/layout")
def layout_get(u=Depends(current_user)):
    with _db() as c:
        row = c.execute("SELECT data FROM layouts WHERE user_id=?", (u["id"],)).fetchone()
    return json.loads(row[0]) if row else {"order": [w["id"] for w in CATALOG], "hidden": []}


@app.put("/api/layout")
def layout_put(data: dict = Body(...), u=Depends(current_user)):
    ids = {w["id"] for w in CATALOG}
    clean = {"order": [i for i in data.get("order", []) if i in ids], "hidden": [i for i in data.get("hidden", []) if i in ids]}
    with _db() as c:
        c.execute("INSERT OR REPLACE INTO layouts VALUES (?,?,?)", (u["id"], json.dumps(clean), datetime.now().isoformat()))
    return clean
