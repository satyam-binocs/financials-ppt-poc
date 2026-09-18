"""Single source of slide geometry and text measurement.

The Python planner decides how much fits on a slide; the Node renderer draws it.
Both read these values — the renderer receives them inside the deck
specification — so the two can never disagree. When they did disagree, table
pagination packed 440px of rows into a band that rendered only 414px.

Lengths are in the renderer's own unit: 1/96 inch, so 1280x720 spans the
13.333x7.5in widescreen canvas. Font sizes share that unit, which means a
rendered point size is 0.75x the number here (fontSize 32 emits sz="2400").
"""

from __future__ import annotations

import math
from typing import Any, Literal


Density = Literal["comfortable", "compact", "dense"]

CANVAS_WIDTH = 1280
CANVAS_HEIGHT = 720

# One horizontal band for every element. Body text used to sit at 96/1064 while
# titles and tables used 72/1136, which cost ~7% of every line for no reason.
# The band was then 0.75in per side; 0.5625in still reads as a deliberate
# margin at this canvas size and returns 36 units of line width.
MARGIN_LEFT = 54
CONTENT_WIDTH = CANVAS_WIDTH - 2 * MARGIN_LEFT

EYEBROW_TOP = 28
EYEBROW_HEIGHT = 16
TITLE_TOP_WITH_EYEBROW = 48
TITLE_TOP = 34
# Room for two rendered title lines, so the title never needs PowerPoint's
# autofit to shrink it. Autofit is banned by the design spec and, worse, lets
# PowerPoint silently rescale type whenever someone edits the deck.
TITLE_HEIGHT = 58
RULE_TOP = 118
# Longest label that still reads as a label in caps; past this the eyebrow keeps
# its own case rather than shouting. Matches the design tokens' allcaps ceiling,
# which the OOXML auditor enforces.
EYEBROW_MAX_CAPS_CHARS = 18

# Content used to start at 168 and stop at 638, leaving the 36 units below the
# rule and the 38 above the footer unused. Both are now reclaimed, and the
# header and footer bands are tightened around what they actually hold.
CONTENT_TOP = 112
CONTENT_BOTTOM = 668
FOOTER_TOP = 684

# Calibrated against rendered layouts (build/phase2/slide-*.layout.json report
# the line count the renderer actually produced): Calibri advances ~0.483 *
# fontSize per character. The old model assumed 90 chars at fontSize 23 where
# 94 fit, and never under-estimated, so every slide broke early.
CHAR_ADVANCE = 0.483
LINE_HEIGHT_FACTOR = 1.28

# Text boxes are emitted with zero horizontal inset, so the full box width is
# usable. Keep a little vertical inset so glyphs do not touch the frame.
TEXT_INSET_X = 0
TEXT_INSET_Y = 2

# Horizontal padding inside a prose row, so text does not touch the band edge —
# the same reason table cells carry an inset.
LIST_INSET_X = 12
PROSE_TEXT_WIDTH = CONTENT_WIDTH - 2 * LIST_INSET_X

# Prose borrows the table's row vocabulary: separation comes from banded fills
# and tight padding rather than from whitespace, which is what let tables carry
# several times the content of a paragraph stack. `pad` is the vertical padding
# inside a row; `lead_after` and `header_before` are folded into those items'
# own heights so one item's size never depends on its neighbours.
#
# A sub-header never renders smaller than the body it introduces.
#
# Sizes follow the analyst register the reference deck actually ships: its runs
# measure 7-16pt with nothing above 16, body at 9-10pt. In these units that is
# body 13 (9.75pt) and title 21 (15.75pt). The previous scale — 19u body, 32u
# title — was a presentation register, and it is what kept a lead paragraph and
# its table on separate slides when together they are a single thought.
PARAGRAPH_STYLE: dict[str, dict[str, int]] = {
    "comfortable": {"body": 13, "lead": 15, "header": 14, "gap": 0, "pad": 10, "lead_after": 10, "header_before": 12},
    "compact": {"body": 12, "lead": 14, "header": 13, "gap": 0, "pad": 8, "lead_after": 8, "header_before": 10},
    "dense": {"body": 11, "lead": 13, "header": 12, "gap": 0, "pad": 6, "lead_after": 6, "header_before": 8},
}

