"""
Formula 1 Driving Assistant - Data Loader Module

Handles all FastF1 API interactions for fetching:
- Available tracks/events per season
- Track layouts and session types
- Fastest lap data and telemetry
- Driving zone analysis (braking, acceleration, turning)
"""

import fastf1
import fastf1.plotting
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass


# Enable FastF1 cache for faster subsequent loads
CACHE_DIR = Path(__file__).parent / ".fastf1_cache"
CACHE_DIR.mkdir(exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))


@dataclass
class LapInfo:
    """Container for lap information"""
    driver: str
    team: str
    lap_time: str
    lap_time_seconds: float
    session_type: str
    compound: str


@dataclass
class TelemetryData:
    """Container for processed telemetry data"""
    x: np.ndarray
    y: np.ndarray
    speed: np.ndarray
    throttle: np.ndarray
    brake: np.ndarray
    gear: np.ndarray
    distance: np.ndarray
    time: np.ndarray
    drs: np.ndarray


@dataclass
class DrivingZones:
    """Container for driving zone analysis"""
    braking_zones: List[Tuple[int, int]]      # (start_idx, end_idx) pairs
    acceleration_zones: List[Tuple[int, int]]
    coasting_zones: List[Tuple[int, int]]
    full_throttle_zones: List[Tuple[int, int]]
    corner_zones: List[Dict[str, Any]]        # Contains corner info with apex


@dataclass
class WeatherData:
    """Container for weather/track conditions"""
    air_temp: float
    track_temp: float
    humidity: float
    pressure: float
    wind_speed: float
    wind_direction: float
    rainfall: bool
    
    def get_condition_string(self) -> str:
        """Return a human-readable weather condition string."""
        if self.rainfall:
            return "WET"
        elif self.track_temp > 40:
            return "HOT"
        elif self.track_temp < 20:
            return "COLD"
        else:
            return "DRY"


@dataclass
class TrackConditions:
    """Container for overall track/session conditions"""
    weather: WeatherData
    tire_compound: str
    tire_life: int
    driver: str
    team: str
    session_type: str
    track_name: str
    
    def get_tire_color(self) -> str:
        """Return tire compound color."""
        colors = {
            'SOFT': '#FF0000',       # Red
            'MEDIUM': '#FFD700',     # Yellow
            'HARD': '#FFFFFF',       # White
            'INTERMEDIATE': '#00FF00', # Green
            'WET': '#0088FF',        # Blue
        }
        return colors.get(self.tire_compound.upper(), '#888888')


@dataclass
class CornerInfo:
    """Enhanced corner information with classification"""
    number: int
    name: str
    entry_idx: int
    apex_idx: int
    exit_idx: int
    entry_speed: float
    apex_speed: float
    exit_speed: float
    apex_gear: int
    x: float
    y: float
    distance: float
    speed_class: str        # 'HIGH_SPEED', 'MEDIUM_SPEED', 'LOW_SPEED'
    corner_type: str        # 'HAIRPIN', 'SWEEPER', 'CHICANE', '90_DEGREE', 'KINK'
    direction: str          # 'LEFT', 'RIGHT'
    angle: float            # Turn angle in degrees


def get_available_seasons() -> List[int]:
    """Get list of available F1 seasons (2018 onwards has good telemetry data)"""
    current_year = 2026
    return list(range(2018, current_year + 1))


def get_season_schedule(year: int) -> List[Dict[str, Any]]:
    """
    Get all events (races) for a given season.
    
    Returns list of dicts with:
        - round_number: int
        - event_name: str
        - country: str
        - circuit_name: str
        - date: str
    """
    try:
        schedule = fastf1.get_event_schedule(year)
        events = []
        
        for idx, row in schedule.iterrows():
            # Skip testing events
            if 'test' in str(row.get('EventName', '')).lower():
                continue
            if pd.isna(row.get('RoundNumber')) or row.get('RoundNumber') == 0:
                continue
                
            events.append({
                'round_number': int(row['RoundNumber']),
                'event_name': row['EventName'],
                'country': row.get('Country', 'Unknown'),
                'circuit_name': row.get('Location', row['EventName']),
                'date': str(row.get('EventDate', ''))[:10]
            })
        
        return events
    except Exception as e:
        print(f"Error fetching schedule for {year}: {e}")
        return []


