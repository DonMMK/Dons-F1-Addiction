"""
Export Module for TikTok-Ready Media
Utilities for creating social media optimized content
"""

import os
from pathlib import Path
from typing import Optional, List, Tuple
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import pandas as pd

from data_loader import load_session, get_driver_fastest_lap, get_lap_telemetry


# TikTok specifications
TIKTOK_WIDTH = 1080
TIKTOK_HEIGHT = 1920
TIKTOK_FPS = 30
TIKTOK_DURATION_MAX = 60  # seconds

# Output directories
BASE_OUTPUT_DIR = Path(__file__).parent / "output"
CHARTS_DIR = BASE_OUTPUT_DIR / "charts"
ANIMATIONS_DIR = BASE_OUTPUT_DIR / "animations"
TIKTOK_READY_DIR = BASE_OUTPUT_DIR / "tiktok_ready"


def setup_output_dirs():
    """Create output directories if they don't exist"""
    for dir_path in [CHARTS_DIR, ANIMATIONS_DIR, TIKTOK_READY_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)


def save_chart_for_tiktok(
    fig: plt.Figure,
    filename: str,
    output_dir: Optional[Path] = None
) -> str:
    """
    Save a matplotlib figure optimized for TikTok
    
    Parameters:
    -----------
    fig : matplotlib.Figure
        The figure to save
    filename : str
        Output filename (without extension)
    output_dir : Path, optional
        Output directory (defaults to TIKTOK_READY_DIR)
    
    Returns:
    --------
    str : Path to saved file
    """
    setup_output_dirs()
    output_dir = output_dir or TIKTOK_READY_DIR
    
    # Save high-resolution PNG
    output_path = output_dir / f"{filename}.png"
    fig.savefig(
        output_path,
        dpi=200,
        facecolor='#1E1E1E',
        bbox_inches='tight',
        pad_inches=0.1
    )
    
    # Also save a TikTok-cropped version
    tiktok_path = output_dir / f"{filename}_tiktok.png"
    crop_for_tiktok(output_path, tiktok_path)
    
    return str(tiktok_path)


def crop_for_tiktok(
    input_path: Path,
    output_path: Path,
    target_width: int = TIKTOK_WIDTH,
    target_height: int = TIKTOK_HEIGHT
) -> None:
    """
    Crop/resize an image to TikTok dimensions (9:16)
    """
    with Image.open(input_path) as img:
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # Calculate target aspect ratio
        target_ratio = target_width / target_height
        current_ratio = img.width / img.height
        
        if current_ratio > target_ratio:
            # Image is wider than target, crop width
            new_width = int(img.height * target_ratio)
            left = (img.width - new_width) // 2
            img = img.crop((left, 0, left + new_width, img.height))
        else:
            # Image is taller than target, crop height
            new_height = int(img.width / target_ratio)
            top = (img.height - new_height) // 2
            img = img.crop((0, top, img.width, top + new_height))
        
        # Resize to exact dimensions
        img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        img.save(output_path, quality=95)


def add_text_overlay(
    image_path: Path,
    title: str,
    subtitle: Optional[str] = None,
    output_path: Optional[Path] = None,
    font_size_title: int = 60,
    font_size_subtitle: int = 36
) -> str:
    """
    Add text overlay to an image for TikTok content
    """
    with Image.open(image_path) as img:
        draw = ImageDraw.Draw(img)
        
        # Use a simple font (system default)
        try:
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size_title)
            font_subtitle = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size_subtitle)
        except:
            font_title = ImageFont.load_default()
            font_subtitle = ImageFont.load_default()
        
        # Calculate text position (centered, near top)
        bbox = draw.textbbox((0, 0), title, font=font_title)
        title_width = bbox[2] - bbox[0]
        title_x = (img.width - title_width) // 2
        title_y = 50
        
        # Add semi-transparent background for text
        padding = 20
        draw.rectangle(
            [(title_x - padding, title_y - padding),
             (title_x + title_width + padding, title_y + font_size_title + padding)],
            fill=(0, 0, 0, 180)
        )
        
        # Draw title
        draw.text((title_x, title_y), title, fill='white', font=font_title)
        
        # Draw subtitle if provided
        if subtitle:
            bbox = draw.textbbox((0, 0), subtitle, font=font_subtitle)
            subtitle_width = bbox[2] - bbox[0]
            subtitle_x = (img.width - subtitle_width) // 2
            subtitle_y = title_y + font_size_title + 20
            draw.text((subtitle_x, subtitle_y), subtitle, fill='#CCCCCC', font=font_subtitle)
        
        output_path = output_path or image_path
        img.save(output_path)
        
    return str(output_path)


