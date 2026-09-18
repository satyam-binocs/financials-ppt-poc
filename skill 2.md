# Presentation Layout Intelligence and Composition Engine

## 1. Purpose

The current presentation design system already defines strong rules for:

- Typography
- Colors and design tokens
- Component styling
- Tables
- Citations
- Content density
- Pagination
- Overflow handling
- Visual QA
- PPTX rendering compliance

However, the system needs an additional **layout intelligence layer** that determines how content should be composed on a slide before assigning coordinates and rendering it.

The goal is to ensure that the generated presentation:

1. Preserves the original content and meaning.
2. Selects an appropriate slide composition automatically.
3. Uses layouts such as:
   - 1→1
   - 1→2
   - 1→3
   - 1→4
   - 2×2
   - 2×3
   - Main + Sidebar
   - Main + Two Supporting Blocks
   - Chart + Commentary
   - Table + Insight
   - Timeline
   - Matrix
   - Comparison
   - Hierarchical layouts
4. Adapts gracefully when content does not fit.
5. Avoids arbitrary coordinate placement.
6. Maintains editability in the final PPTX.
7. Preserves the visual intent of the source UI/design.
8. Prevents overflow, unreadable text, excessive whitespace, weak hierarchy, and broken composition.

The system should not only render components correctly. It should first determine **what the slide should look like structurally**.

---

# 2. Core Design Principle

The layout engine must first determine the slide’s semantic composition based on:

- Number of components
- Component types
- Semantic importance
- Content density
- Component compatibility
- Aspect ratio
- Minimum viable dimensions
- Hierarchy
- Visual dominance
- Available slide area

Only after selecting the composition should the engine calculate coordinates and render the components.

## Required pipeline

```text
Raw Content
    ↓
Content Parsing
    ↓
Semantic Classification
    ↓
Component Measurement
    ↓
Content Density Analysis
    ↓
Layout Candidate Generation
    ↓
Layout Compatibility Validation
    ↓
Layout Scoring
    ↓
Best Layout Selection
    ↓
Geometry Allocation
    ↓
Overflow / Fit Validation
    ↓
Adaptive Fallback
    ↓
PPTX Rendering
    ↓
Visual and Structural QA
```

The current system should be extended with this layer rather than replacing the existing typography, density, citation, and rendering rules.

---

# 3. Content Preservation Hierarchy

When content conflicts with available space, the engine must preserve information in the following priority order:

1. Preserve meaning.
2. Preserve required data.
3. Preserve semantic grouping.
4. Preserve readability.
5. Preserve hierarchy.
6. Preserve logical structure.
7. Preserve visual style.
8. Preserve exact source geometry.

Exact coordinates should not be treated as more important than readability or content preservation.

The engine should preserve the source’s:

- Visual hierarchy
- Component relationships
- Grouping
- Color language
- Spacing language
- Emphasis patterns
- Relative importance
- Overall composition intent

However, it may adapt geometry when the original layout cannot be represented cleanly in PowerPoint.

---

# 4. Layout Grammar and Taxonomy

The system should support a formal layout grammar.

Every slide should be classified into one of the following high-level composition families.

## 4.1 Single-region layout

Used when one component is dominant.

Examples:

- One large chart
- One wide table
- One large diagram
- One major text narrative
- One full-width visual

Pattern:

```text
┌──────────────────────────────┐
│                              │
│       Primary Component      │
│                              │
└──────────────────────────────┘
```

Canonical ID:

```text
L01_SINGLE
```

---

## 4.2 Equal split layout

Used when two components have similar importance and compatible density.

```text
┌──────────────┬──────────────┐
│              │              │
│ Component A  │ Component B  │
│              │              │
└──────────────┴──────────────┘
```

Canonical ID:

```text
L02_SPLIT_EQUAL
```

Use when:

- Two charts have similar importance.
- Two comparable sections have similar content volume.
- Two independent but related components need equal attention.

Do not use when one component is significantly more important or substantially larger than the other.

---

## 4.3 Asymmetric split layout

Used when one component is dominant and the other is supporting.

```text
┌────────────────────┬────────┐
│                    │        │
│                    │Support │
│      Primary       │        │
│                    │        │
└────────────────────┴────────┘
```

Canonical IDs:

```text
L03_SPLIT_LEFT_DOMINANT
L04_SPLIT_RIGHT_DOMINANT
```

Typical ratios:

```text
70:30
65:35
60:40
```

Use for:

- Chart + short commentary
- Main analysis + supporting takeaway
- Main table + small summary
- Primary visual + key implications

---

## 4.4 Three-column layout

```text
┌──────────┬──────────┬──────────┐
│          │          │          │
│    A     │    B     │    C     │
│          │          │          │
└──────────┴──────────┴──────────┘
```

Canonical ID:

```text
L05_THREE_COLUMN
```

Use only when:

