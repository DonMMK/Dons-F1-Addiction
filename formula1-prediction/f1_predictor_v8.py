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
    
    SC_CHANCE = {"Monaco": 0.8, "Singapore": 1.0, "Italy": 0.4, "DEFAULT": 0.3}

class TeamConfig:
    # 2025 Tier List Estimates
    TIERS = {
        "McLaren": 1, "Red Bull Racing": 1, "Ferrari": 1, "Mercedes": 1,
        "Aston Martin": 2, "Alpine": 2,
        "Williams": 3, "RB": 3, "Haas": 3, "Kick Sauber": 3, "Sauber": 3
    }

    # Physics Adjustments per Tier (The "Sandbag" Factors)
    # Tier 1: Hidden pace (-0.3s)
    # Tier 2: Neutral
    # Tier 3: Likely Glory Runs (+0.1s)
    TIER_ADJUSTMENTS = { 1: -0.30, 2: 0.0, 3: 0.15 }

    @staticmethod
    def get_tier(team_name):
        # Fuzzy match team names
        for key in TeamConfig.TIERS:
            if key in str(team_name): return TeamConfig.TIERS[key]
        return 3 # Default to backmarker if unknown

class TrackConfig:
    OVERTAKE_DELTAS = {
        "Monaco": 3.0, "Singapore": 1.5, "Hungary": 1.2,
        "Spain": 1.0, "Australia": 0.8, "Italy": 0.4,
        "Belgium": 0.4, "China": 0.6, "DEFAULT": 0.8
    }
    LAP_COUNTS = { "Monaco": 78, "Singapore": 62, "DEFAULT": 58 }

    @staticmethod
    def get_overtake_delta(gp_name):
        for key in TrackConfig.OVERTAKE_DELTAS:
            if key in gp_name: return TrackConfig.OVERTAKE_DELTAS[key]
        return TrackConfig.OVERTAKE_DELTAS["DEFAULT"]

    @staticmethod
    def get_laps(gp_name):
        for key in TrackConfig.LAP_COUNTS:
            if key in gp_name: return TrackConfig.LAP_COUNTS[key]
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
        if data['meta']['gp'] != gp: return None
        return data['profile']

# ==========================================
# 3. PHYSICS ENGINE (TIER AWARE)
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
        
        # Enhanced Driver Map with Teams
        driver_meta = {}
        for drv in session.drivers:
            try:
                info = session.get_driver(drv)
                if 'Abbreviation' in info:
                    driver_meta[drv] = {
                        "abbr": info['Abbreviation'],
                        "team": info['TeamName']
                    }
            except: continue

        for driver_num, meta in driver_meta.items():
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
                # Basic Fuel Correction
                corrected_pace = avg_raw + ((Config.RACE_START_FUEL - 60.0) * Config.FUEL_BURN_PER_KG)
                
                # --- TIER ADJUSTMENT (THE SANDBAG FIX) ---
                tier = TeamConfig.get_tier(meta['team'])
                adjustment = TeamConfig.TIER_ADJUSTMENTS.get(tier, 0.0)
                final_pace = corrected_pace + adjustment

                driver_abbr = meta['abbr']
                if driver_abbr not in raw_profiles or final_pace < raw_profiles[driver_abbr]['base_pace']:
                    raw_profiles[driver_abbr] = {
                        "base_pace": final_pace,
                        "deg_slope": deg_slope,
                        "stint_len": len(stint),
                        "tier": tier,
                        "team": meta['team'],
                        "status": "VALID"
                    }

        # --- THE "MAX VERSTAPPEN" FIX (TIER 1 NORMALIZATION) ---
        # If a Tier 1 driver is way off the Tier 1 Median, fix them.
        if raw_profiles:
            tier1_paces = [p['base_pace'] for p in raw_profiles.values() if p['tier'] == 1]
            if tier1_paces:
                tier1_median = np.median(tier1_paces)
                
                for abbr, data in raw_profiles.items():
                    if data['tier'] == 1:
                        # If Tier 1 driver is > 0.8s slower than Tier 1 median, they were heavy/testing
                        if data['base_pace'] > (tier1_median + 0.8):
                            rprint(f"[yellow]⚠ DETECTED SANDBAG/TEST: {abbr} (Tier 1) is slow. Resetting to Tier 1 Median.[/yellow]")
                            data['base_pace'] = tier1_median
                            data['status'] = "NORMALIZED"
            
            # --- ANOMALY CLAMP (General) ---
            # Now we use the Tier 1 Median as the "True Fast" baseline
            # If anyone (Tier 2/3) is faster than Tier 1 Median, clamp them.
            if tier1_paces:
                fastest_tier1 = min(tier1_paces)
                for abbr, data in raw_profiles.items():
                    if data['tier'] > 1 and data['base_pace'] < fastest_tier1:
                         rprint(f"[yellow]⚠ GLORY RUN: {abbr} is faster than fastest Tier 1. Clamping.[/yellow]")
                         data['base_pace'] = fastest_tier1 + 0.1
                         data['status'] = "CLAMPED"

        return raw_profiles

