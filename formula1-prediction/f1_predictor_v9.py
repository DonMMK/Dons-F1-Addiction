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
    MONTE_CARLO_RUNS = 5000        
    MIN_LAPS_FOR_STINT = 4         
    OUTLIER_THRESHOLD = 1.07       
    CACHE_DIR = 'f1_cache'
    
    # RELAXED ANOMALY SETTINGS
    ANOMALY_DIFF_LIMIT = 2.0       
    
    # SAFETY CAR PROBABILITY
    SC_CHANCE = {
        "Monaco": 0.8, "Singapore": 1.0, "Italy": 0.5, 
        "Great Britain": 0.6, "DEFAULT": 0.3
    }

class TrackConfig:
    # How much Tyre Deg matters per track (Multiplier)
    DEG_SENSITIVITY = {
        "Great Britain": 1.8, # Silverstone kills tyres
        "Spain": 1.5,
        "Japan": 1.5,
        "Monaco": 0.1,        # Deg irrelevant
        "DEFAULT": 1.0
    }
    
    # Delta required to overtake (Dirty Air Effect)
    OVERTAKE_DELTAS = {
        "Monaco": 3.0, "Singapore": 1.5, "Hungary": 1.2,
        "Great Britain": 0.9, # Maggotts/Becketts makes following hard
        "DEFAULT": 0.7
    }
    
    LAP_COUNTS = { "Monaco": 78, "Singapore": 62, "Great Britain": 52, "DEFAULT": 58 }

    @staticmethod
    def get_config(gp_name):
        # Default values
        cfg = {
            "laps": 58,
            "deg_mult": 1.0,
            "pass_delta": 0.7
        }
        
        # Fuzzy match
        for key in TrackConfig.LAP_COUNTS:
            if key in gp_name: cfg["laps"] = TrackConfig.LAP_COUNTS[key]
            
        for key in TrackConfig.DEG_SENSITIVITY:
            if key in gp_name: cfg["deg_mult"] = TrackConfig.DEG_SENSITIVITY[key]
            
        for key in TrackConfig.OVERTAKE_DELTAS:
            if key in gp_name: cfg["pass_delta"] = TrackConfig.OVERTAKE_DELTAS[key]
            
        return cfg

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
        if data['meta']['gp'] != gp: return None
        return data['profile']

# ==========================================
# 3. PHYSICS ENGINE (PURE DATA - NO BIAS)
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
            if self.session_type == 'FP2': rprint("[yellow]HINT: Try '--session FP1'.[/yellow]")
            return None

    def analyze_stints(self, session):
        try:
            laps = session.laps.pick_track_status('1').pick_accurate().pick_wo_box()
        except: return {}

        raw_profiles = {}
        driver_map = {}
        for drv in session.drivers:
            try:
                info = session.get_driver(drv)
                if 'Abbreviation' in info: driver_map[drv] = info['Abbreviation']
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
                
                # Sanity Checks
                if deg_slope < -0.1: deg_slope = 0.0 # Track evo
                if deg_slope > 0.5: deg_slope = 0.5 # Puncture/Traffic

                avg_raw = np.median(times)
                corrected_pace = avg_raw + ((Config.RACE_START_FUEL - 60.0) * Config.FUEL_BURN_PER_KG)

                # Update if better stint found
                if driver_abbr not in raw_profiles or corrected_pace < raw_profiles[driver_abbr]['base_pace']:
                    raw_profiles[driver_abbr] = {
                        "base_pace": corrected_pace,
                        "deg_slope": max(0.02, deg_slope), # Force min positive deg
                        "stint_len": len(stint),
                        "status": "VALID"
                    }

        # --- SMART ANOMALY FILTER ---
        if raw_profiles:
            all_paces = sorted([p['base_pace'] for p in raw_profiles.values()])
            if all_paces:
                # Baseline from Top 40% (Front runners)
                limit_idx = int(len(all_paces) * 0.4)
                elite_median = np.median(all_paces[:limit_idx+1])
                
                threshold = elite_median - Config.ANOMALY_DIFF_LIMIT
                
                for abbr, data in raw_profiles.items():
                    if data['base_pace'] < threshold:
                        rprint(f"[yellow]⚠ ANOMALY: {abbr} too fast. Clamping.[/yellow]")
                        data['base_pace'] = elite_median - 0.2
                        data['status'] = "CLAMPED"

        return raw_profiles

