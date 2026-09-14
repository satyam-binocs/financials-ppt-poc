# JSON-to-PPTX Generation System

Status: proposed design  
Scope: architecture and interfaces only  
Source profiled: `report.json`  

## 1. Purpose

This system converts a recursively nested analytical report JSON into a clean, editable PowerPoint presentation. The source describes report hierarchy, narrative findings, tables, recommendations, citations, and Highcharts-like chart configurations. It does not describe slides directly.

The system must therefore solve two different problems:

1. Preserve the report's facts, hierarchy, display semantics, citations, and native data structures.
2. Design a presentation whose slide boundaries, visual hierarchy, chart treatment, and density suit the content.

The proposed solution separates semantic interpretation from presentation design and file rendering:

```text
report.json
    -> recursive ingestion
    -> normalized presentation model
    -> validation and evidence registry
    -> LLM narrative plan
    -> LLM slide specifications
    -> deterministic native-PPTX rendering
    -> structural and visual validation
    -> bounded repair loop
    -> final .pptx
```

Python owns ingestion, normalization, validation, orchestration, and LLM workflow. A small JavaScript rendering boundary uses `@oai/artifact-tool` to construct the PPTX and native Office charts. Python invokes that renderer with a versioned JSON slide specification. This avoids maintaining two semantic models while following the supported PowerPoint generation path.

## 2. Goals and non-goals

### 2.1 Goals

- Accept report trees with arbitrary nesting depth.
- Respect `is_hidden` and `display_enabled` independently.
- Support known output formats without coupling them to source UI layouts.
- Preserve numbers, units, qualifiers, citations, and source traceability.
- Generate native, editable PowerPoint charts and tables.
- Let an LLM decide narrative flow, slide grouping, content emphasis, and layout family.
- Use deterministic geometry for final placement and file generation.
- Detect overflow, collisions, clipped labels, excessive density, and awkward whitespace.
- Use multimodal review to catch aesthetic problems that geometry alone cannot identify.
- Retry failed slides through a bounded and auditable repair loop.
- Produce useful diagnostics when some content cannot be represented faithfully.

### 2.2 Non-goals for the first version

- A general-purpose PowerPoint editor.
- Pixel-perfect recreation of the source web report.
- Arbitrary user-authored JavaScript or chart callbacks from input JSON.
- Support for every Highcharts option.
- Multiple independent rendering engines.
- Fully autonomous brand discovery from the internet.
- Real-time collaborative editing.
- Continuous learning or model fine-tuning.

## 3. Observed input profile

The inspected `report.json` contains:

- One top-level `section`, named `financials` and displayed as `Financial Overview`.
- Nine `sub_section` children.
- Thirty-eight output blocks.
- Fifteen `MarkDownSummary` outputs.
- Seven `ReportChart` outputs: three bar, three waterfall, and one line chart with an area-range series.
- Four `ReportTable` outputs.
- Six `ReportSegmentCards` outputs.
- Six `ReportRecommendation` outputs.
- Citation dictionaries at section and subsection levels. Values are source URLs, including PDF page fragments.

Known output forms are:

```text
MarkDownSummary      output: string
ReportRecommendation output: string, with a title
ReportTable          output: { columns, dataSource, zebra }
ReportSegmentCards   output: { columns, cards }
ReportChart          output: { options }
```

The source's segment cards contain long analytical prose. They should become evidence blocks, findings, or continuation slides. They should not automatically become dashboard cards.

## 4. Architectural principles

### 4.1 One canonical semantic model

Raw report JSON is parsed once into a presentation intermediate representation, or PIR. All planning, validation, rendering, and traceability use this model. The renderer never reads the raw report directly.

### 4.2 Deterministic facts, probabilistic design

Code controls visibility, ordering, data conversion, arithmetic checks, citations, and object geometry. The LLM controls storyline, grouping, concise wording, layout choice, and aesthetic repair proposals.

### 4.3 Evidence-linked generation

Every LLM-generated assertion must cite one or more PIR block IDs. Generated numbers must either match an extracted fact or be produced by an approved deterministic calculation.

### 4.4 Native evidence objects

Charts and tables remain editable PowerPoint objects. Raster images may be used only for decorative assets or an explicitly reported last-resort limitation, never silently for required evidence.

### 4.5 Bounded iteration

Each slide receives a maximum number of automated repair attempts. Failure produces a safe fallback or an explicit diagnostic instead of an unbounded agent loop.

### 4.6 Graceful extension

Unknown fields are preserved in `extensions`. Unknown output types produce a placeholder diagnostic and may be skipped or represented as text according to policy. They must not crash the entire deck.

