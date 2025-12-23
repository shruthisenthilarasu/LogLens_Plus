# Test Suite

This directory contains unit tests for LogLens++, focusing on correctness and edge cases rather than full coverage.

## Test Files

### `test_ingestion.py`
Tests for log parsing and ingestion:
- ✅ JSON log parsing (basic, metadata, missing fields)
- ✅ Plain text log parsing (timestamp extraction, level detection, source extraction)
- ✅ Error handling (invalid JSON, missing files)
- ✅ Edge cases (empty lines, unicode, very long messages, timestamp variants)
- ✅ Auto-detection of log formats

**Key Edge Cases Tested:**
- Invalid JSON in strict vs lenient mode
- Missing required fields (uses defaults)
- Unicode characters in messages
- Very long log messages
- Various timestamp formats

### `test_metrics.py`
Tests for metric aggregation:
- ✅ Count aggregation
- ✅ Rate aggregation (events per second)
- ✅ Average, sum, min, max aggregations
- ✅ Grouped metrics (by source, by level)
- ✅ Custom aggregation functions
- ✅ Window expiration (events falling outside time window)
- ✅ Missing value extractor (error handling)
- ✅ Empty filters (no matching events)

**Key Edge Cases Tested:**
- Metrics with no matching events
- Window expiration (time-based cleanup)
- Missing required parameters (value_extractor for average/sum)
- Single event rate calculation
- Custom aggregation functions

### `test_anomaly_detection.py`
Tests for anomaly detection:
- ✅ Spike detection (values above baseline)
- ✅ Drop detection (values below baseline)
- ✅ Threshold boundaries (values at/near threshold)
- ✅ Severity levels (low, medium, high, critical)
- ✅ Insufficient samples (min_samples requirement)
- ✅ Constant values (zero variance handling)
- ✅ Negative and zero values
- ✅ Baseline statistics calculation
- ✅ Reset functionality

**Key Edge Cases Tested:**
- Constant baseline values (std = 0)
- Insufficient samples before detection
- Threshold boundary conditions
- Negative and zero values
- Reset and state management

## Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_ingestion.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=loglens --cov-report=html
```

## Test Philosophy

These tests focus on:
1. **Correctness**: Ensuring core functionality works as expected
2. **Edge Cases**: Handling boundary conditions and error cases
3. **Integration**: Testing components work together
4. **Real-world scenarios**: Testing with realistic data

Not focused on:
- 100% code coverage (intentional)
- Performance benchmarking
- Stress testing

## Test Coverage Summary

- **Ingestion**: 18 tests covering JSON/text parsing, error handling, edge cases
- **Metrics**: 11 tests covering all aggregation types and edge cases
- **Anomaly Detection**: 12 tests covering spike/drop detection and edge cases

**Total: 41 tests, all passing** ✅

