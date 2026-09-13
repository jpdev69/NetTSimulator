"""Main application entry point."""
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from lab_engine.engine import LabEngine
from lab_engine.models import Hypothesis
from scenarios.generator import ScenarioGenerator
from utils.ui import TerminalUI


def main():
    """Main entry point for the lab simulator."""
    # Avoid crashes on consoles with limited charsets (e.g. Windows cp1252)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass

    # Initialize UI
    ui = TerminalUI()
    ui.display_welcome()

    # Wait for the learner to start the lab
    difficulty = ui.prompt_for_difficulty()
    while not ui.prompt_for_lab_command():
        ui.display_info("Command not recognized. The lab begins when you type START LAB.")

    # Generate scenario
    scenario = ScenarioGenerator.generate_scenario(difficulty=difficulty)
    engine = LabEngine(scenario)

    # Display scenario and objective
    ui.display_scenario(
        scenario.incident_id,
        scenario.title,
        scenario.environment,
        scenario.user_reported_symptom,
        scenario.business_impact,
    )

    objective = f"""
Determine why the issue is occurring and identify the network component or protocol responsible.

**Protocols Involved:** {', '.join(scenario.protocols)}

**Ports:** {', '.join(map(str, scenario.relevant_ports))}

**Network Topology:** {scenario.network_topology}
"""
    ui.display_objective(objective)

    # Display initial evidence
    initial_evidence = ScenarioGenerator.create_initial_evidence(scenario)
    evidence_items = [
        {"category": e.category, "description": e.description}
        for e in initial_evidence
    ]
    ui.display_initial_evidence(evidence_items)

    # Phase 1: Hypothesis Formulation
    ui.console.print("\n[bold cyan]PHASE 1: Hypothesis Formulation[/bold cyan]\n")
    hypotheses = ui.prompt_for_hypotheses()
    engine.register_hypotheses(hypotheses)

    ui.display_hypotheses_table(
        [
            {
                "id": i,
                "hypothesis": h,
                "status": "NOT_TESTED",
            }
            for i, h in enumerate(hypotheses)
        ]
    )

    # Phase 2: Hypothesis Prioritization
    ui.console.print("\n[bold cyan]PHASE 2: Hypothesis Prioritization[/bold cyan]\n")
    prioritization = ui.prompt_for_prioritization(len(hypotheses))
    engine.prioritize_hypotheses(
        prioritization["priorities"],
        prioritization["reasons"],
        prioritization["expected"],
        prioritization["falsifying"],
        prioritization["methods"],
    )

    # Phase 3: Interactive Investigation
    ui.console.print("\n[bold cyan]PHASE 3: Interactive Investigation[/bold cyan]\n")
    ui.display_info(
        "Investigate each hypothesis in priority order. Gather as much "
        "evidence as you need, then CONCLUDE - or SKIP the hypothesis."
    )

    for hyp in sorted(engine.session.hypotheses, key=lambda h: h.priority):
        ui.console.print(
            f"\n[bold yellow]Investigating: {hyp.hypothesis}[/bold yellow]\n"
        )

        while True:
            query = ui.prompt_for_investigation()
            command = query.strip().upper()

            if not command:
                ui.display_info(
                    "Enter an investigation query, or one of: "
                    "HELP, STATUS, CONCLUDE, SKIP."
                )
                continue

            if command == "HELP":
                hint_level = ui.prompt_for_hint_level()
                hint = engine.get_hint(hint_level)
                ui.display_hint(hint)
                continue

            if command == "STATUS":
                ui.display_investigation_status(engine.get_investigation_status())
                continue

            if command == "SKIP":
                engine.skip_hypothesis(hyp.id)
                break

            if command == "CONCLUDE":
                conclusion = ui.prompt_for_hypothesis_evaluation()
                eval_result = engine.evaluate_hypothesis(hyp.id, conclusion)
                ui.display_success(
                    f"Hypothesis marked as: {eval_result['recorded_status']}"
                )
                if conclusion == "INCONCLUSIVE":
                    continue
                break

            # Conduct investigation
            result = engine.investigate_hypothesis(hyp.id, query)
            if "error" in result:
                ui.display_error(result["error"])
                continue

            evidence = result["evidence"]
            ui.display_evidence(
                {
                    "category": evidence.category,
                    "description": evidence.description,
                }
            )

    # Phase 4: Final Diagnosis
    ui.console.print("\n[bold cyan]PHASE 4: Final Diagnosis[/bold cyan]\n")
    ui.display_investigation_status(engine.get_investigation_status())

    diagnosis = ui.prompt_for_final_diagnosis()

    # Submit diagnosis
    result = engine.submit_final_diagnosis(
        diagnosis["root_cause"],
        diagnosis["evidence"],
        diagnosis["fault_domain"],
        diagnosis["impact"],
        diagnosis["remediation"],
        diagnosis["confidence"],
    )

    # Display results
    ui.display_final_score(result)

    # Display official RCA
    official_rca = {
        "root_cause": result["official_root_cause"],
        "fault_domain": result["official_fault_domain"],
        "evidence": result["official_evidence"],
        "remediation": result["official_remediation"],
        "failure_chain": result["official_failure_chain"],
    }
    ui.display_official_rca(official_rca)

    # Completion
    ui.console.print("\n[bold green]Lab Complete![/bold green]\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nLab interrupted by user.")
        sys.exit(0)
