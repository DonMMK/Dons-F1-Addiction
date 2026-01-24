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
from rich import print as rprint

# ==========================================
# 1. CONFIGURATION
# ==========================================
class Config:
    FUEL_BURN_PER_KG = 0.035       
    RACE_START_FUEL = 105.0        
    PIT_LOSS_BASELINE = 22.0       
    MONTE_CARLO_RUNS = 2000        
    MIN_LAPS_FOR_STINT = 3         
    OUTLIER_THRESHOLD = 1.07       
    CACHE_DIR = 'f1_cache'

class TrackConfig:
    """Defines how hard it is to pass at specific tracks."""
    # Delta (seconds) required to overtake on track
    OVERTAKE_DELTAS = {
        "Monaco": 3.0,      # Impossible to pass
        "Singapore": 1.5,   # Very hard
        "Hungary": 1.2,     # Hard
        "Spain": 1.0,       # Medium
        "Australia": 0.8,   # Medium
        "Italy": 0.4,       # Easy (Monza)
        "Belgium": 0.4,     # Easy (Spa)
        "China": 0.6,       # Medium-Easy
        "DEFAULT": 0.8      # Standard track
    }
    
    # Total laps for simulation
    LAP_COUNTS = {
        "Monaco": 78,
        "Singapore": 62,
        "DEFAULT": 58
    }

    @staticmethod
    def get_overtake_delta(gp_name):
        return TrackConfig.OVERTAKE_DELTAS.get(gp_name, TrackConfig.OVERTAKE_DELTAS["DEFAULT"])

    @staticmethod
    def get_laps(gp_name):
        return TrackConfig.LAP_COUNTS.get(gp_name, TrackConfig.LAP_COUNTS["DEFAULT"])

# ==========================================
# 2. STATE MANAGER
# ==========================================
class WeekendState:
    FILE_NAME = "weekend_state.json"

    @staticmethod
    def save_physics_profile(year, gp, profile):
        data = {"meta": {"year": year, "gp": gp}, "profile": profile}
        with open(WeekendState.FILE_NAME, 'w') as f:
            json.dump(data, f, indent=4)
        rprint(f"[green]✔ Physics profile saved to {WeekendState.FILE_NAME}[/green]")

    @staticmethod
    def load_physics_profile(year, gp):
        if not os.path.exists(WeekendState.FILE_NAME): return None
        with open(WeekendState.FILE_NAME, 'r') as f:
            data = json.load(f)
        if data['meta']['year'] != year or data['meta']['gp'] != gp: return None
        return data['profile']

# ==========================================
# 3. PHYSICS ENGINE
# ==========================================
class TelemetryAnalyzer:
    def __init__(self, year, gp, session_type):
        self.year = year
        self.gp = gp
        self.session_type = session_type
        if not os.path.exists(Config.CACHE_DIR): os.makedirs(Config.CACHE_DIR)
        fastf1.Cache.enable_cache(Config.CACHE_DIR)

    def load_data(self):
        try:
            session = fastf1.get_session(self.year, self.gp, self.session_type)
            session.load()
            return session
        except Exception as e:
            rprint(f"[red]Error loading session: {e}[/red]")
            if self.session_type == 'FP2':
                rprint("[yellow]HINT: This might be a Sprint Weekend. Try using '--session FP1' instead.[/yellow]")
            return None

    def analyze_stints(self, session):
        try:
            laps = session.laps.pick_track_status('1').pick_accurate().pick_wo_box()
        except:
            return {}

        driver_profiles = {}
        driver_map = {}
        
        # Map IDs to Abbreviations
        for drv_num in session.drivers:
            try:
                abbr = session.get_driver(drv_num)['Abbreviation']
                driver_map[drv_num] = abbr
            except: continue

        for driver_num in session.drivers:
            if driver_num not in driver_map: continue
            driver_abbr = driver_map[driver_num]
            
            d_laps = laps.pick_driver(driver_num)
            if d_laps.empty: continue
                
            for stint_id in d_laps['Stint'].unique():
                stint = d_laps[d_laps['Stint'] == stint_id]
                if len(stint) < Config.MIN_LAPS_FOR_STINT: continue

                median_time = stint['LapTime'].dt.total_seconds().median()
                stint = stint[stint['LapTime'].dt.total_seconds() < median_time * Config.OUTLIER_THRESHOLD]
                if len(stint) < 3: continue

                times = stint['LapTime'].dt.total_seconds().values
                reg = LinearRegression().fit(np.arange(len(times)).reshape(-1, 1), times)
                deg_slope = reg.coef_[0]
                
                if deg_slope < 0: deg_slope = 0.005 
                if deg_slope > 0.3: deg_slope = 0.3 

                avg_raw = np.median(times)
                corrected_pace = avg_raw + ((Config.RACE_START_FUEL - 60.0) * Config.FUEL_BURN_PER_KG)

                if driver_abbr not in driver_profiles or corrected_pace < driver_profiles[driver_abbr]['base_pace']:
                    driver_profiles[driver_abbr] = {
                        "base_pace": corrected_pace,
                        "deg_slope": deg_slope,
                        "stint_len": len(stint)
                    }

        return driver_profiles

