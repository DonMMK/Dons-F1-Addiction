"""
Formula 1 Driving Assistant - Ghost Car Comparison Module

Animated ghost car comparison allowing users to compare two drivers:
- Two F1 car icons moving through the track simultaneously
- Track sections colored by who is faster (using team colors)
- Live telemetry comparison display
- Gap/delta time visualization
- Speed difference analysis
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
from matplotlib.patches import FancyBboxPatch, Polygon, Circle
from matplotlib.collections import LineCollection
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button, Slider
from matplotlib.colors import LinearSegmentedColormap, Normalize
import matplotlib.gridspec as gridspec
import numpy as np
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
from scipy import interpolate

from data_loader import (
    TelemetryData,
    DrivingZones,
    get_lap_telemetry,
    analyze_driving_zones,
    get_circuit_info,
)

# Team colors (2024 season reference - will be dynamically overridden)
TEAM_COLORS = {
    "Red Bull Racing": "#3671C6",
    "Ferrari": "#E80020",
    "Mercedes": "#27F4D2",
    "McLaren": "#FF8000",
    "Aston Martin": "#229971",
    "Alpine": "#FF87BC",
    "Williams": "#64C4FF",
    "AlphaTauri": "#6692FF",
    "RB": "#6692FF",  # Renamed from AlphaTauri
    "Kick Sauber": "#52E252",
    "Alfa Romeo": "#C92D4B",
    "Haas F1 Team": "#B6BABD",
    # Fallback
    "Unknown": "#888888",
}

# Driver to team mapping shortcuts
DRIVER_TEAMS = {
    "VER": "Red Bull Racing",
    "PER": "Red Bull Racing",
    "LEC": "Ferrari",
    "SAI": "Ferrari",
    "HAM": "Mercedes",
    "RUS": "Mercedes",
    "NOR": "McLaren",
    "PIA": "McLaren",
    "ALO": "Aston Martin",
    "STR": "Aston Martin",
    "OCO": "Alpine",
    "GAS": "Alpine",
    "ALB": "Williams",
    "SAR": "Williams",
    "COL": "Williams",
    "TSU": "RB",
    "RIC": "RB",
    "LAW": "RB",
    "BOT": "Kick Sauber",
    "ZHO": "Kick Sauber",
    "MAG": "Haas F1 Team",
    "HUL": "Haas F1 Team",
    "BEA": "Haas F1 Team",
}


@dataclass
class ComparisonSegment:
    """Represents a track segment with comparison data."""

    start_idx: int
    end_idx: int
    faster_driver: int  # 0 = driver1, 1 = driver2, -1 = equal
    time_delta: float  # Positive = driver1 faster, negative = driver2 faster
    avg_speed_diff: float  # driver1 speed - driver2 speed


@dataclass
class LapComparison:
    """Contains full lap comparison analysis."""

    driver1: str
    driver2: str
    driver1_team: str
    driver2_team: str
    driver1_color: str
    driver2_color: str
    driver1_time: float
    driver2_time: float
    total_delta: float
    segments: List[ComparisonSegment]
    mini_sectors: List[Dict[str, Any]]  # Mini-sector times and deltas


def get_driver_color(driver: str, team: str = None) -> str:
    """Get team color for a driver."""
    if team and team in TEAM_COLORS:
        return TEAM_COLORS[team]
    if driver in DRIVER_TEAMS:
        return TEAM_COLORS.get(DRIVER_TEAMS[driver], "#888888")
    return "#888888"


def interpolate_telemetry_to_distance(
    telemetry: TelemetryData, target_distances: np.ndarray
) -> TelemetryData:
    """
    Interpolate telemetry data to common distance points for fair comparison.
    """
    # Create interpolation functions for each channel
    interp_x = interpolate.interp1d(
        telemetry.distance, telemetry.x, kind="linear", fill_value="extrapolate"
    )
    interp_y = interpolate.interp1d(
        telemetry.distance, telemetry.y, kind="linear", fill_value="extrapolate"
    )
    interp_speed = interpolate.interp1d(
        telemetry.distance, telemetry.speed, kind="linear", fill_value="extrapolate"
    )
    interp_throttle = interpolate.interp1d(
        telemetry.distance, telemetry.throttle, kind="linear", fill_value="extrapolate"
    )
    interp_brake = interpolate.interp1d(
        telemetry.distance, telemetry.brake, kind="linear", fill_value="extrapolate"
    )
    interp_gear = interpolate.interp1d(
        telemetry.distance, telemetry.gear, kind="nearest", fill_value="extrapolate"
    )
    interp_time = interpolate.interp1d(
        telemetry.distance, telemetry.time, kind="linear", fill_value="extrapolate"
    )
    interp_drs = interpolate.interp1d(
        telemetry.distance, telemetry.drs, kind="nearest", fill_value="extrapolate"
    )

    return TelemetryData(
        x=interp_x(target_distances),
        y=interp_y(target_distances),
        speed=interp_speed(target_distances),
        throttle=interp_throttle(target_distances),
        brake=interp_brake(target_distances),
        gear=interp_gear(target_distances).astype(int),
        distance=target_distances.copy(),
        time=interp_time(target_distances),
        drs=interp_drs(target_distances),
    )


def analyze_lap_comparison(
    telemetry1: TelemetryData,
    telemetry2: TelemetryData,
    driver1: str,
    driver2: str,
    team1: str = None,
    team2: str = None,
    num_segments: int = 50,
) -> LapComparison:
    """
    Analyze and compare two laps to identify where each driver is faster.

    Args:
        telemetry1: First driver's telemetry
        telemetry2: Second driver's telemetry
        driver1: First driver code
        driver2: Second driver code
        team1: First driver's team
        team2: Second driver's team
        num_segments: Number of track segments for comparison

    Returns:
        LapComparison object with full analysis
    """
    # Create common distance grid
    max_dist = min(telemetry1.distance.max(), telemetry2.distance.max())
    min_dist = max(telemetry1.distance.min(), telemetry2.distance.min())

    # Use finer resolution for interpolation
    num_points = max(len(telemetry1.distance), len(telemetry2.distance))
    common_distances = np.linspace(min_dist, max_dist, num_points)

    # Interpolate both telemetries to common distance grid
    tel1_interp = interpolate_telemetry_to_distance(telemetry1, common_distances)
    tel2_interp = interpolate_telemetry_to_distance(telemetry2, common_distances)

    # Calculate time at each distance point
    time1 = tel1_interp.time - tel1_interp.time[0]
    time2 = tel2_interp.time - tel2_interp.time[0]

    # Total lap times
    lap_time1 = telemetry1.time[-1] - telemetry1.time[0]
    lap_time2 = telemetry2.time[-1] - telemetry2.time[0]
    total_delta = lap_time1 - lap_time2  # Positive = driver2 faster

    # Segment analysis
    segment_length = len(common_distances) // num_segments
    segments = []

    for i in range(num_segments):
        start_idx = i * segment_length
        end_idx = min((i + 1) * segment_length, len(common_distances) - 1)

        # Time delta in this segment
        segment_time1 = time1[end_idx] - time1[start_idx]
        segment_time2 = time2[end_idx] - time2[start_idx]
        time_delta = (
            segment_time2 - segment_time1
        )  # Positive = driver1 faster in segment

        # Speed difference
        avg_speed1 = np.mean(tel1_interp.speed[start_idx:end_idx])
        avg_speed2 = np.mean(tel2_interp.speed[start_idx:end_idx])
        speed_diff = avg_speed1 - avg_speed2

        # Determine faster driver
        if abs(time_delta) < 0.01:  # Within 10ms = essentially equal
            faster = -1
        elif time_delta > 0:
            faster = 0  # Driver 1 faster
        else:
            faster = 1  # Driver 2 faster

        segments.append(
            ComparisonSegment(
                start_idx=start_idx,
                end_idx=end_idx,
                faster_driver=faster,
                time_delta=time_delta,
                avg_speed_diff=speed_diff,
            )
        )

    # Mini-sector analysis (smaller divisions for detailed view)
    num_mini_sectors = 25
    mini_sector_length = len(common_distances) // num_mini_sectors
    mini_sectors = []

    cumulative_delta = 0
    for i in range(num_mini_sectors):
        start_idx = i * mini_sector_length
        end_idx = min((i + 1) * mini_sector_length, len(common_distances) - 1)

        sector_time1 = time1[end_idx] - time1[start_idx]
        sector_time2 = time2[end_idx] - time2[start_idx]
        sector_delta = sector_time2 - sector_time1
        cumulative_delta += sector_delta

        mini_sectors.append(
            {
                "sector": i + 1,
                "start_distance": common_distances[start_idx],
                "end_distance": common_distances[end_idx],
                "driver1_time": sector_time1,
                "driver2_time": sector_time2,
                "delta": sector_delta,
                "cumulative_delta": cumulative_delta,
                "faster": driver1 if sector_delta > 0 else driver2,
            }
        )

    # Get colors
    color1 = get_driver_color(driver1, team1)
    color2 = get_driver_color(driver2, team2)

    return LapComparison(
        driver1=driver1,
        driver2=driver2,
        driver1_team=team1 or DRIVER_TEAMS.get(driver1, "Unknown"),
        driver2_team=team2 or DRIVER_TEAMS.get(driver2, "Unknown"),
        driver1_color=color1,
        driver2_color=color2,
        driver1_time=lap_time1,
        driver2_time=lap_time2,
        total_delta=total_delta,
        segments=segments,
        mini_sectors=mini_sectors,
    )


def create_car_icon(ax, x, y, angle=0, size=1.0, color="#FF0000"):
    """Create an F1 car-shaped icon."""
    s = size * 120

    car_body = (
        np.array(
            [
                [0, -0.5],
                [-0.15, -0.45],
                [-0.18, -0.3],
                [-0.2, 0],
                [-0.18, 0.3],
                [-0.1, 0.45],
                [0, 0.55],
                [0.1, 0.45],
                [0.18, 0.3],
                [0.2, 0],
                [0.18, -0.3],
                [0.15, -0.45],
            ]
        )
        * s
    )

    angle_rad = np.radians(angle)
    cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
    rotation_matrix = np.array([[cos_a, -sin_a], [sin_a, cos_a]])
    car_body_rot = car_body @ rotation_matrix.T

    car_body_rot[:, 0] += x
    car_body_rot[:, 1] += y

    return Polygon(
        car_body_rot,
        closed=True,
        facecolor=color,
        edgecolor="white",
        linewidth=1.5,
        zorder=15,
    )


class GhostComparisonReplay:
    """
    Ghost car comparison replay with two cars racing side by side.

    Features:
    - Two F1 cars moving through the track
    - Track colored by who is faster in each section
    - Live delta time display
    - Speed comparison bars
    - Mini-sector time analysis

    Controls:
    - Space: Play/Pause
    - R: Reset
    - Arrow keys: Step through frames
    - +/-: Adjust playback speed
    """

    def __init__(
        self,
        telemetry1: TelemetryData,
        telemetry2: TelemetryData,
        comparison: LapComparison,
        title: str = "Ghost Comparison",
        rotation: float = 0.0,
        fps: int = 30,
        playback_speed: float = 1.0,
    ):
        self.tel1_orig = telemetry1
        self.tel2_orig = telemetry2
        self.comparison = comparison
        self.title = title
        self.rotation = rotation
        self.fps = fps
        self.playback_speed = playback_speed

        # Create synchronized telemetry on common distance grid
        max_dist = min(telemetry1.distance.max(), telemetry2.distance.max())
        min_dist = max(telemetry1.distance.min(), telemetry2.distance.min())
        self.num_points = max(len(telemetry1.distance), len(telemetry2.distance))
        self.common_distances = np.linspace(min_dist, max_dist, self.num_points)

        self.tel1 = interpolate_telemetry_to_distance(telemetry1, self.common_distances)
        self.tel2 = interpolate_telemetry_to_distance(telemetry2, self.common_distances)

        # Animation state
        self.current_frame = 0
        self.is_playing = False
        self.total_frames = self.num_points

        # Calculate times from start
        self.time1 = self.tel1.time - self.tel1.time[0]
        self.time2 = self.tel2.time - self.tel2.time[0]
        self.lap_duration = max(self.time1[-1], self.time2[-1])

        # Prepare rotated coordinates
        self.x1, self.y1 = self._rotate_coords(self.tel1.x, self.tel1.y)
        self.x2, self.y2 = self._rotate_coords(self.tel2.x, self.tel2.y)

        # Calculate car angles
        self.angles1 = self._calculate_angles(self.x1, self.y1)
        self.angles2 = self._calculate_angles(self.x2, self.y2)

        # Colors
        self.color1 = comparison.driver1_color
        self.color2 = comparison.driver2_color

        # Build track segment colors
        self._build_segment_colors()

        # Setup figure
        self._setup_figure()
        self._setup_controls()

        self.animation = None

    def _rotate_coords(
        self, x: np.ndarray, y: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Rotate coordinates by circuit rotation angle."""
        if self.rotation == 0:
            return x.copy(), y.copy()

        angle_rad = np.radians(self.rotation)
        cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)

        cx, cy = x.mean(), y.mean()
        x_centered = x - cx
        y_centered = y - cy

        x_rot = x_centered * cos_a - y_centered * sin_a + cx
        y_rot = x_centered * sin_a + y_centered * cos_a + cy

        return x_rot, y_rot

    def _calculate_angles(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Calculate heading angles along the track."""
        angles = np.zeros(len(x))
        for i in range(len(x) - 1):
            dx = x[i + 1] - x[i]
            dy = y[i + 1] - y[i]
            angles[i] = np.degrees(np.arctan2(dy, dx)) - 90
        angles[-1] = angles[-2]

        # Smooth angles
        window = 5
        angles = np.convolve(angles, np.ones(window) / window, mode="same")
        return angles

    def _build_segment_colors(self):
        """Build color array for track segments based on who's faster."""
        self.segment_colors = []

        for seg in self.comparison.segments:
            if seg.faster_driver == 0:
                color = self.color1
            elif seg.faster_driver == 1:
                color = self.color2
            else:
                color = "#888888"  # Equal/neutral

            # Add color for each point in segment
            for _ in range(seg.end_idx - seg.start_idx):
                self.segment_colors.append(color)

        # Pad to match full length
        while len(self.segment_colors) < self.num_points:
            self.segment_colors.append("#888888")

    def _setup_figure(self):
        """Setup the matplotlib figure."""
        self.fig = plt.figure(figsize=(20, 12), facecolor="#1a1a2e")
        self.fig.canvas.manager.set_window_title(self.title)

        # Grid layout
        gs = gridspec.GridSpec(
            4,
            6,
            figure=self.fig,
            height_ratios=[0.12, 1, 0.25, 0.08],
            width_ratios=[2.5, 0.5, 0.5, 0.5, 0.5, 0.5],
            hspace=0.12,
            wspace=0.12,
        )

        # Header with driver info
        self.ax_header = self.fig.add_subplot(gs[0, :])
        self.ax_header.set_facecolor("#252540")
        self.ax_header.axis("off")

        # Main track view
        self.ax_track = self.fig.add_subplot(gs[1, :4])
        self.ax_track.set_facecolor("#1a1a2e")
        self.ax_track.set_aspect("equal")
        self.ax_track.axis("off")

        # Delta/gap panel
        self.ax_delta = self.fig.add_subplot(gs[1, 4:])
        self.ax_delta.set_facecolor("#252540")
        self.ax_delta.axis("off")

        # Telemetry comparison
        self.ax_telemetry = self.fig.add_subplot(gs[2, :4])
        self.ax_telemetry.set_facecolor("#1a1a2e")

        # Speed comparison
        self.ax_speed = self.fig.add_subplot(gs[2, 4:])
        self.ax_speed.set_facecolor("#252540")
        self.ax_speed.axis("off")

        # Progress bar
        self.ax_progress = self.fig.add_subplot(gs[3, :4])
        self.ax_progress.set_facecolor("#1a1a2e")

        # Draw static elements
        self._draw_header()
        self._draw_comparison_track()
        self._draw_delta_panel()
        self._setup_telemetry_display()
        self._setup_speed_display()
        self._setup_progress_bar()

        # Create dynamic elements
        self._create_dynamic_elements()

    def _draw_header(self):
        """Draw header with driver comparison info."""
        self.ax_header.set_xlim(0, 1)
        self.ax_header.set_ylim(0, 1)

        comp = self.comparison

        # Driver 1 info (left)
        self.ax_header.add_patch(
            FancyBboxPatch(
                (0.02, 0.15),
                0.35,
                0.7,
                boxstyle="round,pad=0.02",
                facecolor=comp.driver1_color,
                edgecolor="white",
                linewidth=2,
                alpha=0.8,
                transform=self.ax_header.transAxes,
            )
        )
        self.ax_header.text(
            0.195,
            0.5,
            comp.driver1,
            color="white",
            fontsize=20,
            fontweight="bold",
            ha="center",
            va="center",
        )

        # Format lap time
        min1 = int(comp.driver1_time // 60)
        sec1 = comp.driver1_time % 60
        self.ax_header.text(
            0.195,
            0.2,
            f"{min1}:{sec1:06.3f}",
            color="white",
            fontsize=11,
            ha="center",
            va="center",
        )

        # VS in middle
        self.ax_header.text(
            0.5,
            0.5,
            "VS",
            color="#FFD700",
            fontsize=24,
            fontweight="bold",
            ha="center",
            va="center",
        )

        # Driver 2 info (right)
        self.ax_header.add_patch(
            FancyBboxPatch(
                (0.63, 0.15),
                0.35,
                0.7,
                boxstyle="round,pad=0.02",
                facecolor=comp.driver2_color,
                edgecolor="white",
                linewidth=2,
                alpha=0.8,
                transform=self.ax_header.transAxes,
            )
        )
        self.ax_header.text(
            0.805,
            0.5,
            comp.driver2,
            color="white",
            fontsize=20,
            fontweight="bold",
            ha="center",
            va="center",
        )

        min2 = int(comp.driver2_time // 60)
        sec2 = comp.driver2_time % 60
        self.ax_header.text(
            0.805,
            0.2,
            f"{min2}:{sec2:06.3f}",
            color="white",
            fontsize=11,
            ha="center",
            va="center",
        )

        # Total delta
        delta = comp.total_delta
        delta_sign = "+" if delta > 0 else ""
        delta_color = comp.driver2_color if delta > 0 else comp.driver1_color
        faster = comp.driver2 if delta > 0 else comp.driver1

        self.ax_header.text(
            0.5,
            0.15,
            f"{faster} faster by {delta_sign}{abs(delta):.3f}s",
            color=delta_color,
            fontsize=10,
            ha="center",
            va="center",
        )

    def _draw_comparison_track(self):
        """Draw track with color-coded segments showing who's faster."""
        # Create line segments with colors
        points = np.array([self.x1, self.y1]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)

        # Color each segment based on who's faster
        colors = [self.segment_colors[i] for i in range(len(segments))]

        # Draw outer track edge (neutral)
        self.ax_track.plot(
            self.x1, self.y1, color="#666666", linewidth=22, alpha=0.3, zorder=1
        )

        # Draw colored segments
        lc = LineCollection(segments, colors=colors, linewidth=14, alpha=0.85, zorder=2)
        self.ax_track.add_collection(lc)

        # Start/finish marker
        self.ax_track.scatter(
            self.x1[0],
            self.y1[0],
            s=300,
            c="white",
            marker="s",
            zorder=5,
            edgecolors="#00FF00",
            linewidths=3,
        )
        self.ax_track.text(
            self.x1[0],
            self.y1[0],
            "S/F",
            color="#00FF00",
            fontsize=9,
            ha="center",
            va="center",
            fontweight="bold",
            zorder=6,
        )

        # Title
        self.ax_track.set_title(
            self.title, color="white", fontsize=14, fontweight="bold", pad=10
        )

        # Legend
        legend_elements = [
            mpatches.Patch(
                facecolor=self.color1,
                edgecolor="white",
                label=f"{self.comparison.driver1} faster",
            ),
            mpatches.Patch(
                facecolor=self.color2,
                edgecolor="white",
                label=f"{self.comparison.driver2} faster",
            ),
            mpatches.Patch(facecolor="#888888", edgecolor="white", label="Equal"),
        ]
        legend = self.ax_track.legend(
            handles=legend_elements,
            loc="upper left",
            facecolor="#252540",
            edgecolor="white",
            fontsize=9,
            framealpha=0.9,
        )
        plt.setp(legend.get_texts(), color="white")

        # Set limits
        padding = (self.x1.max() - self.x1.min()) * 0.08
        self.ax_track.set_xlim(self.x1.min() - padding, self.x1.max() + padding)
        self.ax_track.set_ylim(self.y1.min() - padding, self.y1.max() + padding)

    def _draw_delta_panel(self):
        """Setup the delta/gap display panel."""
        self.ax_delta.set_xlim(0, 1)
        self.ax_delta.set_ylim(0, 1)

        # Title
        self.ax_delta.text(
            0.5,
            0.95,
            "GAP ANALYSIS",
            color="white",
            fontsize=12,
            fontweight="bold",
            ha="center",
            va="top",
        )

        # Current delta display
        self.ax_delta.text(
            0.5,
            0.82,
            "Current Gap",
            color="#888888",
            fontsize=10,
            ha="center",
            va="center",
        )

        self.delta_text = self.ax_delta.text(
            0.5,
            0.70,
            "+0.000s",
            color="white",
            fontsize=24,
            fontweight="bold",
            ha="center",
            va="center",
        )

        # Gap visualization bar
        self.ax_delta.add_patch(
            FancyBboxPatch(
                (0.1, 0.50),
                0.8,
                0.08,
                boxstyle="round,pad=0.01",
                facecolor="#333333",
                edgecolor="#666666",
                transform=self.ax_delta.transAxes,
            )
        )

        # Center line
        self.ax_delta.axvline(x=0.5, ymin=0.50, ymax=0.58, color="white", linewidth=2)

        # Delta bar (will be updated)
        self.delta_bar = self.ax_delta.add_patch(
            FancyBboxPatch(
                (0.5, 0.51),
                0.0,
                0.06,
                boxstyle="round,pad=0.005",
                facecolor=self.color1,
                transform=self.ax_delta.transAxes,
            )
        )

        # Driver labels
        self.ax_delta.text(
            0.15,
            0.45,
            self.comparison.driver1,
            color=self.color1,
            fontsize=10,
            fontweight="bold",
            ha="center",
        )
        self.ax_delta.text(
            0.85,
            0.45,
            self.comparison.driver2,
            color=self.color2,
            fontsize=10,
            fontweight="bold",
            ha="center",
        )

        # Mini-sector breakdown title
        self.ax_delta.text(
            0.5,
            0.35,
            "━━ SECTOR TIMES ━━",
            color="#888888",
            fontsize=9,
            ha="center",
            va="center",
        )

        # Mini-sector indicators (simplified - show a few key sectors)
        self.sector_texts = []
        num_display_sectors = 5
        for i in range(num_display_sectors):
            y_pos = 0.28 - (i * 0.055)
            txt = self.ax_delta.text(
                0.5,
                y_pos,
                f"S{i+1}: --",
                color="#888888",
                fontsize=9,
                ha="center",
                va="center",
            )
            self.sector_texts.append(txt)

    def _setup_telemetry_display(self):
        """Setup the speed/throttle comparison trace."""
        self.ax_telemetry.set_facecolor("#1a1a2e")

        # Distance axis
        dist_km = self.common_distances / 1000

        # Plot speed traces
        self.ax_telemetry.plot(
            dist_km,
            self.tel1.speed,
            color=self.color1,
            linewidth=2,
            alpha=0.8,
            label=self.comparison.driver1,
        )
        self.ax_telemetry.plot(
            dist_km,
            self.tel2.speed,
            color=self.color2,
            linewidth=2,
            alpha=0.8,
            label=self.comparison.driver2,
        )

        # Current position indicator (will be updated)
        self.pos_line = self.ax_telemetry.axvline(
            x=0, color="white", linewidth=2, linestyle="--", alpha=0.7
        )

        # Styling
        self.ax_telemetry.set_xlabel("Distance (km)", color="white", fontsize=10)
        self.ax_telemetry.set_ylabel("Speed (km/h)", color="white", fontsize=10)
        self.ax_telemetry.tick_params(colors="white")
        self.ax_telemetry.set_xlim(0, dist_km.max())
        self.ax_telemetry.set_ylim(
            0, max(self.tel1.speed.max(), self.tel2.speed.max()) * 1.05
        )

        legend = self.ax_telemetry.legend(
            loc="upper right", facecolor="#252540", edgecolor="white", fontsize=9
        )
        plt.setp(legend.get_texts(), color="white")

        for spine in self.ax_telemetry.spines.values():
            spine.set_color("#666666")

        self.ax_telemetry.grid(True, alpha=0.2, color="#666666")

    def _setup_speed_display(self):
        """Setup the current speed comparison display."""
        self.ax_speed.set_xlim(0, 1)
        self.ax_speed.set_ylim(0, 1)

        # Title
        self.ax_speed.text(
            0.5, 0.95, "SPEED", color="#888888", fontsize=10, ha="center", va="top"
        )

        # Driver 1 speed
        self.ax_speed.add_patch(
            Circle(
                (0.25, 0.65),
                0.15,
                facecolor=self.color1,
                edgecolor="white",
                linewidth=2,
                alpha=0.3,
                transform=self.ax_speed.transAxes,
            )
        )
        self.speed1_text = self.ax_speed.text(
            0.25,
            0.65,
            "0",
            color="white",
            fontsize=18,
            fontweight="bold",
            ha="center",
            va="center",
        )
        self.ax_speed.text(
            0.25,
            0.45,
            self.comparison.driver1,
            color=self.color1,
            fontsize=9,
            fontweight="bold",
            ha="center",
        )

        # Driver 2 speed
        self.ax_speed.add_patch(
            Circle(
                (0.75, 0.65),
                0.15,
                facecolor=self.color2,
                edgecolor="white",
                linewidth=2,
                alpha=0.3,
                transform=self.ax_speed.transAxes,
            )
        )
        self.speed2_text = self.ax_speed.text(
            0.75,
            0.65,
            "0",
            color="white",
            fontsize=18,
            fontweight="bold",
            ha="center",
            va="center",
        )
        self.ax_speed.text(
            0.75,
            0.45,
            self.comparison.driver2,
            color=self.color2,
            fontsize=9,
            fontweight="bold",
            ha="center",
        )

        # Speed difference
        self.ax_speed.text(
            0.5, 0.25, "Δ Speed", color="#888888", fontsize=9, ha="center"
        )
        self.speed_diff_text = self.ax_speed.text(
            0.5,
            0.12,
            "+0 km/h",
            color="white",
            fontsize=12,
            fontweight="bold",
            ha="center",
        )

    def _setup_progress_bar(self):
        """Setup lap progress bar."""
        self.ax_progress.set_xlim(0, 100)
        self.ax_progress.set_ylim(0, 1)
        self.ax_progress.axis("off")

        # Background
        self.ax_progress.barh([0.5], [100], height=0.4, color="#333333", alpha=0.5)

        # Progress bar
        self.progress_bar = self.ax_progress.barh(
            [0.5], [0], height=0.4, color="#00AAFF", alpha=0.8
        )[0]

        # Distance markers
        for pct in [0, 25, 50, 75, 100]:
            self.ax_progress.axvline(x=pct, color="#666666", linewidth=0.5, alpha=0.5)
            self.ax_progress.text(
                pct, 0.1, f"{pct}%", color="#888888", fontsize=8, ha="center"
            )

    def _create_dynamic_elements(self):
        """Create car icons and trails."""
        # Driver 1 car
        self.car1_patch = create_car_icon(
            self.ax_track,
            self.x1[0],
            self.y1[0],
            self.angles1[0],
            size=1.0,
            color=self.color1,
        )
        self.ax_track.add_patch(self.car1_patch)

        # Driver 2 car
        self.car2_patch = create_car_icon(
            self.ax_track,
            self.x2[0],
            self.y2[0],
            self.angles2[0],
            size=1.0,
            color=self.color2,
        )
        self.ax_track.add_patch(self.car2_patch)

        # Trails
        self.trail_length = 60
        (self.trail1,) = self.ax_track.plot(
            [], [], "-", color=self.color1, linewidth=4, alpha=0.4, zorder=9
        )
        (self.trail2,) = self.ax_track.plot(
            [], [], "-", color=self.color2, linewidth=4, alpha=0.4, zorder=9
        )

        # Driver labels above cars
        self.label1 = self.ax_track.text(
            self.x1[0],
            self.y1[0],
            self.comparison.driver1,
            color="white",
            fontsize=8,
            fontweight="bold",
            ha="center",
            va="bottom",
            zorder=20,
            bbox=dict(boxstyle="round,pad=0.2", facecolor=self.color1, alpha=0.8),
        )
        self.label2 = self.ax_track.text(
            self.x2[0],
            self.y2[0],
            self.comparison.driver2,
            color="white",
            fontsize=8,
            fontweight="bold",
            ha="center",
            va="bottom",
            zorder=20,
            bbox=dict(boxstyle="round,pad=0.2", facecolor=self.color2, alpha=0.8),
        )

    def _setup_controls(self):
        """Setup playback controls."""
        ax_play = self.fig.add_axes([0.35, 0.01, 0.08, 0.03])
        ax_pause = self.fig.add_axes([0.44, 0.01, 0.08, 0.03])
        ax_reset = self.fig.add_axes([0.53, 0.01, 0.08, 0.03])
        ax_speed = self.fig.add_axes([0.65, 0.015, 0.15, 0.02])

        self.btn_play = Button(ax_play, "▶ Play", color="#333333", hovercolor="#00FF00")
        self.btn_pause = Button(
            ax_pause, "⏸ Pause", color="#333333", hovercolor="#888888"
        )
        self.btn_reset = Button(
            ax_reset, "⏹ Reset", color="#333333", hovercolor="#FF4444"
        )

        self.slider_speed = Slider(
            ax_speed,
            "Speed",
            0.25,
            4.0,
            valinit=self.playback_speed,
            valstep=0.25,
            color="#00AAFF",
        )

        self.btn_play.on_clicked(self._on_play)
        self.btn_pause.on_clicked(self._on_pause)
        self.btn_reset.on_clicked(self._on_reset)
        self.slider_speed.on_changed(self._on_speed_change)

        self.fig.canvas.mpl_connect("key_press_event", self._on_key_press)

        self.fig.text(
            0.02,
            0.01,
            "Controls: Space=Play/Pause | R=Reset | ←→=Step | +/-=Speed",
            color="#888888",
            fontsize=9,
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
        self.current_frame = 0
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
            self.current_frame = min(self.current_frame + 10, self.total_frames - 1)
            self._update_frame(self.current_frame)
        elif event.key == "left":
            self.current_frame = max(self.current_frame - 10, 0)
            self._update_frame(self.current_frame)
        elif event.key in ["+", "="]:
            self.playback_speed = min(self.playback_speed + 0.25, 4.0)
            self.slider_speed.set_val(self.playback_speed)
        elif event.key == "-":
            self.playback_speed = max(self.playback_speed - 0.25, 0.25)
            self.slider_speed.set_val(self.playback_speed)

    def _update_frame(self, frame_idx: int):
        """Update all dynamic elements for the given frame."""
        frame_idx = int(frame_idx) % self.total_frames

        # Get positions
        x1, y1 = self.x1[frame_idx], self.y1[frame_idx]
        x2, y2 = self.x2[frame_idx], self.y2[frame_idx]

        # Update car 1
        self.car1_patch.remove()
        self.car1_patch = create_car_icon(
            self.ax_track, x1, y1, self.angles1[frame_idx], size=1.0, color=self.color1
        )
        self.ax_track.add_patch(self.car1_patch)

        # Update car 2
        self.car2_patch.remove()
        self.car2_patch = create_car_icon(
            self.ax_track, x2, y2, self.angles2[frame_idx], size=1.0, color=self.color2
        )
        self.ax_track.add_patch(self.car2_patch)

        # Update trails
        trail_start = max(0, frame_idx - self.trail_length)
        self.trail1.set_data(
            self.x1[trail_start : frame_idx + 1], self.y1[trail_start : frame_idx + 1]
        )
        self.trail2.set_data(
            self.x2[trail_start : frame_idx + 1], self.y2[trail_start : frame_idx + 1]
        )

        # Update driver labels (offset above car)
        label_offset = (self.y1.max() - self.y1.min()) * 0.04
        self.label1.set_position((x1, y1 + label_offset))
        self.label2.set_position((x2, y2 + label_offset))

        # Current times and delta
        time1 = self.time1[frame_idx]
        time2 = self.time2[frame_idx]
        delta = time2 - time1  # Positive = driver1 ahead

        # Update delta display
        if delta > 0:
            delta_str = f"+{delta:.3f}s"
            self.delta_text.set_color(self.color1)
            delta_width = min(delta * 0.1, 0.35)  # Scale for visibility
            self.delta_bar.set_x(0.5 - delta_width)
            self.delta_bar.set_width(delta_width)
            self.delta_bar.set_facecolor(self.color1)
        else:
            delta_str = f"{delta:.3f}s"
            self.delta_text.set_color(self.color2)
            delta_width = min(abs(delta) * 0.1, 0.35)
            self.delta_bar.set_x(0.5)
            self.delta_bar.set_width(delta_width)
            self.delta_bar.set_facecolor(self.color2)

        self.delta_text.set_text(delta_str)

        # Update speed displays
        speed1 = self.tel1.speed[frame_idx]
        speed2 = self.tel2.speed[frame_idx]
        speed_diff = speed1 - speed2

        self.speed1_text.set_text(f"{speed1:.0f}")
        self.speed2_text.set_text(f"{speed2:.0f}")

        if speed_diff > 0:
            self.speed_diff_text.set_text(f"+{speed_diff:.0f} km/h")
            self.speed_diff_text.set_color(self.color1)
        else:
            self.speed_diff_text.set_text(f"{speed_diff:.0f} km/h")
            self.speed_diff_text.set_color(self.color2)

        # Update position line on telemetry
        dist_km = self.common_distances[frame_idx] / 1000
        self.pos_line.set_xdata([dist_km, dist_km])

        # Update progress bar
        progress = (frame_idx / self.total_frames) * 100
        self.progress_bar.set_width(progress)

        # Update sector info (show relevant sectors)
        current_dist = self.common_distances[frame_idx]
        for i, sector in enumerate(self.comparison.mini_sectors[:5]):
            if (
                current_dist >= sector["start_distance"]
                and current_dist < sector["end_distance"]
            ):
                delta_ms = sector["delta"] * 1000
                sign = "+" if delta_ms > 0 else ""
                color = self.color1 if delta_ms > 0 else self.color2
                self.sector_texts[i].set_text(f"S{i+1}: {sign}{delta_ms:.0f}ms")
                self.sector_texts[i].set_color(color)
                self.sector_texts[i].set_fontweight("bold")
            elif current_dist > sector["end_distance"]:
                delta_ms = sector["delta"] * 1000
                sign = "+" if delta_ms > 0 else ""
                color = self.color1 if delta_ms > 0 else self.color2
                self.sector_texts[i].set_text(f"S{i+1}: {sign}{delta_ms:.0f}ms")
                self.sector_texts[i].set_color(color)
                self.sector_texts[i].set_fontweight("normal")
            else:
                self.sector_texts[i].set_text(f"S{i+1}: --")
                self.sector_texts[i].set_color("#888888")
                self.sector_texts[i].set_fontweight("normal")

        return [
            self.car1_patch,
            self.car2_patch,
            self.trail1,
            self.trail2,
            self.delta_text,
            self.speed1_text,
            self.speed2_text,
        ]

    def _animate(self, frame):
        """Animation frame callback."""
        if self.is_playing:
            frames_per_interval = int(
                self.playback_speed
                * (self.total_frames / (self.lap_duration * self.fps))
            )
            frames_per_interval = max(1, frames_per_interval)

            self.current_frame += frames_per_interval
            if self.current_frame >= self.total_frames:
                self.current_frame = 0

        return self._update_frame(self.current_frame)

    def _start_animation(self):
        """Start the animation."""
        interval = 1000 / self.fps
        self.animation = FuncAnimation(
            self.fig,
            self._animate,
            interval=interval,
            blit=False,
            cache_frame_data=False,
        )

    def show(self):
        """Display the comparison replay."""
        self._start_animation()
        plt.show()

    def close(self):
        """Close the replay window."""
        if self.animation:
            self.animation.event_source.stop()
        plt.close(self.fig)


def create_comparison_summary_plot(
    telemetry1: TelemetryData,
    telemetry2: TelemetryData,
    comparison: LapComparison,
    title: str = "Lap Comparison",
    rotation: float = 0.0,
) -> plt.Figure:
    """
    Create a static summary plot of the lap comparison.

    Shows:
    - Track colored by who's faster
    - Speed comparison overlay
    - Delta time over distance
    - Mini-sector breakdown
    """
    fig = plt.figure(figsize=(18, 12), facecolor="#1a1a2e")
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.2, wspace=0.2)

    # Interpolate to common grid
    max_dist = min(telemetry1.distance.max(), telemetry2.distance.max())
    min_dist = max(telemetry1.distance.min(), telemetry2.distance.min())
    num_points = max(len(telemetry1.distance), len(telemetry2.distance))
    common_distances = np.linspace(min_dist, max_dist, num_points)

    tel1 = interpolate_telemetry_to_distance(telemetry1, common_distances)
    tel2 = interpolate_telemetry_to_distance(telemetry2, common_distances)

    # Rotate coordinates
    def rotate_coords(x, y, angle):
        if angle == 0:
            return x.copy(), y.copy()
        angle_rad = np.radians(angle)
        cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
        cx, cy = x.mean(), y.mean()
        x_rot = (x - cx) * cos_a - (y - cy) * sin_a + cx
        y_rot = (x - cx) * sin_a + (y - cy) * cos_a + cy
        return x_rot, y_rot

    x, y = rotate_coords(tel1.x, tel1.y, rotation)

    # Build segment colors
    segment_colors = []
    for seg in comparison.segments:
        if seg.faster_driver == 0:
            color = comparison.driver1_color
        elif seg.faster_driver == 1:
            color = comparison.driver2_color
        else:
            color = "#888888"
        for _ in range(seg.end_idx - seg.start_idx):
            segment_colors.append(color)
    while len(segment_colors) < num_points:
        segment_colors.append("#888888")

    # 1. Track map with comparison colors
    ax_track = fig.add_subplot(gs[0, 0])
    ax_track.set_facecolor("#1a1a2e")

    points = np.array([x, y]).T.reshape(-1, 1, 2)
    segments = np.concatenate([points[:-1], points[1:]], axis=1)
    colors = [segment_colors[i] for i in range(len(segments))]

    ax_track.plot(x, y, color="#666666", linewidth=20, alpha=0.3, zorder=1)
    lc = LineCollection(segments, colors=colors, linewidth=12, alpha=0.85, zorder=2)
    ax_track.add_collection(lc)

    # Start/finish
    ax_track.scatter(
        x[0],
        y[0],
        s=200,
        c="white",
        marker="s",
        zorder=5,
        edgecolors="#00FF00",
        linewidths=2,
    )

    ax_track.set_aspect("equal")
    ax_track.axis("off")
    ax_track.set_title(
        f"Track Advantage: {comparison.driver1} vs {comparison.driver2}",
        color="white",
        fontsize=12,
        fontweight="bold",
    )

    # Legend
    legend_elements = [
        mpatches.Patch(
            facecolor=comparison.driver1_color, label=f"{comparison.driver1} faster"
        ),
        mpatches.Patch(
            facecolor=comparison.driver2_color, label=f"{comparison.driver2} faster"
        ),
    ]
    legend = ax_track.legend(
        handles=legend_elements,
        loc="upper left",
        facecolor="#252540",
        edgecolor="white",
        fontsize=9,
    )
    plt.setp(legend.get_texts(), color="white")

    # 2. Speed comparison
    ax_speed = fig.add_subplot(gs[0, 1])
    ax_speed.set_facecolor("#1a1a2e")

    dist_km = common_distances / 1000
    ax_speed.plot(
        dist_km,
        tel1.speed,
        color=comparison.driver1_color,
        linewidth=2,
        label=comparison.driver1,
        alpha=0.9,
    )
    ax_speed.plot(
        dist_km,
        tel2.speed,
        color=comparison.driver2_color,
        linewidth=2,
        label=comparison.driver2,
        alpha=0.9,
    )

    # Fill between to show advantage
    ax_speed.fill_between(
        dist_km,
        tel1.speed,
        tel2.speed,
        where=(tel1.speed > tel2.speed),
        facecolor=comparison.driver1_color,
        alpha=0.3,
    )
    ax_speed.fill_between(
        dist_km,
        tel1.speed,
        tel2.speed,
        where=(tel1.speed < tel2.speed),
        facecolor=comparison.driver2_color,
        alpha=0.3,
    )

    ax_speed.set_xlabel("Distance (km)", color="white", fontsize=10)
    ax_speed.set_ylabel("Speed (km/h)", color="white", fontsize=10)
    ax_speed.tick_params(colors="white")
    ax_speed.set_title(
        "Speed Comparison", color="white", fontsize=12, fontweight="bold"
    )
    ax_speed.legend(facecolor="#252540", edgecolor="white", labelcolor="white")
    ax_speed.grid(True, alpha=0.2, color="#666666")
    for spine in ax_speed.spines.values():
        spine.set_color("#666666")

    # 3. Delta time over distance
    ax_delta = fig.add_subplot(gs[1, 0])
    ax_delta.set_facecolor("#1a1a2e")

    time1 = tel1.time - tel1.time[0]
    time2 = tel2.time - tel2.time[0]
    delta = time2 - time1  # Positive = driver1 ahead

    ax_delta.fill_between(
        dist_km,
        delta,
        0,
        where=(delta > 0),
        facecolor=comparison.driver1_color,
        alpha=0.5,
        label=f"{comparison.driver1} ahead",
    )
    ax_delta.fill_between(
        dist_km,
        delta,
        0,
        where=(delta < 0),
        facecolor=comparison.driver2_color,
        alpha=0.5,
        label=f"{comparison.driver2} ahead",
    )
    ax_delta.plot(dist_km, delta, color="white", linewidth=1.5)
    ax_delta.axhline(y=0, color="white", linewidth=1, linestyle="--", alpha=0.5)

    ax_delta.set_xlabel("Distance (km)", color="white", fontsize=10)
    ax_delta.set_ylabel("Delta (seconds)", color="white", fontsize=10)
    ax_delta.tick_params(colors="white")
    ax_delta.set_title(
        "Gap/Delta Over Lap", color="white", fontsize=12, fontweight="bold"
    )
    ax_delta.legend(facecolor="#252540", edgecolor="white", labelcolor="white")
    ax_delta.grid(True, alpha=0.2, color="#666666")
    for spine in ax_delta.spines.values():
        spine.set_color("#666666")

    # 4. Mini-sector bar chart
    ax_sectors = fig.add_subplot(gs[1, 1])
    ax_sectors.set_facecolor("#1a1a2e")

    sectors = comparison.mini_sectors
    sector_nums = [s["sector"] for s in sectors]
    sector_deltas = [s["delta"] * 1000 for s in sectors]  # Convert to ms
    colors = [
        comparison.driver1_color if d > 0 else comparison.driver2_color
        for d in sector_deltas
    ]

    bars = ax_sectors.bar(
        sector_nums, sector_deltas, color=colors, alpha=0.8, edgecolor="white"
    )
    ax_sectors.axhline(y=0, color="white", linewidth=1)

    ax_sectors.set_xlabel("Mini-Sector", color="white", fontsize=10)
    ax_sectors.set_ylabel("Delta (ms)", color="white", fontsize=10)
    ax_sectors.tick_params(colors="white")
    ax_sectors.set_title(
        "Mini-Sector Time Deltas", color="white", fontsize=12, fontweight="bold"
    )

    # Add total delta annotation
    total_ms = comparison.total_delta * 1000
    faster = comparison.driver2 if comparison.total_delta > 0 else comparison.driver1
    ax_sectors.text(
        0.98,
        0.98,
        f"Total: {faster} by {abs(total_ms):.0f}ms",
        color="white",
        fontsize=10,
        fontweight="bold",
        ha="right",
        va="top",
        transform=ax_sectors.transAxes,
        bbox=dict(boxstyle="round", facecolor="#252540", edgecolor="white"),
    )

    for spine in ax_sectors.spines.values():
        spine.set_color("#666666")

    # Main title
    min1 = int(comparison.driver1_time // 60)
    sec1 = comparison.driver1_time % 60
    min2 = int(comparison.driver2_time // 60)
    sec2 = comparison.driver2_time % 60

    fig.suptitle(
        f"{title}\n{comparison.driver1} ({min1}:{sec1:06.3f}) vs {comparison.driver2} ({min2}:{sec2:06.3f})",
        color="white",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )

    plt.tight_layout()
    return fig


def run_ghost_comparison(
    session,
    driver1: str,
    driver2: str,
    title: str = "Ghost Comparison",
    show_summary: bool = True,
    show_replay: bool = True,
):
    """
    Main function to run a ghost car comparison between two drivers.

    Args:
        session: FastF1 session object
        driver1: First driver code (e.g., 'VER')
        driver2: Second driver code (e.g., 'NOR')
        title: Window/plot title
        show_summary: Whether to show static summary plot first
        show_replay: Whether to show animated replay
    """
    print(f"Loading telemetry for {driver1}...")
    telemetry1 = get_lap_telemetry(session, driver1)

    print(f"Loading telemetry for {driver2}...")
    telemetry2 = get_lap_telemetry(session, driver2)

    if telemetry1 is None or telemetry2 is None:
        print("Error: Could not load telemetry for one or both drivers.")
        return None

    # Get driver info from session
    try:
        drv1_info = session.get_driver(driver1)
        drv2_info = session.get_driver(driver2)
        team1 = drv1_info.get("TeamName", None)
        team2 = drv2_info.get("TeamName", None)
    except:
        team1 = None
        team2 = None

    print("Analyzing lap comparison...")
    comparison = analyze_lap_comparison(
        telemetry1, telemetry2, driver1, driver2, team1, team2
    )

    # Print summary
    print(f"\n{'='*50}")
    print(f"LAP COMPARISON: {driver1} vs {driver2}")
    print(f"{'='*50}")

    min1 = int(comparison.driver1_time // 60)
    sec1 = comparison.driver1_time % 60
    min2 = int(comparison.driver2_time // 60)
    sec2 = comparison.driver2_time % 60

    print(f"{driver1}: {min1}:{sec1:06.3f}")
    print(f"{driver2}: {min2}:{sec2:06.3f}")

    delta = comparison.total_delta
    faster = driver2 if delta > 0 else driver1
    print(f"\n{faster} is faster by {abs(delta):.3f}s")

    # Count segments
    d1_faster = sum(1 for s in comparison.segments if s.faster_driver == 0)
    d2_faster = sum(1 for s in comparison.segments if s.faster_driver == 1)
    equal = sum(1 for s in comparison.segments if s.faster_driver == -1)

    print(f"\nSegment breakdown:")
    print(f"  {driver1} faster: {d1_faster} segments")
    print(f"  {driver2} faster: {d2_faster} segments")
    print(f"  Equal: {equal} segments")
    print(f"{'='*50}\n")

    # Get circuit rotation
    circuit_info = get_circuit_info(session)
    rotation = circuit_info.get("rotation", 0)

    # Show summary plot first
    if show_summary:
        print("Generating comparison summary...")
        fig = create_comparison_summary_plot(
            telemetry1, telemetry2, comparison, title=title, rotation=rotation
        )
        plt.show()

    # Show animated replay
    if show_replay:
        print("Starting ghost comparison replay...")
        replay = GhostComparisonReplay(
            telemetry1, telemetry2, comparison, title=title, rotation=rotation
        )
        replay.show()

    return comparison


# Standalone test
if __name__ == "__main__":
    from data_loader import load_session

    print("Loading test session (2024 Bahrain GP Qualifying)...")
    session = load_session(2024, 1, "Q")

    # Compare top 2 drivers
    run_ghost_comparison(
        session,
        driver1="VER",
        driver2="LEC",
        title="Bahrain GP 2024 Qualifying - VER vs LEC",
        show_summary=True,
        show_replay=True,
    )
