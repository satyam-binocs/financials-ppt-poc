from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import composition, layout
from .core import PresentationModel, to_dict


@dataclass(slots=True)
class Phase2Result:
    pptx_path: Path
    build_dir: Path
    specification_path: Path
    slide_count: int


# Report headings arrive in Title Case ("Investment Thesis And Overview"), which
# reads as a label rather than a statement. Only the function words Title Case
# capitalises are lowered, and never the first one, so proper nouns and acronyms
# are left exactly as the source wrote them.
_FUNCTION_WORDS = frozenset({
    "a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "into",
    "nor", "of", "on", "or", "over", "per", "the", "to", "under", "versus",
    "vs", "with", "within", "without",
})


_CITATION_MARKER = re.compile(r"\[\d+\]")


def source_label(url: str) -> str:
    """A readable source string for the appendix, derived from its URL.

    The design spec and its reference deck put named sources on the References
    slide — `Nielsen, Refrigerated Prepared Foods Scan Data, 2016` — and the
    auditor fails a raw URL anywhere on a slide face. Report JSON only gives us
    URLs, so the host and the last meaningful path segment stand in for a name;
    the full URL stays in the speaker notes.
    """
    cleaned = re.sub(r"^https?://", "", (url or "").strip())
    # Tracking parameters and fragments are not part of a source's identity.
    cleaned = cleaned.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    if not cleaned:
        return "Source unavailable"
    host, _, path = cleaned.partition("/")
    host = host.removeprefix("www.")
    if not host:
        return "Source unavailable"

    noise = {"index", "default", "home", "en", "us", "resources", "news", "pdf"}
    candidates = [
        re.sub(r"\.(html?|php|aspx?|pdf)$", "", segment)
        for segment in path.split("/")
        if segment
    ]
    # The last segment is often an id; prefer the last one that reads as words.
    for segment in reversed(candidates):
        words = re.sub(r"[-_+]+", " ", segment).strip()
        if len(words) < 3 or words.lower() in noise:
            continue
        if not re.search(r"[A-Za-z]{3}", words):
            continue
        return f"{host} — {words[:1].upper()}{words[1:]}"
    return host


def collapse_indices(numbers: list[int]) -> str:
    """`[60, 61, 62, 64]` reads as `60-62, 64`.

    Runs of three or more collapse to a range; two consecutive stay listed,
    which is the collapsing rule the citation spec defines.
    """
    ordered = sorted(set(numbers))
    if not ordered:
        return ""
    groups: list[list[int]] = [[ordered[0]]]
    for value in ordered[1:]:
        if value == groups[-1][-1] + 1:
            groups[-1].append(value)
        else:
            groups.append([value])
    parts = []
    for group in groups:
        parts.append(f"{group[0]}-{group[-1]}" if len(group) >= 3 else ", ".join(str(v) for v in group))
    return ", ".join(parts)


def sentence_case(title: str | None) -> str | None:
    """Lower the function words in a Title Case heading, leaving names alone."""
    if not title:
        return title
    words = title.split(" ")
    for index, word in enumerate(words):
        if index == 0 or not word:
            continue
        # Only touch Capitalised-then-lowercase words; ALLCAPS is an acronym.
        if word[:1].isupper() and word[1:].islower() and word.lower() in _FUNCTION_WORDS:
            words[index] = word.lower()
    return " ".join(words)


