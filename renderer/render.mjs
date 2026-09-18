import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile, fr } from "@oai/artifact-tool";

process.on("uncaughtException", (error) => {
  console.error(`COMPACT_ERROR: ${error?.message ?? error}`);
  process.exit(1);
});
process.on("unhandledRejection", (error) => {
  console.error(`COMPACT_ERROR: ${error?.message ?? error}`);
  process.exit(1);
});

const { SKILL_DIR, TMP_DIR, WORKSPACE_DIR, DECK_SPEC, FINAL_PPTX, RUNTIME_PYTHON } = process.env;
for (const [name, value] of Object.entries({ SKILL_DIR, TMP_DIR, WORKSPACE_DIR, DECK_SPEC, FINAL_PPTX, RUNTIME_PYTHON })) {
  if (!path.isAbsolute(value ?? "")) throw new Error(`${name} must be absolute`);
}
const utils = await import(pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href);
const { resolvePresentationFont, applyPresentationChartFont, finalizePresentation } = utils;
const spec = JSON.parse(await fs.readFile(DECK_SPEC, "utf8"));
const slidesToRender = process.env.DEBUG_SLIDE_COUNT
  ? spec.slides.slice(0, Number(process.env.DEBUG_SLIDE_COUNT))
  : spec.slides;
const theme = spec.theme;
// Geometry comes from the planner (report_pptx/layout.py) so pagination and
// rendering cannot disagree about how much fits on a slide.
const L = spec.layout;
const family = resolvePresentationFont({ fontFamily: "Calibri" });
const textInsets = { top: L.text_inset.y, bottom: L.text_inset.y, left: L.text_inset.x, right: L.text_inset.x };
const charsPerLine = (fontSize, width) =>
  Math.max(8, Math.floor((width - 2 * L.text_inset.x) / (fontSize * 0.483)));
// Mirrors report_pptx.layout.overlay_label_width, which the planner uses to
// decide whether a chart can be narrowed at all.
const overlayLabelWidth = (text) =>
  Math.ceil(text.length * L.chart.overlay_label.font * L.chart.overlay_label.advance)
  + L.chart.overlay_label.padding;
const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const chartOwners = [];
const tableOwners = [];

function textbox(slide, text, position, style = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox", position, fill: "none", line: { fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    typeface: family, fontSize: 24, color: theme.ink, autoFit: "none",
    insets: textInsets,
    ...style,
  };
  return shape;
}

function baseSlide(slide, title, section = null) {
  slide.background.fill = theme.background;
  if (section) {
    // Caps only while it still reads as a label; a long one just shouts.
    const label = section.length <= L.eyebrow_max_caps_chars ? section.toUpperCase() : section;
    textbox(slide, label, { left: L.margin_left, top: L.eyebrow.top, width: 700, height: L.eyebrow.height },
      { fontSize: 11, bold: true, color: theme.primary });
  }
  textbox(slide, title, {
    left: L.margin_left, top: section ? L.title.top_with_eyebrow : L.title.top,
    width: L.content_width, height: L.title.height,
  }, { fontSize: 21, bold: true });
  // No divider under the title: a rule drawn on every slide is decoration
  // rather than structure, and spacing already separates title from content.
}

function addNotes(slide, notes) {
  if (notes) slide.speakerNotes.textFrame.setText(notes);
}

function addFooter(slide, index) {
  const width = 58;
  textbox(slide, String(index).padStart(2, "0"),
    { left: L.canvas.width - L.margin_left - width, top: L.footer_top, width, height: 18 },
    { fontSize: 10, color: theme.muted, alignment: "right" });
}

// Prose is laid out the way table rows are: banded fills and tight padding do
// the separating, so the whitespace a paragraph stack spends between items goes
// back to content. Measurement must match report_pptx/layout.paragraph_height
// exactly, or the planner and the renderer disagree about what fits.
function measureProse(paragraphs, style, { allowFocusBump = false, width = L.prose.text_width } = {}) {
  const singleFocus = allowFocusBump && paragraphs.length === 1;
  const measure = (bump) => paragraphs.map((paragraph) => {
    const role = paragraph.kind === "lead" ? "lead" : paragraph.kind === "header" ? "header" : "body";
    const prefix = paragraph.kind === "bullet" ? "•  " : "";
    const fontSize = bump ? Math.max(style[role], 18) : style[role];
    const lineCount = Math.max(1, Math.ceil((prefix.length + paragraph.text.length) / charsPerLine(fontSize, width)));
    let height = Math.ceil(lineCount * fontSize * 1.28) + style.pad;
    if (role === "lead") height += style.lead_after;
    else if (role === "header") height += style.header_before;
    return { paragraph, role, prefix, fontSize, height };
  });
  let rows = measure(false);
  if (singleFocus) {
    // A lone statement reads better large, but only if it still fits.
    const bumped = measure(true);
    if (bumped.reduce((sum, row) => sum + row.height, 0) <= L.content.height) rows = bumped;
  }
  return rows;
}

