import subprocess
import re
import sys
from rich.console import Console
from rich.table import Table

# --- CONFIGURATION ---
# Map User's "Actual Names" to F1 Driver Codes
NAME_MAP = {
    "Lando": "NOR", "Max": "VER", "George": "RUS", "Oscar": "PIA",
    "Charles": "LEC", "Carlos": "SAI", "Lewis": "HAM", 
    "Kimi": "ANT", "Nico": "HUL", "Issac": "HAD", "Isaac": "HAD"
}

# The 2025 Schedule & Results (From your table)
# Format: (Round, GP_Name, Actual_Winner_Name)
RACES = [
    (1, "Australia", "Lando"),
    (2, "China", "Oscar"),       # Sprint
    (3, "Japan", "Max"),
    (4, "Bahrain", "Oscar"),
    (5, "Saudi Arabia", "Oscar"),
    (6, "Miami", "Oscar"),       # Sprint
    (7, "Emilia Romagna", "Max"),
    (8, "Monaco", "Lando"),
    (9, "Spain", "Oscar"),
    (10, "Canada", "George"),
    (11, "Austria", "Lando"),
    (12, "Great Britain", "Lando"),
    (13, "Belgium", "Oscar"),    # Sprint
    (14, "Hungary", "Lando"),
    (15, "Netherlands", "Oscar"),
    (16, "Italy", "Max"),
    (17, "Azerbaijan", "Max"),
    (18, "Singapore", "George"),
    (19, "United States", "Max"), # Austin (Sprint)
    (20, "Mexico", "Lando"),
    (21, "Brazil", "Lando"),      # Sprint
    (22, "Las Vegas", "Max"),
    (23, "Qatar", "Max"),         # Sprint
    (24, "Abu Dhabi", "Max")
]

# Known Sprint Rounds in 2025 (Run FP1 instead of FP2)
SPRINT_ROUNDS = ["China", "Miami", "Belgium", "United States", "Brazil", "Qatar"]

def get_prediction(gp_name):
    """Runs the v11 predictor and parses the winner."""
    
    # 1. Determine Physics Session
    phys_session = "FP1" if gp_name in SPRINT_ROUNDS else "FP2"
    
    # Run Physics Analysis
    # We suppress output to keep the benchmark clean
    subprocess.run(
        [sys.executable, "f1_predictor_v11.py", "--year", "2025", "--gp", gp_name, "--session", phys_session],
        capture_output=True, text=True
    )

    # 2. Run Race Simulation (Q)
    result = subprocess.run(
        [sys.executable, "f1_predictor_v11.py", "--year", "2025", "--gp", gp_name, "--session", "Q"],
        capture_output=True, text=True
    )
    
    # 3. Parse the Output
    output = result.stdout
    # Regex to find the top driver in the table: "│ DRV    │ XX.X% │"
    # We look for the first row after the header
    match = re.search(r"│ ([A-Z]{3})\s+│ \d+\.\d+%", output)
    
    if match:
        return match.group(1)
    return "ERR"

def main():
    console = Console()
    table = Table(title="2025 Season Validation Test (v11 Engine)")
    
    table.add_column("Rd", justify="right", style="cyan", no_wrap=True)
    table.add_column("GP Name", style="magenta")
    table.add_column("Actual", style="green")
    table.add_column("Predicted", style="yellow")
    table.add_column("Result", justify="center")

    correct_count = 0

    with console.status("[bold green]Running Season Simulation...[/bold green]") as status:
        for round_num, gp, winner_name in RACES:
            status.update(f"Simulating Rd {round_num}: {gp}...")
            
            # Run Model
            predicted_code = get_prediction(gp)
            
            # Validate
            actual_code = NAME_MAP.get(winner_name, "???")
            
            is_match = (predicted_code == actual_code)
            if is_match:
                correct_count += 1
                result_str = "[bold green]PASS[/bold green]"
            else:
                result_str = "[bold red]FAIL[/bold red]"
                
            table.add_row(
                str(round_num), 
                gp, 
                f"{winner_name} ({actual_code})", 
                predicted_code, 
                result_str
            )

    console.print(table)
    
    accuracy = (correct_count / len(RACES)) * 100
    console.print(f"\n[bold]Final Model Accuracy: {accuracy:.1f}%[/bold]")

if __name__ == "__main__":
    main()
