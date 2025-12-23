"""
Log ingestor implementation.

This module provides functionality to ingest logs from file streams,
supporting both JSON and plain text formats.
"""

import json
import re
from datetime import datetime
from typing import Iterator, TextIO, Optional, Dict, Any
from pathlib import Path

from loglens.models import LogEvent


class LogIngestor:
    """
    Ingests logs from file streams, supporting JSON and plain text formats.
    
    The ingestor reads logs line by line and yields LogEvent objects,
    avoiding loading the entire file into memory.
    """
    
    # Common timestamp patterns for plain text logs
    TIMESTAMP_PATTERNS = [
        # ISO format: 2024-01-01T12:00:00 or 2024-01-01T12:00:00.123
        re.compile(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)\s*'),
        # Standard format: 2024-01-01 12:00:00 or 2024-01-01 12:00:00.123
        re.compile(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s*'),
        # Unix timestamp (standalone, not part of other numbers)
        re.compile(r'\b(\d{10}(?:\.\d+)?)\b'),
    ]
    
    # Common log level patterns
    LEVEL_PATTERNS = [
        re.compile(r'\b(DEBUG|INFO|WARNING|ERROR|CRITICAL|TRACE|FATAL)\b', re.IGNORECASE),
    ]
    
    def __init__(
        self,
        default_source: str = "unknown",
        default_level: str = "INFO",
        skip_invalid: bool = True
    ):
        """
        Initialize the log ingestor.
        
        Args:
            default_source: Default source name if not found in log entry
            default_level: Default log level if not found in log entry
            skip_invalid: If True, skip invalid lines instead of raising errors
        """
        self.default_source = default_source
        self.default_level = default_level
        self.skip_invalid = skip_invalid
    
    def ingest_file(
        self,
        file_path: str | Path,
        format: Optional[str] = None
    ) -> Iterator[LogEvent]:
        """
        Ingest logs from a file.
        
        Args:
            file_path: Path to the log file
            format: Format type ('json' or 'text'). If None, auto-detect based on file extension and content
        
        Yields:
            LogEvent objects parsed from the file
        
        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If format is invalid or cannot be determined
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Log file not found: {file_path}")
        
        # Auto-detect format if not specified
        if format is None:
            format = self._detect_format(file_path)
        
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            yield from self.ingest_stream(f, format)
    
    def ingest_stream(
        self,
        stream: TextIO,
        format: str = "auto"
    ) -> Iterator[LogEvent]:
        """
        Ingest logs from a file stream.
        
        Args:
            stream: File-like object to read from
            format: Format type ('json', 'text', or 'auto' for auto-detection)
        
        Yields:
            LogEvent objects parsed from the stream
        """
        if format == "auto":
            format = self._detect_format_from_stream(stream)
            # Reset stream position if possible
            if hasattr(stream, 'seek'):
                stream.seek(0)
        
        if format == "json":
            yield from self._ingest_json(stream)
        elif format == "text":
            yield from self._ingest_text(stream)
        else:
            raise ValueError(f"Unsupported format: {format}. Use 'json' or 'text'")
    
    def _ingest_json(self, stream: TextIO) -> Iterator[LogEvent]:
        """
        Ingest JSON format logs.
        
        Each line should be a JSON object with fields:
        - timestamp (ISO format string or datetime)
        - level (optional, defaults to default_level)
        - source (optional, defaults to default_source)
        - message (required)
        - metadata (optional dict)
        
        Yields:
            LogEvent objects
        """
        for line_num, line in enumerate(stream, start=1):
            line = line.strip()
            if not line:
                continue
            
            try:
                data = json.loads(line)
                
                # Extract fields
                timestamp = self._parse_timestamp(data.get('timestamp'))
                level = data.get('level', self.default_level)
                source = data.get('source', self.default_source)
                message = data.get('message', str(data))  # Fallback to string representation
                metadata = data.get('metadata', {})
                
                # Add any additional fields to metadata
                known_fields = {'timestamp', 'level', 'source', 'message', 'metadata'}
                for key, value in data.items():
                    if key not in known_fields:
                        metadata[key] = value
                
                event = LogEvent(
                    timestamp=timestamp,
                    level=level,
                    source=source,
                    message=message,
                    metadata=metadata
                )
                yield event
                
            except json.JSONDecodeError as e:
                if not self.skip_invalid:
                    raise ValueError(f"Invalid JSON on line {line_num}: {e}")
                continue
            except (ValueError, KeyError) as e:
                if not self.skip_invalid:
                    raise ValueError(f"Error parsing line {line_num}: {e}")
                continue
    
    def _ingest_text(self, stream: TextIO) -> Iterator[LogEvent]:
        """
        Ingest plain text format logs.
        
        Attempts to parse common log formats by extracting:
        - Timestamp (various formats)
        - Log level
        - Source (if identifiable)
        - Message (rest of the line)
        
        Yields:
            LogEvent objects
        """
        for line_num, line in enumerate(stream, start=1):
            line = line.strip()
            if not line:
                continue
            
            try:
                # Try to extract timestamp
                timestamp_match = None
                timestamp = datetime.now()
                for pattern in self.TIMESTAMP_PATTERNS:
                    match = pattern.search(line)
                    if match:
                        ts_str = match.group(1).strip()
                        try:
                            ts_clean = ts_str.replace('Z', '+00:00')
                            timestamp = datetime.fromisoformat(ts_clean)
                            timestamp_match = match
                            break
                        except ValueError:
                            try:
                                ts_float = float(ts_str)
                                timestamp = datetime.fromtimestamp(ts_float)
                                timestamp_match = match
                                break
                            except (ValueError, OSError):
                                continue
                
                # Try to extract level
                level_match = None
                level = self.default_level
                for pattern in self.LEVEL_PATTERNS:
                    match = pattern.search(line)
                    if match:
                        level = match.group(1).upper()
                        level_match = match
                        break
                
                # Try to extract source (look for common patterns)
                source_match = None
                source = self.default_source
                
                # Determine where to start searching (after timestamp and level)
                search_start = 0
                if timestamp_match:
                    search_start = timestamp_match.end()
                if level_match and level_match.start() >= search_start:
                    search_start = level_match.end()
                
                # Pattern: [source] or (source)
                bracket_match = re.search(r'[\[\(]([a-zA-Z0-9_-]+)[\]\)]', line[search_start:])
                if bracket_match:
                    source = bracket_match.group(1)
                    # Create a match-like object with adjusted positions
                    class AdjustedMatch:
                        def __init__(self, match, offset):
                            self._match = match
                            self._offset = offset
                        def start(self):
                            return self._match.start() + self._offset
                        def end(self):
                            return self._match.end() + self._offset
                        def group(self, n=0):
                            return self._match.group(n)
                    source_match = AdjustedMatch(bracket_match, search_start)
                else:
                    # Pattern: source: (look for word followed by colon, after timestamp/level)
                    colon_match = re.search(r'([a-zA-Z0-9_-]+):', line[search_start:])
                    if colon_match:
                        matched_text = colon_match.group(1)
                        # Skip if it's all digits (likely part of timestamp) or contains 'T'
                        if not (matched_text.isdigit() or 'T' in matched_text):
                            source = matched_text
                            # Create a match-like object with adjusted positions
                            class AdjustedMatch:
                                def __init__(self, match, offset):
                                    self._match = match
                                    self._offset = offset
                                def start(self):
                                    return self._match.start() + self._offset
                                def end(self):
                                    return self._match.end() + self._offset
                                def group(self, n=0):
                                    return self._match.group(n)
                            source_match = AdjustedMatch(colon_match, search_start)
                
                # Extract message by removing matched parts
                message = self._extract_message(line, timestamp_match, level_match, source_match)
                
                event = LogEvent(
                    timestamp=timestamp,
                    level=level,
                    source=source,
                    message=message,
                    metadata={'line_number': line_num, 'raw_line': line}
                )
                yield event
                
            except ValueError as e:
                if not self.skip_invalid:
                    raise ValueError(f"Error parsing line {line_num}: {e}")
                continue
    
    def _parse_timestamp(self, timestamp: Any) -> datetime:
        """
        Parse timestamp from various formats.
        
        Args:
            timestamp: Timestamp as datetime, ISO string, or Unix timestamp
        
        Returns:
            datetime object
        
        Raises:
            ValueError: If timestamp cannot be parsed
        """
        if timestamp is None:
            return datetime.now()
        
        if isinstance(timestamp, datetime):
            return timestamp
        
        if isinstance(timestamp, (int, float)):
            # Unix timestamp
            return datetime.fromtimestamp(timestamp)
        
        if isinstance(timestamp, str):
            # Try ISO format
            try:
                return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                pass
            
            # Try common formats
            for pattern in self.TIMESTAMP_PATTERNS:
                match = pattern.search(timestamp)
                if match:
                    ts_str = match.group(1)
                    try:
                        return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                    except ValueError:
                        continue
        
        # Fallback to current time
        return datetime.now()
    
    def _extract_message(
        self,
        line: str,
        timestamp_match: Optional[re.Match],
        level_match: Optional[re.Match],
        source_match: Optional[re.Match]
    ) -> str:
        """
        Extract message by removing matched timestamp, level, and source.
        
        Args:
            line: Original log line
            timestamp_match: Match object for timestamp
            level_match: Match object for level
            source_match: Match object for source
        
        Returns:
            Cleaned message string
        """
        # Build list of positions to remove (start, end)
        to_remove = []
        
        if timestamp_match:
            to_remove.append((timestamp_match.start(), timestamp_match.end()))
        
        if level_match:
            to_remove.append((level_match.start(), level_match.end()))
        
        if source_match:
            # For source matches, also remove trailing colon and whitespace if present
            start = source_match.start()
            end = source_match.end()
            # Check if there's a colon right after the match
            if end < len(line) and line[end] == ':':
                end += 1
            # Also remove following whitespace
            while end < len(line) and line[end] in ' \t':
                end += 1
            to_remove.append((start, end))
        
        # Sort by start position
        to_remove.sort(key=lambda x: x[0])
        
        # Remove from end to start to preserve indices
        message = line
        for start, end in reversed(to_remove):
            message = message[:start] + message[end:]
        
        # Clean up whitespace
        message = re.sub(r'\s+', ' ', message).strip()
        
        # Remove leading separators
        message = re.sub(r'^[:\-\s]+', '', message).strip()
        
        # If message is empty, use original line
        if not message:
            message = line.strip()
        
        return message
    
    def _extract_level(self, line: str) -> Optional[str]:
        """Extract log level from a plain text log line."""
        for pattern in self.LEVEL_PATTERNS:
            match = pattern.search(line)
            if match:
                return match.group(1).upper()
        return None
    
    def _extract_source(self, line: str) -> Optional[str]:
        """
        Extract source from a plain text log line.
        
        Looks for common patterns like:
        - [source] or (source)
        - service_name: or app_name:
        """
        # Pattern: [source] or (source)
        bracket_match = re.search(r'[\[\(]([a-zA-Z0-9_-]+)[\]\)]', line)
        if bracket_match:
            return bracket_match.group(1)
        
        # Pattern: source: at the beginning
        colon_match = re.search(r'^([a-zA-Z0-9_-]+):', line)
        if colon_match:
            return colon_match.group(1)
        
        return None
    
    def _clean_message(self, line: str, timestamp: datetime, level: str, source: str) -> str:
        """
        Clean the message by removing extracted components.
        
        Args:
            line: Original log line
            timestamp: Extracted timestamp
            level: Extracted level
            source: Extracted source
        
        Returns:
            Cleaned message string
        """
        message = line
        
        # Remove timestamp (match the full pattern including any trailing whitespace)
        for pattern in self.TIMESTAMP_PATTERNS:
            # Use the full match, not just group 1
            message = pattern.sub('', message, count=1)
        
        # Remove level (with surrounding whitespace)
        for pattern in self.LEVEL_PATTERNS:
            # Match level with optional surrounding whitespace
            level_pattern = re.compile(rf'\s*{re.escape(pattern.pattern)}\s*', re.IGNORECASE)
            message = level_pattern.sub(' ', message, count=1)
        
        # Remove source patterns (brackets and colons)
        if source and source != self.default_source:
            # Remove [source] or (source) with optional whitespace
            message = re.sub(rf'\s*[\[\(]{re.escape(source)}[\]\)]\s*', ' ', message, count=1)
            # Remove source: at the beginning with optional whitespace
            message = re.sub(rf'^\s*{re.escape(source)}:\s*', '', message, count=1)
        
        # Clean up whitespace and leading/trailing separators
        message = re.sub(r'^\s*[:\-\s]+\s*', '', message)  # Remove leading separators
        message = re.sub(r'\s+', ' ', message).strip()
        
        # If message is empty, use original line
        if not message:
            message = line.strip()
        
        return message
    
    def _detect_format(self, file_path: Path) -> str:
        """
        Detect log format from file extension and content.
        
        Args:
            file_path: Path to the log file
        
        Returns:
            Detected format ('json' or 'text')
        """
        ext = file_path.suffix.lower()
        if ext == '.json' or ext == '.jsonl':
            return 'json'
        
        # For .log files or unknown extensions, check content
        if ext == '.log' or not ext:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    return self._detect_format_from_stream(f)
            except Exception:
                # Fallback to text if detection fails
                return 'text'
        
        return 'text'
    
    def _detect_format_from_stream(self, stream: TextIO) -> str:
        """
        Detect log format by examining the first few lines.
        
        Args:
            stream: File stream to examine
        
        Returns:
            Detected format ('json' or 'text')
        """
        # Read first few lines to detect format
        lines_to_check = 5
        lines = []
        for i, line in enumerate(stream):
            if i >= lines_to_check:
                break
            line = line.strip()
            if line:
                lines.append(line)
        
        if not lines:
            return 'text'
        
        # Check if lines are valid JSON
        json_count = 0
        for line in lines:
            try:
                json.loads(line)
                json_count += 1
            except json.JSONDecodeError:
                pass
        
        # If majority are JSON, assume JSON format
        if json_count >= len(lines) * 0.8:
            return 'json'
        
        return 'text'

