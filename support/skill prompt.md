You are upgrading an existing production-grade presentation design and rendering skill.

The existing skill already contains valuable rules for:

- Design tokens
- Typography
- Color system
- Component styling
- Tables
- Charts
- Citations
- Content density
- Pagination
- Overflow handling
- Visual QA
- PPTX rendering
- Source-faithful reproduction
- Editable PowerPoint generation

Do **not** replace, simplify, weaken, or rewrite these existing rules.

Your task is to perform a careful architectural upgrade by identifying what is missing and integrating a new **Layout Intelligence and Composition Engine** layer into the existing skill.

The objective is to make the skill capable of deciding not only **how individual components look**, but also **how multiple components should be composed together on a slide**.

---

## Primary Objective

Upgrade the skill from:

```text
Component styling + rendering rules
```

to:

```text
Content understanding
→ Semantic hierarchy
→ Layout composition selection
→ Geometry allocation
→ Constraint validation
→ Adaptive fallback
→ Editable rendering
```

The system must intelligently select layouts such as:

- 1→1
- 1→2
- 1→3
- 1→4
- 2×2
- 2×3
- 3×2
- Main + Sidebar
- Main + Two Supporting Blocks
- Asymmetric split
- Vertical stack
- Chart + Commentary
- Table + Insight
- KPI + Chart
- Timeline
- Matrix
- Comparison
- Hierarchical
- Paginated layouts

Do not hardcode one layout pattern for all content.

---

# Required Instructions

## 1. First Audit the Existing Skill

Before editing anything:

1. Read the entire existing skill.
2. Identify what is already implemented.
3. Identify duplicated rules.
4. Identify missing architectural capabilities.
5. Identify where the new layout intelligence layer should be inserted.
6. Avoid creating conflicting rules.
7. Preserve all existing good design constraints.

Do not blindly append a generic design document.

The result should be an integrated, internally consistent skill.

---

## 2. Add a Formal Layout Intelligence Layer

Create a dedicated section called:

```text
Layout Intelligence and Composition Engine
```

This section must define how the system determines the overall composition of a slide before rendering components.

The system must reason about:

- Number of components
- Component types
- Component dimensions
- Text volume
- Semantic importance
- Component compatibility
- Visual hierarchy
- Aspect ratios
- Minimum viable dimensions
- Available slide area
- Visual balance
- Relationship between components
- Whether content is comparable, sequential, hierarchical, or independent

The engine should first answer:

> What is the correct structural composition of this slide?

Only then should it answer:

> Where should each component be placed?

---

## 3. Add a Canonical Layout Taxonomy

Define a layout grammar and canonical layout IDs.

At minimum include:

```text
L01_SINGLE
L02_SPLIT_EQUAL
L03_SPLIT_LEFT_DOMINANT
L04_SPLIT_RIGHT_DOMINANT
L05_THREE_COLUMN
L06_FOUR_COLUMN
L07_GRID_2X2
L08_GRID_2X3
L09_GRID_3X2
L10_VERTICAL_STACK
L11_MAIN_SIDEBAR
L12_MAIN_TWO_SUPPORT
L13_CHART_COMMENTARY
L14_TABLE_INSIGHT
L15_KPI_CHART
L16_TIMELINE
L17_MATRIX
L18_COMPARISON
L19_HIERARCHICAL
L20_PAGINATED
```

For each layout define:

- Intended use
- Component count
- Supported component types
- Minimum dimensions
- Default proportions
- Content density suitability
- When not to use it
- Fallback layouts
- Validation rules

Do not treat these as mere visual templates. Treat them as semantic composition strategies.

---

## 4. Add Content-to-Layout Selection Logic

Add explicit rules for selecting layouts based on content.

Examples:

```text
One large chart
→ full-width single layout

Two equal charts
→ equal split

Chart + short commentary
→ asymmetric split

Chart + long commentary
→ stacked or main + sidebar

Three short metrics
→ three-column layout

Four compact KPIs
→ four-column layout

Four detailed insights
→ 2×2 grid

Six short cards
→ 2×3 grid

Six detailed cards
→ 3×2 grid

Wide table
→ full-width table

Table + concise takeaway
→ table + insight

Main visual + two short insights
→ main + two supporting blocks

Thesis + supporting evidence
→ hierarchical layout
```

The skill must explicitly state that component count alone is not enough.

The engine must consider content length and minimum readable geometry.

---

## 5. Add Component Compatibility Rules

Create a compatibility matrix describing which components can coexist in the same layout.

Include examples such as:

- Chart + short insight → compatible
- Chart + long table → generally incompatible side-by-side
- Long paragraph + long paragraph → stack
- Three short cards → compatible in three columns
- Three detailed cards → do not force into three narrow columns
- Four detailed components → prefer 2×2 over four columns
- Matrix + short annotation → compatible
- Matrix + detailed table → usually separate
- Table + concise takeaway → compatible
- Multiple detailed tables → paginate or split

The engine should evaluate whether components are:

- Semantically related
- Visually compatible
- Similar in reading scale
- Suitable for the available space
- Competing for visual dominance

---

## 6. Add Semantic Roles and Slide Hierarchy

Every component should be classified using semantic roles such as:

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

Every slide should generally contain:

```text
One dominant message
One primary content/visual anchor
One secondary support layer
Optional metadata/citation layer
```

The skill must prevent unrelated components from receiving equal visual weight.

It must also support intentional asymmetry when content importance is unequal.

---

## 7. Add Shared Geometry Allocation

Add a proper geometry model based on a shared slide frame.

The system should define:

- Slide canvas
- Outer margins
- Header region
- Content region
- Footer/source region
- Columns
- Rows
- Gaps
- Anchors
- Parent-child containers
- Minimum and maximum dimensions

All component coordinates should derive from a shared geometry system.

Do not allow every component to independently invent arbitrary `x`, `y`, `width`, and `height`.

The layout engine should produce resolved geometry, and the renderer should simply draw it.

---

## 8. Add Minimum Viable Component Dimensions

Define minimum dimensions by component type.

Examples:

- Chart
- Table
- Short card
- Detailed card
- Callout
- Paragraph
- KPI
- Timeline item
- Matrix
- Commentary panel

A layout must be rejected if any component becomes too narrow or too short to remain readable.

The engine must never solve layout problems only by shrinking text.

---

## 9. Upgrade Density Analysis

The existing character-budget rules must be retained, but expanded.

Character count alone should not determine layout.

Add a multidimensional density model considering:

- Visible character count
- Component count
- Component complexity
- Number of columns
- Number of table rows/columns
- Chart annotation load
- Number of labels
- Nesting depth
- Average component area
- Smallest component area
- Text-heavy component count
- Visual competition
- Citation/metadata load where relevant

The skill should distinguish between:

```text
Vertical occupancy
```

and:

```text
Content complexity
```

Both must be evaluated.

---

## 10. Add Candidate Layout Generation and Scoring

Do not select the first layout that technically fits.

Generate multiple layout candidates and score them.

The score should consider:

```text
Hierarchy fit
Readability
Semantic fit
Component compatibility
Balance
Alignment
Source fidelity
Overflow risk
Density penalty
Tiny-component penalty
Visual competition
Excessive whitespace
Nesting complexity
```

Example:

```text
layout_score =
    hierarchy_fit
  + readability
  + semantic_fit
  + compatibility
  + balance
  + alignment
  + source_fidelity
  - overflow_penalty
  - density_penalty
  - tiny_component_penalty
  - competition_penalty
  - whitespace_penalty
```

The selected layout must be the best valid composition, not simply the first valid composition.

---

## 11. Add Adaptive Fallback Chains

Every layout should have fallback layouts.

Examples:

```text
1→4
→ 1→3 + stacked item
→ 2×2
→ 2×1 stacked
→ pagination
```

```text
1→3
→ 1→2
→ 1→1
→ pagination
```

```text
2×3
→ 3×2
→ 2×2 + remaining items
→ vertical stack
→ pagination
```

```text
Chart + commentary
→ asymmetric split
→ vertical stack
→ separate slides
```

Fallback priority should be:

```text
Reflow
→ Change layout
→ Consolidate related content
→ Reduce non-essential spacing
→ Shorten redundant content
→ Deprioritize optional content
→ Split semantically
```

Never immediately shrink all text to force the original layout.

---

## 12. Add Explicit Layout Invalidity Rules

A layout should be rejected when:

- Text overflows
- Components fall below minimum width
- Components fall below minimum height
- Title overlaps body
- Footer overlaps content
- Table columns become unreadable
- Chart labels become illegible
- Primary visual loses dominance
- Unrelated content is merged
- Child exceeds parent bounds
- Gaps become inconsistent
- Alignment drifts
- Excessive nesting occurs
- Content is clipped
- Required data is removed
- Font falls below minimum
- A continuation slide contains orphaned content
- Excessive whitespace coexists with overcrowded regions

Add these as hard constraints, not optional recommendations.

---

## 13. Add Text Measurement → Geometry Feedback

The layout process must include actual text measurement.

Required loop:

```text
Estimate content dimensions
→ Allocate geometry
→ Measure text wrapping
→ Recalculate actual height
→ Validate fit
→ Reflow or change layout
```

Measurement must account for:

- Font family
- Font size
- Font weight
- Line spacing
- Paragraph spacing
- Internal margins
- Bullet indentation
- Rich text runs
- Table padding
- Citation suffixes
- Maximum text width

Do not rely solely on character count.

---

## 14. Add Parent-Child Geometry Constraints

For nested components:

- Children must remain inside parent bounds.
- Internal spacing must be consistent.
- Child alignment should derive from parent geometry.
- Child components should not independently escape the parent region.

Add explicit bounds validation.

---

## 15. Add Specialized Composition Logic

Add specific composition rules for:

### Charts

- Maintain aspect ratio.
- Preserve visual dominance.
- Avoid narrow charts with large legends.
- Avoid placing two complex charts side-by-side.
- Use stacked layout when necessary.

### Tables

- Prefer full-width placement.
- Avoid detailed tables in sidebars.
- Use table + insight where appropriate.
- Split tables logically when required.
- Preserve required data.

### Cards

- Do not force equal widths/heights when content differs.
- Use columns only for compact cards.
- Use 2×2 or stacked layouts for detailed cards.

### Timelines

- Choose horizontal, vertical, or multi-row based on event count and text length.
- Preserve chronological order.
- Paginate when necessary.

### Matrices

- Preserve axis readability.
- Keep matrix as the primary visual.
- Use side annotations rather than dense quadrant paragraphs.

### Comparisons

- Preserve consistent structure.
- Use tables for detailed comparisons.
- Avoid narrow three-way comparison columns when content is long.

---

## 16. Add Slide Balance Validation

After geometry allocation, validate visual balance.

Check:

- Occupied area
- Empty area
- Left/right distribution
- Top/bottom distribution
- Visual weight
- Text weight
- Primary anchor position
- Component size variance
- Uneven density
- Excessive whitespace
- Content stuck at the top
- Weak primary hierarchy

Do not force symmetry when semantic importance is unequal.

The goal is balanced composition, not mathematically equal regions.

---

## 17. Keep Renderer Responsibilities Separate

The renderer must not make layout decisions.

### Layout engine decides:

- Layout type
- Component positions
- Component sizes
- Reflow
- Fallback
- Pagination
- Hierarchy
- Constraints

### Renderer decides:

- How to draw the resolved primitives
- Which native PPTX object to use
- Text box rendering
- Table rendering
- Chart rendering
- Applying design tokens

The renderer should behave like a deterministic painter.

```text
Layout engine:
"What goes where?"

Renderer:
"Render exactly what was resolved."
```

---

## 18. Add Explainability and Diagnostics

The layout engine should explain:

- Why a layout was selected
- Which layouts were considered
- Which layouts were rejected
- Which constraint caused rejection
- Why fallback occurred
- Why pagination was required

Example diagnostic output:

```json
{
  "selected_layout": "L07_GRID_2X2",
  "reason": [
    "Four detailed components detected",
    "Four-column layout violates minimum width",
    "2x2 provides sufficient reading width",
    "All components satisfy minimum dimensions"
  ],
  "rejected_layouts": [
    {
      "layout": "L06_FOUR_COLUMN",
      "reason": "minimum_width_violation"
    }
  ]
}
```

This is important for debugging backend layout issues.

---

## 19. Preserve Existing Rules

Do not remove or weaken existing rules regarding:

- Typography
- Sentence case
- Font families
- Minimum font sizes
- Line spacing
- Tables
- Citations
- Character budgets
- Pagination
- Source fidelity
- Editable PPTX
- Visual QA
- Overflow handling
- Design tokens
- Component styling

Integrate the new composition engine with the existing rules.

Where conflicts exist, prioritize:

```text
Meaning
→ Required data
→ Readability
→ Semantic grouping
→ Hierarchy
→ Structural correctness
→ Source visual intent
→ Exact geometry
```

---

## 20. Expected Output

Return the upgraded skill as a complete, production-ready document.

Do not only provide recommendations.

You must:

1. Audit the existing skill.
2. Identify missing layout-intelligence capabilities.
3. Integrate those capabilities into the existing skill.
4. Preserve all existing valid rules.
5. Remove duplication and contradictions.
6. Add implementation-ready schemas, algorithms, constraints, and decision rules.
7. Make the skill usable by an LLM that generates presentation layouts.
8. Ensure the skill is explicit enough that the LLM does not default to arbitrary placement or generic card grids.

The final upgraded skill should function as a complete specification for:

```text
Content-aware presentation composition
+
Source-faithful design reproduction
+
Adaptive layout selection
+
Editable PPTX rendering
+
Constraint-based validation
```

Do not produce a high-level essay. Produce an integrated operational skill that an LLM and backend engineer can directly follow.