def create_speed_animation(
    session,
    driver: str,
    output_path: Optional[str] = None,
    fps: int = 30,
    duration: float = 10.0
) -> str:
    """
    Create an animated speed trace for a lap
    
    Parameters:
    -----------
    session : fastf1.core.Session
        The session containing the lap
    driver : str
        Driver abbreviation
    output_path : str, optional
        Output file path
    fps : int
        Frames per second
    duration : float
        Animation duration in seconds
    
    Returns:
    --------
    str : Path to the created animation
    """
    setup_output_dirs()
    
    lap = get_driver_fastest_lap(session, driver)
    if lap is None:
        raise ValueError(f"No lap found for driver {driver}")
    
    telemetry = get_lap_telemetry(lap)
    if telemetry.empty:
        raise ValueError(f"No telemetry data for driver {driver}")
    
    if 'Distance' not in telemetry.columns:
        telemetry = telemetry.add_distance()
    
    # Setup figure
    fig, ax = plt.subplots(figsize=(16, 9), dpi=100)
    fig.patch.set_facecolor('#1E1E1E')
    ax.set_facecolor('#1E1E1E')
    
    ax.set_xlim(0, telemetry['Distance'].max())
    ax.set_ylim(0, telemetry['Speed'].max() * 1.1)
    ax.set_xlabel('Distance (m)', color='white')
    ax.set_ylabel('Speed (km/h)', color='white')
    ax.tick_params(colors='white')
    ax.spines['bottom'].set_color('white')
    ax.spines['left'].set_color('white')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # Team color
    from visualizations import get_team_color
    color = get_team_color(lap['Team'], session)
    
    line, = ax.plot([], [], color=color, linewidth=2)
    point, = ax.plot([], [], 'o', color='white', markersize=10)
    
    # Title
    title = ax.set_title(f"{driver} - {session.event['EventName']}", 
                         color='white', fontsize=16, fontweight='bold')
    
    # Speed text
    speed_text = ax.text(0.95, 0.95, '', transform=ax.transAxes, 
                         fontsize=24, color=color, ha='right', va='top',
                         fontweight='bold')
    
    # Calculate frames
    total_frames = int(fps * duration)
    frame_indices = np.linspace(0, len(telemetry) - 1, total_frames).astype(int)
    
    def init():
        line.set_data([], [])
        point.set_data([], [])
        speed_text.set_text('')
        return line, point, speed_text
    
    def animate(frame):
        idx = frame_indices[frame]
        distance = telemetry['Distance'].iloc[:idx+1]
        speed = telemetry['Speed'].iloc[:idx+1]
        
        line.set_data(distance, speed)
        point.set_data([distance.iloc[-1]], [speed.iloc[-1]])
        speed_text.set_text(f"{speed.iloc[-1]:.0f} km/h")
        
        return line, point, speed_text
    
    anim = animation.FuncAnimation(
        fig, animate, init_func=init,
        frames=total_frames, interval=1000/fps, blit=True
    )
    
    # Save animation
    output_path = output_path or str(ANIMATIONS_DIR / f"{driver}_speed_animation.mp4")
    
    writer = animation.FFMpegWriter(fps=fps, bitrate=5000)
    anim.save(output_path, writer=writer, dpi=100)
    
    plt.close(fig)
    return output_path


