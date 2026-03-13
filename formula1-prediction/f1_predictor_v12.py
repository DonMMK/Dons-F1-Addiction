import os
import argparse
import numpy as np
import pandas as pd
import fastf1
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# ==========================================
# 1. CONFIGURATION
# ==========================================
class Config:
    RACE_START_FUEL = 100.0
    MONTE_CARLO_RUNS = 5000
    CACHE_DIR = "f1_cache"

    SC_CHANCE = {
        "Monaco": 0.8,
        "Singapore": 1.0,
        "Madrid": 0.9,
        "Great Britain": 0.6,
        "DEFAULT": 0.3,
    }

class TrackConfig:
    PASS_DIFFICULTY = {
        "Monaco": 0.95, "Singapore": 0.85, "Madrid": 0.85, "Hungary": 0.7,
        "Great Britain": 0.4, "Belgium": 0.2, "Bahrain": 0.3, "DEFAULT": 0.5,
    }

    LAP_COUNTS = {
        "Monaco": 78, "Singapore": 62, "Great Britain": 52,
        "Belgium": 44, "Madrid": 55, "Las Vegas": 50, "DEFAULT": 58,
    }

    @staticmethod
    def get_config(gp_name):
        cfg = {"laps": 58, "pass_diff": 0.5}
        for key in TrackConfig.LAP_COUNTS:
            if key in gp_name: cfg["laps"] = TrackConfig.LAP_COUNTS[key]
        for key in TrackConfig.PASS_DIFFICULTY:
            if key in gp_name: cfg["pass_diff"] = TrackConfig.PASS_DIFFICULTY[key]
        return cfg

# ==========================================
# 2. SIMULATION ENGINE
# ==========================================
class RaceSimulator:
    def __init__(self, grid_data, gp_name):
        self.grid_df = grid_data
        self.gp_name = gp_name
        self.cfg = TrackConfig.get_config(gp_name)
        self.sc_prob = Config.SC_CHANCE.get(gp_name, Config.SC_CHANCE["DEFAULT"])

    def get_quali_pace(self, driver_abbr):
        try:
            row = self.grid_df[self.grid_df["Abbreviation"] == driver_abbr]
            if not row.empty:
                for q in ["Q3", "Q2", "Q1"]:
                    if q in row.columns:
                        val = row[q].values[0]
                        if pd.notna(val) and val != "":
                            return val.total_seconds()
                if "LapTime" in row.columns:
                    val = row["LapTime"].values[0]
                    if pd.notna(val): return val.total_seconds()
        except: pass
        return None

    def get_grid_pos(self, driver_abbr, index_fallback):
        try:
            row = self.grid_df[self.grid_df["Abbreviation"] == driver_abbr]
            if not row.empty:
                val = row["GridPosition"].values[0]
                if pd.notna(val) and val > 0: return int(val)
        except: pass
        return index_fallback + 1

    def run_simulation(self):
        grid_list = self.grid_df["Abbreviation"].head(22).tolist()

        # Trackers for betting markets
        win_results = {d: 0 for d in grid_list}
        margin_results = {
            "0 - 5 Seconds": 0,
            "5 - 10 Seconds": 0,
            "11+ Seconds": 0
        }

        # 2026 Tiers
        TIER_1_DRIVERS = ["NOR", "PIA", "LEC", "HAM", "RUS", "ANT"]
        TIER_2_DRIVERS = ["HAD", "ALO", "STR"]
        ELITE_DRIVERS = ["VER", "HAM", "LEC", "RUS"]
        ROOKIES = ["BOR", "LIN", "COL"]

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
            delta = q_time - pole_time if q_time else 2.0 + (i * 0.1)

            race_pace = pole_time + 5.0 + delta
            if driver in TIER_1_DRIVERS: race_pace -= 0.25
            elif driver in TIER_2_DRIVERS: race_pace -= 0.15

            consistency = 0.4
            if driver in ELITE_DRIVERS:
                race_pace -= 0.1
                consistency = 0.25
            if driver in ROOKIES:
                race_pace += 0.05
                consistency = 0.8

            driver_configs[driver] = {
                "pace": race_pace,
                "grid": actual_grid,
                "consistency": consistency,
            }

        # MONTE CARLO LOOP
        for _ in range(Config.MONTE_CARLO_RUNS):
            current_race_time = {d: (cfg["grid"] - 1) * 0.2 for d, cfg in driver_configs.items()}

            for d, cfg in driver_configs.items():
                base_time = cfg["pace"] * self.cfg["laps"]
                traffic_drag = 0.0
                if cfg["grid"] > 1:
                    pass_factor = self.cfg["pass_diff"]
                    if d in ELITE_DRIVERS: pass_factor *= 0.5
                    if d in ROOKIES: pass_factor *= 1.2
                    traffic_drag = (cfg["grid"] * 0.5) * pass_factor

                total_time = base_time + traffic_drag + np.random.normal(0, cfg["consistency"] * 10)
                current_race_time[d] += total_time

            # SC BUNCHING (Affects gap betting heavily)
            if np.random.random() < self.sc_prob:
                sorted_drivers = sorted(current_race_time.items(), key=lambda x: x[1])
                leader_time = sorted_drivers[0][1]
                for rank, (d, time) in enumerate(sorted_drivers):
                    current_race_time[d] = leader_time + (rank * 0.5) + np.random.normal(0, 0.2)

            # --- EXTRACT RESULTS & GAPS ---
            sorted_final = sorted(current_race_time.items(), key=lambda x: x[1])
            p1_driver, p1_time = sorted_final[0]
            p2_driver, p2_time = sorted_final[1]

            # Record Winner
            win_results[p1_driver] += 1

            # Record Winning Margin (Time Gap)
            # Simulated drivers don't lift-and-coast, so we apply a slight
            # compression multiplier to simulate race management by the leader.
            raw_gap = p2_time - p1_time
            realistic_gap = raw_gap * 0.85 # Leaders manage pace when far ahead

            if realistic_gap <= 5.0:
                margin_results["0 - 5 Seconds"] += 1
            elif realistic_gap <= 10.0:
                margin_results["5 - 10 Seconds"] += 1
            else:
                margin_results["11+ Seconds"] += 1

        return win_results, margin_results