- Each component is compact.
- Text is short.
- Components have similar semantic weight.
- Minimum column width remains readable.

Do not use three columns for three long paragraphs or detailed cards.

---

## 4.5 Four-column layout

```text
┌──────┬──────┬──────┬──────┐
│  A   │  B   │  C   │  D   │
└──────┴──────┴──────┴──────┘
```

Canonical ID:

```text
L06_FOUR_COLUMN
```

Use primarily for:

- KPIs
- Compact metrics
- Short labels
- Small numerical summaries

Do not use this layout for detailed narrative content.

---

## 4.6 2×2 grid

```text
┌──────────────┬──────────────┐
│      A       │      B       │
├──────────────┼──────────────┤
│      C       │      D       │
└──────────────┴──────────────┘
```

Canonical ID:

```text
L07_GRID_2X2
```

Use when:

- Four components contain meaningful detail.
- Each component needs more width than a four-column layout provides.
- Components are roughly balanced.
- The slide benefits from grouping into rows and columns.

---

## 4.7 2×3 grid

```text
┌──────────┬──────────┬──────────┐
│    A     │    B     │    C     │
├──────────┼──────────┼──────────┤
│    D     │    E     │    F     │
└──────────┴──────────┴──────────┘
```

Canonical ID:

```text
L08_GRID_2X3
```

Use for:

- Six compact cards
- Six short metrics
- Six concise capabilities
- Six small insight blocks

---

## 4.8 3×2 grid

```text
┌──────────────┬──────────────┐
│      A       │      B       │
├──────────────┼──────────────┤
│      C       │      D       │
├──────────────┼──────────────┤
│      E       │      F       │
└──────────────┴──────────────┘
```

Canonical ID:

```text
L09_GRID_3X2
```

Use when:

- Components are vertically compact but need more horizontal width.
- Cards contain more text.
- Two-column reading is preferable to three-column compression.

The engine must choose between 2×3 and 3×2 based on measured content volume.

---

## 4.9 Vertical stack

```text
┌──────────────────────────────┐
│ Component A                  │
├──────────────────────────────┤
│ Component B                  │
├──────────────────────────────┤
│ Component C                  │
└──────────────────────────────┘
```

Canonical ID:

```text
L10_VERTICAL_STACK
```

Use when:

- Components are text-heavy.
- Components cannot fit side-by-side.
- The content has a sequential or narrative relationship.
- Horizontal compression would reduce readability.

---

## 4.10 Main + sidebar

```text
┌────────────────────┬─────────┐
│                    │         │
│       Main         │ Sidebar │
│                    │         │
└────────────────────┴─────────┘
```

Canonical ID:

```text
L11_MAIN_SIDEBAR
```

Use for:

- Main chart + supporting metrics
- Main table + short implications
- Main narrative + metadata
- Main visual + assumptions/context

---

## 4.11 Main + two supporting components

```text
┌────────────────────┬─────────┐
│                    │ Support │
│       Main         ├─────────┤
│                    │ Support │
└────────────────────┴─────────┘
```

Canonical ID:

```text
L12_MAIN_TWO_SUPPORT
```

Use when:

- One component is clearly dominant.
- Two compact supporting insights exist.
- Supporting components are short and independent.

Do not use if the supporting blocks are long or require detailed tables.

---

## 4.12 Chart + commentary

```text
┌────────────────────────┬───────┐
│                        │       │
│         Chart          │ Key   │
│                        │ Take- │
│                        │ away  │
└────────────────────────┴───────┘
```

Canonical ID:

```text
L13_CHART_COMMENTARY
```

Use when the chart is primary and commentary explains the chart.

Rules:

- Chart must retain visual dominance.
- Commentary must not become a second full narrative.
- Commentary should contain concise interpretation, not repeat the chart data.
- If commentary becomes too long, switch to stacked layout or separate slide.

---

## 4.13 Table + insight

```text
┌──────────────────────────────┐
│            Table             │
├──────────────────────────────┤
│ Key implication / takeaway   │
└──────────────────────────────┘
```

Canonical ID:

```text
L14_TABLE_INSIGHT
```

Use when:

- The table contains detailed evidence.
- A concise conclusion or takeaway is required below it.
- The insight is directly derived from the table.

---

## 4.14 KPI + chart layout

```text
┌────────┬────────┬────────┐
│ KPI 1  │ KPI 2  │ KPI 3  │
├──────────────────────────┤
│                          │
│           Chart          │
│                          │
└──────────────────────────┘
```

Canonical ID:

```text
L15_KPI_CHART
```

Use when:

- KPIs summarize the chart.
- KPI values are compact.
- The chart remains the primary visual.

---

## 4.15 Timeline

Canonical ID:

```text
L16_TIMELINE
```

Use for:

- Events over time
- Milestones
- Historical progression
- Process stages
- Roadmaps

The layout engine should determine whether the timeline should be:

- Horizontal
- Vertical
- Two-row
- Paginated

