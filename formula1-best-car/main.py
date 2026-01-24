"""
Main Entry Point for F1 Car Comparison Analysis
Run this script to perform the full analysis and generate visualizations
"""

import argparse
from pathlib import Path
from typing import List, Optional
import pandas as pd

from data_loader import (
    COMPARISON_CONFIGS, load_session, get_event_schedule,
    get_driver_fastest_lap, calculate_gap_to_leader
)
from analysis import (
    calculate_dominance_metrics, calculate_performance_metrics,
    compare_eras, calculate_season_progression, calculate_race_pace_analysis,
    compare_telemetry
)
from visualizations import (
    create_speed_trace_comparison, create_track_speed_map,
    create_track_comparison_map, create_dominance_gap_chart,
    create_sector_comparison, create_lap_time_distribution,
    create_telemetry_comparison_panel, create_era_comparison_chart,
    create_season_progression_chart
)
from export import (
    setup_output_dirs, save_chart_for_tiktok, batch_export_race,
    CHARTS_DIR, TIKTOK_READY_DIR
)

import matplotlib.pyplot as plt


def analyze_single_race(
    year: int,
    race: str,
    drivers: List[str],
    session_type: str = 'Q',
    save_charts: bool = True
) -> dict:
    """
    Perform complete analysis for a single race
    
    Parameters:
    -----------
    year : int
        Season year
    race : str
        Race name
    drivers : List[str]
        List of driver abbreviations
    session_type : str
        'Q' for Qualifying, 'R' for Race
    save_charts : bool
        Whether to save generated charts
    
    Returns:
    --------
    dict : Analysis results and chart paths
    """
    print(f"\n{'='*60}")
    print(f"Analyzing {year} {race} - {session_type}")
    print('='*60)
    
    setup_output_dirs()
    session = load_session(year, race, session_type)
    
    results = {
        'year': year,
        'race': race,
        'session_type': session_type,
        'charts': [],
        'data': {}
    }
    
    race_slug = race.replace(' ', '_').lower()
    
    # Gap analysis
    print("\n📊 Calculating gaps to leader...")
    gaps = calculate_gap_to_leader(session)
    results['data']['gaps'] = gaps
    print(gaps.head(10).to_string())
    
    # Create charts
    if save_charts:
        print("\n🎨 Creating visualizations...")
        
        # Speed trace comparison
        fig = create_speed_trace_comparison(
            session, drivers,
            title=f"{year} {race} GP - Speed Comparison",
            save_path=str(CHARTS_DIR / f"{year}_{race_slug}_speed_trace.png")
        )
        if fig:
            results['charts'].append(f"speed_trace")
            save_chart_for_tiktok(fig, f"{year}_{race_slug}_speed_trace")
            plt.close(fig)
        
        # Track speed maps for top drivers
        for driver in drivers[:3]:
            fig = create_track_speed_map(
                session, driver,
                title=f"{driver} - {race} Track Speed",
                save_path=str(CHARTS_DIR / f"{year}_{race_slug}_{driver}_track.png")
            )
            if fig:
                results['charts'].append(f"track_speed_{driver}")
                plt.close(fig)
        
        # Track comparison
        if len(drivers) >= 2:
            fig = create_track_comparison_map(
                session, drivers[0], drivers[1],
                title=f"{drivers[0]} vs {drivers[1]} - {race}",
                save_path=str(CHARTS_DIR / f"{year}_{race_slug}_track_comparison.png")
            )
            if fig:
                results['charts'].append("track_comparison")
                plt.close(fig)
        
        # Sector comparison
        fig = create_sector_comparison(
            session, drivers,
            title=f"Sector Times - {race}",
            save_path=str(CHARTS_DIR / f"{year}_{race_slug}_sectors.png")
        )
        if fig:
            results['charts'].append("sector_comparison")
            plt.close(fig)
        
        # Telemetry comparison
        if len(drivers) >= 2:
            fig = create_telemetry_comparison_panel(
                session, drivers[0], drivers[1],
                title=f"Telemetry: {drivers[0]} vs {drivers[1]}",
                save_path=str(CHARTS_DIR / f"{year}_{race_slug}_telemetry.png")
            )
            if fig:
                results['charts'].append("telemetry_comparison")
                plt.close(fig)
    
    print(f"\n✅ Created {len(results['charts'])} charts")
    return results