## 5. Component architecture

```text
CLI / service entry point
        |
        v
ReportLoader -> TreeWalker -> Normalizer -> SemanticValidator
                                      |
                                      v
                             PresentationModel
                                      |
                    +-----------------+----------------+
                    |                                  |
                    v                                  v
             EvidenceRegistry                    ThemeResolver
                    |                                  |
                    +-----------------+----------------+
                                      v
                              LangGraph workflow
                         narrative -> slides -> QA/repair
                                      |
                                      v
                           versioned DeckSpecification
                                      |
                                      v
                          ArtifactToolRenderer bridge
                                      |
                         +------------+------------+
                         |                         |
                         v                         v
                      .pptx                  rendered PNGs
                         |                         |
                         +------------+------------+
                                      v
                        Structural + visual validation
```

## 6. Source traversal and visibility

### 6.1 Recursive traversal

The walker accepts dictionaries, arrays, and scalars. It maintains a context containing the parent ID, semantic path, JSON Pointer, inherited citations, navigation metadata, and ordering.

Logical signature:

```python
walk(value: JsonValue, context: WalkContext) -> Iterator[SourceEvent]
```

Events:

- `NodeStarted`
- `OutputFound`
- `NodeFinished`
- `UnknownStructureFound`

The walker does not perform slide planning.

### 6.2 Visibility rules

Visibility is resolved before outputs reach the PIR:

```text
node.is_hidden == true
    Hide node heading, its outputs, and its subtree.

node.is_hidden == false and node.display_enabled == false
    Hide only node.display_text.
    Keep outputs and eligible descendants.

node.is_hidden == false and node.display_enabled == true
    Keep heading and outputs.
```

`display_enabled` must never suppress output content. The normalized node stores `heading_visible` separately from `content_visible`.

### 6.3 Ordering

Children sort by the following stable key:

1. `ordering`, if numeric.
2. `sub_ordering`, if numeric.
3. Original array index.

Missing or duplicated ordering values produce warnings but preserve source order.

## 7. Canonical schemas

The following are design-level Python/Pydantic schemas. Names and fields form the contract; this document does not implement them.

### 7.1 Common types

```python
Scalar = str | int | float | bool | None
JsonValue = Scalar | list["JsonValue"] | dict[str, "JsonValue"]

class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"

class SourceRef(BaseModel):
    json_pointer: str
    node_id: str | None
    output_index: int | None

class Diagnostic(BaseModel):
    code: str
    severity: Severity
    message: str
    source: SourceRef | None
    slide_id: str | None
    recoverable: bool
    details: dict[str, JsonValue] = {}
```

### 7.2 Citation model

```python
class Citation(BaseModel):
    id: str
    url: str
    label: str | None
    source_scope_id: str
    restricted: bool = False

class CitationRef(BaseModel):
    citation_id: str
    local_marker: str
```

Citation IDs are scoped because separate sections may reuse `[1]` for different URLs. During normalization, the system creates globally unique IDs such as `financials/revenue_growth:1`.

### 7.3 Rich text

```python
class TextStyle(BaseModel):
    bold: bool = False
    italic: bool = False
    underline: bool = False

class TextRun(BaseModel):
    text: str
    style: TextStyle
    citations: list[CitationRef] = []

class Paragraph(BaseModel):
    runs: list[TextRun]
    level: int = 0
    kind: Literal["body", "bullet", "heading", "note"]
```

Markdown parsing supports headings, emphasis, bullets, escaped characters, and citation markers. Unsupported Markdown is converted to plain text with a warning.

### 7.4 Presentation intermediate representation

```python
class PresentationModel(BaseModel):
    schema_version: Literal["1.0"]
    report_id: str
    is_sample_report: bool
    sections: list[SectionModel]
    citations: dict[str, Citation]
    facts: dict[str, Fact]
    diagnostics: list[Diagnostic]

class SectionModel(BaseModel):
    id: str
    name: str | None
    heading: str | None
    heading_visible: bool
    summary_headline: str | None
    order: tuple[int | None, int | None, int]
    blocks: list[ContentBlock]
    children: list["SectionModel"]
    source: SourceRef
    extensions: dict[str, JsonValue] = {}
```

`ContentBlock` is a discriminated union:

```python
ContentBlock = Annotated[
    NarrativeBlock
    | RecommendationBlock
    | TableBlock
    | ChartBlock
    | EvidenceBlock,
    Field(discriminator="kind"),
]
```

