import subprocess
import re
import sys
from rich.console import Console
from rich.table import Table
from rich.live import Live

# --- CONFIGURATION 2023 ---
# Official Winners (Round, GP Name, Winner Code)
# Note: Imola was cancelled in 2023
RACES_2023 = [
    (1, "Bahrain", "VER"),
    (2, "Saudi Arabia", "PER"),
    (3, "Australia", "VER"),
    (4, "Azerbaijan", "PER"),     # Sprint
    (5, "Miami", "VER"),
    (6, "Monaco", "VER"),
    (7, "Spain", "VER"),
    (8, "Canada", "VER"),
    (9, "Austria", "VER"),        # Sprint
    (10, "Great Britain", "VER"),
    (11, "Hungary", "VER"),
    (12, "Belgium", "VER"),       # Sprint
    (13, "Netherlands", "VER"),
    (14, "Italy", "VER"),
    (15, "Singapore", "SAI"),     # The only non-RB win
    (16, "Japan", "VER"),
    (17, "Qatar", "VER"),         # Sprint
    (18, "United States", "VER"), # Austin (Sprint)
    (19, "Mexico", "VER"),
    (20, "Brazil", "VER"),        # Sprint
    (21, "Las Vegas", "VER"),
    (22, "Abu Dhabi", "VER")
]

# Sprint weekends use FP1 for Long Runs (FP2 is Parc Ferme/Useless)
SPRINT_ROUNDS = ["Azerbaijan", "Austria", "Belgium", "Qatar", "United States", "Brazil"]

def run_step(gp_name, session):
    """Runs a single step of the predictor."""
    try:
        result = subprocess.run(
            [sys.executable, "f1_predictor_v11.py", "--year", "2023", "--gp", gp_name, "--session", session],
            capture_output=True, text=True, check=False
        )
        return result.stdout
    except Exception as e:
        return ""

def parse_winner(output):
    """Extracts the winner from the v11 CLI output."""
    match = re.search(r"│ ([A-Z]{3})\s+│ \d+\.\d+%", output)
    if match:
        return match.group(1)
    return "ERR"

def main():
    console = Console()
    
    table = Table(title="2023 Season Validation Test (v11 Engine)")
    table.add_column("Rd", justify="right", style="cyan", no_wrap=True)
    table.add_column("GP Name", style="white")
    table.add_column("Real Winner", style="green")
    table.add_column("Model Prediction", style="yellow")
    table.add_column("Result", justify="center")

    correct_count = 0
    total_races = len(RACES_2023)

    # Live display updates row by row
    with Live(table, refresh_per_second=4):
        for round_num, gp, actual_winner in RACES_2023:
            
            # 1. Physics Generation (FP1 for Sprint, FP2 for Standard)
            practice_session = "FP1" if gp in SPRINT_ROUNDS else "FP2"
            run_step(gp, practice_session)
            
            # 2. Prediction (Quali Anchor)
            q_output = run_step(gp, "Q")
            predicted_winner = parse_winner(q_output)
            
            # 3. Score
            if predicted_winner == actual_winner:
                res_style = "[bold green]PASS[/bold green]"
                correct_count += 1
            else:
                if predicted_winner == "ERR":
                    res_style = "[bold red]ERROR[/bold red]"
                else:
                    res_style = "[bold red]FAIL[/bold red]"

            table.add_row(
                str(round_num),
                gp,
                actual_winner,
                predicted_winner,
                res_style
            )

    accuracy = (correct_count / total_races) * 100
    
    console.print("\n[bold]--------------------------------------------------[/bold]")
    console.print(f"[bold]FINAL ACCURACY: {accuracy:.1f}% ({correct_count}/{total_races})[/bold]")
    console.print("[bold]--------------------------------------------------[/bold]")
    
    if accuracy > 80:
        console.print("[green]Analysis: Model correctly identifies dominant car (RB19).[/green]")
    else:
        console.print("[yellow]Analysis: Model is overthinking. In 2023, Pole = Win mostly.[/yellow]")

if __name__ == "__main__":
    main()
