#!/usr/bin/env python3
"""
Anomaly Detection Quick Start

Simple examples for getting started with anomaly detection.
"""

from datetime import datetime, timedelta
from loglens.analytics import create_detector, create_multi_detector


# Example 1: Monitor a single metric
def monitor_error_rate():
    """Monitor error rate for anomalies."""
    
    # Create detector
    detector = create_detector(
        metric_name='error_rate',
        window_size=20,    # Use last 20 values for baseline
        threshold=2.0       # Flag if z-score >= 2.0
    )
    
    # Add values over time
    base_time = datetime.now()
    
    # Normal values (build baseline)
    for i in range(20):
        value = 10 + (i % 3)  # Normal: 10-12
        detector.add_value(value, base_time + timedelta(minutes=i*5))
    
    # Add a spike
    anomaly = detector.add_value(30, base_time + timedelta(minutes=100))
    
    if anomaly:
        print(f"🚨 {anomaly.explanation}")
        print(f"   Severity: {anomaly.severity}")
        # Example output: "error_rate spiked 2.3x above baseline (30.00 vs 13.00 average)"


# Example 2: Monitor multiple metrics
def monitor_multiple_metrics():
    """Monitor multiple metrics simultaneously."""
    
    detector = create_multi_detector(window_size=15, threshold=2.0)
    
    # Build baselines
    base_time = datetime.now()
    for i in range(15):
        timestamp = base_time + timedelta(minutes=i*5)
        detector.add_metric_value('error_count', 10 + i % 3, timestamp)
        detector.add_metric_value('response_time', 100 + i * 2, timestamp)
    
    # Check current values
    current_metrics = {
        'error_count': 35,      # Spike!
        'response_time': 50,     # Drop
    }
    
    anomalies = detector.get_all_anomalies(current_metrics)
    
    for anomaly in anomalies:
        print(f"🚨 {anomaly.metric_name}: {anomaly.explanation}")


# Example 3: Real-time monitoring pattern
def real_time_monitoring():
    """Pattern for real-time monitoring."""
    
    detector = create_detector('error_rate', window_size=30, threshold=2.0)
    
    # In your monitoring loop:
    while True:
        # Get current metric value (from your metric processor)
        current_value = get_current_error_rate()  # Your function
        
        # Check for anomaly
        anomaly = detector.add_value(current_value)
        
        if anomaly:
            # Send alert
            send_alert(anomaly.explanation)
            # Example: "Error rate spiked 2.3x above baseline in the last 10 minutes."


if __name__ == "__main__":
    print("Anomaly Detection Quick Start Examples")
    print("=" * 70)
    
    print("\n1. Single Metric Monitoring:")
    monitor_error_rate()
    
    print("\n2. Multi-Metric Monitoring:")
    monitor_multiple_metrics()
    
    print("\n" + "=" * 70)
    print("See examples/anomaly_detection_example.py for more details")

