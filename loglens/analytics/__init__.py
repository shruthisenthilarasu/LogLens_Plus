"""
Analytics module.

This module handles metrics calculation, pattern detection, and insights generation.
"""

from loglens.analytics.metrics import (
    Metric,
    MetricResult,
    MetricProcessor,
    AggregationType,
    error_rate_metric,
    warning_rate_metric,
    events_by_source_metric,
    events_by_level_metric,
)

from loglens.analytics.anomaly_detector import (
    AnomalyDetector,
    MultiMetricAnomalyDetector,
    Anomaly,
    AnomalyType,
    create_detector,
    create_multi_detector,
)

__all__ = [
    'Metric',
    'MetricResult',
    'MetricProcessor',
    'AggregationType',
    'error_rate_metric',
    'warning_rate_metric',
    'events_by_source_metric',
    'events_by_level_metric',
    'AnomalyDetector',
    'MultiMetricAnomalyDetector',
    'Anomaly',
    'AnomalyType',
    'create_detector',
    'create_multi_detector',
]

