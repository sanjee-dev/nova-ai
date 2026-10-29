"""NOVA's local web dashboard, chat API, and optional Google sign-in."""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from groq import Groq

from nova.config import DEFAULT_MODEL, SYSTEM_PROMPT, Config, ConfigError, load_config
from nova.history import ChatHistory
from nova.llm import friendly_error_message, list_models, stream_chat

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = PROJECT_ROOT / "web"
load_dotenv(PROJECT_ROOT / ".env")

BASE_URL = os.getenv("NOVA_BASE_URL", "").rstrip("/")
if not BASE_URL and os.getenv("RENDER_EXTERNAL_HOSTNAME"):
    BASE_URL = f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}"
if not BASE_URL and os.getenv("VERCEL_URL"):
    BASE_URL = f"https://{os.environ['VERCEL_URL']}"
if not BASE_URL:
    BASE_URL = "http://127.0.0.1:8000"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_CONFIGURED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
def _default_local_preview() -> bool:
    return not os.getenv("VERCEL") and BASE_URL.startswith(("http://127.0.0.1", "http://localhost"))


LOCAL_PREVIEW = os.getenv("NOVA_LOCAL_PREVIEW", str(_default_local_preview()).lower()).lower() in {
    "1",
    "true",
    "yes",
}
SESSION_SECRET = os.getenv("NOVA_SESSION_SECRET") or secrets.token_urlsafe(48)
def _default_database_path() -> Path:
    if os.getenv("VERCEL"):
        return Path("/tmp/nova-ai/chats.sqlite3")
    return Path.home() / ".nova-ai" / "chats.sqlite3"


DATABASE_PATH = Path(os.getenv("NOVA_DB_PATH", str(_default_database_path()))).expanduser()


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _initialize_database() -> None:
    with _connect() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                messages TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS chats_user_updated ON chats(user_id, updated_at DESC)"
        )


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _user_for(request: Request) -> dict[str, str]:
    user = request.session.get("user")
    if user:
        return user
    if not GOOGLE_CONFIGURED and LOCAL_PREVIEW:
        return {"id": "local-preview", "name": "Local preview", "email": ""}
    raise HTTPException(status_code=401, detail="Please sign in with Google to continue.")


def _get_client() -> tuple[Groq, Config]:
    try:
        config = load_config()
    except ConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    client = getattr(app.state, "groq_client", None)
    if client is None:
        client = Groq(api_key=config.api_key)
        app.state.groq_client = client
    return client, config


def _chat_row(chat_id: str, user_id: str) -> sqlite3.Row:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Chat not found.")
    return row


def _serialize_chat(row: sqlite3.Row, include_messages: bool = False) -> dict[str, object]:
    result: dict[str, object] = {
        "id": row["id"],
        "title": row["title"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_messages:
        result["messages"] = json.loads(row["messages"])
    return result


_initialize_database()
app = FastAPI(title="NOVA AI", docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=BASE_URL.startswith("https://"),
    max_age=60 * 60 * 24 * 14,
)
app.mount("/assets", StaticFiles(directory=WEB_ROOT), name="assets")


class ChatInput(BaseModel):
    content: str = Field(min_length=1, max_length=12000)
    model: str | None = Field(default=None, max_length=150)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_ROOT / "index.html")


@app.get("/api/session")
def session_info(request: Request) -> dict[str, object]:
    user = request.session.get("user")
    return {
        "authenticated": bool(user),
        "auth_configured": GOOGLE_CONFIGURED,
        "local_preview": not GOOGLE_CONFIGURED and LOCAL_PREVIEW,
        "user": user or ({"name": "Local preview", "email": ""} if not GOOGLE_CONFIGURED and LOCAL_PREVIEW else None),
        "model": os.getenv("MODEL_NAME", DEFAULT_MODEL),
    }


@app.get("/auth/google")
def google_login(request: Request) -> RedirectResponse:
    if not GOOGLE_CONFIGURED:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured yet.")
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": f"{BASE_URL}/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")


@app.get("/auth/google/callback")
def google_callback(request: Request, code: str = "", state: str = "", error: str = "") -> RedirectResponse:
    expected_state = request.session.pop("oauth_state", None)
    if error or not code or not expected_state or not secrets.compare_digest(state, expected_state):
        return RedirectResponse("/?signin=failed", status_code=303)
    try:
        token_response = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": f"{BASE_URL}/auth/google/callback",
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        token_response.raise_for_status()
        access_token = token_response.json()["access_token"]
        profile_response = httpx.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        profile_response.raise_for_status()
        profile = profile_response.json()
        if not profile.get("sub") or not profile.get("email_verified"):
            return RedirectResponse("/?signin=unverified", status_code=303)
    except (httpx.HTTPError, KeyError, ValueError):
        return RedirectResponse("/?signin=failed", status_code=303)

    request.session.clear()
    request.session["user"] = {
        "id": str(profile["sub"]),
        "name": str(profile.get("name") or profile.get("email") or "NOVA user"),
        "email": str(profile.get("email", "")),
        "picture": str(profile.get("picture", "")),
    }
    return RedirectResponse("/", status_code=303)


@app.post("/auth/logout")
def logout(request: Request) -> dict[str, bool]:
    request.session.clear()
    return {"ok": True}


@app.get("/api/chats")
def get_chats(request: Request) -> list[dict[str, object]]:
    user = _user_for(request)
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM chats WHERE user_id = ? ORDER BY updated_at DESC", (user["id"],)
        ).fetchall()
    return [_serialize_chat(row) for row in rows]


