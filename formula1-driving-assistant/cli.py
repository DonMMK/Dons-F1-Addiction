"""
Formula 1 Driving Assistant - CLI Interface Module

Interactive command-line interface using rich and questionary for:
- Season selection
- Track/Event selection
- Session type selection
- Driver selection
- Visualization options
"""

import sys
from typing import Optional, List, Dict, Any

# Rich for beautiful console output
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text
from rich import box

# Questionary for interactive prompts
import questionary
from questionary import Style

# Local imports
from data_loader import (
    get_available_seasons,
    get_season_schedule,
    get_session_types,
    load_session,
    get_fastest_lap_info,
    get_lap_telemetry,
    analyze_driving_zones,
    get_all_drivers_fastest_laps,
    get_circuit_info,
    get_track_conditions,
    get_enhanced_corners,
)
from track_visualizer import (
    create_track_plot,
    create_telemetry_dashboard,
    show_plot,
    save_plot,
)
from lap_replay import run_lap_replay
from ghost_comparison import (
    run_ghost_comparison,
    analyze_lap_comparison,
    create_comparison_summary_plot,
)

# Initialize rich console
console = Console()

# Custom questionary style
custom_style = Style(
    [
        ("qmark", "fg:cyan bold"),
        ("question", "fg:white bold"),
        ("answer", "fg:green bold"),
        ("pointer", "fg:cyan bold"),
        ("highlighted", "fg:cyan bold"),
        ("selected", "fg:green"),
        ("separator", "fg:gray"),
        ("instruction", "fg:gray italic"),
    ]
)


def display_banner():
    """Display the application banner."""
    banner = """
    ╔═══════════════════════════════════════════════════════════╗
    ║        🏎️  F1 DRIVING ASSISTANT  🏁                        ║
    ║     Learn the racing line from the fastest drivers        ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    console.print(Panel(banner, style="cyan", box=box.DOUBLE))


def select_season() -> Optional[int]:
    """Prompt user to select a season."""
    seasons = get_available_seasons()

    choices = [str(year) for year in reversed(seasons)]
    choices.append("Exit")

    answer = questionary.select(
        "Select a season:", choices=choices, style=custom_style
    ).ask()

    if answer == "Exit" or answer is None:
        return None

    return int(answer)


def select_event(year: int) -> Optional[Dict[str, Any]]:
    """Prompt user to select an event/track."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Loading {year} calendar...[/cyan]".format(year=year)),
        console=console,
    ) as progress:
        progress.add_task("loading", total=None)
        events = get_season_schedule(year)

    if not events:
        console.print("[red]No events found for this season.[/red]")
        return None

    # Display events table
    table = Table(title=f"🗓️  {year} F1 Calendar", box=box.ROUNDED, style="cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Event", style="white")
    table.add_column("Circuit", style="green")
    table.add_column("Country", style="yellow")
    table.add_column("Date", style="dim")

    for event in events:
        table.add_row(
            str(event["round_number"]),
            event["event_name"],
            event["circuit_name"],
            event["country"],
            event["date"],
        )

    console.print(table)
    console.print()

    # Create choices
    choices = [
        f"{e['round_number']:02d}. {e['event_name']} ({e['circuit_name']})"
        for e in events
    ]
    choices.append("← Back to season selection")

    answer = questionary.select(
        "Select a track:", choices=choices, style=custom_style
    ).ask()

    if answer is None or "Back" in answer:
        return None

    # Extract round number
    round_num = int(answer.split(".")[0])
    return next(e for e in events if e["round_number"] == round_num)