TABLE_TOP = 120
TABLE_HEADER_FONT = 13
TABLE_BODY_FONT = 12
TABLE_INSET_X = 4
TABLE_INSET_Y = 2
TABLE_ROW_MIN = 26
TABLE_ROW_MAX = 240
TABLE_HEADER_MIN = 32
TABLE_HEADER_MAX = 56
TABLE_ROW_PADDING = 8
# Column widths follow each column's character load, but never drop below what
# its longest word needs: a starved column breaks words and wraps deeper, which
# is what drives the row height that costs slides.
TABLE_COLUMN_MIN_WIDTH = 104
TABLE_MAX_WORD_CHARS = 16
# Splitting a wide table sideways produces two half-empty slides, and
# content-proportional widths keep seven columns legible, so split later.
TABLE_MAX_COLUMNS = 7

PARAGRAPH_CAPACITY = CONTENT_BOTTOM - CONTENT_TOP
TABLE_BAND_HEIGHT = CONTENT_BOTTOM - TABLE_TOP

# A short intro paragraph belongs with the table it introduces rather than on a
# slide of its own. Past this height the prose stops being an intro and would
# squeeze the table into extra pages.
TABLE_PROSE_MAX_HEIGHT = 250
TABLE_PROSE_GAP = 16

# Charts need more of the slide than a table does before they stop reading, so
# an intro above one has to be shorter.
CHART_TOP = 118
CHART_LEFT = MARGIN_LEFT + 14
CHART_WIDTH = CANVAS_WIDTH - 2 * CHART_LEFT
CHART_HEIGHT = CONTENT_BOTTOM - CHART_TOP
CHART_PROSE_MAX_HEIGHT = 215
# Scenario callouts and bridge labels are drawn over the plot area, which the
# chart library insets from the shape by a fixed amount for axis labels and the
# legend. Expressing those as insets rather than absolute coordinates is what
# lets a chart move or resize without stranding its overlays — which is why no
# chart kind is barred from carrying an intro any more.
SCENARIO_PLOT_INSETS = {"left": 82, "top": 9, "right": 22, "bottom": 64}
BRIDGE_PLOT_INSETS = {"left": 62, "top": 9, "right": 22, "bottom": 45}

# Chart-and-commentary split: text down the left, chart taking the rest. The
# narrow column reads at ~63 characters a line against 182 at full width, so
# substantial commentary belongs here rather than stacked above the chart.
CHART_TEXT_WIDTH = 396
CHART_TEXT_GAP = 24
CHART_TEXT_FONT = 13
# Below this share of the band the commentary cannot carry a column of its own,
# and a one-line lead reads better as a strip above a full-width chart.
CHART_TEXT_MIN_SHARE = 0.35

# Overlay labels — scenario callouts and waterfall bridge labels. Whether they
# survive a narrower chart is a measured property of the label text and the
# category count, not a property of the chart kind: a four-category chart with
# short labels fits a half-width plot comfortably, while a seven-category one
# with long labels does not fit even at full width.
OVERLAY_LABEL_FONT = 11
OVERLAY_LABEL_GAP = 11
OVERLAY_LABEL_PADDING = 10
OVERLAY_LABEL_HEIGHT = 22
# Callouts are bold, and bold Calibri advances wider than the body face the
# CHAR_ADVANCE constant was calibrated on. Measured from rendered labels.
OVERLAY_LABEL_ADVANCE = 0.52
SCENARIO_ABBREVIATIONS = {
    "Downside": "Down", "Base case": "Base", "Upside": "Up", "Management plan": "Mgmt",
}


def overlay_label_width(text: str) -> int:
    """Width a callout box needs for its own text, rather than a fixed guess."""
    return math.ceil(len(text) * OVERLAY_LABEL_FONT * OVERLAY_LABEL_ADVANCE) + OVERLAY_LABEL_PADDING


def overlay_label_texts(chart: dict[str, Any]) -> list[str]:
    """The label strings the renderer will draw over a chart's plot area."""
    kind = chart.get("kind")
    labels: list[str] = []
    if kind == "range_line":
        for series in chart.get("series") or []:
            if series.get("role") == "range":
                continue
            name = SCENARIO_ABBREVIATIONS.get(series.get("name", ""), series.get("name", ""))
            for point in series.get("points") or []:
                if point.get("value") is None:
                    continue
                labels.append(f"{name} ${point['value']:.1f}M")
    elif kind == "waterfall":
        for series in chart.get("series") or []:
            for point in series.get("points") or []:
                if point.get("value") is None:
                    continue
                labels.append(point.get("display") or f"{point['value']:.1f}")
    return labels


