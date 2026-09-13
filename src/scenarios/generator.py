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


def _random_mac() -> str:
    """Return a randomized MAC address."""
    return ":".join(f"{random.randint(0, 255):02x}" for _ in range(6))


def _random_hosts() -> Dict[str, str]:
    """Build a randomized but internally consistent host identity set.

    The client and DNS resolver share one subnet; the server, its load
    balancer backend and the firewall sit in a different one, matching
    the topologies presented.
    """
    oct2 = random.randint(0, 255)
    client_third = random.randint(0, 254)
    # Ensure client and server sit in different /24s
    server_third = (client_third + random.randint(1, 254)) % 256
    client_host = random.randint(10, 250)
    server_host = random.randint(10, 250)
    backend_host = 261 - server_host  # mirrored range; never collides
    server_mac = _random_mac()
    rogue_mac = _random_mac()
    while rogue_mac == server_mac:
        rogue_mac = _random_mac()
    return {
        "client_name": random.choice(CLIENT_NAMES),
        "client_ip": f"10.{oct2}.{client_third}.{client_host}",
        "client_subnet": f"10.{oct2}.{client_third}.0/24",
        "dns_server": f"10.{oct2}.{client_third}.2",
        "server_name": random.choice(SERVER_NAMES),
        "server_ip": f"10.{oct2}.{server_third}.{server_host}",
        "server_mac": server_mac,
        "backend_ip": f"10.{oct2}.{server_third}.{backend_host}",
        "rogue_mac": rogue_mac,
        "firewall_ip": f"10.{oct2}.{server_third}.1",
    }


