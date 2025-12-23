#!/usr/bin/env python3
"""
Example demonstrating declarative metric definitions.

This example shows how to define metrics declaratively, making it
easy to add new metrics without changing core logic - just like
internal BI tooling.
"""

from datetime import datetime, timedelta
from loglens.models import LogEvent
from loglens.analytics import Metric, MetricProcessor, AggregationType


def main():
    """Demonstrate declarative metrics."""
    
    # Define metrics declaratively - easy to add new ones!
    metrics = [
        # Simple count metric
        Metric(
            name="error_rate",
            filter=lambda e: e.level == "ERROR",
            aggregation="count",
            window="5m"
        ),
        
        # Rate metric
        Metric(
            name="warning_rate",
            filter=lambda e: e.level == "WARNING",
            aggregation="rate",
            window="5m",
            description="Warnings per second"
        ),
        
        # Grouped metric - events by source
        Metric(
            name="events_by_source",
            filter=lambda e: True,  # All events
            aggregation="count",
            window="15m",
            group_by=lambda e: e.source,
            description="Event count grouped by source"
        ),
        
        # Grouped metric - events by level
        Metric(
            name="events_by_level",
            filter=lambda e: True,
            aggregation="count",
            window="15m",
            group_by=lambda e: e.level,
            description="Event count grouped by log level"
        ),
        
        # Metric with value extraction (if events have numeric metadata)
        Metric(
            name="avg_response_time",
            filter=lambda e: "response_time_ms" in e.metadata,
            aggregation="average",
            window="5m",
            value_extractor=lambda e: e.metadata.get("response_time_ms", 0),
            description="Average response time in milliseconds"
        ),
        
        # Custom aggregation function
        Metric(
            name="error_severity_score",
            filter=lambda e: e.level in ("ERROR", "CRITICAL", "FATAL"),
            aggregation=lambda events: sum(
                3 if e.level == "CRITICAL" else 5 if e.level == "FATAL" else 1
                for e in events
            ),
            window="10m",
            description="Custom severity score for errors"
        ),
    ]
    
    # Create processor - handles all metrics automatically
    processor = MetricProcessor(metrics)
    
    # Simulate incoming log events
    base_time = datetime(2024, 1, 1, 12, 0, 0)
    
    events = [
        # Info events
        LogEvent(timestamp=base_time + timedelta(seconds=i*10),
                 level="INFO", source="app1", message=f"Request {i}")
        for i in range(10)
    ]
    
    # Warning events
    events.extend([
        LogEvent(timestamp=base_time + timedelta(seconds=50 + i*10),
                 level="WARNING", source="app2", message=f"Warning {i}")
        for i in range(5)
    ])
    
    # Error events
    events.extend([
        LogEvent(timestamp=base_time + timedelta(seconds=100 + i*10),
                 level="ERROR", source="app1", message=f"Error {i}")
        for i in range(3)
    ])
    
    # Events with response time metadata
    events.extend([
        LogEvent(timestamp=base_time + timedelta(seconds=130 + i*10),
                 level="INFO", source="app1",
                 message=f"API call {i}",
                 metadata={"response_time_ms": 100 + i * 20})
        for i in range(5)
    ])
    
    # Process events
    print("Processing events and computing metrics...\n")
    for event in events:
        updated = processor.add_event(event)
        if updated:
            # Print updates as they happen
            for metric_name, result in updated.items():
                if result.grouped_values:
                    print(f"  {metric_name} updated: {result.grouped_values}")
                else:
                    print(f"  {metric_name} updated: {result.value}")
    
    # Display final metrics
    print("\n" + "=" * 70)
    print("Final Metrics Summary")
    print("=" * 70)
    
    for metric_name, result in processor.get_all_metrics().items():
        print(f"\n{metric_name}:")
        print(f"  Window: {result.window_start.strftime('%H:%M:%S')} - "
              f"{result.window_end.strftime('%H:%M:%S')}")
        
        if result.grouped_values:
            print("  Grouped values:")
            for key, value in result.grouped_values.items():
                print(f"    {key}: {value}")
        else:
            print(f"  Value: {result.value}")


if __name__ == "__main__":
    main()

