#!/bin/bash
# Script to create a CLI demo GIF using asciinema and agg
# Install: brew install asciinema agg (macOS) or apt-get install asciinema (Linux)

set -e

echo "Creating CLI demo recording..."
echo "This will demonstrate: ingestion → query → anomaly detection"
echo ""

# Clean up any existing files
rm -f cli-demo.cast cli-demo.gif demo_logs.json demo.db

# Create sample log file
python3 << 'EOF'
import json
from datetime import datetime, timedelta

base_time = datetime(2024, 1, 1, 12, 0, 0)
with open('demo_logs.json', 'w') as f:
    for i in range(30):
        timestamp = base_time + timedelta(seconds=i*10)
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
EOF

echo "Sample log file created: demo_logs.json"
echo ""
echo "To record the demo:"
echo "1. Run: asciinema rec cli-demo.cast"
echo "2. Execute these commands:"
echo "   loglens ingest demo_logs.json --format json"
echo "   loglens metrics list"
echo "   loglens query \"SELECT level, COUNT(*) FROM events GROUP BY level\""
echo "   loglens anomalies"
echo "3. Press Ctrl+D to stop recording"
echo "4. Convert to GIF: agg cli-demo.cast cli-demo.gif"
echo ""
echo "Or use ttygif:"
echo "1. Run: ttyrec cli-demo.rec"
echo "2. Execute commands above"
echo "3. Press Ctrl+D"
echo "4. Convert: ttygif cli-demo.rec"

