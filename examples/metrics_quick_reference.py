#!/usr/bin/env python3
"""
Quick Reference: Adding New Metrics

This file demonstrates how easy it is to add new metrics
without changing any core logic - just define them declaratively!
"""

from loglens.analytics import Metric, MetricProcessor

# ============================================================================
# EXAMPLE: Adding a new metric is as simple as defining it!
# ============================================================================

# Want to track API errors? Just add this:
api_error_metric = Metric(
    name="api_error_count",
    filter=lambda e: e.source == "api" and e.level == "ERROR",
    aggregation="count",
    window="5m"
)

# Want to track database query times? Just add this:
db_query_time_metric = Metric(
    name="avg_db_query_time",
    filter=lambda e: "db_query_time" in e.metadata,
    aggregation="average",
    window="10m",
    value_extractor=lambda e: e.metadata.get("db_query_time", 0)
)

# Want to track unique users? Just add this:
unique_users_metric = Metric(
    name="unique_users",
    filter=lambda e: "user_id" in e.metadata,
    aggregation="unique_count",
    window="1h",
    value_extractor=lambda e: e.metadata.get("user_id")
)

# Want to track errors by service? Just add this:
errors_by_service_metric = Metric(
    name="errors_by_service",
    filter=lambda e: e.level == "ERROR",
    aggregation="count",
    window="15m",
    group_by=lambda e: e.source  # Group by source (service name)
)

# ============================================================================
# That's it! No core logic changes needed.
# ============================================================================

# Just add your metrics to the processor:
all_metrics = [
    api_error_metric,
    db_query_time_metric,
    unique_users_metric,
    errors_by_service_metric,
    # ... add as many as you want!
]

processor = MetricProcessor(all_metrics)

# Process events - all metrics update automatically!
# for event in log_stream:
#     processor.add_event(event)
#     metrics = processor.get_all_metrics()
#     # Use metrics however you need!

print("✓ Metrics defined! Add them to your MetricProcessor and you're done!")

