"""
Formula 1 Ghost Car - Race Replay Module

Full race ghost car comparison showing two drivers racing through all laps:
- Two animated F1 car icons racing through each lap (like ghost comparison)
- Track colored by who's faster on each lap
- Real-time delta/gap display during the lap
- Lap-by-lap gap evolution chart
- Position tracking and pit stop indicators
- Cumulative time comparison
- Smooth transitions between laps
"""

import matplotlib

# Set interactive backend if not already set
if matplotlib.get_backend() == "agg":
    try:
        matplotlib.use("Qt5Agg")
    except:
        try:
            matplotlib.use("TkAgg")
        except:
            pass

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Polygon, Circle, Rectangle
from matplotlib.collections import LineCollection
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button, Slider
from matplotlib.colors import LinearSegmentedColormap, Normalize
import matplotlib.gridspec as gridspec
import numpy as np
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass, field
from scipy import interpolate as scipy_interpolate
import colorsys

from data_loader import (
    TelemetryData,
    RaceData,
    RaceLapData,
    get_circuit_info,
    get_driver_race_laps,
    get_race_comparison_data,
)

# Import utilities from ghost_comparison
from ghost_comparison import (
    TEAM_COLORS,
    DRIVER_TEAMS_BY_YEAR,
    get_driver_team_for_year,
    get_dynamic_driver_info,
    differentiate_same_team_colors,
    create_car_icon,
    interpolate_telemetry_to_distance,
)

# Color scheme
COLORS = {
    "background": "#1a1a2e",
    "background_light": "#252540",
    "track": "#444444",
    "track_edge": "#666666",
    "text": "#FFFFFF",
    "text_dim": "#888888",
    "text_highlight": "#FFD700",
    "gauge_bg": "#333333",
    "pit_indicator": "#FF00FF",
    "position_gain": "#00FF00",
    "position_loss": "#FF4444",
}


def format_time(seconds: float) -> str:
    """Format seconds as M:SS.mmm"""
    if seconds < 0:
        sign = "-"
        seconds = abs(seconds)
    else:
        sign = ""
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{sign}{minutes}:{secs:06.3f}"


def format_gap(gap_seconds: float) -> str:
    """Format gap as +X.XXXs or -X.XXXs"""
    if abs(gap_seconds) < 0.001:
        return "0.000s"
    sign = "+" if gap_seconds > 0 else ""
    return f"{sign}{gap_seconds:.3f}s"


@dataclass
class LapTelemetryPair:
    """Synchronized telemetry data for a lap comparison."""
    lap_num: int
    # Driver 1 interpolated data
    x1: np.ndarray
    y1: np.ndarray
    time1: np.ndarray
    speed1: np.ndarray
    angles1: np.ndarray
    # Driver 2 interpolated data
    x2: np.ndarray
    y2: np.ndarray
    time2: np.ndarray
    speed2: np.ndarray
    angles2: np.ndarray
    # Common distance grid
    common_distances: np.ndarray
    # Segment colors
    segment_colors: List[str] = field(default_factory=list)
    # Lap info
    lap_time1: float = 0.0
    lap_time2: float = 0.0
    delta: float = 0.0  # lap_time2 - lap_time1
    has_telemetry: bool = True


@dataclass
class RaceComparison:
    """Container for race comparison analysis"""
    driver1: str
    driver2: str
    team1: str
    team2: str
    driver1_color: Tuple[int, int, int]
    driver2_color: Tuple[int, int, int]
    total_laps: int
    lap_gaps: List[float]  # Gap at end of each lap (positive = driver2 ahead)
    cumulative_times1: List[float]
    cumulative_times2: List[float]
    positions1: List[int]
    positions2: List[int]
    pit_laps1: List[int]
    pit_laps2: List[int]
    winner: str
    final_gap: float
    lap_telemetry_pairs: List[LapTelemetryPair] = field(default_factory=list)