based on the number and length of events.

---

## 4.16 Matrix

Canonical ID:

```text
L17_MATRIX
```

Use for:

- 2D positioning
- Risk/opportunity maps
- Competitive positioning
- Priority matrices
- Quadrant analysis

The matrix should not be forced into a generic card grid.

---

## 4.17 Comparison layout

Canonical ID:

```text
L18_COMPARISON
```

Use for:

- Competitor comparisons
- Before/after analysis
- Product comparisons
- Option comparisons
- Feature comparisons

The layout engine should support:

- Two-way comparison
- Three-way comparison
- Column comparison
- Side-by-side comparison
- Table-based comparison

---

## 4.18 Hierarchical layout

Canonical ID:

```text
L19_HIERARCHICAL
```

Use when content has a clear hierarchy:

- Thesis → evidence
- Main conclusion → supporting reasons
- Strategy → initiatives
- Parent category → child categories
- Executive summary → details

The visual hierarchy must reflect semantic hierarchy.

---

## 4.19 Paginated layout

Canonical ID:

```text
L20_PAGINATED
```

Use when content cannot fit without violating:

- Minimum font size
- Minimum component dimensions
- Readability
- Component hierarchy
- Required data preservation

Pagination should occur at logical boundaries, not arbitrary character positions.

---

# 5. Canonical Layout Registry

The backend should maintain a layout registry rather than embedding layout logic across multiple renderers.

Example structure:

```python
LAYOUT_REGISTRY = {
    "L01_SINGLE": {
        "family": "single",
        "min_components": 1,
        "max_components": 1,
        "supports": ["chart", "table", "text", "diagram", "visual"],
    },
    "L02_SPLIT_EQUAL": {
        "family": "split",
        "min_components": 2,
        "max_components": 2,
        "ratio": [0.5, 0.5],
    },
    "L03_SPLIT_LEFT_DOMINANT": {
        "family": "asymmetric_split",
        "ratio": [0.65, 0.35],
    },
    "L05_THREE_COLUMN": {
        "family": "columns",
        "columns": 3,
    },
    "L07_GRID_2X2": {
        "family": "grid",
        "rows": 2,
        "columns": 2,
    },
    "L08_GRID_2X3": {
        "family": "grid",
        "rows": 2,
        "columns": 3,
    },
}
```

Each layout definition should include:

- Layout ID
- Layout family
- Supported component count
- Supported component types
- Minimum width per region
- Minimum height per region
- Default ratios
- Maximum density
- Allowed nesting
- Alignment rules
- Fallback layouts
- Whether the layout supports pagination
- Whether the layout supports unequal content sizes

---

# 6. Content-to-Layout Selection Rules

The layout engine should not select layouts only based on component count.

It must consider:

- Component count
- Component type
- Content length
- Component aspect ratio
- Semantic importance
- Relative content density
- Component compatibility
- Minimum viable dimensions
- Whether the components are related
- Whether one component is dominant
- Whether the components need comparison
- Whether the slide is sequential or hierarchical

## Initial decision rules

| Content pattern | Preferred layout |
|---|---|
| One large chart | L01_SINGLE |
| One wide table | L01_SINGLE |
| Two equal charts | L02_SPLIT_EQUAL |
| Chart + short commentary | L03_SPLIT_LEFT_DOMINANT |
| Chart + long commentary | L10_VERTICAL_STACK or L03 |
| Three short metrics | L05_THREE_COLUMN |
| Four compact KPIs | L06_FOUR_COLUMN |
| Four detailed insights | L07_GRID_2X2 |
| Six short cards | L08_GRID_2X3 |
| Six detailed cards | L09_GRID_3X2 |
| Multiple text-heavy sections | L10_VERTICAL_STACK |
| Main chart + two short insights | L12_MAIN_TWO_SUPPORT |
| Chart + interpretation | L13_CHART_COMMENTARY |
| Table + takeaway | L14_TABLE_INSIGHT |
| KPI row + chart | L15_KPI_CHART |
| Events over time | L16_TIMELINE |
| 2D analytical positioning | L17_MATRIX |
| Competitor or option comparison | L18_COMPARISON |
| Thesis + evidence | L19_HIERARCHICAL |
| Content exceeding safe limits | L20_PAGINATED |

These are default candidates, not absolute rules. The final layout must be selected after measurement and scoring.

---

# 7. Component Semantic Roles

Every component should be assigned a semantic role.

Supported roles:

```text
primary
secondary
supporting
comparison
evidence
annotation
summary
context
metadata
```

Example:

```json
{
  "type": "chart",
  "role": "primary",
  "importance": 1.0
}
```

```json
{
  "type": "callout",
  "role": "supporting",
  "importance": 0.5
}
```

```json
{
  "type": "source",
  "role": "metadata",
  "importance": 0.1
}
```

The slide should generally follow this hierarchy:

```text
One dominant message
    ↓
One primary visual/content anchor
    ↓
One secondary support layer
    ↓
Optional metadata/citation layer
```

A slide should not contain multiple competing primary components unless it is explicitly a comparison layout.

---

# 8. Component Compatibility Matrix

Not every component combination should be placed side-by-side.

The engine should maintain compatibility rules.

## Example compatibility matrix

| Component combination | Compatibility | Default behavior |
|---|---:|---|
| Chart + short insight | High | Side-by-side |
| Chart + short KPI row | High | Chart + KPI |
| Chart + long paragraph | Medium | Asymmetric or stacked |
| Chart + long table | Low | Stack or split slide |
| Long paragraph + long paragraph | Low | Vertical stack |
| Three short cards | High | Three columns |
| Three long cards | Low | 2+1 or vertical stack |
| Four compact KPIs | High | Four columns |
| Four detailed cards | Medium | 2×2 |
| Matrix + short annotation | High | Matrix + annotation |
| Matrix + detailed table | Low | Separate or stacked |
| Table + concise takeaway | High | Table + insight |
| Two unrelated charts | Medium | Equal split only if visual scale matches |
| Primary chart + decorative graphic | High | Main + support |
| Multiple detailed tables | Low | Paginate |
| Timeline + short summary | High | Timeline + sidebar |
| Timeline + detailed narrative | Medium | Vertical stack |

Compatibility should be determined by:

- Visual competition
- Space requirements
- Semantic relationship
- Reading order
- Minimum dimensions
- Whether the components share a common interpretation

---

# 9. Shared Geometry Grid

All components must be positioned using a shared slide geometry system.

The engine should not independently assign arbitrary coordinates to every component.

## Slide geometry model

```text
Slide Canvas
    ├── Outer margins
    ├── Header zone
    ├── Content zone
    ├── Footer/source zone
    ├── Column grid
    ├── Row grid
    ├── Inter-component gaps
    └── Alignment anchors
```

Example geometry structure:

```python
SlideFrame(
    slide_width=13.333,
    slide_height=7.5,
    left_margin=0.55,
    right_margin=0.55,
    top_margin=0.35,
    bottom_margin=0.35,
    header_height=0.65,
    footer_height=0.25,
    content_gap=0.18,
    column_gap=0.22,
)
```

All component positions should derive from this frame.

## Required geometry properties

Each component should have:

```python
ComponentBox(
    x,
    y,
    width,
    height,
    min_width,
    min_height,
    max_width,
    max_height,
    anchor,
    parent_id,
)
```

The engine must support:

- Shared left alignment
- Shared right alignment
- Shared top alignment
- Shared baseline alignment
- Equal gaps
- Relative positioning
- Parent-child bounds
- Column and row anchoring
- Consistent margins
- Consistent padding

---

# 10. Minimum Component Dimensions

Every component type should define minimum viable dimensions.

Examples:

```python
MIN_COMPONENT_DIMENSIONS = {
    "short_card": {
        "min_width": 1.35,
        "min_height": 0.75,
    },
    "detailed_card": {
        "min_width": 2.25,
        "min_height": 1.20,
    },
    "chart": {
        "min_width": 3.20,
        "min_height": 2.00,
    },
    "table": {
        "min_width": 5.50,
        "min_height": 1.50,
    },
    "callout": {
        "min_width": 2.00,
        "min_height": 0.75,
    },
    "paragraph": {
        "min_width": 3.00,
        "min_height": 0.70,
    },
}
```

These values should be configurable by slide size and design system.

A layout is invalid if any component falls below its minimum viable geometry.

The engine must never solve overflow simply by shrinking components below their minimum dimensions.

---

# 11. Density Model

Character count alone is insufficient for layout selection.

The engine should calculate a multi-dimensional density score.

## Proposed density model

```text
density =
    text_load
  + component_count
  + component_complexity
  + column_count
  + table_complexity
  + visual_competition
  + nesting_depth
  + label_load
  + chart_annotation_load
```

## Metrics to calculate

```python
DensityMetrics(
    visible_character_count,
    component_count,
    text_component_count,
    table_row_count,
    table_column_count,
    chart_count,
    card_count,
    column_count,
    nesting_depth,
    average_component_area,
    smallest_component_area,
    average_text_length,
    longest_text_length,
    label_count,
    citation_count,
)
```

The system should distinguish between:

### Vertical emptiness

How much unused physical space exists.

### Content load

How much content must be rendered.

A slide can have:

- Low vertical occupancy but high content complexity.
- High vertical occupancy but low content complexity.
- High character count but compact labels.
- Low character count but complex tables/charts.

Therefore, both axes must be evaluated independently.

---

# 12. Layout Candidate Generation

The engine should generate multiple layout candidates instead of selecting the first matching layout.

Example:

