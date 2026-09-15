from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


@dataclass(slots=True)
class SourceRef:
    json_pointer: str
    node_id: str | None = None
    output_index: int | None = None


@dataclass(slots=True)
class Diagnostic:
    code: str
    severity: Literal["info", "warning", "error", "fatal"]
    message: str
    source: SourceRef | None = None
    recoverable: bool = True
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Citation:
    id: str
    local_id: str
    url: str
    source_scope_id: str
    restricted: bool = False


@dataclass(slots=True)
class Paragraph:
    text: str
    kind: Literal["body", "bullet", "heading", "note"] = "body"
    level: int = 0
    citation_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class TableColumn:
    key: str
    title: str
    alignment: Literal["left", "center", "right"] = "left"
    inferred_type: Literal["text", "currency", "percent", "number", "mixed"] = "text"


@dataclass(slots=True)
class TableCell:
    raw: Any
    display_value: str
    plain_text: str
    numeric_value: float | None = None
    citation_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DataPoint:
    category: str | None = None
    value: float | None = None
    low: float | None = None
    high: float | None = None
    display: str | None = None
    color: str | None = None
    is_total: bool = False


@dataclass(slots=True)
class ChartSeries:
    id: str
    name: str
    role: Literal["value", "line", "range", "total", "helper"]
    points: list[DataPoint]
    color: str | None = None
    dash_style: str | None = None


@dataclass(slots=True)
class ChartModel:
    kind: Literal["bar", "column", "line", "waterfall", "range_line", "unknown"]
    title: str | None
    categories: list[str]
    series: list[ChartSeries]
    y_axis_title: str | None = None
    y_axis_format: str | None = None
    legend_enabled: bool = True
    source_options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ContentBlock:
    id: str
    kind: Literal["narrative", "recommendation", "table", "chart", "evidence", "unknown"]
    title: str | None
    source: SourceRef
    citation_ids: list[str] = field(default_factory=list)
    paragraphs: list[Paragraph] = field(default_factory=list)
    columns: list[TableColumn] = field(default_factory=list)
    rows: list[dict[str, TableCell]] = field(default_factory=list)
    zebra: bool = False
    chart: ChartModel | None = None
    extensions: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SectionModel:
    id: str
    name: str | None
    heading: str | None
    heading_visible: bool
    summary_headline: str | None
    order: tuple[int | None, int | None, int]
    blocks: list[ContentBlock]
    children: list["SectionModel"]
    source: SourceRef
    extensions: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PresentationModel:
    schema_version: str
    report_id: str
    is_sample_report: bool
    sections: list[SectionModel]
    citations: dict[str, Citation]
    diagnostics: list[Diagnostic]


def to_dict(value: Any) -> Any:
    """Convert semantic dataclasses into JSON-serializable structures."""
    return asdict(value)


