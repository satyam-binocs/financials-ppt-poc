# JSON-to-PPTX

The first implementation phase converts the nested report JSON into a validated, presentation-ready intermediate representation. PPTX rendering and LLM planning are intentionally not part of this phase.

## Normalize a report

```bash
python3 -m report_pptx report.json --output build/normalized-report.json
```

## Render the LLM-planned PowerPoint deck

```bash
cp .env.sample .env
# Add OPENAI_API_KEY and PLANNING_MODEL to .env
python3 -m report_pptx report.json --output build/normalized-report.json --pptx --pptx-name financial-overview-phase3.pptx
```

Phase 3 uses structured LLM output to group narrative points, findings, and recommendations. Code validates exact content coverage, ordering, and slide capacity before rendering native editable charts and tables. Successful plans are cached under `build/llm-cache`.

Set `LLM_PROVIDER=openai` with `OPENAI_API_KEY`, or set `LLM_PROVIDER=anthropic` with `ANTHROPIC_API_KEY`. `PLANNING_MODEL` must contain a model ID supported by the selected provider. The same planning schema, validation, cache, and per-run limits apply to both providers.

Automatic deterministic fallback is implemented but disabled by default. Enable it with `ENABLE_DETERMINISTIC_FALLBACK=true`. To explicitly run the deterministic baseline without making an LLM call, pass `--planner fixed`.

Each uncached API attempt is checked against per-run request, token, and estimated-cost ceilings before it is sent. The gateway reserves `MAX_LLM_OUTPUT_TOKENS_PER_CALL`, then reconciles the ledger with the API-reported token usage. Cached responses do not consume the per-run API budget. Keep the configured per-token prices aligned with the selected planning model.

Use `--strict` to return a nonzero exit code for warnings as well as errors.

## Run tests

```bash
python3 -m unittest discover -s tests -v
```

The technical architecture and later implementation phases are described in [TECHNICAL_DESIGN.md](TECHNICAL_DESIGN.md).
