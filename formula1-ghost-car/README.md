# 🏎️👻 F1 Ghost Car

> **Compare F1 drivers lap-by-lap like never before** — An interactive tool that visualizes real Formula 1 telemetry data for head-to-head driver comparisons.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![FastF1](https://img.shields.io/badge/FastF1-3.3+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 🎯 What Is This?

F1 Ghost Car is a telemetry visualization tool for **comparing F1 drivers**. Compare fastest laps head-to-head, or watch full race replays showing how the gap evolved over every lap.

### Main Features:
- **👻 Ghost Car Lap Comparison** — Compare two drivers' fastest laps with animated racing replay
- **🎬 Single Driver Lap Replay** — Watch one driver's fastest lap unfold with live telemetry
- **🏁 Ghost Car Race Replay** — Full race comparison across all laps with gap evolution

### Session Types:
- **Fastest Lap Modes** (Ghost Lap Comparison, Single Replay): Uses the best lap from any session
- **Race Replay Mode**: Uses all laps from Race (R) or Sprint (S) sessions

## ✨ Features

### � Ghost Car Lap Comparison (Primary Feature)
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

### 🎬 Single Driver Lap Replay
Watch one driver's fastest lap unfold in real-time:
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
- **Corner Approach Info** — Corner type, speed class, direction, phase, speed targets

### 🏁 Ghost Car Race Replay
Compare two drivers across an entire race - see how the gap evolved lap by lap:

#### Race Summary Plot
Static analysis view showing:
- **Gap Evolution Chart** — Line graph showing the gap between drivers over all laps
- **Position Chart** — Track position changes throughout the race
- **Lap Times Comparison** — Side-by-side lap time traces
- **Race Summary** — Final result, pit stops, laps completed

#### Animated Race Replay
Watch both drivers race through every lap:
- **Two F1 car icons** — Racing through each lap in sequence
- **Lap counter** — Current lap / Total laps
- **Running gap display** — Real-time gap showing who leads
- **Pit stop indicators** — Visual markers when drivers pit
- **Gap evolution chart** — Progress marker showing current position in race
- **Driver info panels** — Position, lap time, team colors

#### Race Replay Controls
- `Space` — Play/Pause
- `R` — Reset to lap 1
- `←/→` — Previous/Next lap
- `+/-` — Adjust playback speed
- GUI buttons and speed slider

### Playback Controls (All Modes)
- `Space` — Play/Pause
- `R` — Reset to start
- `←/→` — Step frame by frame
- `+/-` — Speed up/slow down (0.25x to 4x)
- GUI buttons for Play, Pause, Reset
- Speed slider for precise control

## 🚀 Quick Start

### Prerequisites
- Python 3.9 or higher
- Internet connection (for downloading F1 data)

### Installation

```bash
# Navigate to the project
cd formula1-ghost-car

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
1. **Choose your mode**: Ghost Car Comparison, Single Lap Replay, or Race Replay
2. Select a season (2018-2026)
3. Choose a track
4. Pick a session:
   - For Race Replay: Must select Race (R) or Sprint (S)
   - For other modes: Any session works (fastest lap is extracted)
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
formula1-ghost-car/
├── main.py              # Entry point with CLI argument handling
├── cli.py               # Interactive menu interface
├── data_loader.py       # FastF1 API wrapper, data processing
├── track_visualizer.py  # Matplotlib visualizations
├── lap_replay.py        # Single driver animated lap replay
├── ghost_comparison.py  # Two-driver ghost car lap comparison
├── race_replay.py       # Full race ghost car replay (all laps)
├── requirements.txt     # Python dependencies
├── README.md           
└── .fastf1_cache/       # Auto-created cache directory
```

## 📚 How It Works

1. **Data Fetching**: Uses [FastF1](https://github.com/theOehrly/Fast-F1) library to download official F1 telemetry
2. **Lap Extraction**: Gets the fastest lap from the selected session for each driver
3. **Zone Detection**: Analyzes throttle, brake, and speed data to identify driving zones
4. **Comparison**: Aligns laps by distance and calculates segment-by-segment deltas
5. **Visualization**: Renders track with animated car icons and real-time telemetry

## 🔗 Related Projects

- **[f1-race-replay](https://github.com/IAmTomShaw/f1-race-replay)** — Full race replay with all laps (different approach)
- **[FastF1](https://github.com/theOehrly/Fast-F1)** — The Python library that makes F1 data accessible

## 🤝 Contributing

Contributions welcome! Ideas for improvement:
- [x] ~~Ghost Car lap comparison~~ ✅
- [x] ~~Single driver lap replay~~ ✅
- [x] ~~Ghost Car Race Replay (full race, all laps)~~ ✅
- [ ] DRS zones visualization
- [ ] Sector time breakdown
- [ ] Export to video/animation
- [ ] Web interface (Streamlit/Dash)

## 📄 License

MIT License — feel free to use, modify, and share!

---

<p align="center">
  <b>Happy ghost hunting! 👻🏎️</b><br>
  <i>See where champions make the difference.</i>
</p>