function drawProseRows(slide, rows, startY, style, { banded = true, width = L.content_width, left = L.margin_left } = {}) {
  const half = style.pad / 2;
  const textWidth = width - 2 * L.prose.inset_x;
  // An alternating tint reads as a list only when there is a list to read. With
  // one or two rows it is just a tinted panel, so the tint is dropped and the
  // separators carry the structure.
  const bodyRows = rows.filter((row) => row.role === "body").length;
  const tinted = banded && bodyRows >= 3;
  let y = startY;
  let band = 0;
  for (const { paragraph, role, prefix, fontSize, height } of rows) {
    if (!banded && role !== "header") {
      // A lone statement is the whole slide; a band around it would read as an
      // empty table rather than as emphasis.
      textbox(slide, prefix + paragraph.text, {
        left: left + L.prose.inset_x, top: y + half,
        width: textWidth, height: height - style.pad,
      }, { fontSize, color: theme.ink });
      y += height;
      continue;
    }
    if (role === "header") {
      // Matches a table's header: primary fill, white bold label.
      const barTop = y + style.header_before;
      const barHeight = height - style.header_before;
      slide.shapes.add({
        geometry: "rect",
        position: { left, top: barTop, width, height: barHeight },
        fill: theme.primary, line: { fill: "none", width: 0 },
      });
      textbox(slide, paragraph.text, {
        left: left + L.prose.inset_x, top: barTop + half,
        width: textWidth, height: barHeight - style.pad,
      }, { fontSize, bold: true, color: "#FFFFFF" });
      band = 0;
    } else if (role === "lead") {
      // The takeaway line: bold and in the primary colour so hierarchy is
      // unmistakable against the body that follows it.
      textbox(slide, paragraph.text, {
        left: left + L.prose.inset_x, top: y + half, width: textWidth,
        height: height - style.lead_after - style.pad,
      }, { fontSize, bold: true, color: theme.primary });
      band = 0;
    } else {
      // Rows separated the way the tables are: a very light alternating tint
      // and a hairline rule underneath, rather than a boxed cell per item.
      const fill = tinted && band % 2 ? theme.band : theme.surface;
      const row = slide.shapes.add({
        geometry: "rect",
        position: { left, top: y, width, height },
        fill, line: { fill: "none", width: 0 },
      });
      row.name = "structure:prose-row";
      const divider = slide.shapes.add({
        geometry: "rect",
        position: { left, top: y + height - 1, width, height: 1 },
        fill: theme.rule, line: { fill: "none", width: 0 },
      });
      divider.name = "structure:row-divider";
      // The height model is deliberately conservative, so a row is sometimes a
      // line taller than the text needs. Insetting the text box by half the row
      // padding spreads that slack above and below instead of leaving a gap
      // under the text.
      textbox(slide, prefix + paragraph.text, {
        left: left + L.prose.inset_x, top: y + half,
        width: textWidth, height: height - style.pad,
      }, { fontSize, color: theme.ink });
      band += 1;
    }
    y += height;
  }
}

function addParagraphs(slide, paragraphs, top = L.content.top, density = "comfortable") {
  const style = L.paragraph[density] ?? L.paragraph.comfortable;
  const rows = measureProse(paragraphs, style, { allowFocusBump: true });
  const contentHeight = rows.reduce((sum, row) => sum + row.height, 0);
  // Top-anchored, so every slide shares one content baseline. Centring a short
  // run pushed it into the middle of the slide and left a gap above it that no
  // amount of extra content could ever use.
  const startY = paragraphs.length === 1
    ? top + Math.max(0, (L.content.height - contentHeight) / 2)
    : top;
  drawProseRows(slide, rows, startY, style, { banded: paragraphs.length > 1 });
}

// Intro prose above a table or chart: top-anchored, unlike addParagraphs,
// because the visual below owns the rest of the slide.
function addProseStrip(slide, paragraphs, density = "comfortable") {
  const style = L.paragraph[density] ?? L.paragraph.comfortable;
  // A one-line intro above a table needs no band of its own; the table below
  // already carries the banding.
  drawProseRows(slide, measureProse(paragraphs, style), L.content.top, style, {
    banded: paragraphs.length > 1,
  });
}

