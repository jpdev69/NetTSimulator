"""Terminal UI for the Wireshark lab simulator."""
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich.text import Text

MIN_HYPOTHESES = 2


class TerminalUI:
    """Rich terminal UI for lab simulator."""

    def __init__(self):
        """Initialize the terminal UI."""
        self.console = Console()

    def prompt_for_lab_command(self) -> bool:
        """Prompt for the lab start command.

        Returns:
            True only when the learner types START LAB
        """
        command = Prompt.ask(
            "Type [bold]START LAB[/bold] to begin the investigation"
        )
        return command.strip().upper() == "START LAB"

    def prompt_for_difficulty(self) -> Optional[str]:
        """Prompt for the desired difficulty level.

        Returns:
            Difficulty string, or None for a random scenario
        """
        difficulty = Prompt.ask(
            "Select difficulty",
            choices=["beginner", "intermediate", "advanced", "random"],
            default="random",
        )
        return None if difficulty == "random" else difficulty

    def display_welcome(self) -> None:
        """Display welcome screen."""
        title = Text(
            "Network Troubleshooting Lab Simulator",
            style="bold cyan",
            justify="center",
        )
        subtitle = Text(
            "Learn hypothesis-driven network troubleshooting with Wireshark",
            style="italic white",
            justify="center",
        )

        self.console.print()
        self.console.print(title)
        self.console.print(subtitle)
        self.console.print()

    def display_scenario(
        self,
        incident_id: str,
        title: str,
        environment: str,
        symptom: str,
        business_impact: str,
    ) -> None:
        """Display incident scenario."""
        scenario_text = f"""
**Incident ID:** {incident_id}

**Environment:** {environment}

**User-Reported Symptom:** {symptom}

**Business Impact:** {business_impact}
"""
        panel = Panel(
            Markdown(scenario_text),
            title="[bold]Incident Scenario[/bold]",
            border_style="cyan",
        )
        self.console.print(panel)

    def display_objective(self, objective: str) -> None:
        """Display investigation objective."""
        panel = Panel(
            Markdown(objective),
            title="[bold]Investigation Objective[/bold]",
            border_style="green",
        )
        self.console.print(panel)

    def display_initial_evidence(self, evidence_items: List[dict]) -> None:
        """Display initial evidence."""
        table = Table(title="Initial Evidence", border_style="yellow")
        table.add_column("Category", style="cyan")
        table.add_column("Details", style="white")

        for item in evidence_items:
            table.add_row(item["category"], item["description"])

        self.console.print(table)

    def prompt_for_hypotheses(self) -> List[str]:
        """Prompt user to enter hypotheses.

        The lab requires multiple hypotheses: a single-cause guess is
        not a differential diagnosis.

        Returns:
            List of hypothesis strings
        """
        self.console.print(
            "\n[bold cyan]Formulate Your Hypotheses[/bold cyan]\n"
        )
        self.console.print(
            "Based on the scenario and initial evidence, what are the possible causes?\n"
            f"Provide at least {MIN_HYPOTHESES} hypotheses.\n"
        )

        hypotheses = []
        while True:
            hyp = Prompt.ask(
                f"Hypothesis {len(hypotheses) + 1} (or [bold]DONE[/bold] to finish)"
            )
            if hyp.upper() == "DONE":
                if len(hypotheses) >= MIN_HYPOTHESES:
                    break
                self.console.print(
                    f"[red]Enter at least {MIN_HYPOTHESES} hypotheses "
                    f"({len(hypotheses)} so far).[/red]"
                )
            else:
                hypotheses.append(hyp)

        return hypotheses

    def display_hypotheses_table(
        self, hypotheses: List[dict]
    ) -> None:
        """Display hypotheses table."""
        table = Table(title="Hypotheses Summary", border_style="magenta")
        table.add_column("ID", style="cyan")
        table.add_column("Hypothesis", style="white")
        table.add_column("Status", style="yellow")

        for hyp in hypotheses:
            table.add_row(
                str(hyp["id"]), hyp["hypothesis"], hyp.get("status", "NOT_TESTED")
            )

        self.console.print(table)

    def prompt_for_prioritization(self, hypothesis_count: int) -> dict:
        """Prompt user to prioritize hypotheses.

        Args:
            hypothesis_count: Number of hypotheses to prioritize

        Returns:
            Dictionary with prioritization details
        """
        self.console.print(
            "\n[bold cyan]Prioritize Your Hypotheses[/bold cyan]\n"
        )
        self.console.print(
            "For each hypothesis, provide:\n"
            "  - Priority number (1 = highest priority)\n"
            "  - Reason for priority\n"
            "  - Expected evidence if true\n"
            "  - Evidence that would falsify it\n"
            "  - Investigation method\n"
        )

        priorities = []
        reasons = []
        expected = []
        falsifying = []
        methods = []

        for i in range(hypothesis_count):
            self.console.print(f"\n[yellow]Hypothesis {i + 1}:[/yellow]")
            priorities.append(int(Prompt.ask("  Priority")))
            reasons.append(Prompt.ask("  Reason for priority"))
            expected.append(Prompt.ask("  Expected evidence"))
            falsifying.append(Prompt.ask("  Falsifying evidence"))
            methods.append(Prompt.ask("  Investigation method"))

        return {
            "priorities": priorities,
            "reasons": reasons,
            "expected": expected,
            "falsifying": falsifying,
            "methods": methods,
        }

    def display_investigation_status(self, status: dict) -> None:
        """Display investigation status table."""
        table = Table(
            title="Investigation Status", border_style="magenta"
        )
        table.add_column("Priority", style="cyan")
        table.add_column("Hypothesis", style="white")
        table.add_column("Status", style="yellow")
        table.add_column("Evidence Count", style="green")

        for hyp in status["hypotheses"]:
            table.add_row(
                str(hyp["priority"]),
                hyp["hypothesis"],
                hyp["status"],
                str(len(hyp.get("evidence", []))),
            )

        self.console.print(table)

    def prompt_for_investigation(self) -> str:
        """Prompt user for investigation action.

        Returns:
            Investigation query
        """
        self.console.print("\n[bold cyan]Conduct Investigation[/bold cyan]\n")
        query = Prompt.ask(
            "What would you like to investigate? (or [bold]HELP[/bold] for hints)"
        )
        return query

    def display_evidence(self, evidence: dict) -> None:
        """Display evidence from investigation."""
        panel = Panel(
            evidence["description"],
            title=f"[bold]Evidence - {evidence['category'].upper()}[/bold]",
            border_style="green",
        )
        self.console.print(panel)

    def prompt_for_hypothesis_evaluation(self) -> str:
        """Prompt user to evaluate current hypothesis.

        Returns:
            Conclusion: CONFIRM, REJECT, or INCONCLUSIVE
        """
        self.console.print("\n[bold cyan]Evaluate Hypothesis[/bold cyan]\n")
        conclusion = Prompt.ask(
            "Based on the evidence, do you [bold]CONFIRM[/bold], [bold]REJECT[/bold], or find it [bold]INCONCLUSIVE[/bold]?",
            choices=["CONFIRM", "REJECT", "INCONCLUSIVE"],
        )
        return conclusion

    def prompt_for_final_diagnosis(self) -> dict:
        """Prompt user for final diagnosis.

        Returns:
            Dictionary with diagnosis details
        """
        self.console.print("\n[bold magenta]Submit Final Diagnosis[/bold magenta]\n")

        diagnosis = {
            "root_cause": Prompt.ask("Root Cause"),
            "evidence": Prompt.ask("Key Evidence"),
            "fault_domain": Prompt.ask("Fault Domain (Layer/Component)"),
            "impact": Prompt.ask("What did this fault cause?"),
            "remediation": Prompt.ask("Recommended Remediation"),
            "confidence": Prompt.ask(
                "Confidence Level",
                choices=["Low", "Medium", "High"],
            ),
        }

        return diagnosis

    def display_final_score(self, score_details: dict) -> None:
        """Display final scoring results."""
        feedback = score_details["feedback"]
        panel = Panel(
            Markdown(f"```\n{feedback}\n```"),
            title="[bold green]Lab Scoring Results[/bold green]",
            border_style="green",
        )
        self.console.print(panel)

        if score_details.get("is_correct"):
            self.console.print(
                "\n[bold green]✓ Excellent diagnosis![/bold green]"
            )
        else:
            self.console.print(
                "\n[bold yellow]△ Review the official diagnosis for learning points.[/bold yellow]"
            )

    def display_official_rca(self, rca: dict) -> None:
        """Display official Root Cause Analysis."""
        failure_chain = rca.get("failure_chain", "")
        failure_chain_section = (
            f"\n**Failure Chain:**\n```\n{failure_chain}\n```\n" if failure_chain else ""
        )
        rca_text = f"""
## Root Cause Summary

**Root Cause:** {rca['root_cause']}

**Fault Domain:** {rca['fault_domain']}

**Evidence:**
{rca.get('evidence', 'N/A')}
{failure_chain_section}
**Remediation:**
{rca.get('remediation', 'N/A')}
"""
        panel = Panel(
            Markdown(rca_text),
            title="[bold]Official Root Cause Analysis[/bold]",
            border_style="cyan",
        )
        self.console.print(panel)

    def display_error(self, message: str) -> None:
        """Display error message."""
        self.console.print(f"[bold red]Error: {message}[/bold red]")

    def display_info(self, message: str) -> None:
        """Display info message."""
        self.console.print(f"[bold blue]ℹ {message}[/bold blue]")

    def display_success(self, message: str) -> None:
        """Display success message."""
        self.console.print(f"[bold green]✓ {message}[/bold green]")

    def display_hint(self, hint: str) -> None:
        """Display hint message."""
        panel = Panel(
            Markdown(hint),
            title="[bold yellow]Hint[/bold yellow]",
            border_style="yellow",
        )
        self.console.print(panel)

    def prompt_continue(self, message: str = "Continue?") -> bool:
        """Prompt user to continue.

        Args:
            message: Prompt message

        Returns:
            True if user wants to continue
        """
        return Confirm.ask(message)
