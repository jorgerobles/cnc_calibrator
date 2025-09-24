"""
GRBL Configuration Parser - Extracts machine parameters from GRBL settings
"""
import re
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class GRBLMachineConfig:
    """GRBL machine configuration parameters for up to 4 axes"""
    
    # Max rates (mm/min for linear, degrees/min for rotary)
    max_rate_x: float = 1000.0
    max_rate_y: float = 1000.0  
    max_rate_z: float = 1000.0
    max_rate_a: float = 3600.0    # A-axis (rotary) - degrees/min
    
    # Acceleration (mm/sec² for linear, degrees/sec² for rotary)
    acceleration_x: float = 10.0
    acceleration_y: float = 10.0
    acceleration_z: float = 10.0
    acceleration_a: float = 360.0  # A-axis - degrees/sec²
    
    # Homing rates (mm/min)
    homing_feed_rate: float = 25.0
    homing_seek_rate: float = 500.0
    
    # Max travel (mm for linear, degrees for rotary)
    max_travel_x: float = 200.0
    max_travel_y: float = 200.0
    max_travel_z: float = 200.0
    max_travel_a: float = 360.0   # A-axis - full rotation
    
    # Axis configuration
    num_axes: int = 4
    has_rotary_a: bool = True     # A-axis is rotary
    
    # Default feed rate if not specified
    default_feed_rate: float = 1000.0


class GRBLConfigParser:
    """Parses GRBL settings to extract machine configuration"""
    
    # GRBL setting mappings for 4-axis machines
    SETTING_MAP = {
        "$110": "max_rate_x",
        "$111": "max_rate_y", 
        "$112": "max_rate_z",
        "$113": "max_rate_a",        # A-axis max rate
        "$120": "acceleration_x",
        "$121": "acceleration_y",
        "$122": "acceleration_z",
        "$123": "acceleration_a",    # A-axis acceleration
        "$24": "homing_feed_rate",
        "$25": "homing_seek_rate",
        "$130": "max_travel_x",
        "$131": "max_travel_y",
        "$132": "max_travel_z",
        "$133": "max_travel_a"       # A-axis max travel
    }
    
    def parse_settings(self, settings_response: list) -> GRBLMachineConfig:
        """Parse GRBL $$ output into machine configuration"""
        config = GRBLMachineConfig()
        
        for line in settings_response:
            match = re.match(r'(\$\d+)=([\d.]+)', line.strip())
            if match:
                setting_id, value = match.groups()
                if setting_id in self.SETTING_MAP:
                    attr_name = self.SETTING_MAP[setting_id]
                    setattr(config, attr_name, float(value))
        
        return config
    
    def create_default_config(self) -> GRBLMachineConfig:
        """Create default configuration for fallback"""
        return GRBLMachineConfig()
