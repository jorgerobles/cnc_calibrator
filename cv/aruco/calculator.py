# cv/aruco/calculator.py
import numpy as np
import cv2
from typing import Tuple
import math


class ArUcoCalculator:
    """Pure geometric calculations for ArUco - stateless"""
    
    @staticmethod
    def calculate_distance_to_center(point: Tuple[float, float],
                                     camera_center: Tuple[float, float]) -> float:
        dx = point[0] - camera_center[0]
        dy = point[1] - camera_center[1]
        return math.sqrt(dx**2 + dy**2)
    
    @staticmethod
    def calculate_marker_center(corners: np.ndarray) -> Tuple[float, float]:
        center_x = corners[:, 0].mean()
        center_y = corners[:, 1].mean()
        return (float(center_x), float(center_y))
    
    @staticmethod
    def calculate_marker_area(corners: np.ndarray) -> float:
        x = corners[:, 0]
        y = corners[:, 1]
        return 0.5 * abs(sum(x[i]*y[(i+1)%4] - x[(i+1)%4]*y[i] for i in range(4)))
    
    @staticmethod
    def calculate_marker_pose(corners: np.ndarray,
                             marker_size_mm: float,
                             camera_matrix: np.ndarray,
                             dist_coeffs: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        half_size = marker_size_mm / 2.0
        obj_points = np.array([
            [-half_size,  half_size, 0],
            [ half_size,  half_size, 0],
            [ half_size, -half_size, 0],
            [-half_size, -half_size, 0]
        ], dtype=np.float32)
        
        success, rvec, tvec = cv2.solvePnP(
            obj_points,
            corners,
            camera_matrix,
            dist_coeffs,
            flags=cv2.SOLVEPNP_IPPE_SQUARE
        )
        
        if not success:
            raise ValueError("solvePnP failed")
        
        return rvec, tvec
    
    @staticmethod
    def calculate_distance_z(tvec: np.ndarray) -> float:
        return float(tvec[2][0])
    
    @staticmethod
    def pixel_distance_to_mm(pixel_distance: float,
                            tvec: np.ndarray,
                            focal_length: float) -> float:
        z = abs(tvec[2][0])
        if focal_length <= 0 or z <= 0:
            return 0.0
        return (pixel_distance * z) / focal_length