```python
class BlockBase(BaseModel):
    id: str
    kind: str
    title: str | None
    source: SourceRef
    citations: list[CitationRef]
    priority: Literal["primary", "secondary", "appendix"] = "secondary"
    extensions: dict[str, JsonValue] = {}

class NarrativeBlock(BlockBase):
    kind: Literal["narrative"]
    paragraphs: list[Paragraph]

class RecommendationBlock(BlockBase):
    kind: Literal["recommendation"]
    request: list[Paragraph]

class EvidenceBlock(BlockBase):
    kind: Literal["evidence"]
    heading: str | None
    paragraphs: list[Paragraph]

class TableColumn(BaseModel):
    key: str
    title: str
    alignment: Literal["left", "center", "right"]
    inferred_type: Literal["text", "currency", "percent", "number", "mixed"]

class TableCell(BaseModel):
    raw: JsonValue
    paragraphs: list[Paragraph]
    numeric_value: float | None
    display_value: str

class TableBlock(BlockBase):
    kind: Literal["table"]
    columns: list[TableColumn]
    rows: list[dict[str, TableCell]]
    zebra: bool

class ChartBlock(BlockBase):
    kind: Literal["chart"]
    chart: ChartModel
```

### 7.5 Fact registry

```python
class Fact(BaseModel):
    id: str
    value: str | int | float
    normalized_numeric_value: float | None
    unit: str | None
    period: str | None
    subject: str | None
    display_text: str
    source_block_id: str
    citations: list[CitationRef]
```

The first version may extract facts from chart series and table cells deterministically. LLM extraction from prose is optional and must remain evidence-linked.

### 7.6 Chart model

```python
class ChartKind(StrEnum):
    BAR = "bar"
    COLUMN = "column"
    LINE = "line"
    WATERFALL = "waterfall"
    RANGE_LINE = "range_line"

class DataPoint(BaseModel):
    category: str | None
    value: float | None
    low: float | None
    high: float | None
    display: str | None
    color: str | None
    is_total: bool = False
    citations: list[CitationRef] = []

class ChartSeries(BaseModel):
    id: str
    name: str
    role: Literal["value", "line", "range", "total", "helper"]
    points: list[DataPoint]
    color: str | None
    dash_style: str | None

class ChartModel(BaseModel):
    kind: ChartKind
    title: str | None
    categories: list[str]
    series: list[ChartSeries]
    y_axis_title: str | None
    y_axis_format: str | None
    legend_enabled: bool
    source_options: dict[str, JsonValue]
```

Highcharts options remain in `source_options` for diagnostics, but rendering uses normalized fields only.

## 8. Planning schemas

### 8.1 Narrative plan

```python
class NarrativeSectionPlan(BaseModel):
    id: str
    purpose: str
    source_section_ids: list[str]
    key_messages: list[str]
    suggested_slide_count: int

class NarrativePlan(BaseModel):
    audience: str
    objective: str
    deck_title: str
    design_brief: DesignBrief
    sections: list[NarrativeSectionPlan]
    appendix_policy: str
```

### 8.2 Slide plan

```python
class SlidePlan(BaseModel):
    id: str
    sequence: int
    role: Literal[
        "cover", "section", "summary", "chart", "table",
        "findings", "recommendations", "appendix"
    ]
    purpose: str
    source_block_ids: list[str]
    required_fact_ids: list[str]
    title_intent: str
    layout_family: str
```

### 8.3 Renderable slide specification

```python
class SlideSpecification(BaseModel):
    schema_version: Literal["1.0"]
    id: str
    sequence: int
    title: RichTextSpec
    subtitle: RichTextSpec | None
    layout_family: LayoutFamily
    elements: list[SlideElement]
    speaker_notes: list[str]
    source_block_ids: list[str]
    revision: int = 0
```

Element union:

```python
SlideElement = TextElement | ChartElement | TableElement | RuleElement | ImageElement

class ElementBase(BaseModel):
    id: str
    importance: Literal["primary", "secondary", "supporting"]
    source_block_ids: list[str]
    region: Literal["title", "main", "side", "footer", "full"]

class TextElement(ElementBase):
    type: Literal["text"]
    content: list[Paragraph]
    max_lines: int | None

class ChartElement(ElementBase):
    type: Literal["chart"]
    chart_block_id: str
    presentation: ChartPresentationPlan

class TableElement(ElementBase):
    type: Literal["table"]
    table_block_id: str
    row_range: tuple[int, int]
    visible_columns: list[str]

class RuleElement(ElementBase):
    type: Literal["rule"]
    semantic_role: Literal["divider", "baseline", "emphasis"]
```

