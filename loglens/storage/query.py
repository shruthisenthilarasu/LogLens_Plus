"""
SQL-style query interface for metrics and events.

This module provides a BI-friendly SQL query interface that allows
analysts to write SQL queries over stored metrics and events.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from enum import Enum

from loglens.storage.database import LogStorage


class TimeBucket(Enum):
    """Time bucket sizes for grouping."""
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class MetricQuery:
    """
    SQL-style query builder for metrics and events.
    
    Provides a fluent interface for building SQL queries with
    BI-friendly features like time bucketing, aggregations, and filtering.
    """
    
    def __init__(self, storage: LogStorage):
        """
        Initialize the query builder.
        
        Args:
            storage: LogStorage instance
        """
        self.storage = storage
        self.conn = storage.conn
    
    def execute_sql(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        Execute a raw SQL query.
        
        Args:
            sql: SQL query string
            params: Optional parameters for parameterized queries
        
        Returns:
            List of result dictionaries
        
        Example:
            results = query.execute_sql(
                "SELECT * FROM metrics WHERE metric_name = ?",
                ('error_count',)
            )
        """
        if params:
            result = self.conn.execute(sql, params)
        else:
            result = self.conn.execute(sql)
        
        # Fetch all results
        rows = result.fetchall()
        
        if not rows:
            return []
        
        # Get column names from result
        columns = result.columns if hasattr(result, 'columns') else []
        
        # If columns not available, try to get from description
        if not columns:
            try:
                # DuckDB result has column names accessible
                if hasattr(result, 'description'):
                    columns = [desc[0] for desc in result.description]
            except:
                pass
        
        # If still no columns, use generic names
        if not columns:
            columns = [f'col_{i}' for i in range(len(rows[0]) if rows else 0)]
        
        # Convert rows to dictionaries
        return [dict(zip(columns, row)) for row in rows]
    
    def query_metrics_by_time_bucket(
        self,
        metric_name: str,
        bucket_size: Union[TimeBucket, str] = TimeBucket.HOUR,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        aggregation: str = "AVG"
    ) -> List[Dict[str, Any]]:
        """
        Query metrics grouped by time buckets.
        
        This is a common BI pattern for time-series analysis.
        
        Args:
            metric_name: Name of the metric to query
            bucket_size: Size of time buckets (minute, hour, day, etc.)
            start_time: Start of time range
            end_time: End of time range
            aggregation: Aggregation function (AVG, SUM, MAX, MIN, COUNT)
        
        Returns:
            List of dictionaries with bucket_time and aggregated value
        
        Example:
            # Get hourly error rates
            results = query.query_metrics_by_time_bucket(
                'error_rate',
                bucket_size='hour',
                start_time=datetime.now() - timedelta(days=7)
            )
        """
        if isinstance(bucket_size, str):
            bucket_size = TimeBucket(bucket_size.lower())
        
        # Build time bucket expression
        bucket_expr = self._get_time_bucket_expr(bucket_size)
        
        conditions = ["metric_name = ?"]
        params = [metric_name]
        
        if start_time:
            conditions.append("window_start >= ?")
            params.append(start_time)
        
        if end_time:
            conditions.append("window_end <= ?")
            params.append(end_time)
        
        where_clause = "WHERE " + " AND ".join(conditions)
        
        sql = f"""
            SELECT 
                {bucket_expr} AS bucket_time,
                {aggregation}(value) AS metric_value,
                COUNT(*) AS sample_count
            FROM metrics
            {where_clause}
            AND value IS NOT NULL
            GROUP BY bucket_time
            ORDER BY bucket_time
        """
        
        return self.execute_sql(sql, tuple(params))
    
    def query_top_sources(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 10,
        by: str = "event_count"
    ) -> List[Dict[str, Any]]:
        """
        Query top sources by event count or other metrics.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            limit: Number of top sources to return
            by: What to rank by ('event_count', 'error_count', etc.)
        
        Returns:
            List of dictionaries with source and counts
        
        Example:
            # Top 10 sources by event count
            top_sources = query.query_top_sources(limit=10)
        """
        conditions = []
        params = []
        
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        if by == "event_count":
            sql = f"""
                SELECT 
                    source,
                    COUNT(*) AS event_count,
                    COUNT(CASE WHEN level = 'ERROR' THEN 1 END) AS error_count,
                    COUNT(CASE WHEN level = 'WARNING' THEN 1 END) AS warning_count
                FROM events
                {where_clause}
                GROUP BY source
                ORDER BY event_count DESC
                LIMIT ?
            """
            params.append(limit)
        elif by == "error_count":
            sql = f"""
                SELECT 
                    source,
                    COUNT(*) AS event_count,
                    COUNT(CASE WHEN level = 'ERROR' THEN 1 END) AS error_count,
                    COUNT(CASE WHEN level = 'WARNING' THEN 1 END) AS warning_count
                FROM events
                {where_clause}
                GROUP BY source
                ORDER BY error_count DESC
                LIMIT ?
            """
            params.append(limit)
        else:
            raise ValueError(f"Unknown 'by' parameter: {by}")
        
        return self.execute_sql(sql, tuple(params))
    
    def query_metrics_trend(
        self,
        metric_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        bucket_size: Union[TimeBucket, str] = TimeBucket.HOUR
    ) -> List[Dict[str, Any]]:
        """
        Query metric trends over time with time bucketing.
        
        Args:
            metric_name: Name of the metric
            start_time: Start of time range
            end_time: End of time range
            bucket_size: Size of time buckets
        
        Returns:
            List of dictionaries with time bucket and metric values
        """
        return self.query_metrics_by_time_bucket(
            metric_name=metric_name,
            bucket_size=bucket_size,
            start_time=start_time,
            end_time=end_time,
            aggregation="AVG"
        )
    
    def query_error_rate_by_source(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        bucket_size: Union[TimeBucket, str] = TimeBucket.HOUR
    ) -> List[Dict[str, Any]]:
        """
        Query error rate grouped by source and time bucket.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            bucket_size: Size of time buckets
        
        Returns:
            List of dictionaries with bucket_time, source, and error_rate
        """
        if isinstance(bucket_size, str):
            bucket_size = TimeBucket(bucket_size.lower())
        
        bucket_expr = self._get_time_bucket_expr(bucket_size, "timestamp")
        
        conditions = []
        params = []
        
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        sql = f"""
            SELECT 
                {bucket_expr} AS bucket_time,
                source,
                COUNT(*) AS total_events,
                COUNT(CASE WHEN level IN ('ERROR', 'CRITICAL', 'FATAL') THEN 1 END) AS error_count,
                CAST(COUNT(CASE WHEN level IN ('ERROR', 'CRITICAL', 'FATAL') THEN 1 END) AS DOUBLE) / 
                    NULLIF(COUNT(*), 0) * 100.0 AS error_rate
            FROM events
            {where_clause}
            GROUP BY bucket_time, source
            ORDER BY bucket_time, error_rate DESC
        """
        
        return self.execute_sql(sql, tuple(params))
    
    def query_grouped_metrics(
        self,
        metric_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Query grouped metrics (metrics with grouped_values).
        
        Args:
            metric_name: Name of the metric
            start_time: Start of time range
            end_time: End of time range
        
        Returns:
            List of dictionaries with grouped metric values
        """
        conditions = ["metric_name = ?", "grouped_values IS NOT NULL"]
        params = [metric_name]
        
        if start_time:
            conditions.append("window_start >= ?")
            params.append(start_time)
        
        if end_time:
            conditions.append("window_end <= ?")
            params.append(end_time)
        
        where_clause = "WHERE " + " AND ".join(conditions)
        
        # DuckDB can parse JSON, so we can extract grouped values
        sql = f"""
            SELECT 
                window_start,
                window_end,
                grouped_values
            FROM metrics
            {where_clause}
            ORDER BY window_start DESC
        """
        
        results = self.execute_sql(sql, tuple(params))
        
        # Parse grouped_values JSON and expand
        expanded_results = []
        for row in results:
            grouped = row.get('grouped_values', {})
            if isinstance(grouped, str):
                import json
                grouped = json.loads(grouped)
            
            for key, value in grouped.items():
                expanded_results.append({
                    'window_start': row['window_start'],
                    'window_end': row['window_end'],
                    'group_key': key,
                    'group_value': value
                })
        
        return expanded_results
    
    def query_custom(self, sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        Execute a custom SQL query.
        
        This allows full SQL flexibility for complex BI queries.
        
        Args:
            sql: SQL query string
            params: Optional parameters
        
        Returns:
            List of result dictionaries
        
        Example:
            # Complex custom query
            sql = \"\"\"
                SELECT 
                    DATE_TRUNC('hour', window_start) AS hour,
                    metric_name,
                    AVG(value) AS avg_value,
                    MAX(value) AS max_value
                FROM metrics
                WHERE window_start >= ?
                GROUP BY hour, metric_name
                ORDER BY hour DESC
            \"\"\"
            results = query.query_custom(sql, (datetime.now() - timedelta(days=7),))
        """
        return self.execute_sql(sql, params)
    
    def _get_time_bucket_expr(
        self,
        bucket_size: TimeBucket,
        column: str = "window_start"
    ) -> str:
        """
        Get SQL expression for time bucketing.
        
        Args:
            bucket_size: Size of time bucket
            column: Column to bucket (default: window_start)
        
        Returns:
            SQL expression for time bucketing
        """
        # DuckDB uses DATE_TRUNC for time bucketing
        trunc_unit = bucket_size.value.upper()
        return f"DATE_TRUNC('{trunc_unit}', {column})"
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get schema information for a table.
        
        Useful for BI tools to understand available columns.
        
        Args:
            table_name: Name of the table
        
        Returns:
            List of column information dictionaries
        """
        sql = f"DESCRIBE {table_name}"
        return self.execute_sql(sql)
    
    def list_tables(self) -> List[str]:
        """
        List all available tables.
        
        Returns:
            List of table names
        """
        sql = "SHOW TABLES"
        results = self.execute_sql(sql)
        return [row.get('name', row.get(list(row.keys())[0])) for row in results]


def create_query(storage: LogStorage) -> MetricQuery:
    """
    Create a MetricQuery instance.
    
    Args:
        storage: LogStorage instance
    
    Returns:
        MetricQuery instance
    """
    return MetricQuery(storage)

