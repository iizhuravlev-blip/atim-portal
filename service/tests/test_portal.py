import os

os.environ.update(DB_PATH=":memory:", AUTH_MODE="dev", SED_TOKEN="", CRM_TOKEN="", BOT_API_URL="")

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from itsdangerous import URLSafeTimedSerializer  # noqa: E402

from app import config, main  # noqa: E402


@pytest.fixture()
def c(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "p.db")
    with TestClient(main.app) as client:
        yield client


def test_login_required_and_dev_login(c):
    assert c.get("/api/widgets").status_code == 401
    c.get("/api/dev/login/1")
    assert c.get("/api/me").json()["user"]["id"] == 1


def test_widgets_stubs_and_pending(c):
    c.get("/api/dev/login/1")
    ws = {w["id"]: w for w in c.get("/api/widgets").json()}
    assert list(ws) == ["docs.mail", "crm.tasks", "tasks", "bot.today", "marketing", "finance"]
    assert ws["marketing"]["status"] == "stub" and ws["docs.mail"]["status"] == "pending"
    assert ws["tasks"]["wide"] is True


def test_widgets_from_modules_and_combined_tasks(c, monkeypatch):
    monkeypatch.setattr(config, "SED_TOKEN", "s"), monkeypatch.setattr(config, "CRM_TOKEN", "c")
    monkeypatch.setattr(main, "sed_user", lambda uid: {"id": uid, "short_name": "Т.", "full_name": "Тест Тест", "active": True})
    payload = {
        "docs.mail": {"id": "docs.mail", "status": "ok", "metric": {"value": 3, "label": "новых писем"}},
        "docs.tasks": {"id": "docs.tasks", "status": "ok", "items": [{"title": "Поручение", "time": "2020-01-01"}]},
        "crm.tasks": {"id": "crm.tasks", "status": "ok", "metric": {"value": 1}, "items": [{"title": "КП", "time": "2099-01-01"}]},
    }

    async def fake_get(self, url, params=None, **kw):
        if "crm" in url and params["id"] == "crm.tasks":
            return httpx.Response(200, json=payload["crm.tasks"])
        if params["id"] in payload:
            return httpx.Response(200, json=payload[params["id"]])
        return httpx.Response(500)
    monkeypatch.setattr(config, "CRM_API_URL", "http://crm"), monkeypatch.setattr(config, "SED_API_URL", "http://sed")
    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    c.get("/api/dev/login/1")
    ws = {w["id"]: w for w in c.get("/api/widgets").json()}
    assert ws["docs.mail"]["metric"]["value"] == 3
    t = ws["tasks"]
    assert [i["source"] for i in t["items"]] == ["СЭД", "CRM"] and t["metric"]["tone"] == "danger"

    async def down(self, url, params=None, **kw):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(httpx.AsyncClient, "get", down)
    ws = {w["id"]: w for w in c.get("/api/widgets").json()}
    assert ws["docs.mail"]["status"] == "offline" and ws["docs.mail"]["stale"]["metric"]["value"] == 3


def test_layout_saved(c):
    c.get("/api/dev/login/1")
    r = c.put("/api/layout", json={"order": ["tasks", "docs.mail", "evil"], "hidden": ["finance"]}).json()
    assert r == {"order": ["tasks", "docs.mail"], "hidden": ["finance"]}
    assert c.get("/api/layout").json() == r


def test_sso(c, monkeypatch):
    monkeypatch.setattr(config, "AUTH_MODE", "sed"), monkeypatch.setattr(config, "SSO_SECRET", "sec")
    assert c.get("/api/dev/login/1").status_code == 404
    tok = URLSafeTimedSerializer("sec", salt="atim-sso").dumps({"u": 1, "n": "x1"})
    assert c.get(f"/sso?token={tok}", follow_redirects=False).status_code == 303
    assert c.get("/api/me").json()["user"]["id"] == 1
    assert c.get(f"/sso?token={tok}", follow_redirects=False).status_code == 401