```python
candidates = [
    "L02_SPLIT_EQUAL",
    "L03_SPLIT_LEFT_DOMINANT",
    "L10_VERTICAL_STACK",
    "L20_PAGINATED",
]
```

For a set of two components, the engine may generate:

- Equal split
- Left-dominant split
- Right-dominant split
- Vertical stack
- Full-width sequential layout
- Pagination

Each candidate should be measured and scored.

---

# 13. Layout Scoring

Every candidate layout should receive a score.

## Suggested scoring model

```text
layout_score =
      hierarchy_fit
    + readability
    + content_compatibility
    + semantic_fit
    + balance
    + alignment
    + source_fidelity
    - overflow_penalty
    - density_penalty
    - tiny_component_penalty
    - excessive_empty_space_penalty
    - visual_competition_penalty
    - nesting_penalty
    - alignment_drift_penalty
```

Example implementation:

```python
def score_layout(candidate, components, frame):
    return (
        hierarchy_fit(candidate, components)
        + readability_score(candidate, components)
        + compatibility_score(candidate, components)
        + semantic_fit_score(candidate, components)
        + balance_score(candidate, components)
        + alignment_score(candidate, frame)
        + source_fidelity_score(candidate)
        - overflow_penalty(candidate)
        - density_penalty(candidate)
        - tiny_component_penalty(candidate)
        - whitespace_penalty(candidate)
        - competition_penalty(candidate)
    )
```

The scoring system should prefer layouts that are:

- Readable
- Semantically coherent
- Balanced
- Aligned
- Spacious enough
- Content-preserving
- Visually faithful

It should reject layouts that technically fit but look poor.

---

# 14. Adaptive Layout Fallback Chains

Each layout should define fallback layouts.

The system should degrade gracefully instead of immediately shrinking text or breaking the slide.

## Example fallback chain: four-column layout

```text
L06_FOUR_COLUMN
    ↓
L05_THREE_COLUMN + one stacked item
    ↓
L07_GRID_2X2
    ↓
L10_VERTICAL_STACK
    ↓
L20_PAGINATED
```

## Example fallback chain: three-column layout

```text
L05_THREE_COLUMN
    ↓
L02_SPLIT_EQUAL + one stacked item
    ↓
L07_GRID_2X2
    ↓
L10_VERTICAL_STACK
    ↓
L20_PAGINATED
```

## Example fallback chain: 2×3 grid

```text
L08_GRID_2X3
    ↓
L09_GRID_3X2
    ↓
L07_GRID_2X2 + remaining items
    ↓
L10_VERTICAL_STACK
    ↓
L20_PAGINATED
```

## Example fallback chain: chart + commentary

```text
L13_CHART_COMMENTARY
    ↓
L03_SPLIT_LEFT_DOMINANT
    ↓
L10_VERTICAL_STACK
    ↓
L01_SINGLE chart slide + commentary continuation
```

The fallback process should follow this order:

```text
1. Reflow
2. Change layout
3. Consolidate related content
4. Reduce non-essential spacing
5. Shorten only where safe
6. Deprioritize optional content
7. Split at logical boundary
```

The engine must not immediately reduce font size to force a layout.

---

# 15. Layout Invalidity Rules

A candidate layout must be rejected if any of the following occur:

- Text overflows its container.
- Component falls below minimum width.
- Component falls below minimum height.
- Title overlaps body content.
- Footer overlaps content.
- Citation overlaps primary content.
- Table columns become unreadably narrow.
- Chart labels become illegible.
- Primary visual loses dominance.
- Components compete for equal attention despite unequal importance.
- Unrelated content is merged.
- Excessive nesting occurs.
- Child component exceeds parent bounds.
- Alignment drifts between related components.
- Gaps become inconsistent.
- Component content is clipped.
- Text is forced into excessive wrapping.
- Layout creates large unused space while another region is overcrowded.
- Required content is removed.
- Font size drops below design-system minimum.
- Components are compressed only to preserve an arbitrary grid.
- A continuation slide contains only an orphaned card, bullet, or sentence.

---

# 16. Text Measurement and Geometry Feedback Loop

The layout engine must measure text before finalizing geometry.

Required sequence:

```text
Initial content
    ↓
Estimate text dimensions
    ↓
Allocate geometry
    ↓
Render text measurement
    ↓
Check line wrapping
    ↓
Recalculate height
    ↓
Validate component fit
    ↓
Reflow or change layout if required
```

Text measurement must account for:

- Font family
- Font size
- Font weight
- Letter spacing
- Line spacing
- Paragraph spacing
- Internal margins
- Bullet indentation
- Rich text runs
- Citation suffixes
- Table cell padding
- Maximum line width

The engine must not assume that character count directly maps to height.

---

# 17. Parent-Child Geometry

Components that belong to a larger container must use parent-relative geometry.

Example:

```text
Slide
    └── Main container
          ├── Header
          ├── Chart
          └── Commentary
```

Child components must remain within the bounds of their parent.

