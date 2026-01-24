import os
import json
import argparse
import numpy as np
import pandas as pd
import fastf1
import fastf1.plotting
from sklearn.linear_model import LinearRegression
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import track
from rich import print as rprint

# ==========================================
# 1. CONFIGURATION (Physics & Settings)
# ==========================================
class Config:
    # 2025/2026 Hybrid Settings
    # To test on 2025 data, use 0.035. For 2026, lower to ~0.028.
    FUEL_BURN_PER_KG = 0.035       # Seconds gained per kg burned
    RACE_START_FUEL = 105.0        # kg (Standard for 2022-2025 regs)
    PIT_LOSS_BASELINE = 22.0       # Average pit loss (seconds)
    
    # Simulation Settings
    MONTE_CARLO_RUNS = 1000
    MIN_LAPS_FOR_STINT = 5         # Minimum laps to count as a "Race Sim"
    OUTLIER_THRESHOLD = 1.07       # 107% rule for filtering slow laps

    # Cache Directory
    CACHE_DIR = 'f1_cache'

# ==========================================
# 2. STATE MANAGER (Data Persistence)
# ==========================================
class WeekendState:
    """Manages data persistence across sessions (FP1 -> FP2 -> Quali)."""
    FILE_NAME = "weekend_state.json"

    @staticmethod
    def save_physics_profile(year, gp, profile):
        data = {
            "meta": {"year": year, "gp": gp},
            "profile": profile
        }
        with open(WeekendState.FILE_NAME, 'w') as f:
            json.dump(data, f, indent=4)
        rprint(f"[green]✔ Physics profile saved to {WeekendState.FILE_NAME}[/green]")

    @staticmethod
    def load_physics_profile(year, gp):
        if not os.path.exists(WeekendState.FILE_NAME):
            return None
        
        with open(WeekendState.FILE_NAME, 'r') as f:
            data = json.load(f)
            
        # Verify we are loading data for the correct race
        if data['meta']['year'] != year or data['meta']['gp'] != gp:
            rprint("[yellow]⚠ Warning: Stored data is for a different race. Ignoring.[/yellow]")
            return None
            
        return data['profile']

# ==========================================
# 3. PHYSICS ENGINE (Feature Engineering)
# ==========================================
class TelemetryAnalyzer:
    def __init__(self, year, gp, session_type):
        self.year = year
        self.gp = gp
        self.session_type = session_type
        self.setup_fastf1()

    def setup_fastf1(self):
        if not os.path.exists(Config.CACHE_DIR):
            os.makedirs(Config.CACHE_DIR)
        fastf1.Cache.enable_cache(Config.CACHE_DIR)

    def load_data(self):
        rprint(f"[bold cyan]Loading {self.year} {self.gp} {self.session_type}...[/bold cyan]")
        try:
            session = fastf1.get_session(self.year, self.gp, self.session_type)
            session.load()
            return session
        except Exception as e:
            rprint(f"[red]Error loading session: {e}[/red]")
            return None

    def analyze_stints(self, session):
        """
        Extracts Long Run Pace and Tyre Deg from FP2/FP3.
        Returns a dictionary of driver physics profiles.
        """
        laps = session.laps
        # Filter: Green flag, accurate laps, not in/out laps
        laps = laps.pick_track_status('1').pick_accurate().pick_wo_box()
        
        driver_profiles = {}
        
        # Group by Driver and Stint
        # 'Stint' column exists in FastF1
        for driver in session.drivers:
            d_laps = laps.pick_driver(driver)
            if d_laps.empty:
                continue
                
            # Iterate through stints
            for stint_id in d_laps['Stint'].unique():
                stint = d_laps[d_laps['Stint'] == stint_id]
                
                # HEURISTIC 1: Only analyze "Long Runs"
                if len(stint) < Config.MIN_LAPS_FOR_STINT:
                    continue

                # HEURISTIC 2: Filter Outliers (Traffic)
                median_time = stint['LapTime'].dt.total_seconds().median()
                stint = stint[stint['LapTime'].dt.total_seconds() < median_time * Config.OUTLIER_THRESHOLD]
                
                if len(stint) < 3: # Re-check after filtering
                    continue

                # PHYSICS CALCULATION
                # 1. Fuel Correction: FP2 usually ~60kg. Race Start ~105kg.
                # We normalize to "Heavy" (Race Start)
                # Assumption: FP2 Stint starts at 60kg and burns 1.5kg/lap
                # CorrectedTime = ActualTime + (Fuel_Diff * Burn_Rate)
                
                lap_times = stint['LapTime'].dt.total_seconds().values
                lap_numbers = np.arange(len(lap_times))
                
                # Fit Linear Regression for Deg
                reg = LinearRegression().fit(lap_numbers.reshape(-1, 1), lap_times)
                deg_slope = reg.coef_[0]
                
                # Clamp negative deg (track evolution masking wear)
                if deg_slope < 0:
                    deg_slope = 0.01 

                # Base Pace (Fuel Corrected)
                # Assuming 60kg start weight for FP2 run
                avg_raw_pace = np.median(lap_times)
                fuel_correction = (Config.RACE_START_FUEL - 60.0) * Config.FUEL_BURN_PER_KG
                corrected_pace = avg_raw_pace + fuel_correction

                compound = stint['Compound'].iloc[0] if 'Compound' in stint.columns else 'UNKNOWN'

                # Store best stint (lowest corrected pace)
                if driver not in driver_profiles or corrected_pace < driver_profiles[driver]['base_pace']:
                    driver_profiles[driver] = {
                        "driver": driver,
                        "base_pace": corrected_pace,
                        "deg_slope": deg_slope,
                        "compound": compound,
                        "stint_len": len(stint)
                    }

        return driver_profiles