// Cards are peer components, so they get a grid whose boxes the planner already
// resolved. Visually they reuse the table vocabulary: a bordered box, a title
// that reads as a header, tight padding.
function addCardGrid(slide, item, density = "comfortable") {
  const style = L.card.style[density] ?? L.card.style.comfortable;
  const pad = L.card;
  item.cards.forEach((card, index) => {
    const box = item.card_boxes[index];
    if (!box) return;
    // Flat, square, lightly bordered, no fill: a card is a grouping device, not
    // a floating panel.
    const frame = slide.shapes.add({
      geometry: "rect",
      position: { left: box.left, top: box.top, width: box.width, height: box.height },
      fill: theme.surface,
      line: { style: "solid", fill: theme.rule, width: 1 },
    });
    frame.name = "structure:card";
    const textWidth = box.width - 2 * pad.padding_x;
    const left = box.left + pad.padding_x;
    let y = box.top + pad.padding_y;
    const bottom = box.top + box.height - pad.padding_y;

    if (card.title) {
      const lines = Math.max(1, Math.ceil(card.title.length / charsPerLine(style.title, textWidth)));
      const height = Math.ceil(lines * style.title * 1.28);
      textbox(slide, card.title, { left, top: y, width: textWidth, height },
        { fontSize: style.title, bold: true, color: theme.primary });
      y += height + style.line_gap;
    }
    if (card.badges?.length) {
      const height = Math.ceil(style.badge * 1.28);
      textbox(slide, card.badges.join("  ·  "), { left, top: y, width: textWidth, height },
        { fontSize: style.badge, bold: true, color: theme.muted });
      y += height + style.line_gap;
    }
    for (const paragraph of card.paragraphs ?? []) {
      const heading = paragraph.kind === "heading";
      const fontSize = heading ? style.badge : style.body;
      const lines = Math.max(1, Math.ceil(paragraph.text.length / charsPerLine(fontSize, textWidth)));
      const height = Math.ceil(lines * fontSize * 1.28);
      if (y + height > bottom) break;   // the planner sized this; never spill the box
      textbox(slide, paragraph.text, { left, top: y, width: textWidth, height }, {
        fontSize,
        bold: heading,
        color: heading ? theme.ink : theme.muted,
      });
      y += height + style.line_gap;
    }
  });
}

// The source list. Slides carry only [n] markers; the full strings live here,
// which is the one place the design spec allows them — and the only place the
// OOXML auditor exempts from its citation checks.
function addReferences(slide, item) {
  const style = L.reference;
  const entries = item.entries ?? [];
  const columns = entries.length > style.two_column_threshold ? 2 : 1;
  const width = Math.floor((L.content_width - (columns - 1) * style.column_gap) / columns);
  const perColumn = Math.ceil(entries.length / columns);
  const lineHeight = Math.ceil(style.font * 1.28);

  entries.forEach((entry, index) => {
    const column = Math.floor(index / perColumn);
    const row = index % perColumn;
    const left = L.margin_left + column * (width + style.column_gap);
    const top = L.content.top + row * (lineHeight + style.line_gap);
    if (top + lineHeight > L.content.bottom) return;
    textbox(slide, `[${entry.label ?? entry.index}]  ${entry.text}`,
      { left, top, width, height: lineHeight },
      { fontSize: style.font, color: theme.muted });
  });
}

// A grid of share-of-total charts. Each is a native pie so it stays editable.
function addChartGrid(slide, item) {
  item.charts.forEach((chart, index) => {
    const box = item.chart_boxes[index];
    if (!box) return;
    if (chart.title) {
      textbox(slide, chart.title, { left: box.left, top: box.top, width: box.width, height: 26 },
        { fontSize: 13, bold: true, color: theme.ink });
    }
    addChart(slide, chart, {
      left: box.left, top: box.top + 30,
      width: box.width, height: box.height - 30,
    });
  });
}

// The commentary column beside a chart. It reuses the same banded rows the rest
// of the deck uses — measured against the narrow width, and against the same
// model report_pptx/layout.prose_block_height uses to decide it fits.
function addSideParagraphs(slide, paragraphs, density = "comfortable") {
  const style = L.paragraph[density] ?? L.paragraph.comfortable;
  drawProseBox(slide, paragraphs, style, {
    left: L.margin_left, top: L.content.top, width: L.chart.text_width,
  });
}

// Prose inside an arbitrary box: measured at the width the type will actually
// wrap at, then drawn with the table vocabulary at the box's own left edge.
function drawProseBox(slide, paragraphs, style, box) {
  const rows = measureProse(paragraphs, style, { width: box.width - 2 * L.prose.inset_x });
  drawProseRows(slide, rows, box.top, style, {
    banded: paragraphs.length > 1, width: box.width, left: box.left,
  });
}

