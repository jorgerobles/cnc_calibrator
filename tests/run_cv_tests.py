#!/usr/bin/env python3
# tmp/run_cv_tests.py
# Hardware tests for CameraManager - requires physical camera
import unittest
import sys
import os
import time
import cv2

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cv import CameraManager, CameraEvents


class TestCameraManagerHardware(unittest.TestCase):
    """Hardware tests for CameraManager - requires physical camera connected"""
    
    @classmethod
    def setUpClass(cls):
        """Check if camera is available before running tests"""
        print("\n" + "="*60)
        print("HARDWARE TEST - Checking for camera availability")
        print("="*60)
        
        # Try to detect camera
        cap = cv2.VideoCapture(0)
        cls.camera_available = cap.isOpened()
        if cls.camera_available:
            ret, _ = cap.read()
            cls.camera_available = ret
        cap.release()
        
        if not cls.camera_available:
            raise unittest.SkipTest("No camera detected - skipping hardware tests")
        
        print("✓ Camera detected - running hardware tests\n")
    
    def setUp(self):
        """Create camera manager for each test"""
        self.manager = CameraManager(camera_id=0, resolution=(640, 480))
        self.events_received = []
        
    def tearDown(self):
        """Clean up after each test"""
        if self.manager.is_connected:
            self.manager.disconnect()
        time.sleep(0.1)  # Allow camera to fully release
    
    def test_list_cameras(self):
        """Test camera enumeration"""
        print("Testing camera enumeration...")
        cameras = self.manager.list_cameras()
        
        self.assertIsInstance(cameras, list, "list_cameras should return a list")
        self.assertGreater(len(cameras), 0, "Should detect at least one camera")
        
        # Verify structure
        first_camera = cameras[0]
        self.assertIn('index', first_camera)
        self.assertIn('name', first_camera)
        self.assertIn('backend', first_camera)
        self.assertIn('width', first_camera)
        self.assertIn('height', first_camera)
        
        print(f"  ✓ Found {len(cameras)} camera(s)")
        for cam in cameras:
            print(f"    - {cam['name']}: {cam['width']}x{cam['height']} ({cam['backend']})")
    
    def test_connection_lifecycle(self):
        """Test connect -> capture -> disconnect"""
        print("Testing connection lifecycle...")
        
        # Initially disconnected
        self.assertFalse(self.manager.is_connected, "Should start disconnected")
        
        # Connect
        success = self.manager.connect()
        self.assertTrue(success, "Connection should succeed")
        self.assertTrue(self.manager.is_connected, "Should be connected after connect()")
        print("  ✓ Connected successfully")
        
        # Capture frame
        frame = self.manager.capture_frame()
        self.assertIsNotNone(frame, "Should capture frame")
        self.assertEqual(len(frame.shape), 3, "Frame should be 3D (H,W,C)")
        self.assertGreater(frame.shape[0], 0, "Frame height should be > 0")
        self.assertGreater(frame.shape[1], 0, "Frame width should be > 0")
        print(f"  ✓ Captured frame: {frame.shape}")
        
        # Disconnect
        self.manager.disconnect()
        self.assertFalse(self.manager.is_connected, "Should be disconnected after disconnect()")
        print("  ✓ Disconnected successfully")
    
    def test_multiple_captures(self):
        """Test capturing multiple frames"""
        print("Testing multiple frame captures...")
        
        self.manager.connect()
        
        frame_count = 10
        successful_captures = 0
        
        for i in range(frame_count):
            frame = self.manager.capture_frame()
            if frame is not None:
                successful_captures += 1
        
        success_rate = (successful_captures / frame_count) * 100
        self.assertGreater(success_rate, 90, f"Success rate {success_rate}% should be > 90%")
        
        print(f"  ✓ Captured {successful_captures}/{frame_count} frames ({success_rate:.1f}%)")
        
        self.manager.disconnect()
    
    def test_resolution_setting(self):
        """Test changing resolution"""
        print("Testing resolution setting...")
        
        self.manager.connect()
        
        # Try to set resolution
        target_width, target_height = 320, 240
        success = self.manager.set_resolution(target_width, target_height)
        
        # Get actual resolution
        info = self.manager.get_camera_info()
        actual_width = info['width']
        actual_height = info['height']
        
        print(f"  ✓ Requested: {target_width}x{target_height}, Got: {actual_width}x{actual_height}")
        
        # Note: Some cameras may not support exact resolution
        self.assertIsInstance(success, bool, "set_resolution should return bool")
        
        self.manager.disconnect()
    
    def test_camera_info(self):
        """Test getting camera information"""
        print("Testing camera info...")
        
        # Info while disconnected
        info = self.manager.get_camera_info()
        self.assertEqual(info['camera_id'], 0)
        self.assertFalse(info['connected'])
        print(f"  ✓ Info while disconnected: {info}")
        
        # Info while connected
        self.manager.connect()
        info = self.manager.get_camera_info()
        self.assertEqual(info['camera_id'], 0)
        self.assertTrue(info['connected'])
        self.assertIn('width', info)
        self.assertIn('height', info)
        self.assertIn('fps', info)
        self.assertIn('backend', info)
        print(f"  ✓ Info while connected: {info['width']}x{info['height']} @ {info['fps']}fps ({info['backend']})")
        
        self.manager.disconnect()
    
    def test_event_emission(self):
        """Test that events are emitted correctly"""
        print("Testing event emission...")
        
        # Listen to events
        def on_connected(success):
            self.events_received.append(('connected', success))
        
        def on_disconnected():
            self.events_received.append(('disconnected',))
        
        def on_frame_captured(frame):
            self.events_received.append(('frame_captured', frame is not None))
        
        self.manager.listen(CameraEvents.CONNECTED, on_connected)
        self.manager.listen(CameraEvents.DISCONNECTED, on_disconnected)
        self.manager.listen(CameraEvents.FRAME_CAPTURED, on_frame_captured)
        
        # Connect
        self.manager.connect()
        time.sleep(0.05)  # Allow event processing
        
        # Capture
        self.manager.capture_frame()
        time.sleep(0.05)
        
        # Disconnect
        self.manager.disconnect()
        time.sleep(0.05)
        
        # Verify events
        event_types = [e[0] for e in self.events_received]
        self.assertIn('connected', event_types, "Should emit CONNECTED event")
        self.assertIn('disconnected', event_types, "Should emit DISCONNECTED event")
        self.assertIn('frame_captured', event_types, "Should emit FRAME_CAPTURED event")
        
        print(f"  ✓ Received events: {event_types}")
    
    def test_reconnection(self):
        """Test disconnect and reconnect"""
        print("Testing reconnection...")
        
        # First connection
        self.manager.connect()
        frame1 = self.manager.capture_frame()
        self.assertIsNotNone(frame1)
        print("  ✓ First connection successful")
        
        # Disconnect
        self.manager.disconnect()
        time.sleep(0.1)
        
        # Reconnect
        success = self.manager.connect()
        self.assertTrue(success, "Reconnection should succeed")
        frame2 = self.manager.capture_frame()
        self.assertIsNotNone(frame2)
        print("  ✓ Reconnection successful")
        
        self.manager.disconnect()
    
    def test_capture_without_connection(self):
        """Test that capture fails gracefully without connection"""
        print("Testing capture without connection...")
        
        # Try to capture without connecting
        frame = self.manager.capture_frame()
        self.assertIsNone(frame, "Should return None when not connected")
        print("  ✓ Correctly returns None when disconnected")


def run_tests():
    """Run all tests with verbose output"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestCameraManagerHardware)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*60)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
