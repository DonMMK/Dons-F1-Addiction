# 🏎️ Formula Nerd Heaven

> **Dive deep into F1 telemetry like a true data addict** — An interactive tool that visualizes real Formula 1 telemetry data for racing enthusiasts.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![FastF1](https://img.shields.io/badge/FastF1-3.3+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 🎯 What Is This?

Formula Nerd Heaven is an interactive tool that fetches real Formula 1 telemetry data and visualizes it in two powerful ways:

- **🎬 Animated Lap Replay** — Watch a driver's fastest lap unfold in real-time with live telemetry
- **👻 Ghost Car Comparison** — Compare two drivers' laps head-to-head with animated racing

Perfect for F1 fans who want to understand what separates the fastest drivers!

## ✨ Features

### 📊 Interactive Analysis
- Select any F1 track from 2018 onwards
- Choose from Qualifying, Race, Sprint, or Practice sessions
- Compare different drivers' laps

### 🎬 Animated Lap Replay
Watch the lap unfold in real-time with our enhanced replay system:
- **F1 Car Icon** — Realistic car shape rotating with the racing line
- **Live telemetry** — Speed, Gear, Throttle %, Brake %
- **Track Conditions Panel** — Weather, tire compound with color-coded indicator, tire age
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

### 👻 Ghost Car Comparison
Compare two drivers' fastest laps head-to-head:

#### Track Analysis
- **Color-coded track sections** showing who is faster where:
  - Each driver's team color highlights sections where they are faster
  - Example: Verstappen vs Norris = 🔵 Blue sections (Red Bull) vs 🟠 Orange sections (McLaren)
  - Gray sections indicate equal pace

#### Comparison Summary Plot
Static analysis view with four panels:
- **Track Advantage Map** — Track layout colored by who's faster in each section
- **Speed Comparison** — Overlaid speed traces with shaded advantage areas
- **Gap/Delta Chart** — Running time delta over the lap showing where time is gained/lost
- **Mini-Sector Breakdown** — Bar chart of time deltas for each track segment

#### Animated Ghost Replay
Watch both cars race through the lap together:
- **Two F1 car icons** — Each in their team color racing simultaneously
- **Live gap display** — Real-time delta timer showing current gap
- **Gap visualization bar** — Visual indicator of who's ahead and by how much
- **Speed comparison** — Side-by-side speed readouts with delta
- **Sector-by-sector timing** — Mini-sector times updating as cars progress
- **Driver labels** — Color-coded labels above each car
- **Trails** — Different colored trails behind each car
- **Same controls as single-car replay**

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

This launches an interactive menu where you:
1. **Choose your mode first**: Lap Replay or Ghost Comparison
2. Select a season (2018-2026)
3. Choose a track
4. Pick a session (Qualifying, Race, etc.)
5. Select driver(s) based on your chosen mode

#### Quick Test
```bash
python main.py --test
```
Runs a quick demo with 2024 Bahrain GP qualifying data.

#### Ghost Comparison via Command Line
```bash
python main.py --ghost --year 2024 --round 1 --driver1 VER --driver2 NOR
```

## 📁 Project Structure

```
formula1-driving-assistant/
├── main.py              # Entry point with CLI argument handling
├── cli.py               # Interactive menu interface
├── data_loader.py       # FastF1 API wrapper, data processing, corner classification
├── track_visualizer.py  # Matplotlib visualizations
├── lap_replay.py        # Animated lap replay with car icon & status info
├── ghost_comparison.py  # Ghost car comparison with 2-driver lap analysis
├── requirements.txt     # Python dependencies
├── README.md           
└── .fastf1_cache/       # Auto-created cache directory
```

## � How It Works

1. **Data Fetching**: Uses [FastF1](https://github.com/theOehrly/Fast-F1) library to download official F1 telemetry
2. **Zone Detection**: Analyzes throttle, brake, and speed data to identify driving zones
3. **Corner Detection**: Finds local speed minima to identify corners and their characteristics
4. **Visualization**: Renders track using X/Y position data with animated car icons

## 🙏 Credits & References

- **[FastF1](https://github.com/theOehrly/Fast-F1)** — The excellent Python library that makes F1 data accessible
- **[f1-race-replay](https://github.com/IAmTomShaw/f1-race-replay)** — Reference for visualization techniques
- **F1 Data** — Telemetry provided by Formula 1

## 🤝 Contributing

Contributions welcome! Ideas for improvement:
- [x] ~~Add lap comparison (overlay two drivers)~~ ✅ Ghost Car Comparison added!
- [ ] DRS zones visualization
- [ ] Sector time breakdown
- [ ] Export to video/animation
- [ ] Web interface (Streamlit/Dash)

## 📄 License

MIT License — feel free to use, modify, and share!

---

<p align="center">
  <b>Happy nerding! 🏁</b><br>
  <i>Data is the new downforce.</i>
</p>
