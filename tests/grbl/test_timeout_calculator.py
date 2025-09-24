"""
Comprehensive unit tests for Timeout Calculator system
Save as: tests/test_timeout_calculator.py
"""
import unittest
import math
from unittest.mock import Mock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..')))

# Import directly from specific files to avoid package dependencies
from grbl.config import GRBLMachineConfig, GRBLConfigParser
from grbl.timeout.command_analyzer import CommandAnalyzer, CommandType, ParsedCommand
from grbl.timeout.movement_calculator import MovementCalculator, SafetyMarginProvider
from grbl.timeout.calculator import TimeoutCalculator, TimeoutCalculatorService


class TestGRBLConfigParser(unittest.TestCase):
    
    def setUp(self):
        self.parser = GRBLConfigParser()
    
    def test_parse_basic_settings(self):
        """Test parsing of basic GRBL settings (4-axis)"""
        settings = [
            "$110=1000.000",  # X max rate
            "$111=1000.000",  # Y max rate  
            "$112=500.000",   # Z max rate
            "$113=3600.000",  # A max rate (rotary)
            "$120=10.000",    # X acceleration
            "$121=10.000",    # Y acceleration
            "$122=2.000",     # Z acceleration
            "$123=360.000",   # A acceleration (rotary)
        ]
        
        config = self.parser.parse_settings(settings)
        
        self.assertEqual(config.max_rate_x, 1000.0)
        self.assertEqual(config.max_rate_y, 1000.0)
        self.assertEqual(config.max_rate_z, 500.0)
        self.assertEqual(config.max_rate_a, 3600.0)
        self.assertEqual(config.acceleration_x, 10.0)
        self.assertEqual(config.acceleration_y, 10.0)
        self.assertEqual(config.acceleration_z, 2.0)
        self.assertEqual(config.acceleration_a, 360.0)
    
    def test_parse_homing_settings(self):
        """Test parsing of homing-related settings"""
        settings = [
            "$24=25.000",   # Homing feed rate
            "$25=500.000",  # Homing seek rate
        ]
        
        config = self.parser.parse_settings(settings)
        
        self.assertEqual(config.homing_feed_rate, 25.0)
        self.assertEqual(config.homing_seek_rate, 500.0)
    
    def test_parse_travel_settings(self):
        """Test parsing of max travel settings"""
        settings = [
            "$130=200.000",  # X max travel
            "$131=200.000",  # Y max travel
            "$132=200.000",  # Z max travel
            "$133=360.000",  # A max travel (rotary)
        ]
        
        config = self.parser.parse_settings(settings)
        
        self.assertEqual(config.max_travel_x, 200.0)
        self.assertEqual(config.max_travel_y, 200.0)
        self.assertEqual(config.max_travel_z, 200.0)
        self.assertEqual(config.max_travel_a, 360.0)
    
    def test_parse_malformed_settings(self):
        """Test handling of malformed settings"""
        settings = [
            "invalid line",
            "$110",  # Missing value
            "$999=123.456",  # Unknown setting
            "$110=1000.000",  # Valid setting
        ]
        
        config = self.parser.parse_settings(settings)
        
        # Should still parse the valid setting
        self.assertEqual(config.max_rate_x, 1000.0)
        # Other values should remain defaults
        self.assertEqual(config.max_rate_y, 1000.0)  # Default
    
    def test_default_config(self):
        """Test default configuration creation"""
        config = self.parser.create_default_config()
        
        self.assertIsInstance(config, GRBLMachineConfig)
        self.assertEqual(config.max_rate_x, 1000.0)
        self.assertEqual(config.max_rate_a, 3600.0)
        self.assertEqual(config.default_feed_rate, 1000.0)


