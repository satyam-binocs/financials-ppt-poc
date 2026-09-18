# Vendored: pe-deck-design (v2)

These two files are vendored **verbatim** from the `pe-deck-design` v2 skill
bundle shipped in `support/pptx sample 3.zip`:

| File | Purpose |
|---|---|
| `scripts/audit_deck.py` | Post-build OOXML compliance audit |
| `assets/design-tokens.json` | Thresholds the auditor reads (the script resolves `../assets/design-tokens.json`) |

Do not edit them. They are third-party and are kept byte-identical so they can
be re-synced when the skill updates. Our own policy — which of its rules we
enforce and which we knowingly diverge from — lives in `tools/audit_deck.py`,
not in here.

## Why only these two

The rest of the bundle targets a different rendering stack. `pe_components.js`
and `build_from_plan.js` are written against `pptxgenjs`, while this repo renders
through `@oai/artifact-tool`; `layout_engine.py` and `compose_engine.py` overlap
with `report_pptx/layout.py` and `report_pptx/composition.py`, which already
carry the same responsibilities against our own geometry.

The auditor is different: it reads the finished `.pptx` as a zip and parses
slide XML with `ElementTree`, so it is independent of whichever library produced
the file. That is what makes it reusable here unmodified.

## Provenance

The full v2 bundle, its reference docs, and its checksum manifest remain in
`support/`. Every file extracted from the v1 bundle was verified against that
manifest's SHA-256 digests before anything was vendored.