def chart_overlays_fit(chart: dict[str, Any], box: dict[str, int]) -> bool:
    """Whether a chart's overlay labels fit inside one category slot.

    Each label is drawn beside its data point and may flip to whichever side has
    room, so the binding constraint is that a label plus its leader gap fits
    within the horizontal space one category owns. That keeps labels clear of
    each other and inside the plot at any chart width.
    """
    labels = overlay_label_texts(chart)
    if not labels:
        return True
    insets = SCENARIO_PLOT_INSETS if chart.get("kind") == "range_line" else BRIDGE_PLOT_INSETS
    plot_width = box["width"] - insets["left"] - insets["right"]
    categories = len(chart.get("categories") or []) or 1
    step = plot_width / categories
    return max(overlay_label_width(text) for text in labels) + OVERLAY_LABEL_GAP <= step


def chart_text_geometry() -> dict[str, int]:
    """Resolved boxes for the commentary column and the chart beside it."""
    chart_left = MARGIN_LEFT + CHART_TEXT_WIDTH + CHART_TEXT_GAP
    return {
        "text_left": MARGIN_LEFT,
        "text_width": CHART_TEXT_WIDTH,
        "chart_left": chart_left,
        "chart_width": CANVAS_WIDTH - chart_left - MARGIN_LEFT,
    }


def fits_chart_text_column(items: list[dict[str, Any]], density: Density = "comfortable") -> bool:
    """Whether commentary both fits the narrow column and earns one."""
    height = prose_block_height(items, density, width=prose_text_width(CHART_TEXT_WIDTH))
    if height > PARAGRAPH_CAPACITY:
        return False
    if chart_text_geometry()["chart_width"] < MIN_COMPONENT_DIMENSIONS["chart"]["min_width"]:
        return False
    return height >= CHART_TEXT_MIN_SHARE * PARAGRAPH_CAPACITY

CAPACITY: dict[str, int] = {density: PARAGRAPH_CAPACITY for density in PARAGRAPH_STYLE}

# ── Cards and grids ────────────────────────────────────────────────────────────
# Card content arrives as a set of peer components, so it is the one content
# shape that wants a grid rather than a full-width stack. Geometry mirrors the
# table vocabulary: a bordered box, tight padding, a title that reads as a
# header.
CARD_GAP_X = 16
CARD_GAP_Y = 14
CARD_PADDING_X = 12
CARD_PADDING_Y = 10
CARD_STYLE: dict[str, dict[str, int]] = {
    "comfortable": {"title": 14, "body": 12, "badge": 10, "line_gap": 6},
    "compact": {"title": 13, "body": 11, "badge": 10, "line_gap": 5},
    "dense": {"title": 12, "body": 11, "badge": 9, "line_gap": 4},
}
CARD_MAX_PER_SLIDE = 6
# A card is a container: growing it past this only moves dead space inside the
# border, so surplus band height stops being shared out here.
CARD_GROWTH_CAP = 0.30

# Minimum viable geometry per component type. A layout that puts any component
# below these is rejected outright rather than shrunk into it.
MIN_COMPONENT_DIMENSIONS: dict[str, dict[str, int]] = {
    "short_card": {"min_width": 130, "min_height": 72},
    "detailed_card": {"min_width": 216, "min_height": 115},
    "chart": {"min_width": 307, "min_height": 192},
    "table": {"min_width": 528, "min_height": 144},
    "callout": {"min_width": 192, "min_height": 72},
    "paragraph": {"min_width": 288, "min_height": 67},
}
# A card whose body exceeds this is "detailed" and may not go in narrow columns.
CARD_COMPACT_MAX_CHARS = 180

# ── References appendix ───────────────────────────────────────────────────────
# Full source strings belong on one slide at the back, not in the components
# that cite them. Metadata type is permitted to run smaller here than body copy.
REFERENCE_FONT = 10
REFERENCE_LINE_GAP = 4
REFERENCE_COLUMN_GAP = 28
# Past this many entries one column becomes a wall, so the list splits in two.
REFERENCE_TWO_COLUMN_THRESHOLD = 14