def create_track_animation(
    session,
    driver: str,
    output_path: Optional[str] = None,
    fps: int = 30,
    duration: float = 15.0
) -> str:
    """
    Create an animated track visualization showing car position
    """
    setup_output_dirs()
    
    lap = get_driver_fastest_lap(session, driver)
    if lap is None:
        raise ValueError(f"No lap found for driver {driver}")
    
    telemetry = get_lap_telemetry(lap)
    if telemetry.empty:
        raise ValueError(f"No telemetry data for driver {driver}")
    
    # Get position data
    x = telemetry['X'].values
    y = telemetry['Y'].values
    speed = telemetry['Speed'].values
    
    # Rotate track
    from data_loader import get_circuit_info
    circuit_info = get_circuit_info(session)
    if circuit_info is not None:
        rotation = circuit_info.rotation
        x_rot = x * np.cos(np.radians(rotation)) - y * np.sin(np.radians(rotation))
        y_rot = x * np.sin(np.radians(rotation)) + y * np.cos(np.radians(rotation))
        x, y = x_rot, y_rot
    
    # Setup figure
    fig, ax = plt.subplots(figsize=(12, 12), dpi=100)
    fig.patch.set_facecolor('#1E1E1E')
    ax.set_facecolor('#1E1E1E')
    
    # Draw full track outline (faint)
    ax.plot(x, y, color='#333333', linewidth=10)
    
    ax.set_aspect('equal')
    ax.axis('off')
    
    # Team color
    from visualizations import get_team_color
    color = get_team_color(lap['Team'], session)
    
    # Car marker
    car, = ax.plot([], [], 'o', color=color, markersize=20)
    
    # Trail
    trail, = ax.plot([], [], color=color, linewidth=4, alpha=0.7)
    
    # Speed text
    speed_text = ax.text(0.5, 0.95, '', transform=ax.transAxes, 
                         fontsize=36, color=color, ha='center', va='top',
                         fontweight='bold')
    
    # Title
    ax.set_title(f"{driver} - {session.event['EventName']}\n{lap['LapTime']}", 
                 color='white', fontsize=20, fontweight='bold')
    
    # Calculate frames
    total_frames = int(fps * duration)
    frame_indices = np.linspace(0, len(x) - 1, total_frames).astype(int)
    
    # Trail length (show last N points)
    trail_length = 50
    
    def init():
        car.set_data([], [])
        trail.set_data([], [])
        speed_text.set_text('')
        return car, trail, speed_text
    
    def animate(frame):
        idx = frame_indices[frame]
        
        # Car position
        car.set_data([x[idx]], [y[idx]])
        
        # Trail
        start_idx = max(0, idx - trail_length)
        trail.set_data(x[start_idx:idx+1], y[start_idx:idx+1])
        
        # Speed
        speed_text.set_text(f"{speed[idx]:.0f} km/h")
        
        return car, trail, speed_text
    
    anim = animation.FuncAnimation(
        fig, animate, init_func=init,
        frames=total_frames, interval=1000/fps, blit=True
    )
    
    # Save animation
    output_path = output_path or str(ANIMATIONS_DIR / f"{driver}_track_animation.mp4")
    
    writer = animation.FFMpegWriter(fps=fps, bitrate=5000)
    anim.save(output_path, writer=writer, dpi=100)
    
    plt.close(fig)
    return output_path