The LLM chooses regions and layout families, not raw coordinates. The renderer resolves regions into geometry.

### 8.4 Chart presentation plan

```python
class LabelPolicy(StrEnum):
    NONE = "none"
    ALL = "all"
    ENDPOINTS = "endpoints"
    LAST_PERIOD = "last_period"
    EXTREMA = "extrema"
    TOTALS = "totals"
    SELECTED = "selected"
    DIRECT_SERIES = "direct_series"

class ChartPresentationPlan(BaseModel):
    label_policy: LabelPolicy
    selected_labels: list[tuple[str, int]] = []
    legend_position: Literal["none", "top", "right", "bottom"]
    show_markers: bool
    show_gridlines: bool
    emphasis_series_ids: list[str]
    fallback_mode: str | None
    annotation_fact_ids: list[str]
```

### 8.5 Visual review and repair

```python
class VisualIssue(BaseModel):
    code: Literal[
        "overflow", "overlap", "label_collision", "clipped_label",
        "crowded", "too_sparse", "weak_hierarchy", "low_contrast",
        "unbalanced", "small_text", "misleading_chart", "other"
    ]
    severity: Severity
    element_ids: list[str]
    description: str
    evidence_region: tuple[float, float, float, float] | None

class VisualReview(BaseModel):
    slide_id: str
    pass_hard_checks: bool
    aesthetic_score: int
    issues: list[VisualIssue]
    recommended_action: str

class SlideRevision(BaseModel):
    slide_id: str
    operations: list[RevisionOperation]
    rationale: str

class RevisionOperation(BaseModel):
    operation: Literal[
        "shorten_text", "split_slide", "change_layout", "change_label_policy",
        "move_legend", "resize_region", "remove_secondary_element",
        "move_to_appendix", "use_safe_fallback"
    ]
    target_element_id: str | None
    parameters: dict[str, JsonValue]
```

The repair engine accepts only operations from this allowlist.

## 9. Module interfaces

Suggested minimal package structure:

```text
src/
  config.py
  models.py
  ingest.py
  normalize.py
  validate.py
  markdown.py
  charts.py
  evidence.py
  planning.py
  workflow.py
  render_bridge.py
  inspect.py
  cli.py
renderer/
  render.mjs
  layouts.mjs
  charts.mjs
tests/
  fixtures/
```

Schemas should remain together initially in `models.py`. Split them only if that file becomes difficult to navigate.

### 9.1 Loader

```python
class ReportLoader:
    def load(self, path: Path) -> dict[str, JsonValue]: ...
```

Responsibilities:

- Read UTF-8 JSON.
- Enforce file-size and nesting-depth limits.
- Return syntax diagnostics with JSON line and column.
- Never mutate source data.

### 9.2 Normalizer

```python
class ReportNormalizer:
    def normalize(self, raw: dict[str, JsonValue]) -> PresentationModel: ...
```

Responsibilities:

- Recursively traverse the tree.
- Apply visibility and ordering rules.
- Convert outputs into content blocks.
- Resolve scoped citations.
- Parse Markdown and citation markers.
- Normalize charts and tables.
- Preserve unknown fields under `extensions`.

### 9.3 Semantic validator

```python
class SemanticValidator:
    def validate(self, model: PresentationModel) -> ValidationReport: ...
```

Checks:

- Unique normalized IDs.
- Resolvable citations.
- Table column-to-row consistency.
- Numeric chart values.
- Category and series alignment.
- Waterfall total reconciliation within tolerance.
- Range points where `low <= high`.
- Valid color strings.
- Consistent units where a comparison depends on them.

### 9.4 Evidence registry

```python
class EvidenceRegistry:
    def build(self, model: PresentationModel) -> EvidenceIndex: ...
    def verify_slide(self, slide: SlideSpecification) -> list[Diagnostic]: ...
```

The registry validates block and fact references, detects invented numeric tokens, and assembles speaker-note citations.

### 9.5 LLM gateway

```python
class LlmGateway:
    async def complete_structured(
        self,
        task: LlmTask,
        input: BaseModel,
        output_type: type[T],
    ) -> T: ...
```

Responsibilities:

- Provider abstraction at one boundary only.
- Structured responses.
- Timeout and retry policy.
- Prompt and response hashing.
- Token and cost accounting.
- Redacted logging.

The first implementation needs one provider. A second provider adapter should be added only when required.

### 9.6 Planner