class _ProseRun:
    """A run of prose gathered from consecutive sections, paginated as one unit.

    The first contributing section names the slide; later ones are introduced by
    an inline sub-header so the structure the report intended stays visible.
    """

    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []
        self.anchor_id: str | None = None
        self.title: str | None = None
        self.citation_ids: list[str] = []

    def add(self, source_id: str, title: str, items: list[dict[str, Any]], citation_ids: list[str]) -> None:
        if not items:
            return
        if self.anchor_id is None:
            self.anchor_id, self.title = source_id, title
        elif title:
            self.items.append({"text": title, "kind": "header"})
        self.items.extend(items)
        self.citation_ids.extend(citation_ids)

    def fits_as_table_intro(self) -> bool:
        return bool(self.items) and layout.prose_block_height(self.items) <= layout.TABLE_PROSE_MAX_HEIGHT

    def take_as_chart_intro(self, chart_kind: str) -> "_ProseRun | None":
        """Hand the run over as a strip above a chart, or decline and keep it.

        Every chart kind is eligible: scenario callouts and bridge labels now
        derive their plot box from the chart's actual position, so a shortened
        chart no longer strands its overlays.
        """
        if not self.items:
            return None
        if layout.prose_block_height(self.items) > layout.CHART_PROSE_MAX_HEIGHT:
            return None
        taken = _ProseRun()
        taken.items, taken.anchor_id, taken.title, taken.citation_ids = (
            self.items, self.anchor_id, self.title, self.citation_ids,
        )
        self.reset()
        return taken

    def reset(self) -> None:
        self.__init__()

    def flush(self, planner: "FixedDeckPlanner", model: PresentationModel) -> list[dict[str, Any]]:
        if not self.items:
            return []
        slides = [
            {
                "id": f"{self.anchor_id}:summary:{page}", "kind": "summary",
                "title": self.title if page == 1 else f"{self.title} continued",
                "paragraphs": chunk,
                "notes": planner._notes(self.citation_ids, model),
            }
            for page, chunk in enumerate(planner._paginate_paragraphs(self.items), 1)
        ]
        self.__init__()
        return slides


