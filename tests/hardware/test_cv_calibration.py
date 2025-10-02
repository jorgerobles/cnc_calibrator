#!/usr/bin/env python3
# tmp/test_cv_calibration.py
# Tests for camera calibration functionality
import unittest
import sys
import os
import numpy as np
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cv import CalibratedCameraManager, CameraEvents


class TestCameraCalibration(unittest.TestCase):
    """Tests for calibration functionality using CalibratedCameraManager"""
    
    def setUp(self):
        """Create calibrated camera manager for each test"""
        self.manager = CalibratedCameraManager(camera_id=0, resolution=(640, 480))
        
        # Create temporary file for calibration
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.npz', delete=False)
        self.test_calib_file = self.temp_file.name
        self.temp_file.close()
        
        # Sample calibration data
        self.sample_matrix = np.array([
            [800.0, 0.0, 320.0],
            [0.0, 800.0, 240.0],
            [0.0, 0.0, 1.0]
        ])
        self.sample_dist = np.array([[0.1, -0.2, 0.0, 0.0, 0.0]])
    
    def tearDown(self):
        """Clean up temporary files"""
        if os.path.exists(self.test_calib_file):
            os.remove(self.test_calib_file)
    
    def test_not_calibrated_initially(self):
        """CalibratedCameraManager should start uncalibrated"""
        print("Testing initial calibration state...")
        self.assertFalse(self.manager.is_calibrated())
        print("  ✓ Manager starts uncalibrated")
    
    def test_has_calibration_methods(self):
        """Verify calibration methods are injected"""
        print("Testing calibration methods exist...")
        self.assertTrue(hasattr(self.manager, 'load_calibration'))
        self.assertTrue(hasattr(self.manager, 'save_calibration'))
        self.assertTrue(hasattr(self.manager, 'is_calibrated'))
        self.assertTrue(hasattr(self.manager, 'get_calibration'))
        self.assertTrue(hasattr(self.manager, 'get_calibration_info'))
        print("  ✓ All calibration methods present")
    
    def test_load_calibration(self):
        """Test loading calibration from file"""
        print("Testing calibration loading...")
        
        # Create calibration file
        np.savez(self.test_calib_file,
                camera_matrix=self.sample_matrix,
                dist_coeffs=self.sample_dist)
        
        # Load it
        success = self.manager.load_calibration(self.test_calib_file)
        self.assertTrue(success, "Loading should succeed")
        self.assertTrue(self.manager.is_calibrated(), "Should be calibrated after loading")
        
        # Verify data
        matrix, dist = self.manager.get_calibration()
        np.testing.assert_array_equal(matrix, self.sample_matrix)
        np.testing.assert_array_equal(dist, self.sample_dist)
        
        print(f"  ✓ Loaded calibration: matrix shape {matrix.shape}, dist shape {dist.shape}")
    
    def test_load_invalid_file(self):
        """Test loading from non-existent file"""
        print("Testing invalid file loading...")
        
        success = self.manager.load_calibration("nonexistent_file.npz")
        self.assertFalse(success, "Loading invalid file should fail")
        self.assertFalse(self.manager.is_calibrated(), "Should not be calibrated")
        
        print("  ✓ Invalid file handled correctly")
    
    def test_save_calibration(self):
        """Test saving calibration to file"""
        print("Testing calibration saving...")
        
        # Set calibration data manually
        self.manager.camera_matrix = self.sample_matrix
        self.manager.dist_coeffs = self.sample_dist
        
        # Save it
        success = self.manager.save_calibration(self.test_calib_file)
        self.assertTrue(success, "Saving should succeed")
        self.assertTrue(os.path.exists(self.test_calib_file), "File should be created")
        
        # Load in new manager to verify
        manager2 = CalibratedCameraManager()
        manager2.load_calibration(self.test_calib_file)
        
        matrix2, dist2 = manager2.get_calibration()
        np.testing.assert_array_equal(matrix2, self.sample_matrix)
        np.testing.assert_array_equal(dist2, self.sample_dist)
        
        print("  ✓ Calibration saved and reloaded successfully")
    
    def test_save_without_calibration(self):
        """Test saving when no calibration loaded"""
        print("Testing save without calibration...")
        
        success = self.manager.save_calibration(self.test_calib_file)
        self.assertFalse(success, "Saving without calibration should fail")
        
        print("  ✓ Save without calibration handled correctly")
    
    def test_get_calibration_info(self):
        """Test getting calibration information"""
        print("Testing calibration info...")
        
        # Initially uncalibrated
        info = self.manager.get_calibration_info()
        self.assertFalse(info['calibrated'])
        self.assertIsNone(info['file'])
        print(f"  ✓ Uncalibrated info: {info}")
        
        # Load calibration
        np.savez(self.test_calib_file,
                camera_matrix=self.sample_matrix,
                dist_coeffs=self.sample_dist)
        self.manager.load_calibration(self.test_calib_file)
        
        # Check info again
        info = self.manager.get_calibration_info()
        self.assertTrue(info['calibrated'])
        self.assertEqual(info['file'], self.test_calib_file)
        self.assertEqual(info['matrix_shape'], (3, 3))
        self.assertEqual(info['distortion_count'], 5)
        print(f"  ✓ Calibrated info: {info}")
    
    def test_calibration_events(self):
        """Test that calibration emits events"""
        print("Testing calibration events...")
        
        events_received = []
        
        def on_loaded(file_path):
            events_received.append(('loaded', file_path))
        
        def on_saved(file_path):
            events_received.append(('saved', file_path))
        
        # Listen to events
        self.manager.listen(CameraEvents.CALIBRATION_LOADED, on_loaded)
        self.manager.listen(CameraEvents.CALIBRATION_SAVED, on_saved)
        
        # Create and load calibration
        np.savez(self.test_calib_file,
                camera_matrix=self.sample_matrix,
                dist_coeffs=self.sample_dist)
        self.manager.load_calibration(self.test_calib_file)
        
        # Check loaded event
        self.assertEqual(len(events_received), 1)
        self.assertEqual(events_received[0][0], 'loaded')
        self.assertEqual(events_received[0][1], self.test_calib_file)
        
        # Save and check saved event
        temp_file2 = tempfile.NamedTemporaryFile(suffix='.npz', delete=False)
        temp_file2.close()
        self.manager.save_calibration(temp_file2.name)
        
        self.assertEqual(len(events_received), 2)
        self.assertEqual(events_received[1][0], 'saved')
        
        # Cleanup
        os.remove(temp_file2.name)
        
        print(f"  ✓ Received events: {[e[0] for e in events_received]}")
    
    def test_get_calibration_matrices(self):
        """Test getting calibration matrices"""
        print("Testing calibration matrix retrieval...")
        
        # Initially None
        matrix, dist = self.manager.get_calibration()
        self.assertIsNone(matrix)
        self.assertIsNone(dist)
        
        # Load calibration
        np.savez(self.test_calib_file,
                camera_matrix=self.sample_matrix,
                dist_coeffs=self.sample_dist)
        self.manager.load_calibration(self.test_calib_file)
        
        # Should have matrices now
        matrix, dist = self.manager.get_calibration()
        self.assertIsNotNone(matrix)
        self.assertIsNotNone(dist)
        self.assertEqual(matrix.shape, (3, 3))
        self.assertEqual(dist.shape, (1, 5))
        
        print("  ✓ Calibration matrices retrieved correctly")


def run_tests():
    """Run all calibration tests"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestCameraCalibration)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*60)
    print("CALIBRATION TESTS SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*60)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("="*60)
    print("CAMERA CALIBRATION TESTS")
    print("Testing CalibratedCameraManager decorator functionality")
    print("="*60 + "\n")
    
    success = run_tests()
    sys.exit(0 if success else 1)
