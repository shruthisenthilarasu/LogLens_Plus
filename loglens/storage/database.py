"""
Database storage layer using DuckDB.

This module provides efficient storage and querying of log events
and aggregated metrics using DuckDB, optimized for analytics workloads.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Iterator, Union
import duckdb


class LogStorage:
    """
    Storage layer for log events and metrics using DuckDB.
    
    Provides efficient storage and querying capabilities optimized
    for time-series analytics workloads.
    """
    
    def __init__(self, db_path: Union[str, Path] = "loglens.db"):
        """
        Initialize the storage layer.
        
        Args:
            db_path: Path to the DuckDB database file
        """
        self.db_path = Path(db_path)
        self.conn = duckdb.connect(str(self.db_path))
        self._initialize_schema()
    
    def _initialize_schema(self) -> None:
        """Initialize database schemas for events and metrics."""
        # Events table - stores raw log events
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id BIGINT PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                level VARCHAR NOT NULL,
                source VARCHAR NOT NULL,
                message TEXT NOT NULL,
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index on timestamp for efficient time-range queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_timestamp 
            ON events(timestamp)
        """)
        
        # Create index on level for filtering
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_level 
            ON events(level)
        """)
        
        # Create index on source for filtering
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_source 
            ON events(source)
        """)
        
        # Metrics table - stores aggregated metrics
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS metrics (
                id BIGINT PRIMARY KEY,
                metric_name VARCHAR NOT NULL,
                window_start TIMESTAMP NOT NULL,
                window_end TIMESTAMP NOT NULL,
                value DOUBLE,
                grouped_values JSON,
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for metrics
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_name 
            ON metrics(metric_name)
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_window 
            ON metrics(window_start, window_end)
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_name_window 
            ON metrics(metric_name, window_start, window_end)
        """)
    
    def insert_event(self, event) -> int:
        """
        Insert a single log event.
        
        Args:
            event: LogEvent object to insert
        
        Returns:
            ID of the inserted event
        """
        metadata_json = json.dumps(event.metadata) if event.metadata else None
        
        # DuckDB uses different syntax - need to handle auto-increment
        # First, get the next ID
        next_id_result = self.conn.execute("""
            SELECT COALESCE(MAX(id), 0) + 1 FROM events
        """).fetchone()
        next_id = next_id_result[0] if next_id_result else 1
        
        # Insert with explicit ID
        self.conn.execute("""
            INSERT INTO events (id, timestamp, level, source, message, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            next_id,
            event.timestamp,
            event.level,
            event.source,
            event.message,
            metadata_json
        ))
        
        return next_id
    
    def insert_events(self, events: List) -> List[int]:
        """
        Insert multiple log events in a batch.
        
        Args:
            events: List of LogEvent objects
        
        Returns:
            List of inserted event IDs
        """
        if not events:
            return []
        
        # For DuckDB, we'll insert one by one to get IDs
        # Alternatively, we can use a single transaction
        ids = []
        for event in events:
            ids.append(self.insert_event(event))
        
        return ids
    
    def insert_metric(self, metric_name: str, window_start: datetime,
                     window_end: datetime, value: Optional[float] = None,
                     grouped_values: Optional[Dict[str, Any]] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Insert a metric result.
        
        Args:
            metric_name: Name of the metric
            window_start: Start of the time window
            window_end: End of the time window
            value: Single metric value (if not grouped)
            grouped_values: Grouped metric values (if grouped)
            metadata: Additional metadata
        
        Returns:
            ID of the inserted metric
        """
        grouped_json = json.dumps(grouped_values) if grouped_values else None
        metadata_json = json.dumps(metadata) if metadata else None
        
        # Get next ID for metrics
        next_id_result = self.conn.execute("""
            SELECT COALESCE(MAX(id), 0) + 1 FROM metrics
        """).fetchone()
        next_id = next_id_result[0] if next_id_result else 1
        
        # Insert with explicit ID
        self.conn.execute("""
            INSERT INTO metrics (id, metric_name, window_start, window_end, 
                                value, grouped_values, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            next_id,
            metric_name,
            window_start,
            window_end,
            value,
            grouped_json,
            metadata_json
        ))
        
        return next_id
    
    def query_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        level: Optional[str] = None,
        source: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Query events with filters.
        
        Args:
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)
            level: Filter by log level
            source: Filter by source
            limit: Maximum number of results
        
        Returns:
            List of event dictionaries
        """
        conditions = []
        params = []
        
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)
        
        if level:
            conditions.append("level = ?")
            params.append(level)
        
        if source:
            conditions.append("source = ?")
            params.append(source)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        limit_clause = f"LIMIT {limit}" if limit else ""
        
        query = f"""
            SELECT id, timestamp, level, source, message, metadata, created_at
            FROM events
            {where_clause}
            ORDER BY timestamp DESC
            {limit_clause}
        """
        
        results = self.conn.execute(query, params).fetchall()
        
        events = []
        for row in results:
            event = {
                'id': row[0],
                'timestamp': row[1],
                'level': row[2],
                'source': row[3],
                'message': row[4],
                'metadata': json.loads(row[5]) if row[5] else {},
                'created_at': row[6]
            }
            events.append(event)
        
        return events
    
    def query_metrics(
        self,
        metric_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Query metrics with filters.
        
        Args:
            metric_name: Filter by metric name
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)
            limit: Maximum number of results
        
        Returns:
            List of metric dictionaries
        """
        conditions = []
        params = []
        
        if metric_name:
            conditions.append("metric_name = ?")
            params.append(metric_name)
        
        if start_time:
            conditions.append("window_start >= ?")
            params.append(start_time)
        
        if end_time:
            conditions.append("window_end <= ?")
            params.append(end_time)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        limit_clause = f"LIMIT {limit}" if limit else ""
        
        query = f"""
            SELECT id, metric_name, window_start, window_end, 
                   value, grouped_values, metadata, created_at
            FROM metrics
            {where_clause}
            ORDER BY window_start DESC
            {limit_clause}
        """
        
        results = self.conn.execute(query, params).fetchall()
        
        metrics = []
        for row in results:
            metric = {
                'id': row[0],
                'metric_name': row[1],
                'window_start': row[2],
                'window_end': row[3],
                'value': row[4],
                'grouped_values': json.loads(row[5]) if row[5] else None,
                'metadata': json.loads(row[6]) if row[6] else {},
                'created_at': row[7]
            }
            metrics.append(metric)
        
        return metrics
    
    def get_metric_summary(
        self,
        metric_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get summary statistics for a metric over a time range.
        
        Args:
            metric_name: Name of the metric
            start_time: Start of time range
            end_time: End of time range
        
        Returns:
            Dictionary with summary statistics
        """
        conditions = ["metric_name = ?"]
        params = [metric_name]
        
        if start_time:
            conditions.append("window_start >= ?")
            params.append(start_time)
        
        if end_time:
            conditions.append("window_end <= ?")
            params.append(end_time)
        
        where_clause = "WHERE " + " AND ".join(conditions)
        
        query = f"""
            SELECT 
                COUNT(*) as count,
                AVG(value) as avg_value,
                MIN(value) as min_value,
                MAX(value) as max_value,
                SUM(value) as sum_value
            FROM metrics
            {where_clause}
            AND value IS NOT NULL
        """
        
        result = self.conn.execute(query, params).fetchone()
        
        if result and result[0] > 0:
            return {
                'count': result[0],
                'avg': result[1],
                'min': result[2],
                'max': result[3],
                'sum': result[4]
            }
        return {'count': 0, 'avg': None, 'min': None, 'max': None, 'sum': None}
    
    def get_event_stats(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get statistics about events in a time range.
        
        Args:
            start_time: Start of time range
            end_time: End of time range
        
        Returns:
            Dictionary with event statistics
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
        
        # Total count
        count_query = f"SELECT COUNT(*) FROM events {where_clause}"
        total_count = self.conn.execute(count_query, params).fetchone()[0]
        
        # Count by level
        level_query = f"""
            SELECT level, COUNT(*) as count
            FROM events
            {where_clause}
            GROUP BY level
            ORDER BY count DESC
        """
        level_counts = dict(self.conn.execute(level_query, params).fetchall())
        
        # Count by source
        source_query = f"""
            SELECT source, COUNT(*) as count
            FROM events
            {where_clause}
            GROUP BY source
            ORDER BY count DESC
        """
        source_counts = dict(self.conn.execute(source_query, params).fetchall())
        
        return {
            'total_events': total_count,
            'by_level': level_counts,
            'by_source': source_counts
        }
    
    def delete_old_events(self, before_date: datetime) -> int:
        """
        Delete events older than the specified date.
        
        Args:
            before_date: Delete events before this date
        
        Returns:
            Number of deleted events
        """
        # Get count before deletion
        count_result = self.conn.execute("""
            SELECT COUNT(*) FROM events WHERE timestamp < ?
        """, (before_date,)).fetchone()
        count = count_result[0] if count_result else 0
        
        # Delete
        self.conn.execute("""
            DELETE FROM events WHERE timestamp < ?
        """, (before_date,))
        
        return count
    
    def delete_old_metrics(self, before_date: datetime) -> int:
        """
        Delete metrics older than the specified date.
        
        Args:
            before_date: Delete metrics before this date
        
        Returns:
            Number of deleted metrics
        """
        # Get count before deletion
        count_result = self.conn.execute("""
            SELECT COUNT(*) FROM metrics WHERE window_end < ?
        """, (before_date,)).fetchone()
        count = count_result[0] if count_result else 0
        
        # Delete
        self.conn.execute("""
            DELETE FROM metrics WHERE window_end < ?
        """, (before_date,))
        
        return count
    
    def vacuum(self) -> None:
        """Optimize database by running VACUUM."""
        self.conn.execute("VACUUM")
    
    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Convenience function for quick access
def create_storage(db_path: Union[str, Path] = "loglens.db") -> LogStorage:
    """
    Create a new LogStorage instance.
    
    Args:
        db_path: Path to the database file
    
    Returns:
        LogStorage instance
    """
    return LogStorage(db_path)

