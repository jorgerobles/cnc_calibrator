import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..','..')))

# Mock external dependencies
sys.modules['serial'] = MagicMock()

from grbl.parser import GRBLResponseParser
# from grbl.serial import SerialConnection  # Skip this import to avoid serial dependency
# from grbl.controller import GRBLController  # Skip this import to avoid serial dependency


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


# Skipping SerialConnection and GRBLController tests since they require serial dependency
# These would need to be run in a proper virtual environment with pyserial installed

class TestGRBLComponentsIntegration(unittest.TestCase):
    """Tests that can run without serial dependency"""
    
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
    print("Note: Some tests are skipped due to missing serial dependency.")
    print("Run with proper virtual environment for full test coverage.")
    # Run tests
    unittest.main(verbosity=2)
