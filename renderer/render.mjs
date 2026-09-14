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
const family = resolvePresentationFont({ fontFamily: "Calibri" });
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
    ...style,
  };
  return shape;
}

function baseSlide(slide, title, section = null) {
  slide.background.fill = theme.background;
  if (section) textbox(slide, section.toUpperCase(), { left: 72, top: 38, width: 700, height: 22 }, { fontSize: 12, bold: true, color: theme.primary });
  textbox(slide, title, { left: 72, top: section ? 66 : 54, width: 1120, height: 70 }, { fontSize: 32, bold: true, autoFit: "shrinkText" });
  const rule = slide.shapes.add({ geometry: "rect", position: { left: 72, top: 132, width: 1136, height: 2 }, fill: theme.rule, line: { fill: "none", width: 0 } });
  rule.name = "title-rule";
}

function addNotes(slide, notes) {
  if (notes) slide.speakerNotes.textFrame.setText(notes);
}

function addFooter(slide, index) {
  textbox(slide, String(index).padStart(2, "0"), { left: 1150, top: 676, width: 58, height: 18 }, { fontSize: 10, color: theme.muted, alignment: "right" });
}

function addParagraphs(slide, paragraphs, top = 168, density = "comfortable") {
  const densityStyle = {
    comfortable: { body: 23, lead: 25, bodyChars: 90, leadChars: 78, gap: 28 },
    compact: { body: 21, lead: 23, bodyChars: 98, leadChars: 84, gap: 20 },
    dense: { body: 19, lead: 21, bodyChars: 108, leadChars: 92, gap: 16 },
  }[density] ?? { body: 23, lead: 25, bodyChars: 90, leadChars: 78, gap: 28 };
  let y = top;
  for (const paragraph of paragraphs) {
    const isLead = paragraph.kind === "lead";
    const prefix = paragraph.kind === "bullet" ? "•  " : "";
    const fontSize = isLead ? densityStyle.lead : densityStyle.body;
    const charsPerLine = isLead ? densityStyle.leadChars : densityStyle.bodyChars;
    const lineCount = Math.max(1, Math.ceil((prefix.length + paragraph.text.length) / charsPerLine));
    const height = Math.ceil(lineCount * fontSize * 1.28 + 8);
    textbox(slide, prefix + paragraph.text, { left: 96, top: y, width: 1064, height }, {
      fontSize, bold: isLead, color: isLead ? theme.ink : theme.muted,
    });
    y += height + densityStyle.gap;
  }
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

function addScenarioCallouts(slide, chart) {
  const visibleSeries = chart.series.filter((series) => series.role !== "range");
  const values = visibleSeries.flatMap((series) => series.points.map((point) => point.value).filter((value) => value != null));
  const axisMax = Math.max(10, Math.ceil(Math.max(...values) / 10) * 10);
  const plot = { left: 168, top: 167, right: 1172, bottom: 570 };
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

    for (const candidate of candidates) {
      const color = theme.chart_colors[candidate.seriesIndex % theme.chart_colors.length];
      const labelLeft = pointX + 11;
      const labelCenterY = candidate.top + 11;
      slide.shapes.add({
        geometry: "line",
        position: { left: pointX + 3, top: candidate.pointY, width: labelLeft - pointX - 3, height: labelCenterY - candidate.pointY },
        fill: "none",
        line: { style: "solid", fill: color, width: 1 },
      });
      const label = slide.shapes.add({
        geometry: "textbox",
        position: { left: labelLeft, top: candidate.top, width: 126, height: 22 },
        fill: theme.background,
        line: { fill: "none", width: 0 },
      });
      label.text = `${abbreviations[candidate.series.name] ?? candidate.series.name} $${candidate.point.value.toFixed(1)}M`;
      label.text.style = { typeface: family, fontSize: 11, bold: true, color, autoFit: "none" };
    }
  }
}

function addBridgeLabels(slide, chart) {
  const categories = [...new Set(chart.series.flatMap((series) => series.points.map((point) => point.category).filter(Boolean)))];
  const values = chart.series.flatMap((series) => series.points.map((point) => point.value).filter((value) => value != null));
  const axisMin = Math.min(0, Math.floor(Math.min(...values)));
  const axisMax = Math.max(1, Math.ceil(Math.max(...values)));
  const plot = { left: 148, top: 167, right: 1172, bottom: 589 };
  const step = (plot.right - plot.left) / categories.length;
  for (const series of chart.series) {
    for (const point of series.points) {
      if (point.value == null || !point.category) continue;
      const categoryIndex = categories.indexOf(point.category);
      const x = plot.left + step * (categoryIndex + 0.5);
      const y = plot.bottom - ((point.value - axisMin) / (axisMax - axisMin)) * (plot.bottom - plot.top);
      const labelY = point.value < 0 ? y + 8 : y - 27;
      slide.shapes.add({
        geometry: "line",
        position: { left: x, top: point.value < 0 ? y : y - 8, width: 1, height: 8 },
        fill: "none",
        line: { style: "solid", fill: point.value < 0 ? theme.negative : theme.primary, width: 1 },
      });
      const label = slide.shapes.add({
        geometry: "textbox",
        position: { left: x - 43, top: labelY, width: 86, height: 20 },
        fill: "none",
        line: { fill: "none", width: 0 },
      });
      label.text = point.display || `${point.value.toFixed(1)}`;
      label.text.style = { typeface: family, fontSize: 12, bold: true, color: point.value < 0 ? theme.negative : theme.ink, alignment: "center", autoFit: "none" };
    }
  }
}

