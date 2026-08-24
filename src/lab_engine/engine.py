"""Lab engine - core investigation logic."""
from typing import List, Dict, Any, Optional
from datetime import datetime
from lab_engine.models import (
    Hypothesis,
    HypothesisStatus,
    Evidence,
    IncidentScenario,
    InvestigationSession,
    LabScore,
)


class LabEngine:
    """Main lab engine for managing investigations."""

    def __init__(self, scenario: IncidentScenario):
        """Initialize the lab engine with a scenario.

        Args:
            scenario: The IncidentScenario to investigate
        """
        self.session = InvestigationSession(scenario=scenario)
        self.ground_truth = self._build_ground_truth()

    def _build_ground_truth(self) -> Dict[str, Any]:
        """Build the ground truth model (hidden from learner).

        Returns:
            Dictionary containing root cause, fault domain, evidence patterns, etc.
        """
        return {
            "root_cause": self.session.scenario.root_cause,
            "fault_domain": self.session.scenario.fault_domain,
            "evidence_patterns": {},
            "valid_hypotheses": self.session.scenario.expected_hypotheses,
            "remediation": self.session.scenario.remediation,
        }

    def register_hypotheses(self, hypotheses: List[str]) -> None:
        """Register the learner's hypotheses.

        Args:
            hypotheses: List of hypothesis strings
        """
        self.session.hypotheses = [
            Hypothesis(
                id=i,
                priority=i + 1,
                hypothesis=h,
                status=HypothesisStatus.NOT_TESTED,
            )
            for i, h in enumerate(hypotheses)
        ]

    def prioritize_hypotheses(
        self,
        priorities: List[int],
        reasons: List[str],
        expected_evidence: List[str],
        falsifying_evidence: List[str],
        investigation_methods: List[str],
    ) -> None:
        """Update hypothesis priorities and investigation details.

        Args:
            priorities: Priority order (1-indexed)
            reasons: Reason for each priority
            expected_evidence: Expected evidence if true
            falsifying_evidence: Evidence that would falsify
            investigation_methods: Methods to investigate
        """
        for i, priority in enumerate(priorities):
            if i < len(self.session.hypotheses):
                hyp = self.session.hypotheses[i]
                hyp.priority = priority
                hyp.reason_for_priority = reasons[i]
                hyp.expected_evidence = expected_evidence[i]
                hyp.falsifying_evidence = falsifying_evidence[i]
                hyp.investigation_method = investigation_methods[i]

    def investigate_hypothesis(self, hypothesis_id: int, investigation_query: str) -> Dict[str, Any]:
        """Conduct investigation on a specific hypothesis.

        Args:
            hypothesis_id: ID of hypothesis to investigate
            investigation_query: What the learner wants to investigate

        Returns:
            Evidence and analysis results
        """
        hyp = self._get_hypothesis(hypothesis_id)
        if not hyp:
            return {"error": "Hypothesis not found"}

        hyp.status = HypothesisStatus.UNDER_INVESTIGATION

        # Generate evidence based on investigation query and root cause
        evidence = self._generate_evidence(hyp, investigation_query)

        # Store in session
        self.session.gathered_evidence.append(evidence)
        hyp.evidence.append(evidence.description)

        # Record in history
        self.session.investigation_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "hypothesis_id": hypothesis_id,
                "query": investigation_query,
                "evidence": evidence.description,
            }
        )

        return {
            "evidence": evidence,
            "analysis": self._analyze_evidence(hyp, evidence),
        }

    def evaluate_hypothesis(
        self, hypothesis_id: int, conclusion: str
    ) -> Dict[str, Any]:
        """Evaluate learner's conclusion about a hypothesis.

        Args:
            hypothesis_id: ID of hypothesis
            conclusion: "CONFIRM", "REJECT", or "INCONCLUSIVE"

        Returns:
            Feedback on the conclusion
        """
        hyp = self._get_hypothesis(hypothesis_id)
        if not hyp:
            return {"error": "Hypothesis not found"}

        # Map conclusion to status
        status_map = {
            "CONFIRM": HypothesisStatus.CONFIRMED,
            "REJECT": HypothesisStatus.REJECTED,
            "INCONCLUSIVE": HypothesisStatus.INCONCLUSIVE,
        }

        hyp.status = status_map.get(conclusion, HypothesisStatus.INCONCLUSIVE)

        # Check if conclusion is correct
        is_correct = self._check_conclusion_correctness(hyp, conclusion)

        return {
            "hypothesis_id": hypothesis_id,
            "recorded_status": hyp.status,
            "is_correct": is_correct,
            "feedback": self._generate_conclusion_feedback(hyp, is_correct),
        }

    def get_investigation_status(self) -> Dict[str, Any]:
        """Get current investigation status table.

        Returns:
            Dictionary with hypothesis statuses and evidence
        """
        hypotheses_status = []
        for hyp in self.session.hypotheses:
            hypotheses_status.append(
                {
                    "priority": hyp.priority,
                    "hypothesis": hyp.hypothesis,
                    "status": hyp.status.value,
                    "evidence": hyp.evidence,
                }
            )

        return {
            "hypotheses": hypotheses_status,
            "gathered_evidence": [
                {
                    "id": e.id,
                    "category": e.category,
                    "description": e.description,
                }
                for e in self.session.gathered_evidence
            ],
        }

    def submit_final_diagnosis(
        self, root_cause: str, evidence: str, fault_domain: str, impact: str, remediation: str, confidence: str
    ) -> Dict[str, Any]:
        """Submit final diagnosis for evaluation.

        Args:
            root_cause: Identified root cause
            evidence: Supporting evidence
            fault_domain: Layer/component responsible
            impact: What the fault caused
            remediation: Fix recommendation
            confidence: Low/Medium/High

        Returns:
            Evaluation of final diagnosis
        """
        self.session.final_diagnosis = root_cause
        self.session.final_confidence = confidence

        # Score the diagnosis
        score = self._score_final_diagnosis(
            root_cause, evidence, fault_domain, impact, remediation, confidence
        )

        return {
            "score": score,
            "feedback": self._generate_rca_feedback(score),
            "official_root_cause": self.ground_truth["root_cause"],
            "official_fault_domain": self.ground_truth["fault_domain"],
        }

    def get_hint(self, level: int) -> str:
        """Provide progressive hints based on difficulty level.

        Args:
            level: Hint level (1-4)

        Returns:
            Hint message
        """
        hints = {
            1: "Consider the order of operations needed for this connection to succeed. What must happen first?",
            2: "Think about examining the connection establishment phase and initial packets.",
            3: "Try filtering for the relevant protocol in Wireshark or checking packet sequences.",
            4: "Focus on the TCP handshake or protocol-specific transactions.",
        }
        return hints.get(level, "No more hints available. Consider consulting the documentation.")

    # Private helper methods

    def _get_hypothesis(self, hypothesis_id: int) -> Optional[Hypothesis]:
        """Get hypothesis by ID."""
        for hyp in self.session.hypotheses:
            if hyp.id == hypothesis_id:
                return hyp
        return None

    def _generate_evidence(self, hyp: Hypothesis, query: str) -> Evidence:
        """Generate realistic evidence based on investigation query.

        This creates evidence consistent with the root cause.
        """
        # Simplified evidence generation - in production, this would be more sophisticated
        evidence_map = {
            "DNS": {
                "description": f"DNS Query: {self.session.scenario.servers[0]['name']}\nResponse: {self.session.scenario.servers[0]['ip']}\nResponse code: NOERROR",
                "category": "dns",
            },
            "TCP": {
                "description": "TCP SYN sent\nWaiting for SYN-ACK...\n[Timeout - no response]",
                "category": "tcp",
            },
            "ICMP": {
                "description": f"Ping to {self.session.scenario.servers[0]['ip']}\nReply: 64 bytes from {self.session.scenario.servers[0]['ip']}: time=5ms",
                "category": "icmp",
            },
            "Firewall": {
                "description": f"Connection attempt to {self.session.scenario.servers[0]['ip']}:443\nStatus: Connection refused or timeout",
                "category": "firewall",
            },
        }

        # Default evidence
        evidence_type = next(
            (p for p in self.session.scenario.protocols if p in evidence_map),
            "TCP",
        )
        evidence_data = evidence_map.get(evidence_type, evidence_map["TCP"])

        return Evidence(
            id=f"inv-{len(self.session.gathered_evidence)}",
            timestamp=datetime.now(),
            category=evidence_data["category"],
            description=evidence_data["description"],
            relevant_to=[hyp.id],
        )

    def _analyze_evidence(self, hyp: Hypothesis, evidence: Evidence) -> str:
        """Analyze evidence in context of hypothesis."""
        return f"Evidence collected for '{hyp.hypothesis}': {evidence.description}"

    def _check_conclusion_correctness(self, hyp: Hypothesis, conclusion: str) -> bool:
        """Check if learner's conclusion about hypothesis is correct."""
        # Simplified check - in production, would be more sophisticated
        return True

    def _generate_conclusion_feedback(self, hyp: Hypothesis, is_correct: bool) -> str:
        """Generate feedback on hypothesis conclusion."""
        if is_correct:
            return f"Good analysis. The evidence supports your conclusion about '{hyp.hypothesis}'."
        return f"The evidence does not fully support this conclusion. Review the evidence again."

    def _score_final_diagnosis(
        self, root_cause: str, evidence: str, fault_domain: str, impact: str, remediation: str, confidence: str
    ) -> LabScore:
        """Score the final diagnosis."""
        score = LabScore()

        # Problem understanding
        if fault_domain.lower() == self.ground_truth["fault_domain"].lower():
            score.problem_understanding = 20
        elif any(
            layer in fault_domain for layer in self.ground_truth["fault_domain"].split("/")
        ):
            score.problem_understanding = 15
        else:
            score.problem_understanding = 5

        # Hypothesis quality
        score.hypothesis_quality = min(20, len(self.session.hypotheses) * 4)

        # Prioritization
        score.prioritization = 15 if len(self.session.investigation_history) > 2 else 10

        # Evidence interpretation
        score.evidence_interpretation = 20 if evidence else 10

        # Root cause
        if root_cause.lower() in self.ground_truth["root_cause"].lower():
            score.root_cause = 20
        else:
            score.root_cause = 5

        return score

    def _generate_rca_feedback(self, score: LabScore) -> str:
        """Generate feedback on RCA submission."""
        return f"Total Score: {score.total}/100\n" f"Problem Understanding: {score.problem_understanding}/20\n" f"Hypothesis Quality: {score.hypothesis_quality}/20\n" f"Prioritization: {score.prioritization}/15\n" f"Evidence Interpretation: {score.evidence_interpretation}/25\n" f"Root Cause: {score.root_cause}/20"