def analyze_season_dominance(
    year: int,
    team: str,
    drivers: List[str],
    races: Optional[List[str]] = None,
    save_charts: bool = True
) -> dict:
    """
    Analyze dominance for a team across a season
    
    Parameters:
    -----------
    year : int
        Season year
    team : str
        Team name
    drivers : List[str]
        List of driver abbreviations
    races : List[str], optional
        Specific races to analyze (None for all)
    save_charts : bool
        Whether to save generated charts
    
    Returns:
    --------
    dict : Dominance analysis results
    """
    print(f"\n{'='*60}")
    print(f"Analyzing {year} {team} Season Dominance")
    print('='*60)
    
    setup_output_dirs()
    
    results = {
        'year': year,
        'team': team,
        'drivers': drivers,
        'charts': [],
        'data': {}
    }
    
    # Calculate dominance metrics
    print("\n📊 Calculating dominance metrics...")
    # Note: This is a simplified version - full calculation would take longer
    # For demo, we'll analyze a few key races
    
    schedule = get_event_schedule(year)
    race_list = races or schedule[schedule['EventFormat'] != 'testing']['EventName'].tolist()[:5]
    
    pole_count = 0
    gaps_to_p2 = []
    
    for race in race_list:
        try:
            print(f"  Analyzing {race}...")
            session = load_session(year, race, 'Q')
            gaps = calculate_gap_to_leader(session)
            
            if gaps.empty:
                continue
            
            pole_driver = gaps.iloc[0]['Driver']
            if pole_driver in drivers:
                pole_count += 1
                if len(gaps) > 1:
                    gaps_to_p2.append(gaps.iloc[1]['GapToLeader'])
                    
        except Exception as e:
            print(f"    Error: {e}")
            continue
    
    results['data']['poles'] = pole_count
    results['data']['avg_gap_to_p2'] = sum(gaps_to_p2) / len(gaps_to_p2) if gaps_to_p2 else 0
    results['data']['races_analyzed'] = len(race_list)
    
    print(f"\n📈 Results:")
    print(f"   Poles: {pole_count}/{len(race_list)}")
    print(f"   Avg Gap to P2: {results['data']['avg_gap_to_p2']:.3f}s")
    
    # Create dominance gap chart
    if save_charts:
        print("\n🎨 Creating dominance chart...")
        fig = create_dominance_gap_chart(
            year, team, drivers,
            title=f"{year} {team} - Gap to P2 Across Season",
            save_path=str(CHARTS_DIR / f"{year}_{team.replace(' ', '_')}_dominance.png")
        )
        if fig:
            results['charts'].append("dominance_gap")
            plt.close(fig)
    
    return results


def analyze_era_comparison(save_charts: bool = True) -> pd.DataFrame:
    """
    Compare dominance across all three eras (2020, 2023, 2025)
    
    Returns:
    --------
    pd.DataFrame : Comparison data across eras
    """
    print(f"\n{'='*60}")
    print("FULL ERA COMPARISON ANALYSIS")
    print('='*60)
    
    setup_output_dirs()
    
    era_data = []
    
    for era_name, config in COMPARISON_CONFIGS.items():
        print(f"\n🏎️  Analyzing {era_name} - {config.primary_car.team} {config.primary_car.car_name}")
        
        try:
            # Get a representative race for quick analysis
            schedule = get_event_schedule(config.year)
            races = schedule[schedule['EventFormat'] != 'testing']['EventName'].tolist()
            
            if not races:
                print(f"   No races found for {config.year}")
                continue
            
            # Analyze first 3 races for demo speed
            poles = 0
            wins = 0
            gaps = []
            
            for race in races[:3]:
                try:
                    q_session = load_session(config.year, race, 'Q')
                    gap_data = calculate_gap_to_leader(q_session)
                    
                    if not gap_data.empty:
                        pole_driver = gap_data.iloc[0]['Driver']
                        if pole_driver in config.primary_car.drivers:
                            poles += 1
                            if len(gap_data) > 1:
                                gaps.append(gap_data.iloc[1]['GapToLeader'])
                                
                except Exception as e:
                    print(f"   Error loading {race}: {e}")
                    continue
            
            era_data.append({
                'Era': era_name,
                'Car': config.primary_car.car_name,
                'Team': config.primary_car.team,
                'Year': config.year,
                'Poles': poles,
                'AvgGapToP2': sum(gaps) / len(gaps) if gaps else 0,
                'RacesAnalyzed': len(races[:3])
            })
            
        except Exception as e:
            print(f"   Error analyzing era: {e}")
            continue
    
    df = pd.DataFrame(era_data)
    
    if save_charts and not df.empty:
        print("\n🎨 Creating era comparison chart...")
        fig = create_era_comparison_chart(
            df,
            title="Dominance Comparison Across F1 Eras",
            save_path=str(CHARTS_DIR / "era_comparison.png")
        )
        if fig:
            plt.close(fig)
    
    print("\n📊 Era Comparison Results:")
    print(df.to_string())
    
    return df


