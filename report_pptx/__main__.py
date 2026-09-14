from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import LlmConfig, load_env
from .core import ReportLoader, ReportNormalizer, SemanticValidator, to_dict
from .planning import IntelligentDeckPlanner
from .render import ArtifactToolRenderer, FixedDeckPlanner
from .workflow import Phase3Workflow, Phase4Workflow


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize report JSON for PPTX planning")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, help="Write normalized JSON to this path")
    parser.add_argument("--strict", action="store_true", help="Return nonzero for warnings as well as errors")
    parser.add_argument("--pptx", action="store_true", help="Render the Phase 2 native PowerPoint deck")
    parser.add_argument("--pptx-name", default="financial-overview-phase2.pptx")
    parser.add_argument("--planner", choices=("llm", "fixed"), default="llm", help="Slide planner (default: llm)")
    args = parser.parse_args()
    load_env(Path.cwd() / ".env")

    try:
        raw = ReportLoader().load(args.input)
        model = ReportNormalizer().normalize(raw)
        report = SemanticValidator().validate(model)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    payload = to_dict(model)
    payload["validation"] = {
        "is_valid": report.is_valid,
        "diagnostics": [to_dict(item) for item in report.diagnostics],
    }
    serialized = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    else:
        if not args.pptx:
            print(serialized)

    if args.pptx:
        if args.planner == "llm":
            config = LlmConfig.from_env()
            if config.enable_visual_review:
                state = Phase4Workflow(config, Path.cwd()).run(model, args.pptx_name)
                if state["status"] not in {"completed", "completed_with_warnings"} or state["render_result"] is None:
                    parser.error("Phase 4 workflow failed: " + "; ".join(state["diagnostics"]))
                print(state["render_result"].pptx_path)
                return 0
            state = Phase3Workflow(config, Path.cwd()).run(model)
            if state["status"] != "completed" or state["deck_specification"] is None:
                parser.error("Phase 3 planning failed: " + "; ".join(state["diagnostics"]))
            specification = state["deck_specification"]
        else:
            specification = FixedDeckPlanner().plan(model)
        result = ArtifactToolRenderer(Path.cwd()).render(specification, name=args.pptx_name)
        print(result.pptx_path)

    has_warning = any(item.severity == "warning" for item in report.diagnostics)
    return 1 if not report.is_valid or (args.strict and has_warning) else 0


if __name__ == "__main__":
    raise SystemExit(main())
