#!/usr/bin/env python3
"""
BI-Style SQL Query Examples

This example demonstrates SQL-style querying capabilities that make
BI analysts light up! Showcases time bucketing, aggregations, and
complex analytical queries.
"""

from datetime import datetime, timedelta
from loglens.models import LogEvent
from loglens.storage import LogStorage, create_query, TimeBucket
from loglens.analytics import Metric, MetricProcessor


def main():
    """Demonstrate BI-style SQL queries."""
    
    print("=" * 70)
    print("LogLens++ BI-Style SQL Query Examples")
    print("=" * 70)
    
    # Setup: Create storage and populate with data
    storage = LogStorage("bi_example.db")
    
    print("\n1. Setting up sample data...")
    print("-" * 70)
    
    # Generate sample events over 7 days
    base_time = datetime(2024, 1, 1, 0, 0, 0)
    events = []
    
    for day in range(7):
        for hour in range(24):
            for minute in [0, 30]:  # Every 30 minutes
                timestamp = base_time + timedelta(days=day, hours=hour, minutes=minute)
                level = ('INFO', 'WARNING', 'ERROR')[hour % 3]
                source = f'app{(day + hour) % 3 + 1}'
                
                events.append(LogEvent(
                    timestamp=timestamp,
                    level=level,
                    source=source,
                    message=f'Event at {timestamp.strftime("%Y-%m-%d %H:%M")}',
                    metadata={'request_id': f'req_{day}_{hour}_{minute}'}
                ))
    
    # Batch insert
    storage.insert_events(events)
    print(f"  Inserted {len(events)} events")
    
    # Compute and store metrics
    metrics_def = [
        Metric(name='error_count', filter=lambda e: e.level == 'ERROR',
               aggregation='count', window='1h'),
        Metric(name='events_by_source', filter=lambda e: True,
               aggregation='count', window='1h', group_by=lambda e: e.source),
    ]
    
    processor = MetricProcessor(metrics_def)
    for event in events[:100]:  # Process subset for demo
        updated = processor.add_event(event)
        for metric_name, result in updated.items():
            storage.insert_metric(
                metric_name=result.metric_name,
                window_start=result.window_start,
                window_end=result.window_end,
                value=result.value,
                grouped_values=result.grouped_values
            )
    
    print("  Computed and stored metrics")
    
    # Create query interface
    query = create_query(storage)
    
    # Example 1: Error rates by time bucket (hourly)
    print("\n2. Error Rates by Time Bucket (Hourly)")
    print("-" * 70)
    error_rates = query.query_metrics_by_time_bucket(
        metric_name='error_count',
        bucket_size=TimeBucket.HOUR,
        start_time=base_time,
        end_time=base_time + timedelta(days=1),
        aggregation='AVG'
    )
    
    print(f"  Found {len(error_rates)} hourly buckets")
    print("  Sample results:")
    for result in error_rates[:5]:
        print(f"    {result['bucket_time']}: {result['metric_value']:.2f} errors "
              f"({result['sample_count']} samples)")
    
    # Example 2: Top sources by event count
    print("\n3. Top Sources by Event Count")
    print("-" * 70)
    top_sources = query.query_top_sources(
        start_time=base_time,
        end_time=base_time + timedelta(days=7),
        limit=10,
        by='event_count'
    )
    
    print(f"  Top {len(top_sources)} sources:")
    for source in top_sources:
        print(f"    {source['source']}: {source['event_count']} events, "
              f"{source['error_count']} errors, {source['warning_count']} warnings")
    
    # Example 3: Error rate by source and time bucket
    print("\n4. Error Rate by Source and Time Bucket")
    print("-" * 70)
    error_by_source = query.query_error_rate_by_source(
        start_time=base_time,
        end_time=base_time + timedelta(days=1),
        bucket_size=TimeBucket.HOUR
    )
    
    print(f"  Found {len(error_by_source)} results")
    print("  Sample results:")
    for result in error_by_source[:5]:
        print(f"    {result['bucket_time']} | {result['source']}: "
              f"{result['error_rate']:.2f}% error rate "
              f"({result['error_count']}/{result['total_events']} errors)")
    
    # Example 4: Custom SQL query - Complex aggregation
    print("\n5. Custom SQL Query - Daily Error Trends")
    print("-" * 70)
    custom_sql = """
        SELECT 
            DATE_TRUNC('day', timestamp) AS day,
            source,
            COUNT(*) AS total_events,
            COUNT(CASE WHEN level = 'ERROR' THEN 1 END) AS error_count,
            COUNT(CASE WHEN level = 'WARNING' THEN 1 END) AS warning_count,
            CAST(COUNT(CASE WHEN level = 'ERROR' THEN 1 END) AS DOUBLE) / 
                NULLIF(COUNT(*), 0) * 100.0 AS error_rate
        FROM events
        WHERE timestamp >= ? AND timestamp <= ?
        GROUP BY day, source
        ORDER BY day, error_rate DESC
    """
    
    custom_results = query.query_custom(
        custom_sql,
        (base_time, base_time + timedelta(days=3))
    )
    
    print(f"  Found {len(custom_results)} daily aggregates")
    print("  Sample results:")
    for result in custom_results[:5]:
        print(f"    {result['day']} | {result['source']}: "
              f"{result['error_rate']:.2f}% error rate "
              f"({result['error_count']} errors, {result['total_events']} total)")
    
    # Example 6: Metric trends over time
    print("\n6. Metric Trends Over Time")
    print("-" * 70)
    trends = query.query_metrics_trend(
        metric_name='error_count',
        start_time=base_time,
        end_time=base_time + timedelta(days=1),
        bucket_size=TimeBucket.HOUR
    )
    
    print(f"  Found {len(trends)} trend points")
    print("  Trend (first 5 hours):")
    for trend in trends[:5]:
        print(f"    {trend['bucket_time']}: {trend['metric_value']:.2f} "
              f"({trend['sample_count']} samples)")
    
    # Example 7: Grouped metrics query
    print("\n7. Grouped Metrics (Events by Source)")
    print("-" * 70)
    grouped = query.query_grouped_metrics(
        metric_name='events_by_source',
        start_time=base_time,
        end_time=base_time + timedelta(days=1)
    )
    
    print(f"  Found {len(grouped)} grouped metric values")
    print("  Sample results:")
    for result in grouped[:5]:
        print(f"    {result['window_start']} | {result['group_key']}: "
              f"{result['group_value']} events")
    
    # Example 8: Table schema inspection (for BI tools)
    print("\n8. Table Schema Inspection")
    print("-" * 70)
    events_schema = query.get_table_schema('events')
    print("  Events table schema:")
    for col in events_schema:
        print(f"    {col.get('column_name', list(col.values())[0])}: "
              f"{col.get('column_type', list(col.values())[1])}")
    
    tables = query.list_tables()
    print(f"\n  Available tables: {', '.join(tables)}")
    
    # Example 9: Advanced custom query - Percentiles and distributions
    print("\n9. Advanced Custom Query - Error Distribution by Hour")
    print("-" * 70)
    advanced_sql = """
        SELECT 
            EXTRACT(HOUR FROM timestamp) AS hour_of_day,
            COUNT(*) AS total_events,
            COUNT(CASE WHEN level = 'ERROR' THEN 1 END) AS error_count,
            COUNT(CASE WHEN level = 'WARNING' THEN 1 END) AS warning_count,
            COUNT(CASE WHEN level = 'INFO' THEN 1 END) AS info_count
        FROM events
        WHERE timestamp >= ? AND timestamp <= ?
        GROUP BY hour_of_day
        ORDER BY hour_of_day
    """
    
    distribution = query.query_custom(
        advanced_sql,
        (base_time, base_time + timedelta(days=1))
    )
    
    print("  Error distribution by hour of day:")
    for row in distribution:
        print(f"    Hour {int(row['hour_of_day'])}: "
              f"{row['error_count']} errors, "
              f"{row['warning_count']} warnings, "
              f"{row['info_count']} info")
    
    storage.close()
    
    print("\n" + "=" * 70)
    print("✓ All BI query examples completed!")
    print("=" * 70)
    print("\nThis is where BI people light up! 🔥")
    print("Full SQL access + time bucketing + aggregations = Happy analysts!")


if __name__ == "__main__":
    main()