@app.post("/api/chats")
def create_chat(request: Request) -> dict[str, object]:
    user = _user_for(request)
    chat_id = str(uuid4())
    now = _now()
    with _connect() as connection:
        connection.execute(
            "INSERT INTO chats(id, user_id, title, messages, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (chat_id, user["id"], "New chat", "[]", now, now),
        )
        row = connection.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
    return _serialize_chat(row)


@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: str, request: Request) -> dict[str, object]:
    user = _user_for(request)
    return _serialize_chat(_chat_row(chat_id, user["id"]), include_messages=True)


@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str, request: Request) -> dict[str, bool]:
    user = _user_for(request)
    with _connect() as connection:
        result = connection.execute(
            "DELETE FROM chats WHERE id = ? AND user_id = ?", (chat_id, user["id"])
        )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Chat not found.")
    return {"ok": True}


@app.get("/api/models")
def get_models(request: Request) -> dict[str, object]:
    _user_for(request)
    client, config = _get_client()
    try:
        models = list_models(client)
    except Exception as exc:  # noqa: BLE001 - return a useful API message
        raise HTTPException(status_code=502, detail=friendly_error_message(exc)) from None
    return {"models": models, "current": config.model_name}


@app.post("/api/chats/{chat_id}/messages")
def send_message(chat_id: str, body: ChatInput, request: Request) -> StreamingResponse:
    user = _user_for(request)
    row = _chat_row(chat_id, user["id"])
    user_text = body.content.strip()
    if not user_text:
        raise HTTPException(status_code=422, detail="Message cannot be blank.")
    client, config = _get_client()
    selected_model = body.model or config.model_name
    messages = json.loads(row["messages"])
    history = ChatHistory(SYSTEM_PROMPT)
    history.messages.extend(messages)
    history.add_user(user_text)
    api_messages = history.messages_for_api(config.max_history_messages)

    def events():
        pieces: list[str] = []
        try:
            for piece in stream_chat(client, selected_model, api_messages):
                pieces.append(piece)
                yield f"data: {json.dumps({'type': 'token', 'text': piece})}\n\n"
            reply = "".join(pieces).strip()
            if not reply:
                yield f"data: {json.dumps({'type': 'error', 'message': 'NOVA returned an empty answer. Please try again.'})}\n\n"
                return
            saved_messages = [*messages, {"role": "user", "content": user_text}, {"role": "assistant", "content": reply}]
            title = row["title"]
            if title == "New chat":
                title = " ".join(user_text.split())[:54] or "New chat"
            with _connect() as connection:
                connection.execute(
                    "UPDATE chats SET title = ?, messages = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                    (title, json.dumps(saved_messages, ensure_ascii=False), _now(), chat_id, user["id"]),
                )
            yield f"data: {json.dumps({'type': 'done', 'title': title})}\n\n"
        except Exception as exc:  # noqa: BLE001 - turn provider errors into an SSE message
            message = friendly_error_message(exc)
            yield f"data: {json.dumps({'type': 'error', 'message': message})}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("nova.web:app", host="127.0.0.1", port=8000, reload=False)