def chars_per_line(font_size: int, width: int = CONTENT_WIDTH) -> int:
    usable = max(1, width - 2 * TEXT_INSET_X)
    return max(8, int(usable / (font_size * CHAR_ADVANCE)))


def paragraph_font(kind: str, density: Density = "comfortable") -> int:
    style = PARAGRAPH_STYLE[density]
    if kind == "lead":
        return style["lead"]
    if kind == "header":
        return style["header"]
    return style["body"]


def paragraph_gap(density: Density = "comfortable") -> int:
    return PARAGRAPH_STYLE[density]["gap"]


def paragraph_height(
    text: str,
    kind: str = "body",
    density: Density = "comfortable",
    *,
    width: int = PROSE_TEXT_WIDTH,
    with_gap: bool = True,
) -> int:
    """Rendered height of one paragraph row, padding included."""
    style = PARAGRAPH_STYLE[density]
    font_size = paragraph_font(kind, density)
    prefix = 3 if kind == "bullet" else 0
    lines = max(1, math.ceil((len(text) + prefix) / chars_per_line(font_size, width)))
    height = math.ceil(lines * font_size * LINE_HEIGHT_FACTOR) + style["pad"]
    if kind == "lead":
        height += style["lead_after"]
    elif kind == "header":
        height += style["header_before"]
    return height + (paragraph_gap(density) if with_gap else 0)


def prose_block_height(
    items: list[dict[str, Any]],
    density: Density = "comfortable",
    *,
    width: int = PROSE_TEXT_WIDTH,
) -> int:
    """Height of a prose run rendered as a strip, with no trailing gap."""
    if not items:
        return 0
    total = sum(
        paragraph_height(item.get("text", "") or "", item.get("kind", "body"), density, width=width)
        for item in items
    )
    return total - paragraph_gap(density)


def prose_text_width(box_width: int) -> int:
    """Width the text inside a prose box actually wraps at.

    A prose row fills its box; the type inside it is inset on both sides. The
    two were previously conflated for the commentary column, which measured at
    the box width and rendered at the narrower text width — an under-estimate,
    the one direction the height model is not allowed to err in.
    """
    return max(1, box_width - 2 * LIST_INSET_X)


def card_font(role: str, density: Density = "comfortable") -> int:
    return CARD_STYLE[density][role]


def card_height(card: Any, width: int, density: Density = "comfortable") -> int:
    """Height one card needs at a given column width."""
    style = CARD_STYLE[density]
    text_width = max(40, width - 2 * CARD_PADDING_X)
    total = 2 * CARD_PADDING_Y
    title = _card_field(card, "title")
    if title:
        lines = max(1, math.ceil(len(title) / chars_per_line(style["title"], text_width)))
        total += math.ceil(lines * style["title"] * LINE_HEIGHT_FACTOR) + style["line_gap"]
    if _card_badges(card):
        total += math.ceil(style["badge"] * LINE_HEIGHT_FACTOR) + style["line_gap"]
    for text in _card_body_texts(card):
        lines = max(1, math.ceil(len(text) / chars_per_line(style["body"], text_width)))
        total += math.ceil(lines * style["body"] * LINE_HEIGHT_FACTOR) + style["line_gap"]
    return total


def card_body_chars(card: Any) -> int:
    return sum(len(text) for text in _card_body_texts(card))


def _card_field(card: Any, name: str) -> str:
    value = card.get(name) if isinstance(card, dict) else getattr(card, name, None)
    return str(value or "")


def _card_badges(card: Any) -> list[str]:
    value = card.get("badges") if isinstance(card, dict) else getattr(card, "badges", None)
    return [str(item) for item in (value or [])]


def _card_body_texts(card: Any) -> list[str]:
    value = card.get("paragraphs") if isinstance(card, dict) else getattr(card, "paragraphs", None)
    texts = []
    for item in value or []:
        text = item.get("text") if isinstance(item, dict) else getattr(item, "text", None)
        if text:
            texts.append(str(text))
    return texts


