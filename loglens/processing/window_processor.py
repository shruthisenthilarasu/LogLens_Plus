"""
Rolling window processor for log events.

This module provides functionality to process log events in time-based windows,
supporting both sliding and tumbling window strategies.
"""

from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Iterator
from enum import Enum

from loglens.models import LogEvent


class WindowType(Enum):
    """Type of time window."""
    SLIDING = "sliding"
    TUMBLING = "tumbling"


class WindowMetrics:
    """
    Metrics computed over a time window.
    
    Attributes:
        total_events: Total number of events in the window
        events_by_level: Count of events grouped by log level
        events_by_source: Count of events grouped by source
        error_rate: Percentage of ERROR and CRITICAL level events
        start_time: Start of the time window
        end_time: End of the time window
    """
    
    def __init__(self, start_time: datetime, end_time: datetime):
        """Initialize metrics for a time window."""
        self.start_time = start_time
        self.end_time = end_time
        self.total_events = 0
        self.events_by_level: Dict[str, int] = defaultdict(int)
        self.events_by_source: Dict[str, int] = defaultdict(int)
        self.error_count = 0
        self.warning_count = 0
    
    @property
    def error_rate(self) -> float:
        """Calculate error rate as percentage."""
        if self.total_events == 0:
            return 0.0
        return (self.error_count / self.total_events) * 100.0
    
    @property
    def warning_rate(self) -> float:
        """Calculate warning rate as percentage."""
        if self.total_events == 0:
            return 0.0
        return (self.warning_count / self.total_events) * 100.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'total_events': self.total_events,
            'events_by_level': dict(self.events_by_level),
            'events_by_source': dict(self.events_by_source),
            'error_rate': self.error_rate,
            'warning_rate': self.warning_rate,
            'error_count': self.error_count,
            'warning_count': self.warning_count,
        }
    
    def __repr__(self) -> str:
        """String representation of metrics."""
        return (
            f"WindowMetrics(start={self.start_time}, end={self.end_time}, "
            f"total={self.total_events}, error_rate={self.error_rate:.2f}%)"
        )