```python
class DeckPlanner:
    async def narrative(self, model: PresentationModel) -> NarrativePlan: ...
    async def slides(
        self,
        model: PresentationModel,
        narrative: NarrativePlan,
    ) -> list[SlidePlan]: ...
    async def specify_slide(
        self,
        context: SlidePlanningContext,
    ) -> SlideSpecification: ...
```

### 9.7 Renderer bridge

```python
class RendererBridge:
    def render(
        self,
        deck: DeckSpecification,
        build_dir: Path,
    ) -> RenderResult: ...
```

The bridge serializes the versioned deck specification, invokes the JavaScript renderer as a subprocess, captures structured diagnostics, and returns PPTX and rendered-slide paths.

It does not contain PowerPoint layout logic.

### 9.8 Inspector

```python
class DeckInspector:
    def inspect_structure(self, result: RenderResult) -> InspectionReport: ...
    async def inspect_visuals(
        self,
        result: RenderResult,
        slides: list[SlideSpecification],
    ) -> list[VisualReview]: ...
```

Structural inspection always runs. Multimodal visual inspection is configurable but recommended for final builds.

## 10. LangGraph workflow

LangGraph manages planning and repair state. Parsing and basic validation remain ordinary function calls because they do not benefit from agent state.

### 10.1 Graph state

```python
class WorkflowState(TypedDict):
    run_id: str
    config: RunConfig
    presentation: PresentationModel
    validation: ValidationReport
    narrative: NarrativePlan | None
    slide_plans: list[SlidePlan]
    slide_specs: dict[str, SlideSpecification]
    render_result: RenderResult | None
    inspections: dict[str, SlideInspection]
    attempts: dict[str, int]
    diagnostics: list[Diagnostic]
    status: Literal["running", "completed", "completed_with_warnings", "failed"]
```

### 10.2 Nodes

#### `validate_source`

- Runs semantic validation.
- Stops on fatal errors.
- Allows warnings and recoverable errors to continue.

#### `plan_narrative`

- Creates the audience-level storyline and design brief.
- Receives only visible content plus evidence IDs.
- Returns `NarrativePlan`.

#### `plan_slides`

- Determines slide count, sequence, roles, and source-block allocation.
- Enforces that every required primary block is assigned or explicitly sent to appendix.

#### `specify_slides`

- Produces `SlideSpecification` objects.
- May run per slide with bounded concurrency.
- Validates every structured response before storing it.

#### `verify_evidence`

- Rejects unsupported claims and unknown fact IDs.
- Routes invalid slides back to `specify_slides` once with diagnostics.
- Uses deterministic checking, not another LLM opinion.

#### `preflight_layout`

- Estimates text capacity, table height, and chart-label collision risk.
- Applies safe deterministic adjustments.
- Routes impossible layouts to revision before rendering.

#### `render_deck`

- Renders the current deck specification.
- Produces PPTX, slide images, object manifests, and renderer diagnostics.

#### `inspect_structure`

- Checks bounds, overlaps, text fit, missing objects, native chart creation, and font availability.

#### `inspect_visuals`

- Sends rendered slide images and compact slide intent to a multimodal model.
- Returns structured visual issues.

#### `decide_repairs`

- Combines deterministic and multimodal issues.
- Passes good slides through unchanged.
- Produces allowlisted revision operations for failed slides.

#### `apply_repairs`

- Applies deterministic operations directly.
- Calls the LLM only when wording, grouping, or layout selection must change.
- Increments the per-slide attempt counter.

#### `finalize`

- Runs final deck-wide checks.
- Writes a build manifest.
- Returns completed, completed-with-warnings, or failed.

### 10.3 Edges

```text
START
  -> validate_source
      fatal -> FAIL
      otherwise -> plan_narrative
  -> plan_slides
  -> specify_slides
  -> verify_evidence
      invalid and retry available -> specify_slides
      invalid and exhausted -> FAIL
  -> preflight_layout
      revisions needed -> apply_repairs
      otherwise -> render_deck
  -> inspect_structure
      renderer failure -> failure_policy
      otherwise -> inspect_visuals
  -> decide_repairs
      all pass -> finalize
      attempts available -> apply_repairs -> render_deck
      attempts exhausted -> safe_fallback -> render_deck
  -> finalize
  -> END
```

### 10.4 Concurrency

Slide specification and visual review may run concurrently per slide. Rendering remains one deck-level operation so PowerPoint theme, relationships, and slide numbering stay consistent. Concurrency limits should be configuration values with conservative defaults.

## 11. Layout system

### 11.1 Layout families

The initial system should support a small curated set:

1. `cover_minimal`
2. `section_divider`
3. `executive_summary`
4. `hero_chart`
5. `chart_with_commentary`
6. `full_width_table`
7. `table_with_takeaway`
8. `findings_list`
9. `recommendations`
10. `appendix_evidence`

Each layout defines named regions, minimum and maximum dimensions, supported element types, and capacity constraints. Avoid a generic freeform layout in the first version.

### 11.2 Theme

The deck theme contains:

- Slide size and safe margins.
- Font family and size scale.
- Background and text colors.
- Primary, secondary, positive, negative, and neutral data colors.
- Chart axis, gridline, marker, and label defaults.
- Table header, banding, border, and padding rules.
- Citation and footer treatment.

For the inspected financial report, the default direction is restrained and analytical: light neutral background, deep purple primary, green for positive movement, red for negative movement, and minimal decoration.

### 11.3 Capacity model

Every region declares limits such as:

- Maximum lines at the target font size.
- Maximum bullets.
- Maximum table rows and columns.
- Minimum chart plot width and height.
- Maximum title lines.
- Minimum separation between objects.

The planner receives those limits. It must split content rather than assume the renderer can fit it.

## 12. Chart translation and label handling

### 12.1 Capability adapter

Chart normalization and rendering are separate:

```python
class ChartAdapter:
    def normalize(self, options: dict[str, JsonValue]) -> ChartModel: ...
    def choose_native_strategy(self, chart: ChartModel) -> NativeChartStrategy: ...
```

Strategies:

- Bar: direct native bar or column chart.
- Waterfall: native waterfall when supported and verified; otherwise editable stacked columns with invisible bases and separate positive, negative, and total series.
- Line: direct native line chart.
- Area range: stacked helper series for lower bound and band width where supported; otherwise two boundary lines with an explicit recorded fallback.

### 12.2 Pre-render label collision model

For each label candidate:

1. Map category index and value to normalized plot coordinates.
2. Estimate text width from font metrics and formatted label.
3. Construct an approximate bounding box.
4. Compare against other label boxes, plot bounds, legend, and annotations.
5. Assign a collision-risk score.

The system then evaluates candidate policies in order of information retained:

1. All labels.
2. Selected labels with alternate positions.
3. Endpoints, extrema, or totals.
4. Direct series labels.
5. No labels with a supporting takeaway or compact data table.

### 12.3 Post-render checks

The object manifest records chart bounds and intended labels. The visual critic inspects the rendered slide for collisions or clipping that PowerPoint introduced. Repair operations may change label policy, selected points, legend position, chart bounds, or the slide layout.

### 12.4 Truth preservation

- Null values remain gaps, never zeros.
- Waterfall totals are checked against their components.
- Display strings do not replace numeric values.
- Units appear in the axis title, data labels, or slide annotation.
- Any transformed chart strategy appears in the build manifest.

## 13. Table handling

Table normalization infers alignment and numeric type while preserving formatted source text. Before rendering, the capacity engine estimates column widths from headers and representative cells.

Split policy:

1. Remove no required rows or columns.
2. Shorten duplicated narrative outside the table.
3. Allocate more slide width.
4. Split rows across continuation slides with repeated headers.
5. Split column groups only when the table remains intelligible.
6. Move the complete table to the appendix and show a concise primary view when the main narrative does not require every column.

Markdown emphasis inside cells becomes rich text where the native table API supports it. Citation markers may remain compact on-slide references with full URLs in speaker notes.

## 14. Prompt contracts

Each prompt must include:

- Task definition.
- Audience and design brief.
- Allowed source block and fact IDs.
- Relevant capacity constraints.
- Allowed layout families or revision operations.
- Required typed output schema.
- Explicit prohibition on inventing numbers or sources.
- Instruction to retain material caveats.

The prompt should not include the full report for every slide. Use the narrative plan plus the blocks assigned to that slide. This reduces cost and accidental cross-slide leakage.

LLM outputs fail validation if they:

- Reference unknown IDs.
- Contain unsupported numeric claims.
- Exceed capacity limits.
- Request unsupported chart types.
- Use raw coordinates.
- Omit a required primary fact.
- Produce unparseable structured output.

## 15. Failure handling

### 15.1 Error classes