def card_grid_boxes(
    cards: list[Any],
    columns: int,
    top: int,
    density: Density = "comfortable",
    *,
    bottom: int = CONTENT_BOTTOM,
) -> tuple[list[dict[str, int]], int]:
    """Resolved boxes for a card grid, plus the height the grid uses.

    Cards in a row share a height — the tallest one's — so a row reads as one
    band, but rows differ from each other rather than being forced equal. Any
    surplus band height is shared out so the grid fills the slide instead of
    leaving a gap under the last row.
    """
    if not cards or columns <= 0:
        return [], 0
    count = len(cards)
    row_heights, width = card_row_heights(cards, columns, density)
    rows = len(row_heights)

    available = bottom - top - (rows - 1) * CARD_GAP_Y
    surplus = available - sum(row_heights)
    if surplus > 0:
        # Let rows breathe, but cap the growth. A card is a container, so
        # stretching it past this just moves the empty space inside the border.
        share = surplus // rows
        row_heights = [
            height + min(share, int(height * CARD_GROWTH_CAP))
            for height in row_heights
        ]

    boxes: list[dict[str, int]] = []
    offsets: list[int] = []
    cursor = top
    for height in row_heights:
        offsets.append(cursor)
        cursor += height + CARD_GAP_Y

    # A final row with fewer cards than columns would leave an empty cell beside
    # them, so its cards share the full width instead.
    last_row_count = count - (rows - 1) * columns
    for index in range(count):
        row, column = divmod(index, columns)
        in_short_last_row = row == rows - 1 and last_row_count < columns
        span = last_row_count if in_short_last_row else columns
        box_width = int((CONTENT_WIDTH - (span - 1) * CARD_GAP_X) / span)
        boxes.append({
            "left": MARGIN_LEFT + column * (box_width + CARD_GAP_X),
            "top": offsets[row],
            "width": box_width,
            "height": row_heights[row],
        })
    used = sum(row_heights) + (rows - 1) * CARD_GAP_Y
    return boxes, used