function numericSeries(chart, categories) {
  return chart.series.filter((series) => series.role !== "range").map((series, seriesIndex) => {
    const alignedPoints = categories.map((category, idx) => {
      const point = chart.categories.length ? series.points[idx] : series.points.find((candidate) => candidate.category === category);
      return point ?? null;
    });
    const lastNumericIndex = alignedPoints.findLastIndex((point) => point?.value != null);
    return {
    name: series.name,
    values: alignedPoints.map((point) => point?.value ?? null),
    fill: theme.chart_colors[seriesIndex % theme.chart_colors.length],
    line: { style: series.dash_style ? "dashed" : "solid", fill: theme.chart_colors[seriesIndex % theme.chart_colors.length], width: 3 },
    marker: { symbol: "circle", size: 7 },
    points: categories.flatMap((category, idx) => {
      const point = chart.categories.length ? series.points[idx] : series.points.find((candidate) => candidate.category === category);
      if (!point) return [];
      const fill = point.value < 0 ? theme.negative : point.is_total ? theme.primary : theme.chart_colors[(seriesIndex + idx) % theme.chart_colors.length];
      return [{ idx, fill }];
    }),
    dataLabelOverrides: chart.kind === "waterfall" ? [] : alignedPoints.flatMap((point, idx) => {
      if (point?.display) return [{ idx, text: point.display, showValue: false, position: "outEnd" }];
      return [];
    }),
  }});
}

// The library insets the plot area from the chart shape by a fixed amount for
// axis labels and the legend, so the overlay plot is derived from wherever the
// chart was actually placed rather than from hard-coded coordinates.
function plotBox(position, insets) {
  return {
    left: position.left + insets.left,
    top: position.top + insets.top,
    right: position.left + position.width - insets.right,
    bottom: position.top + position.height - insets.bottom,
  };
}

function addScenarioCallouts(slide, chart, position) {
  const visibleSeries = chart.series.filter((series) => series.role !== "range");
  const values = visibleSeries.flatMap((series) => series.points.map((point) => point.value).filter((value) => value != null));
  const axisMax = Math.max(10, Math.ceil(Math.max(...values) / 10) * 10);
  const plot = plotBox(position, L.chart.scenario_plot_insets);
  const step = (plot.right - plot.left) / chart.categories.length;
  const abbreviations = { "Downside": "Down", "Base case": "Base", "Upside": "Up", "Management plan": "Mgmt" };

  for (let categoryIndex = 0; categoryIndex < chart.categories.length; categoryIndex++) {
    const pointX = plot.left + step * (categoryIndex + 0.5);
    const candidates = [];
    for (const [seriesIndex, series] of visibleSeries.entries()) {
      const point = series.points[categoryIndex];
      if (point?.value == null) continue;
      const pointY = plot.bottom - (point.value / axisMax) * (plot.bottom - plot.top);
      candidates.push({ series, seriesIndex, point, pointY, top: pointY - 11 });
    }
    candidates.sort((a, b) => a.top - b.top);
    for (let index = 1; index < candidates.length; index++) {
      candidates[index].top = Math.max(candidates[index].top, candidates[index - 1].top + 25);
    }
    const excess = candidates.length ? Math.max(0, candidates.at(-1).top + 22 - plot.bottom) : 0;
    if (excess) for (const candidate of candidates) candidate.top -= excess;
    // Shifting the stack up to clear the plot floor can push the topmost label
    // out of the chart's own box, which a shortened chart makes reachable. Pin
    // it back to the top edge and re-space downwards from there.
    for (let index = 0; index < candidates.length; index++) {
      candidates[index].top = Math.max(
        candidates[index].top,
        index ? candidates[index - 1].top + 25 : position.top,
      );
    }

    for (const candidate of candidates) {
      const color = theme.chart_colors[candidate.seriesIndex % theme.chart_colors.length];
      const text = `${abbreviations[candidate.series.name] ?? candidate.series.name} $${candidate.point.value.toFixed(1)}M`;
      const spec = L.chart.overlay_label;
      // Sized to its own text, and flipped to whichever side has room, so the
      // callouts survive a narrower plot instead of running off the chart.
      const labelWidth = overlayLabelWidth(text);
      const flip = pointX + spec.gap + labelWidth > position.left + position.width;
      const labelLeft = flip ? pointX - spec.gap - labelWidth : pointX + spec.gap;
      const anchorX = flip ? pointX - 3 : pointX + 3;
      const labelCenterY = candidate.top + spec.height / 2;
      slide.shapes.add({
        geometry: "line",
        position: {
          left: Math.min(anchorX, flip ? labelLeft + labelWidth : labelLeft),
          top: Math.min(candidate.pointY, labelCenterY),
          width: Math.abs((flip ? labelLeft + labelWidth : labelLeft) - anchorX),
          height: Math.abs(labelCenterY - candidate.pointY),
        },
        fill: "none",
        line: { style: "solid", fill: color, width: 1 },
      });
      const label = slide.shapes.add({
        geometry: "textbox",
        position: { left: labelLeft, top: candidate.top, width: labelWidth, height: spec.height },
        fill: theme.background,
        line: { fill: "none", width: 0 },
      });
      label.text = text;
      label.text.style = {
        typeface: family, fontSize: spec.font, bold: true, color, autoFit: "none",
        insets: { top: 0, bottom: 0, left: 0, right: 0 },
        alignment: flip ? "right" : "left",
      };
    }
  }
}