# ==========================================
# 4. SIMULATION ENGINE (THE FIX)
# ==========================================
class RaceSimulator:
    def __init__(self, physics_profile, grid_order, gp_name):
        self.physics = physics_profile
        self.grid = grid_order 
        self.overtake_delta = TrackConfig.get_overtake_delta(gp_name)
        self.laps = TrackConfig.get_laps(gp_name)
        rprint(f"[bold yellow]Track Difficulty: {gp_name} (Delta required: {self.overtake_delta}s/lap)[/bold yellow]")
        
    def run_simulation(self):
        results = {d: 0 for d in self.grid}
        
        # Field Average fallback
        if self.physics:
            known_paces = [p['base_pace'] for p in self.physics.values()]
            avg_pace = np.mean(known_paces) if known_paces else 85.0
        else:
            avg_pace = 85.0
        avg_deg = 0.08

        for _ in range(Config.MONTE_CARLO_RUNS):
            # 1. Calculate Theoretical Race Times (Time Trial Mode)
            driver_times = []
            
            for grid_pos, driver in enumerate(self.grid):
                if self.physics and driver in self.physics:
                    base = self.physics[driver]['base_pace']
                    deg = self.physics[driver]['deg_slope']
                else:
                    grid_penalty = (grid_pos - 8) * 0.1 
                    base = avg_pace + grid_penalty
                    deg = avg_deg

                # Theoretical clean air time
                race_time = (base * self.laps) + (deg * np.sum(range(self.laps))) + np.random.normal(0, 4.0)
                
                # Add Grid Position index to track order
                driver_times.append({
                    "driver": driver, 
                    "raw_time": race_time, 
                    "grid_pos": grid_pos
                })

            # 2. APPLY "THE TRAIN" LOGIC (Clamping)
            # Sort by Grid Position because you start in order
            # If P2 is faster than P1, check if the delta is enough to pass.
            
            # Start with the Pole sitter
            final_times = {}
            leader_time = driver_times[0]['raw_time']
            final_times[driver_times[0]['driver']] = leader_time
            
            prev_driver_time = leader_time
            
            # Iterate through the rest of the grid
            for i in range(1, len(driver_times)):
                curr = driver_times[i]
                curr_raw_time = curr['raw_time']
                
                # Calculate Pace Delta per lap (approx)
                time_diff = prev_driver_time - curr_raw_time # Positive means Current is faster
                pace_delta = time_diff / self.laps
                
                # Overtake Check
                if curr_raw_time < prev_driver_time:
                    # Current driver is theoretically faster.
                    if pace_delta < self.overtake_delta:
                        # BUT not fast enough to pass! Get Stuck.
                        # Finish 0.5s behind the car ahead
                        curr_raw_time = prev_driver_time + 0.5
                    else:
                        # Fast enough to overtake! Keep raw time.
                        pass
                
                final_times[curr['driver']] = curr_raw_time
                prev_driver_time = curr_raw_time # This car becomes the blockage for the next one

            # Determine Winner
            winner = min(final_times, key=final_times.get)
            results[winner] += 1
            
        return results

# ==========================================
# 5. MAIN
# ==========================================
def main():
    console = Console()
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--gp", type=str, default="Australia")
    parser.add_argument("--session", type=str, required=True, choices=['FP1', 'FP2', 'Q'])
    args = parser.parse_args()
    
    console.print(Panel.fit(f"F1 PREDICTOR V4 (PHYSICS + TRACK LOGIC) | {args.year} {args.gp}", style="bold red"))

    analyzer = TelemetryAnalyzer(args.year, args.gp, args.session)
    session = analyzer.load_data()
    if not session: return

    if args.session in ['FP1', 'FP2']:
        console.print(f"[bold]Analyzing {args.session}...[/bold]")
        profiles = analyzer.analyze_stints(session)
        if not profiles:
            console.print("[red]No valid runs found.[/red]")
            return
        
        table = Table(title=f"Race Pace ({args.session})")
        table.add_column("Driver")
        table.add_column("Pace")
        for d, p in sorted(profiles.items(), key=lambda x: x[1]['base_pace']):
            table.add_row(d, f"{p['base_pace']:.3f}s")
        console.print(table)
        WeekendState.save_physics_profile(args.year, args.gp, profiles)

    elif args.session == 'Q':
        console.print("[bold]Simulating Race...[/bold]")
        grid = session.results['Abbreviation'].head(20).tolist()
        console.print(f"Pole Position: [bold cyan]{grid[0]}[/bold cyan]")
        
        physics = WeekendState.load_physics_profile(args.year, args.gp)
        if not physics:
            console.print("[red]No Physics data found![/red]")
            return
        
        # Pass GP Name to simulator to get Overtake Delta
        sim = RaceSimulator(physics, grid, args.gp)
        win_counts = sim.run_simulation()
        
        table = Table(title="Predicted Win Probability")
        table.add_column("Driver")
        table.add_column("Win %")
        for d, wins in sorted(win_counts.items(), key=lambda x: x[1], reverse=True):
            if wins > 0:
                table.add_row(d, f"{(wins/Config.MONTE_CARLO_RUNS)*100:.1f}%")
        console.print(table)

if __name__ == "__main__":
    main()