#!/usr/bin/env python3
"""
LogLens++ Workflow Demonstration

This script demonstrates the complete workflow:
1. Ingestion → 2. Query → 3. Anomaly Detection

Can be used to create a GIF or video showing the workflow.
"""

import time
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

from loglens.models import LogEvent
from loglens.ingestion import LogIngestor
from loglens.storage import LogStorage, create_query
from loglens.analytics import Metric, MetricProcessor, create_detector


def print_step(step_num: int, title: str, description: str):
    """Print a workflow step with visual formatting."""
    print("\n" + "=" * 70)
    print(f"STEP {step_num}: {title}")
    print("=" * 70)
    print(description)
    print()


def workflow_demo():
    """Demonstrate the complete LogLens++ workflow."""
    
    db_path = "workflow_demo.db"
    
    # Clean up if exists
    if Path(db_path).exists():
        Path(db_path).unlink()
    
    # ========================================================================
    # STEP 1: INGESTION
    # ========================================================================
    print_step(1, "INGESTION", "Ingesting logs from file...")
    
    # Create sample log file
    log_file = Path("demo_logs.json")
    import json
    with open(log_file, 'w') as f:
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        for i in range(50):
            timestamp = base_time + timedelta(seconds=i*30)
            level = 'ERROR' if i % 10 == 0 else 'WARNING' if i % 5 == 0 else 'INFO'
            source = f'app{i%3+1}'
            
            log_entry = {
                "timestamp": timestamp.isoformat(),
                "level": level,
                "source": source,
                "message": f"Request {i} processed",
                "metadata": {"request_id": f"req_{i}"}
            }
            f.write(json.dumps(log_entry) + "\n")
    
    print(f"📄 Created log file: {log_file}")
    print(f"   Contains 50 log events")
    
    # Ingest logs
    storage = LogStorage(db_path)
    ingestor = LogIngestor()
    
    event_count = 0
    print("\n🔄 Processing logs...")
    for event in ingestor.ingest_file(log_file, format='json'):
        storage.insert_event(event)
        event_count += 1
        if event_count % 10 == 0:
            print(f"   Processed {event_count} events...", end='\r')
    
    print(f"\n✅ Ingested {event_count} events into database")
    storage.close()
    
    time.sleep(1)
    
    # ========================================================================
    # STEP 2: METRICS & QUERY
    # ========================================================================
    print_step(2, "METRICS & QUERY", "Computing metrics and querying data...")
    
    storage = LogStorage(db_path)
    query = create_query(storage)
    
    # Define and compute metrics
    print("📊 Computing metrics...")
    metrics = [
        Metric(name='error_count', filter=lambda e: e.level == 'ERROR',
               aggregation='count', window='5m'),
        Metric(name='events_by_source', filter=lambda e: True,
               aggregation='count', window='5m', group_by=lambda e: e.source),
    ]
    
    processor = MetricProcessor(metrics)
    
    # Re-process events to compute metrics
    events = storage.query_events(limit=None)
    from loglens.models import LogEvent as LE
    
    metric_count = 0
    for event_data in events:
        event = LE(
            timestamp=datetime.fromisoformat(str(event_data['timestamp'])),
            level=event_data['level'],
            source=event_data['source'],
            message=event_data['message'],
            metadata=event_data.get('metadata', {})
        )
        updated = processor.add_event(event)
        for metric_name, result in updated.items():
            storage.insert_metric(
                metric_name=result.metric_name,
                window_start=result.window_start,
                window_end=result.window_end,
                value=result.value,
                grouped_values=result.grouped_values
            )
            metric_count += 1
    
    print(f"✅ Computed {metric_count} metric values")
    
    # Query 1: Error events
    print("\n📝 Query 1: Get error events")
    error_events = storage.query_events(level='ERROR', limit=5)
    print(f"   Found {len(error_events)} error events")
    for event in error_events[:3]:
        print(f"   • {event['timestamp']}: {event['source']} - {event['message']}")
    
    # Query 2: SQL aggregation
    print("\n📝 Query 2: Events by level (SQL)")
    sql_results = query.execute_sql(
        "SELECT level, COUNT(*) as count FROM events GROUP BY level ORDER BY count DESC"
    )
    for row in sql_results:
        print(f"   • {row['level']}: {row['count']} events")
    
    # Query 3: Time bucket query
    print("\n📝 Query 3: Error rate by hour")
    bucket_results = query.query_metrics_by_time_bucket(
        'error_count',
        bucket_size='hour',
        start_time=base_time,
        end_time=base_time + timedelta(hours=1)
    )
    for result in bucket_results[:3]:
        print(f"   • {result['bucket_time']}: {result['metric_value']:.1f} errors")
    
    storage.close()
    time.sleep(1)
    
    # ========================================================================
    # STEP 3: ANOMALY DETECTION
    # ========================================================================
    print_step(3, "ANOMALY DETECTION", "Detecting anomalies in metrics...")
    
    storage = LogStorage(db_path)
    
    # Get metric values
    metrics_list = storage.query_metrics(metric_name='error_count', limit=20)
    
    if metrics_list:
        print("🔍 Building baseline from historical data...")
        
        # Create detector
        detector = create_detector('error_count', window_size=15, threshold=2.0)
        
        # Build baseline
        for m in reversed(metrics_list[:10]):
            if m['value'] is not None:
                window_start = datetime.fromisoformat(str(m['window_start']))
                detector.add_value(m['value'], window_start)
        
        print("✅ Baseline established")
        
        # Check for anomalies in recent values
        print("\n🔍 Checking for anomalies...")
        anomalies_found = []
        
        for m in reversed(metrics_list[10:]):
            if m['value'] is not None:
                window_start = datetime.fromisoformat(str(m['window_start']))
                anomaly = detector.add_value(m['value'], window_start)
                
                if anomaly:
                    anomalies_found.append(anomaly)
                    print(f"\n🚨 ANOMALY DETECTED!")
                    print(f"   {anomaly.explanation}")
                    print(f"   Timestamp: {anomaly.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                    print(f"   Severity: {anomaly.severity.upper()}")
                    print(f"   Z-score: {anomaly.z_score:.2f}")
        
        if not anomalies_found:
            print("✅ No anomalies detected - all metrics within normal range")
    else:
        print("⚠️  No metrics available for anomaly detection")
    
    storage.close()
    time.sleep(1)
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "=" * 70)
    print("WORKFLOW COMPLETE")
    print("=" * 70)
    print("\n✅ Logs ingested")
    print("✅ Metrics computed")
    print("✅ Queries executed")
    print("✅ Anomalies checked")
    print(f"\n📁 Database: {db_path}")
    print(f"📄 Log file: {log_file}")
    print("\n" + "=" * 70)
    
    # Cleanup
    if log_file.exists():
        log_file.unlink()


if __name__ == "__main__":
    try:
        workflow_demo()
    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

