"""
Unit tests for log ingestion and parsing.

Focuses on correctness and edge cases for JSON and plain text log parsing.
"""

import pytest
from datetime import datetime
from io import StringIO
from pathlib import Path
import tempfile

from loglens.ingestion import LogIngestor
from loglens.models import LogEvent


class TestJSONIngestion:
    """Tests for JSON log ingestion."""
    
    def test_basic_json_ingestion(self):
        """Test basic JSON log parsing."""
        ingestor = LogIngestor()
        stream = StringIO('{"timestamp": "2024-01-01T12:00:00", "level": "INFO", "source": "app1", "message": "Test"}')
        
        events = list(ingestor.ingest_stream(stream, format="json"))
        
        assert len(events) == 1
        assert events[0].level == "INFO"
        assert events[0].source == "app1"
        assert events[0].message == "Test"
    
    def test_json_with_metadata(self):
        """Test JSON logs with metadata."""
        ingestor = LogIngestor()
        stream = StringIO('{"timestamp": "2024-01-01T12:00:00", "level": "ERROR", "source": "app1", "message": "Error", "metadata": {"key": "value"}}')
        
        events = list(ingestor.ingest_stream(stream, format="json"))
        
        assert len(events) == 1
        assert events[0].metadata == {"key": "value"}
    
    def test_json_missing_required_fields(self):
        """Test JSON logs with missing required fields."""
        ingestor = LogIngestor(default_source="default", default_level="INFO")
        
        # Missing message - should use string representation
        stream = StringIO('{"timestamp": "2024-01-01T12:00:00", "level": "INFO", "source": "app1"}')
        events = list(ingestor.ingest_stream(stream, format="json"))
        
        assert len(events) == 1
        assert events[0].message  # Should have some message
    
    def test_json_invalid_json(self):
        """Test handling of invalid JSON."""
        ingestor = LogIngestor(skip_invalid=True)
        stream = StringIO('{"invalid": json}\n{"timestamp": "2024-01-01T12:00:00", "level": "INFO", "source": "app1", "message": "Valid"}')
        
        events = list(ingestor.ingest_stream(stream, format="json"))
        
        # Should skip invalid line and process valid one
        assert len(events) == 1
        assert events[0].message == "Valid"
    
    def test_json_invalid_json_strict_mode(self):
        """Test that invalid JSON raises error in strict mode."""
        ingestor = LogIngestor(skip_invalid=False)
        stream = StringIO('{"invalid": json}')
        
        with pytest.raises(ValueError):
            list(ingestor.ingest_stream(stream, format="json"))
    
    def test_json_empty_lines(self):
        """Test that empty lines are skipped."""
        ingestor = LogIngestor()
        stream = StringIO('\n\n{"timestamp": "2024-01-01T12:00:00", "level": "INFO", "source": "app1", "message": "Test"}\n\n')
        
        events = list(ingestor.ingest_stream(stream, format="json"))
        
        assert len(events) == 1
    
    def test_json_multiple_events(self):
        """Test parsing multiple JSON events."""
        ingestor = LogIngestor()
        stream = StringIO(
            '{"timestamp": "2024-01-01T12:00:00", "level": "INFO", "source": "app1", "message": "Event 1"}\n'
            '{"timestamp": "2024-01-01T12:00:05", "level": "ERROR", "source": "app2", "message": "Event 2"}'
        )
        
        events = list(ingestor.ingest_stream(stream, format="json"))
        
        assert len(events) == 2
        assert events[0].level == "INFO"
        assert events[1].level == "ERROR"


