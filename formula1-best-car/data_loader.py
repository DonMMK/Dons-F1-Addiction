"""
Data Loader Module for F1 Car Comparison Analysis
Fetches and caches F1 session data using FastF1 API
"""

import fastf1
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


# Enable caching for faster subsequent loads
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))


@dataclass
class CarConfig:
    """Configuration for a car to analyze"""
    year: int
    team: str
    car_name: str
    drivers: List[str]  # Driver abbreviations
    color: str  # Hex color for plotting


@dataclass
class ComparisonConfig:
    """Configuration for a comparison era"""
    name: str
    year: int
    primary_car: CarConfig
    competitors: List[CarConfig]
    races: Optional[List[str]] = None  # If None, analyze all races


# Define the three comparison eras
COMPARISON_CONFIGS = {
    "2020": ComparisonConfig(
        name="2020 - Mercedes W11 Era",
        year=2020,
        primary_car=CarConfig(
            year=2020,
            team="Mercedes",
            car_name="W11",
            drivers=["HAM", "BOT"],
            color="#00D2BE"
        ),
        competitors=[
            CarConfig(
                year=2020,
                team="Red Bull",
                car_name="RB16",
                drivers=["VER", "ALB"],
                color="#0600EF"
            ),
            CarConfig(
                year=2020,
                team="Racing Point",
                car_name="RP20",
                drivers=["PER", "STR"],
                color="#F596C8"
            ),
        ]
    ),
    "2023": ComparisonConfig(
        name="2023 - Red Bull RB19 Era",
        year=2023,
        primary_car=CarConfig(
            year=2023,
            team="Red Bull Racing",
            car_name="RB19",
            drivers=["VER", "PER"],
            color="#3671C6"
        ),
        competitors=[
            CarConfig(
                year=2023,
                team="Mercedes",
                car_name="W14",
                drivers=["HAM", "RUS"],
                color="#27F4D2"
            ),
            CarConfig(
                year=2023,
                team="Ferrari",
                car_name="SF-23",
                drivers=["LEC", "SAI"],
                color="#E8002D"
            ),
        ]
    ),
    "2025": ComparisonConfig(
        name="2025 - McLaren MCL39 Era",
        year=2025,
        primary_car=CarConfig(
            year=2025,
            team="McLaren",
            car_name="MCL39",
            drivers=["NOR", "PIA"],
            color="#FF8700"
        ),
        competitors=[
            CarConfig(
                year=2025,
                team="Mercedes",
                car_name="W16",
                drivers=["RUS", "ANT"],
                color="#27F4D2"
            ),
            CarConfig(
                year=2025,
                team="Red Bull Racing",
                car_name="RB21",
                drivers=["VER", "LAW"],
                color="#3671C6"
            ),
        ]
    ),
}


def get_event_schedule(year: int) -> pd.DataFrame:
    """Get the event schedule for a given year"""
    schedule = fastf1.get_event_schedule(year)
    # Filter to only include races (not testing)
    schedule = schedule[schedule['EventFormat'] != 'testing']
    return schedule


def load_session(year: int, race: str | int, session_type: str = 'R') -> fastf1.core.Session:
    """
    Load a session with all telemetry data
    
    Parameters:
    -----------
    year : int
        Season year
    race : str or int
        Race name or round number
    session_type : str
        'R' for Race, 'Q' for Qualifying, 'FP1', 'FP2', 'FP3' for practice
    
    Returns:
    --------
    fastf1.core.Session
        Loaded session object with all data
    """
    session = fastf1.get_session(year, race, session_type)
    session.load(telemetry=True, laps=True, weather=True, messages=True)
    return session


def get_driver_fastest_lap(session: fastf1.core.Session, driver: str) -> Optional[fastf1.core.Lap]:
    """Get the fastest lap for a specific driver in a session"""
    driver_laps = session.laps.pick_drivers(driver)
    if driver_laps.empty:
        return None
    fastest = driver_laps.pick_fastest()
    return fastest


def get_team_fastest_lap(session: fastf1.core.Session, team: str) -> Optional[fastf1.core.Lap]:
    """Get the fastest lap for a specific team in a session"""
    team_laps = session.laps.pick_teams(team)
    if team_laps.empty:
        return None
    fastest = team_laps.pick_fastest()
    return fastest


def get_qualifying_results(session: fastf1.core.Session) -> pd.DataFrame:
    """Get qualifying results sorted by position"""
    results = session.results.copy()
    results = results.sort_values('Position')
    return results


def get_race_results(session: fastf1.core.Session) -> pd.DataFrame:
    """Get race results sorted by position"""
    results = session.results.copy()
    results = results.sort_values('Position')
    return results


def get_lap_telemetry(lap: fastf1.core.Lap) -> pd.DataFrame:
    """
    Get telemetry data for a specific lap
    Includes: Speed, Throttle, Brake, Gear, RPM, DRS, Distance, X, Y, Z
    """
    if lap is None:
        return pd.DataFrame()
    
    telemetry = lap.get_telemetry()
    return telemetry


def get_car_data_for_lap(lap: fastf1.core.Lap) -> pd.DataFrame:
    """Get car-specific data (speed, throttle, brake, etc.) for a lap"""
    if lap is None:
        return pd.DataFrame()
    
    car_data = lap.get_car_data()
    car_data = car_data.add_distance()
    return car_data


def get_position_data_for_lap(lap: fastf1.core.Lap) -> pd.DataFrame:
    """Get position data (X, Y, Z coordinates) for a lap"""
    if lap is None:
        return pd.DataFrame()
    
    pos_data = lap.get_pos_data()
    return pos_data