class TestCommandAnalyzer(unittest.TestCase):
    
    def setUp(self):
        self.analyzer = CommandAnalyzer()
        self.current_pos = (0.0, 0.0, 0.0, 0.0)  # 4-axis position
    
    def test_parse_rapid_move(self):
        """Test parsing G0 rapid move commands (4-axis)"""
        command = "G0 X10 Y20 Z5 A90 F1500"
        parsed = self.analyzer.parse_command(command, self.current_pos)
        
        self.assertEqual(parsed.command_type, CommandType.RAPID_MOVE)
        self.assertEqual(parsed.target_position, (10.0, 20.0, 5.0, 90.0))
        self.assertEqual(parsed.feed_rate, 1500.0)
    
    def test_parse_linear_move(self):
        """Test parsing G1 linear move commands (4-axis)"""
        command = "G1 X-5.5 Y10.25 A180 F800"
        parsed = self.analyzer.parse_command(command, self.current_pos)
        
        self.assertEqual(parsed.command_type, CommandType.LINEAR_MOVE)
        self.assertEqual(parsed.target_position, (-5.5, 10.25, 0.0, 180.0))
        self.assertEqual(parsed.feed_rate, 800.0)
    
    def test_parse_4axis_movement(self):
        """Test parsing 4-axis simultaneous movement"""
        command = "G1 X100 Y50 Z-10 A270 F600"
        parsed = self.analyzer.parse_command(command, self.current_pos)
        
        self.assertEqual(parsed.command_type, CommandType.LINEAR_MOVE)
        self.assertEqual(parsed.target_position, (100.0, 50.0, -10.0, 270.0))
        self.assertEqual(parsed.feed_rate, 600.0)
    
    def test_parse_circular_move_g2(self):
        """Test parsing G2 clockwise circular move"""
        command = "G2 X10 Y10 I5 J0 F500"
        parsed = self.analyzer.parse_command(command, self.current_pos)
        
        self.assertEqual(parsed.command_type, CommandType.CIRCULAR_MOVE)
        self.assertEqual(parsed.target_position, (10.0, 10.0, 0.0, 0.0))
        self.assertEqual(parsed.arc_center, (5.0, 0.0))
        self.assertTrue(parsed.is_clockwise)
        self.assertEqual(parsed.feed_rate, 500.0)
    
    def test_parse_circular_move_g3(self):
        """Test parsing G3 counter-clockwise circular move"""
        command = "G3 X0 Y10 R5"
        parsed = self.analyzer.parse_command(command, self.current_pos)
        
        self.assertEqual(parsed.command_type, CommandType.CIRCULAR_MOVE)
        self.assertEqual(parsed.target_position, (0.0, 10.0, 0.0, 0.0))
        self.assertEqual(parsed.arc_radius, 5.0)
        self.assertFalse(parsed.is_clockwise)
    
    def test_parse_homing_command(self):
        """Test parsing homing command"""
        command = "$H"
        parsed = self.analyzer.parse_command(command, self.current_pos)
        
        self.assertEqual(parsed.command_type, CommandType.HOMING)
    
    def test_parse_status_query(self):
        """Test parsing status query"""
        command = "?"
        parsed = self.analyzer.parse_command(command, self.current_pos)
        
        self.assertEqual(parsed.command_type, CommandType.STATUS_QUERY)
    
    def test_parse_settings_command(self):
        """Test parsing settings command"""
        command = "$$"
        parsed = self.analyzer.parse_command(command, self.current_pos)
        
        self.assertEqual(parsed.command_type, CommandType.SETTINGS)
    
    def test_calculate_4d_distance(self):
        """Test 4D distance calculation with rotary axis"""
        start = (0.0, 0.0, 0.0, 350.0)   # 350° A position
        end = (30.0, 40.0, 0.0, 10.0)    # 10° A position
        
        # Test with rotary A-axis
        distance = self.analyzer.calculate_4d_distance(start, end, has_rotary_a=True)
        
        # Linear distance is 50mm (3-4-5 triangle)
        # Rotary distance should be 20° (shortest path), not 340°
        # Should return the dominant motion (50mm > 20°)
        self.assertAlmostEqual(distance, 50.0, places=1)
    
    def test_calculate_arc_length(self):
        """Test arc length calculation"""
        start = (0.0, 0.0, 0.0, 0.0)     # Updated for 4-axis
        end = (0.0, 10.0, 0.0, 0.0)      # Updated for 4-axis  
        center = (0.0, 5.0)
        
        arc_length = self.analyzer.calculate_arc_length(start[:3], end[:3], center, radius=5.0)
        
        # Should be approximately π * radius (half circle)
        expected = math.pi * 5.0
        self.assertAlmostEqual(arc_length, expected, places=1)


