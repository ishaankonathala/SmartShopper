"""Allowlisted tool registration, validation, and typed execution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.agent.schemas import AgentToolName
from app.agent.state import AgentState

ToolHandler = Callable[[BaseModel, AgentState, Session], BaseModel]


class UnknownToolError(ValueError):
    """Raised when a requested action is not registered."""


class InvalidToolArgumentsError(ValueError):
    """Raised when a registered tool receives invalid arguments."""


@dataclass(frozen=True)
class ToolDefinition:
    name: AgentToolName
    description: str
    input_model: type[BaseModel]
    result_model: type[BaseModel]
    handler: ToolHandler


class ToolRegistry:
    """A fixed allowlist; no model-provided code or external URLs are executed."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise ValueError(f"Tool {definition.name} is already registered.")
        self._tools[definition.name] = definition

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError:
            raise UnknownToolError("Requested tool is not registered.") from None

    def definitions(self) -> tuple[ToolDefinition, ...]:
        return tuple(self._tools.values())

    def validate_arguments(self, name: str, arguments: object) -> BaseModel:
        definition = self.get(name)
        try:
            return definition.input_model.model_validate(arguments)
        except ValidationError as error:
            raise InvalidToolArgumentsError("Tool arguments failed validation.") from error

    def execute(
        self,
        name: str,
        arguments: BaseModel,
        state: AgentState,
        db: Session,
    ) -> BaseModel:
        definition = self.get(name)
        result = definition.handler(arguments, state, db)
        try:
            return definition.result_model.model_validate(result)
        except ValidationError as error:
            raise TypeError("Tool returned an invalid result.") from error
