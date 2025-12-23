# Configuration Guide

LogLens++ supports YAML configuration files that allow you to customize metrics, time windows, and alert thresholds without changing code. This shows production thinking - configuration over code!

## Quick Start

1. **Create a default configuration:**
   ```bash
   loglens config init
   ```

2. **Edit the configuration file** (`loglens.yaml`)

3. **Use it with commands:**
   ```bash
   loglens ingest app.log --config loglens.yaml
   loglens anomalies --config loglens.yaml
   ```

## Configuration File Structure

```yaml
# Default values
default_source: myapp
default_level: INFO

# Storage settings
storage:
  db_path: loglens.db
  retention_days: 30

# Metrics definitions
metrics:
  - name: error_count
    filter: event.level in ('ERROR', 'CRITICAL', 'FATAL')
    aggregation: count
    window: 5m
    description: Count of error-level events

# Anomaly detection
anomalies:
  - metric_name: error_count
    window_size: 20
    threshold: 2.0
    min_samples: 5
    enabled: true
```

## Metrics Configuration

Each metric defines:
- **name**: Unique metric name
- **filter**: Python expression to filter events (e.g., `event.level == 'ERROR'`)
- **aggregation**: Type of aggregation (`count`, `rate`, `average`, `sum`, etc.)
- **window**: Time window (e.g., `5m`, `1h`, `15m`)
- **group_by** (optional): Expression to group by (e.g., `event.source`)
- **value_extractor** (optional): Expression to extract numeric values from metadata

### Filter Expressions

Filter expressions are Python expressions that evaluate to True/False:
- `event.level == 'ERROR'` - Match specific level
- `event.level in ('ERROR', 'CRITICAL')` - Match multiple levels
- `event.source == 'api'` - Match specific source
- `'response_time' in event.metadata` - Check metadata
- `True` - Match all events

### Group By Expressions

Group by expressions extract a key from events:
- `event.source` - Group by source
- `event.level` - Group by log level
- `event.metadata.get('service')` - Group by metadata field

### Value Extractor Expressions

Extract numeric values for aggregations like `average`, `sum`, etc.:
- `event.metadata.get('response_time_ms', 0)` - Extract from metadata
- `len(event.message)` - Extract message length

## Anomaly Detection Configuration

Each anomaly config defines:
- **metric_name**: Which metric to monitor
- **window_size**: Number of samples for rolling baseline
- **threshold**: Z-score threshold (default: 2.0)
- **min_samples**: Minimum samples before detecting
- **enabled**: Enable/disable monitoring

## Example Configurations

### Production Configuration

```yaml
default_source: production-api
storage:
  db_path: /var/log/loglens/production.db
  retention_days: 90

metrics:
  - name: api_error_rate
    filter: event.source == 'api' and event.level == 'ERROR'
    aggregation: rate
    window: 1m
    description: API error rate per second

  - name: db_query_time
    filter: 'db_query_time' in event.metadata
    aggregation: average
    window: 5m
    value_extractor: event.metadata.get('db_query_time', 0)
    description: Average database query time

anomalies:
  - metric_name: api_error_rate
    window_size: 30
    threshold: 2.5
    enabled: true
```

### Development Configuration

```yaml
default_source: dev
storage:
  db_path: dev.db
  retention_days: 7

metrics:
  - name: error_count
    filter: event.level == 'ERROR'
    aggregation: count
    window: 5m

anomalies:
  - metric_name: error_count
    window_size: 10
    threshold: 3.0  # Less sensitive in dev
    enabled: true
```

## Using Configuration

### With CLI Commands

```bash
# Ingest with config
loglens ingest app.log --config myconfig.yaml

# Check anomalies with config
loglens anomalies --config myconfig.yaml

# Config is automatically loaded from loglens.yaml if present
loglens ingest app.log  # Uses loglens.yaml if it exists
```

### Programmatically

```python
from loglens.utils.config import load_config
from loglens.analytics import MetricProcessor

# Load config
config = load_config('loglens.yaml')

# Get metrics
metrics = config.to_metrics()
processor = MetricProcessor(metrics)

# Get anomaly detectors
detectors = config.to_anomaly_detectors()
```

## Configuration File Locations

LogLens++ looks for config files in this order:
1. Path specified with `--config` option
2. `loglens.yaml` in current directory
3. `loglens.yml` in current directory
4. `.loglens.yaml` in current directory
5. `~/.loglens.yaml` in home directory

If no config is found, defaults are used.

## Benefits

✅ **No code changes** - Customize behavior via YAML  
✅ **Version control** - Track configuration changes  
✅ **Environment-specific** - Different configs for dev/staging/prod  
✅ **Team collaboration** - Share configs easily  
✅ **Production-ready** - Standard practice for production systems

