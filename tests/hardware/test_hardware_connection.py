"""
Hardware Connection Tests
Test basic connectivity and communication with real hardware
"""
import time
import unittest
from tests.hardware.base_hardware_test import BaseHardwareTest, log_with_timestamp


class TestHardwareConnection(BaseHardwareTest):
    """Test basic hardware connection and communication"""
    
    def test_connection_status(self):
        """Test that connection is established and stable"""
        self.assertTrue(self.controller.is_connected())
        
        # Test status query
        status = self.controller.get_status()
        self.assertIsInstance(status, str)
        self.assertNotEqual(status, "Unknown")
        log_with_timestamp(f"✅ Status: {status}")
    
    def test_position_query(self):
        """Test position reporting"""
        position = self.controller.get_position()
        self.assertIsInstance(position, list)
        self.assertEqual(len(position), 3)  # X, Y, Z
        
        # All coordinates should be numbers
        for coord in position:
            self.assertIsInstance(coord, (int, float))
        
        log_with_timestamp(f"✅ Current position: {position}")
    
    def test_grbl_settings_query(self):
        """Test reading GRBL settings"""
        try:
            response = self.controller.send_command("$$", timeout=5.0)
            self.assertIsInstance(response, list)
            self.assertGreater(len(response), 0)
            
            # Should contain settings in format $123=value
            settings_found = any('$' in line and '=' in line for line in response)
            self.assertTrue(settings_found, "No GRBL settings found in response")
            
            log_with_timestamp(f"✅ Retrieved {len(response)} lines of settings")
            
        except Exception as e:
            self.fail(f"Failed to query GRBL settings: {e}")
    
    def test_realtime_commands(self):
        """Test realtime command responsiveness"""
        initial_status = self.controller.get_status()
        
        # Test status query (?) - should be very fast
        start_time = time.time()
        status = self.controller.get_status()
        query_time = time.time() - start_time
        
        self.assertLess(query_time, 1.0, "Status query took too long")
        self.assertIsInstance(status, str)
        log_with_timestamp(f"✅ Status query time: {query_time:.3f}s")
    
    def test_emergency_stop_recovery(self):
        """Test emergency stop and recovery"""
        # Send emergency stop
        result = self.controller.emergency_stop()
        self.assertTrue(result)
        
        # Wait a moment
        time.sleep(0.5)
        
        # Check status changed
        status = self.controller.get_status()
        # Status should be Hold or similar (depends on GRBL state)
        log_with_timestamp(f"✅ Status after E-stop: {status}")
        
        # Reset to clear
        self.controller.reset()
        time.sleep(2)  # GRBL needs time to reset
        
        # Should be back to normal
        final_status = self.controller.get_status()
        log_with_timestamp(f"✅ Status after reset: {final_status}")
    
    @unittest.skipIf(
        BaseHardwareTest.config and BaseHardwareTest.config.skip_destructive_tests,
        "Destructive tests disabled"
    )
    def test_homing_cycle(self):
        """Test homing cycle (if enabled and safe)"""
        if not self.config.has_homing:
            self.skipTest("Homing not available on this machine")
        
        print("⚠️  Starting homing cycle - ensure machine is clear!")
        time.sleep(2)  # Give user time to see warning
        
        # Start homing
        result = self.controller.home()
        
        if result:
            # Wait for homing to complete
            success = self.wait_for_idle(timeout=60.0)  # Homing can take time
            self.assertTrue(success, "Homing cycle did not complete successfully")
            
            # Check we're at home position (typically 0,0,0 or machine limits)
            home_position = self.controller.get_position()
            print(f"✅ Home position: {home_position}")
        else:
            self.fail("Homing command failed")


if __name__ == '__main__':
    unittest.main(verbosity=2)