def chart_grid_boxes(
    count: int,
    columns: int,
    top: int,
    *,
    bottom: int = CONTENT_BOTTOM,
) -> tuple[list[dict[str, int]], int]:
    """Equal boxes for a grid of charts; a chart has no text to measure."""
    if count <= 0 or columns <= 0:
        return [], 0
    rows = math.ceil(count / columns)
    width = int((CONTENT_WIDTH - (columns - 1) * CARD_GAP_X) / columns)
    available = bottom - top - (rows - 1) * CARD_GAP_Y
    height = int(available / rows)
    boxes = [
        {
            "left": MARGIN_LEFT + (index % columns) * (width + CARD_GAP_X),
            "top": top + (index // columns) * (height + CARD_GAP_Y),
            "width": width,
            "height": height,
        }
        for index in range(count)
    ]
    return boxes, available + (rows - 1) * CARD_GAP_Y


def card_row_heights(cards: list[Any], columns: int, density: Density = "comfortable") -> tuple[list[int], int]:
    """Natural height of each row, sized to the tallest card it holds."""
    width = int((CONTENT_WIDTH - (columns - 1) * CARD_GAP_X) / columns)
    rows = math.ceil(len(cards) / columns)
    heights = [
        max(card_height(card, width, density) for card in cards[row * columns:(row + 1) * columns])
        for row in range(rows)
    ]
    return heights, width


def grid_fits(cards: list[Any], columns: int, top: int, density: Density = "comfortable") -> tuple[bool, str]:
    """Whether a card grid is geometrically valid, and why not when it is not.

    Rows are sized to their content rather than to an equal share of the band:
    an equal share rejects grids that would comfortably fit and inflates the
    ones that are accepted.
    """
    if not cards:
        return False, "no_components"
    row_heights, width = card_row_heights(cards, columns, density)
    available = CONTENT_BOTTOM - top - (len(row_heights) - 1) * CARD_GAP_Y

    detailed = any(card_body_chars(card) > CARD_COMPACT_MAX_CHARS for card in cards)
    minimum = MIN_COMPONENT_DIMENSIONS["detailed_card" if detailed else "short_card"]
    if width < minimum["min_width"]:
        return False, "minimum_width_violation"
    if min(row_heights) < minimum["min_height"]:
        return False, "minimum_height_violation"
    if sum(row_heights) > available:
        return False, "content_exceeds_region"
    return True, ""


def column_weights(columns: list[Any], rows: list[Any]) -> list[float]:
    """Column widths in px, summing to the content width.

    Row height is driven by the column that wraps deepest, so widths
    proportional to character load equalise wrap depth and minimise the row —
    which is what fits more rows per slide. The renderer normalises these into
    fractional column tracks, so they serve as weights unchanged.
    """
    loads: list[float] = []
    minimums: list[float] = []
    for column in columns:
        texts = [_cell_text(row, column.key) for row in rows]
        lengths = [len(text) for text in texts if text]
        mean_length = (sum(lengths) / len(lengths)) if lengths else 0.0
        title = str(getattr(column, "title", "") or "")
        loads.append(float(max(len(title), mean_length, 1.0)))
        # A column narrow enough to break words mid-word looks broken, and the
        # extra wrapping it causes is also what makes the row tall.
        longest_word = max(
            (len(word) for text in [title, *texts] for word in text.split()),
            default=1,
        )
        word_chars = min(TABLE_MAX_WORD_CHARS, longest_word)
        minimums.append(max(
            TABLE_COLUMN_MIN_WIDTH,
            word_chars * TABLE_HEADER_FONT * CHAR_ADVANCE + 2 * TABLE_INSET_X,
        ))

    available = float(CONTENT_WIDTH)
    if sum(minimums) >= available:
        scale = available / sum(minimums)
        return [minimum * scale for minimum in minimums]

    # Share the width in proportion to character load, then lift any column that
    # landed under its minimum and re-share what is left among the others.
    # Lifted columns stay pinned: re-sharing them would push them straight back
    # under the minimum they were just raised to.
    widths = [available * load / sum(loads) for load in loads]
    pinned: set[int] = set()
    for _ in range(len(columns)):
        newly_short = [
            index for index in range(len(columns))
            if index not in pinned and widths[index] < minimums[index]
        ]
        if not newly_short:
            break
        pinned.update(newly_short)
        for index in pinned:
            widths[index] = minimums[index]
        free = [index for index in range(len(columns)) if index not in pinned]
        remaining = available - sum(minimums[index] for index in pinned)
        if not free or remaining <= 0:
            break
        load_total = sum(loads[index] for index in free) or 1.0
        for index in free:
            widths[index] = remaining * loads[index] / load_total
    return widths


def _cell_text(row: Any, key: str) -> str:
    cell = row.get(key) if isinstance(row, dict) else None
    if cell is None:
        return ""
    if isinstance(cell, dict):
        return str(cell.get("plain_text") or "")
    return str(getattr(cell, "plain_text", "") or "")


def _wrapped_lines(text: str, chars: int) -> int:
    explicit = text.splitlines() or [""]
    return sum(max(1, (len(line) + chars - 1) // chars) for line in explicit)


def column_chars(weight: float, total_weight: float, font_size: int) -> int:
    width = CONTENT_WIDTH * weight / total_weight
    usable = max(8, width - 2 * TABLE_INSET_X)
    return max(6, int(usable / (font_size * CHAR_ADVANCE)))


def table_row_height(row: Any, columns: list[Any], weights: list[float]) -> int:
    total_weight = sum(weights) or 1.0
    lines = [
        _wrapped_lines(_cell_text(row, column.key), column_chars(weight, total_weight, TABLE_BODY_FONT))
        for column, weight in zip(columns, weights)
    ]
    needed = max(lines, default=1) * TABLE_BODY_FONT * LINE_HEIGHT_FACTOR + TABLE_ROW_PADDING
    return int(min(TABLE_ROW_MAX, max(TABLE_ROW_MIN, math.ceil(needed))))


def table_header_height(columns: list[Any], weights: list[float]) -> int:
    total_weight = sum(weights) or 1.0
    lines = [
        _wrapped_lines(str(getattr(column, "title", "") or ""), column_chars(weight, total_weight, TABLE_HEADER_FONT))
        for column, weight in zip(columns, weights)
    ]
    needed = max(lines, default=1) * TABLE_HEADER_FONT * LINE_HEIGHT_FACTOR + TABLE_ROW_PADDING
    return int(min(TABLE_HEADER_MAX, max(TABLE_HEADER_MIN, math.ceil(needed))))


def balanced_pages(
    heights: list[int],
    capacity: int,
    *,
    gap: int = 0,
    first_capacity: int | None = None,
) -> list[list[int]]:
    """Split indices into the fewest pages, then even out how full they are.

    Greedy first-fit leaves a nearly empty trailing page whenever the next item
    is slightly too tall. Minimising page count first and balancing second means
    a spill-over page still looks deliberate. `first_capacity` covers the case
    where an intro strip has already claimed part of the opening slide.
    """
    count = len(heights)
    if count == 0:
        return [[]]

    def span(start: int, end: int) -> int:
        return sum(heights[start:end]) - (gap if gap and end > start else 0)

    unreachable = count + 1
    pages_needed = [unreachable] * (count + 1)
    pages_needed[count] = 0
    for start in range(count - 1, -1, -1):
        for end in range(start + 1, count + 1):
            if span(start, end) > capacity and end > start + 1:
                break
            if pages_needed[end] + 1 < pages_needed[start]:
                pages_needed[start] = pages_needed[end] + 1

    # Among splits that use the fewest pages, prefer the most even fill.
    best_cost: dict[int, float] = {}
    choice: dict[int, int] = {}

    def feasible_ends(start: int, limit: int) -> list[int]:
        ends = []
        for end in range(start + 1, count + 1):
            if span(start, end) > limit and end > start + 1:
                break
            ends.append(end)
        return ends

    def solve(start: int) -> float:
        if start == count:
            return 0.0
        if start in best_cost:
            return best_cost[start]
        target = pages_needed[start]
        best = math.inf
        # Largest page first, so an exact tie fills the earlier slide and leaves
        # the short page at the end, where a reader expects it.
        for end in reversed(feasible_ends(start, capacity)):
            if pages_needed[end] + 1 != target:
                continue
            slack = max(0, capacity - span(start, end))
            cost = slack * slack + solve(end)
            if cost < best:
                best = cost
                choice[start] = end
        best_cost[start] = best
        return best

    solve(0)

    def collect(first_end: int | None) -> list[list[int]]:
        pages: list[list[int]] = []
        index = 0
        if first_end is not None:
            pages.append(list(range(0, first_end)))
            index = first_end
        while index < count:
            end = choice.get(index, count)
            if end <= index:
                end = count
            pages.append(list(range(index, end)))
            index = end
        return pages

    if first_capacity is None or first_capacity >= capacity:
        return collect(None)

    # The opening page is smaller, so pick its split separately and let the
    # balanced solution above cover everything that follows.
    best_key: tuple[int, float] | None = None
    best_end: int | None = None
    for end in reversed(feasible_ends(0, first_capacity)):
        slack = max(0, first_capacity - span(0, end))
        # The remainder's cost has to count here too. Minimising only the first
        # page's slack fills it to the brim and strands the leftovers.
        remainder = solve(end) if end < count else 0.0
        key = (1 + (pages_needed[end] if end < count else 0), slack * slack + remainder)
        if best_key is None or key < best_key:
            best_key, best_end = key, end
    return collect(best_end)


# ── Composite slides ─────────────────────────────────────────────────────────
# The densest slide is not a new layout so much as the general case of the ones
# above: a vertical stack of rows, where a row is one full-width block or a
# narrow pair. Nothing here knows which content kinds exist. A row is described
# by a measured minimum height and whether it is elastic — whether it will
# accept whatever height is left over — so a chart, a table and its commentary
# share a slide on the same terms as any other combination.
STACK_ROW_GAP = 16
# A composite keeps one slide title, so an exhibit that arrived under a title of
# its own carries it as a label above its box — otherwise a second table on the
# slide reads as an unexplained strip.
STACK_LABEL_FONT = 12
STACK_LABEL_HEIGHT = math.ceil(STACK_LABEL_FONT * LINE_HEIGHT_FACTOR) + 4
# A labelled block still needs air above its label, but less than a full row
# gap: the label itself already separates it from what came before.
STACK_LABEL_LEAD = STACK_ROW_GAP // 2


def stack_rows(
    measured: list[tuple[int, bool]],
    *,
    top: int = CONTENT_TOP,
    bottom: int = CONTENT_BOTTOM,
    gaps: list[int] | None = None,
) -> list[dict[str, int]] | None:
    """Resolve each row's top and height, or None if the stack does not fit.

    `measured` is (minimum_height, elastic) per row in document order, and
    `gaps` the space above each row after the first. Surplus band height is
    shared out among the elastic rows only: prose and tables are already
    exactly as tall as their content, so growing them would just open dead
    space, while a chart is a viewport that reads better larger.
    """
    if not measured:
        return None
    if gaps is None:
        gaps = [0] + [STACK_ROW_GAP] * (len(measured) - 1)
    band = bottom - top
    heights = [height for height, _ in measured]
    required = sum(heights) + sum(gaps)
    if required > band:
        return None
    elastic = [index for index, (_, is_elastic) in enumerate(measured) if is_elastic]
    if elastic:
        share, remainder = divmod(band - required, len(elastic))
        for position, index in enumerate(elastic):
            heights[index] += share + (1 if position < remainder else 0)
    rows: list[dict[str, int]] = []
    y = top
    for height, gap in zip(heights, gaps):
        y += gap
        rows.append({"top": y, "height": height})
        y += height
    return rows


def to_spec() -> dict[str, Any]:
    """Geometry handed to the renderer inside the deck specification."""
    return {
        "canvas": {"width": CANVAS_WIDTH, "height": CANVAS_HEIGHT},
        "margin_left": MARGIN_LEFT,
        "content_width": CONTENT_WIDTH,
        "eyebrow": {"top": EYEBROW_TOP, "height": EYEBROW_HEIGHT},
        "eyebrow_max_caps_chars": EYEBROW_MAX_CAPS_CHARS,
        "title": {
            "top": TITLE_TOP,
            "top_with_eyebrow": TITLE_TOP_WITH_EYEBROW,
            "height": TITLE_HEIGHT,
        },
        "rule_top": RULE_TOP,
        "content": {"top": CONTENT_TOP, "bottom": CONTENT_BOTTOM, "height": PARAGRAPH_CAPACITY},
        "footer_top": FOOTER_TOP,
        "text_inset": {"x": TEXT_INSET_X, "y": TEXT_INSET_Y},
        "prose": {"inset_x": LIST_INSET_X, "text_width": PROSE_TEXT_WIDTH},
        "stack": {
            "row_gap": STACK_ROW_GAP,
            "label_font": STACK_LABEL_FONT, "label_height": STACK_LABEL_HEIGHT,
            "label_lead": STACK_LABEL_LEAD,
        },
        "paragraph": PARAGRAPH_STYLE,
        "table": {
            "top": TABLE_TOP,
            "band_height": TABLE_BAND_HEIGHT,
            "header_font": TABLE_HEADER_FONT,
            "body_font": TABLE_BODY_FONT,
            "inset": {"x": TABLE_INSET_X, "y": TABLE_INSET_Y},
        },
        "reference": {
            "font": REFERENCE_FONT, "line_gap": REFERENCE_LINE_GAP,
            "column_gap": REFERENCE_COLUMN_GAP,
            "two_column_threshold": REFERENCE_TWO_COLUMN_THRESHOLD,
        },
        "chart": {
            "top": CHART_TOP, "left": CHART_LEFT, "width": CHART_WIDTH, "height": CHART_HEIGHT,
            "scenario_plot_insets": SCENARIO_PLOT_INSETS,
            "bridge_plot_insets": BRIDGE_PLOT_INSETS,
            "text_width": CHART_TEXT_WIDTH, "text_gap": CHART_TEXT_GAP, "text_font": CHART_TEXT_FONT,
            "overlay_label": {
                "font": OVERLAY_LABEL_FONT, "gap": OVERLAY_LABEL_GAP,
                "padding": OVERLAY_LABEL_PADDING, "height": OVERLAY_LABEL_HEIGHT,
                "advance": OVERLAY_LABEL_ADVANCE,
            },
        },
        "card": {
            "gap_x": CARD_GAP_X, "gap_y": CARD_GAP_Y,
            "padding_x": CARD_PADDING_X, "padding_y": CARD_PADDING_Y,
            "style": CARD_STYLE,
        },
    }


def reference_column_width(columns: int) -> int:
    return (CONTENT_WIDTH - (columns - 1) * REFERENCE_COLUMN_GAP) // columns


def reference_entry_chars(columns: int) -> int:
    """Characters one appendix line holds, label prefix included.

    Each entry is drawn one line tall, so an entry that does not fit is clipped
    rather than wrapped. Trimming it here is the only place that knows the
    column width.
    """
    return chars_per_line(REFERENCE_FONT, reference_column_width(columns))


def reference_entries_per_slide() -> int:
    """How many source lines fit the content band across both columns."""
    line = math.ceil(REFERENCE_FONT * LINE_HEIGHT_FACTOR) + REFERENCE_LINE_GAP
    rows = max(1, (CONTENT_BOTTOM - CONTENT_TOP) // line)
    return rows * 2
