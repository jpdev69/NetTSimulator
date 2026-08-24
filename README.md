# NetTSimulator - Network Troubleshooting Training Lab Simulator

A terminal-based, interactive lab simulator for learning hypothesis-driven network troubleshooting using Wireshark methodologies.

## Overview

This simulator trains you to:
- **Observe** → Define the problem
- **Form hypotheses** → Prioritize
- **Investigate systematically** → Gather evidence
- **Confirm/reject hypotheses** → Isolate the fault domain
- **Determine root cause** → Produce an evidence-based RCA

## Project Structure

```
NetTSimulator/
├── src/
│   ├── main.py                 # Application entry point
│   ├── lab_engine/             # Core investigation logic
│   │   ├── __init__.py
│   │   ├── models.py          # Data models (Hypothesis, Evidence, etc.)
│   │   └── engine.py          # LabEngine - manages investigations
│   ├── scenarios/              # Scenario generation
│   │   ├── __init__.py
│   │   └── generator.py       # ScenarioGenerator
│   └── utils/                  # UI and utilities
│       ├── __init__.py
│       └── ui.py              # TerminalUI - Rich-based terminal UI
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Installation

1. **Create and activate virtual environment:**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   # or
   source venv/bin/activate  # On macOS/Linux
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the lab simulator:
```bash
python src/main.py
```

## Lab Workflow

### Phase 1: Hypothesis Formulation
You receive:
- Incident scenario (what happened)
- Investigation objective
- Initial evidence (incomplete by design)

You formulate multiple hypotheses about possible causes.

### Phase 2: Hypothesis Prioritization
For each hypothesis, you provide:
- Priority ranking (1 = investigate first)
- Reason for the priority
- Expected evidence if true
- Evidence that would falsify it
- Investigation method

### Phase 3: Interactive Investigation
You investigate hypotheses one-by-one according to priority:
- Request specific evidence (DNS checks, TCP analysis, packet capture review, etc.)
- Simulator provides realistic evidence consistent with the root cause
- Based on evidence, you confirm, reject, or mark as inconclusive
- Move to the next hypothesis

### Phase 4: Final Diagnosis
You submit your final root cause analysis including:
- **Root Cause:** What actually caused the problem
- **Evidence:** Which observations prove it
- **Fault Domain:** Which layer/component is responsible
- **Impact:** What the fault caused
- **Remediation:** How to fix it
- **Confidence:** Your confidence level (Low/Medium/High)

## Scenarios

The simulator includes realistic network incident scenarios:

1. **Host Cannot Connect to Application Server** (Beginner)
   - Issue: DNS failure
   - Fault Domain: Layer 3/4

2. **Application Intermittently Disconnects** (Intermediate)
   - Issue: Firewall session timeout
   - Fault Domain: Layer 4

3. **Connection Unusually Slow** (Intermediate)
   - Issue: TCP window size misconfiguration
   - Fault Domain: Layer 2/4

4. **DNS Works but HTTPS Fails** (Advanced)
   - Issue: Firewall blocking port 443
   - Fault Domain: Layer 4/5

5. **Server Responds but App Fails** (Advanced)
   - Issue: Application queue overflow
   - Fault Domain: Layer 7

## Core Components

### models.py
Defines data structures:
- `Hypothesis` - Tracks status, evidence, and investigation details
- `Evidence` - Represents gathered information
- `IncidentScenario` - The network problem to investigate
- `InvestigationSession` - State of ongoing investigation
- `LabScore` - Scoring rubric (0-100 points)

### engine.py
Main investigation logic:
- `register_hypotheses()` - Record learner's hypotheses
- `prioritize_hypotheses()` - Set priorities and investigation plans
- `investigate_hypothesis()` - Conduct investigation and generate evidence
- `evaluate_hypothesis()` - Confirm/reject based on evidence
- `submit_final_diagnosis()` - Score final RCA
- `get_hint()` - Progressive hint system (4 levels)

### generator.py
Scenario creation:
- `generate_scenario()` - Create random network incident
- `create_initial_evidence()` - Initial evidence items

### ui.py (TerminalUI)
Rich terminal interface:
- `display_scenario()` - Show incident details
- `prompt_for_hypotheses()` - Collect learner's hypotheses
- `prompt_for_prioritization()` - Collect priority rankings and reasoning
- `display_evidence()` - Show investigation results
- `prompt_for_final_diagnosis()` - Collect final RCA

## Guiding Principles

1. **Never reveal the root cause prematurely** - The simulator only provides evidence relevant to the learner's investigation
2. **Allow wrong investigations** - Troubleshooting is not linear; learners may investigate low-priority hypotheses
3. **Evidence must be consistent** - All packet captures, logs, and timestamps agree with the underlying root cause
4. **Evidence is realistic** - Observations match real Wireshark behavior
5. **No quiz questions** - The simulator simulates an actual incident, not teaching the tools

## Features

- ✓ Terminal-based interactive lab environment
- ✓ 5 realistic network scenarios (beginner to advanced)
- ✓ Hypothesis tracking with status management
- ✓ Evidence-driven investigation workflow
- ✓ Progressive hint system
- ✓ Scoring rubric (100-point scale)
- ✓ Root Cause Analysis comparison
- ✓ Rich terminal UI with tables, panels, and formatting

## Future Enhancements

- PCAP file generation for scenarios
- More realistic Wireshark filter teaching
- Advanced scenarios with simultaneous multiple faults
- Multiplayer investigation sessions
- Session history and replay
- Integration with actual Wireshark captures
- Machine learning-based hint generation

## Dependencies

- `rich==13.7.0` - Terminal UI and formatting
- `pydantic==2.5.0` - Data validation
- `pyyaml==6.0.1` - Configuration (optional)

## Learning Outcomes

After completing labs, you will understand:
- Hypothesis-driven troubleshooting methodology
- Protocol layer analysis (Layers 1-7)
- Evidence-based root cause analysis
- Investigation prioritization strategies
- Common network fault patterns
- Efficient Wireshark usage

## License

Educational use only.

---

**Happy troubleshooting! 🔍**