class TestMovementCalculator(unittest.TestCase):
    
    def setUp(self):
        self.config = GRBLMachineConfig(
            max_rate_x=1000.0,
            max_rate_y=1000.0,
            max_rate_z=500.0,
            max_rate_a=3600.0,      # 60 degrees/sec
            acceleration_x=10.0,
            acceleration_y=10.0,
            acceleration_z=5.0,
            acceleration_a=360.0,   # 6 degrees/sec²
            default_feed_rate=800.0,
            has_rotary_a=True
        )
        self.calculator = MovementCalculator(self.config)
        self.current_pos = (0.0, 0.0, 0.0, 0.0)  # 4-axis position
    
    def test_4axis_move_timing(self):
        """Test timing calculation for 4-axis moves"""
        parsed_cmd = ParsedCommand(
            command_type=CommandType.LINEAR_MOVE,
            target_position=(100.0, 0.0, 0.0, 180.0),  # 100mm X + 180° A rotation
            feed_rate=600.0,
            raw_command="G1 X100 A180 F600"
        )
        
        time = self.calculator.calculate_movement_time(parsed_cmd, self.current_pos)
        
        # Should consider both linear and rotary motion
        self.assertGreater(time, 5.0)
        self.assertLess(time, 60.0)
    
    def test_rotary_only_move(self):
        """Test timing calculation for rotary-only moves"""
        parsed_cmd = ParsedCommand(
            command_type=CommandType.LINEAR_MOVE,
            target_position=(0.0, 0.0, 0.0, 360.0),  # Full rotation
            feed_rate=1800.0,  # 30 degrees/sec
            raw_command="G1 A360 F1800"
        )
        
        time = self.calculator.calculate_movement_time(parsed_cmd, self.current_pos)
        
        # 360° at 30°/sec should take about 12 seconds (plus acceleration)
        self.assertGreater(time, 10.0)
        self.assertLess(time, 20.0)
    
    def test_rotary_wrapping(self):
        """Test rotary axis wrapping (shortest path)"""
        # Move from 350° to 10° (shortest path is 20°, not 340°)
        current_pos = (0.0, 0.0, 0.0, 350.0)
        parsed_cmd = ParsedCommand(
            command_type=CommandType.LINEAR_MOVE,
            target_position=(0.0, 0.0, 0.0, 10.0),
            feed_rate=1800.0,
            raw_command="G1 A10 F1800"
        )
        
        time = self.calculator.calculate_movement_time(parsed_cmd, current_pos)
        
        # Should be much faster than 340° movement
        self.assertLess(time, 5.0)  # 20° should be quick
    
    def test_rapid_move_timing(self):
        """Test timing calculation for rapid moves"""
        parsed_cmd = ParsedCommand(
            command_type=CommandType.RAPID_MOVE,
            target_position=(100.0, 0.0, 0.0, 0.0),
            raw_command="G0 X100"
        )
        
        time = self.calculator.calculate_movement_time(parsed_cmd, self.current_pos)
        
        # Should be faster than linear move (uses max machine rate)
        self.assertGreater(time, 0.0)
        self.assertLess(time, 60.0)  # Reasonable upper bound
    
    def test_linear_move_timing(self):
        """Test timing calculation for linear moves"""
        parsed_cmd = ParsedCommand(
            command_type=CommandType.LINEAR_MOVE,
            target_position=(60.0, 80.0, 0.0, 0.0),  # 100mm diagonal
            feed_rate=600.0,  # 10mm/sec
            raw_command="G1 X60 Y80 F600"
        )
        
        time = self.calculator.calculate_movement_time(parsed_cmd, self.current_pos)
        
        # 100mm at 10mm/sec should take about 10 seconds (plus acceleration)
        self.assertGreater(time, 8.0)
        self.assertLess(time, 15.0)
    
    def test_homing_timing(self):
        """Test timing calculation for homing"""
        parsed_cmd = ParsedCommand(
            command_type=CommandType.HOMING,
            raw_command="$H"
        )
        
        time = self.calculator.calculate_movement_time(parsed_cmd, self.current_pos)
        
        # Homing should take longer than most moves (4 axes)
        self.assertGreater(time, 20.0)
        self.assertLess(time, 300.0)
    
    def test_trapezoidal_profile_full_acceleration(self):
        """Test trapezoidal profile with full acceleration phase"""
        # Long distance that allows full acceleration
        time = self.calculator._calculate_trapezoidal_profile(
            distance=1000.0,  # 1000mm
            max_velocity=16.67,  # 1000mm/min = 16.67mm/sec
            acceleration=10.0   # 10mm/sec²
        )
        
        # Should have accel + constant + decel phases
        self.assertGreater(time, 60.0)  # At least 60 seconds for 1000mm
    
    def test_trapezoidal_profile_triangular(self):
        """Test trapezoidal profile with triangular motion (no constant velocity)"""
        # Short distance that doesn't allow full acceleration
        time = self.calculator._calculate_trapezoidal_profile(
            distance=10.0,     # 10mm
            max_velocity=16.67, # Won't be reached
            acceleration=10.0
        )
        
        # Should be purely triangular motion
        expected_time = 2 * math.sqrt(10.0 / 10.0)  # 2 * sqrt(distance/accel)
        self.assertAlmostEqual(time, expected_time, places=1)


