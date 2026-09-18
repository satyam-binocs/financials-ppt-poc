"""What a slide's composition is, why it was chosen, and whether it is sound.

The planner already made these decisions — it just discarded the reasoning. This
module gives the decisions names from a layout registry, measures the two density
axes separately (how much content, and how much of the slide it occupies), checks
the constraints that can be checked before rendering, and packages the result so
it travels with the slide in the deck specification.

Thresholds here were measured from the shipped corpus rather than imported: over
77 planned slides the character load runs p25=485, median=928, p75=1216,
p90=1675.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from . import layout


CITATION_MARKER = re.compile(r"\[\d+\]")

# Citations are traceability metadata, not content, so they are stripped before
# any content is counted.
CONTENT_LOAD_BANDS = (
    ("sparse", 485),
    ("balanced", 1250),
    ("dense", 1700),
    ("overloaded", None),
)

# A slide is only called underfilled when both axes agree: mostly empty *and*
# carrying little content. Either one alone is a false positive — a three-row
# table is short without being thin.
UNDERFILL_OCCUPANCY = 0.50
UNDERFILL_LOAD = 485

LAYOUT_REGISTRY: dict[str, dict[str, Any]] = {
    "L00_COVER": {
        "family": "cover",
        "min_components": 1, "max_components": 1,
        "supports": ["text"],
        "paginates": False,
        "fallbacks": [],
    },
    "L01_SINGLE": {
        "family": "single",
        "min_components": 1, "max_components": 1,
        "supports": ["chart", "table", "text", "chart_grid"],
        "paginates": True,
        "fallbacks": ["L20_PAGINATED"],
    },
    "L10_VERTICAL_STACK": {
        "family": "stack",
        "min_components": 1, "max_components": 24,
        "supports": ["text", "cards"],
        "paginates": True,
        "fallbacks": ["L20_PAGINATED"],
    },
    "L13_CHART_COMMENTARY": {
        "family": "stacked_pair",
        "min_components": 2, "max_components": 2,
        "supports": ["chart", "text"],
        "paginates": False,
        "fallbacks": ["L01_SINGLE", "L10_VERTICAL_STACK"],
    },
    "L14_TABLE_INSIGHT": {
        "family": "stacked_pair",
        "min_components": 2, "max_components": 2,
        "supports": ["table", "text"],
        "paginates": True,
        "fallbacks": ["L01_SINGLE", "L20_PAGINATED"],
    },
    "L04_SPLIT_RIGHT_DOMINANT": {
        "family": "asymmetric_split",
        "min_components": 2, "max_components": 2,
        "ratio": [0.35, 0.65],
        "supports": ["chart", "text"],
        "paginates": False,
        "fallbacks": ["L13_CHART_COMMENTARY", "L01_SINGLE"],
    },
    "L05_THREE_COLUMN": {
        "family": "columns",
        "columns": 3,
        "min_components": 3, "max_components": 3,
        "supports": ["cards"],
        "paginates": True,
        "fallbacks": ["L07_GRID_2X2", "L10_VERTICAL_STACK", "L20_PAGINATED"],
    },
    "L06_FOUR_COLUMN": {
        "family": "columns",
        "columns": 4,
        "min_components": 4, "max_components": 4,
        "supports": ["cards"],
        "paginates": True,
        "fallbacks": ["L07_GRID_2X2", "L10_VERTICAL_STACK", "L20_PAGINATED"],
    },
    "L07_GRID_2X2": {
        "family": "grid",
        "rows": 2, "columns": 2,
        "min_components": 3, "max_components": 4,
        "supports": ["cards", "chart_grid"],
        "paginates": True,
        "fallbacks": ["L10_VERTICAL_STACK", "L20_PAGINATED"],
    },
    "L08_GRID_2X3": {
        "family": "grid",
        "rows": 2, "columns": 3,
        "min_components": 5, "max_components": 6,
        "supports": ["cards"],
        "paginates": True,
        "fallbacks": ["L09_GRID_3X2", "L10_VERTICAL_STACK", "L20_PAGINATED"],
    },
    "L09_GRID_3X2": {
        "family": "grid",
        "rows": 3, "columns": 2,
        "min_components": 5, "max_components": 6,
        "supports": ["cards"],
        "paginates": True,
        "fallbacks": ["L10_VERTICAL_STACK", "L20_PAGINATED"],
    },
    "L02_SPLIT_EQUAL": {
        "family": "split",
        "columns": 2,
        "min_components": 2, "max_components": 2,
        "ratio": [0.5, 0.5],
        "supports": ["chart_grid", "cards"],
        "paginates": False,
        "fallbacks": ["L10_VERTICAL_STACK"],
    },
    "L21_REFERENCES": {
        "family": "appendix",
        "min_components": 1, "max_components": 1,
        "supports": ["text"],
        "paginates": True,
        "fallbacks": [],
    },
    "L30_COMPOSITE": {
        "family": "composite",
        "min_components": 2, "max_components": 24,
        "supports": ["chart", "table", "text"],
        "paginates": False,
        "fallbacks": ["L14_TABLE_INSIGHT", "L13_CHART_COMMENTARY", "L01_SINGLE"],
    },
    "L20_PAGINATED": {
        "family": "paginated",
        "min_components": 1, "max_components": 24,
        "supports": ["text", "table", "cards", "chart_grid"],
        "paginates": True,
        "fallbacks": [],
    },
}


@dataclass(slots=True)
class DensityMetrics:
    visible_character_count: int = 0
    component_count: int = 0
    text_component_count: int = 0
    table_row_count: int = 0
    table_column_count: int = 0
    chart_count: int = 0
    card_count: int = 0
    column_count: int = 0
    citation_count: int = 0
    longest_text_length: int = 0
    average_text_length: int = 0
    content_load_band: str = "sparse"
    vertical_occupancy: float = 0.0
    vertical_emptiness: float = 1.0


@dataclass(slots=True)
class CompositionRecord:
    layout_id: str
    family: str
    reasons: list[str] = field(default_factory=list)
    rejected: list[dict[str, str]] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    balance_flags: list[str] = field(default_factory=list)
    density: DensityMetrics = field(default_factory=DensityMetrics)

    def to_dict(self) -> dict[str, Any]:
        return {
            "layout_id": self.layout_id,
            "family": self.family,
            "reasons": list(self.reasons),
            "rejected": list(self.rejected),
            "violations": list(self.violations),
            "balance_flags": list(self.balance_flags),
            "density": asdict(self.density),
        }


def classify(slide: dict[str, Any]) -> str:
    """The registry id for a slide the planner has already built."""
    kind = slide.get("kind")
    has_prose = bool(slide.get("paragraphs"))
    if kind == "cover":
        return "L00_COVER"
    if kind == "references":
        return "L21_REFERENCES"
    if kind == "stack":
        # One row of two is the asymmetric split the registry already names;
        # only a genuine multi-row stack is a composite.
        if slide.get("stack_row_count") == 1 and len(slide.get("blocks") or []) == 2:
            return "L04_SPLIT_RIGHT_DOMINANT"
        return STACK_LAYOUT_ID
    if kind == "chart_text":
        return "L04_SPLIT_RIGHT_DOMINANT"
    if kind == "table":
        return "L14_TABLE_INSIGHT" if has_prose else "L01_SINGLE"
    if kind == "chart":
        return "L13_CHART_COMMENTARY" if has_prose else "L01_SINGLE"
    if kind in {"cards", "chart_grid"}:
        return slide.get("layout_id") or "L10_VERTICAL_STACK"
    return "L10_VERTICAL_STACK"


def _plain(text: str) -> str:
    return CITATION_MARKER.sub("", text or "")


def measure(slide: dict[str, Any]) -> DensityMetrics:
    if slide.get("kind") == "stack":
        return _measure_stack(slide)
    metrics = DensityMetrics()
    lengths: list[int] = []
    raw_texts: list[str] = []

    metrics.visible_character_count += len(_plain(slide.get("title") or ""))

    paragraphs = slide.get("paragraphs") or []
    metrics.text_component_count = len(paragraphs)
    for paragraph in paragraphs:
        text = paragraph.get("text") or ""
        raw_texts.append(text)
        lengths.append(len(_plain(text)))

    for item in slide.get("items") or []:
        text = f"{item.get('title', '')} {item.get('text', '')}"
        raw_texts.append(text)
        lengths.append(len(_plain(text)))

    for card in slide.get("cards") or []:
        metrics.card_count += 1
        raw_texts.append(card.get("title") or "")
        for paragraph in card.get("paragraphs") or []:
            text = paragraph.get("text") or ""
            raw_texts.append(text)
            lengths.append(len(_plain(text)))

    columns = slide.get("columns") or []
    rows = slide.get("rows") or []
    metrics.table_column_count = len(columns)
    metrics.table_row_count = len(rows)
    for column in columns:
        raw_texts.append(column.get("title") or "")
    for row in rows:
        for cell in row.values():
            if isinstance(cell, dict):
                text = cell.get("plain_text") or ""
                raw_texts.append(text)
                lengths.append(len(_plain(text)))

    for entry in slide.get("entries") or []:
        raw_texts.append(str(entry.get("text") or ""))

    if slide.get("chart"):
        metrics.chart_count = 1
        chart = slide["chart"]
        raw_texts.extend(str(category) for category in chart.get("categories") or [])
        raw_texts.extend(str(series.get("name") or "") for series in chart.get("series") or [])
    for chart in slide.get("charts") or []:
        metrics.chart_count += 1
        raw_texts.append(chart.get("title") or "")
        raw_texts.extend(str(point.get("category") or "") for point in chart.get("points") or [])

    metrics.visible_character_count += sum(len(_plain(text)) for text in raw_texts)
    metrics.citation_count = sum(len(CITATION_MARKER.findall(text)) for text in raw_texts)
    metrics.longest_text_length = max(lengths, default=0)
    metrics.average_text_length = int(sum(lengths) / len(lengths)) if lengths else 0
    metrics.column_count = int(slide.get("grid_columns") or 0) or metrics.table_column_count
    # A chart grid is one composite exhibit, the same way a many-rowed table is
    # one component; counting each pie separately would push an intro-bearing
    # grid past its layout's component ceiling.
    visual_count = 1 if slide.get("charts") else metrics.chart_count
    metrics.component_count = (
        (1 if slide.get("entries") else 0)
        + visual_count
        + metrics.card_count
        + (1 if rows else 0)
        + (1 if paragraphs else 0)
        + (1 if slide.get("items") else 0)
    )

    for band, ceiling in CONTENT_LOAD_BANDS:
        if ceiling is None or metrics.visible_character_count <= ceiling:
            metrics.content_load_band = band
            break

    metrics.vertical_occupancy = round(_occupancy(slide), 3)
    metrics.vertical_emptiness = round(max(0.0, 1.0 - metrics.vertical_occupancy), 3)
    return metrics


def _occupancy(slide: dict[str, Any]) -> float:
    """Share of the content band the slide's content actually fills."""
    kind = slide.get("kind")
    density = slide.get("density", "comfortable")
    if kind in {"cover", "references"}:
        return 1.0
    if kind == "stack":
        band = layout.CONTENT_BOTTOM - layout.CONTENT_TOP
        return min(1.0, (slide.get("used_height") or 0) / band)
    if kind in {"summary", "findings"} and slide.get("paragraphs"):
        used = sum(
            layout.paragraph_height(p.get("text") or "", p.get("kind", "body"), density)
            for p in slide["paragraphs"]
        )
        return min(1.0, used / layout.CAPACITY[density])
    if kind == "table" and slide.get("row_heights"):
        top = slide.get("table_top", layout.TABLE_TOP)
        band = layout.CONTENT_BOTTOM - top - slide.get("header_height", layout.TABLE_HEADER_MIN)
        return min(1.0, sum(slide["row_heights"]) / band) if band > 0 else 1.0
    if kind in {"cards", "chart_grid"}:
        used = slide.get("grid_used_height")
        if used:
            return min(1.0, used / (layout.CONTENT_BOTTOM - layout.CONTENT_TOP))
        return 1.0
    # A chart fills the band it is given by construction.
    return 1.0


