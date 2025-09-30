"""
Hardware Test Configuration
Configure real hardware settings for testing
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class HardwareTestConfig:
    """Configuration for hardware testing"""
    # Serial connection
    port: str = "/dev/ttyUSB0"  # Windows default, adjust as needed
    baudrate: int = 115200
    timeout: float = 5.0
    
    # Safety limits for testing
    max_test_distance: float = 10.0  # mm - safe small movements
    max_feed_rate: float = 1000.0    # mm/min
    safe_z_height: float = 5.0       # mm above work surface
    
    # Test workspace bounds (work coordinates based on current machine position)
    # Machine currently at WPos: [0, 0, 49.249]
    min_x: float = -10.0
    max_x: float = 10.0
    min_y: float = -10.0
    max_y: float = 10.0
    min_z: float = 40.0      # Safe zone around current Z=49.249
    max_z: float = 60.0
    
    # Hardware capabilities
    has_homing: bool = True
    has_probe: bool = False
    axes_count: int = 3  # 3 or 4 axis
    
    # Test control
    skip_destructive_tests: bool = True
    require_manual_confirmation: bool = True


def get_hardware_config() -> HardwareTestConfig:
    """Get hardware configuration from environment or defaults"""
    config = HardwareTestConfig()
    
    # Override from environment variables if present
    config.port = os.getenv("CNC_TEST_PORT", config.port)
    config.baudrate = int(os.getenv("CNC_TEST_BAUDRATE", str(config.baudrate)))
    config.skip_destructive_tests = os.getenv("CNC_SKIP_DESTRUCTIVE", "true").lower() == "true"
    
    return config


def is_hardware_available() -> bool:
    """Check if hardware is available for testing"""
    import serial.tools.list_ports
    
    config = get_hardware_config()
    available_ports = [port.device for port in serial.tools.list_ports.comports()]
    
    return config.port in available_ports
