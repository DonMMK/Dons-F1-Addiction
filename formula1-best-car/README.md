# Formula 1: Fastest vs Most Dominant Car Analysis

## 🎯 Project Goal
Build a comprehensive F1 car comparison tool using the **FastF1 API** to analyze and visualize which car is the **fastest** vs which is the **most dominant** across different eras. The output will be stunning visualizations optimized for TikTok content.

---

## 📊 Cars to Compare

### Era 1: 2020 Season
| Car | Team | Role |
|-----|------|------|
| **Mercedes W11** | Mercedes | Primary Subject |
| Red Bull RB16 | Red Bull | Competitor |
| Racing Point RP20 | Racing Point | Competitor |

### Era 2: 2023 Season
| Car | Team | Role |
|-----|------|------|
| **Red Bull RB19** | Red Bull | Primary Subject |
| Mercedes W14E | Mercedes | Competitor |
| Ferrari SF-23 | Ferrari | Competitor |

### Era 3: 2025 Season
| Car | Team | Role |
|-----|------|------|
| **McLaren MCL39** | McLaren | Primary Subject |
| Mercedes W16E | Mercedes | Competitor |
| Red Bull RB21 | Red Bull | Competitor |

---

## 📐 Key Definitions

| Term | Definition |
|------|------------|
| **Fastest** | Raw lap time performance of the car |
| **Dominance** | Gap to closest competitors (relative performance) |

---

## 🔬 Analysis Requirements

### 1. Telemetry Comparison
- [ ] Speed traces on track
- [ ] Throttle application patterns
- [ ] Brake pressure analysis
- [ ] Gear usage across sectors
- [ ] DRS usage and effectiveness

### 2. Pace Analysis
- [ ] Qualifying pace (single lap performance)
- [ ] Race pace (long run consistency)
- [ ] Tire degradation comparison
- [ ] Fuel-corrected lap times

### 3. Performance Metrics
- [ ] Sector time breakdowns
- [ ] Corner speed analysis (slow/medium/high-speed)
- [ ] Straight-line speed comparison
- [ ] Acceleration zones performance

### 4. Evolution Analysis
- [ ] Car improvement across the season (compare same car at different races)
- [ ] Development rate vs competitors
- [ ] Track-specific performance trends

---

## 🎨 Visualization Requirements

### Must-Have Visualizations

#### 1. **Track Position Speed Map**
- Overlay car positions on track outline
- Use **team colors** to show distance covered at given timestamps
- Animate to show which car pulls ahead at different track sections

#### 2. **Corner Performance Heatmap**
- Show which car performs better at each corner type
- Color-coded by team (e.g., Mercedes teal, Red Bull blue, McLaren papaya)
- Highlight braking zones, apex speeds, and exit speeds

#### 3. **Speed Trace Comparison**
- Overlay speed traces for all cars on same lap
- Team-colored lines
- Highlight key overtaking/gap sections

#### 4. **Dominance Gap Chart**
- Bar chart showing gap to P2 across all races
- Visualize consistency of dominance
- Year-over-year comparison

#### 5. **Sector Battle Visualization**
- Three-sector breakdown per track
- Show which car won each sector
- Cumulative sector advantage over season

#### 6. **Lap Time Distribution**
- Violin/box plots of lap times
- Show consistency vs raw pace
- Compare qualifying vs race conditions

### Nice-to-Have Visualizations

- [ ] 3D track visualization with speed coloring
- [ ] Animated race replay with telemetry overlay
- [ ] Interactive dashboard for exploring data
- [ ] Side-by-side onboard comparison frames

---

## 🎬 TikTok Content Format

### Video Specifications
- **Aspect Ratio:** 9:16 (vertical)
- **Resolution:** 1080x1920
- **Duration:** 15-60 seconds per clip
- **Style:** Clean, modern, data-driven

### Content Series Ideas
1. **"Which Car is Actually Faster?"** - Raw speed comparison
2. **"The Most Dominant F1 Car Ever"** - Gap analysis
3. **"Corner Kings"** - Corner-by-corner breakdown
4. **"Evolution of Speed"** - Season progression
5. **"The Numbers Don't Lie"** - Statistical deep dive

---

## 🛠️ Technical Requirements

### Dependencies
```python
fastf1
matplotlib
seaborn
pandas
numpy
plotly  # for interactive charts
pillow  # for image processing
```

### FastF1 Features to Utilize
- `fastf1.plotting` - Team colors and styling
- `fastf1.core.Laps` - Lap data analysis
- `fastf1.core.Telemetry` - Detailed telemetry
- `fastf1.ergast` - Historical data

### Output Formats
- PNG/SVG for static charts
- MP4/GIF for animations
- High-DPI exports for social media

---

## 📁 Deliverables

1. **Python Scripts**
   - `data_loader.py` - Fetch and cache F1 data
   - `analysis.py` - Core comparison logic
   - `visualizations.py` - Chart generation
   - `export.py` - TikTok-ready media export

2. **Jupyter Notebooks**
   - `exploration.ipynb` - Data exploration and prototyping
   - `final_analysis.ipynb` - Polished analysis with outputs

3. **Output Assets**
   - `/charts/` - All generated visualizations
   - `/animations/` - Animated comparisons
   - `/tiktok_ready/` - Final cropped/formatted media

---

## ✅ Success Criteria

- [ ] Clear visual answer to "Which car is fastest?"
- [ ] Clear visual answer to "Which car is most dominant?"
- [ ] All visualizations use correct team colors
- [ ] Charts are readable on mobile screens
- [ ] Analysis covers all three eras (2020, 2023, 2025)
- [ ] At least 5 unique TikTok-ready visualizations per era

---

## 📝 Notes

- FastF1 caches data locally - first run may be slow
- 2025 data availability depends on season progress
- Team colors should match official F1 branding
- Consider colorblind-friendly alternatives for accessibility

