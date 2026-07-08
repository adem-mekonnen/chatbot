# app/tools/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Type
from pydantic import BaseModel


class ToolStatus(str, Enum):
    """
    Canonical execution outcome for every tool.

    Using a typed enum instead of substring-matching on the response string
    makes status detection in the orchestration layer unambiguous and
    refactor-safe — adding a new status never requires changing chatbot.py.
    """
    SUCCESS          = "SUCCESS"
    FORBIDDEN        = "FORBIDDEN"        # RBAC / ABAC check failed
    REJECTED         = "REJECTED_BY_TOOL" # Business-rule rejection (e.g. insufficient funds)
    NOT_FOUND        = "NOT_FOUND"        # Resource does not exist
    VALIDATION_FAIL  = "VALIDATION_FAILED"
    ERROR            = "ERROR"            # Unexpected internal error


@dataclass
class ToolResult:
    """Structured return value from every BaseTool.execute() call."""
    status:  ToolStatus
    message: str  # Human-readable text forwarded to the end-user


class BaseTool(ABC):
    """
    Abstract Base Class for all pipeline plugins.
    Subclasses are dynamically registered by the routing engine.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier used by the router (e.g. 'get_balance')."""
        pass

    @property
    @abstractmethod
    def required_action(self) -> str:
        """RBAC permission string required to execute this tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Brief description shown to the LLM in the routing prompt."""
        pass

    @property
    @abstractmethod
    def deterministic_patterns(self) -> List[str]:
        """Regex patterns that bypass LLM routing and trigger this tool directly."""
        pass

    @property
    @abstractmethod
    def schema(self) -> Type[BaseModel]:
        """Pydantic schema for validating and coercing tool parameters."""
        pass

    @abstractmethod
    async def execute(self, user_payload: dict, parameters: BaseModel) -> ToolResult:
        """Execute the tool's core logic and return a structured ToolResult."""
        pass
