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
    RACE_START_FUEL = 100.0        
    MONTE_CARLO_RUNS = 5000        
    CACHE_DIR = 'f1_cache'
    
    # SAFETY CAR PROBABILITY
    SC_CHANCE = {
        "Monaco": 0.8, "Singapore": 1.0, "Italy": 0.5, 
        "Great Britain": 0.6, "DEFAULT": 0.3
    }

class TrackConfig:
    # Overtake Difficulty (0.0 = Easy, 1.0 = Impossible)
    PASS_DIFFICULTY = {
        "Monaco": 0.95, "Singapore": 0.85, "Hungary": 0.7,
        "Great Britain": 0.4, "Belgium": 0.2, "Bahrain": 0.3, # Easy pass tracks
        "DEFAULT": 0.5
    }
    
    LAP_COUNTS = { "Monaco": 78, "Singapore": 62, "Great Britain": 52, "Belgium": 44, "DEFAULT": 58 }

    @staticmethod
    def get_config(gp_name):
        cfg = {"laps": 58, "pass_diff": 0.5}
        for key in TrackConfig.LAP_COUNTS:
            if key in gp_name: cfg["laps"] = TrackConfig.LAP_COUNTS[key]
        for key in TrackConfig.PASS_DIFFICULTY:
            if key in gp_name: cfg["pass_diff"] = TrackConfig.PASS_DIFFICULTY[key]
        return cfg

# ==========================================
# 2. SIMULATION ENGINE (V11 - THE HUNTER)
# ==========================================
class RaceSimulator:
    def __init__(self, grid_data, gp_name):
        self.grid_df = grid_data 
        self.gp_name = gp_name
        self.cfg = TrackConfig.get_config(gp_name)
        self.sc_prob = Config.SC_CHANCE.get(gp_name, Config.SC_CHANCE["DEFAULT"])
        
    def get_quali_pace(self, driver_abbr):
        try:
            row = self.grid_df[self.grid_df['Abbreviation'] == driver_abbr]
            if not row.empty:
                for q in ['Q3', 'Q2', 'Q1']:
                    val = row[q].values[0]
                    if pd.notna(val) and val != '':
                        return val.total_seconds()
        except: pass
        return None

    def get_grid_pos(self, driver_abbr, index_fallback):
        # Try to use official GridPosition column
        try:
            row = self.grid_df[self.grid_df['Abbreviation'] == driver_abbr]
            if not row.empty:
                val = row['GridPosition'].values[0]
                if pd.notna(val) and val > 0:
                    return int(val)
        except: pass
        return index_fallback + 1

    def run_simulation(self):
        # We need the full grid to calculate traffic
        grid_list = self.grid_df['Abbreviation'].head(20).tolist()
        results = {d: 0 for d in grid_list}
        
        # --- PHYSICS SETUP ---
        driver_configs = {}
        pole_time = 80.0
        
        # Find Pole Time
        for d in grid_list:
            t = self.get_quali_pace(d)
            if t: 
                pole_time = t
                break

        for i, driver in enumerate(grid_list):
            q_time = self.get_quali_pace(driver)
            actual_grid = self.get_grid_pos(driver, i)
            
            if q_time:
                delta = q_time - pole_time
            else:
                delta = 2.0 + (i * 0.1)

            # 1. Base Race Pace
            # Race Pace is usually +5s from Quali
            race_pace = pole_time + 5.0 + delta

            # 2. Team Tier Buff (Tyre Management)
            # Top teams degrade slower.
            if driver in ['VER', 'NOR', 'PIA', 'LEC', 'HAM', 'RUS', 'SAI']:
                race_pace -= 0.2 # Elite Tyre Mgmt
            
            # 3. The "Max Factor" (Relentless Consistency)
            # Max/Lando rarely make mistakes
            consistency = 0.4
            if driver == 'VER': 
                race_pace -= 0.1
                consistency = 0.2
            if driver == 'NOR':
                race_pace -= 0.05
                consistency = 0.25

            driver_configs[driver] = {
                "pace": race_pace,
                "grid": actual_grid,
                "consistency": consistency
            }

        # --- MONTE CARLO LOOP ---
        for _ in range(Config.MONTE_CARLO_RUNS):
            # Init state
            current_race_time = {}
            for d, cfg in driver_configs.items():
                # Grid Stagger (0.2s per slot)
                current_race_time[d] = (cfg['grid'] - 1) * 0.2
            
            # LAP BY LAP SIMULATION (Simplified for speed)
            # We simulate "Stints" rather than single laps
            
            # STINT 1 (Clean Air vs Traffic)
            for d, cfg in driver_configs.items():
                base_time = cfg['pace'] * self.cfg['laps']
                
                # --- DYNAMIC OVERTAKE LOGIC ---
                # If you start P10 but are 0.5s faster than P9, P8, P7...
                # The "Traffic Penalty" should be low.
                
                # Calculate Traffic Drag
                traffic_drag = 0.0
                if cfg['grid'] > 1:
                    # Look at who is ahead (approximate pace of cars ahead)
                    # If my pace is 85.0 and cars ahead are 85.5, I pass them easily.
                    # Pass Difficulty factor: 
                    # 0.2 (Spa) -> Easy to pass
                    # 0.9 (Monaco) -> Impossible
                    
                    pass_factor = self.cfg['pass_diff']
                    
                    # If driver is FAST (Tier 1), pass factor reduces
                    if d in ['VER', 'NOR', 'PIA', 'LEC']:
                        pass_factor *= 0.5 # They slice through traffic
                    
                    traffic_drag = (cfg['grid'] * 0.5) * pass_factor

                total_time = base_time + traffic_drag + np.random.normal(0, cfg['consistency'] * 10)
                current_race_time[d] += total_time

            # SC BUNCHING (The Great Equalizer)
            if np.random.random() < self.sc_prob:
                # Find current leader
                sorted_drivers = sorted(current_race_time.items(), key=lambda x: x[1])
                leader_time = sorted_drivers[0][1]
                
                # Compress field
                for rank, (d, time) in enumerate(sorted_drivers):
                    current_race_time[d] = leader_time + (rank * 0.5) + np.random.normal(0, 0.2)

            # Determine Winner
            winner = min(current_race_time, key=current_race_time.get)
            results[winner] += 1
            
        return results

# ==========================================
# 5. MAIN
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
            return fastf1.get_session(self.year, self.gp, self.session_type)
        except: return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--gp", type=str, default="Great Britain")
    parser.add_argument("--session", type=str, required=True, choices=['FP1', 'FP2', 'Q'])
    args = parser.parse_args()
    
    # We only need Q data for V11 (Quali Anchor + Grid Pos)
    if args.session != 'Q': return

    analyzer = TelemetryAnalyzer(args.year, args.gp, args.session)
    session = analyzer.load_data()
    if session:
        try: session.load()
        except: return
        
        sim = RaceSimulator(session.results, args.gp)
        win_counts = sim.run_simulation()
        
        sorted_wins = sorted(win_counts.items(), key=lambda x: x[1], reverse=True)
        if sorted_wins:
            top_driver, wins = sorted_wins[0]
            prob = (wins/Config.MONTE_CARLO_RUNS)*100
            print(f"│ {top_driver}    │ {prob:.1f}% │")

if __name__ == "__main__":
    main()
