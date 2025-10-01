"""
Hardware Test for SmartTimeoutController
Tests the smart timeout controller with real GRBL hardware, focusing on homing
"""
import time
import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from grbl import GRBLController, SmartTimeoutController
from tests.hardware.base_hardware_test import BaseHardwareTest, log_with_timestamp
from tests.hardware.test_config import get_hardware_config, is_hardware_available


class TestSmartTimeoutHardware(BaseHardwareTest):
    """Test SmartTimeoutController with real hardware"""
    
    @classmethod
    def setUpClass(cls):
        """Set up hardware connection with SmartTimeoutController"""
        cls.config = get_hardware_config()
        cls.base_controller = None
        cls.controller = None
        
        # Skip if hardware not available
        if not is_hardware_available():
            raise unittest.SkipTest(f"Hardware not available on port {cls.config.port}")
        
        # Manual confirmation for safety
        if cls.config.require_manual_confirmation:
            response = input(f"\n⚠️  SMART TIMEOUT HARDWARE TEST WARNING ⚠️\n"
                           f"This test will control real CNC hardware on {cls.config.port}\n"
                           f"It will test HOMING with dynamically calculated timeouts.\n"
                           f"Ensure machine is properly configured and safe to operate.\n"
                           f"Continue? (yes/no): ")
            if response.lower() != 'yes':
                raise unittest.SkipTest("Manual confirmation denied")
        
        # Create base controller
        cls.base_controller = GRBLController()
        
        # Wrap with SmartTimeoutController
        cls.controller = SmartTimeoutController(cls.base_controller)
        
        # Connect to hardware (will auto-configure machine settings)
        log_with_timestamp("Connecting with SmartTimeoutController...")
        if not cls.controller.connect(cls.config.port, cls.config.baudrate):
            raise unittest.SkipTest(f"Failed to connect to hardware on {cls.config.port}")
        
        log_with_timestamp(f"✅ Connected with SmartTimeoutController on {cls.config.port}")
        
        # Wait for auto-configuration to complete
        time.sleep(0.5)
        
        # Check if configuration was loaded
        if cls.controller._config_initialized:
            log_with_timestamp("✅ Machine configuration auto-loaded")
            
            # Display timeout calculator config
            config = cls.controller._timeout_calc.config
            log_with_timestamp(f"📊 Machine Config: X={config.max_rate_x} Y={config.max_rate_y} Z={config.max_rate_z} mm/min")
        else:
            log_with_timestamp("⚠️  Using default timeout configuration")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up hardware connection"""
        if cls.controller and cls.controller.is_connected():
            # Get timeout statistics before disconnect
            stats = cls.controller.get_timeout_statistics()
            if stats.get('total_commands', 0) > 0:
                log_with_timestamp(f"\n📊 Timeout Statistics:")
                log_with_timestamp(f"   Total commands: {stats['total_commands']}")
                log_with_timestamp(f"   Avg accuracy: {stats.get('avg_accuracy', 0):.2f}x")
                log_with_timestamp(f"   Min accuracy: {stats.get('min_accuracy', 0):.2f}x")
                log_with_timestamp(f"   Max accuracy: {stats.get('max_accuracy', 0):.2f}x")
            
            # Emergency stop and disconnect
            cls.controller.emergency_stop()
            time.sleep(0.5)
            cls.controller.disconnect()
            log_with_timestamp("✅ Disconnected from hardware")
    
    def test_01_homing_with_smart_timeout(self):
        """Test homing cycle with dynamically calculated timeout"""
        if not self.config.has_homing:
            self.skipTest("Machine does not have homing configured")
        
        log_with_timestamp("\n" + "="*60)
        log_with_timestamp("TEST: Homing with Smart Timeout")
        log_with_timestamp("="*60)
        
        # Get initial status
        initial_status = self.controller.get_status()
        log_with_timestamp(f"Initial status: {initial_status}")
        
        # Perform homing with smart timeout
        log_with_timestamp("🏠 Starting homing cycle...")
        start_time = time.time()
        
        try:
            result = self.controller.home()
            actual_time = time.time() - start_time
            
            log_with_timestamp(f"✅ Homing completed successfully in {actual_time:.2f}s")
            self.assertTrue(result, "Homing command should succeed")
            
            # Wait for machine to settle
            time.sleep(1.0)
            
            # Verify machine is at home position (should be close to 0,0,0 in machine coordinates)
            final_position = self.controller.get_position()
            log_with_timestamp(f"📍 Homed position: {final_position}")
            
            # After homing, machine should be at a known position
            # Typically close to 0,0,0 or max travel depending on homing direction
            self.assertIsNotNone(final_position, "Should have valid position after homing")
            
            # Check machine is idle
            final_status = self.controller.get_status()
            log_with_timestamp(f"📊 Final status: {final_status}")
            self.assertEqual(final_status, 'Idle', "Machine should be idle after homing")
            
            log_with_timestamp("✅ Homing test completed successfully")
            
        except TimeoutError as e:
            actual_time = time.time() - start_time
            log_with_timestamp(f"❌ Homing TIMEOUT after {actual_time:.2f}s")
            self.fail(f"Homing timeout error: {e}")
        
        except Exception as e:
            actual_time = time.time() - start_time
            log_with_timestamp(f"❌ Homing FAILED after {actual_time:.2f}s: {e}")
            raise
    
    def test_02_move_with_smart_timeout(self):
        """Test movement with smart timeout calculation"""
        log_with_timestamp("\n" + "="*60)
        log_with_timestamp("TEST: Movement with Smart Timeout")
        log_with_timestamp("="*60)
        
        initial_position = self.controller.get_position()
        log_with_timestamp(f"📍 Initial position: {initial_position}")
        
        # Test small movement with smart timeout
        target_x = initial_position[0] + 5.0
        target_y = initial_position[1] + 0.0
        target_z = initial_position[2] + 0.0
        
        # Calculate expected timeout
        command = f"G0 X{target_x:.3f} Y{target_y:.3f} Z{target_z:.3f}"
        calculated_timeout = self.controller._timeout_calc.calculate_timeout(
            command,
            self.controller._get_current_position_4axis()
        )
        log_with_timestamp(f"📊 Calculated timeout for 5mm move: {calculated_timeout:.1f}s")
        
        # Execute movement
        log_with_timestamp(f"🎯 Moving to X={target_x:.1f} Y={target_y:.1f} Z={target_z:.1f}")
        start_time = time.time()
        
        try:
            result = self.controller.move_to(target_x, target_y, target_z)
            actual_time = time.time() - start_time
            
            log_with_timestamp(f"✅ Movement completed in {actual_time:.2f}s")
            self.assertTrue(result, "Movement should succeed")
            
            # Wait for idle
            self.wait_for_idle(timeout=10.0)
            
            # Verify position
            final_position = self.controller.get_position()
            log_with_timestamp(f"📍 Final position: {final_position}")
            
            # Check we're close to target
            self.assertAlmostEqual(final_position[0], target_x, delta=0.5,
                                 msg="X position should match target")
            
            # Return to original position
            log_with_timestamp("↩️  Returning to start position")
            self.controller.move_to(initial_position[0], initial_position[1], initial_position[2])
            self.wait_for_idle(timeout=10.0)
            
            log_with_timestamp("✅ Movement test completed successfully")
            
        except TimeoutError as e:
            actual_time = time.time() - start_time
            log_with_timestamp(f"❌ Movement TIMEOUT after {actual_time:.2f}s")
            self.fail(f"Movement timeout - actual: {actual_time:.2f}s, calculated: {calculated_timeout:.1f}s")
        
        except Exception as e:
            log_with_timestamp(f"❌ Movement FAILED: {e}")
            raise
    
    def test_03_jog_with_smart_timeout(self):
        """Test jog with smart timeout calculation"""
        log_with_timestamp("\n" + "="*60)
        log_with_timestamp("TEST: Jog with Smart Timeout")
        log_with_timestamp("="*60)
        
        initial_position = self.controller.get_position()
        log_with_timestamp(f"📍 Initial position: {initial_position}")
        
        # Test jog movement
        jog_distance = 2.0  # mm
        feed_rate = 500.0  # mm/min
        
        log_with_timestamp(f"🎯 Jogging {jog_distance}mm at {feed_rate} mm/min")
        start_time = time.time()
        
        try:
            result = self.controller.jog_relative(x=jog_distance, feed_rate=feed_rate)
            actual_time = time.time() - start_time
            
            log_with_timestamp(f"✅ Jog completed in {actual_time:.2f}s")
            self.assertTrue(result, "Jog should succeed")
            
            # Wait for idle
            self.wait_for_idle(timeout=10.0)
            
            # Check position changed
            new_position = self.controller.get_position()
            distance_moved = new_position[0] - initial_position[0]
            log_with_timestamp(f"📊 Moved {distance_moved:.3f}mm (expected {jog_distance}mm)")
            
            self.assertAlmostEqual(distance_moved, jog_distance, delta=0.2,
                                 msg="Jog distance should match")
            
            # Return to start
            log_with_timestamp("↩️  Jogging back to start")
            self.controller.jog_relative(x=-jog_distance, feed_rate=feed_rate)
            self.wait_for_idle(timeout=10.0)
            
            log_with_timestamp("✅ Jog test completed successfully")
            
        except TimeoutError as e:
            log_with_timestamp(f"❌ Jog TIMEOUT")
            self.fail(f"Jog timeout error: {e}")
        
        except Exception as e:
            log_with_timestamp(f"❌ Jog FAILED: {e}")
            raise
    
    def test_04_timeout_statistics(self):
        """Test timeout statistics are being recorded"""
        log_with_timestamp("\n" + "="*60)
        log_with_timestamp("TEST: Timeout Statistics")
        log_with_timestamp("="*60)
        
        # Get statistics
        stats = self.controller.get_timeout_statistics()
        
        log_with_timestamp(f"📊 Statistics after tests:")
        log_with_timestamp(f"   Total commands: {stats.get('total_commands', 0)}")
        
        if stats.get('total_commands', 0) > 0:
            log_with_timestamp(f"   Average accuracy: {stats.get('avg_accuracy', 0):.2f}x")
            log_with_timestamp(f"   Min accuracy: {stats.get('min_accuracy', 0):.2f}x")
            log_with_timestamp(f"   Max accuracy: {stats.get('max_accuracy', 0):.2f}x")
            log_with_timestamp(f"   Current safety factor: {stats.get('current_safety_factor', 0):.2f}")
            
            # Verify statistics are reasonable
            self.assertGreater(stats['total_commands'], 0, "Should have recorded commands")
            self.assertGreater(stats['avg_accuracy'], 0, "Average accuracy should be positive")
            
            log_with_timestamp("✅ Statistics recording working correctly")
        else:
            log_with_timestamp("⚠️  No statistics recorded yet")


if __name__ == '__main__':
    unittest.main(verbosity=2)