def balance_flags(slide: dict[str, Any], metrics: DensityMetrics) -> list[str]:
    """Deterministic version of the checks a human reviewer makes by eye."""
    flags: list[str] = []
    if (
        metrics.vertical_occupancy < UNDERFILL_OCCUPANCY
        and metrics.visible_character_count < UNDERFILL_LOAD
    ):
        flags.append("underfilled")
    # Both axes have to agree here too. A wide table legitimately carries far
    # more characters than prose, so a high load on a slide that still has room
    # is dense by design, not a defect.
    if metrics.content_load_band == "overloaded" and metrics.vertical_occupancy >= 0.97:
        flags.append("content_overloaded")
    if " continued" in (slide.get("title") or ""):
        lone_prose = metrics.component_count <= 1 and metrics.text_component_count == 1
        lone_row = metrics.component_count <= 1 and metrics.table_row_count == 1
        lone_card = metrics.card_count == 1
        if lone_prose or lone_row or lone_card:
            flags.append("orphan_continuation")
    return flags


def validate(slide: dict[str, Any], metrics: DensityMetrics) -> list[str]:
    """Pre-render invalidity checks, returning named violations.

    Only the rules that can be decided from the plan are here; overflow and
    auto-shrink are verified against the rendered layout files instead.
    """
    violations: list[str] = []
    layout_id = classify(slide)
    definition = LAYOUT_REGISTRY.get(layout_id)
    if definition is None:
        violations.append(f"unknown_layout:{layout_id}")
        return violations

    count = max(1, metrics.component_count)
    if count < definition["min_components"]:
        violations.append("component_count_below_minimum")
    if count > definition["max_components"]:
        violations.append("component_count_above_maximum")

    if slide.get("kind") == "table" and metrics.table_column_count:
        weights = [column.get("layout_weight", 1) for column in slide.get("columns") or []]
        total = sum(weights) or 1
        narrowest = min(
            (layout.CONTENT_WIDTH * weight / total for weight in weights),
            default=layout.CONTENT_WIDTH,
        )
        if narrowest < layout.TABLE_COLUMN_MIN_WIDTH - 1:
            violations.append("table_column_below_minimum_width")

    violations.extend(_validate_stack(slide))

    top = slide.get("table_top") or slide.get("chart_top") or layout.CONTENT_TOP
    if top >= layout.CONTENT_BOTTOM:
        violations.append("content_starts_below_band")

    if slide.get("kind") in {"summary", "findings"} and slide.get("paragraphs"):
        density = slide.get("density", "comfortable")
        used = sum(
            layout.paragraph_height(p.get("text") or "", p.get("kind", "body"), density)
            for p in slide["paragraphs"]
        ) - layout.paragraph_gap(density)
        if used > layout.CAPACITY[density]:
            violations.append("prose_exceeds_capacity")
        if slide["paragraphs"][-1].get("kind") == "header":
            violations.append("stranded_sub_header")

    return violations