# ==========================================
# 4. SIMULATION ENGINE
# ==========================================
class RaceSimulator:
    def __init__(self, physics_profile, grid_order, gp_name):
        self.physics = physics_profile
        self.grid = grid_order 
        self.gp_name = gp_name
        self.laps = TrackConfig.get_laps(gp_name)
        self.sc_prob = Config.SC_CHANCE.get(gp_name, Config.SC_CHANCE["DEFAULT"])
        
    def run_simulation(self):
        results = {d: 0 for d in self.grid}
        
        # Field Average
        if self.physics:
            known_paces = [p['base_pace'] for p in self.physics.values()]
            avg_pace = np.mean(known_paces) if known_paces else 85.0
        else:
            avg_pace = 85.0

        for _ in range(Config.MONTE_CARLO_RUNS):
            driver_states = []
            
            for grid_pos, driver in enumerate(self.grid):
                if self.physics and driver in self.physics:
                    base = self.physics[driver]['base_pace']
                    deg = self.physics[driver]['deg_slope']
                else:
                    grid_penalty = (grid_pos - 8) * 0.1 
                    base = avg_pace + grid_penalty
                    deg = 0.08

                # Clean Air Bonus for Pole Sitter
                if grid_pos == 0:
                    base -= 0.15 # Massive advantage being P1
                
                # Dirty Air Penalty for P2-P10
                if 1 <= grid_pos <= 10:
                    base += 0.05

                driver_states.append({
                    "driver": driver,
                    "pace": base,
                    "deg": deg,
                    "total_time": (grid_pos * 0.1) + np.random.normal(0, 0.5)
                })

            # RACE
            sc_event = np.random.random() < self.sc_prob
            
            for d in driver_states:
                # Run Race
                d['total_time'] += (d['pace'] * self.laps) + (d['deg'] * np.sum(range(self.laps)))
                d['total_time'] += np.random.normal(0, 3.0) 

            # SC BUNCHING
            driver_states.sort(key=lambda x: x['total_time'])
            if sc_event:
                leader_time = driver_states[0]['total_time']
                for i in range(len(driver_states)):
                    driver_states[i]['total_time'] = leader_time + (i * 0.6) + np.random.normal(0, 0.5)

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
    
    console.print(Panel.fit(f"F1 PREDICTOR V8 (TIER LOGIC) | {args.year} {args.gp}", style="bold red"))

    analyzer = TelemetryAnalyzer(args.year, args.gp, args.session)
    session = analyzer.load_data()
    if not session: return

    if args.session in ['FP1', 'FP2']:
        console.print(f"[bold]Analyzing {args.session}...[/bold]")
        profiles = analyzer.analyze_stints(session)
        
        table = Table(title=f"Tier-Adjusted Pace")
        table.add_column("Driver")
        table.add_column("Team")
        table.add_column("Tier")
        table.add_column("Adj. Pace")
        table.add_column("Status")
        
        for d, p in sorted(profiles.items(), key=lambda x: x[1]['base_pace']):
            table.add_row(d, p['team'], str(p['tier']), f"{p['base_pace']:.3f}s", p['status'])
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
            console.print("[red]No Physics data found![/red]")
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