def create_comparison_animation(
    session,
    driver1: str,
    driver2: str,
    output_path: Optional[str] = None,
    fps: int = 30,
    duration: float = 15.0
) -> str:
    """
    Create animated comparison of two drivers on track
    """
    setup_output_dirs()
    
    lap1 = get_driver_fastest_lap(session, driver1)
    lap2 = get_driver_fastest_lap(session, driver2)
    
    if lap1 is None or lap2 is None:
        raise ValueError(f"Could not find laps for both drivers")
    
    tel1 = get_lap_telemetry(lap1)
    tel2 = get_lap_telemetry(lap2)
    
    if tel1.empty or tel2.empty:
        raise ValueError("Missing telemetry data")
    
    # Add distance if needed
    if 'Distance' not in tel1.columns:
        tel1 = tel1.add_distance()
    if 'Distance' not in tel2.columns:
        tel2 = tel2.add_distance()
    
    # Get position data
    x1, y1 = tel1['X'].values, tel1['Y'].values
    x2, y2 = tel2['X'].values, tel2['Y'].values
    
    # Rotate track
    from data_loader import get_circuit_info
    circuit_info = get_circuit_info(session)
    if circuit_info is not None:
        rotation = circuit_info.rotation
        for arrays in [(x1, y1), (x2, y2)]:
            x, y = arrays
            x_rot = x * np.cos(np.radians(rotation)) - y * np.sin(np.radians(rotation))
            y_rot = x * np.sin(np.radians(rotation)) + y * np.cos(np.radians(rotation))
            if arrays == (x1, y1):
                x1, y1 = x_rot, y_rot
            else:
                x2, y2 = x_rot, y_rot
    
    # Setup figure
    fig, ax = plt.subplots(figsize=(12, 12), dpi=100)
    fig.patch.set_facecolor('#1E1E1E')
    ax.set_facecolor('#1E1E1E')
    
    # Draw track outline
    ax.plot(x1, y1, color='#333333', linewidth=10)
    
    ax.set_aspect('equal')
    ax.axis('off')
    
    # Get team colors
    from visualizations import get_team_color
    color1 = get_team_color(lap1['Team'], session)
    color2 = get_team_color(lap2['Team'], session)
    
    # Car markers
    car1, = ax.plot([], [], 'o', color=color1, markersize=15, label=driver1)
    car2, = ax.plot([], [], 's', color=color2, markersize=15, label=driver2)
    
    # Legend
    ax.legend(loc='upper left', facecolor='#2E2E2E', edgecolor='white', 
              labelcolor='white', fontsize=12)
    
    # Gap text
    gap_text = ax.text(0.5, 0.05, '', transform=ax.transAxes, 
                       fontsize=24, color='white', ha='center', va='bottom',
                       fontweight='bold')
    
    # Title
    ax.set_title(f"{driver1} vs {driver2}\n{session.event['EventName']}", 
                 color='white', fontsize=18, fontweight='bold')
    
    # Calculate frames - use distance as reference
    total_frames = int(fps * duration)
    max_dist = min(tel1['Distance'].max(), tel2['Distance'].max())
    distances = np.linspace(0, max_dist, total_frames)
    
    def get_position_at_distance(telemetry, x_arr, y_arr, distance):
        idx = np.searchsorted(telemetry['Distance'], distance)
        idx = min(idx, len(x_arr) - 1)
        return x_arr[idx], y_arr[idx]
    
    def init():
        car1.set_data([], [])
        car2.set_data([], [])
        gap_text.set_text('')
        return car1, car2, gap_text
    
    def animate(frame):
        dist = distances[frame]
        
        # Get positions
        pos1 = get_position_at_distance(tel1, x1, y1, dist)
        pos2 = get_position_at_distance(tel2, x2, y2, dist)
        
        car1.set_data([pos1[0]], [pos1[1]])
        car2.set_data([pos2[0]], [pos2[1]])
        
        # Calculate gap (simplified - based on lap times)
        lap_time1 = lap1['LapTime'].total_seconds()
        lap_time2 = lap2['LapTime'].total_seconds()
        gap = abs(lap_time1 - lap_time2)
        
        if lap_time1 < lap_time2:
            gap_text.set_text(f"{driver1} faster by {gap:.3f}s")
            gap_text.set_color(color1)
        else:
            gap_text.set_text(f"{driver2} faster by {gap:.3f}s")
            gap_text.set_color(color2)
        
        return car1, car2, gap_text
    
    anim = animation.FuncAnimation(
        fig, animate, init_func=init,
        frames=total_frames, interval=1000/fps, blit=True
    )
    
    # Save animation
    output_path = output_path or str(ANIMATIONS_DIR / f"{driver1}_vs_{driver2}_animation.mp4")
    
    writer = animation.FFMpegWriter(fps=fps, bitrate=5000)
    anim.save(output_path, writer=writer, dpi=100)
    
    plt.close(fig)
    return output_path