| Class | Example | Default response |
|---|---|---|
| Input syntax | Invalid JSON | Stop with location and message |
| Input structure | `report` missing or wrong type | Stop as fatal |
| Unsupported content | Unknown `output_format` | Warn, preserve metadata, apply configured fallback |
| Data integrity | Series/category mismatch | Repair only if unambiguous; otherwise omit affected chart and fail or warn by policy |
| Citation | Missing citation ID | Keep content, flag unresolved citation; fail in strict mode |
| LLM transport | Timeout or rate limit | Retry with backoff, then use deterministic fallback where possible |
| LLM schema | Invalid structured output | One schema-correction retry, then fail the affected planning step |
| Evidence | Invented or changed number | Reject slide and regenerate with diagnostics |
| Renderer | Process crash or invalid PPTX | Retry once from clean build directory, then stop |
| Layout | Overflow or collision | Repair slide, split it, then safe fallback |
| Chart capability | Unsupported native feature | Use declared editable fallback and record it |
| Visual quality | Low score without hard failure | Repair until attempt limit, then accept only above configured floor |
| Environment | Missing font or renderer dependency | Stop before planning if required; substitute only approved fonts |

### 15.2 Strict and permissive modes

Strict mode is recommended for diligence decks:

- Unresolved evidence, corrupted chart data, missing required content, or invalid native objects fail the build.
- Aesthetic warnings may complete with warnings only above the configured quality floor.

Permissive mode may skip unsupported secondary blocks and produce a deck with a diagnostic report. It must never silently change facts.

### 15.3 Retry policy

- Network or provider transient failure: exponential backoff with jitter, maximum three attempts.
- Invalid structured LLM response: one corrective retry containing validation errors.
- Evidence failure: one regeneration attempt per slide.
- Visual or layout failure: maximum three slide repair cycles.
- Renderer failure: one clean retry.

Retries must use the same idempotent run ID and retain diagnostics.

### 15.4 Safe fallbacks

Fallback order:

1. Simpler supported layout using the same evidence.
2. Split slide.
3. Reduce labels or move values into a native table.
4. Move secondary evidence to appendix.
5. Use a text-and-table representation when a chart cannot be represented accurately.
6. Fail the build if required evidence still cannot be represented faithfully.

### 15.5 Partial output

The final output directory receives a PPTX only after final validation. Failed builds retain private diagnostics and intermediate renders in the build directory but do not promote them as final deliverables.

## 16. Configuration and secrets

Proposed `.env.sample`:

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=
PLANNING_MODEL=
VISUAL_REVIEW_MODEL=
MAX_SLIDE_REPAIR_ATTEMPTS=3
MAX_LLM_RETRIES=3
LLM_CONCURRENCY=4
PRESENTATION_ASPECT_RATIO=16:9
DEFAULT_LOCALE=en-US
OUTPUT_DIRECTORY=./output
BUILD_DIRECTORY=./build
ENABLE_LLM_VISUAL_REVIEW=true
ENABLE_SPEAKER_NOTE_CITATIONS=true
STRICT_VALIDATION=true
```

Rules:

- `.env` is ignored by version control.
- Logs redact keys, authorization headers, source document URLs when configured, and input excerpts that may be sensitive.
- LLM caches are keyed by provider, model, prompt version, schema version, and redacted input hash.
- Secrets never enter PPTX metadata, speaker notes, manifests, or diagnostic messages.

## 17. Build artifacts

Private build directory:

```text
build/<run-id>/
  normalized-report.json
  narrative-plan.json
  deck-specification.json
  renderer-input.json
  renderer-manifest.json
  validation-report.json
  visual-reviews.json
  slides/
    001.png
    ...
  draft.pptx
```

Public output directory:

```text
output/
  report.pptx
  report-build-summary.json   # optional, no secrets or source URLs
