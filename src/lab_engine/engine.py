"""Lab engine - core investigation logic."""
import re
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


# Investigation-query keywords mapped to evidence categories. Rows are
# evaluated in order, so more specific protocols are matched before generic
# ones (e.g. "Filter DNS packets" resolves to "dns", not "general").
QUERY_CATEGORY_KEYWORDS = [
    (("dns", "nslookup", "resolve", "hostname", "name resolution"), "dns"),
    (("ping", "icmp", "echo request", "echo reply", "reachable", "traceroute", "trace route", "hop"), "icmp"),
    (("tls", "ssl", "certificate", "clienthello", "https"), "tls"),
    (("application", "app", "service"), "application"),
    (("http", "web", "browser", "url", "html"), "http"),
    (("firewall", "acl", "rule", "security policy", "session table", "nat"), "firewall"),
    (("arp", "mac", "ethernet", "layer 2", "l2", "switch", "vlan", "duplex", "qos", "mtu", "interface", "tunnel", "collision", "fcs", "negotiat", "physical", "cam"), "l2"),
    (("window", "throughput", "retransmission", "slow", "latency", "performance", "duplicate ack", "zero window", "speed", "queue", "buffer", "utilization", "uplink", "congest", "saturat"), "performance"),
    (("tcp", "syn", "handshake", "stream", "port", "connection", "flags", "ack", "reset", "rst", "mss"), "tcp"),
    (("udp",), "udp"),
    (("log", "syslog", "event", "netstat", "rout", "load balancer", "backend", "pool", "health check", "node", "backup"), "logs"),
]

# Categories a query falls back to when the scenario has no evidence for
# the primary category. Scenarios that record HTTP-layer observations
# under "application" still answer HTTP queries usefully.
CATEGORY_FALLBACKS = {
    "http": ("application",),
}

# Generic filler words that carry no diagnostic meaning. Removed before
# learner answers are compared with ground-truth text.
STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "been", "but", "by",
        "can", "cannot", "cause", "caused", "causes", "causing", "could",
        "did", "do", "does", "down", "due", "error", "failure", "fault",
        "for", "from", "had", "has", "have", "how", "in", "is", "issue",
        "it", "its", "layer", "no", "not", "of", "on", "or", "problem",
        "root", "should", "so", "that", "the", "these", "this", "those",
        "to", "too", "was", "were", "what", "when", "where", "which",
        "why", "will", "with", "would",
    }
)