class ReportLoader:
    def __init__(self, *, max_bytes: int = 20_000_000) -> None:
        self.max_bytes = max_bytes

    def load(self, path: Path) -> dict[str, Any]:
        size = path.stat().st_size
        if size > self.max_bytes:
            raise ValueError(f"Input is {size} bytes; maximum is {self.max_bytes}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise ValueError("JSON root must be an object")
        if not isinstance(value.get("report"), list):
            raise ValueError("JSON root must contain a 'report' array")
        return value


class ReportNormalizer:
    KNOWN_NODE_KEYS = {
        "children", "citations", "cta_to", "display_enabled", "display_properties",
        "display_text", "has_title", "id", "is_beta", "is_dynamic", "is_hidden",
        "name", "nav_group_key", "nav_group_label", "ordering", "output",
        "restricted_citations", "section_slug", "show_citations", "sub_ordering",
        "summary_headline", "tags", "type", "ui_type",
    }
    CITATION_RE = re.compile(r"(?<!\\)\[(\d+)\]")
    NUMBER_RE = re.compile(r"^\s*([+-])?\$?\s*([\d,]+(?:\.\d+)?)\s*([KMB])?\s*(%)?\s*$", re.I)

    def __init__(self, *, max_depth: int = 100) -> None:
        self.max_depth = max_depth
        self.citations: dict[str, Citation] = {}
        self.diagnostics: list[Diagnostic] = []

    def normalize(self, raw: dict[str, Any]) -> PresentationModel:
        self.citations = {}
        self.diagnostics = []
        sections: list[SectionModel] = []
        for index, node in enumerate(raw["report"]):
            section = self._node(node, f"/report/{index}", index, depth=0, inherited={})
            if section is not None:
                sections.append(section)
        sections.sort(key=lambda section: self._sort_key(section.order))
        report_id = sections[0].id if len(sections) == 1 else "report"
        return PresentationModel(
            schema_version="1.0",
            report_id=report_id,
            is_sample_report=bool(raw.get("is_sample_report", False)),
            sections=sections,
            citations=self.citations.copy(),
            diagnostics=self.diagnostics.copy(),
        )

    def _node(
        self,
        node: Any,
        pointer: str,
        source_index: int,
        *,
        depth: int,
        inherited: dict[str, str],
    ) -> SectionModel | None:
        if depth > self.max_depth:
            self._diag("max_depth", "fatal", f"Nesting exceeds {self.max_depth}", pointer, recoverable=False)
            return None
        if not isinstance(node, dict):
            self._diag("invalid_node", "error", "Report node must be an object", pointer)
            return None
        if node.get("is_hidden", False):
            return None

        node_id = str(node.get("id") or self._synthetic_id(pointer))
        scope = self._citation_scope(node_id, node, inherited)
        outputs = node.get("output", [])
        if not isinstance(outputs, list):
            self._diag("invalid_outputs", "error", "Node output must be an array", pointer, node_id)
            outputs = []
        blocks = [
            self._output(output, f"{pointer}/output/{index}", node_id, index, scope)
            for index, output in enumerate(outputs)
        ]

        children_raw = node.get("children", [])
        if not isinstance(children_raw, list):
            self._diag("invalid_children", "error", "Node children must be an array", pointer, node_id)
            children_raw = []
        children: list[SectionModel] = []
        for index, child in enumerate(children_raw):
            normalized = self._node(
                child,
                f"{pointer}/children/{index}",
                index,
                depth=depth + 1,
                inherited=scope,
            )
            if normalized is not None:
                children.append(normalized)
        children.sort(key=lambda section: self._sort_key(section.order))

        extensions = {key: value for key, value in node.items() if key not in self.KNOWN_NODE_KEYS}
        return SectionModel(
            id=node_id,
            name=self._optional_str(node.get("name")),
            heading=self._optional_str(node.get("display_text")),
            heading_visible=bool(node.get("display_enabled", True)),
            summary_headline=self._optional_str(node.get("summary_headline")),
            order=(self._optional_int(node.get("ordering")), self._optional_int(node.get("sub_ordering")), source_index),
            blocks=blocks,
            children=children,
            source=SourceRef(pointer, node_id),
            extensions=extensions,
        )

    def _citation_scope(self, node_id: str, node: dict[str, Any], inherited: dict[str, str]) -> dict[str, str]:
        scope = inherited.copy()
        restricted = node.get("restricted_citations") if isinstance(node.get("restricted_citations"), dict) else {}
        local = node.get("citations")
        if local is None:
            return scope
        if not isinstance(local, dict):
            self._diag("invalid_citations", "warning", "Citations must be an object", f"{node_id}/citations", node_id)
            return scope
        for local_id, url in local.items():
            if not isinstance(url, str):
                self._diag("invalid_citation_url", "warning", f"Citation {local_id} is not a string", f"{node_id}/citations", node_id)
                continue
            global_id = f"{node_id}:{local_id}"
            scope[str(local_id)] = global_id
            self.citations[global_id] = Citation(
                id=global_id,
                local_id=str(local_id),
                url=url,
                source_scope_id=node_id,
                restricted=str(local_id) in restricted,
            )
        return scope

    def _output(
        self,
        output: Any,
        pointer: str,
        node_id: str,
        index: int,
        citation_scope: dict[str, str],
    ) -> ContentBlock:
        source = SourceRef(pointer, node_id, index)
        block_id = f"{node_id}:output:{index}"
        if not isinstance(output, dict):
            self._diag("invalid_output", "error", "Output must be an object", pointer, node_id)
            return ContentBlock(block_id, "unknown", None, source, extensions={"raw": output})

        output_format = output.get("output_format")
        title = self._optional_str(output.get("title"))
        value = output.get("output")
        common_extensions = {
            key: val for key, val in output.items()
            if key not in {"output", "output_format", "output_format_name", "title"}
        }

        if output_format in {"MarkDownSummary", "ReportRecommendation", "MarkDown"}:
            kind = "recommendation" if output_format == "ReportRecommendation" else "narrative"
            paragraphs = self._parse_markdown(str(value or ""), citation_scope, pointer)
            return ContentBlock(
                block_id, kind, title, source,
                citation_ids=self._all_citations(paragraphs),
                paragraphs=paragraphs,
                extensions=common_extensions,
            )

        if output_format == "ReportSegmentCards" and isinstance(value, dict):
            paragraphs: list[Paragraph] = []
            card_titles: list[str] = []
            for card_index, card in enumerate(value.get("cards", [])):
                if not isinstance(card, dict):
                    continue
                card_title = self._optional_str(card.get("title"))
                if card_title:
                    card_titles.append(card_title)
                    paragraphs.append(Paragraph(card_title, "heading"))
                paragraphs.extend(self._parse_markdown(str(card.get("content") or ""), citation_scope, f"{pointer}/output/cards/{card_index}"))
            return ContentBlock(
                block_id, "evidence", title or (card_titles[0] if len(card_titles) == 1 else None), source,
                citation_ids=self._all_citations(paragraphs),
                paragraphs=paragraphs,
                extensions={**common_extensions, "source_columns": value.get("columns")},
            )

        if output_format in {"ReportTable", "ReportTableMarkDownSummary"} and isinstance(value, dict):
            return self._table(block_id, title, source, value, citation_scope, common_extensions)

        if output_format == "ReportChart" and isinstance(value, dict):
            chart = self._chart(value.get("options"), pointer)
            return ContentBlock(block_id, "chart", title or chart.title, source, chart=chart, extensions=common_extensions)

        self._diag("unknown_output_format", "warning", f"Unsupported output format: {output_format!r}", pointer, node_id)
        return ContentBlock(
            block_id, "unknown", title, source,
            paragraphs=self._parse_markdown(str(value or ""), citation_scope, pointer) if isinstance(value, str) else [],
            extensions={**common_extensions, "output_format": output_format, "raw": value},
        )

    def _table(
        self,
        block_id: str,
        title: str | None,
        source: SourceRef,
        value: dict[str, Any],
        citation_scope: dict[str, str],
        extensions: dict[str, Any],
    ) -> ContentBlock:
        raw_columns = value.get("columns", [])
        raw_rows = value.get("dataSource", [])
        if not isinstance(raw_columns, list) or not isinstance(raw_rows, list):
            self._diag("invalid_table", "error", "Table columns and dataSource must be arrays", source.json_pointer, source.node_id)
            raw_columns, raw_rows = [], []
        columns: list[TableColumn] = []
        for col in raw_columns:
            if not isinstance(col, dict):
                continue
            key = str(col.get("dataIndex") or col.get("key") or "")
            alignment = str((col.get("headerStyle") or {}).get("align") or col.get("position") or "left")
            if alignment not in {"left", "center", "right"}:
                alignment = "left"
            samples = [row.get(key) for row in raw_rows if isinstance(row, dict) and key in row]
            columns.append(TableColumn(key, str(col.get("title") or ""), alignment, self._infer_type(samples)))
        rows: list[dict[str, TableCell]] = []
        all_citations: set[str] = set()
        for row_index, raw_row in enumerate(raw_rows):
            if not isinstance(raw_row, dict):
                self._diag("invalid_table_row", "warning", "Table row must be an object", f"{source.json_pointer}/dataSource/{row_index}", source.node_id)
                continue
            row: dict[str, TableCell] = {}
            for column in columns:
                raw_cell = raw_row.get(column.key)
                display = "" if raw_cell is None else self._cell_text(raw_cell)
                paragraphs = self._parse_markdown(display, citation_scope, source.json_pointer)
                citation_ids = self._all_citations(paragraphs)
                all_citations.update(citation_ids)
                row[column.key] = TableCell(raw_cell, display, self._plain_text(display), self._number(display), citation_ids)
            rows.append(row)
        return ContentBlock(
            block_id, "table", title, source,
            citation_ids=sorted(all_citations), columns=columns, rows=rows,
            zebra=bool(value.get("zebra", False)), extensions=extensions,
        )

    def _chart(self, raw_options: Any, pointer: str) -> ChartModel:
        if not isinstance(raw_options, dict):
            self._diag("invalid_chart", "error", "Chart options must be an object", pointer)
            return ChartModel("unknown", None, [], [], source_options={})
        raw_kind = str((raw_options.get("chart") or {}).get("type") or "unknown").lower()
        kind = raw_kind if raw_kind in {"bar", "column", "line", "waterfall"} else "unknown"
        categories = [str(item) for item in ((raw_options.get("xAxis") or {}).get("categories") or [])]
        series: list[ChartSeries] = []
        for series_index, raw_series in enumerate(raw_options.get("series") or []):
            if not isinstance(raw_series, dict):
                continue
            series_type = str(raw_series.get("type") or raw_kind).lower()
            role: Literal["value", "line", "range", "total", "helper"]
            role = "range" if series_type == "arearange" else "line" if series_type == "line" else "value"
            points: list[DataPoint] = []
            for point_index, raw_point in enumerate(raw_series.get("data") or []):
                category = categories[point_index] if point_index < len(categories) else None
                if isinstance(raw_point, bool):
                    point = DataPoint(category=category)
                elif isinstance(raw_point, (int, float)):
                    point = DataPoint(category=category, value=float(raw_point))
                elif isinstance(raw_point, list) and len(raw_point) >= 2:
                    point = DataPoint(category=category, low=self._float(raw_point[0]), high=self._float(raw_point[1]))
                elif isinstance(raw_point, dict):
                    point = DataPoint(
                        category=self._optional_str(raw_point.get("name")) or category,
                        value=self._float(raw_point.get("y")),
                        display=self._optional_str((raw_point.get("custom") or {}).get("display"))
                            or self._optional_str((raw_point.get("dataLabels") or {}).get("format")),
                        color=self._optional_str(raw_point.get("color")),
                        is_total=bool(raw_point.get("isSum", False)),
                    )
                else:
                    point = DataPoint(category=category)
                points.append(point)
            series.append(ChartSeries(
                id=f"series:{series_index}",
                name=str(raw_series.get("name") or f"Series {series_index + 1}"),
                role=role,
                points=points,
                color=self._optional_str(raw_series.get("color")),
                dash_style=self._optional_str(raw_series.get("dashStyle")),
            ))
        if any(item.role == "range" for item in series):
            kind = "range_line"
        return ChartModel(
            kind=kind,
            title=self._optional_str((raw_options.get("title") or {}).get("text")),
            categories=categories,
            series=series,
            y_axis_title=self._optional_str(((raw_options.get("yAxis") or {}).get("title") or {}).get("text")),
            y_axis_format=self._optional_str(((raw_options.get("yAxis") or {}).get("labels") or {}).get("format")),
            legend_enabled=bool((raw_options.get("legend") or {}).get("enabled", True)),
            source_options=raw_options,
        )

    def _parse_markdown(self, text: str, scope: dict[str, str], pointer: str) -> list[Paragraph]:
        paragraphs: list[Paragraph] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            kind: Literal["body", "bullet", "heading", "note"] = "body"
            level = 0
            if line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                line = line[level:].strip()
                kind = "heading"
            elif re.match(r"^[-*+]\s+", line):
                line = re.sub(r"^[-*+]\s+", "", line)
                kind = "bullet"
            citation_ids: list[str] = []
            for match in self.CITATION_RE.finditer(line):
                local_id = match.group(1)
                global_id = scope.get(local_id)
                if global_id:
                    citation_ids.append(global_id)
                else:
                    self._diag("unresolved_citation", "warning", f"Citation [{local_id}] is unresolved", pointer)
            paragraphs.append(Paragraph(self._plain_text(line), kind, level, list(dict.fromkeys(citation_ids))))
        return paragraphs

    @staticmethod
    def _plain_text(text: str) -> str:
        text = text.replace("\\-", "-")
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"(?<!\*)\*([^*]+)\*", r"\1", text)
        text = re.sub(r"(?<!\\)\[(\d+)\]", r"[\1]", text)
        return text.strip()

    def _infer_type(self, values: list[Any]) -> Literal["text", "currency", "percent", "number", "mixed"]:
        kinds: set[str] = set()
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            if "$" in text and self._number(text) is not None:
                kinds.add("currency")
            elif text.endswith("%") and self._number(text) is not None:
                kinds.add("percent")
            elif self._number(text) is not None:
                kinds.add("number")
            else:
                kinds.add("text")
        return next(iter(kinds)) if len(kinds) == 1 else "mixed" if kinds else "text"

    @classmethod
    def _cell_text(cls, raw_cell: Any) -> str:
        if isinstance(raw_cell, dict):
            if "label" in raw_cell or "badges" in raw_cell:
                parts = [str(raw_cell.get("label") or "")]
                parts.extend(str(badge.get("title", "")) for badge in raw_cell.get("badges") or [] if isinstance(badge, dict))
                if raw_cell.get("rating"):
                    parts.append(str(raw_cell["rating"]))
                return " · ".join(part for part in parts if part)
            return ", ".join(f"{key}: {val}" for key, val in raw_cell.items())
        return str(raw_cell)

    def _number(self, value: str) -> float | None:
        match = self.NUMBER_RE.match(value.replace("**", ""))
        if not match:
            return None
        sign, number, magnitude, _percent = match.groups()
        result = float(number.replace(",", ""))
        result *= {None: 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[magnitude.upper() if magnitude else None]
        return -result if sign == "-" else result

    @staticmethod
    def _float(value: Any) -> float | None:
        if isinstance(value, bool) or value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _all_citations(paragraphs: list[Paragraph]) -> list[str]:
        return sorted({citation for paragraph in paragraphs for citation in paragraph.citation_ids})

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    @staticmethod
    def _synthetic_id(pointer: str) -> str:
        return "node:" + pointer.strip("/").replace("/", ":")

    @staticmethod
    def _sort_key(order: tuple[int | None, int | None, int]) -> tuple[int, int, int]:
        first, second, index = order
        return (first if first is not None else 2**31, second if second is not None else 2**31, index)

    def _diag(
        self,
        code: str,
        severity: Literal["info", "warning", "error", "fatal"],
        message: str,
        pointer: str,
        node_id: str | None = None,
        *,
        recoverable: bool = True,
    ) -> None:
        self.diagnostics.append(Diagnostic(code, severity, message, SourceRef(pointer, node_id), recoverable))


@dataclass(slots=True)
class ValidationReport:
    diagnostics: list[Diagnostic]

    @property
    def is_valid(self) -> bool:
        return not any(item.severity in {"error", "fatal"} for item in self.diagnostics)


class SemanticValidator:
    HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")

    def validate(self, model: PresentationModel) -> ValidationReport:
        diagnostics = list(model.diagnostics)
        seen: set[str] = set()
        for section in self._sections(model.sections):
            self._unique(section.id, section.source, seen, diagnostics)
            for block in section.blocks:
                self._unique(block.id, block.source, seen, diagnostics)
                for citation_id in block.citation_ids:
                    if citation_id not in model.citations:
                        diagnostics.append(Diagnostic("missing_citation", "error", f"Unknown citation {citation_id}", block.source))
                if block.kind == "table":
                    self._table(block, diagnostics)
                elif block.kind == "chart" and block.chart:
                    self._chart(block, diagnostics)
        return ValidationReport(diagnostics)

    def _sections(self, sections: list[SectionModel]):
        for section in sections:
            yield section
            yield from self._sections(section.children)

    @staticmethod
    def _unique(value: str, source: SourceRef, seen: set[str], diagnostics: list[Diagnostic]) -> None:
        if value in seen:
            diagnostics.append(Diagnostic("duplicate_id", "error", f"Duplicate ID: {value}", source))
        seen.add(value)

    @staticmethod
    def _table(block: ContentBlock, diagnostics: list[Diagnostic]) -> None:
        keys = {column.key for column in block.columns}
        if len(keys) != len(block.columns):
            diagnostics.append(Diagnostic("duplicate_table_column", "error", "Table has duplicate column keys", block.source))
        for index, row in enumerate(block.rows):
            if set(row) != keys:
                diagnostics.append(Diagnostic("table_row_mismatch", "error", f"Table row {index} does not match columns", block.source))

    def _chart(self, block: ContentBlock, diagnostics: list[Diagnostic]) -> None:
        chart = block.chart
        assert chart is not None
        if chart.kind == "unknown":
            diagnostics.append(Diagnostic("unknown_chart_type", "error", "Chart type is unsupported", block.source))
        for series in chart.series:
            if chart.categories and len(series.points) != len(chart.categories):
                diagnostics.append(Diagnostic(
                    "chart_length_mismatch", "error",
                    f"Series {series.name!r} has {len(series.points)} points for {len(chart.categories)} categories",
                    block.source,
                ))
            for point in series.points:
                if point.low is not None and point.high is not None and point.low > point.high:
                    diagnostics.append(Diagnostic("invalid_range", "error", "Chart range low exceeds high", block.source))
                if point.color and not self.HEX_COLOR.match(point.color):
                    diagnostics.append(Diagnostic("invalid_color", "warning", f"Invalid point color {point.color!r}", block.source))
        if chart.kind == "waterfall":
            self._waterfall(block, diagnostics)

    @staticmethod
    def _waterfall(block: ContentBlock, diagnostics: list[Diagnostic]) -> None:
        chart = block.chart
        assert chart is not None
        for series in chart.series:
            running = 0.0
            for point in series.points:
                if point.value is None:
                    continue
                if point.is_total:
                    if abs(point.value - running) > max(0.001, abs(point.value) * 0.005):
                        diagnostics.append(Diagnostic(
                            "waterfall_total_mismatch", "warning",
                            f"Waterfall total {point.value:g} differs from calculated {running:g}",
                            block.source,
                        ))
                    running = point.value
                else:
                    running += point.value
