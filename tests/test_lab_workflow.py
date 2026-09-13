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
        scenario = self._generate_until("beginner", "Host Cannot Connect to Application Server")
        engine = LabEngine(scenario)
        engine.register_hypotheses(["DNS resolution failure"])

        result = engine.investigate_hypothesis(0, "Inspect DNS response")

        self.assertIn("No response", result["evidence"].description)
        self.assertNotIn("NOERROR", result["evidence"].description)

    def test_conclusion_correctness_uses_root_cause(self):
        scenario = self._generate_until("beginner", "Host Cannot Connect to Application Server")
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


    # --- Scoring rubric ---------------------------------------------------

    def _submit(self, engine, **overrides):
        diagnosis = {
            "root_cause": "DNS failure - server hostname not resolving",
            "evidence": "DNS queries to the resolver receive no response.",
            "fault_domain": "Layer 3/4 - DNS",
            "impact": "Users cannot reach the application.",
            "remediation": "Restore the DNS service.",
            "confidence": "High",
        }
        diagnosis.update(overrides)
        return engine.submit_final_diagnosis(
            diagnosis["root_cause"],
            diagnosis["evidence"],
            diagnosis["fault_domain"],
            diagnosis["impact"],
            diagnosis["remediation"],
            diagnosis["confidence"],
        )

    def test_single_word_root_cause_answer_does_not_earn_full_credit(self):
        scenario = self._generate_until("beginner", "Host Cannot Connect to Application Server")
        engine = LabEngine(scenario)

        result = self._submit(engine, root_cause="dns")

        self.assertLess(result["score"].root_cause, 20)

    def test_paraphrased_root_cause_answer_earns_credit(self):
        scenario = self._generate_until("beginner", "Host Cannot Connect to Application Server")
        engine = LabEngine(scenario)

        result = self._submit(
            engine, root_cause="The DNS service on the resolver is not responding"
        )

        self.assertGreaterEqual(result["score"].root_cause, 15)

    def test_fault_domain_partial_credit(self):
        scenario = self._generate_until("beginner", "Host Cannot Connect to Application Server")
        engine = LabEngine(scenario)

        result = self._submit(engine, fault_domain="DNS problem")
        self.assertEqual(result["score"].problem_understanding, 15)

        result = self._submit(engine, fault_domain="Layer 3")
        self.assertEqual(result["score"].problem_understanding, 10)

    def test_hypothesis_quality_requires_plausible_hypotheses(self):
        scenario = self._generate_until("beginner", "Host Cannot Connect to Application Server")

        good_engine = LabEngine(scenario)
        good_engine.register_hypotheses(
            [
                "DNS resolution failure",
                "Network connectivity problem",
                "TCP service unavailable",
                "Firewall blocking traffic",
                "Application server failure",
            ]
        )
        junk_engine = LabEngine(scenario)
        junk_engine.register_hypotheses(
            [
                "Solar flares",
                "Cosmic ray hit the CPU",
                "The mouse is unplugged",
                "Aliens",
                "Full moon",
            ]
        )

        good = self._submit(good_engine)
        junk = self._submit(junk_engine)

        self.assertGreater(
            good["score"].hypothesis_quality, junk["score"].hypothesis_quality
        )

    def test_prioritization_rewards_ranking_root_cause_first(self):
        scenario = self._generate_until("beginner", "Host Cannot Connect to Application Server")

        ordered_engine = LabEngine(scenario)
        ordered_engine.register_hypotheses(
            ["DNS resolution failure", "TCP service unavailable"]
        )
        result = self._submit(ordered_engine)
        self.assertEqual(result["score"].prioritization, 15)

        reversed_engine = LabEngine(scenario)
        reversed_engine.register_hypotheses(
            ["TCP service unavailable", "DNS resolution failure"]
        )
        result = self._submit(reversed_engine)
        self.assertEqual(result["score"].prioritization, 12)

    def test_inconclusive_conclusions_are_not_counted_as_wrong(self):
        scenario = self._generate_until("beginner", "Host Cannot Connect to Application Server")
        engine = LabEngine(scenario)
        engine.register_hypotheses(
            ["DNS resolution failure", "TCP service unavailable"]
        )

        engine.evaluate_hypothesis(0, "INCONCLUSIVE")
        engine.evaluate_hypothesis(1, "REJECT")

        result = self._submit(engine)
        self.assertEqual(result["score"].evidence_interpretation, 25)

    # --- Evidence category reachability ------------------------------------

    def _generate_until(self, difficulty, title):
        for _ in range(60):
            scenario = ScenarioGenerator.generate_scenario(difficulty=difficulty)
            if scenario.title == title:
                return scenario
        self.fail(f"Could not generate scenario: {title}")

    def test_http_query_reaches_http_evidence_in_queue_scenario(self):
        scenario = self._generate_until("advanced", "Server Responds but App Fails")
        engine = LabEngine(scenario)
        engine.register_hypotheses(["Application queue overflow"])

        result = engine.investigate_hypothesis(0, "Inspect HTTP requests")

        self.assertEqual(result["evidence"].category, "http")
        self.assertIn("HTTP GET", result["evidence"].description)

    def test_http_query_falls_back_to_application_evidence(self):
        scenario = self._generate_until("beginner", "Host Cannot Connect to Application Server")
        engine = LabEngine(scenario)
        engine.register_hypotheses(["DNS resolution failure"])

        result = engine.investigate_hypothesis(0, "Inspect HTTP traffic")

        self.assertEqual(result["evidence"].category, "http")
        self.assertIn(
            "No HTTP request leaves the client", result["evidence"].description
        )


    # --- Difficulty selection ---------------------------------------------

    def test_expert_difficulty_returns_expert_scenario(self):
        scenario = ScenarioGenerator.generate_scenario(difficulty="expert")

        self.assertEqual(scenario.difficulty, "expert")

    def test_unknown_difficulty_fails_fast(self):
        with self.assertRaises(ValueError):
            ScenarioGenerator.generate_scenario(difficulty="hard")

    # --- Scenario-aware hints ----------------------------------------------

    def test_hints_are_scenario_aware(self):
        scenario = self._generate_until("beginner", "Host Cannot Connect to Application Server")
        engine = LabEngine(scenario)

        hint = engine.get_hint(4)

        self.assertIn("rcode", hint.lower())

    def test_hints_fall_back_when_scenario_has_none(self):
        scenario = self._generate_until("beginner", "Host Cannot Connect to Application Server")
        scenario.hints = []
        engine = LabEngine(scenario)

        hint = engine.get_hint(1)

        self.assertIn("order of operations", hint)

    def test_hints_render_scenario_placeholders(self):
        scenario = self._generate_until("beginner", "Host Cannot Connect to Application Server")
        engine = LabEngine(scenario)

        for level in (1, 2, 3, 4):
            hint = engine.get_hint(level)
            self.assertNotIn("{", hint)

        self.assertIn(scenario.servers[0]["name"], engine.get_hint(1))

    def test_expert_hints_point_at_pmtud(self):
        scenario = ScenarioGenerator.generate_scenario(difficulty="expert")
        engine = LabEngine(scenario)

        hint = engine.get_hint(4)

        self.assertIn("icmp", hint.lower())

    # --- Skipped hypotheses ---------------------------------------------

    def test_skip_records_skipped_status(self):
        scenario = self._generate_until("beginner", "Host Cannot Connect to Application Server")
        engine = LabEngine(scenario)
        engine.register_hypotheses(["DNS resolution failure", "TCP service unavailable"])
        engine.investigate_hypothesis(0, "Inspect DNS response")

        result = engine.skip_hypothesis(0)

        self.assertEqual(result["recorded_status"], "SKIPPED")

    def test_skip_does_not_overwrite_conclusion(self):
        scenario = self._generate_until("beginner", "Host Cannot Connect to Application Server")
        engine = LabEngine(scenario)
        engine.register_hypotheses(["DNS resolution failure", "TCP service unavailable"])
        engine.evaluate_hypothesis(0, "CONFIRM")

        result = engine.skip_hypothesis(0)

        self.assertEqual(result["recorded_status"], "CONFIRMED")

    def test_skip_missing_hypothesis_returns_error(self):
        scenario = self._generate_until("beginner", "Host Cannot Connect to Application Server")
        engine = LabEngine(scenario)
        engine.register_hypotheses(["DNS resolution failure"])

        result = engine.skip_hypothesis(99)

        self.assertIn("error", result)

    # --- Prioritization input validation ----------------------------------

    def test_prioritization_rejects_duplicate_priorities(self):
        ui = TerminalUI()
        with patch("utils.ui.IntPrompt.ask", side_effect=[1, 1, 2]), patch(
            "utils.ui.Prompt.ask", return_value="reason"
        ):
            result = ui.prompt_for_prioritization(2)

        self.assertEqual(result["priorities"], [1, 2])

    # --- Scenario bank breadth ---------------------------------------------

    def test_scenario_bank_covers_all_archetypes(self):
        templates = ScenarioGenerator.SCENARIO_TEMPLATES
        self.assertGreaterEqual(len(templates), 12)
        remaining = {t["title"] for t in templates}
        for _ in range(2000):
            scenario = ScenarioGenerator.generate_scenario()
            remaining.discard(scenario.title)
            self.assertNotIn("{", scenario.root_cause)
            self.assertNotIn("{", scenario.remediation)
            self.assertNotIn("{", scenario.failure_chain)
            for keyword in scenario.fault_keywords:
                self.assertNotIn("{", keyword)
            for hint in scenario.hints:
                self.assertNotIn("{", hint)
            for evidence in scenario.evidence_list:
                self.assertNotIn("{", evidence.description)
            if not remaining:
                break
        self.assertFalse(remaining)

    def test_difficulty_pools_only_contain_matching_templates(self):
        for difficulty in ("beginner", "intermediate", "advanced", "expert"):
            for _ in range(30):
                scenario = ScenarioGenerator.generate_scenario(difficulty=difficulty)
                self.assertEqual(scenario.difficulty, difficulty)

    def test_routing_scenario_traceroute_evidence(self):
        scenario = self._generate_until("beginner", "Branch Office Cannot Reach the Application Subnet")
        engine = LabEngine(scenario)
        engine.register_hypotheses(["Missing return route to the branch subnet"])

        result = engine.investigate_hypothesis(0, "Run a traceroute to the server")

        self.assertEqual(result["evidence"].category, "icmp")
        self.assertIn("Traceroute", result["evidence"].description)

    def test_tls_scenario_reveals_certificate_expiry(self):
        scenario = self._generate_until("advanced", "TCP Handshake Succeeds but HTTPS Fails")
        engine = LabEngine(scenario)
        engine.register_hypotheses(["Expired server certificate"])

        result = engine.investigate_hypothesis(0, "Inspect the TLS handshake")

        self.assertEqual(result["evidence"].category, "tls")
        self.assertIn("Certificate Expired", result["evidence"].description)

    def test_duplex_scenario_collision_evidence(self):
        scenario = self._generate_until("intermediate", "Application Stalls Only During Large Transfers")
        engine = LabEngine(scenario)
        engine.register_hypotheses(["Duplex mismatch on the switch port"])

        result = engine.investigate_hypothesis(0, "Check for late collisions on the link")

        self.assertEqual(result["evidence"].category, "l2")
        self.assertIn("late collisions", result["evidence"].description)

    def test_load_balancer_scenario_pool_evidence(self):
        scenario = self._generate_until("advanced", "Application Fails for Some Users but Not Others")
        engine = LabEngine(scenario)
        engine.register_hypotheses(["Load balancer serving a dead pool member"])

        result = engine.investigate_hypothesis(0, "Check the load balancer pool health")

        self.assertEqual(result["evidence"].category, "logs")
        self.assertIn("probes tcp/80", result["evidence"].description)

    def test_bufferbloat_scenario_latency_evidence(self):
        scenario = self._generate_until("advanced", "Application Turns Unusable Every Evening")
        engine = LabEngine(scenario)
        engine.register_hypotheses(["Backup saturating the WAN link"])

        result = engine.investigate_hypothesis(0, "Check uplink utilization")

        self.assertEqual(result["evidence"].category, "performance")
        self.assertIn("600-900ms", result["evidence"].description)

    def test_arp_conflict_scenario_mac_evidence(self):
        scenario = self._generate_until("intermediate", "Connections to the Server Fail in Waves")
        engine = LabEngine(scenario)
        engine.register_hypotheses(["Duplicate IP conflict"])

        result = engine.investigate_hypothesis(0, "Inspect ARP traffic")

        self.assertEqual(result["evidence"].category, "l2")
        self.assertIn("flaps between", result["evidence"].description)


if __name__ == "__main__":
    unittest.main()
