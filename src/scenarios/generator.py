"""Scenario generator for network troubleshooting labs."""
import random
from datetime import datetime
from typing import List
from lab_engine.models import (
    IncidentScenario,
    Evidence,
)


class ScenarioGenerator:
    """Generates realistic network troubleshooting scenarios."""

    # Scenario templates
    SCENARIO_TEMPLATES = [
        {
            "title": "Host Cannot Connect to Application Server",
            "incident_id": "INC-2026-001",
            "environment": "Production - Data Center",
            "symptom": "User reports connection timeout when accessing web application",
            "impact": "Business-critical application unreachable for 1 customer",
            "difficulty": "beginner",
            "root_cause": "DNS failure - server hostname not resolving",
            "fault_domain": "Layer 3/4 - DNS",
            "protocols": ["DNS", "TCP", "HTTP"],
        },
        {
            "title": "Application Intermittently Disconnects",
            "incident_id": "INC-2026-002",
            "environment": "Production - Branch Office",
            "symptom": "Remote users experience dropped connections every 5-10 minutes",
            "impact": "Productivity impact affecting 50+ users",
            "difficulty": "intermediate",
            "root_cause": "Firewall session timeout and RST packet on idle connections",
            "fault_domain": "Layer 4 - TCP/Firewall",
            "protocols": ["TCP", "IPv4", "Firewall"],
        },
        {
            "title": "Connection Unusually Slow",
            "incident_id": "INC-2026-003",
            "environment": "Production - WAN Link",
            "symptom": "File transfer to remote office takes 10x longer than expected",
            "impact": "Delayed data synchronization affecting business operations",
            "difficulty": "intermediate",
            "root_cause": "TCP window size too small due to misconfigured switch",
            "fault_domain": "Layer 2/4 - TCP/Switch",
            "protocols": ["TCP", "Ethernet", "IPv4"],
        },
        {
            "title": "DNS Works but HTTPS Fails",
            "incident_id": "INC-2026-004",
            "environment": "Production - Cloud",
            "symptom": "DNS resolves correctly but TLS handshake times out",
            "impact": "HTTPS access blocked for external users",
            "difficulty": "advanced",
            "root_cause": "Firewall blocking TCP port 443, but DNS responses confuse the issue",
            "fault_domain": "Layer 4/5 - Firewall/TLS",
            "protocols": ["DNS", "TCP", "TLS", "HTTPS"],
        },
        {
            "title": "Server Responds but App Fails",
            "incident_id": "INC-2026-005",
            "environment": "Production - Hybrid",
            "symptom": "Ping succeeds, TCP port is open, but HTTP requests hang",
            "impact": "Application service degradation",
            "difficulty": "advanced",
            "root_cause": "Application listening but not accepting new connections (queue full)",
            "fault_domain": "Layer 7 - Application",
            "protocols": ["ICMP", "TCP", "HTTP"],
        },
    ]

    @staticmethod
    def generate_scenario(difficulty: str = None) -> IncidentScenario:
        """Generate a random network troubleshooting scenario.

        Args:
            difficulty: Optional difficulty level (beginner, intermediate, advanced, expert)

        Returns:
            IncidentScenario object with complete incident details
        """
        template = random.choice(ScenarioGenerator.SCENARIO_TEMPLATES)

        if difficulty and difficulty != template["difficulty"]:
            # Filter for specific difficulty if requested
            matching = [
                t
                for t in ScenarioGenerator.SCENARIO_TEMPLATES
                if t["difficulty"] == difficulty
            ]
            if matching:
                template = random.choice(matching)

        # Build scenario
        scenario = IncidentScenario(
            incident_id=template["incident_id"],
            title=template["title"],
            environment=template["environment"],
            clients=[
                {"name": "Client-A", "ip": "10.10.10.25", "role": "Workstation"},
            ],
            servers=[
                {"name": "Server-A", "ip": "10.10.20.50", "role": "Application Server"},
            ],
            protocols=template["protocols"],
            relevant_ports=[443, 80, 53, 22],
            user_reported_symptom=template["symptom"],
            business_impact=template["impact"],
            incident_time=datetime.now().isoformat(),
            network_topology="Client -> Firewall -> Router -> Server",
            difficulty=template["difficulty"],
            root_cause=template["root_cause"],
            root_cause_explanation="See detailed analysis in RCA",
            fault_domain=template["fault_domain"],
            remediation="Will be determined during investigation",
            expected_hypotheses=[
                "DNS resolution failure",
                "Network connectivity problem",
                "TCP service unavailable",
                "Firewall blocking traffic",
                "Application/server failure",
            ],
        )

        return scenario

    @staticmethod
    def create_initial_evidence(scenario: IncidentScenario) -> List[Evidence]:
        """Create initial evidence for the scenario.

        Args:
            scenario: The incident scenario

        Returns:
            List of initial evidence pieces
        """
        evidence = [
            Evidence(
                id="init-001",
                timestamp=datetime.now(),
                category="connectivity",
                description=f"Client: {scenario.clients[0]['ip']}, Server: {scenario.servers[0]['ip']}",
                technical_details={
                    "source": scenario.clients[0]["ip"],
                    "destination": scenario.servers[0]["ip"],
                },
                relevant_to=[],
            ),
            Evidence(
                id="init-002",
                timestamp=datetime.now(),
                category="environment",
                description=f"Environment: {scenario.environment}",
                technical_details={"environment": scenario.environment},
                relevant_to=[],
            ),
            Evidence(
                id="init-003",
                timestamp=datetime.now(),
                category="incident",
                description=f"Incident Time: {scenario.incident_time}",
                technical_details={"incident_time": scenario.incident_time},
                relevant_to=[],
            ),
        ]
        return evidence
