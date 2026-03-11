# 🏎️ F1 Race Winner Predictor (2026 Edition)

> **A Physics-Informed Monte Carlo simulation engine updated for the 2026 Regulations, 11-Team Grid, and Madrid GP.**

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Status](https://img.shields.io/badge/Status-2026_Ready-red.svg)

---

## 📅 2026 Season Overhaul

The predictor has been rebuilt to handle the massive regulation changes and grid expansion for the 2026 season.

### 🆕 New Teams & Tracks
* **Cadillac Formula 1 Team:** The grid expands to **22 cars** with the entry of Cadillac (Perez / Bottas).
* **Audi:** Takes over the Sauber entry (Hulkenberg / Bortoleto).
* **Madrid GP:** A new high-difficulty street circuit joining the calendar in September.
* **Sprint Calendar:** Sprints will be held in **China, Miami, Canada, Great Britain, Netherlands, and Singapore**.

### 🏎️ 2026 Driver Lineup & Tiers
The model groups teams into performance tiers based on the new 2026 Engine Regulations.

| Tier | Team | Drivers | Reasoning |
| :--- | :--- | :--- | :--- |
| **Tier 1 (Elite)** | **McLaren** | Norris, Piastri | Stability & Mercedes Power |
| **Tier 1 (Elite)** | **Ferrari** | Leclerc, Hamilton | Manufacturer Resource Advantage |
| **Tier 1 (Elite)** | **Mercedes** | Russell, Antonelli | Manufacturer Resource Advantage |
| **Tier 2 (High)** | **Red Bull** | Verstappen, Hadjar | Risk factor with new Ford Powertrains |
| **Tier 2 (High)** | **Aston Martin**| Alonso, Stroll | Risk factor with new Honda partnership |
| **Tier 3 (Mid)** | **Williams** | Sainz, Albon | Strong lineup, customer engine |
| **Tier 3 (Mid)** | **Alpine** | Gasly, Colapinto | Factory team, mid-field performance |
| **Tier 3 (Mid)** | **Audi** | Hulkenberg, Bortoleto | New manufacturer learning curve |
| **Tier 4 (New)** | **Cadillac** | Perez, Bottas | New entry penalty |
| **Tier 4 (New)** | **Haas** | Ocon, Bearman | Customer team |
| **Tier 4 (New)** | **RB** | Lawson, Lindblad | Junior team status |

---

## 🧠 The Algorithm: 4-Layer Logic

The simulation decides the winner based on four interacting layers of logic. This removes "Friday Sandbagging" noise while respecting the physics of racing.

### 🔹 Layer 1: The Qualifying Anchor (Base Pace)
We assume **Qualifying** is the only moment a car shows its true theoretical speed.
* **Formula:** `RacePace = PoleTime + 5.0s + DeltaToPole`
* **Why:** This prevents the model from being tricked by teams running heavy fuel in practice. If a car qualifies P1, the model treats it as the fastest car, regardless of its Friday times.

### 🔹 Layer 2: The Elite Tier Buff (Tyre Management)
Top teams generally have better suspension kinematics and aero-efficiency, allowing them to extend tyre life compared to the midfield.
* **Buff:** Drivers in **Tier 1** teams receive a **-0.25s per lap** pace advantage in the simulation.
* **Buff:** Drivers in **Tier 2** teams receive a **-0.15s per lap** advantage.
* **Effect:** This prevents a fast Qualifying lap from a backmarker (Glory Run) from translating into an unrealistic Race Win.

### 🔹 Layer 3: Driver Skill Factors
The model applies specific modifiers based on driver experience and historical consistency.
* **The "Champion" Bonus:** Proven winners (Verstappen, Hamilton, Norris, Alonso, Leclerc, Russell) get a **-0.1s pace buff** and **reduced variance** (fewer mistakes).
* **The "Rookie" Penalty:** The 2026 grid features many rookies (Antonelli, Bearman, Hadjar, Bortoleto, Lindblad, Colapinto). They receive a **+0.05s pace penalty** and **High Variance** (simulating inconsistent lap times and errors).

### 🔹 Layer 4: The Hunter Logic (Dynamic Overtaking)
Starting position matters, but *how much* depends on the track and the driver.
* **Formula:** `TrafficDrag = (GridPosition × 0.5) × PassDifficulty`
* **Hunter Bonus:** Elite drivers (Tier 1) have their `PassDifficulty` **halved**, simulating their ability to clear traffic quickly.
* **Track DNA:**
    * **Madrid/Monaco/Singapore:** `PassDifficulty > 0.85` (Starting P1 is critical).
    * **Silverstone/Spa:** `PassDifficulty < 0.40` (Overtaking is possible; pure pace matters more).

---

## 💻 Usage

**Standard Race Prediction:**
```bash
python f1_predictor_v12.py --year 2026 --gp "Australia" --session Q
```

### List Available Races

```bash
python -c "import fastf1; print(fastf1.get_event_schedule(2025)[['RoundNumber', 'Country', 'EventName']].to_string())"
```

# Terminal 1 — Backend
source f1-venv/bin/activate
uvicorn backend.app:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
