#!/usr/bin/env python3
"""
Anomaly Detection Example

This example demonstrates how to use the anomaly detection module
to monitor metrics and get human-readable explanations when anomalies occur.
"""

from datetime import datetime, timedelta
from loglens.analytics import (
    AnomalyDetector,
    MultiMetricAnomalyDetector,
    create_detector,
    create_multi_detector
)


def main():
    """Demonstrate anomaly detection."""
    
    print("=" * 70)
    print("LogLens++ Anomaly Detection Example")
    print("=" * 70)
    
    # Example 1: Single metric monitoring
    print("\n1. Monitoring Error Rate")
    print("-" * 70)
    
    detector = create_detector(
        metric_name='error_rate',
        window_size=20,  # Use last 20 samples for baseline
        threshold=2.0     # Flag if z-score >= 2.0
    )
    
    # Simulate normal operation
    base_time = datetime(2024, 1, 1, 12, 0, 0)
    print("  Building baseline with normal values...")
    
    # Normal error rates (around 5-8 per hour)
    normal_values = [6, 7, 5, 8, 6, 7, 5, 6, 8, 7, 6, 5, 7, 6, 8, 5, 7, 6, 8, 7]
    
    for i, value in enumerate(normal_values):
        timestamp = base_time + timedelta(minutes=i*10)
        detector.add_value(value, timestamp)
    
    print("  Baseline established")
    
    # Now add some anomalies
    print("\n  Monitoring for anomalies...")
    
    # Spike: Error rate suddenly increases
    spike_time = base_time + timedelta(minutes=200)
    spike_value = 25  # Much higher than normal
    anomaly = detector.add_value(spike_value, spike_time)
    
    if anomaly:
        print(f"\n  🚨 ALERT: {anomaly.explanation}")
        print(f"     Detected at: {anomaly.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"     Severity: {anomaly.severity.upper()}")
        print(f"     Z-score: {anomaly.z_score:.2f}")
    
    # Example 2: Multi-metric monitoring
    print("\n2. Multi-Metric Monitoring")
    print("-" * 70)
    
    multi_detector = create_multi_detector(
        window_size=15,
        threshold=2.0
    )
    
    print("  Building baselines for multiple metrics...")
    
    # Build baselines
    for i in range(15):
        timestamp = base_time + timedelta(minutes=i*10)
        multi_detector.add_metric_value('error_count', 10 + i % 3, timestamp)
        multi_detector.add_metric_value('response_time_ms', 150 + i * 2, timestamp)
        multi_detector.add_metric_value('requests_per_sec', 100 - i, timestamp)
    
    print("  Baselines established")
    
    # Check for anomalies across all metrics
    print("\n  Checking current metrics...")
    current_metrics = {
        'error_count': 45,        # Spike!
        'response_time_ms': 80,   # Drop (good, but unusual)
        'requests_per_sec': 50,   # Drop
    }
    
    anomalies = multi_detector.get_all_anomalies(
        current_metrics,
        base_time + timedelta(minutes=150)
    )
    
    if anomalies:
        print(f"\n  🚨 Detected {len(anomalies)} anomaly(ies):")
        for anomaly in anomalies:
            print(f"\n     {anomaly.metric_name}:")
            print(f"       {anomaly.explanation}")
            print(f"       Severity: {anomaly.severity.upper()}")
    else:
        print("  ✓ All metrics within normal range")
    
    # Example 3: Real-time monitoring simulation
    print("\n3. Real-Time Monitoring Simulation")
    print("-" * 70)
    
    # Monitor error rate over time
    error_detector = create_detector('error_rate', window_size=30, threshold=2.0)
    
    # Simulate 6 hours of monitoring (every 5 minutes)
    print("  Simulating 6 hours of monitoring (checking every 5 minutes)...")
    
    # Generate realistic values with some anomalies
    import random
    random.seed(42)  # For reproducibility
    
    anomalies_detected = []
    for hour in range(6):
        for minute in [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]:
            timestamp = base_time + timedelta(hours=hour, minutes=minute)
            
            # Normal error rate with some variation
            if hour == 2 and minute == 30:
                # Simulate a spike at 2:30
                value = 40
            elif hour == 4 and minute == 15:
                # Simulate another spike at 4:15
                value = 35
            else:
                # Normal: 5-10 errors per check
                value = random.randint(5, 10)
            
            anomaly = error_detector.add_value(value, timestamp)
            
            if anomaly:
                anomalies_detected.append(anomaly)
                print(f"\n  🚨 {timestamp.strftime('%H:%M')} - {anomaly.explanation}")
                print(f"     Severity: {anomaly.severity.upper()}")
    
    print(f"\n  Summary: Detected {len(anomalies_detected)} anomalies in 6 hours")
    
    # Example 4: Integration with metrics
    print("\n4. Integration with Metric Processor")
    print("-" * 70)
    
    from loglens.analytics import Metric, MetricProcessor
    
    # Define metrics
    metrics = [
        Metric(name='error_count', filter=lambda e: e.level == 'ERROR',
               aggregation='count', window='5m'),
    ]
    
    processor = MetricProcessor(metrics)
    
    # Create detector for the metric
    metric_detector = create_detector('error_count', window_size=20, threshold=2.0)
    
    print("  Processing events and monitoring for anomalies...")
    
    from loglens.models import LogEvent
    
    # Simulate events
    events = []
    for i in range(50):
        level = 'ERROR' if i % 5 == 0 else 'INFO'
        events.append(LogEvent(
            timestamp=base_time + timedelta(minutes=i*2),
            level=level,
            source='app1',
            message=f'Event {i}'
        ))
    
    # Process and monitor
    for event in events:
        updated = processor.add_event(event)
        for metric_name, result in updated.items():
            if result.value is not None:
                anomaly = metric_detector.add_value(result.value, result.window_end)
                if anomaly:
                    print(f"\n  🚨 {anomaly.explanation}")
    
    print("\n" + "=" * 70)
    print("✓ Anomaly detection example complete!")
    print("=" * 70)
    print("\nKey Features:")
    print("  • Rolling mean and standard deviation for baseline")
    print("  • Z-score based anomaly detection")
    print("  • Human-readable explanations")
    print("  • Severity levels (low, medium, high, critical)")
    print("  • Multi-metric support")


if __name__ == "__main__":
    main()

