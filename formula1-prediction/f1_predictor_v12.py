import os
import json
import argparse
import numpy as np
import pandas as pd
import fastf1
import fastf1.plotting
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
    
    # 2026 SAFETY CAR PROBABILITY (Higher for Street Tracks)
    SC_CHANCE = {
        "Monaco": 0.8, "Singapore": 1.0, "Madrid": 0.9, 
        "Great Britain": 0.6, "DEFAULT": 0.3
    }

class TrackConfig:
    # Overtake Difficulty (0.0 = Easy, 1.0 = Impossible)
    # Madrid is new for 2026 -> Street circuit -> High Difficulty
    PASS_DIFFICULTY = {
        "Monaco": 0.95, "Singapore": 0.85, "Madrid": 0.85, "Hungary": 0.7,
        "Great Britain": 0.4, "Belgium": 0.2, "Bahrain": 0.3,
        "DEFAULT": 0.5
    }
    
    # Updated Lap Counts for 2026 Calendar
    LAP_COUNTS = { 
        "Monaco": 78, "Singapore": 62, "Great Britain": 52, 
        "Belgium": 44, "Madrid": 55, "Las Vegas": 50, "DEFAULT": 58 
    }

    @staticmethod
    def get_config(gp_name):
        cfg = {"laps": 58, "pass_diff": 0.5}
        # Fuzzy match track name
        for key in TrackConfig.LAP_COUNTS:
            if key in gp_name: cfg["laps"] = TrackConfig.LAP_COUNTS[key]
        for key in TrackConfig.PASS_DIFFICULTY:
            if key in gp_name: cfg["pass_diff"] = TrackConfig.PASS_DIFFICULTY[key]
        return cfg

# ==========================================
# 2. SIMULATION ENGINE (V12 - 2026 UPDATE)
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
        try:
            row = self.grid_df[self.grid_df['Abbreviation'] == driver_abbr]
            if not row.empty:
                val = row['GridPosition'].values[0]
                if pd.notna(val) and val > 0:
                    return int(val)
        except: pass
        return index_fallback + 1

    def run_simulation(self):
        # Support for 22 Drivers (11 Teams) in 2026
        grid_list = self.grid_df['Abbreviation'].head(22).tolist()
        results = {d: 0 for d in grid_list}
        
        # --- 2026 DRIVER DATABASE ---
        # Tiers based on expected 2026 Regulations:
        # Tier 1: McLaren, Ferrari, Mercedes (Manufacturer Stability)
        # Tier 2: Red Bull (Ford Risk), Aston Martin (Honda Risk)
        # Tier 3: Williams, Alpine, Audi
        # Tier 4: Haas, RB, Cadillac
        TIER_1_DRIVERS = ['NOR', 'PIA', 'LEC', 'HAM', 'RUS', 'ANT']
        TIER_2_DRIVERS = ['VER', 'HAD', 'ALO', 'STR'] 
        
        # Skill Buffs (Driver Talent independent of Car)
        ELITE_DRIVERS = ['VER', 'NOR', 'HAM', 'LEC', 'ALO', 'RUS']
        ROOKIES = ['ANT', 'BEA', 'HAD', 'BOR', 'LIN', 'COL'] # High Variance

        # --- PHYSICS SETUP ---
        driver_configs = {}
        pole_time = 80.0
        
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
            race_pace = pole_time + 5.0 + delta

            # 2. 2026 Car Performance Buff
            if driver in TIER_1_DRIVERS:
                race_pace -= 0.25 # Massive Aero/Engine advantage
            elif driver in TIER_2_DRIVERS:
                race_pace -= 0.15 # Strong but potentially unreliable

            # 3. Driver Skill Logic
            consistency = 0.4
            
            # The "Champion" Factor (Max/Lewis/Lando/Charles/Fernando)
            if driver in ELITE_DRIVERS:
                race_pace -= 0.1
                consistency = 0.25  # Experienced drivers are consistent
            
            # The "Rookie" Factor (Kimi/Bearman/Hadjar)
            if driver in ROOKIES:
                race_pace += 0.05   # Slight race pace deficit
                consistency = 0.8   # High error rate / inconsistency

            driver_configs[driver] = {
                "pace": race_pace,
                "grid": actual_grid,
                "consistency": consistency
            }

        # --- MONTE CARLO LOOP ---
        for _ in range(Config.MONTE_CARLO_RUNS):
            current_race_time = {}
            for d, cfg in driver_configs.items():
                current_race_time[d] = (cfg['grid'] - 1) * 0.2
            
            # STINT SIMULATION
            for d, cfg in driver_configs.items():
                base_time = cfg['pace'] * self.cfg['laps']
                
                # --- DYNAMIC OVERTAKE LOGIC ---
                traffic_drag = 0.0
                if cfg['grid'] > 1:
                    pass_factor = self.cfg['pass_diff']
                    
                    # Elite Drivers slice through traffic better
                    if d in ELITE_DRIVERS:
                        pass_factor *= 0.5 
                    
                    # Rookies struggle in traffic
                    if d in ROOKIES:
                        pass_factor *= 1.2

                    traffic_drag = (cfg['grid'] * 0.5) * pass_factor

                total_time = base_time + traffic_drag + np.random.normal(0, cfg['consistency'] * 10)
                current_race_time[d] += total_time

            # SC BUNCHING
            if np.random.random() < self.sc_prob:
                sorted_drivers = sorted(current_race_time.items(), key=lambda x: x[1])
                leader_time = sorted_drivers[0][1]
                for rank, (d, time) in enumerate(sorted_drivers):
                    current_race_time[d] = leader_time + (rank * 0.5) + np.random.normal(0, 0.2)

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
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--gp", type=str, default="Great Britain")
    parser.add_argument("--session", type=str, required=True, choices=['FP1', 'FP2', 'Q'])
    args = parser.parse_args()
    
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