def _significant_tokens(text: str) -> set:
    """Extract lowercase words from *text*, dropping generic filler."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {token for token in tokens if token not in STOPWORDS}


def _tokens_match(a: str, b: str) -> bool:
    """Whether two significant tokens refer to the same concept.

    Exact matches always count. Longer tokens also match on a shared
    prefix so morphological variants ("resolving" vs "resolver",
    "misconfigured" vs "misconfiguration") are recognized, while short
    generic fragments ("app" vs "application") are not.
    """
    if a == b:
        return True
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return True
    return len(a) >= 5 and len(b) >= 5 and a[:5] == b[:5]


def _token_coverage(answer: str, reference: str) -> float:
    """Fraction of reference tokens substantively covered by *answer*."""
    reference_tokens = _significant_tokens(reference)
    if not reference_tokens:
        return 0.0
    answer_tokens = _significant_tokens(answer)
    matched = sum(
        1
        for token in reference_tokens
        if any(_tokens_match(token, other) for other in answer_tokens)
    )
    return matched / len(reference_tokens)


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
        hyp.conclusion_correct = is_correct

        return {
            "hypothesis_id": hypothesis_id,
            "recorded_status": hyp.status.value,
            "is_correct": is_correct,
            "feedback": self._generate_conclusion_feedback(hyp, is_correct),
        }

    def skip_hypothesis(self, hypothesis_id: int) -> Dict[str, Any]:
        """Skip a hypothesis without recording a conclusion.

        A skipped hypothesis keeps any conclusion it already reached;
        otherwise it is marked SKIPPED so the final status table
        reflects the learner's choice.

        Args:
            hypothesis_id: ID of hypothesis to skip

        Returns:
            Recorded hypothesis status
        """
        hyp = self._get_hypothesis(hypothesis_id)
        if not hyp:
            return {"error": "Hypothesis not found"}
        concluded = {
            HypothesisStatus.CONFIRMED,
            HypothesisStatus.REJECTED,
            HypothesisStatus.INCONCLUSIVE,
        }
        if hyp.status not in concluded:
            hyp.status = HypothesisStatus.SKIPPED
        return {
            "hypothesis_id": hypothesis_id,
            "recorded_status": hyp.status.value,
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
            "is_correct": score.root_cause >= 15,
            "official_root_cause": self.ground_truth["root_cause"],
            "official_fault_domain": self.ground_truth["fault_domain"],
            "official_remediation": self.ground_truth["remediation"],
            "official_failure_chain": self.session.scenario.failure_chain,
            "official_evidence": "\n".join(
                f"* [{e.category}] {e.description.splitlines()[0]}"
                for e in self.session.scenario.evidence_list
            ),
        }

    def get_hint(self, level: int) -> str:
        """Provide progressive hints based on hint level.

        Scenario hints run from a Socratic question (level 1) to the
        relevant Wireshark filter (level 4). Falls back to generic hints
        when the scenario carries none.

        Args:
            level: Hint level (1-4)

        Returns:
            Hint message
        """
        scenario_hints = self.session.scenario.hints
        if 1 <= level <= len(scenario_hints):
            return scenario_hints[level - 1]
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

    def _map_query_to_category(self, query: str) -> str:
        """Map an investigation query to an evidence category."""
        query_lower = query.lower()
        for keywords, category in QUERY_CATEGORY_KEYWORDS:
            if any(keyword in query_lower for keyword in keywords):
                return category
        return "general"

    def _generate_evidence(self, hyp: Hypothesis, query: str) -> Evidence:
        """Generate realistic evidence based on investigation query.

        Evidence is selected by the learner's query and is always drawn
        from the scenario's ground truth, so every observation stays
        internally consistent with the underlying root cause.
        """
        category = self._map_query_to_category(query)

        # Try the mapped category first, then known aliases, so queries
        # like "check HTTP" stay useful in scenarios that record
        # HTTP-layer observations under "application".
        match = None
        for candidate in (category, *CATEGORY_FALLBACKS.get(category, ())):
            match = next(
                (
                    e
                    for e in self.session.scenario.evidence_list
                    if e.category == candidate
                ),
                None,
            )
            if match is not None:
                break
        if match is not None:
            description = match.description
            technical_details = dict(match.technical_details)
        else:
            # Baseline fallback: nothing anomalous in this area, which is
            # itself consistent with the hidden root cause.
            description = (
                f"No anomalies found while checking '{query}'. "
                "Observed behavior in this area matches the healthy baseline."
            )
            technical_details = {}

        return Evidence(
            id=f"inv-{len(self.session.gathered_evidence)}",
            timestamp=datetime.now(),
            category=category,
            description=description,
            technical_details=technical_details,
            relevant_to=[hyp.id],
        )

    def _analyze_evidence(self, hyp: Hypothesis, evidence: Evidence) -> str:
        """Analyze evidence in context of hypothesis."""
        return f"Evidence collected for '{hyp.hypothesis}': {evidence.description}"

    def _hypothesis_matches_root_cause(self, hyp: Hypothesis) -> bool:
        """Check whether a hypothesis points at the true fault.

        Keywords match at the start of a word, so prefixes like "resol"
        still match "resolution" while "app" no longer matches
        unrelated words like "happens".
        """
        text = hyp.hypothesis.lower()
        return any(
            re.search(rf"\b{re.escape(keyword)}", text)
            for keyword in self.session.scenario.fault_keywords
        )

    def _check_conclusion_correctness(
        self, hyp: Hypothesis, conclusion: str
    ) -> Optional[bool]:
        """Check if learner's conclusion about hypothesis is correct.

        CONFIRM is correct only when the hypothesis actually points at the
        root cause; REJECT is correct only when it does not. INCONCLUSIVE
        is neither right nor wrong and is excluded from scoring.
        """
        matches_root_cause = self._hypothesis_matches_root_cause(hyp)
        if conclusion == "CONFIRM":
            return matches_root_cause
        if conclusion == "REJECT":
            return not matches_root_cause
        return None

    def _generate_conclusion_feedback(
        self, hyp: Hypothesis, is_correct: Optional[bool]
    ) -> str:
        """Generate feedback on hypothesis conclusion."""
        if is_correct is None:
            return (
                "Recorded as inconclusive. Gather more evidence before "
                "committing to a conclusion."
            )
        if is_correct:
            return f"Good analysis. The evidence supports your conclusion about '{hyp.hypothesis}'."
        return f"The evidence does not fully support this conclusion. Review the evidence again."

    def _score_final_diagnosis(
        self, root_cause: str, evidence: str, fault_domain: str, impact: str, remediation: str, confidence: str
    ) -> LabScore:
        """Score the final diagnosis."""
        score = LabScore()
        score.problem_understanding = self._score_fault_domain(fault_domain)
        score.hypothesis_quality = self._score_hypothesis_quality()
        score.prioritization = self._score_prioritization()
        score.evidence_interpretation = self._score_evidence_interpretation(evidence)
        score.root_cause = self._score_root_cause(root_cause)
        return score

    def _score_fault_domain(self, fault_domain: str) -> int:
        """Score problem understanding (/20).

        Exact matches earn full credit, naming the key component (e.g.
        "DNS") earns partial credit, and naming only the right layer
        earns less.
        """
        official = self.ground_truth["fault_domain"]
        if " ".join(fault_domain.lower().split()) == " ".join(
            official.lower().split()
        ):
            return 20
        official_tokens = _significant_tokens(official)
        key_tokens = {token for token in official_tokens if not token.isdigit()}
        learner_tokens = _significant_tokens(fault_domain)
        if any(_tokens_match(lt, kt) for lt in learner_tokens for kt in key_tokens):
            return 15
        if any(_tokens_match(lt, ot) for lt in learner_tokens for ot in official_tokens):
            return 10
        return 5

    def _score_hypothesis_quality(self) -> int:
        """Score hypothesis quality (/20).

        Credit is earned per canonical cause area covered by the
        learner's hypotheses, not per hypothesis typed in.
        """
        expected = self.session.scenario.expected_hypotheses
        if not expected:
            return 20
        covered = set()
        for hyp in self.session.hypotheses:
            hyp_tokens = _significant_tokens(hyp.hypothesis)
            for index, expected_hypothesis in enumerate(expected):
                if index in covered:
                    continue
                expected_tokens = _significant_tokens(expected_hypothesis)
                if any(
                    _tokens_match(ht, et)
                    for ht in hyp_tokens
                    for et in expected_tokens
                ):
                    covered.add(index)
        return round(20 * len(covered) / len(expected))

    def _score_prioritization(self) -> int:
        """Score prioritization (/15).

        Rewards ranking the true fault's hypothesis first; lower ranks
        and never hypothesizing the fault earn progressively less.
        """
        matching = [
            hyp
            for hyp in self.session.hypotheses
            if self._hypothesis_matches_root_cause(hyp)
        ]
        if not matching:
            return 6
        rank_by_id = {
            hyp.id: rank
            for rank, hyp in enumerate(
                sorted(self.session.hypotheses, key=lambda item: item.priority)
            )
        }
        best_rank = min(rank_by_id[hyp.id] for hyp in matching) + 1
        return max(6, 15 - 3 * (best_rank - 1))

    def _score_evidence_interpretation(self, evidence: str) -> int:
        """Score evidence interpretation (/25).

        Base points for citing evidence, plus credit for definitive
        conclusions (CONFIRM/REJECT) that were correct. INCONCLUSIVE
        verdicts are excluded rather than counted as wrong.
        """
        interpretation = 5 if evidence else 0
        definitive = [
            hyp for hyp in self.session.hypotheses if hyp.conclusion_correct is not None
        ]
        if definitive:
            correct = [hyp for hyp in definitive if hyp.conclusion_correct]
            interpretation += round(20 * len(correct) / len(definitive))
        return min(25, interpretation)

    def _score_root_cause(self, root_cause: str) -> int:
        """Score the root cause statement (/20).

        Measured by how much of the official root cause the answer
        substantively covers. One-word answers name a domain at best
        and never earn full credit.
        """
        coverage = _token_coverage(root_cause, self.ground_truth["root_cause"])
        if len(_significant_tokens(root_cause)) < 2:
            return 10 if coverage > 0 else 5
        if coverage >= 0.5:
            return 20
        if coverage >= 0.25:
            return 15
        return 10 if coverage > 0 else 5

    def _generate_rca_feedback(self, score: LabScore) -> str:
        """Generate feedback on RCA submission."""
        return f"Total Score: {score.total}/100\n" f"Problem Understanding: {score.problem_understanding}/20\n" f"Hypothesis Quality: {score.hypothesis_quality}/20\n" f"Prioritization: {score.prioritization}/15\n" f"Evidence Interpretation: {score.evidence_interpretation}/25\n" f"Root Cause: {score.root_cause}/20"
