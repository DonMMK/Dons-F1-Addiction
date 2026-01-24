"""
Visualization Module for F1 Car Comparison
Beautiful charts optimized for TikTok content using team colors
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import fastf1
import fastf1.plotting

from data_loader import (
    CarConfig, ComparisonConfig, COMPARISON_CONFIGS,
    load_session, get_driver_fastest_lap, get_lap_telemetry,
    get_circuit_info, calculate_gap_to_leader
)
from analysis import compare_telemetry, analyze_corner_performance

# Setup FastF1 plotting
fastf1.plotting.setup_mpl(mpl_timedelta_support=True, color_scheme='fastf1')

# TikTok-friendly figure sizes (9:16 aspect ratio)
TIKTOK_FIGSIZE = (9, 16)
TIKTOK_FIGSIZE_WIDE = (16, 9)  # For horizontal content
TIKTOK_DPI = 200

# Custom team colors (fallback)
TEAM_COLORS = {
    'Mercedes': '#00D2BE',
    'Red Bull Racing': '#3671C6',
    'Red Bull': '#0600EF',
    'Ferrari': '#E8002D',
    'McLaren': '#FF8700',
    'Alpine': '#FF87BC',
    'Aston Martin': '#006F62',
    'AlphaTauri': '#4E7C9B',
    'RB': '#6692FF',
    'Alfa Romeo': '#B12039',
    'Haas': '#B6BABD',
    'Williams': '#64C4FF',
    'Racing Point': '#F596C8',
    'Sauber': '#52E252'
}


def get_team_color(team: str, session: Optional[fastf1.core.Session] = None) -> str:
    """Get team color, trying FastF1 first, then fallback"""
    try:
        if session is not None:
            return fastf1.plotting.get_team_color(team, session)
    except:
        pass
    
    # Fallback to custom colors
    for key, color in TEAM_COLORS.items():
        if key.lower() in team.lower() or team.lower() in key.lower():
            return color
    return '#FFFFFF'


def create_speed_trace_comparison(
    session: fastf1.core.Session,
    drivers: List[str],
    title: str = "Speed Trace Comparison",
    save_path: Optional[str] = None
) -> plt.Figure:
    """
    Create a speed trace comparison chart with team colors
    Perfect for showing raw pace differences
    """
    fig, ax = plt.subplots(figsize=TIKTOK_FIGSIZE_WIDE, dpi=TIKTOK_DPI)
    fig.patch.set_facecolor('#1E1E1E')
    ax.set_facecolor('#1E1E1E')
    
    for driver in drivers:
        lap = get_driver_fastest_lap(session, driver)
        if lap is None:
            continue
            
        telemetry = get_lap_telemetry(lap)
        if telemetry.empty:
            continue
        
        # Add distance if not present
        if 'Distance' not in telemetry.columns:
            telemetry = telemetry.add_distance()
        
        # Get team color
        team = lap['Team']
        color = get_team_color(team, session)
        
        # Get driver style for line differentiation
        try:
            style = fastf1.plotting.get_driver_style(driver, ['color', 'linestyle'], session)
            linestyle = style.get('linestyle', '-')
        except:
            linestyle = '-'
        
        ax.plot(
            telemetry['Distance'],
            telemetry['Speed'],
            label=f"{driver} ({lap['LapTime']})" if pd.notna(lap['LapTime']) else driver,
            color=color,
            linestyle=linestyle,
            linewidth=2
        )
    
    ax.set_xlabel('Distance (m)', color='white', fontsize=12)
    ax.set_ylabel('Speed (km/h)', color='white', fontsize=12)
    ax.set_title(title, color='white', fontsize=16, fontweight='bold')
    ax.tick_params(colors='white')
    ax.spines['bottom'].set_color('white')
    ax.spines['left'].set_color('white')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(loc='lower right', facecolor='#2E2E2E', edgecolor='white', labelcolor='white')
    ax.grid(True, alpha=0.3, color='gray')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=TIKTOK_DPI, facecolor='#1E1E1E', bbox_inches='tight')
    
    return fig


def create_track_speed_map(
    session: fastf1.core.Session,
    driver: str,
    title: str = "Track Speed Map",
    save_path: Optional[str] = None,
    colormap: str = 'RdYlGn'
) -> plt.Figure:
    """
    Create a track map colored by speed
    Shows which parts of the track are fast/slow
    """
    lap = get_driver_fastest_lap(session, driver)
    if lap is None:
        return None
    
    telemetry = get_lap_telemetry(lap)
    if telemetry.empty:
        return None
    
    # Get position data
    x = telemetry['X'].values
    y = telemetry['Y'].values
    speed = telemetry['Speed'].values
    
    # Rotate track if circuit info available
    circuit_info = get_circuit_info(session)
    if circuit_info is not None:
        rotation = circuit_info.rotation
        # Apply rotation
        x_rot = x * np.cos(np.radians(rotation)) - y * np.sin(np.radians(rotation))
        y_rot = x * np.sin(np.radians(rotation)) + y * np.cos(np.radians(rotation))
        x, y = x_rot, y_rot
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 12), dpi=TIKTOK_DPI)
    fig.patch.set_facecolor('#1E1E1E')
    ax.set_facecolor('#1E1E1E')
    
    # Create colored line segments
    points = np.array([x, y]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    
    # Normalize speed for colormap
    norm = Normalize(vmin=speed.min(), vmax=speed.max())
    lc = LineCollection(segments, cmap=colormap, norm=norm, linewidth=4)
    lc.set_array(speed)
    
    ax.add_collection(lc)
    ax.autoscale()
    ax.set_aspect('equal')
    ax.axis('off')
    
    # Add colorbar
    cbar = plt.colorbar(lc, ax=ax, shrink=0.8)
    cbar.set_label('Speed (km/h)', color='white', fontsize=12)
    cbar.ax.yaxis.set_tick_params(color='white')
    cbar.outline.set_edgecolor('white')
    plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color='white')
    
    # Title
    team = lap['Team']
    color = get_team_color(team, session)
    ax.set_title(f"{title}\n{driver} - {lap['LapTime']}", 
                 color=color, fontsize=18, fontweight='bold')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=TIKTOK_DPI, facecolor='#1E1E1E', bbox_inches='tight')
    
    return fig


def create_track_comparison_map(
    session: fastf1.core.Session,
    driver1: str,
    driver2: str,
    title: str = "Track Comparison",
    save_path: Optional[str] = None
) -> plt.Figure:
    """
    Create a track map showing which driver is faster at each point
    Color-coded by team colors
    """
    lap1 = get_driver_fastest_lap(session, driver1)
    lap2 = get_driver_fastest_lap(session, driver2)
    
    if lap1 is None or lap2 is None:
        return None
    
    tel1 = get_lap_telemetry(lap1)
    tel2 = get_lap_telemetry(lap2)
    
    if tel1.empty or tel2.empty:
        return None
    
    # Add distance
    if 'Distance' not in tel1.columns:
        tel1 = tel1.add_distance()
    if 'Distance' not in tel2.columns:
        tel2 = tel2.add_distance()
    
    # Get colors
    color1 = get_team_color(lap1['Team'], session)
    color2 = get_team_color(lap2['Team'], session)
    
    # Interpolate to common distance points
    max_dist = min(tel1['Distance'].max(), tel2['Distance'].max())
    distance_points = np.linspace(0, max_dist, 1000)
    
    speed1 = np.interp(distance_points, tel1['Distance'], tel1['Speed'])
    speed2 = np.interp(distance_points, tel2['Distance'], tel2['Speed'])
    x = np.interp(distance_points, tel1['Distance'], tel1['X'])
    y = np.interp(distance_points, tel1['Distance'], tel1['Y'])
    
    # Rotate if needed
    circuit_info = get_circuit_info(session)
    if circuit_info is not None:
        rotation = circuit_info.rotation
        x_rot = x * np.cos(np.radians(rotation)) - y * np.sin(np.radians(rotation))
        y_rot = x * np.sin(np.radians(rotation)) + y * np.cos(np.radians(rotation))
        x, y = x_rot, y_rot
    
    # Determine who is faster at each point
    speed_diff = speed1 - speed2  # Positive = driver1 faster
    
    # Create custom colormap
    cmap = LinearSegmentedColormap.from_list('team_cmap', [color2, '#FFFFFF', color1])
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 12), dpi=TIKTOK_DPI)
    fig.patch.set_facecolor('#1E1E1E')
    ax.set_facecolor('#1E1E1E')
    
    # Create colored line segments
    points = np.array([x, y]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    
    # Normalize speed difference
    max_diff = max(abs(speed_diff.min()), abs(speed_diff.max()))
    norm = Normalize(vmin=-max_diff, vmax=max_diff)
    
    lc = LineCollection(segments, cmap=cmap, norm=norm, linewidth=5)
    lc.set_array(speed_diff)
    
    ax.add_collection(lc)
    ax.autoscale()
    ax.set_aspect('equal')
    ax.axis('off')
    
    # Add colorbar
    cbar = plt.colorbar(lc, ax=ax, shrink=0.8)
    cbar.set_label(f'← {driver2} faster | {driver1} faster →', color='white', fontsize=12)
    cbar.ax.yaxis.set_tick_params(color='white')
    cbar.outline.set_edgecolor('white')
    plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color='white')
    
    # Title
    ax.set_title(title, color='white', fontsize=18, fontweight='bold')
    
    # Legend
    legend_elements = [
        mpatches.Patch(facecolor=color1, label=f'{driver1}'),
        mpatches.Patch(facecolor=color2, label=f'{driver2}')
    ]
    ax.legend(handles=legend_elements, loc='lower right', 
              facecolor='#2E2E2E', edgecolor='white', labelcolor='white')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=TIKTOK_DPI, facecolor='#1E1E1E', bbox_inches='tight')
    
    return fig


def create_dominance_gap_chart(
    year: int,
    primary_team: str,
    primary_drivers: List[str],
    title: str = "Dominance Gap Chart",
    save_path: Optional[str] = None
) -> plt.Figure:
    """
    Create a bar chart showing gap to P2 across all races
    Shows consistency of dominance
    """
    from data_loader import get_event_schedule
    
    schedule = get_event_schedule(year)
    races = schedule[schedule['EventFormat'] != 'testing']['EventName'].tolist()
    
    race_names = []
    gaps = []
    colors = []
    
    for race in races[:22]:  # Limit to avoid too many bars
        try:
            session = load_session(year, race, 'Q')
            gap_data = calculate_gap_to_leader(session)
            
            if gap_data.empty:
                continue
            
            # Check if primary team is on pole
            pole_driver = gap_data.iloc[0]['Driver']
            if pole_driver in primary_drivers:
                gap_to_p2 = gap_data.iloc[1]['GapToLeader'] if len(gap_data) > 1 else 0
                race_names.append(race[:10])  # Truncate race name
                gaps.append(gap_to_p2)
                colors.append(get_team_color(primary_team))
            else:
                # Show negative gap (how far behind they were)
                team_gap = gap_data[gap_data['Driver'].isin(primary_drivers)]
                if not team_gap.empty:
                    race_names.append(race[:10])
                    gaps.append(-team_gap.iloc[0]['GapToLeader'])
                    colors.append('#888888')
                    
        except Exception as e:
            continue
    
    if not gaps:
        return None
    
    # Create figure
    fig, ax = plt.subplots(figsize=TIKTOK_FIGSIZE_WIDE, dpi=TIKTOK_DPI)
    fig.patch.set_facecolor('#1E1E1E')
    ax.set_facecolor('#1E1E1E')
    
    x = np.arange(len(race_names))
    bars = ax.bar(x, gaps, color=colors, edgecolor='white', linewidth=0.5)
    
    # Add horizontal line at 0
    ax.axhline(y=0, color='white', linewidth=1)
    
    ax.set_xticks(x)
    ax.set_xticklabels(race_names, rotation=45, ha='right', color='white', fontsize=8)
    ax.set_ylabel('Gap to P2 (seconds)', color='white', fontsize=12)
    ax.set_title(title, color='white', fontsize=16, fontweight='bold')
    ax.tick_params(colors='white')
    ax.spines['bottom'].set_color('white')
    ax.spines['left'].set_color('white')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # Add average line
    avg_gap = np.mean([g for g in gaps if g > 0])
    ax.axhline(y=avg_gap, color=get_team_color(primary_team), 
               linestyle='--', linewidth=2, alpha=0.7)
    ax.text(len(race_names)-1, avg_gap + 0.02, f'Avg: {avg_gap:.3f}s', 
            color='white', ha='right', fontsize=10)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=TIKTOK_DPI, facecolor='#1E1E1E', bbox_inches='tight')
    
    return fig


def create_sector_comparison(
    session: fastf1.core.Session,
    drivers: List[str],
    title: str = "Sector Time Comparison",
    save_path: Optional[str] = None
) -> plt.Figure:
    """
    Create a stacked bar chart comparing sector times
    """
    sector_data = []
    
    for driver in drivers:
        lap = get_driver_fastest_lap(session, driver)
        if lap is None:
            continue
        
        if pd.notna(lap['Sector1Time']) and pd.notna(lap['Sector2Time']) and pd.notna(lap['Sector3Time']):
            sector_data.append({
                'Driver': driver,
                'Team': lap['Team'],
                'S1': lap['Sector1Time'].total_seconds(),
                'S2': lap['Sector2Time'].total_seconds(),
                'S3': lap['Sector3Time'].total_seconds(),
                'Total': lap['LapTime'].total_seconds() if pd.notna(lap['LapTime']) else 0
            })
    
    if not sector_data:
        return None
    
    df = pd.DataFrame(sector_data)
    df = df.sort_values('Total')
    
    # Create figure
    fig, ax = plt.subplots(figsize=TIKTOK_FIGSIZE, dpi=TIKTOK_DPI)
    fig.patch.set_facecolor('#1E1E1E')
    ax.set_facecolor('#1E1E1E')
    
    y = np.arange(len(df))
    height = 0.6
    
    # Get colors for each team
    colors = [get_team_color(team, session) for team in df['Team']]
    
    # Plot stacked horizontal bars
    s1_bars = ax.barh(y, df['S1'], height, label='Sector 1', 
                       color=[c + '99' for c in colors], edgecolor='white')
    s2_bars = ax.barh(y, df['S2'], height, left=df['S1'], label='Sector 2',
                       color=[c + 'CC' for c in colors], edgecolor='white')
    s3_bars = ax.barh(y, df['S3'], height, left=df['S1'] + df['S2'], label='Sector 3',
                       color=colors, edgecolor='white')
    
    ax.set_yticks(y)
    ax.set_yticklabels(df['Driver'], color='white', fontsize=12)
    ax.set_xlabel('Time (seconds)', color='white', fontsize=12)
    ax.set_title(title, color='white', fontsize=16, fontweight='bold')
    ax.tick_params(colors='white')
    ax.spines['bottom'].set_color('white')
    ax.spines['left'].set_color('white')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # Add lap time labels
    for i, (_, row) in enumerate(df.iterrows()):
        ax.text(row['Total'] + 0.1, i, f"{row['Total']:.3f}s", 
                va='center', color='white', fontsize=10)
    
    ax.legend(loc='lower right', facecolor='#2E2E2E', edgecolor='white', labelcolor='white')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=TIKTOK_DPI, facecolor='#1E1E1E', bbox_inches='tight')
    
    return fig


def create_lap_time_distribution(
    session: fastf1.core.Session,
    drivers: List[str],
    title: str = "Lap Time Distribution",
    save_path: Optional[str] = None
) -> plt.Figure:
    """
    Create violin/box plots of lap times showing consistency
    """
    # Create figure
    fig, ax = plt.subplots(figsize=TIKTOK_FIGSIZE_WIDE, dpi=TIKTOK_DPI)
    fig.patch.set_facecolor('#1E1E1E')
    ax.set_facecolor('#1E1E1E')
    
    lap_data = []
    colors = []
    positions = []
    
    for i, driver in enumerate(drivers):
        driver_laps = session.laps.pick_drivers(driver)
        driver_laps = driver_laps.pick_quicklaps(1.1)  # Within 110% of fastest
        driver_laps = driver_laps.pick_wo_box()  # Exclude pit laps
        
        if driver_laps.empty:
            continue
        
        lap_times = driver_laps['LapTime'].dropna()
        lap_times_seconds = [lt.total_seconds() for lt in lap_times]
        
        if lap_times_seconds:
            team = driver_laps.iloc[0]['Team']
            color = get_team_color(team, session)
            
            bp = ax.boxplot([lap_times_seconds], positions=[i], widths=0.6,
                           patch_artist=True, showfliers=False)
            
            bp['boxes'][0].set_facecolor(color)
            bp['boxes'][0].set_alpha(0.7)
            bp['boxes'][0].set_edgecolor('white')
            bp['medians'][0].set_color('white')
            bp['whiskers'][0].set_color('white')
            bp['whiskers'][1].set_color('white')
            bp['caps'][0].set_color('white')
            bp['caps'][1].set_color('white')
            
            positions.append(i)
            lap_data.append({'driver': driver, 'times': lap_times_seconds})
    
    ax.set_xticks(range(len(drivers)))
    ax.set_xticklabels(drivers, color='white', fontsize=12)
    ax.set_ylabel('Lap Time (seconds)', color='white', fontsize=12)
    ax.set_title(title, color='white', fontsize=16, fontweight='bold')
    ax.tick_params(colors='white')
    ax.spines['bottom'].set_color('white')
    ax.spines['left'].set_color('white')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, alpha=0.3, color='gray', axis='y')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=TIKTOK_DPI, facecolor='#1E1E1E', bbox_inches='tight')
    
    return fig


def create_telemetry_comparison_panel(
    session: fastf1.core.Session,
    driver1: str,
    driver2: str,
    title: str = "Telemetry Comparison",
    save_path: Optional[str] = None
) -> plt.Figure:
    """
    Create a multi-panel telemetry comparison (speed, throttle, brake, gear)
    """
    lap1 = get_driver_fastest_lap(session, driver1)
    lap2 = get_driver_fastest_lap(session, driver2)
    
    if lap1 is None or lap2 is None:
        return None
    
    comparison = compare_telemetry(lap1, lap2, driver1, driver2)
    if not comparison:
        return None
    
    color1 = get_team_color(lap1['Team'], session)
    color2 = get_team_color(lap2['Team'], session)
    
    # Create figure with subplots
    fig, axes = plt.subplots(4, 1, figsize=TIKTOK_FIGSIZE, dpi=TIKTOK_DPI, 
                             sharex=True, gridspec_kw={'hspace': 0.05})
    fig.patch.set_facecolor('#1E1E1E')
    
    distance = comparison['distance']
    
    panels = [
        ('Speed (km/h)', 'speed', [0, 350]),
        ('Throttle (%)', 'throttle', [0, 100]),
        ('Brake', 'brake', [0, 1]),
        ('Gear', 'gear', [0, 8])
    ]
    
    for ax, (ylabel, key, ylim) in zip(axes, panels):
        ax.set_facecolor('#1E1E1E')
        ax.plot(distance, comparison[key][driver1], color=color1, 
                label=driver1, linewidth=1.5)
        ax.plot(distance, comparison[key][driver2], color=color2, 
                label=driver2, linewidth=1.5)
        ax.set_ylabel(ylabel, color='white', fontsize=10)
        ax.set_ylim(ylim)
        ax.tick_params(colors='white')
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.3, color='gray')
    
    # Add legend to top panel
    axes[0].legend(loc='upper right', facecolor='#2E2E2E', 
                   edgecolor='white', labelcolor='white')
    axes[0].set_title(title, color='white', fontsize=14, fontweight='bold')
    
    # X-axis label on bottom panel
    axes[-1].set_xlabel('Distance (m)', color='white', fontsize=12)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=TIKTOK_DPI, facecolor='#1E1E1E', bbox_inches='tight')
    
    return fig


def create_era_comparison_chart(
    data: pd.DataFrame,
    title: str = "Dominance Across Eras",
    save_path: Optional[str] = None
) -> plt.Figure:
    """
    Create a comparison chart across different F1 eras
    """
    if data.empty:
        return None
    
    fig, axes = plt.subplots(2, 2, figsize=TIKTOK_FIGSIZE_WIDE, dpi=TIKTOK_DPI)
    fig.patch.set_facecolor('#1E1E1E')
    
    metrics = [
        ('Poles', 'Pole Positions'),
        ('Wins', 'Race Wins'),
        ('AvgGapToP2', 'Avg Gap to P2 (s)'),
        ('OneTwos', '1-2 Finishes')
    ]
    
    for ax, (col, label) in zip(axes.flat, metrics):
        ax.set_facecolor('#1E1E1E')
        
        colors = [TEAM_COLORS.get(team, '#FFFFFF') for team in data['Team']]
        bars = ax.bar(data['Car'], data[col], color=colors, edgecolor='white')
        
        ax.set_title(label, color='white', fontsize=12, fontweight='bold')
        ax.tick_params(colors='white')
        ax.set_xticklabels(data['Car'], rotation=45, ha='right')
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.2f}' if isinstance(height, float) else str(height),
                       xy=(bar.get_x() + bar.get_width() / 2, height),
                       xytext=(0, 3), textcoords='offset points',
                       ha='center', va='bottom', color='white', fontsize=10)
    
    fig.suptitle(title, color='white', fontsize=16, fontweight='bold')
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=TIKTOK_DPI, facecolor='#1E1E1E', bbox_inches='tight')
    
    return fig


def create_season_progression_chart(
    progression_data: pd.DataFrame,
    team: str,
    title: str = "Season Progression",
    save_path: Optional[str] = None
) -> plt.Figure:
    """
    Show how car performance evolved across the season
    """
    if progression_data.empty:
        return None
    
    fig, ax = plt.subplots(figsize=TIKTOK_FIGSIZE_WIDE, dpi=TIKTOK_DPI)
    fig.patch.set_facecolor('#1E1E1E')
    ax.set_facecolor('#1E1E1E')
    
    color = TEAM_COLORS.get(team, '#FFFFFF')
    
    ax.plot(progression_data['Round'], progression_data['GapToP1'], 
            color=color, linewidth=2, marker='o', markersize=6)
    ax.axhline(y=0, color='green', linestyle='--', alpha=0.7, label='P1')
    
    ax.set_xlabel('Race Round', color='white', fontsize=12)
    ax.set_ylabel('Gap to P1 (seconds)', color='white', fontsize=12)
    ax.set_title(title, color='white', fontsize=16, fontweight='bold')
    ax.tick_params(colors='white')
    ax.spines['bottom'].set_color('white')
    ax.spines['left'].set_color('white')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, alpha=0.3, color='gray')
    ax.invert_yaxis()  # Lower gap is better
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=TIKTOK_DPI, facecolor='#1E1E1E', bbox_inches='tight')
    
    return fig


if __name__ == "__main__":
    # Test visualizations
    print("Testing visualization module...")
    
    # Create output directory
    from pathlib import Path
    output_dir = Path(__file__).parent / "charts"
    output_dir.mkdir(exist_ok=True)
    
    # Load a test session
    print("\nLoading 2023 Bahrain Qualifying...")
    session = load_session(2023, "Bahrain", "Q")
    
    # Test speed trace comparison
    print("Creating speed trace comparison...")
    fig = create_speed_trace_comparison(
        session, 
        ["VER", "LEC", "HAM"],
        title="2023 Bahrain GP - Qualifying Speed Comparison",
        save_path=str(output_dir / "speed_trace_test.png")
    )
    plt.close(fig)
    
    # Test track speed map
    print("Creating track speed map...")
    fig = create_track_speed_map(
        session,
        "VER",
        title="Verstappen - Bahrain Track Speed",
        save_path=str(output_dir / "track_speed_map_test.png")
    )
    if fig:
        plt.close(fig)
    
    # Test track comparison
    print("Creating track comparison map...")
    fig = create_track_comparison_map(
        session,
        "VER",
        "LEC",
        title="Verstappen vs Leclerc - Bahrain",
        save_path=str(output_dir / "track_comparison_test.png")
    )
    if fig:
        plt.close(fig)
    
    # Test sector comparison
    print("Creating sector comparison...")
    fig = create_sector_comparison(
        session,
        ["VER", "LEC", "HAM", "PER", "SAI"],
        title="Sector Time Comparison",
        save_path=str(output_dir / "sector_comparison_test.png")
    )
    if fig:
        plt.close(fig)
    
    # Test telemetry panel
    print("Creating telemetry comparison panel...")
    fig = create_telemetry_comparison_panel(
        session,
        "VER",
        "LEC",
        title="Telemetry: Verstappen vs Leclerc",
        save_path=str(output_dir / "telemetry_panel_test.png")
    )
    if fig:
        plt.close(fig)
    
    print(f"\nTest charts saved to: {output_dir}")
