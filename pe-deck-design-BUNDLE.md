# pe-deck-design — single-file bundle

This one file contains every file of the `pe-deck-design` skill, verbatim, each fenced and labeled with its original path. Nothing has been edited, reformatted, or truncated in bundling — every block below is byte-for-byte the same file already delivered separately. Extract each block back to its labeled path to restore the working skill folder exactly. A checksum manifest and an extraction script are included at the end.

## Original folder layout

pe-deck-design/

  SKILL.md

  assets/design-tokens.json

  assets/example\_spec.json

  scripts/layout\_engine.py

  scripts/pe\_components.js

  scripts/audit\_deck.py

  scripts/example\_build.js

  references/typography.md

  references/components.md

  references/tables.md

  references/citations.md

  references/density-and-pagination.md

  references/source-spec.md

## FILE: `SKILL.md`

\---

name: pe-deck-design

description: "Design system and layout engine for consulting-grade and private-equity PowerPoint decks — the MBB/expert-report register, not the sales-pitch register. Use this skill WHENEVER a .pptx deck is being created or edited for an investor, PE analyst, diligence, IC memo, market study, expert report, strategy review, or any audience that expects dense, cited, small-type consulting slides. Trigger on: 'investment deck', 'IC memo', 'diligence pack', 'market study', 'expert report', 'BCG/McKinsey/Bain style', 'consulting slides', 'board deck', 'CIM', 'teaser', or any deck with tables, sourced metrics, numbered citations, or a References appendix. This skill OVERRIDES the generic pptx skill's typography and design guidance, which is sized for presentation decks and will produce wrong output here. It provides design tokens, a deterministic layout engine, a pptxgenjs component library, and a post-build compliance auditor."

\---

\# PE / consulting deck design

This skill encodes one specification. Everything in it traces back to that spec, and

