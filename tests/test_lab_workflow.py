import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from utils.ui import TerminalUI
from lab_engine.engine import LabEngine
from scenarios.generator import ScenarioGenerator


class TestLabWorkflow(unittest.TestCase):
    def test_investigation_query_selects_requested_evidence(self):
        scenario = ScenarioGenerator.generate_scenario(difficulty="advanced")
        engine = LabEngine(scenario)
        engine.register_hypotheses(["TCP service unavailable"])

        result = engine.investigate_hypothesis(0, "Inspect TCP handshake")

        self.assertEqual(result["evidence"].category, "tcp")

    def test_dns_failure_evidence_does_not_report_success(self):
        scenario = ScenarioGenerator.generate_scenario(difficulty="beginner")
        engine = LabEngine(scenario)
        engine.register_hypotheses(["DNS resolution failure"])

        result = engine.investigate_hypothesis(0, "Inspect DNS response")

        self.assertIn("No response", result["evidence"].description)
        self.assertNotIn("NOERROR", result["evidence"].description)

    def test_conclusion_correctness_uses_root_cause(self):
        scenario = ScenarioGenerator.generate_scenario(difficulty="beginner")
        engine = LabEngine(scenario)
        engine.register_hypotheses(["DNS resolution failure", "TCP service unavailable"])

        self.assertTrue(engine.evaluate_hypothesis(0, "CONFIRM")["is_correct"])
        self.assertTrue(engine.evaluate_hypothesis(1, "REJECT")["is_correct"])

    def test_prompt_for_lab_command_accepts_start_lab(self):
        ui = TerminalUI()
        with patch("utils.ui.Prompt.ask", return_value="Start Lab"):
            self.assertTrue(ui.prompt_for_lab_command())

    def test_prompt_for_lab_command_rejects_invalid_command(self):
        ui = TerminalUI()
        with patch("utils.ui.Prompt.ask", return_value="status"):
            self.assertFalse(ui.prompt_for_lab_command())

    def test_prompt_for_hypotheses_requires_multiple_causes(self):
        ui = TerminalUI()
        with patch(
            "utils.ui.Prompt.ask",
            side_effect=["DNS failure", "DONE", "TCP failure", "DONE"],
        ):
            self.assertEqual(
                ui.prompt_for_hypotheses(),
                ["DNS failure", "TCP failure"],
            )


if __name__ == "__main__":
    unittest.main()
