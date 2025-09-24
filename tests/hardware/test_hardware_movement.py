"""
Hardware Movement Tests
Test actual movement and positioning with real hardware
"""
import time
import unittest
from tests.hardware.base_hardware_test import BaseHardwareTest


class TestHardwareMovement(BaseHardwareTest):
    """Test actual machine movement with safety checks"""
    
    def test_small_jog_movement(self):
        """Test small jog movements in each axis"""
        initial_position = self.controller.get_position()
        
        # Test small movement in X
        result = self.safe_move_relative(x=1.0, feed_rate=300)
        self.assertTrue(result, "X+ movement failed")
        
        # Wait for movement to complete
        self.assertTrue(self.wait_for_idle(), "Movement did not complete")
        
        # Check position changed
        new_position = self.controller.get_position()
        self.assertGreater(new_position[0], initial_position[0], "X position did not increase")
        
        # Return to start
        self.safe_move_relative(x=-1.0, feed_rate=300)
        self.wait_for_idle()
        
        # Test Y axis
        result = self.safe_move_relative(y=1.0, feed_rate=300)
        self.assertTrue(result, "Y+ movement failed")
        self.wait_for_idle()
        
        y_position = self.controller.get_position()
        self.assertGreater(y_position[1], initial_position[1], "Y position did not increase")
        
        # Return to start
        self.safe_move_relative(y=-1.0, feed_rate=300)
        self.wait_for_idle()
        
        print("✅ Small jog movements completed successfully")
    
    def test_positioning_accuracy(self):
        """Test positioning accuracy with precise movements"""
        initial_position = self.controller.get_position()
        
        # Perform a precise movement
        test_distance = 5.0  # 5mm
        result = self.safe_move_relative(x=test_distance, feed_rate=200)
        self.assertTrue(result)
        self.wait_for_idle()
        
        # Check actual distance moved
        moved_position = self.controller.get_position()
        actual_distance = moved_position[0] - initial_position[0]
        
        # Should be within 0.1mm (typical CNC accuracy)
        self.assertAlmostEqual(
            actual_distance, test_distance, delta=0.1,
            msg=f"Expected {test_distance}mm, got {actual_distance:.3f}mm"
        )
        
        # Return to original position
        self.safe_move_relative(x=-test_distance, feed_rate=200)
        self.wait_for_idle()
        
        # Check we're back close to start
        final_position = self.controller.get_position()
        self.assertAlmostEqual(
            final_position[0], initial_position[0], delta=0.1,
            msg="Did not return to original position accurately"
        )
        
        print(f"✅ Positioning accuracy: {abs(actual_distance - test_distance):.3f}mm error")
    
    def test_feed_rate_control(self):
        """Test different feed rates"""
        # Test slow movement
        start_time = time.time()
        result = self.safe_move_relative(x=2.0, feed_rate=60)  # 1mm/s
        self.assertTrue(result)
        self.wait_for_idle()
        slow_time = time.time() - start_time
        
        # Return to start
        self.safe_move_relative(x=-2.0, feed_rate=300)
        self.wait_for_idle()
        
        # Test fast movement  
        start_time = time.time()
        result = self.safe_move_relative(x=2.0, feed_rate=600)  # 10mm/s
        self.assertTrue(result)
        self.wait_for_idle()
        fast_time = time.time() - start_time
        
        # Return to start
        self.safe_move_relative(x=-2.0, feed_rate=300)
        self.wait_for_idle()
        
        # Fast should be significantly quicker
        self.assertLess(fast_time, slow_time, 
                       f"Fast movement ({fast_time:.2f}s) not faster than slow ({slow_time:.2f}s)")
        
        print(f"✅ Feed rate test: Slow={slow_time:.2f}s, Fast={fast_time:.2f}s")
    
    def test_multi_axis_movement(self):
        """Test coordinated multi-axis movement"""
        initial_position = self.controller.get_position()
        
        # Move in X and Y simultaneously
        result = self.safe_move_relative(x=2.0, y=2.0, feed_rate=300)
        self.assertTrue(result)
        self.wait_for_idle()
        
        # Check both axes moved
        new_position = self.controller.get_position()
        self.assertGreater(new_position[0], initial_position[0], "X did not move")
        self.assertGreater(new_position[1], initial_position[1], "Y did not move")
        
        # Calculate actual diagonal distance
        dx = new_position[0] - initial_position[0]
        dy = new_position[1] - initial_position[1]
        actual_distance = (dx**2 + dy**2)**0.5
        expected_distance = (2.0**2 + 2.0**2)**0.5  # ~2.83mm
        
        self.assertAlmostEqual(
            actual_distance, expected_distance, delta=0.1,
            msg=f"Diagonal movement: expected {expected_distance:.2f}mm, got {actual_distance:.2f}mm"
        )
        
        # Return to start
        self.safe_move_relative(x=-2.0, y=-2.0, feed_rate=300)
        self.wait_for_idle()
        
        print("✅ Multi-axis coordinated movement successful")
    
    def test_movement_limits(self):
        """Test movement bounds checking"""
        # Try to move beyond safe limits (should be prevented by safe_move_relative)
        with self.assertRaises(ValueError):
            self.safe_move_relative(x=self.config.max_test_distance + 1)
        
        with self.assertRaises(ValueError):
            self.safe_move_relative(y=self.config.max_test_distance + 1)
        
        print("✅ Movement limits properly enforced")
    
    @unittest.skipIf(
        BaseHardwareTest.config and BaseHardwareTest.config.skip_destructive_tests,
        "Destructive tests disabled"  
    )
    def test_emergency_stop_during_movement(self):
        """Test emergency stop during movement"""
        # Start a longer movement
        result = self.safe_move_relative(x=5.0, feed_rate=100)  # Slow movement
        self.assertTrue(result)
        
        # Wait briefly then emergency stop
        time.sleep(0.5)
        self.controller.emergency_stop()
        
        # Check movement stopped (position should be between start and end)
        stopped_position = self.controller.get_position()
        
        # Should not have completed full movement
        self.assertLess(stopped_position[0] - self.initial_position[0], 5.0)
        self.assertGreater(stopped_position[0] - self.initial_position[0], 0.0)
        
        print(f"✅ Emergency stop effective - stopped at {stopped_position[0] - self.initial_position[0]:.2f}mm")
        
        # Reset and return to safe state
        self.controller.reset()
        time.sleep(2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
