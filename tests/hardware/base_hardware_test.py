"""
Base Hardware Test Class
Provides common functionality for hardware testing
"""
import unittest
import time
import sys
import os
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from grbl.controller import GRBLController
from tests.hardware.test_config import get_hardware_config, is_hardware_available


class BaseHardwareTest(unittest.TestCase):
    """Base class for hardware tests with safety features"""
    
    @classmethod
    def setUpClass(cls):
        """Set up hardware connection for all tests in class"""
        cls.config = get_hardware_config()
        cls.controller: Optional[GRBLController] = None
        
        # Skip if hardware not available
        if not is_hardware_available():
            raise unittest.SkipTest(f"Hardware not available on port {cls.config.port}")
        
        # Manual confirmation for safety
        if cls.config.require_manual_confirmation:
            response = input(f"\n⚠️  HARDWARE TEST WARNING ⚠️\n"
                           f"This test will control real CNC hardware on {cls.config.port}\n"
                           f"Ensure machine is properly configured and safe to operate.\n"
                           f"Continue? (yes/no): ")
            if response.lower() != 'yes':
                raise unittest.SkipTest("Manual confirmation denied")
        
        # Connect to hardware
        cls.controller = GRBLController()
        if not cls.controller.connect(cls.config.port, cls.config.baudrate):
            raise unittest.SkipTest(f"Failed to connect to hardware on {cls.config.port}")
        
        print(f"✅ Connected to CNC hardware on {cls.config.port}")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up hardware connection"""
        if cls.controller and cls.controller.is_connected():
            # Emergency stop and disconnect
            cls.controller.emergency_stop()
            time.sleep(0.5)
            cls.controller.disconnect()
            print("✅ Disconnected from hardware")
    
    def setUp(self):
        """Set up for individual test"""
        self.assertTrue(self.controller.is_connected(), "Hardware not connected")
        
        # Get initial position and status
        self.initial_position = self.controller.get_position()
        self.initial_status = self.controller.get_status()
        
        print(f"📍 Initial position: {self.initial_position}")
        print(f"📊 Initial status: {self.initial_status}")
        
        # Ensure machine is in safe state
        if self.initial_status not in ['Idle', 'Hold']:
            self.controller.emergency_stop()
            time.sleep(1)
            self.controller.reset()
            time.sleep(2)
    
    def tearDown(self):
        """Clean up after individual test"""
        if self.controller and self.controller.is_connected():
            # Stop any movement and return to safe state
            self.controller.emergency_stop()
            time.sleep(0.5)
            
            # Reset if needed
            status = self.controller.get_status()
            if status not in ['Idle']:
                self.controller.reset()
                time.sleep(2)
    
    def safe_move_relative(self, x: float = 0, y: float = 0, z: float = 0, feed_rate: float = 500):
        """Safely move relative with bounds checking"""
        # Check bounds
        current_pos = self.controller.get_position()
        new_x = current_pos[0] + x
        new_y = current_pos[1] + y
        new_z = current_pos[2] + z
        
        # Validate within safe bounds
        if not (self.config.min_x <= new_x <= self.config.max_x):
            raise ValueError(f"X movement {new_x} outside safe bounds [{self.config.min_x}, {self.config.max_x}]")
        
        if not (self.config.min_y <= new_y <= self.config.max_y):
            raise ValueError(f"Y movement {new_y} outside safe bounds [{self.config.min_y}, {self.config.max_y}]")
        
        if not (self.config.min_z <= new_z <= self.config.max_z):
            raise ValueError(f"Z movement {new_z} outside safe bounds [{self.config.min_z}, {self.config.max_z}]")
        
        # Check movement distance
        distance = (x**2 + y**2 + z**2)**0.5
        if distance > self.config.max_test_distance:
            raise ValueError(f"Movement distance {distance:.2f}mm exceeds max {self.config.max_test_distance}mm")
        
        # Perform safe movement
        return self.controller.jog_relative(x, y, z, min(feed_rate, self.config.max_feed_rate))
    
    def wait_for_idle(self, timeout: float = 30.0) -> bool:
        """Wait for machine to reach idle state"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.controller.get_status()
            if status == 'Idle':
                return True
            elif status in ['Alarm', 'Error']:
                return False
            time.sleep(0.1)
        
        return False
    
    def assert_position_near(self, expected_position: list, tolerance: float = 0.1):
        """Assert current position is near expected position within tolerance"""
        actual_position = self.controller.get_position()
        
        for i, (actual, expected) in enumerate(zip(actual_position, expected_position)):
            self.assertAlmostEqual(
                actual, expected, delta=tolerance,
                msg=f"Axis {i}: expected {expected:.3f}, got {actual:.3f}, tolerance {tolerance}"
            )