function addBridgeLabels(slide, chart, position) {
  const categories = [...new Set(chart.series.flatMap((series) => series.points.map((point) => point.category).filter(Boolean)))];
  const values = chart.series.flatMap((series) => series.points.map((point) => point.value).filter((value) => value != null));
  const axisMin = Math.min(0, Math.floor(Math.min(...values)));
  const axisMax = Math.max(1, Math.ceil(Math.max(...values)));
  const plot = plotBox(position, L.chart.bridge_plot_insets);
  const zeroY = plot.bottom - ((0 - axisMin) / (axisMax - axisMin)) * (plot.bottom - plot.top);
  const step = (plot.right - plot.left) / categories.length;
  for (const series of chart.series) {
    for (const point of series.points) {
      if (point.value == null || !point.category) continue;
      const categoryIndex = categories.indexOf(point.category);
      const x = plot.left + step * (categoryIndex + 0.5);
      const y = plot.bottom - ((point.value - axisMin) / (axisMax - axisMin)) * (plot.bottom - plot.top);
      // Reserve a full negative-axis band for negative bridge bars. Their value
      // sits above the zero line while the category stays below the bar, which
      // remains stable across PowerPoint, OnlyOffice, and LibreOffice.
      const isNegative = point.value < 0;
      // A bar at the top of a short plot would otherwise carry its label above
      // the chart box, into the gap belonging to whatever sits above it.
      const labelY = Math.max(position.top, isNegative ? zeroY - 30 : y - 27);
      if (!isNegative) {
        slide.shapes.add({
          geometry: "line",
          position: { left: x, top: y - 8, width: 1, height: 8 },
          fill: "none",
          line: { style: "solid", fill: theme.primary, width: 1 },
        });
      }
      const text = point.display || `${point.value.toFixed(1)}`;
      const labelWidth = overlayLabelWidth(text);
      const label = slide.shapes.add({
        geometry: "textbox",
        position: { left: x - labelWidth / 2, top: labelY, width: labelWidth, height: 20 },
        fill: theme.background,
        line: { fill: "none", width: 0 },
      });
      label.text = text;
      label.text.style = { typeface: family, fontSize: 12, bold: true, color: isNegative ? theme.negative : theme.ink, alignment: "center", autoFit: "none", insets: { top: 0, bottom: 0, left: 0, right: 0 } };
    }
  }
}

