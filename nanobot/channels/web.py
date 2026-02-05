"""Web UI channel (local web chat) using websockets for WS + minimal HTTP."""

from __future__ import annotations

import asyncio
import json
import secrets
from datetime import datetime
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from loguru import logger
from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.datastructures import Headers
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import WebConfig
from nanobot.session.manager import SessionManager


_INDEX_HTML_CACHE: str | None = None


def _load_index_html() -> str:
    global _INDEX_HTML_CACHE
    if _INDEX_HTML_CACHE is not None:
        return _INDEX_HTML_CACHE
    try:
        html_path = resources.files("nanobot.channels").joinpath("web_ui.html")
        _INDEX_HTML_CACHE = html_path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.error(f"Failed to load web UI HTML: {exc}")
        _INDEX_HTML_CACHE = (
            "<!doctype html><html><head><meta charset='utf-8' />"
            "<title>nanobot Web Chat</title></head>"
            "<body><h1>nanobot Web Chat</h1><p>Missing web_ui.html</p></body></html>"
        )
    return _INDEX_HTML_CACHE


def _list_skill_dirs() -> list[str]:
    try:
        skills_root = resources.files("nanobot").joinpath("skills")
        names: list[str] = []
        for entry in skills_root.iterdir():
            name = entry.name
            if name.startswith(".") or name.startswith("__"):
                continue
            if entry.is_dir():
                names.append(name)
        names.sort()
        return names
    except Exception as exc:
        logger.debug(f"Failed to list skills: {exc}")
        return []


def _http_response(status: int, reason: str, content_type: str, body: bytes) -> Response:
    headers = Headers()
    headers["Content-Type"] = content_type
    headers["Content-Length"] = str(len(body))
    headers["Cache-Control"] = "no-store"
    headers["X-Content-Type-Options"] = "nosniff"
    return Response(status_code=status, reason_phrase=reason, headers=headers, body=body)


