"""Chainlit web UI for the Smash tool-calling agent."""

from __future__ import annotations

import os
from typing import Any

import chainlit as cl
from langchain_core.messages import HumanMessage

from agent import build_agent
from sql_agent import build_sql_agent


def _build_api_agent() -> Any:
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


def _build_sql_agent() -> Any:
    model = os.getenv("OLLAMA_MODEL", "qwen3:14b")
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    db_path = os.getenv(
        "SMASH_DB_PATH",
        "/home/ozdotdotdot/code-repos/smashDA/.cache/startgg/smash.db",
    )
    return build_sql_agent(
        model=model,
        base_url=ollama_base_url,
        db_path=db_path,
    )


@cl.on_chat_start
async def on_chat_start() -> None:
    actions = [
        cl.Action(name="api_agent", payload={"mode": "api"}, label="API Agent (rankings & analytics)"),
        cl.Action(name="sql_agent", payload={"mode": "sql"}, label="SQL Agent (query database directly)"),
    ]
    await cl.Message(
        content="**Choose an agent mode:**\n"
        "- **API Agent** — rankings, tournament lookups, player analytics via the Smash API\n"
        "- **SQL Agent** — ask natural language questions answered with SQL against the local database",
        actions=actions,
    ).send()


@cl.action_callback("api_agent")
async def on_api_agent(action: cl.Action) -> None:
    await cl.Message(content="Building API agent...").send()
    agent = _build_api_agent()
    cl.user_session.set("agent", agent)
    cl.user_session.set("history", [])
    await cl.Message(
        content="API agent is ready.\n"
        "Ask about GA rankings, tournament lookups, or analytics."
    ).send()


@cl.action_callback("sql_agent")
async def on_sql_agent(action: cl.Action) -> None:
    await cl.Message(content="Building SQL agent (connecting to database)...").send()
    agent = _build_sql_agent()
    cl.user_session.set("agent", agent)
    cl.user_session.set("history", [])
    await cl.Message(
        content="SQL agent is ready.\n"
        "Ask natural language questions about the Smash database — "
        "tournaments, player stats, match results, and more."
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    agent = cl.user_session.get("agent")
    if agent is None:
        await cl.Message(
            content="Please select an agent mode first using the buttons above."
        ).send()
        return

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
