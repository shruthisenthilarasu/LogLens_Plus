# LogLens++ Examples

This directory contains example scripts and demonstrations of LogLens++ capabilities.

## Dashboard Visualization

**File**: `dashboard.py`

Creates a comprehensive matplotlib-based dashboard showing:
- Error rate trends over time
- Events distribution by log level (pie chart)
- Top sources by event count (bar chart)
- Error rate by source (bar chart)
- Metric trends over time (line chart)

### Usage

```bash
# Generate sample data and create dashboard
python examples/dashboard.py --generate-data

# Or use existing database
python examples/dashboard.py
```

The dashboard is saved as `dashboard.png` in the current directory.

### Customization

You can modify `dashboard.py` to:
- Change time ranges
- Add custom metrics
- Adjust chart styles
- Export to different formats (PDF, SVG, etc.)

## Workflow Demonstration

**File**: `workflow_demo.py`

Demonstrates the complete LogLens++ workflow:
1. **Ingestion**: Reading logs from file and parsing into LogEvent objects
2. **Metrics**: Computing aggregations and storing results
3. **Querying**: Executing SQL queries and time-bucketed analysis
4. **Anomaly Detection**: Identifying spikes and drops in metrics

### Usage

```bash
# Run the complete workflow demo
python examples/workflow_demo.py
```

### Creating a GIF

To create a GIF or video of the workflow:

1. **Using `asciinema`** (terminal recording):
   ```bash
   asciinema rec workflow.cast
   python examples/workflow_demo.py
   # Press Ctrl+D to stop recording
   asciinema play workflow.cast
   ```

2. **Using `ttygif`** (convert terminal to GIF):
   ```bash
   ttyrec workflow.rec
   python examples/workflow_demo.py
   # Press Ctrl+D
   ttygif workflow.rec
   ```

3. **Using screen recording tools**:
   - macOS: QuickTime Player or ScreenFlow
   - Linux: OBS Studio or SimpleScreenRecorder
   - Windows: OBS Studio or ShareX

## Example Output

### Dashboard

The dashboard provides a comprehensive view of your log analytics:

- **Error Rate Over Time**: Line chart showing error percentage trends
- **Events by Level**: Pie chart distribution of log levels
- **Top Sources**: Horizontal bar chart of most active sources
- **Error Rate by Source**: Bar chart showing which sources have highest error rates
- **Metric Trends**: Multi-line chart showing multiple metrics over time

### Workflow Demo

The workflow demo shows:
- Step-by-step ingestion process
- Real-time metric computation
- SQL query execution with results
- Anomaly detection with explanations

## Integration Examples

### Custom Dashboard

You can integrate LogLens++ data into your own dashboards:

```python
from loglens.storage import LogStorage, create_query
import matplotlib.pyplot as plt

storage = LogStorage("loglens.db")
query = create_query(storage)

# Query your data
results = query.execute_sql("SELECT * FROM metrics WHERE ...")

# Create custom visualizations
plt.plot([r['timestamp'] for r in results], [r['value'] for r in results])
plt.savefig('custom_dashboard.png')
```

### Automated Reporting

```python
from loglens.storage import LogStorage
from loglens.analytics import create_detector

storage = LogStorage("loglens.db")
detector = create_detector('error_count', threshold=2.0)

# Check for anomalies daily
metrics = storage.query_metrics(metric_name='error_count', limit=50)
for metric in metrics:
    anomaly = detector.add_value(metric['value'], metric['window_start'])
    if anomaly:
        send_alert(anomaly)
```

## Contributing Examples

If you create useful examples, consider contributing them:
1. Add your script to this directory
2. Update this README with usage instructions
3. Submit a pull request

