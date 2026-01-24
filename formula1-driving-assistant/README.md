# 🏎️ F1 Driving Assistant

> **Learn the racing line from the fastest F1 drivers** — A sim racing training tool that visualizes real Formula 1 telemetry data to help drivers improve their lap times.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![FastF1](https://img.shields.io/badge/FastF1-3.3+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 🎯 What Is This?

F1 Driving Assistant is an interactive tool that fetches real Formula 1 telemetry data and visualizes it in a way that helps sim racers learn:

- **Braking zones** — Where the pros hit the brakes and how hard
- **Acceleration zones** — Where to get back on the throttle
- **Corner analysis** — Entry speed, apex speed, exit speed, and gear selection
- **Racing line** — The exact path taken by the fastest drivers

Perfect for drivers wanting to improve in:
- F1 2024/25 (Codemasters)
- Assetto Corsa / ACC
- iRacing
- Any sim with F1 tracks

## ✨ Features

### 📊 Interactive Track Analysis
- Select any F1 track from 2018 onwards
- Choose from Qualifying, Race, Sprint, or Practice sessions
- Compare different drivers' laps
- See gear usage at every corner

### 🗺️ Track Visualizations
- **Driving Zones Map** — Color-coded braking (red), acceleration (green), full throttle (blue)
- **Speed Gradient Map** — Track colored by speed (slow=blue → fast=red)
- **Telemetry Dashboard** — Speed trace, throttle/brake inputs, gear usage
- **🆕 Animated Lap Replay** — Watch the car move through the track with real-time telemetry!

### 🔄 Corner-by-Corner Breakdown
- Entry speed
- Apex speed  
- Exit speed
- Gear at apex
- Braking point markers

## 🚀 Quick Start

### Prerequisites
- Python 3.9 or higher
- Internet connection (for downloading F1 data)

### Installation

```bash
# Clone the repository
cd formula1-driving-assistant

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Usage

#### Interactive Mode (Recommended)
```bash
python main.py
```

This launches an interactive menu where you can:
1. Select a season (2018-2026)
2. Choose a track
3. Pick a session (Qualifying, Race, etc.)
4. Select a driver or use the pole lap
5. Generate visualizations

#### Quick Test
```bash
python main.py --test
```
Runs a quick demo with 2024 Bahrain GP qualifying data.

#### Direct Mode
```bash
# Specific race and session
python main.py --year 2024 --round 1 --session Q

# Specific driver
python main.py --year 2024 --round 1 --session Q --driver VER

# Save to file
python main.py --year 2024 --round 1 --session Q --save output.png
```

## 📁 Project Structure

```
formula1-driving-assistant/
├── main.py              # Entry point with CLI argument handling
├── cli.py               # Interactive menu interface
├── data_loader.py       # FastF1 API wrapper, data processing, corner classification
├── track_visualizer.py  # Matplotlib visualizations
├── lap_replay.py        # Enhanced animated lap replay with car icon & status info
├── requirements.txt     # Python dependencies
├── README.md           
└── .fastf1_cache/       # Auto-created cache directory
```

## 🖼️ Visualization Examples

### Track Map with Driving Zones
Shows braking zones (red), acceleration zones (green), and full throttle sections (blue) overlaid on the track layout:

```
🔴 Red    = Heavy braking zone
🟢 Green  = Acceleration / throttle application
🔵 Blue   = Full throttle (100%)
🟣 Purple = Corner apex markers with gear info
```

### Telemetry Dashboard
Four-panel view showing:
- Track overview with highlighted corners
- Speed trace over lap distance
- Throttle & brake inputs
- Gear selection throughout the lap

### 🆕 Animated Lap Replay
Watch the lap unfold in real-time with our enhanced replay system:
- **F1 Car Icon** — Realistic car shape instead of a simple dot, rotating with the racing line
- **Live telemetry** — Speed, Gear, Throttle %, Brake %
- **Track Conditions Panel** — Weather (temperature, humidity, wind), tire compound with color-coded indicator, tire age
- **Driver Status Info Box** — Real-time updates showing:
  - 🚀 **FULL THROTTLE** — Flat out on the straights
  - ⬆️ **ACCELERATING** — Getting back on the power
  - 🛑 **BRAKING** — Heavy braking zones
  - ➡️ **COASTING** — Trail braking or lift-off
  - 🔄 **CORNER** — Mid-corner
  - ⬆️/⬇️ **GEAR UP/DOWN** — Gear change notifications
  - 🟢 **DRS ACTIVE** — When DRS is deployed
- **Corner Approach Info** — When approaching a corner:
  - Corner name/number (e.g., "Turn 1", "Turn 4")
  - Corner type: HAIRPIN, SWEEPER, 90 DEGREE, KINK
  - Speed class: HIGH SPEED, MEDIUM SPEED, LOW SPEED
  - Direction: LEFT ⟲ or RIGHT ⟳ with angle
  - Phase: APPROACH → ENTRY → APEX → EXIT
  - Speed targets: Entry/Apex/Exit speeds
- **Input visualization** — Throttle/brake bars updating live
- **Playback controls**:
  - `Space` — Play/Pause
  - `R` — Reset to start
  - `←/→` — Step frame by frame
  - `+/-` — Speed up/slow down (0.25x to 4x)
  - GUI buttons for Play, Pause, Reset
  - Speed slider for precise control

## 🔧 Configuration

### Adjusting Zone Detection
In `data_loader.py`, you can tune the zone detection thresholds:

```python
zones = analyze_driving_zones(
    telemetry,
    brake_threshold=10.0,        # Brake % to count as braking
    throttle_full_threshold=95.0, # Throttle % for full throttle
    throttle_partial_threshold=50.0,  # Below this = coasting
    min_zone_points=5            # Minimum points for a zone
)
```

### Visualization Colors
Edit `COLORS` dict in `track_visualizer.py`:

```python
COLORS = {
    'braking': '#FF4444',        # Red
    'acceleration': '#44FF44',   # Green
    'full_throttle': '#4488FF',  # Blue
    'coasting': '#FFAA00',       # Orange
    'corner_marker': '#FF00FF',  # Magenta
    ...
}
```

## 📚 How It Works

1. **Data Fetching**: Uses [FastF1](https://github.com/theOehrly/Fast-F1) library to download official F1 telemetry
2. **Zone Detection**: Analyzes throttle, brake, and speed data to identify driving zones
3. **Corner Detection**: Finds local speed minima to identify corners and their characteristics
4. **Visualization**: Renders track using X/Y position data, overlaying color-coded zones

## 🙏 Credits & References

- **[FastF1](https://github.com/theOehrly/Fast-F1)** — The excellent Python library that makes F1 data accessible
- **[f1-race-replay](https://github.com/IAmTomShaw/f1-race-replay)** — Reference for visualization techniques
- **F1 Data** — Telemetry provided by Formula 1

## 🤝 Contributing

Contributions welcome! Ideas for improvement:
- [ ] Add lap comparison (overlay two drivers)
- [ ] DRS zones visualization
- [ ] Sector time breakdown
- [ ] Export to video/animation
- [ ] Integration with sim racing apps
- [ ] Web interface (Streamlit/Dash)

## 📄 License

MIT License — feel free to use, modify, and share!

---

<p align="center">
  <b>Happy racing! 🏁</b><br>
  <i>Remember: Smooth is fast, fast is smooth.</i>
</p>
