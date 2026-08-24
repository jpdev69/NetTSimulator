"""Scenario generator for network troubleshooting labs."""
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from lab_engine.models import (
    IncidentScenario,
    Evidence,
)

# Identity pools: hostnames, sites and ports are randomized per lab so no
# two runs feel like replicas of each other.
CLIENT_NAMES = [
    "WKS-0142", "LT-2291", "DESKTOP-7F3A", "ACCOUNTING-PC-03",
    "HR-LAPTOP-11", "POS-TERMINAL-08", "DEV-NB-117", "RECEPTION-02",
]

SERVER_NAMES = [
    "web-prod-03", "app-node-12", "crm-app-01", "filesrv-eu-02",
    "api-gw-07", "erp-core-01", "mail-frontend-04", "orders-svc-02",
]

SITE_NAMES = ["EU-West", "US-East", "US-Central", "APAC-SG", "EU-North", "LATAM"]

EXTRA_PORTS = [80, 25, 1433, 3389, 8080]


def _random_hosts() -> Dict[str, str]:
    """Build a randomized but internally consistent host identity set.

    The client and DNS resolver share one subnet; the server and the
    firewall sit in a different one, matching the topologies presented.
    """
    oct2 = random.randint(0, 255)
    client_third = random.randint(0, 254)
    # Ensure client and server sit in different /24s
    server_third = (client_third + random.randint(1, 254)) % 256
    return {
        "client_name": random.choice(CLIENT_NAMES),
        "client_ip": f"10.{oct2}.{client_third}.{random.randint(10, 250)}",
        "dns_server": f"10.{oct2}.{client_third}.2",
        "server_name": random.choice(SERVER_NAMES),
        "server_ip": f"10.{oct2}.{server_third}.{random.randint(10, 250)}",
        "firewall_ip": f"10.{oct2}.{server_third}.1",
    }


