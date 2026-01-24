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
    # We lower the fuel burn impact because we are now anchoring to Quali
    FUEL_BURN_PER_KG = 0.035       
    RACE_START_FUEL = 100.0        
    MONTE_CARLO_RUNS = 5000        
    CACHE_DIR = 'f1_cache'
    
    # SAFETY CAR & CHAOS (Higher for street tracks)
    SC_CHANCE = {
        "Monaco": 0.8, "Singapore": 1.0, "Italy": 0.5, 
        "Great Britain": 0.6, "DEFAULT": 0.3
    }

class TrackConfig:
    # How hard is it to pass? (Delta required)
    OVERTAKE_DELTAS = {
        "Monaco": 3.0, "Singapore": 1.5, "Hungary": 1.2,
        "Great Britain": 0.8, "Spain": 1.0, "DEFAULT": 0.5
    }
    
    LAP_COUNTS = { "Monaco": 78, "Singapore": 62, "Great Britain": 52, "DEFAULT": 58 }

    @staticmethod
    def get_config(gp_name):
        cfg = {"laps": 58, "pass_delta": 0.5}
        for key in TrackConfig.LAP_COUNTS:
            if key in gp_name: cfg["laps"] = TrackConfig.LAP_COUNTS[key]
        for key in TrackConfig.OVERTAKE_DELTAS:
            if key in gp_name: cfg["pass_delta"] = TrackConfig.OVERTAKE_DELTAS[key]
        return cfg

# ==========================================
# 2. DATA LOADING (UNCHANGED)
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
        except Exception: return None

    # We skip detailed stint analysis here because V10 relies on Quali
    # This keeps the script fast for benchmarking

# ==========================================
# 3. SIMULATION ENGINE (V10 - QUALI ANCHOR)
# ==========================================
class RaceSimulator:
    def __init__(self, grid_data, gp_name):
        self.grid_df = grid_data 
        self.gp_name = gp_name
        self.cfg = TrackConfig.get_config(gp_name)
        self.sc_prob = Config.SC_CHANCE.get(gp_name, Config.SC_CHANCE["DEFAULT"])
        
    def get_quali_pace(self, driver_abbr):
        # Extract best Quali time
        try:
            row = self.grid_df[self.grid_df['Abbreviation'] == driver_abbr]
            if not row.empty:
                # Try Q3 -> Q2 -> Q1
                for q in ['Q3', 'Q2', 'Q1']:
                    val = row[q].values[0]
                    if pd.notna(val) and val != '':
                        return val.total_seconds()
        except: pass
        return None

    def run_simulation(self):
        # Get Top 20 Drivers from Grid
        grid_list = self.grid_df['Abbreviation'].head(20).tolist()
        results = {d: 0 for d in grid_list}
        
        # --- THE V10 "QUALI ANCHOR" LOGIC ---
        driver_configs = {}
        
        # Find Pole Time (The absolute benchmark)
        pole_time = 80.0
        pole_driver = grid_list[0]
        t = self.get_quali_pace(pole_driver)
        if t: pole_time = t

        for grid_pos, driver in enumerate(grid_list):
            q_time = self.get_quali_pace(driver)
            
            if q_time:
                delta_to_pole = q_time - pole_time
            else:
                # Penalty for no time
                delta_to_pole = 2.0 + (grid_pos * 0.1)

            # BASE PACE CALCULATION
            # Instead of using FP2, we say: RacePace = PolePace + Delta + RaceCraftFactor
            
            # 1. Base Race Pace (Theoretical)
            # We assume race pace is ~5s slower than Quali (Fuel + Tyres)
            race_pace = pole_time + 5.0 + delta_to_pole

            # 2. The "Race Craft" Buff (The Max/Lando Factor)
            # Max and Lando tend to have better tyre management than George/Charles
            if driver in ['VER', 'NOR']:
                race_pace -= 0.15  # The "Champion" Bonus
            elif driver in ['RUS', 'LEC']:
                race_pace += 0.05  # The "Tyre Eater" Penalty
            
            # 3. The Traffic Penalty (Dirty Air)
            # Starting P1 is a huge advantage. P10 is stuck in a train.
            traffic_penalty = 0.0
            if grid_pos > 0:
                # 0.2s penalty per grid slot (compounding)
                # But capped at 1.0s to prevent backmarkers being infinite
                traffic_penalty = min(grid_pos * 0.15, 1.5)

            driver_configs[driver] = {
                "pace": race_pace + traffic_penalty,
                "consistency": 0.3 if driver in ['VER', 'NOR', 'PIA'] else 0.5
            }

        # --- MONTE CARLO LOOP ---
        for _ in range(Config.MONTE_CARLO_RUNS):
            driver_states = []
            
            for d in grid_list:
                cfg = driver_configs[d]
                
                # Random Start Variance
                start_var = np.random.normal(0, 0.5)
                
                driver_states.append({
                    "driver": d,
                    "total_time": start_var,
                    "pace": cfg['pace'],
                    "consistency": cfg['consistency']
                })

            # SIMULATE LAPS
            sc_event = np.random.random() < self.sc_prob
            
            for d in driver_states:
                # Run Race
                race_time = d['pace'] * self.cfg['laps']
                
                # Add Variance (Tyre lockups, slow pits)
                variance = np.random.normal(0, d['consistency'] * 10) # Over 50 laps
                
                d['total_time'] += race_time + variance

            # SAFETY CAR BUNCHING
            driver_states.sort(key=lambda x: x['total_time'])
            
            if sc_event:
                # SC resets gaps. Leader stays P1, P2 is +0.5s, P3 +1.0s
                leader_time = driver_states[0]['total_time']
                for i in range(len(driver_states)):
                    driver_states[i]['total_time'] = leader_time + (i * 0.5) + np.random.normal(0, 0.2)
            
            # OVERTAKE CHECK (Final sort)
            # Since we included "Traffic Penalty" in the Pace, 
            # sorting by Total Time effectively simulates inability to pass.
            
            winner = driver_states[0]['driver']
            results[winner] += 1
            
        return results

# ==========================================
# 4. MAIN
# ==========================================
def main():
    console = Console()
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--gp", type=str, default="Great Britain")
    parser.add_argument("--session", type=str, required=True, choices=['FP1', 'FP2', 'Q'])
    args = parser.parse_args()
    
    # Only run on Q session for V10 logic
    if args.session != 'Q':
        return

    analyzer = TelemetryAnalyzer(args.year, args.gp, args.session)
    session = analyzer.load_data()
    if not session: return

    try:
        grid_data = session.results
    except: return
    
    sim = RaceSimulator(grid_data, args.gp)
    win_counts = sim.run_simulation()
    
    # Output Winner for Benchmark
    sorted_wins = sorted(win_counts.items(), key=lambda x: x[1], reverse=True)
    if sorted_wins:
        top_driver, wins = sorted_wins[0]
        prob = (wins/Config.MONTE_CARLO_RUNS)*100
        print(f"│ {top_driver}    │ {prob:.1f}% │")

if __name__ == "__main__":
    main()