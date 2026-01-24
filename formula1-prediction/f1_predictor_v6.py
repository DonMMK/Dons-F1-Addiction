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
    MONTE_CARLO_RUNS = 3000        
    MIN_LAPS_FOR_STINT = 4         
    OUTLIER_THRESHOLD = 1.07       
    CACHE_DIR = 'f1_cache'
    
    # Safety Car Probability (Probability of SC affecting race)
    SC_CHANCE = {
        "Monaco": 0.8,      # High chance
        "Singapore": 1.0,   # Guaranteed
        "Italy": 0.4,
        "DEFAULT": 0.3
    }

class TrackConfig:
    OVERTAKE_DELTAS = {
        "Monaco": 3.0, "Singapore": 1.5, "Hungary": 1.2,
        "Spain": 1.0, "Australia": 0.8, "Italy": 0.4,
        "Belgium": 0.4, "China": 0.6, "DEFAULT": 0.8
    }
    
    LAP_COUNTS = { 
        "Monaco": 78, "Singapore": 62, "Mexico": 71, 
        "Brazil": 71, "Las Vegas": 50, "Abu Dhabi": 58, 
        "DEFAULT": 58 
    }

    @staticmethod
    def get_overtake_delta(gp_name):
        # Fuzzy match for GP name if needed, else default
        for key in TrackConfig.OVERTAKE_DELTAS:
            if key in gp_name:
                return TrackConfig.OVERTAKE_DELTAS[key]
        return TrackConfig.OVERTAKE_DELTAS["DEFAULT"]

    @staticmethod
    def get_laps(gp_name):
        for key in TrackConfig.LAP_COUNTS:
            if key in gp_name:
                return TrackConfig.LAP_COUNTS[key]
        return TrackConfig.LAP_COUNTS["DEFAULT"]

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
        # Relaxed check: Just check GP name to allow cross-year testing if needed
        if data['meta']['gp'] != gp: return None
        return data['profile']

# ==========================================
# 3. PHYSICS ENGINE (With Anomaly Detection)
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
                rprint("[yellow]HINT: This might be a Sprint Weekend. Try using '--session FP1'.[/yellow]")
            return None

    def analyze_stints(self, session):
        try:
            laps = session.laps.pick_track_status('1').pick_accurate().pick_wo_box()
        except:
            return {}

        raw_profiles = {}
        driver_map = {}
        
        # Robust Driver Mapping
        for drv in session.drivers:
            try:
                info = session.get_driver(drv)
                if 'Abbreviation' in info:
                    driver_map[drv] = info['Abbreviation']
            except: continue

        for driver_num, driver_abbr in driver_map.items():
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

                if driver_abbr not in raw_profiles or corrected_pace < raw_profiles[driver_abbr]['base_pace']:
                    raw_profiles[driver_abbr] = {
                        "base_pace": corrected_pace,
                        "deg_slope": deg_slope,
                        "stint_len": len(stint),
                        "is_anomaly": False
                    }

        # ANOMALY FILTER
        if raw_profiles:
            paces = [p['base_pace'] for p in raw_profiles.values()]
            if paces:
                median_field_pace = np.median(paces)
                
                for abbr, data in raw_profiles.items():
                    # If > 1.2s faster than median, likely low fuel
                    if data['base_pace'] < (median_field_pace - 1.2):
                        rprint(f"[yellow]⚠ ANOMALY DETECTED: {abbr} is {-1*(data['base_pace'] - median_field_pace):.2f}s faster than field median.[/yellow]")
                        rprint(f"[yellow]  -> Reclassifying as Low Fuel Run. Clamping to valid Top 3 pace.[/yellow]")
                        
                        # Clamp to median - 0.3s (Conservative estimate of "True" fast pace)
                        data['base_pace'] = median_field_pace - 0.3
                        data['is_anomaly'] = True

        return raw_profiles

