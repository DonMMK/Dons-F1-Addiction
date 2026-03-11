# 🏎️ Don's F1 Addiction

A full-stack Formula 1 data analysis platform built with **React** + **FastAPI** + **FastF1**.

Analyse telemetry, predict race outcomes, and discover what makes the fastest cars tick — all from a sleek, F1-themed web interface.

---

## 📦 Features

### 1. Race Prediction 📊
Monte Carlo simulation engine with **12 model versions** — select the model, season, Grand Prix, and session to generate win-probability predictions.

### 2. Ghost Car Comparison 👻
Compare two drivers' fastest laps head-to-head. Interactive track map with full telemetry overlay (speed, throttle, brake, DRS).

### 3. Best Car Analysis 🏆
Which car dominated each era? Compare the **Mercedes W11**, **Red Bull RB19**, and **McLaren MCL39** with qualifying gaps and season progression charts.

---

## 🏗️ Architecture

```
Dons-F1-Addiction/
├── frontend/                     # React + Vite + TypeScript
│   ├── src/
│   │   ├── components/           # Layout, TrackMap, TelemetryChart, Spinner
│   │   ├── pages/                # HomePage, PredictionPage, GhostCarPage, BestCarPage
│   │   ├── styles/               # F1-themed global CSS
│   │   ├── api.ts                # Typed API client
│   │   └── App.tsx               # Router
│   ├── package.json
│   └── vite.config.ts            # Proxy /api → backend
│
├── backend/                      # FastAPI REST API
│   ├── app.py                    # Application entry point
│   ├── routers/
│   │   ├── common.py             # Seasons, schedules, drivers
│   │   ├── prediction.py         # Prediction model runner
│   │   ├── ghost_car.py          # Telemetry & comparison
│   │   └── best_car.py           # Era analysis & gaps
│   └── requirements.txt
│
├── formula1-prediction/          # Original predictor models (v1-v12)
├── formula1-ghost-car/           # Original ghost car CLI & data loader
├── formula1-best-car/            # Original best car analysis
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.10+**
- **Node.js 18+** and npm
- pip

### 1. Clone & setup Python environment

```bash
git clone https://github.com/DonMMK/Dons-F1-Addiction.git
cd Dons-F1-Addiction

python3 -m venv f1-venv
source f1-venv/bin/activate   # macOS/Linux
pip install -r backend/requirements.txt
```

### 2. Start the backend

```bash
source f1-venv/bin/activate
uvicorn backend.app:app --reload --port 8000
```

The API is now live at `http://localhost:8000`. Explore docs at `http://localhost:8000/docs`.

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser. The Vite dev server proxies `/api` requests to the backend.

---

## 🎮 Usage

| Page | URL | Description |
|------|-----|-------------|
| **Home** | `/` | Overview of available tools |
| **Prediction** | `/prediction` | Select model, GP, session → run Monte Carlo simulation |
| **Ghost Car** | `/ghost-car` | Select two drivers → see track map + telemetry comparison |
| **Best Car** | `/best-car` | Pick an era → season progression + qualifying gap analysis |

### Prediction Models

All predictor versions (v1 through v12) are available in the dropdown. Each version uses a different simulation approach:

| Model | Approach |
|-------|----------|
| v1 | Physics + ML (fuel correction, tyre deg, Linear Regression) |
| v2–v3 | Increased Monte Carlo runs, better stint detection |
| v4–v6 | Track-specific overtake difficulty, safety car probability |
| v7–v9 | Anomaly detection, driver tier buffs |
| v10–v11 | Simplified qualifying-anchor simulation |
| **v12** | 2026-ready: 22-driver grid, new teams (Cadillac), driver tiers |

---

## 🛠️ Technologies

| Layer | Stack |
|-------|-------|
| **Frontend** | React 18, TypeScript, Vite, Recharts, React Router |
| **Backend** | FastAPI, Uvicorn, Pydantic |
| **Data** | FastF1, Pandas, NumPy, scikit-learn |
| **Styling** | Custom CSS (F1.com-inspired dark theme, Titillium Web) |

---

## 📝 Original CLI Tools

The original CLI tools still work independently:

```bash
# Ghost Car (interactive CLI)
cd formula1-ghost-car && python main.py

# Prediction (CLI)
cd formula1-prediction && python f1_predictor_v12.py --year 2026 --gp "Australia" --session Q

# Best Car Analysis
cd formula1-best-car && python main.py
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- [FastF1](https://github.com/theOehrly/Fast-F1) for F1 telemetry data
- Formula 1 for the incredible sport that fuels this addiction