function addChart(slide, chart, position = { left: L.chart.left, top: L.chart.top, width: L.chart.width, height: L.chart.height }) {
  const sourceKind = chart.kind;
  let type = chart.kind;
  if (type === "range_line") type = "line";
  if (type === "waterfall" || type === "column") type = "bar";

  if (type === "pie") {
    // Share-of-total data: one series, no axes, colours carried per slice.
    const points = chart.series[0]?.points ?? [];
    const categories = points.map((point, index) => point.category || `Item ${index + 1}`);
    const native = slide.charts.add("pie", {
      position,
      categories,
      series: [{
        name: chart.series[0]?.name ?? "Share",
        values: points.map((point) => point.value ?? 0),
        points: points.flatMap((point, idx) =>
          point.color ? [{ idx, fill: point.color }] : [{ idx, fill: theme.chart_colors[idx % theme.chart_colors.length] }]),
      }],
      hasLegend: true,
      legend: { position: "bottom", overlay: false, textStyle: { typeface: family, fontSize: 11, fill: theme.muted } },
      // Outside the slice: a label sitting on a dark slice in the source's own
      // palette is unreadable, and the legend already names the slices.
      dataLabels: { showValue: true, position: "outEnd", textStyle: { typeface: family, fontSize: 11, bold: true, fill: theme.ink } },
      chartFill: theme.background,
      plotAreaFill: theme.background,
    });
    applyPresentationChartFont(native, { fontFamily: family });
    return native;
  }
  const categories = chart.categories.length
    ? chart.categories
    : [...new Set(chart.series.flatMap((series) => series.points.map((point) => point.category).filter(Boolean)))];
  const series = numericSeries(chart, categories);
  const isBar = type === "bar" || type === "column";
  const isWaterfall = chart.kind === "waterfall";
  const displayCategories = isWaterfall
    ? categories.map((category) => ({
        "Non-recurring income & expense": "Non-recurring items",
        "Sales and cost corrections": "Sales/cost corrections",
        "Cash to accrual adjustments": "Cash/accrual adjustment",
      })[category] ?? category)
    : categories;
  const hasLegend = chart.kind === "range_line" || series.length > 1;
  const config = {
    position,
    categories: displayCategories,
    series,
    hasLegend,
    legend: { position: "bottom", overlay: false, textStyle: { typeface: family, fontSize: 12, fill: theme.muted } },
    xAxis: { textStyle: { typeface: family, fontSize: 12, fill: theme.muted }, line: { style: "solid", fill: theme.rule, width: 1 }, majorGridlines: null },
    yAxis: { textStyle: { typeface: family, fontSize: 11, fill: theme.muted }, majorGridlines: { style: "solid", fill: theme.rule, width: 1 } },
    chartFill: theme.background,
    plotAreaFill: theme.background,
    displayBlanksAs: "gap",
  };
  if (chart.y_axis_title) config.yAxis.title = chart.y_axis_title;
  if (chart.y_axis_format) {
    config.yAxis.numberFormatCode = chart.y_axis_format.includes("{value}")
      ? (chart.kind === "range_line" ? '$0.0"M"' : "0.0")
      : chart.y_axis_format;
  }
  if (isWaterfall) {
    config.hasLegend = false;
    config.xAxis.tickLabelPosition = "low";
    config.yAxis.min = -1;
    config.yAxis.max = 5;
    config.yAxis.majorUnit = 1;
    config.dataLabels = { showValue: false, textStyle: { typeface: family, fontSize: 11, bold: true, fill: theme.ink } };
    config.barOptions = { direction: "column", grouping: "clustered", gapWidth: 55, varyColors: series.length === 1 };
  } else if (isBar) {
    config.barOptions = { direction: isWaterfall ? "column" : sourceKind === "bar" ? "bar" : "column", grouping: "clustered", gapWidth: 55, varyColors: series.length === 1 };
    config.dataLabels = { showValue: true, position: "outEnd", textStyle: { typeface: family, fontSize: 11, bold: true, fill: theme.ink } };
  } else {
    config.dataLabels = { showValue: false, textStyle: { typeface: family, fontSize: 10, fill: theme.ink } };
  }
  const native = slide.charts.add(type, config);
  applyPresentationChartFont(native, { fontFamily: family });
  return native;
}

