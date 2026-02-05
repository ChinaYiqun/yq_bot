"""Web UI channel (local web chat) using websockets for WS + minimal HTTP."""

from __future__ import annotations

import asyncio
import json
import secrets
from datetime import datetime
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


_INDEX_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>nanobot Web Chat</title>
    <style>
      :root{
        --bg0:#0b0f1a;
        --bg1:#101a33;
        --card: rgba(255,255,255,.06);
        --card2: rgba(255,255,255,.09);
        --stroke: rgba(255,255,255,.10);
        --text:#e9edf7;
        --muted: rgba(233,237,247,.70);
        --brand:#7ad7ff;
        --brand2:#9bffcf;
        --user:#92a8ff;
        --assistant:#7cffc4;
        --warn:#ffcc66;
        --shadow: 0 18px 50px rgba(0,0,0,.45);
        --radius: 18px;
      }

      *{box-sizing:border-box}
      html,body{height:100%}
      body{
        margin:0;
        color:var(--text);
        font-family: ui-rounded, "SF Pro Rounded", "Avenir Next", "Segoe UI Variable Display", "Segoe UI", sans-serif;
        background:
          radial-gradient(1200px 600px at 20% 10%, rgba(122,215,255,.25), transparent 50%),
          radial-gradient(900px 500px at 80% 25%, rgba(155,255,207,.18), transparent 55%),
          radial-gradient(900px 700px at 60% 120%, rgba(146,168,255,.14), transparent 55%),
          linear-gradient(180deg, var(--bg0), var(--bg1));
        overflow:hidden;
      }

      .wrap{
        height:100%;
        display:flex;
        padding: clamp(12px, 2.2vw, 24px);
        gap: clamp(12px, 2.2vw, 18px);
      }

      .panel{
        width: 340px;
        max-width: 42vw;
        background: linear-gradient(180deg, rgba(255,255,255,.08), rgba(255,255,255,.05));
        border: 1px solid var(--stroke);
        border-radius: var(--radius);
        box-shadow: var(--shadow);
        padding: 18px;
        display:flex;
        flex-direction:column;
        gap: 14px;
      }

      .brand{
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap: 10px;
      }
      .brand h1{
        margin:0;
        font-size: 18px;
        letter-spacing: .2px;
        font-weight: 700;
      }
      .pill{
        font-size: 12px;
        padding: 6px 10px;
        border-radius: 999px;
        background: rgba(0,0,0,.25);
        border: 1px solid rgba(255,255,255,.10);
        color: var(--muted);
        user-select:none;
      }
      .pill.ok{color: rgba(122,255,193,.92); border-color: rgba(122,255,193,.25);}
      .pill.bad{color: rgba(255,180,120,.92); border-color: rgba(255,180,120,.25);}

      .kv{
        display:flex;
        flex-direction:column;
        gap: 8px;
      }
      .kv label{
        font-size: 12px;
        color: var(--muted);
      }
      .kv .row{
        display:flex;
        gap: 10px;
        align-items:center;
      }
      .mono{
        font-family: ui-monospace, "SF Mono", Menlo, Monaco, Consolas, "Liberation Mono", monospace;
        font-size: 12px;
        color: rgba(233,237,247,.86);
        padding: 10px 12px;
        border-radius: 14px;
        border: 1px solid rgba(255,255,255,.10);
        background: rgba(0,0,0,.25);
        overflow:hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .btns{display:flex; gap:10px; flex-wrap:wrap}
      button{
        appearance:none;
        border: 1px solid rgba(255,255,255,.12);
        background: linear-gradient(180deg, rgba(255,255,255,.12), rgba(255,255,255,.06));
        color: var(--text);
        border-radius: 14px;
        padding: 10px 12px;
        font-weight: 650;
        font-size: 13px;
        cursor:pointer;
        transition: transform .06s ease, border-color .18s ease, background .18s ease;
      }
      button:hover{border-color: rgba(255,255,255,.22)}
      button:active{transform: translateY(1px)}
      button.secondary{background: rgba(0,0,0,.18)}
      button.danger{border-color: rgba(255,204,102,.28); color: rgba(255,227,163,.96)}

      .hint{
        margin-top:auto;
        font-size: 12px;
        line-height: 1.35;
        color: var(--muted);
      }

      .chat{
        flex:1;
        min-width: 0;
        background: linear-gradient(180deg, rgba(255,255,255,.07), rgba(255,255,255,.04));
        border: 1px solid var(--stroke);
        border-radius: var(--radius);
        box-shadow: var(--shadow);
        display:flex;
        flex-direction:column;
        overflow:hidden;
      }

      .messages{
        flex:1;
        overflow:auto;
        padding: 18px;
        display:flex;
        flex-direction:column;
        gap: 12px;
        scroll-behavior:smooth;
      }
      .messages::-webkit-scrollbar{width: 10px}
      .messages::-webkit-scrollbar-thumb{background: rgba(255,255,255,.10); border-radius: 999px}
      .messages::-webkit-scrollbar-track{background: transparent}

      .msg{
        max-width: 760px;
        display:flex;
        flex-direction:column;
        gap: 6px;
        opacity: 0;
        transform: translateY(6px);
        animation: in .22s ease forwards;
      }
      @keyframes in{
        to{opacity:1; transform: translateY(0)}
      }
      .msg.user{align-self:flex-end}
      .msg.assistant{align-self:flex-start}
      .bubble{
        padding: 12px 14px;
        border-radius: 16px;
        border: 1px solid rgba(255,255,255,.10);
        background: rgba(0,0,0,.22);
        white-space: pre-wrap;
        line-height: 1.35;
        font-size: 14px;
      }
      .msg.user .bubble{
        border-color: rgba(146,168,255,.28);
        background: linear-gradient(180deg, rgba(146,168,255,.18), rgba(0,0,0,.22));
      }
      .msg.assistant .bubble{
        border-color: rgba(124,255,196,.24);
        background: linear-gradient(180deg, rgba(124,255,196,.14), rgba(0,0,0,.22));
      }
      .meta{
        font-size: 11px;
        color: rgba(233,237,247,.55);
      }

      .composer{
        border-top: 1px solid rgba(255,255,255,.10);
        padding: 14px;
        display:flex;
        gap: 10px;
        align-items:flex-end;
        background: rgba(0,0,0,.12);
      }
      textarea{
        flex:1;
        min-height: 44px;
        max-height: 140px;
        resize: none;
        padding: 12px 12px;
        border-radius: 16px;
        border: 1px solid rgba(255,255,255,.12);
        background: rgba(0,0,0,.22);
        color: var(--text);
        font-size: 14px;
        outline:none;
      }
      textarea:focus{border-color: rgba(122,215,255,.35)}
      .send{
        min-width: 90px;
        background: linear-gradient(135deg, rgba(122,215,255,.22), rgba(155,255,207,.18));
        border-color: rgba(122,215,255,.25);
      }

      .toast{
        position: fixed;
        bottom: 18px;
        left: 50%;
        transform: translateX(-50%);
        padding: 10px 12px;
        border-radius: 999px;
        background: rgba(0,0,0,.58);
        border: 1px solid rgba(255,255,255,.14);
        color: rgba(233,237,247,.85);
        font-size: 12px;
        opacity: 0;
        pointer-events:none;
        transition: opacity .18s ease;
      }
      .toast.show{opacity:1}

      @media (max-width: 920px){
        body{overflow:auto}
        .wrap{flex-direction:column; overflow:auto; height:auto}
        .panel{width:100%; max-width:none}
        .chat{min-height: 70vh}
      }
    </style>
  </head>
  <body>
    <div class="wrap">
      <aside class="panel">
        <div class="brand">
          <h1>nanobot Web Chat</h1>
          <div id="status" class="pill bad">disconnected</div>
        </div>

        <div class="kv">
          <label>Session</label>
          <div class="row">
            <div id="session" class="mono" title="Session ID"></div>
            <button id="copy" class="secondary" title="Copy session id">Copy</button>
          </div>
        </div>

        <div class="btns">
          <button id="new" class="secondary">New Chat</button>
          <button id="clear" class="danger">Clear</button>
          <button id="reconnect" class="secondary">Reconnect</button>
        </div>

        <div class="hint">
          Enter to send. Shift+Enter for a newline.<br/>
          Session is stored in your browser so history survives reloads.
        </div>
      </aside>

      <main class="chat">
        <div id="messages" class="messages" aria-live="polite"></div>
        <div class="composer">
          <textarea id="input" placeholder="Message nanobot…"></textarea>
          <button id="send" class="send">Send</button>
        </div>
      </main>
    </div>

    <div id="toast" class="toast"></div>

    <script>
      const $ = (sel) => document.querySelector(sel);
      const elMessages = $("#messages");
      const elInput = $("#input");
      const elStatus = $("#status");
      const elSession = $("#session");
      const elToast = $("#toast");

      const store = {
        get(k){ try { return localStorage.getItem(k) } catch(_) { return null } },
        set(k,v){ try { localStorage.setItem(k,v) } catch(_) {} },
      };

      function randId(prefix){
        const a = new Uint8Array(12);
        crypto.getRandomValues(a);
        return prefix + Array.from(a).map(b => b.toString(16).padStart(2,"0")).join("");
      }

      function getSessionId(){
        const url = new URL(location.href);
        const fromUrl = url.searchParams.get("session");
        if (fromUrl) { store.set("nanobot.web.session", fromUrl); return fromUrl; }
        const fromStore = store.get("nanobot.web.session");
        if (fromStore) return fromStore;
        const sid = randId("s_");
        store.set("nanobot.web.session", sid);
        url.searchParams.set("session", sid);
        history.replaceState(null, "", url.toString());
        return sid;
      }

      function getClientId(){
        const fromStore = store.get("nanobot.web.client");
        if (fromStore) return fromStore;
        const cid = randId("c_");
        store.set("nanobot.web.client", cid);
        return cid;
      }

      const sessionId = getSessionId();
      const clientId = getClientId();
      elSession.textContent = sessionId;

      function toast(msg){
        elToast.textContent = msg;
        elToast.classList.add("show");
        setTimeout(() => elToast.classList.remove("show"), 1400);
      }

      function scrollToBottom(){
        elMessages.scrollTop = elMessages.scrollHeight;
      }

      function addMessage(role, content, ts){
        const wrap = document.createElement("div");
        wrap.className = "msg " + (role === "user" ? "user" : "assistant");

        const bubble = document.createElement("div");
        bubble.className = "bubble";
        bubble.textContent = content || "";

        const meta = document.createElement("div");
        meta.className = "meta";
        const t = ts ? new Date(ts) : new Date();
        meta.textContent = (role === "user" ? "You" : "nanobot") + " · " + t.toLocaleTimeString();

        wrap.appendChild(bubble);
        wrap.appendChild(meta);
        elMessages.appendChild(wrap);
        scrollToBottom();
      }

      function clearMessages(){
        elMessages.innerHTML = "";
      }

      let ws = null;
      let reconnectTimer = null;
      let reconnectDelay = 400;

      function setStatus(ok, text){
        elStatus.textContent = text;
        elStatus.classList.toggle("ok", ok);
        elStatus.classList.toggle("bad", !ok);
      }

      function connect(){
        if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
        if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

        const proto = location.protocol === "https:" ? "wss" : "ws";
        const url = `${proto}://${location.host}/ws?session=${encodeURIComponent(sessionId)}&client=${encodeURIComponent(clientId)}`;
        setStatus(false, "connecting");
        ws = new WebSocket(url);

        ws.onopen = () => {
          reconnectDelay = 400;
          setStatus(true, "connected");
        };

        ws.onclose = () => {
          setStatus(false, "disconnected");
          scheduleReconnect();
        };

        ws.onerror = () => {
          setStatus(false, "error");
          try { ws.close(); } catch(_) {}
        };

        ws.onmessage = (ev) => {
          let data = null;
          try { data = JSON.parse(ev.data); } catch(_) { return; }
          if (!data || !data.type) return;

          if (data.type === "history") {
            clearMessages();
            const ms = Array.isArray(data.messages) ? data.messages : [];
            for (const m of ms) {
              if (!m || !m.role) continue;
              addMessage(m.role, m.content || "", m.timestamp || null);
            }
            return;
          }

          if (data.type === "message") {
            addMessage(data.role || "assistant", data.content || "", data.timestamp || null);
            return;
          }

          if (data.type === "info") {
            toast(data.content || "info");
            return;
          }

          if (data.type === "error") {
            toast(data.content || "error");
            return;
          }
        };
      }

      function scheduleReconnect(){
        if (reconnectTimer) return;
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null;
          reconnectDelay = Math.min(6000, Math.floor(reconnectDelay * 1.6));
          connect();
        }, reconnectDelay);
      }

      function sendMessage(){
        const text = (elInput.value || "").trim();
        if (!text) return;
        elInput.value = "";
        addMessage("user", text, new Date().toISOString());

        if (!ws || ws.readyState !== WebSocket.OPEN) {
          toast("Not connected");
          connect();
          return;
        }

        ws.send(JSON.stringify({ type: "message", content: text }));
      }

      $("#send").addEventListener("click", sendMessage);
      elInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          sendMessage();
        }
      });

      $("#copy").addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(sessionId);
          toast("Session copied");
        } catch(_) {
          toast("Copy failed");
        }
      });

      $("#new").addEventListener("click", () => {
        const sid = randId("s_");
        store.set("nanobot.web.session", sid);
        const url = new URL(location.href);
        url.searchParams.set("session", sid);
        location.href = url.toString();
      });

      $("#clear").addEventListener("click", () => {
        if (!confirm("Clear this session history?")) return;
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "clear" }));
        }
        clearMessages();
        toast("Cleared");
      });

      $("#reconnect").addEventListener("click", () => {
        try { if (ws) ws.close(); } catch(_) {}
        connect();
      });

      connect();
      setTimeout(() => { elInput.focus(); }, 80);
    </script>
  </body>
</html>
"""


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
                200, "OK", "text/html; charset=utf-8", _INDEX_HTML.encode("utf-8")
            )

        if path == "/healthz":
            return _http_response(200, "OK", "text/plain; charset=utf-8", b"ok")

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