def run_full_analysis():
    """
    Run the complete analysis for all eras and generate all visualizations
    """
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║     F1 CAR COMPARISON ANALYSIS - FASTEST vs MOST DOMINANT     ║
    ║                                                               ║
    ║  Comparing: Mercedes W11 (2020) vs RB19 (2023) vs MCL39 (2025)║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    setup_output_dirs()
    
    all_results = {}
    
    # 1. Analyze each era's primary car
    for era_name, config in COMPARISON_CONFIGS.items():
        print(f"\n\n{'#'*60}")
        print(f"# ERA: {era_name} - {config.primary_car.team} {config.primary_car.car_name}")
        print('#'*60)
        
        # Analyze first race of the season
        schedule = get_event_schedule(config.year)
        races = schedule[schedule['EventFormat'] != 'testing']['EventName'].tolist()
        
        if races:
            first_race = races[0]
            
            # Get all drivers for comparison
            all_drivers = config.primary_car.drivers.copy()
            for competitor in config.competitors:
                all_drivers.extend(competitor.drivers)
            
            # Analyze qualifying
            results = analyze_single_race(
                config.year, first_race, all_drivers[:6],
                session_type='Q', save_charts=True
            )
            all_results[f"{era_name}_qualifying"] = results
            
            # Analyze season dominance
            dom_results = analyze_season_dominance(
                config.year,
                config.primary_car.team,
                config.primary_car.drivers,
                races=races[:5],  # First 5 races for speed
                save_charts=True
            )
            all_results[f"{era_name}_dominance"] = dom_results
    
    # 2. Cross-era comparison
    era_df = analyze_era_comparison(save_charts=True)
    all_results['era_comparison'] = era_df.to_dict() if not era_df.empty else {}
    
    # Summary
    print(f"""
    ╔═══════════════════════════════════════════════════════════════╗
    ║                    ANALYSIS COMPLETE                          ║
    ╠═══════════════════════════════════════════════════════════════╣
    ║  Charts saved to: {CHARTS_DIR}
    ║  TikTok-ready exports: {TIKTOK_READY_DIR}
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    return all_results


def main():
    parser = argparse.ArgumentParser(description='F1 Car Comparison Analysis')
    parser.add_argument('--full', action='store_true', help='Run full analysis')
    parser.add_argument('--year', type=int, help='Analyze specific year')
    parser.add_argument('--race', type=str, help='Analyze specific race')
    parser.add_argument('--drivers', nargs='+', help='Drivers to compare')
    parser.add_argument('--quick', action='store_true', help='Quick demo mode')
    
    args = parser.parse_args()
    
    if args.full:
        run_full_analysis()
    elif args.year and args.race and args.drivers:
        analyze_single_race(args.year, args.race, args.drivers)
    elif args.quick:
        # Quick demo - analyze 2023 Bahrain
        print("Running quick demo analysis...")
        analyze_single_race(2023, "Bahrain", ["VER", "LEC", "HAM", "PER"])
    else:
        # Default: show help
        parser.print_help()
        print("\n\nExamples:")
        print("  python main.py --quick                           # Quick demo")
        print("  python main.py --year 2023 --race Bahrain --drivers VER LEC HAM")
        print("  python main.py --full                            # Full analysis")


if __name__ == "__main__":
    main()