function addTable(slide, item, box = null) {
  const values = [
    item.columns.map((column) => column.title),
    ...item.rows.map((row) => item.columns.map((column) => row[column.key]?.plain_text ?? "")),
  ];
  const tracks = item.columns.map((column) => fr(column.layout_weight ?? 1));
  const rowHeights = item.row_heights ?? item.rows.map(() => 62);
  const headerHeight = item.header_height ?? L.table.header_font * 2;
  const cellInsets = { top: L.table.inset.y, bottom: L.table.inset.y, left: L.table.inset.x, right: L.table.inset.x };
  const top = box?.top ?? item.table_top ?? L.table.top;
  const left = box?.left ?? L.margin_left;
  const width = box?.width ?? L.content_width;
  const table = slide.tables.add({
    rows: values.length, columns: item.columns.length,
    left, top, width,
    height: Math.min(L.content.bottom - top, headerHeight + rowHeights.reduce((sum, height) => sum + height, 0)),
    columnTracks: tracks, values,
  });
  // A consulting table: navy header type over a light fill, a strong rule under
  // the header, and subtle horizontal separators. No cell-by-cell gridlines and
  // no heavy banding — the structure comes from alignment and the separators.
  // applyBorders only understands per-edge keys (outside / inside /
  // insideHorizontal / …); a flat {style, fill, width} is silently ignored.
  table.styleOptions = { headerRow: true, bandedRows: false, firstColumn: false };
  table.borders.assign({
    outside: { fill: "none", width: 0 },
    insideVertical: { fill: "none", width: 0 },
    insideHorizontal: { style: "solid", fill: theme.rule, width: 1 },
  });
  table.rows[0].height = headerHeight;
  rowHeights.forEach((height, index) => { table.rows[index + 1].height = height; });
  for (let column = 0; column < item.columns.length; column++) {
    const cell = table.getCell(0, column);
    cell.fill = theme.band;
    cell.text.style = {
      typeface: family, fontSize: L.table.header_font, bold: true,
      color: theme.primary, insets: cellInsets,
      alignment: item.columns[column].align ?? "left",
    };
  }
  for (let row = 1; row < values.length; row++) {
    for (let column = 0; column < item.columns.length; column++) {
      const cell = table.getCell(row, column);
      cell.fill = theme.surface;
      cell.text.style = {
        typeface: family, fontSize: L.table.body_font, color: theme.ink,
        insets: cellInsets,
        // The identifying first column carries the row, so it reads bold.
        bold: column === 0,
        alignment: item.columns[column].align ?? "left",
      };
    }
  }
  // The rule under the header is drawn rather than set as a cell border: a
  // table cell does not expose a borders handle.
  const headerRule = slide.shapes.add({
    geometry: "rect",
    position: { left, top: top + headerHeight - 1, width, height: 1 },
    fill: theme.rule_strong, line: { fill: "none", width: 0 },
  });
  headerRule.name = "structure:table-header-rule";
  return table;
}

for (const [zeroIndex, item] of slidesToRender.entries()) {
  console.error(`RENDER_SLIDE: ${zeroIndex + 1} ${item.kind} ${item.title}`);
  const slide = presentation.slides.add();
  const slideNumber = zeroIndex + 1;
  if (item.kind === "cover") {
    slide.background.fill = theme.ink;
    const rail = slide.shapes.add({
      geometry: "rect",
      position: { left: L.margin_left, top: 102, width: 10, height: 392 },
      fill: theme.accent, line: { fill: "none", width: 0 },
    });
    rail.name = "structure:cover-rail";
    textbox(slide, item.title, { left: L.margin_left + 40, top: 188, width: 1000, height: 150 }, { fontSize: 48, bold: true, color: "#FFFFFF" });
    textbox(slide, item.subtitle, { left: L.margin_left + 40, top: 356, width: 760, height: 46 }, { fontSize: 22, color: "#C3D0E0" });
  } else if (item.kind === "chart" || item.kind === "chart_text") {
    baseSlide(slide, item.title, item.section);
    let position = { left: L.chart.left, top: L.chart.top, width: L.chart.width, height: L.chart.height };
    if (item.kind === "chart_text") {
      // Commentary down the left, chart taking the rest at full band height.
      addSideParagraphs(slide, item.paragraphs ?? [], item.density ?? "comfortable");
      const left = L.margin_left + L.chart.text_width + L.chart.text_gap;
      position = {
        left, top: L.content.top,
        width: L.canvas.width - left - L.margin_left,
        height: L.content.bottom - L.content.top,
      };
    } else if (item.chart_top) {
      // Intro prose above the chart; the chart gives up the space it uses.
      addProseStrip(slide, item.paragraphs ?? []);
      position = {
        left: L.chart.left, top: item.chart_top,
        width: L.chart.width, height: L.content.bottom - item.chart_top,
      };
    }
    addChart(slide, item.chart, position);
    if (item.chart.kind === "range_line") addScenarioCallouts(slide, item.chart, position);
    if (item.chart.kind === "waterfall") addBridgeLabels(slide, item.chart, position);
    chartOwners.push(slideNumber);
  } else if (item.kind === "stack") {
    // A composite slide: the planner resolved a box per block, so this is pure
    // painting. Each block reuses the same drawing primitive it would get on a
    // slide of its own, which is what keeps the vocabulary identical whether an
    // exhibit is alone or sharing.
    baseSlide(slide, item.title, item.section);
    for (const block of item.blocks) {
      // An exhibit that arrived under its own title keeps it as a label, whose
      // height the planner already reserved inside the block's box.
      let box = block.box;
      if (block.label) {
        textbox(slide, block.label,
          { left: box.left, top: box.top, width: box.width, height: L.stack.label_height - 4 },
          { fontSize: L.stack.label_font, bold: true, color: theme.primary });
        box = { ...box, top: box.top + L.stack.label_height, height: box.height - L.stack.label_height };
      }
      if (block.kind === "prose") {
        const style = L.paragraph[block.density ?? "comfortable"] ?? L.paragraph.comfortable;
        drawProseBox(slide, block.paragraphs, style, box);
      } else if (block.kind === "table") {
        addTable(slide, block, box);
        if (!tableOwners.includes(slideNumber)) tableOwners.push(slideNumber);
      } else if (block.kind === "chart") {
        addChart(slide, block.chart, box);
        if (block.chart.kind === "range_line") addScenarioCallouts(slide, block.chart, box);
        if (block.chart.kind === "waterfall") addBridgeLabels(slide, block.chart, box);
        if (!chartOwners.includes(slideNumber)) chartOwners.push(slideNumber);
      }
    }
  } else if (item.kind === "references") {
    baseSlide(slide, item.title);
    addReferences(slide, item);
  } else if (item.kind === "cards") {
    baseSlide(slide, item.title);
    addCardGrid(slide, item, item.density ?? "comfortable");
  } else if (item.kind === "chart_grid") {
    baseSlide(slide, item.title);
    if (item.paragraphs?.length) addProseStrip(slide, item.paragraphs);
    addChartGrid(slide, item);
    chartOwners.push(slideNumber);
  } else if (item.kind === "table") {
    baseSlide(slide, item.title);
    if (item.paragraphs?.length) addProseStrip(slide, item.paragraphs);
    addTable(slide, item);
    tableOwners.push(slideNumber);
  } else if (item.kind === "recommendations") {
    baseSlide(slide, item.title);
    let y = 168;
    for (const [index, entry] of item.items.entries()) {
      textbox(slide, String(index + 1).padStart(2, "0"), { left: 76, top: y + 2, width: 52, height: 32 }, { fontSize: 13, bold: true, color: theme.primary });
      textbox(slide, entry.title, { left: 132, top: y, width: 1016, height: 34 }, { fontSize: 20, bold: true });
      textbox(slide, entry.text, { left: 132, top: y + 42, width: 1016, height: 154 }, { fontSize: 23, color: theme.muted });
      y += 220;
    }
  } else {
    baseSlide(slide, item.title);
    addParagraphs(slide, item.paragraphs ?? [], L.content.top, item.density ?? "comfortable");
  }
  if (slideNumber > 1) addFooter(slide, slideNumber);
  addNotes(slide, item.notes);
  const preview = await presentation.export({ slide, format: "png", scale: 1 });
  await fs.writeFile(path.join(TMP_DIR, `slide-${String(slideNumber).padStart(3, "0")}.png`), new Uint8Array(await preview.arrayBuffer()));
  const layout = await slide.export({ format: "layout" });
  await fs.writeFile(path.join(TMP_DIR, `slide-${String(slideNumber).padStart(3, "0")}.layout.json`), await layout.text());
}

