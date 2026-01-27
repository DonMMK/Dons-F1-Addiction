# Ghost Comparison Enhancements

## Overview
This document describes the three major enhancements added to the ghost car comparison feature in the F1 Driving Assistant.

## 1. Year-Based Team and Driver Management (2021-2026)

### Implementation
- Added `DRIVER_TEAMS_BY_YEAR` dictionary mapping years 2021-2026 to driver-team assignments
- Accounts for major driver transfers:
  - Hamilton: Mercedes → Ferrari (2025)
  - Sainz: Ferrari → Williams (2025)
  - Russell: Williams → Mercedes (2022)
  - And many more...

### Functions Added
- `get_driver_team_for_year(driver_code, year)`: Gets team for specific year
- `get_dynamic_driver_info(session, driver_code)`: Queries FastF1 for real-time team/color data
  - Falls back to year-based mapping if API unavailable
  - Returns tuple of (team_name, color_rgb_tuple)

### Usage
The system automatically detects the session year and uses the correct team assignments, ensuring accurate team colors and comparisons even for historical data or future predictions.

## 2. Same-Team Color Differentiation

### Problem
When both drivers are from the same team (e.g., Hamilton vs Russell at Mercedes), they would have the same cyan color, making the comparison confusing.

### Solution
Implemented HSV color space manipulation to create distinct variants of the team color:

```python
def differentiate_same_team_colors(base_color: Tuple[int, int, int])
```

#### Algorithm
1. Convert RGB team color to HSV color space
2. Create **lighter variant**:
   - Increase value (brightness) by 40%
   - Decrease saturation by 30%
3. Create **darker variant**:
   - Decrease value by 40%
   - Increase saturation by 20%
4. Convert back to RGB

#### Integration
- Automatically detected in `analyze_lap_comparison()` when `team1 == team2`
- Applied before any visualization is created
- Maintains recognizable team identity while ensuring clear differentiation

### Example
- Mercedes base color: `#27F4D2` (cyan)
- Driver 1 (lighter): Bright cyan with less saturation
- Driver 2 (darker): Deep cyan with more saturation

## 3. Corner-by-Corner Information Display

### Overview
Added dual corner information panels showing detailed corner approach data for both drivers simultaneously during ghost replay.

### Display Content

Each driver's panel shows:
- **Corner Name & Phase**: e.g., "Turn 1 - ENTRY" / "Turn 3 - APEX" / "Turn 10 - EXIT"
- **Corner Type & Classification**: e.g., "HAIRPIN • SLOW • LEFT"
- **Speed Data**: 
  - Entry speed (km/h)
  - Apex speed (km/h)
  - Exit speed (km/h)
- **Current Gear**: Gear number at current position
- **DRS Status**: "DRS ON" (green) or "DRS OFF" (gray)

### Implementation Details

#### New Methods
```python
_build_corner_lookup(corners, telemetry)
    - Creates distance-indexed lookup for O(1) corner detection
    
_get_corner_info_at_frame(frame_idx, telemetry_orig, corner_lookup)
    - Maps interpolated frame to original telemetry
    - Determines corner phase (ENTRY/APEX/EXIT)
    - Returns (corner_info, phase) tuple

_setup_corner_displays()
    - Creates dual panel layout with color-coded borders
    - Initializes text elements for dynamic updates

_update_corner_info(frame_idx)
    - Called every frame to refresh both panels
    - Shows corner data when approaching/in corner
    - Falls back to showing gear/DRS when on straight
```

#### Integration
- Corner panels positioned between telemetry display and progress bar
- Split-screen layout: Driver 1 (left) | Driver 2 (right)
- Border colors match driver colors (including differentiated same-team colors)
- Updates in real-time during animation

### Technical Considerations
- **Performance**: Corner lookup is pre-built at initialization for fast frame updates
- **Data Source**: Uses `get_enhanced_corners()` from `data_loader.py`
- **Graceful Degradation**: If corner data unavailable, still shows gear/DRS
- **Distance Mapping**: Handles interpolation between original and synchronized telemetry

## Modified Files

### `/formula1-driving-assistant/ghost_comparison.py`
- Added `colorsys` import for HSV color manipulation
- Added `DRIVER_TEAMS_BY_YEAR` dictionary (2021-2026)
- Added helper functions:
  - `get_driver_team_for_year()`
  - `differentiate_same_team_colors()`
  - `get_dynamic_driver_info()`
- Updated `analyze_lap_comparison()`:
  - Added `session` parameter
  - Integrated dynamic team detection
  - Integrated same-team color differentiation
- Updated `GhostComparisonReplay.__init__()`:
  - Added `session`, `zones1`, `zones2` parameters
  - Added corner lookup initialization
- Updated `GhostComparisonReplay._setup_figure()`:
  - Modified grid layout to 5 rows (added corner info row)
  - Added corner panel axes
  - Called `_setup_corner_displays()`
- Added corner-related methods:
  - `_build_corner_lookup()`
  - `_get_corner_info_at_frame()`
  - `_setup_corner_displays()`
  - `_update_corner_info()`
- Updated `_update_frame()`:
  - Added call to `_update_corner_info()`
- Updated `run_ghost_comparison()`:
  - Added zones loading
  - Passes session and zones to replay

### `/formula1-driving-assistant/cli.py`
- Updated ghost comparison flow:
  - Added zones loading for both drivers
  - Passes `session` to `analyze_lap_comparison()`
  - Passes `session`, `zones1`, `zones2` to `GhostComparisonReplay()`

## Benefits

1. **Historical Accuracy**: Correct team colors for any year from 2021-2026
2. **Visual Clarity**: Same-team comparisons now have distinct colors
3. **Detailed Insights**: Corner-by-corner data reveals driver technique differences
4. **Professional Presentation**: Enhanced UI mimics F1 broadcast graphics

## Usage Example

```python
from ghost_comparison import run_ghost_comparison

# Automatically handles all enhancements
run_ghost_comparison(
    session=session,
    driver1="HAM",  # Mercedes in 2024
    driver2="RUS",  # Mercedes in 2024
    title="Mercedes Comparison",
    show_summary=True,
    show_replay=True
)
```

The system will:
1. Detect both are Mercedes drivers
2. Apply color differentiation (lighter vs darker cyan)
3. Show corner info for both during replay
4. Use 2024 team assignments

## Future Enhancements

Potential additions:
- Corner performance comparison metrics (who's faster in each corner)
- Braking point comparison overlay
- Throttle/brake input comparison in corners
- Historical driver comparison across years (e.g., 2024 Hamilton vs 2025 Hamilton)