def select_session(year: int, round_number: int, event_name: str) -> Optional[str]:
    """Prompt user to select a session type."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Checking available sessions...[/cyan]"),
        console=console,
    ) as progress:
        progress.add_task("loading", total=None)
        sessions = get_session_types(year, round_number)

    session_names = {
        "FP1": "Free Practice 1",
        "FP2": "Free Practice 2",
        "FP3": "Free Practice 3",
        "Q": "Qualifying",
        "SQ": "Sprint Qualifying",
        "SS": "Sprint Shootout",
        "S": "Sprint Race",
        "R": "Race",
    }

    choices = [f"{s} - {session_names.get(s, s)}" for s in sessions]
    choices.append("← Back to track selection")

    console.print(f"\n[cyan]Sessions available for {event_name}:[/cyan]")

    answer = questionary.select(
        "Select a session:", choices=choices, style=custom_style
    ).ask()

    if answer is None or "Back" in answer:
        return None

    return answer.split(" - ")[0]


def select_driver(session, event_name: str) -> Optional[str]:
    """Prompt user to select a driver or use overall fastest."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Loading lap times...[/cyan]"),
        console=console,
    ) as progress:
        progress.add_task("loading", total=None)
        drivers = get_all_drivers_fastest_laps(session)

    if not drivers:
        console.print("[yellow]No lap times available, using session fastest.[/yellow]")
        return None

    # Display driver times
    table = Table(title=f"🏁 Lap Times - {event_name}", box=box.ROUNDED, style="cyan")
    table.add_column("Pos", style="yellow", width=4)
    table.add_column("Driver", style="white")
    table.add_column("Team", style="dim")
    table.add_column("Lap Time", style="green")
    table.add_column("Tyre", style="red")

    for i, driver in enumerate(drivers[:20], 1):
        table.add_row(
            str(i),
            driver["driver"],
            driver["team"],
            driver["lap_time"],
            driver["compound"],
        )

    console.print(table)
    console.print()

    # Create choices
    choices = ["★ Fastest Overall (Pole Position)"]
    choices.extend([f"{d['driver']} - {d['lap_time']}" for d in drivers])
    choices.append("← Back to session selection")

    answer = questionary.select(
        "Select a driver's lap to analyze:", choices=choices, style=custom_style
    ).ask()

    if answer is None or "Back" in answer:
        return "BACK"

    if "Fastest Overall" in answer:
        return None  # Will use overall fastest

    return answer.split(" - ")[0]


def select_visualization_mode() -> str:
    """Prompt user to select visualization type."""
    choices = [
        "🏁 Track Map with Driving Zones",
        "📊 Full Telemetry Dashboard",
        "🌈 Speed Gradient Map",
        "🎬 Animated Lap Replay",
        "👻 Ghost Car Comparison (2 Drivers)",
        "💾 Save All Visualizations",
        "← Back to driver selection",
    ]

    answer = questionary.select(
        "Select visualization mode:", choices=choices, style=custom_style
    ).ask()

    if answer is None or "Back" in answer:
        return "BACK"

    if "Track Map" in answer:
        return "zones"
    elif "Dashboard" in answer:
        return "dashboard"
    elif "Speed Gradient" in answer:
        return "speed"
    elif "Animated Lap Replay" in answer:
        return "replay"
    elif "Ghost Car Comparison" in answer:
        return "ghost"
    elif "Save All" in answer:
        return "save_all"

    return "zones"


def select_two_drivers(session, event_name: str) -> Optional[tuple]:
    """Prompt user to select two drivers for ghost comparison."""
    drivers = get_all_drivers_fastest_laps(session)

    if len(drivers) < 2:
        console.print(
            "[red]Need at least 2 drivers with lap times for comparison.[/red]"
        )
        return None

    # Display driver times
    table = Table(
        title=f"👻 Ghost Comparison - Select 2 Drivers - {event_name}",
        box=box.ROUNDED,
        style="cyan",
    )
    table.add_column("Pos", style="yellow", width=4)
    table.add_column("Driver", style="white")
    table.add_column("Team", style="dim")
    table.add_column("Lap Time", style="green")
    table.add_column("Gap", style="red")

    fastest_time = drivers[0]["lap_time_seconds"]
    for i, driver in enumerate(drivers[:20], 1):
        gap = driver["lap_time_seconds"] - fastest_time
        gap_str = f"+{gap:.3f}s" if gap > 0 else "---"
        table.add_row(
            str(i), driver["driver"], driver["team"], driver["lap_time"], gap_str
        )

    console.print(table)
    console.print()

    # Create choices for first driver
    driver_choices = [f"{d['driver']} - {d['team']} ({d['lap_time']})" for d in drivers]
    driver_choices.append("← Back")

    console.print(
        "[cyan]Select the FIRST driver (their color will be shown on track sections where they're faster):[/cyan]"
    )
    answer1 = questionary.select(
        "Driver 1:", choices=driver_choices, style=custom_style
    ).ask()

    if answer1 is None or "Back" in answer1:
        return None

    driver1 = answer1.split(" - ")[0]

    # Create choices for second driver (exclude first driver)
    driver_choices_2 = [c for c in driver_choices if not c.startswith(driver1)]

    console.print(
        f"\n[cyan]Select the SECOND driver to compare against {driver1}:[/cyan]"
    )
    answer2 = questionary.select(
        "Driver 2:", choices=driver_choices_2, style=custom_style
    ).ask()

    if answer2 is None or "Back" in answer2:
        return None

    driver2 = answer2.split(" - ")[0]

    # Get team info
    team1 = next((d["team"] for d in drivers if d["driver"] == driver1), None)
    team2 = next((d["team"] for d in drivers if d["driver"] == driver2), None)

    return (driver1, driver2, team1, team2)


