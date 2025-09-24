import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..')))

# Mock external dependencies BEFORE importing
sys.modules['serial'] = MagicMock()
sys.modules['serial.tools'] = MagicMock()
sys.modules['serial.tools.list_ports'] = MagicMock()

from grbl.parser import GRBLResponseParser
from grbl.serial import SerialConnection
from grbl.controller import GRBLController


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
    
    @patch('grbl.serial.serial.Serial')
    def test_open_success(self, mock_serial_class):
        """Test successful serial connection"""
        mock_instance = Mock()
        mock_instance.is_open = True
        mock_serial_class.return_value = mock_instance
        
        result = self.serial_conn.open("/dev/ttyUSB0", 115200)
        self.assertTrue(result)
        mock_serial_class.assert_called_once()
        
        # Verify connection parameters
        call_kwargs = mock_serial_class.call_args[1]
        self.assertEqual(call_kwargs['port'], "/dev/ttyUSB0")
        self.assertEqual(call_kwargs['baudrate'], 115200)
    
    @patch('grbl.serial.serial.Serial')
    def test_open_failure(self, mock_serial_class):
        """Test failed serial connection"""
        mock_serial_class.side_effect = Exception("Port not found")
        
        result = self.serial_conn.open("/dev/invalid", 115200)
        self.assertFalse(result)
    
    def test_is_open_when_closed(self):
        """Test is_open when no connection"""
        self.assertFalse(self.serial_conn.is_open())
    
    @patch('grbl.serial.serial.Serial')
    def test_write_data(self, mock_serial_class):
        """Test writing data to serial port"""
        mock_instance = Mock()
        mock_instance.is_open = True
        mock_instance.write.return_value = 5
        mock_serial_class.return_value = mock_instance
        
        # Open connection first
        self.serial_conn.open("/dev/test", 115200)
        
        # Test write
        bytes_written = self.serial_conn.write(b"test\n")
        self.assertEqual(bytes_written, 5)
        mock_instance.write.assert_called_once_with(b"test\n")
    
    @patch('grbl.serial.serial.Serial')
    def test_read_line(self, mock_serial_class):
        """Test reading line from serial port"""
        mock_instance = Mock()
        mock_instance.is_open = True
        mock_instance.readline.return_value = b"ok\r\n"
        mock_serial_class.return_value = mock_instance
        
        # Open connection first
        self.serial_conn.open("/dev/test", 115200)
        
        # Test read
        line = self.serial_conn.read_line()
        self.assertEqual(line, "ok")
        mock_instance.readline.assert_called_once()
    
    @patch('grbl.serial.serial.Serial')
    def test_close_connection(self, mock_serial_class):
        """Test closing serial connection"""
        mock_instance = Mock()
        mock_instance.is_open = True
        mock_serial_class.return_value = mock_instance
        
        # Open and close
        self.serial_conn.open("/dev/test", 115200)
        self.serial_conn.close()
        
        mock_instance.close.assert_called_once()
    
    @patch('grbl.serial.serial.Serial')
    def test_reset_input_buffer(self, mock_serial_class):
        """Test reset_input_buffer"""
        mock_instance = Mock()
        mock_instance.is_open = True
        mock_serial_class.return_value = mock_instance
        
        # Open connection first
        self.serial_conn.open("/dev/test", 115200)
        
        # Test reset buffer
        self.serial_conn.reset_input_buffer()
        mock_instance.reset_input_buffer.assert_called_once()
    
    @patch('grbl.serial.serial.Serial')
    def test_in_waiting(self, mock_serial_class):
        """Test in_waiting property"""
        mock_instance = Mock()
        mock_instance.is_open = True
        mock_instance.in_waiting = 10
        mock_serial_class.return_value = mock_instance
        
        # Open connection first
        self.serial_conn.open("/dev/test", 115200)
        
        # Test in_waiting
        waiting = self.serial_conn.in_waiting()
        self.assertEqual(waiting, 10)


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
    
    def test_move_to_command(self):
        """Test move_to command"""
        self.controller._is_connected = True
        self.mock_serial.is_open.return_value = True
        
        with patch.object(self.controller._communicator, 'send_command_sync') as mock_send:
            mock_send.return_value = ["ok"]
            
            result = self.controller.move_to(x=10.0, y=20.0, z=5.0)
            self.assertTrue(result)
            mock_send.assert_called_once()
    
    def test_jog_relative_command(self):
        """Test jog_relative command"""
        self.controller._is_connected = True
        self.mock_serial.is_open.return_value = True
        
        with patch.object(self.controller._communicator, 'send_command_sync') as mock_send:
            mock_send.return_value = ["ok"]
            
            result = self.controller.jog_relative(x=1.0, y=-1.0, z=0.5)
            self.assertTrue(result)
            # Should call send_command_sync once (jog command in G91 relative mode)
            self.assertEqual(mock_send.call_count, 1)
    
    def test_send_command(self):
        """Test send_command"""
        self.controller._is_connected = True
        
        with patch.object(self.controller._communicator, 'send_command_sync') as mock_send:
            mock_send.return_value = ["ok"]
            
            result = self.controller.send_command("G0 X10")
            self.assertEqual(result, ["ok"])
            mock_send.assert_called_once_with("G0 X10", 5.0)
    
    def test_send_command_async(self):
        """Test send_command_async"""
        self.controller._is_connected = True
        
        with patch.object(self.controller._communicator, 'send_command_async') as mock_send_async:
            mock_future = Mock()
            mock_send_async.return_value = mock_future
            
            result = self.controller.send_command_async("G0 X10")
            self.assertEqual(result, mock_future)
            mock_send_async.assert_called_once_with("G0 X10", 5.0)
    
    def test_send_realtime_command(self):
        """Test send_realtime_command"""
        self.controller._is_connected = True
        
        with patch.object(self.controller._communicator, 'send_realtime_command') as mock_send:
            self.controller.send_realtime_command("!")
            mock_send.assert_called_once_with("!")
    
    def test_get_status_connected(self):
        """Test get_status when connected"""
        self.controller._is_connected = True
        self.controller.current_status = "Idle"
        
        with patch.object(self.controller._communicator, 'send_command_sync') as mock_send:
            mock_send.return_value = ["<Idle|MPos:0.000,0.000,0.000|WPos:0.000,0.000,0.000>"]
            
            status = self.controller.get_status()
            self.assertEqual(status, "Idle")
    
    def test_resume_command(self):
        """Test resume command"""
        self.controller._is_connected = True
        
        with patch.object(self.controller._communicator, 'send_realtime_command') as mock_send:
            result = self.controller.resume()
            self.assertTrue(result)
            mock_send.assert_called_once_with("~")
    
    def test_reset_command(self):
        """Test reset command"""
        self.controller._is_connected = True
        
        with patch.object(self.controller._communicator, 'send_realtime_command') as mock_send:
            result = self.controller.reset()
            self.assertTrue(result)
            mock_send.assert_called_once_with("\x18")


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
    
    def test_interface_compliance(self):
        """Test that controller implements all required interfaces"""
        controller = GRBLController()
        
        # IGRBLConnection interface
        self.assertTrue(hasattr(controller, 'connect'))
        self.assertTrue(hasattr(controller, 'disconnect'))
        self.assertTrue(hasattr(controller, 'is_connected'))
        
        # IGRBLStatus interface
        self.assertTrue(hasattr(controller, 'get_position'))
        self.assertTrue(hasattr(controller, 'get_status'))
        
        # IGRBLMovement interface
        self.assertTrue(hasattr(controller, 'home'))
        self.assertTrue(hasattr(controller, 'move_to'))
        self.assertTrue(hasattr(controller, 'jog_relative'))
        self.assertTrue(hasattr(controller, 'emergency_stop'))
        self.assertTrue(hasattr(controller, 'resume'))
        self.assertTrue(hasattr(controller, 'reset'))
        
        # IGRBLCommunication interface
        self.assertTrue(hasattr(controller, 'send_command'))
        self.assertTrue(hasattr(controller, 'send_command_async'))
        self.assertTrue(hasattr(controller, 'send_realtime_command'))
    
    def test_operations_when_disconnected(self):
        """Test behavior when operations are attempted while disconnected"""
        controller = GRBLController()
        
        # Should raise exceptions for operations requiring connection
        with self.assertRaises(Exception):
            controller.get_position()
        
        with self.assertRaises(Exception):
            controller.send_command("G0 X10")
        
        with self.assertRaises(Exception):
            controller.send_command_async("G1 X5")
        
        with self.assertRaises(Exception):
            controller.send_realtime_command("!")


class TestGRBLComponentsIntegration(unittest.TestCase):
    """Integration tests for GRBL components"""
    
    def test_parser_standalone(self):
        """Test that parser works standalone"""
        parser = GRBLResponseParser()
        self.assertIsNotNone(parser)
        
        # Test various response formats
        test_responses = [
            ("<Idle|MPos:0,0,0|WPos:0,0,0>", "Idle", [0.0, 0.0, 0.0]),
            ("<Run|MPos:10.5,-20.0,5.25|WPos:8.5,-18.0,3.25>", "Run", [10.5, -20.0, 5.25]),
            ("<Hold|MPos:100,200,300|WPos:90,190,290>", "Hold", [100.0, 200.0, 300.0]),
        ]
        
        for response, expected_state, expected_pos in test_responses:
            result = parser.parse_status_response(response)
            self.assertIsNotNone(result)
            self.assertEqual(result['state'], expected_state)
            self.assertEqual(result['machine_position'], expected_pos)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