function addChart(slide, chart) {
  let type = chart.kind;
  if (type === "range_line") type = "line";
  if (type === "waterfall") type = "bar";
  const categories = chart.categories.length
    ? chart.categories
    : [...new Set(chart.series.flatMap((series) => series.points.map((point) => point.category).filter(Boolean)))];
  const series = numericSeries(chart, categories);
  const isBar = type === "bar" || type === "column";
  const isWaterfall = chart.kind === "waterfall";
  const hasLegend = chart.kind === "range_line" || series.length > 1;
  const config = {
    position: { left: 86, top: 158, width: 1108, height: 476 },
    categories,
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
    config.dataLabels = { showValue: false, textStyle: { typeface: family, fontSize: 11, bold: true, fill: theme.ink } };
    config.barOptions = { direction: "column", grouping: "clustered", gapWidth: 55, varyColors: series.length === 1 };
  } else if (isBar) {
    config.barOptions = { direction: isWaterfall ? "column" : type === "bar" ? "bar" : "column", grouping: "clustered", gapWidth: 55, varyColors: series.length === 1 };
    config.dataLabels = { showValue: true, position: "outEnd", textStyle: { typeface: family, fontSize: 11, bold: true, fill: theme.ink } };
  } else {
    config.dataLabels = { showValue: false, textStyle: { typeface: family, fontSize: 10, fill: theme.ink } };
  }
  const native = slide.charts.add(type, config);
  applyPresentationChartFont(native, { fontFamily: family });
  return native;
}

function addTable(slide, item) {
  const values = [
    item.columns.map((column) => column.title),
    ...item.rows.map((row) => item.columns.map((column) => row[column.key]?.plain_text ?? "")),
  ];
  const tracks = item.columns.map((column) => fr(column.layout_weight ?? 1));
  const rowHeights = item.row_heights ?? item.rows.map(() => 62);
  const table = slide.tables.add({ rows: values.length, columns: item.columns.length, left: 72, top: 164, width: 1136, height: Math.min(472, 58 + rowHeights.reduce((sum, height) => sum + height, 0)), columnTracks: tracks, values });
  table.styleOptions = { headerRow: true, bandedRows: true };
  table.borders.assign({ style: "solid", fill: theme.rule, width: 1 });
  table.rows[0].height = 58;
  rowHeights.forEach((height, index) => { table.rows[index + 1].height = height; });
  for (let column = 0; column < item.columns.length; column++) {
    const cell = table.getCell(0, column);
    cell.fill = theme.primary;
      cell.text.style = { typeface: family, fontSize: 16, bold: true, color: "#FFFFFF", autoFit: "shrinkText" };
  }
  for (let row = 1; row < values.length; row++) {
    for (let column = 0; column < item.columns.length; column++) {
      const cell = table.getCell(row, column);
      cell.fill = row % 2 ? theme.surface : "#F0EEF8";
      cell.text.style = { typeface: family, fontSize: 15, color: theme.ink, autoFit: "shrinkText" };
    }
  }
  return table;
}

for (const [zeroIndex, item] of slidesToRender.entries()) {
  console.error(`RENDER_SLIDE: ${zeroIndex + 1} ${item.kind} ${item.title}`);
  const slide = presentation.slides.add();
  const slideNumber = zeroIndex + 1;
  if (item.kind === "cover") {
    slide.background.fill = theme.ink;
    slide.shapes.add({ geometry: "rect", position: { left: 72, top: 102, width: 12, height: 392 }, fill: theme.secondary, line: { fill: "none", width: 0 } });
    textbox(slide, item.title, { left: 116, top: 188, width: 980, height: 150 }, { fontSize: 48, bold: true, color: "#FFFFFF" });
    textbox(slide, item.subtitle, { left: 118, top: 356, width: 700, height: 46 }, { fontSize: 22, color: "#CFC9F3" });
  } else if (item.kind === "chart") {
    baseSlide(slide, item.title, item.section);
    addChart(slide, item.chart);
    if (item.chart.kind === "range_line") addScenarioCallouts(slide, item.chart);
    if (item.chart.kind === "waterfall") addBridgeLabels(slide, item.chart);
    chartOwners.push(slideNumber);
  } else if (item.kind === "table") {
    baseSlide(slide, item.title);
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
    addParagraphs(slide, item.paragraphs ?? [], 168, item.density ?? "comfortable");
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
  chartFallbacks: slidesToRender.filter((slide) => slide.kind === "chart" && ["waterfall", "range_line"].includes(slide.chart.kind)).map((slide) => ({ slideId: slide.id, sourceKind: slide.chart.kind, renderedKind: slide.chart.kind === "waterfall" ? "column" : "line" })),
  finalPath: result.finalPath ?? FINAL_PPTX,
}, null, 2));