class TestTextIngestion:
    """Tests for plain text log ingestion."""
    
    def test_basic_text_ingestion(self):
        """Test basic plain text log parsing."""
        ingestor = LogIngestor()
        stream = StringIO('2024-01-01T12:00:00 INFO [app1] Application started')
        
        events = list(ingestor.ingest_stream(stream, format="text"))
        
        assert len(events) == 1
        assert events[0].level == "INFO"
        assert events[0].source == "app1"
    
    def test_text_without_timestamp(self):
        """Test text logs without timestamp."""
        ingestor = LogIngestor()
        stream = StringIO('INFO Application started')
        
        events = list(ingestor.ingest_stream(stream, format="text"))
        
        assert len(events) == 1
        assert events[0].level == "INFO"
        # Timestamp should default to current time (approximately)
        assert events[0].timestamp is not None
    
    def test_text_without_level(self):
        """Test text logs without log level."""
        ingestor = LogIngestor(default_level="INFO")
        stream = StringIO('2024-01-01T12:00:00 Application started')
        
        events = list(ingestor.ingest_stream(stream, format="text"))
        
        assert len(events) == 1
        assert events[0].level == "INFO"  # Should use default
    
    def test_text_source_extraction(self):
        """Test source extraction from text logs."""
        ingestor = LogIngestor()
        
        # Test bracket format
        stream1 = StringIO('2024-01-01T12:00:00 INFO [app1] Message')
        events1 = list(ingestor.ingest_stream(stream1, format="text"))
        assert events1[0].source == "app1"
        
        # Test colon format
        stream2 = StringIO('2024-01-01T12:00:00 INFO app2: Message')
        events2 = list(ingestor.ingest_stream(stream2, format="text"))
        assert events2[0].source == "app2"
    
    def test_text_empty_lines(self):
        """Test that empty lines are skipped."""
        ingestor = LogIngestor()
        stream = StringIO('\n\n2024-01-01T12:00:00 INFO [app1] Message\n\n')
        
        events = list(ingestor.ingest_stream(stream, format="text"))
        
        assert len(events) == 1
    
    def test_text_invalid_level(self):
        """Test text logs with invalid level."""
        ingestor = LogIngestor(skip_invalid=True)
        stream = StringIO('2024-01-01T12:00:00 INVALID [app1] Message')
        
        events = list(ingestor.ingest_stream(stream, format="text"))
        
        # Should use default level or skip
        assert len(events) == 1


class TestIngestionEdgeCases:
    """Tests for edge cases in log ingestion."""
    
    def test_file_not_found(self):
        """Test error handling for missing file."""
        ingestor = LogIngestor()
        
        with pytest.raises(FileNotFoundError):
            list(ingestor.ingest_file("nonexistent.log"))
    
    def test_auto_detect_json(self):
        """Test automatic format detection for JSON."""
        ingestor = LogIngestor()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('{"timestamp": "2024-01-01T12:00:00", "level": "INFO", "source": "app1", "message": "Test"}')
            f.flush()
            
            events = list(ingestor.ingest_file(f.name))
            assert len(events) == 1
            assert events[0].level == "INFO"
            
            Path(f.name).unlink()
    
    def test_unicode_in_logs(self):
        """Test handling of unicode characters."""
        ingestor = LogIngestor()
        stream = StringIO('{"timestamp": "2024-01-01T12:00:00", "level": "INFO", "source": "app1", "message": "Test: 测试 🚀"}')
        
        events = list(ingestor.ingest_stream(stream, format="json"))
        
        assert len(events) == 1
        assert "测试" in events[0].message
        assert "🚀" in events[0].message
    
    def test_very_long_message(self):
        """Test handling of very long log messages."""
        ingestor = LogIngestor()
        long_message = "A" * 10000
        stream = StringIO(f'{{"timestamp": "2024-01-01T12:00:00", "level": "INFO", "source": "app1", "message": "{long_message}"}}')
        
        events = list(ingestor.ingest_stream(stream, format="json"))
        
        assert len(events) == 1
        assert len(events[0].message) == 10000
    
    def test_timestamp_parsing_variants(self):
        """Test parsing of different timestamp formats."""
        ingestor = LogIngestor()
        
        # ISO format
        stream1 = StringIO('{"timestamp": "2024-01-01T12:00:00", "level": "INFO", "source": "app1", "message": "Test"}')
        events1 = list(ingestor.ingest_stream(stream1, format="json"))
        assert isinstance(events1[0].timestamp, datetime)
        
        # ISO with timezone
        stream2 = StringIO('{"timestamp": "2024-01-01T12:00:00Z", "level": "INFO", "source": "app1", "message": "Test"}')
        events2 = list(ingestor.ingest_stream(stream2, format="json"))
        assert isinstance(events2[0].timestamp, datetime)

