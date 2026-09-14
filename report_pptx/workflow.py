from __future__ import annotations

from pathlib import Path
from dataclasses import replace
from typing import Any, Literal, TypedDict

from .config import LlmConfig
from .core import PresentationModel, SemanticValidator
from .llm import StructuredGateway
from .planning import IntelligentDeckPlanner
from .render import ArtifactToolRenderer, Phase2Result
from .llm import create_gateway
from .visual_review import DeckVisualReview, VisualReviewer


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


class Phase4State(TypedDict):
    presentation: PresentationModel
    deck_specification: dict[str, Any] | None
    render_result: Phase2Result | None
    visual_reviews: list[DeckVisualReview]
    repair_attempts: int
    diagnostics: list[str]
    status: Literal["running", "completed", "completed_with_warnings", "failed"]


class Phase4Workflow:
    """Render, visually review, and replan rejected narrative groups within a hard attempt limit."""

    def __init__(
        self,
        config: LlmConfig,
        workspace: Path,
        planning_gateway: StructuredGateway | None = None,
        visual_gateway: StructuredGateway | None = None,
    ) -> None:
        self.config = config
        self.workspace = workspace
        self.planning_gateway = planning_gateway or create_gateway(config, workspace / "build" / "llm-cache")
        visual_config = replace(config, planning_model=config.visual_review_model)
        self.visual_gateway = visual_gateway or create_gateway(visual_config, workspace / "build" / "visual-review-cache")
        self.planner = IntelligentDeckPlanner(config, workspace, self.planning_gateway)
        self.reviewer = VisualReviewer(config, self.visual_gateway)
        self.renderer = ArtifactToolRenderer(workspace)

    def run(self, presentation: PresentationModel, output_name: str) -> Phase4State:
        state: Phase4State = {
            "presentation": presentation, "deck_specification": None, "render_result": None,
            "visual_reviews": [], "repair_attempts": 0, "diagnostics": [], "status": "running",
        }
        report = SemanticValidator().validate(presentation)
        if not report.is_valid:
            state["diagnostics"] = [f"{item.severity}:{item.code}:{item.message}" for item in report.diagnostics]
            state["status"] = "failed"
            return state

        feedback: dict[str, str] = {}
        iteration_dir = self.workspace / "build" / "phase4" / "iterations"
        try:
            self.config.validate_visual_review()
            for attempt in range(self.config.max_slide_repair_attempts + 1):
                specification = self.planner.plan(presentation, feedback)
                state["deck_specification"] = specification
                draft = self.renderer.render(
                    specification, name=f"visual-review-{attempt}.pptx", output_dir=iteration_dir,
                )
                review = self.reviewer.review(specification, draft.build_dir)
                state["visual_reviews"].append(review)
                if review.accepted:
                    state["render_result"] = self.renderer.render(specification, name=output_name)
                    state["status"] = "completed"
                    return state
                if not review.group_feedback:
                    if review.hard_failures:
                        state["diagnostics"].append(
                            "Visual review found unresolved hard failures on non-narrative slides."
                        )
                    break
                feedback = review.group_feedback
                state["repair_attempts"] = attempt + 1
            final_review = state["visual_reviews"][-1] if state["visual_reviews"] else None
            if final_review and not final_review.hard_failures and state["deck_specification"] is not None:
                state["render_result"] = self.renderer.render(state["deck_specification"], name=output_name)
                state["diagnostics"].append(
                    "Finalized with advisory visual warnings after exhausting layout alternatives; no hard visual failures remain."
                )
                state["status"] = "completed_with_warnings"
                return state
            state["diagnostics"].append(f"Visual acceptance not reached within {self.config.max_slide_repair_attempts} repair attempts")
        except Exception as exc:
            state["diagnostics"].append(f"error:phase4:{exc}")
        state["status"] = "failed"
        return state
