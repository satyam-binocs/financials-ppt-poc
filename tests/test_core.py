from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from report_pptx import FixedDeckPlanner, IntelligentDeckPlanner, ReportLoader, ReportNormalizer, SemanticValidator
from report_pptx import composition, layout
from report_pptx.config import LlmConfig
from report_pptx.llm import AnthropicMessagesGateway, OpenAIResponsesGateway, RunUsageBudget, UsageLimitExceeded, create_gateway
from report_pptx.visual_review import VisualReviewer


def _exhibits(slides, kind):
    """How many exhibits of a kind the deck carries, wherever they were placed."""
    total = 0
    for slide in slides:
        if slide["kind"] == "stack":
            total += sum(block["kind"] == kind for block in slide["blocks"])
        elif kind == "chart" and slide["kind"] in {"chart", "chart_text"}:
            total += 1
        elif kind == "table" and slide["kind"] == "table":
            total += 1
    return total


class SemanticCoreTests(unittest.TestCase):
    def normalize(self, report):
        return ReportNormalizer().normalize({"is_sample_report": False, "report": report})

    def test_visibility_rules_and_recursion(self):
        model = self.normalize([
            {
                "id": "root", "display_text": "Hidden heading", "display_enabled": False,
                "is_hidden": False, "output": [{"output_format": "MarkDownSummary", "output": "Visible"}],
                "children": [
                    {"id": "gone", "is_hidden": True, "output": [{"output_format": "MarkDownSummary", "output": "Gone"}]},
                    {"id": "deep", "display_text": "Deep", "children": [{"id": "deeper", "output": []}]},
                ],
            }
        ])
        root = model.sections[0]
        self.assertFalse(root.heading_visible)
        self.assertEqual(root.blocks[0].paragraphs[0].text, "Visible")
        self.assertEqual([child.id for child in root.children], ["deep"])
        self.assertEqual(root.children[0].children[0].id, "deeper")

    def test_citations_are_scoped_and_inherited(self):
        model = self.normalize([{
            "id": "root", "citations": {"1": "https://example.test/a"},
            "children": [{
                "id": "child", "output": [{"output_format": "MarkDownSummary", "output": "Fact [1]"}]
            }],
        }])
        block = model.sections[0].children[0].blocks[0]
        self.assertEqual(block.citation_ids, ["root:1"])
        self.assertEqual(model.citations["root:1"].url, "https://example.test/a")

    def test_table_and_chart_normalization(self):
        model = self.normalize([{
            "id": "root", "output": [
                {
                    "output_format": "ReportTable",
                    "output": {
                        "columns": [{"key": "amount", "dataIndex": "amount", "title": "Amount", "headerStyle": {"align": "right"}}],
                        "dataSource": [{"amount": "$4.2M"}], "zebra": True,
                    },
                },
                {
                    "output_format": "ReportChart",
                    "output": {"options": {
                        "chart": {"type": "line"}, "xAxis": {"categories": ["A", "B"]},
                        "series": [{"name": "Range", "type": "arearange", "data": [[1, 2], [3, 4]]}],
                    }},
                },
            ],
        }])
        table, chart = model.sections[0].blocks
        self.assertEqual(table.columns[0].inferred_type, "currency")
        self.assertEqual(table.rows[0]["amount"].numeric_value, 4_200_000)
        self.assertEqual(chart.chart.kind, "range_line")
        self.assertEqual(chart.chart.series[0].points[1].high, 4)
        self.assertTrue(SemanticValidator().validate(model).is_valid)

    def test_loader_reports_invalid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "line 1, column 2"):
                ReportLoader().load(path)

    def test_real_report_normalizes(self):
        path = Path(__file__).parents[1] / "report.json"
        raw = ReportLoader().load(path)
        model = ReportNormalizer().normalize(raw)
        self.assertEqual(len(model.sections), 1)
        self.assertEqual(len(model.sections[0].children), 9)
        blocks = [block for child in model.sections[0].children for block in child.blocks]
        self.assertEqual(len(blocks), 38)
        self.assertEqual(sum(block.kind == "chart" for block in blocks), 7)

    def test_fixed_deck_plan_preserves_native_evidence(self):
        path = Path(__file__).parents[1] / "report.json"
        model = ReportNormalizer().normalize(ReportLoader().load(path))
        deck = FixedDeckPlanner().plan(model)
        self.assertEqual(deck["slides"][0]["kind"], "cover")
        # Every chart still reaches the deck. Where it lands is a composition
        # decision: its own slide, a column beside its commentary
        # (`chart_text`), or a row of a composite (`stack`), so the count is
        # taken over exhibits rather than over slide kinds.
        self.assertEqual(_exhibits(deck["slides"], "chart"), 7)
        self.assertGreaterEqual(_exhibits(deck["slides"], "table"), 4)
        self.assertEqual(sum(len(slide.get("items", [])) for slide in deck["slides"]), 6)

    def test_table_pagination_balances_last_page(self):
        class Cell:
            def __init__(self, text): self.plain_text = text
        class Column:
            key = "value"
            inferred_type = "text"
        rows = [{"value": Cell("short") } for _ in range(5)]
        pages = FixedDeckPlanner._paginate_rows(rows, [Column()], available_height=120)
        counts = [len(page_rows) for page_rows, _ in pages]
        self.assertEqual(sum(counts), 5)
        self.assertEqual(len(counts), 2, "should use the fewest pages that fit")
        self.assertLessEqual(max(counts) - min(counts), 1, "spill-over page should not be left sparse")

    def test_paragraph_pagination_fills_available_slide(self):
        paragraphs = [
            {"kind": "body", "text": "A" * 150},
            {"kind": "body", "text": "B" * 155},
            {"kind": "body", "text": "C" * 145},
        ]
        pages = FixedDeckPlanner._paginate_paragraphs(paragraphs)
        self.assertEqual([len(page) for page in pages], [3])

    def test_paragraph_pagination_balances_final_spread_by_height(self):
        paragraphs = [
            {"kind": "body", "text": letter * length}
            for letter, length in zip("ABCDE", [260, 250, 180, 170, 160])
        ]
        # Derive a budget that forces a split from the current height model, so
        # this keeps testing the balancing rather than a stale constant.
        total = sum(layout.paragraph_height(p["text"], p["kind"]) for p in paragraphs)
        pages = FixedDeckPlanner._paginate_paragraphs(paragraphs, available_height=int(total * 0.6))
        self.assertEqual(len(pages), 2)
        self.assertGreaterEqual(len(pages[-1]), 2, "spill-over page should not be a lone orphan")

    def test_llm_planner_uses_structured_grouping_and_preserves_content(self):
        class Gateway:
            def complete(self, *, task, instructions, payload, schema):
                return {"candidate_id": payload["feasible_candidates"][0]["id"], "rationale": "Best feasible candidate."}

        model = self.normalize([{
            "id": "root", "display_text": "Report", "children": [{
                "id": "section", "display_text": "Plan comparison", "output": [{
                    "output_format": "MarkDownSummary",
                    "output": "- First comparison point with supporting detail.\n- Second comparison point.\n- Third comparison point.",
                }],
            }],
        }])
        config = LlmConfig(api_key="test", planning_model="test-model")
        deck = IntelligentDeckPlanner(config, Path.cwd(), Gateway()).plan(model)
        slides = [slide for slide in deck["slides"] if slide["kind"] == "summary"]
        self.assertEqual(len(slides), 1)
        self.assertEqual(len(slides[0]["paragraphs"]), 3)
        self.assertEqual(slides[0]["density"], "comfortable")
        self.assertEqual(deck["planner"]["kind"], "llm")

    def test_candidate_plans_only_offer_minimum_slide_count(self):
        planner = IntelligentDeckPlanner(LlmConfig(), Path.cwd(), object())
        from report_pptx.planning import PlanningGroup, PlanningItem
        items = [
            PlanningItem(f"i{index}", "text", "body", {"comfortable": 100, "compact": 90, "dense": 80})
            for index in range(3)
        ]
        candidates = planner._candidate_plans(PlanningGroup("g", "summary", "Title", items, [{}]))
        self.assertEqual({len(candidate["slides"]) for candidate in candidates}, {1})

    def test_llm_can_move_related_text_beside_bar_chart(self):
        class Gateway:
            def complete(self, *, task, payload, **kwargs):
                self.task = task
                return {"candidate_id": "move_1", "rationale": "The point explains the chart."}

        gateway = Gateway()
        planner = IntelligentDeckPlanner(LlmConfig(), Path.cwd(), gateway)
        slides = planner._compose_chart_text([
            {
                "id": "s:summary:llm:1", "kind": "summary", "title": "Revenue by Product",
                "paragraphs": [{"text": "One concise chart insight.", "kind": "bullet"}],
                "planning_group_id": "s:summary", "notes": "[1] source",
            },
            {
                "id": "chart", "kind": "chart", "title": "Revenue by Product", "section": "Revenue by Product",
                "chart": {"kind": "bar"}, "notes": "[2] source",
            },
        ])
        self.assertEqual(gateway.task, "chart_text_composition")
        self.assertEqual(len(slides), 1)
        self.assertEqual(slides[0]["kind"], "chart_text")
        self.assertEqual(slides[0]["paragraphs"][0]["text"], "One concise chart insight.")

    def test_llm_failure_does_not_fall_back_when_disabled(self):
        class Gateway:
            def complete(self, **kwargs):
                raise RuntimeError("unavailable")

        model = self.normalize([{
            "id": "root", "children": [{"id": "section", "output": [{"output_format": "MarkDownSummary", "output": "Visible"}]}]
        }])
        config = LlmConfig(api_key="test", planning_model="test-model", enable_deterministic_fallback=False)
        with self.assertRaisesRegex(RuntimeError, "unavailable"):
            IntelligentDeckPlanner(config, Path.cwd(), Gateway()).plan(model)

    def test_llm_invalid_partition_is_retried_with_diagnostic(self):
        class Gateway:
            calls = 0
            def complete(self, *, payload, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    return {"candidate_id": "unknown", "rationale": "Invalid draft"}
                self.assert_revision(payload)
                return {"candidate_id": payload["feasible_candidates"][0]["id"], "rationale": "Corrected"}
            @staticmethod
            def assert_revision(payload):
                assert "unknown candidate_id" in payload["previous_validation_error"]

        model = self.normalize([{
            "id": "root", "children": [{"id": "section", "output": [{"output_format": "MarkDownSummary", "output": "- One\n- Two"}]}]
        }])
        gateway = Gateway()
        config = LlmConfig(api_key="test", planning_model="test-model", max_retries=1)
        deck = IntelligentDeckPlanner(config, Path.cwd(), gateway).plan(model)
        self.assertEqual(gateway.calls, 1 + 1)
        self.assertEqual(len([slide for slide in deck["slides"] if slide["kind"] == "summary"]), 1)

    def test_llm_failure_uses_fallback_only_when_enabled(self):
        class Gateway:
            def complete(self, **kwargs):
                raise RuntimeError("unavailable")

        model = self.normalize([{
            "id": "root", "children": [{"id": "section", "output": [{"output_format": "MarkDownSummary", "output": "Visible"}]}]
        }])
        config = LlmConfig(api_key="test", planning_model="test-model", enable_deterministic_fallback=True)
        deck = IntelligentDeckPlanner(config, Path.cwd(), Gateway()).plan(model)
        self.assertEqual(deck["planner"]["kind"], "deterministic_fallback")

    def test_llm_request_limit_is_enforced_before_next_call(self):
        config = LlmConfig(max_requests_per_run=1, max_output_tokens_per_call=10)
        budget = RunUsageBudget(config)
        budget.reserve(5)
        with self.assertRaisesRegex(UsageLimitExceeded, "request limit"):
            budget.reserve(5)

    def test_llm_token_limit_includes_reserved_output(self):
        config = LlmConfig(max_tokens_per_run=100, max_output_tokens_per_call=60)
        budget = RunUsageBudget(config)
        with self.assertRaisesRegex(UsageLimitExceeded, "token limit"):
            budget.reserve(41)

    def test_llm_cost_limit_and_usage_reconciliation(self):
        config = LlmConfig(
            max_output_tokens_per_call=100,
            max_estimated_cost_usd_per_run=0.002,
            input_cost_per_million_tokens=2,
            output_cost_per_million_tokens=12,
        )
        budget = RunUsageBudget(config)
        reservation = budget.reserve(100)
        budget.reconcile(reservation, actual_input_tokens=80, actual_output_tokens=20)
        snapshot = budget.snapshot()
        self.assertEqual(snapshot["api_requests"], 1)
        self.assertEqual(snapshot["total_tokens"], 100)
        self.assertAlmostEqual(snapshot["estimated_cost_usd"], 0.0004)

    def test_gateway_factory_switches_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            openai = create_gateway(LlmConfig(provider="openai"), Path(directory))
            anthropic = create_gateway(LlmConfig(provider="anthropic"), Path(directory))
        self.assertIsInstance(openai, OpenAIResponsesGateway)
        self.assertIsInstance(anthropic, AnthropicMessagesGateway)

    def test_anthropic_structured_text_is_parsed(self):
        response = {"content": [{"type": "text", "text": '{"slides": [], "rationale": "ok"}'}]}
        self.assertEqual(
            AnthropicMessagesGateway._output_text(response),
            '{"slides": [], "rationale": "ok"}',
        )

    def test_visual_review_enforces_scores_and_returns_group_feedback(self):
        class Gateway:
            def complete_with_images(self, *, payload, **kwargs):
                return {"reviews": [
                    {
                        "slide_id": slide["slide_id"], "accepted": True,
                        "aesthetic_score": 6 if index == 0 else 9,
                        "readability_score": 9, "balance_score": 9,
                        "issues": [{"code": "too_sparse", "severity": "warning", "description": "Excess empty space"}] if index == 0 else [],
                        "repair_feedback": "Merge related points" if index == 0 else "No repair needed",
                    }
                    for index, slide in enumerate(payload["slides_in_image_order"])
                ]}

        with tempfile.TemporaryDirectory() as directory:
            build = Path(directory)
            Image.new("RGB", (32, 18), "white").save(build / "slide-001.png")
            Image.new("RGB", (32, 18), "white").save(build / "slide-002.png")
            spec = {"slides": [
                {"id": "s1", "kind": "summary", "title": "One", "planning_group_id": "g1", "paragraphs": [{"text": "A"}]},
                {"id": "s2", "kind": "chart", "title": "Two"},
            ]}
            review = VisualReviewer(LlmConfig(visual_review_batch_size=2), Gateway()).review(spec, build)
        self.assertFalse(review.accepted)
        self.assertFalse(review.hard_failures)
        self.assertIn("g1", review.group_feedback)
        self.assertIn("Excess empty space", review.group_feedback["g1"])


class CompositionTests(unittest.TestCase):
    @staticmethod
    def _card(body_length: int, title: str = "Card") -> dict:
        return {
            "id": f"c{body_length}", "title": title, "badges": ["Tag"],
            "paragraphs": [{"text": "x" * body_length, "kind": "body"}],
        }

    def test_compact_cards_use_columns_and_detailed_cards_do_not(self):
        compact = [self._card(60, f"C{index}") for index in range(3)]
        layout_id, columns, _, reasons = composition.select_card_layout(compact, layout.CONTENT_TOP)
        self.assertEqual(layout_id, "L05_THREE_COLUMN")
        self.assertEqual(columns, 3)

        detailed = [self._card(700, f"D{index}") for index in range(3)]
        layout_id, columns, _, reasons = composition.select_card_layout(detailed, layout.CONTENT_TOP)
        self.assertNotEqual(columns, 3, "detailed cards must not go in three narrow columns")
        self.assertTrue(any("narrow columns" in reason for reason in reasons))

    def test_card_pagination_is_even_and_never_orphans(self):
        cards = [self._card(700, f"D{index}") for index in range(6)]
        pages = composition.plan_card_pages(cards, layout.CONTENT_TOP)
        sizes = [len(page[0]) for page in pages]
        self.assertEqual(sum(sizes), 6)
        self.assertGreater(len(pages), 1, "six detailed cards cannot share one slide")
        self.assertLessEqual(max(sizes) - min(sizes), 1, "pages should be evenly filled")
        self.assertNotIn(1, sizes, "a lone card must not be stranded on its own slide")

    def test_every_planned_card_grid_fits_its_band(self):
        for name in ("report-2.json", "report.json"):
            model = ReportNormalizer().normalize(ReportLoader().load(Path(__file__).parents[1] / name))
            for slide in FixedDeckPlanner().plan(model)["slides"]:
                if slide["kind"] not in {"cards", "chart_grid"}:
                    continue
                boxes = slide.get("card_boxes") or slide.get("chart_boxes") or []
                for box in boxes:
                    self.assertLessEqual(
                        box["top"] + box["height"], layout.CONTENT_BOTTOM,
                        f"{slide['id']} places a component past the content band",
                    )

    def test_table_columns_never_fall_below_the_minimum_width(self):
        """The water-filling loop used to re-share columns it had just pinned."""
        class Column:
            def __init__(self, key, title):
                self.key, self.title, self.inferred_type = key, title, "text"

        columns = [Column("a", "Region"), Column("b", "Key Markets"), Column("c", "Presence"), Column("d", "Strategic Role")]
        rows = [{
            "a": {"plain_text": "Illinois"},
            "b": {"plain_text": "Waukegan and the northern suburbs"},
            "c": {"plain_text": "Yes"},
            "d": {"plain_text": "x" * 600},
        }]

        class Cell:
            def __init__(self, text): self.plain_text = text
        typed = [{key: Cell(value["plain_text"]) for key, value in rows[0].items()}]
        widths = layout.column_weights(columns, typed)
        self.assertAlmostEqual(sum(widths), layout.CONTENT_WIDTH, delta=2)
        self.assertGreaterEqual(
            min(widths), layout.TABLE_COLUMN_MIN_WIDTH - 1,
            "no column may be narrower than the readable minimum",
        )

    def test_chart_commentary_goes_beside_the_chart_only_when_it_earns_a_column(self):
        short = [{"text": "One short lead line.", "kind": "lead"}]
        self.assertFalse(
            layout.fits_chart_text_column(short),
            "a one-line lead would leave the column all but empty",
        )
        substantial = [{"text": "x" * 420, "kind": "body"} for _ in range(3)]
        self.assertTrue(layout.fits_chart_text_column(substantial))
        # And the chart it sits next to keeps a workable width.
        geometry = layout.chart_text_geometry()
        self.assertGreaterEqual(
            geometry["chart_width"], layout.MIN_COMPONENT_DIMENSIONS["chart"]["min_width"]
        )
        # The narrow column is the point: it reads far shorter than full width.
        self.assertLess(
            layout.chars_per_line(13, layout.CHART_TEXT_WIDTH),
            layout.chars_per_line(13, layout.PROSE_TEXT_WIDTH) // 2,
        )

    def test_overlay_fit_is_measured_not_assumed_from_chart_kind(self):
        """Whether callouts survive a narrower plot depends on the labels."""
        def scenario(categories, name):
            return {
                "kind": "range_line",
                "categories": [f"Y{index}" for index in range(categories)],
                "series": [{
                    "name": name, "role": "value",
                    "points": [{"value": 350.3} for _ in range(categories)],
                }],
            }

        narrow = {
            "left": layout.chart_text_geometry()["chart_left"],
            "width": layout.chart_text_geometry()["chart_width"],
        }
        full = {"left": layout.CHART_LEFT, "width": layout.CHART_WIDTH}

        # Four short-labelled categories fit even the half-width plot.
        self.assertTrue(layout.chart_overlays_fit(scenario(4, "Base case"), narrow))
        # Crowding the same plot with categories eventually does not fit.
        self.assertFalse(layout.chart_overlays_fit(scenario(14, "Base case"), narrow))
        # A chart with no overlay labels is never constrained by them.
        self.assertTrue(layout.chart_overlays_fit({"kind": "line", "categories": [], "series": []}, narrow))
        # Full width tolerates more categories than the narrow column.
        crowded = scenario(10, "Management plan")
        self.assertTrue(layout.chart_overlays_fit(crowded, full))
        self.assertFalse(layout.chart_overlays_fit(crowded, narrow))

    def test_overlay_label_width_follows_its_text(self):
        short = layout.overlay_label_width("Up $1.0M")
        long = layout.overlay_label_width("Management plan $1,234.5M")
        self.assertLess(short, long)
        # The old fixed 126-unit box was roughly double what a callout needs.
        self.assertLess(short, 126)

    def test_reduced_first_page_still_balances_the_remainder(self):
        """A smaller opening page must not be filled at the remainder's expense."""
        heights = [106, 106, 87, 87, 106]
        uniform = [len(page) for page in layout.balanced_pages(heights, 480)]
        reduced = [len(page) for page in layout.balanced_pages(heights, 480, first_capacity=421)]
        self.assertEqual(sum(reduced), len(heights))
        self.assertEqual(len(reduced), len(uniform), "the smaller first page should not add a page")
        self.assertNotIn(1, reduced, "filling page one to the brim strands a single row")

    def test_no_planned_slide_strands_a_single_item(self):
        model = ReportNormalizer().normalize(ReportLoader().load(Path(__file__).parents[1] / "report-2.json"))
        summary = FixedDeckPlanner().plan(model)["composition_summary"]
        self.assertNotIn("orphan_continuation", summary["balance_flags"])

    def test_function_words_are_lowered_but_names_are_not(self):
        from report_pptx.render import sentence_case
        self.assertEqual(sentence_case("Investment Thesis And Overview"), "Investment Thesis and Overview")
        self.assertEqual(sentence_case("Margin & Earnings Quality"), "Margin & Earnings Quality")
        self.assertEqual(sentence_case("Revenue By Segment For 2026"), "Revenue by Segment for 2026")
        # Never the first word, and never an acronym or a proper noun.
        self.assertEqual(sentence_case("The Market Overview"), "The Market Overview")
        self.assertEqual(sentence_case("EBITDA And KPC Detail"), "EBITDA and KPC Detail")
        self.assertEqual(sentence_case("American Place Casino"), "American Place Casino")
        self.assertIsNone(sentence_case(None))

    def test_eyebrow_caps_ceiling_matches_the_design_tokens(self):
        """The OOXML auditor fails ALL CAPS runs past this length."""
        tokens = json.loads(
            (Path(__file__).parents[1] / "tools" / "pe-deck-design" / "assets" / "design-tokens.json").read_text()
        )
        self.assertEqual(layout.EYEBROW_MAX_CAPS_CHARS, tokens["type"]["case"]["allcaps_max_chars"])

    def test_planned_decks_report_no_composition_violations(self):
        for name in ("report-2.json", "report.json"):
            model = ReportNormalizer().normalize(ReportLoader().load(Path(__file__).parents[1] / name))
            summary = FixedDeckPlanner().plan(model)["composition_summary"]
            self.assertEqual(summary["violations"], {}, f"{name} planned with layout violations")

    def test_card_and_chart_grid_formats_are_no_longer_dropped(self):
        model = ReportNormalizer().normalize(ReportLoader().load(Path(__file__).parents[1] / "report-2.json"))
        kinds = [block.kind for section in FixedDeckPlanner._sections(model.sections) for block in section.blocks]
        self.assertIn("cards", kinds)
        self.assertIn("chart_grid", kinds)
        unsupported = [
            item for item in model.diagnostics
            if item.code == "unknown_output_format"
        ]
        self.assertEqual(unsupported, [], "every output format in the corpus should normalize")


if __name__ == "__main__":
    unittest.main()


# Commentary long enough to earn a column of its own beside a chart.
_LONG_COMMENTARY = "Commentary about the projection. " * 20


def _compose(slides):
    """Compose and annotate, the way a planner does."""
    return composition.annotate(composition.compose(slides))


class CompositeSlideTests(unittest.TestCase):
    """The composer folds adjacent exhibits onto one slide, by measurement."""

    @staticmethod
    def _prose(text: str, slide_id: str = "s:summary:1", group: str = "g") -> dict:
        return {
            "id": slide_id, "kind": "summary", "title": "Prose",
            "paragraphs": [{"text": text, "kind": "body"}], "section_group": group,
        }

    @staticmethod
    def _table(rows: int, slide_id: str = "t:table:1", group: str = "g") -> dict:
        columns = [
            {"key": "name", "title": "Name", "layout_weight": 0.6, "align": "left"},
            {"key": "value", "title": "Value", "layout_weight": 0.4, "align": "right"},
        ]
        return {
            "id": slide_id, "kind": "table", "title": "Table",
            "columns": columns,
            "rows": [{"name": {"plain_text": f"Row {i}"}, "value": {"plain_text": "1.0"}} for i in range(rows)],
            "row_heights": [layout.TABLE_ROW_MIN] * rows,
            "header_height": layout.TABLE_HEADER_MIN, "section_group": group,
        }

    @staticmethod
    def _chart(slide_id: str = "c:chart", group: str = "g", kind: str = "bar") -> dict:
        return {
            "id": slide_id, "kind": "chart", "title": "Chart", "section": "Section",
            "chart": {
                "kind": kind, "title": "Chart",
                "categories": ["2026", "2027"],
                "series": [{"name": "Revenue", "points": [
                    {"category": "2026", "value": 1.0}, {"category": "2027", "value": 2.0},
                ]}],
            },
            "section_group": group,
        }

    def test_chart_commentary_and_table_share_one_slide(self):
        composed = _compose([
            self._prose("Commentary. " * 24), self._chart(), self._table(4),
        ])
        self.assertEqual(len(composed), 1)
        slide = composed[0]
        self.assertEqual(slide["kind"], "stack")
        self.assertEqual([block["kind"] for block in slide["blocks"]], ["prose", "chart", "table"])
        self.assertEqual(slide["composition"]["violations"], [])
        # Nothing may end below the content band.
        for block in slide["blocks"]:
            box = block["box"]
            self.assertLessEqual(box["top"] + box["height"], layout.CONTENT_BOTTOM)

    def test_a_combination_that_does_not_fit_is_left_alone(self):
        # A table deep enough to fill the band on its own cannot take a lodger.
        rows = (layout.CONTENT_BOTTOM - layout.CONTENT_TOP) // layout.TABLE_ROW_MIN
        composed = _compose([self._prose("Commentary. " * 24), self._table(rows)])
        self.assertEqual([slide["kind"] for slide in composed], ["summary", "table"])

    def test_exhibits_from_different_sections_never_merge(self):
        composed = _compose([
            self._chart(group="one"), self._table(3, group="two"),
        ])
        self.assertEqual([slide["kind"] for slide in composed], ["chart", "table"])

    def test_continuation_pages_are_not_re_parented(self):
        continuation = self._table(3, slide_id="t:table:2")
        continuation["title"] = "Table continued"
        composed = _compose([self._chart(), continuation])
        self.assertEqual([slide["kind"] for slide in composed], ["chart", "table"])

    def test_substantial_commentary_takes_a_column_beside_the_chart(self):
        composed = _compose([self._prose(_LONG_COMMENTARY), self._chart()])
        blocks = composed[0]["blocks"]
        prose, chart = blocks[0], blocks[1]
        self.assertEqual(prose["box"]["top"], chart["box"]["top"], "should share a row")
        self.assertLess(prose["box"]["width"], chart["box"]["width"])

    def test_a_one_line_lead_is_stacked_rather_than_stranded_in_a_column(self):
        composed = _compose([self._prose("Short lead."), self._chart(), self._table(4)])
        blocks = composed[0]["blocks"]
        prose, chart = blocks[0], blocks[1]
        self.assertEqual(prose["box"]["width"], layout.CONTENT_WIDTH)
        self.assertGreater(chart["box"]["top"], prose["box"]["top"], "should be its own row")

    def test_surplus_height_goes_to_the_chart_not_to_the_prose(self):
        composed = _compose([self._prose(_LONG_COMMENTARY), self._chart()])
        prose, chart = composed[0]["blocks"]
        natural = layout.prose_block_height(
            [{"text": _LONG_COMMENTARY, "kind": "body"}],
            width=layout.prose_text_width(prose["box"]["width"]),
        )
        self.assertEqual(prose["box"]["height"], natural)
        self.assertGreater(chart["box"]["height"], layout.MIN_COMPONENT_DIMENSIONS["chart"]["min_height"])

    def test_every_exhibit_survives_composition(self):
        source = [self._prose("Commentary. " * 24), self._chart(), self._table(4)]
        composed = composition.compose(source)
        blocks = [block["kind"] for slide in composed for block in slide.get("blocks", [])]
        self.assertEqual(blocks.count("chart"), 1)
        self.assertEqual(blocks.count("table"), 1)
        self.assertEqual(blocks.count("prose"), 1)

    def test_a_composite_is_measured_across_all_of_its_blocks(self):
        composed = _compose([
            self._prose("Commentary. " * 24), self._chart(), self._table(4),
        ])
        density = composed[0]["composition"]["density"]
        self.assertEqual(density["chart_count"], 1)
        self.assertEqual(density["table_row_count"], 4)
        self.assertGreater(density["visible_character_count"], 250)
        self.assertGreaterEqual(density["vertical_occupancy"], 0.5)

    def test_an_absorbed_exhibit_keeps_its_own_title_as_a_label(self):
        composed = _compose([self._table(4), self._table(3, slide_id="t2:table:1")])
        self.assertEqual(len(composed), 1)
        first, second = composed[0]["blocks"]
        self.assertIsNone(first.get("label"), "the slide title already names the first")
        # Same title on both, so there is nothing to disambiguate.
        self.assertIsNone(second.get("label"))

        other = self._table(3, slide_id="t2:table:1")
        other["title"] = "Appendix detail"
        composed = _compose([self._table(4), other])
        labelled = composed[0]["blocks"][1]
        self.assertEqual(labelled["label"], "Appendix detail")
        # The label lives inside the block's box, so its height was reserved.
        self.assertEqual(
            labelled["box"]["height"],
            layout.STACK_LABEL_HEIGHT + labelled["header_height"] + sum(labelled["row_heights"]),
        )
        self.assertEqual(composed[0]["composition"]["violations"], [])
