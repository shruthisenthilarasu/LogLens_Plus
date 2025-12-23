"""
Main CLI interface for LogLens++.

Provides a command-line interface for ingesting logs, querying metrics,
and detecting anomalies.
"""

import json
import sys
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timedelta

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from loglens.ingestion import LogIngestor
from loglens.storage import LogStorage, create_query
from loglens.analytics import (
    MetricProcessor,
    Metric,
    AnomalyDetector,
    create_detector,
    create_multi_detector,
)
from loglens.utils.config import load_config, create_default_config, LogLensConfig

app = typer.Typer(
    name="loglens",
    help="LogLens++ - Streaming log analytics engine",
    add_completion=False,
)
console = Console()

# Default database path
DEFAULT_DB = "loglens.db"


@app.command()
def ingest(
    logfile: Path = typer.Argument(..., help="Path to log file"),
    db: Optional[str] = typer.Option(None, "--db", "-d", help="Database file path"),
    format: Optional[str] = typer.Option(None, "--format", "-f", help="Log format (json/text/auto)"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Default source name"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config file"),
):
    """
    Ingest logs from a file into the database.
    
    Examples:
        loglens ingest app.log
        loglens ingest app.log --format json
        loglens ingest app.log --source myapp
        loglens ingest app.log --config config.yaml
    """
    if not logfile.exists():
        console.print(f"[red]Error:[/red] Log file not found: {logfile}")
        raise typer.Exit(1)
    
    # Load config if provided
    config_obj = None
    if config:
        try:
            config_obj = load_config(config)
        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] Could not load config: {e}")
    else:
        try:
            config_obj = load_config()
        except:
            pass  # Use defaults
    
    # Use config values or provided values
    db_path = db or (config_obj.storage.db_path if config_obj else DEFAULT_DB)
    default_source = source or (config_obj.default_source if config_obj else "unknown")
    
    console.print(f"[bold]Ingesting logs from:[/bold] {logfile}")
    
    try:
        # Create storage
        storage = LogStorage(db_path)
        
        # Create ingestor
        ingestor = LogIngestor(default_source=default_source)
        
        # Ingest file
        event_count = 0
        with console.status("[bold green]Processing logs..."):
            for event in ingestor.ingest_file(logfile, format=format):
                storage.insert_event(event)
                event_count += 1
        
        # Process metrics if config provided
        if config_obj and config_obj.metrics:
            console.print(f"[bold]Computing metrics...[/bold]")
            metrics = config_obj.to_metrics()
            processor = MetricProcessor(metrics)
            
            # Process events as they're ingested (already done above)
            # Re-process the file to compute metrics
            metric_count = 0
            for event in ingestor.ingest_file(logfile, format=format):
                updated = processor.add_event(event)
                for metric_name, result in updated.items():
                    storage.insert_metric(
                        metric_name=result.metric_name,
                        window_start=result.window_start,
                        window_end=result.window_end,
                        value=result.value,
                        grouped_values=result.grouped_values
                    )
                    metric_count += 1
            
            console.print(f"[green]✓[/green] Computed {metric_count} metric values")
        
        storage.close()
        
        console.print(f"[green]✓[/green] Ingested {event_count} events into {db_path}")
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def metrics(
    action: str = typer.Argument(..., help="Action: list, show, or define"),
    metric_name: Optional[str] = typer.Argument(None, help="Metric name (for show action)"),
    db: str = typer.Option(DEFAULT_DB, "--db", "-d", help="Database file path"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of results to show"),
):
    """
    Manage and view metrics.
    
    Actions:
        list    - List all stored metrics
        show    - Show details for a specific metric
    
    Examples:
        loglens metrics list
        loglens metrics show error_count
        loglens metrics show error_count --limit 20
    """
    if not Path(db).exists():
        console.print(f"[red]Error:[/red] Database not found: {db}")
        raise typer.Exit(1)
    
    storage = LogStorage(db)
    query = create_query(storage)
    
    try:
        if action == "list":
            # List all unique metric names
            sql = """
                SELECT DISTINCT metric_name, COUNT(*) as count,
                       MIN(window_start) as first_seen,
                       MAX(window_end) as last_seen
                FROM metrics
                GROUP BY metric_name
                ORDER BY metric_name
            """
            results = query.execute_sql(sql)
            
            if not results:
                console.print("[yellow]No metrics found in database[/yellow]")
                return
            
            table = Table(title="Stored Metrics")
            table.add_column("Metric Name", style="cyan")
            table.add_column("Count", justify="right", style="green")
            table.add_column("First Seen", style="blue")
            table.add_column("Last Seen", style="blue")
            
            for row in results:
                first_seen = datetime.fromisoformat(str(row['first_seen'])).strftime('%Y-%m-%d %H:%M')
                last_seen = datetime.fromisoformat(str(row['last_seen'])).strftime('%Y-%m-%d %H:%M')
                table.add_row(
                    row['metric_name'],
                    str(row['count']),
                    first_seen,
                    last_seen
                )
            
            console.print(table)
        
        elif action == "show":
            if not metric_name:
                console.print("[red]Error:[/red] Metric name required for 'show' action")
                raise typer.Exit(1)
            
            # Get recent values for the metric
            metrics_list = storage.query_metrics(
                metric_name=metric_name,
                limit=limit
            )
            
            if not metrics_list:
                console.print(f"[yellow]No metrics found for: {metric_name}[/yellow]")
                return
            
            table = Table(title=f"Metric: {metric_name}")
            table.add_column("Window Start", style="blue")
            table.add_column("Window End", style="blue")
            table.add_column("Value", justify="right", style="green")
            table.add_column("Grouped Values", style="cyan")
            
            for m in metrics_list:
                start = datetime.fromisoformat(str(m['window_start'])).strftime('%Y-%m-%d %H:%M:%S')
                end = datetime.fromisoformat(str(m['window_end'])).strftime('%Y-%m-%d %H:%M:%S')
                value = str(m['value']) if m['value'] is not None else "N/A"
                grouped = json.dumps(m['grouped_values']) if m['grouped_values'] else "N/A"
                
                table.add_row(start, end, value, grouped)
            
            console.print(table)
        
        else:
            console.print(f"[red]Error:[/red] Unknown action: {action}")
            console.print("Available actions: list, show")
            raise typer.Exit(1)
    
    finally:
        storage.close()


@app.command()
def query(
    sql: str = typer.Argument(..., help="SQL query to execute"),
    db: str = typer.Option(DEFAULT_DB, "--db", "-d", help="Database file path"),
    format: str = typer.Option("table", "--format", "-f", help="Output format (table/json)"),
):
    """
    Execute a SQL query against the database.
    
    Examples:
        loglens query "SELECT * FROM events LIMIT 10"
        loglens query "SELECT metric_name, AVG(value) FROM metrics GROUP BY metric_name"
        loglens query "SELECT * FROM events WHERE level = 'ERROR'" --format json
    """
    if not Path(db).exists():
        console.print(f"[red]Error:[/red] Database not found: {db}")
        raise typer.Exit(1)
    
    storage = LogStorage(db)
    query_interface = create_query(storage)
    
    try:
        results = query_interface.execute_sql(sql)
        
        if not results:
            console.print("[yellow]No results[/yellow]")
            return
        
        if format == "json":
            # JSON output
            console.print(json.dumps(results, indent=2, default=str))
        else:
            # Table output
            if not results:
                console.print("[yellow]No results[/yellow]")
                return
            
            table = Table()
            # Add columns
            for key in results[0].keys():
                table.add_column(key, style="cyan")
            
            # Add rows
            for row in results:
                table.add_row(*[str(v) for v in row.values()])
            
            console.print(table)
            console.print(f"\n[dim]{len(results)} row(s)[/dim]")
    
    except Exception as e:
        console.print(f"[red]Error executing query:[/red] {e}")
        raise typer.Exit(1)
    
    finally:
        storage.close()


@app.command()
def anomalies(
    metric_name: Optional[str] = typer.Option(None, "--metric", "-m", help="Specific metric to check"),
    db: Optional[str] = typer.Option(None, "--db", "-d", help="Database file path"),
    window: Optional[int] = typer.Option(None, "--window", "-w", help="Rolling window size"),
    threshold: Optional[float] = typer.Option(None, "--threshold", "-t", help="Z-score threshold"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of recent values to check"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config file"),
):
    """
    Detect anomalies in stored metrics.
    
    Examples:
        loglens anomalies
        loglens anomalies --metric error_count
        loglens anomalies --metric error_count --threshold 2.5
        loglens anomalies --config config.yaml
    """
    # Load config if provided
    config_obj = None
    if config:
        try:
            config_obj = load_config(config)
        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] Could not load config: {e}")
    else:
        try:
            config_obj = load_config()
        except:
            pass  # Use defaults
    
    # Use config values or provided values
    db_path = db or (config_obj.storage.db_path if config_obj else DEFAULT_DB)
    
    if not Path(db_path).exists():
        console.print(f"[red]Error:[/red] Database not found: {db_path}")
        raise typer.Exit(1)
    
    storage = LogStorage(db_path)
    query_interface = create_query(storage)
    
    try:
        # Get metrics to check
        if metric_name:
            metric_names = [metric_name]
        else:
            # Get all unique metric names
            sql = "SELECT DISTINCT metric_name FROM metrics"
            results = query_interface.execute_sql(sql)
            metric_names = [row['metric_name'] for row in results]
        
        if not metric_names:
            console.print("[yellow]No metrics found in database[/yellow]")
            return
        
        all_anomalies = []
        
        # Get anomaly configs from config file
        anomaly_configs = {}
        if config_obj:
            anomaly_configs = {a.metric_name: a for a in config_obj.anomalies if a.enabled}
        
        for mname in metric_names:
            # Get recent metric values
            metrics_list = storage.query_metrics(
                metric_name=mname,
                limit=limit * 2  # Get more to build baseline
            )
            
            if len(metrics_list) < 5:
                continue  # Need at least 5 samples
            
            # Get detector config from config file or use defaults
            if mname in anomaly_configs:
                anomaly_config = anomaly_configs[mname]
                detector_window = window or anomaly_config.window_size
                detector_threshold = threshold or anomaly_config.threshold
            else:
                detector_window = window or 20
                detector_threshold = threshold or 2.0
            
            # Create detector
            detector = create_detector(
                metric_name=mname,
                window_size=detector_window,
                threshold=detector_threshold
            )
            
            # Build baseline and detect anomalies
            for m in reversed(metrics_list):  # Process chronologically
                value = m['value']
                if value is None:
                    continue
                
                window_start = datetime.fromisoformat(str(m['window_start']))
                anomaly = detector.add_value(value, window_start)
                
                if anomaly:
                    all_anomalies.append(anomaly)
        
        if not all_anomalies:
            console.print("[green]✓[/green] No anomalies detected")
            return
        
        # Display anomalies
        console.print(f"\n[bold red]🚨 Detected {len(all_anomalies)} anomaly(ies):[/bold red]\n")
        
        table = Table(title="Anomalies")
        table.add_column("Metric", style="cyan")
        table.add_column("Timestamp", style="blue")
        table.add_column("Explanation", style="yellow")
        table.add_column("Severity", justify="center")
        
        # Sort by severity and timestamp
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        all_anomalies.sort(key=lambda a: (severity_order.get(a.severity, 99), a.timestamp))
        
        for anomaly in all_anomalies[:limit]:
            severity_color = {
                "critical": "bold red",
                "high": "red",
                "medium": "yellow",
                "low": "dim"
            }.get(anomaly.severity, "white")
            
            table.add_row(
                anomaly.metric_name,
                anomaly.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                anomaly.explanation,
                f"[{severity_color}]{anomaly.severity.upper()}[/{severity_color}]"
            )
        
        console.print(table)
    
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    
    finally:
        storage.close()