def load_season_data(config: ComparisonConfig, session_type: str = 'Q') -> Dict:
    """
    Load data for an entire season based on comparison config
    
    Parameters:
    -----------
    config : ComparisonConfig
        Configuration for the comparison era
    session_type : str
        Session type to load ('Q' for qualifying, 'R' for race)
    
    Returns:
    --------
    Dict containing session data for each race
    """
    schedule = get_event_schedule(config.year)
    
    season_data = {
        'year': config.year,
        'config': config,
        'races': {}
    }
    
    # Get list of races to analyze
    if config.races:
        race_list = config.races
    else:
        # Use conventional races only (exclude sprints, etc.)
        race_list = schedule[schedule['EventFormat'].isin(['conventional', 'sprint_shootout', 'sprint_qualifying', 'sprint'])]['EventName'].tolist()
    
    for race_name in race_list:
        try:
            print(f"Loading {config.year} {race_name} {session_type}...")
            session = load_session(config.year, race_name, session_type)
            
            race_data = {
                'session': session,
                'primary': {},
                'competitors': {}
            }
            
            # Load primary car data
            for driver in config.primary_car.drivers:
                fastest_lap = get_driver_fastest_lap(session, driver)
                if fastest_lap is not None:
                    race_data['primary'][driver] = {
                        'lap': fastest_lap,
                        'telemetry': get_lap_telemetry(fastest_lap),
                        'lap_time': fastest_lap['LapTime']
                    }
            
            # Load competitor data
            for competitor in config.competitors:
                race_data['competitors'][competitor.team] = {}
                for driver in competitor.drivers:
                    fastest_lap = get_driver_fastest_lap(session, driver)
                    if fastest_lap is not None:
                        race_data['competitors'][competitor.team][driver] = {
                            'lap': fastest_lap,
                            'telemetry': get_lap_telemetry(fastest_lap),
                            'lap_time': fastest_lap['LapTime']
                        }
            
            season_data['races'][race_name] = race_data
            
        except Exception as e:
            print(f"Error loading {race_name}: {e}")
            continue
    
    return season_data


def get_sector_times(session: fastf1.core.Session, drivers: List[str]) -> pd.DataFrame:
    """
    Get sector times for specific drivers
    
    Returns DataFrame with columns: Driver, Sector1Time, Sector2Time, Sector3Time
    """
    all_sectors = []
    
    for driver in drivers:
        fastest_lap = get_driver_fastest_lap(session, driver)
        if fastest_lap is not None:
            all_sectors.append({
                'Driver': driver,
                'Sector1Time': fastest_lap['Sector1Time'],
                'Sector2Time': fastest_lap['Sector2Time'],
                'Sector3Time': fastest_lap['Sector3Time'],
                'LapTime': fastest_lap['LapTime'],
                'Team': fastest_lap['Team']
            })
    
    return pd.DataFrame(all_sectors)


def get_speed_traps(session: fastf1.core.Session, drivers: List[str]) -> pd.DataFrame:
    """
    Get speed trap data for specific drivers
    
    Returns DataFrame with speed trap values
    """
    all_speeds = []
    
    for driver in drivers:
        fastest_lap = get_driver_fastest_lap(session, driver)
        if fastest_lap is not None:
            all_speeds.append({
                'Driver': driver,
                'SpeedI1': fastest_lap['SpeedI1'],
                'SpeedI2': fastest_lap['SpeedI2'],
                'SpeedFL': fastest_lap['SpeedFL'],
                'SpeedST': fastest_lap['SpeedST'],
                'Team': fastest_lap['Team']
            })
    
    return pd.DataFrame(all_speeds)


def get_circuit_info(session: fastf1.core.Session):
    """Get circuit information including corner locations"""
    return session.get_circuit_info()


def calculate_gap_to_leader(session: fastf1.core.Session) -> pd.DataFrame:
    """
    Calculate the gap from each driver's fastest lap to the leader
    
    Returns DataFrame with driver, lap time, and gap to leader
    """
    laps = session.laps.pick_fastest()
    
    # Get all fastest laps
    fastest_laps = []
    for driver in session.drivers:
        driver_fastest = get_driver_fastest_lap(session, driver)
        if driver_fastest is not None and pd.notna(driver_fastest['LapTime']):
            fastest_laps.append({
                'Driver': driver,
                'Team': driver_fastest['Team'],
                'LapTime': driver_fastest['LapTime'],
                'LapTimeSeconds': driver_fastest['LapTime'].total_seconds()
            })
    
    df = pd.DataFrame(fastest_laps)
    if df.empty:
        return df
    
    df = df.sort_values('LapTimeSeconds')
    leader_time = df['LapTimeSeconds'].min()
    df['GapToLeader'] = df['LapTimeSeconds'] - leader_time
    df['GapToLeaderPercent'] = (df['GapToLeader'] / leader_time) * 100
    
    return df


if __name__ == "__main__":
    # Test the data loader
    print("Testing data loader...")
    
    # Test loading a single session
    print("\nLoading 2023 Bahrain Qualifying...")
    session = load_session(2023, "Bahrain", "Q")
    print(f"Session loaded: {session.event['EventName']}")
    print(f"Drivers: {session.drivers}")
    
    # Test getting fastest lap
    ver_lap = get_driver_fastest_lap(session, "VER")
    if ver_lap is not None:
        print(f"\nVerstappen fastest lap: {ver_lap['LapTime']}")
        
        # Test telemetry
        telemetry = get_lap_telemetry(ver_lap)
        print(f"Telemetry points: {len(telemetry)}")
    
    # Test gap calculation
    gaps = calculate_gap_to_leader(session)
    print("\nGaps to leader:")
    print(gaps.head(10))
