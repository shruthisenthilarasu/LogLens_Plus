"""
Configuration management for LogLens++.

Supports YAML configuration files for defining metrics, time windows,
and alert thresholds without code changes.
"""

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import timedelta

from loglens.analytics import Metric, AggregationType
from loglens.analytics.anomaly_detector import AnomalyDetector


@dataclass
class MetricConfig:
    """Configuration for a single metric."""
    
    name: str
    filter: str  # Python expression as string
    aggregation: str
    window: str  # e.g., "5m", "1h"
    description: Optional[str] = None
    group_by: Optional[str] = None  # Python expression
    value_extractor: Optional[str] = None  # Python expression
    percentile: Optional[float] = None


@dataclass
class AnomalyConfig:
    """Configuration for anomaly detection."""
    
    metric_name: str
    window_size: int = 20
    threshold: float = 2.0
    min_samples: int = 5
    enabled: bool = True


@dataclass
class StorageConfig:
    """Configuration for storage."""
    
    db_path: str = "loglens.db"
    retention_days: Optional[int] = None  # Auto-delete events older than this


@dataclass
class LogLensConfig:
    """Main configuration class."""
    
    metrics: List[MetricConfig] = field(default_factory=list)
    anomalies: List[AnomalyConfig] = field(default_factory=list)
    storage: StorageConfig = field(default_factory=StorageConfig)
    default_source: str = "unknown"
    default_level: str = "INFO"
    
    @classmethod
    def from_file(cls, config_path: Union[str, Path]) -> 'LogLensConfig':
        """
        Load configuration from YAML file.
        
        Args:
            config_path: Path to YAML config file
        
        Returns:
            LogLensConfig instance
        
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
        
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LogLensConfig':
        """
        Create config from dictionary.
        
        Args:
            data: Configuration dictionary
        
        Returns:
            LogLensConfig instance
        """
        # Parse metrics
        metrics = []
        for metric_data in data.get('metrics', []):
            metrics.append(MetricConfig(**metric_data))
        
        # Parse anomalies
        anomalies = []
        for anomaly_data in data.get('anomalies', []):
            anomalies.append(AnomalyConfig(**anomaly_data))
        
        # Parse storage
        storage_data = data.get('storage', {})
        storage = StorageConfig(**storage_data)
        
        return cls(
            metrics=metrics,
            anomalies=anomalies,
            storage=storage,
            default_source=data.get('default_source', 'unknown'),
            default_level=data.get('default_level', 'INFO')
        )
    
    def to_metrics(self) -> List[Metric]:
        """
        Convert metric configs to Metric objects.
        
        Returns:
            List of Metric objects
        """
        metrics = []
        
        for metric_config in self.metrics:
            # Compile filter function
            filter_func = self._compile_expression(metric_config.filter, 'event')
            
            # Parse aggregation
            aggregation = metric_config.aggregation.lower()
            try:
                aggregation = AggregationType(aggregation)
            except ValueError:
                # Keep as string if custom
                pass
            
            # Compile optional functions
            group_by = None
            if metric_config.group_by:
                group_by = self._compile_expression(metric_config.group_by, 'event')
            
            value_extractor = None
            if metric_config.value_extractor:
                value_extractor = self._compile_expression(metric_config.value_extractor, 'event')
            
            metric = Metric(
                name=metric_config.name,
                filter=filter_func,
                aggregation=aggregation,
                window=metric_config.window,
                description=metric_config.description,
                group_by=group_by,
                value_extractor=value_extractor,
                percentile=metric_config.percentile
            )
            
            metrics.append(metric)
        
        return metrics
    
    def to_anomaly_detectors(self) -> Dict[str, AnomalyDetector]:
        """
        Convert anomaly configs to AnomalyDetector objects.
        
        Returns:
            Dictionary of metric_name -> AnomalyDetector
        """
        detectors = {}
        
        for anomaly_config in self.anomalies:
            if not anomaly_config.enabled:
                continue
            
            detector = AnomalyDetector(
                metric_name=anomaly_config.metric_name,
                window_size=anomaly_config.window_size,
                threshold=anomaly_config.threshold,
                min_samples=anomaly_config.min_samples
            )
            
            detectors[anomaly_config.metric_name] = detector
        
        return detectors
    
    @staticmethod
    def _compile_expression(expr: str, param_name: str = 'event'):
        """
        Compile a Python expression string into a function.
        
        Args:
            expr: Python expression as string
            param_name: Name of the parameter
        
        Returns:
            Compiled function
        
        Note: This uses eval with restricted globals. In production,
        consider using a more secure expression evaluator.
        """
        # Compile the expression
        code = compile(expr, '<string>', 'eval')
        
        # Safe builtins - only allow safe operations
        safe_builtins = {
            'True': True,
            'False': False,
            'None': None,
            'in': lambda x, y: x in y,
            'not': lambda x: not x,
            'and': lambda x, y: x and y,
            'or': lambda x, y: x or y,
        }
        
        def func(event):
            # Evaluate with restricted environment
            return eval(code, {'__builtins__': safe_builtins}, {param_name: event})
        
        return func


def load_config(config_path: Optional[Union[str, Path]] = None) -> LogLensConfig:
    """
    Load configuration from file or return default.
    
    Args:
        config_path: Path to config file. If None, looks for loglens.yaml in current dir
    
    Returns:
        LogLensConfig instance
    """
    if config_path is None:
        # Look for config in common locations
        possible_paths = [
            Path("loglens.yaml"),
            Path("loglens.yml"),
            Path(".loglens.yaml"),
            Path("~/.loglens.yaml").expanduser(),
        ]
        
        for path in possible_paths:
            if path.exists():
                config_path = path
                break
        
        if config_path is None:
            # Return default config
            return LogLensConfig()
    
    return LogLensConfig.from_file(config_path)


def create_default_config(config_path: Union[str, Path] = "loglens.yaml") -> None:
    """
    Create a default configuration file.
    
    Args:
        config_path: Path where to create the config file
    """
    default_config = {
        'default_source': 'unknown',
        'default_level': 'INFO',
        
        'storage': {
            'db_path': 'loglens.db',
            'retention_days': 30
        },
        
        'metrics': [
            {
                'name': 'error_count',
                'filter': "event.level in ('ERROR', 'CRITICAL', 'FATAL')",
                'aggregation': 'count',
                'window': '5m',
                'description': 'Count of error-level events'
            },
            {
                'name': 'warning_count',
                'filter': "event.level == 'WARNING'",
                'aggregation': 'count',
                'window': '5m',
                'description': 'Count of warning events'
            },
            {
                'name': 'events_by_source',
                'filter': 'True',
                'aggregation': 'count',
                'window': '15m',
                'group_by': 'event.source',
                'description': 'Event count grouped by source'
            },
            {
                'name': 'events_by_level',
                'filter': 'True',
                'aggregation': 'count',
                'window': '15m',
                'group_by': 'event.level',
                'description': 'Event count grouped by log level'
            }
        ],
        
        'anomalies': [
            {
                'metric_name': 'error_count',
                'window_size': 20,
                'threshold': 2.0,
                'min_samples': 5,
                'enabled': True
            },
            {
                'metric_name': 'warning_count',
                'window_size': 20,
                'threshold': 2.5,
                'min_samples': 5,
                'enabled': True
            }
        ]
    }
    
    with open(config_path, 'w') as f:
        yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
    
    print(f"Created default configuration at: {config_path}")

