# 🏎️ F1 Race Winner Predictor (2026 Edition)

> **A Physics-Informed Monte Carlo simulation engine updated for the 2026 Regulations and 11-Team Grid.**

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Status](https://img.shields.io/badge/Status-2026_Ready-red.svg)

---

## 📅 2026 Season Changes

The predictor has been updated to handle the massive regulation overhaul and driver market shake-up.

### 🆕 New Teams & Tracks
* **Cadillac Formula 1 Team:** Joins as the 11th team (PER / BOT).
* **Audi:** Replaces Kick Sauber (HUL / BOR).
* **Madrid GP:** Replaces Barcelona as the "Spanish GP" slot (Street Circuit, High Difficulty).
* **Barcelona-Catalunya:** Remains as a separate European round.

### 🏎️ 2026 Driver Lineup Logic
The model applies specific coefficients based on the confirmed 2026 grid:

| Team | Drivers | Tier Rating |
|------|---------|-------------|
| **McLaren** | Norris (NOR), Piastri (PIA) | **Tier 1 (Elite)** |
| **Ferrari** | Leclerc (LEC), Hamilton (HAM) | **Tier 1 (Elite)** |
| **Mercedes** | Russell (RUS), Antonelli (ANT) | **Tier 1 (Elite)** |
| **Red Bull** | Verstappen (VER), Hadjar (HAD) | **Tier 2 (High)** |
| **Aston Martin**| Alonso (ALO), Stroll (STR) | **Tier 2 (High)** |
| **Williams** | Sainz (SAI), Albon (ALB) | **Tier 3 (Mid)** |
| **Audi** | Hulkenberg (HUL), Bortoleto (BOR)| **Tier 3 (Mid)** |
| **Alpine** | Gasly (GAS), Colapinto (COL) | **Tier 3 (Mid)** |
| **Cadillac** | Perez (PER), Bottas (BOT) | **Tier 4 (New)** |

### ⚡ 2026 Sprint Calendar
The following rounds run the `FP1` physics profile instead of `FP2`:
1.  **China** (Shanghai)
2.  **Miami** (USA)
3.  **Canada** (Montreal) - *New for 2026*
4.  **Great Britain** (Silverstone) - *Returns*
5.  **Netherlands** (Zandvoort) - *New for 2026*
6.  **Singapore** (Marina Bay) - *New for 2026*

---

## 🧠 How It Works (V12 Logic)

The algorithm uses a **"Qualifying Anchor"** system refined for the 2026 Regulations.

### 1. The "Rookie" Factor
2026 features a high number of rookies. The model applies a **Consistency Penalty** to them.
* **Rookies:** Antonelli, Bearman, Hadjar, Bortoleto, Lindblad, Colapinto.
* **Effect:** They may have raw speed (Quali), but in the race simulation, they have higher variance (errors/tyre wear).

### 2. The "Hamilton/Ferrari" Buff
Lewis Hamilton moving to Ferrari creates a "Super Team." The model grants Ferrari the **Tier 1 Elite Buff** (-0.25s/lap), assuming they nailed the 2026 Engine Regs.

### 3. Track DNA
* **Madrid (New):** Configured as `Pass Difficulty: 0.85` (High). Starting P1 is critical.
* **Silverstone:** Configured as `Pass Difficulty: 0.4` (Low). Overtaking is easier.

---

## 💻 Usage

```bash
# Standard prediction
python f1_predictor_v12.py --year 2026 --gp "Australia" --session Q

# Sprint prediction (China)
python f1_predictor_v12.py --year 2026 --gp "China" --session Q