class FixedDeckPlanner:
    """Produce a conservative Phase 2 deck without LLM decisions."""

    def plan(self, model: PresentationModel, *, compose: bool = True) -> dict[str, Any]:
        """Plan a deck. `compose` folds adjacent exhibits onto shared slides.

        The LLM planner asks for an uncomposed baseline: it regroups the prose
        first and composes afterwards, so folding here would hide that prose
        from it inside a stack.
        """
        slides: list[dict[str, Any]] = []
        root = model.sections[0] if model.sections else None
        slides.append({
            "id": "cover",
            "kind": "cover",
            "title": sentence_case("Concise Cdd Report") or "Report",
            "subtitle": "American Casino",
            "notes": self._notes([], model),
        })
        # Reports nest their own way: a single topic often arrives as a parent
        # headline plus several one-paragraph children, and giving each node its
        # own slide is what leaves the deck sparse. Prose from consecutive
        # sections is therefore accumulated into one run and paginated together,
        # with each following section announced by an inline sub-header. A table,
        # chart or recommendation flushes the run, so document order survives and
        # separate topics never merge.
        for top in model.sections:
            start = len(slides)
            run = _ProseRun()
            for section in self._sections([top]):
                if section is root:
                    continue
                title = sentence_case(section.heading or section.name) or "Analysis"
                narrative = next((block for block in section.blocks if block.kind == "narrative" and block.paragraphs), None)
                if section.summary_headline or narrative:
                    items = []
                    if section.summary_headline:
                        items.append({"text": section.summary_headline, "kind": "lead"})
                    if narrative:
                        items.extend({"text": p.text, "kind": p.kind} for p in narrative.paragraphs)
                    run.add(section.id, title, items, narrative.citation_ids if narrative else [])

                recommendations = [block for block in section.blocks if block.kind == "recommendation"]
                if recommendations:
                    slides.extend(run.flush(self, model))
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
                        intro = run.take_as_chart_intro(block.chart.kind)
                        if intro is None:
                            slides.extend(run.flush(self, model))
                        slide = {
                            "id": block.id, "kind": "chart", "title": sentence_case(block.chart.title) or title,
                            "section": title, "chart": to_dict(block.chart),
                            "notes": self._notes(
                                (intro.citation_ids if intro else []) + list(block.citation_ids), model
                            ),
                        }
                        if intro is not None:
                            slide["paragraphs"] = intro.items
                            # Substantial commentary reads far better in a column
                            # beside the chart (~63 chars a line) than stacked
                            # above it at full width (~182), and the chart keeps
                            # the whole band height instead of the remainder.
                            geometry = layout.chart_text_geometry()
                            chart_box = {
                                "left": geometry["chart_left"],
                                "width": geometry["chart_width"],
                            }
                            overlays_fit = layout.chart_overlays_fit(slide["chart"], chart_box)
                            side_by_side = overlays_fit and layout.fits_chart_text_column(intro.items)
                            if side_by_side:
                                slide["kind"] = "chart_text"
                                slide.setdefault("composition", {}).setdefault("reasons", []).append(
                                    "commentary earns its own column beside the chart"
                                )
                            else:
                                prose_height = layout.prose_block_height(intro.items)
                                slide["chart_top"] = layout.CONTENT_TOP + prose_height + layout.TABLE_PROSE_GAP
                                reason = (
                                    "overlay labels would not fit a narrower plot"
                                    if not overlays_fit
                                    else "commentary is too short to carry a column"
                                )
                                slide.setdefault("composition", {}).setdefault("rejected", []).append(
                                    {"layout": "L04_SPLIT_RIGHT_DOMINANT", "reason": reason}
                                )
                        slides.append(slide)
                    elif block.kind == "table":
                        plain = self._table_slides(title, block, model)
                        attached = None
                        candidate = None
                        if run.fits_as_table_intro():
                            candidate = self._table_slides(
                                run.title or title, block, model,
                                prose=run.items, prose_citations=run.citation_ids,
                            )
                            # Never buy an intro with an extra continuation page.
                            if len(candidate) <= len(plain):
                                attached = candidate
                        if attached is not None:
                            run.reset()
                            attached[0].setdefault("composition", {}).setdefault("reasons", []).append(
                                "intro prose folded onto the table slide at no extra page"
                            )
                            slides.extend(attached)
                        else:
                            if run.items and len(candidate or []) > len(plain):
                                plain[0].setdefault("composition", {}).setdefault("rejected", []).append(
                                    {"layout": "L14_TABLE_INSIGHT", "reason": "intro_would_add_a_page"}
                                )
                            slides.extend(run.flush(self, model))
                            slides.extend(plain)
                    elif block.kind == "cards":
                        slides.extend(run.flush(self, model))
                        slides.extend(self._card_slides(title, block, model))
                    elif block.kind == "chart_grid":
                        intro = run.take_as_chart_intro("chart_grid")
                        if intro is None:
                            slides.extend(run.flush(self, model))
                        slides.append(self._chart_grid_slide(title, block, model, intro))
                    elif block.kind == "evidence":
                        items = [{"text": p.text, "kind": p.kind} for p in block.paragraphs if p.kind != "heading"]
                        run.add(block.id, block.title or title, items, block.citation_ids)
            slides.extend(run.flush(self, model))
            # Exhibits may only share a slide with their own top-level section,
            # because the composite keeps the first one's title.
            for slide in slides[start:]:
                slide.setdefault("section_group", top.id)
        slides.extend(self._reference_slides(model, slides))
        # One exhibit per slide is the planner's unit of work, not the deck's
        # unit of space. Adjacent exhibits are now folded onto shared slides for
        # as long as the combination measurably fits the content band.
        if compose:
            slides = composition.compose(slides)
        return {
            "schema_version": "1.0",
            "title": slides[0]["title"],
            # Colour roles follow DESIGN STYLE 1.md §4: deep navy primary,
            # corporate blue secondary, slate grey for supporting text and
            # borders, and exactly one restrained accent. Hierarchy is carried by
            # typography and alignment, not by colour or decoration.
            "theme": {
                "background": "#FFFFFF", "surface": "#FFFFFF", "band": "#F4F6F9",
                "ink": "#1B2A41", "muted": "#64748B",
                "primary": "#1F3864", "secondary": "#2E6DA4",
                "accent": "#B7791F",
                "positive": "#1F7A54", "negative": "#B3261E",
                "rule": "#D7DEE7", "rule_strong": "#1F3864",
                "chart_colors": ["#1F3864", "#2E6DA4", "#6E9BC5", "#8A99AC", "#B7791F"],
            },
            "layout": layout.to_spec(),
            # Record what each slide's composition is and why, so a layout choice
            # can be explained and audited without re-deriving it.
            "slides": composition.annotate(slides),
            "composition_summary": composition.deck_summary(slides),
        }

    def _reference_slides(self, model, slides):
        """Appendix slides carrying the sources the deck actually cites.

        Slides keep their `[n]` markers; the readable source strings live here,
        which is the one place the design spec allows them. Only numbers that
        appear on a slide are listed — a report declares far more citations than
        any one deck ends up referencing — and the full URL stays in the speaker
        notes rather than on the slide face.
        """
        cited = {
            int(marker[1:-1])
            for text in self._slide_texts(slides)
            for marker in _CITATION_MARKER.findall(text)
        }
        by_index = {
            citation.index: citation
            for citation in model.citations.values()
            if citation.index in cited
        }
        if not by_index:
            return []
        # One document often backs many claims and arrives as many URLs that
        # differ only by page or fragment, so entries are grouped by source and
        # carry every number that points at it.
        grouped: dict[str, list[int]] = {}
        for index in sorted(by_index):
            grouped.setdefault(source_label(by_index[index].url), []).append(index)
        entries = [
            {"index": min(numbers), "label": collapse_indices(numbers), "text": label}
            for label, numbers in sorted(grouped.items(), key=lambda pair: min(pair[1]))
        ]
        # An appendix line is drawn exactly one line tall, so anything that
        # would wrap is clipped. Trim to what the column holds instead.
        columns = 2 if len(entries) > layout.REFERENCE_TWO_COLUMN_THRESHOLD else 1
        budget = layout.reference_entry_chars(columns)
        for entry in entries:
            room = budget - len(f"[{entry['label']}]  ")
            if room > 1 and len(entry["text"]) > room:
                entry["text"] = entry["text"][:room - 1].rstrip() + "…"
        per_slide = layout.reference_entries_per_slide()
        pages = [entries[start:start + per_slide] for start in range(0, len(entries), per_slide)]
        return [
            {
                "id": f"references:{page}", "kind": "references",
                "title": "References" if page == 1 else "References continued",
                "entries": chunk,
                "notes": "\n".join(f"[{item['label']}] {by_index[item['index']].url}" for item in chunk),
                "composition": {
                    "reasons": [
                        f"{len(entries)} of {len(model.citations)} declared sources are cited on a slide",
                        "readable source strings belong in the appendix; the full URL stays in the notes",
                    ],
                    "rejected": [],
                },
            }
            for page, chunk in enumerate(pages, 1)
        ]

    @staticmethod
    def _slide_texts(slides):
        for slide in slides:
            yield slide.get("title") or ""
            # A composite carries its content one level down, in blocks.
            for block in slide.get("blocks") or []:
                for paragraph in block.get("paragraphs") or []:
                    yield paragraph.get("text") or ""
                for row in block.get("rows") or []:
                    for cell in row.values():
                        if isinstance(cell, dict):
                            yield cell.get("plain_text") or ""
            for paragraph in slide.get("paragraphs") or []:
                yield paragraph.get("text") or ""
            for item in slide.get("items") or []:
                yield f"{item.get('title', '')} {item.get('text', '')}"
            for card in slide.get("cards") or []:
                yield card.get("title") or ""
                for paragraph in card.get("paragraphs") or []:
                    yield paragraph.get("text") or ""
            for row in slide.get("rows") or []:
                for cell in row.values():
                    if isinstance(cell, dict):
                        yield cell.get("plain_text") or ""

    def _card_slides(self, section_title, block, model):
        """Card sets get a grid chosen by measurement, not by card count alone."""
        title = sentence_case(block.title) or section_title
        payload = [
            {
                "id": card.id,
                "title": card.title,
                "badges": list(card.badges),
                "paragraphs": [{"text": p.text, "kind": p.kind} for p in card.paragraphs],
            }
            for card in block.cards
        ]
        pages = composition.plan_card_pages(payload, layout.CONTENT_TOP)
        result = []
        for page, (cards, layout_id, columns, rejected, reasons) in enumerate(pages, 1):
            payload_page = cards
            boxes, used = layout.card_grid_boxes(payload_page, columns, layout.CONTENT_TOP)
            result.append({
                "id": f"{block.id}:cards:{page}", "kind": "cards",
                "title": title if page == 1 else f"{title} continued",
                "layout_id": layout_id,
                "grid_columns": columns,
                "cards": payload_page,
                "card_boxes": boxes,
                "grid_used_height": used,
                "notes": self._notes(block.citation_ids, model),
                "composition": {"reasons": reasons, "rejected": rejected},
            })
        return result

    def _chart_grid_slide(self, section_title, block, model, intro=None):
        """A chart grid states its own column count, so honour it where it fits."""
        charts = block.charts
        prose_height = layout.prose_block_height(intro.items) if intro else 0
        grid_top = layout.CONTENT_TOP + (prose_height + layout.TABLE_PROSE_GAP if prose_height else 0)
        declared = ((block.extensions.get("output_config") or {}).get("charts_per_row"))
        columns = int(declared) if isinstance(declared, (int, float)) and declared else min(2, len(charts))
        columns = max(1, min(columns, len(charts)))
        reasons = [f"{len(charts)} charts in the grid"]
        if declared:
            reasons.append(f"source declares charts_per_row={int(declared)}; honoured")
        minimum = layout.MIN_COMPONENT_DIMENSIONS["chart"]
        rejected = []
        while columns > 1:
            width = int((layout.CONTENT_WIDTH - (columns - 1) * layout.CARD_GAP_X) / columns)
            if width >= minimum["min_width"]:
                break
            rejected.append({"layout": f"{columns}_per_row", "reason": "minimum_width_violation"})
            columns -= 1
        boxes, used = layout.chart_grid_boxes(len(charts), columns, grid_top)
        rows = -(-len(charts) // columns)
        if boxes and boxes[0]["height"] < minimum["min_height"]:
            reasons.append("chart height is below the comfortable minimum but is the best available")
        layout_id = "L02_SPLIT_EQUAL" if (columns == 2 and rows == 1) else (
            "L01_SINGLE" if len(charts) == 1 else "L07_GRID_2X2"
        )
        reasons.append(f"selected {layout_id}: {columns} per row, {rows} row(s)")
        return {
            "id": f"{block.id}:chart_grid", "kind": "chart_grid",
            "title": sentence_case(block.title) or section_title,
            "layout_id": layout_id,
            "grid_columns": columns,
            "charts": [to_dict(chart) for chart in charts],
            "chart_boxes": boxes,
            "grid_used_height": used,
            "notes": self._notes((intro.citation_ids if intro else []) + list(block.citation_ids), model),
            "composition": {"reasons": reasons, "rejected": rejected},
            **({"paragraphs": intro.items} if intro else {}),
        }

    def _table_slides(self, section_title, block, model, *, prose=None, prose_citations=()):
        keys = [column.key for column in block.columns]
        # Keep the first identifying column on every horizontal continuation.
        limit = layout.TABLE_MAX_COLUMNS
        groups = (
            [keys] if len(keys) <= limit
            else [[keys[0], *keys[i:i + limit - 1]] for i in range(1, len(keys), limit - 1)]
        )
        prose_height = layout.prose_block_height(prose or [])
        table_top = layout.TABLE_TOP if not prose_height else layout.CONTENT_TOP + prose_height + layout.TABLE_PROSE_GAP
        result = []
        page = 0
        for group in groups:
            selected_model_columns = [column for column in block.columns if column.key in group]
            weights = layout.column_weights(selected_model_columns, block.rows)
            header_height = layout.table_header_height(selected_model_columns, weights)
            # Only the opening page carries the intro; continuations get the full band.
            first_band = layout.CONTENT_BOTTOM - table_top - header_height
            pages = self._paginate_rows(
                block.rows, selected_model_columns, weights, header_height,
                first_page_height=first_band if prose_height else None,
            )
            for page_rows, row_heights in pages:
                page += 1
                selected_columns = [
                    {
                        **to_dict(column), "layout_weight": weight,
                        # Numeric columns read right-aligned so digits and
                        # decimals line up; everything else keeps its own
                        # alignment.
                        "align": "right" if column.inferred_type in {"currency", "percent", "number"} else column.alignment,
                    }
                    for column, weight in zip(selected_model_columns, weights)
                ]
                rows = [
                    {key: to_dict(row[key]) for key in group}
                    for row in page_rows
                ]
                slide = {
                    "id": f"{block.id}:table:{page}", "kind": "table",
                    "title": sentence_case(block.title) or section_title if page == 1 else f"{sentence_case(block.title) or section_title} continued",
                    "columns": selected_columns, "rows": rows, "row_heights": row_heights,
                    "header_height": header_height,
                    "notes": self._notes(list(prose_citations) + list(block.citation_ids), model),
                }
                if prose and page == 1:
                    slide["paragraphs"] = prose
                    slide["table_top"] = table_top
                result.append(slide)
        return result

    @staticmethod
    def _paginate_rows(rows, columns, weights=None, header_height=None, *, available_height=None, first_page_height=None):
        if not rows:
            return [([], [])]
        weights = weights or layout.column_weights(columns, rows)
        header_height = header_height or layout.table_header_height(columns, weights)
        if available_height is None:
            available_height = layout.TABLE_BAND_HEIGHT - header_height
        heights = [layout.table_row_height(row, columns, weights) for row in rows]
        pages = layout.balanced_pages(heights, available_height, first_capacity=first_page_height)
        return [
            ([rows[index] for index in page], [heights[index] for index in page])
            for page in pages
        ]

    @staticmethod
    def _sections(sections):
        for section in sections:
            yield section
            yield from FixedDeckPlanner._sections(section.children)

    @staticmethod
    def _paginate_paragraphs(paragraphs, *, available_height=None, density="comfortable"):
        """Pack narrative items into the fewest slides, then even out the fill."""
        if not paragraphs:
            return [[]]
        available_height = available_height or layout.CAPACITY[density]

        def value(item, key, default=None):
            return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)

        heights = [
            layout.paragraph_height(value(item, "text", "") or "", value(item, "kind", "body"), density)
            for item in paragraphs
        ]
        pages = layout.balanced_pages(heights, available_height, gap=layout.paragraph_gap(density))
        grouped = [[paragraphs[index] for index in page] for page in pages]

        # A sub-header stranded at the foot of a slide reads as a mistake; push it
        # onto the slide that carries the content it introduces.
        for position in range(len(grouped) - 1):
            page = grouped[position]
            while len(page) > 1 and value(page[-1], "kind") == "header":
                grouped[position + 1].insert(0, page.pop())
        return [page for page in grouped if page]

    @staticmethod
    def _notes(citation_ids, model):
        lines = []
        for citation_id in dict.fromkeys(citation_ids):
            citation = model.citations.get(citation_id)
            if citation:
                lines.append(f"[{citation.local_id}] {citation.url}")
        return "\n".join(lines)