class ScenarioGenerator:
    """Generates realistic network troubleshooting scenarios."""

    # Scenario templates. Each template carries its hidden ground truth:
    # root-cause-consistent evidence per investigation category, fault
    # keywords for hypothesis matching, remediation, the failure chain,
    # and the progressive hint ladder. Placeholders ({client_ip},
    # {server_ip}, {app_port}, ...) are rendered with the lab's randomized
    # host set at generation time.
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
            "hints": [
                "Before a client can open a TCP session to {server_name}, what must it learn first - and from whom?",
                "Compare reaching {server_name} by name with reaching {server_ip} directly. Where does the first path break?",
                "Capture and filter with `dns`, then follow the transaction for {server_name}.",
                "Check whether any DNS response ever arrives: `dns.flags.rcode` on the reply - or the absence of a reply entirely.",
            ],
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
            "hints": [
                "Sessions work, then die. What changes on the wire while the application sits idle between requests?",
                "Measure the silence between the last data packet and the disconnect. What can expire during quiet periods on a stateful path?",
                "Follow the TCP stream (`tcp.stream eq N`) and read its final packets - who ends the session, and how?",
                "Filter `tcp.flags.reset == 1` and note the reset's source. Compare the idle time before the reset with the upstream firewall's session timeout.",
            ],
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
            "hints": [
                "Latency and loss are clean, so what actually caps how many bytes can be in flight on this connection?",
                "Throughput per round trip is bounded by two negotiated values. What are they, and what happens if one of them is tiny?",
                "Inspect the SYN/SYN-ACK exchange: `tcp.flags.syn == 1` - read the announced window size and the window-scale option.",
                "Watch `tcp.window_size_value` across the flow and check whether window scaling was ever negotiated on the handshake.",
            ],
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
            "hints": [
                "Name resolution already succeeded. What must happen next for the browser to open a session with {server_name}?",
                "Pings reach {server_ip}, so the host is up. What is different between an ICMP echo and a TCP connection to port {app_port}?",
                "Filter the SYNs aimed at the service: `tcp.flags.syn == 1 && tcp.dstport == {app_port}` - what comes back for each one?",
                "Test another open port on {server_ip} (try 22) and compare the responses. Then read the edge firewall policy and its deny counters for tcp/{app_port}.",
            ],
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
            "hints": [
                "Ping works and the handshake completes, so the kernel accepted the connection. Who is supposed to actually read the request after that?",
                "Requests are ACKed but never answered. Is data being lost on the network, or is an established socket not being serviced?",
                "Follow the stream to port {app_port} (`tcp.port == {app_port}`) - the request was ACKed, so where does the conversation stop?",
                "Check the server's listen backlog: `ss -lnt` (or `netstat -s`) on {server_name} - is the accept queue for port {app_port} pinned at its limit?",
            ],
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
        {
            "title": "Large Transfers Stall Over the VPN",
            "incident_id": "INC-2026-006",
            "environment": "Production - VPN Interconnect",
            "symptom": "Branch users can browse and query the application, but uploads and large exports stall and time out",
            "impact": "Branch office of 30 users affected; nightly exports regularly miss their window",
            "difficulty": "expert",
            "root_cause": "Path MTU discovery black hole - tunnel firewall drops ICMP 'fragmentation needed' (type 3/code 4) messages",
            "fault_domain": "Layer 3 - ICMP/PMTUD",
            "protocols": ["TCP", "IP", "ICMP", "VPN"],
            "port_options": [443, 445],
            "topology_options": [
                "Branch Client -> Branch Router -> IPSec VPN -> HQ Firewall -> Application Server",
                "Branch Client -> Site Router -> Site-to-Site Tunnel -> Core Switch -> Server",
                "Branch Client -> Edge Router -> GRE-over-IPSec -> Data Center Firewall -> Server",
            ],
            "fault_keywords": ["mtu", "pmtud", "fragment", "icmp", "mss", "tunnel", "blackhole", "black hole", "oversized"],
            "remediation": "Permit ICMP type 3 code 4 (fragmentation needed) across the VPN zone, or clamp TCP MSS to the tunnel MTU on both tunnel endpoints.",
            "failure_chain": "Tunnel path MTU (1400) is smaller than the LAN MTU (1500)\n      ↓\nPMTUD should notify senders via ICMP 'fragmentation needed'\n      ↓\nTunnel firewall silently drops ICMP type 3 messages\n      ↓\nSenders keep transmitting full-size DF packets that cannot fit the tunnel\n      ↓\nLarge transfers stall with retransmissions; small packets pass unaffected",
            "hints": [
                "Small requests fly while large transfers stall. What property of a packet changes as its payload grows - besides its content?",
                "Only packets above a certain size die on the path. What mechanism normally tells a sender to shrink its segments when a link cannot carry them?",
                "Filter `tcp.analysis.retransmission` and compare the retransmitted segments with the ones that succeed - frame lengths and the DF bit (`ip.flags.df`).",
                "Hunt for 'fragmentation needed' on the path: `icmp.type == 3 && icmp.code == 4`. The router should be sending them - check what the VPN firewall policy does to ICMP.",
            ],
            "evidence": {
                "icmp": "Ping {server_ip} (default 56-byte payload): 4/4 replies, 11ms avg, TTL=63.\nNo ICMP type 3 code 4 (fragmentation needed) messages observed on the tunnel path, even while transfers stall.",
                "tcp": "Handshake negotiates MSS 1460 cleanly; small segments flow normally.\nEvery stalled transfer shows the same pattern: full-size 1500-byte packets with DF set are retransmitted at 1s/2s/4s backoff and never acknowledged - only the large segments are lost.",
                "performance": "Throughput collapses during bulk transfers while interactive traffic runs clean; RTT steady 11ms; zero loss for small packets, total loss for full-size ones.",
                "l2": "All interface error counters 0; speed/duplex negotiated cleanly; the VPN tunnel MTU is 1400 while both LANs use 1500.",
                "firewall": "VPN zone policy permits tcp/{app_port} but denies all ICMP on the tunnel; the deny rule covering ICMP type 3 shows an incrementing hit counter during every failed export.",
                "dns": "DNS Query: {server_name} (A record) -> {server_ip}\nResponse code: NOERROR (7ms).",
                "logs": "Branch router log during stalls: 'pak size 1500 greater than tunnel mtu 1400, DF bit set... dropping' - repeated hundreds of times per export attempt.",
                "application": "Application behaves normally for interactive use; only bulk transfers to {server_name} over the WAN path stall.",
            },
        },
        {
            "title": "Branch Office Cannot Reach the Application Subnet",
            "incident_id": "INC-2026-007",
            "environment": "Production - Branch/WAN",
            "symptom": "An entire branch office cannot reach the application; every connection times out, while the same server works fine from headquarters",
            "impact": "Complete outage for one branch of 25 users; other sites unaffected",
            "difficulty": "beginner",
            "root_cause": "Missing return route on the server-side router - replies to the branch subnet {client_subnet} are blackholed",
            "fault_domain": "Layer 3 - Routing",
            "protocols": ["TCP", "ICMP", "IP"],
            "port_options": [443, 80],
            "topology_options": [
                "Branch Client -> Branch Router -> WAN -> Core Router -> Firewall -> App Server",
                "Branch Client -> Site Switch -> MPLS -> Data Center Core -> Server",
                "Branch Client -> Edge Router -> IPSec VPN -> DC Firewall -> Server",
            ],
            "fault_keywords": ["route", "routing", "router", "subnet", "asymmetric", "return"],
            "remediation": "Restore the static route for the branch subnet on the server-side router and add monitoring for route withdrawal events.",
            "failure_chain": "Static route to {client_subnet} removed during a change window\n      ↓\nServer-side router has no path back to the branch\n      ↓\nSYNs reach the server; SYN-ACKs are dropped at the router\n      ↓\nClient sees only retransmissions, never a response\n      ↓\nWhole branch reports the application as down",
            "hints": [
                "A timeout hides two possibilities: the request never arrived, or the reply never made it back. Which one would be easier to disprove first?",
                "Other sites reach {server_name} without problems. What is different about the path from the branch - in each direction?",
                "Run a traceroute toward {server_ip} and note the last hop that answers, then inspect the routing table on the server-side router ({firewall_ip}).",
                "Check for a return route: look for {client_subnet} in the routing table on {firewall_ip}. SYNs arrive and SYN-ACKs leave the server - so where do the replies die?",
            ],
            "evidence": {
                "dns": "DNS Query: {server_name} (A record) -> {server_ip}\nResponse code: NOERROR (9ms) - resolution works; the failure is beyond DNS.",
                "icmp": "Ping {server_ip} from the branch: 0/4 replies - request timed out.\nTraceroute: hops answer until the server-side router ({firewall_ip}), then nothing further responds.",
                "tcp": "SYN {client_ip} -> {server_ip}:{app_port}: no response; retransmissions at 1s, 2s, 4s.\nCapture on the server segment: the SYN arrives, a SYN-ACK is sent back toward {firewall_ip} - and never appears again on the WAN.",
                "application": "Application on {server_name} is healthy; the monitoring station at headquarters reaches tcp/{app_port} successfully throughout the incident.",
                "firewall": "Firewall policy permits the flow from all internal zones; zero deny log entries during the incident window.",
                "l2": "ARP resolves the gateway MAC cleanly; interface error counters are zero on every segment.",
                "logs": "Server-side router ({firewall_ip}) running config: no route for {client_subnet} - the static route was removed in last night's change window.\nServer log: sessions succeed from every other subnet.",
            },
        },
        {
            "title": "TCP Handshake Succeeds but HTTPS Fails",
            "incident_id": "INC-2026-008",
            "environment": "Production - Public Service",
            "symptom": "Users report the browser blocks the site with a certificate warning; the application never loads",
            "impact": "All external HTTPS access effectively down since midnight",
            "difficulty": "advanced",
            "root_cause": "TLS certificate expired - automatic renewal failed, so the server presents an expired certificate",
            "fault_domain": "Layer 5/6 - TLS/Certificate",
            "protocols": ["DNS", "TCP", "TLS", "HTTPS"],
            "port_options": [443, 8443],
            "topology_options": [
                "Client -> ISP -> Edge Firewall -> Load Balancer -> Server",
                "Remote Client -> Internet -> Perimeter Firewall -> Web Tier -> Server",
                "Client -> Corporate Proxy -> Internet -> CDN -> Server",
            ],
            "fault_keywords": ["certificate", "cert", "tls", "ssl", "expire", "renewal", "pki"],
            "remediation": "Install the renewed certificate on the server (and any load balancer/CDN terminators), fix the failed renewal job, and alert on certificates nearing expiry.",
            "failure_chain": "Automatic certificate renewal job failed silently at 02:00\n      ↓\nServer certificate passed its notAfter date at midnight\n      ↓\nClients abort the TLS handshake with 'Certificate Expired' (alert 45)\n      ↓\nNo application data is ever exchanged over the session\n      ↓\nBrowsers refuse to load the site",
            "hints": [
                "DNS resolves and the TCP connection opens cleanly. What still stands between an open socket and a trusted, loaded page?",
                "Before a browser shows any page content, what does it verify about the server's identity?",
                "Filter the handshake: `tls.handshake.type == 1` and follow the messages between client and {server_name} - who aborts, and with which alert?",
                "Read the certificate's `notAfter` date in the capture (`tls.handshake.certificate`) and the client's `tls.alert_message == 45` - what expired, and when?",
            ],
            "evidence": {
                "dns": "DNS Query: {server_name} (A record) -> {server_ip}\nResponse code: NOERROR (3ms).",
                "icmp": "Ping {server_ip}: replies 5ms, 0% loss - host is reachable.",
                "tcp": "TCP 3-way handshake to {server_ip}:{app_port} completes; segments flow in both directions until the client aborts.",
                "tls": "ClientHello -> ServerHello, Certificate, ServerHello Done.\nClient verifies the certificate... aborts.\ntls.alert_message: Certificate Expired (45).\nServer certificate notAfter: yesterday 23:59 - the renewed certificate was never installed.",
                "http": "GET https://{server_name}/ is never sent - the session is torn down during the TLS handshake, before any request.",
                "firewall": "Firewall permits tcp/{app_port} end-to-end; no drops, no TLS inspection on this policy.",
                "application": "Application is healthy; internal health checks on plain HTTP return 200 OK throughout the incident.",
                "logs": "Certificate automation log: 'renewal failed - CA unreachable' at 02:00.\nExpiry alert raised 14 days ago - unacknowledged.",
            },
        },
        {
            "title": "Application Stalls Only During Large Transfers",
            "incident_id": "INC-2026-009",
            "environment": "Production - Access Layer",
            "symptom": "Interactive use works, but any large transfer to the server stalls with errors; the problem appeared after a switch replacement last night",
            "impact": "Backups and file transfers to one server fail; interactive users mostly unaffected",
            "difficulty": "intermediate",
            "root_cause": "Duplex mismatch - the switch port is hard-coded to full duplex while the server NIC auto-negotiated half, causing late collisions and frame loss",
            "fault_domain": "Layer 1/2 - Duplex",
            "protocols": ["TCP", "Ethernet", "IPv4"],
            "port_options": [445, 443],
            "topology_options": [
                "Client -> Access Switch -> Server",
                "Client -> Access Switch -> Distribution Switch -> Server",
                "Client -> Access Switch -> Router (on a stick) -> Server",
            ],
            "fault_keywords": ["duplex", "collision", "fcs", "negotiat", "physical", "framing", "layer 1", "l1", "nic"],
            "remediation": "Set the switch port and the server NIC to auto-negotiate (or hard-code both sides to the same speed/duplex), then clear and verify the error counters.",
            "failure_chain": "Switch port hard-coded 100/full, server NIC negotiates 100/half\n      ↓\nBoth sides transmit simultaneously believing the link is clean\n      ↓\nLate collisions corrupt frames under load\n      ↓\nFCS errors and retransmissions grow with traffic volume\n      ↓\nLarge transfers stall while small ones survive",
            "hints": [
                "The link is quiet and clean until it gets busy. What does it mean when errors only appear under load?",
                "When both ends of a link disagree about how to take turns, what do the switch's own error counters record?",
                "Filter `tcp.analysis.retransmission` and note when they cluster, then pull the switch port counters for the link to {server_name}.",
                "Compare duplex and speed settings on both ends of the link, plus the counters - late collisions and FCS errors on a 'clean' cable point at a negotiation mismatch.",
            ],
            "evidence": {
                "dns": "DNS Query: {server_name} (A record) -> {server_ip}\nResponse code: NOERROR (6ms).",
                "icmp": "Ping {server_ip}: 4/4 replies at 2ms while idle; during a transfer the same ping shows intermittent timeouts with 1-2 replies lost.",
                "tcp": "Retransmissions and out-of-order segments (`tcp.analysis.retransmission`, `tcp.analysis.lost_segment`) - clustered under load, absent when the link is quiet.",
                "l2": "Switch port facing {server_name}: hard-coded 100/full while the server NIC negotiated 100/half.\nCounters since last night: 8,412 late collisions, 2,207 FCS errors - climbing only during transfers.",
                "performance": "Loss correlates with load: 0% idle, up to 30% during bulk transfers; throughput collapses on large transfers while small flows survive.",
                "application": "Application is healthy; sessions that avoid large payloads complete normally.",
                "logs": "Switch log: 'late collision on port Gi1/0/24' repeating during transfer attempts - the port was reconfigured during last night's switch swap.",
                "firewall": "No firewall in this path drops traffic; no security events logged.",
            },
        },
        {
            "title": "Application Fails for Some Users but Not Others",
            "incident_id": "INC-2026-010",
            "environment": "Production - Web Tier",
            "symptom": "A subset of users consistently cannot load the application while their colleagues use it normally at the same moment",
            "impact": "Roughly half of all user sessions fail; affected users stay affected across retries",
            "difficulty": "advanced",
            "root_cause": "Load balancer health check probes the wrong port - a crashed backend pool member stays marked UP and keeps receiving sessions",
            "fault_domain": "Layer 4/7 - Load Balancer",
            "protocols": ["TCP", "HTTP", "DNS"],
            "port_options": [443, 8080],
            "topology_options": [
                "Users -> Edge Firewall -> Load Balancer -> App Pool (2 nodes)",
                "Users -> CDN -> Load Balancer -> App Pool (2 nodes)",
                "Users -> Perimeter Router -> Load Balancer -> App Pool (2 nodes)",
            ],
            "fault_keywords": ["load balancer", "loadbalancer", "lb", "backend", "pool", "member", "node", "health check"],
            "remediation": "Fix the health check to probe tcp/{app_port} on every pool member, remove or repair the crashed node, and enable health-check alerting.",
            "failure_chain": "Backend node {backend_ip} service crashed at 03:12\n      ↓\nHealth check for that node probes tcp/80 - the wrong port - so it stays 'UP'\n      ↓\nLoad balancer keeps assigning sessions to the dead node\n      ↓\nUsers hashed to that node fail consistently; others never see an error\n      ↓\n'Works for some users, not for others'",
            "hints": [
                "The same URL fails for one user and works for their colleague at the same moment. What does that already tell you about the application itself?",
                "If identical requests get different outcomes, something must be choosing between destinations. What makes that choice?",
                "Follow a failed session and a successful one: `tcp.stream` for both - which destination IP answers each request?",
                "Inspect the load balancer: pool members, their health status, and what the health check actually probes (`show server-farm` / LB dashboard) versus the application port tcp/{app_port}.",
            ],
            "evidence": {
                "dns": "DNS Query: {server_name} (A record) -> {server_ip}\nResponse code: NOERROR (4ms).",
                "icmp": "Ping {server_ip}: replies 4ms, 0% loss.\nPing {backend_ip}: replies arrive too - the node's host is up; only its application service is dead.",
                "tcp": "Failed users: the load balancer forwards their SYNs to {backend_ip} - no SYN-ACK, retransmissions until timeout.\nHealthy users: identical requests complete against {server_ip} in milliseconds.",
                "application": "Impact splits by user, not by time or device: the same users keep failing across retries and reboots, while others never fail once.",
                "logs": "Load balancer config: pool 'app-pool' has two members - {server_ip} and {backend_ip}.\nHealth check for {backend_ip} probes tcp/80, but the application listens on tcp/{app_port}.\nNode {backend_ip} application log: service crashed at 03:12, never restarted - yet the pool still shows it UP.",
                "firewall": "Firewall permits the flow; no drops between users and the load balancer VIP.",
                "performance": "No latency or loss anomalies on the path; failures are binary per user, not degraded.",
            },
        },
        {
            "title": "Application Turns Unusable Every Evening",
            "incident_id": "INC-2026-011",
            "environment": "Production - WAN Link",
            "symptom": "During the evening the application takes 30+ seconds to respond; during working hours it is fast and stable",
            "impact": "Evening-shift users effectively lose the application for four hours every night",
            "difficulty": "advanced",
            "root_cause": "Unshaped nightly backup saturates the WAN uplink - deep buffers inflate queuing delay (bufferbloat) during the backup window",
            "fault_domain": "Layer 2/3 - WAN/QoS",
            "protocols": ["TCP", "ICMP", "IP"],
            "port_options": [443, 1433],
            "topology_options": [
                "Client -> Site Router -> WAN -> Data Center Router -> Server",
                "Client -> Site Router -> MPLS -> Core Router -> Server",
                "Client -> Site Firewall -> VPN -> DC Firewall -> Server",
            ],
            "fault_keywords": ["buffer", "saturat", "congest", "qos", "queue", "backup", "shap", "uplink", "utilization", "bandwidth"],
            "remediation": "Shape or schedule the nightly backup so it cannot fill the uplink, and apply QoS that protects interactive traffic during bulk transfers.",
            "failure_chain": "Nightly backup replication starts at 22:00 on the WAN uplink\n      ↓\nUplink runs at 100% utilization with no traffic shaping\n      ↓\nDeep router buffers absorb packets instead of dropping them\n      ↓\nQueuing delay pushes RTT from 15ms to 600-900ms\n      ↓\nInteractive sessions time out; the app feels down every evening",
            "hints": [
                "The application is fast at 14:00 and unusable at 23:00, on the same path. What else changes between those two moments?",
                "Packets are barely being lost, yet everything crawls. When the network is not dropping traffic, what else can delay it?",
                "Compare latency across the day: `tcp.analysis.ack_rtt` (or a timed ping) at 14:00 vs 23:00 - then check the WAN uplink counters in each window.",
                "Correlate the slow window with what runs then: the backup scheduler and the uplink utilization counters. `show policy-map` on the site router shows no QoS is applied.",
            ],
            "evidence": {
                "dns": "DNS Query: {server_name} (A record) -> {server_ip}\nResponse code: NOERROR (5ms) - resolution unaffected at all hours.",
                "icmp": "Ping {server_ip} at 14:00: 15ms avg, 0% loss.\nPing {server_ip} at 23:00: 640ms avg, 0% loss - the anomaly is latency, not loss.",
                "tcp": "Handshakes complete; only a few retransmissions appear when inflated RTT exceeds the retransmission timeout.\nNo reset storms, no zero-window events.",
                "performance": "During 22:00-02:00: RTT on app flows climbs to 600-900ms; throughput of interactive sessions collapses while loss stays near 0%.\nOutside the window everything returns to baseline immediately.",
                "l2": "Uplink error counters are zero; speed/duplex clean - the link is healthy, just full.",
                "logs": "Backup scheduler: full replication to the DR site starts at 22:00 on the same uplink.\nSite router: uplink utilization 100% for the entire window; no QoS policy attached to the interface.",
                "application": "Application is healthy; slow behavior coincides exactly with the backup window (22:00-02:00).",
                "firewall": "No firewall drops; sessions are permitted and stable.",
            },
        },
        {
            "title": "Connections to the Server Fail in Waves",
            "incident_id": "INC-2026-012",
            "environment": "Production - Access Layer",
            "symptom": "Every few minutes all connections to the server stall or reset at once, then recover on their own minutes later",
            "impact": "Intermittent outages for the whole floor; no configuration was changed",
            "difficulty": "intermediate",
            "root_cause": "Duplicate IP address - an unmanaged test device answers ARP for {server_ip}, periodically winning the ARP race and hijacking client traffic",
            "fault_domain": "Layer 2 - ARP",
            "protocols": ["TCP", "ARP", "IPv4"],
            "port_options": [443, 445],
            "topology_options": [
                "Clients -> Access Switch -> Server",
                "Clients -> Access Switch -> Distribution Switch -> Server",
                "Clients -> Access Switch -> Router -> Server",
            ],
            "fault_keywords": ["arp", "duplicate", "ip conflict", "mac", "flap", "rogue", "spoof", "address conflict"],
            "remediation": "Disconnect or re-address the conflicting test device, clear ARP caches, and enable dynamic ARP inspection on the switch.",
            "failure_chain": "Test bench device connected yesterday with a static IP equal to {server_ip}\n      ↓\nBoth devices answer ARP requests for {server_ip}\n      ↓\nWhenever the rogue's reply is cached, clients send frames to {rogue_mac}\n      ↓\nTraffic vanishes into the wrong host until the cache refreshes\n      ↓\nOutages arrive in waves, healing themselves minutes later",
            "hints": [
                "The outage heals itself without anyone touching anything. What kinds of failures recover on their own - and what do they usually involve?",
                "Before packets can reach an IP, the client must ask which hardware address owns it. What happens when two devices claim it?",
                "Filter `arp` and watch who answers requests for {server_ip} - how many different MACs reply, and which one is the real server?",
                "Compare the ARP cache on {client_name} ({rogue_mac} vs the server's real address) and the switch CAM tables: which ports do the two MACs live behind?",
            ],
            "evidence": {
                "dns": "DNS Query: {server_name} (A record) -> {server_ip}\nResponse code: NOERROR (4ms).",
                "icmp": "Ping {server_ip}: succeeds during clean windows; during failure windows replies stop or arrive from an unexpected MAC.",
                "tcp": "During failure windows, segments bound for {server_ip} are ACKed by the wrong machine or vanish entirely; sessions reset mid-stream (`tcp.flags.reset == 1`).\nDuring clean windows, everything completes.",
                "l2": "ARP cache on {client_name}: entry for {server_ip} flaps between {server_mac} and {rogue_mac}.\nCapture: two different devices answer ARP requests for {server_ip}.",
                "logs": "Switch CAM tables show {server_mac} on the server port and {rogue_mac} on a lab bench port; both were observed answering ARP for {server_ip}.\nSecurity log: an unmanaged test device was connected to that port yesterday.",
                "application": "Application is healthy; failures hit all clients simultaneously in bursts, then clear without intervention.",
                "firewall": "No firewall drops; the failure occurs below the security policy layer.",
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
            if not matching:
                raise ValueError(
                    f"Unknown difficulty '{difficulty}'. "
                    "Valid options: beginner, intermediate, advanced, expert."
                )
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
            hints=[h.format(**hosts_formatted) for h in template.get("hints", [])],
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
