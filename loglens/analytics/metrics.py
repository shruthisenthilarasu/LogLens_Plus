"""
Declarative metric definitions for log analytics.

This module provides a flexible, declarative way to define metrics
that can be computed over log events without changing core logic.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional, Dict, Any, List, Union
from collections import defaultdict
from enum import Enum

from loglens.models import LogEvent


class AggregationType(Enum):
    """Types of aggregation functions."""
    COUNT = "count"
    RATE = "rate"
    AVERAGE = "average"
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    PERCENTILE = "percentile"
    UNIQUE_COUNT = "unique_count"


@dataclass
class Metric:
    """
    Declarative metric definition.
    
    A metric specifies what to measure, how to filter events,
    how to aggregate them, and over what time window.
    
    Example:
        Metric(
            name="error_rate",
            filter=lambda e: e.level == "ERROR",
            aggregation="count",
            window="5m"
        )
    """
    
    name: str
    filter: Callable[[LogEvent], bool]
    aggregation: Union[str, AggregationType, Callable[[List[LogEvent]], Any]]
    window: Union[str, timedelta]
    description: Optional[str] = None
    group_by: Optional[Callable[[LogEvent], str]] = None
    value_extractor: Optional[Callable[[LogEvent], Union[int, float]]] = None
    percentile: Optional[float] = field(default=None)
    
    def __post_init__(self):
        """Validate and normalize metric definition."""
        if not self.name:
            raise ValueError("Metric name cannot be empty")
        
        # Normalize aggregation
        if isinstance(self.aggregation, str):
            try:
                self.aggregation = AggregationType(self.aggregation.lower())
            except ValueError:
                raise ValueError(
                    f"Unknown aggregation type: {self.aggregation}. "
                    f"Supported: {[a.value for a in AggregationType]}"
                )
        elif not isinstance(self.aggregation, (AggregationType, Callable)):
            raise ValueError("aggregation must be a string, AggregationType, or callable")
        
        # Parse window string if needed
        if isinstance(self.window, str):
            self.window = self._parse_window(self.window)
        elif not isinstance(self.window, timedelta):
            raise ValueError("window must be a string (e.g., '5m') or timedelta")
        
        # Validate percentile for percentile aggregation
        if self.aggregation == AggregationType.PERCENTILE:
            if self.percentile is None:
                raise ValueError("percentile must be specified for percentile aggregation")
            if not (0 <= self.percentile <= 100):
                raise ValueError("percentile must be between 0 and 100")
    
    @staticmethod
    def _parse_window(window_str: str) -> timedelta:
        """
        Parse window string like '5m', '15m', '1h', '2d'.
        
        Args:
            window_str: Window string (e.g., '5m', '1h', '30s')
        
        Returns:
            timedelta object
        
        Raises:
            ValueError: If window string is invalid
        """
        pattern = r'^(\d+)([smhd])$'
        match = re.match(pattern, window_str.lower())
        if not match:
            raise ValueError(
                f"Invalid window format: {window_str}. "
                f"Expected format: <number><unit> (e.g., '5m', '1h', '30s')"
            )
        
        value = int(match.group(1))
        unit = match.group(2)
        
        unit_map = {
            's': 'seconds',
            'm': 'minutes',
            'h': 'hours',
            'd': 'days'
        }
        
        return timedelta(**{unit_map[unit]: value})


@dataclass
class MetricResult:
    """Result of computing a metric."""
    
    metric_name: str
    value: Any
    window_start: datetime
    window_end: datetime
    grouped_values: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            'metric': self.metric_name,
            'value': self.value,
            'window_start': self.window_start.isoformat(),
            'window_end': self.window_end.isoformat(),
            'metadata': self.metadata
        }
        if self.grouped_values:
            result['grouped'] = self.grouped_values
        return result
    
    def __repr__(self) -> str:
        """String representation."""
        if self.grouped_values:
            return f"MetricResult({self.metric_name}={self.grouped_values})"
        return f"MetricResult({self.metric_name}={self.value})"


class MetricProcessor:
    """
    Processor that computes multiple declarative metrics.
    
    Maintains rolling windows for each metric and computes
    aggregations as events arrive.
    """
    
    def __init__(self, metrics: List[Metric]):
        """
        Initialize metric processor.
        
        Args:
            metrics: List of Metric definitions to compute
        """
        self.metrics = metrics
        self.metric_windows: Dict[str, List[LogEvent]] = defaultdict(list)
        self.metric_results: Dict[str, MetricResult] = {}
    
    def add_event(self, event: LogEvent) -> Dict[str, MetricResult]:
        """
        Add a new event and update all relevant metrics.
        
        Args:
            event: LogEvent to process
        
        Returns:
            Dictionary of metric_name -> MetricResult for updated metrics
        """
        updated_metrics = {}
        now = event.timestamp
        
        for metric in self.metrics:
            # Check if event matches filter
            if not metric.filter(event):
                continue
            
            # Add event to metric's window
            window_events = self.metric_windows[metric.name]
            window_events.append(event)
            
            # Remove events outside the window
            window_start = now - metric.window
            while window_events and window_events[0].timestamp < window_start:
                window_events.pop(0)
            
            # Compute metric value
            result = self._compute_metric(metric, window_events, window_start, now)
            self.metric_results[metric.name] = result
            updated_metrics[metric.name] = result
        
        return updated_metrics
    
    def _compute_metric(
        self,
        metric: Metric,
        events: List[LogEvent],
        window_start: datetime,
        window_end: datetime
    ) -> MetricResult:
        """
        Compute a metric value from filtered events.
        
        Args:
            metric: Metric definition
            events: List of events in the window
            window_start: Start of time window
            window_end: End of time window
        
        Returns:
            MetricResult
        """
        # Filter events (should already be filtered, but double-check)
        filtered_events = [e for e in events if metric.filter(e)]
        
        # Handle grouping
        if metric.group_by:
            grouped_events = defaultdict(list)
            for event in filtered_events:
                group_key = metric.group_by(event)
                grouped_events[group_key].append(event)
            
            # Compute value for each group
            grouped_values = {}
            for group_key, group_events in grouped_events.items():
                grouped_values[group_key] = self._apply_aggregation(
                    metric, group_events
                )
            
            return MetricResult(
                metric_name=metric.name,
                value=None,  # No single value when grouped
                window_start=window_start,
                window_end=window_end,
                grouped_values=grouped_values
            )
        else:
            # Compute single aggregated value
            value = self._apply_aggregation(metric, filtered_events)
            
            return MetricResult(
                metric_name=metric.name,
                value=value,
                window_start=window_start,
                window_end=window_end
            )
    
    def _apply_aggregation(
        self,
        metric: Metric,
        events: List[LogEvent]
    ) -> Any:
        """
        Apply aggregation function to events.
        
        Args:
            metric: Metric definition
            events: List of events to aggregate
        
        Returns:
            Aggregated value
        """
        if not events:
            return 0 if metric.aggregation == AggregationType.COUNT else None
        
        # Custom aggregation function
        if callable(metric.aggregation):
            return metric.aggregation(events)
        
        # Built-in aggregations
        agg_type = metric.aggregation
        
        if agg_type == AggregationType.COUNT:
            return len(events)
        
        elif agg_type == AggregationType.RATE:
            # Rate per second
            if not events:
                return 0.0
            time_span = (events[-1].timestamp - events[0].timestamp).total_seconds()
            if time_span == 0:
                return float(len(events))
            return len(events) / time_span if time_span > 0 else 0.0
        
        elif agg_type == AggregationType.AVERAGE:
            if not metric.value_extractor:
                raise ValueError(f"value_extractor required for {agg_type.value} aggregation")
            values = [metric.value_extractor(e) for e in events]
            return sum(values) / len(values) if values else 0.0
        
        elif agg_type == AggregationType.SUM:
            if not metric.value_extractor:
                raise ValueError(f"value_extractor required for {agg_type.value} aggregation")
            return sum(metric.value_extractor(e) for e in events)
        
        elif agg_type == AggregationType.MIN:
            if not metric.value_extractor:
                raise ValueError(f"value_extractor required for {agg_type.value} aggregation")
            values = [metric.value_extractor(e) for e in events]
            return min(values) if values else None
        
        elif agg_type == AggregationType.MAX:
            if not metric.value_extractor:
                raise ValueError(f"value_extractor required for {agg_type.value} aggregation")
            values = [metric.value_extractor(e) for e in events]
            return max(values) if values else None
        
        elif agg_type == AggregationType.PERCENTILE:
            if not metric.value_extractor:
                raise ValueError(f"value_extractor required for {agg_type.value} aggregation")
            values = sorted([metric.value_extractor(e) for e in events])
            if not values:
                return None
            index = int((metric.percentile / 100.0) * (len(values) - 1))
            return values[index]
        
        elif agg_type == AggregationType.UNIQUE_COUNT:
            if not metric.value_extractor:
                raise ValueError(f"value_extractor required for {agg_type.value} aggregation")
            unique_values = set(metric.value_extractor(e) for e in events)
            return len(unique_values)
        
        else:
            raise ValueError(f"Unsupported aggregation type: {agg_type}")
    
    def get_metric(self, metric_name: str) -> Optional[MetricResult]:
        """
        Get current value of a metric.
        
        Args:
            metric_name: Name of the metric
        
        Returns:
            MetricResult or None if metric not found
        """
        return self.metric_results.get(metric_name)
    
    def get_all_metrics(self) -> Dict[str, MetricResult]:
        """
        Get all current metric values.
        
        Returns:
            Dictionary of metric_name -> MetricResult
        """
        return self.metric_results.copy()
    
    def process_events(self, events) -> Dict[str, List[MetricResult]]:
        """
        Process a stream of events and collect all metric updates.
        
        Args:
            events: Iterator of LogEvent objects
        
        Returns:
            Dictionary of metric_name -> list of MetricResult updates
        """
        all_updates = defaultdict(list)
        
        for event in events:
            updated = self.add_event(event)
            for metric_name, result in updated.items():
                all_updates[metric_name].append(result)
        
        return dict(all_updates)
    
    def clear(self) -> None:
        """Clear all metrics and reset state."""
        self.metric_windows.clear()
        self.metric_results.clear()


# Convenience functions for common metric definitions

def error_rate_metric(window: Union[str, timedelta] = "5m") -> Metric:
    """Create an error rate metric."""
    return Metric(
        name="error_rate",
        filter=lambda e: e.level in ("ERROR", "CRITICAL", "FATAL"),
        aggregation="count",
        window=window,
        description="Count of error-level events"
    )


def warning_rate_metric(window: Union[str, timedelta] = "5m") -> Metric:
    """Create a warning rate metric."""
    return Metric(
        name="warning_rate",
        filter=lambda e: e.level == "WARNING",
        aggregation="rate",
        window=window,
        description="Rate of warning events per second"
    )


def events_by_source_metric(window: Union[str, timedelta] = "5m") -> Metric:
    """Create a metric that groups events by source."""
    return Metric(
        name="events_by_source",
        filter=lambda e: True,  # All events
        aggregation="count",
        window=window,
        description="Event count grouped by source",
        group_by=lambda e: e.source
    )


def events_by_level_metric(window: Union[str, timedelta] = "5m") -> Metric:
    """Create a metric that groups events by log level."""
    return Metric(
        name="events_by_level",
        filter=lambda e: True,  # All events
        aggregation="count",
        window=window,
        description="Event count grouped by log level",
        group_by=lambda e: e.level
    )

