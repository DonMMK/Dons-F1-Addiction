import subprocess
import re
import sys
import os
from rich.console import Console
from rich.table import Table
from rich.live import Live

# --- CONFIGURATION ---
# 2024 Official Winners (Round, GP Name, Winner Code)
# Note: Belgium winner is HAM (RUS was DSQ)
RACES_2024 = [
    (1, "Bahrain", "VER"),
    (2, "Saudi Arabia", "VER"),
    (3, "Australia", "SAI"),
    (4, "Japan", "VER"),
    (5, "China", "VER"),          # Sprint
    (6, "Miami", "NOR"),          # Sprint
    (7, "Emilia Romagna", "VER"),
    (8, "Monaco", "LEC"),
    (9, "Canada", "VER"),
    (10, "Spain", "VER"),
    (11, "Austria", "RUS"),       # Sprint (VER/NOR Crash)
    (12, "Great Britain", "HAM"),
    (13, "Hungary", "PIA"),
    (14, "Belgium", "HAM"),
    (15, "Netherlands", "NOR"),
    (16, "Italy", "LEC"),
    (17, "Azerbaijan", "PIA"),
    (18, "Singapore", "NOR"),
    (19, "United States", "LEC"), # Austin (Sprint)
    (20, "Mexico", "SAI"),
    (21, "Brazil", "VER"),        # Sprint
    (22, "Las Vegas", "RUS"),
    (23, "Qatar", "VER"),         # Sprint
    (24, "Abu Dhabi", "NOR")
]

# Sprint weekends use FP1 for Long Runs
SPRINT_ROUNDS = ["China", "Miami", "Austria", "United States", "Brazil", "Qatar"]

def run_step(gp_name, session):
    """Runs a single step of the predictor."""
    try:
        result = subprocess.run(
            [sys.executable, "f1_predictor_v11.py", "--year", "2024", "--gp", gp_name, "--session", session],
            capture_output=True, text=True, check=False
        )
        return result.stdout
    except Exception as e:
        return ""

def parse_winner(output):
    """Extracts the winner from the v11 CLI output."""
    # Regex looks for: │ VER    │ 45.2% │
    match = re.search(r"│ ([A-Z]{3})\s+│ \d+\.\d+%", output)
    if match:
        return match.group(1)
    return "ERR"

def main():
    console = Console()
    
    # Create the display table
    table = Table(title="2024 Season Validation Test (v11 Engine)")
    table.add_column("Rd", justify="right", style="cyan", no_wrap=True)
    table.add_column("GP Name", style="white")
    table.add_column("Real Winner", style="green")
    table.add_column("Model Prediction", style="yellow")
    table.add_column("Result", justify="center")

    correct_count = 0
    total_races = len(RACES_2024)

    # Use Live display to update table row by row
    with Live(table, refresh_per_second=4):
        for round_num, gp, actual_winner in RACES_2024:
            
            # 1. Determine Practice Session (FP1 for Sprint, FP2 for Standard)
            # We MUST run this to generate the physics file
            practice_session = "FP1" if gp in SPRINT_ROUNDS else "FP2"
            
            # Run Physics Gen (Hidden)
            run_step(gp, practice_session)
            
            # 2. Run Prediction (Quali Anchor)
            q_output = run_step(gp, "Q")
            predicted_winner = parse_winner(q_output)
            
            # 3. Score
            if predicted_winner == actual_winner:
                res_style = "[bold green]PASS[/bold green]"
                correct_count += 1
            else:
                # Highlight errors
                if predicted_winner == "ERR":
                    res_style = "[bold red]ERROR[/bold red]"
                else:
                    res_style = "[bold red]FAIL[/bold red]"

            # Update Table
            table.add_row(
                str(round_num),
                gp,
                actual_winner,
                predicted_winner,
                res_style
            )

    # Final Score
    accuracy = (correct_count / total_races) * 100
    
    console.print("\n[bold]--------------------------------------------------[/bold]")
    console.print(f"[bold]FINAL ACCURACY: {accuracy:.1f}% ({correct_count}/{total_races})[/bold]")
    console.print("[bold]--------------------------------------------------[/bold]")
    
    if accuracy < 50:
        console.print("[yellow]Analysis: The model is struggling with 2024 variance.[/yellow]")
        console.print("Potential issues: \n1. Austria (Crash prevented Max win)\n2. Belgium (DSQ changed winner)\n3. Strategy wins (Monza/Ferrari) not captured by Quali pace.")
    else:
        console.print("[green]Analysis: Strong correlation with historical results.[/green]")

if __name__ == "__main__":
    main()