def get_session_types(year: int, round_number: int) -> List[str]:
    """
    Get available session types for an event.
    Returns list like: ['FP1', 'FP2', 'FP3', 'Q', 'R'] or ['FP1', 'SQ', 'S', 'Q', 'R']
    """
    try:
        event = fastf1.get_event(year, round_number)
        sessions = []
        
        # Standard sessions
        session_map = {
            'Practice 1': 'FP1',
            'Practice 2': 'FP2', 
            'Practice 3': 'FP3',
            'Qualifying': 'Q',
            'Race': 'R',
            'Sprint': 'S',
            'Sprint Qualifying': 'SQ',
            'Sprint Shootout': 'SS'
        }
        
        for i in range(1, 6):
            session_name = event.get(f'Session{i}')
            if pd.notna(session_name) and session_name in session_map:
                sessions.append(session_map[session_name])
        
        return sessions
    except Exception as e:
        print(f"Error getting sessions: {e}")
        return ['Q', 'R']  # Default fallback


def load_session(year: int, round_number: int, session_type: str = 'Q'):
    """
    Load a FastF1 session with telemetry.
    
    Args:
        year: Season year
        round_number: Race number in the season
        session_type: 'FP1', 'FP2', 'FP3', 'Q', 'R', 'S', 'SQ'
    
    Returns:
        FastF1 Session object
    """
    session = fastf1.get_session(year, round_number, session_type)
    session.load(telemetry=True, weather=True, messages=False)
    return session