class WebChannel(BaseChannel):
    """
    Web UI channel.

    Serves:
    - `GET /` -> a single-page chat UI
    - `WS /ws?session=...&client=...` -> JSON chat protocol
    """

    name = "web"

    def __init__(self, config: WebConfig, bus: MessageBus, workspace: Path):
        super().__init__(config, bus)
        self.config: WebConfig = config
        self._server: Server | None = None
        self._ready = asyncio.Event()
        self._connections: dict[str, set[ServerConnection]] = {}
        self._sessions = SessionManager(workspace)

    async def start(self) -> None:
        """Start the WebSocket + HTTP server."""
        if self._server:
            return

        self._running = True

        host = self.config.host
        port = self.config.port

        logger.info(f"Starting web UI on http://{host}:{port}")

        try:
            self._server = await serve(
                self._ws_handler,
                host=host,
                port=port,
                process_request=self._process_request,
                # Disallow huge payloads; user messages should be small.
                max_size=2 * 1024 * 1024,
            )
            self._ready.set()
            await self._server.wait_closed()
        except asyncio.CancelledError:
            raise
        finally:
            self._running = False
            self._server = None
            self._ready.clear()

    async def stop(self) -> None:
        """Stop the web server and close all client connections."""
        self._running = False

        # Close client connections first (best-effort).
        for conns in list(self._connections.values()):
            for ws in list(conns):
                try:
                    await ws.close(code=1001, reason="Server shutting down")
                except Exception:
                    pass
        self._connections.clear()

        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def send(self, msg: OutboundMessage) -> None:
        """Send an outbound message to all connected clients in the session."""
        conns = self._connections.get(msg.chat_id)
        if not conns:
            return

        payload = {
            "type": "message",
            "role": "assistant",
            "content": msg.content or "",
            "timestamp": datetime.now().isoformat(),
        }
        raw = json.dumps(payload, ensure_ascii=False)

        stale: list[ServerConnection] = []
        for ws in conns:
            try:
                await ws.send(raw)
            except ConnectionClosed:
                stale.append(ws)
            except Exception as e:
                logger.debug(f"Web send failed: {e}")
                stale.append(ws)

        for ws in stale:
            conns.discard(ws)
        if not conns:
            self._connections.pop(msg.chat_id, None)

    async def wait_ready(self, timeout_s: float = 5.0) -> None:
        """Wait until the server is ready (useful in tests)."""
        await asyncio.wait_for(self._ready.wait(), timeout=timeout_s)

    def bound_port(self) -> int | None:
        """Get the bound port (useful when configured with port=0 in tests)."""
        if not self._server or not self._server.sockets:
            return None
        return int(self._server.sockets[0].getsockname()[1])

    async def _process_request(self, _: ServerConnection, request: Request) -> Response | None:
        # Allow WS upgrade for /ws; serve HTTP for everything else.
        path = urlparse(request.path).path

        if path.startswith("/ws"):
            return None

        if path in ("/", "/index.html"):
            return _http_response(
                200, "OK", "text/html; charset=utf-8", _load_index_html().encode("utf-8")
            )

        if path == "/healthz":
            return _http_response(200, "OK", "text/plain; charset=utf-8", b"ok")

        if path == "/api/skills":
            payload = {"skills": _list_skill_dirs()}
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            return _http_response(200, "OK", "application/json; charset=utf-8", body)

        if path == "/favicon.ico":
            return _http_response(204, "No Content", "image/x-icon", b"")

        return _http_response(404, "Not Found", "text/plain; charset=utf-8", b"not found")

    async def _ws_handler(self, ws: ServerConnection) -> None:
        req = getattr(ws, "request", None)
        if req is None:
            await ws.close(code=1008, reason="Missing request context")
            return

        parsed = urlparse(req.path)
        qs = parse_qs(parsed.query)

        session_id = (qs.get("session") or [""])[0].strip() or secrets.token_hex(12)
        client_id = (qs.get("client") or [""])[0].strip() or secrets.token_hex(8)

        if not self.is_allowed(client_id):
            await ws.close(code=1008, reason="Not allowed")
            return

        # Track connection by session.
        conns = self._connections.setdefault(session_id, set())
        conns.add(ws)

        logger.info(f"Web client connected: session={session_id} client={client_id}")

        # Send history on connect.
        await self._send_history(ws, session_id)

        try:
            async for raw in ws:
                await self._handle_ws_message(
                    ws, raw, session_id=session_id, client_id=client_id
                )
        except ConnectionClosed:
            pass
        except Exception as e:
            logger.debug(f"Web client error: {e}")
        finally:
            conns.discard(ws)
            if not conns:
                self._connections.pop(session_id, None)
            logger.info(f"Web client disconnected: session={session_id} client={client_id}")

    async def _send_history(self, ws: ServerConnection, session_id: str) -> None:
        key = f"{self.name}:{session_id}"
        # The agent writes session history via a different SessionManager instance.
        # Force refresh from disk to avoid serving stale cached history on reloads.
        session = self._sessions.get_or_create(key, refresh=True)

        # Send full session messages (role/content/timestamp) for UI rendering.
        messages: list[dict[str, Any]] = []
        for m in session.messages[-200:]:
            role = m.get("role")
            content = m.get("content")
            if role not in ("user", "assistant"):
                continue
            messages.append(
                {
                    "role": role,
                    "content": content or "",
                    "timestamp": m.get("timestamp"),
                }
            )

        payload = {"type": "history", "session": session_id, "messages": messages}
        await ws.send(json.dumps(payload, ensure_ascii=False))

    async def _handle_ws_message(
        self,
        ws: ServerConnection,
        raw: str,
        *,
        session_id: str,
        client_id: str,
    ) -> None:
        data: dict[str, Any] | None = None
        if raw and raw[:1] in ("{", "["):
            try:
                data = json.loads(raw)
            except Exception:
                data = None

        if not isinstance(data, dict):
            # Fallback: treat as plain message text.
            content = (raw or "").strip()
            if content:
                await self._handle_message(
                    sender_id=client_id,
                    chat_id=session_id,
                    content=content,
                )
            return

        msg_type = str(data.get("type") or "")

        if msg_type == "message":
            content = str(data.get("content") or "").strip()
            if not content:
                return
            await self._handle_message(
                sender_id=client_id,
                chat_id=session_id,
                content=content,
            )
            return

        if msg_type == "clear":
            key = f"{self.name}:{session_id}"
            self._sessions.delete(key)
            await ws.send(json.dumps({"type": "info", "content": "cleared"}, ensure_ascii=False))
            await self._send_history(ws, session_id)
            return

        await ws.send(
            json.dumps(
                {"type": "error", "content": f"unknown message type: {msg_type}"},
                ensure_ascii=False,
            )
        )
