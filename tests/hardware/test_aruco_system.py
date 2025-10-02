#!/usr/bin/env python3
# tmp/test_aruco_system.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cv import CalibratedCameraManager
from cv.aruco import ArUcoDetector, ArUcoRenderer, ArUcoEvents
import cv2

def test_aruco_detection_only():
    print("Testing ArUco detection...")
    camera = CalibratedCameraManager(camera_id=0)
    camera.load_calibration("data/calibration/endo.npz")
    camera.connect()
    detector = ArUcoDetector(marker_size_mm=15.0)
    detector.set_calibration(*camera.get_calibration())
    detector.listen(ArUcoEvents.MARKERS_DETECTED, lambda r: print(f"  ✓ {len(r.markers)} markers"))
    frame = camera.capture_frame()
    result = detector.detect(frame)
    camera.disconnect()
    print(f"Result: {len(result.markers)} markers\n")

def test_aruco_with_rendering():
    print("Testing ArUco rendering...")
    camera = CalibratedCameraManager(camera_id=0)
    camera.load_calibration("data/calibration/endo.npz")
    camera.connect()
    detector = ArUcoDetector(marker_size_mm=15.0)
    detector.set_calibration(*camera.get_calibration())
    renderer = ArUcoRenderer()
    frame = camera.capture_frame()
    detection = detector.detect(frame)
    annotated = renderer.render(frame, detection)
    cv2.imwrite("../tmp/aruco_test_output.jpg", annotated)
    print(f"  ✓ Saved tmp/aruco_test_output.jpg\n")
    camera.disconnect()

if __name__ == "__main__":
    print("="*60)
    print("ArUco System Tests")
    print("="*60)
    test_aruco_detection_only()
    test_aruco_with_rendering()
    print("✓ Tests completed")
