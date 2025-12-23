#!/usr/bin/env python3
"""
BI Query Quick Reference

Common SQL query patterns for BI analysts working with LogLens++ metrics.
Copy and adapt these queries for your analysis needs!
"""

from datetime import datetime, timedelta
from loglens.storage import LogStorage, create_query, TimeBucket


def example_queries():
    """Common BI query patterns."""
    
    storage = LogStorage("your_database.db")
    query = create_query(storage)
    
    # ========================================================================
    # 1. ERROR RATES BY TIME BUCKET (Hourly)
    # ========================================================================
    print("1. Error Rates by Hour")
    print("-" * 70)
    
    results = query.query_metrics_by_time_bucket(
        metric_name='error_count',
        bucket_size=TimeBucket.HOUR,
        start_time=datetime.now() - timedelta(days=7),
        aggregation='AVG'
    )
    
    # ========================================================================
    # 2. TOP SOURCES BY EVENT COUNT
    # ========================================================================
    print("\n2. Top 10 Sources by Event Count")
    print("-" * 70)
    
    top_sources = query.query_top_sources(
        start_time=datetime.now() - timedelta(days=7),
        limit=10,
        by='event_count'
    )
    
    # ========================================================================
    # 3. ERROR RATE BY SOURCE AND TIME
    # ========================================================================
    print("\n3. Error Rate by Source (Hourly)")
    print("-" * 70)
    
    error_by_source = query.query_error_rate_by_source(
        start_time=datetime.now() - timedelta(days=1),
        bucket_size=TimeBucket.HOUR
    )
    
    # ========================================================================
    # 4. CUSTOM SQL - DAILY ERROR TRENDS
    # ========================================================================
    print("\n4. Daily Error Trends (Custom SQL)")
    print("-" * 70)
    
    sql = """
        SELECT 
            DATE_TRUNC('day', timestamp) AS day,
            source,
            COUNT(*) AS total_events,
            COUNT(CASE WHEN level = 'ERROR' THEN 1 END) AS error_count,
            CAST(COUNT(CASE WHEN level = 'ERROR' THEN 1 END) AS DOUBLE) / 
                NULLIF(COUNT(*), 0) * 100.0 AS error_rate
        FROM events
        WHERE timestamp >= ? AND timestamp <= ?
        GROUP BY day, source
        ORDER BY day, error_rate DESC
    """
    
    results = query.query_custom(
        sql,
        (datetime.now() - timedelta(days=7), datetime.now())
    )
    
    # ========================================================================
    # 5. CUSTOM SQL - HOURLY ERROR DISTRIBUTION
    # ========================================================================
    print("\n5. Error Distribution by Hour of Day")
    print("-" * 70)
    
    sql = """
        SELECT 
            EXTRACT(HOUR FROM timestamp) AS hour_of_day,
            COUNT(*) AS total_events,
            COUNT(CASE WHEN level = 'ERROR' THEN 1 END) AS error_count,
            COUNT(CASE WHEN level = 'WARNING' THEN 1 END) AS warning_count
        FROM events
        WHERE timestamp >= ? AND timestamp <= ?
        GROUP BY hour_of_day
        ORDER BY hour_of_day
    """
    
    results = query.query_custom(
        sql,
        (datetime.now() - timedelta(days=7), datetime.now())
    )
    
    # ========================================================================
    # 6. CUSTOM SQL - METRIC AGGREGATIONS
    # ========================================================================
    print("\n6. Metric Aggregations (Custom SQL)")
    print("-" * 70)
    
    sql = """
        SELECT 
            metric_name,
            DATE_TRUNC('day', window_start) AS day,
            AVG(value) AS avg_value,
            MIN(value) AS min_value,
            MAX(value) AS max_value,
            SUM(value) AS sum_value,
            COUNT(*) AS sample_count
        FROM metrics
        WHERE window_start >= ? AND window_start <= ?
        AND value IS NOT NULL
        GROUP BY metric_name, day
        ORDER BY day, metric_name
    """
    
    results = query.query_custom(
        sql,
        (datetime.now() - timedelta(days=7), datetime.now())
    )
    
    # ========================================================================
    # 7. CUSTOM SQL - COMPARING METRICS OVER TIME
    # ========================================================================
    print("\n7. Comparing Multiple Metrics Over Time")
    print("-" * 70)
    
    sql = """
        SELECT 
            DATE_TRUNC('hour', window_start) AS hour,
            metric_name,
            AVG(value) AS avg_value
        FROM metrics
        WHERE window_start >= ? AND window_start <= ?
        AND value IS NOT NULL
        GROUP BY hour, metric_name
        ORDER BY hour, metric_name
    """
    
    results = query.query_custom(
        sql,
        (datetime.now() - timedelta(days=1), datetime.now())
    )
    
    # ========================================================================
    # 8. CUSTOM SQL - TOP ERROR SOURCES WITH PERCENTAGES
    # ========================================================================
    print("\n8. Top Error Sources with Percentages")
    print("-" * 70)
    
    sql = """
        SELECT 
            source,
            COUNT(*) AS total_events,
            COUNT(CASE WHEN level = 'ERROR' THEN 1 END) AS error_count,
            CAST(COUNT(CASE WHEN level = 'ERROR' THEN 1 END) AS DOUBLE) / 
                NULLIF(COUNT(*), 0) * 100.0 AS error_percentage,
            COUNT(CASE WHEN level = 'WARNING' THEN 1 END) AS warning_count
        FROM events
        WHERE timestamp >= ? AND timestamp <= ?
        GROUP BY source
        HAVING error_count > 0
        ORDER BY error_count DESC
        LIMIT 10
    """
    
    results = query.query_custom(
        sql,
        (datetime.now() - timedelta(days=7), datetime.now())
    )
    
    # ========================================================================
    # 9. RAW SQL - FULL FLEXIBILITY
    # ========================================================================
    print("\n9. Raw SQL - Full Flexibility")
    print("-" * 70)
    
    # You can write any SQL query!
    results = query.execute_sql(
        "SELECT * FROM events WHERE level = 'ERROR' LIMIT 10"
    )
    
    # Or with parameters
    results = query.execute_sql(
        "SELECT * FROM metrics WHERE metric_name = ? AND value > ?",
        ('error_count', 10)
    )
    
    print("\n" + "=" * 70)
    print("Copy these patterns and adapt for your analysis!")
    print("=" * 70)


if __name__ == "__main__":
    example_queries()

