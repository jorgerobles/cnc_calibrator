"""
Unit tests for refactored GRBL components
Save as: tmp/test_grbl_components.py
"""
import unittest
from unittest.mock import Mock, patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.grbl_parser import GRBLResponseParser
from src.grbl_serial import SerialConnection
from src.grbl_controller import GRBLController


class TestGRBLResponseParser(unittest.TestCase):
    
    def setUp(self):
        self.parser = GRBLResponseParser()
    
    def test_parse_valid_status_response(self):
        """Test parsing valid status response"""
        response = "<Idle|MPos:0.000,0.000,0.000|WPos:0.000,0.000,0.000>"
        result = self.parser.parse_status_response(response)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['state'], 'Idle')
        self.assertEqual(result['machine_position'], [0.0, 0.0, 0.0])
        self.assertEqual(result['work_position'], [0.0, 0.0, 0.0])
    
    def test_parse_status_with_coordinates(self):
        """Test parsing status with actual coordinates"""
        response = "<Run|MPos:10.500,-25.000,5.250|WPos:8.500,-23.000,3.250>"
        result = self.parser.parse_status_response(response)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['state'], 'Run')
        self.assertEqual(result['machine_position'], [10.5, -25.0, 5.25])
        self.assertEqual(result['work_position'], [8.5, -23.0, 3.25])
    
    def test_is_ok_response(self):
        """Test OK response detection"""
        self.assertTrue(self.parser.is_ok_response("ok"))
        self.assertTrue(self.parser.is_ok_response("OK"))
        self.assertFalse(self.parser.is_error_response("ok"))
    
    def test_is_error_response(self):
        """Test error response detection"""
        self.assertTrue(self.parser.is_error_response("error:1"))
        self.assertEqual(self.parser.extract_error_code("error:25"), "25")


class TestSerialConnection(unittest.TestCase):
    
    def setUp(self):
        self.serial_conn = SerialConnection()
    
    @patch('src.grbl_serial.serial.Serial')
    def test_open_success(self, mock_serial):
        """Test successful serial connection"""
        mock_instance = Mock()
        mock_instance.is_open = True
        mock_serial.return_value = mock_instance
        
        result = self.serial_conn.open("/dev/ttyUSB0", 115200)
        self.assertTrue(result)
        mock_serial.assert_called_once()
    
    @patch('src.grbl_serial.serial.Serial')
    def test_open_failure(self, mock_serial):
        """Test failed serial connection"""
        mock_serial.side_effect = Exception("Port not found")
        
        result = self.serial_conn.open("/dev/invalid", 115200)
        self.assertFalse(result)
    
    def test_is_open_when_closed(self):
        """Test is_open when no connection"""
        self.assertFalse(self.serial_conn.is_open())


class TestGRBLController(unittest.TestCase):
    
    def setUp(self):
        # Create mocked dependencies
        self.mock_serial = Mock(spec=SerialConnection)
        self.mock_parser = Mock(spec=GRBLResponseParser)
        
        # Create controller with mocked dependencies
        self.controller = GRBLController(self.mock_serial, self.mock_parser)
    
    def test_connect_success(self):
        """Test successful connection"""
        self.mock_serial.open.return_value = True
        self.mock_serial.is_open.return_value = True
        
        # Mock communicator to return successful response
        with patch.object(self.controller._communicator, 'send_command_sync') as mock_send:
            mock_send.return_value = ["<Idle|MPos:0.000,0.000,0.000|WPos:0.000,0.000,0.000>", "ok"]
            
            result = self.controller.connect("/dev/ttyUSB0", 115200)
            self.assertTrue(result)
            self.assertTrue(self.controller.is_connected())
    
    def test_connect_failure(self):
        """Test connection failure"""
        self.mock_serial.open.return_value = False
        
        result = self.controller.connect("/dev/invalid", 115200)
        self.assertFalse(result)
        self.assertFalse(self.controller.is_connected())
    
    def test_disconnect(self):
        """Test disconnection"""
        # Setup connected state
        self.controller._is_connected = True
        
        self.controller.disconnect()
        self.assertFalse(self.controller.is_connected())
    
    def test_get_position_not_connected(self):
        """Test get_position when not connected"""
        with self.assertRaises(Exception) as context:
            self.controller.get_position()
        self.assertIn("not connected", str(context.exception))
    
    def test_emergency_stop(self):
        """Test emergency stop"""
        self.controller._is_connected = True
        self.mock_serial.is_open.return_value = True
        
        with patch.object(self.controller._communicator, 'send_realtime_command') as mock_send:
            result = self.controller.emergency_stop()
            self.assertTrue(result)
            mock_send.assert_called_once_with("!")
    
    def test_home_command(self):
        """Test homing command"""
        self.controller._is_connected = True
        self.mock_parser.is_ok_response.return_value = True
        
        with patch.object(self.controller._communicator, 'send_command_sync') as mock_send:
            mock_send.return_value = ["ok"]
            
            result = self.controller.home()
            self.assertTrue(result)
            mock_send.assert_called_once_with("$H", timeout=30.0)


class TestGRBLControllerStandalone(unittest.TestCase):
    """Test GRBLController can be instantiated standalone"""
    
    def test_standalone_instantiation(self):
        """Test controller can be created without dependencies"""
        controller = GRBLController()
        
        # Should have default instances
        self.assertIsNotNone(controller._serial)
        self.assertIsNotNone(controller._parser)
        self.assertIsNotNone(controller._communicator)
        
        # Should be in disconnected state
        self.assertFalse(controller.is_connected())
        self.assertEqual(controller.current_position, [0.0, 0.0, 0.0])
        self.assertEqual(controller.current_status, "Unknown")


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
