"""
Anomaly detection for time series metrics.

This module provides anomaly detection using rolling statistics
(mean and standard deviation) to flag sudden spikes or drops in metrics.
"""

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Callable
from enum import Enum

import math


class AnomalyType(Enum):
    """Type of anomaly detected."""
    SPIKE = "spike"
    DROP = "drop"
    NONE = "none"


@dataclass
class Anomaly:
    """
    Represents a detected anomaly in a time series metric.
    
    Attributes:
        metric_name: Name of the metric
        timestamp: When the anomaly was detected
        value: The anomalous value
        baseline_mean: The rolling mean (baseline)
        baseline_std: The rolling standard deviation
        z_score: Z-score of the anomaly
        anomaly_type: Type of anomaly (spike or drop)
        explanation: Human-readable explanation
        severity: Severity level (low, medium, high, critical)
    """
    
    metric_name: str
    timestamp: datetime
    value: float
    baseline_mean: float
    baseline_std: float
    z_score: float
    anomaly_type: AnomalyType
    explanation: str
    severity: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'metric_name': self.metric_name,
            'timestamp': self.timestamp.isoformat(),
            'value': self.value,
            'baseline_mean': self.baseline_mean,
            'baseline_std': self.baseline_std,
            'z_score': self.z_score,
            'anomaly_type': self.anomaly_type.value,
            'explanation': self.explanation,
            'severity': self.severity
        }
    
    def __repr__(self) -> str:
        """String representation."""
        return f"Anomaly({self.metric_name}: {self.explanation})"