class TestSafetyMarginProvider(unittest.TestCase):
    
    def setUp(self):
        self.safety = SafetyMarginProvider()
    
    def test_apply_safety_margin_rapid_move(self):
        """Test safety margin for rapid moves"""
        calculated_time = 5.0
        safe_time = self.safety.apply_safety_margin(calculated_time, CommandType.RAPID_MOVE)
        
        # Should apply 1.5x factor for rapid moves
        expected = 5.0 * 1.5
        self.assertAlmostEqual(safe_time, expected, places=1)
    
    def test_apply_safety_margin_homing(self):
        """Test safety margin for homing (highest factor)"""
        calculated_time = 10.0
        safe_time = self.safety.apply_safety_margin(calculated_time, CommandType.HOMING)
        
        # Should apply 3.0x factor for homing
        expected = 10.0 * 3.0
        self.assertAlmostEqual(safe_time, expected, places=1)
    
    def test_minimum_timeout_enforcement(self):
        """Test minimum timeout enforcement"""
        calculated_time = 0.1
        safe_time = self.safety.apply_safety_margin(calculated_time, CommandType.STATUS_QUERY)
        
        # Should enforce minimum timeout
        self.assertGreaterEqual(safe_time, self.safety.minimum_timeout)
    
    def test_maximum_timeout_enforcement(self):
        """Test maximum timeout enforcement"""
        calculated_time = 200.0  # Very long time
        safe_time = self.safety.apply_safety_margin(calculated_time, CommandType.HOMING)
        
        # Should not exceed maximum
        self.assertLessEqual(safe_time, self.safety.maximum_timeout)
    
    def test_fixed_timeouts(self):
        """Test fixed timeouts for specific commands"""
        status_timeout = self.safety.get_fixed_timeout(CommandType.STATUS_QUERY)
        settings_timeout = self.safety.get_fixed_timeout(CommandType.SETTINGS)
        
        self.assertEqual(status_timeout, 2.0)
        self.assertEqual(settings_timeout, 5.0)


class TestTimeoutCalculator(unittest.TestCase):
    
    def setUp(self):
        self.config = GRBLMachineConfig()
        self.calculator = TimeoutCalculator(self.config)
    
    def test_calculate_timeout_status_query(self):
        """Test timeout calculation for status query"""
        timeout = self.calculator.calculate_timeout("?")
        
        # Should return fixed timeout for status query
        self.assertEqual(timeout, 2.0)
    
    def test_calculate_timeout_rapid_move(self):
        """Test timeout calculation for rapid move"""
        timeout = self.calculator.calculate_timeout("G0 X100 Y100", (0, 0, 0, 0))
        
        # Should calculate based on movement
        self.assertGreater(timeout, 5.0)
        self.assertLess(timeout, 60.0)
    
    def test_calculate_timeout_4axis_move(self):
        """Test timeout calculation for 4-axis move"""
        timeout = self.calculator.calculate_timeout("G1 X50 A180 F600", (0, 0, 0, 0))
        
        # Should consider both linear and rotary motion
        self.assertGreater(timeout, 3.0)
        self.assertLess(timeout, 30.0)
    
    def test_calculate_timeout_homing(self):
        """Test timeout calculation for homing"""
        timeout = self.calculator.calculate_timeout("$H")
        
        # Should be longer than typical moves (4-axis homing)
        self.assertGreater(timeout, 60.0)
    
    def test_update_machine_config(self):
        """Test machine configuration update"""
        settings = [
            "$110=1500.000",  # X max rate
            "$111=1500.000",  # Y max rate
            "$113=7200.000",  # A max rate
        ]
        
        old_max_rate_a = self.calculator.config.max_rate_a
        self.calculator.update_machine_config(settings)
        
        # Config should be updated
        self.assertEqual(self.calculator.config.max_rate_x, 1500.0)
        self.assertEqual(self.calculator.config.max_rate_a, 7200.0)
        self.assertNotEqual(self.calculator.config.max_rate_a, old_max_rate_a)
    
    def test_record_execution_time(self):
        """Test execution time recording for adaptive learning"""
        command = "G0 X10"
        predicted = 5.0
        actual = 6.0
        
        self.calculator.record_execution_time(command, predicted, actual)
        
        stats = self.calculator.get_statistics()
        self.assertEqual(stats['total_commands'], 1)
        self.assertAlmostEqual(stats['avg_accuracy'], 1.2, places=1)  # 6/5 = 1.2
    
    def test_adaptive_safety_factor_adjustment(self):
        """Test adaptive adjustment of safety factor"""
        original_factor = self.calculator.safety_provider.base_safety_factor
        
        # Record consistently slow executions (over-predicting)
        for i in range(15):
            self.calculator.record_execution_time(f"G0 X{i}", 5.0, 7.0)  # 40% over prediction
        
        # Safety factor should decrease
        new_factor = self.calculator.safety_provider.base_safety_factor
        self.assertLess(new_factor, original_factor)