def run_analysis(
    year: int,
    round_number: int,
    session_type: str,
    driver: Optional[str],
    viz_mode: str,
    event_name: str,
    session=None,
    ghost_drivers: Optional[tuple] = None,
):
    """Run the full analysis and display visualizations."""

    # Load session data if not provided
    if session is None:
        with Progress(
            SpinnerColumn(),
            TextColumn(
                "[cyan]Loading telemetry data (this may take a minute)...[/cyan]"
            ),
            console=console,
        ) as progress:
            progress.add_task("loading", total=None)
            session = load_session(year, round_number, session_type)

    # Handle ghost comparison mode separately
    if viz_mode == "ghost" and ghost_drivers:
        driver1, driver2, team1, team2 = ghost_drivers

        with Progress(
            SpinnerColumn(),
            TextColumn(f"[cyan]Loading telemetry for {driver1}...[/cyan]"),
            console=console,
        ) as progress:
            progress.add_task("loading", total=None)
            telemetry1 = get_lap_telemetry(session, driver1)

        with Progress(
            SpinnerColumn(),
            TextColumn(f"[cyan]Loading telemetry for {driver2}...[/cyan]"),
            console=console,
        ) as progress:
            progress.add_task("loading", total=None)
            telemetry2 = get_lap_telemetry(session, driver2)

        if telemetry1 is None or telemetry2 is None:
            console.print(
                "[red]Failed to load telemetry for one or both drivers.[/red]"
            )
            return

        # Load driving zones for both drivers (for corner info)
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Analyzing driving zones...[/cyan]"),
            console=console,
        ) as progress:
            progress.add_task("analyzing", total=None)
            zones1 = analyze_driving_zones(telemetry1)
            zones2 = analyze_driving_zones(telemetry2)

        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Analyzing lap comparison...[/cyan]"),
            console=console,
        ) as progress:
            progress.add_task("analyzing", total=None)
            comparison = analyze_lap_comparison(
                telemetry1, telemetry2, driver1, driver2, team1, team2, session
            )
            circuit_info = get_circuit_info(session)

        # Display comparison summary
        delta = comparison.total_delta
        faster = driver2 if delta > 0 else driver1

        summary_table = Table(
            title="👻 Ghost Comparison Analysis", box=box.ROUNDED, style="cyan"
        )
        summary_table.add_column("", style="white")
        summary_table.add_column(driver1, style="cyan")
        summary_table.add_column(driver2, style="magenta")

        min1 = int(comparison.driver1_time // 60)
        sec1 = comparison.driver1_time % 60
        min2 = int(comparison.driver2_time // 60)
        sec2 = comparison.driver2_time % 60

        summary_table.add_row(
            "Lap Time", f"{min1}:{sec1:06.3f}", f"{min2}:{sec2:06.3f}"
        )
        summary_table.add_row("Team", comparison.driver1_team, comparison.driver2_team)

        # Count segments where each driver is faster
        d1_segments = sum(1 for s in comparison.segments if s.faster_driver == 0)
        d2_segments = sum(1 for s in comparison.segments if s.faster_driver == 1)

        summary_table.add_row("Faster Segments", str(d1_segments), str(d2_segments))

        console.print(summary_table)
        console.print()

        delta_str = f"+{abs(delta):.3f}s" if delta != 0 else "0.000s"
        console.print(f"[green bold]🏆 {faster} is FASTER by {delta_str}[/green bold]")
        console.print()

        # Ask what to show
        viz_choices = [
            "📊 Show Summary Plot (static analysis)",
            "🎬 Start Ghost Replay Animation",
            "📊 + 🎬 Show Both",
            "← Back",
        ]

        viz_answer = questionary.select(
            "What would you like to see?", choices=viz_choices, style=custom_style
        ).ask()

        if viz_answer is None or "Back" in viz_answer:
            return

        title = f"{event_name} {year} - {driver1} vs {driver2} ({session_type})"
        rotation = circuit_info.get("rotation", 0)

        show_summary = "Summary" in viz_answer or "Both" in viz_answer
        show_replay = "Replay" in viz_answer or "Both" in viz_answer

        if show_summary:
            console.print("[cyan]Generating comparison summary plot...[/cyan]")
            fig = create_comparison_summary_plot(
                telemetry1, telemetry2, comparison, title=title, rotation=rotation
            )
            show_plot(fig)

        if show_replay:
            console.print("[cyan]Starting ghost comparison replay...[/cyan]")
            console.print(
                "[dim]Controls: Space=Play/Pause | R=Reset | ←→=Step | +/-=Speed[/dim]"
            )
            console.print(f"[dim]Track sections colored by who is faster:[/dim]")
            console.print(
                f"[dim]  • {comparison.driver1_color} = {driver1} faster[/dim]"
            )
            console.print(
                f"[dim]  • {comparison.driver2_color} = {driver2} faster[/dim]"
            )

            from ghost_comparison import GhostComparisonReplay

            replay = GhostComparisonReplay(
                telemetry1,
                telemetry2,
                comparison,
                session=session,
                zones1=zones1,
                zones2=zones2,
                title=title,
                rotation=rotation,
            )
            replay.show()

        return

    # Normal single-driver analysis
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Loading telemetry data...[/cyan]"),
        console=console,
    ) as progress:
        progress.add_task("loading", total=None)
        telemetry = get_lap_telemetry(session, driver)
        lap_info = get_fastest_lap_info(session) if not driver else None
        circuit_info = get_circuit_info(session)

    if telemetry is None:
        console.print("[red]Failed to load telemetry data.[/red]")
        return

    # Analyze driving zones
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]Analyzing driving zones...[/cyan]"),
        console=console,
    ) as progress:
        progress.add_task("analyzing", total=None)
        zones = analyze_driving_zones(telemetry)

    # Build title
    driver_name = driver if driver else (lap_info.driver if lap_info else "Unknown")
    title = f"{event_name} {year} - {driver_name} ({session_type})"

    # Display analysis summary
    summary_table = Table(title="📈 Analysis Summary", box=box.ROUNDED, style="green")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="white")

    summary_table.add_row("Driver", driver_name)
    summary_table.add_row("Lap Time", lap_info.lap_time if lap_info else "N/A")
    summary_table.add_row("Telemetry Points", f"{len(telemetry.speed):,}")
    summary_table.add_row("Corners Detected", str(len(zones.corner_zones)))
    summary_table.add_row("Braking Zones", str(len(zones.braking_zones)))
    summary_table.add_row("Full Throttle Zones", str(len(zones.full_throttle_zones)))
    summary_table.add_row("Max Speed", f"{telemetry.speed.max():.1f} km/h")
    summary_table.add_row("Min Speed", f"{telemetry.speed.min():.1f} km/h")

    console.print(summary_table)
    console.print()

    # Corner details
    if zones.corner_zones:
        corner_table = Table(title="🔄 Corner Analysis", box=box.SIMPLE, style="yellow")
        corner_table.add_column("Turn", style="cyan", width=6)
        corner_table.add_column("Entry", style="white")
        corner_table.add_column("Apex", style="green")
        corner_table.add_column("Exit", style="white")
        corner_table.add_column("Gear", style="yellow")

        for corner in zones.corner_zones[:15]:  # Show first 15 corners
            corner_table.add_row(
                f"T{corner['number']}",
                f"{corner['entry_speed']:.0f}",
                f"{corner['apex_speed']:.0f}",
                f"{corner['exit_speed']:.0f}",
                str(corner["apex_gear"]),
            )

        console.print(corner_table)
        console.print()

    # Generate and display visualizations
    rotation = circuit_info.get("rotation", 0)

    if viz_mode == "zones":
        console.print("[cyan]Generating track visualization...[/cyan]")
        fig = create_track_plot(telemetry, zones, title=title, rotation=rotation)
        show_plot(fig)

    elif viz_mode == "dashboard":
        console.print("[cyan]Generating telemetry dashboard...[/cyan]")
        fig = create_telemetry_dashboard(telemetry, zones, title=title)
        show_plot(fig)

    elif viz_mode == "speed":
        console.print("[cyan]Generating speed gradient map...[/cyan]")
        fig = create_track_plot(
            telemetry, zones, title=title, show_speed_gradient=True, rotation=rotation
        )
        show_plot(fig)

    elif viz_mode == "replay":
        console.print("[cyan]Starting animated lap replay...[/cyan]")
        console.print(
            "[dim]Controls: Space=Play/Pause | R=Reset | ←→=Step | +/-=Speed[/dim]"
        )

        # Get enhanced data for replay
        track_conditions = get_track_conditions(session, driver)
        enhanced_corners = get_enhanced_corners(session, telemetry, zones.corner_zones)

        if track_conditions:
            console.print(
                f"[dim]Track: {track_conditions.track_name} | "
                f"Tire: {track_conditions.tire_compound} | "
                f"Weather: {track_conditions.weather.get_condition_string()}[/dim]"
            )

        run_lap_replay(
            telemetry=telemetry,
            zones=zones,
            track_conditions=track_conditions,
            enhanced_corners=enhanced_corners,
            title=title,
            rotation=rotation,
        )

    elif viz_mode == "save_all":
        console.print("[cyan]Generating and saving all visualizations...[/cyan]")

        # Create safe filename
        safe_name = (
            f"{year}_{event_name.replace(' ', '_')}_{session_type}_{driver_name}"
        )

        fig1 = create_track_plot(telemetry, zones, title=title, rotation=rotation)
        save_plot(fig1, f"{safe_name}_zones.png")

        fig2 = create_telemetry_dashboard(telemetry, zones, title=title)
        save_plot(fig2, f"{safe_name}_dashboard.png")

        fig3 = create_track_plot(
            telemetry, zones, title=title, show_speed_gradient=True, rotation=rotation
        )
        save_plot(fig3, f"{safe_name}_speed.png")

        console.print(
            f"[green]✓ Saved 3 visualizations with prefix: {safe_name}[/green]"
        )