```python
assert child.x >= parent.x
assert child.y >= parent.y
assert child.x + child.width <= parent.x + parent.width
assert child.y + child.height <= parent.y + parent.height
```

This prevents:

- Floating components
- Broken alignment
- Child overflow
- Inconsistent internal spacing
- Components escaping their intended region

---

# 18. Specialized Composition Patterns

The engine should include specialized layout logic for recurring analytical structures.

## 18.1 Tables

Rules:

- Wide tables should use full-width layouts.
- Do not force detailed tables into sidebars.
- Use table + insight when a concise conclusion exists.
- If a table has too many columns, consider:
  - Column prioritization
  - Horizontal restructuring
  - Splitting by logical dimensions
  - Pagination
- Preserve all required data.
- Do not shrink below table label minimum size.

---

## 18.2 Charts

Rules:

- Chart aspect ratio must be respected.
- Chart should remain dominant when paired with commentary.
- Chart labels must remain readable.
- Avoid placing two charts side-by-side if both require large legends or annotations.
- Prefer stacked charts when horizontal space is insufficient.
- Do not allow commentary to visually overpower the chart.

---

## 18.3 Cards

Rules:

- Cards should not be equalized artificially when content lengths differ significantly.
- Three short cards may use three columns.
- Three detailed cards should use:
  - 2+1
  - 2×2 with an empty region only if visually justified
  - Vertical stack
- Card height should respond to content.
- Avoid card interiors becoming paragraph-heavy.
- Use cards only when each card represents a distinct insight.

---

## 18.4 Callouts

Rules:

- One callout should receive stronger emphasis.
- Two callouts should be balanced by content length.
- Three or more callouts should only be used when insights are clearly distinct.
- Do not create callouts merely to fill whitespace.
- Callouts should not contain long body paragraphs.

---

## 18.5 Timelines

Rules:

- Short events can use horizontal timelines.
- Long event descriptions should use vertical timelines.
- Large event counts should paginate or use multiple rows.
- Avoid tiny timeline labels.
- Preserve chronological order.

---

## 18.6 Comparisons

Rules:

- Comparable entities should share the same visual structure.
- Comparison columns should use consistent alignment.
- Do not force three detailed comparisons into narrow columns.
- For detailed comparisons, use a table or two-column stacked structure.
- Preserve symmetry only when content supports it.

---

## 18.7 Matrices

Rules:

- Matrix axes and labels must remain readable.
- Do not place detailed paragraphs inside quadrants.
- Use annotations or side commentary for explanations.
- Matrix should remain the primary visual.
- If the matrix becomes too dense, split the supporting explanation into another region or slide.

---

# 19. Slide Balance Validation

A slide should be evaluated for visual balance after geometry allocation.

The engine should calculate:

- Occupied area
- Empty area
- Distribution of content across regions
- Visual weight
- Text weight
- Chart weight
- Component size variance
- Left/right balance
- Top/bottom balance
- Primary anchor position

A slide should be flagged when:

- All content is stuck at the top.
- One side is overcrowded and the other is empty.
- A tiny component is placed next to a very dominant component without justification.
- The primary component does not visually dominate.
- Excessive whitespace exists despite available related content.
- Components are technically aligned but visually disconnected.
- Footer/source area consumes disproportionate space.
- The slide feels like a collection of unrelated cards rather than one composition.

Balance should not mean forced symmetry. Unequal layouts are acceptable when semantic importance is unequal.

---

# 20. Pagination Rules

Pagination should be based on semantic boundaries, not only character count.

Existing principles should remain:

- One section equals one slide by default.
- Before creating a new slide, check whether related content can fit.
- Merge related content only when it remains readable.
- Split at logical subtopic boundaries.
- Never create orphaned continuation slides.
- Never shrink below minimum typography solely to avoid pagination.
- Preserve the relationship between title, evidence, and conclusion.

## Pagination decision

```text
Can content fit while preserving:
    - readability?
    - hierarchy?
    - minimum dimensions?
    - semantic grouping?
    - visual balance?
        ↓
Yes → keep on same slide
No  → reflow or consolidate
        ↓
Still no?
        ↓
Split at logical boundary
```

The layout engine should emit decisions such as:

```python
{
    "action": "keep"
}
```

```python
{
    "action": "merge_next"
}
```

```python
{
    "action": "split",
    "reason": "minimum_component_width_violation"
}
```

---

# 21. Source-Faithful Adaptation Rules

The objective is to reproduce the source design faithfully, not redesign it unnecessarily.

The engine must preserve:

- Component appearance
- Component grouping
- Relative positioning intent
- Visual hierarchy
- Typography hierarchy
- Color relationships
- Background treatment
- Borders and separators
- Emphasis patterns
- Spacing language
- Information order

However, source geometry may be adapted when:

- HTML dimensions do not map directly to PowerPoint.
- Text metrics differ.
- PowerPoint requires editable native objects.
- A source layout causes overflow in PPTX.
- A component falls below readable dimensions.
- The source relies on browser behavior unavailable in PowerPoint.

The adaptation principle is:

```text
Preserve visual intent and hierarchy.
Adapt geometry only when required for readability, editability, or structural correctness.
```

Do not interpret “do not redesign” as “preserve broken geometry.”

---

# 22. Content Optimization Order

When content does not fit, use this order:

```text
1. Reflow components
2. Select a better layout
3. Consolidate related components
4. Reduce excessive gaps
5. Reduce non-essential padding
6. Shorten redundant wording
7. Deprioritize optional metadata
8. Split into multiple slides
```

Do not:

- Arbitrarily shrink all text
- Remove required data
- Compress every component equally
- Force all cards to equal height
- Break semantic groups
- Move citations into unrelated areas
- Hide overflow
- Clip content
- Use tiny fonts to preserve one-slide output

---

# 23. Proposed Backend Data Model

A slide should be represented as a semantic layout object before rendering.

Example:

```python
class SlideComposition:
    slide_id: str
    title: str
    subtitle: str | None
    layout_id: str
    components: list[SlideComponent]
    frame: SlideFrame
    density: DensityMetrics
    score: float
    fallback_chain: list[str]
```

```python
class SlideComponent:
    component_id: str
    component_type: str
    semantic_role: str
    importance: float
    content: dict
    estimated_width: float
    estimated_height: float
    min_width: float
    min_height: float
    preferred_aspect_ratio: float | None
    parent_id: str | None
    bounds: ComponentBox | None
```

```python
class LayoutCandidate:
    layout_id: str
    bounds: dict[str, ComponentBox]
    score: float
    violations: list[str]
    warnings: list[str]
    valid: bool
```

---

# 24. Suggested Layout Engine Modules

Recommended backend module structure:

```text
layout_engine/
    __init__.py

    taxonomy.py
        Layout IDs and layout families

    registry.py
        Canonical layout definitions

    semantic_classifier.py
        Component roles and importance

    compatibility.py
        Component compatibility matrix

    density.py
        Content and visual density metrics

    measurement.py
        Text and component measurement

    candidate_generator.py
        Generate possible layouts

    scorer.py
        Score layout candidates

    geometry.py
        Shared grid and coordinate allocation

    constraints.py
        Minimum dimensions and invalidity rules

    fallback.py
        Adaptive layout fallback chains

    balance.py
        Slide balance validation

    pagination.py
        Logical slide splitting

    composition.py
        Final slide composition object

    validator.py
        Pre-render layout validation
```

---

# 25. Suggested Processing Algorithm

```python
def compose_slide(slide_content, slide_frame):
    components = parse_components(slide_content)

    classify_semantic_roles(components)

    measure_components(components)

    density_metrics = calculate_density(components)

    candidate_layouts = generate_layout_candidates(
        components=components,
        density=density_metrics,
        frame=slide_frame,
    )

    valid_candidates = []

    for layout_id in candidate_layouts:
        candidate = allocate_geometry(
            layout_id=layout_id,
            components=components,
            frame=slide_frame,
        )

        validate_geometry(candidate)
        validate_minimum_dimensions(candidate)
        validate_text_fit(candidate)
        validate_component_compatibility(candidate)
        validate_hierarchy(candidate)
        validate_balance(candidate)

        if candidate.is_valid:
            candidate.score = score_layout(
                candidate=candidate,
                components=components,
                frame=slide_frame,
            )
            valid_candidates.append(candidate)

    if valid_candidates:
        return max(valid_candidates, key=lambda item: item.score)

    fallback_layouts = get_fallback_layouts(candidate_layouts)

    for fallback_layout in fallback_layouts:
        candidate = attempt_layout(
            fallback_layout,
            components,
            slide_frame,
        )

        if candidate.is_valid:
            return candidate

    return paginate_content(
        components=components,
        frame=slide_frame,
    )
```

---

# 26. Rendering Separation

The layout engine and renderer must remain separate.

## Layout engine responsibilities

- Understand content
- Classify components
- Select layout
- Allocate geometry
- Measure text
- Validate fit
- Handle fallback
- Decide pagination
- Produce resolved primitives

## Renderer responsibilities

- Translate resolved primitives into PPTX objects
- Use native editable shapes wherever possible
- Render text boxes
- Render tables
- Render charts
- Apply styling tokens
- Preserve geometry
- Avoid making layout decisions

The renderer should remain a deliberately simple painter.

```text
Layout Engine:
"What goes where and how large?"

Renderer:
"Draw exactly what the layout engine resolved."
```

The renderer should not independently decide:

- Whether to stack components
- Whether to shrink text
- Whether to split a slide
- Whether to change column count
- Whether to move components
- Whether to remove content

---

# 27. QA Requirements

The existing QA system should be extended with layout-intelligence checks.