```

The build manifest records versions, warnings, chart fallbacks, slide-to-source mappings, and validation status.

## 18. Observability

Each run should report:

- Input hash and schema version.
- Node and output counts.
- Normalization warnings.
- Planned and final slide counts.
- LLM calls, latency, retries, and token usage.
- Per-slide repair attempts.
- Chart fallback strategies.
- Structural validation failures.
- Visual-quality scores.
- Final status and elapsed time.

Logs use run ID, slide ID, and source block ID for correlation. Raw prompts and report content should be opt-in in production environments.

## 19. Testing strategy

### 19.1 Unit tests

- Recursive traversal at multiple depths.
- Stable ordering with missing and duplicate order fields.
- All combinations of `is_hidden` and `display_enabled`.
- Scoped citation resolution.
- Markdown and inline citation parsing.
- Table type inference.
- Chart normalization for bar, waterfall, line, null values, and area ranges.
- Waterfall reconciliation.
- Evidence token verification.
- Label collision estimation.

### 19.2 Contract tests

- PIR schema serialization.
- Planner structured-output validation.
- Deck specification consumed by renderer.
- Renderer diagnostic schema consumed by Python.
- Version mismatch produces a clear fatal error.

### 19.3 Golden fixtures

Use small JSON fixtures rather than the full report for most tests:

- Hidden section.
- Hidden heading with visible output.
- Deeply nested sections.
- Dense Markdown.
- Wide and long tables.
- Waterfall with positive and negative steps.
- Crossing line series with label collisions.
- Area range with null values.
- Missing citation.
- Unknown output type.

Keep the supplied `report.json` as an end-to-end fixture if its data can safely remain in the repository.

### 19.4 Rendering tests

- PPTX opens without repair warnings.
- Expected native charts and tables exist.
- Slide count matches the specification.
- All objects remain within slide bounds.
- No unintended overlap.
- Text has no overflow.
- Expected fonts resolve.
- Slide images render successfully.

### 19.5 LLM evaluation

Maintain a small evaluation set with human-approved expectations:

- No invented numbers.
- Required caveats retained.
- One clear purpose per slide.
- Sensible grouping and sequence.
- Titles reflect the evidence.
- Visual review identifies seeded collisions and overflow.
- Repairs do not delete required evidence.

Exact wording need not be deterministic. Evidence coverage and schema validity must be deterministic.

## 20. Security and trust boundaries

The input JSON, Markdown, URLs, and source titles are untrusted data.

- Never execute input strings as code.
- Ignore JavaScript callbacks or formatter functions embedded in chart options.
- Restrict URL schemes to approved values when resolving sources.
- Apply maximum file size, nesting depth, string length, row count, series count, and point count.
- Escape XML-sensitive characters before rendering.
- Use subprocess argument arrays rather than shell interpolation.
- Keep renderer access limited to the build and output directories.
- Do not fetch citation URLs during presentation generation unless separately authorized.
- Treat report prose as content, not instructions to the LLM.

## 21. Performance and determinism

Expected input size is small enough that parsing and normalization can remain in memory. Avoid databases and distributed queues in the first version.

Controls:

- Temperature kept low for planning and repair.
- Version every prompt and schema.
- Cache structured LLM results by stable content hash.
- Preserve source ordering.
- Limit concurrent LLM calls.
- Render a full deck per repair cycle initially. Add per-slide rendering only if profiling shows a material bottleneck.

## 22. Acceptance criteria

A build is accepted when:

1. Every included statement maps to source blocks and every generated number maps to a fact or approved calculation.
2. Hidden nodes do not appear.
3. `display_enabled: false` hides the heading without hiding outputs.
4. Required charts and tables remain native and editable.
5. No text or object exceeds slide bounds.
6. No unintended overlap remains.
7. Chart labels do not visibly collide or clip.
8. Required evidence is not removed during repair.
9. Tables are readable at presentation scale.
10. Citations resolve or the build fails according to strictness policy.
11. The deck opens and renders without file-repair warnings.
12. All slides meet the configured visual-quality floor.
13. The build manifest contains all warnings and chart fallbacks.

## 23. Recommended delivery phases

### Phase 1: deterministic semantic core

- Loader, recursive normalizer, schemas, visibility, citations, Markdown, tables, charts, validation, and fixtures.
- Output: validated PIR and diagnostic report.

### Phase 2: fixed-layout native renderer

- Theme, limited layout families, renderer bridge, native charts and tables, image rendering, and structural inspection.
- Output: correct but not yet fully LLM-designed PPTX.

### Phase 3: LLM narrative and slide planning

- Narrative plan, slide plan, structured specifications, evidence verification, caching, and prompt evaluation.
- Output: content-aware slide sequence and compositions.

### Phase 4: visual review and repair

- Label collision analysis, multimodal inspection, allowlisted repairs, safe fallbacks, and attempt limits.
- Output: bounded automatic quality loop.

### Phase 5: hardening

- Full-report evaluation, security limits, observability, configuration, performance profiling, and production packaging.

## 24. Key design decisions

1. The source report is content, not a slide layout specification.
2. `display_enabled` controls only the heading; `is_hidden` controls the node and its output.
3. The PIR is the single semantic source of truth.
4. Python orchestrates; the supported artifact renderer creates PowerPoint objects.
5. The LLM chooses narrative and composition but cannot change facts or emit arbitrary coordinates.
6. Layouts come from a small curated library.
7. Native charts use explicit conversion strategies and documented fallbacks.
8. Both geometry checks and multimodal review are required for final quality.
9. Repair operations are typed, bounded, and auditable.
10. The first version stays local and in-memory; services, databases, and queues wait for demonstrated need.

