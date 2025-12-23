# Database Schema Documentation

This document describes the database schemas used by LogLens++ for storing log events and metrics.

## Database: DuckDB

LogLens++ uses DuckDB, an in-process analytical database optimized for analytics workloads. DuckDB provides:
- Fast columnar storage
- Efficient time-series queries
- SQL interface
- Embedded (no separate server needed)

## Tables

### Events Table

Stores raw log events with full details.

**Schema:**
```sql
CREATE TABLE events (
    id BIGINT PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    level VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    message TEXT NOT NULL,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Columns:**
- `id`: Unique identifier (auto-increment)
- `timestamp`: Event timestamp (indexed)
- `level`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL, etc.) (indexed)
- `source`: Source identifier (e.g., service name) (indexed)
- `message`: Log message content
- `metadata`: JSON object with additional structured data
- `created_at`: When the event was stored in the database

**Indexes:**
- `idx_events_timestamp`: On `timestamp` for time-range queries
- `idx_events_level`: On `level` for filtering by log level
- `idx_events_source`: On `source` for filtering by source

**Example Query:**
```python
# Get all error events in the last hour
events = storage.query_events(
    start_time=datetime.now() - timedelta(hours=1),
    level='ERROR'
)
```

### Metrics Table

Stores aggregated metric results computed over time windows.

**Schema:**
```sql
CREATE TABLE metrics (
    id BIGINT PRIMARY KEY,
    metric_name VARCHAR NOT NULL,
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    value DOUBLE,
    grouped_values JSON,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Columns:**
- `id`: Unique identifier (auto-increment)
- `metric_name`: Name of the metric (indexed)
- `window_start`: Start of the time window (indexed)
- `window_end`: End of the time window (indexed)
- `value`: Single metric value (for non-grouped metrics)
- `grouped_values`: JSON object with grouped values (for grouped metrics)
- `metadata`: Additional metadata about the metric
- `created_at`: When the metric was stored

**Indexes:**
- `idx_metrics_name`: On `metric_name` for filtering by metric
- `idx_metrics_window`: On `(window_start, window_end)` for time-range queries
- `idx_metrics_name_window`: Composite index on `(metric_name, window_start, window_end)` for efficient metric queries

**Example Query:**
```python
# Get error_count metrics for the last day
metrics = storage.query_metrics(
    metric_name='error_count',
    start_time=datetime.now() - timedelta(days=1)
)
```

## Usage Patterns

### Storing Events

```python
from loglens.storage import LogStorage
from loglens.models import LogEvent

storage = LogStorage("logs.db")

# Single event
event = LogEvent(
    timestamp=datetime.now(),
    level='ERROR',
    source='app1',
    message='Database connection failed'
)
event_id = storage.insert_event(event)

# Batch insert
events = [event1, event2, event3]
event_ids = storage.insert_events(events)
```

### Storing Metrics

```python
# Store a metric result
metric_id = storage.insert_metric(
    metric_name='error_count',
    window_start=datetime.now() - timedelta(minutes=5),
    window_end=datetime.now(),
    value=42
)

# Store a grouped metric
metric_id = storage.insert_metric(
    metric_name='events_by_source',
    window_start=datetime.now() - timedelta(minutes=5),
    window_end=datetime.now(),
    grouped_values={'app1': 20, 'app2': 22}
)
```

### Querying

```python
# Query events
events = storage.query_events(
    start_time=datetime.now() - timedelta(hours=1),
    level='ERROR',
    limit=100
)

# Query metrics
metrics = storage.query_metrics(
    metric_name='error_count',
    start_time=datetime.now() - timedelta(days=1)
)

# Get statistics
stats = storage.get_event_stats()
summary = storage.get_metric_summary('error_count')
```

### Data Retention

```python
# Delete old events (older than 30 days)
cutoff = datetime.now() - timedelta(days=30)
deleted = storage.delete_old_events(cutoff)

# Delete old metrics
deleted = storage.delete_old_metrics(cutoff)

# Optimize database
storage.vacuum()
```

## Integration with Metrics System

Use `PersistentMetricProcessor` for automatic storage:

```python
from loglens.storage import create_persistent_processor
from loglens.analytics import Metric

metrics = [
    Metric(name='error_count', filter=lambda e: e.level == 'ERROR',
           aggregation='count', window='5m'),
]

processor = create_persistent_processor('logs.db', metrics, auto_store=True)

# Events and metrics are automatically stored
for event in log_stream:
    processor.add_event(event)
```

## Performance Considerations

1. **Batch Inserts**: Use `insert_events()` for multiple events
2. **Indexes**: All time-based and filter columns are indexed
3. **Vacuum**: Periodically run `vacuum()` to optimize storage
4. **Data Retention**: Regularly delete old data to maintain performance

## File Format

DuckDB stores data in a single file (`.db` extension). The file is:
- Portable (can be moved between systems)
- Self-contained (no external dependencies)
- Efficient (columnar storage format)

