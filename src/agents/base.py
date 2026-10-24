"""Official Google ADK (Agent Development Kit) Integration for LegalPilot-VN.

Exports standard Google ADK classes directly from `google.adk`:
- Agent: Official Google ADK Agent (`google.adk.Agent`).
- Runner: Official Google ADK Runner (`google.adk.Runner`).
- Workflow: Official Google ADK Workflow (`google.adk.Workflow`).
- InMemorySessionService: In-memory session manager for ADK runners.

Also provides multi-agent orchestration primitives for LegalPilot-VN:
- ADKAgent: Base adapter class wrapping Google ADK Agent for the compliance pipeline.
- ToolDefinition: Specification and callable wrapper for agent tools.
- AgentResult: Structured output from an agent execution step.
- ADKRunner: Multi-agent pipeline executor and trace manager.
- invoke_adk_agent: Helper to invoke a Google ADK Agent with DeepSeek LLM.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from google.adk import Agent as GoogleAgent
from google.adk import Runner as GoogleRunner
from google.adk import Workflow
from google.adk.sessions import InMemorySessionService
from google.genai import types

from src.core.config import settings
from src.core.logger import logger
from src.tools.base import ToolDefinition

# Re-export official Google ADK primitives as first-class citizens
Agent = GoogleAgent
Runner = GoogleRunner

__all__ = [
    "ADKAgent",
    "ADKRunner",
    "Agent",
    "AgentResult",
    "GoogleAgent",
    "GoogleRunner",
    "InMemorySessionService",
    "Runner",
    "ToolDefinition",
    "Workflow",
    "get_default_model",
    "invoke_adk_agent",
]


def get_default_model() -> str:
    """Returns the configured model string for Google ADK / LiteLLM."""
    # Ensure DEEPSEEK_API_KEY is available in os.environ for LiteLLM
    if settings.DEEPSEEK_API_KEY and "DEEPSEEK_API_KEY" not in os.environ:
        os.environ["DEEPSEEK_API_KEY"] = settings.DEEPSEEK_API_KEY
    return "deepseek/deepseek-chat"


def invoke_adk_agent(
    agent: GoogleAgent,
    prompt: str,
    user_id: str = "legal_practitioner",
    session_id: str | None = None,
    app_name: str = "legalpilot",
) -> str:
    """Invokes an official Google ADK Agent synchronously via Google ADK Runner.

    Handles message creation using `google.genai.types.Content` and aggregates
    streaming event text from the LLM (DeepSeek / LiteLLM).
    """
    sid = session_id or f"session_{uuid.uuid4().hex[:8]}"
    runner = GoogleRunner(
        app_name=app_name,
        agent=agent,
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )

    msg = types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt)],
    )

    collected_text: list[str] = []
    try:
        for event in runner.run(user_id=user_id, session_id=sid, new_message=msg):
            if hasattr(event, "content") and event.content and event.content.parts:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        collected_text.append(part.text)
    except Exception as e:
        logger.error(f"Google ADK Runner invocation failed for agent '{agent.name}': {e}")
        raise e

    return "".join(collected_text)


@dataclass
class AgentResult:
    """Result of an ADK agent execution."""

    agent_name: str
    success: bool
    data: Any
    error: str | None = None
    execution_time_ms: float = 0.0
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))


def get_llm() -> Any | None:
    """Returns a ChatOpenAI instance configured for DeepSeek if needed."""
    try:
        api_key = settings.DEEPSEEK_API_KEY or settings.OPENAI_API_KEY
        if (
            api_key
            and not api_key.startswith("paste_")
            and not api_key.startswith("sk-local-dummy")
        ):
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=settings.DEEPSEEK_MODEL or "deepseek-chat",
                api_key=api_key,  # type: ignore[arg-type]
                base_url=settings.DEEPSEEK_API_BASE or "https://api.deepseek.com",
                temperature=0.1,
            )
    except Exception as e:
        logger.warning(f"Could not initialize ChatOpenAI: {e}")
    return None


class ADKAgent:
    """Base class for Google ADK agents in LegalPilot-VN.

    Wraps an official Google ADK Agent (`google.adk.Agent`) while providing
    execution tracing and backward-compatible helper methods.
    """

    def __init__(
        self,
        name: str,
        description: str,
        role: str = "assistant",
        tools: list[ToolDefinition] | None = None,
        instruction: str | None = None,
        model: str | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.role = role
        self.tools: list[ToolDefinition] = tools or []
        self._tool_map: dict[str, ToolDefinition] = {t.name: t for t in self.tools}
        self.instruction = instruction or f"Bạn là {name}, chuyên trách nhiệm vụ {description}."
        self.model = model or get_default_model()
        self.llm = get_llm()

        # Build official Google ADK Agent instance
        adk_callables: list[Any] = [t.func for t in self.tools]
        try:
            self.adk_agent: GoogleAgent | None = GoogleAgent(
                name=self.name,
                model=self.model,
                instruction=self.instruction,
                description=self.description,
                # google-adk >= 2.3 requires a list; passing None raises a
                # pydantic validation error and silently disables the ADK agent.
                tools=adk_callables,
            )
        except Exception as e:
            logger.warning(f"Failed to initialize underlying Google ADK Agent for {self.name}: {e}")
            self.adk_agent = None

    def register_tool(self, tool: ToolDefinition) -> None:
        """Registers a tool with the agent."""
        self.tools.append(tool)
        self._tool_map[tool.name] = tool
        if self.adk_agent and hasattr(self.adk_agent, "tools"):
            self.adk_agent.tools.append(tool.func)

    def get_tool(self, tool_name: str) -> ToolDefinition | None:
        """Retrieves a registered tool by name."""
        return self._tool_map.get(tool_name)

    def execute(self, input_data: Any, context: dict[str, Any] | None = None) -> AgentResult:
        """Executes the agent's primary task. Subclasses must implement _run."""
        start_time = time.perf_counter()
        try:
            result_data = self._run(input_data, context or {})
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return AgentResult(
                agent_name=self.name,
                success=True,
                data=result_data,
                execution_time_ms=elapsed_ms,
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return AgentResult(
                agent_name=self.name,
                success=False,
                data=None,
                error=str(e),
                execution_time_ms=elapsed_ms,
            )

    def _run(self, input_data: Any, context: dict[str, Any]) -> Any:
        """Core execution logic to be overridden by subclasses."""
        raise NotImplementedError("Subclasses must implement _run method.")


class ADKRunner:
    """Multi-agent orchestrator runner managing state transitions and step tracing."""

    def __init__(self, agents: list[ADKAgent] | None = None) -> None:
        self.agents: dict[str, ADKAgent] = {a.name: a for a in (agents or [])}
        self.execution_history: list[AgentResult] = []

    def register_agent(self, agent: ADKAgent) -> None:
        """Registers an agent into the runner pipeline."""
        self.agents[agent.name] = agent

    def dispatch(
        self, agent_name: str, input_data: Any, context: dict[str, Any] | None = None
    ) -> AgentResult:
        """Dispatches an execution step to a registered agent and logs the trace."""
        agent = self.agents.get(agent_name)
        if not agent:
            raise ValueError(f"Agent '{agent_name}' is not registered in ADKRunner.")

        result = agent.execute(input_data, context)
        self.execution_history.append(result)
        return result
