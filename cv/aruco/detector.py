# cv/aruco/detector.py
import cv2
import numpy as np
import time
from typing import Optional, Dict, Tuple
from core.event_broker import event_aware
from .interfaces import IArUcoDetector
from .types import ArUcoMarker, ArUcoDetectionResult
from .events import ArUcoEvents
from .calculator import ArUcoCalculator


@event_aware()
class ArUcoDetector(IArUcoDetector):
    """ArUco marker detector - detects, calculates, emits events (no rendering)"""
    
    def __init__(self, dictionary=cv2.aruco.DICT_4X4_50, marker_size_mm: float = 15.0):
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary)
        self.detector_params = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.detector_params)
        
        self.marker_size_mm = marker_size_mm
        self.camera_matrix: Optional[np.ndarray] = None
        self.dist_coeffs: Optional[np.ndarray] = None
        self._previous_markers: Dict[int, ArUcoMarker] = {}
        self.calculator = ArUcoCalculator()
    
    def set_marker_size(self, size_mm: float) -> None:
        self.marker_size_mm = size_mm
    
    def set_calibration(self, camera_matrix: np.ndarray, dist_coeffs: np.ndarray) -> None:
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs
    
    def has_calibration(self) -> bool:
        return self.camera_matrix is not None and self.dist_coeffs is not None
    
    def detect(self, frame: np.ndarray) -> ArUcoDetectionResult:
        timestamp = time.time()
        frame_h, frame_w = frame.shape[:2]
        
        if self.has_calibration():
            cx = float(self.camera_matrix[0, 2])
            cy = float(self.camera_matrix[1, 2])
        else:
            cx = frame_w / 2.0
            cy = frame_h / 2.0
        
        camera_center = (cx, cy)
        
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            corners, ids, rejected = self.detector.detectMarkers(gray)
            
            markers = []
            
            if ids is not None and len(ids) > 0:
                for i, marker_id in enumerate(ids.flatten()):
                    marker = self._process_marker(marker_id, corners[i][0], camera_center)
                    markers.append(marker)
                
                result = ArUcoDetectionResult(
                    frame_shape=(frame_h, frame_w),
                    camera_center=camera_center,
                    markers=markers,
                    timestamp=timestamp,
                    has_calibration=self.has_calibration()
                )
                
                self.emit(ArUcoEvents.MARKERS_DETECTED, result)
                self._emit_tracking_events(markers)
                return result
            else:
                result = ArUcoDetectionResult(
                    frame_shape=(frame_h, frame_w),
                    camera_center=camera_center,
                    markers=[],
                    timestamp=timestamp,
                    has_calibration=self.has_calibration()
                )
                self.emit(ArUcoEvents.NO_MARKERS)
                self._emit_tracking_events([])
                return result
                
        except Exception as e:
            error_msg = f"Error detecting ArUco markers: {e}"
            self.emit(ArUcoEvents.DETECTION_ERROR, error_msg)
            raise
    
    def _process_marker(self, marker_id: int, corners: np.ndarray, camera_center: Tuple[float, float]) -> ArUcoMarker:
        center = self.calculator.calculate_marker_center(corners)
        dist_pixels = self.calculator.calculate_distance_to_center(center, camera_center)
        area = self.calculator.calculate_marker_area(corners)
        
        rvec, tvec, dist_z, dist_mm = None, None, None, None
        
        if self.has_calibration():
            try:
                rvec, tvec = self.calculator.calculate_marker_pose(
                    corners, self.marker_size_mm, self.camera_matrix, self.dist_coeffs
                )
                dist_z = self.calculator.calculate_distance_z(tvec)
                focal_length = self.camera_matrix[0, 0]
                dist_mm = self.calculator.pixel_distance_to_mm(dist_pixels, tvec, focal_length)
            except Exception:
                pass
        
        return ArUcoMarker(
            marker_id=int(marker_id),
            corners=corners,
            center=center,
            distance_to_camera_center=dist_pixels,
            distance_to_camera_center_mm=dist_mm,
            rvec=rvec,
            tvec=tvec,
            distance_z_mm=dist_z,
            area=area
        )
    
    def _emit_tracking_events(self, current_markers):
        current_ids = {m.marker_id for m in current_markers}
        previous_ids = set(self._previous_markers.keys())
        
        entered = current_ids - previous_ids
        for marker_id in entered:
            self.emit(ArUcoEvents.MARKER_ENTERED, marker_id)
        
        exited = previous_ids - current_ids
        for marker_id in exited:
            self.emit(ArUcoEvents.MARKER_EXITED, marker_id)
        
        for marker in current_markers:
            if marker.marker_id in previous_ids:
                prev = self._previous_markers[marker.marker_id]
                if marker.center != prev.center:
                    self.emit(ArUcoEvents.MARKER_MOVED, marker.marker_id, marker.center)
        
        self._previous_markers = {m.marker_id: m for m in current_markers}
