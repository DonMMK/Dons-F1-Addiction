"""
Analysis Module for F1 Car Comparison
Core comparison logic for pace, telemetry, and performance metrics
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import fastf1

from data_loader import (
    ComparisonConfig, CarConfig, COMPARISON_CONFIGS,
    load_session, get_driver_fastest_lap, get_team_fastest_lap,
    get_lap_telemetry, get_sector_times, get_speed_traps,
    calculate_gap_to_leader, get_event_schedule
)


@dataclass
class DominanceMetrics:
    """Metrics for measuring car dominance"""
    avg_gap_to_p2: float  # Average gap to second place (seconds)
    wins: int
    poles: int
    fastest_laps: int
    podiums: int
    one_twos: int  # 1-2 finishes
    races_analyzed: int
    consistency_score: float  # Lower variance = more consistent dominance
    

@dataclass
class PerformanceMetrics:
    """Metrics for measuring raw car performance"""
    avg_lap_time: float  # Average fastest lap time
    avg_sector1_time: float
    avg_sector2_time: float
    avg_sector3_time: float
    avg_top_speed: float
    avg_speed_i1: float
    avg_speed_i2: float
    corner_performance_score: float
    straight_line_score: float


def calculate_dominance_metrics(
    year: int,
    team: str,
    drivers: List[str],
    session_type: str = 'Q'
) -> DominanceMetrics:
    """
    Calculate dominance metrics for a team across a season
    
    Dominance = How much faster than competitors
    """
    schedule = get_event_schedule(year)
    races = schedule[schedule['EventFormat'] != 'testing']['EventName'].tolist()
    
    gaps_to_p2 = []
    wins = 0
    poles = 0
    fastest_laps = 0
    podiums = 0
    one_twos = 0
    races_analyzed = 0
    
    for race in races:
        try:
            # Qualifying session for poles
            q_session = load_session(year, race, 'Q')
            gaps = calculate_gap_to_leader(q_session)
            
            if gaps.empty:
                continue
            
            # Check if team driver is on pole
            pole_driver = gaps.iloc[0]['Driver']
            if pole_driver in drivers:
                poles += 1
                # Calculate gap to P2
                if len(gaps) > 1:
                    gap_to_p2 = gaps.iloc[1]['GapToLeader']
                    gaps_to_p2.append(gap_to_p2)
            
            # Race session for wins and podiums
            try:
                r_session = load_session(year, race, 'R')
                results = r_session.results.sort_values('Position')
                
                # Count wins
                if not results.empty and results.iloc[0]['Abbreviation'] in drivers:
                    wins += 1
                
                # Count podiums (P1, P2, P3)
                for i in range(min(3, len(results))):
                    if results.iloc[i]['Abbreviation'] in drivers:
                        podiums += 1
                
                # Check for 1-2 finish
                if len(results) >= 2:
                    if results.iloc[0]['Abbreviation'] in drivers and results.iloc[1]['Abbreviation'] in drivers:
                        one_twos += 1
                
                # Fastest lap
                fastest_lap = r_session.laps.pick_fastest()
                if fastest_lap is not None and fastest_lap['Driver'] in drivers:
                    fastest_laps += 1
                    
            except Exception:
                pass  # Skip race data if unavailable
            
            races_analyzed += 1
            
        except Exception as e:
            print(f"Error analyzing {race}: {e}")
            continue
    
    # Calculate consistency score (coefficient of variation of gaps)
    consistency_score = np.std(gaps_to_p2) if gaps_to_p2 else 0
    avg_gap = np.mean(gaps_to_p2) if gaps_to_p2 else 0
    
    return DominanceMetrics(
        avg_gap_to_p2=avg_gap,
        wins=wins,
        poles=poles,
        fastest_laps=fastest_laps,
        podiums=podiums,
        one_twos=one_twos,
        races_analyzed=races_analyzed,
        consistency_score=consistency_score
    )


def calculate_performance_metrics(
    year: int,
    team: str,
    drivers: List[str],
    races: Optional[List[str]] = None
) -> PerformanceMetrics:
    """
    Calculate raw performance metrics for a team
    
    Performance = Absolute speed (lap times, sector times, top speeds)
    """
    schedule = get_event_schedule(year)
    if races is None:
        races = schedule[schedule['EventFormat'] != 'testing']['EventName'].tolist()
    
    lap_times = []
    sector1_times = []
    sector2_times = []
    sector3_times = []
    top_speeds = []
    speed_i1s = []
    speed_i2s = []
    
    for race in races:
        try:
            session = load_session(year, race, 'Q')
            
            for driver in drivers:
                fastest_lap = get_driver_fastest_lap(session, driver)
                if fastest_lap is not None:
                    if pd.notna(fastest_lap['LapTime']):
                        lap_times.append(fastest_lap['LapTime'].total_seconds())
                    if pd.notna(fastest_lap['Sector1Time']):
                        sector1_times.append(fastest_lap['Sector1Time'].total_seconds())
                    if pd.notna(fastest_lap['Sector2Time']):
                        sector2_times.append(fastest_lap['Sector2Time'].total_seconds())
                    if pd.notna(fastest_lap['Sector3Time']):
                        sector3_times.append(fastest_lap['Sector3Time'].total_seconds())
                    if pd.notna(fastest_lap['SpeedST']):
                        top_speeds.append(fastest_lap['SpeedST'])
                    if pd.notna(fastest_lap['SpeedI1']):
                        speed_i1s.append(fastest_lap['SpeedI1'])
                    if pd.notna(fastest_lap['SpeedI2']):
                        speed_i2s.append(fastest_lap['SpeedI2'])
                        
        except Exception as e:
            print(f"Error loading {race}: {e}")
            continue
    
    # Calculate averages
    avg_lap_time = np.mean(lap_times) if lap_times else 0
    avg_sector1 = np.mean(sector1_times) if sector1_times else 0
    avg_sector2 = np.mean(sector2_times) if sector2_times else 0
    avg_sector3 = np.mean(sector3_times) if sector3_times else 0
    avg_top_speed = np.mean(top_speeds) if top_speeds else 0
    avg_speed_i1 = np.mean(speed_i1s) if speed_i1s else 0
    avg_speed_i2 = np.mean(speed_i2s) if speed_i2s else 0
    
    # Corner performance (inverse of sector times - lower is better)
    # Normalize to 0-100 scale
    corner_score = 100 - ((avg_sector1 + avg_sector3) / 2)  # Simplified
    straight_score = avg_top_speed / 3.5  # Normalize around 350 km/h max
    
    return PerformanceMetrics(
        avg_lap_time=avg_lap_time,
        avg_sector1_time=avg_sector1,
        avg_sector2_time=avg_sector2,
        avg_sector3_time=avg_sector3,
        avg_top_speed=avg_top_speed,
        avg_speed_i1=avg_speed_i1,
        avg_speed_i2=avg_speed_i2,
        corner_performance_score=corner_score,
        straight_line_score=straight_score
    )


def compare_telemetry(
    lap1: fastf1.core.Lap,
    lap2: fastf1.core.Lap,
    label1: str = "Car 1",
    label2: str = "Car 2"
) -> Dict:
    """
    Compare telemetry between two laps
    
    Returns dict with comparison data for visualization
    """
    tel1 = get_lap_telemetry(lap1)
    tel2 = get_lap_telemetry(lap2)
    
    if tel1.empty or tel2.empty:
        return {}
    
    # Ensure both have distance column
    tel1 = tel1.add_distance() if 'Distance' not in tel1.columns else tel1
    tel2 = tel2.add_distance() if 'Distance' not in tel2.columns else tel2
    
    # Create comparison at common distance points
    max_distance = min(tel1['Distance'].max(), tel2['Distance'].max())
    distance_points = np.linspace(0, max_distance, 500)
    
    comparison = {
        'distance': distance_points,
        'labels': [label1, label2],
        'lap_times': [lap1['LapTime'], lap2['LapTime']],
        'speed': {
            label1: np.interp(distance_points, tel1['Distance'], tel1['Speed']),
            label2: np.interp(distance_points, tel2['Distance'], tel2['Speed'])
        },
        'throttle': {
            label1: np.interp(distance_points, tel1['Distance'], tel1['Throttle']),
            label2: np.interp(distance_points, tel2['Distance'], tel2['Throttle'])
        },
        'brake': {
            label1: np.interp(distance_points, tel1['Distance'], tel1['Brake'].astype(float)),
            label2: np.interp(distance_points, tel2['Distance'], tel2['Brake'].astype(float))
        },
        'gear': {
            label1: np.interp(distance_points, tel1['Distance'], tel1['nGear']),
            label2: np.interp(distance_points, tel2['Distance'], tel2['nGear'])
        },
        'speed_delta': None
    }
    
    # Calculate speed delta (positive = car1 faster)
    comparison['speed_delta'] = comparison['speed'][label1] - comparison['speed'][label2]
    
    return comparison


def analyze_corner_performance(
    session: fastf1.core.Session,
    driver: str
) -> pd.DataFrame:
    """
    Analyze performance at different corner types
    Uses circuit info to identify corners
    """
    circuit_info = session.get_circuit_info()
    if circuit_info is None:
        return pd.DataFrame()
    
    corners = circuit_info.corners
    fastest_lap = get_driver_fastest_lap(session, driver)
    
    if fastest_lap is None:
        return pd.DataFrame()
    
    telemetry = get_lap_telemetry(fastest_lap)
    if telemetry.empty:
        return pd.DataFrame()
    
    telemetry = telemetry.add_distance() if 'Distance' not in telemetry.columns else telemetry
    
    corner_analysis = []
    
    for _, corner in corners.iterrows():
        corner_distance = corner['Distance']
        
        # Get telemetry around the corner (-50m to +50m)
        mask = (telemetry['Distance'] >= corner_distance - 50) & \
               (telemetry['Distance'] <= corner_distance + 50)
        corner_tel = telemetry[mask]
        
        if not corner_tel.empty:
            corner_analysis.append({
                'Corner': corner['Number'],
                'Letter': corner.get('Letter', ''),
                'MinSpeed': corner_tel['Speed'].min(),
                'MaxSpeed': corner_tel['Speed'].max(),
                'AvgSpeed': corner_tel['Speed'].mean(),
                'Distance': corner_distance
            })
    
    return pd.DataFrame(corner_analysis)


def calculate_race_pace_analysis(
    session: fastf1.core.Session,
    drivers: List[str]
) -> pd.DataFrame:
    """
    Analyze race pace (consistency over stint)
    """
    pace_data = []
    
    for driver in drivers:
        driver_laps = session.laps.pick_drivers(driver)
        driver_laps = driver_laps.pick_accurate()  # Only accurate laps
        driver_laps = driver_laps.pick_wo_box()  # Exclude pit laps
        
        if driver_laps.empty:
            continue
        
        lap_times = driver_laps['LapTime'].dropna()
        
        if len(lap_times) > 0:
            pace_data.append({
                'Driver': driver,
                'Team': driver_laps.iloc[0]['Team'],
                'AvgLapTime': lap_times.mean().total_seconds(),
                'MedianLapTime': lap_times.median().total_seconds(),
                'StdLapTime': lap_times.std().total_seconds() if len(lap_times) > 1 else 0,
                'FastestLap': lap_times.min().total_seconds(),
                'TotalLaps': len(lap_times)
            })
    
    df = pd.DataFrame(pace_data)
    if not df.empty:
        df = df.sort_values('AvgLapTime')
    return df


def calculate_season_progression(
    year: int,
    team: str,
    drivers: List[str]
) -> pd.DataFrame:
    """
    Track car performance improvements across the season
    """
    schedule = get_event_schedule(year)
    races = schedule[schedule['EventFormat'] != 'testing']['EventName'].tolist()
    
    progression = []
    
    for i, race in enumerate(races):
        try:
            session = load_session(year, race, 'Q')
            gaps = calculate_gap_to_leader(session)
            
            if gaps.empty:
                continue
            
            # Find best team driver position
            team_gaps = gaps[gaps['Driver'].isin(drivers)]
            if team_gaps.empty:
                continue
            
            best_gap = team_gaps['GapToLeader'].min()
            best_driver = team_gaps.loc[team_gaps['GapToLeader'].idxmin(), 'Driver']
            
            # Get position
            position = gaps[gaps['Driver'] == best_driver].index[0] + 1
            
            progression.append({
                'Round': i + 1,
                'Race': race,
                'BestDriver': best_driver,
                'GapToP1': best_gap,
                'Position': position,
                'Team': team
            })
            
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    return pd.DataFrame(progression)


def compare_eras(configs: Dict[str, ComparisonConfig]) -> pd.DataFrame:
    """
    Compare dominance and performance across different eras
    """
    era_comparison = []
    
    for era_name, config in configs.items():
        print(f"\nAnalyzing {era_name}...")
        
        # Calculate metrics for primary car
        try:
            dominance = calculate_dominance_metrics(
                config.year,
                config.primary_car.team,
                config.primary_car.drivers
            )
            
            era_comparison.append({
                'Era': era_name,
                'Car': config.primary_car.car_name,
                'Team': config.primary_car.team,
                'Year': config.year,
                'Poles': dominance.poles,
                'Wins': dominance.wins,
                'Podiums': dominance.podiums,
                'OneTwos': dominance.one_twos,
                'AvgGapToP2': dominance.avg_gap_to_p2,
                'Consistency': dominance.consistency_score,
                'RacesAnalyzed': dominance.races_analyzed
            })
            
        except Exception as e:
            print(f"Error analyzing {era_name}: {e}")
            continue
    
    return pd.DataFrame(era_comparison)


def get_quali_battle_summary(
    year: int,
    drivers: List[str]
) -> Dict:
    """
    Get qualifying battle summary between teammates
    """
    schedule = get_event_schedule(year)
    races = schedule[schedule['EventFormat'] != 'testing']['EventName'].tolist()
    
    if len(drivers) < 2:
        return {}
    
    driver1, driver2 = drivers[0], drivers[1]
    battles = {driver1: 0, driver2: 0}
    gaps = []
    
    for race in races:
        try:
            session = load_session(year, race, 'Q')
            
            lap1 = get_driver_fastest_lap(session, driver1)
            lap2 = get_driver_fastest_lap(session, driver2)
            
            if lap1 is not None and lap2 is not None:
                time1 = lap1['LapTime'].total_seconds() if pd.notna(lap1['LapTime']) else None
                time2 = lap2['LapTime'].total_seconds() if pd.notna(lap2['LapTime']) else None
                
                if time1 and time2:
                    if time1 < time2:
                        battles[driver1] += 1
                    else:
                        battles[driver2] += 1
                    gaps.append(abs(time1 - time2))
                    
        except Exception:
            continue
    
    return {
        'drivers': drivers,
        'battles': battles,
        'avg_gap': np.mean(gaps) if gaps else 0,
        'total_sessions': battles[driver1] + battles[driver2]
    }


if __name__ == "__main__":
    # Test analysis functions
    print("Testing analysis module...")
    
    # Test gap calculation for a single race
    session = load_session(2023, "Bahrain", "Q")
    gaps = calculate_gap_to_leader(session)
    print("\nBahrain 2023 Q Gaps:")
    print(gaps.head(10))
    
    # Test telemetry comparison
    ver_lap = get_driver_fastest_lap(session, "VER")
    lec_lap = get_driver_fastest_lap(session, "LEC")
    
    if ver_lap is not None and lec_lap is not None:
        comparison = compare_telemetry(ver_lap, lec_lap, "Verstappen", "Leclerc")
        print(f"\nTelemetry comparison points: {len(comparison.get('distance', []))}")
    
    # Test race pace analysis
    race_session = load_session(2023, "Bahrain", "R")
    pace = calculate_race_pace_analysis(race_session, ["VER", "LEC", "HAM"])
    print("\nRace pace analysis:")
    print(pace)
