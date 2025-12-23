# CLI Demo GIF

This file is a placeholder for the CLI demo GIF.

To create the actual GIF:

1. **Using asciinema + agg** (recommended):
   ```bash
   # Install tools
   brew install asciinema agg  # macOS
   # or
   pip install asciinema
   pip install agg
   
   # Record
   asciinema rec cli-demo.cast
   # Run commands:
   loglens ingest demo_logs.json --format json
   loglens metrics list
   loglens query "SELECT level, COUNT(*) FROM events GROUP BY level"
   loglens anomalies
   # Press Ctrl+D
   
   # Convert to GIF
   agg cli-demo.cast cli-demo.gif
   ```

2. **Using ttygif**:
   ```bash
   # Install
   brew install ttygif  # macOS
   
   # Record
   ttyrec cli-demo.rec
   # Run commands above
   # Press Ctrl+D
   
   # Convert
   ttygif cli-demo.rec
   ```

3. **Using screen recording**:
   - macOS: QuickTime Player or ScreenFlow
   - Linux: OBS Studio or SimpleScreenRecorder
   - Windows: OBS Studio or ShareX

The GIF should show the complete workflow: ingestion → query → anomaly detection.