class TestTimeoutCalculatorService(unittest.TestCase):
    
    def setUp(self):
        # Mock GRBL controller
        self.mock_grbl = Mock()
        self.mock_grbl.current_position = [0.0, 0.0, 0.0]
        self.mock_grbl.send_command.return_value = ["ok"]
        
        # Create service
        self.service = TimeoutCalculatorService(self.mock_grbl)
    
    def test_send_command_with_calculated_timeout(self):
        """Test send_command uses calculated timeout"""
        self.service.send_command("G0 X10")
        
        # Should call underlying controller with calculated timeout
        self.mock_grbl.send_command.assert_called_once()
        args, kwargs = self.mock_grbl.send_command.call_args
        
        self.assertEqual(args[0], "G0 X10")
        self.assertIsInstance(args[1], float)  # Timeout should be calculated
        self.assertGreater(args[1], 0.0)
    
    def test_send_command_with_custom_timeout(self):
        """Test send_command respects custom timeout"""
        custom_timeout = 15.0
        self.service.send_command("G0 X100", custom_timeout)
        
        # Should use custom timeout
        self.mock_grbl.send_command.assert_called_once_with("G0 X100", custom_timeout)
    
    def test_4axis_position_handling(self):
        """Test proper handling of 4-axis positions"""
        # Test with 3-axis controller
        self.mock_grbl.current_position = [10.0, 20.0, 5.0]
        self.service.send_command("G1 A90")
        
        # Should extend 3-axis to 4-axis internally
        self.mock_grbl.send_command.assert_called_once()
    
    def test_attribute_delegation(self):
        """Test that other attributes are delegated to wrapped controller"""
        # Access current_position through service
        position = self.service.current_position
        
        self.assertEqual(position, [0.0, 0.0, 0.0])
    
    def test_get_timeout_statistics(self):
        """Test timeout statistics retrieval"""
        stats = self.service.get_timeout_statistics()
        
        self.assertIn('total_commands', stats)
        self.assertIsInstance(stats['total_commands'], int)


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete timeout calculation system"""
    
    def test_end_to_end_calculation(self):
        """Test complete workflow from command to timeout (4-axis)"""
        # Create calculator with known 4-axis config
        config = GRBLMachineConfig(
            max_rate_x=1000.0,
            max_rate_a=3600.0,      # Fast rotary
            default_feed_rate=600.0,
            acceleration_x=10.0,
            acceleration_a=360.0,
            has_rotary_a=True
        )
        calculator = TimeoutCalculator(config)
        
        # Test various 4-axis commands
        test_cases = [
            ("?", 2.0),                    # Status query - fixed
            ("$$", 5.0),                   # Settings - fixed  
            ("$H", lambda t: t > 30.0),    # Homing - calculated, long
            ("G0 X10 A90", lambda t: 1.0 < t < 10.0),        # 4-axis rapid move
            ("G1 X100 A180 F300", lambda t: t > 15.0),       # Slow 4-axis move
            ("G1 A360 F1800", lambda t: 5.0 < t < 25.0),     # Rotary-only move
        ]
        
        for command, expected in test_cases:
            timeout = calculator.calculate_timeout(command)
            
            if callable(expected):
                self.assertTrue(expected(timeout), f"Command '{command}' timeout {timeout} failed expectation")
            else:
                self.assertEqual(timeout, expected, f"Command '{command}' timeout mismatch")


if __name__ == '__main__':
    # Run all tests
    unittest.main(verbosity=2)