class ArtifactToolRenderer:
    PRESENTATIONS_CACHE = Path("/home/skr/.codex/plugins/cache/openai-primary-runtime/presentations")

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self.runtime_root = Path("/home/skr/.cache/codex-runtimes/codex-primary-runtime/dependencies")
        self.skill_dir = self._resolve_skill_dir()

    @classmethod
    def _resolve_skill_dir(cls) -> Path:
        """Locate the presentations skill, whose directory carries its version.

        Pinning the version here breaks the renderer every time the plugin
        updates, so pick the newest installed copy that still has the tools we
        call into.
        """
        candidates = sorted(
            (path for path in cls.PRESENTATIONS_CACHE.glob("*/skills/presentations")
             if (path / "container_tools" / "artifact_tool_utils.mjs").is_file()),
            key=lambda path: path.parents[1].name,
        )
        if not candidates:
            raise RuntimeError(f"No presentations skill found under {cls.PRESENTATIONS_CACHE}")
        return candidates[-1]

    def render(
        self,
        specification: dict[str, Any],
        *,
        name: str = "financial-overview-phase2.pptx",
        output_dir: Path | None = None,
    ) -> Phase2Result:
        build_dir = self.workspace / "build" / "phase2"
        output_dir = (output_dir or self.workspace / "output").resolve()
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
        receipt_path = self.workspace / ".codex-finalizer" / f"{final_path.name}.validation.json"
        if receipt_path.exists():
            receipt_path.unlink()
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