def batch_export_race(
    year: int,
    race: str,
    drivers: List[str],
    export_charts: bool = True,
    export_animations: bool = False
) -> dict:
    """
    Export all visualizations for a race
    
    Parameters:
    -----------
    year : int
        Season year
    race : str
        Race name
    drivers : List[str]
        List of driver abbreviations to include
    export_charts : bool
        Whether to export static charts
    export_animations : bool
        Whether to export animations (slower)
    
    Returns:
    --------
    dict : Paths to all exported files
    """
    setup_output_dirs()
    
    exports = {
        'charts': [],
        'animations': []
    }
    
    # Load sessions
    q_session = load_session(year, race, 'Q')
    
    race_name = race.replace(' ', '_').lower()
    
    if export_charts:
        from visualizations import (
            create_speed_trace_comparison,
            create_track_speed_map,
            create_track_comparison_map,
            create_sector_comparison,
            create_telemetry_comparison_panel
        )
        
        # Speed trace comparison
        try:
            fig = create_speed_trace_comparison(
                q_session, drivers,
                title=f"{year} {race} GP - Qualifying Speed Comparison",
                save_path=str(CHARTS_DIR / f"{year}_{race_name}_speed_trace.png")
            )
            if fig:
                exports['charts'].append(str(CHARTS_DIR / f"{year}_{race_name}_speed_trace.png"))
                plt.close(fig)
        except Exception as e:
            print(f"Error creating speed trace: {e}")
        
        # Track speed map for each driver
        for driver in drivers:
            try:
                fig = create_track_speed_map(
                    q_session, driver,
                    title=f"{driver} - {race} Track Speed",
                    save_path=str(CHARTS_DIR / f"{year}_{race_name}_{driver}_track_speed.png")
                )
                if fig:
                    exports['charts'].append(str(CHARTS_DIR / f"{year}_{race_name}_{driver}_track_speed.png"))
                    plt.close(fig)
            except Exception as e:
                print(f"Error creating track map for {driver}: {e}")
        
        # Track comparison (first two drivers)
        if len(drivers) >= 2:
            try:
                fig = create_track_comparison_map(
                    q_session, drivers[0], drivers[1],
                    title=f"{drivers[0]} vs {drivers[1]} - {race}",
                    save_path=str(CHARTS_DIR / f"{year}_{race_name}_comparison.png")
                )
                if fig:
                    exports['charts'].append(str(CHARTS_DIR / f"{year}_{race_name}_comparison.png"))
                    plt.close(fig)
            except Exception as e:
                print(f"Error creating comparison: {e}")
        
        # Sector comparison
        try:
            fig = create_sector_comparison(
                q_session, drivers,
                title=f"Sector Times - {race}",
                save_path=str(CHARTS_DIR / f"{year}_{race_name}_sectors.png")
            )
            if fig:
                exports['charts'].append(str(CHARTS_DIR / f"{year}_{race_name}_sectors.png"))
                plt.close(fig)
        except Exception as e:
            print(f"Error creating sector comparison: {e}")
    
    if export_animations and len(drivers) >= 2:
        try:
            path = create_comparison_animation(
                q_session, drivers[0], drivers[1],
                output_path=str(ANIMATIONS_DIR / f"{year}_{race_name}_{drivers[0]}_vs_{drivers[1]}.mp4")
            )
            exports['animations'].append(path)
        except Exception as e:
            print(f"Error creating animation: {e}")
    
    return exports


if __name__ == "__main__":
    # Test export functions
    print("Testing export module...")
    setup_output_dirs()
    
    # Test chart export
    print("\nLoading 2023 Bahrain Qualifying...")
    session = load_session(2023, "Bahrain", "Q")
    
    # Create a test chart
    from visualizations import create_speed_trace_comparison
    fig = create_speed_trace_comparison(
        session,
        ["VER", "LEC", "HAM"],
        title="Test Speed Comparison"
    )
    
    # Save for TikTok
    path = save_chart_for_tiktok(fig, "test_chart")
    print(f"Chart saved to: {path}")
    plt.close(fig)
    
    # Test batch export (without animations for speed)
    print("\nTesting batch export...")
    exports = batch_export_race(
        2023, "Bahrain", 
        ["VER", "LEC", "HAM", "PER"],
        export_charts=True,
        export_animations=False
    )
    print(f"Exported {len(exports['charts'])} charts")
    print(f"Charts: {exports['charts']}")
