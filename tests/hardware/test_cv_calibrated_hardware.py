#!/usr/bin/env python3
# tmp/test_cv_calibrated_hardware.py
# Hardware tests for CalibratedCameraManager with real calibration file
import unittest
import sys
import os
import time
import cv2
import numpy as np

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cv import CalibratedCameraManager, CameraEvents


class TestCalibratedCameraManagerHardware(unittest.TestCase):
    """Hardware tests for CalibratedCameraManager - requires physical camera"""
    
    CALIBRATION_FILE = "data/calibration/endo.npz"
    
    @classmethod
    def setUpClass(cls):
        """Check if camera and calibration file are available"""
        print("\\n" + "="*60)
        print("HARDWARE TEST - CalibratedCameraManager")
        print("="*60)
        
        # Check camera
        cap = cv2.VideoCapture(0)
        cls.camera_available = cap.isOpened()
        if cls.camera_available:
            ret, _ = cap.read()
            cls.camera_available = ret
        cap.release()
        
        if not cls.camera_available:
            raise unittest.SkipTest("No camera detected - skipping hardware tests")
        
        print("✓ Camera detected")
        
        # Check calibration file
        if not os.path.exists(cls.CALIBRATION_FILE):
            raise unittest.SkipTest(f"Calibration file not found: {cls.CALIBRATION_FILE}")
        
        print(f"✓ Calibration file found: {cls.CALIBRATION_FILE}")
        
        # Verify calibration file format
        try:
            data = np.load(cls.CALIBRATION_FILE)
            if "camera_matrix" not in data or "dist_coeffs" not in data:
                raise unittest.SkipTest("Invalid calibration file format")
            print(f"✓ Calibration file format valid")
            print(f"  - Camera matrix shape: {data['camera_matrix'].shape}")
            print(f"  - Distortion coeffs shape: {data['dist_coeffs'].shape}")
        except Exception as e:
            raise unittest.SkipTest(f"Error reading calibration file: {e}")
        
        print()
    
    def setUp(self):
        """Create calibrated camera manager for each test"""
        self.manager = CalibratedCameraManager(camera_id=0, resolution=(640, 480))
        self.events_received = []
    
    def tearDown(self):
        """Clean up after each test"""
        if self.manager.is_connected:
            self.manager.disconnect()
        time.sleep(0.1)
    
    def test_load_real_calibration(self):
        """Test loading real calibration file"""
        print("Testing real calibration file loading...")
        
        # Load calibration
        success = self.manager.load_calibration(self.CALIBRATION_FILE)
        self.assertTrue(success, "Loading calibration should succeed")
        self.assertTrue(self.manager.is_calibrated(), "Should be calibrated")
        
        # Verify data loaded
        matrix, dist = self.manager.get_calibration()
        self.assertIsNotNone(matrix, "Camera matrix should be loaded")
        self.assertIsNotNone(dist, "Distortion coeffs should be loaded")
        
        # Verify matrix is 3x3
        self.assertEqual(matrix.shape, (3, 3), "Camera matrix should be 3x3")
        
        print(f"  ✓ Calibration loaded successfully")
        print(f"    Camera matrix:\\n{matrix}")
        print(f"    Distortion coeffs: {dist.flatten()}")
    
    def test_calibrated_connection_lifecycle(self):
        """Test connection with calibration loaded"""
        print("Testing connection lifecycle with calibration...")
        
        # Load calibration first
        self.manager.load_calibration(self.CALIBRATION_FILE)
        self.assertTrue(self.manager.is_calibrated())
        print("  ✓ Calibration loaded")
        
        # Connect
        success = self.manager.connect()
        self.assertTrue(success, "Connection should succeed")
        self.assertTrue(self.manager.is_connected)
        print("  ✓ Camera connected")
        
        # Verify calibration persists after connection
        self.assertTrue(self.manager.is_calibrated(), "Calibration should persist")
        
        # Capture frame
        frame = self.manager.capture_frame()
        self.assertIsNotNone(frame, "Should capture frame")
        print(f"  ✓ Frame captured: {frame.shape}")
        
        # Disconnect
        self.manager.disconnect()
        self.assertFalse(self.manager.is_connected)
        
        # Verify calibration persists after disconnection
        self.assertTrue(self.manager.is_calibrated(), "Calibration should persist after disconnect")
        print("  ✓ Calibration persists through connection lifecycle")
    
    def test_get_camera_info_with_calibration(self):
        """Test camera info includes calibration status"""
        print("Testing camera info with calibration...")
        
        # Get info without calibration
        info = self.manager.get_camera_info()
        print(f"  Info without calibration: {info}")
        
        # Load calibration
        self.manager.load_calibration(self.CALIBRATION_FILE)
        
        # Get calibration info
        calib_info = self.manager.get_calibration_info()
        self.assertTrue(calib_info['calibrated'])
        self.assertEqual(calib_info['file'], self.CALIBRATION_FILE)
        print(f"  ✓ Calibration info: {calib_info}")
    
    def test_calibration_events_with_hardware(self):
        """Test calibration events are emitted correctly"""
        print("Testing calibration events...")
        
        events = []
        
        def on_loaded(file_path):
            events.append(('loaded', file_path))
            print(f"    Event: CALIBRATION_LOADED - {file_path}")
        
        def on_connected(success):
            events.append(('connected', success))
            print(f"    Event: CONNECTED - {success}")
        
        def on_frame(frame):
            events.append(('frame', frame is not None))
        
        # Listen to events
        self.manager.listen(CameraEvents.CALIBRATION_LOADED, on_loaded)
        self.manager.listen(CameraEvents.CONNECTED, on_connected)
        self.manager.listen(CameraEvents.FRAME_CAPTURED, on_frame)
        
        # Load calibration
        self.manager.load_calibration(self.CALIBRATION_FILE)
        time.sleep(0.05)
        
        # Connect
        self.manager.connect()
        time.sleep(0.05)
        
        # Capture
        self.manager.capture_frame()
        time.sleep(0.05)
        
        # Verify events
        event_types = [e[0] for e in events]
        self.assertIn('loaded', event_types, "Should emit CALIBRATION_LOADED")
        self.assertIn('connected', event_types, "Should emit CONNECTED")
        self.assertIn('frame', event_types, "Should emit FRAME_CAPTURED")
        
        print(f"  ✓ Received {len(events)} events: {event_types}")
        
        self.manager.disconnect()
    
    def test_capture_multiple_frames_calibrated(self):
        """Test capturing multiple frames with calibration loaded"""
        print("Testing multiple frame captures with calibration...")
        
        # Load calibration
        self.manager.load_calibration(self.CALIBRATION_FILE)
        self.manager.connect()
        
        frame_count = 20
        successful_captures = 0
        frame_sizes = []
        
        for i in range(frame_count):
            frame = self.manager.capture_frame()
            if frame is not None:
                successful_captures += 1
                frame_sizes.append(frame.shape)
        
        success_rate = (successful_captures / frame_count) * 100
        self.assertGreater(success_rate, 90, f"Success rate {success_rate}% should be > 90%")
        
        # Verify all frames have same size
        if frame_sizes:
            first_size = frame_sizes[0]
            all_same = all(size == first_size for size in frame_sizes)
            self.assertTrue(all_same, "All frames should have same size")
        
        print(f"  ✓ Captured {successful_captures}/{frame_count} frames ({success_rate:.1f}%)")
        print(f"  ✓ Frame size: {frame_sizes[0] if frame_sizes else 'N/A'}")
        
        self.manager.disconnect()
    
    def test_reconnection_with_calibration(self):
        """Test reconnection while maintaining calibration"""
        print("Testing reconnection with calibration...")
        
        # Load calibration
        self.manager.load_calibration(self.CALIBRATION_FILE)
        print("  ✓ Calibration loaded")
        
        # First connection
        self.manager.connect()
        frame1 = self.manager.capture_frame()
        self.assertIsNotNone(frame1)
        print("  ✓ First connection and capture successful")
        
        # Disconnect
        self.manager.disconnect()
        time.sleep(0.2)
        
        # Verify calibration still loaded
        self.assertTrue(self.manager.is_calibrated(), 
                       "Calibration should persist after disconnect")
        print("  ✓ Calibration persisted through disconnect")
        
        # Reconnect
        success = self.manager.connect()
        self.assertTrue(success, "Reconnection should succeed")
        
        # Verify calibration still loaded
        self.assertTrue(self.manager.is_calibrated(), 
                       "Calibration should persist after reconnect")
        
        # Capture again
        frame2 = self.manager.capture_frame()
        self.assertIsNotNone(frame2)
        print("  ✓ Reconnection successful with calibration maintained")
        
        self.manager.disconnect()
    
    def test_calibration_matrix_values(self):
        """Test calibration matrix has reasonable values"""
        print("Testing calibration matrix values...")
        
        self.manager.load_calibration(self.CALIBRATION_FILE)
        matrix, dist = self.manager.get_calibration()
        
        # Check matrix properties
        # Diagonal should be positive (focal lengths and principal point)
        self.assertGreater(matrix[0, 0], 0, "fx should be positive")
        self.assertGreater(matrix[1, 1], 0, "fy should be positive")
        
        # Bottom-right should be 1 (homogeneous coordinates)
        self.assertEqual(matrix[2, 2], 1.0, "Bottom-right should be 1")
        
        # Off-diagonal elements typically small or zero
        self.assertAlmostEqual(matrix[0, 1], 0, places=1, msg="Skew should be near zero")
        self.assertEqual(matrix[1, 0], 0, "Should be zero")
        self.assertEqual(matrix[2, 0], 0, "Should be zero")
        self.assertEqual(matrix[2, 1], 0, "Should be zero")
        
        # Principal point should be reasonable (near image center)
        cx = matrix[0, 2]
        cy = matrix[1, 2]
        self.assertGreater(cx, 100, "cx should be reasonable")
        self.assertGreater(cy, 100, "cy should be reasonable")
        self.assertLess(cx, 2000, "cx should be reasonable")
        self.assertLess(cy, 2000, "cy should be reasonable")
        
        print(f"  ✓ Focal lengths: fx={matrix[0,0]:.2f}, fy={matrix[1,1]:.2f}")
        print(f"  ✓ Principal point: cx={cx:.2f}, cy={cy:.2f}")
        print(f"  ✓ Distortion coeffs: {dist.flatten()}")
        print("  ✓ Matrix values are reasonable")
    
    def test_combined_functionality(self):
        """Integration test: full workflow with hardware and calibration"""
        print("Testing complete workflow...")
        
        workflow_steps = []
        
        # Step 1: List cameras
        cameras = self.manager.list_cameras()
        self.assertGreater(len(cameras), 0)
        workflow_steps.append(f"List cameras: {len(cameras)} found")
        
        # Step 2: Load calibration
        success = self.manager.load_calibration(self.CALIBRATION_FILE)
        self.assertTrue(success)
        workflow_steps.append("Load calibration: SUCCESS")
        
        # Step 3: Connect
        success = self.manager.connect()
        self.assertTrue(success)
        workflow_steps.append("Connect camera: SUCCESS")
        
        # Step 4: Get info
        info = self.manager.get_camera_info()
        calib_info = self.manager.get_calibration_info()
        workflow_steps.append(f"Get info: {info['width']}x{info['height']}, calibrated={calib_info['calibrated']}")
        
        # Step 5: Capture frames
        frames_captured = 0
        for _ in range(5):
            frame = self.manager.capture_frame()
            if frame is not None:
                frames_captured += 1
        workflow_steps.append(f"Capture frames: {frames_captured}/5")
        
        # Step 6: Disconnect
        self.manager.disconnect()
        workflow_steps.append("Disconnect: SUCCESS")
        
        # Print workflow
        print("  Workflow steps:")
        for i, step in enumerate(workflow_steps, 1):
            print(f"    {i}. {step}")
        
        print("  ✓ Complete workflow successful")


def run_tests():
    """Run all hardware tests with calibration"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestCalibratedCameraManagerHardware)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\\n" + "="*60)
    print("CALIBRATED CAMERA HARDWARE TESTS SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*60)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
