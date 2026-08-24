# Development Guide

## Quick Start

1. **Activate virtual environment:**
   ```bash
   venv\Scripts\activate  # Windows
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the simulator:**
   ```bash
   python src/main.py
   ```

## Architecture

### Layered Design

```
UI Layer (TerminalUI)
    ↓
Application Layer (main.py)
    ↓
Engine Layer (LabEngine)
    ↓
Models Layer (Hypothesis, Evidence, Scenario)
    ↓
Generator Layer (ScenarioGenerator)
```

### Data Flow

1. **Scenario Generation** → ScenarioGenerator creates incident
2. **Lab Engine Initialization** → LabEngine loads scenario and builds ground truth
3. **Hypothesis Collection** → UI collects and engine registers learner's hypotheses
4. **Prioritization** → Learner ranks hypotheses; engine stores priorities
5. **Investigation Loop** → For each hypothesis:
   - Learner requests evidence via UI
   - Engine generates evidence consistent with root cause
   - Learner evaluates hypothesis
   - Engine records status and moves to next
6. **Final Diagnosis** → Learner submits RCA; engine scores and compares

## Extending the System

### Adding New Scenarios

Edit `src/scenarios/generator.py`:

```python
SCENARIO_TEMPLATES = [
    # ... existing scenarios ...
    {
        "title": "Your Incident Title",
        "incident_id": "INC-2026-NNN",
        "environment": "Production - Your Location",
        "symptom": "User-reported issue",
        "impact": "Business impact",
        "difficulty": "beginner|intermediate|advanced",
        "root_cause": "The actual cause",
        "fault_domain": "Layer/Component",
        "protocols": ["PROTOCOL1", "PROTOCOL2"],
        "port_options": [443],            # one is picked at random per lab
        "protocols_map": {443: [...]},    # optional per-port protocol variants
        "topology_options": ["...", "..."],  # one is picked at random per lab
        "fault_keywords": ["..."],        # words that mark a hypothesis as the true fault
        "remediation": "...",
        "failure_chain": "...",
        "evidence": {"dns": "...", "tcp": "...", ...},  # per-category ground truth
    },
]
```

Host identities (client/server names and IPs, DNS resolver, firewall IP) and the
incident time are randomized per lab. Use placeholders (`{client_ip}`, `{server_ip}`,
`{server_name}`, `{dns_server}`, `{firewall_ip}`, `{app_port}`) in `root_cause`,
`remediation`, `failure_chain`, `fault_keywords` and `evidence` strings so they stay
consistent with the generated identity set.

### Customizing Evidence Generation

Evidence lives in each scenario template's `evidence` dict, keyed by
category (`dns`, `icmp`, `tcp`, `tls`, `http`, `application`, `firewall`,
`l2`, `performance`, `logs`). Learner queries are mapped to categories in
`LabEngine._map_query_to_category()` (`QUERY_CATEGORY_KEYWORDS` in
`src/lab_engine/engine.py`) — add keywords there if you introduce a new
category:

```python
QUERY_CATEGORY_KEYWORDS = [
    (("your", "keywords"), "your_category"),
    ...
]
```

Categories without template evidence fall back to a baseline
"no anomalies" observation, keeping wrong-area investigations consistent
with the root cause.

### Enhancing the Scoring System

Modify `LabEngine._score_final_diagnosis()` in `src/lab_engine/engine.py`:

```python
def _score_final_diagnosis(self, ...) -> LabScore:
    """Score the final diagnosis with custom logic."""
    score = LabScore()
    # Your scoring logic here
    return score
```

## Testing

Run the test suite:

```bash
python -m unittest discover -s tests
```

Run individual modules:

```bash
# Test scenario generation
python -c "from scenarios.generator import ScenarioGenerator; s = ScenarioGenerator.generate_scenario(); print(s.title)"

# Test lab engine
python -c "from scenarios.generator import ScenarioGenerator; from lab_engine.engine import LabEngine; s = ScenarioGenerator.generate_scenario(); e = LabEngine(s); print(e.session.scenario.incident_id)"
```

## Code Organization Best Practices

- **Models** (`lab_engine/models.py`): Data structures only
- **Engine** (`lab_engine/engine.py`): Business logic and investigation workflow
- **Generator** (`scenarios/generator.py`): Scenario and evidence creation
- **UI** (`utils/ui.py`): Terminal interface, no business logic
- **Main** (`src/main.py`): Orchestrates workflow

## Debugging

Enable verbose output by adding debug prints:

```python
import sys
print(f"DEBUG: {variable_name}", file=sys.stderr)
```

Run with stderr visible:
```bash
python src/main.py 2>&1
```

## Performance Considerations

- Scenario generation is random but fast (<10ms)
- Evidence generation is O(1)
- Investigation history grows linearly with actions
- UI rendering uses Rich's optimized pipeline

## Common Issues

### Import Errors

Ensure `src/` is in `sys.path`:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
```

### Missing Dependencies

```bash
pip install -r requirements.txt
```

### Terminal Display Issues

Rich supports most modern terminals. If display issues occur:
```python
console = Console(force_terminal=True, width=120)
```

---

For more information, see the main README.md