def build(
    slide: dict[str, Any],
    *,
    reasons: list[str] | None = None,
    rejected: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Attach a composition record to a planned slide."""
    layout_id = classify(slide)
    definition = LAYOUT_REGISTRY.get(layout_id, {})
    metrics = measure(slide)
    record = CompositionRecord(
        layout_id=layout_id,
        family=str(definition.get("family", "unknown")),
        reasons=list(reasons or []),
        rejected=list(rejected or []),
        violations=validate(slide, metrics),
        balance_flags=balance_flags(slide, metrics),
        density=metrics,
    )
    return record.to_dict()


def annotate(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Record a composition for every slide that does not already carry one."""
    for slide in slides:
        existing = slide.get("composition")
        reasons = list(existing.get("reasons", [])) if isinstance(existing, dict) else []
        rejected = list(existing.get("rejected", [])) if isinstance(existing, dict) else []
        slide["composition"] = build(slide, reasons=reasons, rejected=rejected)
    return slides


def deck_summary(slides: list[dict[str, Any]]) -> dict[str, Any]:
    """Deck-level counts, so a regression shows up without opening a slide."""
    families: dict[str, int] = {}
    layouts: dict[str, int] = {}
    flags: dict[str, int] = {}
    violations: dict[str, int] = {}
    loads: list[int] = []
    for slide in slides:
        record = slide.get("composition") or {}
        layouts[record.get("layout_id", "?")] = layouts.get(record.get("layout_id", "?"), 0) + 1
        families[record.get("family", "?")] = families.get(record.get("family", "?"), 0) + 1
        for flag in record.get("balance_flags", []):
            flags[flag] = flags.get(flag, 0) + 1
        for violation in record.get("violations", []):
            violations[violation] = violations.get(violation, 0) + 1
        loads.append(int((record.get("density") or {}).get("visible_character_count", 0)))
    loads.sort()
    return {
        "slide_count": len(slides),
        "layouts": layouts,
        "families": families,
        "balance_flags": flags,
        "violations": violations,
        "content_load": {
            "median": loads[len(loads) // 2] if loads else 0,
            "max": loads[-1] if loads else 0,
        },
    }


def select_card_layout(
    cards: list[Any],
    top: int,
    density: str = "comfortable",
) -> tuple[str, int, list[dict[str, str]], list[str]]:
    """Choose a grid for a set of cards by measurement, not by count alone.

    Returns the layout id, its column count, the candidates that were rejected
    and why, and the reasons the winner was chosen. Candidates are tried in
    preference order and the first geometrically valid one wins, which is the
    fallback chain from the specification expressed directly.
    """
    count = len(cards)
    detailed = [card for card in cards if layout.card_body_chars(card) > layout.CARD_COMPACT_MAX_CHARS]
    reasons = [f"{count} card components detected"]
    reasons.append(
        f"{len(detailed)} of {count} exceed the compact body limit "
        f"({layout.CARD_COMPACT_MAX_CHARS} chars)"
    )

    preference: list[tuple[str, int]] = []
    if count == 1:
        preference = [("L01_SINGLE", 1)]
    elif count == 2:
        preference = [("L02_SPLIT_EQUAL", 2), ("L10_VERTICAL_STACK", 1)]
    elif count == 3:
        preference = ([("L05_THREE_COLUMN", 3)] if not detailed else []) + [
            ("L07_GRID_2X2", 2), ("L10_VERTICAL_STACK", 1),
        ]
    elif count == 4:
        preference = ([("L06_FOUR_COLUMN", 4)] if not detailed else []) + [
            ("L07_GRID_2X2", 2), ("L10_VERTICAL_STACK", 1),
        ]
    else:
        preference = ([("L08_GRID_2X3", 3)] if not detailed else []) + [
            ("L09_GRID_3X2", 2), ("L10_VERTICAL_STACK", 1),
        ]

    if detailed and count >= 3:
        reasons.append("detailed cards are not placed in narrow columns")

    rejected: list[dict[str, str]] = []
    for layout_id, columns in preference:
        ok, why = layout.grid_fits(cards, columns, top, density)
        if ok:
            shape = "a stack" if columns == 1 else f"{columns} columns"
            reasons.append(f"selected {layout_id}: {shape} satisfies minimum geometry")
            return layout_id, columns, rejected, reasons
        rejected.append({"layout": layout_id, "reason": why})
    # Nothing fit, so the caller must split. Report the widest shape that would
    # have worked on fewer cards; pagination happens above this function.
    reasons.append("no layout fits this many cards; the set is split across slides")
    return "L20_PAGINATED", 1, rejected, reasons


def plan_card_pages(
    cards: list[Any],
    top: int,
    density: str = "comfortable",
) -> list[tuple[list[Any], str, int, list[dict[str, str]], list[str]]]:
    """Split a card set into slides, each carrying a layout that actually fits.

    Pagination is last in the fallback order: for each slide the largest prefix
    that some layout can hold is taken, so cards are never shrunk to force a
    grid and never left overflowing their region.
    """
    total = len(cards)

    def split_evenly(page_count: int) -> list[list[Any]]:
        base, extra = divmod(total, page_count)
        groups: list[list[Any]] = []
        cursor = 0
        for index in range(page_count):
            size = base + (1 if index < extra else 0)
            groups.append(cards[cursor:cursor + size])
            cursor += size
        return [group for group in groups if group]

    # Fewest slides first, then an even split, so no slide is left holding a
    # single orphaned card while its neighbour is full.
    for page_count in range(1, total + 1):
        groups = split_evenly(page_count)
        if any(len(group) > layout.CARD_MAX_PER_SLIDE for group in groups):
            continue
        resolved = [select_card_layout(group, top, density) for group in groups]
        if all(entry[0] != "L20_PAGINATED" for entry in resolved):
            pages = [
                (group, layout_id, columns, rejected, reasons)
                for group, (layout_id, columns, rejected, reasons) in zip(groups, resolved)
            ]
            if page_count > 1:
                for page in pages:
                    page[4].append(
                        f"card set split evenly across {page_count} slides "
                        f"({', '.join(str(len(group)) for group in groups)} cards)"
                    )
            return pages

    # No even split works, so fall back to one card per slide: it is the
    # smallest indivisible unit and the alternative is losing content.
    pages = []
    for card in cards:
        _, _, rejected, reasons = select_card_layout([card], top, density)
        reasons.append("one card per slide: no multi-card split satisfied the band")
        pages.append(([card], "L01_SINGLE", 1, rejected, reasons))
    return pages


# ── Composite slides ─────────────────────────────────────────────────────────
# Everything above decides how one exhibit is laid out. This decides how many
# exhibits share a slide, and it decides it the same way: by measuring. The
# planner emits one slide per exhibit in document order; the merger then walks
# that list and folds adjacent exhibits together while they still fit the band.
#
# There is deliberately no table of which kinds may combine. A block declares
# two things — whether it can be measured in a narrow column, and whether it
# will accept leftover height — and the packer works from those alone, so a new
# content kind joins by answering the same two questions.

STACK_LAYOUT_ID = "L30_COMPOSITE"

# A table cannot go in a narrow column: its row heights were measured against
# the full content width, and its minimum viable width is most of the slide.
NARROW_BLOCK_KINDS = {"prose"}
# A chart is a viewport, so it takes whatever height is left. Prose and tables
# are exactly as tall as their content.
ELASTIC_BLOCK_KINDS = {"chart"}
# Minimum-dimension keys per block kind, for the pre-render viability check.
BLOCK_FLOORS = {"chart": "chart", "table": "table", "prose": "paragraph"}


def _stack_blocks(
    slide: dict[str, Any], label: str | None = None
) -> list[dict[str, Any]] | None:
    """The slide re-read as a list of blocks, or None if it cannot be merged.

    A continuation page is excluded: it was paginated against a whole band, so
    re-parenting it onto a shared slide would silently change what fits.
    """
    kind = slide.get("kind")
    if " continued" in (slide.get("title") or ""):
        return None
    paragraphs = slide.get("paragraphs") or []
    prose = (
        [{
            "kind": "prose", "paragraphs": paragraphs,
            "density": slide.get("density", "comfortable"),
        }]
        if paragraphs else []
    )
    blocks: list[dict[str, Any]] | None = None
    if kind in {"summary", "findings"}:
        blocks = prose or None
    elif kind == "table" and slide.get("row_heights"):
        blocks = prose + [{
            "kind": "table",
            "columns": slide["columns"], "rows": slide["rows"],
            "row_heights": slide["row_heights"],
            "header_height": slide["header_height"],
        }]
    elif kind in {"chart", "chart_text"} and slide.get("chart"):
        blocks = prose + [{"kind": "chart", "chart": slide["chart"]}]
    if not blocks:
        return None
    if label:
        blocks[0] = {**blocks[0], "label": label}
    return blocks


def _block_height(block: dict[str, Any], width: int) -> int:
    """Minimum height this block needs at the given box width.

    A label sits inside the block's box, so it is part of the block's height.
    """
    kind = block["kind"]
    if kind == "prose":
        content = layout.prose_block_height(
            block["paragraphs"], block.get("density", "comfortable"),
            width=layout.prose_text_width(width),
        )
    elif kind == "table":
        content = block["header_height"] + sum(block["row_heights"])
    else:
        content = layout.MIN_COMPONENT_DIMENSIONS["chart"]["min_height"]
    return content + (layout.STACK_LABEL_HEIGHT if block.get("label") else 0)


def _elastic_accepts(block: dict[str, Any], left: int, width: int) -> bool:
    """Whether an elastic block stays legible in a box this wide."""
    if block["kind"] == "chart":
        if width < layout.MIN_COMPONENT_DIMENSIONS["chart"]["min_width"]:
            return False
        # Overlay labels are the binding constraint on a narrowed plot, and they
        # are measured, not inferred from the chart's kind.
        return layout.chart_overlays_fit(block["chart"], {"left": left, "width": width})
    return True


def _stack_cells(
    blocks: list[dict[str, Any]], no_pair: frozenset[int] = frozenset()
) -> list[list[dict[str, Any]]]:
    """Group blocks into rows, pairing a narrow block with an elastic one.

    Pairing is not automatic: prose triples in height when its line halves, so
    a short lead beside a chart is taller than the same lead stacked above one.
    The two arrangements are measured and the shorter wins.
    """
    split = layout.chart_text_geometry()
    rows: list[list[dict[str, Any]]] = []
    index = 0
    while index < len(blocks):
        first = blocks[index]
        second = blocks[index + 1] if index + 1 < len(blocks) else None
        pair = None
        if second is not None and index not in no_pair:
            kinds = {first["kind"], second["kind"]}
            if kinds <= NARROW_BLOCK_KINDS | ELASTIC_BLOCK_KINDS and len(kinds) == 2:
                narrow, elastic = (
                    (first, second) if first["kind"] in NARROW_BLOCK_KINDS else (second, first)
                )
                narrow_height = _block_height(narrow, split["text_width"])
                elastic_height = _block_height(elastic, split["chart_width"])
                stacked = (
                    _block_height(narrow, layout.CONTENT_WIDTH)
                    + layout.STACK_ROW_GAP
                    + _block_height(elastic, layout.CONTENT_WIDTH)
                )
                row_height = max(narrow_height, elastic_height)
                viable = (
                    narrow_height <= layout.PARAGRAPH_CAPACITY
                    and _elastic_accepts(
                        elastic,
                        split["chart_left"] if narrow is first else layout.MARGIN_LEFT,
                        split["chart_width"],
                    )
                    # A one-line label does not earn a column: it would leave a
                    # hole the height of the chart beside it. Same threshold the
                    # full-band split already uses.
                    and narrow_height >= layout.CHART_TEXT_MIN_SHARE * row_height
                )
                if viable and row_height < stacked:
                    # The pair keeps document order across the row, so the
                    # commentary sits left of a chart that follows it and right
                    # of one it follows.
                    narrow_is_first = narrow is first
                    narrow_left = (
                        split["text_left"] if narrow_is_first
                        else layout.CANVAS_WIDTH - layout.MARGIN_LEFT - split["text_width"]
                    )
                    elastic_left = (
                        split["chart_left"] if narrow_is_first else layout.MARGIN_LEFT
                    )
                    narrow_cell = {
                        "block": narrow, "left": narrow_left,
                        "width": split["text_width"], "narrow": True,
                        "pair_index": index,
                    }
                    elastic_cell = {
                        "block": elastic, "left": elastic_left,
                        "width": split["chart_width"],
                    }
                    pair = (
                        [narrow_cell, elastic_cell] if narrow_is_first
                        else [elastic_cell, narrow_cell]
                    )
        if pair:
            rows.append(pair)
            index += 2
        else:
            rows.append([{
                "block": first, "left": layout.MARGIN_LEFT, "width": layout.CONTENT_WIDTH,
            }])
            index += 1
    return rows


def stack_layout(blocks: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Resolve every block's box, or None if the combination does not fit.

    Pairing is decided against a row's minimum height, but an elastic block
    then absorbs the slide's surplus and the row grows — which can leave the
    narrow column beside it looking stranded. So the layout is resolved, the
    share re-checked against the height the row actually got, and any pairing
    that no longer earns its column is dropped and the stack re-resolved.
    """
    no_pair: frozenset[int] = frozenset()
    for _ in range(len(blocks) + 1):
        resolved = _resolve_stack(blocks, no_pair)
        if resolved is None:
            return None
        stranded = resolved.pop("stranded")
        if not stranded:
            resolved["unpaired"] = no_pair
            return resolved
        no_pair |= stranded
    return None


def _resolve_stack(
    blocks: list[dict[str, Any]], no_pair: frozenset[int]
) -> dict[str, Any] | None:
    rows = _stack_cells(blocks, no_pair)
    measured = [
        (
            max(_block_height(cell["block"], cell["width"]) for cell in row),
            any(cell["block"]["kind"] in ELASTIC_BLOCK_KINDS for cell in row),
        )
        for row in rows
    ]
    # A labelled row announces itself in type, so it pays a reduced gap: the
    # separation is provided once and a half, not twice.
    gaps = [
        0 if position == 0
        else layout.STACK_LABEL_LEAD if any(cell["block"].get("label") for cell in row)
        else layout.STACK_ROW_GAP
        for position, row in enumerate(rows)
    ]
    resolved = layout.stack_rows(measured, gaps=gaps)
    if resolved is None:
        return None
    placed: list[dict[str, Any]] = []
    stranded: set[int] = set()
    for row, geometry in zip(rows, resolved):
        for cell in row:
            natural = _block_height(cell["block"], cell["width"])
            if cell.get("narrow") and natural < layout.CHART_TEXT_MIN_SHARE * geometry["height"]:
                stranded.add(cell["pair_index"])
            block = dict(cell["block"])
            block["box"] = {
                "left": cell["left"], "top": geometry["top"], "width": cell["width"],
                # Elastic blocks take the whole row; the rest keep their measured
                # height and sit at the top of it.
                "height": geometry["height"]
                if block["kind"] in ELASTIC_BLOCK_KINDS
                else min(natural, geometry["height"]),
            }
            placed.append(block)
    last = resolved[-1]
    return {
        "blocks": placed,
        "row_count": len(rows),
        "used_height": last["top"] + last["height"] - layout.CONTENT_TOP,
        "stranded": frozenset(stranded),
    }


def _validate_stack(slide: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    for block in slide.get("blocks") or []:
        box = block.get("box") or {}
        if box.get("top", 0) + box.get("height", 0) > layout.CONTENT_BOTTOM + 1:
            violations.append(f"stack_block_below_band:{block['kind']}")
        floor = layout.MIN_COMPONENT_DIMENSIONS.get(BLOCK_FLOORS.get(block["kind"], ""))
        if not floor:
            continue
        if box.get("width", 0) < floor["min_width"]:
            violations.append(f"stack_block_below_minimum_width:{block['kind']}")
        # A minimum height only binds a block that is given its height rather
        # than measured into it: short prose and a two-row table are legitimately
        # shorter than any floor.
        # The label is inside the box, so the content gets what is left of it.
        content_height = box.get("height", 0) - (
            layout.STACK_LABEL_HEIGHT if block.get("label") else 0
        )
        if block["kind"] in ELASTIC_BLOCK_KINDS and content_height < floor["min_height"]:
            violations.append(f"stack_block_below_minimum_height:{block['kind']}")
    return violations


def _stack_parts(slide: dict[str, Any]):
    """Each block re-expressed as the single-exhibit slide it came from."""
    for block in slide.get("blocks") or []:
        kind = block["kind"]
        if kind == "prose":
            yield {"kind": "summary", "paragraphs": block["paragraphs"]}
        elif kind == "table":
            yield {
                "kind": "table", "columns": block["columns"], "rows": block["rows"],
                "row_heights": block["row_heights"], "header_height": block["header_height"],
            }
        elif kind == "chart":
            yield {"kind": "chart", "chart": block["chart"]}


def _measure_stack(slide: dict[str, Any]) -> DensityMetrics:
    metrics = DensityMetrics()
    metrics.visible_character_count = len(_plain(slide.get("title") or ""))
    lengths: list[int] = []
    for part in _stack_parts(slide):
        sub = measure(part)
        metrics.visible_character_count += sub.visible_character_count
        metrics.component_count += sub.component_count
        metrics.text_component_count += sub.text_component_count
        metrics.table_row_count += sub.table_row_count
        metrics.table_column_count = max(metrics.table_column_count, sub.table_column_count)
        metrics.chart_count += sub.chart_count
        metrics.card_count += sub.card_count
        metrics.citation_count += sub.citation_count
        metrics.longest_text_length = max(metrics.longest_text_length, sub.longest_text_length)
        if sub.average_text_length:
            lengths.append(sub.average_text_length)
    metrics.column_count = metrics.table_column_count
    metrics.average_text_length = int(sum(lengths) / len(lengths)) if lengths else 0
    for band, ceiling in CONTENT_LOAD_BANDS:
        if ceiling is None or metrics.visible_character_count <= ceiling:
            metrics.content_load_band = band
            break
    metrics.vertical_occupancy = round(_occupancy(slide), 3)
    metrics.vertical_emptiness = round(max(0.0, 1.0 - metrics.vertical_occupancy), 3)
    return metrics


def compose(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fold adjacent exhibits from the same section onto shared slides.

    Greedy and order-preserving: a group grows only while the whole group still
    measures inside the content band, and a slide that cannot be re-read as
    blocks — a cover, a card grid, a continuation page — ends the group where it
    stands. `section_group` is what stops two unrelated topics merging under
    one title; slides without one never merge.
    """
    composed: list[dict[str, Any]] = []
    index = 0
    while index < len(slides):
        head = slides[index]
        blocks = _stack_blocks(head)
        group_id = head.get("section_group")
        if blocks is None or group_id is None:
            composed.append(head)
            index += 1
            continue
        group = [head]
        merged = blocks
        end = index + 1
        while end < len(slides):
            candidate_slide = slides[end]
            if candidate_slide.get("section_group") != group_id:
                break
            extra = _stack_blocks(candidate_slide, _absorbed_label(head, candidate_slide))
            if extra is None:
                break
            candidate = merged + extra
            if stack_layout(candidate) is None:
                break
            merged = candidate
            group.append(candidate_slide)
            end += 1
        if len(group) == 1:
            composed.append(head)
            index += 1
            continue
        composed.append(_stack_slide(group, merged))
        index = end
    return composed


def _absorbed_label(head: dict[str, Any], slide: dict[str, Any]) -> str | None:
    """The title an absorbed exhibit keeps, where it still says something new.

    A label that repeats the slide title or its section eyebrow is noise, not
    structure, so it is dropped.
    """
    title = slide.get("title")
    if not title:
        return None
    taken = {head.get("title"), head.get("section"), slide.get("section")}
    return None if title in taken else title


def _stack_slide(group: list[dict[str, Any]], blocks: list[dict[str, Any]]) -> dict[str, Any]:
    resolved = stack_layout(blocks)
    assert resolved is not None  # the group only grew while it fitted
    head = group[0]
    notes = list(dict.fromkeys(
        line for slide in group for line in (slide.get("notes") or "").splitlines() if line
    ))
    absorbed = [slide.get("title") for slide in group[1:] if slide.get("title")]
    reasons = [
        f"{len(blocks)} exhibits share one slide across {resolved['row_count']} rows",
    ]
    if absorbed:
        reasons.append("absorbed: " + "; ".join(absorbed))
    # The absorbed slides' own reasons are deliberately not inherited: they
    # describe a layout that composition has just replaced, so carrying them
    # over would leave the record asserting a split that is no longer there.
    rejected = [
        {
            "layout": "L04_SPLIT_RIGHT_DOMINANT",
            "reason": f"block {index} would be stranded beside a full-height visual",
        }
        for index in sorted(resolved["unpaired"])
    ]
    return {
        "id": "+".join(slide["id"] for slide in group),
        "kind": "stack",
        "title": head.get("title"),
        "section": head.get("section"),
        "section_group": head.get("section_group"),
        "blocks": resolved["blocks"],
        "used_height": resolved["used_height"],
        "stack_row_count": resolved["row_count"],
        "notes": "\n".join(notes),
        "composition": {"reasons": reasons, "rejected": rejected},
    }