# ==========================================
# 4. SIMULATION ENGINE (FIXED)
# ==========================================
class RaceSimulator:
    def __init__(self, physics_profile, grid_order, gp_name):
        self.physics = physics_profile
        self.grid = grid_order 
        self.gp_name = gp_name
        self.overtake_delta = TrackConfig.get_overtake_delta(gp_name)
        # FIX: Correctly call the static method
        self.laps = TrackConfig.get_laps(gp_name)
        self.sc_prob = Config.SC_CHANCE.get(gp_name, Config.SC_CHANCE["DEFAULT"])
        
    def run_simulation(self):
        results = {d: 0 for d in self.grid}
        
        if self.physics:
            known_paces = [p['base_pace'] for p in self.physics.values()]
            avg_pace = np.mean(known_paces) if known_paces else 85.0
        else:
            avg_pace = 85.0
        avg_deg = 0.08

        for _ in range(Config.MONTE_CARLO_RUNS):
            driver_states = []
            
            for grid_pos, driver in enumerate(self.grid):
                if self.physics and driver in self.physics:
                    base = self.physics[driver]['base_pace']
                    deg = self.physics[driver]['deg_slope']
                else:
                    grid_penalty = (grid_pos - 8) * 0.1 
                    base = avg_pace + grid_penalty
                    deg = avg_deg

                # Random Start
                start_var = np.random.normal(0, 0.5)
                
                driver_states.append({
                    "driver": driver,
                    "pace": base,
                    "deg": deg,
                    "total_time": start_var + (grid_pos * 0.1), # Grid stagger
                    "grid_pos": grid_pos
                })

            # SIMULATION PHASES
            
            # Phase 1: Pure Pace
            sc_event = np.random.random() < self.sc_prob
            
            for d in driver_states:
                # Race Time Calculation
                d['total_time'] += (d['pace'] * self.laps) + (d['deg'] * np.sum(range(self.laps)))
                d['total_time'] += np.random.normal(0, 3.0) # Pit variance etc.

            # Phase 2: Safety Car Bunching
            driver_states.sort(key=lambda x: x['total_time'])
            
            if sc_event:
                # If SC happens, gaps are reset. 
                # Drivers behind only 0.5s - 1.0s behind car ahead
                leader_time = driver_states[0]['total_time']
                for i in range(len(driver_states)):
                    driver_states[i]['total_time'] = leader_time + (i * 0.8) + np.random.normal(0, 0.5)

            # Phase 3: The "Trulli Train" (Overtake Difficulty)
            # We must re-sort by Grid to check if faster cars are stuck behind slower cars
            # Note: This is a simplified "Post-Race Clamp" rather than lap-by-lap
            
            final_times = {}
            # We process purely by time for the winner in this simplified model,
            # BUT we apply a penalty if a "Slow" car (High Pace) beat a "Fast" car (Low Pace) 
            # purely due to track position in a low-overtake track.
            
            # For V6, we stick to the time-based win, as the SC logic handles the bunching.
            # The Overtake Delta is implicitly handled by the fact that you need a huge pace delta
            # to overcome the "Grid Stagger" (0.1s start penalty) + Traffic in short runs.
            
            winner = driver_states[0]['driver']
            results[winner] += 1
            
        return results

# ==========================================
# 5. MAIN
# ==========================================
def main():
    console = Console()
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--gp", type=str, default="Italy")
    parser.add_argument("--session", type=str, required=True, choices=['FP1', 'FP2', 'Q'])
    args = parser.parse_args()
    
    console.print(Panel.fit(f"F1 PREDICTOR V6 (FIXED) | {args.year} {args.gp}", style="bold red"))

    analyzer = TelemetryAnalyzer(args.year, args.gp, args.session)
    session = analyzer.load_data()
    if not session: return

    if args.session in ['FP1', 'FP2']:
        console.print(f"[bold]Analyzing {args.session}...[/bold]")
        profiles = analyzer.analyze_stints(session)
        if not profiles:
            console.print("[red]No valid runs found.[/red]")
            return
        
        table = Table(title=f"Race Pace Analysis")
        table.add_column("Driver")
        table.add_column("Pace (Fuel Corr)")
        table.add_column("Status")
        
        for d, p in sorted(profiles.items(), key=lambda x: x[1]['base_pace']):
            status = "[red]ANOMALY[/red]" if p['is_anomaly'] else "[green]VALID[/green]"
            table.add_row(d, f"{p['base_pace']:.3f}s", status)
        console.print(table)
        WeekendState.save_physics_profile(args.year, args.gp, profiles)

    elif args.session == 'Q':
        console.print("[bold]Simulating Race...[/bold]")
        try:
            grid = session.results['Abbreviation'].head(20).tolist()
            console.print(f"Pole: {grid[0]}")
        except:
            console.print("[red]Could not parse Grid. Ensure Quali is complete.[/red]")
            return
        
        physics = WeekendState.load_physics_profile(args.year, args.gp)
        if not physics:
            console.print("[red]No Physics data found! Run FP2 first.[/red]")
            return
        
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