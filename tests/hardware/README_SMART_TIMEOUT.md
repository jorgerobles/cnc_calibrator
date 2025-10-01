# SmartTimeoutController - Hardware Testing Guide

## Overview

This guide explains how to run hardware tests for the SmartTimeoutController with a real GRBL machine.

## Safety First ⚠️

**IMPORTANT**: These tests control real CNC hardware. Before running:

1. ✅ Ensure machine is properly configured and homed
2. ✅ Clear the work area of any obstacles
3. ✅ Verify all axes can move freely
4. ✅ Have emergency stop accessible
5. ✅ Understand the test movements before running

## Prerequisites

### Hardware Requirements
- GRBL controller (ESP32 or similar)
- Machine with homing configured (recommended)
- USB/Serial connection to computer
- Machine should be in a known safe state

### Software Requirements
- Python 3.7+
- Serial port access
- All project dependencies installed

## Configuration

Edit \`tests/hardware/test_config.py\` to match your machine:

\`\`\`python
port = "/dev/ttyUSB0"  # Your serial port
baudrate = 115200

# Safety limits
max_test_distance = 10.0  # Maximum movement per test (mm)
max_feed_rate = 1000.0    # Maximum feed rate (mm/min)

# Workspace bounds (adjust to your machine)
min_x = -10.0
max_x = 10.0
min_y = -10.0  
max_y = 10.0
min_z = 40.0
max_z = 60.0
\`\`\`

## Running the Tests

### Option 1: Interactive Runner (Recommended)

\`\`\`bash
cd tests/hardware
python3 run_smart_timeout_tests.py
\`\`\`

This will:
1. Check hardware connection
2. Ask for confirmation
3. Run all tests sequentially
4. Display detailed results

### Option 2: Direct Execution

\`\`\`bash
cd tests/hardware
python3 test_smart_timeout_hardware.py
\`\`\`

### Option 3: Run Specific Test

\`\`\`bash
cd tests/hardware
python3 test_smart_timeout_hardware.py TestSmartTimeoutHardware.test_01_homing_with_smart_timeout
\`\`\`

## What the Tests Do

### Test 1: Homing with Smart Timeout
- **Purpose**: Verify homing works with calculated timeout
- **Action**: Performs full homing cycle (\$H command)
- **Validates**:
  - Timeout calculation is reasonable (>30s)
  - Homing completes successfully
  - Machine reaches home position
  - Timeout has appropriate safety margin

### Test 2: Movement with Smart Timeout
- **Purpose**: Test linear movement with calculated timeout
- **Action**: Moves 5mm in X axis and returns
- **Validates**:
  - Timeout calculation for moves
  - Movement completes within timeout
  - Position accuracy

### Test 3: Jog with Smart Timeout
- **Purpose**: Test jog commands with smart timeout
- **Action**: Jogs 2mm in X axis and returns
- **Validates**:
  - Jog timeout calculation
  - Jog accuracy
  - Return to original position

### Test 4: Timeout Statistics
- **Purpose**: Verify timeout learning is working
- **Action**: Reads statistics from previous tests
- **Validates**:
  - Commands are being recorded
  - Execution times tracked
  - Accuracy metrics available

## Expected Output

Successful test output looks like:

\`\`\`
18:30:45.123 ✅ Connected with SmartTimeoutController on /dev/ttyUSB0
18:30:45.456 ✅ Machine configuration auto-loaded
18:30:45.789 📊 Machine Config: X=1000 Y=1000 Z=500 mm/min

============================================================
TEST: Homing with Smart Timeout
============================================================
18:30:46.012 Initial status: Idle
18:30:46.034 📊 Calculated timeout for homing: 87.5s
18:30:46.035 ✅ Timeout calculation correct (>30.0s)
18:30:46.036 🏠 Starting homing cycle...
18:31:03.456 ✅ Homing completed successfully in 17.42s
18:31:03.457 📊 Timeout efficiency: 19.9% (actual/calculated)
18:31:04.567 📍 Homed position: [0.0, 0.0, 0.0]
18:31:04.568 📊 Final status: Idle
18:31:04.569 ✅ Homing test completed successfully
.
============================================================
TEST: Movement with Smart Timeout
============================================================
...
\`\`\`

## Troubleshooting

### Test Fails: "Hardware not available"
- Check serial port path in \`test_config.py\`
- Verify USB cable is connected
- Check port permissions: \`sudo usermod -a -G dialout $USER\`

### Test Fails: "Homing timeout"
- Old problem! This should NOT happen with SmartTimeoutController
- If it does: Check machine configuration was loaded
- Verify machine homing speed settings (\$24, \$25)

### Test Fails: "Could not clear Alarm state"
- Manually reset machine
- Check limit switches
- May need to unlock with \$X command manually

### Test Fails: "Movement outside safe bounds"
- Adjust bounds in \`test_config.py\`
- Ensure machine is homed before tests
- Check current position is within test workspace

## Comparing Results

### Before SmartTimeoutController (Hardcoded 30s)
\`\`\`
❌ Homing TIMEOUT after 30.0s
   Machine homing took ~40s but timeout was only 30s
\`\`\`

### After SmartTimeoutController (Calculated ~88s)
\`\`\`
✅ Homing completed successfully in 17.42s
   Calculated timeout: 87.5s
   Actual time: 17.42s
   Efficiency: 19.9%
\`\`\`

## Benefits Demonstrated

1. ✅ **No More Timeout Failures**: Timeouts calculated based on machine config
2. ✅ **Adaptive Learning**: System learns from actual execution times
3. ✅ **Safe Margins**: Timeouts have appropriate safety buffer
4. ✅ **Transparent**: Same API as regular GRBLController

## Next Steps

After successful hardware tests:
1. Review timeout statistics
2. Adjust safety margins if needed
3. Use SmartTimeoutController in production code
4. Monitor timeout efficiency over time

## Support

If tests fail or you have questions:
1. Check machine configuration
2. Review test output logs
3. Verify hardware safety limits
4. Check GRBL settings match test expectations
