"""Chainlit web UI for the Smash tool-calling agent."""

from __future__ import annotations

import os
from typing import Any

import chainlit as cl
from langchain_core.messages import HumanMessage

from agent import build_agent


def _build_agent_from_env() -> Any:
    model = os.getenv("OLLAMA_MODEL", "qwen3:14b")
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    api_base_url = os.getenv("SMASH_API_BASE_URL", "https://server.cetacean-tuna.ts.net")
    include_high_intensity = os.getenv("DISABLE_HIGH_INTENSITY", "false").lower() not in {
        "1",
        "true",
        "yes",
    }
    return build_agent(
        model=model,
        base_url=ollama_base_url,
        api_base_url=api_base_url,
        include_high_intensity=include_high_intensity,
    )


@cl.on_chat_start
async def on_chat_start() -> None:
    agent = _build_agent_from_env()
    cl.user_session.set("agent", agent)
    cl.user_session.set("history", [])
    await cl.Message(
        content=(
            "Smash Data assistant is ready.\n"
            "Ask about GA rankings, tournament lookups, or analytics."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    agent = cl.user_session.get("agent")
    history = cl.user_session.get("history") or []

    history.append(HumanMessage(content=message.content))
    try:
        result = await cl.make_async(agent.invoke)({"messages": history})
        messages = result.get("messages", [])
        cl.user_session.set("history", messages[-40:])
        content = messages[-1].content if messages else "No response from agent."
        await cl.Message(content=content).send()
    except Exception as exc:  # noqa: BLE001
        await cl.Message(content=f"Agent error: {exc}").send()