\`assets/design-tokens.json\` marks each value \`DOC\` (stated in the spec) or \`DERIVED\`

(computed from a spec rule, or a geometry constant the spec implies but does not number).

\*\*Never silently change a \`DOC\` value.\*\* Changing one is a spec change, not a styling choice.

\#\# Precedence — read this first

This skill composes with the built-in \*\*pptx\*\* skill. Split of responsibility:

| Concern | Owner |

|---|---|

| File mechanics: pptxgenjs gotchas, XML editing, \`validate.py\`, rendering to images | \*\*pptx\*\* skill |

| Type scale, grid, components, tables, citations, density, pagination | \*\*this skill\*\* |

Where they conflict, \*\*this skill wins\*\*, because the generic guidance is calibrated for

presentation decks and this register is different:

| Generic pptx skill says | Here |

|---|---|

| Slide title 36–44pt | \*\*14–16pt.\*\* A consulting title is a full sentence stating the so-what, not a headline. |

| Body 14–16pt | \*\*9–10pt.\*\* |

| Section header 20–24pt | \*\*12–14pt.\*\* |

| "Don't create text-only slides", "every slide needs a visual element" | A dense cited table \*is\* the visual. Do not add decorative imagery to a diligence page. |

| "Pick a bold, content-informed colour palette" | Restrained neutral \+ one primary \+ one accent. The data carries the interest. |

| Default canvas 10" × 5.625" | \*\*13.333" × 7.5".\*\* Non-negotiable — see below. |

Everything else from the pptx skill still applies, especially: hex colours without \`\#\`,

never reuse an options object, \`isTextBox: true\` on every \`addText\`, \`margin: 0\` when

aligning to a shape, no accent rules under titles, no decorative stripes, and running

\`scripts/office/validate.py\` after every build.

\*\*The canvas is load-bearing.\*\* Every point size in this spec assumes 13.333" wide. On

pptxgenjs's default 10" canvas the same 9pt body renders \~33% larger relative to the slide

and the entire scale collapses. \`pe\_components.js\` sets this before the first slide exists;

if you hand-roll a deck, set it yourself.

\#\# The pipeline

Four stages, in order. Skipping stage 1 is the most common way to produce a bad deck,

because layout decisions then get made per-component instead of per-slide.

\`\`\`

content spec (JSON)

   │

   ├─1─► layout\_engine.py    density band → type scale, component verdicts, merge plan

   │

   ├─2─► pe\_components.js    measure → distribute → render  (writes the .pptx)

   │

   ├─3─► audit\_deck.py       compliance audit against the emitted XML

   │

   └─4─► render \+ look       soffice → pdftoppm → view every slide

\`\`\`

\`\`\`bash

python3 scripts/layout\_engine.py spec.json               \# 1\. plan

node    scripts/example\_build.js deck.pptx               \# 2\. build (copy this file)

python3 scripts/audit\_deck.py deck.pptx                  \# 3\. audit

python3 /mnt/skills/public/pptx/scripts/office/validate.py deck.pptx   \# file integrity

\`\`\`

\`layout\_engine.py \--selftest\` verifies the engine against its own rules; run it if you

change a token.

\#\# Stage 1 — density decides typography

This is the core inversion, and the part most builders get backwards. \*\*You do not pick a

font size. You count the content, and the count picks the size.\*\*

Character budget \= every piece of visible copy on the slide — title, subtitles, paragraphs,

bullets, card titles and bodies, callouts, table text, chart labels. \*\*Citations are

excluded\*\*: they are traceability metadata, not content.

| Characters | Band | Scale | Action |

|---|---|---|---|

| ≤ 550 | sparse | title 16 / header 14 / body 10 / table 9 / foot 8 | Scale up, widen whitespace, or pull related content forward |

| 551–900 | balanced | title 15 / header 13 / body 10 / table 9 / foot 8 | \*\*Preferred. Ship it.\*\* |

| 901–1000 | dense | title 14 / header 12 / body 9 / table 8 / foot 7 | Optimise: condense copy before changing layout |

| 1001–1200 | dense | same | Strong overflow check: reflow → consolidate → shorten → deprioritise |

| \> 1200 | overflow | — | Recompose or split at a logical boundary |

Two invariants hold across every band:

\- \*\*Hierarchy never crosses.\*\* Each role moves inside its own range; title is always above

  header, header always above body. Only the overall scale shifts.

\- \*\*8pt is the content floor, 16pt the ceiling.\*\* 7pt exists only for source/footnote and

  citation metadata. This is the single reconciliation in the token set (the spec states a

  global 8pt minimum \*and\* a 7–8pt footnote range) and it is recorded as such in the tokens.

\*\*Never solve a fit problem by shrinking type.\*\* The escalation order is fixed:

reflow → consolidate → shorten → deprioritise → split. PowerPoint's autofit shrink is

literally horizontal/vertical font scaling, which the spec forbids; \`audit\_deck.py\` fails

the build if it finds \`normAutofit fontScale\` anywhere.

\#\# Stage 2 — two-phase layout

\`pe\_components.js\` never draws a component when it is declared. It measures everything

first, distributes the leftover vertical space, then renders.

That exists to kill one specific defect: the correct-looking top third and dead bottom

half that every naive slide builder produces. Surplus space flows back to the growable

components (capped per type — a card is a container, so stretching it just moves dead

space inside the border; a table genuinely reads better with taller rows) and then to the

gaps (capped), and what remains is reported as underfill.

\`\`\`js

const { Deck } \= require('./pe\_components');

const deck \= new Deck({ palette: 'graphite\_navy' });

const s \= deck.slide({ band: 'balanced', eyebrow: 'STRATEGY',

                       title: 'Sentence-case sentence stating the so-what' });

await s.compose(\[

  { type: 'body',     text: '...', cite: \[1\] },

  { type: 'callouts', items: \[{ value: '46.74%', label: '...', cite: \[194\] }\] },

  { type: 'header',   text: 'Why this matters' },

  { type: 'bullets',  items: \[{ text: '...', cite: \[1\] }\] },

  { type: 'table',    headers: \[...\], rows: \[...\], hasTags: true, zebra: false },

  { type: 'cards',    items: \[{ title: '...', body: '...', cite: \[51\] }\] },

  { type: 'rail',     items: \[{ title: '...', body: '...', cite: \[66, 67, 68\] }\] },

\]);

s.source().pageNumber(2);

deck.references(SOURCE\_MAP);      // one global index, deck-wide

await deck.save('deck.pptx');     // warns on overrun and on genuine underfill

\`\`\`

\`compose()\` \*\*throws\*\* rather than degrade: 7+ cards, 7+ rail items, 5+ callouts, zebra

striping combined with tags, ragged table rows, or content that cannot fit even at minimum

sizes. Those are spec violations, not layout problems, and the fix is editorial.

Read \`scripts/example\_build.js\` before writing a new deck. The shape of those calls is the

skill; it builds a complete five-slide deck from the spec's own worked example.

\#\# Component law

Not configurable. These are the spec's definitions, and they are the only thing that

distinguishes the three containers from each other.

| Component | Border | Fill | Count rules |

|---|---|---|---|

| \*\*Card\*\* | 1pt neutral | \*\*none\*\* | 1–3 larger with more internal whitespace · 4–6 compact · 7+ switch to a rail or grouped structure |

| \*\*Rail\*\* | 1pt | gradient \*\*of the border colour\*\* | 2–4 generous · 5–6 compact · 7+ split or change component |

| \*\*Callout\*\* | \*\*none\*\* | gradient \*\*of the primary colour\*\* | 1 strong emphasis · 2 balanced by content length · 3+ only if each is a distinct insight |

\- Cards in a row share a common height. Widths need \*\*not\*\* be equal — don't force

  symmetry when content lengths differ materially.

\- Rail item width \*\*follows content length\*\*; a short item should not inflate to match a

  long one. Preserve order when the data is a sequence.

\- Callout heights need \*\*not\*\* match. Each callout carries exactly one data point or message.

\- Long content: reduce padding and spacing \*\*before\*\* reducing font size. If it still

  doesn't fit, restructure or move it — never shrink below the minimum.

\*\*Gradients:\*\* pptxgenjs cannot emit an OOXML gradient fill. \`pe\_components.js\` renders

them as alpha PNGs through \`sharp\` and places them behind the shape — the only route that

survives a round trip into PowerPoint. Do not substitute a solid fill; the gradient is what

separates a rail from a card.

Details and the full count-rule text: \`references/components.md\`.

\#\# Tables

The single sharpest rule, and the one most often broken:

\> \*\*Zebra striping and tags cannot coexist.\*\* If rows carry labels, tags, pills or any

\> visual indicator, keep the background uniform and let the tags create the

\> differentiation. Zebra is permitted only on dense, data-only tables with no tags, no

\> highlighted rows, and no coloured cells, where striping genuinely aids row scanning.

\`compose()\` throws on the combination; \`audit\_deck.py\` detects it in the emitted XML too,

in case a table was built by hand.

Also: subtle horizontal dividers only (no boxed cells, no heavy gridlines); the primary

column visually dominant; descriptive columns wide, numeric and short-label columns narrow;

numbers right-aligned with consistent decimals and units; \*\*1 line preferred, 2 lines

maximum\*\* per cell — past that, restructure the table rather than shrink the font.

Table overflow escalation is its own ordered list: column widths → cell padding → wrapping

→ overall table size → and only then typography, within range.

Full rules: \`references/tables.md\`.

\#\# Citations

Numbered \`\[n\]\` throughout, placed immediately after the claim, metric, statement, chart or

data point they support. \`\[3\]\` · \`\[3, 7\]\` · \`\[3-7\]\` for consecutive runs — both

\`layout\_engine.py\` and \`pe\_components.js\` collapse runs identically, so the two never disagree.

Citations are \*\*metadata, not content\*\*: excluded from the character budget, visually

subordinate (same family, one step down, 8–9pt, regular weight, muted colour), and never

bold, uppercase, badged, pilled, bordered, or given their own card. They must never change

a component's layout — no shrinking main content and no growing a component to fit a source.

Never put full source names, publication titles or URLs inside a card, callout, chart or

table. One global source index across the deck: \`\[3\]\` means the same source on every slide.

Past 6–8 sources on a slide, keep the \`\[n\]\` markers and move the full list to References.

One pptxgenjs constraint worth knowing, since it shapes the bullet implementation: a

bulleted paragraph \*\*cannot\*\* hold two differently-styled runs. Any run without a bullet

option emits its own \`\<a:pPr\>\` with \`\<a:buNone/\>\` and silently kills the bullet for the

whole paragraph; giving every run the bullet option instead splits them into separate

bulleted paragraphs. So "bulleted claim \+ muted citation" is unreachable through \`addText\`

bullets, and \`pe\_components.js\` draws the marker as its own text box at a fixed hanging

indent. That also buys exact indent control the built-in bullet doesn't give.

Full rules: \`references/citations.md\`.

\#\# Pagination

\> \*\*Fit \+ Related \+ Readable → merge. Otherwise → new slide.\*\*

One section \= one slide by default. Before creating a new slide, check whether the next

content fits on the current one. If related content fits without crowding, merge it. If it

doesn't fit, split — but split at a \*\*logical sub-topic boundary\*\*, moving a meaningful

sub-topic rather than leftover content. Every slide, including a continuation, must feel

complete: never a slide carrying one orphaned card or bullet.

Never merge unrelated content just to fill space, and never shrink below minimum type to

avoid a new slide.

\`layout\_engine.py\` emits this as an explicit per-slide plan (\`keep\` / \`merge\_next\` /

\`split\`) with the reasoning attached. Note that vertical emptiness and character load are

different axes: a slide at 800 characters laid out horizontally is dense in the sense the

spec measures, even if it doesn't stack tall. The build only flags underfill when \*\*both\*\*

the vertical space is empty and the character load is below target.

Full rules: \`references/density-and-pagination.md\`.

\#\# Typography rules

Sentence case for titles and headers. ALL CAPS only for short labels, tags, metadata and

eyebrows (≤18 chars). \*\*Never Title Case.\*\* \`audit\_deck.py\` flags both violations.

Never distort a font — no horizontal or vertical scaling, no autofit shrink. Fix fit through

font size (within range), text box size, spacing, or layout.

Line spacing: body 1.10–1.25×, headers 0.95–1.10×, citations 1.10–1.20×. Paragraph spacing

3pt after, section spacing 8pt after.

\*\*Fonts: Manrope for headers, Arial for body.\*\* Manrope has no metric-compatible substitute

in the local renderer, so \*\*header fit in PDF/image QA is approximate\*\* — size header

containers with \~10% slack and don't trust a borderline header overflow read from the

preview. \`estimateLines()\` deliberately over-estimates header width for this reason. Body

text in Arial renders true-to-width, so body overflow reads from QA are trustworthy.

Full rules: \`references/typography.md\`.

\#\# Stage 3 — audit, and what each failure means

\`audit\_deck.py\` reads the emitted XML, so it catches what the plan can't: a stray run size,

an autofit shrink, Title Case that survived editing, a hand-built table with zebra and tags,

a shape outside the margins. Exit code 1 on any FAIL.

| Rule | Level | Meaning |

|---|---|---|

| \`type.min\` / \`type.max\` | FAIL | Run outside 7–16pt, or 7pt used for body content |

| \`type.distortion\` | FAIL | \`normAutofit\` is scaling the font — restructure, don't squeeze |

| \`case.allcaps\` | FAIL | Caps run longer than a label |

| \`grid.margin\` / \`grid.vertical\` | FAIL | Shape outside the content band — content running off-slide |

| \`cite.url\` / \`cite.weight\` | FAIL | Raw URL on a slide, or a bold citation |

| \`density.hard\` | FAIL | Past 1,200 characters |

| \`table.zebra\` | FAIL | Striping on a tagged table |

| \`decoration.stripe\` | WARN | Thin textless bar — the accent-stripe tell |

| \`case.titlecase\`, \`table.wrap\`, \`cite.density\`, \`density.soft\` | WARN | Editorial, not structural |

The References/Appendix slide is auto-detected and exempted from the citation-density and

footnote-size checks — it is the one place full source strings and 7pt metadata belong.

\#\# Stage 4 — look at it

The audit cannot see overlap, collision or visual balance. Render and inspect every slide:

\`\`\`bash

python3 /mnt/skills/public/pptx/scripts/office/soffice.py \--headless \--convert-to pdf deck.pptx

rm \-f slide-\*.jpg && pdftoppm \-jpeg \-r 130 deck.pdf slide

\`\`\`

Look for: text colliding with a container edge, a card title running into its own body

(the classic Manrope-measurement failure), source lines colliding with content, columns

out of alignment, and any component that grew tall with its content stuck at the top.

\#\# Editorial standard

The design system is necessary but not sufficient. For this audience:

\- \*\*Titles are assertions, not labels.\*\* "Club-store placement concentrates presence in the

  West and Southeast", not "Regional footprint". The title carries the finding; the body

  carries the evidence.

\- \*\*Every number is cited.\*\* An uncited metric in a diligence pack is a liability.

\- \*\*Distinguish absence of evidence from evidence of absence.\*\* "No 2016 club placement"

  means uncovered, not lost — and that distinction changes how it is priced.

\- \*\*Two strong components beat six weak ones.\*\* Prioritise information, not component count.

\#\# Files

| Path | Purpose |

|---|---|

| \`assets/design-tokens.json\` | Every value, with \`DOC\`/\`DERIVED\` provenance. Single source of truth. |

| \`scripts/layout\_engine.py\` | Stage 1\. Density, scale, verdicts, merge plan. \`--selftest\` included. |

| \`scripts/pe\_components.js\` | Stage 2\. Two-phase layout \+ component library. |

| \`scripts/audit\_deck.py\` | Stage 3\. Post-build compliance audit. |

| \`scripts/example\_build.js\` | Worked five-slide reference deck. Start here. |

| \`references/typography.md\` | Full type rules and the scale-resolution logic |

| \`references/components.md\` | Card / rail / callout rules in full |

| \`references/tables.md\` | Full table rules |

| \`references/citations.md\` | Full citation rules |

| \`references/density-and-pagination.md\` | Character budget, merging, slide rules |

| \`references/source-spec.md\` | The original specification, preserved in full |

\#\# Dependencies

\`pptxgenjs\`, \`sharp\` (npm, preinstalled) · Python 3 stdlib only for both scripts ·

LibreOffice \+ \`pdftoppm\` for visual QA, via the pptx skill's \`soffice.py\` wrapper.

## FILE: `assets/design-tokens.json`

{

  "$schema": "pe-deck-design/1.0",

  "provenance": {

    "DOC": "value stated verbatim in the source specification",

    "DERIVED": "computed from a DOC rule, or a geometry constant the DOC implies but does not number",

    "note": "Never edit a DOC value silently. Changing one is a spec change, not a styling choice."

  },

  "canvas": {

    "layout": "LAYOUT\_WIDE",

    "width\_in": 13.333,

    "height\_in": 7.5,

    "provenance": "DERIVED",

    "why": "All DOC point sizes (8-16pt) assume a 13.33in canvas. On pptxgenjs's default 10in canvas the same pt values render \~33% larger relative to the slide and the whole scale breaks."

  },

  "grid": {

    "margin\_top\_in": 0.42,

    "margin\_bottom\_in": 0.40,

    "margin\_left\_in": 0.50,

    "margin\_right\_in": 0.50,

    "columns": 12,

    "gutter\_in": 0.16,

    "column\_width\_in": 0.9777,

    "title\_band\_h\_in": 0.55,

    "footer\_band\_h\_in": 0.28,

    "content\_top\_in": 1.05,

    "content\_bottom\_in": 6.95,

    "content\_width\_in": 12.333,

    "content\_height\_in": 5.90,

    "provenance": "DERIVED",

    "why": "DOC requires 'align tables to the slide's main content grid' and 'consistent left/right margins across slides' but does not number the grid. These constants are that grid."

  },

  "type": {

    "fonts": {

      "header": "Manrope",

      "body": "Arial",

      "header\_fallback": "Calibri",

      "provenance": "DOC",

      "qa\_warning": "Manrope is not metric-compatible with anything LibreOffice substitutes. Header fit in local PDF/image QA is APPROXIMATE. Size header containers with \~10% horizontal slack and never trust a borderline header overflow read from the preview."

    },

    "min\_pt": 8,

    "max\_pt": 16,

    "footnote\_floor\_pt": 7,

    "footnote\_floor\_note": "DOC sets a global 8pt minimum AND separately sets source/footnote at 7-8pt. Resolution: 8pt is the floor for CONTENT; 7pt is permitted only for source/footnote/citation metadata. This is the single reconciliation in the token set.",

    "scales": {

      "sparse": {

        "title": 16, "header": 14, "body": 10, "key\_insight": 10,

        "table\_header": 10, "table\_body": 9, "table\_metric": 10, "table\_title": 14,

        "chart\_label": 9, "footnote": 8, "citation": 9

      },

      "balanced": {

        "title": 15, "header": 13, "body": 10, "key\_insight": 10,

        "table\_header": 10, "table\_body": 9, "table\_metric": 10, "table\_title": 13,

        "chart\_label": 9, "footnote": 8, "citation": 9

      },

      "dense": {

        "title": 14, "header": 12, "body": 9, "key\_insight": 9,

        "table\_header": 9, "table\_body": 8, "table\_metric": 9, "table\_title": 12,

        "chart\_label": 8, "footnote": 7, "citation": 8

      }

    },

    "scale\_note": "DOC: 'The relative hierarchy between title, header, body, chart labels, and footnotes should remain consistent; only the overall scale changes.' Each role therefore moves within its own DOC-defined range; roles never cross.",

    "role\_ranges\_doc": {

      "title": \[14, 16, "Bold"\],

      "header": \[12, 14, "Medium"\],

      "body": \[9, 10, "Regular"\],

      "key\_insight": \[9, 10, "Regular"\],

      "table\_title": \[12, 14, "Semibold"\],

      "table\_header": \[9, 10, "Semibold"\],

      "table\_body": \[8, 9, "Regular"\],

      "table\_metric": \[9, 10, "Semibold"\],

      "chart\_label": \[8, 9, "Regular"\],

      "footnote": \[7, 8, "Regular"\],

      "citation": \[8, 9, "Regular"\],

      "provenance": "DOC"

    },

    "line\_spacing\_multiple": {

      "body\_min": 1.10,

      "body\_max": 1.25,

      "header\_min": 0.95,

      "header\_max": 1.10,

      "citation\_min": 1.10,

      "citation\_max": 1.20,

      "provenance": "DOC"

    },

    "paragraph\_space\_after\_pt": 3,

    "section\_space\_after\_pt": 8,

    "provenance\_spacing": "DOC",

    "case": {

      "title": "sentence",

      "header": "sentence",

      "body": "sentence",

      "citation": "sentence",

      "allcaps\_allowed\_for": \["short label", "tag", "metadata", "eyebrow"\],

      "allcaps\_max\_chars": 18,

      "title\_case\_banned": true,

      "provenance": "DOC"

    },

    "distortion": {

      "horizontal\_scale\_allowed": false,

      "vertical\_scale\_allowed": false,

      "autofit\_font\_scale\_allowed": false,

      "provenance": "DOC",

      "why": "DOC: 'Do not stretch, compress, or scale the font.' PowerPoint's normAutofit fontScale is exactly this distortion applied automatically, so autofit shrink is banned; fix fit by layout, not by squeezing glyphs."

    }

  },

  "density": {

    "unit": "characters of visible copy, citations excluded",

    "target\_min": 600,

    "target\_max": 900,

    "soft\_max": 1000,

    "hard\_max": 1200,

    "provenance": "DOC",

    "bands": \[

      { "name": "sparse",     "max": 550,  "action": "Scale up. Increase whitespace. Consider pulling related content forward from the next slide." },

      { "name": "balanced",   "max": 900,  "action": "Preferred. Ship it." },

      { "name": "dense",      "max": 1000, "action": "Optimize if possible: condense copy before changing layout." },

      { "name": "dense",      "max": 1200, "action": "Strong overflow check. Reflow, consolidate, shorten, deprioritise." },

      { "name": "overflow",   "max": null, "action": "Recompose or split at a logical content boundary. Never shrink type to fit." }

    \]

  },

  "components": {

    "card": {

      "border\_pt": 1,

      "border\_role": "neutral",

      "fill": "none",

      "provenance": "DOC",

      "counts": {

        "1-3": "Larger cards, stronger typography, more internal whitespace.",

        "4-6": "Reduce card width and spacing; keep content readable.",

        "7+": "Do not keep shrinking. Switch to a rail or grouped structure."

      },

      "radius\_in": 0.06,

      "pad\_x\_in": 0.16,

      "pad\_y\_in": 0.12,

      "gap\_in": 0.18,

      "equal\_height\_within\_row": true,

      "equal\_width\_required": false,

      "one\_message\_per\_card": true

    },

    "rail": {

      "border\_pt": 1,

      "fill": "gradient of the border colour",

      "provenance": "DOC",

      "counts": {

        "2-4": "Larger item widths, generous spacing.",

        "5-6": "Compact spacing, smaller item widths.",

        "7+": "Split the rail or change the component. Never drop below min type."

      },

      "radius\_in": 0.06,

      "pad\_x\_in": 0.16,

      "pad\_y\_in": 0.12,

      "gap\_in": 0.14,

      "width\_follows\_content": true,

      "preserve\_order": true

    },

    "callout": {

      "border\_pt": 0,

      "fill": "gradient of the primary colour",

      "provenance": "DOC",

      "counts": {

        "1": "Stronger visual emphasis, more whitespace.",

        "2": "Balance by content length; identical heights not required.",

        "3+": "Only when each is a distinct insight; otherwise combine."

      },

      "radius\_in": 0.06,

      "pad\_x\_in": 0.18,

      "pad\_y\_in": 0.14,

      "gap\_in": 0.18,

      "equal\_height\_required": false

    },

    "gradient": {

      "tint\_start\_pct": 10,

      "tint\_end\_pct": 2,

      "angle\_deg": 135,

      "provenance": "DERIVED",

      "why": "DOC specifies gradient fills. pptxgenjs cannot emit a gradient fill, so gradients ship as an alpha PNG generated at build time (scripts/pe\_components.js). Tint percentages keep the fill subordinate to the text above it."

    }

  },

  "table": {

    "cell\_pad\_x\_pt": \[6, 8\],

    "cell\_pad\_y\_pt": \[4, 6\],

    "provenance": "DOC",

    "borders": "Subtle horizontal dividers only. No heavy gridlines. No box around every cell.",

    "row\_height": "Minimum required for content; no excess whitespace.",

    "max\_wrap\_lines": 2,

    "preferred\_wrap\_lines": 1,

    "numeric\_align": "right",

    "text\_align": "left",

    "header\_align": "match column",

    "zebra": {

      "allowed\_when": "Dense data-only table with no tags, pills, labels or highlighted rows, where striping genuinely improves row scanning.",

      "banned\_when": "Rows contain labels, tags, pills or other visual indicators; or the table already uses highlighted rows or coloured tags.",

      "provenance": "DOC"

    },

    "overflow\_order": \[

      "column widths",

      "cell padding",

      "wrapping",

      "overall table size",

      "typography (only within the allowed range, and last)"

    \],

    "provenance\_overflow": "DOC",

    "column\_width\_policy": "Wider for descriptive text, narrower for numbers, percentages, dates and short labels. No unnecessarily wide empty columns. Primary column visually dominant.",

    "emphasis": "Bold only key values, totals or key rows. One consistent treatment for highlighted cells. One accent colour maximum."

  },

  "citation": {

    "style": "numbered",

    "single": "\[3\]",

    "multiple\_non\_consecutive": "\[3, 7\]",

    "consecutive\_range": "\[3-7\]",

    "placement": "immediately after the claim, metric, statement, chart or data point it supports",

    "size\_pt": \[8, 9\],

    "weight": "Regular",

    "colour\_role": "muted",

    "line\_spacing": \[1.1, 1.2\],

    "case": "sentence",

    "banned": \["bold", "uppercase", "coloured badges", "filled pills", "borders", "separate citation cards", "full source names inside components", "URLs inside components", "publication titles inside components"\],

    "chart\_form": "Source \[3, 5\]  — small line at the bottom of the visual",

    "table\_form": "One table-level citation when the same sources support the table. Cell-level only when individual values come from different sources.",

    "grouping\_threshold": 3,

    "appendix\_threshold": 6,

    "global\_index": true,

    "full\_source\_format": "\[3\] Gartner, Semiconductor Forecast, 2025",

    "layout\_impact": "none — citations must never change component layout, shrink main content, or increase component height",

    "excluded\_from\_char\_budget": true,

    "provenance": "DOC"

  },

  "palettes": {

    "provenance": "DERIVED",

    "why": "DOC names colour ROLES (neutral border, primary gradient, one accent, muted citation) but no hex values. These palettes bind the roles. Swap the hexes, keep the roles.",

    "default": "graphite\_navy",

    "graphite\_navy": {

      "primary": "1F3864",

      "accent": "C8102E",

      "ink": "1A1A1A",

      "body": "333333",

      "muted": "6E7278",

      "neutral\_line": "D2D5DA",

      "neutral\_fill": "F4F5F7",

      "surface": "FFFFFF",

      "positive": "1F7A54",

      "negative": "B3261E"

    },

    "slate\_teal": {

      "primary": "12414A",

      "accent": "C2703B",

      "ink": "13191C",

      "body": "323A3D",

      "muted": "6B7578",

      "neutral\_line": "D3D8D9",

      "neutral\_fill": "F3F6F6",

      "surface": "FFFFFF",

      "positive": "1F7A54",

      "negative": "B3261E"

    },

    "ink\_oxblood": {

      "primary": "23262B",

      "accent": "7A1F2B",

      "ink": "111316",

      "body": "31353B",

      "muted": "70757C",

      "neutral\_line": "D6D8DC",

      "neutral\_fill": "F5F5F7",

      "surface": "FFFFFF",

      "positive": "1F7A54",

      "negative": "B3261E"

    }

  }

}

## FILE: `assets/example_spec.json`

{

  "deck": "Project Ardent — Del Real Foods",

  "palette": "graphite\_navy",

  "slides": \[

    {

      "id": "s1", "section": "company", "eyebrow": "COMPANY",

      "title": "Del Real Foods is a refrigerated Hispanic heat-and-eat manufacturer with concentrated customer exposure",

      "blocks": \[

        { "type": "body", "body": "The company sells branded meal components and full meal solutions through retail, club, grocery, foodservice, institutional and online channels, with revenue recognised when products ship or are delivered.", "cite": \[1\] },

        { "type": "callout", "items": \[

          { "value": "46.74%", "label": "Value-added meats revenue share", "cite": \[194\] },

          { "value": "\>60%", "label": "Top 10 customer concentration", "cite": \[1\] },

          { "value": "500+", "label": "Mira Loma plant workers", "cite": \[184\] }

        \] }

      \]

    },

    {

      "id": "s2", "section": "company", "eyebrow": "COMPANY",

      "title": "Why the concentration matters",

      "blocks": \[

        { "type": "bullets", "bullets": \[

          "Concentration above 60% in the top ten accounts makes customer retention the single largest downside driver in the base case."

        \] }

      \]

    },

    {

      "id": "s3", "section": "footprint", "eyebrow": "FOOTPRINT",

      "title": "Club-store placement concentrates presence in the West and Southeast",

      "blocks": \[

        { "type": "table",

          "headers": \["Region", "Presence", "Key markets and strategic role"\],

          "rows": \[

            \["Northwest", "Major", "Portland, Salem, Central Point — club placement extended reach for ready-in-minutes meals."\],

            \["Los Angeles", "Major", "Inglewood, Marina del Rey, Norwalk — club placement opened a prepared-foods outlet."\],

            \["Southeast", "Major", "Atlanta, Charlotte, Myrtle Beach — club placement gave Southeast distribution."\],

            \["Midwest", "Moderate", "Chicago, Plainfield, Middleton — no 2016 club placement left the region uncovered."\],

            \["Texas", "Moderate", "Frisco, Fort Worth — no 2016 club placement left the region uncovered."\]

          \],

          "zebra": false, "has\_tags": true, "cite": \[1, 184\] }

      \]

    },

    {

      "id": "s4", "section": "mna", "eyebrow": "M\&A",

      "title": "Acquiring a frozen adjacency broadens format mix and hedges bid exposure",

      "blocks": \[

        { "type": "body", "body": "A frozen-adjacent asset improves the weaker position in price-sensitive institutional bids and ultra-low-cost channels.", "cite": \[52, 53\] },

        { "type": "rail", "items": \[

          { "title": "Padrino Foods", "body": "Adjacent frozen and authentic Mexican depth.", "cite": \[66, 67, 68, 69\] },

          { "title": "Texas Tamale Company", "body": "Frozen tamale platform with regional appeal.", "cite": \[70, 71, 72, 73, 74\] },

          { "title": "Tucson Foods", "body": "Frozen shelf-life and tamale adjacency.", "cite": \[55, 56, 57, 58, 59, 60\] }

        \] }

      \]

    }

  \]

}

## FILE: `scripts/layout_engine.py`

\#\!/usr/bin/env python3

"""

layout\_engine.py — the deterministic half of the pe-deck-design skill.

Runs BEFORE any .pptx is written. Takes a content spec (JSON), and for each

slide returns: character load, density band, the resolved typography scale,

per-component verdicts, and pagination/merge instructions.

Nothing here is a matter of taste. Every threshold traces to a token in

assets/design-tokens.json, which in turn traces to the source specification.

Usage

\-----

    python3 scripts/layout\_engine.py spec.json                 \# human report

    python3 scripts/layout\_engine.py spec.json \--json          \# machine plan

    python3 scripts/layout\_engine.py spec.json \--json \-o plan.json

    python3 scripts/layout\_engine.py \--selftest

Spec format

\-----------

{

  "deck": "Project Ardent — Del Real Foods",

  "palette": "graphite\_navy",

  "slides": \[

    {

      "id": "s2",

      "section": "channel",

      "title": "Traditional grocery is the largest branded whitespace",

      "eyebrow": "CHANNEL STRATEGY",

      "blocks": \[

        {"type": "callout", "items": \[

            {"value": "46.74%", "label": "Value-added meats rev share", "cite": \[1\]}\]},

        {"type": "cards", "title": "Priority strategies", "items": \[

            {"title": "Win traditional grocery first", "body": "...", "cite": \[194, 184, 51\]}\]},

        {"type": "table", "title": "Regional presence",

         "headers": \["Region", "Presence", "Key markets & strategic role"\],

         "rows": \[\["Northwest", "Major", "Portland, Salem, Central Point — ..."\]\],

         "has\_tags": true, "zebra": false, "cite": \[12\]},

        {"type": "rail", "items": \[{"title": "Format hedge", "body": "..."}\]},

        {"type": "text", "body": "..."},

        {"type": "chart", "title": "Gross sales by channel",

         "labels": \["Club", "Retail", "Foodservice"\], "cite": \[194\]},

        {"type": "footnote", "body": "Management estimates, 2016E."}

      \]

    }

  \]

}

Every block type is optional. \`cite\` is always a list of ints and is always

excluded from the character budget — citations are metadata, not content.

"""

import argparse

import json

import os

import re

import sys

HERE \= os.path.dirname(os.path.abspath(\_\_file\_\_))

TOKENS\_PATH \= os.path.join(HERE, "..", "assets", "design-tokens.json")

\# Blocks whose text is metadata, not content, and is excluded from the budget.

METADATA\_BLOCKS \= {"footnote", "source", "citation", "pagenum"}

\# \--------------------------------------------------------------------------

\# tokens

\# \--------------------------------------------------------------------------

def load\_tokens(path=TOKENS\_PATH):

    with open(path, "r", encoding="utf-8") as fh:

        return json.load(fh)

\# \--------------------------------------------------------------------------

\# character budget

\# \--------------------------------------------------------------------------

\_CITE\_RE \= re.compile(r"\\\[\\s\*\\d+(?:\\s\*\[,\\u2013-\]\\s\*\\d+)\*\\s\*\\\]")

def visible\_chars(text):

    """Character count of one string, with inline \[n\] citations stripped."""

    if not text:

        return 0

    return len(\_CITE\_RE.sub("", str(text)).strip())

def \_block\_chars(block):

    """Visible characters contributed by a single content block."""

    btype \= block.get("type", "text")

    if btype in METADATA\_BLOCKS:

        return 0

    total \= visible\_chars(block.get("title", ""))

    total \+= visible\_chars(block.get("subtitle", ""))

    total \+= visible\_chars(block.get("body", ""))

    for item in block.get("items", \[\]):

        if isinstance(item, str):

            total \+= visible\_chars(item)

            continue

        for key in ("title", "label", "value", "body", "sublabel"):

            total \+= visible\_chars(item.get(key, ""))

    for bullet in block.get("bullets", \[\]):

        total \+= visible\_chars(bullet)

    if btype \== "table":

        for header in block.get("headers", \[\]):

            total \+= visible\_chars(header)

        for row in block.get("rows", \[\]):

            for cell in row:

                total \+= visible\_chars(cell)

    if btype \== "chart":

        for label in block.get("labels", \[\]):

            total \+= visible\_chars(label)

        for label in block.get("series\_names", \[\]):

            total \+= visible\_chars(label)

    return total

def slide\_chars(slide):

    """Total visible character load for a slide, per the DOC engineering formula."""

    total \= visible\_chars(slide.get("title", ""))

    total \+= visible\_chars(slide.get("subtitle", ""))

    total \+= visible\_chars(slide.get("eyebrow", ""))

    for block in slide.get("blocks", \[\]):

        total \+= \_block\_chars(block)

    return total

\# \--------------------------------------------------------------------------

\# density band \-\> typography scale

\# \--------------------------------------------------------------------------

def classify(chars, tokens):

    """Map a character load onto a density band and its prescribed action."""

    for band in tokens\["density"\]\["bands"\]:

        if band\["max"\] is None or chars \<= band\["max"\]:

            return band\["name"\], band\["action"\]

    return "overflow", "Recompose."

def resolve\_scale(band, tokens):

    """

    Density band \-\> concrete point size per role.

    'sparse' and 'balanced' and 'dense' are real scales. 'overflow' is not a

    scale: it is a recomposition order. It clamps to dense so the caller still

    gets usable numbers, but the verdict must stay FAIL.

    """

    key \= band if band in tokens\["type"\]\["scales"\] else "dense"

    return dict(tokens\["type"\]\["scales"\]\[key\])

def validate\_scale(scale, tokens):

    """Assert every resolved size sits inside its DOC-defined range."""

    problems \= \[\]

    ranges \= tokens\["type"\]\["role\_ranges\_doc"\]

    for role, size in scale.items():

        spec \= ranges.get(role)

        if not spec:

            continue

        lo, hi \= spec\[0\], spec\[1\]

        if not (lo \<= size \<= hi):

            problems.append(f"{role} resolved to {size}pt, outside DOC range {lo}-{hi}pt")

    return problems

\# \--------------------------------------------------------------------------

\# component verdicts

\# \--------------------------------------------------------------------------

def \_count\_verdict(kind, n, tokens):

    """Apply the DOC count thresholds for cards / rail / callout."""

    if kind \== "cards":

        if n \<= 3:

            return "OK", "Larger cards, stronger typography, more internal whitespace."

        if n \<= 6:

            return "OK", "Reduce card width and spacing; keep content readable."

        return "FAIL", (f"{n} cards. Do not shrink further — switch to a rail or a "

                        f"grouped structure.")

    if kind \== "rail":

        if n \< 2:

            return "WARN", "A rail of one item is a callout. Use a callout."

        if n \<= 4:

            return "OK", "Larger item widths, generous spacing."

        if n \<= 6:

            return "OK", "Compact spacing, smaller item widths."

        return "FAIL", f"{n} rail items. Split the rail or change the component."

    if kind \== "callout":

        if n \== 1:

            return "OK", "Strong emphasis, generous whitespace."

        if n \== 2:

            return "OK", "Balance by content length; equal heights not required."

        if n \<= 4:

            return "WARN", (f"{n} callouts. Justify that each is a distinct insight, "

                            f"otherwise combine.")

        return "FAIL", f"{n} callouts. Combine — this is a list, not a set of insights."

    return "OK", ""

def \_table\_verdict(block, tokens):

    """DOC table rules that are checkable from the spec alone."""

    findings \= \[\]

    rows \= block.get("rows", \[\])

    headers \= block.get("headers", \[\])

    if not headers:

        findings.append(("WARN", "Table has no header row; column hierarchy is unclear."))

    \# Wrap pressure. \~62 chars per descriptive column line at 8-9pt in a

    \# typical 3-4 column consulting table. Two lines is the DOC ceiling.

    long\_cells \= 0

    for row in rows:

        for cell in row:

            if visible\_chars(cell) \> 124:

                long\_cells \+= 1

    if long\_cells:

        findings.append((

            "FAIL",

            f"{long\_cells} cell(s) will exceed 2 wrapped lines. DOC: restructure the "

            f"table — do not reduce the font."))

    \# Zebra vs tags — the DOC's sharpest table rule.

    if block.get("zebra") and block.get("has\_tags"):

        findings.append((

            "FAIL",

            "Zebra striping is on and the rows carry tags/pills/labels. DOC bans this "

            "combination. Keep the background uniform and let the tags differentiate."))

    if block.get("zebra") and block.get("highlight\_rows"):

        findings.append((

            "FAIL",

            "Zebra striping combined with highlighted rows creates visual noise. Pick one."))

    if not block.get("zebra") and not block.get("has\_tags") and len(rows) \>= 8:

        findings.append((

            "INFO",

            f"{len(rows)} data-only rows and no tags — subtle zebra striping is "

            f"permitted here and will aid row scanning."))

    if len(rows) \> 12:

        findings.append((

            "WARN",

            f"{len(rows)} rows. Consider splitting at a logical grouping boundary."))

    if headers and rows:

        widths \= {len(r) for r in rows}

        if widths \!= {len(headers)}:

            findings.append((

                "FAIL",

                f"Ragged table: header has {len(headers)} columns, rows have {sorted(widths)}."))

    return findings

def component\_report(slide, tokens):

    """Per-block verdicts for one slide."""

    out \= \[\]

    for block in slide.get("blocks", \[\]):

        btype \= block.get("type", "text")

        n \= len(block.get("items", \[\]))

        if btype in ("cards", "rail", "callout"):

            status, msg \= \_count\_verdict(btype, n, tokens)

            out.append({"block": btype, "count": n, "status": status, "message": msg})

        elif btype \== "table":

            for status, msg in \_table\_verdict(block, tokens):

                out.append({"block": "table", "count": len(block.get("rows", \[\])),

                            "status": status, "message": msg})

        elif btype \== "text":

            chars \= \_block\_chars(block)

            if chars \> 480:

                out.append({"block": "text", "count": chars, "status": "WARN",

                            "message": (f"{chars} characters of running prose. Convert to "

                                        f"cards, a rail, or bullets — this is a deck, not a memo.")})

    return out

\# \--------------------------------------------------------------------------

\# citation integrity

\# \--------------------------------------------------------------------------

\_URLISH \= re.compile(r"(https?://|www\\.)", re.I)

def citation\_report(slide):

    """

    DOC: numbered citations only, no URLs or source names inside components,

    grouped references past 3 sources, appendix past 6-8 per slide.

    """

    findings \= \[\]

    slide\_sources \= set()

    def scan(text, where):

        if not text:

            return

        text \= str(text)

        if \_URLISH.search(text):

            findings.append({"status": "FAIL",

                             "message": f"Raw URL inside {where}. Use a numbered citation and "

                                        f"put the full source in the appendix."})

        for match in \_CITE\_RE.finditer(text):

            for num in re.findall(r"\\d+", match.group()):

                slide\_sources.add(int(num))

    scan(slide.get("title"), "slide title")

    for block in slide.get("blocks", \[\]):

        where \= block.get("type", "block")

        scan(block.get("title"), where \+ " title")

        scan(block.get("body"), where \+ " body")

        for item in block.get("items", \[\]):

            if isinstance(item, dict):

                for key in ("title", "body", "value", "label"):

                    scan(item.get(key), where \+ " item")

                for num in item.get("cite", \[\]):

                    slide\_sources.add(int(num))

            else:

                scan(item, where \+ " item")

        for row in block.get("rows", \[\]):

            for cell in row:

                scan(cell, "table cell")

        for num in block.get("cite", \[\]):

            slide\_sources.add(int(num))

        if len(block.get("cite", \[\])) \> 3:

            findings.append({

                "status": "INFO",

                "message": f"{where} cites {len(block\['cite'\])} sources — emit a grouped "

                           f"reference such as \[55-60\], not a list of names."})

    if len(slide\_sources) \> 8:

        findings.append({

            "status": "WARN",

            "message": f"{len(slide\_sources)} distinct sources on this slide. Keep \[n\] markers "

                       f"on the slide and move the full list to the References appendix."})

    return findings, sorted(slide\_sources)

def format\_citation(nums):

    """

    \[3\] · \[3, 7\] · \[3-7\]. Collapses runs of 3 or more consecutive numbers.

    """

    nums \= sorted({int(n) for n in nums})

    if not nums:

        return ""

    parts, start, prev \= \[\], nums\[0\], nums\[0\]

    for num in nums\[1:\] \+ \[None\]:

        if num is not None and num \== prev \+ 1:

            prev \= num

            continue

        if prev \- start \>= 2:

            parts.append(f"{start}-{prev}")

        elif prev \!= start:

            parts.extend(\[str(start), str(prev)\])

        else:

            parts.append(str(start))

        if num is not None:

            start \= prev \= num

    return "\[" \+ ", ".join(parts) \+ "\]"

\# \--------------------------------------------------------------------------

\# pagination / merge

\# \--------------------------------------------------------------------------

def pagination\_plan(slides, tokens):

    """

    DOC decision rule: Fit \+ Related \+ Readable \-\> merge.

    Otherwise \-\> new slide. Never merge unrelated content to fill space.

    """

    target\_max \= tokens\["density"\]\["target\_max"\]

    sparse\_ceiling \= tokens\["density"\]\["bands"\]\[0\]\["max"\]

    plan \= \[\]

    for i, slide in enumerate(slides):

        chars \= slide\_chars(slide)

        nxt \= slides\[i \+ 1\] if i \+ 1 \< len(slides) else None

        action \= {"id": slide.get("id", f"slide{i+1}"), "action": "keep", "reason": ""}

        if chars \> tokens\["density"\]\["hard\_max"\]:

            action\["action"\] \= "split"

            action\["reason"\] \= (

                f"{chars} chars exceeds the {tokens\['density'\]\['hard\_max'\]} hard maximum. "

                f"Split at a logical sub-topic boundary — move a meaningful sub-topic, not "

                f"leftover content. The continuation slide must feel complete on its own.")

        elif nxt is not None and chars \<= sparse\_ceiling:

            related \= slide.get("section") and slide.get("section") \== nxt.get("section")

            combined \= chars \+ slide\_chars(nxt)

            if related and combined \<= target\_max:

                action\["action"\] \= "merge\_next"

                action\["reason"\] \= (

                    f"{chars} chars, same section as '{nxt.get('id')}', combined {combined} "

                    f"chars is within the {target\_max} target. Fit \+ Related \+ Readable \-\> merge.")

            elif not related:

                action\["reason"\] \= (

                    f"{chars} chars is sparse, but the next slide is a different section. "

                    f"DOC: never merge unrelated content only to fill empty space. "

                    f"Scale typography up and increase whitespace instead.")

            else:

                action\["reason"\] \= (

                    f"Sparse ({chars} chars) but merging would reach {combined} chars, past "

                    f"the {target\_max} target. Keep separate and scale up.")

        plan.append(action)

    return plan

\# \--------------------------------------------------------------------------

\# top level

\# \--------------------------------------------------------------------------

def analyse(spec, tokens):

    slides \= spec.get("slides", \[\])

    merge \= pagination\_plan(slides, tokens)

    results \= \[\]

    for i, slide in enumerate(slides):

        chars \= slide\_chars(slide)

        band, action \= classify(chars, tokens)

        scale \= resolve\_scale(band, tokens)

        cites, sources \= citation\_report(slide)

        components \= component\_report(slide, tokens)

        statuses \= \[c\["status"\] for c in components\] \+ \[c\["status"\] for c in cites\]

        verdict \= "FAIL" if ("FAIL" in statuses or band \== "overflow") else \\

                  ("WARN" if "WARN" in statuses else "PASS")

        results.append({

            "id": slide.get("id", f"slide{i+1}"),

            "section": slide.get("section"),

            "title": slide.get("title", ""),

            "chars": chars,

            "band": band,

            "band\_action": action,

            "scale": scale,

            "scale\_problems": validate\_scale(scale, tokens),

            "components": components,

            "citations": cites,

            "sources": sources,

            "source\_marker": format\_citation(sources),

            "pagination": merge\[i\],

            "verdict": verdict,

        })

    all\_sources \= sorted({s for r in results for s in r\["sources"\]})

    return {

        "deck": spec.get("deck", "Untitled"),

        "palette": spec.get("palette", tokens\["palettes"\]\["default"\]),

        "canvas": tokens\["canvas"\],

        "grid": tokens\["grid"\],

        "fonts": tokens\["type"\]\["fonts"\],

        "slides": results,

        "source\_index": all\_sources,

        "deck\_verdict": "FAIL" if any(r\["verdict"\] \== "FAIL" for r in results) else

                        ("WARN" if any(r\["verdict"\] \== "WARN" for r in results) else "PASS"),

    }

ICON \= {"OK": "OK", "PASS": "PASS", "WARN": "WARN", "FAIL": "FAIL", "INFO": "INFO"}

def render(report):

    lines \= \[\]

    add \= lines.append

    add("=" \* 78\)

    add(f"  {report\['deck'\]}")

    add(f"  palette {report\['palette'\]}   "

        f"canvas {report\['canvas'\]\['width\_in'\]}x{report\['canvas'\]\['height\_in'\]}in   "

        f"{report\['fonts'\]\['header'\]}/{report\['fonts'\]\['body'\]}")

    add("=" \* 78\)

    for s in report\["slides"\]:

        add("")

        add(f"\[{s\['verdict'\]}\] {s\['id'\]}  ({s\['section'\] or 'no section'})")

        add(f"  {s\['title'\]\[:72\]}")

        add(f"  {s\['chars'\]} chars \-\> {s\['band'\].upper()} scale")

        add(f"  {s\['band\_action'\]}")

        add(f"  type: title {s\['scale'\]\['title'\]}pt / header {s\['scale'\]\['header'\]}pt / "

            f"body {s\['scale'\]\['body'\]}pt / table {s\['scale'\]\['table\_body'\]}pt / "

            f"footnote {s\['scale'\]\['footnote'\]}pt")

        for problem in s\["scale\_problems"\]:

            add(f"  \!\! {problem}")

        for c in s\["components"\]:

            add(f"  \[{ICON\[c\['status'\]\]}\] {c\['block'\]} x{c\['count'\]}: {c\['message'\]}")

        for c in s\["citations"\]:

            add(f"  \[{ICON\[c\['status'\]\]}\] citation: {c\['message'\]}")

        if s\["sources"\]:

            add(f"  sources on slide: {s\['source\_marker'\]}")

        if s\["pagination"\]\["action"\] \!= "keep":

            add(f"  \>\> {s\['pagination'\]\['action'\].upper()}: {s\['pagination'\]\['reason'\]}")

        elif s\["pagination"\]\["reason"\]:

            add(f"  \-- {s\['pagination'\]\['reason'\]}")

    add("")

    add("-" \* 78\)

    add(f"deck verdict: {report\['deck\_verdict'\]}")

    add(f"global source index: {len(report\['source\_index'\])} sources "

        f"-\> one References slide, one number per source, deck-wide.")

    return "\\n".join(lines)

\# \--------------------------------------------------------------------------

\# selftest

\# \--------------------------------------------------------------------------

def selftest():

    tokens \= load\_tokens()

    failures \= \[\]

    def check(name, got, want):

        if got \!= want:

            failures.append(f"{name}: got {got\!r}, want {want\!r}")

    check("cite strip", visible\_chars("Grow foodservice \[199, 200, 201\]."), len("Grow foodservice ."))

    check("cite range", format\_citation(\[3, 4, 5, 6, 7\]), "\[3-7\]")

    check("cite pair", format\_citation(\[3, 7\]), "\[3, 7\]")

    check("cite single", format\_citation(\[3\]), "\[3\]")

    check("cite mixed", format\_citation(\[1, 2, 3, 9\]), "\[1-3, 9\]")

    check("band sparse", classify(400, tokens)\[0\], "sparse")

    check("band balanced", classify(800, tokens)\[0\], "balanced")

    check("band dense", classify(1100, tokens)\[0\], "dense")

    check("band overflow", classify(1500, tokens)\[0\], "overflow")

    for band in ("sparse", "balanced", "dense"):

        problems \= validate\_scale(resolve\_scale(band, tokens), tokens)

        if problems:

            failures.append(f"scale {band} outside DOC ranges: {problems}")

        scale \= resolve\_scale(band, tokens)

        if not (scale\["title"\] \> scale\["header"\] \> scale\["body"\] \>= scale\["table\_body"\]

                \>= scale\["footnote"\]):

            failures.append(f"scale {band} breaks hierarchy: {scale}")

    zebra\_fail \= \_table\_verdict({"rows": \[\["a", "b"\]\], "headers": \["a", "b"\],

                                 "zebra": True, "has\_tags": True}, tokens)

    if not any(s \== "FAIL" for s, \_ in zebra\_fail):

        failures.append("zebra+tags must FAIL")

    if failures:

        print("SELFTEST FAILED")

        for f in failures:

            print("  \-", f)

        return 1

    print(f"SELFTEST PASSED  ({8 \+ 3 \* 2 \+ 1} assertions)")

    return 0

def main():

    ap \= argparse.ArgumentParser(description="pe-deck-design layout engine")

    ap.add\_argument("spec", nargs="?", help="path to the content spec JSON")

    ap.add\_argument("--json", action="store\_true", help="emit the machine plan")

    ap.add\_argument("-o", "--out", help="write output to a file")

    ap.add\_argument("--tokens", default=TOKENS\_PATH)

    ap.add\_argument("--selftest", action="store\_true")

    args \= ap.parse\_args()

    if args.selftest:

        return selftest()

    if not args.spec:

        ap.error("spec is required unless \--selftest")

    tokens \= load\_tokens(args.tokens)

    with open(args.spec, "r", encoding="utf-8") as fh:

        spec \= json.load(fh)

    report \= analyse(spec, tokens)

    text \= json.dumps(report, indent=2) if args.json else render(report)

    if args.out:

        with open(args.out, "w", encoding="utf-8") as fh:

            fh.write(text)

        print(f"wrote {args.out}  (deck verdict: {report\['deck\_verdict'\]})")

    else:

        print(text)

    return 1 if report\["deck\_verdict"\] \== "FAIL" else 0

if \_\_name\_\_ \== "\_\_main\_\_":

    sys.exit(main())

## FILE: `scripts/pe_components.js`

/\*\*

 \* pe\_components.js — the rendering half of the pe-deck-design skill.

 \*

 \* A pptxgenjs layer that makes the specification's component rules structural

 \* rather than a thing you remember to do.

 \*

 \* ARCHITECTURE — two-phase layout

 \* \-------------------------------

 \* Naive builders place each component the moment it is declared, at its natural

 \* height, top-anchored. That produces the single most recognisable defect in

 \* generated decks: a correct-looking top third and a dead bottom half.

 \*

 \* So rendering happens in two passes:

 \*

 \*   1\. MEASURE   — every block reports { natural, min, growable } without drawing.

 \*   2\. DISTRIBUTE — leftover vertical space goes back to the growable blocks

 \*      (capped), then to the gaps (capped); only then does anything draw.

 \*

 \* This makes the specification mechanical: "Content volume determines component

 \* size, spacing and structure. Never preserve fixed dimensions at the cost of

 \* whitespace or readability." Underfill and overflow both become numbers the

 \* build reports, rather than defects a human has to spot.

 \*

 \* Component law, not configurable:

 \*   card     1pt neutral border, no fill

 \*   rail     1pt border, gradient of that border colour

 \*   callout  no border, gradient of the primary colour

 \*   citation same family, one step down, muted, never bold or boxed

 \*

 \* Gradient note: pptxgenjs cannot emit an OOXML gradient fill. Gradients ship as

 \* alpha PNGs rendered at build time through sharp — the only route that survives

 \* a round trip into PowerPoint.

 \*

 \* Usage:

 \*     const { Deck } \= require('./pe\_components');

 \*     const deck \= new Deck({ palette: 'graphite\_navy' });

 \*     const s \= deck.slide({ band: 'balanced', eyebrow: 'STRATEGY', title: '...' });

 \*     await s.compose(\[

 \*       { type: 'callouts', items: \[...\] },

 \*       { type: 'cards',    items: \[...\] },

 \*     \]);

 \*     s.source().pageNumber(2);

 \*     await deck.save('out.pptx');

 \*/

'use strict';

const fs \= require('fs');

const path \= require('path');

const PptxGenJS \= require('pptxgenjs');

const sharp \= require('sharp');

const TOKENS \= JSON.parse(

  fs.readFileSync(path.join(\_\_dirname, '..', 'assets', 'design-tokens.json'), 'utf8')

);

const GAP\_MIN \= 0.12;

const GAP\_NATURAL \= 0.20;

const GAP\_MAX \= 0.46;

// How far each component may stretch beyond its natural height. A card is a

// content container, so stretching it just moves dead space inside the border;

// a table genuinely reads better with taller rows. These caps encode that.

const GROW\_CAP \= { cards: 0.30, rail: 0.30, callouts: 0.55, table: 0.35, default: 0.50 };

const HEADER\_SEAM \= 0.10; // fixed gap between a header and the block it introduces

/\* \------------------------------------------------------------------ \*/

/\* colour                                                              \*/

/\* \------------------------------------------------------------------ \*/

/\*\* Mix a hex colour toward white. pct 100 \= the colour, pct 0 \= white. \*/

function tint(hex, pct) {

  const c \= hex.replace('\#', '');

  const f \= Math.max(0, Math.min(100, pct)) / 100;

  const mix \= (i) \=\> {

    const v \= parseInt(c.substr(i, 2), 16);

    return Math.round(255 \+ (v \- 255\) \* f).toString(16).padStart(2, '0');

  };

  return (mix(0) \+ mix(2) \+ mix(4)).toUpperCase();

}

/\* \------------------------------------------------------------------ \*/

/\* text metrics                                                        \*/

/\* \------------------------------------------------------------------ \*/

/\*\*

 \* Estimated wrapped line count.

 \*

 \* Deliberately pessimistic for headers: Manrope has no metric-compatible

 \* substitute in the QA renderer and sets wider than Arial at the same point

 \* size. Under-estimating header lines is exactly what makes a card title

 \* collide with its own body, so the header advance is set wide on purpose.

 \*/

function estimateLines(text, widthIn, fontPt, { header \= false } \= {}) {

  if (\!text) return 0;

  const em \= fontPt / 72;

  const advance \= em \* (header ? 0.60 : 0.50);

  const perLine \= Math.max(6, Math.floor(widthIn / advance));

  return String(text)

    .split('\\n')

    .reduce((n, para) \=\> n \+ Math.max(1, Math.ceil(para.length / perLine)), 0);

}

function textHeightIn(text, widthIn, fontPt, lineMult, opts) {

  return (estimateLines(text, widthIn, fontPt, opts) \* fontPt \* lineMult) / 72;

}

/\*\* \[3\] · \[3, 7\] · \[3-7\] — mirrors layout\_engine.format\_citation exactly. \*/

function formatCitation(nums) {

  const s \= \[...new Set((nums || \[\]).map(Number))\].sort((a, b) \=\> a \- b);

  if (\!s.length) return '';

  const parts \= \[\];

  let start \= s\[0\], prev \= s\[0\];

  for (const n of s.slice(1).concat(\[null\])) {

    if (n \!== null && n \=== prev \+ 1\) { prev \= n; continue; }

    if (prev \- start \>= 2\) parts.push(\`${start}-${prev}\`);

    else if (prev \!== start) parts.push(String(start), String(prev));

    else parts.push(String(start));

    if (n \!== null) { start \= n; prev \= n; }

  }

  return \`\[${parts.join(', ')}\]\`;

}

const CITE\_RE \= /\\\[\\s\*\\d+(?:\\s\*\[,\\u2013-\]\\s\*\\d+)\*\\s\*\\\]/g;

/\*\* Visible characters, with inline \[n\] citations stripped — citations are metadata. \*/

function visibleChars(text) {

  return text ? String(text).replace(CITE\_RE, '').trim().length : 0;

}

/\*\* Character load of one compose() block, matching layout\_engine.py exactly. \*/

function blockChars(b) {

  let n \= visibleChars(b.title) \+ visibleChars(b.text) \+ visibleChars(b.body);

  for (const it of b.items || \[\]) {

    if (typeof it \=== 'string') { n \+= visibleChars(it); continue; }

    for (const k of \['title', 'label', 'value', 'body', 'text'\]) n \+= visibleChars(it\[k\]);

  }

  for (const h of b.headers || \[\]) n \+= visibleChars(h);

  for (const r of b.rows || \[\]) for (const c of r) n \+= visibleChars(c);

  return n;

}

/\* \------------------------------------------------------------------ \*/

/\* gradient fills, as alpha PNGs                                       \*/

/\* \------------------------------------------------------------------ \*/

const gradientCache \= new Map();

async function gradientPng(fromHex, toHex, wIn, hIn, radiusIn) {

  const key \= \`${fromHex}-${toHex}-${wIn.toFixed(2)}-${hIn.toFixed(2)}-${radiusIn}\`;

  if (gradientCache.has(key)) return gradientCache.get(key);

  const dpi \= 384;                        // 4x, so PowerPoint scaling stays crisp

  const w \= Math.max(8, Math.round(wIn \* dpi));

  const h \= Math.max(8, Math.round(hIn \* dpi));

  const r \= Math.round(radiusIn \* dpi);

  const svg \= \`\<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"\>

    \<defs\>\<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"\>

      \<stop offset="0%" stop-color="\#${fromHex}"/\>

      \<stop offset="100%" stop-color="\#${toHex}"/\>

    \</linearGradient\>\</defs\>

    \<rect x="0" y="0" width="${w}" height="${h}" rx="${r}" ry="${r}" fill="url(\#g)"/\>

  \</svg\>\`;

  const buf \= await sharp(Buffer.from(svg)).png().toBuffer();

  const data \= 'image/png;base64,' \+ buf.toString('base64');

  gradientCache.set(key, data);

  return data;

}

/\* \------------------------------------------------------------------ \*/

/\* Slide                                                               \*/

/\* \------------------------------------------------------------------ \*/

class Slide {

  constructor(deck, pptxSlide, { band \= 'balanced', title, eyebrow, cite \= \[\] } \= {}) {

    this.deck \= deck;

    this.s \= pptxSlide;

    this.band \= band;

    this.scale \= TOKENS.type.scales\[band\] || TOKENS.type.scales.balanced;

    this.p \= deck.palette;

    this.g \= TOKENS.grid;

    this.t \= TOKENS.type;

    this.y \= this.g.content\_top\_in;

    this.sources \= new Set(cite);

    this.chars \= 0;        // visible characters, citations excluded

    this.overrun \= 0;      // inches of content past the content area

    this.underfill \= 0;    // fraction of the content area left empty

    this.chars \+= visibleChars(title) \+ visibleChars(eyebrow);

    if (eyebrow) this.\_eyebrow(eyebrow);

    if (title) this.\_title(title, cite);

    this.contentTop \= this.y;

  }

  get width() { return this.g.content\_width\_in; }

  get left() { return this.g.margin\_left\_in; }

  \_note(nums) { (nums || \[\]).forEach((n) \=\> this.sources.add(Number(n))); }

  /\*\*

   \* Body text plus a muted citation run. Citations stay visually subordinate:

   \* same family, one step down, muted colour, never bold, never boxed.

   \*/

  \_runs(text, cite, fontPt) {

    if (\!cite || \!cite.length) return String(text);

    this.\_note(cite);

    return \[

      { text: String(text) \+ ' ', options: {} },

      {

        text: formatCitation(cite),

        options: {

          fontSize: Math.max(TOKENS.type.footnote\_floor\_pt, fontPt \- 1),

          color: this.p.muted,

          bold: false,

        },

      },

    \];

  }

  \_citeTail(cite) {

    return cite && cite.length ? ' ' \+ formatCitation(cite) : '';

  }

  /\* \-- fixed bands \--------------------------------------------------- \*/

  \_eyebrow(text) {

    const clean \= String(text).slice(0, TOKENS.type.case.allcaps\_max\_chars).toUpperCase();

    this.s.addText(clean, {

      x: this.left, y: 0.34, w: this.width, h: 0.18,

      isTextBox: true, margin: 0,

      fontFace: this.deck.fonts.header, fontSize: this.scale.footnote,

      bold: true, charSpacing: 1.2, color: this.p.muted, align: 'left', fit: 'none',

    });

    this.y \= Math.max(this.y, 0.60);

  }

  \_title(text, cite) {

    const size \= this.scale.title;

    const h \= textHeightIn(text, this.width, size, 1.08, { header: true }) \+ 0.08;

    this.s.addText(this.\_runs(text, cite, size), {

      x: this.left, y: this.y, w: this.width, h,

      isTextBox: true, margin: 0,

      fontFace: this.deck.fonts.header, fontSize: size, bold: true,

      color: this.p.ink, align: 'left', valign: 'top',

      lineSpacingMultiple: 1.08, fit: 'none',

    });

    // No accent rule under the title — whitespace carries the separation.

    this.y \+= h \+ 0.24;

  }

  /\* \================================================================== \*/

  /\* compose: measure \-\> distribute \-\> render                            \*/

  /\* \================================================================== \*/

  async compose(blocks) {

    const measured \= \[\];

    for (const b of blocks) {

      const m \= await this.\_measure(b);

      m.kind \= b.type;

      this.chars \+= blockChars(b);

      measured.push(m);

    }

    const available \= this.g.content\_bottom\_in \- this.y;

    const n \= measured.length;

    const attachedSeams \= measured.filter((m, i) \=\> m.attachNext && i \< n \- 1).length;

    const gaps \= Math.max(0, n \- 1 \- attachedSeams);

    const seamTotal \= attachedSeams \* HEADER\_SEAM;

    const natural \= measured.reduce((a, m) \=\> a \+ m.natural, 0);

    const minimal \= measured.reduce((a, m) \=\> a \+ m.min, 0);

    let gap \= GAP\_NATURAL;

    let leftover \= available \- natural \- gap \* gaps \- seamTotal;

    if (leftover \< 0\) {

      // Recover from the gaps first — never from typography.

      gap \= Math.max(GAP\_MIN, gaps ? (available \- natural \- seamTotal) / gaps : GAP\_MIN);

      leftover \= available \- natural \- gap \* gaps \- seamTotal;

      if (leftover \< 0\) {

        this.overrun \= \-leftover;

        if (available \- minimal \- gap \* gaps \- seamTotal \< 0\) {

          throw new Error(

            \`compose(): needs ${(minimal \+ gap \* gaps).toFixed(2)}in but only \` \+

            \`${available.toFixed(2)}in is available even at minimum sizes. Split the \` \+

            \`slide at a logical boundary — the spec forbids shrinking type to fit.\`);

        }

      }

    }

    // Hand surplus back: growable blocks first, then the gaps.

    const heights \= measured.map((m) \=\> m.natural);

    if (leftover \> 0\) {

      const growIdx \= measured.map((m, i) \=\> (m.growable ? i : \-1)).filter((i) \=\> i \>= 0);

      const growNat \= growIdx.reduce((a, i) \=\> a \+ measured\[i\].natural, 0);

      if (growNat \> 0\) {

        const want \= leftover \* 0.72;          // most of it to the components

        let given \= 0;

        for (const i of growIdx) {

          const share \= (measured\[i\].natural / growNat) \* want;

          const cap \= GROW\_CAP\[measured\[i\].kind\] ?? GROW\_CAP.default;

          const capped \= Math.min(share, measured\[i\].natural \* cap);

          heights\[i\] \+= capped;

          given \+= capped;

        }

        leftover \-= given;

      }

      if (gaps \> 0 && leftover \> 0\) {

        const extra \= Math.max(0, Math.min(leftover / gaps, GAP\_MAX \- gap));

        gap \+= extra;

        leftover \-= extra \* gaps;

      }

    }

    let cursor \= this.y;

    for (let i \= 0; i \< n; i++) {

      await measured\[i\].render(cursor, heights\[i\]);

      // A header belongs to the block beneath it: keep that seam tight so the

      // distributed slack falls between groups, not between a label and its content.

      const seam \= measured\[i\].attachNext && i \< n \- 1 ? HEADER\_SEAM : gap;

      cursor \+= heights\[i\] \+ seam;

    }

    const attached \= measured.filter((m, i) \=\> m.attachNext && i \< n \- 1).length;

    const used \= cursor \- (n ? gap : 0\) \- this.contentTop;

    const total \= this.g.content\_bottom\_in \- this.contentTop;

    this.underfill \= Math.max(0, 1 \- used / total);

    this.y \= cursor;

    return this;

  }

  async \_measure(b) {

    switch (b.type) {

      case 'header':   return this.\_measureHeader(b);

      case 'body':     return this.\_measureBody(b);

      case 'bullets':  return this.\_measureBullets(b);

      case 'cards':    return this.\_measureCards(b);

      case 'rail':     return this.\_measureRail(b);

      case 'callouts': return this.\_measureCallouts(b);

      case 'table':    return this.\_measureTable(b);

      case 'spacer':   return { natural: b.h || 0.2, min: 0, growable: true,

                                render: async () \=\> {} };

      default:

        throw new Error(\`compose(): unknown block type ${JSON.stringify(b.type)}\`);

    }

  }

  /\* \-- text blocks \---------------------------------------------------- \*/

  \_measureHeader(b) {

    const size \= this.scale.header;

    const h \= textHeightIn(b.text, this.width, size, 1.05, { header: true }) \+ 0.04;

    return {

      natural: h, min: h, growable: false, attachNext: true,

      render: async (y) \=\> {

        this.s.addText(this.\_runs(b.text, b.cite, size), {

          x: this.left, y, w: this.width, h,

          isTextBox: true, margin: 0,

          fontFace: this.deck.fonts.header, fontSize: size, bold: false,

          color: this.p.primary, align: 'left', valign: 'top',

          lineSpacingMultiple: 1.05, fit: 'none',

        });

      },

    };

  }

  \_measureBody(b) {

    const size \= this.scale.body;

    const mult \= 1.18;

    const w \= b.width ? this.width \* b.width : this.width;

    const h \= textHeightIn(b.text \+ this.\_citeTail(b.cite), w, size, mult) \+ 0.06;

    return {

      natural: h, min: h, growable: false,

      render: async (y) \=\> {

        this.s.addText(this.\_runs(b.text, b.cite, size), {

          x: this.left, y, w, h,

          isTextBox: true, margin: 0,

          fontFace: this.deck.fonts.body, fontSize: size, color: this.p.body,

          align: 'left', valign: 'top', lineSpacingMultiple: mult,

          paraSpaceAfter: this.t.paragraph\_space\_after\_pt, fit: 'none',

        });

      },

    };

  }

  /\*\*

   \* Bullets.

   \*

   \* pptxgenjs gotcha, learned the hard way: a bulleted paragraph cannot hold two

   \* differently-styled runs. Any run carrying paragraph properties starts a new

   \* paragraph, and any run WITHOUT a bullet option emits its own \<a:pPr\> with

   \* \<a:buNone/\>, which silently kills the bullet on the whole paragraph. So

   \* "bulleted text \+ muted citation" is unreachable through addText bullets.

   \*

   \* The marker is therefore drawn as its own text box per item, with the claim

   \* in a second box at a fixed hanging indent. That also buys exact control over

   \* the indent, which the built-in bullet does not give.

   \*/

  \_measureBullets(b) {

    const size \= this.scale.body;

    const mult \= 1.18;

    const indent \= 0.20;

    const w \= this.width \- indent;

    const spaceAfter \= this.t.paragraph\_space\_after\_pt / 72;

    const items \= b.items.map((it) \=\> {

      const text \= typeof it \=== 'string' ? it : it.text;

      const cite \= typeof it \=== 'string' ? null : it.cite;

      return { text, cite, h: textHeightIn(text \+ this.\_citeTail(cite), w, size, mult) };

    });

    const natural \= items.reduce((a, it) \=\> a \+ it.h \+ spaceAfter, 0.04);

    return {

      natural, min: natural, growable: false,

      render: async (y) \=\> {

        let ty \= y;

        for (const it of items) {

          this.s.addText('\\u2022', {

            x: this.left, y: ty, w: indent \- 0.06, h: (size \* mult) / 72,

            isTextBox: true, margin: 0,

            fontFace: this.deck.fonts.body, fontSize: size, color: this.p.muted,

            align: 'left', valign: 'top', lineSpacingMultiple: mult, fit: 'none',

          });

          this.s.addText(this.\_runs(it.text, it.cite, size), {

            x: this.left \+ indent, y: ty, w, h: it.h,

            isTextBox: true, margin: 0,

            fontFace: this.deck.fonts.body, fontSize: size, color: this.p.body,

            align: 'left', valign: 'top', lineSpacingMultiple: mult, fit: 'none',

          });

          ty \+= it.h \+ spaceAfter;

        }

      },

    };

  }

  /\* \-- cards \----------------------------------------------------------- \*/

  \_measureCards(b) {

    const items \= b.items;

    const n \= items.length;

    if (n \> 6\) {

      throw new Error(

        \`cards: ${n} items. The spec forbids shrinking past 6 — switch to a rail or a \` \+

        \`grouped structure.\`);

    }

    const spec \= TOKENS.components.card;

    const cols \= b.columns || Math.min(n, n \<= 3 ? n : 3);

    const rows \= Math.ceil(n / cols);

    const gap \= spec.gap\_in;

    const cw \= (this.width \- gap \* (cols \- 1)) / cols;

    const innerW \= cw \- spec.pad\_x\_in \* 2;

    const titlePt \= this.scale.header;

    const bodyPt \= this.scale.body;

    const padY \= spec.pad\_y\_in \* (n \<= 3 ? 1.3 : 1.0);

    const cardH \= items.map((it) \=\>

      textHeightIn(it.title || '', innerW, titlePt, 1.08, { header: true }) \+

      (it.title && it.body ? 0.10 : 0\) \+

      textHeightIn((it.body || '') \+ this.\_citeTail(it.cite), innerW, bodyPt, 1.18) \+

      padY \* 2);

    // Cards within a row share a common height, per the spec.

    const rowNat \= \[\];

    for (let r \= 0; r \< rows; r++) {

      rowNat.push(Math.max(...cardH.slice(r \* cols, (r \+ 1\) \* cols)));

    }

    const natural \= rowNat.reduce((a, h) \=\> a \+ h, 0\) \+ gap \* (rows \- 1);

    return {

      natural, min: natural, growable: true,

      render: async (y, h) \=\> {

        const extra \= Math.max(0, h \- natural);

        let cursor \= y;

        for (let r \= 0; r \< rows; r++) {

          const slice \= items.slice(r \* cols, (r \+ 1\) \* cols);

          const rowH \= rowNat\[r\] \+ (extra \* rowNat\[r\]) / (natural || 1);

          const pad \= padY \+ Math.min(0.24, Math.max(0, (rowH \- rowNat\[r\]) / 2));

          slice.forEach((it, i) \=\> {

            const x \= this.left \+ i \* (cw \+ gap);

            this.s.addShape(this.deck.pptx.ShapeType.roundRect, {

              x, y: cursor, w: cw, h: rowH,

              fill: { type: 'none' },                    // spec: no background fill

              line: { color: this.p.neutral\_line, width: spec.border\_pt },

              rectRadius: spec.radius\_in,

            });

            let ty \= cursor \+ pad;

            if (it.title) {

              const th \= textHeightIn(it.title, innerW, titlePt, 1.08, { header: true });

              this.s.addText(it.title, {

                x: x \+ spec.pad\_x\_in, y: ty, w: innerW, h: th,

                isTextBox: true, margin: 0,

                fontFace: this.deck.fonts.header, fontSize: titlePt, bold: true,

                color: this.p.ink, lineSpacingMultiple: 1.08, valign: 'top', fit: 'none',

              });

              ty \+= th \+ 0.10;

            }

            if (it.body) {

              const bh \= textHeightIn((it.body || '') \+ this.\_citeTail(it.cite),

                                      innerW, bodyPt, 1.18);

              this.s.addText(this.\_runs(it.body, it.cite, bodyPt), {

                x: x \+ spec.pad\_x\_in, y: ty, w: innerW, h: bh,

                isTextBox: true, margin: 0,

                fontFace: this.deck.fonts.body, fontSize: bodyPt, color: this.p.body,

                lineSpacingMultiple: 1.18, valign: 'top', fit: 'none',

              });

            }

          });

          cursor \+= rowH \+ gap;

        }

      },

    };

  }

  /\* \-- rail \------------------------------------------------------------ \*/

  \_measureRail(b) {

    const items \= b.items;

    const n \= items.length;

    if (n \> 6\) {

      throw new Error(

        \`rail: ${n} items. The spec forbids shrinking past 6 — split the rail or change \` \+

        \`the component.\`);

    }

    const spec \= TOKENS.components.rail;

    const line \= b.accent || this.p.primary;

    const gap \= spec.gap\_in;

    // Item width follows content length, pulled toward the mean so nothing

    // collapses to a sliver and nothing hogs the rail.

    const loads \= items.map((it) \=\>

      Math.max(18, (it.title || '').length \+ (it.body || '').length));

    const mean \= loads.reduce((a, x) \=\> a \+ x, 0\) / n;

    const weights \= loads.map((l) \=\> 0.6 \+ 0.4 \* (l / mean));

    const wsum \= weights.reduce((a, x) \=\> a \+ x, 0);

    const avail \= this.width \- gap \* (n \- 1);

    const widths \= weights.map((w) \=\> (w / wsum) \* avail);

    const titlePt \= this.scale.body;

    const bodyPt \= this.scale.body;

    const heights \= items.map((it, i) \=\> {

      const inner \= widths\[i\] \- spec.pad\_x\_in \* 2;

      return textHeightIn(it.title || '', inner, titlePt, 1.08, { header: true }) \+

             (it.title && it.body ? 0.08 : 0\) \+

             textHeightIn((it.body || '') \+ this.\_citeTail(it.cite), inner, bodyPt, 1.18) \+

             spec.pad\_y\_in \* 2;

    });

    const natural \= Math.max(...heights);

    return {

      natural, min: natural, growable: true,

      render: async (y, h) \=\> {

        let x \= this.left;

        for (let i \= 0; i \< n; i++) {

          const w \= widths\[i\];

          const img \= await gradientPng(

            tint(line, TOKENS.components.gradient.tint\_start\_pct),

            tint(line, TOKENS.components.gradient.tint\_end\_pct),

            w, h, spec.radius\_in);

          this.s.addImage({ data: img, x, y, w, h });

          this.s.addShape(this.deck.pptx.ShapeType.roundRect, {

            x, y, w, h,

            fill: { type: 'none' },

            line: { color: line, width: spec.border\_pt },

            rectRadius: spec.radius\_in,

          });

          const inner \= w \- spec.pad\_x\_in \* 2;

          const it \= items\[i\];

          // Centre each item's own content: rail items share a height but not a

          // content length, so top-anchoring leaves short items looking clipped.

          const own \= heights\[i\] \- spec.pad\_y\_in \* 2;

          let ty \= y \+ Math.max(spec.pad\_y\_in, (h \- own) / 2);

          if (it.title) {

            const th \= textHeightIn(it.title, inner, titlePt, 1.08, { header: true });

            this.s.addText(it.title, {

              x: x \+ spec.pad\_x\_in, y: ty, w: inner, h: th,

              isTextBox: true, margin: 0,

              fontFace: this.deck.fonts.header, fontSize: titlePt, bold: true,

              color: this.p.ink, lineSpacingMultiple: 1.08, valign: 'top', fit: 'none',

            });

            ty \+= th \+ 0.08;

          }

          if (it.body) {

            const bh \= textHeightIn((it.body || '') \+ this.\_citeTail(it.cite),

                                    inner, bodyPt, 1.18);

            this.s.addText(this.\_runs(it.body, it.cite, bodyPt), {

              x: x \+ spec.pad\_x\_in, y: ty, w: inner, h: bh,

              isTextBox: true, margin: 0,

              fontFace: this.deck.fonts.body, fontSize: bodyPt, color: this.p.body,

              lineSpacingMultiple: 1.18, valign: 'top', fit: 'none',

            });

          }

          x \+= w \+ gap;

        }

      },

    };

  }

  /\* \-- callouts \--------------------------------------------------------- \*/

  \_measureCallouts(b) {

    const items \= b.items;

    const n \= items.length;

    if (n \> 4\) {

      throw new Error(

        \`callouts: ${n} items. Past three these stop being distinct insights — combine them.\`);

    }

    const spec \= TOKENS.components.callout;

    const base \= b.accent || this.p.primary;

    const gap \= spec.gap\_in;

    const w \= (this.width \- gap \* (n \- 1)) / n;

    const inner \= w \- spec.pad\_x\_in \* 2;

    const valuePt \= n \=== 1 ? Math.min(TOKENS.type.max\_pt, this.scale.title \+ 1\)

                            : this.scale.title;

    const labelPt \= this.scale.body;

    const padY \= spec.pad\_y\_in \* (n \=== 1 ? 1.5 : 1.0);

    const heights \= items.map((it) \=\>

      textHeightIn(it.value || '', inner, valuePt, 1.04, { header: true }) \+ 0.06 \+

      textHeightIn((it.label || '') \+ this.\_citeTail(it.cite), inner, labelPt, 1.15) \+

      padY \* 2);

    const natural \= Math.max(...heights);

    return {

      natural, min: natural, growable: true,

      render: async (y, h) \=\> {

        const img \= await gradientPng(

          tint(base, TOKENS.components.gradient.tint\_start\_pct),

          tint(base, TOKENS.components.gradient.tint\_end\_pct),

          w, h, spec.radius\_in);

        for (let i \= 0; i \< n; i++) {

          const x \= this.left \+ i \* (w \+ gap);

          const it \= items\[i\];

          this.s.addImage({ data: img, x, y, w, h });     // no border, per spec

          const vh \= textHeightIn(it.value || '', inner, valuePt, 1.04, { header: true });

          const lh \= textHeightIn((it.label || '') \+ this.\_citeTail(it.cite),

                                  inner, labelPt, 1.15);

          // Centre the block vertically: a grown callout should read as generous

          // whitespace around the metric, not as a metric stuck to the ceiling.

          const top \= y \+ Math.max(padY, (h \- (vh \+ 0.06 \+ lh)) / 2);

          // The value stays a clean bold run; its citation rides on the label,

          // so the metric never carries bold bracket noise.

          this.s.addText(it.value || '', {

            x: x \+ spec.pad\_x\_in, y: top, w: inner, h: vh,

            isTextBox: true, margin: 0,

            fontFace: this.deck.fonts.header, fontSize: valuePt, bold: true,

            color: this.p.primary, lineSpacingMultiple: 1.04, valign: 'top', fit: 'none',

          });

          this.s.addText(this.\_runs(it.label || '', it.cite, labelPt), {

            x: x \+ spec.pad\_x\_in, y: top \+ vh \+ 0.06, w: inner, h: lh,

            isTextBox: true, margin: 0,

            fontFace: this.deck.fonts.body, fontSize: labelPt, color: this.p.body,

            lineSpacingMultiple: 1.15, valign: 'top', fit: 'none',

          });

        }

      },

    };

  }

  /\* \-- table \------------------------------------------------------------ \*/

  \_measureTable(b) {

    const { title, headers, rows, zebra \= false, hasTags \= false,

            highlightRows \= \[\], cite \= \[\] } \= b;

    if (zebra && hasTags) {

      throw new Error(

        'table: zebra striping with tags/pills is forbidden. Keep the background uniform ' \+

        'and let the tags carry the differentiation.');

    }

    if (zebra && highlightRows.length) {

      throw new Error('table: zebra striping plus highlighted rows is visual noise. Pick one.');

    }

    if (headers && rows.some((r) \=\> r.length \!== headers.length)) {

      throw new Error('table: ragged rows — every row must match the header column count.');

    }

    const t \= TOKENS.table;

    const headPt \= this.scale.table\_header;

    const bodyPt \= this.scale.table\_body;

    const widths \= b.colW || this.\_autoColumnWidths(headers, rows);

    const titleH \= title

      ? textHeightIn(title, this.width, this.scale.table\_title, 1.06, { header: true }) \+ 0.10

      : 0;

    const padPt \= t.cell\_pad\_y\_pt\[0\];

    const cellH \= (pt, lines) \=\> (lines \* pt \* 1.2 \+ padPt \* 2\) / 72;

    const headH \= cellH(headPt, 1);

    const rowH \= rows.map((r) \=\> {

      const lines \= Math.max(...r.map((cell, c) \=\>

        estimateLines(String(cell ?? ''), widths\[c\] \- 0.18, bodyPt)));

      return cellH(bodyPt, Math.max(1, lines));

    });

    const natural \= titleH \+ headH \+ rowH.reduce((a, h) \=\> a \+ h, 0);

    return {

      natural, min: natural, growable: true,

      render: async (y, h) \=\> {

        let ty \= y;

        if (title) {

          this.s.addText(title, {

            x: this.left, y: ty, w: this.width, h: titleH,

            isTextBox: true, margin: 0,

            fontFace: this.deck.fonts.header, fontSize: this.scale.table\_title,

            bold: true, color: this.p.ink, lineSpacingMultiple: 1.06,

            valign: 'top', fit: 'none',

          });

          ty \+= titleH;

        }

        const isNum \= headers.map((\_, c) \=\>

          rows.every((r) \=\> /^\[\\s$€£\]\*-?\[\\d,.\]+\\s\*\[%x×bnmk\]\*$/i.test(String(r\[c\] ?? '').trim())));

        const none \= { type: 'none' };

        const divider \= { pt: 0.75, color: this.p.neutral\_line };

        const pad \= \[padPt, t.cell\_pad\_x\_pt\[0\], padPt, t.cell\_pad\_x\_pt\[0\]\];

        const headerRow \= headers.map((hd, c) \=\> ({

          text: String(hd),

          options: {

            bold: true, fontSize: headPt, fontFace: this.deck.fonts.header,

            color: this.p.ink, fill: { color: this.p.neutral\_fill },

            align: isNum\[c\] ? 'right' : 'left', valign: 'bottom', margin: pad,

            border: \[none, none, { pt: 1, color: this.p.primary }, none\],

          },

        }));

        const bodyRows \= rows.map((r, ri) \=\> {

          const stripe \= zebra && ri % 2 \=== 1;

          const highlight \= highlightRows.includes(ri);

          return r.map((cell, c) \=\> ({

            text: String(cell ?? ''),

            options: {

              fontSize: bodyPt, fontFace: this.deck.fonts.body,

              // The primary column carries the hierarchy: the only bold body cell.

              bold: c \=== 0 || highlight,

              color: c \=== 0 ? this.p.ink : this.p.body,

              align: isNum\[c\] ? 'right' : 'left', valign: 'top', margin: pad,

              fill: highlight ? { color: tint(this.p.primary, 8\) }

                  : stripe ? { color: this.p.neutral\_fill }

                  : { color: this.p.surface },

              border: \[none, none, divider, none\],

            },

          }));

        });

        // Spread surplus across body rows rather than stretching any one row.

        const bodyNat \= rowH.reduce((a, x) \=\> a \+ x, 0);

        const surplus \= Math.max(0, h \- natural);

        const grown \= rowH.map((hh) \=\> hh \+ (bodyNat ? (surplus \* hh) / bodyNat : 0));

        this.\_note(cite);

        this.s.addTable(\[headerRow, ...bodyRows\], {

          x: this.left, y: ty, w: this.width, colW: widths,

          rowH: \[headH, ...grown\], autoPage: false, border: { type: 'none' },

        });

      },

    };

  }

  \_autoColumnWidths(headers, rows) {

    // Descriptive columns get width proportional to content; numeric and short

    // label columns are floored narrow. No unnecessarily wide empty columns.

    const loads \= headers.map((h, c) \=\> {

      const cells \= rows.map((r) \=\> String(r\[c\] ?? '').length);

      const avg \= cells.length ? cells.reduce((a, b) \=\> a \+ b, 0\) / cells.length : 0;

      return Math.max(String(h).length \* 0.9, avg);

    });

    const total \= loads.reduce((a, b) \=\> a \+ b, 0\) || 1;

    const min \= 0.85;

    const widths \= loads.map((l) \=\> Math.max(min, (l / total) \* this.width));

    const scale \= this.width / widths.reduce((a, b) \=\> a \+ b, 0);

    return widths.map((w) \=\> w \* scale);

  }

  /\* \-- footer \----------------------------------------------------------- \*/

  /\*\* Source line pinned to the footer band. Never part of the content flow. \*/

  source(nums, note) {

    this.\_note(nums);

    if (\!this.sources.size && \!note) return this;

    const marker \= formatCitation(\[...this.sources\]);

    const text \= note ? \`Source ${marker} · ${note}\` : \`Source ${marker}\`;

    this.s.addText(text, {

      x: this.left, y: this.deck.canvas.height\_in \- 0.40,

      w: this.width \- 0.8, h: 0.20,

      isTextBox: true, margin: 0,

      fontFace: this.deck.fonts.body, fontSize: this.scale.footnote,

      color: this.p.muted, lineSpacingMultiple: 1.15,

      valign: 'top', align: 'left', fit: 'none',

    });

    return this;

  }

  pageNumber(n) {

    this.s.addText(String(n), {

      x: this.deck.canvas.width\_in \- 0.85, y: this.deck.canvas.height\_in \- 0.40,

      w: 0.35, h: 0.20, isTextBox: true, margin: 0,

      fontFace: this.deck.fonts.body, fontSize: this.scale.footnote,

      color: this.p.muted, align: 'right', fit: 'none',

    });

    return this;

  }

}

/\* \------------------------------------------------------------------ \*/

/\* Deck                                                                \*/

/\* \------------------------------------------------------------------ \*/

class Deck {

  constructor({ palette \= TOKENS.palettes.default, headerFont, bodyFont } \= {}) {

    this.pptx \= new PptxGenJS();              // one instance per output file

    this.canvas \= TOKENS.canvas;

    this.pptx.defineLayout({

      name: 'PE\_WIDE', width: this.canvas.width\_in, height: this.canvas.height\_in,

    });

    this.pptx.layout \= 'PE\_WIDE';             // set before any slide exists

    this.palette \= TOKENS.palettes\[palette\] || TOKENS.palettes\[TOKENS.palettes.default\];

    this.fonts \= {

      header: headerFont || TOKENS.type.fonts.header,

      body: bodyFont || TOKENS.type.fonts.body,

    };

    this.slides \= \[\];

  }

  slide(opts \= {}) {

    const raw \= this.pptx.addSlide();

    raw.background \= { color: this.palette.surface };

    const s \= new Slide(this, raw, opts);

    this.slides.push(s);

    return s;

  }

  /\*\* References appendix — the single global source index. \*/

  references(sourceMap, { band \= 'dense', title \= 'References' } \= {}) {

    const s \= this.slide({ band, title });

    const entries \= Object.keys(sourceMap)

      .map(Number).sort((a, b) \=\> a \- b)

      .map((n) \=\> \`\[${n}\] ${sourceMap\[n\]}\`);

    const cols \= entries.length \> 14 ? 2 : 1;

    const w \= (s.width \- 0.35) / cols;

    const per \= Math.ceil(entries.length / cols);

    for (let c \= 0; c \< cols; c++) {

      const slice \= entries.slice(c \* per, (c \+ 1\) \* per);

      if (\!slice.length) continue;

      s.s.addText(slice.map((t, i, a) \=\> ({

        text: t, options: { breakLine: i \< a.length \- 1 },

      })), {

        x: s.left \+ c \* (w \+ 0.35), y: s.y, w, h: s.g.content\_bottom\_in \- s.y,

        isTextBox: true, margin: 0,

        fontFace: this.fonts.body, fontSize: s.scale.footnote, color: this.palette.muted,

        lineSpacingMultiple: 1.2, paraSpaceAfter: 2, valign: 'top', fit: 'none',

      });

    }

    return s;

  }

  /\*\*

   \* Layout health per slide. Overrun is a failure; heavy underfill is the

   \* signal that the merging rule should have pulled the next section forward.

   \*/

  audit() {

    return this.slides.map((s, i) \=\> ({

      slide: i \+ 1,

      chars: s.chars,

      overrun\_in: Number(s.overrun.toFixed(2)),

      underfill\_pct: Math.round(s.underfill \* 100),

      sources: \[...s.sources\].sort((a, b) \=\> a \- b),

    }));

  }

  async save(file) {

    for (const r of this.audit()) {

      if (r.overrun\_in \> 0.01) {

        console.warn(

          \`WARN slide ${r.slide}: content runs ${r.overrun\_in}in past the content area. \` \+

          \`Split it — do not reduce type to fit.\`);

      } else if (r.underfill\_pct \> 28 && r.chars \< TOKENS.density.target\_min) {

        // Vertical emptiness only means "under-filled" when the character load is

        // also below target. A horizontally composed slide at 800 characters is

        // dense in the sense the spec measures; it just doesn't stack tall.

        console.warn(

          \`WARN slide ${r.slide}: ${r.chars} characters and ${r.underfill\_pct}% of the \` \+

          \`content area empty. Apply the merging rule — pull related content forward, \` \+

          \`or scale the slide up to the sparse band.\`);

      }

    }

    await this.pptx.writeFile({ fileName: file });

    return file;

  }

}

module.exports \= {

  Deck, Slide, TOKENS,

  tint, estimateLines, textHeightIn, formatCitation, gradientPng,

  visibleChars, blockChars,

};

## FILE: `scripts/audit_deck.py`

\#\!/usr/bin/env python3

"""

audit\_deck.py — post-build compliance audit for pe-deck-design.

layout\_engine.py checks the plan. This checks the artefact. They are different

questions: a plan can be clean and the emitted XML still carry an autofit

shrink, a stray 6pt run, a title in Title Case, or a decorative stripe.

Read-only. Opens the .pptx as a zip and parses slide XML with ElementTree —

it never writes OOXML back, so it cannot corrupt namespace prefixes.

Run it after every build, and again after every fix:

    python3 scripts/audit\_deck.py deck.pptx

    python3 scripts/audit\_deck.py deck.pptx \--json

    python3 scripts/audit\_deck.py deck.pptx \--max-chars 1200

Exit code 1 on any FAIL, so it drops straight into a build pipeline.

"""

import argparse

import json

import os

import re

import sys

import zipfile

from collections import defaultdict

from xml.etree import ElementTree as ET

HERE \= os.path.dirname(os.path.abspath(\_\_file\_\_))

TOKENS\_PATH \= os.path.join(HERE, "..", "assets", "design-tokens.json")

A \= "{http://schemas.openxmlformats.org/drawingml/2006/main}"

P \= "{http://schemas.openxmlformats.org/presentationml/2006/main}"

EMU \= 914400.0

CITE\_RE \= re.compile(r"\\\[\\s\*\\d+(?:\\s\*\[,\\u2013-\]\\s\*\\d+)\*\\s\*\\\]")

URL\_RE \= re.compile(r"(https?://|www\\.)", re.I)

\# Source strings that belong in the appendix, not inside a component.

SOURCE\_LEAK\_RE \= re.compile(

    r"\\b(19|20)\\d{2}\\b\\s\*$|"

    r"\\b(Gartner|McKinsey|Bain|BCG|Nielsen|IBISWorld|Euromonitor|Statista|PitchBook|"

    r"Capital IQ|Bloomberg|Reuters)\\b", re.I)

def load\_tokens(path=TOKENS\_PATH):

    with open(path, "r", encoding="utf-8") as fh:

        return json.load(fh)

class Finding:

    \_\_slots\_\_ \= ("level", "slide", "rule", "message")

    def \_\_init\_\_(self, level, slide, rule, message):

        self.level, self.slide, self.rule, self.message \= level, slide, rule, message

    def as\_dict(self):

        return {"level": self.level, "slide": self.slide,

                "rule": self.rule, "message": self.message}

\# \--------------------------------------------------------------------------

\# helpers

\# \--------------------------------------------------------------------------

def slide\_parts(zf):

    names \= \[n for n in zf.namelist()

             if re.fullmatch(r"ppt/slides/slide\\d+\\.xml", n)\]

    return sorted(names, key=lambda n: int(re.search(r"(\\d+)", os.path.basename(n)).group(1)))

def runs(root):

    """Yield (run\_element, rPr\_element\_or\_None, text) for every text run."""

    for r in root.iter(A \+ "r"):

        rpr \= r.find(A \+ "rPr")

        t \= r.find(A \+ "t")

        yield r, rpr, (t.text or "" if t is not None else "")

def all\_text(root):

    return "".join((t.text or "") for t in root.iter(A \+ "t"))

def emu\_in(value):

    try:

        return int(value) / EMU

    except (TypeError, ValueError):

        return None

def is\_references\_slide(root):

    """

    The References/Appendix slide is the one place where full source strings and

    7pt metadata type are correct. Exempt it from the checks that exist purely to

    push that content here.

    """

    head \= all\_text(root)\[:160\].lower()

    return any(k in head for k in ("references", "source list", "appendix", "bibliography"))

def is\_title\_case(text):

    """Heuristic: most words capitalised in a multi-word string."""

    words \= \[w for w in re.findall(r"\[A-Za-z\]\[A-Za-z'\\-\]\*", text) if len(w) \> 3\]

    if len(words) \< 4:

        return False

    caps \= sum(1 for w in words if w\[0\].isupper())

    return caps / len(words) \> 0.7

\# \--------------------------------------------------------------------------

\# checks

\# \--------------------------------------------------------------------------

def check\_typography(root, sn, tokens, out, exempt=False):

    tt \= tokens\["type"\]

    floor, ceiling \= tt\["footnote\_floor\_pt"\], tt\["max\_pt"\]

    content\_floor \= tt\["min\_pt"\]

    allowed\_fonts \= {tt\["fonts"\]\["header"\], tt\["fonts"\]\["body"\],

                     tt\["fonts"\]\["header\_fallback"\]}

    seen\_fonts \= set()

    sizes \= \[\]

    for \_, rpr, text in runs(root):

        if rpr is None:

            continue

        sz \= rpr.get("sz")

        if sz:

            pt \= int(sz) / 100.0

            sizes.append(pt)

            if pt \< floor:

                out.append(Finding("FAIL", sn, "type.min",

                                   f"{pt:g}pt run below the {floor}pt absolute floor: "

                                   f"{text\[:44\]\!r}"))

            elif pt \< content\_floor and len(text.strip()) \> 60 and not exempt:

                out.append(Finding("WARN", sn, "type.min",

                                   f"{pt:g}pt used for {len(text.strip())} characters of copy. "

                                   f"{floor}pt is reserved for source/footnote metadata; "

                                   f"content floor is {content\_floor}pt."))

            if pt \> ceiling:

                out.append(Finding("FAIL", sn, "type.max",

                                   f"{pt:g}pt run exceeds the {ceiling}pt maximum: "

                                   f"{text\[:44\]\!r}"))

        for latin in rpr.iter(A \+ "latin"):

            face \= latin.get("typeface")

            if face:

                seen\_fonts.add(face)

    stray \= {f for f in seen\_fonts if f not in allowed\_fonts and not f.startswith("+")}

    if stray:

        out.append(Finding("WARN", sn, "type.family",

                           f"Fonts outside the {tt\['fonts'\]\['header'\]}/{tt\['fonts'\]\['body'\]} "

                           f"pair: {sorted(stray)}"))

    \# Distortion: PowerPoint's autofit shrink IS horizontal/vertical font scaling.

    for af in root.iter(A \+ "normAutofit"):

        fs, ls \= af.get("fontScale"), af.get("lnSpcReduction")

        if fs or ls:

            out.append(Finding(

                "FAIL", sn, "type.distortion",

                f"normAutofit is shrinking text (fontScale={fs}, lnSpcReduction={ls}). "

                f"The spec forbids scaling the font to force a fit — resize the box, "

                f"cut copy, or move content to another slide."))

    \# Line spacing bands.

    for lnspc in root.iter(A \+ "lnSpc"):

        pct \= lnspc.find(A \+ "spcPct")

        if pct is None:

            continue

        val \= int(pct.get("val", 0)) / 1000.0

        lo \= tt\["line\_spacing\_multiple"\]\["header\_min"\] \* 100

        hi \= tt\["line\_spacing\_multiple"\]\["body\_max"\] \* 100

        if not (lo \- 0.5 \<= val \<= hi \+ 0.5):

            out.append(Finding("WARN", sn, "type.leading",

                               f"Line spacing {val:g}% sits outside the permitted "

                               f"{lo:g}-{hi:g}% window."))

    return sizes

def check\_case(root, sn, tokens, out):

    maxcaps \= tokens\["type"\]\["case"\]\["allcaps\_max\_chars"\]

    for \_, rpr, text in runs(root):

        stripped \= text.strip()

        if not stripped:

            continue

        letters \= \[c for c in stripped if c.isalpha()\]

        if letters and all(c.isupper() for c in letters) and len(stripped) \> maxcaps:

            out.append(Finding("FAIL", sn, "case.allcaps",

                               f"ALL CAPS run of {len(stripped)} chars. Caps are permitted "

                               f"only for labels/tags up to {maxcaps} chars: {stripped\[:44\]\!r}"))

        elif is\_title\_case(stripped) and len(stripped) \> 24:

            out.append(Finding("WARN", sn, "case.titlecase",

                               f"Looks like Title Case; the spec requires sentence case: "

                               f"{stripped\[:52\]\!r}"))

def check\_geometry(root, sn, tokens, out):

    g, c \= tokens\["grid"\], tokens\["canvas"\]

    left, right \= g\["margin\_left\_in"\], c\["width\_in"\] \- g\["margin\_right\_in"\]

    top, bottom \= 0.25, c\["height\_in"\] \- 0.18

    for sp in list(root.iter(P \+ "sp")) \+ list(root.iter(P \+ "pic")) \+ \\

              list(root.iter(P \+ "graphicFrame")):

        xfrm \= sp.find(f".//{A}xfrm")

        if xfrm is None:

            continue

        off, ext \= xfrm.find(A \+ "off"), xfrm.find(A \+ "ext")

        if off is None or ext is None:

            continue

        x, y \= emu\_in(off.get("x")), emu\_in(off.get("y"))

        w, h \= emu\_in(ext.get("cx")), emu\_in(ext.get("cy"))

        if None in (x, y, w, h):

            continue

        if x \< left \- 0.02 or x \+ w \> right \+ 0.02:

            out.append(Finding("FAIL", sn, "grid.margin",

                               f"Shape spans {x:.2f}in-{x+w:.2f}in, outside the "

                               f"{left:.2f}-{right:.2f}in content band."))

        if y \< top or y \+ h \> bottom \+ 0.02:

            out.append(Finding("FAIL", sn, "grid.vertical",

                               f"Shape spans {y:.2f}in-{y+h:.2f}in vertically, outside the "

                               f"{top:.2f}-{bottom:.2f}in band — content is running off-slide."))

        \# Decorative stripes / accent bars: banned as an AI-slide tell.

        has\_text \= sp.find(f".//{A}t") is not None

        if not has\_text and h \< 0.09 and w \> 2.5:

            out.append(Finding("WARN", sn, "decoration.stripe",

                               f"Thin horizontal bar ({w:.1f}in x {h:.2f}in) with no text. "

                               f"Accent rules and colour stripes are banned — use whitespace."))

        if not has\_text and w \< 0.09 and h \> 1.5:

            out.append(Finding("WARN", sn, "decoration.stripe",

                               f"Vertical stripe ({w:.2f}in x {h:.1f}in) with no text. "

                               f"Edge stripes are banned."))

def check\_citations(root, sn, tokens, out, exempt=False):

    text \= all\_text(root)

    if URL\_RE.search(text):

        out.append(Finding("FAIL", sn, "cite.url",

                           "Raw URL on the slide. Citations are numbered \[n\]; full sources "

                           "belong in the References appendix."))

    nums \= set()

    for m in CITE\_RE.finditer(text):

        nums.update(int(n) for n in re.findall(r"\\d+", m.group()))

    if len(nums) \> tokens\["citation"\]\["appendix\_threshold"\] and not exempt:

        out.append(Finding("WARN", sn, "cite.density",

                           f"{len(nums)} distinct sources cited. Keep \[n\] markers on the slide "

                           f"and move the full list to the References appendix."))

    \# Citation runs must be muted and unemphasised.

    for \_, rpr, rtext in runs(root):

        if not CITE\_RE.fullmatch(rtext.strip() or "x"):

            continue

        if rpr is not None and rpr.get("b") \== "1":

            out.append(Finding("FAIL", sn, "cite.weight",

                               f"Bold citation {rtext.strip()\!r}. Citations stay visually "

                               f"subordinate: regular weight, muted colour."))

    for \_, \_, rtext in runs(root):

        s \= rtext.strip()

        if len(s) \> 20 and SOURCE\_LEAK\_RE.search(s) and not CITE\_RE.search(s):

            out.append(Finding("INFO", sn, "cite.leak",

                               f"Possible full source name inside a component: {s\[:52\]\!r}. "

                               f"Use \[n\] here and the full entry in References."))

            break

    return nums

def check\_density(root, sn, tokens, out):

    text \= all\_text(root)

    chars \= len(CITE\_RE.sub("", text).strip())

    d \= tokens\["density"\]

    if chars \> d\["hard\_max"\]:

        out.append(Finding("FAIL", sn, "density.hard",

                           f"{chars} characters exceeds the {d\['hard\_max'\]} hard maximum. "

                           f"Recompose or split at a logical content boundary."))

    elif chars \> d\["soft\_max"\]:

        out.append(Finding("WARN", sn, "density.soft",

                           f"{chars} characters is past the {d\['soft\_max'\]} soft maximum. "

                           f"Reflow, consolidate, shorten, deprioritise — in that order."))

    elif chars \< 200 and chars \> 0:

        out.append(Finding("INFO", sn, "density.sparse",

                           f"Only {chars} characters. Scale typography up, or pull related "

                           f"content forward so the slide reads as complete."))

    return chars

def check\_tables(root, sn, tokens, out):

    for tbl in root.iter(A \+ "tbl"):

        rows \= list(tbl.iter(A \+ "tr"))

        if not rows:

            continue

        \# Zebra detection: alternating body-row fills.

        fills \= \[\]

        for tr in rows\[1:\]:

            colors \= set()

            for tc in tr.iter(A \+ "tc"):

                tcpr \= tc.find(A \+ "tcPr")

                if tcpr is not None:

                    for sf in tcpr.iter(A \+ "srgbClr"):

                        colors.add(sf.get("val"))

            fills.append(tuple(sorted(colors)))

        zebra \= (len(fills) \>= 4 and

                 len({f for f in fills\[0::2\]}) \== 1 and

                 len({f for f in fills\[1::2\]}) \== 1 and

                 set(fills\[0::2\]) \!= set(fills\[1::2\]))

        \# Tag/pill detection: short, emphasised, repeated first-column-ish labels.

        tagish \= 0

        for tr in rows\[1:\]:

            cells \= list(tr.iter(A \+ "tc"))

            for tc in cells\[1:2\]:

                txt \= "".join((t.text or "") for t in tc.iter(A \+ "t")).strip()

                if 0 \< len(txt) \<= 12 and " " not in txt:

                    tagish \+= 1

        has\_tags \= tagish \>= max(2, len(rows) // 2\)

        if zebra and has\_tags:

            out.append(Finding(

                "FAIL", sn, "table.zebra",

                f"Zebra striping on a table whose rows carry short labels/tags "

                f"({tagish} detected). The spec bans this pairing — keep the background "

                f"uniform and let the tags create the differentiation."))

        \# Wrap pressure.

        for ri, tr in enumerate(rows\[1:\], start=1):

            for tc in tr.iter(A \+ "tc"):

                txt \= "".join((t.text or "") for t in tc.iter(A \+ "t"))

                if len(txt) \> 260:

                    out.append(Finding(

                        "WARN", sn, "table.wrap",

                        f"Row {ri} holds a {len(txt)}-character cell — it will exceed the "

                        f"2-line ceiling. Restructure the table rather than shrinking type."))

                    break

        \# Heavy gridlines.

        heavy \= 0

        for ln in tbl.iter(A \+ "lnL"):

            if ln.find(A \+ "noFill") is None:

                heavy \+= 1

        for ln in tbl.iter(A \+ "lnR"):

            if ln.find(A \+ "noFill") is None:

                heavy \+= 1

        if heavy \> len(rows):

            out.append(Finding("WARN", sn, "table.borders",

                               f"{heavy} vertical cell borders. Prefer subtle horizontal "

                               f"dividers; avoid boxing every cell."))

\# \--------------------------------------------------------------------------

\# driver

\# \--------------------------------------------------------------------------

def audit(pptx\_path, tokens):

    out \= \[\]

    stats \= {}

    with zipfile.ZipFile(pptx\_path) as zf:

        parts \= slide\_parts(zf)

        if not parts:

            out.append(Finding("FAIL", 0, "package", "No slides found in the package."))

            return out, stats

        for part in parts:

            sn \= int(re.search(r"(\\d+)", os.path.basename(part)).group(1))

            root \= ET.fromstring(zf.read(part))

            exempt \= is\_references\_slide(root)

            sizes \= check\_typography(root, sn, tokens, out, exempt)

            check\_case(root, sn, tokens, out)

            check\_geometry(root, sn, tokens, out)

            nums \= check\_citations(root, sn, tokens, out, exempt)

            chars \= check\_density(root, sn, tokens, out)

            check\_tables(root, sn, tokens, out)

            stats\[sn\] \= {

                "references\_slide": exempt,

                "chars": chars,

                "sources": sorted(nums),

                "min\_pt": min(sizes) if sizes else None,

                "max\_pt": max(sizes) if sizes else None,

            }

    return out, stats

def render(findings, stats, pptx\_path):

    by\_slide \= defaultdict(list)

    for f in findings:

        by\_slide\[f.slide\].append(f)

    counts \= defaultdict(int)

    for f in findings:

        counts\[f.level\] \+= 1

    lines \= \[f"audit: {os.path.basename(pptx\_path)}", "=" \* 72\]

    for sn in sorted(stats):

        st \= stats\[sn\]

        rng \= (f"{st\['min\_pt'\]:g}-{st\['max\_pt'\]:g}pt"

               if st\["min\_pt"\] is not None else "no text")

        lines.append(f"\\nslide {sn}  |  {st\['chars'\]} chars  |  {rng}  |  "

                     f"{len(st\['sources'\])} sources")

        for f in sorted(by\_slide.get(sn, \[\]), key=lambda x: x.level):

            lines.append(f"  \[{f.level}\] {f.rule}: {f.message}")

        if not by\_slide.get(sn):

            lines.append("  clean")

    lines.append("\\n" \+ "-" \* 72\)

    lines.append(f"FAIL {counts\['FAIL'\]}   WARN {counts\['WARN'\]}   INFO {counts\['INFO'\]}")

    lines.append("verdict: " \+ ("FAIL" if counts\["FAIL"\] else

                                "PASS (with warnings)" if counts\["WARN"\] else "PASS"))

    return "\\n".join(lines)

def main():

    ap \= argparse.ArgumentParser(description="pe-deck-design compliance audit")

    ap.add\_argument("pptx")

    ap.add\_argument("--json", action="store\_true")

    ap.add\_argument("--tokens", default=TOKENS\_PATH)

    ap.add\_argument("--strict", action="store\_true", help="treat WARN as failure")

    args \= ap.parse\_args()

    tokens \= load\_tokens(args.tokens)

    findings, stats \= audit(args.pptx, tokens)

    if args.json:

        print(json.dumps({"file": args.pptx,

                          "findings": \[f.as\_dict() for f in findings\],

                          "stats": stats}, indent=2))

    else:

        print(render(findings, stats, args.pptx))

    levels \= {f.level for f in findings}

    if "FAIL" in levels or (args.strict and "WARN" in levels):

        return 1

    return 0

if \_\_name\_\_ \== "\_\_main\_\_":

    sys.exit(main())

## FILE: `scripts/example_build.js`

/\*\*

 \* example\_build.js — reference implementation and end-to-end test.

 \*

 \* Builds a four-slide deck using the content from the source specification,

 \* exercising every component: callouts, cards, a tagged table, a zebra table,

 \* a rail, and the References appendix.

 \*

 \*     node scripts/example\_build.js \[out.pptx\]

 \*

 \* Read this before writing a new deck. The shape of the calls is the skill.

 \*/

'use strict';

const { Deck } \= require('./pe\_components');

const SOURCES \= {

  1: 'Del Real Foods, Company overview and product disclosure, 2016',

  51: 'Management analysis, branded retail whitespace, 2016',

  52: 'Management analysis, institutional bid positioning, 2016',

  53: 'Management analysis, ultra-low-cost channel coverage, 2016',

  55: 'Tucson Foods, company profile, 2016',

  60: 'Tucson Foods, product and shelf-life disclosure, 2016',

  66: 'Padrino Foods, company profile, 2016',

  69: 'Padrino Foods, product range disclosure, 2016',

  70: 'Texas Tamale Company, company profile, 2016',

  74: 'Texas Tamale Company, distribution disclosure, 2016',

  91: 'Foodservice operator pull-through analysis, 2016',

  93: 'Buyer labour-savings ROI analysis, 2016',

  123: 'Mira Loma labour and line scheduling review, 2016',

  124: 'Cold-chain throughput assessment, 2016',

  184: 'Plant utilisation and ACV analysis, 2016',

  193: 'Broadline distributor coverage review, 2016',

  194: 'Gross sales by channel, 2016E',

  199: 'Foodservice pack format analysis, 2016',

  202: 'Field sales coverage review, 2016',

};

async function main() {

  const out \= process.argv\[2\] || 'pe-example.pptx';

  const deck \= new Deck({ palette: 'graphite\_navy' });

  /\* \---- slide 1: sparse scale — callouts carry the weight \---------- \*/

  const s1 \= deck.slide({

    band: 'sparse',

    eyebrow: 'COMPANY',

    title: 'Del Real Foods is a refrigerated Hispanic heat-and-eat manufacturer '

         \+ 'with concentrated customer exposure',

  });

  await s1.compose(\[

    { type: 'body',

      text: 'The company sells branded meal components and full meal solutions through '

          \+ 'retail, club, grocery, foodservice, institutional and online channels, with '

          \+ 'revenue recognised when products ship or are delivered.', cite: \[1\] },

    { type: 'callouts', items: \[

      { value: '46.74%', label: 'Value-added meats revenue share', cite: \[194\] },

      { value: '\>60%',   label: 'Top 10 customer concentration',   cite: \[1\] },

      { value: '500+',   label: 'Mira Loma plant workers',         cite: \[184\] },

    \] },

    { type: 'header', text: 'Why this matters to the investment case' },

    { type: 'bullets', items: \[

      { text: 'Concentration above 60% in the top ten accounts makes customer retention '

            \+ 'the single largest downside driver in the base case.', cite: \[1\] },

      { text: 'Value-added meats at 46.74% of revenue anchors mix, so margin defence '

            \+ 'depends on protein input hedging.', cite: \[194\] },

      { text: 'A 500-person plant carries the fixed-cost base that the expansion '

            \+ 'sequencing below is designed to absorb.', cite: \[184\] },

    \] },

  \]);

  s1.source().pageNumber(1);

  /\* \---- slide 2: balanced scale — cards \---------------------------- \*/

  const s2 \= deck.slide({

    band: 'balanced',

    eyebrow: 'STRATEGY',

    title: 'Three priority moves sequence expansion ahead of fixed-cost commitment',

  });

  await s2.compose(\[

    { type: 'cards', items: \[

    { title: 'Win traditional grocery first',

      body: 'Make traditional grocery the lead expansion channel: it is only 20.2% of '

          \+ '2016E gross sales, sits at about 9% national ACV, and holds the largest '

          \+ 'branded retail whitespace.',

      cite: \[194, 184, 51\] },

    { title: 'Scale foodservice on repeatable economics',

      body: 'Grow through broadline distributor reach, foodservice pack formats and field '

          \+ 'sales into chains and institutions — but only after proving operator '

          \+ 'pull-through and buyer labour-savings ROI.',

      cite: \[193, 199, 202, 91, 93\] },

    { title: 'Use plant headroom before adding fixed cost',

      body: 'Push volume through Mira Loma, about 62% utilised across 13 lines in a '

          \+ '114,000 sq ft plant, before underwriting major capacity spend.',

      cite: \[184, 123, 124\] },

    \] },

    { type: 'header', text: 'Sequencing test before capital is committed' },

    { type: 'callouts', items: \[

      { value: '20.2%', label: 'Traditional grocery share of 2016E gross sales — the gap '

                             \+ 'the lead channel is meant to close', cite: \[194\] },

      { value: '62%',   label: 'Mira Loma utilisation, the headroom that must be consumed '

                             \+ 'before new fixed cost is underwritten', cite: \[184\] },

    \] },

  \]);

  s2.source().pageNumber(2);

  /\* \---- slide 3: tagged table — zebra must stay OFF \---------------- \*/

  const s3 \= deck.slide({

    band: 'dense',

    eyebrow: 'FOOTPRINT',

    title: 'Club-store placement concentrates presence in the West and Southeast',

  });

  await s3.compose(\[

    { type: 'table',

    headers: \['Region', 'Presence', 'Key markets and strategic role'\],

    rows: \[

      \['Northwest', 'Major',

       'Portland, Salem, Central Point — club placement extended reach for ready-in-minutes meals.'\],

      \['Los Angeles', 'Major',

       'Inglewood, Marina del Rey, Norwalk — club placement opened a prepared-foods outlet.'\],

      \['Southeast', 'Major',

       'Atlanta, Charlotte, Myrtle Beach — club placement gave Southeast distribution.'\],

      \['N. California', 'Major',

       'San Francisco — club placement reached the regional buying network.'\],

      \['San Diego', 'Major',

       'Mission Valley, San Marcos — club placement opened the San Diego regional network.'\],

      \['Midwest', 'Moderate',

       'Chicago, Plainfield, Middleton — no 2016 club placement left the region uncovered.'\],

      \['Texas', 'Moderate',

       'Frisco, Fort Worth — no 2016 club placement left the region uncovered.'\],

    \],

    zebra: false,        // rows carry Major/Moderate tags, so striping is banned

    hasTags: true,

    cite: \[1, 184\] },

    { type: 'header', text: 'Read-through' },

    { type: 'body',

      text: 'Club placement, not brand pull, explains the Major/Moderate split. The three '

          \+ 'Moderate regions are uncovered rather than lost, so they price as expansion '

          \+ 'optionality rather than as competitive displacement risk.', cite: \[1\] },

  \]);

  s3.source().pageNumber(3);

  /\* \---- slide 4: rail \---------------------------------------------- \*/

  const s4 \= deck.slide({

    band: 'balanced',

    eyebrow: 'M\&A',

    title: 'Acquiring a frozen adjacency broadens format mix and hedges bid exposure',

  });

  await s4.compose(\[

    { type: 'body',

      text: 'A frozen-adjacent asset improves the weaker position in price-sensitive '

          \+ 'institutional bids and ultra-low-cost channels.', cite: \[52, 53\] },

    { type: 'header', text: 'Screened targets' },

    { type: 'rail', items: \[

      { title: 'Padrino Foods',

        body: 'Adjacent frozen and authentic Mexican depth.', cite: \[66, 67, 68, 69\] },

      { title: 'Texas Tamale Company',

        body: 'Frozen tamale platform with regional appeal.', cite: \[70, 71, 72, 73, 74\] },

      { title: 'Tucson Foods',

        body: 'Frozen shelf-life and tamale adjacency.', cite: \[55, 56, 57, 58, 59, 60\] },

    \] },

    { type: 'header', text: 'Diligence gates common to all three' },

    { type: 'bullets', items: \[

      { text: 'Confirm frozen capacity is incremental rather than a substitute for '

            \+ 'refrigerated throughput already running at Mira Loma.', cite: \[184\] },

      { text: 'Test whether institutional bid losses trace to format or to price, since '

            \+ 'only the former is fixed by a frozen asset.', cite: \[52, 53\] },

      { text: 'Size the cold-chain and scheduling burden of running two temperature '

            \+ 'states before underwriting synergy.', cite: \[123, 124\] },

    \] },

    { type: 'callouts', items: \[

      { value: '3 of 3', label: 'Targets require a frozen-capacity confirmation before '

                              \+ 'any indicative offer', cite: \[184\] },

      { value: '2 states', label: 'Temperature states to operate post-close, the main '

                                \+ 'source of integration risk', cite: \[123, 124\] },

    \] },

  \]);

  s4.source().pageNumber(4);

  /\* \---- references: one global source index \------------------------ \*/

  deck.references(SOURCES).pageNumber(5);

  await deck.save(out);

  console.log(\`built ${out}\`);

}

main().catch((e) \=\> { console.error(e); process.exit(1); });

## FILE: `references/typography.md`

\# Typography

Source: the specification. \`DOC\` \= stated verbatim, \`DERIVED\` \= computed from a DOC rule.

\#\# Families \`DOC\`

| Role | Font |

|---|---|

| Headers (slide title, section header, card/rail/table titles, callout values, eyebrow) | \*\*Manrope\*\* |

| Body (paragraphs, bullets, table cells, labels, footnotes, citations) | \*\*Arial\*\* |

\*\*QA caveat.\*\* Manrope has no metric-compatible substitute in the local LibreOffice

renderer. Header fit in the PDF/image preview is \*\*approximate\*\*: size header containers

with roughly 10% slack and do not trust a borderline header overflow read from the preview.

Arial renders true-to-width, so body overflow reads are trustworthy.

\`estimateLines()\` in \`pe\_components.js\` uses a 0.60em average advance for headers versus

0.50em for body. That over-estimate is deliberate — under-estimating header lines is

exactly what makes a card title collide with its own body.

If Manrope is unavailable in the target environment, \`Calibri\` is the declared fallback.

Never fall back to Aptos: it has no reliable substitute here and is missing from older

Office installs.

\#\# Role ranges \`DOC\`

| Element | Size | Weight | Use |

|---|---|---|---|

| Slide title | 14–16 pt | Bold | The main message of the slide |

| Section / sub-header | 12–14 pt | Medium | Major content blocks |

| Body text & key insight | 9–10 pt | Regular | Explanatory content |

| Table title | 12–14 pt | Semibold | Clear title above the table |

| Table column header | 9–10 pt | Semibold | Subtle background or divider |

| Table body / cell | 8–9 pt | Regular | Dense tables |

| Table key metric / total | 9–10 pt | Semibold | Subtle emphasis |

| Chart labels | 8–9 pt | Regular | Axes, legends, data labels |

| Source / footnote | 7–8 pt | Regular | Sources, methodology, notes |

| Citation | 8–9 pt | Regular | Inline \`\[n\]\` markers |

\#\# Scale resolution \`DERIVED from DOC\`

The spec states both a per-element range and a slide-level density rule:

\> Sparse slide → 14–16 pt · Balanced slide → 10–14 pt · Dense slide → 8–10 pt

\> Minimum 8 pt, maximum 16 pt.

\> The relative hierarchy between title, header, body, chart labels and footnotes should

\> remain consistent; only the overall scale changes.

Resolution: the per-element table defines each role's range; the density rule decides where

within every range the slide sits. Roles move together and never cross.

| Role | dense | balanced | sparse |

|---|---|---|---|

| title | 14 | 15 | 16 |

| header | 12 | 13 | 14 |

| body / key insight | 9 | 10 | 10 |

| table title | 12 | 13 | 14 |

| table header / metric | 9 | 10 | 10 |

| table body | 8 | 9 | 9 |

| chart label | 8 | 9 | 9 |

| citation | 8 | 9 | 9 |

| footnote | 7 | 8 | 8 |

\*\*Core principle \`DOC\`:\*\* choose the largest overall typography scale that fits the slide

comfortably without creating overflow or excessive whitespace.

\#\#\# The 8pt / 7pt reconciliation

The spec sets a global 8 pt minimum \*and\* separately sets source/footnote at 7–8 pt.

Resolution, recorded in \`design-tokens.json\` as \`footnote\_floor\_note\`:

\- \*\*8 pt is the floor for content.\*\*

\- \*\*7 pt is permitted only for source, footnote and citation metadata.\*\*

\`audit\_deck.py\` enforces exactly this: 7 pt runs are allowed, but a 7 pt run carrying more

than 60 characters of copy is flagged as content masquerading as metadata. The References

slide is exempt.

\#\# Formatting rules \`DOC\`

\*\*Sentence case.\*\* Slide titles and headers use sentence case. ALL CAPS is permitted only

for short labels, tags or metadata (≤18 characters — \`DERIVED\` bound). Title Case for every

word is banned. \`audit\_deck.py\` flags long caps runs as FAIL and probable Title Case as WARN.

\*\*Keep lines readable.\*\* Avoid long, stretched lines. If a line runs too long, adjust the

text area or the layout — not the font size.

\*\*Never distort the font.\*\* No horizontal or vertical stretching, compressing or scaling.

To make text fit, change font size (within range), text box size, spacing, or layout.

PowerPoint's autofit shrink is this distortion applied automatically, so

\`\<a:normAutofit fontScale="…"\>\` is a build failure. Every \`addText\` in the component

library passes \`fit: 'none'\` to prevent it being written in the first place.

\*\*Line spacing.\*\*

| Role | Multiple |

|---|---|

| Body | 1.10–1.25× |

| Headers | 0.95–1.10× |

| Citations | 1.10–1.20× |

\*\*Paragraph spacing:\*\* 3 pt after. \*\*Section spacing:\*\* 8 pt after. Keep both minimal and

consistent.

\#\# One-line summary \`DOC\`

\> Keep typography readable, proportional and consistent. Use sentence case, control line

\> length, never distort fonts, and maintain consistent line spacing across the slide.

## FILE: `references/components.md`

\# Components: cards, rails, callouts

Source: the specification. \`DOC\` \= stated verbatim, \`DERIVED\` \= computed or a geometry

constant the spec implies but does not number.

\#\# The defining difference \`DOC\`

These three containers are distinguished by border and fill alone. That is the whole

visual system — if a rail looks like a card, the system has failed.

| Component | Border | Fill |

|---|---|---|

| \*\*Card\*\* | 1 pt, neutral | \*\*none\*\* |

| \*\*Rail\*\* | 1 pt | gradient \*\*of the border colour\*\* |

| \*\*Callout\*\* | \*\*none\*\* | gradient \*\*of the primary colour\*\* |

\`pe\_components.js\` hardcodes these. They are not parameters, and no caller can override them.

\#\#\# Gradients in practice \`DERIVED\`

pptxgenjs cannot emit an OOXML gradient fill. The component library renders each gradient

as a rounded-rect alpha PNG through \`sharp\` at 4× placement resolution and places it behind

the shape. This is the only route that survives a round trip into PowerPoint.

Tint stops: 10% → 2% of the base colour, mixed toward white, on a 135° axis. Deliberately

faint — the fill is a container signal, not a highlight. Do not substitute a solid fill:

the gradient is the only thing separating a rail from a card.

Geometry \`DERIVED\`: corner radius 0.06", card padding 0.16" × 0.12", rail padding

0.16" × 0.12", callout padding 0.18" × 0.14", gaps 0.18" / 0.14" / 0.18".

\#\# Cards \`DOC\`

| Count | Treatment |

|---|---|

| 1–3 | Larger cards, stronger typography, more internal whitespace |

| 4–6 | Reduce card width and spacing while keeping content readable |

| 7+ | \*\*Do not keep shrinking.\*\* Switch to a more scalable layout — a rail or a grouped structure |

\- Card height follows content, but \*\*cards within the same row must share a common height\*\*.

\- Short content → increase whitespace. Long content → reduce padding and spacing \*\*before\*\*

  reducing font size.

\- \*\*Don't force equal card widths\*\* when content lengths differ significantly.

\- Each card contains \*\*one primary data point or message\*\*.

\`compose()\` throws at 7+. Growth cap for cards is 0.30 \`DERIVED\`: a card is a content

container, so stretching it past that just moves dead space inside the border. Surplus

beyond the cap flows to the gaps instead.

\#\# Horizontal rail \`DOC\`

| Count | Treatment |

|---|---|

| 2–4 | Larger item widths, generous spacing |

| 5–6 | Compact spacing, smaller item widths |

| 7+ | \*\*Do not reduce typography below the minimum.\*\* Split the rail or change the component |

\- \*\*Item width responds to content length\*\* rather than being rigidly equal. Short items

  should not create excessive empty space just to match a long item.

\- Maintain consistent alignment across all items.

\- \*\*Preserve order\*\* when the data represents a sequence.

\- Keep each item concise — rail items are not paragraphs.

\- If the rail becomes too tall or compressed, \*\*restructure before reducing typography\*\*.

Width algorithm \`DERIVED\`: each item is weighted by character load, then pulled toward the

mean (\`0.6 \+ 0.4 × load/mean\`) so nothing collapses to a sliver and nothing hogs the rail.

Items share a height but each item's own content is centred vertically within it, so short

items don't read as clipped.

\#\# Callouts \`DOC\`

| Count | Treatment |

|---|---|

| 1 | Stronger visual emphasis and more whitespace |

| 2 | Balance by content length; they \*\*don't need identical heights\*\* |

| 3+ | Only when each represents a \*\*distinct insight\*\*; otherwise combine them |

\- Short insight → larger type and more whitespace. Long insight → increase available space

  and reduce internal spacing \*\*before\*\* reducing font size.

\- Keep the primary message visually dominant.

\- \*\*Don't force every callout to the same height\*\* when content differs significantly.

\- Avoid callouts becoming containers for large amounts of body text.

\- If content exceeds readable capacity, \*\*restructure or move the overflow\*\* rather than

  shrinking below the minimum font size.

Implementation \`DERIVED\`: a single callout gets value type at \`title \+ 1\` (capped at 16pt)

and 1.5× vertical padding. The metric itself is a clean bold run — its citation rides on

the label beneath, so the number never carries bold bracket noise. Content is centred

vertically inside a grown callout.

\`compose()\` throws at 5+. At 3–4 the layout engine emits a WARN asking you to justify that

each is genuinely distinct.

\#\# The common rule \`DOC\`

\> Content volume determines component size, spacing and structure. Never preserve fixed

\> dimensions at the cost of whitespace or readability. When content exceeds the component's

\> capacity, restructure or move to the next slide rather than continuously shrinking the

\> component.

This rule is what the two-phase layout in \`pe\_components.js\` exists to make mechanical.

## FILE: `references/tables.md`

\# Tables

Source: the specification. \`DOC\` \= stated verbatim, \`DERIVED\` \= computed.

\#\# Element specification \`DOC\`

| Element | Size | Weight | Alignment / spacing | Style rule |

|---|---|---|---|---|

| Table title | 12–14 pt | Semibold | Left | Clear title above the table |

| Column header | 9–10 pt | Semibold | Match column | Subtle background or divider |

| Body / cell text | 8–9 pt | Regular | Text left; numbers right | Compact and readable |

| Key metric / total | 9–10 pt | Semibold | Match column | Subtle emphasis |

| Source / footnote | 7–8 pt | Regular | Left | Keep below the table |

| Cell padding | — | — | 6–8 pt horizontal, 4–6 pt vertical | Consistent throughout |

| Borders | — | — | — | Prefer subtle horizontal dividers; avoid heavy gridlines |

| Row height | — | — | — | Minimum required for content; avoid excess whitespace |

| Number format | — | — | Right aligned | Keep decimals and units consistent |

| Text wrapping | — | — | — | Prefer 1–2 lines; avoid overly tall cells |

\#\# Zebra striping — the sharpest rule \`DOC\`

\> Avoid zebra striping when rows contain labels, tags, pills or other visual indicators.

\> Keep the table background uniform and use the tags/pills to create visual differentiation.

\>

\> For dense data-only tables without tags, subtle zebra striping can be used if it improves

\> row scanning.

\>

\> Avoid combining zebra stripes \+ coloured tags \+ highlighted rows — it creates unnecessary

\> visual noise.

Enforced in two places, because a table can be built by hand as well as through the library:

\- \`pe\_components.js\` \*\*throws\*\* on \`zebra: true\` with \`hasTags: true\`, and on \`zebra: true\`

  with \`highlightRows\`.

\- \`audit\_deck.py\` detects alternating body-row fills in the emitted XML, detects short

  single-word second-column values as probable tags, and FAILs the combination.

The layout engine also emits an INFO the other way: a data-only table of 8+ rows with no

tags is a case where striping is \*\*permitted\*\* and will aid scanning.

\#\# Column hierarchy and width \`DOC\`

\- Make the \*\*primary / most important column visually dominant\*\*. Avoid giving every column

  equal visual weight.

\- \*\*Wider columns for descriptive text.\*\* Narrower for numbers, percentages, dates and short

  labels. Avoid unnecessarily wide empty columns.

\`\_autoColumnWidths()\` \`DERIVED\` weights each column by the greater of its header length and

its mean cell length, floors every column at 0.85", then normalises to the content width.

The first column is the only bold body column — that is how hierarchy is expressed without

adding colour.

\#\# Wrapping \`DOC\`

\- \*\*Prefer 1 line. Allow a maximum of 2 lines\*\* for normal cells.

\- If content consistently exceeds 2 lines, \*\*restructure the table rather than making the

  font smaller\*\*.

\`layout\_engine.py\` FAILs any cell past \~124 characters (≈2 lines at table sizes);

\`audit\_deck.py\` WARNs past 260 characters in the emitted XML.

\#\# Numbers \`DOC\`

\- Right-align numeric values.

\- Align decimal places within a column.

\- Use consistent units and decimal precision — \`12.4%, 8.7%, 5.2%\`, not mixed formats.

Detection \`DERIVED\`: a column is treated as numeric when \*\*every\*\* cell matches a

currency/number/unit pattern. One stray text cell makes the whole column left-aligned,

which is the correct conservative behaviour.

\#\# Emphasis and colour \`DOC\`

\- \*\*Bold only\*\* important values, totals or key rows. Never bold an entire table.

\- Use \*\*one\*\* visual treatment for highlighted cells, consistently.

\- Keep the table primarily neutral. \*\*One accent colour\*\* for emphasis. Don't colour every

  row or column differently.

\#\# Structure and position \`DOC\`

\- Separate logical groups with spacing or subtle dividers. \*\*Avoid borders around every

  individual cell.\*\*

\- Align tables to the slide's main content grid. Maintain consistent left/right margins

  across slides. Avoid tables floating with arbitrary positioning.

The library draws bottom dividers only — left and right cell borders are explicitly

\`{ type: 'none' }\`, and the header carries a single 1 pt primary-colour rule beneath it.

\`audit\_deck.py\` WARNs if it finds more vertical cell borders than rows.

\#\# Overflow order \`DOC\`

Fixed escalation, and typography is \*\*last\*\*:

1\. Column widths

2\. Cell padding

3\. Wrapping

4\. Overall table size

5\. Only then, typography within the allowed range

\> Never allow unreadable text just to preserve the table structure.

## FILE: `references/citations.md`

\# Citations

Source: the specification. \`DOC\` \= stated verbatim, \`DERIVED\` \= computed.

\> Citations should function as \*\*traceability metadata, not a visual content element\*\*.

That sentence governs everything below.

\#\# Style and placement \`DOC\`

\- Numbered citations \`\[n\]\` are the default style across the \*\*entire\*\* presentation.

\- Place the citation \*\*immediately after\*\* the claim, metric, statement, chart or data

  point it supports.

\- \`\[3\]\` for a single source · \`\[3, 7\]\` for multiple non-consecutive · \`\[3-7\]\` for

  consecutive runs.

Both \`layout\_engine.format\_citation()\` and \`pe\_components.formatCitation()\` implement the

same collapse: a run of three or more consecutive numbers becomes a range, two consecutive

numbers stay listed. The two implementations are deliberately mirrored so the plan and the

build never disagree.

\#\# Typography \`DOC\`

| Property | Value |

|---|---|

| Font | Same family as the presentation |

| Size | 8–9 pt |

| Weight | Regular |

| Colour | Secondary / muted |

| Line height | 1.1–1.2× |

| Case | Sentence case |

\*\*Never\*\* use bold, uppercase styling, coloured badges, filled pills, borders, or separate

citation cards. \`audit\_deck.py\` FAILs a bold citation run.

In the component library, \`\_runs()\` splits any cited text into two runs: the claim at body

size and colour, then the citation one step down in the muted colour. A citation never

inherits the emphasis of the text it follows — which is why a callout's metric carries no

bracket: the citation rides on the label beneath instead.

\#\# What must never appear inside a component \`DOC\`

Do \*\*not\*\* display full source names, publication titles, URLs or long source text within

cards, callouts, charts, tables or any other content component.

\`audit\_deck.py\` FAILs on any raw URL found on a slide, and emits an INFO when it spots what

looks like a publication name or a bare year inside a component.

\#\# Form by context \`DOC\`

| Context | Form |

|---|---|

| Key metric | \`12.4% CAGR \[3\]\` · \`$42B market size \[3, 7\]\` |

| Chart or visualisation | Small source line at the bottom of the visual: \`Source \[3, 5\]\` |

| Table | \*\*One table-level citation\*\* when the same sources support the table. Cell-level citations only when individual values come from different sources. |

\#\# Grouping and the appendix \`DOC\`

\- If a component has \*\*more than 3 sources\*\*, use grouped references rather than listing

  source names.

\- If a slide contains \*\*more than 6–8 sources\*\*, do not expand the slide footer with full

  source information. Keep numbered citations on the slide and provide the complete list in

  the References / Appendix.

Both thresholds are wired: the layout engine emits INFO past 3 sources on a component and

WARN past 8 on a slide; the auditor repeats the slide-level check against the emitted XML.

\#\# The global index \`DOC\`

\> Maintain a single source index across the entire deck. \`\[3\]\` must always refer to the

\> same source wherever it appears.

Full source details follow one consistent format:

\`\`\`

\[3\] Gartner, Semiconductor Forecast, 2025

\[7\] McKinsey, Global Semiconductor Outlook, 2025

\`\`\`

\`Deck.references(sourceMap)\` renders this as a single appendix slide, sorted numerically,

splitting to two columns past 14 entries. The auditor auto-detects the References slide and

exempts it from the citation-density and 7 pt-metadata checks — it is the one place full

source strings belong.

\#\# Layout independence \`DOC\`

\> Citation space must never change the primary component layout. Do not shrink the main

\> content or increase component height just to accommodate longer source text.

Two consequences, both enforced:

1\. \*\*Citations are excluded from the character budget.\*\* \`visible\_chars()\` in Python and

   \`visibleChars()\` in JS strip \`\[n\]\` markers before counting. A slide is never pushed into

   a denser band by its own sourcing.

2\. \*\*Citations never drive component sizing.\*\* They are measured as part of the text they

   follow, never as a reason to grow a container.

\#\# A pptxgenjs constraint worth knowing \`DERIVED\`

A bulleted paragraph \*\*cannot\*\* hold two differently-styled runs. Any run without a bullet

option emits its own \`\<a:pPr\>\` containing \`\<a:buNone/\>\`, which silently kills the bullet for

the entire paragraph; giving every run the bullet option instead splits them into separate

bulleted paragraphs, so the citation lands on its own bulleted line.

Both failure modes were verified against rendered output. Because "bulleted claim \+ muted

citation" is therefore unreachable through \`addText\` bullets, \`pe\_components.js\` draws the

bullet marker as its own text box at a fixed 0.20" hanging indent and puts the claim in a

second box with mixed runs. That also gives exact indent control the built-in bullet does

not expose.

## FILE: `references/density-and-pagination.md`

\# Slide density and pagination

Source: the specification. \`DOC\` \= stated verbatim, \`DERIVED\` \= computed.

\#\# The character budget \`DOC\`

Each slide has a total character budget: the sum of all visible content elements — titles,

paragraphs, bullets, card text, callouts, table text, labels and other readable copy.

\*\*Citations are excluded, because they are metadata.\*\*

| Band | Characters | Action |

|---|---|---|

| Target | 600–900 | Preferred |

| Soft maximum | 1,000 | Optimise if possible |

| Hard maximum | 1,200 | Strong overflow check |

| Beyond | \> 1,200 | Recompose / condense / consider next slide |

\#\#\# The engineering formula \`DOC\`

\`\`\`

slide characters \=

    title

  \+ subtitles / context

  \+ paragraphs

  \+ bullets

  \+ card titles

  \+ card bodies

  \+ callouts

  \+ table text

  \+ chart labels

  \+ other visible copy

then:

  ≤ 900        → Preferred

  901–1,000    → Optimise if possible

  1,001–1,200  → Strong overflow check

  \> 1,200      → Recompose / condense / consider next slide

\`\`\`

Implemented identically twice: \`slide\_chars()\` in \`layout\_engine.py\` (pre-build, from the

content spec) and \`blockChars()\` in \`pe\_components.js\` (during build, accumulated on the

slide). \`audit\_deck.py\` recomputes it a third time from the emitted XML, which catches

anything added outside \`compose()\`.

\#\#\# Guardrail, not a page-break trigger \`DOC\`

\- Character limits are a \*\*density guardrail\*\*, not an automatic page break.

\- When the total exceeds target, \*\*first restructure, condense or prioritise\*\*.

\- Create a next slide only when important content still cannot fit clearly.

\- \*\*Never shrink typography below the defined minimum\*\* just to stay within the limit.

\#\# Density drives typography \`DOC\`

The band selects the scale. See \`typography.md\` for the full table.

| Band | Characters | Scale |

|---|---|---|

| sparse | ≤ 550 \`DERIVED\` | title 16 / header 14 / body 10 |

| balanced | 551–900 | title 15 / header 13 / body 10 |

| dense | 901–1,200 | title 14 / header 12 / body 9 |

| overflow | \> 1,200 | not a scale — a recomposition order |

The 550 boundary is \`DERIVED\`: the spec names the three bands and sets the 600–900 target,

so the sparse ceiling is placed just below the target floor.

\#\# Dynamic slide merging \`DOC\`

\> Before creating a new slide, check whether the next content can fit on the current slide.

\>

\> \- If related content fits without making the slide crowded → \*\*merge\*\* it into the

\>   current slide.

\> \- If there is not enough space → \*\*create a new slide\*\*.

\> \- Never reduce text below the minimum font size just to make content fit.

\> \- Never merge unrelated content only to fill empty space.

\> \- Reflow and resize components before creating a new slide.

\*\*Decision rule:\*\*

\`\`\`

Fit \+ Related \+ Readable          → Merge

Doesn't fit / Unrelated / Not readable → New slide

\`\`\`

\*\*Worked example \`DOC\`:\*\* Slide 1 has 3 cards but space below them. If Slide 2 contains

2 related callouts \+ pointers that fit comfortably, move them onto Slide 1 instead of

creating Slide 2\.

This prevents unnecessary slides, excessive whitespace and under-filled layouts while

keeping the slide readable.

\`pagination\_plan()\` emits this per slide as \`keep\` / \`merge\_next\` / \`split\`, with the

reasoning attached. Merging requires a matching \`section\` field and a combined total within

the 900-character target; a sparse slide whose neighbour belongs to a different section is

explicitly told \*\*not\*\* to merge, and to scale up instead.

\#\# Two different axes \`DERIVED\`

Vertical emptiness and character load are \*\*not\*\* the same measurement. A slide at 800

characters composed horizontally — three callouts across, a wide table — is dense in the

sense the spec measures, even though it doesn't stack tall.

So \`Deck.save()\` only warns about underfill when \*\*both\*\* conditions hold: more than 28% of

the content area is empty \*\*and\*\* the character load is below the 600 target. That prevents

the build from nagging about correctly composed horizontal slides while still catching

genuinely thin ones.

\#\# Additional slide rules \`DOC\`

\- \*\*One section \= one slide by default.\*\* Do not split unless content genuinely requires it.

\- \*\*Use any layout / component combination.\*\* No fixed card count, column count or template

  structure.

\- \*\*Optimise before splitting:\*\* reflow → consolidate → shorten → deprioritise → split.

\- \*\*Set a minimum readable font size.\*\* Never solve overflow by continuously shrinking

  typography.

\- \*\*Control component density.\*\* Avoid too many small components competing for attention.

\- \*\*Avoid excessive whitespace.\*\* If meaningful content can naturally fit, don't push it to

  the next slide.

\- \*\*Don't force symmetry.\*\* Unequal card sizes or layouts are acceptable when driven by

  content importance.

\- \*\*Split at logical boundaries.\*\* If a second slide is needed, move a meaningful

  sub-topic — not leftover content.

\- \*\*Keep citations out of the content budget.\*\* Use \`\[n\]\` citations as lightweight metadata.

\- \*\*Prioritise information, not component count.\*\* A slide with 2 important components can

  be better than one with 6 weak ones.

\- \*\*Every slide must feel complete.\*\* Avoid continuation slides containing only one small

  card, bullet or callout.

\#\# The engine rule in one line \`DOC\`

\> Fit one complete section within a shared slide content budget, using an adaptive layout;

\> optimise composition before pagination, and move to the next slide only when important

\> content cannot remain readable and meaningful on the current slide.

## FILE: `references/source-spec.md`

\# Source specification — preserved in full

This file preserves the original specification as supplied, in its own order, including the

worked examples and sample tables. It exists so that nothing is lost in the translation into

tokens and code, and so any rule in this skill can be traced back to its origin.

\*\*If this file and the rest of the skill ever disagree, this file is correct\*\* and the

skill has a bug. Every \`DOC\` value in \`assets/design-tokens.json\` comes from here.

Editorial note: the only changes are formatting (markdown structure, tables reconstructed

from the flattened export) and the removal of duplicated fragments from the export process.

No rule, number, threshold or example has been altered, dropped or added.

\---

\#\# 1\. Font style and rules

\*\*Header — Manrope. Body — Arial.\*\*

\#\#\# Font rules

| Element | Font size | Weight | Recommended use |

|---|---|---|---|

| Slide title | 14–16 pt | Bold | Main message of the slide |

| Section / sub-header | 12–14 pt | Medium | Major content blocks |

| Body text & key insight | 9–10 pt | Regular | Explanatory content |

| Table text | 8–9 pt | Regular | Dense tables |

| Chart labels | 8–9 pt | Regular | Axes, legends, data labels |

| Source / footnote | 7–8 pt | Regular | Sources, methodology, notes |

\#\#\# Font formatting rules

\*\*Use sentence case\*\*

\- Use sentence case for slide titles and headers.

\- Use ALL CAPS only for short labels, tags, or metadata.

\- Avoid Title Case for every word.

\*\*Keep text lines readable\*\*

\- Avoid long, stretched lines of text.

\- If a line becomes too long, adjust the text area or layout rather than shrinking the font.

\*\*Never distort the font\*\*

\- Do not stretch, compress, or scale the font horizontally or vertically.

\- To make text fit, adjust font size, text box size, spacing, or layout.

\*\*Maintain consistent line spacing\*\*

\- Body: 1.1–1.25× the font size

\- Headers: 0.95–1.1× the font size

\- Keep paragraph spacing minimal and consistent. Paragraph spacing: 3 pt after.

  Section spacing: 8 pt after.

\*\*Even simpler backend rule\*\*

\> Keep typography readable, proportional, and consistent. Use sentence case, control line

\> length, never distort fonts, and maintain consistent line spacing across the slide.

\#\#\# Backend logic for font sizing

\> Determine font size at the overall slide level based on content density and available

\> whitespace. Use a single proportional typography scale across the slide: increase the

\> scale for sparse slides, keep it moderate for balanced slides, and reduce it for dense

\> slides. Maintain 8 pt as the minimum and 16 pt as the maximum.

\*\*Simple rule\*\*

\`\`\`

Sparse slide   → 14–16 pt

Balanced slide → 10–14 pt

Dense slide    → 8–10 pt

\`\`\`

The relative hierarchy between title, header, body, chart labels, and footnotes should

remain consistent; only the overall scale changes.

\*\*Core principle\*\*

\> Choose the largest overall typography scale that fits the slide comfortably without

\> creating overflow or excessive whitespace.

\---

\#\# 2\. Table rules and representation

\#\#\# Table representation 1 — no zebra

\> no zebra \> has label with any one of column or row

| Region / Presence | | Key Markets & Strategic Role |

|---|---|---|

| Northwest | Major | Portland, Salem, Central Point — Costco placement made this region part of Del Real's club-store reach for ready-in-minutes Hispanic meals and sides. |

| Los Angeles | Major | Inglewood, Marina del Rey, Norwalk — Costco placement made Los Angeles a club-store outlet for Del Real's prepared Hispanic foods, extending access through Costco's Los Angeles region. |

| Southeast | Major | Atlanta, Charlotte, Myrtle Beach — Costco placement gave Del Real club-store distribution in Costco's Southeast region for its ready-in-minutes Hispanic meals and sides. |

(Presence values shown in the source as HIGH / HIGH / HIGH labels.)

\#\#\# Table representation 2 — in zebra

| Region / Presence | | Key Markets & Strategic Role |

|---|---|---|

| Northwest | Major | Portland, Salem, Central Point — Costco placement made this region part of Del Real's club-store reach for ready-in-minutes Hispanic meals and sides. |

| Los Angeles | Major | Inglewood, Marina del Rey, Norwalk — Costco placement made Los Angeles a club-store outlet for Del Real's prepared Hispanic foods, extending access through Costco's Los Angeles region. |

| Southeast | Major | Atlanta, Charlotte, Myrtle Beach — Costco placement gave Del Real club-store distribution in Costco's Southeast region for its ready-in-minutes Hispanic meals and sides. |

| Northern California | Major | San Francisco — Costco placement made Northern California a club-store outlet for Del Real's prepared Hispanic foods through Costco's regional buying network. |

| San Diego | Major | Mission Valley, San Marcos — Costco placement made San Diego a club-store outlet for Del Real's prepared Hispanic foods through Costco's San Diego regional network |

| Midwest | Moderate | Chicago, Plainfield, Middleton — No Costco placement in 2016 left Del Real outside the Midwest club-store footprint at that time |

| Northeast | Moderate | Not disclosed — No Costco placement in 2016 left Del Real outside the Northeast club-store footprint at that time. |

| Texas | Moderate | Frisco, Fort Worth — No Costco placement in 2016 left Del Real outside the Texas club-store footprint at that time. |

\#\#\# Table element specification

| Element | Font size | Weight | Alignment / spacing | Style rule |

|---|---|---|---|---|

| Table title | 12–14 pt | Semibold | Left | Clear title above table |

| Column header | 9–10 pt | Semibold | Match column | Subtle background or divider |

| Body / cell text | 8–9 pt | Regular | Text: left; numbers: right | Compact and readable |

| Key metric / total | 9–10 pt | Semibold | Match column | Subtle emphasis |

| Source / footnote | 7–8 pt | Regular | Left | Keep below table |

| Cell padding | — | — | 6–8 pt horizontal, 4–6 pt vertical | Consistent throughout |

| Borders | — | — | — | Prefer subtle horizontal dividers; avoid heavy gridlines |

| Row height | — | — | — | Minimum required for content; avoid excess whitespace |

| Number format | — | — | Right aligned | Keep decimals and units consistent |

| Text wrapping | — | — | — | Prefer 1–2 lines; avoid overly tall cells |

\#\#\# Table layout rules

\*\*Keep column hierarchy clear\*\*

\- Make the primary/most important column visually dominant.

\- Avoid giving every column equal visual weight.

\*\*Use consistent column widths\*\*

\- Give wider columns to descriptive text.

\- Give narrower columns to numbers, percentages, dates, and short labels.

\- Avoid unnecessarily wide empty columns.

\*\*Limit cell wrapping\*\*

\- Prefer 1 line where possible.

\- Allow maximum 2 lines for normal cells.

\- If content consistently exceeds 2 lines, restructure the table rather than making the

  font smaller.

\*\*Keep numbers visually scannable\*\*

\- Right-align numeric values.

\- Align decimal places within a column.

\- Use consistent units and decimal precision.

\- Example: 12.4%, 8.7%, 5.2% rather than mixed formats.

\*\*Use emphasis selectively\*\*

\- Bold only important values, totals, or key rows.

\- Avoid bolding entire tables.

\- Use one visual treatment for highlighted cells consistently.

\*\*Avoid excessive colors\*\*

\- Keep the table primarily neutral.

\- Use one accent color for emphasis.

\- Don't color every row or column differently.

\*\*Use zebra striping only when needed\*\*

\- Avoid zebra striping when rows contain labels, tags, pills, or other visual indicators.

\- Keep the table background uniform and use the tags/pills to create visual differentiation.

\- For dense data-only tables without tags, subtle zebra striping can be used if it improves

  row scanning.

\- Avoid combining zebra stripes \+ colored tags \+ highlighted rows, as it creates

  unnecessary visual noise.

\*\*Separate groups visually\*\*

\- Use spacing or subtle dividers between logical groups.

\- Avoid adding borders around every individual cell.

\*\*Maintain consistent table position\*\*

\- Align tables to the slide's main content grid.

\- Maintain consistent left/right margins across slides.

\- Avoid tables floating with arbitrary positioning.

\*\*Handle overflow at table level\*\*

\- First adjust column widths → cell padding → wrapping → overall table size.

\- Only then reduce typography within the allowed range.

\- Never allow unreadable text just to preserve the table structure.

\---

\#\# 3\. Other components

\#\#\# Card representation

\> 1 pt for line

\> no background fill, only border line \> in neutral

\*\*Priority Strategies — What to do\*\*

\- \*\*Win Traditional Grocery first:\*\* Make Traditional Grocery the lead expansion channel,

  since it is only 20.2% of 2016E gross sales \[194\], sits at about 9% national ACV \[184\],

  and has the biggest branded retail whitespace \[51\].

\- \*\*Scale Foodservice with repeatable economics:\*\* Grow Foodservice through broadline

  distributor reach, foodservice pack formats, and field sales into chains, convenience,

  and institutions, but only after proving operator pull-through and buyer labor-savings

  ROI \[193\]\[199\]\[200\]\[201\]\[202\]\[91\]\[92\]\[93\].

\- \*\*Use plant headroom before adding fixed cost:\*\* Push volume through Mira Loma, which is

  about 62% utilized with 13 lines in a 114,000 sq ft plant \[184\], before underwriting

  major capacity spend; execution depends on labor, line scheduling, and cold-chain

  throughput \[123\]\[124\].

\#\#\# Horizontal rail representation

\> 1 pt for line

\> background fill with gradient of line color

\*\*4. Acquire frozen adjacency to broaden format mix\*\*

Format hedge · Shelf-life coverage · Strategic Logic

Buy a frozen-adjacent asset to improve Del Real's weaker position in price-sensitive

institutional bids and ultra-low-cost channels. \[52\]\[53\]\[62\]\[76\]\[77\]

\*\*Screen Targets\*\*

\- Padrino Foods: adjacent frozen and authentic Mexican depth \[66\]\[67\]\[68\]\[69\]

\- Texas Tamale Company: frozen tamale platform with regional appeal \[70\]\[71\]\[72\]\[73\]\[74\]

\- Tucson Foods: frozen shelf-life and tamale adjacency \[55\]\[56\]\[57\]\[58\]\[59\]\[60\]

\#\#\# Call-out representation

\> no line

\> background fill with gradient of primary color

Del Real Foods is a U.S.-based refrigerated Hispanic and heat-and-eat foods manufacturer

headquartered in Mira Loma, California \[1\]. It sells branded meal components and full meal

solutions through retail, club, grocery, foodservice, institutional, and online channels,

with revenue recognized when products ship or are delivered \[1\].

| Value | Label |

|---|---|

| 46.74% | Value-Added Meats Rev Share |

| \>60% | Top 10 Customer Concentration |

| 500+ | Mira Loma Plant Workers |

\#\#\# Component sizing rules

\*\*Cards\*\*

\- 1–3 cards: allow larger cards, stronger typography, and more internal whitespace.

\- 4–6 cards: reduce card width and spacing while keeping content readable.

\- 7+ items: do not keep shrinking cards; switch to a more scalable layout such as a rail or

  grouped structure.

\- Card height should follow content, but cards within the same row should maintain a common

  height.

\- Short content → increase whitespace.

\- Long content → reduce padding and spacing before reducing font size.

\- Don't force equal card widths when content lengths are significantly different.

\- Each card should contain one primary data point or message.

\*\*Horizontal rail\*\*

\- 2–4 items: use larger item widths and generous spacing.

\- 5–6 items: use compact spacing and smaller item widths.

\- 7+ items: do not reduce typography below the minimum; split the rail or change the

  component.

\- Item width should respond to content length, rather than being rigidly equal.

\- Short items should not create excessive empty space just to match a long item.

\- Maintain consistent alignment across all items.

\- Preserve the order when the data represents a sequence.

\- Keep each item concise; avoid turning rail items into paragraphs.

\- If the rail becomes too tall or compressed, restructure before reducing typography.

\*\*Callouts\*\*

\- 1 callout: allow stronger visual emphasis and more whitespace.

\- 2 callouts: balance them based on content length; they don't need identical heights.

\- 3+ callouts: use only when each represents a distinct insight; otherwise combine them.

\- Short insight → larger type and more whitespace.

\- Long insight → increase available space and reduce internal spacing before reducing font

  size.

\- Keep the primary message visually dominant.

\- Don't force every callout to the same height when content differs significantly.

\- Avoid callouts becoming containers for large amounts of body text.

\- If content exceeds the readable capacity, restructure or move the overflow, rather than

  shrinking below the minimum font size.

\*\*Common rule for all three\*\*

\> Content volume determines component size, spacing, and structure. Never preserve fixed

\> dimensions at the cost of whitespace or readability. When content exceeds the component's

\> capacity, restructure or move to the next slide rather than continuously shrinking the

\> component.

\---

\#\# 4\. Edge case — dynamic slide merging rule

\- Before creating a new slide, check whether the next content can fit on the current slide.

\- If related content fits without making the slide crowded → merge it into the current slide.

\- If there is not enough space → create a new slide.

\- Never reduce text below the minimum font size just to make content fit.

\- Never merge unrelated content only to fill empty space.

\- Reflow and resize components before creating a new slide.

\*\*Simple decision rule\*\*

\`\`\`

Fit \+ Related \+ Readable                → Merge

Doesn't fit / Unrelated / Not readable  → New slide

\`\`\`

\*\*Example\*\*

\> Slide 1 has 3 cards, but there is space below them. If Slide 2 contains 2 related

\> callouts \+ pointers that fit comfortably, move them onto Slide 1 instead of creating

\> Slide 2\.

This prevents unnecessary slides, excessive whitespace, and under-filled layouts while

keeping the slide readable.

\---

\#\# 5\. Citation rules and representation

\*\*Citation representation example\*\*

\> Scale Foodservice with repeatable economics: Grow Foodservice through broadline

\> distributor reach, foodservice pack formats, and field sales into chains, convenience,

\> and institutions, but only after proving operator pull-through and buyer labor-savings

\> ROI \[199 200 201 202 91 92 93\].

\#\#\# Citation styling and usage

\- Use numbered citations \`\[n\]\` as the default citation style across the entire presentation.

\- Place the citation immediately after the claim, metric, statement, chart, or data point it

  supports.

\- Use \`\[3\]\` for a single source, \`\[3, 7\]\` for multiple non-consecutive sources, and \`\[3–7\]\`

  for consecutive sources.

\- Do not display full source names, publication titles, URLs, or long source text within

  cards, callouts, charts, tables, or other content components.

\*\*Keep citation typography visually subordinate to the content:\*\*

| Property | Value |

|---|---|

| Font | Same font family as the presentation |

| Size | 8–9 pt |

| Weight | Regular |

| Color | Secondary / muted text color |

| Line height | 1.1–1.2× |

| Case | Sentence case |

\- Do not use bold, uppercase styling, colored badges, filled pills, borders, or separate

  citation cards.

\- For key metrics, place the citation directly after the value or supporting statement:

  \`12.4% CAGR \[3\]\` · \`$42B market size \[3, 7\]\`

\- For charts and visualizations, place the citation in a small source line at the bottom of

  the visual: \`Source \[3, 5\]\`

\- For tables, use one citation at the table level when the same sources support the table.

  Use cell-level citations only when individual values come from different sources.

\- If a component has more than 3 sources, use grouped references rather than listing source

  names.

\- If a slide contains more than 6–8 sources, do not expand the slide footer with full source

  information. Use numbered citations on the slide and provide the complete source list in

  the References / Appendix.

\- Maintain a single source index across the entire deck. \`\[3\]\` must always refer to the same

  source wherever it appears.

\*\*Full source details should follow one consistent format:\*\*

\`\`\`

\[3\] Gartner, Semiconductor Forecast, 2025

\[7\] McKinsey, Global Semiconductor Outlook, 2025

\`\`\`

\- Citation space must never change the primary component layout. Do not shrink the main

  content or increase component height just to accommodate longer source text.

\- Citations should function as traceability metadata, not as a visual content element.

\---

\#\# 6\. Slide rules

\#\#\# Slide content-density rule

Each slide has a total character budget calculated as the sum of all visible content

elements on that slide. This includes titles, paragraphs, bullets, card text, callouts,

table text, labels, and other readable copy. Citations are excluded from the primary

content budget because they are metadata.

\*\*Recommended rule\*\*

\- Target: 600–900 characters per slide

\- Soft maximum: 1,000 characters

\- Hard maximum: 1,200 characters

\- Character limits are a density guardrail, not an automatic page-break trigger.

\- When the total exceeds the target, first restructure, condense, or prioritize the content.

\- Create a next slide only when important content still cannot fit clearly.

\- Never shrink typography below the defined minimum just to stay within the character limit.

\- One section should remain on one slide by default.

\- If a section genuinely requires more space, split it at a logical content boundary, not at

  an arbitrary character count.

\*\*Engineering formula\*\*

\`\`\`

Slide characters \=

    Title

  \+ subtitles/context

  \+ paragraphs

  \+ bullets

  \+ card titles

  \+ card bodies

  \+ callouts

  \+ table text

  \+ chart labels

  \+ other visible copy

Then:

  ≤ 900       → Preferred

  901–1,000   → Optimize if possible

  1,001–1,200 → Strong overflow check

  \> 1,200     → Recompose / condense / consider next slide

\`\`\`

\#\#\# Additional slide rules

\- One section \= one slide by default. Do not split unless content genuinely requires it.

\- Use any layout/component combination. No fixed card count, column count, or template

  structure.

\- Optimize before splitting: reflow → consolidate → shorten → deprioritize → split.

\- Set a minimum readable font size. Never solve overflow by continuously shrinking

  typography.

\- Control component density. Avoid too many small components competing for attention.

\- Avoid excessive whitespace. If meaningful content can naturally fit, don't push it to the

  next slide.

\- Don't force symmetry. Unequal card sizes or layouts are acceptable when driven by content

  importance.

\- Split at logical boundaries. If a second slide is needed, move a meaningful sub-topic —

  not leftover content.

\- Keep citations out of the content budget. Use \`\[n\]\` citations as lightweight metadata.

\- Prioritize information, not component count. A slide with 2 important components can be

  better than one with 6 weak components.

\- Every slide must feel complete. Avoid continuation slides containing only one small card,

  bullet, or callout.

\#\#\# The complete engine rule in one line

\> Fit one complete section within a shared slide content budget, using an adaptive layout;

\> optimize composition before pagination, and move to the next slide only when important

\> content cannot remain readable and meaningful on the current slide.

## Checksum manifest

Verifies every block above is complete and unaltered.

| File | Bytes | SHA-256 |
| :---- | :---- | :---- |
| `SKILL.md` | 17446 | `8c959707f7937787249e8c33c8f210f01bf7615ccf5e254eeb2214a7eec67180` |
| `assets/design-tokens.json` | 10865 | `d60df7dcdb508fd5bfbde4b15e3e4fe833301a662c6f255f788f72c8453fa943` |
| `assets/example_spec.json` | 3015 | `fee519be5003a840abbbe16f863ab644b04ac08f73365ac2d80be0ca07d10032` |
| `scripts/layout_engine.py` | 22489 | `6676d49013dbdfe2346a5be8ed9d39afa9f7dc12c851e097034f340fa8b230cd` |
| `scripts/pe_components.js` | 36244 | `ed0921589feeb3c83b29aa3ab35d5c607af8641308b7b0af952ff31b1df41a34` |
| `scripts/audit_deck.py` | 17845 | `29d2eb8087789eda1a656ed2df64cc02ad8b68c9d4eb158d615165d5614ff9b3` |
| `scripts/example_build.js` | 8720 | `1fb4e361da841e63f6d9df00c33af2f7208d8d29601f1f87574b64709cc7a869` |
| `references/typography.md` | 4630 | `4d2ed6dc6d52b0308c5cda493266bc4467397c2eec8b9284cfd5c96296d9082b` |
| `references/components.md` | 4743 | `6414078395a65194043900f73a9a362a901dceb1281c527cef463571166008d4` |
| `references/tables.md` | 4410 | `9562c47b35077ef422541e4e5be4daf7a4ad8bf250f4a3e6caa19a154886e24d` |
| `references/citations.md` | 4763 | `48ba94a3c1e8eb02a251e3f972cbbb4f2bca3078bb81c67217ce1101f0db7d5d` |
| `references/density-and-pagination.md` | 5503 | `30765785e579c4703a1e743a3c5abb0e02cb7f7643ab017f3835e267c18c1e9d` |
| `references/source-spec.md` | 19254 | `aaa86ad80da9728a86e8aac977a035db5b9ec359553695e1f76649855c376a65` |

## Extraction script

Run this against this bundle file to reconstruct the original folder losslessly. It parses on the `## FILE:` markers and fence lines above, so it survives the exact fence length chosen per file.

