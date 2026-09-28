"""Google ADK (Agent Development Kit) Base Abstractions for LegalPilot-VN.

Provides standard interfaces for multi-agent systems following Google ADK:
- ADKAgent: Base class for domain-specific agent workers.
- ToolDefinition: Specification and callable wrapper for agent tools.
- AgentResult: Structured output from an agent execution step.
- ADKRunner: Multi-agent pipeline executor and trace manager.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolDefinition:
    """Tool definition compliant with Google ADK tool specifications."""

    name: str
    description: str
    func: Callable[..., Any]
    parameters_schema: dict[str, Any] = field(default_factory=dict)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.func(*args, **kwargs)


@dataclass
class AgentResult:
    """Result of an ADK agent execution."""

    agent_name: str
    success: bool
    data: Any
    error: str | None = None
    execution_time_ms: float = 0.0
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class ADKAgent:
    """Base class for Google ADK-compliant agents."""

    def __init__(
        self,
        name: str,
        description: str,
        role: str = "assistant",
        tools: list[ToolDefinition] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.role = role
        self.tools: list[ToolDefinition] = tools or []
        self._tool_map: dict[str, ToolDefinition] = {t.name: t for t in self.tools}

    def register_tool(self, tool: ToolDefinition) -> None:
        """Registers a tool with the agent."""
        self.tools.append(tool)
        self._tool_map[tool.name] = tool

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

    def dispatch(self, agent_name: str, input_data: Any, context: dict[str, Any] | None = None) -> AgentResult:
        """Dispatches an execution step to a registered agent and logs the trace."""
        agent = self.agents.get(agent_name)
        if not agent:
            raise ValueError(f"Agent '{agent_name}' is not registered in ADKRunner.")

        result = agent.execute(input_data, context)
        self.execution_history.append(result)
        return result
