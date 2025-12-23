"""
Helper functions for integrating storage with metrics processing.

This module provides convenience functions for common storage patterns,
such as automatically storing metrics as they are computed.
"""

from typing import List, Optional
from datetime import datetime

from loglens.storage.database import LogStorage
from loglens.analytics.metrics import MetricResult, MetricProcessor
from loglens.models import LogEvent


class PersistentMetricProcessor:
    """
    Metric processor that automatically persists metrics to storage.
    
    This combines MetricProcessor with LogStorage to automatically
    save computed metrics to the database.
    """
    
    def __init__(
        self,
        storage: LogStorage,
        metrics: List,
        auto_store: bool = True
    ):
        """
        Initialize persistent metric processor.
        
        Args:
            storage: LogStorage instance for persistence
            metrics: List of Metric definitions
            auto_store: If True, automatically store metrics when computed
        """
        self.storage = storage
        self.processor = MetricProcessor(metrics)
        self.auto_store = auto_store
    
    def add_event(self, event: LogEvent) -> dict:
        """
        Add event and optionally store to database.
        
        Args:
            event: LogEvent to process
        
        Returns:
            Dictionary of updated metrics
        """
        # Store event
        self.storage.insert_event(event)
        
        # Process metrics
        updated_metrics = self.processor.add_event(event)
        
        # Auto-store metrics if enabled
        if self.auto_store:
            for metric_name, result in updated_metrics.items():
                self._store_metric(result)
        
        return updated_metrics
    
    def add_events(self, events: List[LogEvent]) -> dict:
        """
        Add multiple events in batch.
        
        Args:
            events: List of LogEvent objects
        
        Returns:
            Dictionary of updated metrics
        """
        # Store events
        self.storage.insert_events(events)
        
        # Process metrics
        all_updated = {}
        for event in events:
            updated = self.processor.add_event(event)
            for metric_name, result in updated.items():
                if metric_name not in all_updated:
                    all_updated[metric_name] = result
                else:
                    # Update with latest result
                    all_updated[metric_name] = result
        
        # Auto-store metrics if enabled
        if self.auto_store:
            for metric_name, result in all_updated.items():
                self._store_metric(result)
        
        return all_updated
    
    def _store_metric(self, result: MetricResult) -> int:
        """
        Store a metric result to database.
        
        Args:
            result: MetricResult to store
        
        Returns:
            ID of stored metric
        """
        return self.storage.insert_metric(
            metric_name=result.metric_name,
            window_start=result.window_start,
            window_end=result.window_end,
            value=result.value,
            grouped_values=result.grouped_values,
            metadata=result.metadata
        )
    
    def get_metric(self, metric_name: str):
        """Get current metric value from processor."""
        return self.processor.get_metric(metric_name)
    
    def get_all_metrics(self):
        """Get all current metrics from processor."""
        return self.processor.get_all_metrics()
    
    def get_stored_metric(
        self,
        metric_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ):
        """
        Get stored metrics from database.
        
        Args:
            metric_name: Name of metric
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum number of results
        
        Returns:
            List of stored metric dictionaries
        """
        return self.storage.query_metrics(
            metric_name=metric_name,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )


def create_persistent_processor(
    db_path: str,
    metrics: List,
    auto_store: bool = True
) -> PersistentMetricProcessor:
    """
    Create a persistent metric processor with storage.
    
    Args:
        db_path: Path to database file
        metrics: List of Metric definitions
        auto_store: Automatically store metrics when computed
    
    Returns:
        PersistentMetricProcessor instance
    """
    storage = LogStorage(db_path)
    return PersistentMetricProcessor(storage, metrics, auto_store)

