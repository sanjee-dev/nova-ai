import json
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from nova import web
from nova.config import Config


@pytest.fixture
def web_client(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "DATABASE_PATH", tmp_path / "chats.sqlite3")
    monkeypatch.setattr(web, "GOOGLE_CONFIGURED", False)
    monkeypatch.setattr(web, "ANONYMOUS_ACCESS", True)
    monkeypatch.setattr(web, "LOCAL_PREVIEW", True)
    web._initialize_database()
    with TestClient(web.app) as client:
        yield client


def test_preview_session_can_create_open_list_and_delete_chat(web_client):
    session = web_client.get("/api/session").json()
    assert session["local_preview"] is True
    assert session["public_access"] is True
    assert session["user"]["name"] == "Guest"

    created = web_client.post("/api/chats").json()
    assert created["title"] == "New chat"
    assert web_client.get("/api/chats").json()[0]["id"] == created["id"]
    assert web_client.get(f"/api/chats/{created['id']}").json()["messages"] == []
    assert web_client.delete(f"/api/chats/{created['id']}").json() == {"ok": True}
    assert web_client.get("/api/chats").json() == []


def test_chat_lookup_is_scoped_to_its_owner(web_client):
    created = web_client.post("/api/chats").json()
    with pytest.raises(HTTPException) as error:
        web._chat_row(created["id"], "another-user")
    assert error.value.status_code == 404


def test_chat_api_requires_google_sign_in_when_preview_is_disabled(web_client, monkeypatch):
    monkeypatch.setattr(web, "GOOGLE_CONFIGURED", True)
    assert web_client.get("/api/chats").status_code == 401


def test_guest_chats_are_separate_between_browser_sessions(web_client, tmp_path, monkeypatch):
    monkeypatch.setattr(web, "LOCAL_PREVIEW", False)
    with TestClient(web.app) as another_browser:
        first_session = web_client.get("/api/session").json()
        second_session = another_browser.get("/api/session").json()
        first_guest = first_session["user"]["id"]
        second_guest = second_session["user"]["id"]
        assert first_session["authenticated"] is False
        assert first_session["public_access"] is True
        assert first_guest != second_guest
        web_client.post("/api/chats")
        assert len(web_client.get("/api/chats").json()) == 1
        assert another_browser.get("/api/chats").json() == []


def test_default_database_path_uses_vercel_writable_tmp(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    assert web._default_database_path().as_posix() == "/tmp/nova-ai/chats.sqlite3"


def test_local_preview_is_disabled_by_default_on_vercel(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    assert web._default_local_preview() is False


def test_local_database_path_stays_in_user_home(monkeypatch):
    monkeypatch.delenv("VERCEL", raising=False)
    assert web._default_database_path() == web.Path.home() / ".nova-ai" / "chats.sqlite3"


def test_google_login_uses_callback_and_rejects_invalid_state(monkeypatch):
    monkeypatch.setattr(web, "GOOGLE_CONFIGURED", True)
    monkeypatch.setattr(web, "GOOGLE_CLIENT_ID", "test-client-id")
    with TestClient(web.app, follow_redirects=False) as client:
        response = client.get("/auth/google")
        query = parse_qs(urlparse(response.headers["location"]).query)
        assert query["client_id"] == ["test-client-id"]
        assert query["redirect_uri"] == [f"{web.BASE_URL}/auth/google/callback"]
        assert query["state"]
        callback = client.get("/auth/google/callback?code=fake&state=wrong")
        assert callback.headers["location"] == "/?signin=failed"


def test_streamed_reply_is_saved_and_chat_gets_a_title(web_client, monkeypatch):
    client = MagicMock()
    config = Config(api_key="test-key", model_name="test-model", max_history_messages=40)
    monkeypatch.setattr(web, "_get_client", lambda: (client, config))
    monkeypatch.setattr(web, "stream_chat", lambda *_args: iter(["A useful ", "answer."]))

    chat_id = web_client.post("/api/chats").json()["id"]
    response = web_client.post(
        f"/api/chats/{chat_id}/messages",
        json={"content": "  Help me plan  ", "model": "test-model"},
    )

    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert [event["type"] for event in events] == ["token", "token", "done"]
    saved_chat = web_client.get(f"/api/chats/{chat_id}").json()
    assert saved_chat["title"] == "Help me plan"
    assert saved_chat["messages"] == [
        {"role": "user", "content": "Help me plan"},
        {"role": "assistant", "content": "A useful answer."},
    ]