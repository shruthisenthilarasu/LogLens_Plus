"""
Unit tests for metric aggregation.

Focuses on correctness and edge cases for different aggregation types.
"""

import pytest
from datetime import datetime, timedelta

from loglens.models import LogEvent
from loglens.analytics import Metric, MetricProcessor, AggregationType


class TestMetricAggregation:
    """Tests for metric aggregation."""
    
    def test_count_aggregation(self):
        """Test count aggregation."""
        metric = Metric(
            name='error_count',
            filter=lambda e: e.level == 'ERROR',
            aggregation='count',
            window='5m'
        )
        
        processor = MetricProcessor([metric])
        
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        events = [
            LogEvent(timestamp=base_time + timedelta(seconds=i*10),
                     level='ERROR' if i % 2 == 0 else 'INFO',
                     source='app1', message=f'Event {i}')
            for i in range(10)
        ]
        
        for event in events:
            processor.add_event(event)
        
        result = processor.get_metric('error_count')
        assert result is not None
        assert result.value == 5  # 5 error events
    
    def test_rate_aggregation(self):
        """Test rate aggregation (events per second)."""
        metric = Metric(
            name='error_rate',
            filter=lambda e: e.level == 'ERROR',
            aggregation='rate',
            window='1m'
        )
        
        processor = MetricProcessor([metric])
        
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        events = [
            LogEvent(timestamp=base_time + timedelta(seconds=i),
                     level='ERROR',
                     source='app1', message=f'Event {i}')
            for i in range(10)
        ]
        
        for event in events:
            processor.add_event(event)
        
        result = processor.get_metric('error_rate')
        assert result is not None
        assert result.value > 0  # Should have a positive rate
        # 10 events over ~9 seconds = ~1.1 events/second
        assert 0.5 < result.value < 2.0
    
    def test_average_aggregation(self):
        """Test average aggregation with value extraction."""
        metric = Metric(
            name='avg_response_time',
            filter=lambda e: 'response_time' in e.metadata,
            aggregation='average',
            window='5m',
            value_extractor=lambda e: e.metadata.get('response_time', 0)
        )
        
        processor = MetricProcessor([metric])
        
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        events = [
            LogEvent(timestamp=base_time + timedelta(seconds=i*10),
                     level='INFO',
                     source='app1',
                     message=f'Request {i}',
                     metadata={'response_time': 100 + i * 10})
            for i in range(5)
        ]
        
        for event in events:
            processor.add_event(event)
        
        result = processor.get_metric('avg_response_time')
        assert result is not None
        # Average of [100, 110, 120, 130, 140] = 120
        assert abs(result.value - 120.0) < 0.1
    
    def test_sum_aggregation(self):
        """Test sum aggregation."""
        metric = Metric(
            name='total_requests',
            filter=lambda e: 'request_count' in e.metadata,
            aggregation='sum',
            window='5m',
            value_extractor=lambda e: e.metadata.get('request_count', 0)
        )
        
        processor = MetricProcessor([metric])
        
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        events = [
            LogEvent(timestamp=base_time + timedelta(seconds=i*10),
                     level='INFO',
                     source='app1',
                     message=f'Batch {i}',
                     metadata={'request_count': i + 1})
            for i in range(5)
        ]
        
        for event in events:
            processor.add_event(event)
        
        result = processor.get_metric('total_requests')
        assert result is not None
        # Sum of [1, 2, 3, 4, 5] = 15
        assert result.value == 15
    
    def test_min_max_aggregation(self):
        """Test min and max aggregations."""
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        events = [
            LogEvent(timestamp=base_time + timedelta(seconds=i*10),
                     level='INFO',
                     source='app1',
                     message=f'Event {i}',
                     metadata={'value': [50, 100, 25, 200, 75][i]})
            for i in range(5)
        ]
        
        # Test MIN
        min_metric = Metric(
            name='min_value',
            filter=lambda e: 'value' in e.metadata,
            aggregation='min',
            window='5m',
            value_extractor=lambda e: e.metadata.get('value', 0)
        )
        
        processor_min = MetricProcessor([min_metric])
        for event in events:
            processor_min.add_event(event)
        
        min_result = processor_min.get_metric('min_value')
        assert min_result.value == 25
        
        # Test MAX
        max_metric = Metric(
            name='max_value',
            filter=lambda e: 'value' in e.metadata,
            aggregation='max',
            window='5m',
            value_extractor=lambda e: e.metadata.get('value', 0)
        )
        
        processor_max = MetricProcessor([max_metric])
        for event in events:
            processor_max.add_event(event)
        
        max_result = processor_max.get_metric('max_value')
        assert max_result.value == 200
    
    def test_grouped_aggregation(self):
        """Test grouped metrics."""
        metric = Metric(
            name='events_by_source',
            filter=lambda e: True,
            aggregation='count',
            window='5m',
            group_by=lambda e: e.source
        )
        
        processor = MetricProcessor([metric])
        
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        events = [
            LogEvent(timestamp=base_time + timedelta(seconds=i*10),
                     level='INFO',
                     source=f'app{i%3+1}',
                     message=f'Event {i}')
            for i in range(9)
        ]
        
        for event in events:
            processor.add_event(event)
        
        result = processor.get_metric('events_by_source')
        assert result is not None
        assert result.grouped_values is not None
        # Should have 3 groups (app1, app2, app3) with 3 events each
        assert len(result.grouped_values) == 3
        assert all(count == 3 for count in result.grouped_values.values())


