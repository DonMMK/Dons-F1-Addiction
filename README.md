# 🏎️ Don's F1 Addiction

A collection of Formula 1 data analysis tools built with Python and the FastF1 library. Analyze telemetry, predict race outcomes, and discover what makes the fastest cars tick.

## 📦 Features

### 1. F1 Ghost Car 👻
**Compare drivers lap-by-lap like never before.** An interactive CLI tool for ghost car comparisons and race replays.

**Features:**
- 👻 **Ghost Car Lap Comparison** - Compare two drivers' fastest laps head-to-head with animated replay
- 🎬 **Single Driver Lap Replay** - Watch one driver's fastest lap unfold with live telemetry
- 🏁 **Ghost Car Race Replay** - Full race comparison across all laps with gap evolution
- 🗓️ Browse F1 calendars from 2018 onwards (including pre-season testing)

> **Fastest Lap Modes** use the best lap from any session. **Race Replay** compares all laps from Race/Sprint sessions.

### 2. F1 Prediction
Machine learning models for predicting race outcomes based on historical data, qualifying results, and track characteristics.

**Features:**
- Race winner predictions
- Grid position analysis
- Historical performance benchmarking (2023-2025)
- Track-specific insights

### 3. Best Car Analysis
Statistical analysis to determine which car has the performance advantage across different circuits and conditions.

**Features:**
- Car performance comparisons
- Circuit-specific analysis
- Data visualization and export

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9 or higher
- pip (Python package manager)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/DonMMK/Dons-F1-Addiction.git
   cd Dons-F1-Addiction
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv f1-venv
   ```

3. **Activate the virtual environment**
   ```bash
   # macOS/Linux
   source f1-venv/bin/activate
   
   # Windows
   f1-venv\Scripts\activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

---

## 🎮 Usage

### F1 Ghost Car

```bash
cd formula1-ghost-car
python main.py
```

Use the interactive CLI to:
1. **Choose your mode**: 👻 Ghost Car Comparison, 🎬 Single Lap Replay, or 🏁 Race Replay
2. Select a season (2018-2026)
3. Choose a race or pre-season testing event
4. Pick a session:
   - **Race Replay**: Requires Race (R) or Sprint (S) session
   - **Other modes**: Any session (fastest lap is extracted)
5. Select driver(s) based on your chosen mode

### F1 Prediction

```bash
cd formula1-prediction
python f1_predictor.py
```

### Best Car Analysis

```bash
cd formula1-best-car
python main.py
```

---

## 📁 Project Structure

```
Dons-F1-Addiction/
├── formula1-ghost-car/           # Ghost Car comparison tool 👻
│   ├── main.py                   # Entry point
│   ├── cli.py                    # Interactive command-line interface
│   ├── data_loader.py            # FastF1 data loading utilities
│   ├── track_visualizer.py       # Track and telemetry plots
│   ├── lap_replay.py             # Animated lap replays
│   └── ghost_comparison.py       # Driver comparison animations
│
├── formula1-prediction/          # Race outcome predictions
│   ├── f1_predictor_v*.py        # Main prediction model
│   └── benchmark_*.py            # Historical accuracy tests
│
├── formula1-best-car/            # Car performance analysis
│   ├── main.py                   # Entry point
│   ├── analysis.py               # Statistical analysis
│   └── visualizations.py         # Performance charts
│
└── requirements.txt              # Python dependencies
```

---

## 🛠️ Technologies

- **[FastF1](https://github.com/theOehrly/Fast-F1)** - F1 telemetry and timing data
- **[Matplotlib](https://matplotlib.org/)** - Data visualization
- **[Rich](https://rich.readthedocs.io/)** - Beautiful terminal output
- **[Questionary](https://questionary.readthedocs.io/)** - Interactive CLI prompts
- **[Pandas](https://pandas.pydata.org/)** - Data manipulation
- **[NumPy](https://numpy.org/)** - Numerical computing

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [FastF1](https://github.com/theOehrly/Fast-F1) for providing access to F1 telemetry data
- Formula 1 for the incredible sport that fuels this addiction
- GecklesTheClown (Professional git checker)

## Alternatives 
https://openf1.org/

https://my.sportmonks.com/subscriptions/create/sport/2/plans