# ==========================================
# MAIN
# ==========================================
class TelemetryAnalyzer:
    def __init__(self, year, gp, session_type):
        self.year = year
        self.gp = gp
        self.session_type = session_type
        if not os.path.exists(Config.CACHE_DIR):
            os.makedirs(Config.CACHE_DIR)
        fastf1.Cache.enable_cache(Config.CACHE_DIR)

    def load_data(self):
        try: return fastf1.get_session(self.year, self.gp, self.session_type)
        except: return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--gp", type=str, default="Great Britain")
    parser.add_argument("--session", type=str, required=True, choices=["FP1", "FP2", "FP3", "Q"])
    args = parser.parse_args()

    console = Console()
    analyzer = TelemetryAnalyzer(args.year, args.gp, args.session)
    session = analyzer.load_data()

    if not session:
        console.print(f"[red]Could not load {args.session} data for {args.gp} {args.year}[/red]")
        return

    try: session.load()
    except Exception as e:
        console.print(f"[red]Error loading session: {e}[/red]")
        return

    if args.session in ["FP1", "FP2", "FP3"]:
        laps = session.laps
        if laps.empty:
            console.print(f"[red]No lap data available[/red]")
            return
        best_laps = laps.loc[laps.groupby("Driver")["LapTime"].idxmin()]
        best_laps = best_laps[["Driver", "LapTime"]].copy().rename(columns={"Driver": "Abbreviation"}).sort_values("LapTime").reset_index(drop=True)
        best_laps["GridPosition"] = range(1, len(best_laps) + 1)
        grid_data = best_laps
        session_label = f"{args.session} (Preliminary)"
    else:
        grid_data = session.results
        session_label = "Qualifying"

    sim = RaceSimulator(grid_data, args.gp)

    # Unpack the two return dictionaries
    win_counts, margin_counts = sim.run_simulation()

    # 1. Output Winner Predictions
    sorted_wins = sorted(win_counts.items(), key=lambda x: x[1], reverse=True)
    table_wins = Table(title=f"{args.gp} GP {args.year} - Winner Prediction")
    table_wins.add_column("Pos", style="cyan", justify="right")
    table_wins.add_column("Driver", style="white")
    table_wins.add_column("Win Probability", style="green", justify="right")

    for i, (driver, wins) in enumerate(sorted_wins[:10], 1):
        prob = (wins / Config.MONTE_CARLO_RUNS) * 100
        table_wins.add_row(str(i), driver, f"{prob:.1f}%")
    console.print(table_wins)

    # 2. Output Winning Margin Predictions
    console.print("\n")
    table_margins = Table(title="⏱️ Winning Margin Odds (Gap P1 to P2)", style="magenta")
    table_margins.add_column("Time Gap Bracket", style="white")
    table_margins.add_column("Probability", style="yellow", justify="right")
    table_margins.add_column("Implied Fair Odds", style="cyan", justify="right")

    for bracket, counts in margin_counts.items():
        prob = (counts / Config.MONTE_CARLO_RUNS)
        prob_pct = prob * 100
        # Calculate implied odds (1 / probability)
        implied_odds = (1 / prob) if prob > 0 else 0.0

        table_margins.add_row(
            bracket,
            f"{prob_pct:.1f}%",
            f"{implied_odds:.2f}"
        )

    console.print(table_margins)

if __name__ == "__main__":
    main()