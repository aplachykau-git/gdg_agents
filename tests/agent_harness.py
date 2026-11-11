"""Offline conversation harness for ADK agents.

Runs a real ADK ``Runner`` (real tools, real session state, real event flow) with a scripted
model instead of Gemini, so conversation contracts can be tested without network or quota::

    harness = AgentHarness(agent, steps=[call("update_speaker", name="Jane"), text("Saved!")])
    events = harness.say("My name is Jane")

Each model invocation consumes the next step. A step is either a tool call or a text reply.
"""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.sessions.base_session_service import BaseSessionService
from google.genai import types


@dataclass
class Step:
    kind: str  # "call" | "text"
    name: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    text: str = ""


def call(tool: str, /, **args: Any) -> Step:
    return Step(kind="call", name=tool, args=args)


def text(value: str) -> Step:
    return Step(kind="text", text=value)


class ScriptedLlm(BaseLlm):
    model: str = "scripted-test-model"
    steps: list[Step] = []
    requests: list[LlmRequest] = []

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self.requests.append(llm_request)
        if not self.steps:
            raise AssertionError("ScriptedLlm ran out of steps")
        step = self.steps.pop(0)
        if step.kind == "call":
            part = types.Part(function_call=types.FunctionCall(name=step.name, args=step.args))
        else:
            part = types.Part(text=step.text)
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


def clone_with_model(agent: LlmAgent, model: BaseLlm) -> LlmAgent:
    """Copy an agent (and its sub-agents) so it runs on ``model`` without touching the original."""
    clone = agent.model_copy(update={"model": model, "parent_agent": None, "sub_agents": []})
    clone.sub_agents = [clone_with_model(sub, model) for sub in agent.sub_agents if isinstance(sub, LlmAgent)]
    for sub in clone.sub_agents:
        sub.parent_agent = clone
    return clone


class AgentHarness:
    def __init__(
        self,
        agent: LlmAgent,
        steps: list[Step] | None = None,
        session_service: BaseSessionService | None = None,
        app_name: str = "harness",
        user_id: str = "tester",
        session_id: str | None = None,
        initial_state: dict[str, Any] | None = None,
    ):
        self.llm = ScriptedLlm(steps=list(steps or []), requests=[])
        self.agent = clone_with_model(agent, self.llm)
        self.session_service = session_service or InMemorySessionService()
        self.runner = Runner(app_name=app_name, agent=self.agent, session_service=self.session_service)
        self.app_name = app_name
        self.user_id = user_id
        self.session_id = session_id or asyncio.run(self._create_session(initial_state))

    async def _create_session(self, state: dict[str, Any] | None) -> str:
        session = await self.session_service.create_session(
            app_name=self.app_name, user_id=self.user_id, state=copy.deepcopy(state or {})
        )
        return session.id

    def script(self, *steps: Step) -> "AgentHarness":
        self.llm.steps.extend(steps)
        return self

    def say(
        self,
        message: str = "",
        *,
        attachments: list[tuple[str, bytes]] | None = None,
        state_delta: dict[str, Any] | None = None,
    ) -> list[Any]:
        parts = [types.Part(inline_data=types.Blob(mime_type=m, data=d)) for m, d in attachments or []]
        if message:
            parts.append(types.Part(text=message))
        return asyncio.run(self._run(types.Content(role="user", parts=parts), state_delta))

    async def _run(self, content: types.Content, state_delta: dict[str, Any] | None) -> list[Any]:
        events = []
        async for event in self.runner.run_async(
            user_id=self.user_id, session_id=self.session_id, new_message=content, state_delta=state_delta
        ):
            events.append(event)
        return events

    def state(self) -> dict[str, Any]:
        session = asyncio.run(
            self.session_service.get_session(app_name=self.app_name, user_id=self.user_id, session_id=self.session_id)
        )
        return dict(session.state)

    @staticmethod
    def tool_responses(events: list[Any], name: str | None = None) -> list[dict[str, Any]]:
        responses = []
        for event in events:
            for part in (event.content.parts if event.content else None) or []:
                if part.function_response and (name is None or part.function_response.name == name):
                    responses.append(dict(part.function_response.response or {}))
        return responses