def get_fastest_lap_info(session) -> Optional[LapInfo]:
    """Get information about the fastest lap in a session."""
    try:
        fastest = session.laps.pick_fastest()
        if fastest is None:
            return None
        
        lap_time = fastest['LapTime']
        if pd.isna(lap_time):
            return None
            
        # Format lap time
        total_seconds = lap_time.total_seconds()
        minutes = int(total_seconds // 60)
        seconds = total_seconds % 60
        lap_time_str = f"{minutes}:{seconds:06.3f}"
        
        return LapInfo(
            driver=str(fastest['Driver']),
            team=str(fastest.get('Team', 'Unknown')),
            lap_time=lap_time_str,
            lap_time_seconds=total_seconds,
            session_type=session.name,
            compound=str(fastest.get('Compound', 'Unknown'))
        )
    except Exception as e:
        print(f"Error getting fastest lap: {e}")
        return None


def get_lap_telemetry(session, driver: Optional[str] = None) -> Optional[TelemetryData]:
    """
    Get telemetry data for the fastest lap.
    
    Args:
        session: FastF1 session object
        driver: Optional driver code. If None, uses overall fastest.
    
    Returns:
        TelemetryData object with all telemetry arrays
    """
    try:
        if driver:
            laps = session.laps.pick_drivers(driver)
            fastest = laps.pick_fastest()
        else:
            fastest = session.laps.pick_fastest()
        
        if fastest is None:
            return None
        
        telemetry = fastest.get_telemetry()
        
        if telemetry is None or telemetry.empty:
            return None
        
        return TelemetryData(
            x=telemetry['X'].to_numpy(),
            y=telemetry['Y'].to_numpy(),
            speed=telemetry['Speed'].to_numpy(),
            throttle=telemetry['Throttle'].to_numpy(),
            brake=telemetry['Brake'].to_numpy().astype(float),
            gear=telemetry['nGear'].to_numpy(),
            distance=telemetry['Distance'].to_numpy(),
            time=telemetry['Time'].dt.total_seconds().to_numpy(),
            drs=telemetry['DRS'].to_numpy()
        )
    except Exception as e:
        print(f"Error getting telemetry: {e}")
        return None


def analyze_driving_zones(telemetry: TelemetryData, 
                          brake_threshold: float = 10.0,
                          throttle_full_threshold: float = 95.0,
                          throttle_partial_threshold: float = 50.0,
                          min_zone_points: int = 5) -> DrivingZones:
    """
    Analyze telemetry to identify driving zones.
    
    Args:
        telemetry: TelemetryData object
        brake_threshold: Brake pressure % to consider braking
        throttle_full_threshold: Throttle % to consider full throttle
        throttle_partial_threshold: Below this = coasting/trail braking
        min_zone_points: Minimum points to form a zone
    
    Returns:
        DrivingZones with identified zones
    """
    n = len(telemetry.speed)
    
    braking_zones = []
    acceleration_zones = []
    coasting_zones = []
    full_throttle_zones = []
    corner_zones = []
    
    # Identify braking zones (brake > threshold)
    braking = telemetry.brake > brake_threshold
    braking_zones = _find_continuous_zones(braking, min_zone_points)
    
    # Identify full throttle zones
    full_throttle = telemetry.throttle >= throttle_full_threshold
    full_throttle_zones = _find_continuous_zones(full_throttle, min_zone_points)
    
    # Identify coasting zones (low throttle, low brake)
    coasting = (telemetry.throttle < throttle_partial_threshold) & (telemetry.brake < brake_threshold)
    coasting_zones = _find_continuous_zones(coasting, min_zone_points)
    
    # Identify acceleration zones (throttle increasing, speed increasing)
    speed_diff = np.diff(telemetry.speed, prepend=telemetry.speed[0])
    throttle_high = telemetry.throttle > throttle_partial_threshold
    accelerating = throttle_high & (speed_diff > 0) & ~braking
    acceleration_zones = _find_continuous_zones(accelerating, min_zone_points)
    
    # Identify corners (speed minima with surrounding deceleration/acceleration)
    corner_zones = _find_corners(telemetry, min_zone_points)
    
    return DrivingZones(
        braking_zones=braking_zones,
        acceleration_zones=acceleration_zones,
        coasting_zones=coasting_zones,
        full_throttle_zones=full_throttle_zones,
        corner_zones=corner_zones
    )


def _find_continuous_zones(mask: np.ndarray, min_points: int) -> List[Tuple[int, int]]:
    """Find continuous True regions in a boolean mask."""
    zones = []
    in_zone = False
    start_idx = 0
    
    for i, val in enumerate(mask):
        if val and not in_zone:
            in_zone = True
            start_idx = i
        elif not val and in_zone:
            in_zone = False
            if i - start_idx >= min_points:
                zones.append((start_idx, i - 1))
    
    # Handle zone that extends to the end
    if in_zone and len(mask) - start_idx >= min_points:
        zones.append((start_idx, len(mask) - 1))
    
    return zones


def _find_corners(telemetry: TelemetryData, min_points: int = 5) -> List[Dict[str, Any]]:
    """
    Find corner locations by detecting speed local minima.
    """
    corners = []
    speed = telemetry.speed
    
    # Smooth speed to reduce noise
    window = 10
    if len(speed) > window * 2:
        speed_smooth = np.convolve(speed, np.ones(window)/window, mode='same')
    else:
        speed_smooth = speed
    
    # Find local minima (potential corner apexes)
    for i in range(min_points, len(speed_smooth) - min_points):
        # Check if this is a local minimum
        is_minimum = True
        for j in range(1, min_points + 1):
            if speed_smooth[i] >= speed_smooth[i - j] or speed_smooth[i] >= speed_smooth[i + j]:
                is_minimum = False
                break
        
        if is_minimum and speed_smooth[i] < np.mean(speed_smooth) * 0.9:
            # Find entry (where braking starts) and exit (where acceleration ends)
            entry_idx = i
            exit_idx = i
            
            # Search backward for corner entry
            for j in range(i - 1, max(0, i - 100), -1):
                if speed_smooth[j] > speed_smooth[j + 1]:
                    entry_idx = j
                else:
                    break
            
            # Search forward for corner exit
            for j in range(i + 1, min(len(speed_smooth) - 1, i + 100)):
                if speed_smooth[j] > speed_smooth[j - 1]:
                    exit_idx = j
                else:
                    break
            
            # Only add if not overlapping with previous corner
            if not corners or entry_idx > corners[-1]['exit_idx'] + min_points:
                corners.append({
                    'entry_idx': entry_idx,
                    'apex_idx': i,
                    'exit_idx': exit_idx,
                    'apex_speed': float(speed[i]),
                    'entry_speed': float(speed[entry_idx]),
                    'exit_speed': float(speed[exit_idx]),
                    'apex_gear': int(telemetry.gear[i]),
                    'x': float(telemetry.x[i]),
                    'y': float(telemetry.y[i]),
                    'distance': float(telemetry.distance[i])
                })
    
    # Number the corners
    for idx, corner in enumerate(corners):
        corner['number'] = idx + 1
    
    return corners


def get_circuit_info(session) -> Dict[str, Any]:
    """Get circuit metadata from session."""
    try:
        circuit = session.get_circuit_info()
        return {
            'rotation': float(circuit.rotation) if hasattr(circuit, 'rotation') else 0.0,
            'corners': circuit.corners.to_dict('records') if hasattr(circuit, 'corners') else []
        }
    except Exception:
        return {'rotation': 0.0, 'corners': []}


def get_weather_data(session) -> Optional[WeatherData]:
    """
    Get weather conditions from the session.
    Uses average values across the session.
    """
    try:
        if session.weather_data is None or session.weather_data.empty:
            return None
        
        weather = session.weather_data
        return WeatherData(
            air_temp=float(weather['AirTemp'].mean()),
            track_temp=float(weather['TrackTemp'].mean()),
            humidity=float(weather['Humidity'].mean()),
            pressure=float(weather['Pressure'].mean()),
            wind_speed=float(weather['WindSpeed'].mean()),
            wind_direction=float(weather['WindDirection'].mean()),
            rainfall=bool(weather['Rainfall'].any())
        )
    except Exception as e:
        print(f"Error getting weather data: {e}")
        return None


def get_track_conditions(session, driver: Optional[str] = None) -> Optional[TrackConditions]:
    """
    Get full track conditions including weather and tire info.
    
    Args:
        session: FastF1 session object
        driver: Optional driver code. If None, uses overall fastest.
    
    Returns:
        TrackConditions object
    """
    try:
        # Get weather
        weather = get_weather_data(session)
        if weather is None:
            weather = WeatherData(
                air_temp=25.0, track_temp=30.0, humidity=50.0,
                pressure=1013.0, wind_speed=5.0, wind_direction=0.0,
                rainfall=False
            )
        
        # Get lap info
        if driver:
            laps = session.laps.pick_drivers(driver)
            fastest = laps.pick_fastest()
        else:
            fastest = session.laps.pick_fastest()
        
        if fastest is None:
            return None
        
        compound = str(fastest.get('Compound', 'UNKNOWN'))
        tire_life = int(fastest.get('TyreLife', 0)) if pd.notna(fastest.get('TyreLife')) else 0
        driver_code = str(fastest.get('Driver', 'UNK'))
        team = str(fastest.get('Team', 'Unknown'))
        
        # Get track name
        track_name = session.event.get('EventName', 'Unknown Track')
        
        return TrackConditions(
            weather=weather,
            tire_compound=compound,
            tire_life=tire_life,
            driver=driver_code,
            team=team,
            session_type=session.name,
            track_name=track_name
        )
    except Exception as e:
        print(f"Error getting track conditions: {e}")
        return None


def classify_corner_type(entry_speed: float, apex_speed: float, exit_speed: float, 
                         angle: float, track_avg_speed: float) -> Tuple[str, str]:
    """
    Classify corner by type and speed class.
    
    Returns:
        Tuple of (speed_class, corner_type)
    """
    # Speed classification based on apex speed relative to track average
    speed_ratio = apex_speed / track_avg_speed if track_avg_speed > 0 else 0.5
    
    if speed_ratio > 0.75:
        speed_class = 'HIGH_SPEED'
    elif speed_ratio > 0.50:
        speed_class = 'MEDIUM_SPEED'
    else:
        speed_class = 'LOW_SPEED'
    
    # Corner type based on angle and speed
    abs_angle = abs(angle) if angle else 90
    
    if abs_angle >= 150:
        corner_type = 'HAIRPIN'
    elif abs_angle <= 30:
        corner_type = 'KINK'
    elif abs_angle <= 60 and speed_class == 'HIGH_SPEED':
        corner_type = 'SWEEPER'
    elif abs_angle >= 80 and abs_angle <= 100:
        corner_type = '90_DEGREE'
    elif speed_class == 'LOW_SPEED' and abs_angle > 100:
        corner_type = 'HAIRPIN'
    else:
        corner_type = 'SWEEPER' if speed_class == 'HIGH_SPEED' else '90_DEGREE'
    
    return speed_class, corner_type


def get_corner_direction(x_before: float, y_before: float, x_apex: float, y_apex: float,
                         x_after: float, y_after: float) -> Tuple[str, float]:
    """
    Determine corner direction and angle.
    
    Returns:
        Tuple of (direction, angle_degrees)
    """
    # Vector from before to apex
    v1x = x_apex - x_before
    v1y = y_apex - y_before
    
    # Vector from apex to after
    v2x = x_after - x_apex
    v2y = y_after - y_apex
    
    # Cross product to determine direction
    cross = v1x * v2y - v1y * v2x
    
    # Dot product for angle
    dot = v1x * v2x + v1y * v2y
    mag1 = np.sqrt(v1x**2 + v1y**2)
    mag2 = np.sqrt(v2x**2 + v2y**2)
    
    if mag1 > 0 and mag2 > 0:
        cos_angle = dot / (mag1 * mag2)
        cos_angle = np.clip(cos_angle, -1, 1)
        angle = np.degrees(np.arccos(cos_angle))
    else:
        angle = 90.0
    
    direction = 'RIGHT' if cross > 0 else 'LEFT'
    
    return direction, 180 - angle  # Convert to turn angle


def get_enhanced_corners(session, telemetry: TelemetryData, 
                         corner_zones: List[Dict[str, Any]]) -> List[CornerInfo]:
    """
    Enhance corner data with official names and classifications.
    
    Args:
        session: FastF1 session object
        telemetry: TelemetryData object
        corner_zones: Basic corner data from analyze_driving_zones
    
    Returns:
        List of CornerInfo objects with full classification
    """
    enhanced_corners = []
    
    # Get official corner data from circuit info
    try:
        circuit_info = session.get_circuit_info()
        official_corners = circuit_info.corners.to_dict('records') if hasattr(circuit_info, 'corners') else []
    except:
        official_corners = []
    
    # Calculate track average speed for classification
    track_avg_speed = float(np.mean(telemetry.speed))
    
    for i, corner in enumerate(corner_zones):
        # Find closest official corner by distance
        corner_name = f"Turn {corner['number']}"
        corner_angle = 90.0  # Default
        
        for official in official_corners:
            official_dist = official.get('Distance', 0)
            corner_dist = corner.get('distance', 0)
            
            if abs(official_dist - corner_dist) < 150:  # Within 150m
                corner_num = official.get('Number', corner['number'])
                corner_letter = official.get('Letter', '')
                if corner_letter:
                    corner_name = f"Turn {corner_num}{corner_letter}"
                else:
                    corner_name = f"Turn {corner_num}"
                corner_angle = abs(official.get('Angle', 90.0))
                break
        
        # Get direction and angle from telemetry
        apex_idx = corner['apex_idx']
        entry_idx = corner['entry_idx']
        exit_idx = corner['exit_idx']
        
        # Sample points for direction calculation
        before_idx = max(0, entry_idx - 20)
        after_idx = min(len(telemetry.x) - 1, exit_idx + 20)
        
        direction, turn_angle = get_corner_direction(
            telemetry.x[before_idx], telemetry.y[before_idx],
            telemetry.x[apex_idx], telemetry.y[apex_idx],
            telemetry.x[after_idx], telemetry.y[after_idx]
        )
        
        # Use calculated angle if official not available
        if corner_angle == 90.0:
            corner_angle = turn_angle
        
        # Classify corner
        speed_class, corner_type = classify_corner_type(
            corner['entry_speed'],
            corner['apex_speed'],
            corner['exit_speed'],
            corner_angle,
            track_avg_speed
        )
        
        enhanced_corners.append(CornerInfo(
            number=corner['number'],
            name=corner_name,
            entry_idx=entry_idx,
            apex_idx=apex_idx,
            exit_idx=exit_idx,
            entry_speed=corner['entry_speed'],
            apex_speed=corner['apex_speed'],
            exit_speed=corner['exit_speed'],
            apex_gear=corner['apex_gear'],
            x=corner['x'],
            y=corner['y'],
            distance=corner['distance'],
            speed_class=speed_class,
            corner_type=corner_type,
            direction=direction,
            angle=corner_angle
        ))
    
    return enhanced_corners


def get_driver_colors(session) -> Dict[str, Tuple[int, int, int]]:
    """Get team colors for each driver."""
    try:
        color_mapping = fastf1.plotting.get_driver_color_mapping(session)
        rgb_colors = {}
        for driver, hex_color in color_mapping.items():
            hex_color = hex_color.lstrip('#')
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            rgb_colors[driver] = rgb
        return rgb_colors
    except Exception:
        return {}


def get_all_drivers_fastest_laps(session) -> List[Dict[str, Any]]:
    """Get fastest lap info for all drivers in session."""
    drivers = []
    
    try:
        for driver in session.drivers:
            driver_laps = session.laps.pick_drivers(driver)
            if driver_laps.empty:
                continue
            
            fastest = driver_laps.pick_fastest()
            if fastest is None or pd.isna(fastest.get('LapTime')):
                continue
            
            lap_time = fastest['LapTime'].total_seconds()
            minutes = int(lap_time // 60)
            seconds = lap_time % 60
            
            drivers.append({
                'driver': str(fastest['Driver']),
                'team': str(fastest.get('Team', 'Unknown')),
                'lap_time': f"{minutes}:{seconds:06.3f}",
                'lap_time_seconds': lap_time,
                'compound': str(fastest.get('Compound', 'Unknown'))
            })
        
        # Sort by lap time
        drivers.sort(key=lambda x: x['lap_time_seconds'])
        
        return drivers
    except Exception as e:
        print(f"Error getting driver laps: {e}")
        return []


if __name__ == "__main__":
    # Quick test
    print("Testing Data Loader...")
    print("\nAvailable seasons:", get_available_seasons())
    
    print("\n2024 Schedule:")
    schedule = get_season_schedule(2024)
    for event in schedule[:3]:
        print(f"  Round {event['round_number']}: {event['event_name']} ({event['circuit_name']})")
    
    print("\nLoading Monaco 2024 Qualifying...")
    session = load_session(2024, 8, 'Q')  # Monaco is typically round 8
    
    fastest = get_fastest_lap_info(session)
    if fastest:
        print(f"Fastest lap: {fastest.driver} - {fastest.lap_time}")
    
    telemetry = get_lap_telemetry(session)
    if telemetry:
        print(f"Telemetry points: {len(telemetry.speed)}")
        zones = analyze_driving_zones(telemetry)
        print(f"Braking zones: {len(zones.braking_zones)}")
        print(f"Corners detected: {len(zones.corner_zones)}")
