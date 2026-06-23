"""
Configuration management for the oil spill analysis pipeline
"""

import os
import json
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class Config:
    """Central configuration manager for the pipeline"""
    
    def __init__(self, config_path: str = None):
        """
        Initialize configuration from file or use defaults
        
        Parameters:
        -----------
        config_path : str, optional
            Path to JSON configuration file
        """
        self.config = self._get_default_config()
        
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                self.config.update(user_config)
                logger.info(f"Loaded configuration from {config_path}")
    
    @staticmethod
    def _get_default_config() -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'data': {
                'raw_dir': '../data/raw',
                'processed_dir': 'data/processed',
                'outputs_dir': 'outputs',
                'animations_dir': 'outputs/animations',
                'figures_dir': 'outputs/figures',
                'logs_dir': 'logs'
            },
            'extraction': {
                'tiff_patterns': ['*.tif', '*.tiff']
            },
            'download': {
                'cds_api_key': None,  # Set from environment or config
                'cmems_username': None,  # Set from environment or config
                'cmems_password': None,  # Set from environment or config
                'era5_grid_resolution': 0.25,
                'era5_padding': 0.25,
                'cmems_dataset_id': 'cmems_mod_glo_phy_my_0.083deg_P1D-m'
            },
            'simulation': {
                'oil_type': 'GENERIC MEDIUM CRUDE',
                'coastline_action': 'previous',
                'num_particles': 1000,
                'duration_hours': 24,
                'horizontal_diffusivity': 1.0,
                'wind_uncertainty': 0.2,
                'current_uncertainty': 0.1
            },
            'pg_classifier': {
                'darkness_threshold': -15.0,  # dB
                'smoothness_threshold': 1.5,  # dB
                'elongation_min': 1.8,
                'compactness_min': 2.0,
                'alignment_tolerance': 40.0,  # degrees
                'trajectory_distance_threshold': 10.0,  # km
                'drift_time_window': (1, 2)  # hours
            },
            'rf_classifier': {
                'model_path': '../models/rf_classifier.pkl',
                'feature_columns': [
                    'mean_intensity', 
                    'std_intensity', 
                    'elongation_ratio', 
                    'compactness'
                ]
            },
            'decision_layer': {
                'pg_weight': 0.4,
                'rf_weight': 0.4,
                'nlp_weight': 0.2,
                'confidence_threshold': 0.5
            },
            # configuration for the computer vision model wrapper
            'cv_model': {
                'quick_inference_path': 'mados',
                'model_type': 'marinext',
                'fallback_enabled': True,
                'darkness_threshold': -18.0
            }
        }
    
    def get(self, key: str, default=None) -> Any:
        """Get configuration value using dot notation"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value using dot notation"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
    
    def save(self, output_path: str) -> None:
        """Save configuration to JSON file"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(self.config, f, indent=2)
        logger.info(f"Configuration saved to {output_path}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary"""
        return self.config.copy()


# Global configuration instance
_global_config = None


def get_config() -> Config:
    """Get or create global configuration instance"""
    global _global_config
    if _global_config is None:
        _global_config = Config()
    return _global_config


def set_config(config: Config) -> None:
    """Set global configuration instance"""
    global _global_config
    _global_config = config