# ==========================================
# 4. SIMULATION ENGINE (DEGRADATION HEAVY)
# ==========================================
class RaceSimulator:
    def __init__(self, physics_profile, grid_order, gp_name):
        self.physics = physics_profile
        self.grid = grid_order 
        self.gp_name = gp_name
        self.cfg = TrackConfig.get_config(gp_name)
        self.sc_prob = Config.SC_CHANCE.get(gp_name, Config.SC_CHANCE["DEFAULT"])
        
        rprint(f"[bold cyan]Track Config: {gp_name}[/bold cyan]")
        rprint(f" -> Laps: {self.cfg['laps']}")
        rprint(f" -> Deg Sensitivity: {self.cfg['deg_mult']}x")
        rprint(f" -> Overtake Delta: {self.cfg['pass_delta']}s")

    def run_simulation(self):
        results = {d: 0 for d in self.grid}
        
        # Field Averages for unknown drivers
        if self.physics:
            known_paces = [p['base_pace'] for p in self.physics.values()]
            known_degs = [p['deg_slope'] for p in self.physics.values()]
            avg_pace = np.mean(known_paces)
            avg_deg = np.mean(known_degs)
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

                # GRID BIAS (The "Dirty Air" Start)
                # Starting further back adds "Traffic Time" immediately
                start_penalty = grid_pos * 0.3 # 0.3s lost per grid slot at start

                driver_states.append({
                    "driver": driver,
                    "pace": base,
                    "deg": deg,
                    "total_time": start_penalty + np.random.normal(0, 0.5),
                    "grid_pos": grid_pos
                })

            # === RACE SIMULATION ===
            sc_event = np.random.random() < self.sc_prob
            
            for d in driver_states:
                # 1. Pure Pace
                race_time = (d['pace'] * self.cfg['laps'])
                
                # 2. Degradation (The Key Factor)
                # Sum of arithmetic progression: n/2 * (2a + (n-1)d)
                # We simply sum the deg loss per lap * multiplier
                deg_loss = np.sum([d['deg'] * lap * self.cfg['deg_mult'] for lap in range(self.cfg['laps'])])
                
                d['total_time'] += race_time + deg_loss
                d['total_time'] += np.random.normal(0, 2.5) # Pitstop variance

            # === TRAFFIC & SC LOGIC ===
            driver_states.sort(key=lambda x: x['total_time'])
            
            # If Safety Car, field bunches up
            if sc_event:
                leader_time = driver_states[0]['total_time']
                for i in range(len(driver_states)):
                    # Compressed field
                    driver_states[i]['total_time'] = leader_time + (i * 0.5) + np.random.normal(0, 0.5)

            # === THE "IMPOSSIBLE PASS" CLAMP ===
            # Re-check against starting grid. 
            # If Driver A started P1 (VER) and Driver B started P5 (HAM),
            # Driver B needs a massive time delta to actually have passed VER on track.
            
            # Convert Time Delta to Pace Delta
            # This is complex in Monte Carlo, so we use a Probability Weighting instead.
            # If the calculated winner started outside Top 4, reduce their win count probability
            # unless they were MUCH faster.
            
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
    parser.add_argument("--gp", type=str, default="Great Britain")
    parser.add_argument("--session", type=str, required=True, choices=['FP1', 'FP2', 'Q'])
    args = parser.parse_args()
    
    console.print(Panel.fit(f"F1 PREDICTOR V9 (DEGRADATION ENGINE) | {args.year} {args.gp}", style="bold red"))

    analyzer = TelemetryAnalyzer(args.year, args.gp, args.session)
    session = analyzer.load_data()
    if not session: return

    if args.session in ['FP1', 'FP2']:
        console.print(f"[bold]Analyzing {args.session}...[/bold]")
        profiles = analyzer.analyze_stints(session)
        
        table = Table(title=f"Race Pace & Degradation Analysis")
        table.add_column("Driver")
        table.add_column("Base Pace")
        table.add_column("Deg Slope")
        table.add_column("Status")
        
        for d, p in sorted(profiles.items(), key=lambda x: x[1]['base_pace']):
            table.add_row(d, f"{p['base_pace']:.3f}s", f"{p['deg_slope']:.4f}", p['status'])
        console.print(table)
        WeekendState.save_physics_profile(args.year, args.gp, profiles)

    elif args.session == 'Q':
        console.print("[bold]Simulating Race...[/bold]")
        try:
            grid = session.results['Abbreviation'].head(20).tolist()
            console.print(f"Pole: {grid[0]}")
        except:
            console.print("[red]No Grid Data.[/red]")
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