#!/usr/bin/env python3
"""
Example demonstrating the storage layer.

This example shows how to:
1. Store log events efficiently
2. Store aggregated metrics
3. Query events and metrics
4. Get statistics and summaries
"""

from datetime import datetime, timedelta
from loglens.models import LogEvent
from loglens.storage import LogStorage
from loglens.analytics import Metric, MetricProcessor


def main():
    """Demonstrate storage functionality."""
    
    # Create storage instance
    storage = LogStorage("example_logs.db")
    
    print("=" * 70)
    print("LogLens++ Storage Example")
    print("=" * 70)
    
    # 1. Store events
    print("\n1. Storing Log Events")
    print("-" * 70)
    
    base_time = datetime(2024, 1, 1, 12, 0, 0)
    events = [
        LogEvent(
            timestamp=base_time + timedelta(seconds=i*30),
            level=('INFO', 'WARNING', 'ERROR')[i % 3],
            source=f'app{i%2+1}',
            message=f'Request {i} processed',
            metadata={'request_id': f'req_{i}', 'duration_ms': 100 + i*10}
        )
        for i in range(15)
    ]
    
    # Batch insert
    event_ids = storage.insert_events(events)
    print(f"  Stored {len(event_ids)} events")
    
    # 2. Query events
    print("\n2. Querying Events")
    print("-" * 70)
    
    # Get all error events
    error_events = storage.query_events(level='ERROR', limit=5)
    print(f"  Error events (last 5):")
    for event in error_events:
        print(f"    - {event['timestamp'].strftime('%H:%M:%S')}: "
              f"{event['source']} - {event['message']}")
    
    # Get events in time range
    start = base_time + timedelta(minutes=2)
    end = base_time + timedelta(minutes=5)
    range_events = storage.query_events(start_time=start, end_time=end)
    print(f"\n  Events between {start.strftime('%H:%M')} and {end.strftime('%H:%M')}: "
          f"{len(range_events)}")
    
    # 3. Compute and store metrics
    print("\n3. Computing and Storing Metrics")
    print("-" * 70)
    
    # Define metrics
    metrics_def = [
        Metric(
            name='error_count',
            filter=lambda e: e.level == 'ERROR',
            aggregation='count',
            window='5m'
        ),
        Metric(
            name='events_by_source',
            filter=lambda e: True,
            aggregation='count',
            window='5m',
            group_by=lambda e: e.source
        ),
    ]
    
    processor = MetricProcessor(metrics_def)
    
    # Process events and store metrics
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
    
    print("  Metrics computed and stored")
    
    # 4. Query metrics
    print("\n4. Querying Metrics")
    print("-" * 70)
    
    stored_metrics = storage.query_metrics(metric_name='error_count')
    print(f"  Stored error_count metrics: {len(stored_metrics)}")
    if stored_metrics:
        latest = stored_metrics[0]
        print(f"    Latest: {latest['value']} errors in window "
              f"{latest['window_start'].strftime('%H:%M')} - "
              f"{latest['window_end'].strftime('%H:%M')}")
    
    # 5. Get statistics
    print("\n5. Event Statistics")
    print("-" * 70)
    
    stats = storage.get_event_stats()
    print(f"  Total events: {stats['total_events']}")
    print(f"  By level: {stats['by_level']}")
    print(f"  By source: {stats['by_source']}")
    
    # 6. Metric summaries
    print("\n6. Metric Summaries")
    print("-" * 70)
    
    summary = storage.get_metric_summary('error_count')
    print(f"  Error count summary:")
    print(f"    Count: {summary['count']}")
    print(f"    Average: {summary['avg']:.2f}" if summary['avg'] else "    Average: N/A")
    print(f"    Min: {summary['min']}" if summary['min'] is not None else "    Min: N/A")
    print(f"    Max: {summary['max']}" if summary['max'] is not None else "    Max: N/A")
    
    # 7. Cleanup example (data retention)
    print("\n7. Data Retention")
    print("-" * 70)
    
    # Delete events older than 1 hour
    cutoff = datetime.now() - timedelta(hours=1)
    deleted = storage.delete_old_events(cutoff)
    print(f"  Deleted {deleted} old events (older than 1 hour)")
    
    remaining = storage.query_events()
    print(f"  Remaining events: {len(remaining)}")
    
    storage.close()
    
    print("\n" + "=" * 70)
    print("Example complete! Database saved to: example_logs.db")
    print("=" * 70)


if __name__ == "__main__":
    main()

