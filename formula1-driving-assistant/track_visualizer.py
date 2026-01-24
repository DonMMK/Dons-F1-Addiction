"""
Formula 1 Driving Assistant - Track Visualizer Module

Creates 2D track visualizations with driving zone overlays:
- Track layout from telemetry X/Y coordinates
- Color-coded braking zones (red)
- Acceleration zones (green)
- Full throttle sections (blue)
- Corner markers with gear/speed annotations
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize
import numpy as np
from typing import Optional, Dict, List, Tuple, Any

from data_loader import TelemetryData, DrivingZones


# Color scheme for different driving states
COLORS = {
    'braking': '#FF4444',       # Red
    'acceleration': '#44FF44',   # Green
    'full_throttle': '#4488FF',  # Blue
    'coasting': '#FFAA00',       # Orange
    'corner_marker': '#FF00FF',  # Magenta
    'track': '#333333',          # Dark gray
    'track_edge': '#666666',     # Medium gray
    'background': '#1a1a2e',     # Dark blue-ish
    'text': '#FFFFFF',           # White
}


def create_track_plot(
    telemetry: TelemetryData,
    zones: DrivingZones,
    title: str = "Track Analysis",
    show_corners: bool = True,
    show_speed_gradient: bool = False,
    show_gear_markers: bool = True,
    rotation: float = 0.0,
    figsize: Tuple[int, int] = (14, 10)
) -> plt.Figure:
    """
    Create a comprehensive track visualization.
    
    Args:
        telemetry: TelemetryData with X, Y, speed, etc.
        zones: DrivingZones with analyzed driving zones
        title: Plot title
        show_corners: Whether to show corner numbers/info
        show_speed_gradient: Color track by speed instead of zones
        show_gear_markers: Show gear at corner apexes
        rotation: Circuit rotation in degrees
        figsize: Figure size
    
    Returns:
        matplotlib Figure object
    """
    fig, ax = plt.subplots(figsize=figsize, facecolor=COLORS['background'])
    ax.set_facecolor(COLORS['background'])
    
    # Apply rotation if specified
    x, y = telemetry.x.copy(), telemetry.y.copy()
    if rotation != 0:
        x, y = rotate_coordinates(x, y, rotation)
    
    # Draw base track
    ax.plot(x, y, color=COLORS['track_edge'], linewidth=12, alpha=0.5, zorder=1)
    ax.plot(x, y, color=COLORS['track'], linewidth=8, alpha=0.8, zorder=2)
    
    if show_speed_gradient:
        # Color track by speed
        _draw_speed_gradient(ax, x, y, telemetry.speed)
    else:
        # Draw driving zones
        _draw_zones(ax, x, y, zones, telemetry)
    
    # Draw corner markers
    if show_corners:
        _draw_corners(ax, zones.corner_zones, show_gear_markers, rotation)
    
    # Mark start/finish
    _draw_start_finish(ax, x, y)
    
    # Create legend
    _create_legend(ax, show_speed_gradient)
    
    # Set title and clean up axes
    ax.set_title(title, color=COLORS['text'], fontsize=16, fontweight='bold', pad=20)
    ax.set_aspect('equal')
    ax.axis('off')
    
    plt.tight_layout()
    return fig


def _draw_zones(ax, x: np.ndarray, y: np.ndarray, zones: DrivingZones, telemetry: TelemetryData):
    """Draw color-coded driving zones on the track."""
    
    # Draw braking zones (highest priority - on top)
    for start, end in zones.braking_zones:
        ax.plot(x[start:end+1], y[start:end+1], 
                color=COLORS['braking'], linewidth=6, alpha=0.9, zorder=5)
    
    # Draw acceleration zones
    for start, end in zones.acceleration_zones:
        ax.plot(x[start:end+1], y[start:end+1], 
                color=COLORS['acceleration'], linewidth=6, alpha=0.8, zorder=4)
    
    # Draw full throttle zones
    for start, end in zones.full_throttle_zones:
        ax.plot(x[start:end+1], y[start:end+1], 
                color=COLORS['full_throttle'], linewidth=5, alpha=0.7, zorder=3)


def _draw_speed_gradient(ax, x: np.ndarray, y: np.ndarray, speed: np.ndarray):
    """Draw track colored by speed gradient."""
    points = np.array([x, y]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    
    # Create speed colormap (blue = slow, red = fast)
    cmap = LinearSegmentedColormap.from_list('speed', ['#0000FF', '#00FF00', '#FFFF00', '#FF0000'])
    norm = Normalize(vmin=speed.min(), vmax=speed.max())
    
    lc = LineCollection(segments, cmap=cmap, norm=norm, linewidth=6, alpha=0.9)
    lc.set_array(speed[:-1])
    ax.add_collection(lc)
    
    # Add colorbar
    cbar = plt.colorbar(lc, ax=ax, shrink=0.5, aspect=20, pad=0.02)
    cbar.set_label('Speed (km/h)', color=COLORS['text'], fontsize=10)
    cbar.ax.yaxis.set_tick_params(color=COLORS['text'])
    plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color=COLORS['text'])


def _draw_corners(ax, corners: List[Dict[str, Any]], show_gear: bool, rotation: float):
    """Draw corner markers with information."""
    for corner in corners:
        cx, cy = corner['x'], corner['y']
        
        # Apply rotation if needed
        if rotation != 0:
            cx, cy = rotate_coordinates(np.array([cx]), np.array([cy]), rotation)
            cx, cy = cx[0], cy[0]
        
        # Draw corner marker
        ax.scatter(cx, cy, s=150, c=COLORS['corner_marker'], 
                   marker='o', zorder=10, edgecolors='white', linewidths=2)
        
        # Add corner number
        label = f"T{corner['number']}"
        if show_gear:
            label += f"\nG{corner['apex_gear']}"
            label += f"\n{int(corner['apex_speed'])}km/h"
        
        ax.annotate(label, (cx, cy), 
                    xytext=(10, 10), textcoords='offset points',
                    color=COLORS['text'], fontsize=8, fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.7),
                    zorder=11)


def _draw_start_finish(ax, x: np.ndarray, y: np.ndarray):
    """Draw start/finish line marker."""
    # Draw at the first point (start/finish)
    ax.scatter(x[0], y[0], s=300, c='white', marker='s', zorder=12, edgecolors='black', linewidths=2)
    ax.annotate("S/F", (x[0], y[0]), 
                xytext=(15, 15), textcoords='offset points',
                color=COLORS['text'], fontsize=10, fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='green', alpha=0.8),
                zorder=13)


def _create_legend(ax, speed_gradient: bool):
    """Create a legend for the plot."""
    if speed_gradient:
        return  # Speed gradient has its own colorbar
    
    legend_items = [
        mpatches.Patch(color=COLORS['braking'], label='Braking Zone'),
        mpatches.Patch(color=COLORS['acceleration'], label='Acceleration'),
        mpatches.Patch(color=COLORS['full_throttle'], label='Full Throttle'),
        mpatches.Patch(color=COLORS['corner_marker'], label='Corner Apex'),
    ]
    
    legend = ax.legend(handles=legend_items, loc='upper right',
                       facecolor='black', edgecolor='white', 
                       fontsize=9, framealpha=0.8)
    plt.setp(legend.get_texts(), color=COLORS['text'])


def rotate_coordinates(x: np.ndarray, y: np.ndarray, angle_degrees: float) -> Tuple[np.ndarray, np.ndarray]:
    """Rotate coordinates by given angle."""
    angle_rad = np.radians(angle_degrees)
    cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
    
    # Center the rotation
    cx, cy = x.mean(), y.mean()
    x_centered = x - cx
    y_centered = y - cy
    
    x_rot = x_centered * cos_a - y_centered * sin_a + cx
    y_rot = x_centered * sin_a + y_centered * cos_a + cy
    
    return x_rot, y_rot


def create_telemetry_dashboard(
    telemetry: TelemetryData,
    zones: DrivingZones,
    title: str = "Telemetry Dashboard",
    figsize: Tuple[int, int] = (16, 12)
) -> plt.Figure:
    """
    Create a comprehensive telemetry dashboard with track and data plots.
    
    Shows:
    - Track map with zones (top left)
    - Speed trace (top right)
    - Throttle/Brake overlay (bottom left)
    - Gear usage (bottom right)
    """
    fig = plt.figure(figsize=figsize, facecolor=COLORS['background'])
    
    # Create grid
    gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)
    
    # 1. Track map (top left)
    ax_track = fig.add_subplot(gs[0, 0])
    ax_track.set_facecolor(COLORS['background'])
    _draw_mini_track(ax_track, telemetry, zones)
    ax_track.set_title("Track Layout", color=COLORS['text'], fontsize=12)
    ax_track.set_aspect('equal')
    ax_track.axis('off')
    
    # 2. Speed trace (top right)
    ax_speed = fig.add_subplot(gs[0, 1])
    ax_speed.set_facecolor(COLORS['background'])
    _draw_speed_trace(ax_speed, telemetry, zones)
    ax_speed.set_title("Speed Trace", color=COLORS['text'], fontsize=12)
    
    # 3. Throttle/Brake (bottom left)
    ax_inputs = fig.add_subplot(gs[1, 0])
    ax_inputs.set_facecolor(COLORS['background'])
    _draw_input_trace(ax_inputs, telemetry)
    ax_inputs.set_title("Throttle & Brake", color=COLORS['text'], fontsize=12)
    
    # 4. Gear usage (bottom right)
    ax_gear = fig.add_subplot(gs[1, 1])
    ax_gear.set_facecolor(COLORS['background'])
    _draw_gear_trace(ax_gear, telemetry, zones)
    ax_gear.set_title("Gear Selection", color=COLORS['text'], fontsize=12)
    
    fig.suptitle(title, color=COLORS['text'], fontsize=16, fontweight='bold', y=0.98)
    
    plt.tight_layout()
    return fig


def _draw_mini_track(ax, telemetry: TelemetryData, zones: DrivingZones):
    """Draw a simplified track map."""
    x, y = telemetry.x, telemetry.y
    ax.plot(x, y, color=COLORS['track'], linewidth=4, alpha=0.5)
    
    # Highlight braking zones
    for start, end in zones.braking_zones:
        ax.plot(x[start:end+1], y[start:end+1], color=COLORS['braking'], linewidth=3)
    
    # Mark corners
    for corner in zones.corner_zones:
        ax.scatter(corner['x'], corner['y'], s=50, c=COLORS['corner_marker'], zorder=5)


def _draw_speed_trace(ax, telemetry: TelemetryData, zones: DrivingZones):
    """Draw speed vs distance trace."""
    distance_km = telemetry.distance / 1000
    
    # Plot speed
    ax.fill_between(distance_km, telemetry.speed, alpha=0.3, color=COLORS['full_throttle'])
    ax.plot(distance_km, telemetry.speed, color=COLORS['full_throttle'], linewidth=1.5)
    
    # Mark braking zones
    for start, end in zones.braking_zones:
        ax.axvspan(distance_km[start], distance_km[end], alpha=0.3, color=COLORS['braking'])
    
    ax.set_xlabel("Distance (km)", color=COLORS['text'])
    ax.set_ylabel("Speed (km/h)", color=COLORS['text'])
    ax.tick_params(colors=COLORS['text'])
    ax.grid(True, alpha=0.2)
    ax.set_xlim(0, distance_km.max())
    ax.set_ylim(0, telemetry.speed.max() * 1.1)
    
    for spine in ax.spines.values():
        spine.set_color(COLORS['text'])


def _draw_input_trace(ax, telemetry: TelemetryData):
    """Draw throttle and brake traces."""
    distance_km = telemetry.distance / 1000
    
    # Throttle (green, positive)
    ax.fill_between(distance_km, telemetry.throttle, alpha=0.5, color=COLORS['acceleration'], label='Throttle')
    
    # Brake (red, shown as negative for clarity)
    brake_normalized = telemetry.brake * 100 if telemetry.brake.max() <= 1 else telemetry.brake
    ax.fill_between(distance_km, -brake_normalized, alpha=0.5, color=COLORS['braking'], label='Brake')
    
    ax.axhline(y=0, color=COLORS['text'], linewidth=0.5)
    ax.set_xlabel("Distance (km)", color=COLORS['text'])
    ax.set_ylabel("Input %", color=COLORS['text'])
    ax.tick_params(colors=COLORS['text'])
    ax.legend(facecolor='black', edgecolor='white', labelcolor=COLORS['text'])
    ax.grid(True, alpha=0.2)
    ax.set_xlim(0, distance_km.max())
    ax.set_ylim(-110, 110)
    
    for spine in ax.spines.values():
        spine.set_color(COLORS['text'])


def _draw_gear_trace(ax, telemetry: TelemetryData, zones: DrivingZones):
    """Draw gear usage over the lap."""
    distance_km = telemetry.distance / 1000
    
    # Plot gear as step function
    ax.step(distance_km, telemetry.gear, where='mid', color=COLORS['coasting'], linewidth=2)
    ax.fill_between(distance_km, telemetry.gear, step='mid', alpha=0.3, color=COLORS['coasting'])
    
    # Mark corner apexes
    for corner in zones.corner_zones:
        corner_dist = corner['distance'] / 1000
        ax.axvline(x=corner_dist, color=COLORS['corner_marker'], alpha=0.5, linestyle='--', linewidth=0.5)
        ax.annotate(f"T{corner['number']}", (corner_dist, 8.2), 
                    color=COLORS['text'], fontsize=7, ha='center')
    
    ax.set_xlabel("Distance (km)", color=COLORS['text'])
    ax.set_ylabel("Gear", color=COLORS['text'])
    ax.tick_params(colors=COLORS['text'])
    ax.set_yticks(range(1, 9))
    ax.grid(True, alpha=0.2)
    ax.set_xlim(0, distance_km.max())
    ax.set_ylim(0.5, 8.5)
    
    for spine in ax.spines.values():
        spine.set_color(COLORS['text'])


def show_plot(fig: plt.Figure):
    """Display the plot."""
    plt.show()


def save_plot(fig: plt.Figure, filepath: str, dpi: int = 150):
    """Save the plot to a file."""
    fig.savefig(filepath, dpi=dpi, facecolor=fig.get_facecolor(), 
                edgecolor='none', bbox_inches='tight')
    print(f"Plot saved to: {filepath}")


if __name__ == "__main__":
    # Test visualization with sample data
    from data_loader import load_session, get_lap_telemetry, analyze_driving_zones, get_fastest_lap_info
    
    print("Loading session data...")
    session = load_session(2024, 1, 'Q')  # Bahrain 2024 Qualifying
    
    lap_info = get_fastest_lap_info(session)
    if lap_info:
        print(f"Fastest lap: {lap_info.driver} - {lap_info.lap_time}")
    
    telemetry = get_lap_telemetry(session)
    if telemetry:
        print(f"Analyzing {len(telemetry.speed)} telemetry points...")
        zones = analyze_driving_zones(telemetry)
        
        print(f"Found {len(zones.braking_zones)} braking zones")
        print(f"Found {len(zones.corner_zones)} corners")
        
        # Create and show track plot
        title = f"Bahrain GP 2024 - {lap_info.driver if lap_info else 'Fastest'} Lap"
        fig = create_track_plot(telemetry, zones, title=title)
        show_plot(fig)
        
        # Create dashboard
        fig_dash = create_telemetry_dashboard(telemetry, zones, title=title)
        show_plot(fig_dash)
