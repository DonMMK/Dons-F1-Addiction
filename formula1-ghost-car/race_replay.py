"""
Formula 1 Ghost Car - Race Replay Module

Full race ghost car comparison showing two drivers racing through all laps:
- Two F1 car icons racing through each lap
- Lap-by-lap gap evolution
- Position tracking
- Pit stop indicators
- Real-time gap visualization
- Cumulative time comparison
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
from dataclasses import dataclass
from scipy import interpolate
import colorsys

from data_loader import (
    TelemetryData,
    RaceData,
    RaceLapData,
    get_circuit_info,
    get_driver_race_laps,
    get_race_comparison_data,
)

# Import team colors from ghost_comparison
from ghost_comparison import (
    TEAM_COLORS,
    DRIVER_TEAMS_BY_YEAR,
    get_driver_team_for_year,
    get_dynamic_driver_info,
    differentiate_same_team_colors,
    create_car_icon,
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


def analyze_race_comparison(
    race1: RaceData,
    race2: RaceData,
    session=None,
    year: int = 2024,
) -> RaceComparison:
    """
    Analyze full race comparison between two drivers.
    
    Args:
        race1: RaceData for driver 1
        race2: RaceData for driver 2
        session: FastF1 session for color lookup
        year: Season year for team color lookup
    
    Returns:
        RaceComparison with lap-by-lap analysis
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
    )


