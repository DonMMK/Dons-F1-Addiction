"""
Formula 1 Driving Assistant - Lap Replay Animation Module

Enhanced animated lap replay with:
- Car icon moving through the track in real-time
- Live telemetry display (speed, throttle, brake, gear)
- Track conditions panel (weather, tire compound)
- Driver status info box (accelerating, braking, cornering)
- Corner approach with detailed info (name, type, speed class)
- Play/Pause/Stop controls with keyboard shortcuts
"""

import matplotlib
# Set interactive backend if not already set (for standalone testing)
if matplotlib.get_backend() == 'agg':
    try:
        matplotlib.use('Qt5Agg')
    except:
        try:
            matplotlib.use('TkAgg')
        except:
            pass

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Polygon, Circle, Wedge
from matplotlib.collections import PatchCollection
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button, Slider
import matplotlib.gridspec as gridspec
import matplotlib.path as mpath
import numpy as np
from typing import Optional, Tuple, List

from data_loader import (
    TelemetryData, DrivingZones, TrackConditions, CornerInfo,
    get_enhanced_corners, get_track_conditions
)


# Color scheme
COLORS = {
    'background': '#1a1a2e',
    'background_light': '#252540',
    'track': '#444444',
    'track_edge': '#666666',
    'car': '#FF0000',
    'car_trail': '#FF6600',
    'throttle': '#00FF00',
    'brake': '#FF0000',
    'text': '#FFFFFF',
    'text_dim': '#888888',
    'text_highlight': '#FFD700',
    'gauge_bg': '#333333',
    'speed_bar': '#00AAFF',
    'gear_bg': '#222222',
    # Status colors
    'status_accelerating': '#00FF00',
    'status_braking': '#FF4444',
    'status_coasting': '#FFD700',
    'status_full_throttle': '#00AAFF',
    'status_corner': '#FF00FF',
    # Corner type colors
    'corner_hairpin': '#FF0000',
    'corner_sweeper': '#00AAFF',
    'corner_chicane': '#FF00FF',
    'corner_90deg': '#FFD700',
    'corner_kink': '#00FF00',
    # Weather
    'weather_dry': '#FFD700',
    'weather_wet': '#00AAFF',
    'weather_hot': '#FF4444',
    'weather_cold': '#88CCFF',
}

# Tire compound colors
TIRE_COLORS = {
    'SOFT': '#FF0000',
    'MEDIUM': '#FFD700',
    'HARD': '#FFFFFF',
    'INTERMEDIATE': '#00FF00',
    'WET': '#0088FF',
}


def create_car_icon(ax, x, y, angle=0, size=1.0, color='#FF0000'):
    """
    Create an F1 car-shaped icon using matplotlib patches.
    
    Returns a list of patches that form the car shape.
    """
    # Scale factor
    s = size * 150
    
    # F1 car body shape (simplified top-down view)
    # Main body
    car_body = np.array([
        [0, -0.5],      # Rear center
        [-0.15, -0.45], # Rear left
        [-0.18, -0.3],  # Body left
        [-0.2, 0],      # Sidepod left
        [-0.18, 0.3],   # Front body left
        [-0.1, 0.45],   # Nose left
        [0, 0.55],      # Nose tip
        [0.1, 0.45],    # Nose right
        [0.18, 0.3],    # Front body right
        [0.2, 0],       # Sidepod right
        [0.18, -0.3],   # Body right
        [0.15, -0.45],  # Rear right
    ]) * s
    
    # Rotate
    angle_rad = np.radians(angle)
    cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
    rotation_matrix = np.array([[cos_a, -sin_a], [sin_a, cos_a]])
    car_body_rot = car_body @ rotation_matrix.T
    
    # Translate
    car_body_rot[:, 0] += x
    car_body_rot[:, 1] += y
    
    return Polygon(car_body_rot, closed=True, facecolor=color, 
                   edgecolor='white', linewidth=1.5, zorder=15)


