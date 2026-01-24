#!/usr/bin/env python3
"""
Formula 1 Driving Assistant - Main Entry Point

A sim racing training tool that visualizes real F1 telemetry data
to help drivers learn braking zones, racing lines, and optimal inputs.

Usage:
    python main.py           # Interactive CLI mode
    python main.py --quick   # Quick mode with prompts
"""

# Set matplotlib backend BEFORE any other imports
import matplotlib
try:
    matplotlib.use('Qt5Agg')
except:
    try:
        matplotlib.use('TkAgg')
    except:
        try:
            matplotlib.use('GTK3Agg')
        except:
            pass  # Use default

import argparse
import sys

from rich.console import Console

console = Console()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="F1 Driving Assistant - Learn the racing line from the fastest drivers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py                    Interactive mode (recommended)
    python main.py --test             Test with sample data
    python main.py --year 2024 --round 1 --session Q
                                      Direct analysis mode
        """
    )
    
    parser.add_argument('--test', action='store_true',
                        help='Run a quick test with sample data')
    parser.add_argument('--year', type=int, 
                        help='Season year (e.g., 2024)')
    parser.add_argument('--round', type=int,
                        help='Round number')
    parser.add_argument('--session', type=str, default='Q',
                        help='Session type: FP1, FP2, FP3, Q, R, S, SQ')
    parser.add_argument('--driver', type=str, default=None,
                        help='Driver code (e.g., VER, HAM). Omit for fastest.')
    parser.add_argument('--save', type=str, default=None,
                        help='Save visualization to file')
    
    args = parser.parse_args()
    
    if args.test:
        run_test()
    elif args.year and args.round:
        run_direct(args)
    else:
        # Run interactive CLI
        from cli import main as cli_main
        cli_main()


def run_test():
    """Run a quick test with sample data."""
    console.print("[cyan]Running test with 2024 Bahrain GP Qualifying...[/cyan]\n")
    
    from data_loader import load_session, get_fastest_lap_info, get_lap_telemetry, analyze_driving_zones
    from track_visualizer import create_track_plot, show_plot
    
    try:
        console.print("[dim]Loading session (first run may take a minute to cache)...[/dim]")
        session = load_session(2024, 1, 'Q')
        
        lap_info = get_fastest_lap_info(session)
        if lap_info:
            console.print(f"[green]✓ Fastest lap: {lap_info.driver} - {lap_info.lap_time}[/green]")
        
        console.print("[dim]Loading telemetry...[/dim]")
        telemetry = get_lap_telemetry(session)
        
        if telemetry:
            console.print(f"[green]✓ Loaded {len(telemetry.speed):,} telemetry points[/green]")
            
            console.print("[dim]Analyzing driving zones...[/dim]")
            zones = analyze_driving_zones(telemetry)
            console.print(f"[green]✓ Found {len(zones.corner_zones)} corners, {len(zones.braking_zones)} braking zones[/green]")
            
            console.print("\n[cyan]Generating track visualization...[/cyan]")
            title = f"Bahrain GP 2024 - {lap_info.driver if lap_info else 'Fastest'}"
            fig = create_track_plot(telemetry, zones, title=title)
            show_plot(fig)
        else:
            console.print("[red]✗ Failed to load telemetry[/red]")
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[yellow]Make sure you have an internet connection for first-time data download.[/yellow]")
        sys.exit(1)


def run_direct(args):
    """Run direct analysis from command line arguments."""
    from data_loader import (
        load_session, get_fastest_lap_info, get_lap_telemetry, 
        analyze_driving_zones, get_circuit_info, get_season_schedule
    )
    from track_visualizer import create_track_plot, create_telemetry_dashboard, show_plot, save_plot
    
    console.print(f"[cyan]Loading {args.year} Round {args.round} {args.session}...[/cyan]")
    
    try:
        # Get event name
        events = get_season_schedule(args.year)
        event = next((e for e in events if e['round_number'] == args.round), None)
        event_name = event['event_name'] if event else f"Round {args.round}"
        
        session = load_session(args.year, args.round, args.session)
        
        lap_info = get_fastest_lap_info(session)
        driver_name = args.driver if args.driver else (lap_info.driver if lap_info else "Unknown")
        
        console.print(f"[dim]Fastest lap: {lap_info.driver} - {lap_info.lap_time}[/dim]" if lap_info else "")
        
        telemetry = get_lap_telemetry(session, args.driver)
        if not telemetry:
            console.print("[red]Failed to load telemetry[/red]")
            sys.exit(1)
        
        zones = analyze_driving_zones(telemetry)
        circuit_info = get_circuit_info(session)
        
        console.print(f"[green]✓ {len(zones.corner_zones)} corners, {len(zones.braking_zones)} braking zones[/green]")
        
        title = f"{event_name} {args.year} - {driver_name}"
        fig = create_track_plot(telemetry, zones, title=title, 
                               rotation=circuit_info.get('rotation', 0))
        
        if args.save:
            save_plot(fig, args.save)
            console.print(f"[green]Saved to {args.save}[/green]")
        else:
            show_plot(fig)
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
