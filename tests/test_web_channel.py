import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
import websockets

from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus
from nanobot.channels.web import WebChannel
from nanobot.config.schema import WebConfig
from nanobot.providers.base import LLMProvider, LLMResponse


class _MockProvider(LLMProvider):
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content") or ""
                break
        return LLMResponse(content=f"echo: {last_user}")

    def get_default_model(self) -> str:
        return "mock"


@pytest.mark.asyncio
async def test_web_channel_roundtrip_and_history(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Keep sessions isolated from the real home directory.
    monkeypatch.setenv("HOME", str(tmp_path))

    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    bus = MessageBus()
    web = WebChannel(
        WebConfig(enabled=True, host="127.0.0.1", port=0),
        bus,
        workspace=workspace,
    )
    agent = AgentLoop(bus=bus, provider=_MockProvider(), workspace=workspace, model="mock")

    async def dispatch_outbound() -> None:
        try:
            while True:
                msg = await bus.consume_outbound()
                await web.send(msg)
        except asyncio.CancelledError:
            return

    web_task = asyncio.create_task(web.start())
    await web.wait_ready()

    dispatch_task = asyncio.create_task(dispatch_outbound())
    agent_task = asyncio.create_task(agent.run())

    session_id = "test_session"
    uri = f"ws://127.0.0.1:{web.bound_port()}/ws?session={session_id}&client=test_client"

    try:
        # 1) Chat roundtrip.
        async with websockets.connect(uri, proxy=None) as ws:
            history = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert history["type"] == "history"
            assert history["messages"] == []

            await ws.send(json.dumps({"type": "message", "content": "hello"}))

            assistant = None
            for _ in range(10):
                data = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                if data.get("type") == "message" and data.get("role") == "assistant":
                    assistant = data
                    break
            assert assistant is not None
            assert assistant["content"] == "echo: hello"

        # 2) Reconnect; server should provide updated history from disk.
        async with websockets.connect(uri, proxy=None) as ws:
            history2 = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert history2["type"] == "history"
            msgs = history2["messages"]
            assert any(m["role"] == "user" and m["content"] == "hello" for m in msgs)
            assert any(m["role"] == "assistant" and m["content"] == "echo: hello" for m in msgs)
    finally:
        agent.stop()
        await web.stop()

        dispatch_task.cancel()
        agent_task.cancel()
        web_task.cancel()

        for t in (dispatch_task, agent_task, web_task):
            try:
                await t
            except asyncio.CancelledError:
                pass