class AnomalyDetector:
    """
    Detects anomalies in time series metrics using rolling statistics.
    
    Uses a rolling window to compute mean and standard deviation,
    then flags values that deviate significantly from the baseline.
    """
    
    def __init__(
        self,
        metric_name: str,
        window_size: int = 20,
        threshold: float = 2.0,
        min_samples: int = 5
    ):
        """
        Initialize the anomaly detector.
        
        Args:
            metric_name: Name of the metric being monitored
            window_size: Number of samples in the rolling window
            threshold: Z-score threshold for flagging anomalies (default: 2.0)
            min_samples: Minimum samples needed before detecting anomalies
        """
        self.metric_name = metric_name
        self.window_size = window_size
        self.threshold = threshold
        self.min_samples = min_samples
        
        # Rolling window of values
        self.values: deque = deque(maxlen=window_size)
        
        # Rolling window of timestamps
        self.timestamps: deque = deque(maxlen=window_size)
    
    def add_value(self, value: float, timestamp: Optional[datetime] = None) -> Optional[Anomaly]:
        """
        Add a new value and check for anomalies.
        
        Args:
            value: New metric value
            timestamp: Timestamp of the value (defaults to now)
        
        Returns:
            Anomaly object if detected, None otherwise
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Add to rolling window
        self.values.append(value)
        self.timestamps.append(timestamp)
        
        # Need minimum samples before detecting
        if len(self.values) < self.min_samples:
            return None
        
        # Calculate statistics
        mean = self._calculate_mean()
        std = self._calculate_std(mean)
        
        # Skip if std is too small (constant values)
        if std < 1e-10:
            return None
        
        # Calculate z-score
        z_score = (value - mean) / std
        
        # Check if anomaly
        if abs(z_score) >= self.threshold:
            anomaly_type = AnomalyType.SPIKE if z_score > 0 else AnomalyType.DROP
            explanation = self._generate_explanation(value, mean, std, z_score, anomaly_type)
            severity = self._calculate_severity(abs(z_score))
            
            return Anomaly(
                metric_name=self.metric_name,
                timestamp=timestamp,
                value=value,
                baseline_mean=mean,
                baseline_std=std,
                z_score=z_score,
                anomaly_type=anomaly_type,
                explanation=explanation,
                severity=severity
            )
        
        return None
    
    def _calculate_mean(self) -> float:
        """Calculate mean of values in rolling window."""
        if not self.values:
            return 0.0
        return sum(self.values) / len(self.values)
    
    def _calculate_std(self, mean: Optional[float] = None) -> float:
        """Calculate standard deviation of values in rolling window."""
        if len(self.values) < 2:
            return 0.0
        
        if mean is None:
            mean = self._calculate_mean()
        
        variance = sum((x - mean) ** 2 for x in self.values) / len(self.values)
        return math.sqrt(variance)
    
    def _generate_explanation(
        self,
        value: float,
        mean: float,
        std: float,
        z_score: float,
        anomaly_type: AnomalyType
    ) -> str:
        """
        Generate human-readable explanation for the anomaly.
        
        Args:
            value: The anomalous value
            mean: Baseline mean
            std: Baseline standard deviation
            z_score: Z-score
            anomaly_type: Type of anomaly
        
        Returns:
            Human-readable explanation string
        """
        abs_z = abs(z_score)
        
        if anomaly_type == AnomalyType.SPIKE:
            if mean > 0:
                multiplier = value / mean
                if multiplier >= 2.0:
                    return f"{self.metric_name} spiked {multiplier:.1f}x above baseline ({value:.2f} vs {mean:.2f} average)"
                else:
                    return f"{self.metric_name} spiked {abs_z:.1f} standard deviations above baseline ({value:.2f} vs {mean:.2f} average)"
            else:
                return f"{self.metric_name} spiked to {value:.2f} ({abs_z:.1f} standard deviations above baseline)"
        else:  # DROP
            if mean > 0:
                multiplier = mean / value if value > 0 else float('inf')
                if multiplier >= 2.0:
                    return f"{self.metric_name} dropped {multiplier:.1f}x below baseline ({value:.2f} vs {mean:.2f} average)"
                else:
                    return f"{self.metric_name} dropped {abs_z:.1f} standard deviations below baseline ({value:.2f} vs {mean:.2f} average)"
            else:
                return f"{self.metric_name} dropped to {value:.2f} ({abs_z:.1f} standard deviations below baseline)"
    
    def _calculate_severity(self, abs_z_score: float) -> str:
        """
        Calculate severity based on z-score.
        
        Args:
            abs_z_score: Absolute z-score
        
        Returns:
            Severity level (low, medium, high, critical)
        """
        if abs_z_score >= 4.0:
            return "critical"
        elif abs_z_score >= 3.0:
            return "high"
        elif abs_z_score >= 2.5:
            return "medium"
        else:
            return "low"
    
    def get_baseline_stats(self) -> Dict[str, float]:
        """
        Get current baseline statistics.
        
        Returns:
            Dictionary with mean and std
        """
        mean = self._calculate_mean()
        std = self._calculate_std(mean)
        return {
            'mean': mean,
            'std': std,
            'sample_count': len(self.values)
        }
    
    def reset(self) -> None:
        """Reset the detector (clear rolling window)."""
        self.values.clear()
        self.timestamps.clear()


class MultiMetricAnomalyDetector:
    """
    Detects anomalies across multiple metrics simultaneously.
    
    Useful for monitoring multiple metrics and getting a unified
    view of system health.
    """
    
    def __init__(
        self,
        window_size: int = 20,
        threshold: float = 2.0,
        min_samples: int = 5
    ):
        """
        Initialize multi-metric detector.
        
        Args:
            window_size: Rolling window size for each metric
            threshold: Z-score threshold
            min_samples: Minimum samples before detecting
        """
        self.window_size = window_size
        self.threshold = threshold
        self.min_samples = min_samples
        self.detectors: Dict[str, AnomalyDetector] = {}
    
    def add_metric_value(
        self,
        metric_name: str,
        value: float,
        timestamp: Optional[datetime] = None
    ) -> Optional[Anomaly]:
        """
        Add a metric value and check for anomalies.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            timestamp: Timestamp (defaults to now)
        
        Returns:
            Anomaly if detected, None otherwise
        """
        # Get or create detector for this metric
        if metric_name not in self.detectors:
            self.detectors[metric_name] = AnomalyDetector(
                metric_name=metric_name,
                window_size=self.window_size,
                threshold=self.threshold,
                min_samples=self.min_samples
            )
        
        detector = self.detectors[metric_name]
        return detector.add_value(value, timestamp)
    
    def get_all_anomalies(
        self,
        metric_values: Dict[str, float],
        timestamp: Optional[datetime] = None
    ) -> List[Anomaly]:
        """
        Check multiple metrics at once.
        
        Args:
            metric_values: Dictionary of metric_name -> value
            timestamp: Timestamp (defaults to now)
        
        Returns:
            List of detected anomalies
        """
        anomalies = []
        for metric_name, value in metric_values.items():
            anomaly = self.add_metric_value(metric_name, value, timestamp)
            if anomaly:
                anomalies.append(anomaly)
        
        return anomalies
    
    def get_baseline_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Get baseline statistics for all metrics.
        
        Returns:
            Dictionary of metric_name -> stats
        """
        return {
            name: detector.get_baseline_stats()
            for name, detector in self.detectors.items()
        }
    
    def reset(self, metric_name: Optional[str] = None) -> None:
        """
        Reset detector(s).
        
        Args:
            metric_name: If provided, reset only this metric. Otherwise reset all.
        """
        if metric_name:
            if metric_name in self.detectors:
                self.detectors[metric_name].reset()
        else:
            for detector in self.detectors.values():
                detector.reset()


def create_detector(
    metric_name: str,
    window_size: int = 20,
    threshold: float = 2.0
) -> AnomalyDetector:
    """
    Create an anomaly detector for a single metric.
    
    Args:
        metric_name: Name of the metric
        window_size: Rolling window size
        threshold: Z-score threshold
    
    Returns:
        AnomalyDetector instance
    """
    return AnomalyDetector(metric_name, window_size, threshold)


def create_multi_detector(
    window_size: int = 20,
    threshold: float = 2.0
) -> MultiMetricAnomalyDetector:
    """
    Create a multi-metric anomaly detector.
    
    Args:
        window_size: Rolling window size
        threshold: Z-score threshold
    
    Returns:
        MultiMetricAnomalyDetector instance
    """
    return MultiMetricAnomalyDetector(window_size, threshold)

