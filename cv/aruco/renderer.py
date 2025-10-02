# cv/aruco/renderer.py
import cv2
import numpy as np
from typing import Tuple
from .interfaces import IArUcoRenderer
from .types import ArUcoDetectionResult, ArUcoMarker


class ArUcoRenderer(IArUcoRenderer):
    """Renders ArUco information on frames (no detection, only drawing)"""
    
    def __init__(self):
        self.show_boxes = True
        self.show_ids = True
        self.show_distances = True
        self.show_camera_center = True
        self.show_center_lines = True
        
        self.box_color = (0, 255, 0)
        self.id_color = (255, 0, 0)
        self.center_color = (0, 255, 255)
        
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.font_scale = 0.5
        self.font_thickness = 2
    
    def set_options(self, **options) -> None:
        for key, value in options.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def render(self, frame: np.ndarray, detection: ArUcoDetectionResult) -> np.ndarray:
        output = frame.copy()
        
        if self.show_camera_center:
            self._draw_camera_center(output, detection.camera_center)
        
        for marker in detection.markers:
            self._draw_marker(output, marker, detection)
        
        self._draw_stats(output, detection)
        return output
    
    def _draw_camera_center(self, frame: np.ndarray, center: Tuple[float, float]):
        cx, cy = int(center[0]), int(center[1])
        size = 20
        thickness = 2
        color = self.center_color
        
        cv2.line(frame, (cx - size, cy), (cx + size, cy), color, thickness)
        cv2.line(frame, (cx, cy - size), (cx, cy + size), color, thickness)
        cv2.circle(frame, (cx, cy), 5, color, -1)
    
    def _draw_marker(self, frame: np.ndarray, marker: ArUcoMarker, detection: ArUcoDetectionResult):
        if self.show_boxes:
            self._draw_box(frame, marker)
        if self.show_ids:
            self._draw_id(frame, marker)
        if self.show_distances:
            self._draw_distances(frame, marker)
        if self.show_center_lines:
            self._draw_center_line(frame, marker, detection.camera_center)
    
    def _draw_box(self, frame: np.ndarray, marker: ArUcoMarker):
        corners = marker.corners.astype(int)
        cv2.polylines(frame, [corners], True, self.box_color, 2)
    
    def _draw_id(self, frame: np.ndarray, marker: ArUcoMarker):
        cx, cy = int(marker.center[0]), int(marker.center[1])
        text = f"ID:{marker.marker_id}"
        
        (tw, th), _ = cv2.getTextSize(text, self.font, self.font_scale, self.font_thickness)
        cv2.rectangle(frame, (cx - tw//2 - 5, cy - th - 10), (cx + tw//2 + 5, cy - 5), (0, 0, 0), -1)
        cv2.putText(frame, text, (cx - tw//2, cy - 10), self.font, self.font_scale, self.id_color, self.font_thickness)
    
    def _draw_distances(self, frame: np.ndarray, marker: ArUcoMarker):
        cx, cy = int(marker.center[0]), int(marker.center[1])
        dist_px = marker.distance_to_camera_center
        text = f"{dist_px:.1f}px"
        
        if marker.distance_to_camera_center_mm is not None:
            dist_mm = marker.distance_to_camera_center_mm
            text += f" ({dist_mm:.1f}mm)"
        
        if marker.distance_z_mm is not None:
            text += f" Z:{marker.distance_z_mm:.1f}mm"
        
        cv2.putText(frame, text, (cx, cy + 20), self.font, self.font_scale * 0.8, (255, 255, 255), 1)
    
    def _draw_center_line(self, frame: np.ndarray, marker: ArUcoMarker, camera_center: Tuple[float, float]):
        pt1 = (int(marker.center[0]), int(marker.center[1]))
        pt2 = (int(camera_center[0]), int(camera_center[1]))
        cv2.line(frame, pt1, pt2, (255, 200, 0), 1, cv2.LINE_AA)
    
    def _draw_stats(self, frame: np.ndarray, detection: ArUcoDetectionResult):
        count = len(detection.markers)
        text = f"Markers: {count}"
        cv2.putText(frame, text, (10, 30), self.font, 0.7, (255, 255, 255), 2)
