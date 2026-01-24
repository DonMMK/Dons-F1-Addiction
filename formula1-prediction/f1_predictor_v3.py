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
# 1. CONFIGURATION
# ==========================================
class Config:
    # Physics Constants
    FUEL_BURN_PER_KG = 0.035       
    RACE_START_FUEL = 105.0        
    PIT_LOSS_BASELINE = 22.0       
    
    # Simulation Settings
    MONTE_CARLO_RUNS = 2000        
    MIN_LAPS_FOR_STINT = 3         
    OUTLIER_THRESHOLD = 1.07       

    # Cache
    CACHE_DIR = 'f1_cache'

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
        # Pick clean laps
        try:
            laps = session.laps.pick_track_status('1').pick_accurate().pick_wo_box()
        except:
            rprint("[red]Could not parse laps. Session might be empty or declared Wet.[/red]")
            return {}

        driver_profiles = {}
        
        # MAP NUMBERS TO NAMES
        driver_map = {}
        for drv_num in session.drivers:
            try:
                abbr = session.get_driver(drv_num)['Abbreviation']
                driver_map[drv_num] = abbr
            except:
                continue

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
                # On Sprint weekends (FP1), fuel might be varied, but we assume race prep (~60kg+)
                corrected_pace = avg_raw + ((Config.RACE_START_FUEL - 60.0) * Config.FUEL_BURN_PER_KG)

                if driver_abbr not in driver_profiles or corrected_pace < driver_profiles[driver_abbr]['base_pace']:
                    driver_profiles[driver_abbr] = {
                        "base_pace": corrected_pace,
                        "deg_slope": deg_slope,
                        "stint_len": len(stint)
                    }

        return driver_profiles

# ==========================================
# 4. SIMULATION ENGINE
# ==========================================
class RaceSimulator:
    def __init__(self, physics_profile, grid_order, laps=58):
        self.physics = physics_profile
        self.grid = grid_order 
        self.laps = laps
        
    def run_simulation(self):
        results = {d: 0 for d in self.grid}
        
        # Calculate Field Average
        if self.physics:
            known_paces = [p['base_pace'] for p in self.physics.values()]
            avg_pace = np.mean(known_paces) if known_paces else 85.0
        else:
            avg_pace = 85.0 # Total guess fallback
            
        avg_deg = 0.08

        for _ in range(Config.MONTE_CARLO_RUNS):
            race_times = {}
            
            for grid_pos, driver in enumerate(self.grid):
                if self.physics and driver in self.physics:
                    base = self.physics[driver]['base_pace']
                    deg = self.physics[driver]['deg_slope']
                else:
                    # Penalize unknown drivers based on grid slot
                    grid_penalty = (grid_pos - 8) * 0.1 
                    base = avg_pace + grid_penalty
                    deg = avg_deg

                # Traffic Penalty
                traffic_loss = grid_pos * 1.5 

                # Race Calc
                stint1_len = 25
                time_s1 = (base * stint1_len) + (deg * np.sum(range(stint1_len)))
                
                stint2_len = self.laps - stint1_len
                time_s2 = ((base + 0.4) * stint2_len) + ((deg * 0.7) * np.sum(range(stint2_len)))
                
                pit_time = Config.PIT_LOSS_BASELINE + np.random.normal(0, 0.4)
                variance = np.random.normal(0, 3.0) 

                total_time = time_s1 + time_s2 + pit_time + traffic_loss + variance
                race_times[driver] = total_time
            
            winner = min(race_times, key=race_times.get)
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
    # UPDATED: Added FP1 to choices
    parser.add_argument("--session", type=str, required=True, choices=['FP1', 'FP2', 'Q'])
    args = parser.parse_args()
    
    console.print(Panel.fit(f"F1 PREDICTOR V3 | {args.year} {args.gp} | {args.session}", style="bold red"))

    analyzer = TelemetryAnalyzer(args.year, args.gp, args.session)
    session = analyzer.load_data()
    if not session: return

    # LOGIC: Analyze Stints for BOTH FP1 and FP2
    if args.session in ['FP1', 'FP2']:
        console.print(f"[bold]Analyzing {args.session} Stints...[/bold]")
        profiles = analyzer.analyze_stints(session)
        
        if not profiles:
            console.print("[red]No valid long runs found. Try a different session.[/red]")
            return

        table = Table(title=f"Race Simulations ({args.session})")
        table.add_column("Driver")
        table.add_column("Pace (Fuel Corr)")
        table.add_column("Deg")
        
        for d, p in sorted(profiles.items(), key=lambda x: x[1]['base_pace']):
            table.add_row(d, f"{p['base_pace']:.3f}s", f"{p['deg_slope']:.4f}")
        
        console.print(table)
        WeekendState.save_physics_profile(args.year, args.gp, profiles)

    elif args.session == 'Q':
        console.print("[bold]Simulating Race...[/bold]")
        grid = session.results['Abbreviation'].head(20).tolist()
        console.print(f"Pole: {grid[0]}")
        
        physics = WeekendState.load_physics_profile(args.year, args.gp)
        if not physics:
            console.print("[red]No Physics data found! Did you run FP1/FP2 first?[/red]")
            return
        
        # Verify data freshness
        console.print(f"[green]Loaded Physics for {len(physics)} drivers.[/green]")

        sim = RaceSimulator(physics, grid)
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