def main():
    """Main application loop."""
    display_banner()

    console.print("[dim]Tip: Use arrow keys to navigate, Enter to select[/dim]\n")

    while True:
        # Season selection
        year = select_season()
        if year is None:
            console.print("\n[cyan]Thanks for using F1 Driving Assistant! 👋[/cyan]")
            sys.exit(0)

        while True:
            # Event selection
            event = select_event(year)
            if event is None:
                break  # Back to season selection

            while True:
                # Session selection
                session_type = select_session(
                    year, event["round_number"], event["event_name"]
                )
                if session_type is None:
                    break  # Back to event selection

                # Load session for driver selection
                console.print()
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[cyan]Loading session...[/cyan]"),
                    console=console,
                ) as progress:
                    progress.add_task("loading", total=None)
                    session = load_session(year, event["round_number"], session_type)

                while True:
                    # Driver selection
                    driver = select_driver(session, event["event_name"])
                    if driver == "BACK":
                        break  # Back to session selection

                    while True:
                        # Visualization selection
                        viz_mode = select_visualization_mode()
                        if viz_mode == "BACK":
                            break  # Back to driver selection

                        # Handle ghost comparison mode - need to select second driver
                        ghost_drivers = None
                        if viz_mode == "ghost":
                            ghost_drivers = select_two_drivers(
                                session, event["event_name"]
                            )
                            if ghost_drivers is None:
                                continue  # Back to visualization selection

                        # Run analysis
                        run_analysis(
                            year=year,
                            round_number=event["round_number"],
                            session_type=session_type,
                            driver=driver,
                            viz_mode=viz_mode,
                            event_name=event["event_name"],
                            session=session,
                            ghost_drivers=ghost_drivers,
                        )

                        # Ask if user wants another visualization
                        if not questionary.confirm(
                            "Generate another visualization?", style=custom_style
                        ).ask():
                            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[cyan]Interrupted. Goodbye! 👋[/cyan]")
        sys.exit(0)