def analyze_race_comparison(
    race1: RaceData,
    race2: RaceData,
    session=None,
    year: int = 2024,
    rotation: float = 0.0,
) -> RaceComparison:
    """
    Analyze full race comparison between two drivers.
    
    Args:
        race1: RaceData for driver 1
        race2: RaceData for driver 2
        session: FastF1 session for color lookup
        year: Season year for team color lookup
        rotation: Track rotation angle in degrees
    
    Returns:
        RaceComparison with lap-by-lap analysis and synchronized telemetry
    """
    # Get team colors
    if session:
        team1, color1 = get_dynamic_driver_info(session, race1.driver)
        team2, color2 = get_dynamic_driver_info(session, race2.driver)
    else:
        team1 = race1.team
        team2 = race2.team
        # Default colors
        hex1 = TEAM_COLORS.get(team1, "#FF0000")
        hex2 = TEAM_COLORS.get(team2, "#0000FF")
        color1 = tuple(int(hex1.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        color2 = tuple(int(hex2.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
    
    # Handle same team colors
    if team1 == team2:
        color1, color2 = differentiate_same_team_colors(color1)
    
    # Calculate lap-by-lap gaps
    total_laps = min(race1.total_laps, race2.total_laps)
    
    cumulative_times1 = []
    cumulative_times2 = []
    positions1 = []
    positions2 = []
    lap_gaps = []
    pit_laps1 = []
    pit_laps2 = []
    lap_telemetry_pairs = []
    
    color1_hex = "#{:02x}{:02x}{:02x}".format(*color1)
    color2_hex = "#{:02x}{:02x}{:02x}".format(*color2)
    
    for lap_num in range(total_laps):
        lap1 = race1.laps[lap_num] if lap_num < len(race1.laps) else None
        lap2 = race2.laps[lap_num] if lap_num < len(race2.laps) else None
        
        if lap1:
            cumulative_times1.append(lap1.cumulative_time)
            positions1.append(lap1.position)
            if lap1.is_pit_lap:
                pit_laps1.append(lap_num + 1)
        else:
            cumulative_times1.append(cumulative_times1[-1] if cumulative_times1 else 0)
            positions1.append(positions1[-1] if positions1 else 0)
        
        if lap2:
            cumulative_times2.append(lap2.cumulative_time)
            positions2.append(lap2.position)
            if lap2.is_pit_lap:
                pit_laps2.append(lap_num + 1)
        else:
            cumulative_times2.append(cumulative_times2[-1] if cumulative_times2 else 0)
            positions2.append(positions2[-1] if positions2 else 0)
        
        # Gap: positive means driver2 is behind (driver1 is ahead)
        gap = cumulative_times2[-1] - cumulative_times1[-1]
        lap_gaps.append(gap)
        
        # Build synchronized telemetry for this lap
        tel_pair = _build_lap_telemetry_pair(
            lap_num=lap_num + 1,
            lap1=lap1,
            lap2=lap2,
            color1_hex=color1_hex,
            color2_hex=color2_hex,
            rotation=rotation,
        )
        lap_telemetry_pairs.append(tel_pair)
    
    # Determine winner
    final_gap = lap_gaps[-1] if lap_gaps else 0
    winner = race1.driver if final_gap > 0 else race2.driver
    
    return RaceComparison(
        driver1=race1.driver,
        driver2=race2.driver,
        team1=team1,
        team2=team2,
        driver1_color=color1,
        driver2_color=color2,
        total_laps=total_laps,
        lap_gaps=lap_gaps,
        cumulative_times1=cumulative_times1,
        cumulative_times2=cumulative_times2,
        positions1=positions1,
        positions2=positions2,
        pit_laps1=pit_laps1,
        pit_laps2=pit_laps2,
        winner=winner,
        final_gap=final_gap,
        lap_telemetry_pairs=lap_telemetry_pairs,
    )


def _rotate_coords(x: np.ndarray, y: np.ndarray, rotation: float) -> Tuple[np.ndarray, np.ndarray]:
    """Rotate coordinates by angle in degrees."""
    if rotation == 0:
        return x.copy(), y.copy()
    
    angle_rad = np.radians(rotation)
    cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
    
    cx, cy = x.mean(), y.mean()
    x_centered = x - cx
    y_centered = y - cy
    
    x_rot = x_centered * cos_a - y_centered * sin_a + cx
    y_rot = x_centered * sin_a + y_centered * cos_a + cy
    
    return x_rot, y_rot


def _calculate_angles(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Calculate heading angles along the track."""
    angles = np.zeros(len(x))
    for i in range(len(x) - 1):
        dx = x[i + 1] - x[i]
        dy = y[i + 1] - y[i]
        angles[i] = np.degrees(np.arctan2(dy, dx)) - 90
    angles[-1] = angles[-2] if len(angles) > 1 else 0
    
    # Smooth angles
    window = 5
    if len(angles) >= window:
        angles = np.convolve(angles, np.ones(window) / window, mode="same")
    return angles


def _build_segment_colors(
    time1: np.ndarray,
    time2: np.ndarray,
    color1_hex: str,
    color2_hex: str,
    num_points: int,
) -> List[str]:
    """Build segment colors based on who's faster."""
    colors = []
    for i in range(num_points):
        if i >= len(time1) or i >= len(time2):
            colors.append("#888888")
        elif abs(time1[i] - time2[i]) < 0.01:
            colors.append("#888888")  # Equal
        elif time1[i] < time2[i]:
            colors.append(color1_hex)  # Driver 1 faster
        else:
            colors.append(color2_hex)  # Driver 2 faster
    return colors


def _build_lap_telemetry_pair(
    lap_num: int,
    lap1: Optional[RaceLapData],
    lap2: Optional[RaceLapData],
    color1_hex: str,
    color2_hex: str,
    rotation: float,
) -> LapTelemetryPair:
    """
    Build synchronized telemetry data for a lap comparison.
    
    Interpolates both drivers' telemetry to a common distance grid,
    calculates time deltas at each point, and determines segment colors.
    """
    # Check if we have telemetry for both
    tel1 = lap1.telemetry if lap1 else None
    tel2 = lap2.telemetry if lap2 else None
    
    has_telemetry = tel1 is not None and tel2 is not None
    
    if not has_telemetry:
        # Return empty pair with just lap info
        return LapTelemetryPair(
            lap_num=lap_num,
            x1=np.array([0]),
            y1=np.array([0]),
            time1=np.array([0]),
            speed1=np.array([0]),
            angles1=np.array([0]),
            x2=np.array([0]),
            y2=np.array([0]),
            time2=np.array([0]),
            speed2=np.array([0]),
            angles2=np.array([0]),
            common_distances=np.array([0]),
            segment_colors=["#888888"],
            lap_time1=lap1.lap_time_seconds if lap1 else 0,
            lap_time2=lap2.lap_time_seconds if lap2 else 0,
            delta=(lap2.lap_time_seconds if lap2 else 0) - (lap1.lap_time_seconds if lap1 else 0),
            has_telemetry=False,
        )
    
    # Create common distance grid
    max_dist = min(tel1.distance.max(), tel2.distance.max())
    min_dist = max(tel1.distance.min(), tel2.distance.min())
    num_points = max(min(len(tel1.distance), len(tel2.distance)), 200)
    common_distances = np.linspace(min_dist, max_dist, num_points)
    
    # Interpolate both to common grid
    interp_tel1 = interpolate_telemetry_to_distance(tel1, common_distances)
    interp_tel2 = interpolate_telemetry_to_distance(tel2, common_distances)
    
    # Rotate coordinates
    x1, y1 = _rotate_coords(interp_tel1.x, interp_tel1.y, rotation)
    x2, y2 = _rotate_coords(interp_tel2.x, interp_tel2.y, rotation)
    
    # Calculate angles
    angles1 = _calculate_angles(x1, y1)
    angles2 = _calculate_angles(x2, y2)
    
    # Build segment colors
    segment_colors = _build_segment_colors(
        interp_tel1.time, interp_tel2.time,
        color1_hex, color2_hex, num_points
    )
    
    lap_time1 = lap1.lap_time_seconds if lap1 else 0
    lap_time2 = lap2.lap_time_seconds if lap2 else 0
    
    return LapTelemetryPair(
        lap_num=lap_num,
        x1=x1,
        y1=y1,
        time1=interp_tel1.time,
        speed1=interp_tel1.speed,
        angles1=angles1,
        x2=x2,
        y2=y2,
        time2=interp_tel2.time,
        speed2=interp_tel2.speed,
        angles2=angles2,
        common_distances=common_distances,
        segment_colors=segment_colors,
        lap_time1=lap_time1,
        lap_time2=lap_time2,
        delta=lap_time2 - lap_time1,
        has_telemetry=True,
    )


class RaceReplayAnimation:
    """
    Full race ghost car replay animation with frame-by-frame lap animation.
    
    Shows two drivers racing through all laps of a race with:
    - Animated car icons racing around the track (like ghost lap comparison)
    - Track colored by who's faster on each segment
    - Real-time delta display during lap
    - Running cumulative gap display
    - Position tracking
    - Pit stop indicators
    - Gap evolution chart
    - Speed comparison
    
    Controls:
    - Space: Play/Pause
    - R: Reset to lap 1
    - Left/Right: Previous/Next lap
    - +/-: Adjust playback speed
    - L: Jump to specific lap
    """
    
    def __init__(
        self,
        race1: RaceData,
        race2: RaceData,
        comparison: RaceComparison,
        session=None,
        title: str = "Race Replay",
        rotation: float = 0.0,
        fps: int = 30,
        playback_speed: float = 1.0,
    ):
        self.race1 = race1
        self.race2 = race2
        self.comparison = comparison
        self.session = session
        self.title = title
        self.rotation = rotation
        self.fps = fps
        self.playback_speed = playback_speed
        
        # Animation state
        self.current_lap = 0
        self.current_frame = 0
        self.is_playing = False
        self.total_laps = comparison.total_laps
        
        # Colors
        self.color1 = comparison.driver1_color
        self.color2 = comparison.driver2_color
        self.color1_hex = "#{:02x}{:02x}{:02x}".format(*self.color1)
        self.color2_hex = "#{:02x}{:02x}{:02x}".format(*self.color2)
        
        # Get the first lap with telemetry for frame calculations
        self.current_tel_pair = self._get_current_tel_pair()
        self.total_frames = len(self.current_tel_pair.x1) if self.current_tel_pair.has_telemetry else 100
        
        # Setup figure
        self._setup_figure()
        self._setup_controls()
        
        self.animation = None
    
    def _get_current_tel_pair(self) -> LapTelemetryPair:
        """Get telemetry pair for current lap."""
        if self.current_lap < len(self.comparison.lap_telemetry_pairs):
            return self.comparison.lap_telemetry_pairs[self.current_lap]
        return self.comparison.lap_telemetry_pairs[0] if self.comparison.lap_telemetry_pairs else None
    
    def _setup_figure(self):
        """Setup the matplotlib figure and axes."""
        self.fig = plt.figure(figsize=(20, 12), facecolor=COLORS["background"])
        self.fig.canvas.manager.set_window_title(self.title)
        
        # Grid layout - similar to GhostComparisonReplay
        gs = gridspec.GridSpec(
            5, 6,
            figure=self.fig,
            height_ratios=[0.12, 1, 0.25, 0.15, 0.08],
            width_ratios=[2.5, 0.5, 0.5, 0.5, 0.5, 0.5],
            hspace=0.12,
            wspace=0.12,
        )
        
        # Header with driver info
        self.ax_header = self.fig.add_subplot(gs[0, :])
        self.ax_header.set_facecolor(COLORS["background_light"])
        self.ax_header.axis("off")
        
        # Main track view
        self.ax_track = self.fig.add_subplot(gs[1, :4])
        self.ax_track.set_facecolor(COLORS["background"])
        self.ax_track.set_aspect("equal")
        self.ax_track.axis("off")
        
        # Delta/gap panel
        self.ax_delta = self.fig.add_subplot(gs[1, 4:])
        self.ax_delta.set_facecolor(COLORS["background_light"])
        self.ax_delta.axis("off")
        
        # Gap evolution chart (replacing telemetry panel)
        self.ax_gap_chart = self.fig.add_subplot(gs[2, :4])
        self.ax_gap_chart.set_facecolor(COLORS["background"])
        
        # Speed comparison
        self.ax_speed = self.fig.add_subplot(gs[2, 4:])
        self.ax_speed.set_facecolor(COLORS["background_light"])
        self.ax_speed.axis("off")
        
        # Driver 1 info panel
        self.ax_driver1 = self.fig.add_subplot(gs[3, :3])
        self.ax_driver1.set_facecolor(COLORS["background"])
        self.ax_driver1.axis("off")
        
        # Driver 2 info panel
        self.ax_driver2 = self.fig.add_subplot(gs[3, 3:])
        self.ax_driver2.set_facecolor(COLORS["background"])
        self.ax_driver2.axis("off")
        
        # Progress bar
        self.ax_progress = self.fig.add_subplot(gs[4, :4])
        self.ax_progress.set_facecolor(COLORS["background"])
        
        # Draw static elements
        self._draw_header()
        self._draw_track()
        self._draw_delta_panel()
        self._draw_gap_chart()
        self._setup_speed_display()
        self._draw_driver_panels()
        self._setup_progress_bar()
        
        # Create dynamic elements
        self._create_dynamic_elements()
    
    def _draw_header(self):
        """Draw header with driver comparison and lap info."""
        self.ax_header.set_xlim(0, 1)
        self.ax_header.set_ylim(0, 1)
        
        comp = self.comparison
        
        # Driver 1 info (left)
        self.ax_header.add_patch(FancyBboxPatch(
            (0.02, 0.15), 0.28, 0.7,
            boxstyle="round,pad=0.02",
            facecolor=self.color1_hex,
            edgecolor="white", linewidth=2, alpha=0.8,
            transform=self.ax_header.transAxes,
        ))
        self.ax_header.text(
            0.16, 0.5, comp.driver1,
            color="white", fontsize=18, fontweight="bold",
            ha="center", va="center",
        )
        self.ax_header.text(
            0.16, 0.2, comp.team1,
            color="white", fontsize=9,
            ha="center", va="center", alpha=0.8,
        )
        
        # Current lap indicator (center)
        self.lap_indicator = self.ax_header.text(
            0.5, 0.65, f"LAP 1 / {self.total_laps}",
            color=COLORS["text_highlight"], fontsize=24, fontweight="bold",
            ha="center", va="center",
        )
        self.ax_header.text(
            0.5, 0.3, "RACE REPLAY",
            color=COLORS["text_dim"], fontsize=12,
            ha="center", va="center",
        )
        
        # Driver 2 info (right)
        self.ax_header.add_patch(FancyBboxPatch(
            (0.70, 0.15), 0.28, 0.7,
            boxstyle="round,pad=0.02",
            facecolor=self.color2_hex,
            edgecolor="white", linewidth=2, alpha=0.8,
            transform=self.ax_header.transAxes,
        ))
        self.ax_header.text(
            0.84, 0.5, comp.driver2,
            color="white", fontsize=18, fontweight="bold",
            ha="center", va="center",
        )
        self.ax_header.text(
            0.84, 0.2, comp.team2,
            color="white", fontsize=9,
            ha="center", va="center", alpha=0.8,
        )
    
    def _draw_track(self):
        """Draw track with color-coded segments."""
        tel_pair = self._get_current_tel_pair()
        
        if not tel_pair.has_telemetry:
            self.ax_track.text(
                0.5, 0.5, f"No telemetry data for Lap {self.current_lap + 1}",
                transform=self.ax_track.transAxes,
                ha="center", va="center",
                color=COLORS["text"], fontsize=14,
            )
            return
        
        x, y = tel_pair.x1, tel_pair.y1
        
        # Create line segments with colors
        points = np.array([x, y]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)
        colors = tel_pair.segment_colors[:len(segments)]
        
        # Draw outer track edge (neutral)
        self.ax_track.plot(
            x, y, color=COLORS["track_edge"], linewidth=22, alpha=0.3, zorder=1
        )
        
        # Draw colored segments
        lc = LineCollection(segments, colors=colors, linewidth=14, alpha=0.85, zorder=2)
        self.track_lc = self.ax_track.add_collection(lc)
        
        # Start/finish marker
        self.ax_track.scatter(
            x[0], y[0], s=300, c="white", marker="s", zorder=5,
            edgecolors="#00FF00", linewidths=3,
        )
        self.ax_track.text(
            x[0], y[0], "S/F",
            color="#00FF00", fontsize=9, ha="center", va="center",
            fontweight="bold", zorder=6,
        )
        
        # Title
        self.ax_track.set_title(
            self.title, color="white", fontsize=14, fontweight="bold", pad=10
        )
        
        # Legend
        legend_elements = [
            mpatches.Patch(facecolor=self.color1_hex, edgecolor="white",
                          label=f"{self.comparison.driver1} faster"),
            mpatches.Patch(facecolor=self.color2_hex, edgecolor="white",
                          label=f"{self.comparison.driver2} faster"),
            mpatches.Patch(facecolor="#888888", edgecolor="white", label="Equal"),
        ]
        legend = self.ax_track.legend(
            handles=legend_elements, loc="upper left",
            facecolor=COLORS["background_light"], edgecolor="white", fontsize=9, framealpha=0.9,
        )
        plt.setp(legend.get_texts(), color="white")
        
        # Set limits
        padding = (x.max() - x.min()) * 0.08
        self.ax_track.set_xlim(x.min() - padding, x.max() + padding)
        self.ax_track.set_ylim(y.min() - padding, y.max() + padding)
    
    def _draw_delta_panel(self):
        """Setup the delta/gap display panel."""
        self.ax_delta.set_xlim(0, 1)
        self.ax_delta.set_ylim(0, 1)
        
        # Title
        self.ax_delta.text(
            0.5, 0.95, "RACE GAP",
            color="white", fontsize=12, fontweight="bold",
            ha="center", va="top",
        )
        
        # Cumulative gap display
        self.ax_delta.text(
            0.5, 0.82, "Race Gap",
            color=COLORS["text_dim"], fontsize=10, ha="center", va="center",
        )
        self.race_gap_text = self.ax_delta.text(
            0.5, 0.70, "+0.000s",
            color="white", fontsize=24, fontweight="bold",
            ha="center", va="center",
        )
        
        # Lap delta display
        self.ax_delta.text(
            0.5, 0.55, "Lap Delta",
            color=COLORS["text_dim"], fontsize=10, ha="center", va="center",
        )
        self.lap_delta_text = self.ax_delta.text(
            0.5, 0.43, "+0.000s",
            color="white", fontsize=18, fontweight="bold",
            ha="center", va="center",
        )
        
        # Gap bar visualization
        self.ax_delta.add_patch(FancyBboxPatch(
            (0.1, 0.28), 0.8, 0.08,
            boxstyle="round,pad=0.01",
            facecolor=COLORS["gauge_bg"], edgecolor=COLORS["text_dim"],
            transform=self.ax_delta.transAxes,
        ))
        self.ax_delta.axvline(x=0.5, ymin=0.28, ymax=0.36, color="white", linewidth=2)
        
        self.delta_bar = self.ax_delta.add_patch(FancyBboxPatch(
            (0.5, 0.29), 0.0, 0.06,
            boxstyle="round,pad=0.005",
            facecolor=self.color1_hex,
            transform=self.ax_delta.transAxes,
        ))
        
        # Driver labels for gap bar
        self.ax_delta.text(
            0.15, 0.23, self.comparison.driver1,
            color=self.color1_hex, fontsize=10, fontweight="bold", ha="center",
        )
        self.ax_delta.text(
            0.85, 0.23, self.comparison.driver2,
            color=self.color2_hex, fontsize=10, fontweight="bold", ha="center",
        )
        
        # Pit stop indicator
        self.pit_indicator = self.ax_delta.text(
            0.5, 0.12, "",
            color=COLORS["pit_indicator"], fontsize=10, fontweight="bold",
            ha="center", va="center",
        )
        
        # Leader indicator
        self.leader_text = self.ax_delta.text(
            0.5, 0.03, "",
            color=COLORS["text"], fontsize=11, fontweight="bold",
            ha="center", va="center",
        )
    
    def _draw_gap_chart(self):
        """Draw the gap evolution chart."""
        laps = list(range(1, self.total_laps + 1))
        gaps = self.comparison.lap_gaps
        
        # Fill areas
        self.ax_gap_chart.fill_between(
            laps, [0] * len(gaps), gaps,
            where=[g > 0 for g in gaps],
            color=self.color1_hex, alpha=0.3,
            label=f"{self.comparison.driver1} ahead",
        )
        self.ax_gap_chart.fill_between(
            laps, [0] * len(gaps), gaps,
            where=[g <= 0 for g in gaps],
            color=self.color2_hex, alpha=0.3,
            label=f"{self.comparison.driver2} ahead",
        )
        
        # Plot line
        self.ax_gap_chart.plot(laps, gaps, color="white", linewidth=2, zorder=5)
        
        # Zero line
        self.ax_gap_chart.axhline(y=0, color=COLORS["text_dim"], linewidth=1, linestyle="--")
        
        # Mark pit stops
        for pit_lap in self.comparison.pit_laps1:
            self.ax_gap_chart.axvline(x=pit_lap, color=self.color1_hex, linestyle=":", alpha=0.7)
        for pit_lap in self.comparison.pit_laps2:
            self.ax_gap_chart.axvline(x=pit_lap, color=self.color2_hex, linestyle=":", alpha=0.7)
        
        # Progress marker
        self.gap_marker = self.ax_gap_chart.axvline(
            x=1, color=COLORS["text_highlight"], linewidth=2, zorder=10
        )
        
        # Styling
        self.ax_gap_chart.set_xlabel("Lap", color=COLORS["text"], fontsize=10)
        self.ax_gap_chart.set_ylabel("Gap (s)", color=COLORS["text"], fontsize=10)
        self.ax_gap_chart.tick_params(colors=COLORS["text"])
        self.ax_gap_chart.set_xlim(1, self.total_laps)
        
        legend = self.ax_gap_chart.legend(
            loc="upper right", facecolor=COLORS["background_light"],
            edgecolor=COLORS["text_dim"], fontsize=9,
        )
        plt.setp(legend.get_texts(), color=COLORS["text"])
        
        for spine in self.ax_gap_chart.spines.values():
            spine.set_color(COLORS["text_dim"])
        
        self.ax_gap_chart.grid(True, alpha=0.2, color=COLORS["text_dim"])
    
    def _setup_speed_display(self):
        """Setup the current speed comparison display."""
        self.ax_speed.set_xlim(0, 1)
        self.ax_speed.set_ylim(0, 1)
        
        # Title
        self.ax_speed.text(
            0.5, 0.95, "SPEED", color=COLORS["text_dim"], fontsize=10,
            ha="center", va="top",
        )
        
        # Driver 1 speed
        self.ax_speed.add_patch(Circle(
            (0.25, 0.65), 0.15,
            facecolor=self.color1_hex, edgecolor="white", linewidth=2, alpha=0.3,
            transform=self.ax_speed.transAxes,
        ))
        self.speed1_text = self.ax_speed.text(
            0.25, 0.65, "0",
            color="white", fontsize=18, fontweight="bold",
            ha="center", va="center",
        )
        self.ax_speed.text(
            0.25, 0.45, self.comparison.driver1,
            color=self.color1_hex, fontsize=9, fontweight="bold", ha="center",
        )
        
        # Driver 2 speed
        self.ax_speed.add_patch(Circle(
            (0.75, 0.65), 0.15,
            facecolor=self.color2_hex, edgecolor="white", linewidth=2, alpha=0.3,
            transform=self.ax_speed.transAxes,
        ))
        self.speed2_text = self.ax_speed.text(
            0.75, 0.65, "0",
            color="white", fontsize=18, fontweight="bold",
            ha="center", va="center",
        )
        self.ax_speed.text(
            0.75, 0.45, self.comparison.driver2,
            color=self.color2_hex, fontsize=9, fontweight="bold", ha="center",
        )
        
        # Speed difference
        self.ax_speed.text(
            0.5, 0.25, "Δ Speed", color=COLORS["text_dim"], fontsize=9, ha="center",
        )
        self.speed_diff_text = self.ax_speed.text(
            0.5, 0.12, "+0 km/h",
            color="white", fontsize=12, fontweight="bold", ha="center",
        )
    
    def _draw_driver_panels(self):
        """Draw driver info panels."""
        comp = self.comparison
        
        # Driver 1 panel
        self.ax_driver1.set_xlim(0, 1)
        self.ax_driver1.set_ylim(0, 1)
        
        self.ax_driver1.add_patch(FancyBboxPatch(
            (0.02, 0.1), 0.96, 0.8,
            boxstyle="round,pad=0.02",
            facecolor=COLORS["background_light"], edgecolor=self.color1_hex,
            linewidth=2, alpha=0.6,
            transform=self.ax_driver1.transAxes,
        ))
        
        self.ax_driver1.text(
            0.5, 0.85, f"{comp.driver1}",
            color=self.color1_hex, fontsize=14, fontweight="bold", ha="center",
        )
        
        self.driver1_pos_text = self.ax_driver1.text(
            0.25, 0.5, "P1",
            color=COLORS["text_highlight"], fontsize=24, fontweight="bold", ha="center",
        )
        
        self.driver1_laptime_text = self.ax_driver1.text(
            0.7, 0.55, "Lap: --",
            color=COLORS["text"], fontsize=11, ha="center",
        )
        
        self.driver1_total_text = self.ax_driver1.text(
            0.7, 0.35, "Total: --",
            color=COLORS["text_dim"], fontsize=10, ha="center",
        )
        
        # Driver 2 panel
        self.ax_driver2.set_xlim(0, 1)
        self.ax_driver2.set_ylim(0, 1)
        
        self.ax_driver2.add_patch(FancyBboxPatch(
            (0.02, 0.1), 0.96, 0.8,
            boxstyle="round,pad=0.02",
            facecolor=COLORS["background_light"], edgecolor=self.color2_hex,
            linewidth=2, alpha=0.6,
            transform=self.ax_driver2.transAxes,
        ))
        
        self.ax_driver2.text(
            0.5, 0.85, f"{comp.driver2}",
            color=self.color2_hex, fontsize=14, fontweight="bold", ha="center",
        )
        
        self.driver2_pos_text = self.ax_driver2.text(
            0.25, 0.5, "P2",
            color=COLORS["text_highlight"], fontsize=24, fontweight="bold", ha="center",
        )
        
        self.driver2_laptime_text = self.ax_driver2.text(
            0.7, 0.55, "Lap: --",
            color=COLORS["text"], fontsize=11, ha="center",
        )
        
        self.driver2_total_text = self.ax_driver2.text(
            0.7, 0.35, "Total: --",
            color=COLORS["text_dim"], fontsize=10, ha="center",
        )
    
    def _setup_progress_bar(self):
        """Setup lap progress bar."""
        self.ax_progress.set_xlim(0, 100)
        self.ax_progress.set_ylim(0, 1)
        self.ax_progress.axis("off")
        
        # Background
        self.ax_progress.barh([0.5], [100], height=0.4, color=COLORS["gauge_bg"], alpha=0.5)
        
        # Progress bar
        self.progress_bar = self.ax_progress.barh(
            [0.5], [0], height=0.4, color=COLORS["text_highlight"], alpha=0.8
        )[0]
        
        # Distance markers
        for pct in [0, 25, 50, 75, 100]:
            self.ax_progress.axvline(x=pct, color=COLORS["text_dim"], linewidth=0.5, alpha=0.5)
            self.ax_progress.text(
                pct, 0.1, f"{pct}%", color=COLORS["text_dim"], fontsize=8, ha="center"
            )
    
    def _create_dynamic_elements(self):
        """Create car icons and trails."""
        tel_pair = self._get_current_tel_pair()
        
        if not tel_pair.has_telemetry:
            self.car1_patch = None
            self.car2_patch = None
            return
        
        # Driver 1 car
        self.car1_patch = create_car_icon(
            self.ax_track,
            tel_pair.x1[0], tel_pair.y1[0],
            tel_pair.angles1[0],
            size=1.0, color=self.color1_hex,
        )
        self.ax_track.add_patch(self.car1_patch)
        
        # Driver 2 car
        self.car2_patch = create_car_icon(
            self.ax_track,
            tel_pair.x2[0], tel_pair.y2[0],
            tel_pair.angles2[0],
            size=1.0, color=self.color2_hex,
        )
        self.ax_track.add_patch(self.car2_patch)
        
        # Trails
        self.trail_length = 60
        (self.trail1,) = self.ax_track.plot(
            [], [], "-", color=self.color1_hex, linewidth=4, alpha=0.4, zorder=9
        )
        (self.trail2,) = self.ax_track.plot(
            [], [], "-", color=self.color2_hex, linewidth=4, alpha=0.4, zorder=9
        )
        
        # Driver labels above cars
        label_offset = (tel_pair.y1.max() - tel_pair.y1.min()) * 0.04
        self.label1 = self.ax_track.text(
            tel_pair.x1[0], tel_pair.y1[0] + label_offset,
            self.comparison.driver1,
            color="white", fontsize=8, fontweight="bold",
            ha="center", va="bottom", zorder=20,
            bbox=dict(boxstyle="round,pad=0.2", facecolor=self.color1_hex, alpha=0.8),
        )
        self.label2 = self.ax_track.text(
            tel_pair.x2[0], tel_pair.y2[0] + label_offset,
            self.comparison.driver2,
            color="white", fontsize=8, fontweight="bold",
            ha="center", va="bottom", zorder=20,
            bbox=dict(boxstyle="round,pad=0.2", facecolor=self.color2_hex, alpha=0.8),
        )
    
    def _redraw_track_for_lap(self):
        """Redraw track with colors for current lap."""
        tel_pair = self._get_current_tel_pair()
        
        # Clear track axis and redraw
        self.ax_track.clear()
        self.ax_track.set_facecolor(COLORS["background"])
        self.ax_track.set_aspect("equal")
        self.ax_track.axis("off")
        
        if not tel_pair.has_telemetry:
            self.ax_track.text(
                0.5, 0.5, f"No telemetry for Lap {self.current_lap + 1}",
                transform=self.ax_track.transAxes,
                ha="center", va="center",
                color=COLORS["text"], fontsize=14,
            )
            self.car1_patch = None
            self.car2_patch = None
            return
        
        x, y = tel_pair.x1, tel_pair.y1
        
        # Create line segments with colors
        points = np.array([x, y]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)
        colors = tel_pair.segment_colors[:len(segments)]
        
        # Draw outer track edge
        self.ax_track.plot(
            x, y, color=COLORS["track_edge"], linewidth=22, alpha=0.3, zorder=1
        )
        
        # Draw colored segments
        lc = LineCollection(segments, colors=colors, linewidth=14, alpha=0.85, zorder=2)
        self.ax_track.add_collection(lc)
        
        # Start/finish marker
        self.ax_track.scatter(
            x[0], y[0], s=300, c="white", marker="s", zorder=5,
            edgecolors="#00FF00", linewidths=3,
        )
        self.ax_track.text(
            x[0], y[0], "S/F",
            color="#00FF00", fontsize=9, ha="center", va="center",
            fontweight="bold", zorder=6,
        )
        
        # Title
        self.ax_track.set_title(
            self.title, color="white", fontsize=14, fontweight="bold", pad=10
        )
        
        # Legend
        legend_elements = [
            mpatches.Patch(facecolor=self.color1_hex, edgecolor="white",
                          label=f"{self.comparison.driver1} faster"),
            mpatches.Patch(facecolor=self.color2_hex, edgecolor="white",
                          label=f"{self.comparison.driver2} faster"),
        ]
        legend = self.ax_track.legend(
            handles=legend_elements, loc="upper left",
            facecolor=COLORS["background_light"], edgecolor="white", fontsize=9,
        )
        plt.setp(legend.get_texts(), color="white")
        
        # Set limits
        padding = (x.max() - x.min()) * 0.08
        self.ax_track.set_xlim(x.min() - padding, x.max() + padding)
        self.ax_track.set_ylim(y.min() - padding, y.max() + padding)
        
        # Recreate dynamic elements
        self._create_dynamic_elements()
    
    def _setup_controls(self):
        """Setup playback controls."""
        ax_play = self.fig.add_axes([0.30, 0.01, 0.08, 0.03])
        ax_pause = self.fig.add_axes([0.39, 0.01, 0.08, 0.03])
        ax_reset = self.fig.add_axes([0.48, 0.01, 0.08, 0.03])
        ax_prev = self.fig.add_axes([0.20, 0.01, 0.08, 0.03])
        ax_next = self.fig.add_axes([0.58, 0.01, 0.08, 0.03])
        ax_speed = self.fig.add_axes([0.70, 0.015, 0.15, 0.02])
        
        self.btn_play = Button(ax_play, "▶ Play", color=COLORS["gauge_bg"], hovercolor="#00FF00")
        self.btn_pause = Button(ax_pause, "⏸ Pause", color=COLORS["gauge_bg"], hovercolor=COLORS["text_dim"])
        self.btn_reset = Button(ax_reset, "⏹ Reset", color=COLORS["gauge_bg"], hovercolor="#FF4444")
        self.btn_prev = Button(ax_prev, "◀ Prev", color=COLORS["gauge_bg"], hovercolor=COLORS["text_dim"])
        self.btn_next = Button(ax_next, "Next ▶", color=COLORS["gauge_bg"], hovercolor=COLORS["text_dim"])
        
        self.slider_speed = Slider(
            ax_speed, "Speed", 0.25, 4.0,
            valinit=self.playback_speed, valstep=0.25,
            color=COLORS["text_highlight"],
        )
        
        self.btn_play.on_clicked(self._on_play)
        self.btn_pause.on_clicked(self._on_pause)
        self.btn_reset.on_clicked(self._on_reset)
        self.btn_prev.on_clicked(self._on_prev_lap)
        self.btn_next.on_clicked(self._on_next_lap)
        self.slider_speed.on_changed(self._on_speed_change)
        
        self.fig.canvas.mpl_connect("key_press_event", self._on_key_press)
        
        self.fig.text(
            0.02, 0.01,
            "Controls: Space=Play/Pause | R=Reset | ←→=Prev/Next Lap | +/-=Speed",
            color=COLORS["text_dim"], fontsize=9,
        )
    
    def _on_play(self, event=None):
        if not self.is_playing:
            self.is_playing = True
            if self.animation is None:
                self._start_animation()
    
    def _on_pause(self, event=None):
        self.is_playing = False
    
    def _on_reset(self, event=None):
        self.is_playing = False
        self.current_lap = 0
        self.current_frame = 0
        self.current_tel_pair = self._get_current_tel_pair()
        self.total_frames = len(self.current_tel_pair.x1) if self.current_tel_pair.has_telemetry else 100
        self._redraw_track_for_lap()
        self._update_frame(0)
    
    def _on_prev_lap(self, event=None):
        if self.current_lap > 0:
            self.current_lap -= 1
            self.current_frame = 0
            self.current_tel_pair = self._get_current_tel_pair()
            self.total_frames = len(self.current_tel_pair.x1) if self.current_tel_pair.has_telemetry else 100
            self._redraw_track_for_lap()
            self._update_frame(0)
    
    def _on_next_lap(self, event=None):
        if self.current_lap < self.total_laps - 1:
            self.current_lap += 1
            self.current_frame = 0
            self.current_tel_pair = self._get_current_tel_pair()
            self.total_frames = len(self.current_tel_pair.x1) if self.current_tel_pair.has_telemetry else 100
            self._redraw_track_for_lap()
            self._update_frame(0)
    
    def _on_speed_change(self, val):
        self.playback_speed = val
    
    def _on_key_press(self, event):
        if event.key == " ":
            if self.is_playing:
                self._on_pause()
            else:
                self._on_play()
        elif event.key == "r":
            self._on_reset()
        elif event.key == "right":
            self._on_next_lap()
        elif event.key == "left":
            self._on_prev_lap()
        elif event.key in ["+", "="]:
            self.playback_speed = min(self.playback_speed + 0.25, 4.0)
            self.slider_speed.set_val(self.playback_speed)
        elif event.key == "-":
            self.playback_speed = max(self.playback_speed - 0.25, 0.25)
            self.slider_speed.set_val(self.playback_speed)
    
    def _update_frame(self, frame_idx: int):
        """Update all dynamic elements for the given frame."""
        tel_pair = self.current_tel_pair
        
        if not tel_pair.has_telemetry or self.car1_patch is None:
            return []
        
        frame_idx = int(frame_idx) % self.total_frames
        
        # Get positions
        x1, y1 = tel_pair.x1[frame_idx], tel_pair.y1[frame_idx]
        x2, y2 = tel_pair.x2[frame_idx], tel_pair.y2[frame_idx]
        
        # Update car 1
        self.car1_patch.remove()
        self.car1_patch = create_car_icon(
            self.ax_track, x1, y1, tel_pair.angles1[frame_idx],
            size=1.0, color=self.color1_hex,
        )
        self.ax_track.add_patch(self.car1_patch)
        
        # Update car 2
        self.car2_patch.remove()
        self.car2_patch = create_car_icon(
            self.ax_track, x2, y2, tel_pair.angles2[frame_idx],
            size=1.0, color=self.color2_hex,
        )
        self.ax_track.add_patch(self.car2_patch)
        
        # Update trails
        trail_start = max(0, frame_idx - self.trail_length)
        self.trail1.set_data(
            tel_pair.x1[trail_start:frame_idx + 1],
            tel_pair.y1[trail_start:frame_idx + 1]
        )
        self.trail2.set_data(
            tel_pair.x2[trail_start:frame_idx + 1],
            tel_pair.y2[trail_start:frame_idx + 1]
        )
        
        # Update driver labels
        label_offset = (tel_pair.y1.max() - tel_pair.y1.min()) * 0.04
        self.label1.set_position((x1, y1 + label_offset))
        self.label2.set_position((x2, y2 + label_offset))
        
        # Current times and deltas
        time1 = tel_pair.time1[frame_idx]
        time2 = tel_pair.time2[frame_idx]
        lap_delta = time2 - time1  # Positive = driver1 ahead in this lap
        
        # Race gap (cumulative)
        lap_idx = self.current_lap
        if lap_idx > 0 and lap_idx <= len(self.comparison.lap_gaps):
            prev_gap = self.comparison.lap_gaps[lap_idx - 1]
        else:
            prev_gap = 0
        race_gap = prev_gap + lap_delta
        
        # Update lap indicator
        self.lap_indicator.set_text(f"LAP {self.current_lap + 1} / {self.total_laps}")
        
        # Update delta displays
        if lap_delta > 0:
            self.lap_delta_text.set_text(f"+{lap_delta:.3f}s")
            self.lap_delta_text.set_color(self.color1_hex)
        else:
            self.lap_delta_text.set_text(f"{lap_delta:.3f}s")
            self.lap_delta_text.set_color(self.color2_hex)
        
        if race_gap > 0:
            self.race_gap_text.set_text(f"+{race_gap:.3f}s")
            self.race_gap_text.set_color(self.color1_hex)
            self.leader_text.set_text(f"{self.comparison.driver1} leads")
            self.leader_text.set_color(self.color1_hex)
            delta_width = min(abs(race_gap) * 0.02, 0.35)
            self.delta_bar.set_x(0.5 - delta_width)
            self.delta_bar.set_width(delta_width)
            self.delta_bar.set_facecolor(self.color1_hex)
        else:
            self.race_gap_text.set_text(f"{race_gap:.3f}s")
            self.race_gap_text.set_color(self.color2_hex)
            self.leader_text.set_text(f"{self.comparison.driver2} leads")
            self.leader_text.set_color(self.color2_hex)
            delta_width = min(abs(race_gap) * 0.02, 0.35)
            self.delta_bar.set_x(0.5)
            self.delta_bar.set_width(delta_width)
            self.delta_bar.set_facecolor(self.color2_hex)
        
        # Update speed displays
        speed1 = tel_pair.speed1[frame_idx]
        speed2 = tel_pair.speed2[frame_idx]
        speed_diff = speed1 - speed2
        
        self.speed1_text.set_text(f"{speed1:.0f}")
        self.speed2_text.set_text(f"{speed2:.0f}")
        
        if speed_diff > 0:
            self.speed_diff_text.set_text(f"+{speed_diff:.0f} km/h")
            self.speed_diff_text.set_color(self.color1_hex)
        else:
            self.speed_diff_text.set_text(f"{speed_diff:.0f} km/h")
            self.speed_diff_text.set_color(self.color2_hex)
        
        # Update gap chart marker
        progress_in_lap = frame_idx / self.total_frames
        chart_x = self.current_lap + 1 + progress_in_lap
        self.gap_marker.set_xdata([chart_x, chart_x])
        
        # Update progress bar
        progress = (frame_idx / self.total_frames) * 100
        self.progress_bar.set_width(progress)
        
        # Update driver panels
        if lap_idx < len(self.race1.laps):
            lap1 = self.race1.laps[lap_idx]
            self.driver1_pos_text.set_text(f"P{lap1.position}")
            self.driver1_laptime_text.set_text(f"Lap: {format_time(lap1.lap_time_seconds)}")
            self.driver1_total_text.set_text(f"Total: {format_time(lap1.cumulative_time)}")
        
        if lap_idx < len(self.race2.laps):
            lap2 = self.race2.laps[lap_idx]
            self.driver2_pos_text.set_text(f"P{lap2.position}")
            self.driver2_laptime_text.set_text(f"Lap: {format_time(lap2.lap_time_seconds)}")
            self.driver2_total_text.set_text(f"Total: {format_time(lap2.cumulative_time)}")
        
        # Pit stop indicator
        pit_text = ""
        if (self.current_lap + 1) in self.comparison.pit_laps1:
            pit_text += f"🔧 {self.comparison.driver1} PIT  "
        if (self.current_lap + 1) in self.comparison.pit_laps2:
            pit_text += f"🔧 {self.comparison.driver2} PIT"
        self.pit_indicator.set_text(pit_text)
        
        return [self.car1_patch, self.car2_patch, self.trail1, self.trail2]
    
    def _animate(self, frame):
        """Animation frame callback."""
        if self.is_playing:
            tel_pair = self.current_tel_pair
            
            if tel_pair.has_telemetry:
                # Calculate frames to advance
                lap_duration = tel_pair.lap_time1 if tel_pair.lap_time1 > 0 else 90
                frames_per_interval = int(
                    self.playback_speed * (self.total_frames / (lap_duration * self.fps))
                )
                frames_per_interval = max(1, frames_per_interval)
                
                self.current_frame += frames_per_interval
                
                # Check if lap complete
                if self.current_frame >= self.total_frames:
                    self.current_frame = 0
                    self.current_lap += 1
                    
                    if self.current_lap >= self.total_laps:
                        self.is_playing = False
                        self.current_lap = self.total_laps - 1
                        self._show_final_result()
                    else:
                        # Move to next lap
                        self.current_tel_pair = self._get_current_tel_pair()
                        self.total_frames = len(self.current_tel_pair.x1) if self.current_tel_pair.has_telemetry else 100
                        self._redraw_track_for_lap()
        
        return self._update_frame(self.current_frame)
    
    def _show_final_result(self):
        """Show final race result."""
        winner = self.comparison.winner
        gap = abs(self.comparison.final_gap)
        
        self.race_gap_text.set_text("🏁 FINISHED")
        self.race_gap_text.set_color(COLORS["text_highlight"])
        self.leader_text.set_text(f"Winner: {winner} by {format_gap(gap)}")
        self.leader_text.set_color(COLORS["text_highlight"])
        self.fig.canvas.draw_idle()
    
    def _start_animation(self):
        """Start the animation."""
        interval = 1000 / self.fps
        self.animation = FuncAnimation(
            self.fig, self._animate,
            interval=interval, blit=False, cache_frame_data=False,
        )
    
    def show(self):
        """Display the animation."""
        self._update_frame(0)
        self._start_animation()
        plt.show()
    
    def close(self):
        """Close the figure."""
        if self.animation:
            self.animation.event_source.stop()
        plt.close(self.fig)


def create_race_summary_plot(
    race1: RaceData,
    race2: RaceData,
    comparison: RaceComparison,
    title: str = "Race Summary",
) -> plt.Figure:
    """
    Create a static race summary plot.
    
    Shows:
    - Gap evolution over the race
    - Position changes
    - Lap time comparison
    - Final result
    """
    fig = plt.figure(figsize=(14, 10), facecolor=COLORS["background"])
    
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.3)
    
    color1_hex = "#{:02x}{:02x}{:02x}".format(*comparison.driver1_color)
    color2_hex = "#{:02x}{:02x}{:02x}".format(*comparison.driver2_color)
    
    # Gap evolution
    ax_gap = fig.add_subplot(gs[0, 0])
    ax_gap.set_facecolor(COLORS["background_light"])
    ax_gap.set_title("Gap Evolution", color=COLORS["text"], fontsize=12)
    
    laps = list(range(1, comparison.total_laps + 1))
    gaps = comparison.lap_gaps
    
    ax_gap.fill_between(
        laps, [0] * len(gaps), gaps,
        where=[g > 0 for g in gaps],
        color=color1_hex, alpha=0.3,
        label=f"{comparison.driver1} ahead",
    )
    ax_gap.fill_between(
        laps, [0] * len(gaps), gaps,
        where=[g <= 0 for g in gaps],
        color=color2_hex, alpha=0.3,
        label=f"{comparison.driver2} ahead",
    )
    ax_gap.plot(laps, gaps, color="white", linewidth=2)
    ax_gap.axhline(y=0, color=COLORS["text_dim"], linestyle="--")
    
    # Mark pit stops
    for pit_lap in comparison.pit_laps1:
        ax_gap.axvline(x=pit_lap, color=color1_hex, linestyle=":", alpha=0.7)
    for pit_lap in comparison.pit_laps2:
        ax_gap.axvline(x=pit_lap, color=color2_hex, linestyle=":", alpha=0.7)
    
    ax_gap.set_xlabel("Lap", color=COLORS["text"])
    ax_gap.set_ylabel("Gap (s)", color=COLORS["text"])
    ax_gap.tick_params(colors=COLORS["text"])
    ax_gap.legend(facecolor=COLORS["background_light"], labelcolor=COLORS["text"])
    for spine in ax_gap.spines.values():
        spine.set_color(COLORS["text_dim"])
    
    # Position chart
    ax_pos = fig.add_subplot(gs[0, 1])
    ax_pos.set_facecolor(COLORS["background_light"])
    ax_pos.set_title("Position Through Race", color=COLORS["text"], fontsize=12)
    
    ax_pos.plot(laps, comparison.positions1, color=color1_hex, linewidth=2,
                marker="o", markersize=3, label=comparison.driver1)
    ax_pos.plot(laps, comparison.positions2, color=color2_hex, linewidth=2,
                marker="o", markersize=3, label=comparison.driver2)
    
    ax_pos.invert_yaxis()  # P1 at top
    ax_pos.set_xlabel("Lap", color=COLORS["text"])
    ax_pos.set_ylabel("Position", color=COLORS["text"])
    ax_pos.tick_params(colors=COLORS["text"])
    ax_pos.legend(facecolor=COLORS["background_light"], labelcolor=COLORS["text"])
    for spine in ax_pos.spines.values():
        spine.set_color(COLORS["text_dim"])
    
    # Lap times
    ax_laptimes = fig.add_subplot(gs[1, 0])
    ax_laptimes.set_facecolor(COLORS["background_light"])
    ax_laptimes.set_title("Lap Times", color=COLORS["text"], fontsize=12)
    
    times1 = [lap.lap_time_seconds for lap in race1.laps[:comparison.total_laps]]
    times2 = [lap.lap_time_seconds for lap in race2.laps[:comparison.total_laps]]
    
    ax_laptimes.plot(laps[:len(times1)], times1, color=color1_hex, linewidth=1.5,
                     alpha=0.8, label=comparison.driver1)
    ax_laptimes.plot(laps[:len(times2)], times2, color=color2_hex, linewidth=1.5,
                     alpha=0.8, label=comparison.driver2)
    
    ax_laptimes.set_xlabel("Lap", color=COLORS["text"])
    ax_laptimes.set_ylabel("Lap Time (s)", color=COLORS["text"])
    ax_laptimes.tick_params(colors=COLORS["text"])
    ax_laptimes.legend(facecolor=COLORS["background_light"], labelcolor=COLORS["text"])
    for spine in ax_laptimes.spines.values():
        spine.set_color(COLORS["text_dim"])
    
    # Summary panel
    ax_summary = fig.add_subplot(gs[1, 1])
    ax_summary.set_facecolor(COLORS["background_light"])
    ax_summary.axis("off")
    ax_summary.set_title("Race Summary", color=COLORS["text"], fontsize=12)
    
    summary_text = f"""
    🏁 RACE RESULT
    
    Winner: {comparison.winner}
    Final Gap: {format_gap(abs(comparison.final_gap))}
    
    {comparison.driver1}:
      Final Position: P{comparison.positions1[-1] if comparison.positions1 else '?'}
      Pit Stops: {len(comparison.pit_laps1)}
      Laps Completed: {race1.total_laps}
    
    {comparison.driver2}:
      Final Position: P{comparison.positions2[-1] if comparison.positions2 else '?'}
      Pit Stops: {len(comparison.pit_laps2)}
      Laps Completed: {race2.total_laps}
    """
    
    ax_summary.text(
        0.1, 0.9, summary_text,
        transform=ax_summary.transAxes,
        va="top", ha="left",
        color=COLORS["text"],
        fontsize=11,
        fontfamily="monospace",
    )
    
    fig.suptitle(title, color=COLORS["text"], fontsize=14, fontweight="bold")
    
    return fig


def run_race_replay(
    session,
    driver1: str,
    driver2: str,
    title: str = "Race Replay",
    show_summary: bool = True,
    show_replay: bool = True,
):
    """
    Run full race ghost car replay.
    
    Args:
        session: FastF1 Race session
        driver1: First driver code
        driver2: Second driver code
        title: Window title
        show_summary: Whether to show static summary first
        show_replay: Whether to show animated replay
    """
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    
    console = Console()
    
    # Get circuit info for rotation first
    circuit_info = get_circuit_info(session)
    rotation = circuit_info.get("rotation", 0) if circuit_info else 0
    
    # Get year for team colors
    year = session.event.year if hasattr(session, "event") else 2024
    
    # Load race data
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Loading race data for {driver1}...[/cyan]".format(driver1=driver1)),
        console=console,
    ) as progress:
        progress.add_task("loading", total=None)
        race1 = get_driver_race_laps(session, driver1, load_telemetry=True)
    
    if race1 is None:
        console.print(f"[red]Could not load race data for {driver1}[/red]")
        return
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Loading race data for {driver2}...[/cyan]".format(driver2=driver2)),
        console=console,
    ) as progress:
        progress.add_task("loading", total=None)
        race2 = get_driver_race_laps(session, driver2, load_telemetry=True)
    
    if race2 is None:
        console.print(f"[red]Could not load race data for {driver2}[/red]")
        return
    
    console.print(f"[green]✓ Loaded {race1.total_laps} laps for {driver1}[/green]")
    console.print(f"[green]✓ Loaded {race2.total_laps} laps for {driver2}[/green]")
    
    # Analyze comparison (with rotation for synchronized telemetry)
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Analyzing race comparison and building lap telemetry...[/cyan]"),
        console=console,
    ) as progress:
        progress.add_task("analyzing", total=None)
        comparison = analyze_race_comparison(race1, race2, session, year, rotation)
    
    # Count laps with telemetry
    laps_with_telemetry = sum(1 for tel_pair in comparison.lap_telemetry_pairs if tel_pair.has_telemetry)
    
    console.print(f"[green]✓ Analysis complete - {comparison.total_laps} laps compared[/green]")
    console.print(f"[green]✓ {laps_with_telemetry} laps have telemetry for animation[/green]")
    console.print(f"[yellow]Winner: {comparison.winner} by {format_gap(abs(comparison.final_gap))}[/yellow]")
    
    # Show summary plot
    if show_summary:
        console.print("\n[cyan]Displaying race summary...[/cyan]")
        fig = create_race_summary_plot(race1, race2, comparison, title)
        plt.show()
    
    # Show replay
    if show_replay:
        console.print("\n[cyan]Starting race replay animation...[/cyan]")
        console.print("[dim]Controls: Space=Play/Pause, R=Reset, ←/→=Prev/Next Lap, +/-=Speed[/dim]")
        console.print("[dim]Two ghost cars will race through each lap with real-time delta tracking![/dim]")
        
        replay = RaceReplayAnimation(
            race1=race1,
            race2=race2,
            comparison=comparison,
            session=session,
            title=title,
            rotation=rotation,
        )
        replay.show()


# Standalone test
if __name__ == "__main__":
    from data_loader import load_session
    
    print("Loading test race data...")
    session = load_session(2024, 1, "R")  # Bahrain 2024 Race
    
    run_race_replay(
        session=session,
        driver1="VER",
        driver2="LEC",
        title="Bahrain GP 2024 - VER vs LEC",
        show_summary=True,
        show_replay=True,
    )