class RaceReplayAnimation:
    """
    Full race ghost car replay animation.
    
    Shows two drivers racing through all laps of a race with:
    - Animated car icons on track
    - Current lap indicator
    - Running gap display
    - Position tracking
    - Pit stop indicators
    - Gap evolution chart
    
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
        
        # Find a reference lap with telemetry for track outline
        self._find_reference_telemetry()
        
        # Setup figure
        self._setup_figure()
        self._setup_controls()
        
        self.animation = None
    
    def _find_reference_telemetry(self):
        """Find a lap with telemetry to use for track outline."""
        self.reference_telemetry = None
        
        # Try to find any lap with telemetry
        for lap in self.race1.laps[:10]:  # Check first 10 laps
            if lap.telemetry is not None:
                self.reference_telemetry = lap.telemetry
                break
        
        if self.reference_telemetry is None:
            for lap in self.race2.laps[:10]:
                if lap.telemetry is not None:
                    self.reference_telemetry = lap.telemetry
                    break
        
        if self.reference_telemetry is None:
            print("Warning: No telemetry data found for track visualization")
    
    def _rotate_coords(self, x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
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
    
    def _setup_figure(self):
        """Setup the matplotlib figure and axes."""
        self.fig = plt.figure(figsize=(18, 10), facecolor=COLORS["background"])
        self.fig.canvas.manager.set_window_title(self.title)
        
        # Grid layout
        gs = gridspec.GridSpec(
            3, 4,
            figure=self.fig,
            height_ratios=[3, 1, 0.3],
            width_ratios=[2, 1, 1, 1],
            hspace=0.15,
            wspace=0.2,
        )
        
        # Main track view
        self.ax_track = self.fig.add_subplot(gs[0, 0:2])
        self.ax_track.set_facecolor(COLORS["background"])
        self.ax_track.set_aspect("equal")
        self.ax_track.axis("off")
        
        # Gap evolution chart
        self.ax_gap = self.fig.add_subplot(gs[0, 2:4])
        self.ax_gap.set_facecolor(COLORS["background_light"])
        self.ax_gap.set_title("Gap Evolution", color=COLORS["text"], fontsize=12)
        
        # Driver 1 info panel
        self.ax_driver1 = self.fig.add_subplot(gs[1, 0])
        self.ax_driver1.set_facecolor(COLORS["background_light"])
        self.ax_driver1.axis("off")
        
        # Driver 2 info panel
        self.ax_driver2 = self.fig.add_subplot(gs[1, 1])
        self.ax_driver2.set_facecolor(COLORS["background_light"])
        self.ax_driver2.axis("off")
        
        # Lap times comparison
        self.ax_laptimes = self.fig.add_subplot(gs[1, 2:4])
        self.ax_laptimes.set_facecolor(COLORS["background_light"])
        self.ax_laptimes.set_title("Lap Times", color=COLORS["text"], fontsize=10)
        
        # Controls area
        self.ax_controls = self.fig.add_subplot(gs[2, :])
        self.ax_controls.set_facecolor(COLORS["background"])
        self.ax_controls.axis("off")
        
        # Draw initial content
        self._draw_track()
        self._draw_gap_chart()
        self._draw_driver_panels()
        self._draw_lap_times_chart()
        self._create_dynamic_elements()
    
    def _draw_track(self):
        """Draw the track outline."""
        if self.reference_telemetry is None:
            self.ax_track.text(
                0.5, 0.5,
                "No track data available",
                transform=self.ax_track.transAxes,
                ha="center", va="center",
                color=COLORS["text"],
                fontsize=14,
            )
            return
        
        x, y = self._rotate_coords(
            self.reference_telemetry.x,
            self.reference_telemetry.y
        )
        
        # Draw track outline
        self.ax_track.plot(
            x, y,
            color=COLORS["track"],
            linewidth=15,
            solid_capstyle="round",
            zorder=1,
        )
        self.ax_track.plot(
            x, y,
            color=COLORS["track_edge"],
            linewidth=18,
            solid_capstyle="round",
            zorder=0,
        )
        
        # Add start/finish line
        self.ax_track.scatter(
            [x[0]], [y[0]],
            c="white",
            s=100,
            marker="s",
            zorder=5,
            label="Start/Finish",
        )
        
        # Set limits with padding
        padding = (x.max() - x.min()) * 0.1
        self.ax_track.set_xlim(x.min() - padding, x.max() + padding)
        self.ax_track.set_ylim(y.min() - padding, y.max() + padding)
        
        # Title
        self.ax_track.set_title(
            f"LAP 1 / {self.total_laps}",
            color=COLORS["text"],
            fontsize=16,
            fontweight="bold",
            pad=10,
        )
    
    def _draw_gap_chart(self):
        """Draw the gap evolution chart."""
        laps = list(range(1, self.total_laps + 1))
        gaps = self.comparison.lap_gaps
        
        # Create color array based on who's ahead
        colors = []
        for gap in gaps:
            if gap > 0:
                colors.append(self.color1_hex)  # Driver 1 ahead
            else:
                colors.append(self.color2_hex)  # Driver 2 ahead
        
        # Fill areas
        self.ax_gap.fill_between(
            laps,
            [0] * len(gaps),
            gaps,
            where=[g > 0 for g in gaps],
            color=self.color1_hex,
            alpha=0.3,
            label=f"{self.comparison.driver1} ahead",
        )
        self.ax_gap.fill_between(
            laps,
            [0] * len(gaps),
            gaps,
            where=[g <= 0 for g in gaps],
            color=self.color2_hex,
            alpha=0.3,
            label=f"{self.comparison.driver2} ahead",
        )
        
        # Plot line
        self.ax_gap.plot(laps, gaps, color="white", linewidth=2, zorder=5)
        
        # Zero line
        self.ax_gap.axhline(y=0, color=COLORS["text_dim"], linewidth=1, linestyle="--")
        
        # Mark pit stops
        for pit_lap in self.comparison.pit_laps1:
            if pit_lap <= len(gaps):
                self.ax_gap.axvline(
                    x=pit_lap,
                    color=self.color1_hex,
                    linestyle=":",
                    alpha=0.7,
                )
        for pit_lap in self.comparison.pit_laps2:
            if pit_lap <= len(gaps):
                self.ax_gap.axvline(
                    x=pit_lap,
                    color=self.color2_hex,
                    linestyle=":",
                    alpha=0.7,
                )
        
        # Styling
        self.ax_gap.set_xlabel("Lap", color=COLORS["text"])
        self.ax_gap.set_ylabel("Gap (seconds)", color=COLORS["text"])
        self.ax_gap.tick_params(colors=COLORS["text"])
        self.ax_gap.set_xlim(1, self.total_laps)
        
        # Add progress marker (will be updated during animation)
        self.gap_marker = self.ax_gap.axvline(
            x=1, color="yellow", linewidth=2, zorder=10
        )
        
        self.ax_gap.legend(
            loc="upper right",
            facecolor=COLORS["background_light"],
            edgecolor=COLORS["text_dim"],
            labelcolor=COLORS["text"],
        )
        
        # Set spine colors
        for spine in self.ax_gap.spines.values():
            spine.set_color(COLORS["text_dim"])
    
    def _draw_driver_panels(self):
        """Draw driver info panels."""
        # Driver 1
        self.ax_driver1.add_patch(Rectangle(
            (0, 0), 1, 1,
            facecolor=self.color1_hex,
            alpha=0.3,
            transform=self.ax_driver1.transAxes,
        ))
        
        self.driver1_name = self.ax_driver1.text(
            0.5, 0.8,
            self.comparison.driver1,
            transform=self.ax_driver1.transAxes,
            ha="center", va="center",
            color=COLORS["text"],
            fontsize=20,
            fontweight="bold",
        )
        
        self.driver1_team = self.ax_driver1.text(
            0.5, 0.55,
            self.comparison.team1,
            transform=self.ax_driver1.transAxes,
            ha="center", va="center",
            color=COLORS["text_dim"],
            fontsize=10,
        )
        
        self.driver1_position = self.ax_driver1.text(
            0.5, 0.3,
            "P1",
            transform=self.ax_driver1.transAxes,
            ha="center", va="center",
            color=COLORS["text_highlight"],
            fontsize=24,
            fontweight="bold",
        )
        
        self.driver1_laptime = self.ax_driver1.text(
            0.5, 0.1,
            "---",
            transform=self.ax_driver1.transAxes,
            ha="center", va="center",
            color=COLORS["text"],
            fontsize=12,
        )
        
        # Driver 2
        self.ax_driver2.add_patch(Rectangle(
            (0, 0), 1, 1,
            facecolor=self.color2_hex,
            alpha=0.3,
            transform=self.ax_driver2.transAxes,
        ))
        
        self.driver2_name = self.ax_driver2.text(
            0.5, 0.8,
            self.comparison.driver2,
            transform=self.ax_driver2.transAxes,
            ha="center", va="center",
            color=COLORS["text"],
            fontsize=20,
            fontweight="bold",
        )
        
        self.driver2_team = self.ax_driver2.text(
            0.5, 0.55,
            self.comparison.team2,
            transform=self.ax_driver2.transAxes,
            ha="center", va="center",
            color=COLORS["text_dim"],
            fontsize=10,
        )
        
        self.driver2_position = self.ax_driver2.text(
            0.5, 0.3,
            "P2",
            transform=self.ax_driver2.transAxes,
            ha="center", va="center",
            color=COLORS["text_highlight"],
            fontsize=24,
            fontweight="bold",
        )
        
        self.driver2_laptime = self.ax_driver2.text(
            0.5, 0.1,
            "---",
            transform=self.ax_driver2.transAxes,
            ha="center", va="center",
            color=COLORS["text"],
            fontsize=12,
        )
    
    def _draw_lap_times_chart(self):
        """Draw lap times comparison chart."""
        # This will show recent lap times
        self.ax_laptimes.set_xlim(0, 10)
        self.ax_laptimes.set_ylim(0, 1)
        self.ax_laptimes.axis("off")
        
        self.laptimes_text = self.ax_laptimes.text(
            0.5, 0.5,
            "Lap times will appear here",
            transform=self.ax_laptimes.transAxes,
            ha="center", va="center",
            color=COLORS["text_dim"],
            fontsize=10,
        )
    
    def _create_dynamic_elements(self):
        """Create elements that will be updated during animation."""
        if self.reference_telemetry is None:
            self.car1 = None
            self.car2 = None
            return
        
        x, y = self._rotate_coords(
            self.reference_telemetry.x,
            self.reference_telemetry.y
        )
        angles = self._calculate_angles(x, y)
        
        # Store track data for animation
        self.track_x = x
        self.track_y = y
        self.track_angles = angles
        
        # Create car icons at start position
        self.car1 = create_car_icon(
            self.ax_track,
            x[0], y[0],
            angle=angles[0],
            size=1.2,
            color=self.color1_hex,
        )
        self.ax_track.add_patch(self.car1)
        
        self.car2 = create_car_icon(
            self.ax_track,
            x[0], y[0],
            angle=angles[0],
            size=1.2,
            color=self.color2_hex,
        )
        self.ax_track.add_patch(self.car2)
        
        # Driver labels
        self.label1 = self.ax_track.text(
            x[0], y[0] + 500,
            self.comparison.driver1,
            ha="center", va="bottom",
            color=self.color1_hex,
            fontsize=10,
            fontweight="bold",
            zorder=20,
        )
        
        self.label2 = self.ax_track.text(
            x[0], y[0] + 500,
            self.comparison.driver2,
            ha="center", va="bottom",
            color=self.color2_hex,
            fontsize=10,
            fontweight="bold",
            zorder=20,
        )
        
        # Gap display
        self.gap_text = self.ax_track.text(
            0.5, 0.95,
            "GAP: 0.000s",
            transform=self.ax_track.transAxes,
            ha="center", va="top",
            color=COLORS["text"],
            fontsize=16,
            fontweight="bold",
            bbox=dict(
                boxstyle="round,pad=0.3",
                facecolor=COLORS["background_light"],
                edgecolor=COLORS["text_dim"],
            ),
            zorder=25,
        )
        
        # Pit indicator
        self.pit_text = self.ax_track.text(
            0.5, 0.05,
            "",
            transform=self.ax_track.transAxes,
            ha="center", va="bottom",
            color=COLORS["pit_indicator"],
            fontsize=14,
            fontweight="bold",
            zorder=25,
        )
    
    def _setup_controls(self):
        """Setup playback controls."""
        # Buttons
        self.btn_play_ax = self.fig.add_axes([0.3, 0.02, 0.08, 0.04])
        self.btn_play = Button(
            self.btn_play_ax, "▶ Play",
            color=COLORS["gauge_bg"],
            hovercolor=COLORS["background_light"],
        )
        self.btn_play.label.set_color(COLORS["text"])
        self.btn_play.on_clicked(self._on_play)
        
        self.btn_pause_ax = self.fig.add_axes([0.4, 0.02, 0.08, 0.04])
        self.btn_pause = Button(
            self.btn_pause_ax, "⏸ Pause",
            color=COLORS["gauge_bg"],
            hovercolor=COLORS["background_light"],
        )
        self.btn_pause.label.set_color(COLORS["text"])
        self.btn_pause.on_clicked(self._on_pause)
        
        self.btn_reset_ax = self.fig.add_axes([0.5, 0.02, 0.08, 0.04])
        self.btn_reset = Button(
            self.btn_reset_ax, "⟲ Reset",
            color=COLORS["gauge_bg"],
            hovercolor=COLORS["background_light"],
        )
        self.btn_reset.label.set_color(COLORS["text"])
        self.btn_reset.on_clicked(self._on_reset)
        
        # Previous/Next lap buttons
        self.btn_prev_ax = self.fig.add_axes([0.15, 0.02, 0.08, 0.04])
        self.btn_prev = Button(
            self.btn_prev_ax, "◀ Prev",
            color=COLORS["gauge_bg"],
            hovercolor=COLORS["background_light"],
        )
        self.btn_prev.label.set_color(COLORS["text"])
        self.btn_prev.on_clicked(self._on_prev_lap)
        
        self.btn_next_ax = self.fig.add_axes([0.65, 0.02, 0.08, 0.04])
        self.btn_next = Button(
            self.btn_next_ax, "Next ▶",
            color=COLORS["gauge_bg"],
            hovercolor=COLORS["background_light"],
        )
        self.btn_next.label.set_color(COLORS["text"])
        self.btn_next.on_clicked(self._on_next_lap)
        
        # Speed slider
        self.slider_ax = self.fig.add_axes([0.78, 0.02, 0.15, 0.04])
        self.speed_slider = Slider(
            self.slider_ax,
            "Speed",
            0.25, 4.0,
            valinit=self.playback_speed,
            valstep=0.25,
            color=COLORS["text_highlight"],
        )
        self.speed_slider.label.set_color(COLORS["text"])
        self.speed_slider.valtext.set_color(COLORS["text"])
        self.speed_slider.on_changed(self._on_speed_change)
        
        # Keyboard controls
        self.fig.canvas.mpl_connect("key_press_event", self._on_key_press)
    
    def _on_play(self, event=None):
        """Start playback."""
        self.is_playing = True
        if self.animation is None:
            self._start_animation()
    
    def _on_pause(self, event=None):
        """Pause playback."""
        self.is_playing = False
    
    def _on_reset(self, event=None):
        """Reset to beginning."""
        self.current_lap = 0
        self.current_frame = 0
        self._update_display()
    
    def _on_prev_lap(self, event=None):
        """Go to previous lap."""
        if self.current_lap > 0:
            self.current_lap -= 1
            self.current_frame = 0
            self._update_display()
    
    def _on_next_lap(self, event=None):
        """Go to next lap."""
        if self.current_lap < self.total_laps - 1:
            self.current_lap += 1
            self.current_frame = 0
            self._update_display()
    
    def _on_speed_change(self, val):
        """Handle speed slider change."""
        self.playback_speed = val
    
    def _on_key_press(self, event):
        """Handle keyboard input."""
        if event.key == " ":
            if self.is_playing:
                self._on_pause()
            else:
                self._on_play()
        elif event.key == "r":
            self._on_reset()
        elif event.key == "left":
            self._on_prev_lap()
        elif event.key == "right":
            self._on_next_lap()
        elif event.key == "+":
            new_speed = min(4.0, self.playback_speed + 0.25)
            self.speed_slider.set_val(new_speed)
        elif event.key == "-":
            new_speed = max(0.25, self.playback_speed - 0.25)
            self.speed_slider.set_val(new_speed)
    
    def _update_display(self):
        """Update all display elements for current lap."""
        lap_idx = self.current_lap
        
        # Update track title
        self.ax_track.set_title(
            f"LAP {lap_idx + 1} / {self.total_laps}",
            color=COLORS["text"],
            fontsize=16,
            fontweight="bold",
            pad=10,
        )
        
        # Update gap marker on chart
        self.gap_marker.set_xdata([lap_idx + 1, lap_idx + 1])
        
        # Get current lap data
        if lap_idx < len(self.race1.laps):
            lap1 = self.race1.laps[lap_idx]
            self.driver1_position.set_text(f"P{lap1.position}")
            self.driver1_laptime.set_text(format_time(lap1.lap_time_seconds))
        
        if lap_idx < len(self.race2.laps):
            lap2 = self.race2.laps[lap_idx]
            self.driver2_position.set_text(f"P{lap2.position}")
            self.driver2_laptime.set_text(format_time(lap2.lap_time_seconds))
        
        # Update gap display
        if lap_idx < len(self.comparison.lap_gaps):
            gap = self.comparison.lap_gaps[lap_idx]
            leader = self.comparison.driver1 if gap > 0 else self.comparison.driver2
            self.gap_text.set_text(f"GAP: {format_gap(abs(gap))}\n{leader} leads")
        
        # Check for pit stops
        pit_text = ""
        if (lap_idx + 1) in self.comparison.pit_laps1:
            pit_text += f"🔧 {self.comparison.driver1} PIT  "
        if (lap_idx + 1) in self.comparison.pit_laps2:
            pit_text += f"🔧 {self.comparison.driver2} PIT"
        self.pit_text.set_text(pit_text)
        
        # Update lap times display
        self._update_laptimes_display(lap_idx)
        
        self.fig.canvas.draw_idle()
    
    def _update_laptimes_display(self, lap_idx: int):
        """Update the lap times comparison display."""
        # Show last 5 laps
        start_lap = max(0, lap_idx - 4)
        
        text_lines = []
        text_lines.append(f"{'Lap':>4} | {self.comparison.driver1:>8} | {self.comparison.driver2:>8} | {'Delta':>8}")
        text_lines.append("-" * 45)
        
        for i in range(start_lap, lap_idx + 1):
            if i < len(self.race1.laps) and i < len(self.race2.laps):
                t1 = self.race1.laps[i].lap_time_seconds
                t2 = self.race2.laps[i].lap_time_seconds
                delta = t1 - t2
                
                t1_str = f"{t1:7.3f}s"
                t2_str = f"{t2:7.3f}s"
                delta_str = f"{delta:+7.3f}s"
                
                # Mark current lap
                marker = "→" if i == lap_idx else " "
                text_lines.append(f"{marker}{i+1:>3} | {t1_str} | {t2_str} | {delta_str}")
        
        self.laptimes_text.set_text("\n".join(text_lines))
        self.laptimes_text.set_fontfamily("monospace")
    
    def _animate_lap(self, frame):
        """Animate a single frame within a lap."""
        if not self.is_playing:
            return []
        
        if self.reference_telemetry is None:
            return []
        
        lap_idx = self.current_lap
        
        # Get telemetry for current lap
        tel1 = self.race1.laps[lap_idx].telemetry if lap_idx < len(self.race1.laps) else None
        tel2 = self.race2.laps[lap_idx].telemetry if lap_idx < len(self.race2.laps) else None
        
        # If no telemetry, use reference track
        if tel1 is None:
            x1, y1 = self.track_x, self.track_y
        else:
            x1, y1 = self._rotate_coords(tel1.x, tel1.y)
        
        if tel2 is None:
            x2, y2 = self.track_x, self.track_y
        else:
            x2, y2 = self._rotate_coords(tel2.x, tel2.y)
        
        # Calculate positions based on frame and lap times
        num_frames = max(len(x1), len(x2))
        frame_skip = int(self.playback_speed * 2)
        
        self.current_frame += frame_skip
        
        # Calculate indices
        idx1 = min(self.current_frame, len(x1) - 1)
        idx2 = min(self.current_frame, len(x2) - 1)
        
        # Update car positions
        if self.car1 is not None:
            self.car1.remove()
            angles1 = self._calculate_angles(x1, y1)
            self.car1 = create_car_icon(
                self.ax_track,
                x1[idx1], y1[idx1],
                angle=angles1[idx1],
                size=1.2,
                color=self.color1_hex,
            )
            self.ax_track.add_patch(self.car1)
            self.label1.set_position((x1[idx1], y1[idx1] + 500))
        
        if self.car2 is not None:
            self.car2.remove()
            angles2 = self._calculate_angles(x2, y2)
            self.car2 = create_car_icon(
                self.ax_track,
                x2[idx2], y2[idx2],
                angle=angles2[idx2],
                size=1.2,
                color=self.color2_hex,
            )
            self.ax_track.add_patch(self.car2)
            self.label2.set_position((x2[idx2], y2[idx2] + 500))
        
        # Check if lap is complete
        if self.current_frame >= num_frames - 1:
            self.current_frame = 0
            self.current_lap += 1
            
            if self.current_lap >= self.total_laps:
                self.is_playing = False
                self.current_lap = self.total_laps - 1
                self._show_final_result()
            else:
                self._update_display()
        
        return [self.car1, self.car2] if self.car1 and self.car2 else []
    
    def _show_final_result(self):
        """Show final race result."""
        winner = self.comparison.winner
        gap = abs(self.comparison.final_gap)
        
        result_text = f"🏁 RACE COMPLETE 🏁\n\n"
        result_text += f"Winner: {winner}\n"
        result_text += f"Gap: {format_gap(gap)}"
        
        self.gap_text.set_text(result_text)
        self.fig.canvas.draw_idle()
    
    def _start_animation(self):
        """Start the animation."""
        self.animation = FuncAnimation(
            self.fig,
            self._animate_lap,
            interval=1000 // self.fps,
            blit=False,
            cache_frame_data=False,
        )
    
    def show(self):
        """Display the animation."""
        self._update_display()
        plt.tight_layout()
        plt.show()
    
    def close(self):
        """Close the figure."""
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
    
    # Get circuit info for rotation
    circuit_info = get_circuit_info(session)
    rotation = circuit_info.get("rotation", 0) if circuit_info else 0
    
    # Get year for team colors
    year = session.event.year if hasattr(session, "event") else 2024
    
    # Analyze comparison
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Analyzing race comparison...[/cyan]"),
        console=console,
    ) as progress:
        progress.add_task("analyzing", total=None)
        comparison = analyze_race_comparison(race1, race2, session, year)
    
    console.print(f"[green]✓ Analysis complete - {comparison.total_laps} laps compared[/green]")
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