## Structural checks

- All components fit inside slide bounds.
- All children fit inside parent bounds.
- No overlap between unrelated components.
- No title/body collision.
- No footer/content collision.
- No clipped text.
- No missing required content.
- No duplicate components.
- No orphaned continuation slide.
- All citations are preserved.
- All tables remain editable where required.
- All charts remain editable where supported.

## Layout checks

- Selected layout is compatible with component count.
- Component widths satisfy minimum values.
- Component heights satisfy minimum values.
- Primary component retains visual dominance.
- Layout score is above minimum threshold.
- No excessive density.
- No excessive whitespace.
- No invalid nesting.
- No alignment drift.
- No inconsistent gaps.
- No unreadable columns.

## Typography checks

- Font size is not below minimum.
- No unwanted autofit.
- No font distortion.
- No accidental all-caps text.
- No title case violations.
- Line spacing remains within defined range.
- Citations do not distort primary layout.

## Visual QA

Render the PPTX through:

```text
PPTX
    ↓
LibreOffice / PowerPoint rendering
    ↓
PDF
    ↓
Slide images
    ↓
Visual inspection / automated checks
```

Inspect:

- Overlap
- Overflow
- Misaligned columns
- Uneven spacing
- Weak hierarchy
- Excessive whitespace
- Source/citation collisions
- Broken table layouts
- Floating logos
- Chart label collisions
- Components stuck at the top
- Inconsistent card heights
- Broken continuation slides

---

# 28. Implementation Priorities

## Phase 1 — Foundation

Implement:

- Layout taxonomy
- Canonical layout registry
- Semantic roles
- Shared geometry frame
- Minimum component dimensions
- Component compatibility matrix

## Phase 2 — Selection Intelligence

Implement:

- Density metrics
- Candidate generation
- Layout scoring
- Layout selection rules
- Fallback chains

## Phase 3 — Geometry and Validation

Implement:

- Parent-child geometry
- Text measurement feedback loop
- Balance validation
- Invalidity rules
- Layout-level QA

## Phase 4 — Specialized Layouts

Implement:

- Chart + commentary
- Table + insight
- KPI + chart
- Timeline
- Matrix
- Comparison
- Hierarchical layouts

## Phase 5 — Pagination and Optimization

Implement:

- Logical pagination
- Semantic splitting
- Reflow strategies
- Content preservation priorities
- Multi-slide continuation handling

---

# 29. Acceptance Criteria

The implementation should be considered successful when:

1. The engine chooses between 1→1, 1→2, 1→3, 1→4, 2×2, 2×3, 3×2, asymmetric, stacked, and specialized layouts automatically.
2. Layout selection is based on measured content rather than only component count.
3. Long content does not get forced into narrow columns.
4. Three detailed cards do not automatically become three tiny columns.
5. Four detailed components use a 2×2 layout instead of a four-column layout.
6. A chart remains dominant when paired with commentary.
7. Tables are not compressed into unusable sidebars.
8. Components never fall below their minimum viable dimensions.
9. Text is not shrunk merely to preserve a layout.
10. The system uses fallback layouts before pagination.
11. Pagination happens at semantic boundaries.
12. The renderer receives resolved geometry and does not make layout decisions.
13. The final PPTX remains editable.
14. The source design language and visual hierarchy remain intact.
15. Visual QA identifies layout defects before delivery.
16. Required content and data are never silently lost.
17. The engine can explain why a layout was selected or rejected.

Example diagnostic output:

```json
{
  "selected_layout": "L07_GRID_2X2",
  "reason": [
    "4 components detected",
    "Each component exceeds three-column minimum text width",
    "Content density is medium-high",
    "2x2 provides better readability",
    "All components satisfy minimum dimensions"
  ],
  "rejected_layouts": [
    {
      "layout": "L06_FOUR_COLUMN",
      "reason": "minimum_width_violation"
    },
    {
      "layout": "L05_THREE_COLUMN",
      "reason": "component_count_mismatch"
    }
  ]
}
```

---

# 30. Final Engineering Principle

The presentation system should not be treated as a collection of independent components placed on a canvas.

It should be treated as a **content-aware composition engine**.

The correct architecture is:

```text
Content Understanding
    +
Semantic Hierarchy
    +
Layout Grammar
    +
Compatibility Rules
    +
Density Measurement
    +
Geometry Allocation
    +
Constraint Validation
    +
Adaptive Fallback
    +
Native Rendering
```

The most important rule is:

> First determine the semantic composition of the slide — single-region, split, grid, asymmetric, hierarchical, sequential, or specialized — based on component count, importance, compatibility, density, aspect ratio, and minimum geometry. Only then allocate coordinates and render the slide.

The existing design bundle already provides strong rules for typography, density, citations, tables, pagination, and QA. This new layer should be added as the missing **Layout Intelligence and Composition System**, not used to replace the existing design-token and compliance system.