# LogLens++ Design Document

This document explains the architectural decisions, design tradeoffs, and future directions for LogLens++.

## Table of Contents

1. [Core Design Principles](#core-design-principles)
2. [Architecture Decisions](#architecture-decisions)
3. [Design Tradeoffs](#design-tradeoffs)
4. [Implementation Details](#implementation-details)
5. [Extensibility](#extensibility)
6. [Future Work](#future-work)

## Core Design Principles

1. **Streaming-First**: Process logs as they arrive, not in batches
2. **Memory Efficiency**: Bounded memory usage regardless of log volume
3. **Configuration Over Code**: Customize behavior via YAML, not code changes
4. **BI-Friendly**: SQL access and declarative metrics for analysts
5. **Production-Ready**: Error handling, validation, and operational concerns

## Architecture Decisions

### Modular Pipeline Design

LogLens++ uses a pipeline architecture where each stage is independent:

```
Logs → Ingestion → Processing → Storage → Analytics
```

**Rationale:**
- Each stage can be tested independently
- Easy to swap implementations (e.g., different storage backends)
- Clear separation of concerns
- Enables parallel development

**Tradeoff:** Slight overhead from data structure conversions between stages, but provides flexibility.

### Event-Driven Processing

Events flow through the system as they're ingested, enabling real-time analysis.

**Benefits:**
- Low latency (metrics update immediately)
- Memory efficient (process and discard)
- Real-time anomaly detection

**Tradeoff:** More complex than batch processing, but enables streaming use cases.

## Design Tradeoffs

### Streaming vs Batch Processing

**Chosen: Streaming**

**Why:**
- **Real-time insights**: Detect issues as they happen
- **Memory efficiency**: Process line-by-line, don't load entire files
- **Scalability**: Can handle log streams of any size
- **User experience**: Immediate feedback on anomalies

**Tradeoffs:**
- **Complexity**: More complex than batch (need to handle partial data, windows)
- **State management**: Must maintain rolling windows and baselines
- **Ordering**: Must handle out-of-order events (future enhancement)

**When Batch Would Be Better:**
- Historical analysis of large datasets
- One-time processing jobs
- When real-time isn't required

**Future Enhancement:** Hybrid mode - streaming for real-time, batch for historical reprocessing.

### Memory Usage Strategy

**Design: Bounded Memory**

**Approach:**
1. **Streaming ingestion**: Process logs line-by-line, never load full file
2. **Rolling windows**: Use `deque` with `maxlen` to bound window size
3. **Event expiration**: Automatically remove events outside time windows
4. **Columnar storage**: DuckDB compresses data efficiently

**Memory Bounds:**
- **Sliding windows**: `window_size × avg_event_size` per metric
- **Tumbling windows**: Clears after each window (lower memory)
- **Storage**: DuckDB uses columnar compression (efficient)

**Tradeoffs:**
- **Bounded memory**: Can't process infinite history in memory
- **Window size limits**: Must choose appropriate window sizes
- **Storage required**: Need persistent storage for historical data

**Alternative Considered:** In-memory only (faster but limited by RAM)

**Decision:** Hybrid - memory for active windows, storage for history.

### Windowing Strategy

**Two Strategies Implemented:**

#### Sliding Windows
- **Use Case**: Real-time monitoring, continuous metrics
- **Memory**: Bounded by window size
- **Latency**: Immediate updates
- **Complexity**: Must maintain event buffer

#### Tumbling Windows
- **Use Case**: Fixed intervals, batch reporting
- **Memory**: Clears after each window
- **Latency**: Window-aligned (e.g., hourly)
- **Complexity**: Simpler (no buffer management)

**Tradeoff:**
- **Sliding**: More responsive but higher memory
- **Tumbling**: Lower memory but less granular

**Decision:** Support both - users choose based on use case.

### Storage: DuckDB vs Alternatives

**Chosen: DuckDB**

**Comparison:**

| Feature | DuckDB | SQLite | PostgreSQL | In-Memory |
|---------|--------|--------|------------|-----------|
| Analytical Queries | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| Embedded | ✅ | ✅ | ❌ | ✅ |
| Time-Series | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| Setup Complexity | Low | Low | High | Low |
| Concurrent Writes | Limited | Good | Excellent | N/A |
| File Size | Medium | Small | Large | N/A |

**Why DuckDB:**
1. **Analytical Performance**: 10-100x faster than SQLite for aggregations
2. **Time-Series Optimized**: Excellent DATE_TRUNC and window functions
3. **Embedded**: No server setup, single file
4. **SQL Interface**: Full SQL for BI tools
5. **Columnar Storage**: Efficient compression

**Tradeoffs:**
- **Concurrent Writes**: Not optimized for high-concurrency writes (acceptable for log analytics)
- **File-Based**: Single file (not distributed, but portable)
- **Memory**: Columnar format can be memory-intensive for very large queries

**When to Use Alternatives:**
- **SQLite**: If you need better concurrent writes or smaller file size
- **PostgreSQL**: If you need distributed storage or very high write throughput
- **In-Memory**: If you only need recent data and can accept data loss

### Extensibility Strategy

**Design: Plugin Architecture (Future)**

**Current Approach:**
- **Declarative Metrics**: Add metrics via YAML, no code changes
- **Custom Aggregations**: Support custom Python functions
- **Modular Components**: Easy to extend individual modules

**Future: Plugin System**
- **Custom Parsers**: Add support for new log formats
- **Custom Storage**: Swap DuckDB for other backends
- **Custom Aggregations**: Register new aggregation types
- **Custom Anomaly Detectors**: Add ML-based detection

**Tradeoff:**
- **Current**: Simple, Python-based extensions
- **Future**: More complex but more powerful

## Implementation Details

### Rolling Window Implementation

**Sliding Windows:**

```python
# Uses deque for O(1) operations
events = deque(maxlen=window_size)

# Add event: O(1)
events.append(event)

# Remove expired: O(1) per event
while events[0].timestamp < window_start:
    events.popleft()
```

**Key Decisions:**
1. **`deque` over `list`**: O(1) removal from front vs O(n)
2. **Event-driven expiration**: Remove as new events arrive, not on timer
3. **Bounded size**: `maxlen` prevents unbounded growth

**Memory Complexity:** O(window_size) - constant regardless of total events

**Tumbling Windows:**

```python
# Align to time boundaries
window_start = align_to_boundary(event.timestamp)
window_end = window_start + window_size

# Clear after window completes
if event.timestamp >= window_end:
    process_window()
    events.clear()
```

**Key Decisions:**
1. **Boundary alignment**: Clean time boundaries (hour/day)
2. **Automatic completion**: Window completes when next event arrives
3. **Memory clearing**: Events cleared after processing

**Memory Complexity:** O(window_size) - but clears periodically

### Metric Aggregation Implementation

**Design: Incremental Updates**

Metrics update incrementally as events arrive, not by recalculating from scratch.

**Benefits:**
- **Performance**: O(1) updates vs O(n) recalculation
- **Real-time**: Immediate metric updates
- **Efficient**: Only process new events

**Tradeoff:**
- **Complexity**: Must handle window expiration correctly
- **State**: Must maintain metric state

**Alternative Considered:** Recalculate from storage (simpler but slower)

**Decision:** Incremental for performance, with validation from storage for correctness.

### Anomaly Detection Algorithm

**Algorithm: Z-Score Based**

```
z_score = (value - mean) / std_dev
if abs(z_score) >= threshold:
    flag_anomaly()
```

**Why Z-Score:**
- **Simple**: Easy to understand and tune
- **Effective**: Works well for most time-series data
- **Fast**: O(1) calculation
- **Interpretable**: Z-score directly relates to standard deviations

**Tradeoffs:**
- **Assumes Normal Distribution**: May not work for all data types
- **Sensitive to Outliers**: Outliers can skew baseline
- **Single Metric**: Doesn't consider correlations

**Alternatives Considered:**
- **Moving Average**: Simpler but less sensitive
- **Percentile-Based**: More robust to outliers but less interpretable
- **ML-Based**: More powerful but complex

**Future Enhancement:** Support multiple algorithms (percentile, ML-based)

### Expression Evaluation

**Current: Python `eval()` with Restricted Globals**

**Why:**
- **Flexibility**: Users can write complex filter expressions
- **Familiar**: Python syntax
- **Powerful**: Full Python expression support

**Tradeoffs:**
- **Security**: `eval()` can be dangerous (mitigated with restricted globals)
- **Performance**: Slower than compiled code

**Future Enhancement:**
- **AST Compilation**: Compile expressions to bytecode
- **Expression Validator**: Validate expressions before execution
- **Sandboxed Execution**: Use restricted execution environment

## Extensibility

### Adding New Log Formats

**Current:** JSON and plain text supported

**Extending:**
1. Create new parser class in `ingestion/`
2. Implement `_ingest_<format>()` method
3. Register in `LogIngestor.ingest_stream()`

**Example:**
```python
def _ingest_csv(self, stream):
    # Parse CSV format
    for line in stream:
        # Parse and yield LogEvent
        yield event
```

### Adding New Aggregation Types

**Current:** count, rate, average, sum, min, max, percentile, unique_count

**Extending:**
1. Add to `AggregationType` enum
2. Implement in `MetricProcessor._apply_aggregation()`
3. Or use custom function (already supported)

**Example:**
```python
# Custom aggregation
def custom_median(events):
    values = sorted([e.value for e in events])
    return values[len(values) // 2]

metric = Metric(
    name='median_response_time',
    aggregation=custom_median,
    ...
)
```

### Adding New Storage Backends

**Current:** DuckDB only

**Extending:**
1. Implement `StorageInterface` (future)
2. Create backend class (e.g., `PostgreSQLStorage`)
3. Swap in `LogStorage` factory

**Future Design:**
```python
class StorageInterface:
    def insert_event(self, event): ...
    def query_events(self, ...): ...
    def insert_metric(self, ...): ...

class DuckDBStorage(StorageInterface): ...
class PostgreSQLStorage(StorageInterface): ...
```

### Adding New Anomaly Detection Algorithms

**Current:** Z-score based

**Extending:**
1. Create new detector class
2. Implement `AnomalyDetector` interface
3. Register in configuration

**Future Design:**
```python
class AnomalyDetectorInterface:
    def add_value(self, value, timestamp): ...
    def get_baseline_stats(self): ...

class ZScoreDetector(AnomalyDetectorInterface): ...
class PercentileDetector(AnomalyDetectorInterface): ...
class MLDetector(AnomalyDetectorInterface): ...
```

## Future Work

### High Priority

#### 1. Dashboard/Visualization

**Goal:** Web-based dashboard for metrics visualization

**Design:**
- **Backend**: FastAPI or Flask API
- **Frontend**: React/Vue with charting library (Chart.js, D3.js)
- **Real-time Updates**: WebSocket for live metrics
- **Features**:
  - Time-series charts
  - Metric dashboards
  - Anomaly alerts
  - Custom queries

**Implementation:**
```
loglens/
  ├── api/          # REST API
  ├── dashboard/    # Web dashboard
  └── websocket/    # Real-time updates
```

**Tradeoffs:**
- **Complexity**: Adds web stack (but enables better UX)
- **Dependencies**: More dependencies (but standard web stack)

#### 2. Distributed Ingestion

**Goal:** Scale ingestion across multiple nodes

**Design:**
- **Message Queue**: Kafka/RabbitMQ for log distribution
- **Worker Pool**: Multiple ingestion workers
- **Coordination**: Redis for shared state
- **Sharding**: Partition logs by source/time

**Architecture:**
```
Logs → Kafka → Workers → Storage
              ↓
         Redis (coordination)
```

**Tradeoffs:**
- **Complexity**: Much more complex (but enables scale)
- **Dependencies**: Requires message queue infrastructure
- **Consistency**: Must handle distributed state

**Alternative:** Start with single-node, add distribution later

#### 3. Out-of-Order Event Handling

**Goal:** Handle events that arrive out of chronological order

**Design:**
- **Buffer Window**: Hold events in buffer for reordering
- **Watermark**: Process events up to watermark
- **Late Events**: Handle events that arrive late

**Implementation:**
```python
class OrderedWindowProcessor:
    def __init__(self, max_lateness=timedelta(minutes=5)):
        self.buffer = {}  # timestamp -> events
        self.watermark = None
    
    def add_event(self, event):
        # Buffer if within lateness window
        # Process when watermark advances
```

**Tradeoffs:**
- **Latency**: Must wait for late events (configurable)
- **Memory**: Buffer increases memory usage
- **Complexity**: More complex ordering logic

### Medium Priority

#### 4. Advanced Anomaly Detection

**Enhancements:**
- **Percentile-Based**: More robust to outliers
- **Seasonal Detection**: Handle daily/weekly patterns
- **Multi-Metric Correlation**: Detect anomalies across related metrics
- **ML-Based**: Use isolation forest, LSTM, etc.

**Design:**
```python
class SeasonalAnomalyDetector:
    def __init__(self):
        self.hourly_baselines = {}  # hour -> baseline
        self.daily_baselines = {}   # day -> baseline
    
    def add_value(self, value, timestamp):
        # Compare against seasonal baseline
        hour = timestamp.hour
        baseline = self.hourly_baselines.get(hour)
        # Detect anomaly relative to seasonal pattern
```

#### 5. Alerting System

**Goal:** Send alerts when anomalies are detected

**Design:**
- **Alert Channels**: Email, Slack, PagerDuty, webhooks
- **Alert Rules**: Configurable thresholds and conditions
- **Alert Aggregation**: Prevent alert storms
- **Alert History**: Track alert history

**Implementation:**
```yaml
alerts:
  - metric: error_count
    condition: z_score > 3.0
    channels:
      - type: slack
        webhook: https://...
      - type: email
        recipients: [team@example.com]
```

#### 6. Log Pattern Detection

**Goal:** Automatically detect common log patterns

**Design:**
- **Pattern Mining**: Extract common patterns from logs
- **Template Extraction**: Identify log templates
- **Anomaly Patterns**: Detect unusual patterns
- **Clustering**: Group similar log messages

**Use Cases:**
- Identify common error patterns
- Detect new error types
- Reduce log noise

#### 7. Multi-Tenancy Support

**Goal:** Support multiple organizations/tenants

**Design:**
- **Tenant Isolation**: Separate databases or schemas
- **Resource Limits**: Per-tenant quotas
- **Access Control**: Tenant-based authentication
- **Billing**: Usage tracking per tenant

**Implementation:**
```python
class MultiTenantStorage:
    def __init__(self, tenant_id):
        self.db_path = f"tenant_{tenant_id}.db"
        # Isolated storage per tenant
```

### Low Priority / Research

#### 8. Machine Learning Integration

**Ideas:**
- **Log Classification**: Auto-categorize logs
- **Predictive Anomaly Detection**: Predict anomalies before they occur
- **Log Clustering**: Group similar logs automatically
- **Root Cause Analysis**: Correlate anomalies with root causes

#### 9. Distributed Storage

**Goal:** Scale storage across multiple nodes

**Design:**
- **Sharding**: Partition by time or source
- **Replication**: Replicate for availability
- **Query Federation**: Query across shards

**Considerations:**
- **Complexity**: Significant increase
- **When Needed**: Only for very large scale (>100GB/day)

#### 10. Real-Time Streaming API

**Goal:** Stream metrics and anomalies in real-time

**Design:**
- **WebSocket API**: Push updates to clients
- **SSE (Server-Sent Events)**: Simpler alternative
- **gRPC Streaming**: For high-performance use cases

**Use Cases:**
- Live dashboards
- Real-time monitoring
- Alert systems

## Performance Characteristics

### Ingestion Performance

- **Throughput**: ~10,000-50,000 events/second (single-threaded)
- **Memory**: O(window_size) per metric
- **Latency**: <10ms per event (excluding I/O)

**Bottlenecks:**
- **I/O**: File reading (mitigated by streaming)
- **Storage Writes**: DuckDB inserts (batch inserts help)
- **Metric Computation**: O(n) where n = events in window

**Optimization Opportunities:**
- Parallel ingestion (multiple files)
- Batch metric updates
- Async storage writes

### Query Performance

- **Time-Range Queries**: O(log n) with indexes
- **Aggregations**: O(n) where n = matching rows
- **SQL Queries**: DuckDB optimizes automatically

**Optimization:**
- Indexes on timestamp, level, source
- Materialized views for common queries (future)
- Query result caching (future)

### Memory Usage

- **Per Metric**: ~window_size × 100 bytes (estimated)
- **Storage Buffer**: DuckDB manages internally
- **Total**: Bounded by number of metrics × window size

**Example:**
- 10 metrics with 20-sample windows = ~20KB
- 100 metrics with 100-sample windows = ~1MB

## Scalability Limits

### Current Limits

- **Single File**: DuckDB recommended <100GB per file
- **Concurrent Writes**: Limited (acceptable for log analytics)
- **Memory**: Bounded by window sizes (configurable)

### Scaling Strategies

1. **Horizontal**: Multiple LogLens++ instances (shard by source/time)
2. **Vertical**: Larger windows, more metrics (limited by memory)
3. **Storage**: Partition databases by time (daily/weekly)

### When to Scale

- **>1M events/day**: Current design handles easily
- **>10M events/day**: Consider partitioning
- **>100M events/day**: Need distributed architecture

## Security Considerations

### Current State

- **Expression Evaluation**: Uses restricted globals (basic security)
- **File Access**: Standard file permissions
- **No Authentication**: CLI assumes trusted environment

### Future Enhancements

- **Expression Sandboxing**: More secure expression evaluation
- **Access Control**: User authentication and authorization
- **Encryption**: Encrypt sensitive log data
- **Audit Logging**: Track who accessed what data

## Conclusion

LogLens++ is designed as a **streaming-first, memory-efficient** log analytics engine with a focus on **ease of use** and **extensibility**. The design prioritizes:

1. **Real-time processing** over batch
2. **Bounded memory** over unlimited history
3. **Configuration** over code changes
4. **SQL access** for BI integration
5. **Modularity** for future extension

The architecture supports current needs while providing clear paths for future enhancements like dashboards, distributed processing, and advanced analytics.