class LapReplayAnimation:
    """
    Enhanced animated lap replay with telemetry visualization.
    
    Features:
    - F1 car icon instead of dot
    - Track conditions display (weather, tire)
    - Driver status info box (accelerating, braking, cornering)
    - Corner approach info with detailed classification
    
    Controls:
    - Space: Play/Pause
    - R: Reset to start
    - Left/Right arrows: Step frame by frame
    - +/-: Speed up/slow down
    """
    
    def __init__(
        self,
        telemetry: TelemetryData,
        zones: Optional[DrivingZones] = None,
        track_conditions: Optional[TrackConditions] = None,
        enhanced_corners: Optional[List[CornerInfo]] = None,
        title: str = "Lap Replay",
        rotation: float = 0.0,
        fps: int = 30,
        playback_speed: float = 1.0
    ):
        self.telemetry = telemetry
        self.zones = zones
        self.track_conditions = track_conditions
        self.enhanced_corners = enhanced_corners or []
        self.title = title
        self.rotation = rotation
        self.fps = fps
        self.playback_speed = playback_speed
        
        # Animation state
        self.current_frame = 0
        self.is_playing = False
        self.total_frames = len(telemetry.speed)
        self.prev_gear = 0
        
        # Calculate frame skip based on time data for real-time playback
        self.time_data = telemetry.time
        self.lap_duration = self.time_data[-1] - self.time_data[0]
        
        # Prepare rotated coordinates
        self.x, self.y = self._rotate_coords(telemetry.x, telemetry.y)
        
        # Calculate car angles along the track
        self.car_angles = self._calculate_car_angles()
        
        # Build corner lookup for quick access
        self._build_corner_lookup()
        
        # Setup the figure
        self._setup_figure()
        self._setup_controls()
        
        # Animation object
        self.animation = None
    
    def _rotate_coords(self, x: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Rotate coordinates by the circuit rotation angle."""
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
    
    def _calculate_car_angles(self) -> np.ndarray:
        """Calculate the car heading angle at each point."""
        angles = np.zeros(len(self.x))
        
        for i in range(len(self.x) - 1):
            dx = self.x[i + 1] - self.x[i]
            dy = self.y[i + 1] - self.y[i]
            angles[i] = np.degrees(np.arctan2(dy, dx)) - 90  # Adjust for car orientation
        
        angles[-1] = angles[-2]  # Copy last angle
        
        # Smooth angles
        window = 5
        angles_smooth = np.convolve(angles, np.ones(window)/window, mode='same')
        
        return angles_smooth
    
    def _build_corner_lookup(self):
        """Build a lookup structure for quick corner detection."""
        self.corner_ranges = []
        
        for corner in self.enhanced_corners:
            # Include approach zone (100 indices before entry)
            approach_start = max(0, corner.entry_idx - 100)
            self.corner_ranges.append({
                'approach_start': approach_start,
                'entry_idx': corner.entry_idx,
                'apex_idx': corner.apex_idx,
                'exit_idx': corner.exit_idx,
                'corner': corner
            })
    
    def _get_current_corner(self, frame_idx: int) -> Optional[Tuple[CornerInfo, str]]:
        """
        Get the corner info if we're approaching or in a corner.
        
        Returns:
            Tuple of (CornerInfo, phase) where phase is 'APPROACH', 'ENTRY', 'APEX', 'EXIT'
            or None if not near a corner
        """
        for cr in self.corner_ranges:
            if cr['approach_start'] <= frame_idx < cr['entry_idx']:
                return (cr['corner'], 'APPROACH')
            elif cr['entry_idx'] <= frame_idx < cr['apex_idx']:
                return (cr['corner'], 'ENTRY')
            elif cr['apex_idx'] <= frame_idx < cr['exit_idx']:
                return (cr['corner'], 'APEX')
            elif cr['exit_idx'] <= frame_idx < cr['exit_idx'] + 30:
                return (cr['corner'], 'EXIT')
        
        return None
    
    def _get_driver_status(self, frame_idx: int) -> dict:
        """
        Determine the driver's current status.
        
        Returns dict with:
            - status: str ('ACCELERATING', 'BRAKING', 'FULL_THROTTLE', 'COASTING', 'CORNER')
            - gear_change: str or None ('UP', 'DOWN', None)
            - drs: bool
            - corner_info: CornerInfo or None
            - corner_phase: str or None
        """
        throttle = self.telemetry.throttle[frame_idx]
        brake = self.telemetry.brake[frame_idx]
        gear = int(self.telemetry.gear[frame_idx])
        drs = self.telemetry.drs[frame_idx]
        
        # Normalize brake if needed
        if brake <= 1:
            brake = brake * 100
        
        # Check gear change
        gear_change = None
        if gear > self.prev_gear and self.prev_gear > 0:
            gear_change = 'UP'
        elif gear < self.prev_gear and gear > 0:
            gear_change = 'DOWN'
        
        # Check corner
        corner_result = self._get_current_corner(frame_idx)
        
        # Determine primary status
        if brake > 10:
            status = 'BRAKING'
        elif throttle >= 95:
            status = 'FULL_THROTTLE'
        elif throttle > 50:
            status = 'ACCELERATING'
        else:
            status = 'COASTING'
        
        # Override with corner if in corner
        if corner_result and corner_result[1] in ['ENTRY', 'APEX']:
            status = 'CORNER'
        
        return {
            'status': status,
            'gear_change': gear_change,
            'drs': drs > 0 if not np.isnan(drs) else False,
            'corner_info': corner_result[0] if corner_result else None,
            'corner_phase': corner_result[1] if corner_result else None
        }
    
    def _setup_figure(self):
        """Setup the matplotlib figure with track, telemetry, and status panels."""
        self.fig = plt.figure(figsize=(18, 11), facecolor=COLORS['background'])
        self.fig.canvas.manager.set_window_title(self.title)
        
        # Create grid: main track area + side panels
        gs = gridspec.GridSpec(4, 5, figure=self.fig, 
                               height_ratios=[0.15, 1, 0.25, 0.1],
                               width_ratios=[3, 0.8, 0.8, 0.8, 0.8],
                               hspace=0.15, wspace=0.15)
        
        # Track conditions bar (top)
        self.ax_conditions = self.fig.add_subplot(gs[0, :])
        self.ax_conditions.set_facecolor(COLORS['background_light'])
        self.ax_conditions.axis('off')
        
        # Main track view (spans left columns, main row)
        self.ax_track = self.fig.add_subplot(gs[1, :3])
        self.ax_track.set_facecolor(COLORS['background'])
        self.ax_track.set_aspect('equal')
        self.ax_track.axis('off')
        
        # Driver status / info box (right side, main row)
        self.ax_status = self.fig.add_subplot(gs[1, 3:])
        self.ax_status.set_facecolor(COLORS['background_light'])
        self.ax_status.axis('off')
        
        # Telemetry bars (bottom section)
        self.ax_inputs = self.fig.add_subplot(gs[2, :3])
        self.ax_inputs.set_facecolor(COLORS['background'])
        
        # Speed display (right of inputs)
        self.ax_speed = self.fig.add_subplot(gs[2, 3:])
        self.ax_speed.set_facecolor(COLORS['background_light'])
        self.ax_speed.axis('off')
        
        # Progress/time display (bottom row, will add controls here)
        self.ax_progress = self.fig.add_subplot(gs[3, :3])
        self.ax_progress.set_facecolor(COLORS['background'])
        
        # Draw static elements
        self._draw_track_conditions()
        self._draw_track()
        self._setup_status_display()
        self._setup_input_bars()
        self._setup_speed_display()
        self._setup_progress_bar()
        
        # Create dynamic elements (car icon, etc.)
        self._create_dynamic_elements()
    
    def _draw_track_conditions(self):
        """Draw the track conditions header bar."""
        self.ax_conditions.set_xlim(0, 1)
        self.ax_conditions.set_ylim(0, 1)
        
        if not self.track_conditions:
            self.ax_conditions.text(0.5, 0.5, "Track conditions not available",
                                   color=COLORS['text_dim'], fontsize=12, ha='center', va='center')
            return
        
        tc = self.track_conditions
        weather = tc.weather
        
        # Driver & Session info
        self.ax_conditions.text(0.02, 0.5, f"[DRV] {tc.driver}", color=COLORS['text'],
                               fontsize=14, fontweight='bold', ha='left', va='center')
        self.ax_conditions.text(0.12, 0.5, f"| {tc.team}", color=COLORS['text_dim'],
                               fontsize=11, ha='left', va='center')
        self.ax_conditions.text(0.28, 0.5, f"| {tc.session_type}", color=COLORS['text_dim'],
                               fontsize=11, ha='left', va='center')
        
        # Tire info with colored circle
        tire_color = TIRE_COLORS.get(tc.tire_compound.upper(), '#888888')
        tire_circle = Circle((0.42, 0.5), 0.03, facecolor=tire_color, 
                            edgecolor='white', linewidth=1.5, transform=self.ax_conditions.transAxes)
        self.ax_conditions.add_patch(tire_circle)
        self.ax_conditions.text(0.46, 0.5, f"{tc.tire_compound} (Lap {tc.tire_life})",
                               color=COLORS['text'], fontsize=11, ha='left', va='center')
        
        # Weather info
        weather_icon = "[WET]" if weather.rainfall else "[DRY]"
        condition = weather.get_condition_string()
        self.ax_conditions.text(0.62, 0.5, f"{weather_icon} {condition}",
                               color=COLORS['text'], fontsize=11, ha='left', va='center')
        
        # Temperatures
        self.ax_conditions.text(0.72, 0.5, f"| Air: {weather.air_temp:.0f}°C",
                               color=COLORS['text_dim'], fontsize=10, ha='left', va='center')
        self.ax_conditions.text(0.82, 0.5, f"Track: {weather.track_temp:.0f}°C",
                               color=COLORS['text_dim'], fontsize=10, ha='left', va='center')
        
        # Wind
        self.ax_conditions.text(0.93, 0.5, f"Wind: {weather.wind_speed:.0f} km/h",
                               color=COLORS['text_dim'], fontsize=10, ha='left', va='center')
    
    def _draw_track(self):
        """Draw the static track layout."""
        # Track outline
        self.ax_track.plot(self.x, self.y, color=COLORS['track_edge'], 
                          linewidth=18, alpha=0.4, zorder=1)
        self.ax_track.plot(self.x, self.y, color=COLORS['track'], 
                          linewidth=12, alpha=0.8, zorder=2)
        
        # Start/finish marker
        self.ax_track.scatter(self.x[0], self.y[0], s=250, c='white', 
                             marker='s', zorder=5, edgecolors='green', linewidths=3)
        self.ax_track.text(self.x[0], self.y[0], 'S/F', color='green', fontsize=8,
                          ha='center', va='center', fontweight='bold', zorder=6)
        
        # Corner markers
        for corner in self.enhanced_corners:
            # Rotate corner position
            angle_rad = np.radians(self.rotation)
            cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
            cx, cy = self.telemetry.x.mean(), self.telemetry.y.mean()
            
            x = corner.x - cx
            y = corner.y - cy
            x_rot = x * cos_a - y * sin_a + cx
            y_rot = x * sin_a + y * cos_a + cy
            
            # Color based on corner type
            type_colors = {
                'HAIRPIN': COLORS['corner_hairpin'],
                'SWEEPER': COLORS['corner_sweeper'],
                'CHICANE': COLORS['corner_chicane'],
                '90_DEGREE': COLORS['corner_90deg'],
                'KINK': COLORS['corner_kink'],
            }
            marker_color = type_colors.get(corner.corner_type, COLORS['text_dim'])
            
            self.ax_track.scatter(x_rot, y_rot, s=100, c=marker_color, 
                                 marker='o', zorder=4, edgecolors='white', linewidths=1)
            self.ax_track.text(x_rot, y_rot, str(corner.number), color='white',
                              fontsize=7, ha='center', va='center', fontweight='bold', zorder=5)
        
        # Title
        self.ax_track.set_title(self.title, color=COLORS['text'], 
                               fontsize=14, fontweight='bold', pad=10)
        
        # Set limits with padding
        padding = (self.x.max() - self.x.min()) * 0.1
        self.ax_track.set_xlim(self.x.min() - padding, self.x.max() + padding)
        self.ax_track.set_ylim(self.y.min() - padding, self.y.max() + padding)
    
    def _setup_status_display(self):
        """Setup the driver status information panel."""
        self.ax_status.set_xlim(0, 1)
        self.ax_status.set_ylim(0, 1)
        
        # Static title
        self.ax_status.text(0.5, 0.97, "DRIVER STATUS", color=COLORS['text'],
                           fontsize=12, fontweight='bold', ha='center', va='top')
        
        # Main status box background
        status_box = FancyBboxPatch((0.05, 0.72), 0.9, 0.2, 
                                    boxstyle="round,pad=0.02",
                                    facecolor=COLORS['gauge_bg'], 
                                    edgecolor=COLORS['text_dim'],
                                    linewidth=2,
                                    transform=self.ax_status.transAxes)
        self.ax_status.add_patch(status_box)
        
        # Dynamic status text (will be updated)
        self.status_main_text = self.ax_status.text(0.5, 0.82, "READY",
                                                    color=COLORS['status_accelerating'],
                                                    fontsize=18, fontweight='bold',
                                                    ha='center', va='center')
        
        # Gear change indicator
        self.gear_change_text = self.ax_status.text(0.5, 0.68, "",
                                                    color=COLORS['text_highlight'],
                                                    fontsize=11, ha='center', va='center')
        
        # Corner info section title
        self.ax_status.text(0.5, 0.58, "━━━ CORNER INFO ━━━", color=COLORS['text_dim'],
                           fontsize=9, ha='center', va='center')
        
        # Corner info box
        corner_box = FancyBboxPatch((0.05, 0.12), 0.9, 0.42,
                                    boxstyle="round,pad=0.02",
                                    facecolor=COLORS['background'],
                                    edgecolor=COLORS['text_dim'],
                                    linewidth=1,
                                    transform=self.ax_status.transAxes)
        self.ax_status.add_patch(corner_box)
        
        # Corner name
        self.corner_name_text = self.ax_status.text(0.5, 0.48, "---",
                                                    color=COLORS['text'],
                                                    fontsize=14, fontweight='bold',
                                                    ha='center', va='center')
        
        # Corner type and speed class
        self.corner_type_text = self.ax_status.text(0.5, 0.40, "",
                                                    color=COLORS['text_dim'],
                                                    fontsize=10, ha='center', va='center')
        
        # Corner direction
        self.corner_direction_text = self.ax_status.text(0.5, 0.33, "",
                                                         color=COLORS['text_dim'],
                                                         fontsize=10, ha='center', va='center')
        
        # Corner phase
        self.corner_phase_text = self.ax_status.text(0.5, 0.26, "",
                                                     color=COLORS['text_highlight'],
                                                     fontsize=11, fontweight='bold',
                                                     ha='center', va='center')
        
        # Corner speeds
        self.corner_speeds_text = self.ax_status.text(0.5, 0.17, "",
                                                      color=COLORS['text_dim'],
                                                      fontsize=9, ha='center', va='center')
        
        # DRS indicator
        self.drs_text = self.ax_status.text(0.5, 0.05, "",
                                            color=COLORS['status_full_throttle'],
                                            fontsize=10, fontweight='bold',
                                            ha='center', va='center')
    
    def _setup_input_bars(self):
        """Setup throttle and brake visualization bars."""
        self.ax_inputs.set_xlim(0, 100)
        self.ax_inputs.set_ylim(0, 3)
        self.ax_inputs.axis('off')
        
        # Background bars
        self.ax_inputs.barh([2.0], [100], height=0.6, color=COLORS['gauge_bg'], alpha=0.5)
        self.ax_inputs.barh([1.0], [100], height=0.6, color=COLORS['gauge_bg'], alpha=0.5)
        
        # Labels
        self.ax_inputs.text(-2, 2.0, "THR", color=COLORS['throttle'], fontsize=11, 
                           fontweight='bold', ha='right', va='center')
        self.ax_inputs.text(-2, 1.0, "BRK", color=COLORS['brake'], fontsize=11,
                           fontweight='bold', ha='right', va='center')
        
        # Percentage labels on right
        self.throttle_pct_text = self.ax_inputs.text(102, 2.0, "0%", color=COLORS['throttle'],
                                                     fontsize=10, ha='left', va='center')
        self.brake_pct_text = self.ax_inputs.text(102, 1.0, "0%", color=COLORS['brake'],
                                                  fontsize=10, ha='left', va='center')
        
        # Dynamic bars (will be updated)
        self.throttle_bar = self.ax_inputs.barh([2.0], [0], height=0.6, 
                                                 color=COLORS['throttle'], alpha=0.8)[0]
        self.brake_bar = self.ax_inputs.barh([1.0], [0], height=0.6,
                                              color=COLORS['brake'], alpha=0.8)[0]
    
    def _setup_speed_display(self):
        """Setup the speed and gear display."""
        self.ax_speed.set_xlim(0, 1)
        self.ax_speed.set_ylim(0, 1)
        
        # Speed label
        self.ax_speed.text(0.5, 0.85, "SPEED", color=COLORS['text_dim'],
                          fontsize=10, ha='center', va='center')
        
        # Speed value
        self.speed_text = self.ax_speed.text(0.5, 0.6, "0", color=COLORS['text'],
                                             fontsize=32, fontweight='bold',
                                             ha='center', va='center')
        self.ax_speed.text(0.5, 0.38, "km/h", color=COLORS['text_dim'],
                          fontsize=10, ha='center', va='center')
        
        # Gear display
        self.ax_speed.text(0.25, 0.15, "GEAR", color=COLORS['text_dim'],
                          fontsize=9, ha='center', va='center')
        self.gear_text = self.ax_speed.text(0.25, 0.02, "N", color=COLORS['text'],
                                            fontsize=24, fontweight='bold',
                                            ha='center', va='center')
        
        # Lap time
        self.ax_speed.text(0.75, 0.15, "TIME", color=COLORS['text_dim'],
                          fontsize=9, ha='center', va='center')
        self.time_text = self.ax_speed.text(0.75, 0.02, "0:00.000", color=COLORS['text'],
                                            fontsize=12, fontweight='bold',
                                            ha='center', va='center')
    
    def _setup_progress_bar(self):
        """Setup the lap progress bar."""
        self.ax_progress.set_xlim(0, 100)
        self.ax_progress.set_ylim(0, 1)
        self.ax_progress.axis('off')
        
        # Background
        self.ax_progress.barh([0.5], [100], height=0.4, color=COLORS['gauge_bg'], alpha=0.5)
        
        # Progress bar (dynamic)
        self.progress_bar = self.ax_progress.barh([0.5], [0], height=0.4,
                                                   color=COLORS['speed_bar'], alpha=0.8)[0]
        
        # Distance markers
        for pct in [0, 25, 50, 75, 100]:
            self.ax_progress.axvline(x=pct, color=COLORS['text_dim'], linewidth=0.5, alpha=0.3)
            self.ax_progress.text(pct, 0.1, f"{pct}%", color=COLORS['text_dim'],
                                 fontsize=8, ha='center')
    
    def _create_dynamic_elements(self):
        """Create elements that will be updated during animation."""
        # F1 car icon (starts at first position)
        initial_angle = self.car_angles[0]
        car_color = COLORS['car']
        if self.track_conditions:
            # Use team color approximation (simplified)
            car_color = COLORS['car']
        
        self.car_patch = create_car_icon(self.ax_track, self.x[0], self.y[0], 
                                         initial_angle, size=1.0, color=car_color)
        self.ax_track.add_patch(self.car_patch)
        
        # Trail behind car (last N positions)
        self.trail_length = 80
        self.trail_line, = self.ax_track.plot([], [], '-', color=COLORS['car_trail'],
                                               linewidth=4, alpha=0.5, zorder=9)
        
        # Glow effect around car
        self.car_glow, = self.ax_track.plot([], [], 'o', color=COLORS['car'],
                                            markersize=25, alpha=0.3, zorder=8)
    
    def _setup_controls(self):
        """Setup play/pause/reset buttons."""
        # Button axes
        ax_play = self.fig.add_axes([0.35, 0.01, 0.08, 0.035])
        ax_pause = self.fig.add_axes([0.44, 0.01, 0.08, 0.035])
        ax_reset = self.fig.add_axes([0.53, 0.01, 0.08, 0.035])
        ax_speed = self.fig.add_axes([0.65, 0.015, 0.15, 0.025])
        
        # Buttons
        self.btn_play = Button(ax_play, '> Play', color=COLORS['gauge_bg'], 
                               hovercolor=COLORS['throttle'])
        self.btn_pause = Button(ax_pause, '|| Pause', color=COLORS['gauge_bg'],
                                hovercolor=COLORS['text_dim'])
        self.btn_reset = Button(ax_reset, '[] Reset', color=COLORS['gauge_bg'],
                                hovercolor=COLORS['brake'])
        
        # Speed slider
        self.slider_speed = Slider(ax_speed, 'Speed', 0.25, 4.0, 
                                   valinit=self.playback_speed, valstep=0.25,
                                   color=COLORS['speed_bar'])
        
        # Connect callbacks
        self.btn_play.on_clicked(self._on_play)
        self.btn_pause.on_clicked(self._on_pause)
        self.btn_reset.on_clicked(self._on_reset)
        self.slider_speed.on_changed(self._on_speed_change)
        
        # Keyboard controls
        self.fig.canvas.mpl_connect('key_press_event', self._on_key_press)
        
        # Instructions
        self.fig.text(0.02, 0.01, "Controls: Space=Play/Pause | R=Reset | ←→=Step | +/-=Speed",
                     color=COLORS['text_dim'], fontsize=9)
    
    def _on_play(self, event=None):
        """Start playback."""
        if not self.is_playing:
            self.is_playing = True
            if self.animation is None:
                self._start_animation()
    
    def _on_pause(self, event=None):
        """Pause playback."""
        self.is_playing = False
    
    def _on_reset(self, event=None):
        """Reset to beginning."""
        self.is_playing = False
        self.current_frame = 0
        self.prev_gear = 0
        self._update_frame(0)
    
    def _on_speed_change(self, val):
        """Update playback speed."""
        self.playback_speed = val
    
    def _on_key_press(self, event):
        """Handle keyboard input."""
        if event.key == ' ':
            if self.is_playing:
                self._on_pause()
            else:
                self._on_play()
        elif event.key == 'r':
            self._on_reset()
        elif event.key == 'right':
            self.current_frame = min(self.current_frame + 10, self.total_frames - 1)
            self._update_frame(self.current_frame)
        elif event.key == 'left':
            self.current_frame = max(self.current_frame - 10, 0)
            self._update_frame(self.current_frame)
        elif event.key == '+' or event.key == '=':
            self.playback_speed = min(self.playback_speed + 0.25, 4.0)
            self.slider_speed.set_val(self.playback_speed)
        elif event.key == '-':
            self.playback_speed = max(self.playback_speed - 0.25, 0.25)
            self.slider_speed.set_val(self.playback_speed)
    
    def _update_frame(self, frame_idx: int) -> list:
        """Update all dynamic elements for a given frame."""
        frame_idx = int(frame_idx) % self.total_frames
        
        # Get current values
        car_x, car_y = self.x[frame_idx], self.y[frame_idx]
        car_angle = self.car_angles[frame_idx]
        speed = self.telemetry.speed[frame_idx]
        gear = int(self.telemetry.gear[frame_idx])
        throttle = self.telemetry.throttle[frame_idx]
        brake = self.telemetry.brake[frame_idx]
        
        # Normalize brake (might be 0-1 or 0-100)
        if brake <= 1:
            brake = brake * 100
        
        # Update car icon (remove old, add new)
        self.car_patch.remove()
        self.car_patch = create_car_icon(self.ax_track, car_x, car_y, 
                                         car_angle, size=1.0, color=COLORS['car'])
        self.ax_track.add_patch(self.car_patch)
        
        # Update glow
        self.car_glow.set_data([car_x], [car_y])
        
        # Update trail
        trail_start = max(0, frame_idx - self.trail_length)
        self.trail_line.set_data(self.x[trail_start:frame_idx+1], 
                                  self.y[trail_start:frame_idx+1])
        
        # Update telemetry displays
        self.speed_text.set_text(f"{speed:.0f}")
        self.gear_text.set_text(str(gear) if gear > 0 else "N")
        self.throttle_pct_text.set_text(f"{throttle:.0f}%")
        self.brake_pct_text.set_text(f"{brake:.0f}%")
        
        # Update input bars
        self.throttle_bar.set_width(throttle)
        self.brake_bar.set_width(brake)
        
        # Update time
        current_time = self.telemetry.time[frame_idx] - self.telemetry.time[0]
        minutes = int(current_time // 60)
        seconds = current_time % 60
        self.time_text.set_text(f"{minutes}:{seconds:06.3f}")
        
        # Update progress bar
        progress = (frame_idx / self.total_frames) * 100
        self.progress_bar.set_width(progress)
        
        # Get and update driver status
        status = self._get_driver_status(frame_idx)
        self._update_status_display(status)
        
        # Store current gear for next frame comparison
        self.prev_gear = gear
        
        return [self.car_patch, self.car_glow, self.trail_line, 
                self.throttle_bar, self.brake_bar,
                self.speed_text, self.gear_text, self.time_text, self.progress_bar]
    
    def _update_status_display(self, status: dict):
        """Update the driver status panel."""
        # Status colors
        status_colors = {
            'ACCELERATING': COLORS['status_accelerating'],
            'BRAKING': COLORS['status_braking'],
            'FULL_THROTTLE': COLORS['status_full_throttle'],
            'COASTING': COLORS['status_coasting'],
            'CORNER': COLORS['status_corner'],
        }
        
        # Status icons (ASCII compatible)
        status_icons = {
            'ACCELERATING': '^',
            'BRAKING': '!',
            'FULL_THROTTLE': '>>',
            'COASTING': '-',
            'CORNER': '*',
        }
        
        main_status = status['status']
        icon = status_icons.get(main_status, '')
        self.status_main_text.set_text(f"{icon} {main_status}")
        self.status_main_text.set_color(status_colors.get(main_status, COLORS['text']))
        
        # Gear change indicator
        if status['gear_change']:
            gear_icon = '^' if status['gear_change'] == 'UP' else 'v'
            self.gear_change_text.set_text(f"{gear_icon} GEAR {status['gear_change']}")
        else:
            self.gear_change_text.set_text("")
        
        # DRS indicator
        if status['drs']:
            self.drs_text.set_text("[DRS ACTIVE]")
        else:
            self.drs_text.set_text("")
        
        # Corner info
        corner = status['corner_info']
        phase = status['corner_phase']
        
        if corner:
            self.corner_name_text.set_text(corner.name)
            
            # Type with formatting
            type_display = corner.corner_type.replace('_', ' ')
            speed_display = corner.speed_class.replace('_', ' ')
            self.corner_type_text.set_text(f"{type_display} • {speed_display}")
            
            # Direction with arrow
            dir_arrow = '<--' if corner.direction == 'LEFT' else '-->'
            self.corner_direction_text.set_text(f"{dir_arrow} {corner.direction} ({corner.angle:.0f} deg)")
            
            # Phase
            phase_colors = {
                'APPROACH': COLORS['text_highlight'],
                'ENTRY': COLORS['status_braking'],
                'APEX': COLORS['status_corner'],
                'EXIT': COLORS['status_accelerating'],
            }
            self.corner_phase_text.set_text(f">> {phase}")
            self.corner_phase_text.set_color(phase_colors.get(phase, COLORS['text']))
            
            # Speeds
            self.corner_speeds_text.set_text(
                f"Entry: {corner.entry_speed:.0f} → Apex: {corner.apex_speed:.0f} → Exit: {corner.exit_speed:.0f} km/h"
            )
        else:
            self.corner_name_text.set_text("---")
            self.corner_type_text.set_text("No corner approaching")
            self.corner_direction_text.set_text("")
            self.corner_phase_text.set_text("")
            self.corner_speeds_text.set_text("")
    
    def _animate(self, frame):
        """Animation function called each frame."""
        if self.is_playing:
            # Calculate frame step based on playback speed
            frames_per_interval = int(self.playback_speed * (self.total_frames / (self.lap_duration * self.fps)))
            frames_per_interval = max(1, frames_per_interval)
            
            self.current_frame += frames_per_interval
            if self.current_frame >= self.total_frames:
                self.current_frame = 0  # Loop
                self.prev_gear = 0
        
        return self._update_frame(self.current_frame)
    
    def _start_animation(self):
        """Initialize and start the animation."""
        interval = 1000 / self.fps  # milliseconds between frames
        self.animation = FuncAnimation(
            self.fig,
            self._animate,
            interval=interval,
            blit=False,  # blit=True can cause issues with text updates
            cache_frame_data=False
        )
    
    def show(self):
        """Display the replay window."""
        self._start_animation()
        plt.show()
    
    def close(self):
        """Close the replay window."""
        if self.animation:
            self.animation.event_source.stop()
        plt.close(self.fig)


def run_lap_replay(
    telemetry: TelemetryData,
    zones: Optional[DrivingZones] = None,
    track_conditions: Optional[TrackConditions] = None,
    enhanced_corners: Optional[List[CornerInfo]] = None,
    title: str = "Lap Replay",
    rotation: float = 0.0
):
    """
    Convenience function to create and run a lap replay.
    
    Args:
        telemetry: TelemetryData object with lap telemetry
        zones: Optional DrivingZones for additional context
        track_conditions: Optional TrackConditions with weather/tire info
        enhanced_corners: Optional list of CornerInfo for detailed corner data
        title: Window title
        rotation: Circuit rotation in degrees
    """
    replay = LapReplayAnimation(
        telemetry=telemetry,
        zones=zones,
        track_conditions=track_conditions,
        enhanced_corners=enhanced_corners,
        title=title,
        rotation=rotation
    )
    replay.show()


if __name__ == "__main__":
    # Test the replay
    from data_loader import (
        load_session, get_lap_telemetry, analyze_driving_zones, 
        get_fastest_lap_info, get_circuit_info, get_track_conditions,
        get_enhanced_corners
    )
    
    print("Loading test data...")
    session = load_session(2024, 1, 'Q')  # Bahrain 2024 Qualifying
    
    lap_info = get_fastest_lap_info(session)
    print(f"Fastest lap: {lap_info.driver} - {lap_info.lap_time}" if lap_info else "No lap info")
    
    telemetry = get_lap_telemetry(session)
    if telemetry:
        zones = analyze_driving_zones(telemetry)
        circuit_info = get_circuit_info(session)
        track_conditions = get_track_conditions(session)
        enhanced_corners = get_enhanced_corners(session, telemetry, zones.corner_zones)
        
        print(f"Track conditions: {track_conditions}")
        print(f"Corners detected: {len(enhanced_corners)}")
        for corner in enhanced_corners[:3]:
            print(f"  {corner.name}: {corner.corner_type} ({corner.speed_class}) - {corner.direction}")
        
        title = f"Bahrain GP 2024 - {lap_info.driver if lap_info else 'Fastest'} ({lap_info.lap_time if lap_info else ''})"
        
        print("Starting replay...")
        run_lap_replay(
            telemetry=telemetry,
            zones=zones,
            track_conditions=track_conditions,
            enhanced_corners=enhanced_corners,
            title=title,
            rotation=circuit_info.get('rotation', 0)
        )
    else:
        print("Failed to load telemetry")