class RollingWindowProcessor:
    """
    Processor that maintains metrics over a rolling time window.
    
    Supports both sliding and tumbling window strategies:
    - Sliding window: Continuously updates as new events arrive, removing old ones
    - Tumbling window: Processes events in fixed, non-overlapping time intervals
    """
    
    def __init__(
        self,
        window_size: timedelta,
        window_type: WindowType = WindowType.SLIDING,
        update_interval: Optional[timedelta] = None
    ):
        """
        Initialize the rolling window processor.
        
        Args:
            window_size: Size of the time window (e.g., timedelta(minutes=5))
            window_type: Type of window (SLIDING or TUMBLING)
            update_interval: For tumbling windows, interval between window updates.
                           If None, defaults to window_size
        """
        self.window_size = window_size
        self.window_type = window_type
        self.update_interval = update_interval or window_size
        
        # Event storage (using deque for efficient append/popleft)
        self.events: deque = deque()
        
        # Current window metrics
        self.current_metrics: Optional[WindowMetrics] = None
        
        # For tumbling windows: track current window boundaries
        self.current_window_start: Optional[datetime] = None
        self.current_window_end: Optional[datetime] = None
        
        # For tumbling windows: store completed windows
        self.completed_windows: List[WindowMetrics] = []
    
    def add_event(self, event: LogEvent) -> Optional[WindowMetrics]:
        """
        Add a new log event to the processor.
        
        Args:
            event: LogEvent to add
        
        Returns:
            Updated WindowMetrics if window was updated, None otherwise
        """
        if self.window_type == WindowType.SLIDING:
            return self._add_event_sliding(event)
        else:
            return self._add_event_tumbling(event)
    
    def _add_event_sliding(self, event: LogEvent) -> WindowMetrics:
        """
        Add event to sliding window.
        
        Args:
            event: LogEvent to add
        
        Returns:
            Updated WindowMetrics
        """
        # Window is relative to the most recent event timestamp
        window_end = event.timestamp
        window_start = window_end - self.window_size
        
        # Add new event
        self.events.append(event)
        
        # Remove events outside the window (older than window_start)
        while self.events and self.events[0].timestamp < window_start:
            self.events.popleft()
        
        # Recalculate metrics for current window
        return self._calculate_metrics(window_start, window_end)
    
    def _add_event_tumbling(self, event: LogEvent) -> Optional[WindowMetrics]:
        """
        Add event to tumbling window.
        
        Args:
            event: LogEvent to add
        
        Returns:
            WindowMetrics if a window was completed, None otherwise
        """
        event_time = event.timestamp
        completed_window = None
        
        # Initialize first window if needed
        if self.current_window_start is None:
            # Align window to a clean boundary (e.g., start of minute/hour)
            self.current_window_start = self._align_window_start(event_time)
            self.current_window_end = self.current_window_start + self.window_size
            self.current_metrics = WindowMetrics(
                self.current_window_start,
                self.current_window_end
            )
        
        # Check if event falls in current window
        if event_time < self.current_window_start:
            # Event is too old, skip it
            return None
        elif event_time >= self.current_window_end:
            # Event is in a future window, complete current window and start new one
            if self.current_metrics:
                completed_window = self.current_metrics
                self.completed_windows.append(completed_window)
            
            # Start new window(s) until we catch up
            while event_time >= self.current_window_end:
                self.current_window_start = self.current_window_end
                self.current_window_end = self.current_window_start + self.window_size
            
            # Initialize new window
            self.current_metrics = WindowMetrics(
                self.current_window_start,
                self.current_window_end
            )
            self.events.clear()
        
        # Add event to current window
        self.events.append(event)
        self._update_metrics(self.current_metrics, event)
        
        return completed_window
    
    def _align_window_start(self, event_time: datetime) -> datetime:
        """
        Align window start to a clean boundary.
        
        For example, if window is 5 minutes, align to start of 5-minute interval.
        
        Args:
            event_time: Timestamp to align from
        
        Returns:
            Aligned window start time
        """
        # For simplicity, align to the start of the current minute/hour/day
        # based on window size
        if self.window_size >= timedelta(days=1):
            # Align to start of day
            return event_time.replace(hour=0, minute=0, second=0, microsecond=0)
        elif self.window_size >= timedelta(hours=1):
            # Align to start of hour
            return event_time.replace(minute=0, second=0, microsecond=0)
        elif self.window_size >= timedelta(minutes=1):
            # Align to start of minute
            return event_time.replace(second=0, microsecond=0)
        else:
            # For sub-minute windows, use event time as-is
            return event_time
    
    def _calculate_metrics(self, start_time: datetime, end_time: datetime) -> WindowMetrics:
        """
        Calculate metrics for events in the current window.
        
        Args:
            start_time: Start of the window (inclusive)
            end_time: End of the window (inclusive for sliding, exclusive for tumbling)
        
        Returns:
            WindowMetrics object
        """
        metrics = WindowMetrics(start_time, end_time)
        
        # For sliding windows, end_time is inclusive (it's the most recent event)
        # For tumbling windows, end_time is exclusive (it's the window boundary)
        end_inclusive = (self.window_type == WindowType.SLIDING)
        
        for event in self.events:
            if end_inclusive:
                if start_time <= event.timestamp <= end_time:
                    self._update_metrics(metrics, event)
            else:
                if start_time <= event.timestamp < end_time:
                    self._update_metrics(metrics, event)
        
        self.current_metrics = metrics
        return metrics
    
    def _update_metrics(self, metrics: WindowMetrics, event: LogEvent) -> None:
        """
        Update metrics with a new event.
        
        Args:
            metrics: WindowMetrics to update
            event: LogEvent to add to metrics
        """
        metrics.total_events += 1
        metrics.events_by_level[event.level] += 1
        metrics.events_by_source[event.source] += 1
        
        if event.level in ('ERROR', 'CRITICAL', 'FATAL'):
            metrics.error_count += 1
        elif event.level == 'WARNING':
            metrics.warning_count += 1
    
    def get_current_metrics(self) -> Optional[WindowMetrics]:
        """
        Get metrics for the current window.
        
        Returns:
            Current WindowMetrics or None if no events processed yet
        """
        if self.window_type == WindowType.SLIDING:
            # For sliding windows, use the most recent event timestamp
            if not self.events:
                return None
            window_end = self.events[-1].timestamp
            window_start = window_end - self.window_size
            # Remove old events first
            while self.events and self.events[0].timestamp < window_start:
                self.events.popleft()
            # Recalculate metrics with cleaned buffer
            return self._calculate_metrics(window_start, window_end)
        else:
            # For tumbling windows, return current window metrics
            return self.current_metrics
    
    def get_completed_windows(self) -> List[WindowMetrics]:
        """
        Get all completed windows (only relevant for tumbling windows).
        
        Returns:
            List of completed WindowMetrics
        """
        return self.completed_windows.copy()
    
    def clear_completed_windows(self) -> None:
        """Clear the list of completed windows."""
        self.completed_windows.clear()
    
    def process_events(self, events: Iterator[LogEvent]) -> Iterator[WindowMetrics]:
        """
        Process a stream of events and yield metrics updates.
        
        Args:
            events: Iterator of LogEvent objects
        
        Yields:
            WindowMetrics when windows are updated (for sliding) or completed (for tumbling)
        """
        for event in events:
            updated_metrics = self.add_event(event)
            if updated_metrics:
                yield updated_metrics
    
    def get_event_count(self) -> int:
        """Get the number of events currently in the window."""
        return len(self.events)
    
    def clear(self) -> None:
        """Clear all events and reset metrics."""
        self.events.clear()
        self.current_metrics = None
        self.current_window_start = None
        self.current_window_end = None
        self.completed_windows.clear()

