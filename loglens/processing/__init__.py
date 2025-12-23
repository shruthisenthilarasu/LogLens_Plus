"""
Log processing module.

This module handles parsing, transformation, and normalization of log data.
"""

from loglens.processing.window_processor import (
    RollingWindowProcessor,
    WindowMetrics,
    WindowType
)

__all__ = ['RollingWindowProcessor', 'WindowMetrics', 'WindowType']

