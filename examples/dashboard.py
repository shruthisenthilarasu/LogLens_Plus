#!/usr/bin/env python3
"""
LogLens++ Dashboard Example

Creates a matplotlib-based dashboard showing metrics, trends, and anomalies.
This demonstrates how to visualize LogLens++ data.
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

from loglens.models import LogEvent
from loglens.storage import LogStorage, create_query
from loglens.analytics import Metric, MetricProcessor


def create_dashboard(db_path: str = "loglens.db", output_file: str = "dashboard.png"):
    """
    Create a dashboard visualization from LogLens++ data.
    
    Args:
        db_path: Path to database
        output_file: Output file for dashboard image
    """
    storage = LogStorage(db_path)
    query = create_query(storage)
    
    # Get time range (last 24 hours)
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=24)
    
    # Create figure with subplots
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
    
    # 1. Error Rate Over Time (top, full width)
    ax1 = fig.add_subplot(gs[0, :])
    plot_error_rate_trend(query, ax1, start_time, end_time)
    
    # 2. Events by Level (pie chart)
    ax2 = fig.add_subplot(gs[1, 0])
    plot_events_by_level(storage, ax2, start_time, end_time)
    
    # 3. Events by Source (bar chart)
    ax3 = fig.add_subplot(gs[1, 1])
    plot_events_by_source(storage, ax3, start_time, end_time)
    
    # 4. Error Rate by Source (bar chart)
    ax4 = fig.add_subplot(gs[1, 2])
    plot_error_rate_by_source(query, ax4, start_time, end_time)
    
    # 5. Metric Trends (line chart)
    ax5 = fig.add_subplot(gs[2, :])
    plot_metric_trends(query, ax5, start_time, end_time)
    
    # Add title
    fig.suptitle('LogLens++ Dashboard', fontsize=16, fontweight='bold', y=0.995)
    
    # Save to examples directory if not absolute path
    if not Path(output_file).is_absolute():
        output_path = Path(__file__).parent / output_file
    else:
        output_path = Path(output_file)
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Dashboard saved to: {output_path}")
    plt.close()


def plot_error_rate_trend(query, ax, start_time, end_time):
    """Plot error rate trend over time."""
    sql = """
        SELECT 
            DATE_TRUNC('hour', timestamp) AS hour,
            COUNT(*) AS total_events,
            COUNT(CASE WHEN level IN ('ERROR', 'CRITICAL', 'FATAL') THEN 1 END) AS error_count,
            CAST(COUNT(CASE WHEN level IN ('ERROR', 'CRITICAL', 'FATAL') THEN 1 END) AS DOUBLE) / 
                NULLIF(COUNT(*), 0) * 100.0 AS error_rate
        FROM events
        WHERE timestamp >= ? AND timestamp <= ?
        GROUP BY hour
        ORDER BY hour
    """
    
    results = query.execute_sql(sql, (start_time, end_time))
    
    if not results:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Error Rate Over Time', fontweight='bold')
        return
    
    hours = [datetime.fromisoformat(str(r['hour'])) for r in results]
    error_rates = [r['error_rate'] for r in results]
    
    ax.plot(hours, error_rates, marker='o', linewidth=2, markersize=6, color='#e74c3c')
    ax.fill_between(hours, error_rates, alpha=0.3, color='#e74c3c')
    ax.set_title('Error Rate Over Time', fontweight='bold', fontsize=12)
    ax.set_xlabel('Time')
    ax.set_ylabel('Error Rate (%)')
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')


def plot_events_by_level(storage, ax, start_time, end_time):
    """Plot events distribution by log level."""
    stats = storage.get_event_stats(start_time=start_time, end_time=end_time)
    
    if not stats['by_level']:
        ax.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Events by Level', fontweight='bold')
        return
    
    levels = list(stats['by_level'].keys())
    counts = list(stats['by_level'].values())
    
    # Color mapping
    colors = {
        'ERROR': '#e74c3c',
        'WARNING': '#f39c12',
        'INFO': '#3498db',
        'DEBUG': '#95a5a6',
        'CRITICAL': '#8e44ad',
        'FATAL': '#c0392b'
    }
    
    pie_colors = [colors.get(level, '#95a5a6') for level in levels]
    
    ax.pie(counts, labels=levels, autopct='%1.1f%%', colors=pie_colors, startangle=90)
    ax.set_title('Events by Level', fontweight='bold', fontsize=12)


def plot_events_by_source(storage, ax, start_time, end_time):
    """Plot events count by source."""
    stats = storage.get_event_stats(start_time=start_time, end_time=end_time)
    
    if not stats['by_source']:
        ax.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Events by Source', fontweight='bold')
        return
    
    # Get top 10 sources
    sources = sorted(stats['by_source'].items(), key=lambda x: x[1], reverse=True)[:10]
    source_names = [s[0] for s in sources]
    source_counts = [s[1] for s in sources]
    
    ax.barh(source_names, source_counts, color='#3498db')
    ax.set_title('Top Sources by Event Count', fontweight='bold', fontsize=12)
    ax.set_xlabel('Event Count')
    ax.grid(True, alpha=0.3, axis='x')


def plot_error_rate_by_source(query, ax, start_time, end_time):
    """Plot error rate by source."""
    sql = """
        SELECT 
            source,
            COUNT(*) AS total_events,
            COUNT(CASE WHEN level IN ('ERROR', 'CRITICAL', 'FATAL') THEN 1 END) AS error_count,
            CAST(COUNT(CASE WHEN level IN ('ERROR', 'CRITICAL', 'FATAL') THEN 1 END) AS DOUBLE) / 
                NULLIF(COUNT(*), 0) * 100.0 AS error_rate
        FROM events
        WHERE timestamp >= ? AND timestamp <= ?
        GROUP BY source
        HAVING error_count > 0
        ORDER BY error_rate DESC
        LIMIT 10
    """
    
    results = query.execute_sql(sql, (start_time, end_time))
    
    if not results:
        ax.text(0.5, 0.5, 'No errors', ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Error Rate by Source', fontweight='bold')
        return
    
    sources = [r['source'] for r in results]
    error_rates = [r['error_rate'] for r in results]
    
    colors = ['#e74c3c' if rate > 10 else '#f39c12' if rate > 5 else '#f1c40f' for rate in error_rates]
    
    ax.barh(sources, error_rates, color=colors)
    ax.set_title('Error Rate by Source (%)', fontweight='bold', fontsize=12)
    ax.set_xlabel('Error Rate (%)')
    ax.grid(True, alpha=0.3, axis='x')


def plot_metric_trends(query, ax, start_time, end_time):
    """Plot multiple metric trends."""
    sql = """
        SELECT 
            DATE_TRUNC('hour', window_start) AS hour,
            metric_name,
            AVG(value) AS avg_value
        FROM metrics
        WHERE window_start >= ? AND window_end <= ?
        AND value IS NOT NULL
        GROUP BY hour, metric_name
        ORDER BY hour, metric_name
    """
    
    results = query.execute_sql(sql, (start_time, end_time))
    
    if not results:
        ax.text(0.5, 0.5, 'No metrics available', ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Metric Trends', fontweight='bold')
        return
    
    # Group by metric name
    metric_data = defaultdict(list)
    for r in results:
        hour = datetime.fromisoformat(str(r['hour']))
        metric_data[r['metric_name']].append((hour, r['avg_value']))
    
    # Plot each metric
    colors = plt.cm.tab10(np.linspace(0, 1, len(metric_data)))
    for (metric_name, data), color in zip(metric_data.items(), colors):
        hours, values = zip(*sorted(data))
        ax.plot(hours, values, marker='o', label=metric_name, linewidth=2, color=color)
    
    ax.set_title('Metric Trends Over Time', fontweight='bold', fontsize=12)
    ax.set_xlabel('Time')
    ax.set_ylabel('Metric Value')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')


def generate_sample_data(db_path: str = "dashboard_demo.db"):
    """Generate sample data for dashboard demonstration."""
    from loglens.ingestion import LogIngestor
    
    storage = LogStorage(db_path)
    ingestor = LogIngestor()
    
    # Generate events over last 24 hours
    base_time = datetime.now() - timedelta(hours=24)
    events = []
    
    for hour in range(24):
        for minute in [0, 15, 30, 45]:
            timestamp = base_time + timedelta(hours=hour, minutes=minute)
            
            # Vary error rate (higher during "business hours")
            error_prob = 0.1 if 9 <= hour <= 17 else 0.05
            level = 'ERROR' if np.random.random() < error_prob else \
                   'WARNING' if np.random.random() < 0.2 else 'INFO'
            
            source = f'app{np.random.randint(1, 4)}'
            
            events.append(LogEvent(
                timestamp=timestamp,
                level=level,
                source=source,
                message=f'Event at {timestamp.strftime("%H:%M")}',
                metadata={'request_id': f'req_{hour}_{minute}'}
            ))
    
    # Insert events
    for event in events:
        storage.insert_event(event)
    
    # Compute and store metrics
    metrics = [
        Metric(name='error_count', filter=lambda e: e.level == 'ERROR',
               aggregation='count', window='1h'),
        Metric(name='events_by_source', filter=lambda e: True,
               aggregation='count', window='1h', group_by=lambda e: e.source),
    ]
    
    processor = MetricProcessor(metrics)
    for event in events:
        updated = processor.add_event(event)
        for metric_name, result in updated.items():
            storage.insert_metric(
                metric_name=result.metric_name,
                window_start=result.window_start,
                window_end=result.window_end,
                value=result.value,
                grouped_values=result.grouped_values
            )
    
    storage.close()
    print(f"Generated sample data in {db_path}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--generate-data":
        generate_sample_data()
        create_dashboard("dashboard_demo.db", "dashboard.png")
    else:
        # Try to use existing database
        try:
            create_dashboard()
        except Exception as e:
            print(f"Error: {e}")
            print("Run with --generate-data to create sample data first")
            print("Example: python dashboard.py --generate-data")

