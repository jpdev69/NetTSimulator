"""Core data models for the lab simulator."""
from enum import Enum
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime


class HypothesisStatus(str, Enum):
    """Status of a hypothesis during investigation."""
    NOT_TESTED = "NOT_TESTED"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"
    CONFIRMED = "CONFIRMED"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class Hypothesis:
    """Represents a single hypothesis during troubleshooting."""
    id: int
    priority: int
    hypothesis: str
    status: HypothesisStatus = HypothesisStatus.NOT_TESTED
    evidence: List[str] = field(default_factory=list)
    reason_for_priority: str = ""
    expected_evidence: str = ""
    falsifying_evidence: str = ""
    investigation_method: str = ""


@dataclass
class Evidence:
    """Represents a piece of evidence gathered during investigation."""
    id: str
    timestamp: datetime
    category: str  # e.g., "dns", "tcp", "icmp", "application", "firewall"
    description: str
    technical_details: Dict[str, Any] = field(default_factory=dict)
    relevant_to: List[int] = field(default_factory=list)  # hypothesis IDs


@dataclass
class IncidentScenario:
    """Represents a network troubleshooting incident."""
    incident_id: str
    title: str
    environment: str
    clients: List[Dict[str, str]]
    servers: List[Dict[str, str]]
    protocols: List[str]
    relevant_ports: List[int]
    user_reported_symptom: str
    business_impact: str
    incident_time: str
    network_topology: str
    difficulty: str  # "beginner", "intermediate", "advanced", "expert"
    root_cause: str
    root_cause_explanation: str
    fault_domain: str
    evidence_list: List[Evidence] = field(default_factory=list)
    expected_hypotheses: List[str] = field(default_factory=list)
    remediation: str = ""
    failure_chain: str = ""


@dataclass
class InvestigationSession:
    """Tracks the state of an ongoing investigation."""
    scenario: IncidentScenario
    hypotheses: List[Hypothesis] = field(default_factory=list)
    gathered_evidence: List[Evidence] = field(default_factory=list)
    current_hypothesis_index: int = 0
    investigation_history: List[Dict[str, Any]] = field(default_factory=list)
    final_diagnosis: Optional[str] = None
    final_confidence: Optional[str] = None
    session_start: datetime = field(default_factory=datetime.now)


@dataclass
class LabScore:
    """Scoring rubric for lab completion."""
    problem_understanding: int = 0  # /20
    hypothesis_quality: int = 0  # /20
    prioritization: int = 0  # /15
    evidence_interpretation: int = 0  # /25
    root_cause: int = 0  # /20

    @property
    def total(self) -> int:
        """Calculate total score."""
        return (
            self.problem_understanding
            + self.hypothesis_quality
            + self.prioritization
            + self.evidence_interpretation
            + self.root_cause
        )