const stagingDir = path.join(WORKSPACE_DIR, ".codex-finalizer");
await fs.mkdir(stagingDir, { recursive: true });
await fs.mkdir(path.dirname(FINAL_PPTX), { recursive: true });
const candidatePath = path.join(stagingDir, "phase2-candidate.pptx");
console.error("EXPORT_CANDIDATE");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);
console.error("FINALIZE_CANDIDATE");
const result = await finalizePresentation({
  workspaceDir: WORKSPACE_DIR,
  candidatePath,
  finalPath: FINAL_PPTX,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu", "12192000,6858000",
    "--validate-heading-fit",
    ...tableOwners.flatMap((number) => ["--require-native-table-slide", String(number)]),
  ],
  explicitTotalSlideCount: slidesToRender.length,
  requiredNativeTableOwnerSlides: tableOwners,
  requiredNativeChartOwnerSlides: chartOwners,
  materializeLiteralChartWorkbooks: true,
  nativeChartTargetApplication: "powerpoint",
  fontPolicy: { basis: "design", families: [family] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, `${path.basename(FINAL_PPTX)}.validation.json`),
});
await fs.writeFile(path.join(TMP_DIR, "render-result.json"), JSON.stringify({
  slideCount: slidesToRender.length,
  chartOwners,
  tableOwners,
  chartFallbacks: slidesToRender.flatMap((slide) => {
    const charts = slide.kind === "stack"
      ? (slide.blocks ?? []).filter((block) => block.kind === "chart").map((block) => block.chart)
      : (slide.chart ? [slide.chart] : []);
    return charts
      .filter((chart) => ["waterfall", "range_line"].includes(chart.kind))
      .map((chart) => ({ slideId: slide.id, sourceKind: chart.kind, renderedKind: chart.kind === "waterfall" ? "column" : "line" }));
  }),
  finalPath: result.finalPath ?? FINAL_PPTX,
}, null, 2));