@app.command()
def stats(
    db: str = typer.Option(DEFAULT_DB, "--db", "-d", help="Database file path"),
    hours: int = typer.Option(24, "--hours", "-h", help="Time range in hours"),
):
    """
    Show database statistics.
    
    Examples:
        loglens stats
        loglens stats --hours 48
    """
    if not Path(db).exists():
        console.print(f"[red]Error:[/red] Database not found: {db}")
        raise typer.Exit(1)
    
    storage = LogStorage(db)
    
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        # Get event stats
        event_stats = storage.get_event_stats(start_time=start_time, end_time=end_time)
        
        # Get metric stats
        query_interface = create_query(storage)
        metric_sql = """
            SELECT COUNT(DISTINCT metric_name) as metric_count,
                   COUNT(*) as metric_values
            FROM metrics
            WHERE window_start >= ? AND window_end <= ?
        """
        metric_results = query_interface.execute_sql(
            metric_sql,
            (start_time, end_time)
        )
        metric_stats = metric_results[0] if metric_results else {}
        
        # Display stats
        console.print(Panel.fit(
            f"[bold]Database Statistics[/bold]\n\n"
            f"[cyan]Time Range:[/cyan] {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"[bold]Events:[/bold]\n"
            f"  Total: {event_stats['total_events']}\n"
            f"  By Level: {event_stats['by_level']}\n"
            f"  By Source: {event_stats['by_source']}\n\n"
            f"[bold]Metrics:[/bold]\n"
            f"  Unique Metrics: {metric_stats.get('metric_count', 0)}\n"
            f"  Total Values: {metric_stats.get('metric_values', 0)}",
            title="LogLens++ Stats",
            border_style="blue"
        ))
    
    finally:
        storage.close()


@app.command()
def config(
    action: str = typer.Argument(..., help="Action: init (create default config)"),
    path: Path = typer.Option("loglens.yaml", "--path", "-p", help="Config file path"),
):
    """
    Manage configuration files.
    
    Actions:
        init    - Create a default configuration file
    
    Examples:
        loglens config init
        loglens config init --path myconfig.yaml
    """
    if action == "init":
        try:
            create_default_config(path)
            console.print(f"[green]✓[/green] Created default configuration at: {path}")
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
    else:
        console.print(f"[red]Error:[/red] Unknown action: {action}")
        console.print("Available actions: init")
        raise typer.Exit(1)


def main():
    """Main entry point for CLI."""
    app()


if __name__ == "__main__":
    main()

