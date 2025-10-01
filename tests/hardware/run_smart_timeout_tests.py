#!/usr/bin/env python3
"""
Run Smart Timeout Hardware Tests
Helper script to run hardware tests for SmartTimeoutController
"""
import sys
import os
import subprocess

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

def main():
    print("="*70)
    print("Smart Timeout Controller - Hardware Test Runner")
    print("="*70)
    print()
    print("This will run hardware tests with a real GRBL machine.")
    print("Make sure your CNC is connected and safe to operate.")
    print()
    
    # Check if we should run tests
    response = input("Run hardware tests? (yes/no): ")
    if response.lower() != "yes":
        print("Tests cancelled.")
        return
    
    print()
    print("Starting hardware tests...")
    print("="*70)
    print()
    
    # Run the tests
    test_file = os.path.join(
        os.path.dirname(__file__),
        "test_smart_timeout_hardware.py"
    )
    
    result = subprocess.run(
        [sys.executable, test_file],
        cwd=os.path.dirname(test_file)
    )
    
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
