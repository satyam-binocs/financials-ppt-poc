from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import PresentationModel, to_dict


@dataclass(slots=True)
class Phase2Result:
    pptx_path: Path
    build_dir: Path
    specification_path: Path
    slide_count: int


class FixedDeckPlanner:
    """Produce a conservative Phase 2 deck without LLM decisions."""

    def plan(self, model: PresentationModel) -> dict[str, Any]:
        slides: list[dict[str, Any]] = []
        root = model.sections[0] if model.sections else None
        slides.append({
            "id": "cover",
            "kind": "cover",
            "title": (root.heading if root and root.heading_visible else None) or "Report",
            "subtitle": "Financial analysis",
            "notes": self._notes([], model),
        })
        for section in self._sections(model.sections):
            if section is root:
                continue
            title = section.heading if section.heading_visible and section.heading else section.name or "Analysis"
            narrative = next((block for block in section.blocks if block.kind == "narrative" and block.paragraphs), None)
            if section.summary_headline or narrative:
                paragraphs = []
                if section.summary_headline:
                    paragraphs.append({"text": section.summary_headline, "kind": "lead"})
                if narrative:
                    paragraphs.extend(
                        {"text": p.text, "kind": p.kind}
                        for p in narrative.paragraphs
                    )
                chunks = self._paginate_paragraphs(paragraphs)
                for page, chunk in enumerate(chunks, 1):
                    slides.append({
                        "id": f"{section.id}:summary:{page}", "kind": "summary",
                        "title": title if page == 1 else f"{title} continued",
                        "paragraphs": chunk,
                        "notes": self._notes(narrative.citation_ids if narrative else [], model),
                    })

            recommendations = [block for block in section.blocks if block.kind == "recommendation"]
            if recommendations:
                for page, start in enumerate(range(0, len(recommendations), 2), 1):
                    batch = recommendations[start:start + 2]
                    slides.append({
                        "id": f"{section.id}:recommendations:{page}", "kind": "recommendations",
                        "title": title if page == 1 else f"{title} continued",
                        "items": [
                            {"title": block.title or "Request", "text": " ".join(p.text for p in block.paragraphs)}
                            for block in batch
                        ],
                        "notes": self._notes([c for block in batch for c in block.citation_ids], model),
                    })

            for block in section.blocks:
                if block.kind == "chart" and block.chart:
                    slides.append({
                        "id": block.id, "kind": "chart", "title": block.chart.title or title,
                        "section": title, "chart": to_dict(block.chart),
                        "notes": self._notes(block.citation_ids, model),
                    })
                elif block.kind == "table":
                    slides.extend(self._table_slides(title, block, model))
                elif block.kind == "evidence":
                    chunks = self._paginate_paragraphs(
                        [p for p in block.paragraphs if p.kind != "heading"]
                    )
                    for page, chunk in enumerate(chunks, 1):
                        slides.append({
                            "id": f"{block.id}:{page}", "kind": "findings",
                            "title": block.title or title if page == 1 else f"{block.title or title} continued",
                            "paragraphs": [{"text": p.text, "kind": p.kind} for p in chunk],
                            "notes": self._notes(block.citation_ids, model),
                        })
        return {
            "schema_version": "1.0",
            "title": slides[0]["title"],
            "theme": {
                "background": "#F5FAF7", "surface": "#FFFFFF", "ink": "#12372A",
                "muted": "#526B61", "primary": "#0F766E", "secondary": "#34D399",
                "positive": "#16A34A", "negative": "#DC2626", "rule": "#CFE3D8",
                "chart_colors": ["#0F766E", "#16A34A", "#65A30D", "#64748B", "#34D399"],
            },
            "slides": slides,
        }

    def _table_slides(self, section_title, block, model):
        keys = [column.key for column in block.columns]
        # Keep the first identifying column on every horizontal continuation.
        groups = [keys] if len(keys) <= 5 else [[keys[0], *keys[i:i + 4]] for i in range(1, len(keys), 4)]
        result = []
        page = 0
        for group in groups:
            selected_model_columns = [column for column in block.columns if column.key in group]
            for page_rows, row_heights in self._paginate_rows(block.rows, selected_model_columns):
                page += 1
                selected_columns = [
                    {**to_dict(column), "layout_weight": self._column_weight(column, index)}
                    for index, column in enumerate(selected_model_columns)
                ]
                rows = [
                    {key: to_dict(row[key]) for key in group}
                    for row in page_rows
                ]
                result.append({
                    "id": f"{block.id}:table:{page}", "kind": "table",
                    "title": block.title or section_title if page == 1 else f"{block.title or section_title} continued",
                    "columns": selected_columns, "rows": rows, "row_heights": row_heights,
                    "notes": self._notes(block.citation_ids, model),
                })
        return result

    @staticmethod
    def _paginate_rows(rows, columns, *, available_height=440):
        if not rows:
            return [([], [])]
        weights = [FixedDeckPlanner._column_weight(column, index) for index, column in enumerate(columns)]
        total_weight = sum(weights)

        def row_height(row):
            line_counts = []
            for column, weight in zip(columns, weights):
                width = 1136 * weight / total_weight
                chars_per_line = max(8, int(width / 8.2))
                text = row[column.key].plain_text
                explicit_lines = text.splitlines() or [""]
                lines = sum(max(1, (len(line) + chars_per_line - 1) // chars_per_line) for line in explicit_lines)
                line_counts.append(lines)
            return min(190, max(54, max(line_counts, default=1) * 19 + 18))

        heights = [row_height(row) for row in rows]
        pages = []
        current_rows, current_heights, used = [], [], 0
        for row, height in zip(rows, heights):
            if current_rows and used + height > available_height:
                pages.append([current_rows, current_heights])
                current_rows, current_heights, used = [], [], 0
            current_rows.append(row)
            current_heights.append(height)
            used += height
        if current_rows:
            pages.append([current_rows, current_heights])

        # Balance adjacent pages when the later page is visibly sparse.
        if len(pages) > 1:
            previous, final = pages[-2], pages[-1]
            while len(previous[0]) - len(final[0]) > 1:
                moved_height = previous[1][-1]
                if moved_height + sum(final[1]) > available_height:
                    break
                final[0].insert(0, previous[0].pop())
                final[1].insert(0, previous[1].pop())
        return [(page_rows, page_heights) for page_rows, page_heights in pages]

    @staticmethod
    def _column_weight(column, index):
        label = f"{column.key} {getattr(column, 'title', '')}".lower()
        if any(term in label for term in ("insight", "evidence", "basis", "drivers", "equation")):
            return 4.0
        if index == 0:
            return 1.3
        if column.inferred_type in {"currency", "percent", "number"}:
            return 1.0
        return 1.6

    @staticmethod
    def _sections(sections):
        for section in sections:
            yield section
            yield from FixedDeckPlanner._sections(section.children)

    @staticmethod
    def _paginate_paragraphs(paragraphs, *, available_height=460):
        """Pack narrative items by estimated rendered height, then balance the final spread."""
        if not paragraphs:
            return [[]]

        def value(item, key, default=None):
            return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)

        def item_height(item):
            kind = value(item, "kind", "body")
            text = value(item, "text", "") or ""
            is_lead = kind == "lead"
            font_size = 25 if is_lead else 23
            chars_per_line = 78 if is_lead else 90
            prefix_length = 2 if kind in {"bullet", "body"} else 0
            lines = max(1, math.ceil((len(text) + prefix_length) / chars_per_line))
            return math.ceil(lines * font_size * 1.28 + 8) + 28

        heights = [item_height(item) for item in paragraphs]
        pages: list[list[Any]] = []
        current: list[Any] = []
        used = 0
        for item, height in zip(paragraphs, heights):
            if current and used + height > available_height:
                pages.append(current)
                current, used = [], 0
            current.append(item)
            used += height
        if current:
            pages.append(current)

        # Repartition the last two pages by measured height. This avoids a sparse
        # one-item continuation when a more even split (or one page) will fit.
        if len(pages) > 1:
            combined = pages[-2] + pages[-1]
            combined_heights = [item_height(item) for item in combined]
            if sum(combined_heights) <= available_height:
                pages[-2:] = [combined]
            else:
                candidates = []
                for split in range(1, len(combined)):
                    left_height = sum(combined_heights[:split])
                    right_height = sum(combined_heights[split:])
                    if left_height <= available_height and right_height <= available_height:
                        candidates.append((abs(left_height - right_height), split))
                if candidates:
                    _, split = min(candidates)
                    pages[-2:] = [combined[:split], combined[split:]]
        return pages

    @staticmethod
    def _notes(citation_ids, model):
        lines = []
        for citation_id in dict.fromkeys(citation_ids):
            citation = model.citations.get(citation_id)
            if citation:
                lines.append(f"[{citation.local_id}] {citation.url}")
        return "\n".join(lines)


class ArtifactToolRenderer:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self.runtime_root = Path("/home/skr/.cache/codex-runtimes/codex-primary-runtime/dependencies")
        self.skill_dir = Path("/home/skr/.codex/plugins/cache/openai-primary-runtime/presentations/26.909.12148/skills/presentations")

    def render(self, specification: dict[str, Any], *, name: str = "financial-overview-phase2.pptx") -> Phase2Result:
        build_dir = self.workspace / "build" / "phase2"
        output_dir = self.workspace / "output"
        build_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        node_modules = build_dir / "node_modules"
        if not node_modules.exists():
            node_modules.symlink_to(self.runtime_root / "node" / "node_modules", target_is_directory=True)
        spec_path = build_dir / "deck-specification.json"
        spec_path.write_text(json.dumps(specification, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        renderer_source = self.workspace / "renderer" / "render.mjs"
        renderer_copy = build_dir / "render.mjs"
        shutil.copy2(renderer_source, renderer_copy)
        final_path = output_dir / name
        if final_path.exists():
            final_path.unlink()
        env = os.environ.copy()
        env.update({
            "SKILL_DIR": str(self.skill_dir),
            "TMP_DIR": str(build_dir),
            "WORKSPACE_DIR": str(self.workspace),
            "DECK_SPEC": str(spec_path),
            "FINAL_PPTX": str(final_path),
            "RUNTIME_PYTHON": str(self.runtime_root / "python" / "bin" / "python3"),
            "RUNTIME_NODE_MODULES": str(self.runtime_root / "node" / "node_modules"),
            "RUNTIME_BIN_DIR": str(self.runtime_root / "bin" / "override"),
        })
        completed = subprocess.run(
            [str(self.runtime_root / "node" / "bin" / "node"), str(renderer_copy)],
            cwd=build_dir, env=env, text=True, capture_output=True,
        )
        (build_dir / "renderer.stdout.log").write_text(completed.stdout, encoding="utf-8")
        (build_dir / "renderer.stderr.log").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode:
            raise RuntimeError(f"Renderer failed ({completed.returncode}): {completed.stderr[-2000:]}")
        if not final_path.exists():
            raise RuntimeError("Renderer completed without producing the final PPTX")
        return Phase2Result(final_path, build_dir, spec_path, len(specification["slides"]))