class ScenarioGenerator:
    """Generates realistic network troubleshooting scenarios."""

    # Scenario templates. Each template carries its hidden ground truth:
    # root-cause-consistent evidence per investigation category, fault
    # keywords for hypothesis matching, remediation, and the failure chain.
    # Placeholders ({client_ip}, {server_ip}, {app_port}, ...) are rendered
    # with the lab's randomized host set at generation time.
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
            "port_options": [80, 443],
            "protocols_map": {
                80: ["DNS", "TCP", "HTTP"],
                443: ["DNS", "TCP", "HTTPS"],
            },
            "topology_options": [
                "Client -> Access Switch -> Core Switch -> Firewall -> App Server",
                "Client -> Switch -> Router -> DMZ Firewall -> Server",
                "Client -> VPN -> Data Center Core -> Load Balancer -> Server",
            ],
            "fault_keywords": ["dns", "resol", "hostname", "name"],
            "remediation": "Restore DNS service on the resolver and verify the A record for the application hostname.",
            "failure_chain": "Client needs hostname resolved\n      ↓\nDNS server unreachable / no response\n      ↓\nName resolution never completes\n      ↓\nNo TCP connection to the application is ever attempted\n      ↓\nUser observes connection timeout",
            "evidence": {
                "dns": "DNS Query: {server_name} (A record) -> resolver {dns_server}\n[No response] - retransmission 1, 2, 3 (1s/2s/4s backoff)\ndns.flags.rcode: N/A - no response packet received from {dns_server}",
                "icmp": "Ping {server_ip}: 4/4 replies, avg 4ms TTL=63\nNetwork layer to the server is healthy.",
                "tcp": "SYN {client_ip} -> {server_ip}:{app_port}\nSYN-ACK received - ACK sent\nTCP 3-way handshake completes when the IP address is used directly.",
                "application": "No HTTP request leaves the client for {server_name} - name resolution fails before any connection attempt to the web application.",
                "firewall": "Firewall policy permits udp/53 and tcp/{app_port} for this host pair; zero deny log entries.",
                "l2": "ARP resolves gateway MAC; interface errors 0; duplex/speed negotiated cleanly.",
                "logs": "Client resolver cache: no A record cached for {server_name}; resolver retries logged against {dns_server}.",
            },
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
            "port_options": [443, 1433],
            "topology_options": [
                "Branch Client -> Access Switch -> Branch Firewall -> WAN Router -> HQ Firewall -> Server",
                "Branch Client -> SD-WAN Gateway -> HQ Edge Firewall -> Server",
                "Remote User -> VPN Concentrator -> Core Switch -> Firewall -> Server",
            ],
            "fault_keywords": ["firewall", "timeout", "idle", "session", "rst", "reset", "drop"],
            "remediation": "Raise the firewall TCP idle timeout for this flow or enable application-layer keep-alive.",
            "failure_chain": "Application session established\n      ↓\nUser idle for >300s\n      ↓\nFirewall session entry expires (idle timeout)\n      ↓\nFirewall sends RST to the client\n      ↓\nApplication reports dropped connection",
            "evidence": {
                "dns": "DNS Query: {server_name} (A record) -> {server_ip}\nResponse code: NOERROR (12ms).",
                "icmp": "Ping {server_ip}: replies avg 3ms, 0% loss.",
                "tcp": "Handshake completes (SYN / SYN-ACK / ACK).\nSession idle ~300s...\nRST received from {firewall_ip} (upstream firewall)\ntcp.flags.reset == 1 at frame #4892.",
                "firewall": "Session table: TCP idle timeout = 300s for this flow.\nLog: 'session closed: idle timeout exceeded - RST sent to client'.",
                "application": "Disconnects occur only after silence; sessions under continuous use never drop.",
                "performance": "No retransmissions or loss during active periods; RTT stable at 3-5ms.",
            },
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
            "port_options": [445, 21, 443],
            "topology_options": [
                "Client -> LAN Switch -> WAN Router -> MPLS -> Remote Router -> Switch -> Server",
                "Client -> Edge Router -> Metro Ethernet WAN -> Remote Switch -> Server",
                "Client -> Site Router -> IPSec Tunnel -> Remote Core Switch -> Server",
            ],
            "fault_keywords": ["window", "throughput", "slow", "switch", "shap", "qos", "misconfigur"],
            "remediation": "Remove the legacy QoS/traffic-shaping policy on the server switch port and restore TCP window scaling.",
            "failure_chain": "Legacy shaping policy applied on server switch port\n      ↓\nTCP options stripped - window scaling not negotiated\n      ↓\nReceive window pinned at 1024 bytes\n      ↓\nBytes in flight capped at 1024 per RTT\n      ↓\nTransfer takes ~10x longer than baseline",
            "evidence": {
                "dns": "DNS Query: {server_name} (A record) -> {server_ip}\nResponse code: NOERROR (8ms).",
                "icmp": "Ping {server_ip}: 28ms avg, 0% loss - link latency is normal.",
                "tcp": "SYN -> SYN-ACK: Window Size 1024, window-scale option absent.\ntcp.window_size_value == 1024 for the entire flow.",
                "performance": "Bytes in flight capped at 1024; throughput ~10x below baseline; RTT steady 28ms; zero retransmissions.",
                "l2": "Switch port for {server_name} carries legacy QoS shaping policy 'legacy-1m'; negotiated speed/duplex 1Gbps full, interface errors 0.",
                "application": "Application responds correctly to requests; transfer rate is limited at the transport layer, not by the app.",
            },
        },
        {
            "title": "DNS Works but HTTPS Fails",
            "incident_id": "INC-2026-004",
            "environment": "Production - Cloud",
            "symptom": "DNS resolves correctly but TLS handshake times out",
            "impact": "HTTPS access blocked for external users",
            "difficulty": "advanced",
            "root_cause": "Firewall blocking TCP port {app_port}, but DNS responses confuse the issue",
            "fault_domain": "Layer 4/5 - Firewall/TLS",
            "protocols": ["DNS", "TCP", "TLS", "HTTPS"],
            "port_options": [443, 8443],
            "topology_options": [
                "Client -> ISP -> Edge Firewall -> Cloud Load Balancer -> Server",
                "Remote Client -> Internet -> Perimeter Firewall -> Cloud vSwitch -> Server",
                "Client -> Corporate Proxy -> Internet -> Cloud Security Group -> Server",
            ],
            "fault_keywords": ["firewall", "{app_port}", "tls", "https", "block", "filter", "acl"],
            "remediation": "Add an explicit permit for tcp/{app_port} to the server on the edge firewall policy.",
            "failure_chain": "DNS resolution permitted - hostname resolves\n      ↓\nEdge firewall implicitly denies tcp/{app_port}\n      ↓\nSYN packets dropped silently\n      ↓\nTCP session never establishes, TLS never begins\n      ↓\nUser sees HTTPS timeout although 'DNS works'",
            "evidence": {
                "dns": "DNS Query: {server_name} (A record) -> {server_ip}\nResponse code: NOERROR (2ms) - resolution succeeds.",
                "icmp": "Ping {server_ip}: replies 6ms, 0% loss - host is reachable.",
                "tcp": "TCP SYN {client_ip} -> {server_ip}:{app_port} sent\n[Timeout - no response]\nSYN retransmissions at 1s, 2s, 4s...\nControl check: SYN to {server_ip}:22 receives SYN-ACK.",
                "tls": "No TLS ClientHello observed on the wire - the TCP session to :{app_port} never establishes, so TLS negotiation never begins.",
                "firewall": "Edge firewall policy: implicit deny tcp/{app_port} -> {server_ip}; deny hit counter increments with each SYN.\nPermits exist for udp/53 and icmp only.",
                "application": "HTTPS unreachable; client reports ERR_CONNECTION_TIMED_OUT after ~21s.",
            },
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
            "port_options": [443, 8080],
            "topology_options": [
                "Client -> VPN -> Firewall -> Hybrid Router -> On-prem Server",
                "Client -> Switch -> Load Balancer -> On-prem App Server",
                "Client -> Cloud Gateway -> Direct Connect -> On-prem Switch -> Server",
            ],
            "fault_keywords": ["application", "queue", "backlog", "server", "accept", "listen", "app"],
            "remediation": "Restart the wedged application workers and raise the listen backlog; add monitoring on the accept queue.",
            "failure_chain": "Application workers wedged but process still listening\n      ↓\nAccept queue fills to its backlog limit (128/128)\n      ↓\nKernel completes handshakes; no worker ever dequeues\n      ↓\nHTTP requests are ACKed but never processed\n      ↓\nClient requests hang until timeout",
            "evidence": {
                "icmp": "Ping {server_ip}: 2ms avg, 0% loss - host reachable.",
                "tcp": "SYN -> SYN-ACK -> ACK completes (kernel accepts on behalf of the listener).\nAfter the HTTP GET is sent: no application data returns; connection stalls in ESTABLISHED.\ntcp.analysis.retransmission of the request segment.",
                "dns": "DNS Query: {server_name} (A record) -> {server_ip}\nResponse code: NOERROR (5ms).",
                "http": "HTTP GET transmitted and ACKed by the kernel; no HTTP response ever arrives - client times out after 30s.",
                "application": "{server_name} accepting on :{app_port} but accept queue full (Recv-Q 128/128); application log: 'listen backlog exceeded' warnings repeating.",
                "logs": "netstat on {server_name}: 128 connections in the :{app_port} Recv-Q backlog, none dequeued in the last 20 minutes.",
                "performance": "Server CPU 12%, memory nominal, zero packet loss, latency low - resources fine; the application is not servicing its sockets.",
            },
        },
    ]

    @staticmethod
    def generate_scenario(difficulty: Optional[str] = None) -> IncidentScenario:
        """Generate a random network troubleshooting scenario.

        The scenario type, difficulty, topology, hosts, ports and incident
        time are all randomized per generation; the evidence is rendered
        from the same randomized identity set so it stays internally
        consistent with the hidden root cause.

        Args:
            difficulty: Optional difficulty level (beginner, intermediate, advanced, expert)

        Returns:
            IncidentScenario object with complete incident details
        """
        candidates = ScenarioGenerator.SCENARIO_TEMPLATES
        if difficulty:
            matching = [
                t
                for t in ScenarioGenerator.SCENARIO_TEMPLATES
                if t["difficulty"] == difficulty.lower()
            ]
            if matching:
                candidates = matching

        template = random.choice(candidates)

        # Randomize the lab identity: hosts, ports, topology, site, time.
        hosts = _random_hosts()
        app_port = random.choice(template.get("port_options", [443]))
        hosts["app_port"] = str(app_port)

        protocols = template.get("protocols_map", {}).get(app_port, template["protocols"])
        relevant_ports = {app_port, 22, 53}
        extra_port = random.choice([None] + EXTRA_PORTS)
        if extra_port:
            relevant_ports.add(extra_port)

        hosts_formatted = dict(hosts)
        evidence_list = [
            Evidence(
                id=f"truth-{category}",
                timestamp=datetime.now(),
                category=category,
                description=description.format(**hosts_formatted),
                relevant_to=[],
            )
            for category, description in template["evidence"].items()
        ]

        incident_time = datetime.now() - timedelta(
            hours=random.randint(1, 72), minutes=random.randint(0, 59)
        )

        scenario = IncidentScenario(
            incident_id=template["incident_id"],
            title=template["title"],
            environment=f"{template['environment']} - {random.choice(SITE_NAMES)}",
            clients=[
                {"name": hosts["client_name"], "ip": hosts["client_ip"], "role": "Workstation"},
            ],
            servers=[
                {"name": hosts["server_name"], "ip": hosts["server_ip"], "role": "Application Server"},
            ],
            protocols=list(protocols),
            relevant_ports=sorted(relevant_ports),
            user_reported_symptom=template["symptom"],
            business_impact=template["impact"],
            incident_time=incident_time.isoformat(),
            network_topology=random.choice(template["topology_options"]),
            difficulty=template["difficulty"],
            root_cause=template["root_cause"].format(**hosts_formatted),
            root_cause_explanation="See detailed analysis in RCA",
            fault_domain=template["fault_domain"],
            evidence_list=evidence_list,
            remediation=template["remediation"].format(**hosts_formatted),
            failure_chain=template["failure_chain"].format(**hosts_formatted),
            fault_keywords=[k.format(**hosts_formatted) for k in template["fault_keywords"]],
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

        Intentionally incomplete: the learner must still have multiple
        plausible explanations after reviewing it.

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