# ==========================================
# 4. SIMULATION ENGINE (Monte Carlo)
# ==========================================
class RaceSimulator:
    def __init__(self, physics_profile, grid_order, laps=58):
        self.physics = physics_profile
        self.grid = grid_order # List of driver codes ['VER', 'HAM', ...]
        self.laps = laps
        
    def run_simulation(self):
        """Runs the Monte Carlo simulation."""
        results = {d: 0 for d in self.grid}
        
        # If we have no physics data (e.g. FP1 only), return pure grid probability
        if not self.physics:
            rprint("[yellow]⚠ No physics data available. Predicting based on Grid only.[/yellow]")
            for i, driver in enumerate(self.grid):
                # Simple decay probability for top 3
                if i == 0: results[driver] = 50
                elif i == 1: results[driver] = 30
                elif i == 2: results[driver] = 10
                else: results[driver] = 1
            return results

        # Run 1000 virtual races
        for _ in range(Config.MONTE_CARLO_RUNS):
            race_times = {}
            
            for driver in self.grid:
                if driver not in self.physics:
                    # Fallback for drivers with no long run data (Average of field)
                    base = np.mean([p['base_pace'] for p in self.physics.values()])
                    deg = 0.05
                else:
                    d_data = self.physics[driver]
                    base = d_data['base_pace']
                    deg = d_data['deg_slope']
                
                # SIMULATE RACE TIME
                # Total Time = (Base * Laps) + (Deg * Sum(0..Laps)) - (FuelEffect)
                # Simplified 1-stop strategy logic for simulation speed
                
                # Stint 1 (Soft/Med) - 25 Laps
                stint1_time = (base * 25) + (deg * np.sum(range(25))) 
                
                # Pit Stop
                pit_time = Config.PIT_LOSS_BASELINE + np.random.normal(0, 0.5) # Random variance
                
                # Stint 2 (Hard) - 33 Laps (Assume lower deg on hards)
                stint2_base = base + 0.5 # Harder tyre is slower
                stint2_deg = deg * 0.6   # Harder tyre degrades less
                stint2_time = (stint2_base * 33) + (stint2_deg * np.sum(range(33)))
                
                # Fuel Effect (Time gained over race)
                # Total fuel burned = ~100kg. Avg lap is faster by (100/2) * 0.035
                total_fuel_gain = (Config.RACE_START_FUEL * Config.FUEL_BURN_PER_KG) * self.laps * 0.5
                
                # Final Race Time
                # Add random race variance (mistakes, traffic)
                variance = np.random.normal(0, 5.0) 
                
                total_time = stint1_time + pit_time + stint2_time - total_fuel_gain + variance
                race_times[driver] = total_time
            
            # Determine Winner of this run
            winner = min(race_times, key=race_times.get)
            results[winner] += 1
            
        return results

