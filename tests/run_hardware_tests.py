#!/usr/bin/env python3
"""
Hardware Test Runner
Safely execute hardware tests with proper setup and safety checks
"""
import os
import sys
import serial.tools.list_ports
import unittest
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from tests.hardware.test_config import get_hardware_config, is_hardware_available


def list_available_ports():
    """List all available serial ports"""
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("❌ No serial ports found")
        return []
    
    print("📡 Available serial ports:")
    for i, port in enumerate(ports, 1):
        print(f"  {i}. {port.device} - {port.description}")
    
    return ports


def configure_test_environment():
    """Interactive configuration of test environment"""
    config = get_hardware_config()
    
    print("🔧 CNC Hardware Test Configuration")
    print("=" * 50)
    
    # Show current config
    print(f"Current port: {config.port}")
    print(f"Baudrate: {config.baudrate}")
    print(f"Max test distance: {config.max_test_distance}mm")
    print(f"Skip destructive tests: {config.skip_destructive_tests}")
    
    # List available ports
    ports = list_available_ports()
    
    # Allow user to select port
    if ports:
        try:
            choice = input(f"\nSelect port number (1-{len(ports)}) or press Enter for default [{config.port}]: ")
            if choice.strip():
                port_index = int(choice) - 1
                config.port = ports[port_index].device
                print(f"Selected port: {config.port}")
        except (ValueError, IndexError):
            print("Invalid choice, using default port")
    
    # Set environment variables for test run
    os.environ["CNC_TEST_PORT"] = config.port
    os.environ["CNC_TEST_BAUDRATE"] = str(config.baudrate)
    
    return config


def run_safety_checklist():
    """Run through safety checklist before testing"""
    print("\n⚠️  HARDWARE SAFETY CHECKLIST ⚠️")
    print("=" * 50)
    
    checklist = [
        "Machine is properly powered and initialized",
        "Work area is clear of obstructions", 
        "Emergency stop button is accessible",
        "Machine limits/homing are properly configured",
        "No cutting tools or workpieces are installed",
        "You have verified the communication port is correct",
        "You understand tests will move the machine"
    ]
    
    for item in checklist:
        response = input(f"✓ {item}? (y/n): ")
        if response.lower() not in ['y', 'yes']:
            print("❌ Safety checklist failed. Aborting tests.")
            return False
    
    print("✅ Safety checklist passed")
    return True


def run_hardware_tests():
    """Run hardware tests with safety measures"""
    
    print("🤖 CNC Hardware Test Runner")
    print("=" * 50)
    
    # Configure test environment
    config = configure_test_environment()
    
    # Check hardware availability
    if not is_hardware_available():
        print(f"❌ Hardware not available on port {config.port}")
        print("Check connection and port configuration")
        return False
    
    print(f"✅ Hardware detected on {config.port}")
    
    # Run safety checklist
    if not run_safety_checklist():
        return False
    
    # Final confirmation
    response = input(f"\n🚀 Ready to run hardware tests on {config.port}? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Test execution cancelled by user")
        return False
    
    print("\n🧪 Starting Hardware Tests...")
    print("=" * 50)
    
    # Run tests
    try:
        # Load test suite
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        
        # Add connection tests
        from tests.hardware.test_hardware_connection import TestHardwareConnection
        suite.addTests(loader.loadTestsFromTestCase(TestHardwareConnection))
        
        # Add movement tests
        from tests.hardware.test_hardware_movement import TestHardwareMovement
        suite.addTests(loader.loadTestsFromTestCase(TestHardwareMovement))
        
        # Run tests with verbose output
        runner = unittest.TextTestRunner(verbosity=2, buffer=False)
        result = runner.run(suite)
        
        # Summary
        print("\n" + "=" * 50)
        if result.wasSuccessful():
            print("✅ All hardware tests passed!")
        else:
            print(f"❌ {len(result.failures)} failures, {len(result.errors)} errors")
            
        return result.wasSuccessful()
        
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        return False
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        return False


if __name__ == "__main__":
    success = run_hardware_tests()
    sys.exit(0 if success else 1)
