# NetTSimulator - Network Troubleshooting Training Lab

A terminal-based lab simulator for practicing hypothesis-driven network troubleshooting:
work a realistic incident the way you would with Wireshark in the field - observe,
form and prioritize hypotheses, gather evidence, and produce an evidence-based root
cause analysis.

## Quick Start

```bash
python -m venv venv
venv\Scripts\activate        # Windows (source venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
python src/main.py
```

## The Lab Workflow

Pick a difficulty (or a random scenario), type `START LAB`, then work the incident in four phases:

1. **Hypothesis Formulation** - You receive an incident brief, an investigation
   objective, and intentionally incomplete initial evidence. Formulate at least two
   competing hypotheses.
2. **Prioritization** - Rank your hypotheses and record, for each: why it deserves
   its rank, the evidence that would confirm it, the evidence that would falsify it,
   and how you plan to investigate it.
3. **Investigation** - Work your hypotheses in priority order. Request evidence
   freely (DNS checks, ICMP, TCP analysis, firewall state, logs, ...). Supporting
   commands: `HELP` (progressive scenario hints), `STATUS` (live progress table),
   `CONCLUDE` (CONFIRM / REJECT / INCONCLUSIVE), `SKIP`. Evidence always stays
   consistent with the hidden root cause; investigating the wrong area returns a
   healthy baseline, never a leak.
4. **Final Diagnosis** - Submit your root cause, key evidence, fault domain, impact,
   remediation, and confidence. The simulator scores your RCA against its hidden
   ground truth, then reveals the official failure chain.

## Scenario Bank

| # | Scenario | Difficulty | Fault Domain |
|---|----------|------------|--------------|
| 1 | Host Cannot Connect to Application Server | Beginner | Layer 3/4 |
| 2 | Application Intermittently Disconnects | Intermediate | Layer 4 |
| 3 | Connection Unusually Slow | Intermediate | Layer 2/4 |
| 4 | DNS Works but HTTPS Fails | Advanced | Layer 4/5 |
| 5 | Server Responds but App Fails | Advanced | Layer 7 |
| 6 | Large Transfers Stall Over the VPN | Expert | Layer 3 |
| 7 | Branch Office Cannot Reach the Application Subnet | Beginner | Layer 3 |
| 8 | TCP Handshake Succeeds but HTTPS Fails | Advanced | Layer 5/6 |
| 9 | Application Stalls Only During Large Transfers | Intermediate | Layer 1/2 |
| 10 | Application Fails for Some Users but Not Others | Advanced | Layer 4/7 |
| 11 | Application Turns Unusable Every Evening | Advanced | Layer 2/3 |
| 12 | Connections to the Server Fail in Waves | Intermediate | Layer 2 |

Lab identities - hosts, IPs, subnets, MAC addresses, ports, topologies, and incident
times - are randomized per run, so no two labs are identical.

## Project Layout

```
NetTSimulator/
├── src/
│   ├── main.py             # Entry point; orchestrates the four lab phases
│   ├── lab_engine/
│   │   ├── models.py       # Data models (Hypothesis, Evidence, IncidentScenario, LabScore)
│   │   └── engine.py       # LabEngine: investigation, evidence, hints, scoring
│   ├── scenarios/
│   │   └── generator.py    # Scenario templates + randomized lab identities
│   └── utils/
│       └── ui.py           # Rich-based terminal UI
├── tests/                  # Unit tests: python -m unittest discover -s tests
└── prompt/                 # Original simulator design prompt
```

For architecture details and instructions for adding new scenarios, see [DEVELOPMENT.md](DEVELOPMENT.md).