# ==========================================
# 5. CLI & MAIN LOGIC
# ==========================================
def main():
    console = Console()
    parser = argparse.ArgumentParser(description="F1 Strategy Predictor")
    parser.add_argument("--year", type=int, default=2025, help="Season Year")
    parser.add_argument("--gp", type=str, default="Australia", help="Grand Prix Name")
    parser.add_argument("--session", type=str, required=True, choices=['FP1', 'FP2', 'FP3', 'Q'], help="Current Session")
    
    args = parser.parse_args()
    
    console.print(Panel.fit(f"F1 PREDICTOR ENGINE | {args.year} {args.gp} | {args.session}", style="bold red"))

    # Initialize Engine
    analyzer = TelemetryAnalyzer(args.year, args.gp, args.session)
    session = analyzer.load_data()
    
    if not session:
        return

    # LOGIC BRANCHING
    if args.session in ['FP1', 'FP2', 'FP3']:
        console.print("[bold]analyzing Practice Data for Long Runs...[/bold]")
        profiles = analyzer.analyze_stints(session)
        
        # Display Stint Data
        table = Table(title="Detected Race Simulations (Fuel Corrected)")
        table.add_column("Driver", style="cyan")
        table.add_column("Compound", style="magenta")
        table.add_column("Race Pace (Est)", style="green")
        table.add_column("Deg Slope", style="yellow")
        table.add_column("Laps", justify="right")

        sorted_profiles = sorted(profiles.values(), key=lambda x: x['base_pace'])
        
        for p in sorted_profiles:
            table.add_row(
                p['driver'], 
                p['compound'], 
                f"{p['base_pace']:.3f}s", 
                f"{p['deg_slope']:.4f}", 
                str(p['stint_len'])
            )
        
        console.print(table)
        
        # Save to State if FP2/FP3
        if args.session in ['FP2', 'FP3']:
            WeekendState.save_physics_profile(args.year, args.gp, profiles)
            
        # Quick Prediction based on Pace
        if sorted_profiles:
            top_pick = sorted_profiles[0]['driver']
            console.print(f"\n[bold green]Early Prediction (Pure Pace): {top_pick} looks strongest.[/bold green]")
        else:
            console.print("\n[red]Insufficient Long Run Data found in this session.[/red]")

    elif args.session == 'Q':
        console.print("[bold]analyzing Qualifying Results...[/bold]")
        # 1. Get Grid
        results = session.results
        grid = results['Abbreviation'].head(20).tolist() # Top 20 grid
        
        console.print(f"Pole Position: [bold]{grid[0]}[/bold]")
        
        # 2. Load Physics
        physics = WeekendState.load_physics_profile(args.year, args.gp)
        
        if not physics:
            console.print("[yellow]⚠ Warning: No FP2/FP3 data found in history. Simulation will be generic.[/yellow]")
        else:
            console.print(f"[green]✔ Loaded Physics Profiles for {len(physics)} drivers.[/green]")

        # 3. Run Simulation
        sim = RaceSimulator(physics, grid)
        console.print("[bold]Running 1000 Monte Carlo Simulations...[/bold]")
        win_counts = sim.run_simulation()
        
        # 4. Display Win Matrix
        win_table = Table(title="Sunday Win Probability")
        win_table.add_column("Driver", style="cyan")
        win_table.add_column("Win %", style="green")
        
        total_runs = Config.MONTE_CARLO_RUNS
        for driver, wins in sorted(win_counts.items(), key=lambda item: item[1], reverse=True):
            if wins > 0:
                prob = (wins / total_runs) * 100
                win_table.add_row(driver, f"{prob:.1f}%")
                
        console.print(win_table)

if __name__ == "__main__":
    main()