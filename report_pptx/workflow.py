from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, TypedDict

from .config import LlmConfig
from .core import PresentationModel, SemanticValidator
from .llm import StructuredGateway
from .planning import IntelligentDeckPlanner


class WorkflowState(TypedDict):
    presentation: PresentationModel
    validation_ok: bool
    deck_specification: dict[str, Any] | None
    diagnostics: list[str]
    status: Literal["running", "completed", "failed"]


class Phase3Workflow:
    """Small explicit state workflow; nodes map directly to a future LangGraph graph."""

    def __init__(self, config: LlmConfig, workspace: Path, gateway: StructuredGateway | None = None) -> None:
        self.planner = IntelligentDeckPlanner(config, workspace, gateway)

    def run(self, presentation: PresentationModel) -> WorkflowState:
        state: WorkflowState = {
            "presentation": presentation, "validation_ok": False, "deck_specification": None,
            "diagnostics": [], "status": "running",
        }
        report = SemanticValidator().validate(presentation)
        state["validation_ok"] = report.is_valid
        state["diagnostics"] = [f"{item.severity}:{item.code}:{item.message}" for item in report.diagnostics]
        if not report.is_valid:
            state["status"] = "failed"
            return state
        try:
            state["deck_specification"] = self.planner.plan(presentation)
            state["status"] = "completed"
        except Exception as exc:
            state["diagnostics"].append(f"error:llm_planning:{exc}")
            state["status"] = "failed"
        return state
