#!/usr/bin/env python3
"""
Formula 1 Ghost Car - Main Entry Point

A telemetry analysis tool that visualizes real F1 data
to help racing enthusiasts dive deep into driver performance.

Usage:
    python main.py           # Interactive CLI mode
    python main.py --quick   # Quick mode with prompts
"""

# Set matplotlib backend BEFORE any other imports
import matplotlib

try:
    matplotlib.use("Qt5Agg")
except:
    try:
        matplotlib.use("TkAgg")
    except:
        try:
            matplotlib.use("GTK3Agg")
        except:
            pass  # Use default

import argparse
import sys

from rich.console import Console

console = Console()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Formula 1 Ghost Car - Dive deep into F1 telemetry",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py                    Interactive mode (recommended)
    python main.py --test             Test with sample data
    python main.py --ghost --year 2024 --round 1 --driver1 VER --driver2 NOR
                                      Ghost car comparison
        """,
    )

    parser.add_argument(
        "--test", action="store_true", help="Run a quick test with sample data"
    )
    parser.add_argument(
        "--ghost", action="store_true", help="Run ghost car comparison mode"
    )
    parser.add_argument("--year", type=int, help="Season year (e.g., 2024)")
    parser.add_argument("--round", type=int, help="Round number")
    parser.add_argument(
        "--session",
        type=str,
        default="Q",
        help="Session type: FP1, FP2, FP3, Q, R, S, SQ",
    )
    parser.add_argument(
        "--driver1",
        type=str,
        default=None,
        help="First driver for ghost comparison (e.g., VER)",
    )
    parser.add_argument(
        "--driver2",
        type=str,
        default=None,
        help="Second driver for ghost comparison (e.g., NOR)",
    )

    args = parser.parse_args()

    if args.test:
        run_test()
    elif args.ghost and args.year and args.round and args.driver1 and args.driver2:
        run_ghost_comparison_direct(args)
    else:
        # Run interactive CLI
        from cli import main as cli_main

        cli_main()


def run_test():
    """Run a quick test with sample data."""
    console.print("[cyan]Running test with 2024 Bahrain GP Qualifying...[/cyan]\n")

    from data_loader import (
        load_session,
        get_fastest_lap_info,
        get_lap_telemetry,
        analyze_driving_zones,
    )
    from track_visualizer import create_track_plot, show_plot

    try:
        console.print(
            "[dim]Loading session (first run may take a minute to cache)...[/dim]"
        )
        session = load_session(2024, 1, "Q")

        lap_info = get_fastest_lap_info(session)
        if lap_info:
            console.print(
                f"[green]✓ Fastest lap: {lap_info.driver} - {lap_info.lap_time}[/green]"
            )

        console.print("[dim]Loading telemetry...[/dim]")
        telemetry = get_lap_telemetry(session)

        if telemetry:
            console.print(
                f"[green]✓ Loaded {len(telemetry.speed):,} telemetry points[/green]"
            )

            console.print("[dim]Analyzing driving zones...[/dim]")
            zones = analyze_driving_zones(telemetry)
            console.print(
                f"[green]✓ Found {len(zones.corner_zones)} corners, {len(zones.braking_zones)} braking zones[/green]"
            )

            console.print("\n[cyan]Starting lap replay animation...[/cyan]")
            title = f"Bahrain GP 2024 - {lap_info.driver if lap_info else 'Fastest'}"

            from track_visualizer import show_plot
            from lap_replay import run_lap_replay
            from data_loader import get_track_conditions, get_enhanced_corners, get_circuit_info

            circuit_info = get_circuit_info(session)
            track_conditions = get_track_conditions(session)
            enhanced_corners = get_enhanced_corners(session, telemetry, zones.corner_zones)

            run_lap_replay(
                telemetry=telemetry,
                zones=zones,
                track_conditions=track_conditions,
                enhanced_corners=enhanced_corners,
                title=title,
                rotation=circuit_info.get("rotation", 0),
            )
        else:
            console.print("[red]✗ Failed to load telemetry[/red]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print(
            "[yellow]Make sure you have an internet connection for first-time data download.[/yellow]"
        )
        sys.exit(1)


def run_ghost_comparison_direct(args):
    """Run ghost car comparison from command line arguments."""
    from data_loader import load_session, get_season_schedule
    from ghost_comparison import run_ghost_comparison

    console.print(
        f"[cyan]Loading {args.year} Round {args.round} {args.session}...[/cyan]"
    )
    console.print(f"[cyan]Comparing {args.driver1} vs {args.driver2}...[/cyan]")

    try:
        # Get event name
        events = get_season_schedule(args.year)
        event = next((e for e in events if e["round_number"] == args.round), None)
        event_name = event["event_name"] if event else f"Round {args.round}"

        session = load_session(args.year, args.round, args.session)

        title = f"{event_name} {args.year} - {args.driver1} vs {args.driver2} ({args.session})"

        run_ghost_comparison(
            session=session,
            driver1=args.driver1,
            driver2=args.driver2,
            title=title,
            show_summary=True,
            show_replay=True,
        )

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