\#\!/usr/bin/env python3

"""extract\_bundle.py — reconstruct pe-deck-design/ from this bundle file.

Usage: python3 extract\_bundle.py pe-deck-design-BUNDLE.md \[output\_dir\]

"""

import re, sys, os

def main():

    bundle\_path \= sys.argv\[1\] if len(sys.argv) \> 1 else "pe-deck-design-BUNDLE.md"

    out\_dir \= sys.argv\[2\] if len(sys.argv) \> 2 else "pe-deck-design"

    text \= open(bundle\_path, "r", encoding="utf-8").read()

    pattern \= re.compile(

        r"\#\# FILE: \`(\[^\`\]+)\`\\n\\n(\`{4,})\[a-zA-Z\]\*\\n(.\*?)\\n\\2\\n",

        re.DOTALL)

    count \= 0

    for m in pattern.finditer(text):

        rel\_path, \_, content \= m.groups()

        full \= os.path.join(out\_dir, rel\_path)

        os.makedirs(os.path.dirname(full), exist\_ok=True)

        with open(full, "w", encoding="utf-8") as fh:

            fh.write(content)

        print(f"wrote {full}  ({len(content)} bytes)")

        count \+= 1

    print(f"\\n{count} files restored to {out\_dir}/")

if \_\_name\_\_ \== "\_\_main\_\_":

    main()

