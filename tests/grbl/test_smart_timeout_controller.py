import unittest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Mock external dependencies
sys.modules["serial"] = MagicMock()
sys.modules["serial.tools"] = MagicMock()
sys.modules["serial.tools.list_ports"] = MagicMock()

from grbl.controller import GRBLController
from grbl.smart_timeout_controller import SmartTimeoutController
from grbl.timeout import TimeoutCalculator


class TestSmartTimeoutController(unittest.TestCase):
    
    def setUp(self):
        # Create mock base controller
        self.mock_controller = Mock(spec=GRBLController)
        self.mock_controller.current_position = [0.0, 0.0, 0.0]
        self.mock_controller._parser = Mock()
        self.mock_controller._parser.is_ok_response = Mock(return_value=True)
        
        # Create mock timeout calculator
        self.mock_timeout_calc = Mock(spec=TimeoutCalculator)
        self.mock_timeout_calc.calculate_timeout = Mock(return_value=60.0)
        self.mock_timeout_calc.timeout_history = []
        self.mock_timeout_calc.get_statistics = Mock(return_value={"total_commands": 0})
        
        # Create smart controller
        self.smart_controller = SmartTimeoutController(
            self.mock_controller,
            self.mock_timeout_calc
        )
    
    def test_initialization(self):
        controller = SmartTimeoutController(self.mock_controller)
        self.assertIsNotNone(controller._controller)
        self.assertIsNotNone(controller._timeout_calc)
        self.assertFalse(controller._config_initialized)
    
    def test_connect_delegation(self):
        self.mock_controller.connect.return_value = True
        result = self.smart_controller.connect("/dev/ttyUSB0", 115200)
        self.assertTrue(result)
        self.mock_controller.connect.assert_called_once_with("/dev/ttyUSB0", 115200)
    
    def test_disconnect_delegation(self):
        self.smart_controller.disconnect()
        self.mock_controller.disconnect.assert_called_once()
        self.assertFalse(self.smart_controller._config_initialized)
    
    def test_is_connected_delegation(self):
        self.mock_controller.is_connected.return_value = True
        result = self.smart_controller.is_connected()
        self.assertTrue(result)
        self.mock_controller.is_connected.assert_called_once()
    
    def test_get_position_delegation(self):
        expected_pos = [10.5, 20.0, 5.25]
        self.mock_controller.get_position.return_value = expected_pos
        result = self.smart_controller.get_position()
        self.assertEqual(result, expected_pos)
        self.mock_controller.get_position.assert_called_once()
    
    def test_get_status_delegation(self):
        self.mock_controller.get_status.return_value = "Idle"
        result = self.smart_controller.get_status()
        self.assertEqual(result, "Idle")
        self.mock_controller.get_status.assert_called_once()
    
    def test_home_with_calculated_timeout(self):
        self.mock_controller.send_command.return_value = ["ok"]
        self.mock_timeout_calc.calculate_timeout.return_value = 120.0
        
        result = self.smart_controller.home()
        
        self.assertTrue(result)
        self.mock_timeout_calc.calculate_timeout.assert_called_once_with("$H", (0.0, 0.0, 0.0, 0.0))
        self.mock_controller.send_command.assert_called_once_with("$H", 120.0)
    
    def test_move_to_with_calculated_timeout(self):
        self.mock_controller.send_command.return_value = ["ok"]
        self.mock_timeout_calc.calculate_timeout.return_value = 30.0
        
        result = self.smart_controller.move_to(10.0, 20.0, 5.0)
        
        self.assertTrue(result)
        self.mock_timeout_calc.calculate_timeout.assert_called_once()
        call_args = self.mock_timeout_calc.calculate_timeout.call_args[0]
        self.assertIn("G0", call_args[0])
        self.assertIn("10.000", call_args[0])
        self.mock_controller.send_command.assert_called_once()
    
    def test_move_to_with_feed_rate(self):
        self.mock_controller.send_command.return_value = ["ok"]
        self.mock_timeout_calc.calculate_timeout.return_value = 25.0
        
        result = self.smart_controller.move_to(10.0, 20.0, 5.0, feed_rate=800.0)
        
        self.assertTrue(result)
        call_args = self.mock_timeout_calc.calculate_timeout.call_args[0]
        self.assertIn("F800", call_args[0])
    
    def test_jog_relative_with_calculated_timeout(self):
        self.mock_controller.send_command.return_value = ["ok"]
        self.mock_timeout_calc.calculate_timeout.return_value = 15.0
        
        result = self.smart_controller.jog_relative(1.0, -1.0, 0.5, feed_rate=500)
        
        self.assertTrue(result)
        call_args = self.mock_timeout_calc.calculate_timeout.call_args[0]
        self.assertIn("$J=G91", call_args[0])
        self.assertIn("F500", call_args[0])
    
    def test_send_command_with_none_timeout_calculates(self):
        self.mock_controller.send_command.return_value = ["ok"]
        self.mock_timeout_calc.calculate_timeout.return_value = 10.0
        
        result = self.smart_controller.send_command("G0 X10")
        
        self.assertEqual(result, ["ok"])
        self.mock_timeout_calc.calculate_timeout.assert_called_once_with("G0 X10", (0.0, 0.0, 0.0, 0.0))
        self.mock_controller.send_command.assert_called_once_with("G0 X10", 10.0)
    
    def test_send_command_with_explicit_timeout(self):
        self.mock_controller.send_command.return_value = ["ok"]
        
        result = self.smart_controller.send_command("G0 X10", timeout=5.0)
        
        self.assertEqual(result, ["ok"])
        self.mock_timeout_calc.calculate_timeout.assert_not_called()
        self.mock_controller.send_command.assert_called_once_with("G0 X10", 5.0)
    
    def test_send_command_async_with_none_timeout(self):
        mock_future = Mock()
        self.mock_controller.send_command_async.return_value = mock_future
        self.mock_timeout_calc.calculate_timeout.return_value = 8.0
        
        result = self.smart_controller.send_command_async("G1 X5")
        
        self.assertEqual(result, mock_future)
        self.mock_timeout_calc.calculate_timeout.assert_called_once()
        self.mock_controller.send_command_async.assert_called_once_with("G1 X5", 8.0)
    
    def test_send_command_async_with_explicit_timeout(self):
        mock_future = Mock()
        self.mock_controller.send_command_async.return_value = mock_future
        
        result = self.smart_controller.send_command_async("G1 X5", timeout=3.0)
        
        self.assertEqual(result, mock_future)
        self.mock_timeout_calc.calculate_timeout.assert_not_called()
        self.mock_controller.send_command_async.assert_called_once_with("G1 X5", 3.0)
    
    def test_emergency_stop_delegation(self):
        self.mock_controller.emergency_stop.return_value = True
        result = self.smart_controller.emergency_stop()
        self.assertTrue(result)
        self.mock_controller.emergency_stop.assert_called_once()
    
    def test_resume_delegation(self):
        self.mock_controller.resume.return_value = True
        result = self.smart_controller.resume()
        self.assertTrue(result)
        self.mock_controller.resume.assert_called_once()
    
    def test_reset_delegation(self):
        self.mock_controller.reset.return_value = True
        result = self.smart_controller.reset()
        self.assertTrue(result)
        self.mock_controller.reset.assert_called_once()
    
    def test_unlock_delegation(self):
        self.mock_controller.unlock.return_value = True
        result = self.smart_controller.unlock()
        self.assertTrue(result)
        self.mock_controller.unlock.assert_called_once()
    
    def test_send_realtime_command_delegation(self):
        self.smart_controller.send_realtime_command("!")
        self.mock_controller.send_realtime_command.assert_called_once_with("!")
    
    def test_get_current_position_4axis_from_3axis(self):
        self.mock_controller.current_position = [10.0, 20.0, 30.0]
        pos = self.smart_controller._get_current_position_4axis()
        self.assertEqual(pos, (10.0, 20.0, 30.0, 0.0))
    
    def test_get_current_position_4axis_from_4axis(self):
        self.mock_controller.current_position = [10.0, 20.0, 30.0, 90.0]
        pos = self.smart_controller._get_current_position_4axis()
        self.assertEqual(pos, (10.0, 20.0, 30.0, 90.0))
    
    def test_get_current_position_4axis_from_empty(self):
        self.mock_controller.current_position = []
        pos = self.smart_controller._get_current_position_4axis()
        self.assertEqual(pos, (0.0, 0.0, 0.0, 0.0))
    
    def test_execution_time_recording(self):
        self.mock_controller.send_command.return_value = ["ok"]
        self.mock_timeout_calc.calculate_timeout.return_value = 10.0
        
        self.smart_controller.send_command("G0 X10")
        
        self.mock_timeout_calc.record_execution_time.assert_called_once()
        call_args = self.mock_timeout_calc.record_execution_time.call_args[0]
        self.assertEqual(call_args[0], "G0 X10")
        self.assertEqual(call_args[1], 10.0)
        self.assertIsInstance(call_args[2], float)
        self.assertGreater(call_args[2], 0)
    
    def test_get_timeout_statistics(self):
        expected_stats = {
            "total_commands": 5,
            "avg_accuracy": 1.1
        }
        self.mock_timeout_calc.get_statistics.return_value = expected_stats
        
        result = self.smart_controller.get_timeout_statistics()
        
        self.assertEqual(result, expected_stats)
        self.mock_timeout_calc.get_statistics.assert_called_once()
    
    def test_reset_timeout_statistics(self):
        self.smart_controller.reset_timeout_statistics()
        self.assertEqual(len(self.mock_timeout_calc.timeout_history), 0)
    
    def test_attribute_delegation_via_getattr(self):
        self.mock_controller.some_custom_attribute = "test_value"
        result = self.smart_controller.some_custom_attribute
        self.assertEqual(result, "test_value")
    
    def test_auto_config_on_connect(self):
        self.mock_controller.send_command.return_value = [
            "$110=1000.000",
            "$111=1000.000",
            "ok"
        ]
        
        # Simulate connection event
        self.smart_controller._on_connected(True)
        
        self.mock_controller.send_command.assert_called_with("$$", timeout=5.0)
        self.mock_timeout_calc.update_machine_config.assert_called_once()
        self.assertTrue(self.smart_controller._config_initialized)
    
    def test_auto_config_skip_if_already_initialized(self):
        self.smart_controller._config_initialized = True
        
        self.smart_controller._on_connected(True)
        
        self.mock_controller.send_command.assert_not_called()
    
    def test_auto_config_skip_on_failed_connection(self):
        self.smart_controller._on_connected(False)
        self.mock_controller.send_command.assert_not_called()


class TestSmartTimeoutControllerIntegration(unittest.TestCase):
    
    def test_interfaces_implemented(self):
        from grbl.interfaces import IGRBLConnection, IGRBLStatus, IGRBLMovement, IGRBLCommunication
        
        mock_controller = Mock(spec=GRBLController)
        mock_controller.current_position = [0.0, 0.0, 0.0]
        
        smart_controller = SmartTimeoutController(mock_controller)
        
        self.assertIsInstance(smart_controller, IGRBLConnection)
        self.assertIsInstance(smart_controller, IGRBLStatus)
        self.assertIsInstance(smart_controller, IGRBLMovement)
        self.assertIsInstance(smart_controller, IGRBLCommunication)


if __name__ == "__main__":
    unittest.main(verbosity=2)
