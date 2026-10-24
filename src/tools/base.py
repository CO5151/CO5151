"""Base tool abstractions for LegalPilot-VN (Google ADK compliant tools)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class ToolDefinition:
    """Tool definition compliant with Google ADK tool specifications."""

    name: str
    description: str
    func: Callable[..., Any]
    parameters_schema: dict[str, Any] = field(default_factory=dict)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.func(*args, **kwargs)
