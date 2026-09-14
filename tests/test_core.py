from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image

from report_pptx import FixedDeckPlanner, IntelligentDeckPlanner, ReportLoader, ReportNormalizer, SemanticValidator
from report_pptx.config import LlmConfig
from report_pptx.llm import AnthropicMessagesGateway, OpenAIResponsesGateway, RunUsageBudget, UsageLimitExceeded, create_gateway
from report_pptx.visual_review import VisualReviewer


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
        self.assertEqual(sum(slide["kind"] == "chart" for slide in deck["slides"]), 7)
        self.assertGreaterEqual(sum(slide["kind"] == "table" for slide in deck["slides"]), 4)
        self.assertEqual(sum(len(slide.get("items", [])) for slide in deck["slides"]), 6)

    def test_table_pagination_balances_last_page(self):
        class Cell:
            def __init__(self, text): self.plain_text = text
        class Column:
            key = "value"
            inferred_type = "text"
        rows = [{"value": Cell("short") } for _ in range(5)]
        pages = FixedDeckPlanner._paginate_rows(rows, [Column()], available_height=220)
        self.assertEqual([len(page_rows) for page_rows, _ in pages], [3, 2])

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
        pages = FixedDeckPlanner._paginate_paragraphs(paragraphs, available_height=360)
        self.assertEqual(len(pages), 2)
        self.assertGreaterEqual(len(pages[-1]), 2)

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


if __name__ == "__main__":
    unittest.main()