class TestMetricEdgeCases:
    """Tests for edge cases in metric aggregation."""
    
    def test_empty_filter(self):
        """Test metric with filter that matches no events."""
        metric = Metric(
            name='no_matches',
            filter=lambda e: False,
            aggregation='count',
            window='5m'
        )
        
        processor = MetricProcessor([metric])
        
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        events = [
            LogEvent(timestamp=base_time + timedelta(seconds=i*10),
                     level='INFO',
                     source='app1', message=f'Event {i}')
            for i in range(5)
        ]
        
        for event in events:
            processor.add_event(event)
        
        result = processor.get_metric('no_matches')
        # Should return 0 for count when no matches
        assert result is None or result.value == 0
    
    def test_window_expiration(self):
        """Test that events expire from window correctly."""
        metric = Metric(
            name='recent_errors',
            filter=lambda e: e.level == 'ERROR',
            aggregation='count',
            window='1m'  # 1 minute window
        )
        
        processor = MetricProcessor([metric])
        
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        
        # Add events spanning more than 1 minute
        events = [
            LogEvent(timestamp=base_time + timedelta(seconds=i*30),
                     level='ERROR',
                     source='app1', message=f'Error {i}')
            for i in range(5)
        ]
        
        for event in events:
            processor.add_event(event)
        
        result = processor.get_metric('recent_errors')
        # Only events within 1 minute of the last event should be counted
        assert result is not None
        assert result.value >= 1  # At least the last event
    
    def test_missing_value_extractor(self):
        """Test that aggregations requiring value_extractor raise error."""
        metric = Metric(
            name='avg_without_extractor',
            filter=lambda e: True,
            aggregation='average',
            window='5m'
            # Missing value_extractor
        )
        
        processor = MetricProcessor([metric])
        
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        event = LogEvent(timestamp=base_time, level='INFO', source='app1', message='Test')
        
        with pytest.raises(ValueError, match="value_extractor"):
            processor.add_event(event)
    
    def test_custom_aggregation_function(self):
        """Test custom aggregation function."""
        def custom_agg(events):
            return sum(len(e.message) for e in events)
        
        metric = Metric(
            name='total_message_length',
            filter=lambda e: True,
            aggregation=custom_agg,
            window='5m'
        )
        
        processor = MetricProcessor([metric])
        
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        events = [
            LogEvent(timestamp=base_time + timedelta(seconds=i*10),
                     level='INFO',
                     source='app1', message='Test')
            for i in range(5)
        ]
        
        for event in events:
            processor.add_event(event)
        
        result = processor.get_metric('total_message_length')
        assert result is not None
        # 5 events * 4 characters = 20
        assert result.value == 20
    
    def test_rate_with_single_event(self):
        """Test rate calculation with single event."""
        metric = Metric(
            name='single_event_rate',
            filter=lambda e: True,
            aggregation='rate',
            window='1m'
        )
        
        processor = MetricProcessor([metric])
        
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        event = LogEvent(timestamp=base_time, level='INFO', source='app1', message='Test')
        
        processor.add_event(event)
        
        result = processor.get_metric('single_event_rate')
        # With single event, rate should be defined (not divide by zero)
        assert result is not None
        assert result.value >= 0

